"""
Simple TrainForgeConductor Client

A lightweight client wrapper for easy usage.

Usage:
    from examples.client import ConductorClient
    
    client = ConductorClient()
    response = client.chat("Hello!")
    print(response)
"""

from typing import Optional
import httpx


class ConductorClient:
    """Simple client for TrainForgeConductor."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 60.0
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
    
    def chat(
        self,
        message: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        """
        Simple chat completion.
        
        Args:
            message: User message
            system: Optional system prompt
            model: Model to use
            provider: Force specific provider ("cerebras" or "nvidia")
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Assistant response text
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": message})
        
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        if model:
            payload["model"] = model
        if provider:
            payload["provider"] = provider
        
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
    def chat_full(
        self,
        messages: list[dict],
        **kwargs
    ) -> dict:
        """
        Full chat completion with message history.
        
        Args:
            messages: List of message dicts with "role" and "content"
            **kwargs: Additional parameters (model, provider, max_tokens, etc.)
            
        Returns:
            Full response dict
        """
        payload = {"messages": messages, **kwargs}
        
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload
            )
            response.raise_for_status()
            return response.json()
    
    def batch(
        self,
        prompts: list[str],
        system: Optional[str] = None,
        **kwargs
    ) -> list[str]:
        """
        Batch multiple prompts.
        
        Args:
            prompts: List of user prompts
            system: Optional system prompt for all
            **kwargs: Additional parameters
            
        Returns:
            List of response texts
        """
        requests = []
        for prompt in prompts:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            requests.append({"messages": messages, **kwargs})
        
        with httpx.Client(timeout=self.timeout * len(prompts)) as client:
            response = client.post(
                f"{self.base_url}/v1/batch/chat/completions",
                json={"requests": requests, "wait_for_all": True}
            )
            response.raise_for_status()
            data = response.json()
            
            return [
                r["choices"][0]["message"]["content"]
                for r in data["responses"]
            ]
    
    def status(self) -> dict:
        """Get conductor status."""
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{self.base_url}/status")
            response.raise_for_status()
            return response.json()
    
    def models(self) -> list[str]:
        """List available models."""
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{self.base_url}/v1/models")
            response.raise_for_status()
            return [m["id"] for m in response.json()["data"]]


# Quick usage example
if __name__ == "__main__":
    client = ConductorClient()
    
    # Simple chat
    print("Simple chat:")
    print(client.chat("What is 2+2?"))
    
    # With system prompt
    print("\nWith system prompt:")
    print(client.chat(
        "Write a haiku",
        system="You are a poet. Be creative."
    ))
    
    # Batch
    print("\nBatch requests:")
    answers = client.batch([
        "Capital of France?",
        "Capital of Japan?",
        "Capital of Brazil?"
    ], max_tokens=20)
    for a in answers:
        print(f"  - {a}")

