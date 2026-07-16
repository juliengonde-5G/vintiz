#!/usr/bin/env python3
"""Interactively create the first manager without a default password."""

from __future__ import annotations

import argparse
import asyncio
import getpass

from sqlalchemy import func, select

from app.core.database import async_session
from app.core.security import hash_password
from app.models.user import User, UserRole


async def _create(username: str, email: str, password: str) -> None:
    async with async_session() as db:
        manager_count = (
            await db.execute(
                select(func.count(User.id)).where(User.role == UserRole.manager)
            )
        ).scalar_one()
        if manager_count:
            raise RuntimeError(
                "A manager already exists; create additional users from /admin/users"
            )
        duplicate = (
            await db.execute(
                select(User.id).where(
                    (User.username == username) | (User.email == email)
                )
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            raise RuntimeError("Username or email already exists")
        db.add(
            User(
                username=username,
                email=email,
                password_hash=hash_password(password),
                role=UserRole.manager,
                is_active=True,
            )
        )
        await db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the first Vintiz manager")
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    username = args.username.strip()
    email = args.email.strip().lower()
    if len(username) < 3 or "@" not in email:
        parser.error("valid --username and --email are required")

    password = getpass.getpass("Manager password (12+ characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        parser.error("passwords do not match")
    if len(password) < 12:
        parser.error("password must contain at least 12 characters")

    asyncio.run(_create(username, email, password))
    print(f"Manager {username!r} created; no default credential was stored")


if __name__ == "__main__":
    main()
