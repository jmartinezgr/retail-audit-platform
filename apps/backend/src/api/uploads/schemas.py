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
