"""24-hour on-disk cache for HTTP responses."""
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any

CACHE_DIR = Path(__file__).parent / ".cache" / "psa"
CACHE_TTL_SECONDS = 24 * 3600  # 24 hours


def _cache_key(url: str, params: Optional[Dict[str, Any]] = None) -> str:
    """Generate cache key from URL and params."""
    key_str = url
    if params:
        key_str += json.dumps(params, sort_keys=True)
    return hashlib.sha256(key_str.encode()).hexdigest()


def get_cached(url: str, params: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Retrieve cached response if valid (within TTL)."""
    key = _cache_key(url, params)
    cache_file = CACHE_DIR / key
    
    if not cache_file.exists():
        return None
    
    # Check TTL
    if time.time() - cache_file.stat().st_mtime > CACHE_TTL_SECONDS:
        cache_file.unlink()
        return None
    
    return cache_file.read_text(encoding="utf-8")


def set_cached(url: str, content: str, params: Optional[Dict[str, Any]] = None) -> None:
    """Store response in cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(url, params)
    cache_file = CACHE_DIR / key
    cache_file.write_text(content, encoding="utf-8")


def clear_cache() -> None:
    """Clear all cached files."""
    if CACHE_DIR.exists():
        for cache_file in CACHE_DIR.glob("*"):
            cache_file.unlink()
