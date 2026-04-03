import time
import asyncio
import json
from collections import defaultdict

# Global caches and locks
_hunt_cache = defaultdict(list)
_cache_last_updated = 0
_cache_refresh_interval = 15  # seconds
_cache_lock = asyncio.Lock()

_collection_cache = defaultdict(list)
_collection_cache_last_updated = 0
_collection_cache_refresh_interval = 15  # seconds
_collection_cache_lock = asyncio.Lock()

# Load forms.json and prepare mapping
with open("forms.json", "r") as f:
    _forms_mapping = json.load(f)

# Invert mapping: form name → base name
_form_to_base = {}
for base, forms in _forms_mapping.items():
    for form in forms:
        _form_to_base[form] = base


# ------------------------
# Hunt Cache Functions
# ------------------------

async def refresh_hunt_cache(db_instance):
    global _hunt_cache, _cache_last_updated
    async with _cache_lock:
        try:
            rows = await db_instance.fetch("""
                SELECT TRIM(shiny_hunt) AS name, userid
                FROM shusers
                WHERE shinyafk = false
            """)
            temp_cache = defaultdict(list)
            for row in rows:
                name = row["name"]
                if name:
                    temp_cache[name.lower()].append(row["userid"])
            _hunt_cache = temp_cache
            _cache_last_updated = time.time()
        except Exception as e:
            print("❌ DB Cache Refresh Error:", e)


async def get_users_hunting(pokemon_name: str, db_instance):
    now = time.time()
    if now - _cache_last_updated > _cache_refresh_interval:
        await refresh_hunt_cache(db_instance)

    name = pokemon_name.lower()
    user_ids = set(_hunt_cache.get(name, []))

    # If it's a base form, include users hunting all its variants
    if name in _forms_mapping:
        for form in _forms_mapping[name]:
            user_ids.update(_hunt_cache.get(form, []))

    return list(user_ids)


# ------------------------
# Collection Cache Functions
# ------------------------

async def refresh_collection_cache(db_instance):
    global _collection_cache, _collection_cache_last_updated
    async with _collection_cache_lock:
        try:
            rows = await db_instance.fetch("""
                SELECT userid, collection
                FROM shusers
                WHERE colafk = false
            """)
            temp_cache = defaultdict(list)
            for row in rows:
                userid = row["userid"]
                collection = row["collection"]
                if collection:
                    for name in map(str.strip, collection.split(",")):
                        if name:
                            temp_cache[name.lower()].append(userid)
            _collection_cache = temp_cache
            _collection_cache_last_updated = time.time()
        except Exception as e:
            print("❌ Collection Cache Refresh Error:", e)


async def get_users_collecting(pokemon_name: str, db_instance):
    now = time.time()
    if now - _collection_cache_last_updated > _collection_cache_refresh_interval:
        await refresh_collection_cache(db_instance)

    name = pokemon_name.lower()
    user_ids = set(_collection_cache.get(name, []))

    # If it's a base form, include users collecting all its variants
    if name in _forms_mapping:
        for form in _forms_mapping[name]:
            user_ids.update(_collection_cache.get(form, []))

    return list(user_ids)
