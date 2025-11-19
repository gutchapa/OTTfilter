from fastapi import APIRouter, HTTPException
from app.models.movie import NaturalLanguageQuery, ParsedQuery, Movie
from app.services.openai_service import parse_natural_language_query
from app.services.youtube import search_youtube_videos
from app.core.database import get_database
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/natural", response_model=dict)
async def natural_language_search(query: NaturalLanguageQuery):
    """Process natural language search query"""
    try:
        # 1. Parse query with AI
        parsed = await parse_natural_language_query(query.query)
        
        # 2. Search YouTube if intent matches
        youtube_results = []
        if parsed.intent == "search_youtube" or parsed.intent == "search_song":
            search_term = parsed.keywords or query.query
            youtube_results = search_youtube_videos(search_term)
        
        # 3. Search Movies in DB
        db = await get_database()
        db_query = {}
        
        if parsed.genres:
            db_query['genres'] = {'$in': parsed.genres}
        
        if parsed.languages:
            db_query['language'] = {'$in': parsed.languages}
            
        if parsed.platforms:
            db_query['ott_platforms'] = {'$in': parsed.platforms}
            
        if parsed.min_rating:
            db_query['rating'] = {'$gte': parsed.min_rating}
            
        if parsed.cast_name:
            db_query['cast'] = {'$regex': parsed.cast_name, '$options': 'i'}
            
        if parsed.keywords and parsed.intent == "search_movie":
            db_query['$or'] = [
                {'title': {'$regex': parsed.keywords, '$options': 'i'}},
                {'original_title': {'$regex': parsed.keywords, '$options': 'i'}}
            ]
            
        sort_field = 'popularity'
        if parsed.sort_by == 'release_date':
            sort_field = 'release_date'
        elif parsed.sort_by == 'rating':
            sort_field = 'rating'
            
        movies = await db.movies.find(db_query, {'_id': 0}).sort(sort_field, -1).limit(20).to_list(20)
        
        return {
            "parsed_query": parsed,
            "movies": movies,
            "youtube_results": youtube_results
        }
        
    except Exception as e:
        logger.error(f"Error in natural_language_search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/basic", response_model=list[Movie])
async def basic_search(q: str):
    """Simple keyword search"""
    try:
        db = await get_database()
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
        logger.error(f"Error in basic_search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
