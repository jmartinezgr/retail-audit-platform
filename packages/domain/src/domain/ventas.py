"""
Esquema de una Factura (cabecera + ítems) - lo que se espera de las dos
hojas del excel subido ("facturas" e "items"). Fuente de verdad para la
validación estructural en pipeline/silver.py; ver docs/DATA_MODEL.md para
la descripción completa.
"""

from dataclasses import dataclass
from enum import Enum


class MetodoPago(str, Enum):
    EFECTIVO = "EFECTIVO"
    TARJETA = "TARJETA"
    TRANSFERENCIA = "TRANSFERENCIA"


# Columnas de la hoja "facturas" (cabecera - una fila por factura)
FACTURA_COLUMNAS_REQUERIDAS = [
    "numero_factura",
    "fecha",
    "sede_codigo",
    "trabajador_codigo",
    "metodo_pago",
    "iva_pct",
    "total_factura",
]
FACTURA_COLUMNAS_OPCIONALES = ["comprador_codigo"]

# Columnas de la hoja "items" (una fila por ítem de una factura)
ITEM_COLUMNAS_REQUERIDAS = [
    "numero_factura",
    "producto_sku",
    "cantidad",
    "precio_unitario",
    "total_item",
]
ITEM_COLUMNAS_OPCIONALES = ["codigo_descuento"]


@dataclass
class ValidacionColumnas:
    """Chequeo rápido de encabezados - no tipa ni valida datos, solo si
    las columnas que trae cada hoja del excel son las que se esperan. Más
    liviano que correr silver completo, pensado para dar feedback
    inmediato antes de disparar el pipeline de verdad."""

    columnas_encontradas: list[str]
    columnas_faltantes: list[str]
    columnas_opcionales_presentes: list[str]
    columnas_extra: list[str]
    valido: bool


def _validar(columnas: list[str], requeridas: list[str], opcionales: list[str]) -> ValidacionColumnas:
    presentes = set(columnas)
    esperadas = set(requeridas) | set(opcionales)

    faltantes = [c for c in requeridas if c not in presentes]
    opcionales_presentes = [c for c in opcionales if c in presentes]
    extra = [c for c in columnas if c not in esperadas]

    return ValidacionColumnas(
        columnas_encontradas=list(columnas),
        columnas_faltantes=faltantes,
        columnas_opcionales_presentes=opcionales_presentes,
        columnas_extra=extra,
        valido=len(faltantes) == 0,
    )


def validar_columnas_factura(columnas: list[str]) -> ValidacionColumnas:
    return _validar(columnas, FACTURA_COLUMNAS_REQUERIDAS, FACTURA_COLUMNAS_OPCIONALES)


def validar_columnas_item(columnas: list[str]) -> ValidacionColumnas:
    return _validar(columnas, ITEM_COLUMNAS_REQUERIDAS, ITEM_COLUMNAS_OPCIONALES)
