"""TrainForgeConductor - Multi-Provider LLM API Conductor."""

import asyncio
from contextlib import asynccontextmanager
import time
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.config import settings, load_config
from app.models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    BatchRequest,
    BatchResponse,
    ConductorStatus,
)
from app.scheduler import Scheduler, SchedulingStrategy
from app.providers import (
    CerebrasProvider,
    NvidiaProvider,
    GroqProvider,
    GeminiProvider,
    MistralProvider,
    OpenRouterProvider,
    DeepSeekProvider,
    HuggingFaceProvider,
    CohereProvider,
    SambaNovaProvider,
)
from app.providers.base import ProviderKey
from app.rate_limiter import RateLimitBucket
from app.models_mapping import ModelMapper, DEFAULT_MODEL
from app.exceptions import (
    AllProvidersExhaustedError,
    MaxRetriesExhaustedError,
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer() if settings.log_level == "DEBUG" else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Global scheduler instance
scheduler: Optional[Scheduler] = None
model_mapper: Optional[ModelMapper] = None

# Provider definition table — add new providers here only
PROVIDER_DEFINITIONS = [
    {
        "name": "cerebras",
        "class": CerebrasProvider,
        "default_base_url": "https://api.cerebras.ai/v1",
        "default_rpm": 1000,
        "default_tpm": 1_000_000,
    },
    {
        "name": "nvidia",
        "class": NvidiaProvider,
        "default_base_url": "https://integrate.api.nvidia.com/v1",
        "default_rpm": 60,
        "default_tpm": 100_000,
    },
    {
        "name": "groq",
        "class": GroqProvider,
        "default_base_url": "https://api.groq.com/openai/v1",
        "default_rpm": 30,
        "default_tpm": 6_000,
    },
    {
        "name": "gemini",
        "class": GeminiProvider,
        "default_base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_rpm": 15,
        "default_tpm": 1_000_000,
    },
    {
        "name": "mistral",
        "class": MistralProvider,
        "default_base_url": "https://api.mistral.ai/v1",
        "default_rpm": 60,
        "default_tpm": 100_000,
    },
    {
        "name": "openrouter",
        "class": OpenRouterProvider,
        "default_base_url": "https://openrouter.ai/api/v1",
        "default_rpm": 60,
        "default_tpm": 100_000,
    },
    {
        "name": "deepseek",
        "class": DeepSeekProvider,
        "default_base_url": "https://api.deepseek.com/v1",
        "default_rpm": 60,
        "default_tpm": 100_000,
    },
    {
        "name": "huggingface",
        "class": HuggingFaceProvider,
        "default_base_url": "https://api-inference.huggingface.co/v1",
        "default_rpm": 30,
        "default_tpm": 50_000,
    },
    {
        "name": "cohere",
        "class": CohereProvider,
        "default_base_url": "https://api.cohere.com/compatibility/v1",
        "default_rpm": 20,
        "default_tpm": 100_000,
    },
    {
        "name": "sambanova",
        "class": SambaNovaProvider,
        "default_base_url": "https://api.sambanova.ai/v1",
        "default_rpm": 60,
        "default_tpm": 100_000,
    },
]


async def initialize_scheduler(config: dict) -> Scheduler:
    """Initialize the scheduler with providers from config."""
    global model_mapper

    conductor_config = config.get("conductor", {})
    strategy = SchedulingStrategy(
        conductor_config.get("scheduling_strategy", "round_robin")
    )

    # Initialize model mapper with custom mappings from config
    custom_models = config.get("models", {})
    model_mapper = ModelMapper(custom_models)

    await logger.ainfo(
        "Model mapper initialized",
        available_models=model_mapper.get_available_models()
    )

    sched = Scheduler(strategy=strategy)
    providers_config = config.get("providers", {})

    # Initialize all providers from the definition table
    for definition in PROVIDER_DEFINITIONS:
        name = definition["name"]
        provider_config = providers_config.get(name, {})

        if not provider_config.get("enabled", False):
            continue
        if not provider_config.get("keys"):
            continue

        provider = definition["class"](
            base_url=provider_config.get("base_url", definition["default_base_url"]),
            model_mapper=model_mapper,
        )

        for i, key_config in enumerate(provider_config.get("keys", [])):
            key_name = key_config.get("name", f"{name}-key-{i+1}")
            bucket = RateLimitBucket(
                name=f"{name}:{key_name}",
                requests_per_minute=key_config.get("requests_per_minute", definition["default_rpm"]),
                tokens_per_minute=key_config.get("tokens_per_minute", definition["default_tpm"]),
            )
            provider_key = ProviderKey(
                provider_name=name,
                key_name=key_name,
                api_key=key_config["api_key"],
                bucket=bucket,
                base_url=provider.base_url,
            )
            provider.add_key(provider_key)

        if provider.keys:
            await sched.add_provider(provider)
            await logger.ainfo(
                f"{name.upper()} provider initialized",
                keys_count=len(provider.keys)
            )

    await sched.start()
    return sched


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global scheduler

    await logger.ainfo("Starting TrainForgeConductor...")

    config = load_config(settings.config_path)
    await logger.ainfo("Configuration loaded", config_path=settings.config_path)

    scheduler = await initialize_scheduler(config)

    if not scheduler.providers:
        await logger.awarning(
            "No providers configured! Add API keys to config/config.yaml"
        )

    await logger.ainfo(
        "TrainForgeConductor ready",
        providers=list(scheduler.providers.keys()),
    )

    yield

    await logger.ainfo("Shutting down TrainForgeConductor...")
    if scheduler:
        await scheduler.stop()


# Create FastAPI app
app = FastAPI(
    title="TrainForgeConductor",
    description="Multi-Provider LLM API Conductor with intelligent rate limit scheduling",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "trainforge-conductor"}


@app.get("/status", response_model=ConductorStatus)
async def get_status():
    """Get conductor status including all provider rate limits."""
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    status = await scheduler.get_status()

    from app.models import ProviderStatus
    provider_statuses = [
        ProviderStatus(
            provider=p["provider"],
            key_name=p["key_name"],
            requests_remaining=p["requests_remaining"],
            tokens_remaining=p["tokens_remaining"],
            requests_per_minute=p["requests_per_minute"],
            tokens_per_minute=p["tokens_per_minute"],
            reset_at=p["reset_at"],
            is_exhausted=p.get("is_exhausted", False),
            exhausted_at=p.get("exhausted_at"),
            is_available=p["is_available"],
        )
        for p in status["providers"]
    ]

    return ConductorStatus(
        status=status["status"],
        total_providers=status["total_providers"],
        total_keys=status["total_keys"],
        available_keys=status["available_keys"],
        providers=provider_statuses,
        pending_requests=status["pending_requests"],
        scheduling_strategy=status["strategy"],
    )


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completion(request: ChatCompletionRequest):
    """
    OpenAI-compatible chat completion endpoint.

    Use unified model names like "llama-70b" or "llama-8b" - the conductor
    will automatically translate to the correct provider-specific name.

    The conductor routes requests to available providers based on rate limits
    and the configured scheduling strategy.

    Optional fields:
    - model: Model to use (default: llama-70b). Use unified names.
    - provider: Force a specific provider (e.g., "cerebras" or "nvidia")
    - priority: Request priority (0-10, higher = more priority)
    - auto_retry: Automatically retry on failures with exponential backoff (default: true).
    - max_retries: Maximum number of retry attempts when auto_retry is enabled (default: 10).
    """
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    if not scheduler.providers:
        raise HTTPException(
            status_code=503,
            detail="No providers configured. Add API keys to config/config.yaml"
        )

    try:
        response = await scheduler.submit(request, wait=True)
        return response
    except MaxRetriesExhaustedError as e:
        await logger.aerror(
            "Auto-retry exhausted",
            total_attempts=e.total_attempts,
            total_duration_seconds=e.total_duration_seconds,
            retry_log_entries=len(e.retry_log),
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": "max_retries_exhausted",
                "message": str(e),
                "total_attempts": e.total_attempts,
                "total_duration_seconds": round(e.total_duration_seconds, 2),
                "retry_log": e.retry_log,
            },
        )
    except AllProvidersExhaustedError as e:
        await logger.aerror(
            "All providers exhausted",
            error_count=len(e.errors),
            errors=[str(err) for err in e.errors],
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": "all_providers_exhausted",
                "message": "All providers failed to process request",
                "provider_errors": [
                    {
                        "provider": err.provider,
                        "message": err.message,
                        "status_code": getattr(err, 'status_code', None),
                        "type": type(err).__name__,
                    }
                    for err in e.errors
                ],
            }
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail={
                "error": "timeout",
                "message": "Request timed out waiting for available capacity",
            }
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "runtime_error",
                "message": str(e),
            }
        )
    except Exception as e:
        await logger.aerror("Chat completion failed", error=str(e), error_type=type(e).__name__)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": str(e),
            }
        )


@app.post("/v1/batch/chat/completions", response_model=BatchResponse)
async def batch_chat_completion(batch: BatchRequest):
    """
    Submit a batch of chat completion requests.

    All requests will be scheduled across available providers
    to maximize throughput while respecting rate limits.
    """
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    if not scheduler.providers:
        raise HTTPException(
            status_code=503,
            detail="No providers configured. Add API keys to config/config.yaml"
        )

    start_time = time.time()

    tasks = [
        scheduler.submit(req, wait=True)
        for req in batch.requests
    ]

    responses: list[ChatCompletionResponse] = []
    failed: list[dict] = []

    if batch.wait_for_all:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed.append({"index": i, "error": str(result)})
            else:
                responses.append(result)
    else:
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            try:
                result = await coro
                responses.append(result)
            except Exception as e:
                failed.append({"index": i, "error": str(e)})

    elapsed_ms = (time.time() - start_time) * 1000

    return BatchResponse(
        responses=responses,
        failed=failed,
        total_time_ms=elapsed_ms,
    )


@app.get("/v1/models")
async def list_models():
    """
    List all available unified model names.

    These are the model names you can use in requests.
    The conductor automatically translates them to provider-specific names.
    """
    if not model_mapper:
        raise HTTPException(status_code=503, detail="Model mapper not initialized")

    models = []
    for unified_name in model_mapper.get_available_models():
        models.append({
            "id": unified_name,
            "object": "model",
        })

    return {
        "data": models,
        "object": "list",
        "default_model": DEFAULT_MODEL,
    }


def main():
    """Entry point for the conductor."""
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()