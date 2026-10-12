from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Eco Monitoring API"
    database_url: str
    log_level: str = "INFO"
    log_json: bool = True


settings = Settings()
