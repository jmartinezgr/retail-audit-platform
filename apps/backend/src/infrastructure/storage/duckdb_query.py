"""
Consultas SQL reales sobre las tablas Delta del lake, vía DuckDB - para
paginar/filtrar sin traer todo a memoria en Python ni repetir esta lógica
en Polars. Pensado para `gold`, que puede tener decenas de miles de filas
(N facturas × 15 reglas).

Nota: la extensión `delta` de DuckDB NO respeta las variables legacy
`SET s3_endpoint=...` - intenta resolver credenciales vía IMDS/metadata
service si no hay un Secret configurado, y eso truena contra MinIO local
(no hay IMDS). Hay que usar `CREATE SECRET` (mecanismo actual de DuckDB).
"""

import duckdb

from src.infrastructure.config.settings import settings


def _connection() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute("INSTALL delta")
    con.execute("LOAD delta")
    con.execute(
        f"""
        CREATE SECRET (
            TYPE s3,
            KEY_ID '{settings.MINIO_ACCESS_KEY}',
            SECRET '{settings.MINIO_SECRET_KEY}',
            REGION 'us-east-1',
            ENDPOINT '{settings.MINIO_ENDPOINT}',
            USE_SSL false,
            URL_STYLE 'path'
        )
        """
    )
    return con


def _delta_uri(object_key: str) -> str:
    return f"s3://{settings.MINIO_BUCKET}/{object_key}"


_FILTER_COLUMNS = ("severidad", "regla", "sede_codigo", "paso", "numero_factura")


def query_gold(
    object_key: str,
    limit: int = 50,
    offset: int = 0,
    severidad: str | None = None,
    regla: str | None = None,
    sede_codigo: str | None = None,
    paso: bool | None = None,
    numero_factura: str | None = None,
) -> tuple[list[dict], int]:
    """Filtra + pagina la tabla gold. Devuelve (filas, total_sin_paginar)."""
    filtros = {
        "severidad": severidad,
        "regla": regla,
        "sede_codigo": sede_codigo,
        "paso": paso,
        "numero_factura": numero_factura,
    }
    clauses = [f"{col} = ?" for col in _FILTER_COLUMNS if filtros[col] is not None]
    params = [filtros[col] for col in _FILTER_COLUMNS if filtros[col] is not None]
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    con = _connection()
    uri = _delta_uri(object_key)

    total = con.execute(
        f"SELECT count(*) FROM delta_scan('{uri}') {where_sql}", params
    ).fetchone()[0]

    rows = (
        con.execute(
            f"""
            SELECT * FROM delta_scan('{uri}') {where_sql}
            ORDER BY numero_factura, regla
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        )
        .pl()
        .to_dicts()
    )

    return rows, total


def get_rows_by_factura(object_key: str, numero_factura: str) -> list[dict]:
    """Todas las filas de una tabla Delta (silver o gold) para una
    numero_factura exacta - usado por la página de detalle de factura."""
    con = _connection()
    uri = _delta_uri(object_key)
    return (
        con.execute(
            f"SELECT * FROM delta_scan('{uri}') WHERE numero_factura = ?",
            [numero_factura],
        )
        .pl()
        .to_dicts()
    )


def summary_gold(object_key: str) -> list[dict]:
    """Conteo por (regla, severidad, paso) - para poblar filtros y un
    resumen rápido en el frontend sin traer las filas."""
    con = _connection()
    uri = _delta_uri(object_key)
    return (
        con.execute(
            f"""
            SELECT regla, severidad, paso, count(*) AS n
            FROM delta_scan('{uri}')
            GROUP BY 1, 2, 3
            ORDER BY 1, 2, 3
            """
        )
        .pl()
        .to_dicts()
    )
