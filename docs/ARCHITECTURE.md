# Arquitectura

> Complementa a `PLANNING.md` (qué se construye y por qué, producto/roadmap)
> y a `DATA_MODEL.md` (qué forma tienen los datos: entidades, esquema de
> entrada/salida de cada capa). Este documento es sobre **cómo se organiza
> el código**, backend y frontend. Se actualiza cada vez que se agrega un
> módulo nuevo o se toma una decisión estructural. Backend primero, frontend
> más abajo (§ Frontend).

## El patrón: capas por responsabilidad técnica, no por feature

`apps/backend/src/` se organiza en tres carpetas de primer nivel:

```
src/
  domain/            # lógica de negocio pura, sin FastAPI/SQLAlchemy/Minio
  infrastructure/     # adaptadores concretos: Postgres, MinIO/R2, Delta, DuckDB
  api/                # FastAPI: routers + schemas Pydantic (DTOs)
  main.py
```

**Por qué así y no "package by feature"** (una carpeta `uploads/` con su
router+service+repo+model adentro, como estaba antes): con capas técnicas,
`domain/` queda garantizado libre de imports de framework — es la parte que
se puede testear sin levantar FastAPI ni una base de datos, y es la parte
que en la práctica es la más "interesante" de este proyecto (el motor de
reglas, el pipeline bronze/silver/gold). Aislarla de una vez evita que
lógica de negocio se cuele mezclada con SQLAlchemy o Pydantic sin darse
cuenta.

**Por qué no full hexagonal/clean architecture** (con una capa
`application/` separada e interfaces/ports por cada repositorio): para el
tamaño de este proyecto sería ceremonia sin beneficio real — no hay
necesidad genuina de poder intercambiar Postgres o MinIO por otra cosa. El
service de cada módulo en `api/` orquesta `domain/` + `infrastructure/`
directo, sin capa de interfaces intermedia.

### `domain/` — lógica de negocio pura

Reglas: **cero imports de FastAPI, SQLAlchemy, Minio, Polars-con-storage.**
Solo Python + tipos + (cuando aplique) operaciones sobre `polars.DataFrame`
en memoria, nunca leyendo/escribiendo directo a storage.

- `uploads.py` — `UploadStatus` (enum).
- `catalog.py` — `TipoDescuento`, `Categoria` (enums).
- `ventas.py` — `MetodoPago` (enum) + `FACTURA_COLUMNAS_REQUERIDAS`/
  `FACTURA_COLUMNAS_OPCIONALES`/`ITEM_COLUMNAS_REQUERIDAS`/
  `ITEM_COLUMNAS_OPCIONALES`: el contrato de columnas que se espera de
  cada una de las 2 hojas del excel (cabecera de factura, ítems). Es la
  fuente de verdad que usa `silver.py` — `DATA_MODEL.md` lo documenta en
  formato humano/diagrama, pero el código manda si difieren. También
  `validar_columnas_factura()`/`validar_columnas_item()`: mismo
  contrato, pero solo comparan nombres de columna (usado por el chequeo
  rápido de `api/uploads/`, no por silver).
- `rules/types.py` — `Severidad` (enum ERROR/WARNING) y `CatalogosSnapshot`
  (dataclass con los catálogos como `pl.DataFrame`, incluye `compradores`
  — la forma en la que el motor de reglas necesita los datos, sin saber
  que vienen de Postgres).
- `rules/engine.py` — el motor de reglas **estáticas**: `_enrich_facturas()`
  hace un left-join de la cabecera contra sedes/trabajadores/compradores,
  `_enrich_items()` une cada ítem con su cabecera (sede/fecha/total) y
  contra productos/códigos de descuento/transferencias. `evaluar()` corre
  `_evaluar_cabecera()` (9 reglas, una evaluación por factura, `item_id =
  null`) + `_evaluar_items()` (9 reglas, una evaluación por ítem) —
  funciones = expresiones de Polars vectorizadas, no loops fila por fila.
  Catálogo completo de las 18 reglas, severidad, tipo (endógena/exógena) y
  ámbito (cabecera/ítem) en `DATA_MODEL.md`. *(pendiente)* el evaluador de
  reglas **dinámicas** (JSONLogic, configurables desde el frontend) —
  motor aparte, no compite con este.
- `pipeline/bronze.py` — `to_bronze(file_bytes: bytes) -> tuple[pl.DataFrame, pl.DataFrame]`:
  recibe los bytes crudos del excel (no una ruta ni un objeto de storage,
  para que sea testeable sin MinIO), lee las 2 hojas con
  `pl.read_excel(..., sheet_id=0)` (`sheet_id=0` = cargar todas las hojas,
  devuelve un dict `{nombre: DataFrame}`) y devuelve `(facturas, items)`
  con todas las columnas como texto (`pl.Utf8`), sin tipar ni validar
  nada. Lanza `HojaFaltanteError` si falta alguna de las 2 hojas
  esperadas (`HOJA_FACTURAS = "facturas"`, `HOJA_ITEMS = "items"`).
- `pipeline/silver.py` — `to_silver_facturas(bronze_facturas)` /
  `to_silver_items(bronze_items, numeros_factura_validos)`: tipan cada
  hoja contra su esquema (`domain/ventas.py`) y agregan
  `_errores: List[Utf8]` / `_es_valida: bool` por fila. Ninguna fila se
  descarta. `to_silver_items` recibe el set de `numero_factura` válidos
  de la cabecera para marcar ítems huérfanos (estructural, pero no
  evaluable sin la otra hoja) y asigna `item_id` (posicional, 1..N por
  factura, vía `pl.int_range(...).over("numero_factura")` — robusto
  incluso si `item_duplicado_en_factura` falla y el mismo producto se
  repite). Si faltan columnas obligatorias por completo, lanzan
  `SilverSchemaError` en vez de procesar fila por fila. Esquema completo
  en `DATA_MODEL.md`.
- `pipeline/gold.py` — `to_gold(facturas, items, catalogos, hoy=None) -> pl.DataFrame`:
  delgado a propósito, solo llama a `rules.engine.evaluar()`. `hoy` es
  inyectable (default `date.today()`) para que los tests sean
  deterministas sin mockear el reloj del sistema.
- `demo/generator.py` — `generar_ventas(catalogos, facturas, error_rate, seed=None, hoy=None) -> (pl.DataFrame, pl.DataFrame, dict[str,int])`:
  genera `facturas` facturas, cada una con 1-5 ítems (productos elegidos
  **sin reemplazo** por factura — con reemplazo, una factura limpia podía
  repetir producto por pura coincidencia y disparar
  `item_duplicado_en_factura` sin haber inyectado nada; bug real
  encontrado y corregido esta sesión), + probabilidad `error_rate` de
  aplicar UN mutador de `MUTADORES_CABECERA` (14, mutan el dict de la
  factura) o `MUTADORES_ITEM` (12, mutan/agregan un ítem de la lista) —
  nunca ambos. Devuelve `(facturas_df, items_df, conteo_por_tipo)`. `seed`
  y `hoy` opcionales para reproducibilidad en tests. `random`/`date.today()`
  la hacen "pura salvo por eso", igual que `bronze()`/`gold()` — ver
  convención abajo.

### Convención en `pipeline/`: qué es "puro" acá

`bronze()` parsea bytes de excel en memoria (`pl.read_excel` sobre un
`BytesIO`) — no toca red ni disco, así que cuenta como puro/testeable aunque
técnicamente "parsear" no sea una operación trivial. Lo que **no** entra a
`domain/pipeline/` es leer esos bytes de MinIO o escribir el resultado a
Delta — eso lo hace `infrastructure/storage/` (`minio_client.get_object_bytes`,
`lake.write_delta`), y quien los conecta es el `service.py` de
`api/audits/`.

### `infrastructure/` — adaptadores al mundo exterior

Todo lo que habla con Postgres, MinIO/R2, o (cuando entre) Delta/DuckDB.
Implementaciones concretas, sin lógica de negocio.

- `config/settings.py` — `Settings` (pydantic-settings, lee `.env`).
- `db/` — `base.py` (`Base` de SQLAlchemy), `session.py` (`engine`,
  `SessionLocal`), y una subcarpeta por feature con sus modelos + repos
  (ej. `db/uploads/models.py`, `db/uploads/repository.py`;
  `db/catalog/models.py` tiene `SedeModel`, `TrabajadorModel`,
  `ProductoModel`, `CodigoDescuentoModel` (gana
  `categorias_aplicables: ARRAY(String)`, nullable — null/vacío = aplica
  a todas las categorías, mismo patrón que `sede_codigo` nulo = global),
  `TransferenciaModel`, `CompradorModel` (`codigo`, `nombre` — catálogo
  simple, sin FK) con `ForeignKey` reales entre sí).
- `storage/minio_client.py` — cliente de MinIO/S3 (`get_minio_client`,
  `get_object_bytes`, `put_object_bytes` para subir bytes directo
  server-side sin URL prefirmada, `get_presigned_download_url` para
  dar una URL de descarga temporal — usados por `api/demo/`).
- `storage/lake.py` — `write_delta()` / `read_delta()`: Polars + `deltalake`
  contra el bucket S3-compatible. `storage_options` incluye
  `AWS_ALLOW_HTTP` y `AWS_S3_ALLOW_UNSAFE_RENAME` porque MinIO (y S3
  alternativos en general) no dan por garantizado el locking atómico que
  `delta-rs` asume por defecto en S3 real — como el pipeline es de un solo
  escritor por job, no hace falta ese locking.
- `db/catalog/snapshot.py` — `load_catalog_snapshot(db) -> CatalogosSnapshot`:
  convierte los catálogos de Postgres (vía `CatalogRepository`) a
  `pl.DataFrame` — el único lugar donde SQLAlchemy y `domain/rules`
  se tocan. `productos` ahora incluye `categoria` (necesaria para
  `codigo_descuento_aplica_a_categoria`) y `codigos_descuento` incluye
  `categorias_aplicables`. Se lee EN VIVO cada vez que se llama, sin
  cachear — es justo lo que permite re-ejecutar `gold` después de
  cambiar algo en un catálogo sin tocar bronze/silver. También la usa
  `api/demo/` para que el generador construya facturas con datos reales.
- `storage/duckdb_query.py` — `query_gold()` (filtros + paginación real,
  incluye `numero_factura` como filtro exacto), `summary_gold()` (conteo
  por regla/severidad/paso), `matrix_gold()` (agrega gold por
  `(numero_factura, regla)` con `bool_and(paso)` — "peor caso": si
  cualquier `item_id` de esa factura falló esa regla, sale `false` —
  paginado por FACTURA vía una subquery `DISTINCT numero_factura ORDER
  BY ... LIMIT/OFFSET`, no por fila agregada, para que una página
  traiga siempre un número entero de facturas × 18 reglas, lista para
  pivotear a una matriz ancha en el frontend) y `get_rows_by_factura()`
  (todas las filas de una tabla Delta cualquiera — silver/facturas,
  silver/items o gold — para una `numero_factura` exacta, usado por la
  página de detalle de factura), SQL directo contra la tabla Delta vía
  `delta_scan()`. Conexión nueva por llamada (~160ms de overhead:
  instalar/cargar la extensión `delta` + crear el secret — se midió, y
  para esta escala no vale la pena cachear la conexión con la
  complejidad de thread-safety que traería). Probado contra 750,000
  filas: agregación 0.74s, página filtrada 0.06s. **Importante**: la
  extensión `delta` NO respeta las variables legacy `SET s3_endpoint=...`
  (intenta resolver credenciales vía IMDS si no hay un secret, y truena
  contra MinIO) — hay que usar `CREATE SECRET`.

#### Convención de rutas en el bucket

```
jobs/{upload_id}/
  upload/{filename}         ← archivo crudo tal cual se subió (no es Delta)
  bronze/facturas/          ← tabla Delta (domain/pipeline/bronze.py)
  bronze/items/             ← tabla Delta
  silver/facturas/          ← tabla Delta (domain/pipeline/silver.py)
  silver/items/             ← tabla Delta
  gold/                      ← tabla Delta (domain/pipeline/gold.py) - una sola tabla plana
```

`upload/` guarda el archivo tal cual; bronze y silver son 2 hojas → 2
tablas Delta cada una (`facturas`/`items`, cada una con su propio
`_delta_log/`); gold sigue siendo una sola tabla plana (distingue
cabecera de ítem por la columna `item_id`, no por ruta). La ruta de
`upload/` la arma `api/uploads/service.py` y queda guardada en
`UploadModel.object_name`; las de bronze/silver/gold las arma
`api/audits/service.py` (`_bronze_facturas_key`, `_bronze_items_key`,
`_silver_facturas_key`, `_silver_items_key`, `_gold_key`).

### `api/` — la única capa que sabe que existe HTTP

Una subcarpeta por feature, cada una con:
- `router.py` — endpoints de FastAPI.
- `schemas.py` — request/response models de Pydantic (DTOs, no se reusan
  como modelos de dominio ni de DB).
- `service.py` — orquesta: llama a `infrastructure/` para leer/guardar,
  llama a `domain/` para la lógica, devuelve datos simples al router.

Ya existe:
- `api/uploads/` — subir excel → URL prefirmada de MinIO → registro en
  Postgres (guarda `object_name` y `session_id` explícitos) → consultar
  estado. `GET /uploads/` filtra por `session_id` (dependency
  `get_session_id`, header `X-Client-Id`, cae a `"anonymous"` si no viene
  — ver `PLANNING.md` §2 "Aislar uploads entre visitantes"). `GET
  /uploads/{id}/validate-columns` (`domain/ventas.validar_columnas_factura`
  + `validar_columnas_item` + `domain/pipeline/bronze.read_columns`, que
  lee solo encabezados de las 2 hojas vía `read_options={"n_rows": 0}` de
  fastexcel — no carga filas) da un chequeo instantáneo de ambas hojas
  sin tocar bronze/silver/gold ni el status del job — responde
  `{facturas: {...}, items: {...}, valido}` (una `SheetValidationResponse`
  por hoja).
- `api/audits/` — dos triggers separados, a propósito (ver `PLANNING.md`
  §"Re-run gold"):
  - `POST /audits/{upload_id}/run` → `AuditService.run_pipeline` (bronze →
    silver para las 2 hojas, encadenados — son deterministas del archivo
    subido, no hay razón para separarlos). `to_silver_items` recibe el
    set de `numero_factura` de `silver_facturas` para marcar ítems
    huérfanos.
  - `POST /audits/{upload_id}/run-gold` → `AuditService.run_gold`: lee
    `silver/facturas` y `silver/items` YA GUARDADOS en Delta (no rehace
    bronze/silver) + el estado ACTUAL de los catálogos vía
    `load_catalog_snapshot()`, y regenera `gold`. Re-ejecutable en
    cualquier momento sin volver a subir el excel — por ejemplo, después
    de corregir un código de descuento en el catálogo. Solo acá se marca
    `UploadStatus.COMPLETED` (antes de que existiera gold, `run_pipeline`
    dejaba el estado en `PROCESSING` a propósito).

  Ambos corren con `BackgroundTasks` de FastAPI (no bloquean la
  respuesta; el `db: Session` inyectado por `Depends` sigue vivo durante
  la tarea de fondo porque FastAPI corre las background tasks *antes*
  del cierre de dependencias `yield` — por diseño, no por casualidad).

  `GET /audits/{upload_id}/bronze` y `.../silver` leen las 2 tablas
  Delta correspondientes y las devuelven como preview JSON
  (`DualLayerPreviewResponse` — `{sheets: {facturas: {...}, items:
  {...}}}`, cada hoja con su propio `row_count`/`columns`/`preview`);
  `GET .../gold` sigue devolviendo un preview plano de una sola tabla
  (`LayerPreviewResponse`) — un preview fijo (primeras filas), no
  pensado para la tabla del frontend.
  `GET /audits/{upload_id}/gold/query` (filtros `severidad`/`regla`/
  `sede_codigo`/`paso`/`numero_factura` + `limit`/`offset`, vía
  `duckdb_query.query_gold`), `GET /audits/{upload_id}/gold/summary`
  (conteo por regla/severidad/paso, vía `duckdb_query.summary_gold`) y
  `GET /audits/{upload_id}/gold/matrix` (filas largas agregadas por
  "peor caso", vía `duckdb_query.matrix_gold`, paginado por factura) sí
  son para eso. `GET /audits/{upload_id}/factura/{numero_factura}`
  (`AuditService.get_factura_detail`) junta todo lo relacionado a una
  factura puntual: la cabecera y sus ítems tal como quedaron en silver
  (tipados) + cada regla evaluada contra ella en gold, separadas en
  `evaluaciones_cabecera`/`evaluaciones_items` (por `item_id is null`) —
  para la página de detalle de factura del frontend, no requiere paginar
  porque una factura tiene a lo sumo 18 evaluaciones de cabecera + 18 ×
  N_ítems de ítem. Si gold todavía no existe para el upload, devuelve
  `evaluaciones_cabecera: []`, `evaluaciones_items: []` y
  `gold_ready: false` en vez de fallar (silver, en cambio, si no existe
  deja que la excepción de `delta_scan` se propague — mismo criterio que
  el resto de `api/audits/`: "la capa no existe" es un 500, consistente
  con `/bronze`, `/silver`, `/gold`).
- `api/demo/` — `POST /demo/generate-excel` (`facturas`, `error_rate`)
  llama a `load_catalog_snapshot()` + `generar_ventas()`, escribe las 2
  hojas (`facturas`, `items`) al mismo workbook (`xlsxwriter.Workbook`
  compartido — `df.write_excel(workbook=wb, worksheet=...)` para cada
  una, patrón documentado en el propio docstring de `write_excel`), sube
  el resultado a `demo/{uuid}/ventas_generadas.xlsx` en el bucket
  (`put_object_bytes`, **no** crea un registro de upload) y devuelve una
  URL de descarga prefirmada (`get_presigned_download_url`) + el detalle
  de qué se inyectó (`facturas_totales`, `items_totales`,
  `facturas_con_error`, `errores_por_tipo`). El usuario decide si sube
  el archivo por el flujo normal de `api/uploads/` para correrlo por el
  pipeline.

Pendiente: `api/catalog/` (CRUD de sedes/trabajadores/productos/etc., solo
si la fase de reglas dinámicas editables lo necesita).

## Convención de imports

Sin `__init__.py` (namespace packages implícitos de Python 3) — así estaba
ya y se mantiene. Los imports son siempre absolutos desde `src`, ej.
`from src.infrastructure.db.uploads.repository import UploadRepository`.
Se corre con `uvicorn src.main:app` desde `apps/backend/` (para que `src`
resuelva como paquete).

## Tests

`apps/backend/tests/`, con `pytest` — la estructura espeja `src/` (ej.
`tests/domain/pipeline/test_silver.py` para `src/domain/pipeline/silver.py`,
`tests/domain/rules/test_engine.py` para `src/domain/rules/engine.py`,
`tests/domain/demo/test_generator.py` para `src/domain/demo/generator.py`).
Hoy solo cubre `domain/` (pipeline + rules + demo) porque es la parte
pura/sin infraestructura — justo la ventaja de haber aislado `domain/` de
FastAPI/SQLAlchemy/Minio desde el principio: 87 tests, todos con datos en
memoria, sin Postgres ni MinIO corriendo (los tests de `rules/engine.py`
y `demo/generator.py` construyen su propio `CatalogosSnapshot` de
juguete en vez de leer Postgres de verdad — con cobertura completa
sede×producto en `transferencias`, para no repetir el problema real que
salió al validar el generador contra el seed de verdad). `tests/conftest.py`
mete `apps/backend` en `sys.path` (no hay `__init__.py`, así que sin esto
los imports `from src....` no resuelven).

Correr desde `apps/backend` con el venv activo:
```
python -m pytest -v
```

## Scripts operativos

`apps/backend/scripts/` — herramientas que se corren a mano, no código de
la app en producción (ej. `seed_catalog.py`). Se ejecutan con
`python scripts/<archivo>.py` desde `apps/backend`, con el venv activo.

## Frontend

`apps/frontend/` — Vite + React + TypeScript. Estructura:

```
src/
  types/api.ts         # espeja los schemas Pydantic del backend, a mano
  lib/api.ts            # cliente HTTP tipado (fetch), un objeto `api.*` por router del backend
  lib/session.ts          # UUID anónimo en localStorage - lib/api.ts lo manda como X-Client-Id
  lib/pipeline.ts        # runFullPipeline() - corre bronze→silver→gold esperando cada capa de verdad
  lib/theme.tsx           # ThemeProvider/useTheme - toggle .dark, persiste en localStorage
  lib/i18n.tsx             # I18nProvider/useI18n - t(key, vars) con interpolación {placeholder}
  i18n/translations.ts    # diccionarios en/es, ~80 claves (layout, landing, home, job, gold, columnCheck)
  components/ui/         # shadcn/ui (generados, no se editan a mano salvo necesidad real)
  components/app/        # componentes propios (layout, status-badge, gold-table, gold-matrix,
                          #   column-check, theme-toggle, language-toggle)
  pages/                  # una por ruta (landing-page, home-page, job-detail-page, invoice-detail-page)
  App.tsx                 # rutas (react-router) - "/" landing, "/app" home, "/jobs/:id" detalle,
                          #   "/jobs/:id/fac/:facturaId" detalle de factura
  main.tsx                # QueryClientProvider + BrowserRouter + Toaster
```

**Por qué `lib/api.ts` y no llamar `fetch` directo en cada componente**: un
solo lugar que sabe la forma de cada endpoint — si el backend cambia una
ruta, se actualiza acá una vez. `types/api.ts` es manual por ahora (no
generado desde el OpenAPI del backend); si el contrato empieza a
desincronizarse seguido, generar con `openapi-typescript` es la mejora
obvia.

**Dev proxy, no CORS**: `vite.config.ts` reenvía `/api/*` →
`http://127.0.0.1:8000` (con el prefijo quitado). El frontend real nunca
necesita CORS en desarrollo — el `allow_origins=["*"]` que vive sin
commitear en `main.py` es solo para el visor HTML provisional
(`viewer.html`), no para esto. En producción, el backend desplegado sí
necesita CORS acotado al dominio real del frontend (pendiente para la
fase de deploy).

**TanStack Table instalada, sin usar todavía**: la tabla de gold
(`components/app/gold-table.tsx`) pagina y filtra en el servidor (DuckDB
hace el trabajo pesado), así que una tabla headless no aportaba nada ahí
— se armó con los primitivos de `components/ui/table`. Queda instalada
para cuando una pantalla necesite ordenar/filtrar en memoria de verdad.

**Resumen (matriz) vs. Detallado**: `gold-table.tsx` es ahora un wrapper
con `Tabs` — "Resumen" (`gold-matrix.tsx`, nuevo) y "Detallado"
(`GoldDetailedTable`, la tabla plana de antes, sin cambios de fondo).
`gold-matrix.tsx` pagina por factura (`GET /audits/{id}/gold/matrix`,
`GoldMatrixRow[]` en formato largo) y pivotea en el cliente a una tabla
ancha: una fila por factura, una columna por regla (18), celda = ícono
OK/WARNING/ERROR (`paso`/`severidad` de esa combinación
factura×regla — ya viene agregada por "peor caso" desde el backend, el
frontend no agrega nada). Click en una fila navega a
`/jobs/{uploadId}/fac/{numero_factura}`, igual que el ícono "ver"
(`lucide-react` `Eye`) de la tabla detallada — ambos caminos llegan a la
misma página.

**Página de detalle de factura**: `pages/invoice-detail-page.tsx` pide
`GET /audits/{id}/factura/{numero_factura}` (un solo request) y arma 3
bloques: card de datos de cabecera (sede, trabajador, comprador, fecha,
método de pago, IVA, subtotal calculado desde los ítems vs. total
registrado), card de reglas de cabecera (`evaluaciones_cabecera`, igual
patrón que antes) y una tabla de ítems donde cada fila es expandible
(click) para ver las reglas de ítem que le corresponden a ese `item_id`
puntual (`evaluaciones_items` agrupadas por `item_id` en un `Map` antes
de renderizar). Si el mismo `numero_factura` aparece más de una vez en
la hoja `facturas` (caso patológico, no debería pasar — cada cabecera es
única), la página lo muestra con una alerta en vez de fallar. Al listar
evaluaciones hay que usar `${regla}-${índice}` como key de React, no
solo `regla`: con datos duplicados puede haber dos filas por regla y una
key no única rompía el render (bug real encontrado con Playwright,
consola mostraba "two children with the same key", corregido en la
ronda anterior — el mismo cuidado aplica ahora a la lista de ítems).

**Landing vs. app**: `/` es marketing (`landing-page.tsx`, sin `AppLayout`
— tiene su propio header mínimo), `/app` y `/jobs/:id` sí usan
`AppLayout` (el logo dentro de la app apunta a `/app`, no a `/`; hay un
link "Sobre el proyecto" de vuelta a `/`).

**Tema**: los tokens de color en `index.css` (`--primary`, `--ring`,
`--accent`, `--sidebar-*`, `--chart-*`) están recoloreados a violeta
(`oklch` hue ~292) sobre la base neutral de shadcn — fondos/texto siguen
neutros, el acento es deliberadamente selectivo. El bloque `.dark` (lo
generó el preset de shadcn) se activa con `theme-toggle.tsx` vía
`lib/theme.tsx`; un script inline en `index.html` lee `localStorage`
antes de que React monte para no mostrar un flash del tema equivocado.

**i18n propio, no `react-i18next`**: la superficie a traducir es chica
(un solo idioma alterno) y no justificaba la dependencia — `lib/i18n.tsx`
es un contexto simple con un diccionario plano (`i18n/translations.ts`)
e interpolación `{placeholder}` por regex. Inglés por defecto (portafolio
para audiencia internacional), español disponible por `language-toggle.tsx`,
persistido en `localStorage` igual que el tema. Solo se traduce la UI
estática del frontend — los datos que produce el backend (nombres de
regla, mensajes de gold, códigos de catálogo) se quedan en español a
propósito, es el idioma real del dominio. `lib/pipeline.ts` no formatea
strings directamente: emite un `PipelineStatus` tipado (unión discriminada)
que `job-detail-page.tsx` traduce, porque `pipeline.ts` vive fuera de
React y no puede llamar a `useI18n()`.

## Historial de cambios estructurales

- **2026-09-01**: reorganizado de "package by feature" (`uploads/`,
  `shared/`) a capas (`domain/`, `infrastructure/`, `api/`). Se hizo temprano
  a propósito, antes de que hubiera más módulos que mover.
- **2026-09-01**: agregado `domain/catalog.py` +
  `infrastructure/db/catalog/` (modelos, repositorio) + `scripts/seed_catalog.py`.
- **2026-09-01**: agregado `domain/pipeline/bronze.py`,
  `infrastructure/storage/lake.py`, `api/audits/` (primer tramo del
  pipeline, corre en background). `UploadModel` ahora guarda `object_name`
  explícito en vez de reconstruir la ruta a mano.
- **2026-09-01**: corregida la convención de rutas del bucket — el archivo
  crudo pasó de `jobs/{id}/bronze/{filename}` a `jobs/{id}/upload/{filename}`,
  y la tabla Delta de `jobs/{id}/delta/bronze` a `jobs/{id}/bronze` — para
  que `upload/bronze/silver/gold` queden como hermanos al mismo nivel, sin
  que "bronze" signifique dos cosas distintas.
- **2026-09-01**: agregado `domain/ventas.py` (esquema de `Venta`) +
  `domain/pipeline/silver.py`, encadenado en `AuditService.run_pipeline`
  (antes `run_bronze`). Documentación movida a `docs/` (`PLANNING.md`,
  `ARCHITECTURE.md`) y agregado `docs/DATA_MODEL.md` (entidades, esquema de
  entrada/salida por capa, diagrama de clases). `CLAUDE.md` se queda en la
  raíz — es donde Claude Code lo carga automático.
- **2026-09-01**: agregado `tests/` con `pytest` — cobertura de
  `domain/pipeline/bronze.py` y `silver.py` (18 tests: tipado correcto,
  cada tipo de error detectado individualmente, la fila nunca se descarta,
  columnas obligatorias faltantes por completo vs. campo opcional
  faltante).
- **2026-09-01**: agregado `domain/rules/` (`types.py`, `engine.py` — 15
  reglas estáticas) + `domain/pipeline/gold.py` +
  `infrastructure/db/catalog/snapshot.py`. `api/audits/` gana
  `POST /audits/{id}/run-gold` y `GET /audits/{id}/gold`, separado de
  `run` para poder re-auditar sin resubir el excel. Probado end-to-end:
  detectó una inconsistencia real en `scripts/make_sample_excel.py`
  (`trabajador_pertenece_a_sede`, un empleado puesto en la sede
  equivocada a mano) — se corrigió el fixture, no la regla.
- **2026-09-01**: agregado `domain/demo/generator.py` + `api/demo/`
  (generador de excels sintéticos, 21 mutadores). Dos bugs reales
  encontrados y corregidos al validarlo contra el seed real (no del
  generador): `codigo_descuento_vigente` comparaba contra "hoy" en vez
  de contra la fecha de la venta (`generator.py`); `cantidad_dentro_de_transferencias`
  disparaba en el 74% de filas limpias por falta de cobertura de
  transferencias en el seed (`scripts/seed_catalog.py`, ahora garantiza
  una transferencia base por cada combinación sede×producto). Bonus:
  `codigo_descuento_existe` no trataba `""` igual que `null`
  (`domain/rules/engine.py`) — no afecta excels reales (el round-trip por
  Excel ya normaliza celda vacía a `null`), pero sí el contrato
  documentado en `DATA_MODEL.md`, así que se corrigió en la raíz.
- **2026-09-01**: `domain/demo/generator.py` reescrito para no llamar a
  Polars por fila (`_Prepared` precomputa los catálogos a listas de
  Python una sola vez) — 20,000 filas en ~0.6s. Límite de `filas` subido
  de 1,000 a 50,000 en el schema.
- **2026-09-02**: `generar_ventas` gana un `hoy` inyectable (igual que
  `to_gold`) — un test con fecha fija empezó a fallar el día después de
  escribirse porque el generador seguía usando `date.today()` real.
- **2026-09-02**: agregado `infrastructure/storage/duckdb_query.py`
  (`query_gold`, `summary_gold`) + `GET /audits/{id}/gold/query` y
  `.../gold/summary` — paginación/filtros reales sobre gold vía SQL
  (DuckDB + `delta_scan`), ya no solo el preview fijo. Encontrado en el
  camino: `codigo_descuento_vigente` podía devolver `paso = null` (fecha
  inválida + código real) — corregido con la misma guarda que ya usaban
  las otras reglas de fecha.
- **2026-09-02**: scaffold de `apps/frontend/` (React + Vite + TS +
  Tailwind + shadcn/ui) — primeras dos pantallas (home, detalle de job)
  contra la API real, probadas en navegador con Playwright. Título de
  este documento cambiado de "Arquitectura del backend" a "Arquitectura"
  ahora que también cubre frontend.
- **2026-09-02**: `UploadModel` gana `session_id` (sesión anónima por
  navegador, header `X-Client-Id`) — `GET /uploads/` ahora filtra por
  sesión. Agregado `GET /uploads/{id}/validate-columns`
  (`domain/ventas.validar_columnas` + `bronze.read_columns`, solo
  encabezados). Frontend: landing page en `/` (home pasa a `/app`), tema
  recoloreado a violeta, `column-check.tsx` integrado en el detalle del
  job. Corregido `gold-table.tsx`: no mostraba ningún mensaje cuando gold
  todavía no existía (quedaba vacía en silencio) — encontrado probando el
  flujo completo en navegador, no asumiendo el camino feliz.
- **2026-09-02**: agregado `lib/theme.tsx` (toggle de modo oscuro,
  persistido) y `lib/i18n.tsx` + `i18n/translations.ts` (i18n propio,
  inglés por defecto, español disponible) — ver detalle arriba en "Tema"
  e "i18n propio". Toda la UI estática (landing, home, detalle de job)
  traducida. Verificado con `tsc -b`, `oxlint`, `npm run build`, y en
  navegador real con Playwright (claro/oscuro × en/es).
- **2026-09-02**: landing page — reescrito el párrafo de origen para no
  nombrar el dominio/industria real (portafolio, ver `PLANNING.md`), y
  agregada la sección "cómo valida una regla" (endógena/exógena).
  `DATA_MODEL.md` clasifica las 15 reglas con esa misma taxonomía.
- **2026-09-02**: filtro por `numero_factura` en `GET
  /audits/{id}/gold/query` + nuevo `GET
  /audits/{id}/factura/{numero_factura}` (`duckdb_query.get_rows_by_factura`,
  `AuditService.get_venta_detail`) — ver detalle arriba en "Filtro por
  factura + página de detalle". Frontend: input de factura + columna de
  acción "ver" en `gold-table.tsx`, página nueva
  `pages/invoice-detail-page.tsx` en `/jobs/:id/fac/:facturaId`. Bug real
  encontrado probando contra una factura duplicada de verdad: la key de
  React en la lista de evaluaciones era solo `regla`, colisionaba cuando
  la misma factura (y por lo tanto la misma regla) aparecía dos veces —
  corregido a `${regla}-${índice}`.
- **2026-09-03**: rediseño grande — `Venta` (una fila = una factura
  completa) se separó en `Factura` (cabecera) + `ItemFactura` (línea),
  para modelar facturas multi-ítem de verdad. El excel pasa de 1 hoja a
  2 (`facturas`, `items`); bronze/silver ganan una tabla por hoja
  (`bronze/facturas`, `bronze/items`, `silver/facturas`,
  `silver/items`); gold sigue siendo una sola tabla plana pero gana
  `item_id` (nullable — `null` = regla de cabecera, con valor = regla de
  ítem). El motor de reglas pasó de 15 a 18 reglas: `factura_cuadra` →
  `item_cuadra` (misma fórmula, ahora por ítem), `factura_no_duplicada`
  (duplicado de número de factura en el archivo) →
  `item_duplicado_en_factura` (mismo producto repetido dentro de la
  misma factura — ya no aplica "no se puede repetir numero_factura",
  eso es justo lo normal con multi-ítem), y 3 reglas nuevas:
  `comprador_existe` (WARNING, catálogo `Comprador` nuevo — no toda
  venta tiene comprador registrado), `factura_total_cuadra` (ERROR,
  cabecera: `total_factura ≈ Σ(total_item) × (1+iva_pct/100)`, la
  reconciliación de totales con IVA que antes el dominio no podía
  expresar), `codigo_descuento_aplica_a_categoria` (WARNING,
  `CodigoDescuentoModel` gana `categorias_aplicables: ARRAY(String)`).
  `scripts/seed_catalog.py` pasó de `DELETE`+reinsertar a
  `drop_all`+`create_all` de las tablas de catálogo (no hay Alembic, y
  `create_all` no altera columnas de tablas existentes). Bug real
  encontrado y corregido: el generador elegía productos por ítem CON
  reemplazo, así que una factura "limpia" con pocos productos en el
  catálogo de prueba podía repetir uno por pura coincidencia y disparar
  `item_duplicado_en_factura` sin que se hubiera inyectado nada (mismo
  patrón de falso positivo que `cantidad_dentro_de_transferencias` en
  una sesión anterior) — corregido eligiendo productos sin reemplazo por
  factura. Backend: `api/demo/generate-excel` ahora recibe `facturas` en
  vez de `filas` y escribe las 2 hojas a un mismo
  `xlsxwriter.Workbook` compartido. Frontend: `gold-table.tsx` gana un
  toggle Resumen/Detallado (`gold-matrix.tsx` nuevo, matriz factura×regla
  paginada por factura vía `GET /audits/{id}/gold/matrix`),
  `invoice-detail-page.tsx` se reescribió para mostrar cabecera + tabla
  de ítems expandibles. Suite de tests de dominio reescrita contra el
  esquema nuevo: 87 tests (antes 61).
