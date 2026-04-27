import uuid
from datetime import datetime

from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "collaborateur"


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str | None = None
    role: str | None = None


class TokenData(BaseModel):
    sub: str | None = None


class CashierPinSetRequest(BaseModel):
    user_id: uuid.UUID
    pin: str  # 4 digits, validated server-side


class CashierPinClearRequest(BaseModel):
    user_id: uuid.UUID


class CashierPinLoginRequest(BaseModel):
    pin: str


class CashierResponse(BaseModel):
    id: uuid.UUID
    username: str
    role: str

    model_config = {"from_attributes": True}


class CashierWithPinStatusResponse(BaseModel):
    id: uuid.UUID
    username: str
    role: str
    is_active: bool
    has_pin: bool

    model_config = {"from_attributes": True}
