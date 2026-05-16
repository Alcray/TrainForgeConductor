"""Tests for ModelMapper with all providers."""

import pytest
from app.models_mapping import ModelMapper


@pytest.fixture
def mapper():
    return ModelMapper()


def test_llama_70b_groq(mapper):
    assert mapper.get_provider_model("llama-70b", "groq") == "llama-3.3-70b-versatile"


def test_llama_70b_sambanova(mapper):
    assert mapper.get_provider_model("llama-70b", "sambanova") == "Meta-Llama-3.3-70B-Instruct"


def test_llama_70b_huggingface(mapper):
    assert mapper.get_provider_model("llama-70b", "huggingface") == "meta-llama/Llama-3.3-70B-Instruct"


def test_llama_8b_groq(mapper):
    assert mapper.get_provider_model("llama-8b", "groq") == "llama-3.1-8b-instant"


def test_gemini_flash(mapper):
    assert mapper.get_provider_model("gemini-flash", "gemini") == "gemini-2.0-flash"


def test_gemini_flash_openrouter(mapper):
    assert mapper.get_provider_model("gemini-flash", "openrouter") == "google/gemini-2.0-flash-exp:free"


def test_mistral_7b(mapper):
    assert mapper.get_provider_model("mistral-7b", "mistral") == "open-mistral-7b"


def test_deepseek_r1(mapper):
    assert mapper.get_provider_model("deepseek-r1", "sambanova") == "DeepSeek-R1"


def test_deepseek_chat_openrouter(mapper):
    assert mapper.get_provider_model("deepseek-chat", "openrouter") == "deepseek/deepseek-chat:free"


def test_command_r(mapper):
    assert mapper.get_provider_model("command-r", "cohere") == "command-r-08-2024"


def test_command_r_plus(mapper):
    assert mapper.get_provider_model("command-r-plus", "cohere") == "command-r-plus-08-2024"


def test_gemma2_9b_groq(mapper):
    assert mapper.get_provider_model("gemma2-9b", "groq") == "gemma2-9b-it"


def test_qwen_72b_openrouter(mapper):
    assert mapper.get_provider_model("qwen-72b", "openrouter") == "qwen/qwen-2.5-72b-instruct:free"


def test_unknown_model_returns_as_is(mapper):
    assert mapper.get_provider_model("some-custom-model", "groq") == "some-custom-model"


def test_none_model_returns_default(mapper):
    result = mapper.get_provider_model(None, "cerebras")
    assert result == "llama-3.3-70b"


def test_get_available_models(mapper):
    models = mapper.get_available_models()
    assert "llama-70b" in models
    assert "gemini-flash" in models
    assert "deepseek-r1" in models
    assert "command-r" in models