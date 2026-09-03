from datetime import date

from pydantic import BaseModel


class RuleDefinitionCreate(BaseModel):
    """Forma completa de una regla nueva - la validación de negocio (tipo
    UMBRAL vs VENTANA_EXCLUSION, whitelist de campos, nombre no
    reservado/duplicado) vive en api/rules/service.py, no acá, porque
    necesita consultar la DB (nombres ya usados)."""

    nombre: str
    tipo: str  # "UMBRAL" | "VENTANA_EXCLUSION"
    ambito: str  # "CABECERA" | "ITEM"
    severidad: str  # "ERROR" | "WARNING"
    mensaje: str
    campo: str | None = None
    operador: str | None = None
    valor: float | None = None
    filtro_categoria: str | None = None
    filtro_sede: str | None = None
    sede_codigo: str | None = None
    fecha_inicio: date | None = None
    fecha_fin: date | None = None


class RuleDefinitionUpdate(BaseModel):
    """PATCH parcial - todos los campos opcionales, incluyendo `activa`
    (el toggle activar/desactivar). El servicio fusiona con la regla
    existente antes de re-validar la forma completa."""

    nombre: str | None = None
    tipo: str | None = None
    ambito: str | None = None
    severidad: str | None = None
    activa: bool | None = None
    mensaje: str | None = None
    campo: str | None = None
    operador: str | None = None
    valor: float | None = None
    filtro_categoria: str | None = None
    filtro_sede: str | None = None
    sede_codigo: str | None = None
    fecha_inicio: date | None = None
    fecha_fin: date | None = None


class RuleDefinitionResponse(BaseModel):
    id: int
    nombre: str
    tipo: str
    ambito: str
    severidad: str
    activa: bool
    mensaje: str
    campo: str | None
    operador: str | None
    valor: float | None
    filtro_categoria: str | None
    filtro_sede: str | None
    sede_codigo: str | None
    fecha_inicio: date | None
    fecha_fin: date | None

    model_config = {"from_attributes": True}


class FieldOption(BaseModel):
    campo: str
    label: str


class AvailableFieldsResponse(BaseModel):
    """Whitelist de campos evaluables por ámbito + categorías/sedes reales
    del catálogo - para poblar los selects del formulario del frontend
    sin hardcodear ninguna de las dos cosas ahí."""

    cabecera: list[FieldOption]
    item: list[FieldOption]
    categorias: list[str]
    sedes: list[str]
