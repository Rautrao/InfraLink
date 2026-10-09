from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://infra:infra_dev_password@localhost:5432/infra"
    jwt_secret: str = "replace-this-development-secret"
    cors_origins: str = "http://localhost:3000"
    dev_mode: bool = True
    upload_dir: str = "/data/uploads"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
