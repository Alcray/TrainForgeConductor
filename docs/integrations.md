# Integrations

## Python Client (Recommended)

The easiest way to use TrainForgeConductor:

```python
from examples.client import ConductorClient

client = ConductorClient()

# Simple chat
response = client.chat("Hello!")
print(response)

# With system prompt
response = client.chat("Write a poem", system="You are a poet")

# Specify model
response = client.chat("Hello!", model="llama-8b")

# Force specific provider
response = client.chat("Hello!", provider="cerebras")

# Batch multiple prompts (distributed across providers)
answers = client.batch([
    "What is Python?",
    "What is JavaScript?",
    "What is Rust?"
])
for answer in answers:
    print(answer)

# Check rate limit status
status = client.status()
print(f"Available keys: {status['available_keys']}")
```

---

## OpenAI SDK

TrainForgeConductor is **OpenAI API compatible**. Just change the base URL:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed"  # Conductor handles auth
)

response = client.chat.completions.create(
    model="llama-70b",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ],
    max_tokens=100
)

print(response.choices[0].message.content)
```

---

## Using requests

```python
import requests

response = requests.post(
    "http://localhost:8000/v1/chat/completions",
    json={
        "model": "llama-70b",
        "messages": [{"role": "user", "content": "Hello!"}]
    }
)

data = response.json()
print(data["choices"][0]["message"]["content"])
print(f"Provider used: {data['provider']}")
```

---

## Async with httpx

```python
import asyncio
import httpx

async def chat(message: str) -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "http://localhost:8000/v1/chat/completions",
            json={
                "model": "llama-70b",
                "messages": [{"role": "user", "content": message}]
            }
        )
        return response.json()["choices"][0]["message"]["content"]

result = asyncio.run(chat("Hello!"))
print(result)
```

---

## JavaScript / Node.js

### OpenAI SDK

```javascript
import OpenAI from 'openai';

const client = new OpenAI({
  baseURL: 'http://localhost:8000/v1',
  apiKey: 'not-needed'
});

const response = await client.chat.completions.create({
  model: 'llama-70b',
  messages: [{ role: 'user', content: 'Hello!' }]
});

console.log(response.choices[0].message.content);
```

### Using fetch

```javascript
const response = await fetch('http://localhost:8000/v1/chat/completions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: 'llama-70b',
    messages: [{ role: 'user', content: 'Hello!' }]
  })
});

const data = await response.json();
console.log(data.choices[0].message.content);
console.log(`Provider: ${data.provider}`);
```

---

## curl

### Simple request

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama-70b",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### With system prompt

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama-70b",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is Python?"}
    ],
    "max_tokens": 500
  }'
```

### Force specific provider

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama-70b",
    "messages": [{"role": "user", "content": "Hello!"}],
    "provider": "cerebras"
  }'
```

### Check status

```bash
curl http://localhost:8000/status | jq
```

### List models

```bash
curl http://localhost:8000/v1/models | jq
```

---

## Batch Processing

Send multiple requests at once for maximum throughput:

### Python

```python
import requests

response = requests.post(
    "http://localhost:8000/v1/batch/chat/completions",
    json={
        "requests": [
            {"model": "llama-70b", "messages": [{"role": "user", "content": "What is Python?"}]},
            {"model": "llama-70b", "messages": [{"role": "user", "content": "What is JavaScript?"}]},
            {"model": "llama-70b", "messages": [{"role": "user", "content": "What is Rust?"}]},
        ],
        "wait_for_all": True
    }
)

data = response.json()
print(f"Completed in {data['total_time_ms']:.0f}ms")

for r in data["responses"]:
    print(f"[{r['provider']}]: {r['choices'][0]['message']['content'][:50]}...")
```

### curl

```bash
curl -X POST http://localhost:8000/v1/batch/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "requests": [
      {"model": "llama-70b", "messages": [{"role": "user", "content": "Q1"}]},
      {"model": "llama-70b", "messages": [{"role": "user", "content": "Q2"}]}
    ],
    "wait_for_all": true
  }'
```

---

## LangChain

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed",
    model="llama-70b"
)

response = llm.invoke("Hello!")
print(response.content)
```

---

## LlamaIndex

```python
from llama_index.llms.openai_like import OpenAILike

llm = OpenAILike(
    api_base="http://localhost:8000/v1",
    api_key="not-needed",
    model="llama-70b"
)

response = llm.complete("Hello!")
print(response.text)
```
