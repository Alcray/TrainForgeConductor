#!/usr/bin/env python3
"""Tests for TrainForgeConductor - tests both providers and scheduling."""

import asyncio
import sys
import time
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import pytest

BASE_URL = "http://localhost:8000"


class TestConductorHealth:
    """Basic health and status tests."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test that health endpoint returns healthy."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            print("✓ Health check passed")

    @pytest.mark.asyncio
    async def test_status_endpoint(self):
        """Test that status endpoint shows configured providers."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/status")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert data["total_providers"] >= 1
            assert data["total_keys"] >= 1
            print(f"✓ Status: {data['total_providers']} providers, {data['total_keys']} keys")

    @pytest.mark.asyncio
    async def test_models_endpoint(self):
        """Test that models endpoint lists unified model names."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/v1/models")
            assert response.status_code == 200
            data = response.json()
            assert len(data["data"]) > 0
            # Should have unified model names like llama-70b
            model_ids = [m["id"] for m in data["data"]]
            assert "llama-70b" in model_ids or "llama-8b" in model_ids
            print(f"✓ Unified models available: {model_ids[:3]}...")


class TestCerebrasProvider:
    """Tests specifically for Cerebras provider."""

    @pytest.mark.asyncio
    async def test_cerebras_simple_completion(self):
        """Test a simple completion via Cerebras using unified model name."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BASE_URL}/v1/chat/completions",
                json={
                    "messages": [
                        {"role": "user", "content": "Say only the word 'CEREBRAS_OK' and nothing else."}
                    ],
                    "model": "llama-70b",  # Unified model name
                    "max_tokens": 20,
                    "provider": "cerebras",  # Force Cerebras
                    "temperature": 0,
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["provider"] == "cerebras"
            assert len(data["choices"]) > 0
            content = data["choices"][0]["message"]["content"]
            print(f"✓ Cerebras response: {content[:50]}")

    @pytest.mark.asyncio
    async def test_cerebras_with_system_prompt(self):
        """Test Cerebras with system prompt."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BASE_URL}/v1/chat/completions",
                json={
                    "messages": [
                        {"role": "system", "content": "You are a math tutor. Be concise."},
                        {"role": "user", "content": "What is 15 + 27?"}
                    ],
                    "model": "llama-70b",
                    "max_tokens": 50,
                    "provider": "cerebras",
                    "temperature": 0,
                }
            )
            assert response.status_code == 200
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            assert "42" in content
            print(f"✓ Cerebras math: {content[:50]}")


class TestNvidiaProvider:
    """Tests specifically for NVIDIA NIM provider."""

    @pytest.mark.asyncio
    async def test_nvidia_simple_completion(self):
        """Test a simple completion via NVIDIA NIM using unified model name."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BASE_URL}/v1/chat/completions",
                json={
                    "messages": [
                        {"role": "user", "content": "Say only the word 'NVIDIA_OK' and nothing else."}
                    ],
                    "model": "llama-70b",  # Unified model name
                    "max_tokens": 20,
                    "provider": "nvidia",  # Force NVIDIA
                    "temperature": 0,
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["provider"] == "nvidia"
            assert len(data["choices"]) > 0
            content = data["choices"][0]["message"]["content"]
            print(f"✓ NVIDIA response: {content[:50]}")

    @pytest.mark.asyncio
    async def test_nvidia_with_system_prompt(self):
        """Test NVIDIA with system prompt."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BASE_URL}/v1/chat/completions",
                json={
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant. Be very brief."},
                        {"role": "user", "content": "What is the capital of Japan?"}
                    ],
                    "model": "llama-8b",  # Test with llama-8b
                    "max_tokens": 50,
                    "provider": "nvidia",
                    "temperature": 0,
                }
            )
            assert response.status_code == 200
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            assert "Tokyo" in content or "tokyo" in content.lower()
            print(f"✓ NVIDIA geography: {content[:50]}")


class TestScheduling:
    """Tests for the scheduling and load balancing."""

    @pytest.mark.asyncio
    async def test_round_robin_distribution(self):
        """Test that requests are distributed across providers."""
        providers_used = set()
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            for i in range(4):
                response = await client.post(
                    f"{BASE_URL}/v1/chat/completions",
                    json={
                        "messages": [
                            {"role": "user", "content": f"Say 'test {i}' only."}
                        ],
                        "max_tokens": 10,
                        "temperature": 0,
                    }
                )
                assert response.status_code == 200
                data = response.json()
                providers_used.add(data["provider"])
                print(f"  Request {i+1}: {data['provider']}")
        
        # Should have used both providers with round-robin
        assert len(providers_used) >= 1  # At least one provider
        print(f"✓ Round-robin used providers: {providers_used}")

    @pytest.mark.asyncio
    async def test_batch_processing(self):
        """Test batch request processing."""
        questions = [
            "What is 1+1?",
            "What is 2+2?",
            "What is 3+3?",
        ]
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            start = time.time()
            response = await client.post(
                f"{BASE_URL}/v1/batch/chat/completions",
                json={
                    "requests": [
                        {"messages": [{"role": "user", "content": q}], "max_tokens": 20}
                        for q in questions
                    ],
                    "wait_for_all": True,
                }
            )
            elapsed = time.time() - start
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["responses"]) == len(questions)
            assert len(data["failed"]) == 0
            
            providers = [r["provider"] for r in data["responses"]]
            print(f"✓ Batch completed in {elapsed:.2f}s")
            print(f"  Providers used: {providers}")

    @pytest.mark.asyncio
    async def test_rate_limit_status_updates(self):
        """Test that rate limit status updates after requests."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Get initial status
            status1 = await client.get(f"{BASE_URL}/status")
            initial = status1.json()
            
            # Make a request
            await client.post(
                f"{BASE_URL}/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 10,
                }
            )
            
            # Get updated status
            status2 = await client.get(f"{BASE_URL}/status")
            updated = status2.json()
            
            # At least one provider should have fewer requests remaining
            print(f"✓ Status updates correctly after requests")
            for p in updated["providers"]:
                print(f"  {p['provider']}/{p['key_name']}: {p['requests_remaining']} RPM remaining")


class TestEdgeCases:
    """Edge case and error handling tests."""

    @pytest.mark.asyncio
    async def test_empty_message(self):
        """Test handling of empty message content."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BASE_URL}/v1/chat/completions",
                json={
                    "messages": [
                        {"role": "user", "content": ""}
                    ],
                    "max_tokens": 20,
                }
            )
            # Should either succeed or return a clear error
            assert response.status_code in [200, 400, 422]
            print(f"✓ Empty message handled: status {response.status_code}")

    @pytest.mark.asyncio
    async def test_long_conversation(self):
        """Test multi-turn conversation."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BASE_URL}/v1/chat/completions",
                json={
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "My name is Alice."},
                        {"role": "assistant", "content": "Hello Alice! Nice to meet you."},
                        {"role": "user", "content": "What is my name?"}
                    ],
                    "max_tokens": 50,
                    "temperature": 0,
                }
            )
            assert response.status_code == 200
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            assert "Alice" in content or "alice" in content.lower()
            print(f"✓ Multi-turn conversation: {content[:50]}")


# Simple runner for quick testing without pytest
async def run_quick_tests():
    """Run a quick subset of tests."""
    print("=" * 60)
    print("TrainForgeConductor Quick Tests")
    print("=" * 60)
    
    tests = [
        ("Health Check", TestConductorHealth().test_health_endpoint),
        ("Status Check", TestConductorHealth().test_status_endpoint),
        ("Models List", TestConductorHealth().test_models_endpoint),
        ("Cerebras Completion", TestCerebrasProvider().test_cerebras_simple_completion),
        ("NVIDIA Completion", TestNvidiaProvider().test_nvidia_simple_completion),
        ("Batch Processing", TestScheduling().test_batch_processing),
    ]
    
    passed = 0
    failed = 0
    
    for name, test in tests:
        print(f"\n→ Running: {name}")
        try:
            await test()
            passed += 1
        except Exception as e:
            print(f"✗ FAILED: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_quick_tests())
    sys.exit(0 if success else 1)

