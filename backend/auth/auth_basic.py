"""Basic authentication endpoints."""
import os
from typing import Optional

from fastapi import APIRouter, Response, Request, HTTPException, Form
from pydantic import BaseModel

from .baked_credential import verify_password, get_baked_username

router = APIRouter(prefix="/auth", tags=["auth"])

# Session configuration from environment
SESSION_MAX_AGE_SECONDS = int(os.getenv("SESSION_MAX_AGE_SECONDS", "604800"))  # 7 days
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", None)


class LoginRequest(BaseModel):
    """Login request body."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response."""
    success: bool
    username: Optional[str] = None


class SessionResponse(BaseModel):
    """Session status response."""
    authenticated: bool
    user: Optional[dict] = None


@router.post("/login")
async def login(
    response: Response,
    username: str = Form(...),
    password: str = Form(...)
) -> LoginResponse:
    """
    Authenticate user and set session cookie.
    
    POST /auth/login
    Body: username, password (form data)
    """
    if verify_password(username, password):
        # Set HttpOnly session cookie
        response.set_cookie(
            key="session_user",
            value=username,
            max_age=SESSION_MAX_AGE_SECONDS,
            secure=COOKIE_SECURE,
            httponly=True,
            samesite="lax",
            domain=COOKIE_DOMAIN
        )
        return LoginResponse(success=True, username=username)
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/logout")
async def logout(response: Response) -> dict:
    """
    Clear session cookie.
    
    POST /auth/logout
    """
    response.delete_cookie(
        key="session_user",
        domain=COOKIE_DOMAIN
    )
    return {"success": True}


@router.get("/session")
async def get_session(request: Request) -> SessionResponse:
    """
    Check current session status.
    
    GET /auth/session
    Returns: {authenticated: bool, user?: {username: str}}
    """
    session_user = request.cookies.get("session_user")
    
    if session_user and session_user == get_baked_username():
        return SessionResponse(
            authenticated=True,
            user={"username": session_user}
        )
    else:
        return SessionResponse(authenticated=False)
