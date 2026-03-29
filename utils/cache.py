"""
utils/cache.py
==============
Lightweight JSON-backed cache for expensive LLM / search results.

Design notes
------------
- The in-memory dict `_cache` is **process-local**.  In Streamlit, each worker
  process handles one user session, so there is no cross-user contamination.
- Disk persistence means the same topic is not re-researched across page reloads
  or minor API retries.
- All disk I/O is wrapped in try/except so a cache failure is never fatal.
"""

from __future__ import annotations

import json
import os
import tempfile

_CACHE_PATH: str = os.path.join(tempfile.gettempdir(), "noteforge_cache.json")

_cache: dict[str, str] = {}
_loaded: bool = False


def _ensure_loaded() -> None:
    global _cache, _loaded
    if _loaded:
        return
    if os.path.exists(_CACHE_PATH):
        try:
            with open(_CACHE_PATH, encoding="utf-8") as fh:
                _cache = json.load(fh)
        except Exception:
            _cache = {}
    _loaded = True


def get_from_cache(key: str) -> str | None:
    """Return the cached value for *key*, or ``None`` if absent."""
    _ensure_loaded()
    return _cache.get(key)


def set_cache(key: str, value: str) -> None:
    """Store *value* under *key* in memory and flush to disk."""
    _ensure_loaded()
    _cache[key] = value
    try:
        with open(_CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump(_cache, fh, indent=2, ensure_ascii=False)
    except Exception:
        pass  # Cache write failure is non-fatal


def clear_cache() -> None:
    """Wipe the in-memory cache and delete the cache file."""
    global _cache, _loaded
    _cache  = {}
    _loaded = True
    try:
        os.remove(_CACHE_PATH)
    except FileNotFoundError:
        pass