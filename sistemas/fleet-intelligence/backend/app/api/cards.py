"""Card routes: itens dentro das fases."""
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..core.activity import log_activity
from ..database import get_db
from ..models import Board, BoardConnection, Card, CardLink, Phase, User
from ..schemas import CardCreate, CardMove, CardOut, CardUpdate
from .deps import get_current_user, require_not_viewer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cards", tags=["cards"])


def _load_phase(db: Session, phase_id: uuid.UUID) -> Phase:
    phase = db.get(Phase, phase_id)
    if not phase:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fase nao encontrada")
    return phase


def _next_position(db: Session, phase_id: uuid.UUID) -> int:
    max_pos = db.execute(
        select(func.coalesce(func.max(Card.position), -1)).where(
            Card.phase_id == phase_id
        )
    ).scalar_one()
    return int(max_pos) + 1


def _trigger_crossflow(db: Session, card: Card, phase_id: uuid.UUID, current_user_id: uuid.UUID):
    """If the card lands on a trigger phase, create a linked child card in the target board."""
    phase = db.get(Phase, phase_id)
    if not phase:
        return

    conns = list(db.execute(
        select(BoardConnection).where(
            BoardConnection.trigger_phase_id == phase_id,
            BoardConnection.source_board_id == phase.board_id,
            BoardConnection.is_active.is_(True),
        )
    ).scalars())

    for conn in conns:
        existing = db.execute(
            select(CardLink).where(
                CardLink.source_card_id == card.id,
                CardLink.connection_id == conn.id,
            )
        ).scalar_one_or_none()
        if existing:
            continue

        child = Card(
            phase_id=conn.target_phase_id,
            title=card.title,
            description=card.description,
            priority=card.priority,
            assignee_id=card.assignee_id,
            due_date=card.due_date,
            tags=card.tags or [],
            card_metadata=card.card_metadata or {},
            position=_next_position(db, conn.target_phase_id),
            created_by=current_user_id,
        )
        db.add(child)
        db.flush()

        link = CardLink(
            connection_id=conn.id,
            source_card_id=card.id,
            target_card_id=child.id,
            status="pending",
        )
        db.add(link)
        db.flush()

        logger.info("Cross-flow: card %s -> child %s (conn %s)", card.id, child.id, conn.id)
        log_activity(db, user_id=current_user_id, action="crossflow_create",
                     entity_type="card_link", entity_id=link.id,
                     details={"parent_title": card.title, "child_card_id": str(child.id)})


@router.get("/chassi-lookup")
def chassi_lookup(
    chassi: str = Query(..., min_length=1, description="Numero do chassi a consultar"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Busca informacoes do equipamento pelo chassi no banco de dados."""
    sql = text("""
        WITH cte_protheus AS (
            SELECT DISTINCT ON (tccp.vv1_chassi)
                tccp.vv1_chassi AS chassi,
                tccp.a1_cgc AS protheus_cpf_cnpj,
                tccp.a1_nome AS protheus_cliente,
                tc.nome AS protheus_cliente2,
                tc.nome_fantasia,
                tc.uf,
                COALESCE(
                    NULLIF(tc.telefone, ''),
                    NULLIF(tc.telefone_pcs, ''),
                    NULLIF(tc.telefone_ofi, ''),
                    NULLIF(tc.telefone_vda, ''),
                    'nao tem'
                ) AS telefone,
                COALESCE(
                    NULLIF(tc.email, ''),
                    NULLIF(tc.email1, ''),
                    NULLIF(tc.email2, ''),
                    'nao tem'
                ) AS email,
                tc.contato
            FROM layer_bronze.tb_cliente_chassi_protheus tccp
            LEFT JOIN tb_cliente tc ON tccp.a1_cgc = tc.cnpj_cpf
        ),
        cte_horimetro AS (
            SELECT DISTINCT ON (om.serial_number)
                om.serial_number AS chassi,
                oeh.reading_value AS horimetro,
                oeh.report_time AS data_horimetro
            FROM layer_bronze.opc_engine_hours oeh
            LEFT JOIN layer_bronze.opc_equipment om ON om.principal_id = oeh.principal_id
            ORDER BY om.serial_number, oeh.reading_value DESC
        ),
        cte_localizacao AS (
            SELECT DISTINCT ON (oe.serial_number)
                oe.serial_number AS chassi,
                lm.latitude,
                lm.longitude,
                lm.estado,
                lm.cidade,
                lm.mesorregiao,
                lm.regional
            FROM localizacao_maquinas lm
            LEFT JOIN layer_bronze.opc_equipment oe ON lm.principal_id = oe.principal_id
            ORDER BY oe.serial_number, lm.principal_id
        )
        SELECT
            p.chassi,
            p.protheus_cpf_cnpj,
            p.protheus_cliente,
            p.protheus_cliente2,
            p.nome_fantasia,
            p.uf,
            p.telefone,
            p.email,
            p.contato,
            h.horimetro,
            h.data_horimetro,
            l.latitude,
            l.longitude,
            l.estado,
            l.cidade,
            l.mesorregiao,
            l.regional
        FROM cte_protheus p
        LEFT JOIN cte_horimetro h ON h.chassi = p.chassi
        LEFT JOIN cte_localizacao l ON l.chassi = p.chassi
        WHERE p.chassi = :chassi
    """)

    try:
        row = db.execute(sql, {"chassi": chassi.strip().upper()}).mappings().fetchone()
    except Exception as exc:
        logger.error("Chassi lookup error: %s", exc)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            "Erro ao consultar banco de dados") from exc

    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Chassi '{chassi}' nao encontrado")

    data_h = row.get("data_horimetro")
    return {
        "chassi": row.get("chassi"),
        "cliente": row.get("protheus_cliente"),
        "cpf_cnpj": row.get("protheus_cpf_cnpj"),
        "email": row.get("email"),
        "telefone": row.get("telefone"),
        "contato": row.get("contato"),
        "horimetro": str(row.get("horimetro") or ""),
        "data_horimetro": data_h.isoformat() if data_h else None,
        "cidade": row.get("cidade"),
        "estado": row.get("estado"),
        "regional": row.get("regional"),
        "latitude": str(row.get("latitude") or ""),
        "longitude": str(row.get("longitude") or ""),
    }


@router.get("", response_model=list[CardOut])
def list_cards(
    phase_id: uuid.UUID | None = None,
    assignee_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Card]:
    stmt = select(Card).order_by(Card.phase_id, Card.position)
    if phase_id:
        stmt = stmt.where(Card.phase_id == phase_id)
    if assignee_id:
        stmt = stmt.where(Card.assignee_id == assignee_id)
    return list(db.execute(stmt).scalars())


@router.post("", response_model=CardOut, status_code=status.HTTP_201_CREATED)
def create_card(
    payload: CardCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_not_viewer),
) -> Card:
    _load_phase(db, payload.phase_id)
    position = payload.position
    if position is None:
        position = _next_position(db, payload.phase_id)

    card = Card(
        phase_id=payload.phase_id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        assignee_id=payload.assignee_id,
        due_date=payload.due_date,
        tags=payload.tags or [],
        card_metadata=payload.metadata or {},
        position=position,
        created_by=current.id,
    )
    db.add(card)
    db.flush()

    _trigger_crossflow(db, card, payload.phase_id, current.id)

    db.commit()
    db.refresh(card)
    log_activity(db, user_id=current.id, action="create_card",
                 entity_type="card", entity_id=card.id,
                 details={"title": card.title, "phase_id": str(payload.phase_id)})
    db.commit()
    return card


@router.get("/{card_id}", response_model=CardOut)
def get_card(
    card_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Card:
    card = db.get(Card, card_id)
    if not card:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Card nao encontrado")
    return card


@router.patch("/{card_id}", response_model=CardOut)
def update_card(
    card_id: uuid.UUID,
    payload: CardUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_not_viewer),
) -> Card:
    card = db.get(Card, card_id)
    if not card:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Card nao encontrado")
    data = payload.model_dump(exclude_unset=True)
    if "metadata" in data:
        incoming = data.pop("metadata") or {}
        # Preserve system keys (_completed etc) unless explicitly overwritten
        merged = {**card.card_metadata}
        merged.update(incoming)
        card.card_metadata = merged
    changed_keys = list(data.keys())
    for k, v in data.items():
        setattr(card, k, v)
    db.commit()
    db.refresh(card)
    log_activity(db, user_id=current.id, action="update_card",
                 entity_type="card", entity_id=card.id,
                 details={"title": card.title, "changes": changed_keys})
    db.commit()
    return card


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card(
    card_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: User = Depends(require_not_viewer),
) -> None:
    card = db.get(Card, card_id)
    if not card:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Card nao encontrado")
    card_title = card.title
    db.delete(card)
    db.commit()
    log_activity(db, user_id=current.id, action="delete_card",
                 entity_type="card", entity_id=card_id,
                 details={"title": card_title})
    db.commit()


@router.post("/{card_id}/move", response_model=CardOut)
def move_card(
    card_id: uuid.UUID,
    payload: CardMove,
    db: Session = Depends(get_db),
    current: User = Depends(require_not_viewer),
) -> Card:
    """Move a card to another phase and/or position."""
    card = db.get(Card, card_id)
    if not card:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Card nao encontrado")

    target_link_check = db.execute(
        select(CardLink).where(
            CardLink.target_card_id == card.id,
            CardLink.status == "pending",
        )
    ).scalar_one_or_none()
    if target_link_check and card.assignee_id and card.assignee_id != current.id and current.role != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Somente o responsavel designado pode mover este card"
        )

    _load_phase(db, payload.target_phase_id)

    source_phase_id = card.phase_id
    target_phase_id = payload.target_phase_id
    target_pos = payload.target_position

    same_phase = source_phase_id == target_phase_id

    card.position = -1
    card.phase_id = target_phase_id
    db.flush()

    if same_phase:
        siblings = list(
            db.execute(
                select(Card)
                .where(Card.phase_id == target_phase_id, Card.id != card.id)
                .order_by(Card.position)
            ).scalars()
        )
    else:
        source_siblings = list(
            db.execute(
                select(Card)
                .where(Card.phase_id == source_phase_id)
                .order_by(Card.position)
            ).scalars()
        )
        for i, s in enumerate(source_siblings):
            s.position = i
        db.flush()

        siblings = list(
            db.execute(
                select(Card)
                .where(Card.phase_id == target_phase_id, Card.id != card.id)
                .order_by(Card.position)
            ).scalars()
        )

    target_pos = max(0, min(target_pos, len(siblings)))
    new_order = siblings[:target_pos] + [card] + siblings[target_pos:]
    for i, c in enumerate(new_order):
        c.position = i

    if not same_phase:
        _trigger_crossflow(db, card, target_phase_id, current.id)

        # Auto-complete link: if this TARGET card moves to completion_phase,
        # advance the SOURCE card to advance_to_phase
        pending_link = db.execute(
            select(CardLink).where(
                CardLink.target_card_id == card.id,
                CardLink.status == "pending",
            )
        ).scalar_one_or_none()

        if pending_link:
            conn = db.get(BoardConnection, pending_link.connection_id)
            if conn and target_phase_id == conn.completion_phase_id:
                pending_link.status = "completed"
                pending_link.completed_at = datetime.now(timezone.utc)
                source_card = db.get(Card, pending_link.source_card_id)
                if source_card:
                    source_card.phase_id = conn.advance_to_phase_id
                    source_card.position = _next_position(db, conn.advance_to_phase_id)
                    db.flush()
                logger.info("Auto-complete link %s: target moved to completion phase", pending_link.id)
                log_activity(
                    db, user_id=current.id, action="crossflow_auto_advance",
                    entity_type="card_link", entity_id=pending_link.id,
                    details={"source_card": str(pending_link.source_card_id),
                             "advance_to_phase": str(conn.advance_to_phase_id)},
                )

    db.commit()
    db.refresh(card)

    if not same_phase:
        log_activity(db, user_id=current.id, action="move_card",
                     entity_type="card", entity_id=card.id,
                     details={"title": card.title,
                              "from_phase": str(source_phase_id),
                              "to_phase": str(target_phase_id)})
        db.commit()

    return card


@router.post("/{card_id}/approve", response_model=CardOut)
def approve_card(
    card_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: User = Depends(require_not_viewer),
) -> Card:
    """Gestor aprova o documento. Conclui o card no fluxo principal e no subfluxo."""
    card = db.get(Card, card_id)
    if not card:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Card nao encontrado")

    link = db.execute(
        select(CardLink).where(
            CardLink.source_card_id == card.id,
            CardLink.status == "completed",
        )
    ).scalar_one_or_none()

    if not link:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Este card nao possui documentacao pendente de aprovacao",
        )

    conn = db.get(BoardConnection, link.connection_id)
    if not conn:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conexao nao encontrada")

    # Move main card to next phase after current
    current_phase = db.get(Phase, card.phase_id)
    if current_phase:
        next_phase = db.execute(
            select(Phase)
            .where(Phase.board_id == current_phase.board_id,
                   Phase.position > current_phase.position)
            .order_by(Phase.position)
        ).scalars().first()
        if next_phase:
            card.phase_id = next_phase.id
            card.position = _next_position(db, next_phase.id)

    # Mark main card as completed
    card.card_metadata = {**(card.card_metadata or {}), "_completed": True}

    # Move subflow card to last phase of subflow and mark completed
    last_sub_phase = db.execute(
        select(Phase)
        .where(Phase.board_id == conn.target_board_id)
        .order_by(Phase.position.desc())
    ).scalars().first()

    target_card = db.get(Card, link.target_card_id)
    if target_card and last_sub_phase:
        target_card.phase_id = last_sub_phase.id
        target_card.position = _next_position(db, last_sub_phase.id)
        target_card.card_metadata = {**(target_card.card_metadata or {}), "_completed": True}

    link.status = "approved"

    db.commit()
    db.refresh(card)

    log_activity(db, user_id=current.id, action="approve_card",
                 entity_type="card", entity_id=card.id,
                 details={"title": card.title, "link_id": str(link.id),
                          "target_card": str(link.target_card_id)})
    db.commit()
    return card


@router.post("/{card_id}/reject", response_model=CardOut)
def reject_card(
    card_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: User = Depends(require_not_viewer),
) -> Card:
    """Gestor rejeita o documento. Volta ambos os cards para reiniciar o processo."""
    card = db.get(Card, card_id)
    if not card:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Card nao encontrado")

    link = db.execute(
        select(CardLink).where(
            CardLink.source_card_id == card.id,
            CardLink.status == "completed",
        )
    ).scalar_one_or_none()

    if not link:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Este card nao possui documentacao pendente de aprovacao",
        )

    conn = db.get(BoardConnection, link.connection_id)
    if not conn:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conexao nao encontrada")

    # Move main card back to trigger phase
    card.phase_id = conn.trigger_phase_id
    card.position = _next_position(db, conn.trigger_phase_id)
    # Remove completed flag if present
    meta = dict(card.card_metadata or {})
    meta.pop("_completed", None)
    card.card_metadata = meta

    # Move subflow card back to target phase (upload)
    target_card = db.get(Card, link.target_card_id)
    if target_card:
        target_card.phase_id = conn.target_phase_id
        target_card.position = _next_position(db, conn.target_phase_id)
        sub_meta = dict(target_card.card_metadata or {})
        sub_meta.pop("_completed", None)
        target_card.card_metadata = sub_meta

    # Reset link to pending so the process can restart
    link.status = "pending"
    link.completed_at = None

    db.commit()
    db.refresh(card)

    log_activity(db, user_id=current.id, action="reject_card",
                 entity_type="card", entity_id=card.id,
                 details={"title": card.title, "link_id": str(link.id),
                          "target_card": str(link.target_card_id)})
    db.commit()
    return card
