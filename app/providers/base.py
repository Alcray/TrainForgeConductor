"""Base provider abstraction."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import httpx
import structlog

from app.models import ChatCompletionRequest, ChatCompletionResponse
from app.rate_limiter import RateLimitBucket
from app.models_mapping import ModelMapper

logger = structlog.get_logger()


@dataclass
class ProviderKey:
    """A single API key with its rate limit bucket."""
    
    provider_name: str
    key_name: str
    api_key: str
    bucket: RateLimitBucket
    base_url: str
    
    async def is_available(self, estimated_tokens: int = 100) -> bool:
        """Check if this key is available for a request."""
        return await self.bucket.can_acquire(estimated_tokens)
    
    async def acquire(self, estimated_tokens: int = 100) -> bool:
        """Acquire a request slot."""
        return await self.bucket.acquire(estimated_tokens)
    
    def get_status(self) -> dict:
        """Get status including provider info."""
        status = self.bucket.get_status()
        status["provider"] = self.provider_name
        status["key_name"] = self.key_name
        return status


class BaseProvider(ABC):
    """Base class for LLM providers."""
    
    name: str = "base"
    
    def __init__(self, base_url: str, model_mapper: ModelMapper = None):
        self.base_url = base_url
        self.keys: list[ProviderKey] = []
        self._current_key_index = 0
        self._client: Optional[httpx.AsyncClient] = None
        self.model_mapper = model_mapper or ModelMapper()
    
    async def get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def add_key(self, key: ProviderKey) -> None:
        """Add an API key to this provider."""
        self.keys.append(key)
    
    async def get_available_key(self, estimated_tokens: int = 100) -> Optional[ProviderKey]:
        """Get an available key using round-robin with fallback."""
        if not self.keys:
            return None
        
        # Try starting from current index
        for i in range(len(self.keys)):
            idx = (self._current_key_index + i) % len(self.keys)
            key = self.keys[idx]
            if await key.is_available(estimated_tokens):
                self._current_key_index = (idx + 1) % len(self.keys)
                return key
        
        return None
    
    def has_available_keys(self) -> bool:
        """Check if any keys are potentially available."""
        return len(self.keys) > 0
    
    def get_all_keys_status(self) -> list[dict]:
        """Get status of all keys."""
        return [key.get_status() for key in self.keys]
    
    def get_model_name(self, request_model: Optional[str]) -> str:
        """
        Get the provider-specific model name.
        
        Uses the model mapper to translate unified names like "llama-70b"
        to provider-specific names like "llama-3.3-70b" or "meta/llama-3.3-70b-instruct".
        """
        return self.model_mapper.get_provider_model(request_model, self.name)
    
    @abstractmethod
    async def chat_completion(
        self,
        key: ProviderKey,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Execute a chat completion request."""
        pass
    
    def estimate_tokens(self, request: ChatCompletionRequest) -> int:
        """Estimate token count for a request (rough approximation)."""
        # Rough estimation: 4 characters per token
        total_chars = sum(len(m.content) for m in request.messages)
        return max(100, total_chars // 4)
