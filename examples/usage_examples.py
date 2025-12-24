#!/usr/bin/env python3
"""
TrainForgeConductor Usage Examples

Run the conductor first:
    trainforge-conductor

Then run these examples:
    python examples/usage_examples.py
"""

import asyncio


def example_simple_request():
    """Simple request using requests library."""
    print("\n=== Simple Request (requests) ===")
    import requests
    
    response = requests.post(
        "http://localhost:8000/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "Say hello!"}],
            "max_tokens": 50
        }
    )
    
    data = response.json()
    print(f"Provider: {data['provider']}")
    print(f"Response: {data['choices'][0]['message']['content']}")


def example_openai_sdk():
    """Using the OpenAI SDK (recommended)."""
    print("\n=== OpenAI SDK (Recommended) ===")
    from openai import OpenAI
    
    client = OpenAI(
        base_url="http://localhost:8000/v1",
        api_key="not-needed"
    )
    
    response = client.chat.completions.create(
        model="llama-3.3-70b",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the capital of France?"}
        ],
        max_tokens=100
    )
    
    print(f"Response: {response.choices[0].message.content}")


def example_force_provider():
    """Force a specific provider."""
    print("\n=== Force Specific Provider ===")
    import requests
    
    # Force Cerebras
    response = requests.post(
        "http://localhost:8000/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "Hello from Cerebras!"}],
            "provider": "cerebras",
            "max_tokens": 30
        }
    )
    print(f"Cerebras: {response.json()['choices'][0]['message']['content']}")
    
    # Force NVIDIA
    response = requests.post(
        "http://localhost:8000/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "Hello from NVIDIA!"}],
            "provider": "nvidia",
            "max_tokens": 30
        }
    )
    print(f"NVIDIA: {response.json()['choices'][0]['message']['content']}")


def example_batch_requests():
    """Send multiple requests at once."""
    print("\n=== Batch Requests ===")
    import requests
    
    questions = [
        "What is Python?",
        "What is JavaScript?",
        "What is Rust?",
    ]
    
    response = requests.post(
        "http://localhost:8000/v1/batch/chat/completions",
        json={
            "requests": [
                {"messages": [{"role": "user", "content": q}], "max_tokens": 50}
                for q in questions
            ],
            "wait_for_all": True
        }
    )
    
    data = response.json()
    print(f"Completed {len(data['responses'])} requests in {data['total_time_ms']:.0f}ms")
    
    for i, resp in enumerate(data["responses"]):
        content = resp["choices"][0]["message"]["content"]
        print(f"  [{resp['provider']}] Q{i+1}: {content[:60]}...")


def example_check_status():
    """Check conductor status and rate limits."""
    print("\n=== Conductor Status ===")
    import requests
    
    response = requests.get("http://localhost:8000/status")
    data = response.json()
    
    print(f"Status: {data['status']}")
    print(f"Strategy: {data['scheduling_strategy']}")
    print(f"Providers: {data['total_providers']}, Keys: {data['total_keys']}")
    
    print("\nRate Limits:")
    for p in data["providers"]:
        print(f"  {p['provider']}/{p['key_name']}: "
              f"{p['requests_remaining']}/{p['requests_per_minute']} RPM, "
              f"{p['tokens_remaining']:,}/{p['tokens_per_minute']:,} TPM")


async def example_async_requests():
    """Async requests for better performance."""
    print("\n=== Async Requests ===")
    import httpx
    
    async def ask(question: str) -> dict:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "http://localhost:8000/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": question}],
                    "max_tokens": 50
                }
            )
            return response.json()
    
    # Run multiple requests concurrently
    questions = ["What is 1+1?", "What is 2+2?", "What is 3+3?"]
    results = await asyncio.gather(*[ask(q) for q in questions])
    
    for q, r in zip(questions, results):
        answer = r["choices"][0]["message"]["content"]
        print(f"  Q: {q} → A: {answer[:50]}")


def example_conversation():
    """Multi-turn conversation."""
    print("\n=== Multi-turn Conversation ===")
    from openai import OpenAI
    
    client = OpenAI(
        base_url="http://localhost:8000/v1",
        api_key="not-needed"
    )
    
    messages = [
        {"role": "system", "content": "You are a helpful math tutor."},
    ]
    
    # First turn
    messages.append({"role": "user", "content": "What is 5 * 7?"})
    response = client.chat.completions.create(
        model="llama-3.3-70b",
        messages=messages,
        max_tokens=50
    )
    assistant_msg = response.choices[0].message.content
    messages.append({"role": "assistant", "content": assistant_msg})
    print(f"User: What is 5 * 7?")
    print(f"Assistant: {assistant_msg}")
    
    # Second turn
    messages.append({"role": "user", "content": "Now divide that by 5"})
    response = client.chat.completions.create(
        model="llama-3.3-70b", 
        messages=messages,
        max_tokens=50
    )
    print(f"User: Now divide that by 5")
    print(f"Assistant: {response.choices[0].message.content}")


def main():
    print("=" * 60)
    print("TrainForgeConductor Usage Examples")
    print("=" * 60)
    
    try:
        example_check_status()
        example_simple_request()
        example_openai_sdk()
        example_force_provider()
        example_batch_requests()
        asyncio.run(example_async_requests())
        example_conversation()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError: {e}")
        print("Make sure the conductor is running: trainforge-conductor")


if __name__ == "__main__":
    main()

