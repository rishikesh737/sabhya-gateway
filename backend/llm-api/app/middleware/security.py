"""
Sabhya AI - Security Middleware

Security Decisions:
- HSTS with preload for HTTPS enforcement
- CSP to prevent XSS attacks
- X-Frame-Options DENY to prevent clickjacking
- Referrer-Policy for privacy
- CORS with explicit origin allowlist (no wildcards in production)
"""

import os
import time
import logging
from typing import List

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

def get_cors_origins() -> List[str]:
    """Get allowed CORS origins from environment."""
    origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    return [o.strip() for o in origins.split(",") if o.strip()]


def get_allowed_hosts() -> List[str]:
    """Get allowed hosts from environment."""
    hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1")
    return [h.strip() for h in hosts.split(",") if h.strip()]


# Security headers configuration
SECURITY_HEADERS = {
    # HSTS - Force HTTPS for 1 year, include subdomains, allow preload
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    
    # Prevent MIME type sniffing
    "X-Content-Type-Options": "nosniff",
    
    # Prevent clickjacking - deny all framing
    "X-Frame-Options": "DENY",
    
    # XSS Protection (legacy, but still useful)
    "X-XSS-Protection": "1; mode=block",
    
    # Referrer Policy - only send origin on cross-origin requests
    "Referrer-Policy": "strict-origin-when-cross-origin",
    
    # Permissions Policy - disable dangerous browser features
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
    
    # Content Security Policy
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:; "
        "connect-src 'self' http://localhost:* https://*; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
}


# ============================================================================
# MIDDLEWARE SETUP
# ============================================================================

def add_security_middleware(app: FastAPI) -> None:
    """
    Add all security middleware to FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    # Get configuration
    cors_origins = get_cors_origins()
    allowed_hosts = get_allowed_hosts()
    
    logger.info(f"Configuring CORS for origins: {cors_origins}")
    logger.info(f"Configuring trusted hosts: {allowed_hosts}")
    
    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "X-CSRF-Token",
        ],
        expose_headers=[
            "X-Process-Time",
            "X-Request-ID",
            "X-Rate-Limit-Remaining",
        ],
        max_age=600,  # Cache preflight for 10 minutes
    )
    
    # Trusted Host Middleware (prevent host header attacks)
    if allowed_hosts and allowed_hosts != ["*"]:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=allowed_hosts
        )


async def security_headers_middleware(request: Request, call_next) -> Response:
    """
    Middleware to add security headers to all responses.
    
    Usage:
        app.middleware("http")(security_headers_middleware)
    """
    # Record start time
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Add security headers
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    
    # Add processing time header
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}"
    
    # Add request ID if available
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        response.headers["X-Request-ID"] = request_id
    
    return response


async def request_id_middleware(request: Request, call_next) -> Response:
    """
    Middleware to generate unique request ID for tracing.
    """
    from uuid import uuid4
    
    # Generate or use existing request ID
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    
    return response


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_security_headers_dict() -> dict:
    """
    Get security headers as dict for manual response construction.
    
    Usage:
        from starlette.responses import JSONResponse
        return JSONResponse(data, headers=get_security_headers_dict())
    """
    return SECURITY_HEADERS.copy()


def validate_security_config() -> dict:
    """
    Validate security configuration and return status.
    
    Returns:
        {
            'is_secure': bool,
            'warnings': [list of warnings],
            'config': {current config}
        }
    """
    warnings = []
    
    cors_origins = get_cors_origins()
    if "*" in cors_origins:
        warnings.append("CORS allows all origins (*) - not recommended for production")
    
    allowed_hosts = get_allowed_hosts()
    if "*" in allowed_hosts:
        warnings.append("Trusted hosts allows all hosts (*) - not recommended for production")
    
    secret_key = os.getenv("SECRET_KEY", "")
    if len(secret_key) < 32:
        warnings.append("SECRET_KEY is too short (< 32 chars)")
    if "change" in secret_key.lower() or "default" in secret_key.lower():
        warnings.append("SECRET_KEY appears to be a default value")
    
    return {
        'is_secure': len(warnings) == 0,
        'warnings': warnings,
        'config': {
            'cors_origins': cors_origins,
            'allowed_hosts': allowed_hosts,
            'headers_configured': list(SECURITY_HEADERS.keys())
        }
    }
