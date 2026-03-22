import json
import os
import tempfile

CACHE_FILE = os.path.join(tempfile.gettempdir(), "noteforge_cache.json")

# Load once into memory at startup — no repeated disk reads
_cache: dict = {}
_loaded = False


def _ensure_loaded():
    global _cache, _loaded
    if not _loaded:
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    _cache = json.load(f)
            except Exception:
                _cache = {}
        _loaded = True


def get_from_cache(key):
    _ensure_loaded()
    return _cache.get(key)


def set_cache(key, value):
    _ensure_loaded()
    _cache[key] = value
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_cache, f, indent=2)
    except Exception:
        pass