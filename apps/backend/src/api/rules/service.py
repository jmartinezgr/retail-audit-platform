"""
Servicio de reglas dinámicas - CRUD sobre RuleDefinitionModel + metadata
(whitelist de campos, categorías, sedes) para el formulario del
frontend. La validación de la "forma" de una regla (UMBRAL vs
VENTANA_EXCLUSION, whitelist de campos por ámbito, nombre no
reservado/duplicado) vive acá y no en schemas.py porque necesita
consultar la DB - mismo patrón delgado que AuditService.
"""

from sqlalchemy.orm import Session

from src.domain.catalog import Categoria
from src.domain.rules.dynamic import CAMPOS_CABECERA, CAMPOS_ITEM
from src.domain.rules.engine import NOMBRES_REGLAS_ESTATICAS
from src.infrastructure.db.catalog.repository import CatalogRepository
from src.infrastructure.db.rules.models import RuleDefinitionModel
from src.infrastructure.db.rules.repository import RuleDefinitionRepository

_EDITABLE_FIELDS = [
    "nombre", "tipo", "ambito", "severidad", "activa", "mensaje",
    "campo", "operador", "valor", "filtro_categoria", "filtro_sede",
    "sede_codigo", "fecha_inicio", "fecha_fin",
]

_CAMPO_LABELS = {
    "total_factura": "Total de la factura",
    "iva_pct": "IVA (%)",
    "cantidad": "Cantidad",
    "precio_unitario": "Precio unitario",
    "total_item": "Total del ítem",
    "descuento_pct": "Descuento aplicado (%)",
    "margen_pct": "Margen (%)",
}


class RuleValidationError(ValueError):
    """Una regla dinámica con forma inválida - se traduce a un 422 en el router."""


class RuleService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = RuleDefinitionRepository(db)
        self.catalog_repo = CatalogRepository(db)

    def list_rules(self) -> list[RuleDefinitionModel]:
        return self.repo.list()

    def get_available_fields(self) -> dict:
        return {
            "cabecera": [{"campo": c, "label": _CAMPO_LABELS[c]} for c in sorted(CAMPOS_CABECERA)],
            "item": [{"campo": c, "label": _CAMPO_LABELS[c]} for c in sorted(CAMPOS_ITEM)],
            "categorias": [c.value for c in Categoria],
            "sedes": [s.codigo for s in self.catalog_repo.list_sedes()],
        }

    def create_rule(self, data: dict) -> RuleDefinitionModel:
        data = {**data, "activa": True}
        self._validar(data, excluir_id=None)
        return self.repo.create(data)

    def update_rule(self, rule_id: int, data: dict) -> RuleDefinitionModel:
        existing = self.repo.get(rule_id)
        if existing is None:
            raise ValueError(f"Regla {rule_id} no encontrada")
        merged = {field: getattr(existing, field) for field in _EDITABLE_FIELDS}
        merged.update(data)
        self._validar(merged, excluir_id=rule_id)
        return self.repo.update(rule_id, merged)

    def delete_rule(self, rule_id: int) -> bool:
        return self.repo.delete(rule_id)

    def _validar(self, data: dict, excluir_id: int | None) -> None:
        nombre = data.get("nombre")
        if not nombre:
            raise RuleValidationError("nombre es obligatorio")
        if nombre in NOMBRES_REGLAS_ESTATICAS:
            raise RuleValidationError(f"'{nombre}' ya es el nombre de una regla estática, no se puede reusar")
        existente = self.repo.get_by_nombre(nombre)
        if existente and existente.id != excluir_id:
            raise RuleValidationError(f"ya existe una regla dinámica llamada '{nombre}'")

        tipo = data.get("tipo")
        if tipo == "UMBRAL":
            campo, operador, valor = data.get("campo"), data.get("operador"), data.get("valor")
            if not (campo and operador and valor is not None):
                raise RuleValidationError("una regla UMBRAL necesita campo, operador y valor")
            ambito = data.get("ambito")
            campos_validos = CAMPOS_CABECERA if ambito == "CABECERA" else CAMPOS_ITEM
            if campo not in campos_validos:
                raise RuleValidationError(f"'{campo}' no es un campo válido para el ámbito {ambito}")
            if data.get("filtro_categoria") and ambito != "ITEM":
                raise RuleValidationError("filtro_categoria solo aplica a reglas de ámbito ITEM")
        elif tipo == "VENTANA_EXCLUSION":
            sede, inicio, fin = data.get("sede_codigo"), data.get("fecha_inicio"), data.get("fecha_fin")
            if not (sede and inicio and fin):
                raise RuleValidationError("una regla VENTANA_EXCLUSION necesita sede_codigo, fecha_inicio y fecha_fin")
            if inicio > fin:
                raise RuleValidationError("fecha_inicio debe ser anterior o igual a fecha_fin")
            data["ambito"] = "CABECERA"
        else:
            raise RuleValidationError(f"tipo de regla desconocido: {tipo}")
