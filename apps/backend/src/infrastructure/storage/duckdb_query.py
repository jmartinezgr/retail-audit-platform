"""
Consultas SQL reales sobre las tablas Delta del lake, vía DuckDB - para
paginar/filtrar sin traer todo a memoria en Python ni repetir esta lógica
en Polars. Pensado para `gold`, que puede tener decenas de miles de filas
(N facturas × 15 reglas).

Nota: la extensión `delta` de DuckDB NO respeta las variables legacy
`SET s3_endpoint=...` - intenta resolver credenciales vía IMDS/metadata
service si no hay un Secret configurado, y eso truena contra MinIO/R2
(no hay IMDS). Hay que usar `CREATE SECRET` (mecanismo actual de DuckDB).
"""

import duckdb

from src.infrastructure.config.settings import settings


def _connection() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute("INSTALL delta")
    con.execute("LOAD delta")
    use_ssl = "true" if settings.S3_SECURE else "false"
    con.execute(
        f"""
        CREATE SECRET (
            TYPE s3,
            KEY_ID '{settings.S3_ACCESS_KEY}',
            SECRET '{settings.S3_SECRET_KEY}',
            REGION '{settings.S3_REGION}',
            ENDPOINT '{settings.S3_ENDPOINT}',
            USE_SSL {use_ssl},
            URL_STYLE 'path'
        )
        """
    )
    return con


def _delta_uri(object_key: str) -> str:
    return f"s3://{settings.S3_BUCKET}/{object_key}"


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


def matrix_gold(object_key: str, limit: int = 25, offset: int = 0) -> tuple[list[dict], int]:
    """Agrega gold por (numero_factura, regla) con 'peor caso'
    (bool_and(paso) - si CUALQUIER item_id de esa factura falló esa
    regla, sale false) y pagina por FACTURA (no por fila agregada), para
    que el frontend pueda pivotear una página completa a una matriz
    ancha (factura x regla) de un vistazo. Devuelve (filas_largas,
    total_facturas)."""
    con = _connection()
    uri = _delta_uri(object_key)

    total = con.execute(f"SELECT count(DISTINCT numero_factura) FROM delta_scan('{uri}')").fetchone()[0]

    rows = (
        con.execute(
            f"""
            WITH agg AS (
                SELECT
                    numero_factura,
                    regla,
                    any_value(severidad) AS severidad,
                    bool_and(paso) AS paso,
                    any_value(sede_codigo) AS sede_codigo,
                    any_value(fecha) AS fecha
                FROM delta_scan('{uri}')
                GROUP BY numero_factura, regla
            ),
            pagina AS (
                SELECT DISTINCT numero_factura FROM agg ORDER BY numero_factura LIMIT ? OFFSET ?
            )
            SELECT agg.* FROM agg JOIN pagina ON agg.numero_factura IS NOT DISTINCT FROM pagina.numero_factura
            ORDER BY numero_factura, regla
            """,
            [limit, offset],
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


def dashboard_stats(gold_key: str, silver_facturas_key: str) -> dict:
    """Estadísticas agregadas de una corrida: cuántas facturas son
    válidas/tienen error/solo warning, cuántas tienen problemas de
    itemización (producto duplicado, total que no cuadra), valor
    registrado vs. valor de las facturas 100% válidas, y qué reglas
    fallan más (por cantidad de facturas afectadas, no de filas - una
    regla de ítem no debe pesar más solo porque una factura tenga más
    ítems). Une gold con silver/facturas (gold no trae el monto)."""
    con = _connection()
    gold_uri = _delta_uri(gold_key)
    facturas_uri = _delta_uri(silver_facturas_key)

    resumen = con.execute(
        f"""
        WITH factura_status AS (
            SELECT
                numero_factura,
                bool_or(severidad = 'ERROR' AND NOT paso) AS has_error,
                bool_or(severidad = 'WARNING' AND NOT paso) AS has_warning,
                bool_or(regla = 'item_duplicado_en_factura' AND NOT paso) AS has_item_duplicado,
                bool_or(regla = 'factura_total_cuadra' AND NOT paso) AS has_total_mismatch
            FROM delta_scan('{gold_uri}')
            GROUP BY numero_factura
        )
        SELECT
            count(*) AS total_facturas,
            count(*) FILTER (WHERE NOT has_error AND NOT has_warning) AS facturas_validas,
            count(*) FILTER (WHERE has_error) AS facturas_con_error,
            count(*) FILTER (WHERE has_warning AND NOT has_error) AS facturas_solo_warning,
            count(*) FILTER (WHERE has_item_duplicado) AS facturas_con_items_duplicados,
            count(*) FILTER (WHERE has_total_mismatch) AS facturas_con_total_no_cuadra,
            coalesce(sum(f.total_factura), 0) AS valor_total_registrado,
            coalesce(sum(f.total_factura) FILTER (WHERE NOT fs.has_error AND NOT fs.has_warning), 0) AS valor_validado
        FROM delta_scan('{facturas_uri}') f
        LEFT JOIN factura_status fs ON f.numero_factura IS NOT DISTINCT FROM fs.numero_factura
        """
    ).pl().to_dicts()[0]

    reglas = (
        con.execute(
            f"""
            SELECT regla, any_value(severidad) AS severidad, count(DISTINCT numero_factura) AS facturas_afectadas
            FROM delta_scan('{gold_uri}')
            WHERE NOT paso
            GROUP BY regla
            ORDER BY facturas_afectadas DESC
            """
        )
        .pl()
        .to_dicts()
    )

    return {**resumen, "reglas": reglas}


def problematic_facturas(gold_key: str, silver_facturas_key: str) -> tuple[list[dict], list[dict]]:
    """Para la exportación: (resumen, detalle). `resumen` es una fila por
    factura problemática (al menos una violación) con sus datos de
    cabecera; `detalle` es cada evaluación que falló (item_id incluido)
    para esas facturas - literalmente toda fila de gold con paso=false,
    ya que eso es justo lo que hace que una factura sea "problemática"."""
    con = _connection()
    gold_uri = _delta_uri(gold_key)
    facturas_uri = _delta_uri(silver_facturas_key)

    resumen = (
        con.execute(
            f"""
            WITH factura_status AS (
                SELECT
                    numero_factura,
                    bool_or(severidad = 'ERROR' AND NOT paso) AS tiene_error,
                    bool_or(severidad = 'WARNING' AND NOT paso) AS tiene_warning,
                    count(*) FILTER (WHERE NOT paso) AS violaciones
                FROM delta_scan('{gold_uri}')
                GROUP BY numero_factura
            )
            SELECT
                f.numero_factura, f.sede_codigo, f.fecha, f.trabajador_codigo,
                f.comprador_codigo, f.total_factura,
                fs.tiene_error, fs.tiene_warning, fs.violaciones
            FROM delta_scan('{facturas_uri}') f
            JOIN factura_status fs ON f.numero_factura IS NOT DISTINCT FROM fs.numero_factura
            WHERE fs.tiene_error OR fs.tiene_warning
            ORDER BY fs.tiene_error DESC, f.numero_factura
            """
        )
        .pl()
        .to_dicts()
    )

    detalle = (
        con.execute(
            f"""
            SELECT numero_factura, item_id, regla, severidad, mensaje
            FROM delta_scan('{gold_uri}')
            WHERE NOT paso
            ORDER BY numero_factura, regla
            """
        )
        .pl()
        .to_dicts()
    )

    return resumen, detalle


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
