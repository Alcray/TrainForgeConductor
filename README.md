<p align="center">
  <img src="assets/banner.png" alt="TrainForgeConductor" width="600">
</p>

<h1 align="center">🚂 TrainForgeConductor</h1>

<p align="center">
  <strong>Multiply your LLM rate limits by routing across multiple providers</strong>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> •
  <a href="docs/integrations.md">Integrations</a> •
  <a href="docs/api-reference.md">API Reference</a> •
  <a href="docs/configuration.md">Configuration</a>
</p>

---

## Why TrainForgeConductor?

| Without Conductor | With Conductor |
|-------------------|----------------|
| 1 provider, 1 rate limit | Combined rate limits from ALL providers |
| Provider down = you're down | Automatic failover to other providers |
| Different APIs per provider | One unified API for everything |

**Example:** Cerebras (30 RPM) + NVIDIA (40 RPM) = **70 requests/minute** 🚀

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/yourusername/TrainForgeConductor.git
cd TrainForgeConductor

python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Configure

```bash
cp config/config.example.yaml config/config.yaml
```

Add your API keys to `config/config.yaml`:

```yaml
providers:
  cerebras:
    enabled: true
    keys:
      - name: my-cerebras
        api_key: YOUR_CEREBRAS_KEY    # Get from https://cloud.cerebras.ai
        requests_per_minute: 30
        tokens_per_minute: 60000

  nvidia:
    enabled: true
    keys:
      - name: my-nvidia
        api_key: YOUR_NVIDIA_KEY      # Get from https://build.nvidia.com
        requests_per_minute: 40
        tokens_per_minute: 100000
```

### 3. Run

```bash
trainforge-conductor
```

### 4. Use

```python
from examples.client import ConductorClient

client = ConductorClient()

# Simple chat - automatically routes to available provider
response = client.chat("Hello!")
print(response)

# With system prompt
response = client.chat("Write a haiku", system="You are a poet")

# Batch multiple questions at once
answers = client.batch([
    "What is Python?",
    "What is JavaScript?",
    "What is Rust?"
])
```

That's it! The conductor automatically distributes requests across Cerebras and NVIDIA.

---

## Unified Model Names

Use simple names that work on **all providers**:

| Model | Description |
|-------|-------------|
| `llama-70b` | Llama 3.3 70B *(default, best quality)* |
| `llama-8b` | Llama 3.1 8B *(faster)* |

Configure custom model names in `config/config.yaml`:

```yaml
models:
  my-model:
    cerebras: "llama-3.3-70b"
    nvidia: "meta/llama-3.3-70b-instruct"
```

See [Configuration docs](docs/configuration.md#custom-model-names) for more details.

---

## How It Works

```
Your App                    TrainForgeConductor                 Providers
   │                              │                                │
   │  POST /v1/chat/completions   │                                │
   │  model: "llama-70b"          │                                │
   │─────────────────────────────▶│                                │
   │                              │   Round-robin scheduling       │
   │                              │──────────────────────────────▶ │ Cerebras (30 RPM)
   │                              │                                │
   │                              │──────────────────────────────▶ │ NVIDIA (40 RPM)
   │                              │                                │
   │◀─────────────────────────────│   Combined: 70 RPM!            │
```

---

## Rate Limits

| Provider | Requests/min | Tokens/min | Get API Key |
|----------|-------------|------------|-------------|
| Cerebras | 30 | 60,000 | [cloud.cerebras.ai](https://cloud.cerebras.ai) |
| NVIDIA NIM | 40 | 100,000 | [build.nvidia.com](https://build.nvidia.com) |

**Tip:** Add multiple API keys to multiply your limits!

---

## Documentation

| Document | Description |
|----------|-------------|
| [**Integrations**](docs/integrations.md) | Python, JavaScript, curl, OpenAI SDK |
| [**API Reference**](docs/api-reference.md) | All endpoints and parameters |
| [**Configuration**](docs/configuration.md) | Config options, model mapping, strategies |
| [**Docker**](docs/docker.md) | Container deployment |

---

## License

MIT
