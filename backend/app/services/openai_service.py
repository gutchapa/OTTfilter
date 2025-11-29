import openai
import json
import logging
from app.core.config import get_settings
from app.models.movie import ParsedQuery
from typing import List, Optional

settings = get_settings()
openai.api_key = settings.OPENAI_API_KEY
logger = logging.getLogger(__name__)

# openai.api_key set below

async def parse_natural_language_query(query: str) -> ParsedQuery:
    """Parse natural language query using OpenAI to extract filters"""
    if not settings.OPENAI_API_KEY:
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
            oscar_year = (release_year - 1) if release_year else None
            return ParsedQuery(
                min_rating=6.5,
                sort_by="rating",
                release_year=oscar_year,
                keywords=None,
                languages=languages if languages else None,
                intent="filter"
            )

        # Detect actor/cast searches
        cast_name = None
        filter_prefixes = ['top', 'best', 'latest', 'new', 'recent', 'highest', 'greatest']
        has_filter_prefix = any(query_lower.startswith(prefix) for prefix in filter_prefixes)

        actor_pattern = r'^(.+?)\s+(movies?|films?)$'
        actor_match = re.search(actor_pattern, query_lower)

        if actor_match and not has_filter_prefix:
            cast_name = actor_match.group(1).strip()
            for word in filter_prefixes:
                cast_name = re.sub(r'\b' + word + r'\b', '', cast_name, flags=re.IGNORECASE).strip()
            if release_year:
                cast_name = cast_name.replace(str(release_year), '').strip()
            for lang in ['tamil', 'hindi', 'telugu', 'malayalam', 'kannada', 'english']:
                cast_name = cast_name.replace(lang, '').strip()
            cast_name = ' '.join(cast_name.split())

            if cast_name and not cast_name.isdigit():
                return ParsedQuery(
                    cast_name=cast_name,
                    languages=languages if languages else None,
                    release_year=release_year,
                    min_rating=min_rating,
                    sort_by=sort_by,
                    intent="search_movie"
                )

        # Clean up keywords
        keywords_clean = query
        filter_words = ['top', 'best', 'greatest', 'latest', 'recent', 'new', 'movies', 'movie', 'film', 'films']

        if release_year:
            keywords_clean = keywords_clean.replace(str(release_year), '')

        for word in filter_words:
            keywords_clean = re.sub(r'\b' + word + r'\b', '', keywords_clean, flags=re.IGNORECASE)

        keywords_clean = re.sub(r'\b\d+\b', '', keywords_clean)
        keywords_clean = ' '.join(keywords_clean.split()).strip()

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

TYPO CORRECTION (CRITICAL):
- Users often make typos when typing movie names and actor names
- ALWAYS correct spelling errors and put the CORRECTED version in the output
- This is CRITICAL for good user experience - be forgiving with spelling

Movie Title Typos:
- "touist fmly" -> keywords: "tourist family", intent: "search_movie"
- "incption" -> keywords: "inception", intent: "search_movie"
- "the god fater" -> keywords: "the godfather", intent: "search_movie"
- "avngers" -> keywords: "avengers", intent: "search_movie"
- "jailr" -> keywords: "jailer", intent: "search_movie"

Actor Name Typos:
- "ranji", "rajni", "rajini" -> cast_name: "rajinikanth"
- "ameer khan" -> cast_name: "aamir khan"
- "salmen khan" -> cast_name: "salman khan"
- "allu arjn" -> cast_name: "allu arjun"
- "vijy" -> cast_name: "vijay"
- Use your knowledge to correct common Indian actor name typos

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
- "Oscar 2025" -> {"min_rating": 6.5, "release_year": 2024, "sort_by": "rating", "intent": "filter"}
- "top 10 2024 tamil movies" -> {"languages": ["Tamil"], "min_rating": 7.0, "release_year": 2024, "sort_by": "rating", "intent": "filter"}

Return only valid JSON, no explanations."""

        response = await openai.ChatCompletion.acreate(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Parse this query: {query}"}
            ],
            temperature=0.3,
            
        )

        parsed_data = json.loads(response.choices[0].message.content)

        # DEBUG LOGGING
        logger.info(f"🔍 QUERY: '{query}'")
        logger.info(f"🤖 OPENAI PARSED: {json.dumps(parsed_data, indent=2)}")

        parsed_query = ParsedQuery(**parsed_data)
        logger.info(f"📋 FINAL PARSED: {parsed_query.dict()}")

        return parsed_query

    except Exception as e:
        logger.error(f"Error parsing natural language query: {str(e)}")
        return ParsedQuery(keywords=query, intent="search_movie")

async def generate_content_warnings(title: str, genres: List[str], synopsis: str, certification: Optional[str]) -> List[str]:
    """Use AI to generate detailed content warnings based on movie info"""
    if not settings.OPENAI_API_KEY or not certification:
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
["warning 1", "warning 2", "warning 3"]"""

        response = await openai.ChatCompletion.acreate(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a content rating expert who provides detailed, helpful warnings for families."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=150,
            
        )
        
        result = json.loads(response.choices[0].message.content)
        # Handle both array and object responses
        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            # Try common keys
            for key in ['warnings', 'content_warnings', 'items', 'data']:
                if key in result and isinstance(result[key], list):
                    return result[key]
            # If it's a dict with string values, convert to list
            return list(result.values()) if result else []
        return []

    except Exception as e:
        logger.error(f"Error generating content warnings: {str(e)}")
        return []

async def correct_actor_name(misspelled_name: str) -> str:
    """Use LLM to correct actor name spelling"""
    if not settings.OPENAI_API_KEY:
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

        response = await openai.ChatCompletion.acreate(
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
