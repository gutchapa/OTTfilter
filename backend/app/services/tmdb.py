import httpx
import logging
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

# Shared HTTP client with connection pooling
http_client = httpx.AsyncClient(
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
    timeout=httpx.Timeout(30.0)
)

async def fetch_tmdb_data(endpoint: str, params: dict = None):
    """Fetch data from TMDB API with connection pooling"""
    headers = {
        "Authorization": f"Bearer {settings.TMDB_API_KEY}",
        "accept": "application/json"
    }
    
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
