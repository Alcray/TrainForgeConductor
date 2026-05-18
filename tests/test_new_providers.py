#!/usr/bin/env python3
"""Integration tests for new providers added in PR #4."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import pytest

BASE_URL = "http://localhost:8000"


class TestGroqProvider:
    """Tests specifically for Groq provider."""

    @pytest.mark.asyncio
    async def test_groq_simple_completion(self):
        """Test a simple completion via Groq using unified model name."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BASE_URL}/v1/chat/completions",
                json={
                    "messages": [
                        {"role": "user", "content": "Say only the word 'GROQ_OK' and nothing else."}
                    ],
                    "model": "llama-70b",
                    "max_tokens": 20,
                    "provider": "groq",
                    "temperature": 0,
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["provider"] == "groq"
            assert len(data["choices"]) > 0
            content = data["choices"][0]["message"]["content"]
            print(f"✔ Groq response: {content[:50]}")

    @pytest.mark.asyncio
    async def test_groq_with_system_prompt(self):
        """Test Groq with system prompt."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BASE_URL}/v1/chat/completions",
                json={
                    "messages": [
                        {"role": "system", "content": "You are a math tutor. Be concise."},
                        {"role": "user", "content": "What is 10 + 32?"}
                    ],
                    "model": "llama-70b",
                    "max_tokens": 50,
                    "provider": "groq",
                    "temperature": 0,
                }
            )
            assert response.status_code == 200
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            assert "42" in content
            print(f"✔ Groq math: {content[:50]}")

    @pytest.mark.asyncio
    async def test_groq_fast_model(self):
        """Test Groq with llama-8b instant model."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BASE_URL}/v1/chat/completions",
                json={
                    "messages": [
                        {"role": "user", "content": "What is the capital of France?"}
                    ],
                    "model": "llama-8b",
                    "max_tokens": 50,
                    "provider": "groq",
                    "temperature": 0,
                }
            )
            assert response.status_code == 200
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            assert "Paris" in content or "paris" in content.lower()
            print(f"✔ Groq fast model: {content[:50]}")


class TestOpenRouterProvider:
    """Tests specifically for OpenRouter provider."""

    @pytest.mark.asyncio
    async def test_openrouter_simple_completion(self):
        """Test a simple completion via OpenRouter using unified model name."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BASE_URL}/v1/chat/completions",
                json={
                    "messages": [
                        {"role": "user", "content": "Say only the word 'OPENROUTER_OK' and nothing else."}
                    ],
                    "model": "llama-70b",
                    "max_tokens": 20,
                    "provider": "openrouter",
                    "temperature": 0,
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["provider"] == "openrouter"
            assert len(data["choices"]) > 0
            content = data["choices"][0]["message"]["content"]
            print(f"✔ OpenRouter response: {content[:50]}")

    @pytest.mark.asyncio
    async def test_openrouter_with_system_prompt(self):
        """Test OpenRouter with system prompt."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BASE_URL}/v1/chat/completions",
                json={
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant. Be very brief."},
                        {"role": "user", "content": "What is the capital of Germany?"}
                    ],
                    "model": "llama-70b",
                    "max_tokens": 50,
                    "provider": "openrouter",
                    "temperature": 0,
                }
            )
            assert response.status_code == 200
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            assert "Berlin" in content or "berlin" in content.lower()
            print(f"✔ OpenRouter geography: {content[:50]}")

    @pytest.mark.asyncio
    async def test_openrouter_free_model(self):
        """Test OpenRouter with a free Gemini model."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BASE_URL}/v1/chat/completions",
                json={
                    "messages": [
                        {"role": "user", "content": "What is 5 + 5?"}
                    ],
                    "model": "gemini-flash",
                    "max_tokens": 20,
                    "provider": "openrouter",
                    "temperature": 0,
                }
            )
            assert response.status_code == 200
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            assert "10" in content
            print(f"✔ OpenRouter Gemini: {content[:50]}")


class TestDeepSeekProvider:
    """Tests specifically for DeepSeek provider."""

    @pytest.mark.asyncio
    async def test_deepseek_simple_completion(self):
        """Test a simple completion via DeepSeek."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BASE_URL}/v1/chat/completions",
                json={
                    "messages": [
                        {"role": "user", "content": "Say only the word 'DEEPSEEK_OK' and nothing else."}
                    ],
                    "model": "deepseek-chat",
                    "max_tokens": 20,
                    "provider": "deepseek",
                    "temperature": 0,
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["provider"] == "deepseek"
            content = data["choices"][0]["message"]["content"]
            print(f"✔ DeepSeek response: {content[:50]}")


class TestGeminiProvider:
    """Tests specifically for Gemini provider."""

    @pytest.mark.asyncio
    async def test_gemini_simple_completion(self):
        """Test a simple completion via Gemini."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BASE_URL}/v1/chat/completions",
                json={
                    "messages": [
                        {"role": "user", "content": "Say only the word 'GEMINI_OK' and nothing else."}
                    ],
                    "model": "gemini-flash",
                    "max_tokens": 20,
                    "provider": "gemini",
                    "temperature": 0,
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["provider"] == "gemini"
            content = data["choices"][0]["message"]["content"]
            print(f"✔ Gemini response: {content[:50]}")