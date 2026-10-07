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
    JUSTWATCH_ENABLED: bool = True  # Using custom JustWatch implementation

    # Semantic search (EmbeddingGemma). Off by default; needs requirements-embeddings.txt
    EMBEDDINGS_ENABLED: bool = False
    EMBEDDING_MODEL: str = "google/embeddinggemma-300m"
    EMBEDDING_DIM: int = 256  # Matryoshka: 768, 512, 256 or 128
    SEMANTIC_WEIGHT: float = 500.0  # Similarity (0-1) x weight is added to popularity when ranking
    HF_TOKEN: Optional[str] = None  # Model is gated: accept the Gemma licence on Hugging Face first

    class Config:
        extra = "ignore"
        # Look for .env in the backend directory (parent of app)
        import os
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
        env_file_encoding = 'utf-8'

@lru_cache
def get_settings():
    return Settings()
