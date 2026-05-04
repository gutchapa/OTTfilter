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

# Global OTT provider name mappings
PROVIDER_MAPPINGS = {
    'Netflix': 'Netflix',
    'Prime Video': 'Prime Video',
    'Amazon Prime Video': 'Prime Video',
    'Amazon': 'Prime Video',
    'Disney Plus': 'Disney+',
    'Disney+': 'Disney+',
    'Hotstar': 'JioHotstar',
    'Disney+ Hotstar': 'JioHotstar',
    'JioHotstar': 'JioHotstar',
    'Jio Cinema': 'Jio Cinema',
    'Zee5': 'Zee5',
    'ZEE5': 'Zee5',
    'Sony Liv': 'SonyLIV',
    'SonyLIV': 'SonyLIV',
    'Sony': 'SonyLIV',
    'Voot': 'Voot',
    'MX Player': 'MX Player',
    'Aha': 'Aha',
    'Sun NXT': 'Sun NXT',
    'Sun Nxt': 'Sun NXT',
    'VI movies and tv': 'VI Movies',
    'VI Movies': 'VI Movies',
    'Amazon MX Player': 'MX Player',
    'ManoramaMAX': 'ManoramaMAX',
    'Hulu': 'Hulu',
    'HBO Max': 'Max',
    'Max': 'Max',
    'Apple TV Plus': 'Apple TV+',
    'Apple TV': 'Apple TV',
    'Paramount Plus': 'Paramount+',
    'Peacock': 'Peacock',
    'Crunchyroll': 'Crunchyroll',
    'MUBI': 'MUBI',
    'Criterion Channel': 'Criterion Channel',
    'Tubi': 'Tubi',
    'Pluto TV': 'Pluto TV',
    'Rakuten Viki': 'Viki',
    'Viki': 'Viki',
    'YouTube': 'YouTube Movies',
    'YouTube Movies': 'YouTube Movies',
    'Google Play': 'Google Play Movies',
    'Google Play Movies': 'Google Play Movies',
    'iTunes': 'Apple TV',
    'Apple iTunes': 'Apple TV',
}

def _map_provider(provider_name: str) -> str:
    """Map TMDB/JustWatch provider name to standardized platform name (case-insensitive)"""
    name_lower = provider_name.lower()
    # Sort by key length descending so "Amazon Prime Video" matches before "Amazon"
    for key, value in sorted(PROVIDER_MAPPINGS.items(), key=lambda x: -len(x[0])):
        if key.lower() in name_lower:
            return value
    return None

async def get_streaming_providers(tmdb_id: int, title: str = None, year: int = None):
    """Get streaming availability - India first, then global"""
    data = await fetch_tmdb_data(f"/movie/{tmdb_id}/watch/providers")
    
    # Track: India streaming, India rental, global by provider->countries
    in_streaming = set()
    in_rental = set()
    global_streaming = {}  # provider_name -> [countries]

    if data and 'results' in data:
        for country_code, country_data in data['results'].items():
            is_india = (country_code == 'IN')
            
            # Collect all provider types
            all_providers = []
            all_providers.extend([(p, 'stream') for p in country_data.get('flatrate', [])])
            all_providers.extend([(p, 'stream') for p in country_data.get('free', [])])
            all_providers.extend([(p, 'stream') for p in country_data.get('ads', [])])
            all_providers.extend([(p, 'rent') for p in country_data.get('rent', [])])
            all_providers.extend([(p, 'rent') for p in country_data.get('buy', [])])
            
            for provider, ptype in all_providers:
                mapped = _map_provider(provider['provider_name'])
                if not mapped:
                    continue
                    
                if is_india:
                    if ptype == 'stream':
                        in_streaming.add(mapped)
                    else:
                        in_rental.add(mapped)
                else:
                    if mapped not in global_streaming:
                        global_streaming[mapped] = []
                    if country_code not in global_streaming[mapped]:
                        global_streaming[mapped].append(country_code)

    # Build result: India first, then global sorted by country count
    providers = []
    
    # India streaming (top priority)
    for name in sorted(in_streaming):
        providers.append({'name': name})
    
    # India rental
    for name in sorted(in_rental):
        providers.append({'name': f'{name} (Rent)'})
    
    # Global providers sorted by most countries first
    for name, countries in sorted(global_streaming.items(), key=lambda x: -len(x[1])):
        providers.append({'name': name, 'countries': sorted(countries)[:15]})

    # Try JustWatch GraphQL API if TMDB didn't give results
    if not providers and title and settings.JUSTWATCH_ENABLED:
        try:
            # JustWatch GraphQL API endpoint
            url = "https://apis.justwatch.com/graphql"

            # GraphQL query to search for movie
            query = """
            query GetSearchTitles($searchTitlesFilter: TitleFilter!, $country: Country!, $language: Language!) {
              popularTitles(
                country: $country
                filter: $searchTitlesFilter
                first: 5
              ) {
                edges {
                  node {
                    ... on MovieOrShow {
                      objectType
                      objectId
                      content(country: $country, language: $language) {
                        title
                        originalReleaseYear
                      }
                      offers(country: $country, platform: WEB) {
                        monetizationType
                        package {
                          packageId
                          clearName
                        }
                      }
                    }
                  }
                }
              }
            }
            """

            variables = {
                "searchTitlesFilter": {"searchQuery": title},
                "country": "IN",
                "language": "en"
            }

            response = await http_client.post(
                url,
                json={"query": query, "variables": variables},
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                data = response.json()
                edges = data.get('data', {}).get('popularTitles', {}).get('edges', [])

                for edge in edges:
                    node = edge.get('node', {})
                    if node.get('objectType') == 'MOVIE':
                        content = node.get('content', {})
                        movie_year = content.get('originalReleaseYear')

                        # Match year if provided
                        if year and movie_year and abs(movie_year - year) > 1:
                            continue

                        offers = node.get('offers', [])
                        for offer in offers:
                            package = offer.get('package', {})
                            provider_name = package.get('clearName', '')
                            mapped = _map_provider(provider_name)
                            if mapped:
                                if offer.get('monetizationType') in ['FLATRATE', 'FREE', 'ADS']:
                                    providers.append({'name': mapped})
                                elif offer.get('monetizationType') in ['RENT', 'BUY']:
                                    providers.append({'name': f'{mapped} (Rent)'})

                        if providers:
                            break

                if providers:
                    logger.info(f"JustWatch found {len(providers)} providers for '{title}'")
        except Exception as e:
            logger.warning(f"JustWatch lookup failed: {str(e)}")

    # Deduplicate by name
    seen = set()
    unique = []
    for p in providers:
        key = p['name'] if isinstance(p, dict) else p
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique

async def process_movie(movie_data: dict, generate_warnings: bool = False) -> Optional[Movie]:
    """Process a movie from TMDB and enrich with additional data"""
    try:
        tmdb_id = movie_data['id']

        # Get basic details first to extract title and year
        details = await get_movie_details(tmdb_id)
        if not details:
            return None

        title = details.get('title', '')
        release_date = details.get('release_date', '')
        year = int(release_date[:4]) if release_date and len(release_date) >= 4 else None

        # Fetch remaining data with title/year for JustWatch
        fetch_tasks = [
            get_movie_credits(tmdb_id),
            get_streaming_providers(tmdb_id, title, year),
            get_movie_certification(tmdb_id)
        ]

        results = await asyncio.gather(*fetch_tasks)
        (cast, director), providers, certification = results

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

        # Attach original language to each OTT provider so users know what to expect
        # Regional films may only be available as dubbed versions on some platforms
        for p in providers:
            if isinstance(p, dict) and 'language' not in p:
                p['language'] = language_name

        movie = Movie(
            id=str(uuid.uuid4()),
            tmdb_id=tmdb_id,
            title=title,
            original_title=details.get('original_title', ''),
            genres=[genre['name'] for genre in details.get('genres', [])],
            language=language_name,
            original_language=original_lang,
            cast=cast,
            director=director,
            rating=round(details.get('vote_average', 0), 1),
            imdb_rating=round(imdb_rating, 1) if imdb_rating else None,
            certification=certification,
            content_warnings=None,  # Generated on-demand
            vote_count=details.get('vote_count', 0),
            release_date=release_date,
            synopsis=details.get('overview', ''),
            ott_platforms=providers,
            poster_url=f"{TMDB_IMAGE_BASE}{details['poster_path']}" if details.get('poster_path') else None,
            backdrop_url=f"{TMDB_IMAGE_BASE}{details['backdrop_path']}" if details.get('backdrop_path') else None,
            runtime=details.get('runtime'),
            popularity=details.get('popularity', 0)
        )

        # Only generate content warnings if explicitly requested (on-demand)
        if generate_warnings and certification:
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
