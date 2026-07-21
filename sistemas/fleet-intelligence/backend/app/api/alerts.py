"""Alerts routes: cards proximos do vencimento."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Card, Phase, Board, User
from .deps import get_current_user

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _is_completed(card: Card) -> bool:
    """Check if card has been marked as completed via metadata flag."""
    return bool((card.card_metadata or {}).get("_completed"))


@router.get("/due-soon", response_model=list[dict])
def due_soon_cards(
    days: int = Query(default=7, ge=1, le=90, description="Dias ate o vencimento"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Cards com data limite nos proximos N dias ou ja vencidos. Exclui cards concluidos."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=days)

    stmt = (
        select(Card, Phase.name.label("phase_name"), Phase.board_id, Board.name.label("board_name"))
        .join(Phase, Card.phase_id == Phase.id)
        .join(Board, Phase.board_id == Board.id)
        .where(Card.due_date.isnot(None))
        .where(Card.due_date <= cutoff)
        .where(Board.is_archived.is_(False))
        .order_by(Card.due_date.asc())
    )
    rows = db.execute(stmt).all()

    results = []
    for card, phase_name, board_id, board_name in rows:
        # Skip completed cards — they should not generate alerts
        if _is_completed(card):
            continue
        is_overdue = card.due_date < now if card.due_date else False
        results.append({
            "id": str(card.id),
            "title": card.title,
            "description": card.description,
            "priority": card.priority,
            "due_date": card.due_date.isoformat() if card.due_date else None,
            "is_overdue": is_overdue,
            "phase_id": str(card.phase_id),
            "phase_name": phase_name,
            "board_id": str(board_id),
            "board_name": board_name,
            "assignee_id": str(card.assignee_id) if card.assignee_id else None,
            "tags": card.tags or [],
        })

    return results


@router.get("/count")
def alerts_count(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Contagem rapida de cards vencendo para badge no header (exclui concluidos)."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=days)

    # Fetch all matching cards and filter in Python (JSONB path varies by PG version)
    rows = db.execute(
        select(Card)
        .join(Phase, Card.phase_id == Phase.id)
        .join(Board, Phase.board_id == Board.id)
        .where(Card.due_date.isnot(None))
        .where(Card.due_date <= cutoff)
        .where(Board.is_archived.is_(False))
    ).scalars().all()

    count = sum(1 for c in rows if not _is_completed(c))
    return {"count": count}
