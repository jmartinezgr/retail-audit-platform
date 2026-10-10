import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ruta absoluta al .env de apps/agent, no relativa al cwd del proceso -
# cuando el backend importa este módulo para exponer /agent/ask (ver
# apps/backend/src/api/agent/service.py), el cwd real es apps/backend,
# cuyo propio .env (otras claves: DATABASE_URL, S3_*, etc.) rompía la
# carga de esta Settings con "extra inputs not permitted" (visto en
# pruebas reales del endpoint).
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # El agente nunca importa infrastructure/ del backend (ver
    # docs/copilot-spec.md) - le pega por HTTP al backend ya corriendo,
    # así no duplica credenciales de Postgres/R2 ni su configuración.
    #
    # Default dinámico, no hardcodeado: en Render, $PORT lo asigna la
    # plataforma en cada deploy (no es un valor fijo) - si no hay $PORT
    # (dev local), cae al 8000 de siempre. Importa sobre todo en
    # producción: el backend se llama a sí mismo por loopback en vez de
    # salir a su propia URL pública (ver apps/agent/README.md, "Chat UI"
    # - evita una vuelta innecesaria por el borde/proxy de Render para
    # una llamada que nunca sale de la misma máquina).
    BACKEND_BASE_URL: str = Field(default_factory=lambda: f"http://127.0.0.1:{os.environ.get('PORT', '8000')}")

    # "ollama" (local, gratis, necesita Ollama corriendo) o "groq" (API
    # gratuita hosteada, sin tarjeta - ver apps/agent/README.md para qué
    # modelo usar y por qué, verificado en vivo, no de memoria).
    LLM_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-20b"

    # "ollama" o "gemini" (API gratuita de Google AI Studio, sin
    # tarjeta) - independiente de LLM_PROVIDER, se puede mezclar (ej.
    # chat con Groq, embeddings con Gemini, como en prod) porque Groq no
    # ofrece embeddings propios.
    EMBED_PROVIDER: str = "ollama"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    GOOGLE_API_KEY: str = ""
    GEMINI_EMBED_MODEL: str = "gemini-embedding-001"

    # Fase 3 (RAG) - Qdrant corre aparte del docker-compose principal del
    # proyecto (ver apps/agent/README.md), colección propia para no
    # mezclarse con nada de otro proyecto que use la misma instancia.
    # En producción, QDRANT_URL=":memory:" usa el modo embebido de
    # qdrant-client (sin servidor aparte) - el índice vive solo en RAM
    # de este proceso y se reconstruye solo, perezosamente, en el primer
    # uso real (ver agent/rag/retrieve.py).
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "auditlake_rules"

    # Tope de iteraciones agente<->tools antes de forzar una respuesta
    # parcial en vez de seguir loopeando (ver docs/copilot-spec.md,
    # restricción #4).
    MAX_STEPS: int = 8

    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8")

    @property
    def EMBED_DIM(self) -> int:
        """Derivado del proveedor, no una variable aparte a sincronizar a
        mano - verificado en vivo (no asumido): nomic-embed-text da 768,
        gemini-embedding-001 da 3072. Si EMBED_PROVIDER cambia, esto
        cambia solo; una colección de Qdrant ya creada con la dimensión
        vieja no se migra sola (ver "Setup" en el README si cambias de
        proveedor con un índice ya construido)."""
        return 3072 if self.EMBED_PROVIDER == "gemini" else 768


settings = Settings()
