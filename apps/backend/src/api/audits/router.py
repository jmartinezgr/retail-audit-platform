"""
Router de Audits - dispara y consulta el procesamiento de un upload
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from src.api.audits.schemas import (
    GoldPageResponse,
    GoldSummaryResponse,
    LayerPreviewResponse,
    RunAuditResponse,
)
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
    """Dispara el pipeline (bronze -> silver) en background, no bloquea la
    respuesta"""
    service = AuditService(db)
    background_tasks.add_task(service.run_pipeline, upload_id)
    return {"upload_id": upload_id, "status": "PROCESSING"}


@router.get("/{upload_id}/bronze", response_model=LayerPreviewResponse)
def get_bronze(upload_id: str, db: Session = Depends(get_db)):
    """Consulta la tabla bronze resultante"""
    service = AuditService(db)
    return service.get_bronze_preview(upload_id)


@router.get("/{upload_id}/silver", response_model=LayerPreviewResponse)
def get_silver(upload_id: str, db: Session = Depends(get_db)):
    """Consulta la tabla silver resultante"""
    service = AuditService(db)
    return service.get_silver_preview(upload_id)


@router.post("/{upload_id}/run-gold", response_model=RunAuditResponse)
def run_gold(
    upload_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Regenera gold a partir del silver YA GUARDADO + el estado actual de
    los catálogos, sin volver a subir el excel ni rehacer bronze/silver"""
    service = AuditService(db)
    background_tasks.add_task(service.run_gold, upload_id)
    return {"upload_id": upload_id, "status": "PROCESSING"}


@router.get("/{upload_id}/gold", response_model=LayerPreviewResponse)
def get_gold(upload_id: str, db: Session = Depends(get_db)):
    """Consulta la tabla gold resultante (preview fijo, primeras filas)"""
    service = AuditService(db)
    return service.get_gold_preview(upload_id)


@router.get("/{upload_id}/gold/query", response_model=GoldPageResponse)
def query_gold(
    upload_id: str,
    limit: int = Query(default=50, gt=0, le=1000),
    offset: int = Query(default=0, ge=0),
    severidad: str | None = None,
    regla: str | None = None,
    sede_codigo: str | None = None,
    paso: bool | None = None,
    db: Session = Depends(get_db),
):
    """Página filtrada de gold, vía DuckDB directo sobre la tabla Delta -
    para la tabla de resultados del frontend (puede haber decenas de
    miles de filas, esto no es el preview fijo de /gold)"""
    service = AuditService(db)
    return service.query_gold(upload_id, limit, offset, severidad, regla, sede_codigo, paso)


@router.get("/{upload_id}/gold/summary", response_model=GoldSummaryResponse)
def gold_summary(upload_id: str, db: Session = Depends(get_db)):
    """Conteo por (regla, severidad, paso) - para poblar filtros y un
    resumen rápido sin traer las filas"""
    service = AuditService(db)
    return service.get_gold_summary(upload_id)
