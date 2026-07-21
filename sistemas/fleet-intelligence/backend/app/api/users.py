"""User management (admin-only for write ops)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.activity import log_activity
from ..core.security import hash_password
from ..database import get_db
from ..models import User
from ..schemas import UserCreate, UserOut, UserUpdate
from .deps import get_current_user, require_admin

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[User]:
    return list(db.execute(select(User).order_by(User.full_name)).scalars())


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
) -> User:
    user = User(
        email=payload.email.lower(),
        username=payload.username,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email ou username ja existem",
        )
    db.refresh(user)
    log_activity(db, user_id=current.id, action="create_user",
                 entity_type="user", entity_id=user.id,
                 details={"username": user.username, "role": user.role})
    db.commit()
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario nao encontrado")
    data = payload.model_dump(exclude_unset=True)
    changed_keys = list(data.keys())
    if "password" in data:
        user.hashed_password = hash_password(data.pop("password"))
    for k, v in data.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    log_activity(db, user_id=current.id, action="update_user",
                 entity_type="user", entity_id=user.id,
                 details={"username": user.username, "changes": changed_keys})
    db.commit()
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
) -> None:
    if user_id == current.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Voce nao pode deletar sua propria conta"
        )
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario nao encontrado")
    username = user.username
    db.delete(user)
    db.commit()
    log_activity(db, user_id=current.id, action="delete_user",
                 entity_type="user", entity_id=user_id,
                 details={"username": username})
    db.commit()
