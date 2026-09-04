from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str
    debug: bool

    DATABASE_URL: str
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str
    # Defaults = comportamiento local actual (MinIO por HTTP). En prod contra
    # R2 (HTTPS-only, exige region "auto"): MINIO_SECURE=true, MINIO_REGION=auto.
    MINIO_SECURE: bool = False
    MINIO_REGION: str = "us-east-1"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
