import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import login_rate_limit, reset_login_rate_limit
from app.core.security import (
    create_access_token,
    verify_password,
    verify_token,
    oauth2_scheme,
)
from app.models.user import User
from app.schemas.user import Token

logger = logging.getLogger("vintiz")
router = APIRouter(prefix="/auth", tags=["auth"])


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkVerify(BaseModel):
    email: EmailStr
    code: str


class MagicLinkTokenVerify(BaseModel):
    token: str


class MagicLinkVerifyResponse(BaseModel):
    access_token: str
    expires_in: int
    client_id: str
    membership_number: str | None
    email: str | None = None


@router.post("/login", response_model=Token, dependencies=[Depends(login_rate_limit)])
async def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Authenticate user with username + password, return JWT.

    Rate-limited per client IP via the `login_rate_limit` dependency.
    """
    result = await db.execute(
        select(User).where(User.username == form_data.username)
    )
    user = result.scalar_one_or_none()
    if user is None or not verify_password(form_data.password, user.password_hash):
        logger.info(
            "Failed login attempt: username=%s ip=%s",
            form_data.username,
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    # Reset rate-limit bucket on successful login so legitimate users aren't penalised
    await reset_login_rate_limit(request)
    logger.info("Successful login: user_id=%s username=%s", user.id, user.username)
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
    return Token(
        access_token=access_token,
        username=user.username,
        role=user.role.value,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Accept a valid token and return a new one with a fresh expiry."""
    payload = verify_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    new_token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
    return Token(access_token=new_token)


# ---------------------------------------------------------------------------
# Public client space — magic-link OTP (PR1)
# ---------------------------------------------------------------------------


@router.post("/magic-link/request", status_code=status.HTTP_204_NO_CONTENT)
async def magic_link_request(
    payload: MagicLinkRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Issue a 6-digit OTP for the public client space.

    Always returns 204 — no information leaked about whether the email
    exists. Rate-limited per email/IP inside the service to prevent
    enumeration and Brevo abuse.
    """
    from app.services.magic_link import issue

    client_ip = request.client.host if request.client else None
    await issue(db, payload.email, ip=client_ip)
    await db.commit()
    return None


@router.post("/magic-link/verify", response_model=MagicLinkVerifyResponse)
async def magic_link_verify(
    payload: MagicLinkVerify,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Exchange a valid OTP for a 1h client JWT (role=client)."""
    from app.services.magic_link import MagicLinkError, verify

    client_ip = request.client.host if request.client else None
    try:
        result = await verify(db, payload.email, payload.code, ip=client_ip)
    except MagicLinkError as exc:
        await db.commit()  # persist attempt count even on failure
        if exc.code == "too_many_attempts":
            raise HTTPException(status_code=429, detail="too_many_attempts")
        raise HTTPException(status_code=401, detail="invalid_or_expired")
    await db.commit()
    return MagicLinkVerifyResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        client_id=result.client_id,
        membership_number=result.membership_number,
        email=result.email,
    )


@router.post("/magic-link/verify-token", response_model=MagicLinkVerifyResponse)
async def magic_link_verify_token(
    payload: MagicLinkTokenVerify,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Passwordless login via the one-time link token (no code to type).

    Exchanges the opaque token from the email link for the same 1h client
    JWT as the OTP path. Generic 401 on any invalid/expired/used token."""
    from app.services.magic_link import MagicLinkError, verify_by_token

    client_ip = request.client.host if request.client else None
    try:
        result = await verify_by_token(db, payload.token, ip=client_ip)
    except MagicLinkError:
        await db.commit()
        raise HTTPException(status_code=401, detail="invalid_or_expired")
    await db.commit()
    return MagicLinkVerifyResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        client_id=result.client_id,
        membership_number=result.membership_number,
        email=result.email,
    )
