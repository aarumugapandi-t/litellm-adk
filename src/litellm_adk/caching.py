import litellm
import os
from typing import Optional
from .observability.logger import adk_logger

class CacheManager:
    """
    Production-grade caching module utilizing LiteLLM's native caching 
    with Redis / Dragonfly backends.
    """
    
    @classmethod
    def enable_redis_cache(cls, 
                           host: str = "127.0.0.1", 
                           port: int = 6379, 
                           password: Optional[str] = None, 
                           semantic: bool = False,
                           ttl: int = 3600):
        """
        Enables exact-match or semantic caching using Redis.
        Dragonfly is fully compatible with the Redis protocol and can be 
        used interchangeably via this method.
        """
        adk_logger.info(f"Enabling {'Semantic' if semantic else 'Exact'} Redis/Dragonfly cache at {host}:{port}")
        
        cache_type = "redis-semantic" if semantic else "redis"
        
        kwargs = {}
        if semantic:
            kwargs["similarity_threshold"] = 0.8
            # litellm's RedisSemanticCache strictly requires a password or REDIS_PASSWORD env var.
            # Empty strings evaluate to false in `password or os.environ["REDIS_PASSWORD"]`
            # so we must inject it directly into the environment if it's missing.
            os.environ.setdefault("REDIS_PASSWORD", "")
            
        litellm.cache = litellm.Cache(
            type=cache_type,
            host=host,
            port=port,
            password=password,
            ttl=ttl,
            **kwargs
        )
        
    @classmethod
    def disable_cache(cls):
        """Disables global litellm caching."""
        litellm.cache = None
        adk_logger.info("Global cache disabled.")
