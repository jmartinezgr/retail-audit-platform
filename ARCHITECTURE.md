# Arquitectura del backend

> Complementa a `PLANNING.md` (qué se construye y por qué, producto/roadmap).
> Este documento es sobre **cómo se organiza el código**. Se actualiza cada
> vez que se agrega un módulo nuevo o se toma una decisión estructural.

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
- `catalog.py` — `TipoDescuento`, `Categoria` (enums). Los catálogos son
  sobre todo datos de referencia; no hay más lógica de dominio acá todavía
  — cuando el motor de reglas necesite evaluar cosas como "¿está vigente
  este código de descuento hoy?", esa lógica va en `rules/`, no aquí.
- *(pendiente)* `rules/` — motor de reglas: reglas estáticas + evaluador de
  reglas dinámicas (JSONLogic).
- `pipeline/bronze.py` — `to_bronze(file_bytes: bytes) -> pl.DataFrame`:
  recibe los bytes crudos del excel (no una ruta ni un objeto de storage,
  para que sea testeable sin MinIO) y devuelve todas las columnas como
  texto (`pl.Utf8`), sin tipar ni validar nada. *(pendiente)* `silver.py`,
  `gold.py`.

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
- *(pendiente)* `storage/duckdb_query.py` — helpers para correr SQL vía
  DuckDB sobre las tablas Delta (lo que consume `api/` para servir
  resultados paginados/filtrados, cuando exista `gold`).

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
- `api/audits/` — `POST /audits/{upload_id}/run` dispara el pipeline con
  `BackgroundTasks` de FastAPI (no bloquea la respuesta; el `db: Session`
  inyectado por `Depends` sigue vivo durante la tarea de fondo porque
  FastAPI corre las background tasks *antes* del cierre de dependencias
  `yield` — por diseño, no por casualidad). `GET /audits/{upload_id}/bronze`
  lee la tabla Delta resultante y la devuelve como preview JSON. Hoy solo
  corre `bronze()`; cuando existan `silver()`/`gold()` se encadenan en el
  mismo `AuditService.run_bronze` (o se renombra a algo como `run_pipeline`).

Pendiente: `api/catalog/` (CRUD de sedes/trabajadores/productos/etc., solo
si la fase de reglas dinámicas editables lo necesita).

## Convención de imports

Sin `__init__.py` (namespace packages implícitos de Python 3) — así estaba
ya y se mantiene. Los imports son siempre absolutos desde `src`, ej.
`from src.infrastructure.db.uploads.repository import UploadRepository`.
Se corre con `uvicorn src.main:app` desde `apps/backend/` (para que `src`
resuelva como paquete).

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
