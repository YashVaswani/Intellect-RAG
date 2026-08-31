# engine/cache.py
"""
Semantic caching — avoids redundant API calls for similar/repeated questions.
Uses cosine similarity between query embeddings + number/date awareness to prevent stale cache hits on different dates/sessions.
Never caches refusal or error messages.
"""
import json
import time
import logging
import re
import numpy as np
from engine.clients import gemini_client
from google.genai import types
import config

logger = logging.getLogger(__name__)

# In-memory cache
_cache: list[dict] = []


def _extract_numbers(text: str) -> set[str]:
    """Extract numbers and dates from query text to prevent false cache matches on different dates/sessions."""
    return set(re.findall(r'\b\d+\b', text))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a_arr = np.array(a)
    b_arr = np.array(b)
    dot = np.dot(a_arr, b_arr)
    norm = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
    if norm == 0:
        return 0.0
    return float(dot / norm)


def _embed_for_cache(text: str) -> list[float] | None:
    """Generate embedding for cache comparison."""
    try:
        response = gemini_client.models.embed_content(
            model=config.EMBED_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=config.VECTOR_DIMENSION
            ),
        )
        return response.embeddings[0].values
    except Exception as e:
        logger.debug(f"Cache embedding failed: {e}")
        return None


def lookup(query: str) -> dict | None:
    """
    Check if a similar query exists in cache.
    Requires similarity > threshold AND exact matching numbers/dates.
    """
    if not config.CACHE_ENABLED:
        return None

    query_embedding = _embed_for_cache(query)
    if not query_embedding:
        return None

    query_numbers = _extract_numbers(query)
    ttl_seconds = config.CACHE_TTL_HOURS * 3600
    now = time.time()

    best_match = None
    best_similarity = 0.0

    for entry in _cache:
        # Check TTL
        if now - entry["timestamp"] > ttl_seconds:
            continue

        # Date / Number Mismatch check: if queries have different numbers (e.g. 7/2/25 vs 8/2/25), skip match
        cached_numbers = _extract_numbers(entry["query"])
        if query_numbers != cached_numbers:
            continue

        similarity = _cosine_similarity(query_embedding, entry["embedding"])
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = entry

    if best_match and best_similarity >= config.CACHE_SIMILARITY_THRESHOLD:
        logger.info(
            f"Cache HIT (similarity={best_similarity:.3f}): "
            f"'{query[:50]}...' matched '{best_match['query'][:50]}...'"
        )
        return {
            "answer": best_match["answer"],
            "sources": best_match.get("sources", []),
            "source_type": best_match.get("source_type", "cached"),
            "confidence_score": best_match.get("confidence_score", 0.0),
            "cached": True,
            "cache_similarity": best_similarity,
        }

    return None


def store(
    query: str,
    answer: str,
    sources: list[dict] = None,
    source_type: str = "internal",
    confidence_score: float = 0.0,
):
    """
    Store a query-response pair in the cache.
    Refusals and error messages are NEVER stored in cache.
    """
    if not config.CACHE_ENABLED:
        return

    # CRITICAL RULE: Never cache refusals, empty answers, or error/fallback messages
    skip_phrases = [
        config.GUARDRAIL_REFUSAL_MESSAGE,
        "could not find information",
        "sorry",
        "⚠️",           # Fallback error prefix
        "rate-limited",  # Model rate limit message
        "unavailable",   # Generic unavailable message
        "try again",     # Retry suggestion
    ]
    if not answer or any(phrase.lower() in answer.lower() for phrase in skip_phrases):
        logger.info(f"Cache SKIP: Error/refusal answer not cached for '{query[:40]}'")
        return

    query_embedding = _embed_for_cache(query)
    if not query_embedding:
        return

    entry = {
        "query": query,
        "embedding": query_embedding,
        "answer": answer,
        "sources": sources or [],
        "source_type": source_type,
        "confidence_score": confidence_score,
        "timestamp": time.time(),
    }

    _cache.append(entry)

    if len(_cache) > 500:
        _cache.sort(key=lambda x: x["timestamp"])
        del _cache[:100]

    logger.debug(f"Cached response for: '{query[:50]}...' (cache size: {len(_cache)})")


def clear():
    """Clear the entire cache."""
    global _cache
    _cache = []
    logger.info("Semantic cache cleared")


def get_stats() -> dict:
    """Return cache statistics."""
    ttl_seconds = config.CACHE_TTL_HOURS * 3600
    now = time.time()
    active = sum(1 for e in _cache if now - e["timestamp"] <= ttl_seconds)
    return {
        "total_entries": len(_cache),
        "active_entries": active,
        "expired_entries": len(_cache) - active,
    }
