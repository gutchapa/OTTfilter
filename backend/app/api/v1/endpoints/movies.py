from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.models.movie import Movie, MovieFilter, FilterOptions
from app.services.movie_service import process_movie
from app.services.tmdb import fetch_tmdb_data
from app.core.database import get_database
from pymongo import UpdateOne
import asyncio
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/discover", response_model=dict)
async def discover_movies(
    page: int = Query(1, ge=1),
    language: Optional[str] = None,
    genre: Optional[str] = None
):
    """Discover popular movies and cache them"""
    try:
        db = await get_database()
        
        # FAST PATH: Return cached movies from database first
        cached_movies = await db.movies.find({}, {'_id': 0}).sort('popularity', -1).limit(50).to_list(50)
        
        if len(cached_movies) > 10:
            return {
                'movies': cached_movies,
                'page': page,
                'total_pages': 1
            }
        
        # SLOW PATH: Fetch from TMDB
        logger.info("Cache miss - fetching from TMDB")
        
        params = {'page': 1, 'sort_by': 'popularity.desc', 'region': 'IN'}
        data = await fetch_tmdb_data('/discover/movie', params)
        
        if not data:
            return {'movies': cached_movies, 'page': 1, 'total_pages': 1}
        
        results = data.get('results', [])[:20]
        
        movies = []
        batch_size = 10
        for i in range(0, len(results), batch_size):
            batch = results[i:i+batch_size]
            batch_movies = await asyncio.gather(
                *[process_movie(movie_data) for movie_data in batch],
                return_exceptions=True
            )
            movies.extend([m for m in batch_movies if m is not None and isinstance(m, Movie)])
        
        if movies:
            bulk_operations = [
                UpdateOne(
                    {'tmdb_id': movie.tmdb_id},
                    {'$set': movie.model_dump()},
                    upsert=True
                )
                for movie in movies
            ]
            if bulk_operations:
                await db.movies.bulk_write(bulk_operations)
        
        return {
            'movies': movies,
            'page': page,
            'total_pages': data.get('total_pages', 1)
        }
    
    except Exception as e:
        logger.error(f"Error in discover_movies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/filter", response_model=List[Movie])
async def filter_movies(filters: MovieFilter):
    """Filter movies based on criteria"""
    try:
        db = await get_database()
        query = {}
        
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
        
        movies = await db.movies.find(query, {'_id': 0}).sort('popularity', -1).limit(50).to_list(50)
        
        return movies
    
    except Exception as e:
        logger.error(f"Error in filter_movies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{movie_id}", response_model=Movie)
async def get_movie(movie_id: str):
    """Get a specific movie by ID"""
    db = await get_database()
    movie = await db.movies.find_one({'id': movie_id}, {'_id': 0})
    
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    return movie

@router.get("/options/all", response_model=FilterOptions)
async def get_filter_options():
    """Get all available filter options"""
    try:
        db = await get_database()
        
        genres = await db.movies.distinct('genres')
        genres = sorted([g for g in genres if g])
        
        languages = await db.movies.distinct('language')
        languages = sorted([lang for lang in languages if lang])
        
        platforms = await db.movies.distinct('ott_platforms')
        platforms = sorted([p for p in platforms if p])
        
        return FilterOptions(
            genres=genres,
            languages=languages,
            platforms=platforms
        )
    except Exception as e:
        logger.error(f"Error getting filter options: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
