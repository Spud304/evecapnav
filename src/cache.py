"""Backwards-compat shim.

Cache module moved to `src.repositories.intel_cache_repository` in
Phase D of the layered restructure. Keeping the old import path so
`src.tasks`, `src.routes`, and `tests/seeds/build_cache.py` (which
imports the underscore-prefixed helpers `_cache_path` and
`_init_cache_db`) continue to work through Phase G.
"""

from src.stores.intel_cache_store import (  # noqa: F401
    _DANGER_CACHE_TTL,
    _cache_path,
    _danger_cache,
    _danger_cache_time,
    _get_meta,
    _init_cache_db,
    _initialized_paths,
    _invalidate_danger_cache,
    _save_esi_table,
    _set_meta,
    is_esi_cache_stale,
    load_cached_safe_spots,
    load_danger_data,
    load_sovereignty,
    load_zkill_stats,
    mark_esi_updated,
    save_cached_safe_spots,
    save_esi_activity,
    save_esi_jumps,
    save_esi_kills,
    save_sovereignty,
    save_zkill_stats,
)
