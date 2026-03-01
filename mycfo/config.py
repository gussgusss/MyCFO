import os


class Config:
    APP_ENV = os.getenv("APP_ENV", "development")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///mycfo.db")
    JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
    JWT_ACCESS_TTL_SECONDS = int(os.getenv("JWT_ACCESS_TTL_SECONDS", "1800"))
    HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
    HUGGINGFACE_MODEL = os.getenv("HUGGINGFACE_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")
    HUGGINGFACE_TIMEOUT_SECONDS = int(os.getenv("HUGGINGFACE_TIMEOUT_SECONDS", "30"))
    SQLALCHEMY_ECHO = False
