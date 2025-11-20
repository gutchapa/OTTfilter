from fastapi import APIRouter
from app.api.v1.endpoints import movies, search

api_router = APIRouter()

# Movies endpoints
api_router.include_router(movies.router, prefix="/movies", tags=["movies"])

# Search endpoints
# Note: We map /natural to /natural-search to match old API if needed, 
# but for v1 we will try to keep it clean and update frontend.
# However, to support the "discover" and "filter-options" which were root level in old API:

api_router.include_router(movies.router, prefix="", tags=["root-movies"]) 
# This exposes /discover and /options/all at /api/v1/discover etc.

api_router.include_router(search.router, prefix="", tags=["root-search"])
# This exposes /natural and /basic
