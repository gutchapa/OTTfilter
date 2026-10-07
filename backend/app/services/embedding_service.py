"""Semantic search with EmbeddingGemma.

Opt-in via EMBEDDINGS_ENABLED=true. Everything here fails soft: if the model or
its dependencies are missing, search falls back to the existing keyword/fuzzy path.

Vectors live in their own collection (`movie_embeddings`) so the feature can be
rolled back by dropping that collection - the `movies` documents are untouched.
"""
import asyncio
import hashlib
import logging
from typing import Dict, List, Optional

import numpy as np

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# EmbeddingGemma expects task prefixes; omitting them noticeably hurts retrieval.
QUERY_PREFIX = "task: search result | query: "
DOC_PREFIX = "title: {title} | text: "

COLLECTION = "movie_embeddings"

_model = None
_model_failed = False
_model_lock = asyncio.Lock()


def is_enabled() -> bool:
    return settings.EMBEDDINGS_ENABLED and not _model_failed


def movie_document(movie: dict) -> str:
    """Text we embed for a movie: title, original title, genres, language, people, synopsis."""
    title = movie.get("title") or "none"
    parts = []
    original = movie.get("original_title")
    if original and original != movie.get("title"):
        parts.append(original)
    if movie.get("genres"):
        parts.append(", ".join(movie["genres"]))
    if movie.get("language"):
        parts.append(f"{movie['language']} movie")
    if movie.get("cast"):
        parts.append("Starring " + ", ".join(movie["cast"][:5]))
    if movie.get("director"):
        parts.append(f"Directed by {movie['director']}")
    if movie.get("synopsis"):
        parts.append(movie["synopsis"])
    return DOC_PREFIX.format(title=title) + ". ".join(parts)


def _text_hash(text: str) -> str:
    return hashlib.sha1(f"{settings.EMBEDDING_MODEL}:{settings.EMBEDDING_DIM}:{text}".encode()).hexdigest()


def _normalize(vectors: np.ndarray) -> np.ndarray:
    # Matryoshka truncation: keep the first N dims, then re-normalise so dot product == cosine
    vectors = vectors[:, : settings.EMBEDDING_DIM]
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def _load_model():
    from sentence_transformers import SentenceTransformer

    # float32 on purpose: EmbeddingGemma produces garbage in fp16
    return SentenceTransformer(settings.EMBEDDING_MODEL, token=settings.HF_TOKEN)


async def _get_model():
    global _model, _model_failed
    if _model is not None or _model_failed:
        return _model
    async with _model_lock:
        if _model is None and not _model_failed:
            try:
                logger.info(f"🧠 Loading embedding model {settings.EMBEDDING_MODEL}...")
                _model = await asyncio.to_thread(_load_model)
                logger.info("🧠 Embedding model loaded")
            except Exception as e:
                _model_failed = True
                logger.error(f"🧠 Could not load embedding model, semantic search disabled: {e}")
    return _model


async def _encode(texts: List[str]) -> Optional[np.ndarray]:
    model = await _get_model()
    if model is None or not texts:
        return None
    vectors = await asyncio.to_thread(model.encode, texts, batch_size=16, convert_to_numpy=True)
    return _normalize(np.asarray(vectors, dtype=np.float32))


async def embed_query(query: str) -> Optional[np.ndarray]:
    vectors = await _encode([QUERY_PREFIX + query])
    return None if vectors is None else vectors[0]


async def get_movie_vectors(db, movies: List[dict]) -> Dict[int, np.ndarray]:
    """Return {tmdb_id: vector}, embedding and storing any movie that is missing or stale."""
    docs = {m["tmdb_id"]: movie_document(m) for m in movies if m.get("tmdb_id") is not None}
    if not docs:
        return {}

    stored = await db[COLLECTION].find(
        {"tmdb_id": {"$in": list(docs)}}, {"_id": 0, "tmdb_id": 1, "hash": 1, "vector": 1}
    ).to_list(None)

    vectors: Dict[int, np.ndarray] = {}
    for row in stored:
        if row.get("hash") == _text_hash(docs[row["tmdb_id"]]):
            vectors[row["tmdb_id"]] = np.asarray(row["vector"], dtype=np.float32)

    missing = [tid for tid in docs if tid not in vectors]
    if missing:
        encoded = await _encode([docs[tid] for tid in missing])
        if encoded is None:
            return vectors
        for tid, vec in zip(missing, encoded):
            vectors[tid] = vec
            await db[COLLECTION].update_one(
                {"tmdb_id": tid},
                {"$set": {"tmdb_id": tid, "hash": _text_hash(docs[tid]), "vector": vec.tolist()}},
                upsert=True,
            )
        logger.info(f"🧠 Embedded {len(missing)} new movies")
    return vectors


async def semantic_candidates(db, query_vec: np.ndarray, db_filter: dict, limit: int = 20) -> List[dict]:
    """Nearest cached movies to the query that also satisfy the hard filters (language, platform...).

    Brute-force cosine over the stored vectors - fine for a cache in the low thousands.
    Move to Atlas Vector Search if the catalogue grows well past that.
    """
    rows = await db[COLLECTION].find({}, {"_id": 0, "tmdb_id": 1, "vector": 1}).to_list(None)
    if not rows:
        return []
    ids = [r["tmdb_id"] for r in rows]
    matrix = np.asarray([r["vector"] for r in rows], dtype=np.float32)
    scores = matrix @ query_vec
    ranked = [ids[i] for i in np.argsort(-scores)[: limit * 5]]

    query = {**db_filter, "tmdb_id": {"$in": ranked}}
    found = await db.movies.find(query, {"_id": 0}).to_list(None)
    order = {tid: i for i, tid in enumerate(ranked)}
    found.sort(key=lambda m: order.get(m["tmdb_id"], len(order)))
    return found[:limit]


async def rerank(db, query: str, movies: List[dict], hard_filter: dict, weight: float, expand: bool = True) -> List[dict]:
    """Optionally add semantically similar cached movies, then blend similarity into the popularity score.

    Returns `movies` unchanged on any failure so search never breaks because of embeddings.
    """
    try:
        query_vec = await embed_query(query)
        if query_vec is None:
            return movies

        if expand:
            seen = {m.get("tmdb_id") for m in movies}
            extra = [m for m in await semantic_candidates(db, query_vec, hard_filter) if m["tmdb_id"] not in seen]
            if extra:
                logger.info(f"🧠 Semantic search added {len(extra)} movies")
            movies = movies + extra

        vectors = await get_movie_vectors(db, movies)
        for movie in movies:
            vec = vectors.get(movie.get("tmdb_id"))
            sim = float(vec @ query_vec) if vec is not None else 0.0
            movie["semantic_score"] = round(sim, 4)
            movie["popularity"] = movie.get("popularity", 0) + sim * weight
        return sorted(movies, key=lambda x: x.get("popularity", 0), reverse=True)
    except Exception as e:
        logger.error(f"🧠 Semantic rerank failed, using keyword results: {e}", exc_info=True)
        return movies
