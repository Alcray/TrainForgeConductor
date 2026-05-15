"""Google Gemini provider implementation."""

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


class GeminiProvider(BaseProvider):
    """Google Gemini provider — free tier available."""

    name = "gemini"

    def __init__(self, base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai", model_mapper: ModelMapper = None):
        super().__init__(base_url, model_mapper)

    async def chat_completion(
        self,
        key: ProviderKey,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Execute chat completion via Gemini API."""

        model = self.get_model_name(request.model)

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
            "Sending request to Gemini",
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

            choice = data["choices"][0]
            usage = data.get("usage", {})

            total_tokens = usage.get("total_tokens", 0)
            if total_tokens > 0:
                await key.bucket.consume_tokens(total_tokens)

            return ChatCompletionResponse(
                id=data.get("id", f"gemini-{int(time.time())}"),
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
                "Gemini API error",
                status_code=status_code,
                response=response_text,
                key_name=key.key_name,
            )

            if status_code == 429:
                retry_after = e.response.headers.get("retry-after")
                retry_seconds = float(retry_after) if retry_after else None
                raise RateLimitError(
                    provider=self.name,
                    retry_after=retry_seconds,
                    message=f"Rate limit exceeded: {response_text[:200]}",
                )

            if 500 <= status_code < 600:
                raise ProviderUnavailableError(
                    provider=self.name,
                    status_code=status_code,
                    message=f"Gemini server error: {response_text[:200]}",
                )

            if status_code == 400:
                response_lower = response_text.lower()
                if "image" in response_lower or "vision" in response_lower:
                    raise CapabilityError(
                        provider=self.name,
                        capability="vision",
                        message=f"Vision not supported: {response_text[:200]}",
                    )
                if "tool" in response_lower or "function" in response_lower:
                    raise CapabilityError(
                        provider=self.name,
                        capability="tool_calls",
                        message=f"Tool calling error: {response_text[:200]}",
                    )
                raise CapabilityError(
                    provider=self.name,
                    capability="unknown",
                    message=f"Request error: {response_text[:200]}",
                )

            raise

        except httpx.TimeoutException as e:
            await logger.aerror("Gemini request timeout", error=str(e))
            raise ProviderUnavailableError(
                provider=self.name,
                status_code=504,
                message=f"Request timeout: {str(e)}",
            )
        except (RateLimitError, CapabilityError, ProviderUnavailableError):
            raise
        except Exception as e:
            await logger.aerror("Gemini request failed", error=str(e))
            raise