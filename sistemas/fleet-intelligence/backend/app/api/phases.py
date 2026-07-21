"""Phase routes: colunas do Kanban."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.activity import log_activity
from ..database import get_db
from ..models import Board, Phase, User
from ..schemas import PhaseCreate, PhaseOut, PhaseReorder, PhaseUpdate
from .deps import get_current_user, require_not_viewer

router = APIRouter(tags=["phases"])


@router.get("/boards/{board_id}/phases", response_model=list[PhaseOut])
def list_phases(
    board_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Phase]:
    stmt = select(Phase).where(Phase.board_id == board_id).order_by(Phase.position)
    return list(db.execute(stmt).scalars())


@router.post(
    "/boards/{board_id}/phases",
    response_model=PhaseOut,
    status_code=status.HTTP_201_CREATED,
)
def create_phase(
    board_id: uuid.UUID,
    payload: PhaseCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_not_viewer),
) -> Phase:
    if not db.get(Board, board_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fluxo nao encontrado")

    position = payload.position
    if position is None:
        max_pos = db.execute(
            select(func.coalesce(func.max(Phase.position), -1)).where(
                Phase.board_id == board_id
            )
        ).scalar_one()
        position = int(max_pos) + 1

    phase = Phase(
        board_id=board_id,
        name=payload.name,
        color=payload.color,
        wip_limit=payload.wip_limit,
        position=position,
    )
    db.add(phase)
    db.commit()
    db.refresh(phase)
    log_activity(db, user_id=current.id, action="create_phase",
                 entity_type="phase", entity_id=phase.id,
                 details={"name": phase.name, "board_id": str(board_id)})
    db.commit()
    return phase


@router.patch("/phases/{phase_id}", response_model=PhaseOut)
def update_phase(
    phase_id: uuid.UUID,
    payload: PhaseUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_not_viewer),
) -> Phase:
    phase = db.get(Phase, phase_id)
    if not phase:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fase nao encontrada")
    changes = payload.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(phase, k, v)
    db.commit()
    db.refresh(phase)
    log_activity(db, user_id=current.id, action="update_phase",
                 entity_type="phase", entity_id=phase.id,
                 details={"name": phase.name, "changes": list(changes.keys())})
    db.commit()
    return phase


@router.delete("/phases/{phase_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_phase(
    phase_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: User = Depends(require_not_viewer),
) -> None:
    phase = db.get(Phase, phase_id)
    if not phase:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fase nao encontrada")
    phase_name = phase.name
    board_id = phase.board_id
    db.delete(phase)
    db.commit()
    log_activity(db, user_id=current.id, action="delete_phase",
                 entity_type="phase", entity_id=phase_id,
                 details={"name": phase_name, "board_id": str(board_id)})
    db.commit()


@router.post("/boards/{board_id}/phases/reorder", response_model=list[PhaseOut])
def reorder_phases(
    board_id: uuid.UUID,
    payload: PhaseReorder,
    db: Session = Depends(get_db),
    _: User = Depends(require_not_viewer),
) -> list[Phase]:
    phases = list(
        db.execute(select(Phase).where(Phase.board_id == board_id)).scalars()
    )
    phase_map = {p.id: p for p in phases}
    if set(phase_map.keys()) != set(payload.phase_ids):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "phase_ids deve conter exatamente as fases existentes do fluxo",
        )
    for i, pid in enumerate(payload.phase_ids):
        phase_map[pid].position = 1000 + i
    db.flush()
    for i, pid in enumerate(payload.phase_ids):
        phase_map[pid].position = i
    db.commit()
    return [phase_map[pid] for pid in payload.phase_ids]
