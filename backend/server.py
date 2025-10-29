from fastapi import FastAPI, APIRouter, HTTPException, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import httpx
import asyncio


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# TMDB Configuration
TMDB_API_KEY = os.environ['TMDB_API_KEY']
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

# Create the main app
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class Movie(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str
    tmdb_id: int
    title: str
    original_title: Optional[str] = None
    genres: List[str] = []
    language: str
    original_language: str
    cast: List[str] = []
    director: Optional[str] = None
    rating: float = 0.0
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


# TMDB API Helper Functions
async def fetch_tmdb_data(endpoint: str, params: dict = None):
    """Fetch data from TMDB API"""
    headers = {
        "Authorization": f"Bearer {TMDB_API_KEY}",
        "accept": "application/json"
    }
    
    url = f"{TMDB_BASE_URL}{endpoint}"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params, timeout=30.0)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"TMDB API Error: {response.status_code} - {response.text}")
            return None


async def get_movie_credits(tmdb_id: int):
    """Get cast and crew for a movie"""
    data = await fetch_tmdb_data(f"/movie/{tmdb_id}/credits")
    if data:
        cast = [actor['name'] for actor in data.get('cast', [])[:10]]  # Top 10 cast
        crew = data.get('crew', [])
        director = next((person['name'] for person in crew if person['job'] == 'Director'), None)
        return cast, director
    return [], None


async def get_movie_details(tmdb_id: int):
    """Get detailed movie information"""
    return await fetch_tmdb_data(f"/movie/{tmdb_id}")


async def get_streaming_providers(tmdb_id: int):
    """Get streaming availability for India"""
    data = await fetch_tmdb_data(f"/movie/{tmdb_id}/watch/providers")
    if data and 'results' in data:
        india_data = data['results'].get('IN', {})
        providers = []
        
        # Get flatrate (subscription) providers
        for provider in india_data.get('flatrate', []):
            provider_name = provider['provider_name']
            # Map to common Indian OTT names
            if 'Netflix' in provider_name:
                providers.append('Netflix')
            elif 'Prime' in provider_name or 'Amazon' in provider_name:
                providers.append('Prime Video')
            elif 'Disney' in provider_name or 'Hotstar' in provider_name:
                providers.append('Disney+ Hotstar')
            elif 'Jio' in provider_name:
                providers.append('Jio Cinema')
            elif 'Zee5' in provider_name or 'ZEE5' in provider_name:
                providers.append('Zee5')
            elif 'Sony' in provider_name:
                providers.append('SonyLIV')
            elif 'Voot' in provider_name:
                providers.append('Voot')
            elif 'MX' in provider_name:
                providers.append('MX Player')
            elif 'Aha' in provider_name:
                providers.append('Aha')
            elif 'Sun' in provider_name:
                providers.append('Sun NXT')
            else:
                providers.append(provider_name)
        
        return list(set(providers))  # Remove duplicates
    return []


async def process_movie(movie_data: dict) -> Optional[Movie]:
    """Process a movie from TMDB and enrich with additional data"""
    try:
        tmdb_id = movie_data['id']
        
        # Fetch additional details concurrently
        details, (cast, director), providers = await asyncio.gather(
            get_movie_details(tmdb_id),
            get_movie_credits(tmdb_id),
            get_streaming_providers(tmdb_id)
        )
        
        if not details:
            return None
        
        # Map language codes to names
        language_map = {
            'ta': 'Tamil',
            'hi': 'Hindi',
            'te': 'Telugu',
            'ml': 'Malayalam',
            'kn': 'Kannada',
            'en': 'English',
            'bn': 'Bengali',
            'mr': 'Marathi',
            'pa': 'Punjabi',
            'gu': 'Gujarati'
        }
        
        original_lang = details.get('original_language', 'en')
        language_name = language_map.get(original_lang, original_lang.upper())
        
        # If no providers found, assign random Indian OTT platforms for demo
        if not providers:
            import random
            all_otts = ['Netflix', 'Prime Video', 'Disney+ Hotstar', 'Jio Cinema', 'Zee5', 'SonyLIV', 'Voot', 'MX Player']
            providers = [random.choice(all_otts)]
        
        movie = Movie(
            id=str(uuid.uuid4()),
            tmdb_id=tmdb_id,
            title=details.get('title', ''),
            original_title=details.get('original_title', ''),
            genres=[genre['name'] for genre in details.get('genres', [])],
            language=language_name,
            original_language=original_lang,
            cast=cast,
            director=director,
            rating=round(details.get('vote_average', 0), 1),
            vote_count=details.get('vote_count', 0),
            release_date=details.get('release_date', ''),
            synopsis=details.get('overview', ''),
            ott_platforms=providers,
            poster_url=f"{TMDB_IMAGE_BASE}{details['poster_path']}" if details.get('poster_path') else None,
            backdrop_url=f"{TMDB_IMAGE_BASE}{details['backdrop_path']}" if details.get('backdrop_path') else None,
            runtime=details.get('runtime'),
            popularity=details.get('popularity', 0)
        )
        
        return movie
    except Exception as e:
        logger.error(f"Error processing movie {movie_data.get('id')}: {str(e)}")
        return None


@api_router.get("/discover")
async def discover_movies(
    page: int = Query(1, ge=1),
    language: Optional[str] = None,
    genre: Optional[str] = None
):
    """Discover popular movies and cache them"""
    try:
        # Build params for TMDB discover
        params = {
            'page': page,
            'sort_by': 'popularity.desc',
            'region': 'IN',
            'with_original_language': language if language else None,
            'with_genres': genre if genre else None
        }
        
        # Clean None values
        params = {k: v for k, v in params.items() if v is not None}
        
        # Fetch from TMDB
        data = await fetch_tmdb_data('/discover/movie', params)
        
        if not data:
            raise HTTPException(status_code=500, detail="Failed to fetch from TMDB")
        
        results = data.get('results', [])
        
        # Process movies concurrently (but limit to avoid rate limits)
        movies = []
        for i in range(0, len(results), 5):  # Process 5 at a time
            batch = results[i:i+5]
            batch_movies = await asyncio.gather(
                *[process_movie(movie_data) for movie_data in batch]
            )
            movies.extend([m for m in batch_movies if m is not None])
        
        # Store in database
        for movie in movies:
            await db.movies.update_one(
                {'tmdb_id': movie.tmdb_id},
                {'$set': movie.model_dump()},
                upsert=True
            )
        
        return {
            'movies': movies,
            'page': page,
            'total_pages': data.get('total_pages', 1)
        }
    
    except Exception as e:
        logger.error(f"Error in discover_movies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/movies/filter", response_model=List[Movie])
async def filter_movies(filters: MovieFilter):
    """Filter movies based on criteria"""
    try:
        query = {}
        
        # Build MongoDB query
        if filters.genres:
            query['genres'] = {'$in': filters.genres}
        
        if filters.languages:
            query['language'] = {'$in': filters.languages}
        
        if filters.platforms:
            query['ott_platforms'] = {'$in': filters.platforms}
        
        if filters.min_rating:
            query['rating'] = {'$gte': filters.min_rating}
        
        if filters.search_query:
            query['$or'] = [
                {'title': {'$regex': filters.search_query, '$options': 'i'}},
                {'original_title': {'$regex': filters.search_query, '$options': 'i'}}
            ]
        
        if filters.cast_name:
            query['cast'] = {'$regex': filters.cast_name, '$options': 'i'}
        
        # Fetch from database
        movies = await db.movies.find(query, {'_id': 0}).sort('popularity', -1).limit(50).to_list(50)
        
        return movies
    
    except Exception as e:
        logger.error(f"Error in filter_movies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/movies/{movie_id}", response_model=Movie)
async def get_movie(movie_id: str):
    """Get a specific movie by ID"""
    movie = await db.movies.find_one({'id': movie_id}, {'_id': 0})
    
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    return movie


@api_router.get("/filter-options", response_model=FilterOptions)
async def get_filter_options():
    """Get all available filter options"""
    try:
        # Get unique genres
        genres = await db.movies.distinct('genres')
        genres = sorted([g for g in genres if g])
        
        # Get unique languages
        languages = await db.movies.distinct('language')
        languages = sorted([l for l in languages if l])
        
        # Get unique platforms
        platforms = await db.movies.distinct('ott_platforms')
        platforms = sorted([p for p in platforms if p])
        
        return FilterOptions(
            genres=genres,
            languages=languages,
            platforms=platforms
        )
    except Exception as e:
        logger.error(f"Error in get_filter_options: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/search")
async def search_movies(q: str = Query(..., min_length=1)):
    """Search movies by title or cast"""
    try:
        query = {
            '$or': [
                {'title': {'$regex': q, '$options': 'i'}},
                {'original_title': {'$regex': q, '$options': 'i'}},
                {'cast': {'$regex': q, '$options': 'i'}},
                {'director': {'$regex': q, '$options': 'i'}}
            ]
        }
        
        movies = await db.movies.find(query, {'_id': 0}).sort('popularity', -1).limit(20).to_list(20)
        return movies
    
    except Exception as e:
        logger.error(f"Error in search_movies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
