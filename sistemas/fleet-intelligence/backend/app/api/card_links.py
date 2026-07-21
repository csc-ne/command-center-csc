"""Card links routes: view and complete cross-flow card links."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.activity import log_activity
from ..database import get_db
from ..models import Board, Card, CardLink, BoardConnection, Phase, User
from .deps import get_current_user

router = APIRouter(prefix="/card-links", tags=["card-links"])


class CardLinkOut(BaseModel):
    id: uuid.UUID
    connection_id: uuid.UUID
    source_card_id: uuid.UUID
    target_card_id: uuid.UUID
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    source_card_title: str | None = None
    target_card_title: str | None = None
    source_board_name: str | None = None
    target_board_name: str | None = None

    model_config = {"from_attributes": True}


@router.get("/card/{card_id}", response_model=list[CardLinkOut])
def get_card_links(
    card_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get all links involving this card (as source or target)."""
    stmt = select(CardLink).where(
        (CardLink.source_card_id == card_id) |
        (CardLink.target_card_id == card_id)
    )
    links = list(db.execute(stmt).scalars())
    results = []
    for link in links:
        src_card = db.get(Card, link.source_card_id)
        tgt_card = db.get(Card, link.target_card_id)
        # Get board names via phase
        src_board_name = None
        tgt_board_name = None
        if src_card:
            src_phase = db.get(Phase, src_card.phase_id)
            if src_phase:
                src_board = db.get(Board, src_phase.board_id)
                src_board_name = src_board.name if src_board else None
        if tgt_card:
            tgt_phase = db.get(Phase, tgt_card.phase_id)
            if tgt_phase:
                tgt_board = db.get(Board, tgt_phase.board_id)
                tgt_board_name = tgt_board.name if tgt_board else None

        results.append(CardLinkOut(
            id=link.id,
            connection_id=link.connection_id,
            source_card_id=link.source_card_id,
            target_card_id=link.target_card_id,
            status=link.status,
            created_at=link.created_at,
            completed_at=link.completed_at,
            source_card_title=src_card.title if src_card else None,
            target_card_title=tgt_card.title if tgt_card else None,
            source_board_name=src_board_name,
            target_board_name=tgt_board_name,
        ))
    return results


@router.get("/board/{board_id}", response_model=list[str])
def get_linked_card_ids(
    board_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return IDs of all cards in this board that participate in a link (source or target)."""
    # Get all phase IDs for this board
    phase_ids = list(db.execute(
        select(Phase.id).where(Phase.board_id == board_id)
    ).scalars())
    if not phase_ids:
        return []

    # Cards in this board
    card_ids = list(db.execute(
        select(Card.id).where(Card.phase_id.in_(phase_ids))
    ).scalars())
    if not card_ids:
        return []

    # Find links involving these cards
    linked = set()
    links = list(db.execute(
        select(CardLink).where(
            (CardLink.source_card_id.in_(card_ids)) |
            (CardLink.target_card_id.in_(card_ids))
        )
    ).scalars())
    for link in links:
        if link.source_card_id in card_ids:
            linked.add(str(link.source_card_id))
        if link.target_card_id in card_ids:
            linked.add(str(link.target_card_id))
    return list(linked)


@router.post("/{link_id}/complete", response_model=CardLinkOut)
def complete_link(
    link_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Mark a card link as completed. Only the assignee of the target card can do this.
    Advances the source card to the next phase."""
    link = db.get(CardLink, link_id)
    if not link:
        raise HTTPException(404, "Link nao encontrado")
    if link.status == "completed":
        raise HTTPException(400, "Link ja foi concluido")

    target_card = db.get(Card, link.target_card_id)
    if not target_card:
        raise HTTPException(404, "Card destino nao encontrado")

    # Only assignee or admin can complete
    if target_card.assignee_id and target_card.assignee_id != current.id and current.role != "admin":
        raise HTTPException(403, "Somente o responsavel designado pode concluir esta tarefa")

    conn = db.get(BoardConnection, link.connection_id)
    if not conn:
        raise HTTPException(404, "Conexao nao encontrada")

    # Mark link as completed
    link.status = "completed"
    link.completed_at = datetime.now(timezone.utc)

    # Move target card to completion phase
    target_card.phase_id = conn.completion_phase_id
    target_card.position = 0
    db.flush()

    # Advance source card to the next phase
    source_card = db.get(Card, link.source_card_id)
    if source_card:
        source_card.phase_id = conn.advance_to_phase_id
        source_card.position = 0

    db.commit()
    db.refresh(link)

    log_activity(db, user_id=current.id, action="complete_card_link",
                 entity_type="card_link", entity_id=link.id,
                 details={"source_card": str(link.source_card_id),
                          "target_card": str(link.target_card_id)})
    db.commit()

    return CardLinkOut(
        id=link.id, connection_id=link.connection_id,
        source_card_id=link.source_card_id, target_card_id=link.target_card_id,
        status=link.status, created_at=link.created_at, completed_at=link.completed_at,
    )
