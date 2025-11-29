from difflib import SequenceMatcher
from typing import Optional, Tuple, List
import logging
from app.services.tmdb import fetch_tmdb_data

logger = logging.getLogger(__name__)


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
