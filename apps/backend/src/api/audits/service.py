"""
Servicio de auditoría - orquesta el pipeline (domain) sobre un upload
confirmado, usando los adaptadores de infraestructura.
"""

from sqlalchemy.orm import Session

from src.domain.pipeline.bronze import to_bronze
from src.domain.pipeline.gold import to_gold
from src.domain.pipeline.silver import to_silver
from src.domain.uploads import UploadStatus
from src.infrastructure.db.catalog.snapshot import load_catalog_snapshot
from src.infrastructure.db.uploads.repository import UploadRepository
from src.infrastructure.storage import duckdb_query, lake
from src.infrastructure.storage.minio_client import get_object_bytes


def _bronze_key(upload_id: str) -> str:
    return f"jobs/{upload_id}/bronze"


def _silver_key(upload_id: str) -> str:
    return f"jobs/{upload_id}/silver"


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

            bronze_df = to_bronze(file_bytes)
            lake.write_delta(bronze_df, _bronze_key(upload_id))

            silver_df = to_silver(bronze_df)
            lake.write_delta(silver_df, _silver_key(upload_id))
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
            silver_df = lake.read_delta(_silver_key(upload_id))
            catalogos = load_catalog_snapshot(self.db)
            gold_df = to_gold(silver_df, catalogos)
            lake.write_delta(gold_df, _gold_key(upload_id))
            self.uploads.update_status(upload_id, UploadStatus.COMPLETED)
        except Exception:
            self.uploads.update_status(upload_id, UploadStatus.FAILED)
            raise

    def get_bronze_preview(self, upload_id: str, limit: int = 20) -> dict:
        return self._preview(_bronze_key(upload_id), upload_id, limit)

    def get_silver_preview(self, upload_id: str, limit: int = 20) -> dict:
        return self._preview(_silver_key(upload_id), upload_id, limit)

    def get_gold_preview(self, upload_id: str, limit: int = 20) -> dict:
        return self._preview(_gold_key(upload_id), upload_id, limit)

    def _preview(self, object_key: str, upload_id: str, limit: int) -> dict:
        df = lake.read_delta(object_key)
        return {
            "upload_id": upload_id,
            "row_count": df.height,
            "columns": df.columns,
            "preview": df.head(limit).to_dicts(),
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

    def get_venta_detail(self, upload_id: str, numero_factura: str) -> dict:
        """Todo lo que se sabe de una factura puntual: la venta tal como
        quedó en silver (tipada) + cada regla evaluada contra ella en
        gold. Usado por la página de detalle de factura del frontend."""
        ventas = duckdb_query.get_rows_by_factura(_silver_key(upload_id), numero_factura)

        evaluaciones: list[dict] = []
        gold_ready = True
        try:
            evaluaciones = duckdb_query.get_rows_by_factura(_gold_key(upload_id), numero_factura)
        except Exception:
            gold_ready = False
        evaluaciones.sort(key=lambda r: r["regla"])

        return {
            "upload_id": upload_id,
            "numero_factura": numero_factura,
            "ventas": ventas,
            "evaluaciones": evaluaciones,
            "gold_ready": gold_ready,
        }
