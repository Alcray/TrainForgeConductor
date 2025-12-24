"""Request scheduler for distributing work across providers."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import structlog

from app.models import ChatCompletionRequest, ChatCompletionResponse
from app.providers.base import BaseProvider, ProviderKey
from app.rate_limiter import RateLimiterManager

logger = structlog.get_logger()


class SchedulingStrategy(str, Enum):
    """Available scheduling strategies."""
    ROUND_ROBIN = "round_robin"      # Alternate between providers
    LEAST_LOADED = "least_loaded"    # Pick provider with most capacity
    SEQUENTIAL = "sequential"        # Fill one provider before moving to next


@dataclass
class PendingRequest:
    """A request waiting to be scheduled."""
    request: ChatCompletionRequest
    future: asyncio.Future
    created_at: datetime = field(default_factory=datetime.now)
    estimated_tokens: int = 100
    preferred_provider: Optional[str] = None


class Scheduler:
    """
    Schedules requests across multiple providers based on rate limits.
    
    Supports multiple scheduling strategies and handles retries,
    queueing when rate limited, and load balancing.
    """
    
    def __init__(
        self,
        strategy: SchedulingStrategy = SchedulingStrategy.ROUND_ROBIN,
        max_queue_size: int = 1000,
        max_wait_time: float = 60.0,
    ):
        self.strategy = strategy
        self.max_queue_size = max_queue_size
        self.max_wait_time = max_wait_time
        
        self.providers: dict[str, BaseProvider] = {}
        self.rate_limiter = RateLimiterManager()
        self._queue: asyncio.Queue[PendingRequest] = asyncio.Queue(maxsize=max_queue_size)
        self._current_provider_index = 0
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
        self._lock = asyncio.Lock()
    
    async def add_provider(self, provider: BaseProvider) -> None:
        """Add a provider to the scheduler."""
        async with self._lock:
            self.providers[provider.name] = provider
            await logger.ainfo(
                "Added provider",
                provider=provider.name,
                keys_count=len(provider.keys)
            )
    
    def get_provider(self, name: str) -> Optional[BaseProvider]:
        """Get a provider by name."""
        return self.providers.get(name)
    
    async def start(self) -> None:
        """Start the scheduler worker."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        await logger.ainfo("Scheduler started", strategy=self.strategy.value)
    
    async def stop(self) -> None:
        """Stop the scheduler worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        # Close all provider clients
        for provider in self.providers.values():
            await provider.close()
        await logger.ainfo("Scheduler stopped")
    
    async def _worker_loop(self) -> None:
        """Background worker that processes queued requests."""
        while self._running:
            try:
                # Wait for a request with timeout
                try:
                    pending = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Process the request
                try:
                    result = await self._execute_request(pending)
                    pending.future.set_result(result)
                except Exception as e:
                    pending.future.set_exception(e)
                finally:
                    self._queue.task_done()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                await logger.aerror("Worker error", error=str(e))
    
    async def submit(
        self,
        request: ChatCompletionRequest,
        wait: bool = True,
    ) -> ChatCompletionResponse:
        """
        Submit a request for scheduling.
        
        If wait=True, blocks until the request is completed.
        If wait=False, returns a Future that can be awaited later.
        """
        # Estimate tokens for rate limiting
        estimated_tokens = self._estimate_tokens(request)
        
        # First, try to execute immediately if capacity available
        result = await self._try_immediate_execution(request, estimated_tokens)
        if result:
            return result
        
        # Queue the request for later execution
        loop = asyncio.get_event_loop()
        future: asyncio.Future[ChatCompletionResponse] = loop.create_future()
        
        pending = PendingRequest(
            request=request,
            future=future,
            estimated_tokens=estimated_tokens,
            preferred_provider=request.provider,
        )
        
        try:
            self._queue.put_nowait(pending)
        except asyncio.QueueFull:
            raise RuntimeError("Request queue is full")
        
        if wait:
            return await asyncio.wait_for(future, timeout=self.max_wait_time)
        return await future
    
    async def _try_immediate_execution(
        self,
        request: ChatCompletionRequest,
        estimated_tokens: int,
    ) -> Optional[ChatCompletionResponse]:
        """Try to execute a request immediately if capacity available."""
        provider, key = await self._select_provider_and_key(
            estimated_tokens,
            preferred_provider=request.provider
        )
        
        if provider and key:
            if await key.acquire(estimated_tokens):
                try:
                    return await provider.chat_completion(key, request)
                except Exception as e:
                    await logger.aerror(
                        "Immediate execution failed",
                        provider=provider.name,
                        error=str(e)
                    )
                    raise
        
        return None
    
    async def _execute_request(self, pending: PendingRequest) -> ChatCompletionResponse:
        """Execute a pending request, waiting for capacity if needed."""
        max_attempts = 10
        attempt = 0
        
        while attempt < max_attempts:
            attempt += 1
            
            provider, key = await self._select_provider_and_key(
                pending.estimated_tokens,
                preferred_provider=pending.preferred_provider
            )
            
            if provider and key:
                if await key.acquire(pending.estimated_tokens):
                    try:
                        return await provider.chat_completion(key, pending.request)
                    except Exception as e:
                        await logger.aerror(
                            "Request execution failed",
                            provider=provider.name,
                            error=str(e)
                        )
                        # Don't retry on API errors, just raise
                        raise
            
            # No capacity available, wait a bit
            await asyncio.sleep(1.0)
        
        raise RuntimeError("Failed to execute request after maximum attempts")
    
    async def _select_provider_and_key(
        self,
        estimated_tokens: int,
        preferred_provider: Optional[str] = None,
    ) -> tuple[Optional[BaseProvider], Optional[ProviderKey]]:
        """Select a provider and key based on the scheduling strategy."""
        
        # If a specific provider is requested
        if preferred_provider and preferred_provider in self.providers:
            provider = self.providers[preferred_provider]
            key = await provider.get_available_key(estimated_tokens)
            if key:
                return provider, key
            return None, None
        
        if self.strategy == SchedulingStrategy.ROUND_ROBIN:
            return await self._select_round_robin(estimated_tokens)
        elif self.strategy == SchedulingStrategy.LEAST_LOADED:
            return await self._select_least_loaded(estimated_tokens)
        elif self.strategy == SchedulingStrategy.SEQUENTIAL:
            return await self._select_sequential(estimated_tokens)
        
        return None, None
    
    async def _select_round_robin(
        self,
        estimated_tokens: int,
    ) -> tuple[Optional[BaseProvider], Optional[ProviderKey]]:
        """Round-robin selection across providers."""
        provider_names = list(self.providers.keys())
        if not provider_names:
            return None, None
        
        # Try each provider starting from current index
        for i in range(len(provider_names)):
            idx = (self._current_provider_index + i) % len(provider_names)
            provider = self.providers[provider_names[idx]]
            key = await provider.get_available_key(estimated_tokens)
            
            if key:
                self._current_provider_index = (idx + 1) % len(provider_names)
                return provider, key
        
        return None, None
    
    async def _select_least_loaded(
        self,
        estimated_tokens: int,
    ) -> tuple[Optional[BaseProvider], Optional[ProviderKey]]:
        """Select the provider/key with the most remaining capacity."""
        best_provider = None
        best_key = None
        best_capacity = -1
        
        for provider in self.providers.values():
            for key in provider.keys:
                if await key.is_available(estimated_tokens):
                    # Calculate remaining capacity (prioritize by requests + tokens)
                    capacity = (
                        key.bucket.requests_remaining * 1000 +
                        key.bucket.tokens_remaining
                    )
                    if capacity > best_capacity:
                        best_capacity = capacity
                        best_provider = provider
                        best_key = key
        
        return best_provider, best_key
    
    async def _select_sequential(
        self,
        estimated_tokens: int,
    ) -> tuple[Optional[BaseProvider], Optional[ProviderKey]]:
        """Use providers sequentially (fill one before moving to next)."""
        for provider in self.providers.values():
            key = await provider.get_available_key(estimated_tokens)
            if key:
                return provider, key
        return None, None
    
    def _estimate_tokens(self, request: ChatCompletionRequest) -> int:
        """Estimate token count for a request."""
        # Rough estimation: 4 characters per token + expected output
        total_chars = sum(len(m.content) for m in request.messages)
        input_tokens = max(10, total_chars // 4)
        output_tokens = request.max_tokens or 1024
        return input_tokens + output_tokens // 2  # Assume half max output
    
    @property
    def pending_count(self) -> int:
        """Number of pending requests in queue."""
        return self._queue.qsize()
    
    async def get_status(self) -> dict:
        """Get scheduler status."""
        provider_statuses = []
        total_keys = 0
        available_keys = 0
        
        for provider in self.providers.values():
            for key in provider.keys:
                total_keys += 1
                status = key.get_status()
                provider_statuses.append(status)
                if status["is_available"]:
                    available_keys += 1
        
        return {
            "status": "running" if self._running else "stopped",
            "strategy": self.strategy.value,
            "total_providers": len(self.providers),
            "total_keys": total_keys,
            "available_keys": available_keys,
            "pending_requests": self.pending_count,
            "providers": provider_statuses,
        }

