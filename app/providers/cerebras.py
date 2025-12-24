"""Cerebras provider implementation."""

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

logger = structlog.get_logger()


class CerebrasProvider(BaseProvider):
    """Cerebras AI provider."""
    
    name = "cerebras"
    
    def __init__(self, base_url: str = "https://api.cerebras.ai/v1", model_mapper: ModelMapper = None):
        super().__init__(base_url, model_mapper)
    
    async def chat_completion(
        self,
        key: ProviderKey,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Execute chat completion via Cerebras API."""
        
        # Translate unified model name to Cerebras-specific name
        model = self.get_model_name(request.model)
        
        # Prepare request payload
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
            "Sending request to Cerebras",
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
                id=data.get("id", f"cerebras-{int(time.time())}"),
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
            await logger.aerror(
                "Cerebras API error",
                status_code=e.response.status_code,
                response=e.response.text,
            )
            raise
        except Exception as e:
            await logger.aerror("Cerebras request failed", error=str(e))
            raise
