"""User schemas."""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


Role = Literal["admin", "operator", "viewer"]


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    full_name: str = Field(..., min_length=2, max_length=200)
    role: Role = "operator"


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=128)


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=200)
    role: Role | None = None
    is_active: bool | None = None
    is_approved: bool | None = None
    password: str | None = Field(None, min_length=6, max_length=128)


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    is_email_verified: bool
    is_approved: bool
    created_at: datetime
    updated_at: datetime
