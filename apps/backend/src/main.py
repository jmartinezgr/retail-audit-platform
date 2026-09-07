import duckdb
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from src.infrastructure.config.settings import settings
from src.infrastructure.db.base import Base
from src.infrastructure.db.session import engine

# IMPORTANTE:
# Importar modelos para que SQLAlchemy los detecte
from src.infrastructure.db.uploads.models import UploadModel
from src.infrastructure.db.catalog.models import (
    SedeModel,
    TrabajadorModel,
    ProductoModel,
    CodigoDescuentoModel,
    TransferenciaModel,
)
from src.infrastructure.db.rules.models import RuleDefinitionModel
from src.api.uploads.router import router as uploads_router
from src.api.audits.router import router as audits_router
from src.api.demo.router import router as demo_router
from src.api.rules.router import router as rules_router

app = FastAPI(title="Retail Audit Platform - Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crear tablas en BD
Base.metadata.create_all(bind=engine)

# Registrar routers
app.include_router(uploads_router)
app.include_router(audits_router)
app.include_router(demo_router)
app.include_router(rules_router)


@app.get("/healthz")
def healthz():
    """Health check para el hosting (ej. Render) - sin tocar DB/storage,
    solo confirma que el proceso está vivo y respondiendo."""
    return {"status": "ok"}


@app.exception_handler(duckdb.IOException)
async def duckdb_io_exception_handler(request: Request, exc: duckdb.IOException) -> JSONResponse:
    """delta_scan() sobre una capa (bronze/silver/gold) que todavía no
    existe -porque el pipeline sigue corriendo en background- lanza este
    error genérico de DuckDB, no un 404 real. Un `Exception`/500 sin
    registrar aquí se resuelve en ServerErrorMiddleware, que queda *fuera*
    de CORSMiddleware - el navegador lo reportaría como un falso bloqueo
    de CORS en vez del error real (visto en /dashboard, /gold, etc. antes
    de este fix). `duckdb.IOException` no es la clase `Exception` desnuda,
    así que Starlette la maneja en ExceptionMiddleware (adentro de
    CORSMiddleware) y la respuesta sí lleva los headers correctos.
    """
    if "No files in log segment" in str(exc):
        return JSONResponse(
            status_code=404,
            content={"detail": "This layer isn't available yet - process the pipeline first."},
        )
    return JSONResponse(status_code=500, content={"detail": "Storage error. Please try again."})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Último recurso para cualquier otra excepción no prevista - da un
    cuerpo JSON legible en vez del texto plano por defecto de Starlette.
    Nota: por lo explicado arriba, esta respuesta específica NO lleva
    headers CORS (limitación de Starlette con `Exception`/500 desnudo),
    así que en el navegador se sigue viendo como un fallo de CORS - pero
    ya no debería dispararse en el flujo normal de la app."""
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
