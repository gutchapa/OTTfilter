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

async def get_streaming_providers(tmdb_id: int, title: str = None, year: int = None):
    """Get streaming availability for India with JustWatch integration"""
    # Try TMDB first - check all monetization types (flatrate, free, ads)
    data = await fetch_tmdb_data(f"/movie/{tmdb_id}/watch/providers")
    providers = []

    if data and 'results' in data:
        india_data = data['results'].get('IN', {})

        # Check all monetization types: flatrate (subscription), free (with ads), ads
        all_providers = []
        all_providers.extend(india_data.get('flatrate', []))
        all_providers.extend(india_data.get('free', []))
        all_providers.extend(india_data.get('ads', []))

        for provider in all_providers:
            provider_name = provider['provider_name']
            if 'Netflix' in provider_name:
                providers.append('Netflix')
            elif 'Prime' in provider_name or 'Amazon' in provider_name:
                providers.append('Prime Video')
            elif 'Disney' in provider_name or 'Hotstar' in provider_name:
                providers.append('JioHotstar')  # Rebrand to JioHotstar
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
            elif 'YouTube' not in provider_name:  # Exclude YouTube Movies/Rent
                providers.append(provider_name)

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
                            if offer.get('monetizationType') in ['FLATRATE', 'FREE', 'ADS']:
                                package = offer.get('package', {})
                                provider_name = package.get('clearName', '')

                                # Map to our platform names
                                if 'Netflix' in provider_name:
                                    providers.append('Netflix')
                                elif 'Prime' in provider_name or 'Amazon' in provider_name:
                                    providers.append('Prime Video')
                                elif 'Disney' in provider_name or 'Hotstar' in provider_name:
                                    providers.append('JioHotstar')
                                elif 'Jio Cinema' in provider_name:
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
                                elif 'Sun NXT' in provider_name:
                                    providers.append('Sun NXT')

                        if providers:
                            break

                if providers:
                    logger.info(f"JustWatch found {len(providers)} providers for '{title}'")
        except Exception as e:
            logger.warning(f"JustWatch lookup failed: {str(e)}")

    return list(set(providers))  # Remove duplicates

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

        # Don't assign random OTT platforms - leave empty if not found
        # Honesty is better than fake data

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
            ott_platforms=providers,  # May be empty - that's OK
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
