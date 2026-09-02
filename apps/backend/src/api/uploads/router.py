"""
Router de Uploads - Simple y directo
"""

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from src.api.uploads.schemas import (
    ColumnValidationResponse,
    RequestUploadUrlRequest,
    RequestUploadUrlResponse,
    UploadStatusResponse,
)
from src.api.uploads.service import UploadService
from src.infrastructure.db.session import SessionLocal

router = APIRouter(prefix="/uploads", tags=["uploads"])

# Sesión anónima por navegador (ver nota en UploadModel) - el frontend
# manda un UUID que genera y guarda en localStorage. Sin header (curl,
# scripts, el visor viejo) cae a "anonymous" - no rompe nada existente,
# solo agrupa todo lo que no manda el header bajo una sesión compartida.
ANONYMOUS_SESSION = "anonymous"


def get_session_id(x_client_id: str | None = Header(default=None)) -> str:
    return x_client_id or ANONYMOUS_SESSION


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
    session_id: str = Depends(get_session_id),
    db: Session = Depends(get_db),
):
    """Generar URL presignada para upload"""
    service = UploadService(db)
    return service.request_upload_url(payload.filename, session_id)


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


@router.get("/{upload_id}/validate-columns", response_model=ColumnValidationResponse)
def validate_columns(upload_id: str, db: Session = Depends(get_db)):
    """Chequeo rápido de columnas del excel - no corre bronze/silver/gold"""
    service = UploadService(db)
    return service.validate_columns(upload_id)


@router.get("/", tags=["uploads"])
def list_recent_uploads(
    limit: int = 20,
    session_id: str = Depends(get_session_id),
    db: Session = Depends(get_db),
):
    """Listar uploads recientes de la sesión"""
    service = UploadService(db)
    uploads = service.list_recent(session_id, limit)
    return {"count": len(uploads), "uploads": uploads}
