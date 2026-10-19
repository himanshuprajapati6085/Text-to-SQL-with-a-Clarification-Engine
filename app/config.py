from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_ENV: str = "development"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DATABASE_URL: str = "sqlite:///./college.db"
    LLM_API_KEY: str = "mock-key-development"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    MAX_RESULT_ROWS: int = 200
    QUERY_TIMEOUT_SECONDS: int = 5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
