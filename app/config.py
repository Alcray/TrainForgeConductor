"""Configuration management for TrainForgeConductor."""

from typing import Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import yaml
from pathlib import Path


class ProviderKeyConfig(BaseModel):
    """Configuration for a single API key."""
    api_key: str
    requests_per_minute: int = Field(default=60, ge=1)
    tokens_per_minute: int = Field(default=100000, ge=1)
    name: Optional[str] = None  # Optional friendly name for this key


class ProviderConfig(BaseModel):
    """Configuration for a provider (e.g., Cerebras, NVIDIA)."""
    enabled: bool = True
    base_url: str
    keys: list[ProviderKeyConfig] = []
    default_model: str
    supported_models: list[str] = []


class ConductorConfig(BaseModel):
    """Main conductor configuration."""
    scheduling_strategy: str = Field(
        default="round_robin",
        pattern="^(round_robin|least_loaded|sequential)$"
    )
    request_timeout: int = Field(default=120, ge=1)
    max_retries: int = Field(default=3, ge=0)
    retry_delay: float = Field(default=1.0, ge=0)


class Settings(BaseSettings):
    """Application settings loaded from environment."""
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    config_path: str = "./config/config.yaml"

    class Config:
        env_prefix = "CONDUCTOR_"


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    path = Path(config_path)
    if not path.exists():
        return get_default_config()
    
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_default_config() -> dict:
    """Return default configuration structure."""
    return {
        "conductor": {
            "scheduling_strategy": "round_robin",
            "request_timeout": 120,
            "max_retries": 3,
            "retry_delay": 1.0,
        },
        "providers": {
            "cerebras": {
                "enabled": True,
                "base_url": "https://api.cerebras.ai/v1",
                "default_model": "llama-3.3-70b",
                "supported_models": [
                    "llama-3.3-70b",
                    "llama-3.1-8b",
                    "llama-3.1-70b",
                ],
                "keys": [],
            },
            "nvidia": {
                "enabled": True,
                "base_url": "https://integrate.api.nvidia.com/v1",
                "default_model": "meta/llama-3.1-8b-instruct",
                "supported_models": [
                    "meta/llama-3.1-8b-instruct",
                    "meta/llama-3.1-70b-instruct",
                    "meta/llama-3.3-70b-instruct",
                ],
                "keys": [],
            },
        },
    }


settings = Settings()

