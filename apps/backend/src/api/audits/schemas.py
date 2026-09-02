from pydantic import BaseModel


class RunAuditResponse(BaseModel):
    """Response al disparar el procesamiento de un upload"""

    upload_id: str
    status: str


class LayerPreviewResponse(BaseModel):
    """Preview de una tabla del pipeline (bronze/silver/gold)"""

    upload_id: str
    row_count: int
    columns: list[str]
    preview: list[dict]


class GoldPageResponse(BaseModel):
    """Página filtrada de gold - vía DuckDB, no un preview fijo"""

    upload_id: str
    total: int
    limit: int
    offset: int
    rows: list[dict]


class GoldSummaryResponse(BaseModel):
    """Conteo por (regla, severidad, paso) - para filtros/resumen"""

    upload_id: str
    counts: list[dict]
