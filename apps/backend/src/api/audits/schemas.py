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
