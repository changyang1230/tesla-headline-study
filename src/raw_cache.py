"""On-disk cache for raw HTTP responses (sitemap XML, Wayback snapshots, article HTML).

Every harvester used to discard the raw response after filtering it in memory — so any
change to the discovery vocabulary (which happened three times in one session: adding
hospitalisation/damage terms, then dropping the outcome requirement entirely) meant
re-fetching everything over the network from scratch, even though the actual bytes
hadn't changed. This module fixes that: check the cache first, fetch only on a miss,
always write what was fetched.

Cache key is the exact URL fetched (sha1 hash for the filename); the raw response bytes
are the value. Not committed to git (data/raw_cache/ is gitignored, same as data/bodies/)
— this is a local performance cache, not a data artefact to redistribute.
"""

from __future__ import annotations

import hashlib
import pathlib

CACHE_ROOT = pathlib.Path("data/raw_cache")


def _cache_path(subdir: str, url: str) -> pathlib.Path:
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return CACHE_ROOT / subdir / f"{key}.cache"


def get(subdir: str, url: str) -> bytes | None:
    """Cached response bytes for this URL, or None on a cache miss."""
    path = _cache_path(subdir, url)
    if path.exists():
        return path.read_bytes()
    return None


def put(subdir: str, url: str, data: bytes) -> None:
    path = _cache_path(subdir, url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
