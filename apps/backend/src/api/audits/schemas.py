from pydantic import BaseModel


class RunAuditResponse(BaseModel):
    """Response al disparar el procesamiento de un upload"""

    upload_id: str
    status: str


class BronzePreviewResponse(BaseModel):
    """Preview de la tabla bronze resultante"""

    upload_id: str
    row_count: int
    columns: list[str]
    preview: list[dict]
