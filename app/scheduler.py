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
from app.exceptions import (
    ProviderError,
    RateLimitError,
    CapabilityError,
    ProviderUnavailableError,
    AllProvidersExhaustedError,
    MaxRetriesExhaustedError,
)

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
        
        When auto_retry is enabled (default), the conductor automatically retries
        on transient failures (rate limits, provider unavailability) with exponential
        backoff, up to max_retries attempts. The user gets either a successful
        response or a MaxRetriesExhaustedError with a full retry log.
        
        When auto_retry is disabled, behavior is unchanged: try immediately, then
        queue the request and wait for capacity.
        """
        estimated_tokens = self._estimate_tokens(request)
        
        if request.auto_retry:
            return await self._submit_with_retry(
                request, estimated_tokens, request.max_retries,
            )
        else:
            return await self._submit_no_retry(request, estimated_tokens, wait)
    
    async def _submit_with_retry(
        self,
        request: ChatCompletionRequest,
        estimated_tokens: int,
        max_retries: int,
    ) -> ChatCompletionResponse:
        """
        Submit with persistent auto-retry on failures.
        
        Retries with exponential backoff (2s, 4s, 8s, ... capped at 30s).
        Early-terminates if all errors are non-retryable (e.g. CapabilityError).
        Returns the response with retry_count set on success.
        Raises MaxRetriesExhaustedError with full retry log on exhaustion.
        """
        retry_log: list[dict] = []
        start_time = datetime.now()
        
        for attempt in range(max_retries + 1):
            try:
                result = await self._try_immediate_execution(request, estimated_tokens)
                
                if result is not None:
                    # Success — stamp the retry count and return
                    result.retry_count = attempt
                    if attempt > 0:
                        await logger.ainfo(
                            "Request succeeded after retries",
                            retry_count=attempt,
                            total_duration=(datetime.now() - start_time).total_seconds(),
                        )
                    return result
                
                # No capacity available (all keys rate-limited, no errors)
                if attempt >= max_retries:
                    raise MaxRetriesExhaustedError(
                        retry_log=retry_log,
                        total_attempts=attempt + 1,
                        total_duration_seconds=(datetime.now() - start_time).total_seconds(),
                    )
                
                backoff = min(2 ** (attempt + 1), 30)
                retry_log.append({
                    "attempt": attempt + 1,
                    "timestamp": datetime.now().isoformat(),
                    "error_type": "no_capacity",
                    "error_message": "No provider capacity available, waiting for rate limits to reset",
                    "provider_errors": [],
                    "wait_seconds": backoff,
                })
                
                await logger.awarning(
                    "No capacity available, auto-retrying",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    backoff_seconds=backoff,
                )
                await asyncio.sleep(backoff)
                
            except AllProvidersExhaustedError as e:
                # Check for early termination: if every error is a CapabilityError
                # (permanent, not transient), retrying will never help.
                all_capability = (
                    e.errors
                    and all(isinstance(err, CapabilityError) for err in e.errors)
                )
                
                if attempt >= max_retries or all_capability:
                    duration = (datetime.now() - start_time).total_seconds()
                    # Log the final failed attempt before raising
                    retry_log.append({
                        "attempt": attempt + 1,
                        "timestamp": datetime.now().isoformat(),
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "provider_errors": [
                            {
                                "provider": err.provider,
                                "type": type(err).__name__,
                                "message": err.message,
                            }
                            for err in e.errors
                        ],
                        "wait_seconds": 0,
                    })
                    raise MaxRetriesExhaustedError(
                        retry_log=retry_log,
                        total_attempts=attempt + 1,
                        total_duration_seconds=duration,
                        final_error=e,
                    )
                
                # Compute backoff, respecting retry-after from rate limit errors
                base_backoff = min(2 ** (attempt + 1), 30)
                retry_after_hint = max(
                    (
                        getattr(err, "retry_after", None) or 0
                        for err in e.errors
                        if isinstance(err, RateLimitError)
                    ),
                    default=0,
                )
                backoff = max(base_backoff, retry_after_hint)
                # Still cap the backoff at a reasonable ceiling
                backoff = min(backoff, 60)
                
                retry_log.append({
                    "attempt": attempt + 1,
                    "timestamp": datetime.now().isoformat(),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "provider_errors": [
                        {
                            "provider": err.provider,
                            "type": type(err).__name__,
                            "message": err.message,
                        }
                        for err in e.errors
                    ],
                    "wait_seconds": backoff,
                })
                
                await logger.awarning(
                    "All providers exhausted, auto-retrying",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    backoff_seconds=backoff,
                    errors=[str(err) for err in e.errors],
                )
                await asyncio.sleep(backoff)
            
            except MaxRetriesExhaustedError:
                raise
        
        # Safety net — should not normally be reached
        raise MaxRetriesExhaustedError(
            retry_log=retry_log,
            total_attempts=max_retries + 1,
            total_duration_seconds=(datetime.now() - start_time).total_seconds(),
        )
    
    async def _submit_no_retry(
        self,
        request: ChatCompletionRequest,
        estimated_tokens: int,
        wait: bool = True,
    ) -> ChatCompletionResponse:
        """
        Original submit behavior: try immediately, then queue.
        
        Used when auto_retry is disabled.
        """
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
        """
        Try to execute a request immediately if capacity available.
        
        On retryable errors (429, capability issues), tries next provider.
        Returns None if no capacity available (will be queued).
        Raises AllProvidersExhaustedError if all providers failed.
        """
        tried_providers: set[str] = set()
        errors: list[ProviderError] = []
        
        while True:
            provider, key = await self._select_provider_and_key(
                estimated_tokens,
                preferred_provider=request.provider,
                exclude_providers=tried_providers,
            )
            
            if not provider or not key:
                # No more providers available
                if errors:
                    # We tried some providers and they all failed
                    raise AllProvidersExhaustedError(errors)
                # No capacity available at all, return None to queue
                return None
            
            tried_providers.add(f"{provider.name}:{key.key_name}")
            
            if not await key.acquire(estimated_tokens):
                # This key doesn't have capacity, try next
                continue
            
            try:
                return await provider.chat_completion(key, request)
                
            except RateLimitError as e:
                # Mark key as exhausted and try next provider
                await key.bucket.mark_exhausted()
                errors.append(e)
                await logger.awarning(
                    "Rate limit hit, trying next provider",
                    provider=provider.name,
                    key=key.key_name,
                    error=str(e),
                )
                continue
                
            except CapabilityError as e:
                # This provider can't handle this request, try next
                errors.append(e)
                await logger.awarning(
                    "Capability error, trying next provider",
                    provider=provider.name,
                    capability=e.capability,
                    error=str(e),
                )
                continue
                
            except ProviderUnavailableError as e:
                # Provider is down, try next
                errors.append(e)
                await logger.awarning(
                    "Provider unavailable, trying next",
                    provider=provider.name,
                    error=str(e),
                )
                continue
                
            except Exception as e:
                # Unknown error - log it and try next provider
                await logger.aerror(
                    "Unexpected error, trying next provider",
                    provider=provider.name,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                errors.append(ProviderError(
                    message=str(e),
                    provider=provider.name,
                    retryable=True,
                ))
                continue
    
    async def _execute_request(self, pending: PendingRequest) -> ChatCompletionResponse:
        """
        Execute a pending request, waiting for capacity if needed.
        
        Retries with different providers on retryable errors.
        """
        max_wait_attempts = 30  # Max times to wait for capacity (30 seconds)
        wait_attempt = 0
        errors: list[ProviderError] = []
        
        while wait_attempt < max_wait_attempts:
            tried_providers: set[str] = set()
            
            # Try all available providers
            while True:
                provider, key = await self._select_provider_and_key(
                    pending.estimated_tokens,
                    preferred_provider=pending.preferred_provider,
                    exclude_providers=tried_providers,
                )
                
                if not provider or not key:
                    # No more providers to try right now
                    break
                
                tried_providers.add(f"{provider.name}:{key.key_name}")
                
                if not await key.acquire(pending.estimated_tokens):
                    continue
                
                try:
                    return await provider.chat_completion(key, pending.request)
                    
                except RateLimitError as e:
                    await key.bucket.mark_exhausted()
                    errors.append(e)
                    await logger.awarning(
                        "Rate limit hit on queued request, trying next provider",
                        provider=provider.name,
                        key=key.key_name,
                    )
                    continue
                    
                except CapabilityError as e:
                    errors.append(e)
                    await logger.awarning(
                        "Capability error on queued request, trying next provider",
                        provider=provider.name,
                        capability=e.capability,
                    )
                    continue
                    
                except ProviderUnavailableError as e:
                    errors.append(e)
                    await logger.awarning(
                        "Provider unavailable for queued request, trying next",
                        provider=provider.name,
                    )
                    continue
                    
                except Exception as e:
                    await logger.aerror(
                        "Unexpected error on queued request",
                        provider=provider.name,
                        error=str(e),
                    )
                    errors.append(ProviderError(
                        message=str(e),
                        provider=provider.name,
                        retryable=True,
                    ))
                    continue
            
            # All providers tried, wait for capacity to free up
            wait_attempt += 1
            await asyncio.sleep(1.0)
        
        # All attempts exhausted
        if errors:
            raise AllProvidersExhaustedError(errors)
        raise RuntimeError("Failed to execute request: no providers available")
    
    async def _select_provider_and_key(
        self,
        estimated_tokens: int,
        preferred_provider: Optional[str] = None,
        exclude_providers: Optional[set[str]] = None,
    ) -> tuple[Optional[BaseProvider], Optional[ProviderKey]]:
        """
        Select a provider and key based on the scheduling strategy.
        
        Args:
            estimated_tokens: Estimated tokens for the request
            preferred_provider: Force a specific provider if specified
            exclude_providers: Set of "provider:key" strings to skip (already tried)
        """
        exclude_providers = exclude_providers or set()
        
        # If a specific provider is requested
        if preferred_provider and preferred_provider in self.providers:
            provider = self.providers[preferred_provider]
            key = await provider.get_available_key(estimated_tokens, exclude_providers)
            if key:
                return provider, key
            return None, None
        
        if self.strategy == SchedulingStrategy.ROUND_ROBIN:
            return await self._select_round_robin(estimated_tokens, exclude_providers)
        elif self.strategy == SchedulingStrategy.LEAST_LOADED:
            return await self._select_least_loaded(estimated_tokens, exclude_providers)
        elif self.strategy == SchedulingStrategy.SEQUENTIAL:
            return await self._select_sequential(estimated_tokens, exclude_providers)
        
        return None, None
    
    async def _select_round_robin(
        self,
        estimated_tokens: int,
        exclude_providers: Optional[set[str]] = None,
    ) -> tuple[Optional[BaseProvider], Optional[ProviderKey]]:
        """Round-robin selection across providers."""
        exclude_providers = exclude_providers or set()
        provider_names = list(self.providers.keys())
        if not provider_names:
            return None, None
        
        # Try each provider starting from current index
        for i in range(len(provider_names)):
            idx = (self._current_provider_index + i) % len(provider_names)
            provider = self.providers[provider_names[idx]]
            key = await provider.get_available_key(estimated_tokens, exclude_providers)
            
            if key:
                self._current_provider_index = (idx + 1) % len(provider_names)
                return provider, key
        
        return None, None
    
    async def _select_least_loaded(
        self,
        estimated_tokens: int,
        exclude_providers: Optional[set[str]] = None,
    ) -> tuple[Optional[BaseProvider], Optional[ProviderKey]]:
        """Select the provider/key with the most remaining capacity."""
        exclude_providers = exclude_providers or set()
        best_provider = None
        best_key = None
        best_capacity = -1
        
        for provider in self.providers.values():
            for key in provider.keys:
                # Skip excluded provider:key combinations
                if f"{provider.name}:{key.key_name}" in exclude_providers:
                    continue
                    
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
        exclude_providers: Optional[set[str]] = None,
    ) -> tuple[Optional[BaseProvider], Optional[ProviderKey]]:
        """Use providers sequentially (fill one before moving to next)."""
        exclude_providers = exclude_providers or set()
        for provider in self.providers.values():
            key = await provider.get_available_key(estimated_tokens, exclude_providers)
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

