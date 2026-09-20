import json
from functools import lru_cache

from .config import MENUS_FILE
from .models import Restaurant


@lru_cache
def load_restaurants() -> list[Restaurant]:
    if not MENUS_FILE.exists():
        return []
    raw = json.loads(MENUS_FILE.read_text(encoding="utf-8"))
    return [Restaurant(**r) for r in raw.get("restaurants", [])]


def reload_restaurants() -> list[Restaurant]:
    load_restaurants.cache_clear()
    return load_restaurants()
