from pydantic import BaseModel, Field


class GenerateExcelRequest(BaseModel):
    facturas: int = Field(default=1000, gt=0, le=50000)
    error_rate: float = Field(default=0.1, ge=0.0, le=1.0)


class GenerateExcelResponse(BaseModel):
    download_url: str
    facturas_totales: int
    items_totales: int
    facturas_con_error: int
    errores_por_tipo: dict[str, int]
