# AuditLake

Proyecto de portafolio: motor de auditoría de datos por capas
(bronze/silver/gold, estilo lakehouse) para ventas de una cadena de tiendas
ficticia. Antes de tocar código, lee:

- `PLANNING.md` — qué se construye, decisiones de producto/stack, y por qué
  (dominio, reglas, deploy, fases).
- `ARCHITECTURE.md` — cómo se organiza el código del backend
  (`domain/infrastructure/api`) y por qué se eligió así en vez de
  "package by feature" o hexagonal estricto.

Ambos son documentos vivos: si tomas o cambias una decisión relevante de
producto o de estructura, actualízalos en el mismo turno, no lo dejes para
después.

## Stack

- Backend: Python (FastAPI, SQLAlchemy, Polars, `deltalake`, DuckDB).
- Frontend: React + Vite.
- Storage: MinIO (local, vía `docker-compose.yml`) / Cloudflare R2 (prod).
- DB operacional: Postgres.
- No hay NestJS ni Spark en este proyecto — ver `PLANNING.md` y
  `ARCHITECTURE.md` para el razonamiento.
