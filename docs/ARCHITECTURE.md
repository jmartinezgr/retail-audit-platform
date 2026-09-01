# Arquitectura del backend

> Complementa a `PLANNING.md` (qué se construye y por qué, producto/roadmap)
> y a `DATA_MODEL.md` (qué forma tienen los datos: entidades, esquema de
> entrada/salida de cada capa). Este documento es sobre **cómo se organiza
> el código**. Se actualiza cada vez que se agrega un módulo nuevo o se
> toma una decisión estructural.

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
- `ventas.py` — `MetodoPago` (enum) + `VENTA_COLUMNAS_REQUERIDAS` /
  `VENTA_COLUMNAS_OPCIONALES`: el contrato de columnas que se espera del
  excel. Es la fuente de verdad que usa `silver.py` — `DATA_MODEL.md` lo
  documenta en formato humano/diagrama, pero el código manda si difieren.
- `rules/types.py` — `Severidad` (enum ERROR/WARNING) y `CatalogosSnapshot`
  (dataclass con los catálogos como `pl.DataFrame` — la forma en la que el
  motor de reglas necesita los datos, sin saber que vienen de Postgres).
- `rules/engine.py` — el motor de reglas **estáticas**: `_enrich()` hace
  un left-join de silver contra los 5 catálogos de una sola vez (evita
  repetir el join en cada regla), y `evaluar()` corre las 15 reglas
  (funciones = expresiones de Polars vectorizadas, no loops fila por
  fila) devolviendo una fila por (factura, regla). Catálogo completo de
  reglas, severidad y el porqué de cada una en `DATA_MODEL.md`.
  *(pendiente)* el evaluador de reglas **dinámicas** (JSONLogic,
  configurables desde el frontend) — motor aparte, no compite con este.
- `pipeline/bronze.py` — `to_bronze(file_bytes: bytes) -> pl.DataFrame`:
  recibe los bytes crudos del excel (no una ruta ni un objeto de storage,
  para que sea testeable sin MinIO) y devuelve todas las columnas como
  texto (`pl.Utf8`), sin tipar ni validar nada.
- `pipeline/silver.py` — `to_silver(bronze_df: pl.DataFrame) -> pl.DataFrame`:
  tipa cada columna contra el esquema de `Venta` (`domain/ventas.py`) y
  agrega `_errores: List[Utf8]` / `_es_valida: bool` por fila. Ninguna fila
  se descarta. Si faltan columnas obligatorias por completo, lanza
  `SilverSchemaError` en vez de intentar procesar fila por fila — eso es un
  archivo mal formado, no una fila con datos sucios. Esquema completo en
  `DATA_MODEL.md`.
- `pipeline/gold.py` — `to_gold(silver_df, catalogos, hoy=None) -> pl.DataFrame`:
  delgado a propósito, solo llama a `rules.engine.evaluar()`. `hoy` es
  inyectable (default `date.today()`) para que los tests sean
  deterministas sin mockear el reloj del sistema.

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
  `ProductoModel`, `CodigoDescuentoModel`, `TransferenciaModel` con
  `ForeignKey` reales entre sí).
- `storage/minio_client.py` — cliente de MinIO/S3 (`get_minio_client`,
  `get_object_bytes`).
- `storage/lake.py` — `write_delta()` / `read_delta()`: Polars + `deltalake`
  contra el bucket S3-compatible. `storage_options` incluye
  `AWS_ALLOW_HTTP` y `AWS_S3_ALLOW_UNSAFE_RENAME` porque MinIO (y S3
  alternativos en general) no dan por garantizado el locking atómico que
  `delta-rs` asume por defecto en S3 real — como el pipeline es de un solo
  escritor por job, no hace falta ese locking.
- `db/catalog/snapshot.py` — `load_catalog_snapshot(db) -> CatalogosSnapshot`:
  convierte los catálogos de Postgres (vía `CatalogRepository`) a
  `pl.DataFrame` — el único lugar donde SQLAlchemy y `domain/rules`
  se tocan. Se lee EN VIVO cada vez que se llama, sin cachear — es
  justo lo que permite re-ejecutar `gold` después de cambiar algo en un
  catálogo sin tocar bronze/silver.
- *(pendiente)* `storage/duckdb_query.py` — helpers para correr SQL vía
  DuckDB sobre las tablas Delta, si hace falta paginar/filtrar en el
  backend en vez de traer la tabla completa a memoria (hoy `gold` cabe
  cómodo en memoria para el tamaño de esta demo).

#### Convención de rutas en el bucket

```
jobs/{upload_id}/
  upload/{filename}   ← archivo crudo tal cual se subió (no es Delta)
  bronze/              ← tabla Delta (domain/pipeline/bronze.py)
  silver/               ← tabla Delta (domain/pipeline/silver.py)
  gold/                 ← tabla Delta (domain/pipeline/gold.py)
```

`upload/` guarda el archivo tal cual; `bronze/silver/gold` son cada una
directamente una tabla Delta (con su propio `_delta_log/`), al mismo nivel
— nada anidado bajo una carpeta `delta/` genérica. La ruta de `upload/` la
arma `api/uploads/service.py` y queda guardada en `UploadModel.object_name`;
las de `bronze/silver/gold` las arma cada `service.py` de `api/` que las
necesite (hoy solo `api/audits/service.py._bronze_key`).

### `api/` — la única capa que sabe que existe HTTP

Una subcarpeta por feature, cada una con:
- `router.py` — endpoints de FastAPI.
- `schemas.py` — request/response models de Pydantic (DTOs, no se reusan
  como modelos de dominio ni de DB).
- `service.py` — orquesta: llama a `infrastructure/` para leer/guardar,
  llama a `domain/` para la lógica, devuelve datos simples al router.

Ya existe:
- `api/uploads/` — subir excel → URL prefirmada de MinIO → registro en
  Postgres (guarda `object_name` explícito) → consultar estado.
- `api/audits/` — dos triggers separados, a propósito (ver `PLANNING.md`
  §"Re-run gold"):
  - `POST /audits/{upload_id}/run` → `AuditService.run_pipeline` (bronze →
    silver, encadenados — son deterministas del archivo subido, no hay
    razón para separarlos).
  - `POST /audits/{upload_id}/run-gold` → `AuditService.run_gold`: lee el
    `silver` YA GUARDADO en Delta (no rehace bronze/silver) + el estado
    ACTUAL de los catálogos vía `load_catalog_snapshot()`, y regenera
    `gold`. Re-ejecutable en cualquier momento sin volver a subir el
    excel — por ejemplo, después de corregir un código de descuento en
    el catálogo. Solo acá se marca `UploadStatus.COMPLETED` (antes de que
    existiera gold, `run_pipeline` dejaba el estado en `PROCESSING` a
    propósito).

  Ambos corren con `BackgroundTasks` de FastAPI (no bloquean la
  respuesta; el `db: Session` inyectado por `Depends` sigue vivo durante
  la tarea de fondo porque FastAPI corre las background tasks *antes*
  del cierre de dependencias `yield` — por diseño, no por casualidad).

  `GET /audits/{upload_id}/bronze`, `.../silver`, `.../gold` leen la
  tabla Delta correspondiente y la devuelven como preview JSON
  (`LayerPreviewResponse`, genérico para cualquier capa).

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
`tests/domain/rules/test_engine.py` para `src/domain/rules/engine.py`).
Hoy solo cubre `domain/` (pipeline + rules) porque es la parte pura/sin
infraestructura — justo la ventaja de haber aislado `domain/` de
FastAPI/SQLAlchemy/Minio desde el principio: 51 tests, todos con datos en
memoria, sin Postgres ni MinIO corriendo (los tests de `rules/engine.py`
construyen su propio `CatalogosSnapshot` de juguete en vez de leer
Postgres de verdad). `tests/conftest.py` mete `apps/backend` en
`sys.path` (no hay `__init__.py`, así que sin esto los imports
`from src....` no resuelven).

Correr desde `apps/backend` con el venv activo:
```
python -m pytest -v
```

## Scripts operativos

`apps/backend/scripts/` — herramientas que se corren a mano, no código de
la app en producción (ej. `seed_catalog.py`). Se ejecutan con
`python scripts/<archivo>.py` desde `apps/backend`, con el venv activo.

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
