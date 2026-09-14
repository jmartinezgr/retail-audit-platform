"""Catálogo descriptivo de las 18 reglas estáticas.

Empaqueta como dato consultable lo que hoy solo vive como prosa en
docs/DATA_MODEL.md (nombre, severidad, ámbito, origen endógeno/exógeno,
y qué valida cada regla) - no reimplementa ni cambia el comportamiento
de ninguna regla, esa lógica sigue siendo solo la de engine.py. Existe
para que el agente conversacional (ver docs/copilot-spec.md) pueda
responder "¿qué chequea la regla X?" con datos reales en vez de que el
modelo lo invente.

`descripcion_en` es texto real, no traducido a mano para este archivo -
son las mismas cadenas ya escritas y en uso en
apps/frontend/src/i18n/translations.ts (`rule.*`, diccionario `en`) para
el landing page. Se copian acá (no se importan desde el frontend - son
proyectos separados) para poder indexarlas también en inglés en
agent/rag/index.py (ver apps/agent/README.md, Fase 3, "por qué también
en inglés").
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
    descripcion_en: str


_REGLAS = [
    DescripcionRegla("sede_existe", Severidad.ERROR, AmbitoRegla.CABECERA, "exogena", "El código de sede existe en el catálogo maestro.", "The store code exists in the master catalog."),
    DescripcionRegla("sede_activa", Severidad.ERROR, AmbitoRegla.CABECERA, "exogena", "La sede no está inactiva/cerrada (N/A si la sede no existe).", "The store isn't marked inactive or closed."),
    DescripcionRegla("trabajador_existe", Severidad.ERROR, AmbitoRegla.CABECERA, "exogena", "El código de trabajador existe en el catálogo maestro.", "The worker code exists in the master catalog."),
    DescripcionRegla("trabajador_activo", Severidad.ERROR, AmbitoRegla.CABECERA, "exogena", "El trabajador no está inactivo (N/A si el trabajador no existe).", "The worker isn't marked inactive."),
    DescripcionRegla("trabajador_pertenece_a_sede", Severidad.ERROR, AmbitoRegla.CABECERA, "exogena", "El trabajador registrado pertenece a la sede de la factura, no a otra (N/A si el trabajador no existe).", "The worker actually belongs to the store on the invoice, not a different one."),
    DescripcionRegla("comprador_existe", Severidad.WARNING, AmbitoRegla.CABECERA, "exogena", "Si se registró un código de comprador, que exista en el catálogo (N/A si no se registró ninguno - normal en ventas de mostrador).", "If a buyer code was registered, it exists in the buyers catalog — no buyer registered is fine, that's normal for walk-in sales."),
    DescripcionRegla("fecha_no_futura", Severidad.ERROR, AmbitoRegla.CABECERA, "endogena", "La fecha de la factura no es una fecha futura.", "The invoice date isn't in the future."),
    DescripcionRegla("fecha_posterior_a_apertura", Severidad.ERROR, AmbitoRegla.CABECERA, "exogena", "La fecha de la factura no es anterior a la fecha de apertura de la sede.", "The invoice date isn't earlier than when the store opened."),
    DescripcionRegla("factura_total_cuadra", Severidad.ERROR, AmbitoRegla.CABECERA, "endogena", "El total registrado de la factura coincide con la suma de sus ítems más IVA, con una tolerancia de 0.01.", "The registered total matches the sum of its line items plus IVA, within a small tolerance."),
    DescripcionRegla("producto_existe", Severidad.ERROR, AmbitoRegla.ITEM, "exogena", "El SKU del producto existe en el catálogo maestro.", "The product SKU exists in the master catalog."),
    DescripcionRegla("codigo_descuento_existe", Severidad.ERROR, AmbitoRegla.ITEM, "exogena", "Si el ítem usó un código de descuento, que exista en el catálogo (N/A si no se usó ninguno).", "If a discount code was used, it exists in the catalog — no code used is fine."),
    DescripcionRegla("codigo_descuento_vigente", Severidad.WARNING, AmbitoRegla.ITEM, "exogena", "La fecha de la factura cae dentro de la ventana de vigencia del código de descuento usado.", "The discount code's validity window covers the invoice date."),
    DescripcionRegla("codigo_descuento_aplica_a_sede", Severidad.WARNING, AmbitoRegla.ITEM, "exogena", "El código de descuento es global o está restringido a la sede de la factura, no a otra.", "The discount code is either store-wide or global, not restricted to a different store."),
    DescripcionRegla("codigo_descuento_aplica_a_categoria", Severidad.WARNING, AmbitoRegla.ITEM, "exogena", "El código de descuento aplica a todas las categorías o incluye la categoría de este producto.", "The discount code applies to this product's category, or to all categories."),
    DescripcionRegla("item_cuadra", Severidad.ERROR, AmbitoRegla.ITEM, "endogena", "El total del ítem coincide con cantidad × precio unitario menos el descuento, con una tolerancia de 0.01.", "The line's total matches quantity × unit price minus its discount."),
    DescripcionRegla("margen_no_negativo", Severidad.WARNING, AmbitoRegla.ITEM, "exogena", "El precio unitario de venta no es menor al costo registrado del producto.", "The unit price isn't below the product's cost."),
    DescripcionRegla("cantidad_dentro_de_transferencias", Severidad.WARNING, AmbitoRegla.ITEM, "exogena", "Chequeo simplificado: la suma histórica total de transferencias hacia esa sede para ese SKU es al menos la cantidad vendida (no es un balance temporal ordenado por fecha).", "The quantity sold doesn't exceed what was historically transferred to that store for that product (a simplified check, not a real-time balance)."),
    DescripcionRegla("item_duplicado_en_factura", Severidad.ERROR, AmbitoRegla.ITEM, "endogena", "El mismo SKU de producto no aparece dos veces en la misma factura (debería ser una sola línea con la cantidad sumada).", "The same product doesn't appear twice in the same invoice — that should be one line with the quantity summed."),
]

CATALOGO_REGLAS_ESTATICAS: dict[str, DescripcionRegla] = {r.nombre: r for r in _REGLAS}

assert set(CATALOGO_REGLAS_ESTATICAS) == NOMBRES_REGLAS_ESTATICAS, (
    "CATALOGO_REGLAS_ESTATICAS se desincronizó de NOMBRES_REGLAS_ESTATICAS - "
    "revisa que las 18 reglas de engine.py tengan su descripción acá."
)
