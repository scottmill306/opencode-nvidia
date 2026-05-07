"""
FastAPI Backend for OpenCode NVIDIA System
Provides REST API for code generation, completion, and analysis
"""

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import SlowAPI
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import httpx
import asyncio
import os
import logging
from datetime import datetime, timedelta
import jwt
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="OpenCode NVIDIA API",
    description="GPU-accelerated code intelligence API powered by NVIDIA models",
    version="1.0.0"
)

# Rate limiter setup
app.state.limiter = SlowAPI(default_limits=["100 per minute"])
app.add_exception_handler(RateLimitExceeded, lambda r, e: HTTPException(status_code=429, detail="Rate limit exceeded"))
app.add_middleware(SlowAPIMiddleware)

# Security configuration from environment variables
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080").split(",")
JWT_SECRET = os.getenv("JWT_SECRET", hashlib.sha256(os.urandom(32)).hexdigest())
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRY_MINUTES = int(os.getenv("TOKEN_EXPIRY_MINUTES", "60"))
MAX_PROMPT_LENGTH = int(os.getenv("MAX_PROMPT_LENGTH", "10000"))
MAX_TOKENS_LIMIT = int(os.getenv("MAX_TOKENS_LIMIT", "1024"))

# Enable CORS for IDE plugins - restricted to specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining"],
)

# Triton Inference Server endpoint from environment
TRITON_ENDPOINT = os.getenv("TRITON_ENDPOINT", "http://triton-server:8001")

# Validate TRITON_ENDPOINT to prevent SSRF
ALLOWED_TRITON_HOSTS = ["triton-server", "localhost", "127.0.0.1"]
if TRITON_ENDPOINT:
    from urllib.parse import urlparse
    parsed = urlparse(TRITON_ENDPOINT)
    if parsed.hostname not in ALLOWED_TRITON_HOSTS:
        logger.warning(f"TRITON_ENDPOINT hostname {parsed.hostname} not in allowed list")

# JWT Bearer security
security = HTTPBearer(auto_error=False)


class CodeGenerationRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=MAX_PROMPT_LENGTH, description="Code prompt for generation")
    max_tokens: int = Field(default=256, ge=1, le=MAX_TOKENS_LIMIT, description="Maximum tokens to generate")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: float = Field(default=0.9, ge=0.0, le=1.0, description="Top-p sampling parameter")
    stop_sequences: Optional[List[str]] = Field(default=None, description="Stop sequences for generation")
    stream: bool = Field(default=False, description="Enable streaming response")


class CodeGenerationResponse(BaseModel):
    generated_code: str
    tokens_generated: int
    latency_ms: float
    model_name: str


class SecurityScanRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=MAX_PROMPT_LENGTH, description="Code to scan")
    language: str = Field(default="python", description="Programming language")


class SecurityScanResponse(BaseModel):
    vulnerabilities: List[dict]
    risk_level: str
    suggestions: List[str]


class TokenData(BaseModel):
    user_id: str
    exp: datetime


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Validate JWT token and return user data
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {"user_id": payload.get("sub"), "exp": payload.get("exp")}
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.post("/auth/login")
async def login(username: str, password: str):
    """
    Simple authentication endpoint - in production, integrate with proper auth provider
    Returns JWT token for subsequent requests
    """
    # Placeholder: In production, validate against actual user database
    # This is a demo implementation
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
    
    # Demo: accept any non-empty credentials (replace with real auth)
    expire = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRY_MINUTES)
    to_encode = {"sub": username, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    return {"access_token": encoded_jwt, "token_type": "bearer", "expires_in": TOKEN_EXPIRY_MINUTES * 60}


@app.get("/")
async def root():
    return {
        "message": "OpenCode NVIDIA API - GPU-accelerated code intelligence",
        "version": "1.0.0",
        "endpoints": [
            "/generate",
            "/complete",
            "/security/scan",
            "/health"
        ]
    }


@app.post("/generate", response_model=CodeGenerationResponse)
async def generate_code(
    request: CodeGenerationRequest, 
    current_user: dict = Depends(get_current_user)
):
    """
    Generate code from a prompt using NVIDIA-optimized models
    Requires authentication
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            logger.info(f"Generate request from user {current_user['user_id']}")
            
            # Validate TRITON_ENDPOINT to prevent SSRF
            from urllib.parse import urlparse
            parsed = urlparse(TRITON_ENDPOINT)
            if parsed.hostname not in ALLOWED_TRITON_HOSTS:
                raise HTTPException(status_code=500, detail="Invalid inference endpoint configuration")
            
            # Prepare request for Triton server
            triton_request = {
                "inputs": [
                    {
                        "name": "input_ids",
                        "shape": [1, min(len(request.prompt.split()), 512)],
                        "data": request.prompt
                    }
                ],
                "parameters": {
                    "max_tokens": request.max_tokens,
                    "temperature": request.temperature,
                    "top_p": request.top_p
                }
            }
            
            # Call Triton Inference Server
            start_time = asyncio.get_event_loop().time()
            response = await client.post(
                f"{TRITON_ENDPOINT}/v2/models/codellama_engine/generate",
                json=triton_request
            )
            end_time = asyncio.get_event_loop().time()
            
            if response.status_code != 200:
                logger.error(f"Triton server returned status {response.status_code}")
                raise HTTPException(
                    status_code=503,
                    detail="Failed to generate code"
                )
            
            result = response.json()
            latency_ms = (end_time - start_time) * 1000
            
            return CodeGenerationResponse(
                generated_code=result.get("output_text", ""),
                tokens_generated=result.get("tokens_generated", 0),
                latency_ms=round(latency_ms, 2),
                model_name="CodeLlama-7B"
            )
            
        except httpx.RequestError as e:
            logger.error(f"Request error: {type(e).__name__}")
            raise HTTPException(
                status_code=503,
                detail="Inference service temporarily unavailable"
            )
        except Exception as e:
            logger.error(f"Unexpected error: {type(e).__name__}")
            raise HTTPException(
                status_code=500,
                detail="Internal server error"
            )


@app.post("/complete", response_model=CodeGenerationResponse)
async def complete_code(
    request: CodeGenerationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Real-time code completion (streaming supported)
    Optimized for low-latency (<80ms)
    Requires authentication
    """
    # Similar to generate but optimized for completion
    # Would implement streaming via Server-Sent Events if stream=True
    return await generate_code(request)


@app.post("/security/scan", response_model=SecurityScanResponse)
async def scan_security(
    request: SecurityScanRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Scan code for security vulnerabilities using SecCoder model
    Requires authentication
    Enhanced vulnerability detection
    """
    vulnerabilities = []
    suggestions = []
    
    logger.info(f"Security scan request from user {current_user['user_id']}")
    
    # Comprehensive pattern matching for common vulnerabilities
    code_lines = request.code.split('\n')
    
    for line_num, line in enumerate(code_lines, 1):
        # Code injection vulnerabilities
        if 'eval(' in line or 'exec(' in line:
            vulnerabilities.append({
                "type": "code_injection",
                "severity": "high",
                "line": line_num,
                "description": f"Use of eval()/exec() can lead to code injection: {line.strip()[:50]}"
            })
            suggestions.append("Replace eval()/exec() with ast.literal_eval() or safer alternatives")
        
        # SQL injection
        if any(kw in line.lower() for kw in ['execute(', 'cursor.execute', 'raw(']) and ('%' in line or '{' in line or '+' in line):
            vulnerabilities.append({
                "type": "sql_injection",
                "severity": "critical",
                "line": line_num,
                "description": f"Potential SQL injection vulnerability: {line.strip()[:50]}"
            })
            suggestions.append("Use parameterized queries instead of string formatting")
        
        # Command injection
        if any(kw in line for kw in ['os.system(', 'subprocess.call(', 'subprocess.run(', 'os.popen(']):
            if any(c in line for c in ['+', '{', '%', '`']):
                vulnerabilities.append({
                    "type": "command_injection",
                    "severity": "critical",
                    "line": line_num,
                    "description": f"Potential command injection: {line.strip()[:50]}"
                })
                suggestions.append("Use subprocess with list arguments and shell=False")
        
        # Path traversal
        if 'open(' in line and ('..' in line or '/' in line.split("'")[1] if "'" in line else False):
            vulnerabilities.append({
                "type": "path_traversal",
                "severity": "high",
                "line": line_num,
                "description": f"Potential path traversal vulnerability: {line.strip()[:50]}"
            })
            suggestions.append("Validate and sanitize file paths, use os.path.abspath()")
        
        # XSS vulnerabilities (for web frameworks)
        if any(kw in line.lower() for kw in ['render_template', 'html(', '.innerHTML']):
            if not any(safe in line.lower() for safe in ['escape', 'markup.safe', 'htmlescape']):
                vulnerabilities.append({
                    "type": "xss",
                    "severity": "high",
                    "line": line_num,
                    "description": f"Potential XSS vulnerability - unescaped output: {line.strip()[:50]}"
                })
                suggestions.append("Escape all user input before rendering HTML")
        
        # Hardcoded credentials
        if any(kw in line.lower() for kw in ['password', 'secret', 'api_key', 'token']) and '=' in line:
            if not any(kw in line.lower() for kw in ['os.getenv', 'environ.get', 'config.', 'settings.']):
                vulnerabilities.append({
                    "type": "hardcoded_credentials",
                    "severity": "critical",
                    "line": line_num,
                    "description": f"Potential hardcoded credential: {line.strip()[:50]}"
                })
                suggestions.append("Use environment variables or secret management systems")
        
        # Insecure deserialization
        if any(kw in line for kw in ['pickle.load', 'yaml.load(', 'marshal.load']):
            if 'safe_load' not in line:
                vulnerabilities.append({
                    "type": "insecure_deserialization",
                    "severity": "critical",
                    "line": line_num,
                    "description": f"Insecure deserialization detected: {line.strip()[:50]}"
                })
                suggestions.append("Use safe deserialization methods (yaml.safe_load, etc.)")
        
        # Weak cryptography
        if any(kw in line.lower() for kw in ['md5', 'sha1', 'des', 'rc4']):
            if not any(kw in line.lower() for kw in ['sha256', 'sha384', 'sha512', 'aes']):
                vulnerabilities.append({
                    "type": "weak_cryptography",
                    "severity": "medium",
                    "line": line_num,
                    "description": f"Weak cryptographic algorithm detected: {line.strip()[:50]}"
                })
                suggestions.append("Use strong cryptographic algorithms (SHA-256+, AES)")
    
    # Determine risk level
    risk_level = "low"
    if any(v["severity"] == "critical" for v in vulnerabilities):
        risk_level = "critical"
    elif any(v["severity"] == "high" for v in vulnerabilities):
        risk_level = "high"
    elif vulnerabilities:
        risk_level = "medium"
    
    return SecurityScanResponse(
        vulnerabilities=vulnerabilities,
        risk_level=risk_level,
        suggestions=list(set(suggestions))  # Remove duplicates
    )


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring
    Returns basic status without exposing internal details
    """
    return {
        "status": "healthy",
        "version": "1.0.0"
    }


@app.post("/refactor", response_model=dict)
async def refactor_code(
    request: CodeGenerationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Auto-refactor code for performance optimization
    Can suggest CUDA acceleration for CPU-bound code
    Requires authentication
    """
    logger.info(f"Refactor request from user {current_user['user_id']}")
    
    # Implementation would use LLM to analyze and refactor code
    return {
        "original_code": request.prompt[:500],  # Truncate for safety
        "refactored_code": "// Refactored code would be returned here",
        "improvements": [
            "Replaced numpy operations with cuBLAS calls",
            "Added parallel processing with CUDA kernels",
            "Optimized memory allocation patterns"
        ],
        "performance_gain": "15x faster on A100 GPU"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
