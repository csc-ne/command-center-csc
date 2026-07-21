"""Board connections & permissions routes (admin-only)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.activity import log_activity
from ..database import get_db
from ..models import Board, BoardConnection, BoardPermission, Phase, User
from .deps import get_current_user, require_admin

router = APIRouter(tags=["connections"])


# ---------- Schemas ----------

class ConnectionCreate(BaseModel):
    source_board_id: uuid.UUID
    target_board_id: uuid.UUID
    trigger_phase_id: uuid.UUID
    target_phase_id: uuid.UUID
    completion_phase_id: uuid.UUID
    advance_to_phase_id: uuid.UUID


class ConnectionOut(BaseModel):
    id: uuid.UUID
    source_board_id: uuid.UUID
    target_board_id: uuid.UUID
    trigger_phase_id: uuid.UUID
    target_phase_id: uuid.UUID
    completion_phase_id: uuid.UUID
    advance_to_phase_id: uuid.UUID
    is_active: bool
    # Resolved names for frontend display
    source_board_name: str | None = None
    target_board_name: str | None = None
    trigger_phase_name: str | None = None
    target_phase_name: str | None = None
    completion_phase_name: str | None = None
    advance_to_phase_name: str | None = None

    model_config = {"from_attributes": True}


class PermissionSet(BaseModel):
    user_ids: list[uuid.UUID]


class PermissionOut(BaseModel):
    board_id: uuid.UUID
    user_ids: list[uuid.UUID]
    user_names: list[str] = []


# ---------- Board Connections ----------

@router.get("/boards/{board_id}/connections", response_model=list[ConnectionOut])
def list_connections(
    board_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """List all connections where this board is source or target."""
    stmt = select(BoardConnection).where(
        (BoardConnection.source_board_id == board_id) |
        (BoardConnection.target_board_id == board_id)
    )
    conns = list(db.execute(stmt).scalars())
    results = []
    for c in conns:
        # Resolve names
        src_board = db.get(Board, c.source_board_id)
        tgt_board = db.get(Board, c.target_board_id)
        trigger_ph = db.get(Phase, c.trigger_phase_id)
        target_ph = db.get(Phase, c.target_phase_id)
        comp_ph = db.get(Phase, c.completion_phase_id)
        adv_ph = db.get(Phase, c.advance_to_phase_id)
        results.append(ConnectionOut(
            id=c.id,
            source_board_id=c.source_board_id,
            target_board_id=c.target_board_id,
            trigger_phase_id=c.trigger_phase_id,
            target_phase_id=c.target_phase_id,
            completion_phase_id=c.completion_phase_id,
            advance_to_phase_id=c.advance_to_phase_id,
            is_active=c.is_active,
            source_board_name=src_board.name if src_board else None,
            target_board_name=tgt_board.name if tgt_board else None,
            trigger_phase_name=trigger_ph.name if trigger_ph else None,
            target_phase_name=target_ph.name if target_ph else None,
            completion_phase_name=comp_ph.name if comp_ph else None,
            advance_to_phase_name=adv_ph.name if adv_ph else None,
        ))
    return results


@router.post("/boards/{board_id}/connections", response_model=ConnectionOut, status_code=201)
def create_connection(
    board_id: uuid.UUID,
    payload: ConnectionCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
):
    """Create a cross-flow connection."""
    if payload.source_board_id != board_id:
        raise HTTPException(400, "source_board_id deve ser o board da URL")
    if payload.source_board_id == payload.target_board_id:
        raise HTTPException(400, "Fluxo de origem e destino devem ser diferentes")

    conn = BoardConnection(
        source_board_id=payload.source_board_id,
        target_board_id=payload.target_board_id,
        trigger_phase_id=payload.trigger_phase_id,
        target_phase_id=payload.target_phase_id,
        completion_phase_id=payload.completion_phase_id,
        advance_to_phase_id=payload.advance_to_phase_id,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    log_activity(db, user_id=current.id, action="create_connection",
                 entity_type="board_connection", entity_id=conn.id,
                 details={"source": str(payload.source_board_id),
                          "target": str(payload.target_board_id)})
    db.commit()

    src_board = db.get(Board, conn.source_board_id)
    tgt_board = db.get(Board, conn.target_board_id)
    return ConnectionOut(
        id=conn.id,
        source_board_id=conn.source_board_id,
        target_board_id=conn.target_board_id,
        trigger_phase_id=conn.trigger_phase_id,
        target_phase_id=conn.target_phase_id,
        completion_phase_id=conn.completion_phase_id,
        advance_to_phase_id=conn.advance_to_phase_id,
        is_active=conn.is_active,
        source_board_name=src_board.name if src_board else None,
        target_board_name=tgt_board.name if tgt_board else None,
    )


@router.delete("/connections/{connection_id}", status_code=204)
def delete_connection(
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
):
    conn = db.get(BoardConnection, connection_id)
    if not conn:
        raise HTTPException(404, "Conexao nao encontrada")
    db.delete(conn)
    db.commit()
    log_activity(db, user_id=current.id, action="delete_connection",
                 entity_type="board_connection", entity_id=connection_id)
    db.commit()


# ---------- Board Permissions ----------

@router.get("/boards/{board_id}/permissions", response_model=PermissionOut)
def get_permissions(
    board_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Get which users have access to this board."""
    perms = list(db.execute(
        select(BoardPermission).where(BoardPermission.board_id == board_id)
    ).scalars())
    user_ids = [p.user_id for p in perms]
    user_names = []
    for uid in user_ids:
        u = db.get(User, uid)
        user_names.append(u.full_name if u else "?")
    return PermissionOut(board_id=board_id, user_ids=user_ids, user_names=user_names)


@router.put("/boards/{board_id}/permissions", response_model=PermissionOut)
def set_permissions(
    board_id: uuid.UUID,
    payload: PermissionSet,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
):
    """Replace the permission list for a board. Empty list = open to all."""
    if not db.get(Board, board_id):
        raise HTTPException(404, "Fluxo nao encontrado")

    # Delete existing
    existing = list(db.execute(
        select(BoardPermission).where(BoardPermission.board_id == board_id)
    ).scalars())
    for p in existing:
        db.delete(p)
    db.flush()

    # Insert new
    for uid in payload.user_ids:
        db.add(BoardPermission(board_id=board_id, user_id=uid))
    db.commit()

    log_activity(db, user_id=current.id, action="set_board_permissions",
                 entity_type="board", entity_id=board_id,
                 details={"user_count": len(payload.user_ids)})
    db.commit()

    user_names = []
    for uid in payload.user_ids:
        u = db.get(User, uid)
        user_names.append(u.full_name if u else "?")

    return PermissionOut(board_id=board_id, user_ids=payload.user_ids, user_names=user_names)
