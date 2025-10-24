"""Authentication and rate limiting middleware."""
import os
import time
from collections import defaultdict
from typing import Dict, Tuple, Optional

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from .baked_credential import get_baked_username

# Configuration from environment
LOGIN_RPM = int(os.getenv("LOGIN_RPM", "20"))
LOCKOUT_AFTER = int(os.getenv("LOCKOUT_AFTER", "6"))
LOCKOUT_SECONDS = int(os.getenv("LOCKOUT_SECONDS", "900"))  # 15 minutes

# Rate limiting state
_login_attempts: Dict[str, list] = defaultdict(list)
_lockouts: Dict[str, float] = {}  # IP -> lockout_until timestamp


# Public paths that don't require authentication
PUBLIC_PATHS = {
    "/auth/login",
    "/auth/logout",
    "/auth/session",
    "/api/health",
    "/docs",
    "/redoc",
    "/openapi.json"
}


def is_public_path(path: str) -> bool:
    """Check if path is public (no auth required)."""
    if path in PUBLIC_PATHS:
        return True
    # Also allow static files
    if path.startswith("/assets/") or path == "/" or path == "/login":
        return True
    return False


def check_rate_limit(ip: str) -> Tuple[bool, Optional[str]]:
    """
    Check if IP is rate limited or locked out.

    Returns:
        (allowed, error_message)
    """
    now = time.time()

    # Check lockout
    if ip in _lockouts:
        lockout_until = _lockouts[ip]
        if now < lockout_until:
            remaining = int(lockout_until - now)
            return False, f"Too many failed attempts. Locked out for {remaining} seconds."
        else:
            # Lockout expired
            del _lockouts[ip]
            _login_attempts[ip] = []

    # Check rate limit (attempts in last minute)
    attempts = _login_attempts[ip]
    # Remove attempts older than 60 seconds
    attempts[:] = [t for t in attempts if now - t < 60]

    if len(attempts) >= LOGIN_RPM:
        return False, f"Rate limit exceeded. Max {LOGIN_RPM} attempts per minute."

    return True, None


def record_login_attempt(ip: str, success: bool) -> None:
    """Record a login attempt and handle lockouts."""
    now = time.time()

    if not success:
        # Record failed attempt
        attempts = _login_attempts[ip]
        attempts.append(now)

        # Remove old attempts (last hour)
        attempts[:] = [t for t in attempts if now - t < 3600]

        # Check if should lock out
        recent_failures = [t for t in attempts if now - t < 300]  # Last 5 minutes
        if len(recent_failures) >= LOCKOUT_AFTER:
            _lockouts[ip] = now + LOCKOUT_SECONDS
    else:
        # Successful login - clear attempts
        _login_attempts[ip] = []
        if ip in _lockouts:
            del _lockouts[ip]


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for authentication and rate limiting."""

    async def dispatch(self, request: Request, call_next):
        """Process request with auth and rate limit checks."""
        path = request.url.path

        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        # Rate limit login endpoint
        if path == "/auth/login" and request.method == "POST":
            allowed, error_msg = check_rate_limit(client_ip)
            if not allowed:
                raise HTTPException(status_code=429, detail=error_msg)

        # Check authentication for protected paths
        if not is_public_path(path):
            session_user = request.cookies.get("session_user")
            if not session_user or session_user != get_baked_username():
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required"
                )

        # Process request
        response = await call_next(request)

        # Record login attempt result
        if path == "/auth/login" and request.method == "POST":
            success = response.status_code == 200
            record_login_attempt(client_ip, success)

        return response