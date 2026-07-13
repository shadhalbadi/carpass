"""Seed default users and fee tables only — no demo car listings."""

from sqlalchemy import select

from app.auth import hash_password
from app.database import AsyncSessionLocal
from app.models import User
from app.services.cost_engine import ensure_defaults

_SEED_DONE = False


async def seed_all() -> None:
    global _SEED_DONE
    if _SEED_DONE:
        return
    async with AsyncSessionLocal() as db:
        await ensure_defaults(db)

        async def ensure_user(email: str, password: str, role: str, name: str, company: str = "") -> None:
            existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if existing:
                return
            db.add(
                User(
                    email=email,
                    full_name=name,
                    hashed_password=hash_password(password),
                    role=role,
                    company_name=company,
                )
            )

        await ensure_user("admin@carpass.om", "admin123", "admin", "CarPass Admin")
        await ensure_user("buyer@carpass.om", "buyer123", "buyer", "Demo Buyer")
        await ensure_user("agent@carpass.om", "agent123", "agent", "Sohar Clearing Agent", "Al Bahr Clearance LLC")
        await db.commit()
    _SEED_DONE = True
