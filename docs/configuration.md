# Configuration

Configuration is managed through `config/config.yaml`.

## Quick Setup

```bash
cp config/config.example.yaml config/config.yaml
# Edit config/config.yaml with your API keys
```

---

## Full Configuration Example

```yaml
conductor:
  scheduling_strategy: round_robin  # round_robin | least_loaded | sequential
  request_timeout: 120
  max_retries: 3
  retry_delay: 1.0

# Custom model mappings (optional)
models:
  my-model:
    cerebras: "llama-3.3-70b"
    nvidia: "meta/llama-3.3-70b-instruct"

providers:
  cerebras:
    enabled: true
    base_url: https://api.cerebras.ai/v1
    keys:
      - name: account-1
        api_key: csk-xxxxx
        requests_per_minute: 30
        tokens_per_minute: 60000
      - name: account-2          # Multiple keys = more capacity!
        api_key: csk-yyyyy
        requests_per_minute: 30
        tokens_per_minute: 60000

  nvidia:
    enabled: true
    base_url: https://integrate.api.nvidia.com/v1
    keys:
      - name: nvidia-main
        api_key: nvapi-xxxxx
        requests_per_minute: 40
        tokens_per_minute: 100000
```

---

## Custom Model Names

Define your own model aliases in `config/config.yaml`:

```yaml
models:
  # Short aliases
  fast:
    cerebras: "llama3.1-8b"
    nvidia: "meta/llama-3.1-8b-instruct"
  
  smart:
    cerebras: "llama-3.3-70b"
    nvidia: "meta/llama-3.3-70b-instruct"
  
  # Or any custom name you want
  my-production-model:
    cerebras: "llama-3.3-70b"
    nvidia: "meta/llama-3.3-70b-instruct"
```

Then use your custom names in requests:

```python
from examples.client import ConductorClient

client = ConductorClient()

# Use your custom model name
response = client.chat("Hello!", model="fast")
response = client.chat("Complex question", model="smart")
```

---

## Built-in Model Mappings

These work out of the box without any configuration:

| Unified Name | Cerebras | NVIDIA |
|-------------|----------|--------|
| `llama-70b` | `llama-3.3-70b` | `meta/llama-3.3-70b-instruct` |
| `llama-8b` | `llama3.1-8b` | `meta/llama-3.1-8b-instruct` |
| `llama-3.3-70b` | `llama-3.3-70b` | `meta/llama-3.3-70b-instruct` |
| `llama-3.1-8b` | `llama3.1-8b` | `meta/llama-3.1-8b-instruct` |
| `llama-3.1-70b` | `llama-3.1-70b` | `meta/llama-3.1-70b-instruct` |

---

## Scheduling Strategies

| Strategy | Behavior | Best For |
|----------|----------|----------|
| `round_robin` | Alternates between providers | Balanced load (default) |
| `least_loaded` | Uses provider with most remaining capacity | Maximum throughput |
| `sequential` | Fills one provider before moving to next | Cost optimization |

### round_robin (default)

```
Request 1 → Cerebras
Request 2 → NVIDIA
Request 3 → Cerebras
Request 4 → NVIDIA
...
```

### least_loaded

Picks the provider/key with the most remaining requests and tokens.

### sequential

Uses Cerebras until rate limited, then switches to NVIDIA.

---

## Multiple API Keys

Add multiple keys per provider to multiply your rate limits:

```yaml
providers:
  cerebras:
    keys:
      - name: account-1
        api_key: KEY_1
        requests_per_minute: 30    # 30 RPM
      - name: account-2
        api_key: KEY_2
        requests_per_minute: 30    # +30 RPM
      # Total: 60 RPM from Cerebras alone!
```

---

## Environment Variables

Override config with environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CONDUCTOR_HOST` | `0.0.0.0` | Server host |
| `CONDUCTOR_PORT` | `8000` | Server port |
| `CONDUCTOR_LOG_LEVEL` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `CONDUCTOR_CONFIG_PATH` | `./config/config.yaml` | Config file path |

---

## Rate Limits Reference

### Cerebras

| Model | Requests/min | Tokens/min | Context |
|-------|-------------|------------|---------|
| llama-3.3-70b | 30 | 64,000 | 65,536 |
| llama3.1-8b | 30 | 60,000 | 8,192 |
| qwen-3-32b | 30 | 64,000 | 65,536 |

**Hourly limits:** 900 requests, 1M tokens  
**Daily limits:** 14,400 requests, 1M tokens

Get your key: https://cloud.cerebras.ai/

### NVIDIA NIM

| Limit | Value |
|-------|-------|
| Requests/min | 40 |
| Tokens/min | ~100,000 |

Get your key: https://build.nvidia.com/
