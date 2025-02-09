import redis
import json
import logging
from functools import lru_cache
from typing import Any, Dict, Optional
from datetime import timedelta

# הגדרת לוגר
logger = logging.getLogger(__name__)

class CacheManager:
    """מנהל מטמון היברידי המשלב Redis ומטמון בזיכרון"""
    
    def __init__(self, redis_host: str = 'localhost', redis_port: int = 6379):
        """אתחול מנהל המטמון"""
        self._memory_cache: Dict[str, Any] = {}
        try:
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=0,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            # בדיקת חיבור
            self.redis_client.ping()
            logger.info("Successfully connected to Redis")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
        except Exception as e:
            logger.error(f"Unexpected error initializing Redis: {e}")
            self.redis_client = None
        
    @lru_cache(maxsize=1000)
    def get_from_memory(self, key: str) -> Optional[Any]:
        """קבלת ערך ממטמון הזיכרון"""
        if not key:
            logger.warning("Attempted to get from memory with empty key")
            return None
            
        value = self._memory_cache.get(key)
        if value is not None:
            logger.debug(f"Cache hit in memory for key {key}")
            return value
            
        # אם לא נמצא בזיכרון, ננסה להביא מ-Redis
        value = self.get_from_redis(key)
        if value is not None:
            self._memory_cache[key] = value
            
        return value
        
    def get_from_redis(self, key: str) -> Optional[Any]:
        """קבלת ערך ממטמון Redis"""
        if not self.redis_client:
            logger.warning("Redis client not available")
            return None
            
        if not key:
            logger.warning("Attempted to get from Redis with empty key")
            return None
            
        try:
            value = self.redis_client.get(key)
            if value:
                decoded_value = json.loads(value)
                logger.debug(f"Cache hit in Redis for key {key}")
                return decoded_value
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode Redis value for key {key}: {e}")
            return None
        except redis.RedisError as e:
            logger.error(f"Redis error getting key {key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting from Redis: {e}")
            return None
            
    def set_in_cache(self, key: str, value: Any, expire: int = 3600) -> bool:
        """שמירת ערך במטמון"""
        if not key:
            logger.warning("Attempted to set in cache with empty key")
            return False
            
        success = True
        
        try:
            # שמירה בזיכרון
            self._memory_cache[key] = value
            
            # שמירה ב-Redis אם זמין
            if self.redis_client:
                json_value = json.dumps(value)
                self.redis_client.setex(key, expire, json_value)
            else:
                success = False
                
            # ניקוי מטמון הזיכרון של lru_cache
            self.get_from_memory.cache_clear()
            logger.debug(f"Successfully cached value for key {key}")
            
            return success
        except json.JSONEncodeError as e:
            logger.error(f"Failed to encode value for key {key}: {e}")
            return False
        except redis.RedisError as e:
            logger.error(f"Redis error setting key {key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error setting in cache: {e}")
            return False
            
    def invalidate(self, key: str) -> bool:
        """ביטול תוקף ערך במטמון"""
        if not key:
            logger.warning("Attempted to invalidate with empty key")
            return False
            
        success = True
        
        try:
            # מחיקה מהזיכרון
            self._memory_cache.pop(key, None)
            
            # מחיקה מ-Redis אם זמין
            if self.redis_client:
                self.redis_client.delete(key)
            else:
                success = False
                
            # ניקוי מטמון הזיכרון של lru_cache
            self.get_from_memory.cache_clear()
            logger.debug(f"Successfully invalidated key {key}")
            
            return success
        except redis.RedisError as e:
            logger.error(f"Redis error invalidating key {key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error invalidating cache: {e}")
            return False
            
    def get_or_set(self, key: str, callback, expire: int = 3600) -> Any:
        """קבלת ערך מהמטמון או יצירתו אם לא קיים"""
        if not key:
            logger.warning("Attempted get_or_set with empty key")
            return None
            
        try:
            # ניסיון לקבל מהמטמון
            value = self.get_from_memory(key)
            
            if value is None:
                try:
                    # אם לא נמצא, יצירת ערך חדש
                    value = callback()
                    if value is not None:
                        self.set_in_cache(key, value, expire)
                except Exception as e:
                    logger.error(f"Error executing callback for key {key}: {e}")
                    return None
                    
            return value
        except Exception as e:
            logger.error(f"Error in get_or_set for key {key}: {e}")
            return None 