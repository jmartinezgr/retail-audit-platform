from fastapi import FastAPI
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

# Crear tablas en BD
Base.metadata.create_all(bind=engine)

# Registrar routers
app.include_router(uploads_router)
app.include_router(audits_router)
app.include_router(demo_router)
app.include_router(rules_router)
