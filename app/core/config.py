from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str
    OPENAI_API_KEY: str
    FIREBASE_PROJECT_ID: str
    FIREBASE_CREDENTIALS_JSON: str


settings = Settings()
