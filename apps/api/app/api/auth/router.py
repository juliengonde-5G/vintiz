import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
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
    return Token(access_token=access_token)


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
