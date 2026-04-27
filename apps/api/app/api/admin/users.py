"""Admin user management — CRUD over the ``users`` table.

POS PIN management lives in ``/api/pos/cashier/*`` (CashierService); this
router only handles user lifecycle (create, edit role/email/active state,
reset password, soft-delete).

All endpoints are manager-only. A manager cannot deactivate themselves.
"""

from __future__ import annotations

import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import RoleChecker, get_current_user, hash_password
from app.models.user import User, UserRole


router = APIRouter(tags=["admin"])

manager_only = RoleChecker(["manager"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class UserOut(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    has_pin: bool


class CreateUserRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.collaborateur


class UpdateUserRequest(BaseModel):
    email: EmailStr | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class ResetPasswordResponse(BaseModel):
    new_password: str


def _serialize(u: User) -> UserOut:
    return UserOut(
        id=str(u.id),
        username=u.username,
        email=u.email,
        role=u.role.value,
        is_active=bool(u.is_active),
        has_pin=bool(u.pin_hash),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/users", dependencies=[Depends(manager_only)], response_model=list[UserOut])
async def list_users(db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (
        await db.execute(select(User).order_by(User.created_at.desc()))
    ).scalars().all()
    return [_serialize(u) for u in rows]


@router.post(
    "/users",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(manager_only)],
    response_model=UserOut,
)
async def create_user(
    payload: CreateUserRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Mot de passe trop court (8 char. min)")

    existing = (
        await db.execute(
            select(User).where(
                (User.username == payload.username) | (User.email == payload.email)
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username ou email déjà utilisé")

    user = User(
        username=payload.username,
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.commit()
    return _serialize(user)


@router.put(
    "/users/{user_id}",
    dependencies=[Depends(manager_only)],
    response_model=UserOut,
)
async def update_user(
    user_id: uuid.UUID,
    payload: UpdateUserRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # A manager cannot demote/deactivate themselves
    if user.id == current_user.id:
        if payload.is_active is False:
            raise HTTPException(status_code=400, detail="Vous ne pouvez pas vous désactiver vous-même")
        if payload.role is not None and payload.role != UserRole.manager:
            raise HTTPException(status_code=400, detail="Vous ne pouvez pas changer votre propre rôle")

    if payload.email is not None:
        user.email = str(payload.email)
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = bool(payload.is_active)
    await db.flush()
    await db.commit()
    return _serialize(user)


@router.post(
    "/users/{user_id}/reset-password",
    dependencies=[Depends(manager_only)],
    response_model=ResetPasswordResponse,
)
async def reset_password(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    new_password = secrets.token_urlsafe(9)  # ~12 char alphanum
    user.password_hash = hash_password(new_password)
    await db.flush()
    await db.commit()
    return ResetPasswordResponse(new_password=new_password)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(manager_only)],
)
async def soft_delete_user(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas vous désactiver vous-même")
    user.is_active = False
    await db.flush()
    await db.commit()
    return None
