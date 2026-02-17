"""NVIDIA NIM provider implementation."""

import time
import httpx
import structlog

from app.models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    Message,
    Usage,
)
from app.providers.base import BaseProvider, ProviderKey
from app.models_mapping import ModelMapper
from app.exceptions import (
    RateLimitError,
    CapabilityError,
    ProviderUnavailableError,
)

logger = structlog.get_logger()


class NvidiaProvider(BaseProvider):
    """NVIDIA NIM provider (via build.nvidia.com or self-hosted)."""
    
    name = "nvidia"
    
    def __init__(self, base_url: str = "https://integrate.api.nvidia.com/v1", model_mapper: ModelMapper = None):
        super().__init__(base_url, model_mapper)
    
    async def chat_completion(
        self,
        key: ProviderKey,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Execute chat completion via NVIDIA NIM API."""
        
        # Translate unified model name to NVIDIA-specific name
        model = self.get_model_name(request.model)
        
        # Prepare request payload (OpenAI-compatible)
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
        }
        
        if request.stop:
            payload["stop"] = request.stop
        
        headers = {
            "Authorization": f"Bearer {key.api_key}",
            "Content-Type": "application/json",
        }
        
        client = await self.get_client()
        
        await logger.ainfo(
            "Sending request to NVIDIA NIM",
            model=model,
            key_name=key.key_name,
            messages_count=len(request.messages),
        )
        
        try:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            
            # Parse response
            choice = data["choices"][0]
            usage = data.get("usage", {})
            
            # Update token consumption
            total_tokens = usage.get("total_tokens", 0)
            if total_tokens > 0:
                await key.bucket.consume_tokens(total_tokens)
            
            return ChatCompletionResponse(
                id=data.get("id", f"nvidia-{int(time.time())}"),
                created=data.get("created", int(time.time())),
                model=model,
                choices=[
                    ChatCompletionChoice(
                        index=0,
                        message=Message(
                            role="assistant",
                            content=choice["message"]["content"],
                        ),
                        finish_reason=choice.get("finish_reason", "stop"),
                    )
                ],
                usage=Usage(
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                ),
                provider=self.name,
                provider_key_name=key.key_name,
            )
            
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            response_text = e.response.text
            
            await logger.aerror(
                "NVIDIA NIM API error",
                status_code=status_code,
                response=response_text,
                key_name=key.key_name,
            )
            
            # Handle rate limit (429)
            if status_code == 429:
                # Try to extract retry-after header
                retry_after = e.response.headers.get("retry-after")
                retry_seconds = float(retry_after) if retry_after else None
                raise RateLimitError(
                    provider=self.name,
                    retry_after=retry_seconds,
                    message=f"Rate limit exceeded: {response_text[:200]}",
                )
            
            # Handle server errors (5xx) - provider temporarily unavailable
            if 500 <= status_code < 600:
                raise ProviderUnavailableError(
                    provider=self.name,
                    status_code=status_code,
                    message=f"NVIDIA server error: {response_text[:200]}",
                )
            
            # Handle capability/validation errors (400)
            if status_code == 400:
                # Check for known capability issues
                response_lower = response_text.lower()
                if "tool" in response_lower or "function" in response_lower:
                    raise CapabilityError(
                        provider=self.name,
                        capability="parallel_tool_calls",
                        message=f"Tool calling error: {response_text[:200]}",
                    )
                if "image" in response_lower or "vision" in response_lower:
                    raise CapabilityError(
                        provider=self.name,
                        capability="vision",
                        message=f"Vision/image error: {response_text[:200]}",
                    )
                # Generic capability error
                raise CapabilityError(
                    provider=self.name,
                    capability="unknown",
                    message=f"Request error: {response_text[:200]}",
                )
            
            # Re-raise other errors
            raise
            
        except httpx.TimeoutException as e:
            await logger.aerror("NVIDIA NIM request timeout", error=str(e))
            raise ProviderUnavailableError(
                provider=self.name,
                status_code=504,
                message=f"Request timeout: {str(e)}",
            )
        except (RateLimitError, CapabilityError, ProviderUnavailableError):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            await logger.aerror("NVIDIA NIM request failed", error=str(e))
            raise
