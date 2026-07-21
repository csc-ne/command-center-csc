"""Card attachment routes: upload/download/delete files."""
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.activity import log_activity
from ..database import get_db
from ..models import Card, CardAttachment, User
from .deps import get_current_user, require_not_viewer

router = APIRouter(prefix="/attachments", tags=["attachments"])

UPLOAD_DIR = "/app/uploads"
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_TYPES = {
    "image/png", "image/jpeg", "image/jpg", "image/webp",
    "application/pdf",
}


class AttachmentOut(BaseModel):
    id: uuid.UUID
    card_id: uuid.UUID
    uploaded_by: uuid.UUID
    uploaded_by_name: str | None = None
    filename: str
    file_size: int
    mime_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/card/{card_id}", response_model=list[AttachmentOut])
def list_attachments(
    card_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all attachments for a card."""
    attachments = list(db.execute(
        select(CardAttachment)
        .where(CardAttachment.card_id == card_id)
        .order_by(CardAttachment.created_at.desc())
    ).scalars())
    results = []
    for a in attachments:
        uploader = db.get(User, a.uploaded_by)
        results.append(AttachmentOut(
            id=a.id, card_id=a.card_id, uploaded_by=a.uploaded_by,
            uploaded_by_name=uploader.full_name if uploader else None,
            filename=a.filename, file_size=a.file_size,
            mime_type=a.mime_type, created_at=a.created_at,
        ))
    return results


@router.post("/card/{card_id}", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    card_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current: User = Depends(require_not_viewer),
):
    """Upload a file to a card."""
    card = db.get(Card, card_id)
    if not card:
        raise HTTPException(404, "Card nao encontrado")

    # Validate type
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Tipo de arquivo nao permitido: {content_type}. Use PNG, JPG ou PDF.")

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"Arquivo muito grande. Limite: {MAX_FILE_SIZE // (1024*1024)}MB")

    # Save to disk
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename or "file")[1]
    stored_name = f"{file_id}{ext}"
    file_path = os.path.join(UPLOAD_DIR, stored_name)

    with open(file_path, "wb") as f:
        f.write(content)

    attachment = CardAttachment(
        card_id=card_id,
        uploaded_by=current.id,
        filename=file.filename or "arquivo",
        file_path=file_path,
        file_size=len(content),
        mime_type=content_type,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    log_activity(db, user_id=current.id, action="upload_attachment",
                 entity_type="card", entity_id=card_id,
                 details={"filename": attachment.filename})
    db.commit()

    return AttachmentOut(
        id=attachment.id, card_id=attachment.card_id,
        uploaded_by=attachment.uploaded_by,
        uploaded_by_name=current.full_name,
        filename=attachment.filename, file_size=attachment.file_size,
        mime_type=attachment.mime_type, created_at=attachment.created_at,
    )


@router.get("/{attachment_id}/download")
def download_attachment(
    attachment_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Download an attachment file."""
    attachment = db.get(CardAttachment, attachment_id)
    if not attachment:
        raise HTTPException(404, "Anexo nao encontrado")
    if not os.path.exists(attachment.file_path):
        raise HTTPException(404, "Arquivo nao encontrado no servidor")
    return FileResponse(
        attachment.file_path,
        media_type=attachment.mime_type,
        filename=attachment.filename,
    )


@router.delete("/{attachment_id}", status_code=204)
def delete_attachment(
    attachment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: User = Depends(require_not_viewer),
):
    """Delete an attachment."""
    attachment = db.get(CardAttachment, attachment_id)
    if not attachment:
        raise HTTPException(404, "Anexo nao encontrado")

    # Remove file from disk
    if os.path.exists(attachment.file_path):
        os.remove(attachment.file_path)

    filename = attachment.filename
    card_id = attachment.card_id
    db.delete(attachment)
    db.commit()

    log_activity(db, user_id=current.id, action="delete_attachment",
                 entity_type="card", entity_id=card_id,
                 details={"filename": filename})
    db.commit()
