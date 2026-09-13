import time
from typing import Tuple
import redis.asyncio as aioredis
from app.core.config import settings


class UnauthRateLimiter:
    """
    Sliding window rate limiter for unauthenticated guest sessions
    using Redis key TTLs.
    """

    def __init__(self):
        self.redis_client = None

    async def get_redis(self):
        if self.redis_client is None:
            self.redis_client = aioredis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                decode_responses=True,
            )
        return self.redis_client

    async def check_and_consume(
        self, client_id: str, limit: int = None, window_seconds: int = None
    ) -> Tuple[bool, int, int]:
        """
        Checks if client has remaining generations and increments count if allowed.
        Returns: (allowed: bool, remaining: int, reset_in_seconds: int)
        """
        limit = limit or settings.RATE_LIMIT_GENERATIONS_PER_DAY
        window = window_seconds or settings.RATE_LIMIT_WINDOW_SECONDS

        try:
            r = await self.get_redis()
            key = f"rate_limit:unauth:{client_id}"

            current_count = await r.get(key)

            if current_count is None:
                # First generation: initialize counter with TTL
                await r.setex(key, window, 1)
                return True, limit - 1, window

            count = int(current_count)
            ttl = await r.ttl(key)
            if ttl < 0:
                ttl = window

            if count >= limit:
                return False, 0, ttl

            # Increment count
            await r.incr(key)
            return True, limit - (count + 1), ttl

        except Exception as e:
            # If redis is temporarily unavailable in local dev, gracefully allow generation
            print(f"[RateLimiter] Redis warning: {e}")
            return True, 1, 0

    async def get_remaining(
        self, client_id: str, limit: int = None, window_seconds: int = None
    ) -> Tuple[int, int]:
        """
        Query current remaining quota without consuming it.
        """
        limit = limit or settings.RATE_LIMIT_GENERATIONS_PER_DAY
        window = window_seconds or settings.RATE_LIMIT_WINDOW_SECONDS

        try:
            r = await self.get_redis()
            key = f"rate_limit:unauth:{client_id}"
            current_count = await r.get(key)

            if current_count is None:
                return limit, window

            count = int(current_count)
            ttl = await r.ttl(key)
            if ttl < 0:
                ttl = window

            remaining = max(0, limit - count)
            return remaining, ttl
        except Exception:
            return limit, window


rate_limiter = UnauthRateLimiter()
