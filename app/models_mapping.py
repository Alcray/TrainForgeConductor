"""
Unified model name mapping.
This allows you to use simple names like "llama-70b" and the conductor
will automatically translate to the correct provider-specific name.
"""

DEFAULT_MODEL_MAPPING = {
    # Llama 3.3 70B
    "llama-70b": {
        "cerebras": "llama-3.3-70b",
        "nvidia": "meta/llama-3.3-70b-instruct",
        "groq": "llama-3.3-70b-versatile",
        "openrouter": "meta-llama/llama-3.3-70b-instruct",
        "sambanova": "Meta-Llama-3.3-70B-Instruct",
        "huggingface": "meta-llama/Llama-3.3-70B-Instruct",
    },
    "llama-3.3-70b": {
        "cerebras": "llama-3.3-70b",
        "nvidia": "meta/llama-3.3-70b-instruct",
        "groq": "llama-3.3-70b-versatile",
        "openrouter": "meta-llama/llama-3.3-70b-instruct",
        "sambanova": "Meta-Llama-3.3-70B-Instruct",
        "huggingface": "meta-llama/Llama-3.3-70B-Instruct",
    },
    # Llama 3.1 8B
    "llama-8b": {
        "cerebras": "llama3.1-8b",
        "nvidia": "meta/llama-3.1-8b-instruct",
        "groq": "llama-3.1-8b-instant",
        "openrouter": "meta-llama/llama-3.1-8b-instruct",
        "sambanova": "Meta-Llama-3.1-8B-Instruct",
        "huggingface": "meta-llama/Llama-3.1-8B-Instruct",
    },
    "llama-3.1-8b": {
        "cerebras": "llama3.1-8b",
        "nvidia": "meta/llama-3.1-8b-instruct",
        "groq": "llama-3.1-8b-instant",
        "openrouter": "meta-llama/llama-3.1-8b-instruct",
        "sambanova": "Meta-Llama-3.1-8B-Instruct",
        "huggingface": "meta-llama/Llama-3.1-8B-Instruct",
    },
    # Llama 3.1 70B
    "llama-3.1-70b": {
        "cerebras": "llama-3.1-70b",
        "nvidia": "meta/llama-3.1-70b-instruct",
        "groq": "llama-3.1-70b-versatile",
        "openrouter": "meta-llama/llama-3.1-70b-instruct",
        "sambanova": "Meta-Llama-3.1-70B-Instruct",
        "huggingface": "meta-llama/Llama-3.1-70B-Instruct",
    },
    # Llama 3.1 405B
    "llama-405b": {
        "nvidia": "meta/llama-3.1-405b-instruct",
        "sambanova": "Meta-Llama-3.1-405B-Instruct",
        "openrouter": "meta-llama/llama-3.1-405b-instruct",
    },
    # Gemini models
    "gemini-flash": {
        "gemini": "gemini-2.0-flash",
        "openrouter": "google/gemini-2.0-flash-exp:free",
    },
    "gemini-2.0-flash": {
        "gemini": "gemini-2.0-flash",
        "openrouter": "google/gemini-2.0-flash-exp:free",
    },
    "gemini-flash-lite": {
        "gemini": "gemini-2.0-flash-lite",
    },
    # Mistral models
    "mistral-small": {
        "mistral": "mistral-small-latest",
        "openrouter": "mistralai/mistral-small",
    },
    "mistral-7b": {
        "mistral": "open-mistral-7b",
        "openrouter": "mistralai/mistral-7b-instruct:free",
        "huggingface": "mistralai/Mistral-7B-Instruct-v0.3",
    },
    # DeepSeek models
    "deepseek-chat": {
        "deepseek": "deepseek-chat",
        "openrouter": "deepseek/deepseek-chat:free",
    },
    "deepseek-coder": {
        "deepseek": "deepseek-coder",
        "openrouter": "deepseek/deepseek-coder:free",
    },
    "deepseek-r1": {
        "deepseek": "deepseek-reasoner",
        "openrouter": "deepseek/deepseek-r1:free",
        "sambanova": "DeepSeek-R1",
    },
    # Cohere models
    "command-r": {
        "cohere": "command-r-08-2024",
        "openrouter": "cohere/command-r",
    },
    "command-r-plus": {
        "cohere": "command-r-plus-08-2024",
        "openrouter": "cohere/command-r-plus",
    },
    # Groq specific
    "mixtral-8x7b": {
        "groq": "mixtral-8x7b-32768",
        "openrouter": "mistralai/mixtral-8x7b-instruct",
    },
    "gemma-7b": {
        "groq": "gemma-7b-it",
        "openrouter": "google/gemma-7b-it:free",
        "huggingface": "google/gemma-7b-it",
    },
    "gemma2-9b": {
        "groq": "gemma2-9b-it",
        "openrouter": "google/gemma-2-9b-it:free",
        "huggingface": "google/gemma-2-9b-it",
    },
    # Qwen models
    "qwen-72b": {
        "sambanova": "Qwen2.5-72B-Instruct",
        "openrouter": "qwen/qwen-2.5-72b-instruct:free",
        "huggingface": "Qwen/Qwen2.5-72B-Instruct",
    },
}

DEFAULT_MODEL = "llama-70b"


class ModelMapper:
    """Maps unified model names to provider-specific names."""

    def __init__(self, custom_mappings: dict = None):
        """
        Initialize with optional custom mappings from config.

        Args:
            custom_mappings: Dict of {unified_name: {provider: provider_name}}
        """
        self.mappings = DEFAULT_MODEL_MAPPING.copy()
        if custom_mappings:
            self.mappings.update(custom_mappings)

    def get_provider_model(self, unified_name: str, provider: str) -> str:
        """
        Get the provider-specific model name.

        Args:
            unified_name: The unified model name (e.g., "llama-70b")
            provider: The provider name (e.g., "cerebras", "nvidia")

        Returns:
            Provider-specific model name
        """
        if not unified_name:
            unified_name = DEFAULT_MODEL
        name_lower = unified_name.lower().strip()
        if name_lower in self.mappings:
            provider_models = self.mappings[name_lower]
            if provider in provider_models:
                return provider_models[provider]
        return unified_name

    def get_available_models(self) -> list[str]:
        """Get list of available unified model names."""
        return list(self.mappings.keys())

    def add_mapping(self, unified_name: str, provider_models: dict):
        """Add a custom model mapping."""
        self.mappings[unified_name.lower()] = provider_models