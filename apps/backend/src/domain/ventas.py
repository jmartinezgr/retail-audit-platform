"""
Esquema de la entidad Venta - lo que se espera de cada fila del excel
subido. Fuente de verdad para la validación estructural en
pipeline/silver.py; ver docs/DATA_MODEL.md para la descripción completa.
"""

from dataclasses import dataclass
from enum import Enum


class MetodoPago(str, Enum):
    EFECTIVO = "EFECTIVO"
    TARJETA = "TARJETA"
    TRANSFERENCIA = "TRANSFERENCIA"


# Columnas obligatorias y opcionales del excel de ventas
VENTA_COLUMNAS_REQUERIDAS = [
    "numero_factura",
    "fecha",
    "sede_codigo",
    "trabajador_codigo",
    "producto_sku",
    "cantidad",
    "precio_unitario",
    "total",
    "metodo_pago",
]
VENTA_COLUMNAS_OPCIONALES = ["codigo_descuento"]


@dataclass
class ValidacionColumnas:
    """Chequeo rápido de encabezados - no tipa ni valida datos, solo si
    las columnas que trae el excel son las que se esperan. Más liviano
    que correr silver completo, pensado para dar feedback inmediato
    antes de disparar el pipeline de verdad."""

    columnas_encontradas: list[str]
    columnas_faltantes: list[str]
    columnas_opcionales_presentes: list[str]
    columnas_extra: list[str]
    valido: bool


def validar_columnas(columnas: list[str]) -> ValidacionColumnas:
    presentes = set(columnas)
    esperadas = set(VENTA_COLUMNAS_REQUERIDAS) | set(VENTA_COLUMNAS_OPCIONALES)

    faltantes = [c for c in VENTA_COLUMNAS_REQUERIDAS if c not in presentes]
    opcionales_presentes = [c for c in VENTA_COLUMNAS_OPCIONALES if c in presentes]
    extra = [c for c in columnas if c not in esperadas]

    return ValidacionColumnas(
        columnas_encontradas=list(columnas),
        columnas_faltantes=faltantes,
        columnas_opcionales_presentes=opcionales_presentes,
        columnas_extra=extra,
        valido=len(faltantes) == 0,
    )
