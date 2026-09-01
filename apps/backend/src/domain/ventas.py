"""
Esquema de la entidad Venta - lo que se espera de cada fila del excel
subido. Fuente de verdad para la validación estructural en
pipeline/silver.py; ver docs/DATA_MODEL.md para la descripción completa.
"""

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
