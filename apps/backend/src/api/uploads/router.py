"""
Router de Uploads - Simple y directo
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.uploads.schemas import (
    RequestUploadUrlRequest,
    RequestUploadUrlResponse,
    UploadStatusResponse,
)
from src.api.uploads.service import UploadService
from src.infrastructure.db.session import SessionLocal

router = APIRouter(prefix="/uploads", tags=["uploads"])


def get_db():
    """Sesión de BD por request"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/request-upload-url", response_model=RequestUploadUrlResponse)
def request_upload_url(
    payload: RequestUploadUrlRequest,
    db: Session = Depends(get_db),
):
    """Generar URL presignada para upload"""
    service = UploadService(db)
    return service.request_upload_url(payload.filename)


@router.post("/confirm/{upload_id}")
def confirm_upload(upload_id: str, db: Session = Depends(get_db)):
    """Confirmar que upload terminó"""
    service = UploadService(db)
    return service.confirm_upload(upload_id)


@router.get("/{upload_id}/status", response_model=UploadStatusResponse)
def get_upload_status(upload_id: str, db: Session = Depends(get_db)):
    """Obtener estado de un upload"""
    service = UploadService(db)
    return service.get_upload_status(upload_id)


@router.get("/", tags=["uploads"])
def list_recent_uploads(limit: int = 20, db: Session = Depends(get_db)):
    """Listar uploads recientes"""
    service = UploadService(db)
    uploads = service.list_recent(limit)
    return {"count": len(uploads), "uploads": uploads}
