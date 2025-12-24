"""
Unified model name mapping.

This allows you to use simple names like "llama-70b" and the conductor
will automatically translate to the correct provider-specific name.
"""

# Default model mappings: unified name -> provider-specific names
DEFAULT_MODEL_MAPPING = {
    # Llama 3.3 70B - the flagship model
    "llama-70b": {
        "cerebras": "llama-3.3-70b",
        "nvidia": "meta/llama-3.3-70b-instruct",
    },
    "llama-3.3-70b": {
        "cerebras": "llama-3.3-70b",
        "nvidia": "meta/llama-3.3-70b-instruct",
    },
    
    # Llama 3.1 8B - fast and cheap
    "llama-8b": {
        "cerebras": "llama3.1-8b",
        "nvidia": "meta/llama-3.1-8b-instruct",
    },
    "llama-3.1-8b": {
        "cerebras": "llama3.1-8b",
        "nvidia": "meta/llama-3.1-8b-instruct",
    },
    
    # Llama 3.1 70B
    "llama-3.1-70b": {
        "cerebras": "llama-3.1-70b",
        "nvidia": "meta/llama-3.1-70b-instruct",
    },
}

# Default model to use when none specified
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
        
        # Normalize the name
        name_lower = unified_name.lower().strip()
        
        # Check if it's in our mappings
        if name_lower in self.mappings:
            provider_models = self.mappings[name_lower]
            if provider in provider_models:
                return provider_models[provider]
        
        # If not found, return as-is (maybe it's already provider-specific)
        return unified_name
    
    def get_available_models(self) -> list[str]:
        """Get list of available unified model names."""
        return list(self.mappings.keys())
    
    def add_mapping(self, unified_name: str, provider_models: dict):
        """Add a custom model mapping."""
        self.mappings[unified_name.lower()] = provider_models
