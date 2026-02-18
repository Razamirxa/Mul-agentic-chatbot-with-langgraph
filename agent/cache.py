"""Response cache for the MUL chatbot.

Caches query→response pairs so repeated/similar questions get instant
answers without hitting the LLM or Tavily API again.

Features:
  - Normalizes queries (lowercase, strip whitespace/punctuation) for fuzzy matching
  - TTL-based expiration (default: 1 hour)
  - Max size limit with LRU eviction
  - Thread-safe for concurrent requests
  - Cache stats endpoint for monitoring
"""

import re
import time
import threading
from collections import OrderedDict


class ResponseCache:
    """In-memory LRU cache with TTL for chatbot responses."""

    def __init__(self, max_size: int = 500, ttl_seconds: int = 3600):
        """
        Args:
            max_size: Maximum number of cached entries (LRU eviction).
            ttl_seconds: Time-to-live for each entry in seconds (default: 1 hour).
        """
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _normalize(query: str) -> str:
        """Normalize a query for cache key matching.
        
        Lowercases, strips whitespace, removes punctuation so that
        'What programs does MUL offer?' == 'what programs does mul offer'
        """
        q = query.lower().strip()
        q = re.sub(r'[^\w\s]', '', q)      # remove punctuation
        q = re.sub(r'\s+', ' ', q)          # collapse whitespace
        return q

    def get(self, query: str) -> str | None:
        """Look up a cached response. Returns None on miss or expiry."""
        key = self._normalize(query)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            # Check TTL
            if time.time() - entry["timestamp"] > self._ttl:
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return entry["response"]

    def put(self, query: str, response: str) -> None:
        """Store a query→response pair in the cache."""
        key = self._normalize(query)
        with self._lock:
            # Update existing or insert new
            self._cache[key] = {
                "response": response,
                "timestamp": time.time(),
                "original_query": query,
            }
            self._cache.move_to_end(key)

            # Evict oldest if over capacity
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def stats(self) -> dict:
        """Return cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "ttl_seconds": self._ttl,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{(self._hits / total * 100):.1f}%" if total > 0 else "0%",
            }

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0


# ── Singleton cache instance ────────────────────
# 500 entries, 15-minute TTL (keeps fee/admission data fresh)
cache = ResponseCache(max_size=500, ttl_seconds=900)
