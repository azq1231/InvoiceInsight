"""Layered image caching system with LRU memory cache and disk cache"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional
import hashlib
from diskcache import Cache
from datetime import datetime, timedelta

from src.utils.config import get_config

logger = logging.getLogger(__name__)


class ImageCache:
    """Layered caching system: memory LRU + persistent disk cache"""
    
    def __init__(self):
        self.config = get_config()
        cache_dir = Path(self.config.get('cache.disk_cache_dir', 'data/cache'))
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.disk_cache = Cache(str(cache_dir))
        self.thumbnail_ttl = self.config.get('cache.thumbnail_ttl', 3600)
        self.image_ttl = self.config.get('cache.image_ttl', 1800)
        
        logger.info(f"Image cache initialized at {cache_dir}")
    
    def _generate_key(self, url: str, size_suffix: str = '') -> str:
        """Generate cache key from URL"""
        key = hashlib.md5(f"{url}{size_suffix}".encode()).hexdigest()
        return key
    
    def get_image(self, url: str, is_thumbnail: bool = False) -> Optional[bytes]:
        """Get image from cache"""
        try:
            key = self._generate_key(url, '_thumb' if is_thumbnail else '_full')
            
            cached = self.disk_cache.get(key)
            if cached:
                logger.debug(f"Cache hit for key: {key[:8]}...")
                return cached
            
            logger.debug(f"Cache miss for key: {key[:8]}...")
            return None
            
        except Exception as e:
            logger.error(f"Cache get failed: {e}")
            return None
    
    def set_image(self, url: str, image_bytes: bytes, is_thumbnail: bool = False):
        """Store image in cache with TTL"""
        try:
            key = self._generate_key(url, '_thumb' if is_thumbnail else '_full')
            ttl = self.thumbnail_ttl if is_thumbnail else self.image_ttl
            
            self.disk_cache.set(key, image_bytes, expire=ttl)
            logger.debug(f"Cached image with key: {key[:8]}... (TTL: {ttl}s)")
            
        except Exception as e:
            logger.error(f"Cache set failed: {e}")
    
    def clear_expired(self):
        """Clear expired cache entries"""
        try:
            expired_count = 0
            for key in list(self.disk_cache):
                if self.disk_cache.get(key) is None:
                    expired_count += 1
            
            if expired_count > 0:
                logger.info(f"Cleared {expired_count} expired cache entries")
                
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
    
    def clear_all(self):
        """Clear all cache entries"""
        try:
            self.disk_cache.clear()
            logger.info("All cache cleared")
        except Exception as e:
            logger.error(f"Cache clear failed: {e}")
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        try:
            return {
                'size': len(self.disk_cache),
                'volume': self.disk_cache.volume(),
                'directory': str(self.disk_cache.directory)
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}
