"""
Circuit breaker pattern implementation for external API calls.
Prevents cascading failures and runaway costs from failing services.
"""

import asyncio
import os
import time
from enum import Enum
from typing import Callable, Optional, TypeVar, Any
import structlog

logger = structlog.get_logger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker for external API calls.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, reject requests immediately
    - HALF_OPEN: Testing recovery, allow one request

    Usage:
        breaker = CircuitBreaker("openai", max_failures=5, reset_timeout=60)
        result = await breaker.call(my_async_function, arg1, arg2)
    """

    def __init__(
        self,
        name: str,
        max_failures: Optional[int] = None,
        reset_timeout: Optional[int] = None,
    ):
        self.name = name
        self.max_failures = max_failures or int(
            os.getenv("CIRCUIT_BREAKER_MAX_FAILURES", "5")
        )
        self.reset_timeout = reset_timeout or int(
            os.getenv("CIRCUIT_BREAKER_RESET_TIMEOUT", "60")
        )

        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED
        self._lock = asyncio.Lock()

    async def call(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Execute a function with circuit breaker protection.

        Args:
            func: Async function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            CircuitBreakerOpen: When circuit is open and rejecting requests
            Original exception: When func fails
        """
        async with self._lock:
            # Check if we should transition from OPEN to HALF_OPEN
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    logger.info(
                        "circuit_breaker_half_open",
                        name=self.name,
                        message="Attempting recovery"
                    )
                    self.state = CircuitState.HALF_OPEN
                else:
                    logger.warning(
                        "circuit_breaker_open",
                        name=self.name,
                        failure_count=self.failure_count,
                        message="Circuit breaker is open, rejecting request"
                    )
                    raise CircuitBreakerOpen(
                        f"Circuit breaker '{self.name}' is open. "
                        f"Service has failed {self.failure_count} times. "
                        f"Try again in {self._time_until_reset():.0f}s."
                    )

        # Execute the function
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try recovery."""
        if self.last_failure_time is None:
            return True
        return time.monotonic() - self.last_failure_time >= self.reset_timeout

    def _time_until_reset(self) -> float:
        """Calculate seconds until circuit attempts reset."""
        if self.last_failure_time is None:
            return 0
        elapsed = time.monotonic() - self.last_failure_time
        return max(0, self.reset_timeout - elapsed)

    async def _on_success(self):
        """Handle successful call."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                logger.info(
                    "circuit_breaker_recovered",
                    name=self.name,
                    message="Service recovered, closing circuit"
                )
            self.failure_count = 0
            self.last_failure_time = None
            self.state = CircuitState.CLOSED

    async def _on_failure(self):
        """Handle failed call."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.monotonic()

            if self.state == CircuitState.HALF_OPEN:
                # Failed during recovery attempt, back to OPEN
                logger.warning(
                    "circuit_breaker_recovery_failed",
                    name=self.name,
                    message="Recovery attempt failed, opening circuit"
                )
                self.state = CircuitState.OPEN
            elif self.failure_count >= self.max_failures:
                # Too many failures, open the circuit
                logger.error(
                    "circuit_breaker_opened",
                    name=self.name,
                    failure_count=self.failure_count,
                    max_failures=self.max_failures,
                    message=f"Opening circuit breaker after {self.failure_count} failures"
                )
                self.state = CircuitState.OPEN
            else:
                logger.warning(
                    "circuit_breaker_failure",
                    name=self.name,
                    failure_count=self.failure_count,
                    max_failures=self.max_failures,
                )

    def reset(self):
        """Manually reset the circuit breaker."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        logger.info("circuit_breaker_reset", name=self.name)


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open and rejecting requests."""
    pass


# Global circuit breakers for external services
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(service_name: str) -> CircuitBreaker:
    """
    Get or create a circuit breaker for a service.

    Args:
        service_name: Name of the external service (e.g., "openai", "google_calendar")

    Returns:
        CircuitBreaker instance
    """
    if service_name not in _circuit_breakers:
        _circuit_breakers[service_name] = CircuitBreaker(service_name)
    return _circuit_breakers[service_name]
