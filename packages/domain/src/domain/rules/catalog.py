"""Catálogo descriptivo de las 18 reglas estáticas.

Empaqueta como dato consultable lo que hoy solo vive como prosa en
docs/DATA_MODEL.md (nombre, severidad, ámbito, origen endógeno/exógeno,
y qué valida cada regla) - no reimplementa ni cambia el comportamiento
de ninguna regla, esa lógica sigue siendo solo la de engine.py. Existe
para que el agente conversacional (ver docs/copilot-spec.md) pueda
responder "¿qué chequea la regla X?" con datos reales en vez de que el
modelo lo invente.
"""

from dataclasses import dataclass

from domain.rules.engine import NOMBRES_REGLAS_ESTATICAS
from domain.rules.types import AmbitoRegla, Severidad


@dataclass(frozen=True)
class DescripcionRegla:
    nombre: str
    severidad: Severidad
    ambito: AmbitoRegla
    origen: str  # "endogena" | "exogena" - puramente descriptivo, no altera evaluación
    descripcion: str


_REGLAS = [
    DescripcionRegla("sede_existe", Severidad.ERROR, AmbitoRegla.CABECERA, "exogena", "El código de sede existe en el catálogo maestro."),
    DescripcionRegla("sede_activa", Severidad.ERROR, AmbitoRegla.CABECERA, "exogena", "La sede no está inactiva/cerrada (N/A si la sede no existe)."),
    DescripcionRegla("trabajador_existe", Severidad.ERROR, AmbitoRegla.CABECERA, "exogena", "El código de trabajador existe en el catálogo maestro."),
    DescripcionRegla("trabajador_activo", Severidad.ERROR, AmbitoRegla.CABECERA, "exogena", "El trabajador no está inactivo (N/A si el trabajador no existe)."),
    DescripcionRegla("trabajador_pertenece_a_sede", Severidad.ERROR, AmbitoRegla.CABECERA, "exogena", "El trabajador registrado pertenece a la sede de la factura, no a otra (N/A si el trabajador no existe)."),
    DescripcionRegla("comprador_existe", Severidad.WARNING, AmbitoRegla.CABECERA, "exogena", "Si se registró un código de comprador, que exista en el catálogo (N/A si no se registró ninguno - normal en ventas de mostrador)."),
    DescripcionRegla("fecha_no_futura", Severidad.ERROR, AmbitoRegla.CABECERA, "endogena", "La fecha de la factura no es una fecha futura."),
    DescripcionRegla("fecha_posterior_a_apertura", Severidad.ERROR, AmbitoRegla.CABECERA, "exogena", "La fecha de la factura no es anterior a la fecha de apertura de la sede."),
    DescripcionRegla("factura_total_cuadra", Severidad.ERROR, AmbitoRegla.CABECERA, "endogena", "El total registrado de la factura coincide con la suma de sus ítems más IVA, con una tolerancia de 0.01."),
    DescripcionRegla("producto_existe", Severidad.ERROR, AmbitoRegla.ITEM, "exogena", "El SKU del producto existe en el catálogo maestro."),
    DescripcionRegla("codigo_descuento_existe", Severidad.ERROR, AmbitoRegla.ITEM, "exogena", "Si el ítem usó un código de descuento, que exista en el catálogo (N/A si no se usó ninguno)."),
    DescripcionRegla("codigo_descuento_vigente", Severidad.WARNING, AmbitoRegla.ITEM, "exogena", "La fecha de la factura cae dentro de la ventana de vigencia del código de descuento usado."),
    DescripcionRegla("codigo_descuento_aplica_a_sede", Severidad.WARNING, AmbitoRegla.ITEM, "exogena", "El código de descuento es global o está restringido a la sede de la factura, no a otra."),
    DescripcionRegla("codigo_descuento_aplica_a_categoria", Severidad.WARNING, AmbitoRegla.ITEM, "exogena", "El código de descuento aplica a todas las categorías o incluye la categoría de este producto."),
    DescripcionRegla("item_cuadra", Severidad.ERROR, AmbitoRegla.ITEM, "endogena", "El total del ítem coincide con cantidad × precio unitario menos el descuento, con una tolerancia de 0.01."),
    DescripcionRegla("margen_no_negativo", Severidad.WARNING, AmbitoRegla.ITEM, "exogena", "El precio unitario de venta no es menor al costo registrado del producto."),
    DescripcionRegla("cantidad_dentro_de_transferencias", Severidad.WARNING, AmbitoRegla.ITEM, "exogena", "Chequeo simplificado: la suma histórica total de transferencias hacia esa sede para ese SKU es al menos la cantidad vendida (no es un balance temporal ordenado por fecha)."),
    DescripcionRegla("item_duplicado_en_factura", Severidad.ERROR, AmbitoRegla.ITEM, "endogena", "El mismo SKU de producto no aparece dos veces en la misma factura (debería ser una sola línea con la cantidad sumada)."),
]

CATALOGO_REGLAS_ESTATICAS: dict[str, DescripcionRegla] = {r.nombre: r for r in _REGLAS}

assert set(CATALOGO_REGLAS_ESTATICAS) == NOMBRES_REGLAS_ESTATICAS, (
    "CATALOGO_REGLAS_ESTATICAS se desincronizó de NOMBRES_REGLAS_ESTATICAS - "
    "revisa que las 18 reglas de engine.py tengan su descripción acá."
)
