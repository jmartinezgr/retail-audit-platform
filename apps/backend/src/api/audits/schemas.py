from pydantic import BaseModel


class RunAuditResponse(BaseModel):
    """Response al disparar el procesamiento de un upload"""

    upload_id: str
    status: str


class SheetPreview(BaseModel):
    """Preview de una hoja (facturas o items) dentro de bronze/silver"""

    row_count: int
    columns: list[str]
    preview: list[dict]


class DualLayerPreviewResponse(BaseModel):
    """Preview de bronze/silver - 2 hojas (facturas + items), no una tabla plana"""

    upload_id: str
    sheets: dict[str, SheetPreview]


class LayerPreviewResponse(BaseModel):
    """Preview de gold - una sola tabla plana"""

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


class GoldMatrixResponse(BaseModel):
    """Página de la matriz factura x regla (peor caso por item_id) - el
    frontend la pivotea a una tabla ancha"""

    upload_id: str
    total: int
    limit: int
    offset: int
    rows: list[dict]


class FacturaDetailResponse(BaseModel):
    """Todo lo relacionado a una factura puntual: la cabecera y sus
    ítems en silver + cada regla evaluada contra ella en gold, separadas
    en cabecera/ítem"""

    upload_id: str
    numero_factura: str
    facturas: list[dict]
    items: list[dict]
    evaluaciones_cabecera: list[dict]
    evaluaciones_items: list[dict]
    gold_ready: bool


class RuleFailureBreakdown(BaseModel):
    """Cuántas facturas (no filas) tienen esta regla fallando - para el
    ranking de reglas más problemáticas del dashboard"""

    regla: str
    severidad: str
    facturas_afectadas: int


class DashboardResponse(BaseModel):
    """Estadísticas agregadas de una corrida - resumen ejecutivo para
    la pestaña Dashboard del frontend"""

    upload_id: str
    total_facturas: int
    facturas_validas: int
    facturas_con_error: int
    facturas_solo_warning: int
    facturas_con_items_duplicados: int
    facturas_con_total_no_cuadra: int
    valor_total_registrado: float
    valor_validado: float
    reglas: list[RuleFailureBreakdown]


class ExportProblematicResponse(BaseModel):
    """URL de descarga del excel (2 hojas) con las facturas problemáticas"""

    download_url: str
    facturas_problematicas: int
