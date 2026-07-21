"""Card schemas."""
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Priority = Literal["low", "medium", "high", "critical"]


class CardBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: str | None = None
    priority: Priority = "medium"
    assignee_id: uuid.UUID | None = None
    due_date: datetime | None = None
    tags: list[str] = []


class CardCreate(CardBase):
    phase_id: uuid.UUID
    position: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CardUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = None
    priority: Priority | None = None
    assignee_id: uuid.UUID | None = None
    due_date: datetime | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class CardMove(BaseModel):
    target_phase_id: uuid.UUID
    target_position: int = Field(..., ge=0)


class CardOut(CardBase):
    # The ORM attribute is `card_metadata` (SQLAlchemy's Base already owns
    # `metadata`). The validator below remaps it to `metadata` for JSON output.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phase_id: uuid.UUID
    position: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _from_orm(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        if hasattr(data, "card_metadata"):
            return {
                "id": data.id,
                "phase_id": data.phase_id,
                "title": data.title,
                "description": data.description,
                "position": data.position,
                "priority": data.priority,
                "assignee_id": data.assignee_id,
                "due_date": data.due_date,
                "tags": list(data.tags or []),
                "metadata": dict(data.card_metadata or {}),
                "created_by": data.created_by,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
        return data
