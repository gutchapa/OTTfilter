from fastapi import FastAPI, APIRouter, HTTPException, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Tuple
import uuid
from datetime import datetime, timezone
import httpx
import asyncio
import json
from openai import AsyncOpenAI
from googleapiclient.discovery import build
from difflib import SequenceMatcher


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

# OpenAI Configuration
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# YouTube Configuration
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', '')
youtube_service = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY) if YOUTUBE_API_KEY else None

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


class NaturalLanguageQuery(BaseModel):
    query: str


class ParsedQuery(BaseModel):
    genres: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    platforms: Optional[List[str]] = None
    min_rating: Optional[float] = None
    cast_name: Optional[str] = None
    keywords: Optional[str] = None
    sort_by: Optional[str] = "popularity"
    intent: Optional[str] = None


class YouTubeVideo(BaseModel):
    video_id: str
    title: str
    thumbnail_url: str
    channel_title: str
    url: str


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



# AI-powered Natural Language Processing
async def parse_natural_language_query(query: str) -> ParsedQuery:
    """Parse natural language query using OpenAI to extract filters"""
    if not openai_client:
        # Fallback: return basic query
        return ParsedQuery(keywords=query)
    
    try:
        system_prompt = """You are a movie search query parser. Extract structured filters from natural language queries.

Available options:
- Languages: Tamil, Hindi, Telugu, Malayalam, Kannada, English, Bengali, Marathi, Punjabi, Gujarati
- Genres: Action, Adventure, Animation, Comedy, Crime, Drama, Fantasy, Horror, Music, Romance, Science Fiction, Thriller, War
- Platforms: Netflix, Prime Video, Disney+ Hotstar, Jio Cinema, Zee5, SonyLIV, Voot, MX Player, Aha, Sun NXT

PLATFORM NAME VARIATIONS (user may say any of these):
- "jio", "jio star", "jio cinema", "jiocinema" -> map to "Jio Cinema"
- "netflix" -> "Netflix"  
- "prime", "prime video", "amazon prime" -> "Prime Video"
- "hotstar", "disney hotstar", "disney+ hotstar" -> "Disney+ Hotstar"
- "zee5", "zee 5" -> "Zee5"
- "sony", "sonyliv", "sony liv" -> "SonyLIV"
- If user mentions a platform, put it in platforms array, NOT in keywords

IMPORTANT: Users may have typos in actor names. Keep the name AS-IS in cast_name field.

Extract and return JSON with:
{
  "languages": ["Tamil"],  // if language mentioned
  "genres": ["Romance"],  // if genre mentioned  
  "platforms": ["Jio Cinema"],  // if ANY platform mentioned (check variations above)
  "min_rating": 7.0,  // if rating mentioned
  "cast_name": "exact name from query",  // actor/director name EXACTLY as typed
  "keywords": null,  // ONLY for song names or specific movie titles, NOT for platforms
  "sort_by": "release_date",  // "rating" if "highest/best", "release_date" if "latest/recent/new", else "popularity"
  "intent": "search_movie"
}

Examples:
- "jio star movies" -> {"platforms": ["Jio Cinema"]}
- "latest tamil movies on netflix" -> {"languages": ["Tamil"], "platforms": ["Netflix"], "sort_by": "release_date"}
- "fahid fasil latest movie" -> {"cast_name": "fahid fasil", "sort_by": "release_date"}
- "tamil movie with sollamale song" -> {"languages": ["Tamil"], "keywords": "sollamale", "intent": "search_song"}
- "prime video action movies" -> {"platforms": ["Prime Video"], "genres": ["Action"]}

Return only valid JSON, no explanations."""

        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Parse this query: {query}"}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        parsed_data = json.loads(response.choices[0].message.content)
        return ParsedQuery(**parsed_data)
        
    except Exception as e:
        logger.error(f"Error parsing natural language query: {str(e)}")
        return ParsedQuery(keywords=query)


# YouTube Integration
def search_youtube_videos(query: str, max_results: int = 5) -> List[YouTubeVideo]:
    """Search YouTube for videos"""
    if not youtube_service:
        return []
    
    try:
        request = youtube_service.search().list(
            part='snippet',
            q=query,
            type='video',
            maxResults=max_results,
            regionCode='IN'
        )
        response = request.execute()
        
        videos = []
        for item in response.get('items', []):
            video = YouTubeVideo(
                video_id=item['id']['videoId'],
                title=item['snippet']['title'],
                thumbnail_url=item['snippet']['thumbnails']['medium']['url'],
                channel_title=item['snippet']['channelTitle'],
                url=f"https://www.youtube.com/watch?v={item['id']['videoId']}"
            )
            videos.append(video)
        
        return videos
    except Exception as e:
        logger.error(f"Error searching YouTube: {str(e)}")
        return []



# Fuzzy Matching Helpers
def fuzzy_match_score(str1: str, str2: str) -> float:
    """Calculate similarity between two strings (0-1)"""
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

def find_best_match(query: str, options: List[str], threshold: float = 0.6) -> Optional[Tuple[str, float]]:
    """Find best matching option for a query string"""
    best_match = None
    best_score = 0
    
    for option in options:
        score = fuzzy_match_score(query, option)
        if score > best_score and score >= threshold:
            best_score = score
            best_match = option
    
    return (best_match, best_score) if best_match else None

async def fuzzy_search_actor(name: str) -> Optional[Tuple[int, str]]:
    """Search for actor with fuzzy matching across multiple attempts"""
    # Try original name first
    search_params = {'query': name, 'page': 1}
    person_data = await fetch_tmdb_data('/search/person', search_params)
    
    if person_data and person_data.get('results'):
        # Check each result and find best fuzzy match
        best_match = None
        best_score = 0
        
        for person in person_data['results'][:5]:
            person_name = person['name']
            score = fuzzy_match_score(name, person_name)
            
            # Test if this person has movies
            test_params = {'with_cast': person['id'], 'page': 1}
            test_data = await fetch_tmdb_data('/discover/movie', test_params)
            
            if test_data and test_data.get('results') and len(test_data['results']) > 0:
                if score > best_score:
                    best_score = score
                    best_match = (person['id'], person['name'])
        
        if best_match:
            logger.info(f"Fuzzy matched '{name}' to '{best_match[1]}' (score: {best_score:.2f})")
            return best_match
    
    # Try variations
    name_parts = name.lower().split()
    if len(name_parts) >= 2:
        # Try with common spelling variations
        variations = [
            ' '.join(name_parts),  # Original
            ' '.join(name_parts[::-1]),  # Reversed
            name_parts[0] + ' ' + name_parts[-1],  # First and last only
        ]
        
        for variant in variations[1:]:  # Skip first as already tried
            search_params = {'query': variant, 'page': 1}


async def correct_actor_name(misspelled_name: str) -> str:
    """Use LLM to correct actor name spelling"""
    if not openai_client:
        return misspelled_name
    
    try:
        prompt = f"""Given this possibly misspelled Indian actor/actress name: "{misspelled_name}"

Correct it to the most likely proper spelling. Common Indian actors include:
- Fahadh Faasil (Malayalam)
- Vijay, Rajinikanth, Suriya, Ajith Kumar, Dhanush (Tamil)
- Aishwarya Lekshmi, Aishwarya Rajesh (Tamil/Malayalam)
- Prabhas, Mahesh Babu, Allu Arjun (Telugu)
- Shah Rukh Khan, Aamir Khan, Salman Khan, Ranbir Kapoor (Hindi)

Return ONLY the corrected name, nothing else. If unsure, return the original name."""

        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert in Indian cinema actor names."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=50
        )
        
        corrected = response.choices[0].message.content.strip()
        if corrected and corrected.lower() != misspelled_name.lower():
            logger.info(f"Name correction: '{misspelled_name}' → '{corrected}'")
            return corrected
        return misspelled_name
        
    except Exception as e:
        logger.error(f"Error correcting actor name: {str(e)}")
        return misspelled_name

            person_data = await fetch_tmdb_data('/search/person', search_params)
            
            if person_data and person_data.get('results'):
                for person in person_data['results'][:3]:
                    # Quick test
                    test_params = {'with_cast': person['id'], 'page': 1}
                    test_data = await fetch_tmdb_data('/discover/movie', test_params)
                    
                    if test_data and test_data.get('results') and len(test_data['results']) > 0:
                        logger.info(f"Variation matched '{name}' to '{person['name']}'")
                        return (person['id'], person['name'])
    
    return None


@api_router.get("/discover")
async def discover_movies(
    page: int = Query(1, ge=1),
    language: Optional[str] = None,
    genre: Optional[str] = None
):
    """Discover popular movies and cache them"""
    try:
        # If it's the first page and no filters, fetch diverse content
        if page == 1 and not language and not genre:
            # Fetch movies from multiple Indian languages
            indian_languages = ['ta', 'hi', 'te', 'ml', 'kn']
            all_movies = []
            
            # Fetch popular movies from each language (4 movies per language)
            for lang in indian_languages:
                params = {
                    'page': 1,
                    'sort_by': 'popularity.desc',
                    'region': 'IN',
                    'with_original_language': lang
                }
                
                data = await fetch_tmdb_data('/discover/movie', params)
                if data and data.get('results'):
                    results = data['results'][:4]  # Take top 4 from each language
                    
                    # Process movies
                    for movie_data in results:
                        movie = await process_movie(movie_data)
                        if movie:
                            all_movies.append(movie)
            
            # Also add some English content
            params = {'page': 1, 'sort_by': 'popularity.desc', 'region': 'IN'}
            data = await fetch_tmdb_data('/discover/movie', params)
            if data and data.get('results'):
                for movie_data in data['results'][:10]:  # Take top 10 English
                    movie = await process_movie(movie_data)
                    if movie:
                        all_movies.append(movie)
            
            # Store in database
            for movie in all_movies:
                await db.movies.update_one(
                    {'tmdb_id': movie.tmdb_id},
                    {'$set': movie.model_dump()},
                    upsert=True
                )
            
            return {
                'movies': all_movies,
                'page': 1,
                'total_pages': 1
            }
        
        # Regular discover with filters
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



@api_router.post("/natural-search")
async def natural_language_search(nl_query: NaturalLanguageQuery):
    """Search movies using natural language query"""
    try:
        # Parse the natural language query
        parsed = await parse_natural_language_query(nl_query.query)
        
        # If intent is to search for songs, use YouTube
        if parsed.intent == "search_song" and parsed.keywords:
            youtube_query = f"{parsed.keywords} song"
            if parsed.languages:
                youtube_query += f" {parsed.languages[0]}"
            
            youtube_videos = search_youtube_videos(youtube_query, max_results=10)
            
            return {
                "intent": "youtube_search",
                "parsed_query": parsed.model_dump(),
                "youtube_results": [v.model_dump() for v in youtube_videos],
                "movies": []
            }
        
        # Build MongoDB query for movie search
        query = {}
        
        if parsed.languages:
            query['language'] = {'$in': parsed.languages}
        
        if parsed.genres:
            query['genres'] = {'$in': parsed.genres}
        
        if parsed.platforms:
            query['ott_platforms'] = {'$in': parsed.platforms}
        
        if parsed.min_rating:
            query['rating'] = {'$gte': parsed.min_rating}
        
        if parsed.cast_name:
            # First, try to find in database
            query['$or'] = [
                {'cast': {'$regex': parsed.cast_name, '$options': 'i'}},
                {'director': {'$regex': parsed.cast_name, '$options': 'i'}}
            ]
            
            # Determine sort order
            sort_field = 'popularity'
            if parsed.sort_by == 'rating':
                sort_field = 'rating'
            elif parsed.sort_by == 'release_date':
                sort_field = 'release_date'
        
        # Fetch movies from database first
        movies = await db.movies.find(query, {'_id': 0}).sort(sort_field if 'sort_field' in locals() else 'popularity', -1).limit(30).to_list(30)
        
        # If no movies found and cast_name is present, search TMDB
        if len(movies) == 0 and parsed.cast_name:
            # Use fuzzy search for actor
            result = await fuzzy_search_actor(parsed.cast_name)
            
            if result:
                person_id, person_name = result
                # Get movies by this person
                discover_params = {
                    'with_cast': person_id,
                    'sort_by': 'release_date.desc' if parsed.sort_by == 'release_date' else 'popularity.desc',
                    'page': 1
                }
                
                movies_data = await fetch_tmdb_data('/discover/movie', discover_params)
                
                if movies_data and movies_data.get('results'):
                    logger.info(f"Found {len(movies_data['results'])} movies for {person_name}")
                    # Process and cache these movies
                    for movie_data in movies_data['results']:
                        movie = await process_movie(movie_data)
                        if movie:
                            movies.append(movie)
                            # Cache in database
                            await db.movies.update_one(
                                {'tmdb_id': movie.tmdb_id},
                                {'$set': movie.model_dump()},
                                upsert=True
                            )
        
        if parsed.keywords and not parsed.cast_name:
            if '$or' in query:
                # Already has $or for cast, combine
                query['$and'] = [
                    {'$or': query.pop('$or')},
                    {'$or': [
                        {'title': {'$regex': parsed.keywords, '$options': 'i'}},
                        {'original_title': {'$regex': parsed.keywords, '$options': 'i'}}
                    ]}
                ]
            else:
                query['$or'] = [
                    {'title': {'$regex': parsed.keywords, '$options': 'i'}},
                    {'original_title': {'$regex': parsed.keywords, '$options': 'i'}}
                ]
            
            # If no movies found yet, fetch from database with keywords
            if len(movies) == 0:
                movies = await db.movies.find(query, {'_id': 0}).sort('popularity', -1).limit(30).to_list(30)
        
        # Determine sort order and sort movies
        # Convert Movie objects to dicts for easier handling
        movies_dicts = [m.model_dump() if hasattr(m, 'model_dump') else m for m in movies]
        
        if parsed.sort_by == 'rating':
            movies_dicts.sort(key=lambda x: x.get('rating', 0), reverse=True)
        elif parsed.sort_by == 'release_date':
            movies_dicts.sort(key=lambda x: x.get('release_date', ''), reverse=True)
        else:
            movies_dicts.sort(key=lambda x: x.get('popularity', 0), reverse=True)
        
        # If looking for songs/trailers, also get YouTube results for top movies
        youtube_results = []
        if youtube_service and movies_dicts and parsed.keywords:
            # Get trailer/song for top movie
            top_movie = movies_dicts[0]
            yt_query = f"{top_movie['title']} {parsed.keywords}"
            youtube_results = search_youtube_videos(yt_query, max_results=5)
        
        return {
            "intent": "movie_search",
            "parsed_query": parsed.model_dump(),
            "movies": movies_dicts,
            "youtube_results": [v.model_dump() for v in youtube_results]
        }
    
    except Exception as e:
        logger.error(f"Error in natural_language_search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/youtube/search")
async def search_youtube(q: str = Query(..., min_length=1), max_results: int = 10):
    """Search YouTube for videos (trailers, songs, scenes)"""
    try:
        if not youtube_service:
            raise HTTPException(status_code=503, detail="YouTube API not configured")
        
        videos = search_youtube_videos(q, max_results)
        return {"videos": [v.model_dump() for v in videos]}
    
    except Exception as e:
        logger.error(f"Error in YouTube search: {str(e)}")
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
