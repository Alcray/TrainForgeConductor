"""Pydantic models for API requests and responses."""

from typing import Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class Message(BaseModel):
    """Chat message."""
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""
    messages: list[Message]
    model: Optional[str] = None  # If None, uses provider's default
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=1024, ge=1)
    top_p: float = Field(default=1.0, ge=0, le=1)
    stream: bool = False
    stop: Optional[list[str]] = None
    
    # Conductor-specific fields
    provider: Optional[str] = None  # Force specific provider
    priority: int = Field(default=0, ge=0, le=10)  # Higher = more priority


class ChatCompletionChoice(BaseModel):
    """A single completion choice."""
    index: int
    message: Message
    finish_reason: str


class Usage(BaseModel):
    """Token usage information."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: Usage
    
    # Conductor metadata
    provider: str
    provider_key_name: Optional[str] = None


class BatchRequest(BaseModel):
    """Batch of chat completion requests."""
    requests: list[ChatCompletionRequest]
    wait_for_all: bool = True  # Wait for all to complete before returning


class BatchResponse(BaseModel):
    """Response for batch requests."""
    responses: list[ChatCompletionResponse]
    failed: list[dict] = []  # Failed requests with error info
    total_time_ms: float


class ProviderStatus(BaseModel):
    """Status of a provider key."""
    provider: str
    key_name: str
    requests_remaining: int
    tokens_remaining: int
    requests_per_minute: int
    tokens_per_minute: int
    reset_at: datetime
    is_available: bool


class ConductorStatus(BaseModel):
    """Overall conductor status."""
    status: str
    total_providers: int
    total_keys: int
    available_keys: int
    providers: list[ProviderStatus]
    pending_requests: int
    scheduling_strategy: str

