import json
import os

CACHE_FILE = "cache.json"


def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    with open(CACHE_FILE, "r") as f:
        return json.load(f)


def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def get_from_cache(key):
    cache = load_cache()
    return cache.get(key)


def set_cache(key, value):
    cache = load_cache()
    cache[key] = value
    save_cache(cache)