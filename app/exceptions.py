"""Custom exceptions for provider error handling."""

from typing import Optional


class ProviderError(Exception):
    """Base exception for provider errors."""
    
    def __init__(
        self,
        message: str,
        provider: str,
        status_code: Optional[int] = None,
        retryable: bool = True,
    ):
        self.message = message
        self.provider = provider
        self.status_code = status_code
        self.retryable = retryable
        super().__init__(message)
    
    def __str__(self):
        return f"[{self.provider}] {self.message}"


class RateLimitError(ProviderError):
    """Raised when provider returns 429 rate limit error."""
    
    def __init__(
        self,
        provider: str,
        retry_after: Optional[float] = None,
        message: str = "Rate limit exceeded",
    ):
        self.retry_after = retry_after
        super().__init__(
            message=message,
            provider=provider,
            status_code=429,
            retryable=True,
        )


class CapabilityError(ProviderError):
    """Raised when provider doesn't support a requested capability."""
    
    def __init__(
        self,
        provider: str,
        capability: str,
        message: Optional[str] = None,
    ):
        self.capability = capability
        super().__init__(
            message=message or f"Provider does not support: {capability}",
            provider=provider,
            status_code=400,
            retryable=True,  # Can retry with different provider
        )


class ProviderUnavailableError(ProviderError):
    """Raised when provider is temporarily unavailable (5xx errors)."""
    
    def __init__(
        self,
        provider: str,
        status_code: int = 503,
        message: str = "Provider temporarily unavailable",
    ):
        super().__init__(
            message=message,
            provider=provider,
            status_code=status_code,
            retryable=True,
        )


class AllProvidersExhaustedError(Exception):
    """Raised when all providers have been tried and failed."""
    
    def __init__(self, errors: list[ProviderError]):
        self.errors = errors
        self.message = self._build_message()
        super().__init__(self.message)
    
    def _build_message(self) -> str:
        if not self.errors:
            return "All providers exhausted (no errors recorded)"
        
        error_details = []
        for err in self.errors:
            error_details.append(f"  - {err.provider}: {err.message}")
        
        return "All providers failed:\n" + "\n".join(error_details)


class MaxRetriesExhaustedError(Exception):
    """Raised when auto-retry exhausts all retry attempts."""
    
    def __init__(
        self,
        retry_log: list[dict],
        total_attempts: int,
        total_duration_seconds: float,
        final_error: Optional[Exception] = None,
    ):
        self.retry_log = retry_log
        self.total_attempts = total_attempts
        self.total_duration_seconds = total_duration_seconds
        self.final_error = final_error
        super().__init__(
            f"Request failed after {total_attempts} attempts "
            f"over {total_duration_seconds:.1f}s"
        )
