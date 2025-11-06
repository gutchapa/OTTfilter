import asyncio
import json
import logging
import os
import uuid
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Optional, Tuple

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Query
from googleapiclient.discovery import build
from motor.motor_asyncio import AsyncIOMotorClient
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# MongoDB connection
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# TMDB Configuration
TMDB_API_KEY = os.environ["TMDB_API_KEY"]
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

# OpenAI Configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# YouTube Configuration
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
youtube_service = build("youtube", "v3", developerKey=YOUTUBE_API_KEY) if YOUTUBE_API_KEY else None

# OMDb Configuration
OMDB_API_KEY = os.environ.get("OMDB_API_KEY", "")
OMDB_BASE_URL = "http://www.omdbapi.com/"

# Shared HTTP client with connection pooling for better performance
http_client = httpx.AsyncClient(
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=50), timeout=httpx.Timeout(30.0)
)

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


# TMDB API Helper Functions
async def fetch_tmdb_data(endpoint: str, params: dict = None):
    """Fetch data from TMDB API with connection pooling"""
    headers = {"Authorization": f"Bearer {TMDB_API_KEY}", "accept": "application/json"}

    url = f"{TMDB_BASE_URL}{endpoint}"

    try:
        response = await http_client.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"TMDB API Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"TMDB API Request Error: {str(e)}")
        return None


async def get_movie_credits(tmdb_id: int):
    """Get cast and crew for a movie"""
    data = await fetch_tmdb_data(f"/movie/{tmdb_id}/credits")
    if data:
        cast = [actor["name"] for actor in data.get("cast", [])[:10]]  # Top 10 cast
        crew = data.get("crew", [])
        director = next((person["name"] for person in crew if person["job"] == "Director"), None)
        return cast, director
    return [], None


async def get_movie_details(tmdb_id: int):
    """Get detailed movie information"""
    return await fetch_tmdb_data(f"/movie/{tmdb_id}")


async def get_imdb_rating(imdb_id: str) -> Optional[float]:
    """Get IMDb rating from OMDb API"""
    if not OMDB_API_KEY or not imdb_id:
        return None

    try:
        params = {"apikey": OMDB_API_KEY, "i": imdb_id}  # IMDb ID format: tt1234567

        response = await http_client.get(OMDB_BASE_URL, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get("Response") == "True" and data.get("imdbRating") != "N/A":
                return float(data["imdbRating"])
    except Exception as e:
        logger.error(f"Error fetching IMDb rating: {str(e)}")

    return None


async def get_movie_certification(tmdb_id: int) -> Optional[str]:
    """Get movie certification/rating (PG, PG-13, R, U/A, etc.) from TMDB"""
    try:
        data = await fetch_tmdb_data(f"/movie/{tmdb_id}/release_dates")

        if not data or "results" not in data:
            return None

        # Priority: India (IN) > United States (US) > Any available
        certifications = {}

        for country_data in data["results"]:
            country = country_data["iso_3166_1"]
            release_dates = country_data.get("release_dates", [])

            for release in release_dates:
                cert = release.get("certification", "").strip()
                if cert:
                    certifications[country] = cert
                    break

        # Return in priority order
        if "IN" in certifications:
            return certifications["IN"]
        elif "US" in certifications:
            return certifications["US"]
        elif certifications:
            # Return any available certification
            return list(certifications.values())[0]

        return None

    except Exception as e:
        logger.error(f"Error fetching certification: {str(e)}")
        return None


async def generate_content_warnings(
    title: str, genres: List[str], synopsis: str, certification: Optional[str]
) -> List[str]:
    """Use AI to generate detailed content warnings based on movie info"""
    if not openai_client or not certification:
        return []

    try:
        genre_str = ", ".join(genres) if genres else "Unknown"

        prompt = f"""Given this movie information, provide specific content warnings that explain WHY it has this rating.

Movie: {title}
Certification: {certification}
Genres: {genre_str}
Synopsis: {synopsis[:300]}

Based on the certification and genres, list 3-5 specific content warnings. Be precise and helpful for parents.

For Horror/Thriller: mention jump scares, supernatural elements, gore, violence
For Action: mention violence intensity, blood, combat scenes
For Drama: mention emotional intensity, mature themes
For Comedy: mention crude humor, language
For any rating: mention sexual content, nudity, profanity, drug use if applicable

Return ONLY a JSON array of strings, no explanations:
["warning 1", "warning 2", "warning 3"]

Example for Horror movie rated A:
["Jump scares and intense supernatural horror", "Disturbing imagery and dark atmosphere", "Violence and frightening scenes"]

Example for Action movie rated PG-13:
["Intense action violence and fight sequences", "Mild language", "Some peril and destruction"]"""

        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a content rating expert who provides detailed, helpful warnings for families.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=150,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        # Handle both array and object responses
        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            # Try common keys
            for key in ["warnings", "content_warnings", "items", "data"]:
                if key in result and isinstance(result[key], list):
                    return result[key]
            # If it's a dict with string values, convert to list
            return list(result.values()) if result else []
        return []

    except Exception as e:
        logger.error(f"Error generating content warnings: {str(e)}")
        return []

        return None

    except Exception as e:
        logger.error(f"Error fetching certification: {str(e)}")
        return None

        logger.error(f"Error fetching IMDb rating: {str(e)}")

    return None


async def get_streaming_providers(tmdb_id: int, title: str = None, year: int = None):
    """Get streaming availability for India using JustWatch (better India data than TMDB)"""
    providers = []

    # Try JustWatch first (better India OTT coverage)
    if title:
        try:
            from simplejustwatchapi.justwatch import search as justwatch_search

            # Search JustWatch for the movie in India
            # best_only=False to get ALL streaming platforms, not just "best" offer
            results = justwatch_search(title, "IN", "en", 3, False)

            logger.info(f"🔎 JustWatch search for '{title}': {len(results)} results found")

            # Find the matching movie (by year if available)
            for idx, entry in enumerate(results):
                logger.info(f"🎯 Checking result {idx + 1}: {entry.title if hasattr(entry, 'title') else 'unknown'} ({entry.release_year if hasattr(entry, 'release_year') else '?'})")
                # Match by year if provided
                if year and hasattr(entry, 'release_year'):
                    if entry.release_year != year:
                        continue
                elif results[0] != entry:
                    # If no year, just use the first result
                    break

                # Extract platform names
                if hasattr(entry, 'offers') and entry.offers:
                    logger.info(f"🔍 JustWatch raw data for '{title}': {len(entry.offers)} offers found")
                    for offer in entry.offers:
                        platform_name = offer.package.name
                        offer_type = offer.monetization_type if hasattr(offer, 'monetization_type') else 'unknown'
                        logger.info(f"   📺 Raw platform name: '{platform_name}' (type: {offer_type})")

                        # Map JustWatch names to our standard names
                        mapped = None
                        if "Netflix" in platform_name:
                            mapped = "Netflix"
                            providers.append(mapped)
                        elif "Prime" in platform_name or "Amazon" in platform_name:
                            mapped = "Prime Video"
                            providers.append(mapped)
                        elif "Hotstar" in platform_name or "Disney" in platform_name:
                            # Hotstar has been rebranded to JioHotstar after Disney-Jio merger in India
                            # All Hotstar/Disney+ Hotstar references now map to JioHotstar
                            mapped = "JioHotstar"
                            providers.append(mapped)
                        elif "Jio Cinema" in platform_name or "JioCinema" in platform_name:
                            mapped = "Jio Cinema"
                            providers.append(mapped)
                        elif "Zee5" in platform_name or "ZEE5" in platform_name:
                            mapped = "Zee5"
                            providers.append(mapped)
                        elif "Sony" in platform_name:
                            mapped = "SonyLIV"
                            providers.append(mapped)
                        elif "Voot" in platform_name:
                            mapped = "Voot"
                            providers.append(mapped)
                        elif "MX" in platform_name:
                            mapped = "MX Player"
                            providers.append(mapped)
                        elif "Aha" in platform_name:
                            mapped = "Aha"
                            providers.append(mapped)
                        elif "Sun" in platform_name:
                            mapped = "Sun NXT"
                            providers.append(mapped)
                        elif "Lionsgate" not in platform_name and "Channel" not in platform_name:
                            # Skip platform-specific channels, keep main platforms
                            logger.info(f"   ⚠️  Unmapped platform: '{platform_name}'")
                            providers.append(platform_name)

                        if mapped:
                            logger.info(f"      ✅ Mapped to: '{mapped}'")

                    # Found a match with offers, stop searching
                    if providers:
                        logger.info(f"🎬 JustWatch found {len(set(providers))} unique platforms for '{title}': {list(set(providers))}")
                        break
        except Exception as e:
            logger.warning(f"JustWatch lookup failed for '{title}': {str(e)}")

    # Fallback to TMDB if JustWatch didn't find anything
    if not providers:
        data = await fetch_tmdb_data(f"/movie/{tmdb_id}/watch/providers")
        if data and "results" in data:
            india_data = data["results"].get("IN", {})

            # Get flatrate (subscription) providers
            for provider in india_data.get("flatrate", []):
                provider_name = provider["provider_name"]
                # Map to common Indian OTT names
                if "Netflix" in provider_name:
                    providers.append("Netflix")
                elif "Prime" in provider_name or "Amazon" in provider_name:
                    providers.append("Prime Video")
                elif "Disney" in provider_name or "Hotstar" in provider_name:
                    # Hotstar rebranded to JioHotstar after Disney-Jio merger
                    providers.append("JioHotstar")
                elif "Jio" in provider_name:
                    providers.append("Jio Cinema")
                elif "Zee5" in provider_name or "ZEE5" in provider_name:
                    providers.append("Zee5")
                elif "Sony" in provider_name:
                    providers.append("SonyLIV")
                elif "Voot" in provider_name:
                    providers.append("Voot")
                elif "MX" in provider_name:
                    providers.append("MX Player")
                elif "Aha" in provider_name:
                    providers.append("Aha")
                elif "Sun" in provider_name:
                    providers.append("Sun NXT")
                else:
                    providers.append(provider_name)

    return list(set(providers))  # Remove duplicates


async def process_movie(movie_data: dict) -> Optional[Movie]:
    """Process a movie from TMDB and enrich with additional data"""
    try:
        tmdb_id = movie_data["id"]

        # Fetch basic data concurrently (except providers - needs title)
        fetch_tasks = [
            get_movie_details(tmdb_id),
            get_movie_credits(tmdb_id),
            get_movie_certification(tmdb_id),
        ]

        results = await asyncio.gather(*fetch_tasks)
        details, (cast, director), certification = results

        if not details:
            return None

        # Now fetch providers with title and year for better JustWatch matching
        title = details.get("title", "")
        release_date = details.get("release_date", "")
        year = int(release_date[:4]) if release_date and len(release_date) >= 4 else None
        providers = await get_streaming_providers(tmdb_id, title, year)

        # Fetch IMDb rating separately if available
        imdb_rating = None
        imdb_id = details.get("imdb_id")
        if imdb_id:
            imdb_rating = await get_imdb_rating(imdb_id)

        # Map language codes to names
        language_map = {
            "ta": "Tamil",
            "hi": "Hindi",
            "te": "Telugu",
            "ml": "Malayalam",
            "kn": "Kannada",
            "en": "English",
            "bn": "Bengali",
            "mr": "Marathi",
            "pa": "Punjabi",
            "gu": "Gujarati",
        }

        original_lang = details.get("original_language", "en")
        language_name = language_map.get(original_lang, original_lang.upper())

        # Use OTT platforms from TMDB as-is
        # If TMDB has data, show it. If not, leave empty (no random assignment)
        movie = Movie(
            id=str(uuid.uuid4()),
            tmdb_id=tmdb_id,
            title=details.get("title", ""),
            original_title=details.get("original_title", ""),
            genres=[genre["name"] for genre in details.get("genres", [])],
            language=language_name,
            original_language=original_lang,
            cast=cast,
            director=director,
            rating=round(details.get("vote_average", 0), 1),
            imdb_rating=round(imdb_rating, 1) if imdb_rating else None,
            certification=certification,
            content_warnings=None,  # Will be generated on-demand
            vote_count=details.get("vote_count", 0),
            release_date=details.get("release_date", ""),
            synopsis=details.get("overview", ""),
            ott_platforms=providers,
            poster_url=f"{TMDB_IMAGE_BASE}{details['poster_path']}" if details.get("poster_path") else None,
            backdrop_url=f"{TMDB_IMAGE_BASE}{details['backdrop_path']}" if details.get("backdrop_path") else None,
            runtime=details.get("runtime"),
            popularity=details.get("popularity", 0),
        )

        # Content warnings are now generated on-demand (not during initial fetch)
        # This makes search 10x faster - warnings generated only when user clicks "Why A?"
        movie.content_warnings = None

        return movie
    except Exception as e:
        logger.error(f"Error processing movie {movie_data.get('id')}: {str(e)}")
        return None


# AI-powered Natural Language Processing
async def parse_natural_language_query(query: str) -> ParsedQuery:
    """Parse natural language query using OpenAI to extract filters"""
    if not openai_client:
        # Fallback: basic parsing without AI
        import re
        query_lower = query.lower()

        # Extract year (2020-2099)
        year_match = re.search(r'\b(20\d{2})\b', query)
        release_year = int(year_match.group(1)) if year_match else None

        # Extract common languages
        languages = []
        if any(word in query_lower for word in ['tamil', 'தமிழ்']):
            languages.append('Tamil')
        if any(word in query_lower for word in ['hindi', 'हिंदी']):
            languages.append('Hindi')
        if any(word in query_lower for word in ['telugu', 'తెలుగు']):
            languages.append('Telugu')
        if any(word in query_lower for word in ['malayalam', 'മലയാളം']):
            languages.append('Malayalam')
        if any(word in query_lower for word in ['kannada', 'ಕನ್ನಡ']):
            languages.append('Kannada')

        # Extract "top" or "best" queries
        min_rating = 7.0 if any(word in query_lower for word in ['top', 'best', 'greatest']) else None

        # Sort by
        sort_by = "popularity"
        if any(word in query_lower for word in ['latest', 'recent', 'new']):
            sort_by = "release_date"
        elif any(word in query_lower for word in ['top', 'best', 'highest']):
            sort_by = "rating"

        # Special case: Oscar/Awards - search for highly rated movies
        if any(word in query_lower for word in ['oscar', 'academy award', 'award']):
            # Oscar ceremonies honor films from the PREVIOUS year
            # e.g., "Oscar 2025" ceremony honors 2024 films
            oscar_year = (release_year - 1) if release_year else None
            return ParsedQuery(
                min_rating=6.5,  # Lowered to 6.5 to get more results
                sort_by="rating",
                release_year=oscar_year,
                keywords=None,  # Don't search by title for Oscar queries
                languages=languages if languages else None,
                intent="filter"  # Use filter intent, not search_movie
            )

        # Detect actor/cast searches: "actor name movies" or "actor name films"
        # BUT only if query doesn't start with filter words like "top", "best", etc.
        cast_name = None
        filter_prefixes = ['top', 'best', 'latest', 'new', 'recent', 'highest', 'greatest']
        has_filter_prefix = any(query_lower.startswith(prefix) for prefix in filter_prefixes)

        actor_pattern = r'^(.+?)\s+(movies?|films?)$'
        actor_match = re.search(actor_pattern, query_lower)

        if actor_match and not has_filter_prefix:
            # Extract actor name (everything before "movies"/"films")
            cast_name = actor_match.group(1).strip()
            # Remove filter words from actor name
            for word in filter_prefixes:
                cast_name = re.sub(r'\b' + word + r'\b', '', cast_name, flags=re.IGNORECASE).strip()
            # Remove year from actor name
            if release_year:
                cast_name = cast_name.replace(str(release_year), '').strip()
            # Remove language names from actor name
            for lang in ['tamil', 'hindi', 'telugu', 'malayalam', 'kannada', 'english']:
                cast_name = cast_name.replace(lang, '').strip()
            cast_name = ' '.join(cast_name.split())  # Clean whitespace

            # Make sure we actually have a name (not just numbers or empty)
            if cast_name and not cast_name.isdigit():
                # This is an actor search - return with cast_name
                return ParsedQuery(
                    cast_name=cast_name,
                    languages=languages if languages else None,
                    release_year=release_year,
                    min_rating=min_rating,
                    sort_by=sort_by,
                    intent="search_movie"
                )

        # Clean up keywords: remove year, numbers, and filter words
        keywords_clean = query
        filter_words = ['top', 'best', 'greatest', 'latest', 'recent', 'new', 'movies', 'movie', 'film', 'films']

        # Remove year if present
        if release_year:
            keywords_clean = keywords_clean.replace(str(release_year), '')

        # Remove filter words and numbers
        for word in filter_words:
            keywords_clean = re.sub(r'\b' + word + r'\b', '', keywords_clean, flags=re.IGNORECASE)

        # Remove standalone numbers (like "10" in "top 10")
        keywords_clean = re.sub(r'\b\d+\b', '', keywords_clean)

        # Clean up extra whitespace
        keywords_clean = ' '.join(keywords_clean.split()).strip()

        # Return basic parsed query
        return ParsedQuery(
            keywords=keywords_clean if keywords_clean else None,
            languages=languages if languages else None,
            release_year=release_year,
            min_rating=min_rating,
            sort_by=sort_by,
            intent="search_movie" if keywords_clean else "filter"
        )

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

ACTOR NAME DETECTION:
- If query contains partial names like "lakshmi", "vijay", "fahadh" followed by "movies", treat it as cast_name
- Single names like "rajini", "kamal", "dhanush" are often actor names, not keywords
- Examples: "lakshmi movies" -> cast_name: "lakshmi"
- Examples: "vijay tamil" -> cast_name: "vijay", languages: ["Tamil"]

THEME/DESCRIPTION UNDERSTANDING (IMPORTANT):
- If user describes movie themes/topics, map to appropriate genres, NOT keywords
- "brilliant mind", "genius", "intellectual" -> genres: ["Drama", "Thriller"] (NOT keywords)
- "mind-bending", "psychological" -> genres: ["Thriller", "Science Fiction"]
- "emotional", "heart-touching" -> genres: ["Drama", "Romance"]
- "funny", "comedy" -> genres: ["Comedy"]
- "scary", "horror" -> genres: ["Horror"]
- "inspiring", "biographical" -> genres: ["Drama"]
- ONLY use keywords for ACTUAL song names or specific movie titles, not descriptions

MOVIE TITLE SEARCH (CRITICAL):
- If user types a single word or phrase that could be a movie name, put it in keywords
- Examples: "conjuring" -> keywords: "conjuring", intent: "search_movie"
- Examples: "inception" -> keywords: "inception", intent: "search_movie"
- Examples: "dark knight" -> keywords: "dark knight", intent: "search_movie"
- Do NOT confuse movie titles with themes/genres

IMPORTANT: Users may have typos in actor names. Keep the name AS-IS in cast_name field.

COMEDY SCENES & CLIPS (IMPORTANT):
- If user searches for "comedy scenes", "best scenes", "funny moments", "clips" etc., treat as YouTube search
- Examples: "vadivelu best comedy scenes" -> intent: "search_youtube", keywords: "vadivelu comedy scenes"
- Examples: "salman khan action scenes" -> intent: "search_youtube", keywords: "salman khan action scenes"

OSCAR/AWARDS SEARCHES (CRITICAL):
- If query mentions "oscar", "academy award", or "award", this is a filter for highly-rated movies
- DO NOT put "oscar" in keywords (it will search for movies with "Oscar" in title)
- Oscar ceremonies honor films from the PREVIOUS year (e.g., Oscar 2025 = 2024 films)
- Set min_rating: 6.5, intent: "filter", and release_year to year-1 if year mentioned
- Examples: "Oscar 2025" -> {"min_rating": 6.5, "release_year": 2024, "sort_by": "rating", "intent": "filter"}
- Examples: "oscar winning movies" -> {"min_rating": 6.5, "sort_by": "rating", "intent": "filter"}

YEAR EXTRACTION (CRITICAL):
- ALWAYS extract 4-digit years (2020-2099) from the query into release_year
- Examples: "top 10 2024 tamil movies" -> extract release_year: 2024
- Examples: "best 2023 hindi films" -> extract release_year: 2023
- Examples: "2022 action movies" -> extract release_year: 2022
- DO NOT include the year in keywords - put it in release_year field
- For Oscar queries, use year-1 (e.g., Oscar 2025 -> release_year: 2024)

Extract and return JSON with:
{
  "languages": ["Tamil"],  // if language mentioned
  "genres": ["Drama", "Thriller"],  // if genre OR theme/description mentioned
  "platforms": ["Jio Cinema"],  // if ANY platform mentioned (check variations above)
  "min_rating": 7.0,  // if rating mentioned, or 7.0 for "top/best", or 6.5 for Oscar/Awards
  "cast_name": "exact name from query",  // actor/director name EXACTLY as typed (even partial names)
  "keywords": "movie title",  // for song names, specific MOVIE TITLES, OR scene/clip searches
  "release_year": 2024,  // if year mentioned (use year-1 for Oscar searches)
  "sort_by": "release_date",  // "rating" if "highest/best/top", "release_date" if "latest/recent/new", else "popularity"
  "intent": "search_movie"  // "search_song" for songs, "search_youtube" for scenes/clips, "filter" for Oscar/Awards, "search_movie" for titles

}

Examples:
- "conjuring" -> {"keywords": "conjuring", "intent": "search_movie"}
- "inception" -> {"keywords": "inception", "intent": "search_movie"}
- "dark knight" -> {"keywords": "dark knight", "intent": "search_movie"}
- "vadivelu best comedy scenes" -> {"keywords": "vadivelu comedy scenes", "intent": "search_youtube", "cast_name": "vadivelu"}
- "salman khan action clips" -> {"keywords": "salman khan action scenes", "intent": "search_youtube", "cast_name": "salman khan"}
- "top 10 brilliant mind kind of movies" -> {"genres": ["Drama", "Thriller"], "min_rating": 7.0, "sort_by": "rating"}
- "psychological thriller movies" -> {"genres": ["Thriller"]}
- "lakshmi movies malayalam" -> {"cast_name": "lakshmi", "languages": ["Malayalam"]}
- "vijay movies" -> {"cast_name": "vijay"}
- "jio star movies" -> {"platforms": ["Jio Cinema"]}
- "latest tamil movies on netflix" -> {"languages": ["Tamil"], "platforms": ["Netflix"], "sort_by": "release_date"}
- "fahid fasil latest movie" -> {"cast_name": "fahid fasil", "sort_by": "release_date"}
- "tamil movie with sollamale song" -> {"languages": ["Tamil"], "keywords": "sollamale", "intent": "search_song"}
- "prime video action movies" -> {"platforms": ["Prime Video"], "genres": ["Action"]}
- "inspiring biographical movies" -> {"genres": ["Drama"], "min_rating": 7.0}
- "Oscar 2025" -> {"min_rating": 6.5, "release_year": 2024, "sort_by": "rating", "intent": "filter"}
- "oscar winning tamil movies" -> {"min_rating": 6.5, "languages": ["Tamil"], "sort_by": "rating", "intent": "filter"}
- "top 10 2024 tamil movies" -> {"languages": ["Tamil"], "min_rating": 7.0, "release_year": 2024, "sort_by": "rating", "intent": "filter"}
- "best 2023 hindi films" -> {"languages": ["Hindi"], "min_rating": 7.0, "release_year": 2023, "sort_by": "rating", "intent": "filter"}
- "2022 action movies" -> {"genres": ["Action"], "release_year": 2022, "intent": "filter"}

Return only valid JSON, no explanations."""

        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Parse this query: {query}"},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        parsed_data = json.loads(response.choices[0].message.content)

        # DEBUG LOGGING: Log what OpenAI returned
        logger.info(f"🔍 QUERY: '{query}'")
        logger.info(f"🤖 OPENAI PARSED: {json.dumps(parsed_data, indent=2)}")

        parsed_query = ParsedQuery(**parsed_data)
        logger.info(f"📋 FINAL PARSED: {parsed_query.model_dump()}")

        return parsed_query

    except Exception as e:
        logger.error(f"Error parsing natural language query: {str(e)}")
        return ParsedQuery(keywords=query, intent="search_movie")


# YouTube Integration
def search_youtube_videos(query: str, max_results: int = 5) -> List[YouTubeVideo]:
    """Search YouTube for videos"""
    if not youtube_service:
        return []

    try:
        request = youtube_service.search().list(
            part="snippet", q=query, type="video", maxResults=max_results, regionCode="IN"
        )
        response = request.execute()

        videos = []
        for item in response.get("items", []):
            video = YouTubeVideo(
                video_id=item["id"]["videoId"],
                title=item["snippet"]["title"],
                thumbnail_url=item["snippet"]["thumbnails"]["medium"]["url"],
                channel_title=item["snippet"]["channelTitle"],
                url=f"https://www.youtube.com/watch?v={item['id']['videoId']}",
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
    search_params = {"query": name, "page": 1}
    person_data = await fetch_tmdb_data("/search/person", search_params)

    if person_data and person_data.get("results"):
        # Check each result and find best fuzzy match
        best_match = None
        best_score = 0

        for person in person_data["results"][:5]:
            person_name = person["name"]
            score = fuzzy_match_score(name, person_name)

            # Test if this person has movies
            test_params = {"with_cast": person["id"], "page": 1}
            test_data = await fetch_tmdb_data("/discover/movie", test_params)

            if test_data and test_data.get("results") and len(test_data["results"]) > 0:
                if score > best_score:
                    best_score = score
                    best_match = (person["id"], person["name"])

        if best_match:
            logger.info(f"Fuzzy matched '{name}' to '{best_match[1]}' (score: {best_score:.2f})")
            return best_match

    # Try variations
    name_parts = name.lower().split()
    if len(name_parts) >= 2:
        # Try with common spelling variations
        variations = [
            " ".join(name_parts),  # Original
            " ".join(name_parts[::-1]),  # Reversed
            name_parts[0] + " " + name_parts[-1],  # First and last only
        ]

        for variant in variations[1:]:  # Skip first as already tried
            search_params = {"query": variant, "page": 1}
            person_data = await fetch_tmdb_data("/search/person", search_params)

            if person_data and person_data.get("results"):
                for person in person_data["results"][:3]:
                    # Quick test
                    test_params = {"with_cast": person["id"], "page": 1}
                    test_data = await fetch_tmdb_data("/discover/movie", test_params)

                    if test_data and test_data.get("results") and len(test_data["results"]) > 0:
                        logger.info(f"Variation matched '{name}' to '{person['name']}'")
                        return (person["id"], person["name"])

    return None


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
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=50,
        )

        corrected = response.choices[0].message.content.strip()
        if corrected and corrected.lower() != misspelled_name.lower():
            logger.info(f"Name correction: '{misspelled_name}' → '{corrected}'")
            return corrected
        return misspelled_name

    except Exception as e:
        logger.error(f"Error correcting actor name: {str(e)}")
        return misspelled_name


@api_router.get("/discover")
async def discover_movies(page: int = Query(1, ge=1), language: Optional[str] = None, genre: Optional[str] = None):
    """Discover latest movies from all OTT platforms"""
    try:
        # FAST PATH: Return cached latest movies from database first
        # Filter to show only movies from last 2 years
        from datetime import datetime
        current_year = datetime.now().year
        year_filter = {"release_date": {"$regex": f"^(202[2-9]|20[3-9][0-9])"}}  # 2022 onwards

        cached_movies = (
            await db.movies.find(year_filter, {"_id": 0})
            .sort("release_date", -1)  # Sort by latest first
            .limit(50)
            .to_list(50)
        )

        if len(cached_movies) > 10:
            # Transform cached platform names (Disney+ Hotstar -> JioHotstar)
            for movie in cached_movies:
                if "ott_platforms" in movie and movie["ott_platforms"]:
                    movie["ott_platforms"] = [
                        "JioHotstar" if platform == "Disney+ Hotstar" else platform
                        for platform in movie["ott_platforms"]
                    ]

            # We have enough cached movies, return them immediately
            return {"movies": cached_movies, "page": page, "total_pages": 1}

        # SLOW PATH: Only fetch from TMDB if we don't have enough cached movies
        # This runs in background on first load
        logger.info("Cache miss - fetching latest movies from TMDB")

        # Fetch latest movies (released in last 2 years)
        params = {
            "page": 1,
            "sort_by": "release_date.desc",  # Changed from popularity.desc
            "region": "IN",
            "primary_release_date.gte": f"{current_year - 2}-01-01",  # Last 2 years
        }
        data = await fetch_tmdb_data("/discover/movie", params)

        if not data:
            return {"movies": cached_movies, "page": 1, "total_pages": 1}

        results = data.get("results", [])[:20]  # Limit to 20 to avoid timeout

        # Process movies concurrently in larger batches for better performance
        movies = []
        batch_size = 10  # Increased from 5 to 10 for faster processing
        for i in range(0, len(results), batch_size):
            batch = results[i : i + batch_size]
            batch_movies = await asyncio.gather(
                *[process_movie(movie_data) for movie_data in batch],
                return_exceptions=True,  # Don't fail entire batch if one movie fails
            )
            # Filter out None and exceptions
            movies.extend([m for m in batch_movies if m is not None and isinstance(m, Movie)])

        # Batch insert into database for better performance
        if movies:
            from pymongo import UpdateOne

            bulk_operations = [
                UpdateOne({"tmdb_id": movie.tmdb_id}, {"$set": movie.model_dump()}, upsert=True) for movie in movies
            ]
            if bulk_operations:
                await db.movies.bulk_write(bulk_operations)

        return {"movies": movies, "page": page, "total_pages": data.get("total_pages", 1)}

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
            query["genres"] = {"$in": filters.genres}

        if filters.languages:
            query["language"] = {"$in": filters.languages}

        if filters.platforms:
            query["ott_platforms"] = {"$in": filters.platforms}

        if filters.min_rating:
            query["rating"] = {"$gte": filters.min_rating}

        if filters.search_query:
            query["$or"] = [
                {"title": {"$regex": filters.search_query, "$options": "i"}},
                {"original_title": {"$regex": filters.search_query, "$options": "i"}},
            ]

        if filters.cast_name:
            query["cast"] = {"$regex": filters.cast_name, "$options": "i"}

        # Fetch from database
        movies = await db.movies.find(query, {"_id": 0}).sort("popularity", -1).limit(50).to_list(50)

        # Transform cached platform names (Disney+ Hotstar -> JioHotstar)
        for movie in movies:
            if "ott_platforms" in movie and movie["ott_platforms"]:
                movie["ott_platforms"] = [
                    "JioHotstar" if platform == "Disney+ Hotstar" else platform
                    for platform in movie["ott_platforms"]
                ]

        return movies

    except Exception as e:
        logger.error(f"Error in filter_movies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/movies/{movie_id}", response_model=Movie)
async def get_movie(movie_id: str):
    """Get a specific movie by ID"""
    movie = await db.movies.find_one({"id": movie_id}, {"_id": 0})

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    return movie


@api_router.get("/movies/{movie_id}/content-warnings")
async def get_content_warnings(movie_id: str):
    """Generate content warnings for a movie on-demand (only when user clicks 'Why A?')"""
    movie = await db.movies.find_one({"id": movie_id}, {"_id": 0})

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    # If already generated, return cached
    if movie.get("content_warnings"):
        return {"warnings": movie["content_warnings"]}

    # Generate warnings on-demand
    certification = movie.get("certification")
    if not certification or not openai_client:
        return {"warnings": []}

    try:
        warnings = await generate_content_warnings(
            movie["title"],
            movie.get("genres", []),
            movie.get("synopsis", ""),
            certification
        )

        # Cache the warnings in database for future requests
        if warnings:
            await db.movies.update_one(
                {"id": movie_id},
                {"$set": {"content_warnings": warnings}}
            )

        return {"warnings": warnings}
    except Exception as e:
        logger.error(f"Error generating content warnings: {str(e)}")
        return {"warnings": []}


@api_router.get("/filter-options", response_model=FilterOptions)
async def get_filter_options():
    """Get all available filter options"""
    try:
        # Get unique genres
        genres = await db.movies.distinct("genres")
        genres = sorted([g for g in genres if g])

        # Get unique languages
        languages = await db.movies.distinct("language")
        languages = sorted([lang for lang in languages if lang])

        # Get unique platforms
        platforms = await db.movies.distinct("ott_platforms")
        platforms = sorted([p for p in platforms if p])

        return FilterOptions(genres=genres, languages=languages, platforms=platforms)
    except Exception as e:
        logger.error(f"Error in get_filter_options: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/search")
async def search_movies(q: str = Query(..., min_length=1)):
    """Search movies by title or cast"""
    try:
        query = {
            "$or": [
                {"title": {"$regex": q, "$options": "i"}},
                {"original_title": {"$regex": q, "$options": "i"}},
                {"cast": {"$regex": q, "$options": "i"}},
                {"director": {"$regex": q, "$options": "i"}},
            ]
        }

        movies = await db.movies.find(query, {"_id": 0}).sort("popularity", -1).limit(20).to_list(20)

        # Transform cached platform names (Disney+ Hotstar -> JioHotstar)
        for movie in movies:
            if "ott_platforms" in movie and movie["ott_platforms"]:
                movie["ott_platforms"] = [
                    "JioHotstar" if platform == "Disney+ Hotstar" else platform
                    for platform in movie["ott_platforms"]
                ]

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

        # If intent is YouTube search (songs, comedy scenes, clips), use YouTube
        if parsed.intent in ["search_song", "search_youtube"] and parsed.keywords:
            youtube_query = parsed.keywords
            if parsed.intent == "search_song":
                youtube_query = f"{parsed.keywords} song"

            if parsed.languages:
                youtube_query += f" {parsed.languages[0]}"

            youtube_videos = search_youtube_videos(youtube_query, max_results=15)

            # Also search for movies if cast_name present
            movies = []
            if parsed.cast_name:
                query = {
                    "$or": [
                        {"cast": {"$regex": parsed.cast_name, "$options": "i"}},
                        {"director": {"$regex": parsed.cast_name, "$options": "i"}},
                    ]
                }
                movies = await db.movies.find(query, {"_id": 0}).sort("popularity", -1).limit(10).to_list(10)

            return {
                "intent": "youtube_search",
                "parsed_query": parsed.model_dump(),
                "youtube_results": [v.model_dump() for v in youtube_videos],
                "movies": movies,
            }

        # Build MongoDB query for movie search
        query = {}

        if parsed.languages:
            query["language"] = {"$in": parsed.languages}

        if parsed.genres:
            query["genres"] = {"$in": parsed.genres}

        # Filter by release year if specified
        if parsed.release_year:
            query["release_date"] = {"$regex": f"^{parsed.release_year}"}

        if parsed.platforms:
            query["ott_platforms"] = {"$in": parsed.platforms}

        if parsed.min_rating:
            query["rating"] = {"$gte": parsed.min_rating}

        # CRITICAL FIX: If keywords present (movie title search), search by title
        if parsed.keywords and parsed.intent == "search_movie":
            query["$or"] = [
                {"title": {"$regex": parsed.keywords, "$options": "i"}},
                {"original_title": {"$regex": parsed.keywords, "$options": "i"}},
            ]

        if parsed.cast_name:
            # If we already have $or for title search, combine with AND
            cast_or = [
                {"cast": {"$regex": parsed.cast_name, "$options": "i"}},
                {"director": {"$regex": parsed.cast_name, "$options": "i"}},
            ]

            if "$or" in query:
                # Combine title search with cast search using $and
                query = {"$and": [{"$or": query.pop("$or")}, {"$or": cast_or}], **query}  # Add remaining filters
            else:
                query["$or"] = cast_or

            # Determine sort order
            sort_field = "popularity"
            if parsed.sort_by == "rating":
                sort_field = "rating"
            elif parsed.sort_by == "release_date":
                sort_field = "release_date"

        # DEBUG LOGGING: Log MongoDB query
        logger.info(f"🗄️  MONGODB QUERY: {json.dumps(query, default=str)}")

        # Fetch movies from database first
        # Increase limit if filtering by platform (they should have many movies)
        limit = 100 if parsed.platforms else 50
        movies = (
            await db.movies.find(query, {"_id": 0})
            .sort(sort_field if "sort_field" in locals() else "popularity", -1)
            .limit(limit)
            .to_list(limit)
        )

        logger.info(f"📊 MONGODB RESULTS: {len(movies)} movies found")

        # FIX 2: If we have < 10 results from cache, fetch fresh from TMDB
        # For actor searches, skip this and use actor-specific TMDB search below
        if len(movies) < 10 and not parsed.cast_name:
            logger.info(f"⚠️  Only {len(movies)} cached results, fetching from TMDB...")

            # If searching by movie title (keywords), use TMDB search, not discover
            if parsed.keywords and parsed.intent == "search_movie":
                search_params = {"query": parsed.keywords, "page": 1}
                if parsed.languages:
                    lang_code_map = {
                        "Tamil": "ta",
                        "Hindi": "hi",
                        "Telugu": "te",
                        "Malayalam": "ml",
                        "Kannada": "kn",
                        "English": "en",
                    }
                    lang_code = lang_code_map.get(parsed.languages[0], "en")
                    search_params["language"] = lang_code

                # Add year filter
                if parsed.release_year:
                    search_params["year"] = parsed.release_year

                logger.info(f"🎬 TMDB SEARCH: /search/movie with {search_params}")
                tmdb_data = await fetch_tmdb_data("/search/movie", search_params)
            else:
                # Build TMDB discover params for genre/language/platform filters
                tmdb_params = {
                    "page": 1,
                    "sort_by": "popularity.desc" if parsed.sort_by == "popularity" else f"{parsed.sort_by}.desc",
                    "region": "IN",
                }

                if parsed.languages:
                    lang_code_map = {
                        "Tamil": "ta",
                        "Hindi": "hi",
                        "Telugu": "te",
                        "Malayalam": "ml",
                        "Kannada": "kn",
                        "English": "en",
                    }
                    lang_code = lang_code_map.get(parsed.languages[0], "en")
                    tmdb_params["with_original_language"] = lang_code

                if parsed.genres:
                    # Map genre names to TMDB IDs
                    genre_map = {
                        "Action": 28,
                        "Adventure": 12,
                        "Animation": 16,
                        "Comedy": 35,
                        "Crime": 80,
                        "Drama": 18,
                        "Fantasy": 14,
                        "Horror": 27,
                        "Music": 10402,
                        "Romance": 10749,
                        "Science Fiction": 878,
                        "Thriller": 53,
                        "War": 10752,
                    }
                    genre_ids = [str(genre_map.get(g)) for g in parsed.genres if g in genre_map]
                    if genre_ids:
                        tmdb_params["with_genres"] = ",".join(genre_ids)

                if parsed.min_rating:
                    tmdb_params["vote_average.gte"] = parsed.min_rating
                    # FIX: Remove vote_count requirement for regional language queries
                    # Tamil/Telugu/Malayalam movies rely on word-of-mouth, not TMDB ratings
                    regional_languages = ["Tamil", "Telugu", "Malayalam", "Kannada", "Bengali", "Marathi", "Punjabi"]
                    if not parsed.languages or not any(lang in regional_languages for lang in parsed.languages):
                        tmdb_params["vote_count.gte"] = 50  # Only for non-regional queries
                    else:
                        logger.info(f"🎬 Skipping vote_count requirement for regional language: {parsed.languages}")

                # Add year filter
                if parsed.release_year:
                    tmdb_params["primary_release_year"] = parsed.release_year

                logger.info(f"🎬 TMDB DISCOVER: /discover/movie with {tmdb_params}")
                # Fetch from TMDB
                tmdb_data = await fetch_tmdb_data("/discover/movie", tmdb_params)

            if tmdb_data and tmdb_data.get("results"):
                logger.info(f"✅ TMDB returned {len(tmdb_data['results'])} movies")
                # Process up to 20 movies
                batch_size = 10
                results = tmdb_data["results"][:20]

                for i in range(0, len(results), batch_size):
                    batch = results[i : i + batch_size]
                    batch_movies = await asyncio.gather(
                        *[process_movie(movie_data) for movie_data in batch], return_exceptions=True
                    )
                    for m in batch_movies:
                        if m is not None and isinstance(m, Movie):
                            movies.append(m)
                            # Cache it
                            await db.movies.update_one({"tmdb_id": m.tmdb_id}, {"$set": m.model_dump()}, upsert=True)

        # CRITICAL FIX: If searching by cast_name, filter to only movies where actor is in top 5 (leads)
        # And prioritize movies where they're in top 2 (main leads)
        if parsed.cast_name and len(movies) > 0:
            lead_movies = []  # Movies where actor is in top 2
            supporting_movies = []  # Movies where actor is in top 3-5

            for movie in movies:
                cast = movie.get("cast", [])
                director = (movie.get("director", "") or "").lower()
                name_lower = parsed.cast_name.lower()

                # Check if director
                if name_lower in director:
                    lead_movies.append(movie)
                    continue

                # Find position in cast
                for idx, actor in enumerate(cast[:5]):
                    if name_lower in actor.lower():
                        if idx < 2:  # Top 2 = main leads
                            lead_movies.append(movie)
                        else:  # Position 3-5 = supporting
                            supporting_movies.append(movie)
                        break

            # Prioritize lead movies, then supporting
            movies = lead_movies + supporting_movies
            logger.info(
                f"Filtered: {len(lead_movies)} lead roles, {len(supporting_movies)} supporting roles for '{parsed.cast_name}'"
            )

        # FIX 2: If < 10 movies found for actor, search TMDB (changed from == 0 to < 10)
        if len(movies) < 10 and parsed.cast_name:
            logger.info(f"🎭 Only {len(movies)} movies found for actor '{parsed.cast_name}', trying TMDB actor search...")
            # Use LLM to correct the name (async)
            corrected_name = await correct_actor_name(parsed.cast_name)
            logger.info(f"🎭 Corrected name: '{corrected_name}'")

            # Use the corrected name for TMDB search
            result = await fuzzy_search_actor(corrected_name)

            if result:
                person_id, person_name = result
                # Get movies by this person
                discover_params = {
                    "with_cast": person_id,
                    "sort_by": "release_date.desc" if parsed.sort_by == "release_date" else "popularity.desc",
                    "page": 1,
                }

                # FIX: Apply year filter for actor searches
                if parsed.release_year:
                    discover_params["primary_release_year"] = parsed.release_year
                    logger.info(f"🎭 Filtering actor movies by year: {parsed.release_year}")

                movies_data = await fetch_tmdb_data("/discover/movie", discover_params)

                if movies_data and movies_data.get("results"):
                    logger.info(f"Found {len(movies_data['results'])} movies for {person_name}")
                    # Process and cache these movies
                    for movie_data in movies_data["results"]:
                        movie = await process_movie(movie_data)
                        if movie:
                            movies.append(movie)
                            # Cache in database
                            await db.movies.update_one(
                                {"tmdb_id": movie.tmdb_id}, {"$set": movie.model_dump()}, upsert=True
                            )

        if parsed.keywords and not parsed.cast_name:
            if "$or" in query:
                # Already has $or for cast, combine
                query["$and"] = [
                    {"$or": query.pop("$or")},
                    {
                        "$or": [
                            {"title": {"$regex": parsed.keywords, "$options": "i"}},
                            {"original_title": {"$regex": parsed.keywords, "$options": "i"}},
                        ]
                    },
                ]
            else:
                query["$or"] = [
                    {"title": {"$regex": parsed.keywords, "$options": "i"}},
                    {"original_title": {"$regex": parsed.keywords, "$options": "i"}},
                ]

            # If no movies found yet, fetch from database with keywords
            if len(movies) == 0:
                movies = await db.movies.find(query, {"_id": 0}).sort("popularity", -1).limit(30).to_list(30)

        # Determine sort order and sort movies
        # Convert Movie objects to dicts for easier handling and remove duplicates
        seen_tmdb_ids = set()
        unique_movies = []

        for m in movies:
            movie_dict = m.model_dump() if hasattr(m, "model_dump") else m
            tmdb_id = movie_dict.get("tmdb_id")

            if tmdb_id not in seen_tmdb_ids:
                seen_tmdb_ids.add(tmdb_id)
                unique_movies.append(movie_dict)

        movies_dicts = unique_movies

        if parsed.sort_by == "rating":
            movies_dicts.sort(key=lambda x: x.get("rating", 0), reverse=True)
        elif parsed.sort_by == "release_date":
            movies_dicts.sort(key=lambda x: x.get("release_date", ""), reverse=True)
        else:
            movies_dicts.sort(key=lambda x: x.get("popularity", 0), reverse=True)

        # FIX 1: For Oscar queries, exclude compilation films (e.g., "2025 Oscar Nominated Short Films")
        # These are not actual Oscar winners, just collections of nominated shorts
        query_lower = nl_query.query.lower()
        if any(word in query_lower for word in ['oscar', 'academy award', 'award']):
            original_count = len(movies_dicts)
            movies_dicts = [
                m for m in movies_dicts
                if not any(phrase in m.get('title', '').lower() for phrase in [
                    'oscar nominated short films',
                    'academy awards short films',
                    'a night at the oscars',
                    'oscar shorts'
                ])
            ]
            filtered_count = original_count - len(movies_dicts)
            if filtered_count > 0:
                logger.info(f"🎬 Filtered out {filtered_count} Oscar compilation films")

        # Transform cached platform names for rebranded platforms
        # Disney+ Hotstar -> JioHotstar (post-merger)
        for movie in movies_dicts:
            if "ott_platforms" in movie and movie["ott_platforms"]:
                movie["ott_platforms"] = [
                    "JioHotstar" if platform == "Disney+ Hotstar" else platform
                    for platform in movie["ott_platforms"]
                ]

        # If looking for songs/trailers ONLY, get YouTube results (not for theme descriptions)
        youtube_results = []
        if youtube_service and movies_dicts and parsed.keywords and parsed.intent == "search_song":
            # Only search YouTube if explicitly looking for songs
            top_movie = movies_dicts[0]
            yt_query = f"{top_movie['title']} {parsed.keywords}"
            youtube_results = search_youtube_videos(yt_query, max_results=5)

        return {
            "intent": "movie_search",
            "parsed_query": parsed.model_dump(),
            "movies": movies_dicts,
            "youtube_results": [v.model_dump() for v in youtube_results],
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
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
    await http_client.aclose()  # Close HTTP connection pool
