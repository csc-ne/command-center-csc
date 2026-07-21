"""Shared FastAPI dependencies.

Suporta dois modos de autenticacao:
  1. Bearer token (JWT proprio do Fleet Intelligence) — para chamadas API diretas
  2. Cookie portal_token (SSO do Command Center) — para acesso via navegador

Quando o SSO e usado, o usuario local e criado/atualizado automaticamente
a partir dos dados do token do Command Center.
"""
import hashlib
import hmac
import json
import uuid
from base64 import urlsafe_b64decode
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, Header, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..core.security import decode_token, hash_password
from ..database import get_db
from ..models import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _pad_b64(s: str) -> str:
    """Add missing padding to base64url string."""
    return s + "=" * (4 - len(s) % 4)


def _validate_portal_token(token: str) -> Optional[dict]:
    """Validate a Command Center JWT HS256 token (same logic as Node systems)."""
    secret = getattr(settings, "PORTAL_JWT_SECRET", "")
    if not secret or not token:
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    h, p, sig = parts
    try:
        header = json.loads(urlsafe_b64decode(_pad_b64(h)))
        if header.get("alg") != "HS256":
            return None
        expected = hmac.new(
            secret.encode(), f"{h}.{p}".encode(), hashlib.sha256
        ).digest()
        # Compare base64url representations
        import base64
        expected_b64 = base64.urlsafe_b64encode(expected).rstrip(b"=").decode()
        if not hmac.compare_digest(sig, expected_b64):
            return None
        payload = json.loads(urlsafe_b64decode(_pad_b64(p)))
        import time
        if not payload.get("exp") or time.time() > payload["exp"]:
            return None
        return payload
    except Exception:
        return None


def _get_or_create_sso_user(db: Session, portal_payload: dict) -> User:
    """Find or create a local user from Command Center SSO payload."""
    email = (portal_payload.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(status_code=401, detail="SSO token sem email")

    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user:
        # Atualiza nome se mudou no portal
        display = portal_payload.get("displayName") or portal_payload.get("name", "")
        if display and user.full_name != display:
            user.full_name = display
            db.commit()
        return user

    # Cria usuario local a partir do SSO
    username = email.split("@")[0].replace(".", "_")
    base_username = username
    counter = 1
    while db.execute(select(User).where(User.username == username)).scalar_one_or_none():
        username = f"{base_username}{counter}"
        counter += 1

    display = portal_payload.get("displayName") or portal_payload.get("name", "")
    full_name = display or base_username.replace("_", " ").replace(".", " ").title()

    user = User(
        email=email,
        username=username,
        full_name=full_name,
        hashed_password=hash_password(uuid.uuid4().hex),  # senha aleatoria (login via SSO)
        role="operator",
        is_active=True,
        is_email_verified=True,
        is_approved=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1) Tenta Bearer token (JWT proprio do FI)
    if token:
        try:
            payload = decode_token(token)
            user_id_str = payload.get("sub")
            if user_id_str:
                user = db.get(User, uuid.UUID(user_id_str))
                if user and user.is_active:
                    return user
        except Exception:
            pass

    # 2) Tenta cookie portal_token (SSO do Command Center)
    portal_token = request.cookies.get("portal_token")
    if portal_token:
        portal_payload = _validate_portal_token(portal_token)
        if portal_payload:
            return _get_or_create_sso_user(db, portal_payload)

    raise credentials_exc


def require_admin(current: User = Depends(get_current_user)) -> User:
    if current.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores",
        )
    return current


def require_not_viewer(current: User = Depends(get_current_user)) -> User:
    """Allow admin or operator, but block viewers from write operations."""
    if current.role == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuários com perfil de visualizador não podem realizar esta ação",
        )
    return current
