from pydantic import BaseModel, Field


class GenerateExcelRequest(BaseModel):
    filas: int = Field(default=50, gt=0, le=1000)
    error_rate: float = Field(default=0.1, ge=0.0, le=1.0)


class GenerateExcelResponse(BaseModel):
    download_url: str
    filas_totales: int
    filas_con_error: int
    errores_por_tipo: dict[str, int]
