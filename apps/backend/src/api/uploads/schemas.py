"""
Schemas Pydantic para validación de requests/responses
"""

from pydantic import BaseModel
from datetime import datetime


class RequestUploadUrlRequest(BaseModel):
    """Request para generar URL de upload"""

    filename: str


class RequestUploadUrlResponse(BaseModel):
    """Response con URL presignada"""

    upload_url: str
    object_name: str
    upload_id: str


class ConfirmUploadResponse(BaseModel):
    """Response de confirmación de upload"""

    upload_id: str
    status: str
    filename: str


class UploadStatusResponse(BaseModel):
    """Response con estado del upload"""

    upload_id: str
    filename: str
    status: str
    created_at: str


class UploadListItemResponse(BaseModel):
    """Item en lista de uploads"""

    upload_id: str
    filename: str
    status: str
    created_at: str


class UploadListResponse(BaseModel):
    """Response con lista de uploads"""

    count: int
    uploads: list[UploadListItemResponse]


class ColumnValidationResponse(BaseModel):
    """Chequeo rápido de columnas - no corre el pipeline completo"""

    upload_id: str
    columnas_encontradas: list[str]
    columnas_faltantes: list[str]
    columnas_opcionales_presentes: list[str]
    columnas_extra: list[str]
    valido: bool
