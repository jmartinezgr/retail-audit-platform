"""
Capa bronze: el excel crudo tal cual llegó, sin tipar ni validar nada.
Cero criterio de negocio acá - eso es responsabilidad de silver/gold.
"""

from io import BytesIO

import polars as pl


def to_bronze(file_bytes: bytes) -> pl.DataFrame:
    """Lee el excel y devuelve un DataFrame con todas las columnas como
    texto, exactamente como llegaron - ninguna fila se descarta ni se
    corrige en esta capa."""
    df = pl.read_excel(BytesIO(file_bytes))
    return df.select(pl.all().cast(pl.Utf8))


def read_columns(file_bytes: bytes) -> list[str]:
    """Lee solo los encabezados, sin cargar filas - para el chequeo rápido
    de columnas (domain/ventas.validar_columnas) sin correr bronze/silver/gold."""
    df = pl.read_excel(BytesIO(file_bytes), read_options={"n_rows": 0})
    return df.columns
