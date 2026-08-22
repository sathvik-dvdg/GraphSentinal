# [WSL2]
# Error.md #18/#27 — real session auth replacing the frontend's fake
# "any non-empty credentials" gate.
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.api.v1.deps import check_login_rate_limit
from app.config import settings
from app.models.schemas import LoginRequest, LoginResponse, LogoutResponse, MeResponse
from app.services import auth_service

router = APIRouter()


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest, _: None = Depends(check_login_rate_limit)):
    username_ok = secrets.compare_digest(request.username, settings.operator_username)
    password_ok = secrets.compare_digest(request.password, settings.operator_password)
    if not (username_ok and password_ok):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    token = auth_service.create_session()
    return {"token": token, "username": settings.operator_username, "expires_in_hours": settings.session_ttl_hours}


@router.post("/auth/logout", response_model=LogoutResponse)
async def logout(authorization: str | None = Header(default=None)):
    token = auth_service.extract_bearer_token(authorization)
    auth_service.destroy_session(token)
    return {"status": "logged_out"}


@router.get("/auth/me", response_model=MeResponse)
async def me(authorization: str | None = Header(default=None)):
    token = auth_service.extract_bearer_token(authorization)
    if not auth_service.validate_session(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return {"username": settings.operator_username}
