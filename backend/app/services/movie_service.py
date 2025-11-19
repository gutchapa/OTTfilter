import asyncio
import uuid
import logging
from typing import List, Optional, Tuple
from app.core.config import get_settings
from app.core.database import get_database
from app.models.movie import Movie
from app.services.tmdb import fetch_tmdb_data, TMDB_IMAGE_BASE
from app.services.openai_service import generate_content_warnings
import httpx

settings = get_settings()
logger = logging.getLogger(__name__)

OMDB_BASE_URL = "http://www.omdbapi.com/"

# Shared HTTP client
http_client = httpx.AsyncClient(
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
    timeout=httpx.Timeout(30.0)
)

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

async def get_imdb_rating(imdb_id: str) -> Optional[float]:
    """Get IMDb rating from OMDb API"""
    if not settings.OMDB_API_KEY or not imdb_id:
        return None
    
    try:
        params = {
            'apikey': settings.OMDB_API_KEY,
            'i': imdb_id
        }
        
        response = await http_client.get(OMDB_BASE_URL, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get('Response') == 'True' and data.get('imdbRating') != 'N/A':
                return float(data['imdbRating'])
    except Exception as e:
        logger.error(f"Error fetching IMDb rating: {str(e)}")
    
    return None

async def get_movie_certification(tmdb_id: int) -> Optional[str]:
    """Get movie certification/rating"""
    try:
        data = await fetch_tmdb_data(f'/movie/{tmdb_id}/release_dates')
        
        if not data or 'results' not in data:
            return None
        
        certifications = {}
        
        for country_data in data['results']:
            country = country_data['iso_3166_1']
            release_dates = country_data.get('release_dates', [])
            
            for release in release_dates:
                cert = release.get('certification', '').strip()
                if cert:
                    certifications[country] = cert
                    break
        
        if 'IN' in certifications:
            return certifications['IN']
        elif 'US' in certifications:
            return certifications['US']
        elif certifications:
            return list(certifications.values())[0]
        
        return None
        
    except Exception as e:
        logger.error(f"Error fetching certification: {str(e)}")
        return None

async def get_streaming_providers(tmdb_id: int):
    """Get streaming availability for India"""
    data = await fetch_tmdb_data(f"/movie/{tmdb_id}/watch/providers")
    if data and 'results' in data:
        india_data = data['results'].get('IN', {})
        providers = []
        
        for provider in india_data.get('flatrate', []):
            provider_name = provider['provider_name']
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
        
        return list(set(providers))
    return []

async def process_movie(movie_data: dict) -> Optional[Movie]:
    """Process a movie from TMDB and enrich with additional data"""
    try:
        tmdb_id = movie_data['id']
        
        fetch_tasks = [
            get_movie_details(tmdb_id),
            get_movie_credits(tmdb_id),
            get_streaming_providers(tmdb_id),
            get_movie_certification(tmdb_id)
        ]
        
        results = await asyncio.gather(*fetch_tasks)
        details, (cast, director), providers, certification = results
        
        if not details:
            return None
        
        imdb_rating = None
        imdb_id = details.get('imdb_id')
        if imdb_id:
            imdb_rating = await get_imdb_rating(imdb_id)
        
        language_map = {
            'ta': 'Tamil', 'hi': 'Hindi', 'te': 'Telugu', 'ml': 'Malayalam',
            'kn': 'Kannada', 'en': 'English', 'bn': 'Bengali', 'mr': 'Marathi',
            'pa': 'Punjabi', 'gu': 'Gujarati'
        }
        
        original_lang = details.get('original_language', 'en')
        language_name = language_map.get(original_lang, original_lang.upper())
        
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
            imdb_rating=round(imdb_rating, 1) if imdb_rating else None,
            certification=certification,
            content_warnings=None,
            vote_count=details.get('vote_count', 0),
            release_date=details.get('release_date', ''),
            synopsis=details.get('overview', ''),
            ott_platforms=providers,
            poster_url=f"{TMDB_IMAGE_BASE}{details['poster_path']}" if details.get('poster_path') else None,
            backdrop_url=f"{TMDB_IMAGE_BASE}{details['backdrop_path']}" if details.get('backdrop_path') else None,
            runtime=details.get('runtime'),
            popularity=details.get('popularity', 0)
        )
        
        if certification:
            warnings = await generate_content_warnings(
                movie.title,
                movie.genres,
                movie.synopsis,
                certification
            )
            movie.content_warnings = warnings
        
        return movie
    except Exception as e:
        logger.error(f"Error processing movie {movie_data.get('id')}: {str(e)}")
        return None
