from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Clinical Memory System Gateway"

    database_url: str = (
        "postgresql+psycopg2://postgres:postgres@localhost:5432/clinical_memory"
    )

    jwt_secret_key: str = "CHANGE_THIS_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"

    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    class Config:
        env_file = ".env"


settings = Settings()