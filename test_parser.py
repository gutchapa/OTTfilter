#!/usr/bin/env python3
"""Test the fallback parser with problematic queries"""

import re
from typing import Optional, List
from pydantic import BaseModel


class ParsedQuery(BaseModel):
    genres: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    platforms: Optional[List[str]] = None
    min_rating: Optional[float] = None
    cast_name: Optional[str] = None
    keywords: Optional[str] = None
    release_year: Optional[int] = None
    sort_by: Optional[str] = "popularity"
    intent: Optional[str] = None


def parse_natural_language_query(query: str) -> ParsedQuery:
    """Parse natural language query (fallback parser without OpenAI)"""
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
            min_rating=7.5,  # Lowered from 8.0 to get more results
            sort_by="rating",
            release_year=oscar_year,
            keywords=None,  # Don't search by title for Oscar queries
            languages=languages if languages else None,
            intent="filter"  # Use filter intent, not search_movie
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


# Test cases
test_queries = [
    "Top 10 2024 tamil movies",
    "Oscar 2025",
    "inception",
    "best 2023 hindi movies",
    "latest telugu movies",
]

print("=" * 80)
print("PARSER TEST RESULTS")
print("=" * 80)

for query in test_queries:
    print(f"\nQuery: '{query}'")
    print("-" * 80)
    parsed = parse_natural_language_query(query)
    print(f"  keywords:      {parsed.keywords}")
    print(f"  languages:     {parsed.languages}")
    print(f"  release_year:  {parsed.release_year}")
    print(f"  min_rating:    {parsed.min_rating}")
    print(f"  sort_by:       {parsed.sort_by}")
    print(f"  intent:        {parsed.intent}")
    print()

print("=" * 80)
print("\nEXPECTED BEHAVIOR:")
print("-" * 80)
print("1. 'Top 10 2024 tamil movies':")
print("   - Should extract: keywords='tamil', year=2024, languages=['Tamil']")
print("   - Will search for Tamil movies from 2024 with min_rating=7.0")
print()
print("2. 'Oscar 2025':")
print("   - Should extract: keywords=None, year=2025, min_rating=8.0, intent='filter'")
print("   - Will use discover endpoint with rating filter (no title search)")
print()
