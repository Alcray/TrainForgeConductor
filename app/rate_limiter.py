"""Token bucket rate limiter for managing API rate limits."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import structlog

logger = structlog.get_logger()


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting."""
    
    name: str
    requests_per_minute: int
    tokens_per_minute: int
    
    # Current state
    requests_remaining: int = field(init=False)
    tokens_remaining: int = field(init=False)
    window_start: datetime = field(init=False)
    
    # Lock for thread-safe operations
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    
    def __post_init__(self):
        self.requests_remaining = self.requests_per_minute
        self.tokens_remaining = self.tokens_per_minute
        self.window_start = datetime.now()
    
    async def _maybe_reset_window(self) -> None:
        """Reset the window if a minute has passed."""
        now = datetime.now()
        if now - self.window_start >= timedelta(minutes=1):
            self.requests_remaining = self.requests_per_minute
            self.tokens_remaining = self.tokens_per_minute
            self.window_start = now
            await logger.adebug(
                "Rate limit window reset",
                bucket=self.name,
                requests=self.requests_remaining,
                tokens=self.tokens_remaining
            )
    
    async def can_acquire(self, estimated_tokens: int = 100) -> bool:
        """Check if we can acquire a request slot."""
        async with self._lock:
            await self._maybe_reset_window()
            return (
                self.requests_remaining > 0 and 
                self.tokens_remaining >= estimated_tokens
            )
    
    async def acquire(self, estimated_tokens: int = 100) -> bool:
        """
        Try to acquire a request slot.
        Returns True if acquired, False if rate limited.
        """
        async with self._lock:
            await self._maybe_reset_window()
            
            if self.requests_remaining <= 0:
                await logger.adebug(
                    "Rate limited (requests)",
                    bucket=self.name,
                    remaining=self.requests_remaining
                )
                return False
            
            if self.tokens_remaining < estimated_tokens:
                await logger.adebug(
                    "Rate limited (tokens)",
                    bucket=self.name,
                    remaining=self.tokens_remaining,
                    requested=estimated_tokens
                )
                return False
            
            self.requests_remaining -= 1
            self.tokens_remaining -= estimated_tokens
            return True
    
    async def release_tokens(self, actual_tokens: int, estimated_tokens: int) -> None:
        """
        Adjust token count after actual usage is known.
        This allows us to reclaim tokens if we overestimated.
        """
        async with self._lock:
            diff = estimated_tokens - actual_tokens
            if diff > 0:
                # We overestimated, give back the difference
                self.tokens_remaining = min(
                    self.tokens_remaining + diff,
                    self.tokens_per_minute
                )
    
    async def consume_tokens(self, additional_tokens: int) -> None:
        """Consume additional tokens (e.g., for completion tokens)."""
        async with self._lock:
            self.tokens_remaining = max(0, self.tokens_remaining - additional_tokens)
    
    @property
    def time_until_reset(self) -> timedelta:
        """Time remaining until the rate limit window resets."""
        elapsed = datetime.now() - self.window_start
        remaining = timedelta(minutes=1) - elapsed
        return max(remaining, timedelta(0))
    
    @property
    def reset_at(self) -> datetime:
        """When the rate limit window will reset."""
        return self.window_start + timedelta(minutes=1)
    
    def get_status(self) -> dict:
        """Get current status of the bucket."""
        return {
            "name": self.name,
            "requests_remaining": self.requests_remaining,
            "tokens_remaining": self.tokens_remaining,
            "requests_per_minute": self.requests_per_minute,
            "tokens_per_minute": self.tokens_per_minute,
            "reset_at": self.reset_at,
            "is_available": self.requests_remaining > 0 and self.tokens_remaining > 100,
        }


class RateLimiterManager:
    """Manages multiple rate limit buckets."""
    
    def __init__(self):
        self.buckets: dict[str, RateLimitBucket] = {}
        self._lock = asyncio.Lock()
    
    async def add_bucket(
        self,
        key: str,
        name: str,
        requests_per_minute: int,
        tokens_per_minute: int
    ) -> RateLimitBucket:
        """Add a new rate limit bucket."""
        async with self._lock:
            bucket = RateLimitBucket(
                name=name,
                requests_per_minute=requests_per_minute,
                tokens_per_minute=tokens_per_minute,
            )
            self.buckets[key] = bucket
            return bucket
    
    async def get_bucket(self, key: str) -> Optional[RateLimitBucket]:
        """Get a bucket by key."""
        return self.buckets.get(key)
    
    async def get_available_buckets(self, estimated_tokens: int = 100) -> list[str]:
        """Get keys of all buckets that have capacity."""
        available = []
        for key, bucket in self.buckets.items():
            if await bucket.can_acquire(estimated_tokens):
                available.append(key)
        return available
    
    async def get_all_status(self) -> list[dict]:
        """Get status of all buckets."""
        return [bucket.get_status() for bucket in self.buckets.values()]

