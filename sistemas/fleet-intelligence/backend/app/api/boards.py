"""Board routes: CRUD de fluxos Kanban."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import exists, select
from sqlalchemy.orm import Session, selectinload

from ..core.activity import log_activity
from ..database import get_db
from ..models import Board, BoardConnection, BoardPermission, Phase, User
from ..schemas import BoardCreate, BoardOut, BoardUpdate, BoardWithPhases
from .deps import get_current_user, require_admin, require_not_viewer

router = APIRouter(prefix="/boards", tags=["boards"])


def _user_can_see_board(db: Session, board_id: uuid.UUID, user: User) -> bool:
    if user.role == "admin":
        return True
    has_perms = db.execute(
        select(exists().where(BoardPermission.board_id == board_id))
    ).scalar()
    if not has_perms:
        return True
    return db.execute(
        select(exists().where(
            BoardPermission.board_id == board_id,
            BoardPermission.user_id == user.id,
        ))
    ).scalar()


@router.get("", response_model=list[BoardOut])
def list_boards(
    include_archived: bool = False,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[Board]:
    stmt = select(Board).order_by(Board.created_at.desc())
    if not include_archived:
        stmt = stmt.where(Board.is_archived.is_(False))
    boards = list(db.execute(stmt).scalars())
    if current.role != "admin":
        boards = [b for b in boards if _user_can_see_board(db, b.id, current)]
    return boards


@router.post("", response_model=BoardOut, status_code=status.HTTP_201_CREATED)
def create_board(
    payload: BoardCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_not_viewer),
) -> Board:
    board = Board(
        name=payload.name,
        description=payload.description,
        color=payload.color,
        icon=payload.icon,
        owner_id=current.id,
    )
    db.add(board)
    db.commit()
    db.refresh(board)
    log_activity(db, user_id=current.id, action="create_board",
                 entity_type="board", entity_id=board.id,
                 details={"name": board.name})
    db.commit()
    return board


@router.get("/{board_id}", response_model=BoardWithPhases)
def get_board(
    board_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> Board:
    if not _user_can_see_board(db, board_id, current):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Voce nao tem acesso a este fluxo")
    stmt = (
        select(Board)
        .where(Board.id == board_id)
        .options(selectinload(Board.phases).selectinload(Phase.cards))
    )
    board = db.execute(stmt).scalar_one_or_none()
    if not board:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fluxo nao encontrado")
    return board


@router.patch("/{board_id}", response_model=BoardOut)
def update_board(
    board_id: uuid.UUID,
    payload: BoardUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_not_viewer),
) -> Board:
    board = db.get(Board, board_id)
    if not board:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fluxo nao encontrado")
    changes = payload.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(board, k, v)
    db.commit()
    db.refresh(board)
    log_activity(db, user_id=current.id, action="update_board",
                 entity_type="board", entity_id=board.id,
                 details={"changes": list(changes.keys())})
    db.commit()
    return board


@router.delete("/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board(
    board_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: User = Depends(require_not_viewer),
) -> None:
    board = db.get(Board, board_id)
    if not board:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fluxo nao encontrado")
    board_name = board.name
    db.delete(board)
    db.commit()
    log_activity(db, user_id=current.id, action="delete_board",
                 entity_type="board", entity_id=board_id,
                 details={"name": board_name})
    db.commit()


# ---------- Demo Setup ----------

class DemoSetupOut(BaseModel):
    created: bool
    main_board_id: str
    sub_board_id: str
    connection_id: str
    message: str


DEMO_MAIN_NAME = "Fluxo Principal"
DEMO_SUB_NAME = "Subfluxo - Documentacao"


@router.post("/seed-demo", response_model=DemoSetupOut)
def seed_demo(
    db: Session = Depends(get_db),
    current: User = Depends(require_admin),
) -> DemoSetupOut:
    """Cria os 2 fluxos de demonstracao com conexao configurada. Idempotente."""

    existing_main = db.execute(
        select(Board).where(Board.name == DEMO_MAIN_NAME, Board.is_archived.is_(False))
    ).scalar_one_or_none()

    if existing_main:
        existing_sub = db.execute(
            select(Board).where(Board.name == DEMO_SUB_NAME, Board.is_archived.is_(False))
        ).scalar_one_or_none()
        existing_conn = db.execute(
            select(BoardConnection).where(BoardConnection.source_board_id == existing_main.id)
        ).scalar_one_or_none()
        return DemoSetupOut(
            created=False,
            main_board_id=str(existing_main.id),
            sub_board_id=str(existing_sub.id) if existing_sub else "",
            connection_id=str(existing_conn.id) if existing_conn else "",
            message="Fluxos de demonstracao ja existem",
        )

    # Fluxo Principal
    main_board = Board(
        name=DEMO_MAIN_NAME,
        description="Fluxo principal de aprovacao de documentos",
        color="indigo",
        icon="Workflow",
        owner_id=current.id,
    )
    db.add(main_board)
    db.flush()

    main_phases_def = [
        ("Informacoes Iniciais", "indigo", 0),
        ("Aguardando Documentacao", "amber", 1),
        ("Analise de Aprovacao", "violet", 2),
        ("Concluido", "emerald", 3),
    ]
    main_phases = []
    for ph_name, ph_color, ph_pos in main_phases_def:
        ph = Phase(board_id=main_board.id, name=ph_name, color=ph_color, position=ph_pos)
        db.add(ph)
        main_phases.append(ph)
    db.flush()

    # Subfluxo - Documentacao
    sub_board = Board(
        name=DEMO_SUB_NAME,
        description="Subfluxo para upload e validacao de documentos",
        color="blue",
        icon="FileText",
        owner_id=current.id,
    )
    db.add(sub_board)
    db.flush()

    sub_phases_def = [
        ("Upload de Documento", "blue", 0),
        ("Documento Enviado", "indigo", 1),
        ("Aprovado", "emerald", 2),
    ]
    sub_phases = []
    for ph_name, ph_color, ph_pos in sub_phases_def:
        ph = Phase(board_id=sub_board.id, name=ph_name, color=ph_color, position=ph_pos)
        db.add(ph)
        sub_phases.append(ph)
    db.flush()

    # Connection:
    # trigger_phase    = main[1] "Aguardando Documentacao" -> cria card filho em sub[0]
    # target_phase     = sub[0]  "Upload de Documento"    -> onde o card filho nasce
    # completion_phase = sub[1]  "Documento Enviado"      -> ao chegar aqui auto-avanca main
    # advance_to_phase = main[2] "Analise de Aprovacao"   -> gestor aprova/rejeita
    conn = BoardConnection(
        source_board_id=main_board.id,
        target_board_id=sub_board.id,
        trigger_phase_id=main_phases[1].id,
        target_phase_id=sub_phases[0].id,
        completion_phase_id=sub_phases[1].id,
        advance_to_phase_id=main_phases[2].id,
        is_active=True,
    )
    db.add(conn)
    db.commit()

    log_activity(db, user_id=current.id, action="seed_demo",
                 entity_type="board", entity_id=main_board.id,
                 details={"main_board": str(main_board.id), "sub_board": str(sub_board.id)})
    db.commit()

    return DemoSetupOut(
        created=True,
        main_board_id=str(main_board.id),
        sub_board_id=str(sub_board.id),
        connection_id=str(conn.id),
        message="Fluxos de demonstracao criados com sucesso",
    )
