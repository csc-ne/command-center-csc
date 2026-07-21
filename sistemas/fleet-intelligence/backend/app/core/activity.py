"""Activity logging helper."""
import uuid
from sqlalchemy.orm import Session
from ..models import ActivityLog


def log_activity(
    db: Session,
    *,
    user_id: uuid.UUID,
    action: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Insert an activity log entry. Non-blocking — swallows exceptions."""
    try:
        entry = ActivityLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
            ip_address=ip_address,
        )
        db.add(entry)
        db.flush()
    except Exception:
        pass  # never break the main operation because of logging
