from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str
    debug: bool

    DATABASE_URL: str
    # Genéricos S3-compatible - MinIO local, Cloudflare R2 en prod, mismo
    # código (infrastructure/storage/lake.py + s3_client.py), solo cambian
    # estos valores.
    S3_ENDPOINT: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET: str
    # Defaults = comportamiento local actual (MinIO por HTTP). En prod contra
    # R2 (HTTPS-only, exige region "auto"): S3_SECURE=true, S3_REGION=auto.
    S3_SECURE: bool = False
    S3_REGION: str = "us-east-1"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
