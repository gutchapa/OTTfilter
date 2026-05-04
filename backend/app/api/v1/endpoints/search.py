from fastapi import APIRouter, HTTPException
from app.models.movie import NaturalLanguageQuery, ParsedQuery, Movie
from app.services.openai_service import parse_natural_language_query, correct_actor_name
from app.services.youtube import search_youtube_videos
from app.services.tmdb import fetch_tmdb_data
from app.services.movie_service import process_movie
from app.services.utils import fuzzy_match_score, fuzzy_search_actor
from app.core.database import get_database
import logging
import asyncio
import json

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/natural", response_model=dict)
async def natural_language_search(query: NaturalLanguageQuery):
    """Process natural language search query with all 27 features"""
    try:
        # 1. Parse query with AI (with fallback parser)
        parsed = await parse_natural_language_query(query.query)
        
        # 1b. SMART FALLBACK: If AI parsed as genres only but query looks like a title, treat as title search
        # Example: "love action drama" -> AI sees genres, but it's actually a movie title
        # BUT: Don't override if cast_name is already set (e.g., "Oriol Paulo movies")
        if not parsed.keywords and not parsed.cast_name and parsed.intent == "search_movie":
            query_lower = query.query.lower().strip()
            words = query_lower.split()
            
            # If 2-4 words that could be a title (not just single genre words)
            genre_words = {'action', 'comedy', 'drama', 'romance', 'thriller', 'horror', 'adventure', 
                          'fantasy', 'sci-fi', 'science fiction', 'crime', 'mystery', 'family', 'animation'}
            
            # Check if this looks like a specific title vs just genres
            non_genre_words = [w for w in words if w not in genre_words]
            
            if len(words) >= 3 or (len(words) >= 2 and non_genre_words):
                logger.info(f"SMART FALLBACK: Treating '{query.query}' as movie title")
                parsed.keywords = query.query
                parsed.genres = None
        
        # 2. Search YouTube if intent matches
        youtube_results = []
        if parsed.intent == "search_youtube" or parsed.intent == "search_song":
            search_term = parsed.keywords or query.query
            youtube_results = search_youtube_videos(search_term)

        # 3. Build MongoDB query
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

        # Year filtering
        if parsed.release_year:
            db_query['release_date'] = {'$regex': f"^{parsed.release_year}"}

        # Movie title search with fuzzy matching support
        if parsed.keywords and parsed.intent == "search_movie":
            # Split search into words for better fuzzy matching
            # e.g., "kuti puli" -> searches for titles containing both "kuti" AND "puli"
            words = parsed.keywords.split()

            if len(words) > 1:
                # Multi-word search: match if title contains all words (order-independent)
                word_patterns = [{'title': {'$regex': word, '$options': 'i'}} for word in words]
                word_patterns_original = [{'original_title': {'$regex': word, '$options': 'i'}} for word in words]

                db_query['$or'] = [
                    {'$and': word_patterns},  # All words in title
                    {'$and': word_patterns_original},  # All words in original_title
                    {'title': {'$regex': parsed.keywords, '$options': 'i'}},  # Exact phrase in title
                    {'original_title': {'$regex': parsed.keywords, '$options': 'i'}}  # Exact phrase in original
                ]
            else:
                # Single word search
                db_query['$or'] = [
                    {'title': {'$regex': parsed.keywords, '$options': 'i'}},
                    {'original_title': {'$regex': parsed.keywords, '$options': 'i'}}
                ]

        # Actor/cast search
        if parsed.cast_name:
            # If we already have $or for title search, combine with AND
            cast_or = [
                {'cast': {'$regex': parsed.cast_name, '$options': 'i'}},
                {'director': {'$regex': parsed.cast_name, '$options': 'i'}}
            ]

            if '$or' in db_query:
                # Combine title search with cast search using $and
                db_query = {
                    '$and': [
                        {'$or': db_query.pop('$or')},
                        {'$or': cast_or}
                    ],
                    **db_query  # Add remaining filters
                }
            else:
                db_query['$or'] = cast_or

        sort_field = 'popularity'
        if parsed.sort_by == 'release_date':
            sort_field = 'release_date'
        elif parsed.sort_by == 'rating':
            sort_field = 'rating'

        # DEBUG LOGGING
        logger.info(f"🗄️  MONGODB QUERY: {json.dumps(db_query, default=str)}")

        # Fetch movies from database first
        limit = 100 if parsed.platforms else 50
        movies = await db.movies.find(db_query, {'_id': 0}).sort(sort_field, -1).limit(limit).to_list(limit)

        logger.info(f"📊 MONGODB RESULTS: {len(movies)} movies found")

        # If < 10 results from cache and not actor search, fetch fresh from TMDB
        if len(movies) < 10 and not parsed.cast_name:
            logger.info(f"⚠️  Only {len(movies)} cached results, fetching from TMDB...")

            # Movie title search - use /search/movie
            if parsed.keywords and parsed.intent == "search_movie":
                search_params = {'query': parsed.keywords, 'page': 1}
                if parsed.languages:
                    lang_code_map = {
                        'Tamil': 'ta', 'Hindi': 'hi', 'Telugu': 'te',
                        'Malayalam': 'ml', 'Kannada': 'kn', 'English': 'en'
                    }
                    lang_code = lang_code_map.get(parsed.languages[0], 'en')
                    search_params['language'] = lang_code

                if parsed.release_year:
                    search_params['year'] = parsed.release_year

                logger.info(f"🎬 TMDB SEARCH: /search/movie with {search_params}")
                tmdb_data = await fetch_tmdb_data('/search/movie', search_params)
            else:
                # Genre/language/platform filters - use /discover/movie
                tmdb_params = {
                    'page': 1,
                    'sort_by': f"{parsed.sort_by}.desc" if parsed.sort_by != "popularity" else "popularity.desc",
                    'region': 'IN'
                }

                if parsed.languages:
                    lang_code_map = {
                        'Tamil': 'ta', 'Hindi': 'hi', 'Telugu': 'te',
                        'Malayalam': 'ml', 'Kannada': 'kn', 'English': 'en'
                    }
                    lang_code = lang_code_map.get(parsed.languages[0], 'en')
                    tmdb_params['with_original_language'] = lang_code

                if parsed.genres:
                    genre_map = {
                        'Action': 28, 'Adventure': 12, 'Animation': 16, 'Comedy': 35,
                        'Crime': 80, 'Drama': 18, 'Fantasy': 14, 'Horror': 27,
                        'Music': 10402, 'Romance': 10749, 'Science Fiction': 878,
                        'Thriller': 53, 'War': 10752
                    }
                    genre_ids = [str(genre_map.get(g)) for g in parsed.genres if g in genre_map]
                    if genre_ids:
                        tmdb_params['with_genres'] = ','.join(genre_ids)

                if parsed.min_rating:
                    tmdb_params['vote_average.gte'] = parsed.min_rating
                    # Skip vote_count for regional languages
                    regional_languages = ['Tamil', 'Telugu', 'Malayalam', 'Kannada', 'Bengali', 'Marathi', 'Punjabi']
                    if not parsed.languages or not any(lang in regional_languages for lang in parsed.languages):
                        tmdb_params['vote_count.gte'] = 50
                    else:
                        logger.info(f"🎬 Skipping vote_count requirement for regional language: {parsed.languages}")

                if parsed.release_year:
                    tmdb_params['primary_release_year'] = parsed.release_year

                logger.info(f"🎬 TMDB DISCOVER: /discover/movie with {tmdb_params}")
                tmdb_data = await fetch_tmdb_data('/discover/movie', tmdb_params)

            if tmdb_data and tmdb_data.get('results'):
                logger.info(f"✅ TMDB returned {len(tmdb_data['results'])} movies")

                # CRITICAL: Fuzzy matching for movie title searches
                results = tmdb_data['results'][:20]

                if parsed.keywords and parsed.intent == "search_movie":
                    search_term_lower = parsed.keywords.lower()
                    filtered_results = []

                    for result in results:
                        title = result.get('title', '').lower()
                        original_title = result.get('original_title', '').lower()

                        # Exact substring match
                        exact_match = search_term_lower in title or search_term_lower in original_title

                        # Fuzzy match for typos (e.g., "kidari" -> "kidaari", "kuti puli" -> "kutti puli")
                        # Lowered threshold from 0.75 to 0.65 to handle single-char typos
                        fuzzy_score_title = fuzzy_match_score(search_term_lower, title)
                        fuzzy_score_original = fuzzy_match_score(search_term_lower, original_title)
                        fuzzy_match = fuzzy_score_title >= 0.65 or fuzzy_score_original >= 0.65

                        if exact_match or fuzzy_match:
                            filtered_results.append(result)
                            if fuzzy_match and not exact_match:
                                logger.info(f"✅ Fuzzy matched '{parsed.keywords}' to '{result.get('title')}' (score: {max(fuzzy_score_title, fuzzy_score_original):.2f})")
                        else:
                            logger.info(f"⚠️  Filtered out irrelevant TMDB result: '{result.get('title')}' (doesn't contain '{parsed.keywords}')")

                    results = filtered_results
                    logger.info(f"🔍 After title relevance filter: {len(results)} movies remain")

                # Process movies in batches
                batch_size = 10
                for i in range(0, len(results), batch_size):
                    batch = results[i:i+batch_size]
                    batch_movies = await asyncio.gather(
                        *[process_movie(movie_data) for movie_data in batch],
                        return_exceptions=True
                    )
                    for m in batch_movies:
                        if m is not None and isinstance(m, Movie):
                            movies.append(m.dict())
                            # Cache it
                            await db.movies.update_one(
                                {'tmdb_id': m.tmdb_id},
                                {'$set': m.dict()},
                                upsert=True
                            )

        # Actor lead/supporting filtering
        if parsed.cast_name and len(movies) > 0:
            lead_movies = []  # Top 2 cast
            supporting_movies = []  # Position 3-5

            for movie in movies:
                cast = movie.get('cast', [])
                director = (movie.get('director', '') or '').lower()
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

            movies = lead_movies + supporting_movies
            logger.info(f"Filtered: {len(lead_movies)} lead roles, {len(supporting_movies)} supporting roles for '{parsed.cast_name}'")

        # DIRECTOR SEARCH: If we have cast_name (could be director), search TMDB for their filmography
        # Only run when user is searching for an actor/director WITHOUT a specific movie title
        if len(movies) < 5 and parsed.cast_name and not parsed.keywords:
            logger.info(f"🎬 Only {len(movies)} movies found locally for '{parsed.cast_name}', searching TMDB person...")
            
            # Search for person on TMDB
            person_search = await fetch_tmdb_data('/search/person', {'query': parsed.cast_name})
            
            if person_search and person_search.get('results'):
                # Find best match
                best_match = None
                for person in person_search['results']:
                    name = person.get('name', '').lower()
                    if parsed.cast_name.lower() in name or name in parsed.cast_name.lower():
                        best_match = person
                        break
                
                if not best_match:
                    best_match = person_search['results'][0]  # Use first result
                
                person_id = best_match.get('id')
                person_name = best_match.get('name')
                logger.info(f"🎬 Found person: {person_name} (ID: {person_id})")
                
                # Get their movie credits
                credits = await fetch_tmdb_data(f'/person/{person_id}/movie_credits')
                
                if credits:
                    # Get movies they directed
                    directed_movies = [m for m in credits.get('crew', []) if m.get('job') == 'Director']
                    logger.info(f"🎬 {person_name} directed {len(directed_movies)} movies")
                    
                    # Sort by popularity or release date
                    directed_movies.sort(key=lambda x: x.get('popularity', 0), reverse=True)
                    
                    for movie_data in directed_movies[:15]:
                        m = await process_movie(movie_data)
                        if m:
                            movies.append(m.dict())
                            await db.movies.update_one(
                                {'tmdb_id': m.tmdb_id},
                                {'$set': m.dict()},
                                upsert=True
                            )
                    
                    # Also get movies they acted in
                    acted_movies = credits.get('cast', [])
                    logger.info(f"🎬 {person_name} acted in {len(acted_movies)} movies")
                    
                    for movie_data in acted_movies[:10]:
                        m = await process_movie(movie_data)
                        if m:
                            movies.append(m.dict())
                            await db.movies.update_one(
                                {'tmdb_id': m.tmdb_id},
                                {'$set': m.dict()},
                                upsert=True
                            )

        # Fuzzy actor search fallback (only when keywords not set - pure actor search)
        if len(movies) < 10 and parsed.cast_name and not parsed.keywords:
            logger.info(f"🎭 Only {len(movies)} movies found for actor '{parsed.cast_name}', trying TMDB actor search...")
            corrected_name = await correct_actor_name(parsed.cast_name)
            logger.info(f"🎭 Corrected name: '{corrected_name}'")

            result = await fuzzy_search_actor(corrected_name)

            if result:
                person_id, person_name = result
                discover_params = {
                    'with_cast': person_id,
                    'sort_by': 'release_date.desc' if parsed.sort_by == 'release_date' else 'popularity.desc',
                    'page': 1
                }

                if parsed.release_year:
                    discover_params['primary_release_year'] = parsed.release_year
                    logger.info(f"🎭 Filtering actor movies by year: {parsed.release_year}")

                movies_data = await fetch_tmdb_data('/discover/movie', discover_params)

                if movies_data and movies_data.get('results'):
                    logger.info(f"Found {len(movies_data['results'])} movies for {person_name}")
                    for movie_data in movies_data['results'][:10]:
                        m = await process_movie(movie_data)
                        if m:
                            movies.append(m.dict())
                            await db.movies.update_one(
                                {'tmdb_id': m.tmdb_id},
                                {'$set': m.dict()},
                                upsert=True
                            )

        # Oscar compilation exclusion
        query_lower = query.query.lower()
        if any(word in query_lower for word in ['oscar', 'academy award', 'award']):
            original_count = len(movies)
            movies = [
                m for m in movies
                if not any(phrase in m.get('title', '').lower() for phrase in [
                    'oscar nominated short films',
                    'academy awards short films',
                    'a night at the oscars',
                    'oscar shorts'
                ])
            ]
            filtered_count = original_count - len(movies)
            if filtered_count > 0:
                logger.info(f"🎬 Filtered out {filtered_count} Oscar compilation films")

        # DEDUPLICATION: Remove duplicate movies by tmdb_id
        seen_tmdb_ids = set()
        unique_movies = []
        for movie in movies:
            tmdb_id = movie.get('tmdb_id')
            if tmdb_id and tmdb_id not in seen_tmdb_ids:
                seen_tmdb_ids.add(tmdb_id)
                unique_movies.append(movie)
            elif not tmdb_id:
                # Include movies without tmdb_id (shouldn't happen but safety)
                unique_movies.append(movie)
        movies = unique_movies
        logger.info(f"🔄 After deduplication: {len(movies)} unique movies")

        # JioHotstar rebrand transformation
        for movie in movies:
            if 'ott_platforms' in movie and movie['ott_platforms']:
                movie['ott_platforms'] = [
                    'JioHotstar' if platform == 'Disney+ Hotstar' else platform
                    for platform in movie['ott_platforms']
                ]

        # PRIORITIZE DIRECTOR MATCHES: If searching by cast_name (director), boost their movies to top
        if parsed.cast_name:
            cast_name_lower = parsed.cast_name.lower()
            for movie in movies:
                director = (movie.get('director') or '').lower()
                cast = [c.lower() for c in movie.get('cast', [])]
                
                # MASSIVE boost for director match (ensures they appear first)
                if cast_name_lower in director or director in cast_name_lower:
                    movie['popularity'] = movie.get('popularity', 0) + 10000
                    logger.info(f"⭐ DIRECTOR MATCH: Boosting '{movie.get('title')}' by 10000")
                # Big boost for cast match
                elif any(cast_name_lower in c or c in cast_name_lower for c in cast):
                    movie['popularity'] = movie.get('popularity', 0) + 5000
                    logger.info(f"⭐ CAST MATCH: Boosting '{movie.get('title')}' by 5000")
        
        # ALSO: If query contains name that matches director, boost those movies
        # This handles cases like "Mirage Oriol Paulo" where AI parses as keywords not cast_name
        query_lower = query.query.lower()
        for movie in movies:
            director = (movie.get('director') or '').lower()
            if director and len(director) > 3:  # Avoid short name matches
                # Check if director name appears in query
                director_parts = director.split()
                for part in director_parts:
                    if len(part) > 3 and part in query_lower:
                        movie['popularity'] = movie.get('popularity', 0) + 8000
                        logger.info(f"⭐ QUERY DIRECTOR MATCH: Boosting '{movie.get('title')}' by 8000 for '{part}'")
                        break

        # Smart sorting for movie title searches
        if parsed.keywords and parsed.intent == "search_movie":
            search_term_lower = parsed.keywords.lower()

            for movie in movies:
                title_lower = movie.get('title', '').lower()
                original_title_lower = movie.get('original_title', '').lower()

                # Boost score for exact title match
                if search_term_lower == title_lower or search_term_lower == original_title_lower:
                    movie['popularity'] = movie.get('popularity', 0) + 1000

                # Boost for movies with OTT platforms
                if movie.get('ott_platforms'):
                    movie['popularity'] = movie.get('popularity', 0) + 500

                # Boost for recent movies
                release_date = movie.get('release_date', '')
                if release_date:
                    try:
                        year = int(release_date[:4])
                        recency_boost = max(0, (year - 2000) * 10)
                        movie['popularity'] = movie.get('popularity', 0) + recency_boost
                    except:
                        pass

            # Re-sort by boosted popularity
            movies = sorted(movies, key=lambda x: x.get('popularity', 0), reverse=True)

        # Limit final results
        movies = movies[:20]

        return {
            "intent": parsed.intent or "search_movie",
            "parsed_query": parsed.dict(),
            "movies": movies,
            "youtube_results": [v.dict() for v in youtube_results] if youtube_results else []
        }

    except Exception as e:
        logger.error(f"Error in natural_language_search: {str(e)}", exc_info=True)
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
