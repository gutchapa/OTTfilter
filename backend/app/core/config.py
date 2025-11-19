from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    MONGO_URL: str
    DB_NAME: str = "ott_filter"
    TMDB_API_KEY: str
    OPENAI_API_KEY: Optional[str] = None
    YOUTUBE_API_KEY: Optional[str] = None
    OMDB_API_KEY: Optional[str] = None
    JUSTWATCH_ENABLED: bool = False  # JustWatch API is currently broken (404 errors)

    class Config:
        extra = "ignore"
        # Look for .env in the backend directory (parent of app)
        import os
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
        env_file_encoding = 'utf-8'

@lru_cache
def get_settings():
    return Settings()
