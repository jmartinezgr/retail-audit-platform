"""
Router de Audits - dispara y consulta el procesamiento de un upload
"""

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from src.api.audits.schemas import BronzePreviewResponse, RunAuditResponse
from src.api.audits.service import AuditService
from src.infrastructure.db.session import SessionLocal

router = APIRouter(prefix="/audits", tags=["audits"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/{upload_id}/run", response_model=RunAuditResponse)
def run_audit(
    upload_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Dispara el pipeline en background (no bloquea la respuesta)"""
    service = AuditService(db)
    background_tasks.add_task(service.run_bronze, upload_id)
    return {"upload_id": upload_id, "status": "PROCESSING"}


@router.get("/{upload_id}/bronze", response_model=BronzePreviewResponse)
def get_bronze(upload_id: str, db: Session = Depends(get_db)):
    """Consulta la tabla bronze resultante"""
    service = AuditService(db)
    return service.get_bronze_preview(upload_id)
