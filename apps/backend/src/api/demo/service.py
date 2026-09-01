"""
Servicio de demo - genera un excel de ventas sintético y lo sube al
bucket bajo demo/ (no crea un registro de upload; el usuario decide si
lo sube por el flujo normal para correr el pipeline sobre él).
"""

import uuid
from io import BytesIO

from sqlalchemy.orm import Session

from src.domain.demo.generator import generar_ventas
from src.infrastructure.db.catalog.snapshot import load_catalog_snapshot
from src.infrastructure.storage.minio_client import (
    get_presigned_download_url,
    put_object_bytes,
)

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class DemoService:
    def __init__(self, db: Session):
        self.db = db

    def generate_excel(self, filas: int, error_rate: float) -> dict:
        catalogos = load_catalog_snapshot(self.db)
        df, conteo = generar_ventas(catalogos, filas=filas, error_rate=error_rate)

        buffer = BytesIO()
        df.write_excel(buffer)

        object_name = f"demo/{uuid.uuid4()}/ventas_generadas.xlsx"
        put_object_bytes(object_name, buffer.getvalue(), XLSX_CONTENT_TYPE)
        download_url = get_presigned_download_url(object_name)

        return {
            "download_url": download_url,
            "filas_totales": df.height,
            "filas_con_error": sum(conteo.values()),
            "errores_por_tipo": conteo,
        }
