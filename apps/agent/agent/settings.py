from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # El agente nunca importa infrastructure/ del backend (ver
    # docs/copilot-spec.md) - le pega por HTTP al backend ya corriendo,
    # así no duplica credenciales de Postgres/R2 ni su configuración.
    BACKEND_BASE_URL: str = "http://127.0.0.1:8000"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"

    # Fase 3 (RAG) - Qdrant corre aparte del docker-compose principal del
    # proyecto (ver apps/agent/README.md), colección propia para no
    # mezclarse con nada de otro proyecto que use la misma instancia.
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "auditlake_rules"

    # Tope de iteraciones agente<->tools antes de forzar una respuesta
    # parcial en vez de seguir loopeando (ver docs/copilot-spec.md,
    # restricción #4).
    MAX_STEPS: int = 8

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
