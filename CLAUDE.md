# AuditLake

Proyecto de portafolio: motor de auditoría de datos por capas
(bronze/silver/gold, estilo lakehouse) para ventas de una cadena de tiendas
ficticia. Antes de tocar código, lee:

- `docs/PLANNING.md` — qué se construye, decisiones de producto/stack, y
  por qué (dominio, reglas, deploy, fases).
- `docs/ARCHITECTURE.md` — cómo se organiza el código, backend
  (`domain/infrastructure/api`, y por qué en vez de "package by feature"
  o hexagonal estricto) y frontend (`apps/frontend/`, React + Vite +
  shadcn/ui).
- `docs/DATA_MODEL.md` — las entidades del dominio (catálogos + Venta) y
  el esquema de entrada/salida de cada capa del pipeline (qué columnas
  espera el excel, qué forma tiene bronze/silver/gold), con diagrama de
  clases.

Todos son documentos vivos: si tomas o cambias una decisión relevante de
producto, estructura, o esquema de datos, actualízalos en el mismo turno,
no lo dejes para después.

## CORS

`main.py` arma `allow_origins` desde `settings.cors_origins_list`
(`CORS_ORIGINS` en `.env`, coma-separado). Default = solo
`http://localhost:5173` (dev de Vite, aunque normalmente ni hace falta —
el dev server ya proxea `/api` mismo-origen, ver `vite.config.ts`). En
prod (Render), `CORS_ORIGINS` se pone al dominio real del frontend en
Vercel. El `.env` local del usuario tiene `CORS_ORIGINS=*` (sin commitear,
es su override personal) para poder seguir usando un visor HTML
provisional (`viewer.html`, fuera del repo, en un scratchpad) que le pega
directo al backend sin pasar por el proxy de Vite — no cambiar ese default
del código a `*`, es solo su `.env` local.

## Stack

- Backend: Python (FastAPI, SQLAlchemy, Polars, `deltalake`, DuckDB).
- Frontend: React + Vite + TypeScript, Tailwind + shadcn/ui, TanStack Query.
- Storage: MinIO (local, vía `docker-compose.yml`) / Cloudflare R2 (prod).
- DB operacional: Postgres.
- No hay NestJS ni Spark en este proyecto — ver `PLANNING.md` y
  `ARCHITECTURE.md` para el razonamiento.
