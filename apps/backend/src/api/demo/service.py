"""
Servicio de demo - genera un excel de ventas sintético (2 hojas: facturas
+ items) y lo sube al bucket bajo demo/ (no crea un registro de upload;
el usuario decide si lo sube por el flujo normal para correr el pipeline
sobre él).
"""

import uuid
from io import BytesIO

from sqlalchemy.orm import Session
from xlsxwriter import Workbook

from src.domain.demo.generator import generar_ventas
from src.domain.pipeline.bronze import HOJA_FACTURAS, HOJA_ITEMS
from src.infrastructure.db.catalog.snapshot import load_catalog_snapshot
from src.infrastructure.storage.s3_client import (
    get_presigned_download_url,
    put_object_bytes,
)

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class DemoService:
    def __init__(self, db: Session):
        self.db = db

    def generate_excel(self, facturas: int, error_rate: float) -> dict:
        catalogos = load_catalog_snapshot(self.db)
        facturas_df, items_df, conteo = generar_ventas(catalogos, facturas=facturas, error_rate=error_rate)

        buffer = BytesIO()
        with Workbook(buffer, {"in_memory": True}) as wb:
            facturas_df.write_excel(workbook=wb, worksheet=HOJA_FACTURAS)
            items_df.write_excel(workbook=wb, worksheet=HOJA_ITEMS)

        object_name = f"demo/{uuid.uuid4()}/ventas_generadas.xlsx"
        put_object_bytes(object_name, buffer.getvalue(), XLSX_CONTENT_TYPE)
        download_url = get_presigned_download_url(object_name)

        return {
            "download_url": download_url,
            "facturas_totales": facturas_df.height,
            "items_totales": items_df.height,
            "facturas_con_error": sum(conteo.values()),
            "errores_por_tipo": conteo,
        }
