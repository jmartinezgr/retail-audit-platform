from fastapi import FastAPI
from src.infrastructure.db.base import Base
from src.infrastructure.db.session import engine

# IMPORTANTE:
# Importar modelos para que SQLAlchemy los detecte
from src.infrastructure.db.uploads.models import UploadModel
from src.api.uploads.router import router as uploads_router

app = FastAPI(title="Retail Audit Platform - Backend")

# Crear tablas en BD
Base.metadata.create_all(bind=engine)

# Registrar routers
app.include_router(uploads_router)
