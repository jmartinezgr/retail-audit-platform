# AuditLake

Proyecto de portafolio: motor de auditoría de datos por capas
(bronze/silver/gold, estilo lakehouse) para ventas de una cadena de tiendas
ficticia. Antes de tocar código, lee:

- `docs/PLANNING.md` — qué se construye, decisiones de producto/stack, y
  por qué (dominio, reglas, deploy, fases).
- `docs/ARCHITECTURE.md` — cómo se organiza el código del backend
  (`domain/infrastructure/api`) y por qué se eligió así en vez de
  "package by feature" o hexagonal estricto.
- `docs/DATA_MODEL.md` — las entidades del dominio (catálogos + Venta) y
  el esquema de entrada/salida de cada capa del pipeline (qué columnas
  espera el excel, qué forma tiene bronze/silver/gold), con diagrama de
  clases.

Todos son documentos vivos: si tomas o cambias una decisión relevante de
producto, estructura, o esquema de datos, actualízalos en el mismo turno,
no lo dejes para después.

## Estado local sin commitear (a propósito)

`apps/backend/src/main.py` tiene un `CORSMiddleware(allow_origins=["*"])`
agregado a mano, **sin commitear**, para un visor HTML provisional
(`viewer.html`, vive fuera del repo en un scratchpad, no en el proyecto)
que navega uploads/bronze/silver/gold desde el navegador. Es intencional:
- No commitear tal cual (`allow_origins=["*"]` no debe llegar a producción).
- No "limpiarlo" automáticamente tampoco — el usuario lo pidió dejar así
  para seguir usando el visor. Si algún día se commitea CORS de verdad
  (para el frontend real de la fase 6), hay que acotar `allow_origins` al
  dominio real, no dejarlo abierto.
- Si `git status` muestra `main.py` modificado sin que nadie lo haya
  tocado en la sesión actual, es por esto — no es un cambio perdido.

## Stack

- Backend: Python (FastAPI, SQLAlchemy, Polars, `deltalake`, DuckDB).
- Frontend: React + Vite.
- Storage: MinIO (local, vía `docker-compose.yml`) / Cloudflare R2 (prod).
- DB operacional: Postgres.
- No hay NestJS ni Spark en este proyecto — ver `PLANNING.md` y
  `ARCHITECTURE.md` para el razonamiento.
