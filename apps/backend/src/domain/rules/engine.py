"""
Motor de reglas ESTÁTICAS de gold - evalúa las facturas y sus ítems
contra los catálogos maestros. Guarda TODAS las evaluaciones (pase o
falle): una fila por (factura, item_id, regla), donde item_id es null
para reglas de CABECERA (una evaluación por factura) y tiene valor para
reglas de ÍTEM (una evaluación por ítem). Las reglas dinámicas/
configurables (JSONLogic) son un motor aparte, pendiente - ver
docs/PLANNING.md §4 y §7.

Ver docs/DATA_MODEL.md para el catálogo completo de reglas, su
severidad, si son de cabecera o de ítem, y el esquema de salida de gold.
"""

from datetime import date

import polars as pl

from src.domain.rules.types import CatalogosSnapshot, Severidad

TOLERANCIA_TOTAL = 0.01


def _enrich_facturas(facturas: pl.DataFrame, catalogos: CatalogosSnapshot) -> pl.DataFrame:
    """Une la cabecera de cada factura con los catálogos que necesitan
    las reglas de cabecera (left join - una factura sin match queda con
    las columnas del catálogo en null, eso es justo lo que detecta la
    regla '*_existe')."""
    df = facturas

    df = df.join(
        catalogos.sedes.rename(
            {"codigo": "sede_codigo", "activa": "_sede_activa", "fecha_apertura": "_sede_fecha_apertura"}
        ),
        on="sede_codigo",
        how="left",
    )
    df = df.join(
        catalogos.trabajadores.rename(
            {"codigo": "trabajador_codigo", "activo": "_trabajador_activo", "sede_codigo": "_trabajador_sede_codigo"}
        ),
        on="trabajador_codigo",
        how="left",
    )
    df = df.join(
        catalogos.compradores.rename({"codigo": "comprador_codigo"}).with_columns(
            pl.lit(True).alias("_comprador_existe")
        ),
        on="comprador_codigo",
        how="left",
    )
    df = df.with_columns(pl.col("_comprador_existe").fill_null(False))

    return df


def _enrich_items(items: pl.DataFrame, facturas_enriquecidas: pl.DataFrame, catalogos: CatalogosSnapshot) -> pl.DataFrame:
    """Une cada ítem con los campos de su factura (sede, fecha, para las
    reglas que los necesitan) y con los catálogos que necesitan las
    reglas de ítem."""
    cabecera = facturas_enriquecidas.select(
        "numero_factura", "fecha", "sede_codigo", "total_factura",
    )
    df = items.join(cabecera, on="numero_factura", how="left")

    df = df.join(
        catalogos.productos.rename({"sku": "producto_sku", "costo": "_producto_costo", "categoria": "_producto_categoria"}),
        on="producto_sku",
        how="left",
    )
    df = df.join(
        catalogos.codigos_descuento.rename(
            {
                "codigo": "codigo_descuento",
                "tipo": "_descuento_tipo",
                "valor": "_descuento_valor",
                "vigencia_inicio": "_descuento_vigencia_inicio",
                "vigencia_fin": "_descuento_vigencia_fin",
                "sede_codigo": "_descuento_sede_codigo",
                "categorias_aplicables": "_descuento_categorias",
            }
        ),
        on="codigo_descuento",
        how="left",
    )

    disponible = (
        catalogos.transferencias.group_by(["producto_sku", "sede_destino_codigo"])
        .agg(pl.col("cantidad").sum().alias("_cantidad_disponible"))
        .rename({"sede_destino_codigo": "sede_codigo"})
    )
    df = df.join(disponible, on=["producto_sku", "sede_codigo"], how="left")
    df = df.with_columns(pl.col("_cantidad_disponible").fill_null(0))

    return df


def _resultado(
    df: pl.DataFrame,
    regla: str,
    severidad: Severidad,
    paso: pl.Expr,
    mensaje_falla: str,
    mensaje_pasa: str = "OK",
    item_id: pl.Expr | None = None,
) -> pl.DataFrame:
    return df.select(
        pl.col("numero_factura"),
        (item_id if item_id is not None else pl.lit(None, dtype=pl.Int64)).alias("item_id"),
        pl.col("sede_codigo"),
        pl.col("fecha"),
        pl.lit(regla).alias("regla"),
        pl.lit(severidad.value).alias("severidad"),
        paso.alias("paso"),
        pl.when(paso).then(pl.lit(mensaje_pasa)).otherwise(pl.lit(mensaje_falla)).alias("mensaje"),
    )


def _evaluar_cabecera(df: pl.DataFrame, hoy: date) -> list[pl.DataFrame]:
    resultados: list[pl.DataFrame] = []

    sede_existe = pl.col("_sede_activa").is_not_null()
    resultados.append(_resultado(df, "sede_existe", Severidad.ERROR, sede_existe, "la sede no existe en el catálogo"))

    sede_activa = ~sede_existe | pl.col("_sede_activa")
    resultados.append(_resultado(df, "sede_activa", Severidad.ERROR, sede_activa, "la sede está inactiva/cerrada"))

    trabajador_existe = pl.col("_trabajador_activo").is_not_null()
    resultados.append(
        _resultado(df, "trabajador_existe", Severidad.ERROR, trabajador_existe, "el trabajador no existe en el catálogo")
    )

    trabajador_activo = ~trabajador_existe | pl.col("_trabajador_activo")
    resultados.append(_resultado(df, "trabajador_activo", Severidad.ERROR, trabajador_activo, "el trabajador está inactivo"))

    trabajador_pertenece_a_sede = ~trabajador_existe | (pl.col("_trabajador_sede_codigo") == pl.col("sede_codigo"))
    resultados.append(
        _resultado(
            df, "trabajador_pertenece_a_sede", Severidad.ERROR, trabajador_pertenece_a_sede,
            "el trabajador pertenece a otra sede",
        )
    )

    tiene_comprador = pl.col("comprador_codigo").is_not_null() & (pl.col("comprador_codigo").str.strip_chars() != "")
    comprador_existe = ~tiene_comprador | pl.col("_comprador_existe")
    resultados.append(
        _resultado(
            df, "comprador_existe", Severidad.WARNING, comprador_existe,
            "el comprador no existe en el catálogo", "OK (sin comprador registrado)",
        )
    )

    fecha_no_futura = pl.col("fecha").is_null() | (pl.col("fecha") <= pl.lit(hoy))
    resultados.append(_resultado(df, "fecha_no_futura", Severidad.ERROR, fecha_no_futura, "la fecha de venta es futura"))

    fecha_posterior_a_apertura = (
        pl.col("fecha").is_null()
        | pl.col("_sede_fecha_apertura").is_null()
        | (pl.col("fecha") >= pl.col("_sede_fecha_apertura"))
    )
    resultados.append(
        _resultado(
            df, "fecha_posterior_a_apertura", Severidad.ERROR, fecha_posterior_a_apertura,
            "la venta es anterior a que la sede abriera",
        )
    )

    total_esperado = pl.col("_suma_items") * (1 + pl.col("iva_pct") / 100)
    factura_total_cuadra = (
        pl.col("_suma_items").is_null()
        | pl.col("iva_pct").is_null()
        | pl.col("total_factura").is_null()
        | ((pl.col("total_factura") - total_esperado).abs() <= TOLERANCIA_TOTAL)
    )
    resultados.append(
        _resultado(
            df, "factura_total_cuadra", Severidad.ERROR, factura_total_cuadra,
            "el total registrado no cuadra con la suma de los ítems + IVA",
        )
    )

    return resultados


def _evaluar_items(df: pl.DataFrame, hoy: date) -> list[pl.DataFrame]:
    resultados: list[pl.DataFrame] = []
    item_id = pl.col("item_id")

    producto_existe = pl.col("_producto_costo").is_not_null()
    resultados.append(
        _resultado(df, "producto_existe", Severidad.ERROR, producto_existe, "el producto no existe en el catálogo", item_id=item_id)
    )

    # "" cuenta como "sin descuento" igual que null (documentado en
    # DATA_MODEL.md) - normalmente un excel real ya llega con null en vez
    # de "" para una celda vacía, pero no hay que depender de eso
    tiene_descuento = pl.col("codigo_descuento").is_not_null() & (pl.col("codigo_descuento").str.strip_chars() != "")
    sin_descuento_msg = "OK (sin código de descuento)"

    descuento_existe = ~tiene_descuento | pl.col("_descuento_tipo").is_not_null()
    resultados.append(
        _resultado(
            df, "codigo_descuento_existe", Severidad.ERROR, descuento_existe,
            "el código de descuento no existe en el catálogo", sin_descuento_msg, item_id=item_id,
        )
    )

    descuento_vigente = (
        ~tiene_descuento
        | pl.col("_descuento_tipo").is_null()
        | pl.col("fecha").is_null()  # fecha inválida ya la marcó silver, no doble-penalizar
        | ((pl.col("fecha") >= pl.col("_descuento_vigencia_inicio")) & (pl.col("fecha") <= pl.col("_descuento_vigencia_fin")))
    )
    resultados.append(
        _resultado(
            df, "codigo_descuento_vigente", Severidad.WARNING, descuento_vigente,
            "el código de descuento no está vigente en la fecha de la venta", sin_descuento_msg, item_id=item_id,
        )
    )

    descuento_aplica_a_sede = (
        ~tiene_descuento
        | pl.col("_descuento_tipo").is_null()
        | pl.col("_descuento_sede_codigo").is_null()
        | (pl.col("_descuento_sede_codigo") == pl.col("sede_codigo"))
    )
    resultados.append(
        _resultado(
            df, "codigo_descuento_aplica_a_sede", Severidad.WARNING, descuento_aplica_a_sede,
            "el código de descuento es de otra sede", sin_descuento_msg, item_id=item_id,
        )
    )

    descuento_aplica_a_categoria = (
        ~tiene_descuento
        | pl.col("_descuento_tipo").is_null()
        | pl.col("_descuento_categorias").is_null()
        | (pl.col("_descuento_categorias").list.len() == 0)
        | pl.col("_descuento_categorias").list.contains(pl.col("_producto_categoria"))
    )
    resultados.append(
        _resultado(
            df, "codigo_descuento_aplica_a_categoria", Severidad.WARNING, descuento_aplica_a_categoria,
            "el código de descuento no aplica a la categoría de este producto", sin_descuento_msg, item_id=item_id,
        )
    )

    descuento_valor = (
        pl.when(pl.col("_descuento_tipo") == "PORCENTAJE")
        .then(pl.col("cantidad") * pl.col("precio_unitario") * pl.col("_descuento_valor") / 100)
        .when(pl.col("_descuento_tipo") == "VALOR_FIJO")
        .then(pl.col("_descuento_valor"))
        .otherwise(0.0)
    )
    subtotal_esperado = pl.col("cantidad") * pl.col("precio_unitario") - descuento_valor
    item_cuadra = (
        pl.col("cantidad").is_null()
        | pl.col("precio_unitario").is_null()
        | pl.col("total_item").is_null()
        | ((pl.col("total_item") - subtotal_esperado).abs() <= TOLERANCIA_TOTAL)
    )
    resultados.append(
        _resultado(
            df, "item_cuadra", Severidad.ERROR, item_cuadra,
            "el total del ítem no cuadra con cantidad × precio_unitario − descuento", item_id=item_id,
        )
    )

    margen_no_negativo = (
        pl.col("_producto_costo").is_null()
        | pl.col("precio_unitario").is_null()
        | (pl.col("precio_unitario") >= pl.col("_producto_costo"))
    )
    resultados.append(
        _resultado(df, "margen_no_negativo", Severidad.WARNING, margen_no_negativo, "se vendió por debajo del costo", item_id=item_id)
    )

    cantidad_dentro_de_transferencias = pl.col("cantidad").is_null() | (pl.col("cantidad") <= pl.col("_cantidad_disponible"))
    resultados.append(
        _resultado(
            df, "cantidad_dentro_de_transferencias", Severidad.WARNING, cantidad_dentro_de_transferencias,
            "la cantidad vendida excede lo transferido históricamente a esa sede para ese producto "
            "(chequeo simplificado: suma total histórica, no un balance temporal)", item_id=item_id,
        )
    )

    duplicado = (
        pl.struct(["numero_factura", "producto_sku"]).is_duplicated()
        & pl.col("numero_factura").is_not_null()
        & pl.col("producto_sku").is_not_null()
    )
    resultados.append(
        _resultado(
            df, "item_duplicado_en_factura", Severidad.ERROR, ~duplicado,
            "el producto está repetido en la misma factura (debería ser una sola línea con la cantidad sumada)",
            item_id=item_id,
        )
    )

    return resultados


def evaluar(facturas: pl.DataFrame, items: pl.DataFrame, catalogos: CatalogosSnapshot, hoy: date | None = None) -> pl.DataFrame:
    """Evalúa las reglas estáticas sobre facturas + items. `hoy` es
    inyectable para que los tests sean deterministas; por defecto usa la
    fecha real."""
    hoy = hoy or date.today()

    facturas_enr = _enrich_facturas(facturas, catalogos)

    suma_items = items.group_by("numero_factura").agg(pl.col("total_item").sum().alias("_suma_items"))
    facturas_enr = facturas_enr.join(suma_items, on="numero_factura", how="left")

    items_enr = _enrich_items(items, facturas_enr, catalogos)

    resultados = _evaluar_cabecera(facturas_enr, hoy) + _evaluar_items(items_enr, hoy)
    return pl.concat(resultados)
