import enum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserRole(str, enum.Enum):
    manager = "manager"
    collaborateur = "collaborateur"


class User(Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False, default=UserRole.collaborateur
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 4-digit POS PIN, bcrypt-hashed. Nullable: managers don't need a POS PIN.
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
