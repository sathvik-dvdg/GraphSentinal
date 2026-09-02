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
    is_operator = secrets.compare_digest(request.username, settings.operator_username) and auth_service.verify_password(request.password, settings.operator_password)
    is_readonly = (
        bool(settings.readonly_username)
        and bool(settings.readonly_password)
        and secrets.compare_digest(request.username, settings.readonly_username)
        and auth_service.verify_password(request.password, settings.readonly_password)
    )
    if not (is_operator or is_readonly):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    
    role = settings.operator_role if is_operator else "readonly"
    token = auth_service.create_session(username=request.username, role=role)
    return {
        "token": token,
        "username": request.username,
        "role": role,
        "expires_in_hours": settings.session_ttl_hours,
    }


@router.post("/auth/logout", response_model=LogoutResponse)
async def logout(authorization: str | None = Header(default=None)):
    token = auth_service.extract_bearer_token(authorization)
    auth_service.destroy_session(token)
    return {"status": "logged_out"}


@router.get("/auth/me", response_model=MeResponse)
async def me(authorization: str | None = Header(default=None)):
    token = auth_service.extract_bearer_token(authorization)
    session = auth_service.validate_session(token)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return {"username": session.get("username", settings.operator_username), "role": session.get("role", "operator")}

