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
    """Discover latest movies (last 2 years) and cache them"""
    try:
        db = await get_database()

        # FAST PATH: Return cached latest movies from database
        from datetime import datetime
        current_year = datetime.now().year
        two_years_ago = current_year - 2

        # Filter to last 2 years for discover (show latest content)
        year_query = {'release_date': {'$regex': f'^({current_year}|{current_year-1}|{two_years_ago})'}}

        cached_movies = await db.movies.find(year_query, {'_id': 0}).sort('release_date', -1).limit(50).to_list(50)

        # JioHotstar rebrand transformation
        for movie in cached_movies:
            if 'ott_platforms' in movie and movie['ott_platforms']:
                movie['ott_platforms'] = [
                    'JioHotstar' if platform == 'Disney+ Hotstar' else platform
                    for platform in movie['ott_platforms']
                ]

        if len(cached_movies) > 10:
            return {
                'movies': cached_movies,
                'page': page,
                'total_pages': 1
            }

        # SLOW PATH: Fetch latest movies from TMDB
        logger.info("Cache miss - fetching latest movies from TMDB")

        # Fetch diverse content: all Indian languages, last 2 years
        params = {
            'page': 1,
            'sort_by': 'release_date.desc',  # Latest movies first
            'region': 'IN',
            'primary_release_date.gte': f'{two_years_ago}-01-01',  # Last 2 years
            'with_original_language': 'hi|ta|te|ml|kn|en'  # Hindi, Tamil, Telugu, Malayalam, Kannada, English
        }
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
                    {'$set': movie.dict()},
                    upsert=True
                )
                for movie in movies
            ]
            if bulk_operations:
                await db.movies.bulk_write(bulk_operations)

        # JioHotstar rebrand for new movies too
        movies_dicts = [m.dict() for m in movies]
        for movie in movies_dicts:
            if 'ott_platforms' in movie and movie['ott_platforms']:
                movie['ott_platforms'] = [
                    'JioHotstar' if platform == 'Disney+ Hotstar' else platform
                    for platform in movie['ott_platforms']
                ]

        return {
            'movies': movies_dicts,
            'page': page,
            'total_pages': data.get('total_pages', 1)
        }

    except Exception as e:
        logger.exception("Error in discover_movies")
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

        raw_platforms = await db.movies.distinct('ott_platforms')
        # Normalize: ott_platforms can be str or dict {"name": "...", ...}
        platform_names = set()
        for p in raw_platforms:
            if p:
                if isinstance(p, dict):
                    platform_names.add(p.get('name', ''))
                elif isinstance(p, str):
                    platform_names.add(p)
        platforms = sorted([p for p in platform_names if p])

        return FilterOptions(
            genres=genres,
            languages=languages,
            platforms=platforms
        )
    except Exception as e:
        logger.error(f"Error getting filter options: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{movie_id}/content-warnings", response_model=dict)
async def get_content_warnings(movie_id: str):
    """Generate content warnings on-demand for a movie"""
    try:
        db = await get_database()

        # Fetch movie from database
        movie = await db.movies.find_one({'id': movie_id}, {'_id': 0})

        if not movie:
            raise HTTPException(status_code=404, detail="Movie not found")

        # Check if warnings already cached
        if movie.get('content_warnings'):
            return {
                'movie_id': movie_id,
                'content_warnings': movie['content_warnings'],
                'cached': True
            }

        # Generate warnings using AI
        certification = movie.get('certification')
        if not certification:
            return {
                'movie_id': movie_id,
                'content_warnings': [],
                'message': 'No certification available for this movie'
            }

        warnings = await generate_content_warnings(
            title=movie.get('title', ''),
            genres=movie.get('genres', []),
            synopsis=movie.get('synopsis', ''),
            certification=certification
        )

        # Cache warnings in database
        if warnings:
            await db.movies.update_one(
                {'id': movie_id},
                {'$set': {'content_warnings': warnings}}
            )

        return {
            'movie_id': movie_id,
            'content_warnings': warnings,
            'cached': False
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating content warnings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
