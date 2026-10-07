"""Embedding service tests with a fake model and an in-memory Mongo stand-in (no torch, no DB)."""
import asyncio
import os

import numpy as np

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("TMDB_API_KEY", "test")

from app.services import embedding_service as es  # noqa: E402

VOCAB = ["village", "family", "heist", "space", "tamil", "hindi", "comedy", "thriller"]


class FakeModel:
    """Bag-of-words 'embedding' so similarity is predictable."""

    def __init__(self):
        self.calls = 0

    def encode(self, texts, **_):
        self.calls += len(texts)
        out = np.zeros((len(texts), 768), dtype=np.float32)
        for i, t in enumerate(texts):
            for j, w in enumerate(VOCAB):
                out[i, j] = t.lower().count(w)
            out[i, 767] = 0.01
        return out


class Cursor:
    def __init__(self, docs):
        self.docs = docs

    async def to_list(self, _):
        return [dict(d) for d in self.docs]


def _match(doc, query):
    for key, cond in query.items():
        if isinstance(cond, dict) and "$in" in cond:
            val = doc.get(key)
            vals = val if isinstance(val, list) else [val]
            if not any(v in cond["$in"] for v in vals):
                return False
        elif doc.get(key) != cond:
            return False
    return True


class Collection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    def find(self, query, _projection=None):
        return Cursor([d for d in self.docs if _match(d, query)])

    async def update_one(self, flt, update, upsert=False):
        for d in self.docs:
            if _match(d, flt):
                d.update(update["$set"])
                return
        self.docs.append(dict(update["$set"]))


class FakeDB:
    def __init__(self, movies):
        self.movies = Collection(movies)
        self.cols = {"movies": self.movies, es.COLLECTION: Collection()}

    def __getitem__(self, name):
        return self.cols[name]


MOVIES = [
    {"tmdb_id": 1, "title": "Heist Night", "language": "Hindi", "genres": ["Thriller"], "synopsis": "A heist thriller", "popularity": 50},
    {"tmdb_id": 2, "title": "Village Days", "language": "Tamil", "genres": ["Comedy"], "synopsis": "A family comedy in a village", "popularity": 10},
    {"tmdb_id": 3, "title": "Orbit", "language": "English", "genres": ["Drama"], "synopsis": "Lost in space", "popularity": 30},
]


def setup_function(_):
    es._model = FakeModel()
    es._model_failed = False


def test_document_has_prefix_and_fields():
    doc = es.movie_document({**MOVIES[1], "cast": ["A", "B"], "director": "D"})
    assert doc.startswith("title: Village Days | text: ")
    assert "Starring A, B" in doc and "Directed by D" in doc and "Tamil movie" in doc


def test_vectors_truncated_and_normalised():
    vec = asyncio.run(es.embed_query("village family"))
    assert vec.shape == (es.settings.EMBEDDING_DIM,)
    assert abs(np.linalg.norm(vec) - 1.0) < 1e-5


def test_vectors_cached_in_own_collection():
    db = FakeDB(MOVIES)
    asyncio.run(es.get_movie_vectors(db, MOVIES))
    first = es._model.calls
    asyncio.run(es.get_movie_vectors(db, MOVIES))
    assert first == 3 and es._model.calls == 3  # second call served from Mongo
    assert all("vector" not in m for m in db.movies.docs)  # movies docs untouched


def test_stale_vector_reembedded_when_text_changes():
    db = FakeDB(MOVIES)
    asyncio.run(es.get_movie_vectors(db, MOVIES))
    changed = [{**MOVIES[0], "synopsis": "Now a space story"}]
    asyncio.run(es.get_movie_vectors(db, changed))
    assert es._model.calls == 4


def test_rerank_expands_and_respects_hard_filter():
    db = FakeDB(MOVIES)
    asyncio.run(es.get_movie_vectors(db, MOVIES))
    out = asyncio.run(es.rerank(db, "family village comedy", [], {"language": {"$in": ["Tamil"]}}, weight=500))
    assert [m["tmdb_id"] for m in out] == [2]
    assert out[0]["semantic_score"] > 0.5


def test_rerank_promotes_semantic_match():
    db = FakeDB(MOVIES)
    out = asyncio.run(es.rerank(db, "village family", [dict(m) for m in MOVIES], {}, weight=500))
    assert out[0]["tmdb_id"] == 2  # least popular, best match


def test_rerank_no_expand_keeps_input_set():
    db = FakeDB(MOVIES)
    asyncio.run(es.get_movie_vectors(db, MOVIES))
    out = asyncio.run(es.rerank(db, "village", [dict(MOVIES[0])], {}, weight=500, expand=False))
    assert [m["tmdb_id"] for m in out] == [1]


def test_model_failure_falls_back_to_input():
    es._model = None
    es._model_failed = True
    movies = [dict(m) for m in MOVIES]
    assert asyncio.run(es.rerank(FakeDB(MOVIES), "village", movies, {}, weight=500)) == movies
    assert not es.is_enabled()
