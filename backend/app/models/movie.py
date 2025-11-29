from pydantic import BaseModel, Field
from typing import List, Optional

class Movie(BaseModel):
    class Config: orm_mode = True
    id: str
    tmdb_id: int
    title: str
    original_title: Optional[str] = None
    genres: List[str] = []
    language: str
    original_language: str
    cast: List[str] = []
    director: Optional[str] = None
    rating: float = 0.0  # TMDB rating
    imdb_rating: Optional[float] = None  # IMDb rating from OMDb
    certification: Optional[str] = None  # Content rating (PG, PG-13, R, U/A, etc.)
    content_warnings: Optional[List[str]] = None  # Detailed content warnings
    vote_count: int = 0
    release_date: Optional[str] = None
    synopsis: str = ""
    ott_platforms: List[str] = []
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    runtime: Optional[int] = None
    popularity: float = 0.0

class MovieFilter(BaseModel):
    genres: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    platforms: Optional[List[str]] = None
    min_rating: Optional[float] = None
    search_query: Optional[str] = None
    cast_name: Optional[str] = None

class FilterOptions(BaseModel):
    genres: List[str]
    languages: List[str]
    platforms: List[str]

class NaturalLanguageQuery(BaseModel):
    query: str

class ParsedQuery(BaseModel):
    genres: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    platforms: Optional[List[str]] = None
    min_rating: Optional[float] = None
    cast_name: Optional[str] = None
    keywords: Optional[str] = None
    release_year: Optional[int] = None  # For filtering by year (e.g., "2024 movies")
    sort_by: Optional[str] = "popularity"
    intent: Optional[str] = None

class YouTubeVideo(BaseModel):
    video_id: str
    title: str
    thumbnail_url: str
    channel_title: str
    url: str
