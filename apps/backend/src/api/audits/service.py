"""
Servicio de auditoría - orquesta el pipeline (domain) sobre un upload
confirmado, usando los adaptadores de infraestructura.
"""

import uuid
from io import BytesIO

import polars as pl
from sqlalchemy.orm import Session
from xlsxwriter import Workbook

from src.domain.pipeline.bronze import to_bronze
from src.domain.pipeline.gold import to_gold
from src.domain.pipeline.silver import to_silver_facturas, to_silver_items
from src.domain.uploads import UploadStatus
from src.infrastructure.db.catalog.snapshot import load_catalog_snapshot
from src.infrastructure.db.uploads.repository import UploadRepository
from src.infrastructure.storage import duckdb_query, lake
from src.infrastructure.storage.minio_client import (
    get_object_bytes,
    get_presigned_download_url,
    put_object_bytes,
)

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_RESUMEN_SCHEMA = {
    "numero_factura": pl.Utf8,
    "sede_codigo": pl.Utf8,
    "fecha": pl.Date,
    "trabajador_codigo": pl.Utf8,
    "comprador_codigo": pl.Utf8,
    "total_factura": pl.Float64,
    "tiene_error": pl.Boolean,
    "tiene_warning": pl.Boolean,
    "violaciones": pl.Int64,
}
_DETALLE_SCHEMA = {
    "numero_factura": pl.Utf8,
    "item_id": pl.Int64,
    "regla": pl.Utf8,
    "severidad": pl.Utf8,
    "mensaje": pl.Utf8,
}


def _bronze_facturas_key(upload_id: str) -> str:
    return f"jobs/{upload_id}/bronze/facturas"


def _bronze_items_key(upload_id: str) -> str:
    return f"jobs/{upload_id}/bronze/items"


def _silver_facturas_key(upload_id: str) -> str:
    return f"jobs/{upload_id}/silver/facturas"


def _silver_items_key(upload_id: str) -> str:
    return f"jobs/{upload_id}/silver/items"


def _gold_key(upload_id: str) -> str:
    return f"jobs/{upload_id}/gold"


class AuditService:
    def __init__(self, db: Session):
        self.db = db
        self.uploads = UploadRepository(db)

    def run_pipeline(self, upload_id: str) -> None:
        """Corre bronze -> silver sobre el upload. Deterministas del
        archivo: no hace falta repetirlas para re-auditar tras un cambio
        en los catálogos, para eso está run_gold por separado."""
        upload = self.uploads.get(upload_id)
        if not upload:
            raise ValueError(f"Upload {upload_id} no encontrado")

        self.uploads.update_status(upload_id, UploadStatus.PROCESSING)
        try:
            file_bytes = get_object_bytes(upload.object_name)

            bronze_facturas, bronze_items = to_bronze(file_bytes)
            lake.write_delta(bronze_facturas, _bronze_facturas_key(upload_id))
            lake.write_delta(bronze_items, _bronze_items_key(upload_id))

            silver_facturas = to_silver_facturas(bronze_facturas)
            numeros_validos = set(silver_facturas["numero_factura"].drop_nulls().to_list())
            silver_items = to_silver_items(bronze_items, numeros_validos)

            lake.write_delta(silver_facturas, _silver_facturas_key(upload_id))
            lake.write_delta(silver_items, _silver_items_key(upload_id))
        except Exception:
            self.uploads.update_status(upload_id, UploadStatus.FAILED)
            raise

    def run_gold(self, upload_id: str) -> None:
        """Lee el silver YA GUARDADO (no rehace bronze/silver) + el estado
        ACTUAL de los catálogos, y regenera gold. Re-ejecutable en
        cualquier momento sin volver a subir el excel - por ejemplo,
        después de corregir un código de descuento en el catálogo."""
        upload = self.uploads.get(upload_id)
        if not upload:
            raise ValueError(f"Upload {upload_id} no encontrado")

        self.uploads.update_status(upload_id, UploadStatus.PROCESSING)
        try:
            silver_facturas = lake.read_delta(_silver_facturas_key(upload_id))
            silver_items = lake.read_delta(_silver_items_key(upload_id))
            catalogos = load_catalog_snapshot(self.db)
            gold_df = to_gold(silver_facturas, silver_items, catalogos)
            lake.write_delta(gold_df, _gold_key(upload_id))
            self.uploads.update_status(upload_id, UploadStatus.COMPLETED)
        except Exception:
            self.uploads.update_status(upload_id, UploadStatus.FAILED)
            raise

    def get_bronze_preview(self, upload_id: str, limit: int = 20) -> dict:
        return self._preview_dual(_bronze_facturas_key(upload_id), _bronze_items_key(upload_id), upload_id, limit)

    def get_silver_preview(self, upload_id: str, limit: int = 20) -> dict:
        return self._preview_dual(_silver_facturas_key(upload_id), _silver_items_key(upload_id), upload_id, limit)

    def get_gold_preview(self, upload_id: str, limit: int = 20) -> dict:
        df = lake.read_delta(_gold_key(upload_id))
        return {
            "upload_id": upload_id,
            "row_count": df.height,
            "columns": df.columns,
            "preview": df.head(limit).to_dicts(),
        }

    def _preview_dual(self, facturas_key: str, items_key: str, upload_id: str, limit: int) -> dict:
        """Bronze y silver son 2 tablas (facturas + items) - el preview
        junta ambas bajo un `sheets` en vez de una sola `preview` plana."""
        facturas_df = lake.read_delta(facturas_key)
        items_df = lake.read_delta(items_key)
        return {
            "upload_id": upload_id,
            "sheets": {
                "facturas": {
                    "row_count": facturas_df.height,
                    "columns": facturas_df.columns,
                    "preview": facturas_df.head(limit).to_dicts(),
                },
                "items": {
                    "row_count": items_df.height,
                    "columns": items_df.columns,
                    "preview": items_df.head(limit).to_dicts(),
                },
            },
        }

    def query_gold(
        self,
        upload_id: str,
        limit: int,
        offset: int,
        severidad: str | None,
        regla: str | None,
        sede_codigo: str | None,
        paso: bool | None,
        numero_factura: str | None = None,
    ) -> dict:
        rows, total = duckdb_query.query_gold(
            _gold_key(upload_id),
            limit=limit,
            offset=offset,
            severidad=severidad,
            regla=regla,
            sede_codigo=sede_codigo,
            paso=paso,
            numero_factura=numero_factura,
        )
        return {"upload_id": upload_id, "total": total, "limit": limit, "offset": offset, "rows": rows}

    def get_gold_summary(self, upload_id: str) -> dict:
        counts = duckdb_query.summary_gold(_gold_key(upload_id))
        return {"upload_id": upload_id, "counts": counts}

    def get_gold_matrix(self, upload_id: str, limit: int, offset: int) -> dict:
        rows, total = duckdb_query.matrix_gold(_gold_key(upload_id), limit=limit, offset=offset)
        return {"upload_id": upload_id, "total": total, "limit": limit, "offset": offset, "rows": rows}

    def get_factura_detail(self, upload_id: str, numero_factura: str) -> dict:
        """Todo lo que se sabe de una factura puntual: la cabecera y sus
        ítems tal como quedaron en silver (tipados) + cada regla evaluada
        contra ella en gold, separadas en cabecera/ítem. Usado por la
        página de detalle de factura del frontend."""
        facturas = duckdb_query.get_rows_by_factura(_silver_facturas_key(upload_id), numero_factura)
        items = duckdb_query.get_rows_by_factura(_silver_items_key(upload_id), numero_factura)
        items.sort(key=lambda r: r["item_id"])

        evaluaciones: list[dict] = []
        gold_ready = True
        try:
            evaluaciones = duckdb_query.get_rows_by_factura(_gold_key(upload_id), numero_factura)
        except Exception:
            gold_ready = False

        evaluaciones_cabecera = [e for e in evaluaciones if e["item_id"] is None]
        evaluaciones_items = [e for e in evaluaciones if e["item_id"] is not None]
        evaluaciones_cabecera.sort(key=lambda r: r["regla"])
        evaluaciones_items.sort(key=lambda r: (r["item_id"], r["regla"]))

        return {
            "upload_id": upload_id,
            "numero_factura": numero_factura,
            "facturas": facturas,
            "items": items,
            "evaluaciones_cabecera": evaluaciones_cabecera,
            "evaluaciones_items": evaluaciones_items,
            "gold_ready": gold_ready,
        }

    def get_dashboard(self, upload_id: str) -> dict:
        stats = duckdb_query.dashboard_stats(_gold_key(upload_id), _silver_facturas_key(upload_id))
        return {"upload_id": upload_id, **stats}

    def export_problematic(self, upload_id: str) -> dict:
        """Genera un excel de 2 hojas con las facturas que tienen al
        menos una violación (resumen de cabecera + detalle de cada regla
        que falló) y lo sube al bucket - mismo patrón que
        api/demo/service.py para el excel sintético."""
        resumen, detalle = duckdb_query.problematic_facturas(_gold_key(upload_id), _silver_facturas_key(upload_id))

        resumen_df = pl.DataFrame(resumen, schema=_RESUMEN_SCHEMA) if resumen else pl.DataFrame(schema=_RESUMEN_SCHEMA)
        detalle_df = pl.DataFrame(detalle, schema=_DETALLE_SCHEMA) if detalle else pl.DataFrame(schema=_DETALLE_SCHEMA)

        buffer = BytesIO()
        with Workbook(buffer, {"in_memory": True}) as wb:
            resumen_df.write_excel(workbook=wb, worksheet="facturas_problematicas")
            detalle_df.write_excel(workbook=wb, worksheet="violaciones")

        object_name = f"jobs/{upload_id}/export/{uuid.uuid4()}.xlsx"
        put_object_bytes(object_name, buffer.getvalue(), XLSX_CONTENT_TYPE)
        download_url = get_presigned_download_url(object_name)

        return {"download_url": download_url, "facturas_problematicas": len(resumen)}
