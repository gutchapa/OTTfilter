import os
import pytest

# Setup dummy environment for Settings
os.environ.setdefault('MONGO_URL', 'mongodb://127.0.0.1:27017')
os.environ.setdefault('DB_NAME', 'ott_filter')
os.environ.setdefault('TMDB_API_KEY', 'fake')
os.environ.setdefault('OPENAI_API_KEY', 'fake')
os.environ.setdefault('YOUTUBE_API_KEY', 'fake')
os.environ.setdefault('OMDB_API_KEY', 'fake')

import pytest
from fastapi.testclient import TestClient
from app.main import app

@ pytest.fixture(autouse=True)
def setup_mocks(monkeypatch):
    # Stub database to return some cached results
    class DummyCollection:
        def find(self, *args, **kwargs): return self
        def sort(self, *args, **kwargs): return self
        def limit(self, *args, **kwargs): return self
        async def to_list(self, *args, **kwargs): return [{'cached': True}]

        async def update_one(self, *args, **kwargs): return None
    class DummyDB:
        @property
        def movies(self): return DummyCollection()

    async def dummy_get_db(): return DummyDB()
    monkeypatch.setattr("app.api.v1.endpoints.search.get_database", dummy_get_db)

    # Stub NL parser to mark as movie search
    class Parsed:
        def __init__(self, query):
            self.query = query
            self.intent = "search_movie"
            self.keywords = query
            self.cast_name = None
            self.languages = None
            self.genres = None
            self.min_rating = None
            self.sort_by = "popularity"
            self.platforms = None
            self.release_year = None
        def model_dump(self):
            return {
                'query': self.query,
                'intent': self.intent,
                'keywords': self.keywords,
                'cast_name': self.cast_name,
                'languages': self.languages,
                'genres': self.genres,
                'min_rating': self.min_rating,
                'sort_by': self.sort_by,
                'platforms': self.platforms,
                'release_year': self.release_year
            }

    async def fake_parse_nl(q): return Parsed(q)
    monkeypatch.setattr("app.api.v1.endpoints.search.parse_natural_language_query", fake_parse_nl)

    # Stub fetch_tmdb_data to return known result
    fake_movie = {'tmdb_id': 123, 'title': 'Test Movie'}
    async def fake_fetch(path, params): return {'results': [fake_movie]}
    monkeypatch.setattr("app.api.v1.endpoints.search.fetch_tmdb_data", fake_fetch)

    # Stub process_movie to return model-like object
    class FakeMovie:
        def __init__(self, data):
            self.data = data
            self.tmdb_id = data.get("tmdb_id")
        def model_dump(self): return self.data

    async def fake_process(data): return FakeMovie(data)
    # Make FakeMovie recognized as the Movie class inside the endpoint
    monkeypatch.setattr("app.api.v1.endpoints.search.Movie", FakeMovie)
    monkeypatch.setattr("app.api.v1.endpoints.search.process_movie", fake_process)

    # Stub fuzzy matching to always pass relevance filter
    monkeypatch.setattr("app.api.v1.endpoints.search.fuzzy_match_score", lambda a, b: 1.0)
    # Stub other services
    monkeypatch.setattr("app.api.v1.endpoints.search.correct_actor_name", lambda x: x)
    monkeypatch.setattr("app.api.v1.endpoints.search.fuzzy_search_actor", lambda x: None)


def test_natural_search_bypasses_cache_and_returns_fresh():
    client = TestClient(app)
    response = client.post("/api/natural", json={"query": "Any movie"})
    assert response.status_code == 200
    data = response.json()
    # Should always fetch fresh data, so we expect our fake_movie
    assert 'movies' in data
    movies = data['movies']
    assert isinstance(movies, list)
    assert movies == [{'tmdb_id': 123, 'title': 'Test Movie'}]
