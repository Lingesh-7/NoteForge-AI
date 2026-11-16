import json
import os
import tempfile
import threading

CACHE_FILE = os.path.join(tempfile.gettempdir(), "noteforge_cache.json")

# Oldest entries are dropped past this size so a long-running deployment
# doesn't grow the cache without bound.
MAX_ENTRIES = 500

_cache: dict = {}
_loaded = False
_lock = threading.Lock()  # Streamlit serves concurrent users as threads in one
                           # process, so guard the shared in-memory cache + file.


def _ensure_loaded():
    global _cache, _loaded
    if not _loaded:
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                _cache = data if isinstance(data, dict) else {}
            except Exception:
                _cache = {}
        _loaded = True


def get_from_cache(key):
    with _lock:
        _ensure_loaded()
        return _cache.get(key)


def set_cache(key, value):
    with _lock:
        _ensure_loaded()
        _cache.pop(key, None)  # re-insert so the key counts as newest
        _cache[key] = value
        while len(_cache) > MAX_ENTRIES:
            _cache.pop(next(iter(_cache)))
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(_cache, f)
        except Exception:
            pass  # the cache is an optimisation; never fail a run over it
