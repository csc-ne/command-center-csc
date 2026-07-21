"""Board schemas."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from .phase import PhaseWithCards


class BoardBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    color: str = "indigo"
    icon: str = "Workflow"


class BoardCreate(BoardBase):
    pass


class BoardUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    color: str | None = None
    icon: str | None = None
    is_archived: bool | None = None


class BoardOut(BoardBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class BoardWithPhases(BoardOut):
    phases: list["PhaseWithCards"] = []
