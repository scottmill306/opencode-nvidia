#!/usr/bin/env python3
"""
Security Verification Script
Validates that all security patches are properly configured
"""

import os
import sys
import re
from pathlib import Path

def check_env_file():
    """Verify .env file exists and has secure values"""
    print("🔍 Checking .env file...")
    
    env_path = Path(".env")
    if not env_path.exists():
        print("❌ .env file not found!")
        return False
    
    with open(env_path) as f:
        content = f.read()
    
    checks = {
        "JWT_SECRET": r"JWT_SECRET=[a-f0-9]{64}",
        "MINIO_ROOT_USER": r"MINIO_ROOT_USER=minioadmin_[a-f0-9]{16}",
        "MINIO_ROOT_PASSWORD": r"MINIO_ROOT_PASSWORD=[a-f0-9]{64}",
        "ALLOWED_ORIGINS": r"ALLOWED_ORIGINS="
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if re.search(pattern, content):
            print(f"  ✅ {check_name} configured")
        else:
            print(f"  ❌ {check_name} missing or insecure")
            all_passed = False
    
    # Check for default/insecure values
    insecure_patterns = [
        (r"minioadmin$", "Default MinIO username"),
        (r"change.?me", "Placeholder password"),
        (r"your-super-secret", "Example JWT secret"),
    ]
    
    for pattern, description in insecure_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            print(f"  ⚠️  Warning: {description} detected")
            all_passed = False
    
    return all_passed

def check_docker_compose():
    """Verify docker-compose.yml security configurations"""
    print("\n🔍 Checking docker-compose.yml...")
    
    dc_path = Path("docker-compose.yml")
    if not dc_path.exists():
        print("❌ docker-compose.yml not found!")
        return False
    
    with open(dc_path) as f:
        content = f.read()
    
    checks = {
        "Environment variables for credentials": r"\$\{MINIO_ROOT_USER",
        "Resource limits": r"limits:",
        "Non-default passwords": r"minioadmin_secure|minioadmin_[a-f0-9]",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if re.search(pattern, content):
            print(f"  ✅ {check_name}")
        else:
            print(f"  ⚠️  {check_name} - review recommended")
    
    return all_passed

def check_main_py():
    """Verify main.py security implementations"""
    print("\n🔍 Checking backend/main.py...")
    
    main_path = Path("backend/main.py")
    if not main_path.exists():
        print("❌ backend/main.py not found!")
        return False
    
    with open(main_path) as f:
        content = f.read()
    
    checks = {
        "JWT authentication": r"jwt\.decode",
        "Rate limiting": r"SlowAPI",
        "CORS restrictions": r"ALLOWED_ORIGINS.*getenv",
        "Input validation": r"Field\([^)]*max_length",
        "SSRF prevention": r"ALLOWED_TRITON_HOSTS",
        "Generic error messages": r"Inference service temporarily unavailable",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if re.search(pattern, content):
            print(f"  ✅ {check_name}")
        else:
            print(f"  ❌ {check_name} missing")
            all_passed = False
    
    # Check for insecure patterns
    insecure = [
        (r'allow_origins=\["\*"\]', "Wildcard CORS"),
        (r'minioadmin/minioadmin', "Hardcoded credentials"),
    ]
    
    for pattern, description in insecure:
        if re.search(pattern, content):
            print(f"  ❌ Security issue: {description}")
            all_passed = False
    
    return all_passed

def check_vscode_extension():
    """Verify VSCode extension security"""
    print("\n🔍 Checking plugins/vscode/src/extension.ts...")
    
    ext_path = Path("plugins/vscode/src/extension.ts")
    if not ext_path.exists():
        print("❌ extension.ts not found!")
        return False
    
    with open(ext_path) as f:
        content = f.read()
    
    checks = {
        "HTTPS default": r"https://localhost",
        "Authentication": r"getAuthToken",
        "HTML sanitization": r"replace\(/&/g.*replace\(/</g",
        "CSP headers": r"contentSecurityPolicy",
        "DOMPurify import": r"import.*DOMPurify",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if re.search(pattern, content):
            print(f"  ✅ {check_name}")
        else:
            print(f"  ⚠️  {check_name} - review recommended")
    
    return all_passed

def check_dockerfile():
    """Verify Dockerfile security"""
    print("\n🔍 Checking backend/Dockerfile...")
    
    dockerfile_path = Path("backend/Dockerfile")
    if not dockerfile_path.exists():
        print("❌ Dockerfile not found!")
        return False
    
    with open(dockerfile_path) as f:
        content = f.read()
    
    checks = {
        "Non-root user": r"USER appuser",
        "User creation": r"useradd.*-r",
        "Minimal base image": r"python:.*-slim",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if re.search(pattern, content):
            print(f"  ✅ {check_name}")
        else:
            print(f"  ❌ {check_name} missing")
            all_passed = False
    
    return all_passed

def main():
    print("=" * 60)
    print("🛡️  OpenCode NVIDIA Security Verification")
    print("=" * 60)
    
    results = []
    
    results.append(("Environment Configuration", check_env_file()))
    results.append(("Docker Compose", check_docker_compose()))
    results.append(("Backend API", check_main_py()))
    results.append(("VSCode Extension", check_vscode_extension()))
    results.append(("Dockerfile", check_dockerfile()))
    
    print("\n" + "=" * 60)
    print("📊 Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nTotal: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 All security checks passed!")
        return 0
    else:
        print("\n⚠️  Some security issues need attention")
        return 1

if __name__ == "__main__":
    sys.exit(main())
