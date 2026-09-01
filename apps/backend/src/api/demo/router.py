"""
Router de Demo - genera excels de ventas sintéticos para probar el
pipeline sin craftear filas a mano.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.demo.schemas import GenerateExcelRequest, GenerateExcelResponse
from src.api.demo.service import DemoService
from src.infrastructure.db.session import SessionLocal

router = APIRouter(prefix="/demo", tags=["demo"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/generate-excel", response_model=GenerateExcelResponse)
def generate_excel(payload: GenerateExcelRequest, db: Session = Depends(get_db)):
    """Genera un excel de ventas sintético (referenciando catálogos
    reales) con `error_rate` de probabilidad de inyectar una violación
    por fila. Devuelve una URL de descarga + el detalle de qué se
    inyectó, para comparar después contra lo que gold detecte."""
    service = DemoService(db)
    return service.generate_excel(payload.filas, payload.error_rate)
