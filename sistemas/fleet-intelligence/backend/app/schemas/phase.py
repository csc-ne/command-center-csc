"""Phase schemas."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from .card import CardOut


class PhaseBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    color: str = "slate"
    wip_limit: int | None = None


class PhaseCreate(PhaseBase):
    position: int | None = None  # if None, append to end


class PhaseUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    color: str | None = None
    wip_limit: int | None = None


class PhaseReorder(BaseModel):
    """Reorder list of phases within a board."""
    phase_ids: list[uuid.UUID]


class PhaseOut(PhaseBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    board_id: uuid.UUID
    position: int
    created_at: datetime
    updated_at: datetime


class PhaseWithCards(PhaseOut):
    cards: list["CardOut"] = []
