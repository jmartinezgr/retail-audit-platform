"""
Router de Audits - dispara y consulta el procesamiento de un upload
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from src.api.audits.schemas import (
    DashboardResponse,
    DualLayerPreviewResponse,
    ExportProblematicResponse,
    FacturaDetailResponse,
    GoldMatrixResponse,
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


@router.get("/{upload_id}/bronze", response_model=DualLayerPreviewResponse)
def get_bronze(upload_id: str, db: Session = Depends(get_db)):
    """Consulta las tablas bronze resultantes (facturas + items)"""
    service = AuditService(db)
    return service.get_bronze_preview(upload_id)


@router.get("/{upload_id}/silver", response_model=DualLayerPreviewResponse)
def get_silver(upload_id: str, db: Session = Depends(get_db)):
    """Consulta las tablas silver resultantes (facturas + items)"""
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
    numero_factura: str | None = None,
    db: Session = Depends(get_db),
):
    """Página filtrada de gold, vía DuckDB directo sobre la tabla Delta -
    para la tabla de resultados del frontend (puede haber decenas de
    miles de filas, esto no es el preview fijo de /gold)"""
    service = AuditService(db)
    return service.query_gold(
        upload_id, limit, offset, severidad, regla, sede_codigo, paso, numero_factura
    )


@router.get("/{upload_id}/gold/summary", response_model=GoldSummaryResponse)
def gold_summary(upload_id: str, db: Session = Depends(get_db)):
    """Conteo por (regla, severidad, paso) - para poblar filtros y un
    resumen rápido sin traer las filas"""
    service = AuditService(db)
    return service.get_gold_summary(upload_id)


@router.get("/{upload_id}/gold/matrix", response_model=GoldMatrixResponse)
def gold_matrix(
    upload_id: str,
    limit: int = Query(default=25, gt=0, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Página de la matriz factura x regla (peor caso por factura) - vía
    DuckDB, paginada por factura (no por fila) para que el frontend
    pueda pivotearla a una tabla ancha de un vistazo"""
    service = AuditService(db)
    return service.get_gold_matrix(upload_id, limit, offset)


@router.get("/{upload_id}/factura/{numero_factura}", response_model=FacturaDetailResponse)
def get_factura_detail(upload_id: str, numero_factura: str, db: Session = Depends(get_db)):
    """Todo lo relacionado a una factura puntual: la cabecera y sus ítems
    (silver) + cada regla evaluada contra ella (gold) - para la página de
    detalle de factura del frontend"""
    service = AuditService(db)
    return service.get_factura_detail(upload_id, numero_factura)


@router.get("/{upload_id}/dashboard", response_model=DashboardResponse)
def get_dashboard(upload_id: str, db: Session = Depends(get_db)):
    """Resumen ejecutivo de la corrida: facturas válidas/con error/solo
    warning, problemas de itemización, valor registrado vs. valor de las
    facturas 100% válidas, y ranking de reglas por facturas afectadas"""
    service = AuditService(db)
    return service.get_dashboard(upload_id)


@router.post("/{upload_id}/export/problematic", response_model=ExportProblematicResponse)
def export_problematic(upload_id: str, db: Session = Depends(get_db)):
    """Genera y sube un excel (2 hojas: resumen de facturas problemáticas
    + detalle de cada violación) y devuelve una URL de descarga prefirmada"""
    service = AuditService(db)
    return service.export_problematic(upload_id)
