# API Reference

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/chat/completions` | POST | Chat completion (OpenAI compatible) |
| `/v1/batch/chat/completions` | POST | Batch multiple requests |
| `/v1/models` | GET | List available models |
| `/status` | GET | Conductor and rate limit status |
| `/health` | GET | Health check |

---

## POST /v1/chat/completions

OpenAI-compatible chat completion endpoint.

### Request Body

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `messages` | array | ✓ | - | List of message objects |
| `model` | string | | `llama-70b` | Model to use (unified name) |
| `temperature` | float | | 0.7 | Sampling temperature (0-2) |
| `max_tokens` | int | | 1024 | Maximum tokens to generate |
| `top_p` | float | | 1.0 | Nucleus sampling (0-1) |
| `stop` | array | | null | Stop sequences |
| `provider` | string | | null | Force specific provider: `"cerebras"` or `"nvidia"` |

### Message Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `role` | string | ✓ | `"system"`, `"user"`, or `"assistant"` |
| `content` | string | ✓ | Message content |

### Response

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "llama-3.3-70b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 8,
    "total_tokens": 18
  },
  "provider": "cerebras",
  "provider_key_name": "my-cerebras"
}
```

### Example

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama-70b",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Hello!"}
    ],
    "max_tokens": 100
  }'
```

---

## POST /v1/batch/chat/completions

Submit multiple requests at once for parallel processing.

### Request Body

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `requests` | array | ✓ | - | List of chat completion requests |
| `wait_for_all` | bool | | true | Wait for all to complete |

### Response

```json
{
  "responses": [
    { /* ChatCompletionResponse */ },
    { /* ChatCompletionResponse */ }
  ],
  "failed": [
    {"index": 2, "error": "Error message"}
  ],
  "total_time_ms": 1234.5
}
```

### Example

```bash
curl -X POST http://localhost:8000/v1/batch/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "requests": [
      {"model": "llama-70b", "messages": [{"role": "user", "content": "Q1"}]},
      {"model": "llama-70b", "messages": [{"role": "user", "content": "Q2"}]}
    ]
  }'
```

---

## GET /v1/models

List all available unified model names.

### Response

```json
{
  "data": [
    {"id": "llama-70b", "object": "model"},
    {"id": "llama-8b", "object": "model"},
    {"id": "llama-3.3-70b", "object": "model"},
    {"id": "llama-3.1-8b", "object": "model"},
    {"id": "llama-3.1-70b", "object": "model"}
  ],
  "object": "list",
  "default_model": "llama-70b"
}
```

---

## GET /status

Get conductor status and rate limit information.

### Response

```json
{
  "status": "running",
  "total_providers": 2,
  "total_keys": 3,
  "available_keys": 3,
  "scheduling_strategy": "round_robin",
  "pending_requests": 0,
  "providers": [
    {
      "provider": "cerebras",
      "key_name": "cerebras-main",
      "requests_remaining": 995,
      "tokens_remaining": 998000,
      "requests_per_minute": 1000,
      "tokens_per_minute": 1000000,
      "reset_at": "2024-01-01T12:01:00Z",
      "is_available": true
    },
    {
      "provider": "nvidia",
      "key_name": "nvidia-main",
      "requests_remaining": 58,
      "tokens_remaining": 95000,
      "requests_per_minute": 60,
      "tokens_per_minute": 100000,
      "reset_at": "2024-01-01T12:01:00Z",
      "is_available": true
    }
  ]
}
```

---

## GET /health

Simple health check endpoint.

### Response

```json
{
  "status": "healthy",
  "service": "trainforge-conductor"
}
```

---

## Error Responses

### 503 Service Unavailable

```json
{
  "detail": "No providers configured. Add API keys to config/config.yaml"
}
```

### 504 Gateway Timeout

```json
{
  "detail": "Request timed out waiting for available capacity"
}
```

### 500 Internal Server Error

```json
{
  "detail": "Error message from provider"
}
```

