import pytest
from fastapi.testclient import TestClient
from app.main import app

@ pytest.fixture(autouse=True)
def setup_mocks(monkeypatch):
    # Stub database to return some cached results
    class DummyCollection:
        async def find(self, *args, **kwargs): return self
        def sort(self, *args, **kwargs): return self
        def limit(self, *args, **kwargs): return self
        async def to_list(self, *args, **kwargs): return [{'cached': True}]

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

    async def fake_parse_nl(q): return Parsed(q)
    monkeypatch.setattr("app.api.v1.endpoints.search.parse_natural_language_query", fake_parse_nl)

    # Stub fetch_tmdb_data to return known result
    fake_movie = {'tmdb_id': 123, 'title': 'Test Movie'}
    async def fake_fetch(path, params): return {'results': [fake_movie]}
    monkeypatch.setattr("app.api.v1.endpoints.search.fetch_tmdb_data", fake_fetch)

    # Stub process_movie to return model-like object
    class FakeMovie:
        def __init__(self, data): self.data = data
        def model_dump(self): return self.data

    async def fake_process(data): return FakeMovie(data)
    monkeypatch.setattr("app.api.v1.endpoints.search.process_movie", fake_process)

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
