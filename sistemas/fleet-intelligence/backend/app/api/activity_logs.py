"""Activity logs routes (admin-only)."""
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ActivityLog, User
from .deps import get_current_user, require_admin

router = APIRouter(prefix="/activity-logs", tags=["activity-logs"])


class ActivityLogOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_name: str | None = None
    action: str
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    details: dict = {}
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[ActivityLogOut])
def list_activity_logs(
    user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """List activity logs with optional filters. Admin only."""
    stmt = (
        select(ActivityLog, User.full_name.label("user_name"))
        .outerjoin(User, ActivityLog.user_id == User.id)
        .order_by(ActivityLog.created_at.desc())
    )
    if user_id:
        stmt = stmt.where(ActivityLog.user_id == user_id)
    if entity_type:
        stmt = stmt.where(ActivityLog.entity_type == entity_type)

    stmt = stmt.offset(offset).limit(limit)
    rows = db.execute(stmt).all()

    return [
        ActivityLogOut(
            id=log.id,
            user_id=log.user_id,
            user_name=user_name,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            details=log.details or {},
            created_at=log.created_at,
        )
        for log, user_name in rows
    ]
