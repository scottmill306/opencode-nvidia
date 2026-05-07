# Deployment Guide - OpenCode NVIDIA System

## 🚀 Quick Start

### 1. Environment Setup

The `.env` file has been automatically generated with secure random values. **Save these values securely!**

```bash
# View your generated credentials (for initial setup only)
cat .env
```

**⚠️ IMPORTANT:** For production, update these values:
- `ALLOWED_ORIGINS` - Set to your actual domain(s)
- Generate new secrets if this file is committed to version control

### 2. Docker Compose Deployment

```bash
# Start all services
docker-compose --env-file .env up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f backend
```

### 3. Verify Security Configuration

Run the security verification script:

```bash
python scripts/verify_security.py
```

### 4. Test Authentication

```bash
# Login to get JWT token
curl -X POST "http://localhost:8080/auth/login?username=testuser&password=testpass" \
  -H "Content-Type: application/json"

# Use token for authenticated requests
TOKEN="your-token-here"
curl -X POST "http://localhost:8080/generate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"prompt": "def hello():", "max_tokens": 50}'
```

## 🔐 Security Checklist

### Pre-Deployment

- [ ] `.env` file created with secure values
- [ ] Default MinIO credentials changed
- [ ] JWT secret is cryptographically random (64+ characters)
- [ ] ALLOWED_ORIGINS restricted to your domains
- [ ] HTTPS certificates configured (production only)

### Post-Deployment

- [ ] All endpoints require authentication (except `/health` and `/auth/login`)
- [ ] Rate limiting is active (100 req/min default)
- [ ] CORS properly configured
- [ ] No sensitive data in error messages
- [ ] Containers running as non-root users

### VSCode Extension Setup

1. Open VSCode
2. Install dependencies: `cd plugins/vscode && npm install`
3. Configure extension:
   - Open Settings → OpenCode
   - Set API Endpoint: `https://your-domain.com:8080` (production)
   - Or use default: `https://localhost:8080` (development)
4. First API call will prompt for login
5. Token stored securely in VSCode configuration

## 🛡️ Security Features Implemented

| Feature | Status | Description |
|---------|--------|-------------|
| JWT Authentication | ✅ | All sensitive endpoints protected |
| Rate Limiting | ✅ | 100 requests/minute per IP |
| CORS Restrictions | ✅ | Whitelist-based origin control |
| Input Validation | ✅ | Pydantic constraints on all inputs |
| XSS Protection | ✅ | HTML sanitization in webviews |
| SSRF Prevention | ✅ | Endpoint allowlist validation |
| Non-root Containers | ✅ | All services run as limited users |
| Resource Limits | ✅ | CPU/memory constraints in Docker |
| Error Handling | ✅ | Generic messages, detailed server logs |
| Secret Management | ✅ | Environment variables, no hardcoded values |

## 🔧 Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET` | Auto-generated | Secret key for JWT tokens |
| `MINIO_ROOT_USER` | Auto-generated | MinIO admin username |
| `MINIO_ROOT_PASSWORD` | Auto-generated | MinIO admin password |
| `ALLOWED_ORIGINS` | localhost only | CORS whitelist (comma-separated) |
| `TOKEN_EXPIRY_MINUTES` | 60 | JWT token validity period |
| `MAX_PROMPT_LENGTH` | 10000 | Maximum input length |
| `MAX_TOKENS_LIMIT` | 1024 | Maximum tokens to generate |
| `TRITON_ENDPOINT` | internal URL | Triton server endpoint |

### Docker Compose Overrides

Create `docker-compose.override.yml` for custom configurations:

```yaml
version: '3.8'
services:
  backend:
    environment:
      - TOKEN_EXPIRY_MINUTES=120
      - MAX_PROMPT_LENGTH=20000
```

## 📊 Monitoring & Logging

### Health Checks

```bash
# Backend health
curl http://localhost:8080/health

# Triton server health
curl http://localhost:8000/v2/health/ready

# Container status
docker-compose ps
```

### Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# Last 100 lines
docker-compose logs --tail=100 backend
```

## 🚨 Troubleshooting

### Authentication Issues

```bash
# Clear stored token in VSCode
# Settings → OpenCode → Auth Token → Delete value
# Then re-login through the extension
```

### CORS Errors

Check `ALLOWED_ORIGINS` in `.env`:
```bash
# For development
ALLOWED_ORIGINS=http://localhost:8080,http://127.0.0.1:8080

# For production
ALLOWED_ORIGINS=https://your-domain.com,https://app.your-domain.com
```

### Rate Limiting

If you hit rate limits:
```bash
# Check current limits in main.py
# Default: 100 requests/minute
# Adjust in docker-compose.yml environment section
```

## 🔒 Production Hardening

### Additional Recommendations

1. **HTTPS/TLS**: Configure reverse proxy (nginx/traefik) with valid certificates
2. **Firewall Rules**: Restrict access to necessary ports only
3. **Secret Management**: Integrate HashiCorp Vault or AWS Secrets Manager
4. **Monitoring**: Add Prometheus/Grafana for metrics
5. **Audit Logging**: Enable comprehensive request logging
6. **Backup Strategy**: Regular backups of volumes and configurations
7. **Updates**: Subscribe to security advisories for dependencies

### Reverse Proxy Example (nginx)

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 📝 Version History

- **v1.0.0** - Initial secure release
  - All critical vulnerabilities patched
  - JWT authentication implemented
  - Rate limiting enabled
  - Enhanced security scanner
  - XSS protection in VSCode extension

## 🆘 Support

For security issues, see [SECURITY.md](SECURITY.md)

For general questions, refer to [README.md](README.md)
