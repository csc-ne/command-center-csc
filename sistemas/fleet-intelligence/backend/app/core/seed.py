"""Ensure initial admin user exists on first boot."""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import User
from .security import hash_password

logger = logging.getLogger(__name__)

DEFAULT_ADMIN_EMAIL = "admin@veneza.com"
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"


def ensure_seed_admin(db: Session) -> None:
    """Create default admin if the users table is empty.

    Called once on app startup. If any admin already exists, this is a no-op.
    """
    try:
        exists = db.execute(
            select(User).where(User.role == "admin").limit(1)
        ).scalar_one_or_none()
        if exists:
            return
        admin = User(
            email=DEFAULT_ADMIN_EMAIL,
            username=DEFAULT_ADMIN_USERNAME,
            full_name="Administrador",
            hashed_password=hash_password(DEFAULT_ADMIN_PASSWORD),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        logger.warning(
            "Seeded default admin user '%s' (password: '%s'). CHANGE IT!",
            DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD,
        )
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to seed admin user: %s", exc)
        db.rollback()
