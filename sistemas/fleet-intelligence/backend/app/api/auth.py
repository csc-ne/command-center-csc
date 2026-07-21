"""Authentication & registration routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..core.security import create_access_token, hash_password, verify_password
from ..database import get_db
from ..models import User
from ..schemas import (
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    Token,
    UserOut,
)
from .deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _authenticate(db: Session, username: str, password: str) -> User | None:
    stmt = select(User).where(
        or_(User.email == username.lower(), User.username == username)
    )
    user = db.execute(stmt).scalar_one_or_none()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> Token:
    """JSON login endpoint."""
    user = _authenticate(db, payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario ou senha incorretos",
        )
    token = create_access_token(
        subject=user.id, extra={"role": user.role, "username": user.username}
    )
    return Token(
        access_token=token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/token", response_model=Token, include_in_schema=False)
def token_form(
    form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> Token:
    """OAuth2-compatible form-based endpoint (for Swagger UI)."""
    user = _authenticate(db, form.username, form.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        subject=user.id, extra={"role": user.role, "username": user.username}
    )
    return Token(
        access_token=token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/register", response_model=MessageResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user. Inserts directly into DB, ready to login."""
    if payload.password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="As senhas nao conferem.",
        )

    email_lower = payload.email.lower()
    existing = db.execute(
        select(User).where(User.email == email_lower)
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este email ja esta cadastrado.",
        )

    username = email_lower.split("@")[0]
    base_username = username
    counter = 1
    while db.execute(select(User).where(User.username == username)).scalar_one_or_none():
        username = f"{base_username}{counter}"
        counter += 1

    full_name = base_username.replace(".", " ").replace("_", " ").title()

    user = User(
        email=email_lower,
        username=username,
        full_name=full_name,
        hashed_password=hash_password(payload.password),
        role="operator",
        is_active=True,
        is_email_verified=True,
        is_approved=True,
    )
    db.add(user)
    db.commit()

    return MessageResponse(
        message="Cadastro realizado com sucesso! Voce ja pode fazer login."
    )


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)) -> User:
    return current
