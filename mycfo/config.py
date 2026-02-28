import os


class Config:
    APP_ENV = os.getenv("APP_ENV", "development")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///mycfo.db")
    JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
    JWT_ACCESS_TTL_SECONDS = int(os.getenv("JWT_ACCESS_TTL_SECONDS", "1800"))
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    SQLALCHEMY_ECHO = False
