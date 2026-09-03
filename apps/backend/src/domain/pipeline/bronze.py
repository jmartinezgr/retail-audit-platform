"""
Capa bronze: el excel crudo tal cual llegó, sin tipar ni validar nada.
Cero criterio de negocio acá - eso es responsabilidad de silver/gold.

El excel tiene 2 hojas: "facturas" (cabecera) e "items" (líneas) - ver
docs/DATA_MODEL.md.
"""

from io import BytesIO

import polars as pl

HOJA_FACTURAS = "facturas"
HOJA_ITEMS = "items"


class HojaFaltanteError(Exception):
    """El excel no tiene alguna de las 2 hojas esperadas - error de
    estructura del archivo completo, no de una fila puntual."""


def to_bronze(file_bytes: bytes) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Lee las 2 hojas del excel y devuelve (facturas, items), cada una
    con todas las columnas como texto, exactamente como llegaron -
    ninguna fila se descarta ni se corrige en esta capa."""
    hojas = pl.read_excel(BytesIO(file_bytes), sheet_id=0)

    faltantes = [h for h in (HOJA_FACTURAS, HOJA_ITEMS) if h not in hojas]
    if faltantes:
        raise HojaFaltanteError(f"Faltan hojas en el excel: {', '.join(faltantes)}")

    facturas = hojas[HOJA_FACTURAS].select(pl.all().cast(pl.Utf8))
    items = hojas[HOJA_ITEMS].select(pl.all().cast(pl.Utf8))
    return facturas, items


def read_columns(file_bytes: bytes) -> dict[str, list[str]]:
    """Lee solo los encabezados de cada hoja, sin cargar filas - para el
    chequeo rápido de columnas (domain/ventas.validar_columnas_*) sin
    correr bronze/silver/gold. Devuelve {} para una hoja que no exista
    (el chequeo de columnas reporta eso como si faltaran todas)."""
    hojas = pl.read_excel(BytesIO(file_bytes), sheet_id=0, read_options={"n_rows": 0})
    return {nombre: df.columns for nombre, df in hojas.items()}
