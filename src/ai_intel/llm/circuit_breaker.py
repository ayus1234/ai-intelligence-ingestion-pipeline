"""Circuit breaker state machine for LLM providers."""

from __future__ import annotations

import time
from enum import Enum

from ai_intel.logging import get_logger

logger = get_logger(__name__)


class CircuitBreakerState(str, Enum):
    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"  # Disabled due to repeated failures
    HALF_OPEN = "HALF_OPEN"  # Probing recovery


class CircuitBreaker:
    def __init__(
        self,
        provider_name: str,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self.provider_name = provider_name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float = 0.0

    def can_execute(self) -> bool:
        """Check if provider is available to execute requests."""
        if self.state == CircuitBreakerState.CLOSED:
            return True

        now = time.time()
        if self.state == CircuitBreakerState.OPEN:
            if now - self.last_failure_time >= self.cooldown_seconds:
                logger.info(
                    "circuit_breaker_half_open",
                    extra={"provider": self.provider_name, "cooldown_elapsed": now - self.last_failure_time},
                )
                self.state = CircuitBreakerState.HALF_OPEN
                return True
            return False

        # HALF_OPEN state allows probing request
        return True

    def record_success(self) -> None:
        """Record successful execution, resetting circuit breaker to CLOSED."""
        if self.state != CircuitBreakerState.CLOSED:
            logger.info("circuit_breaker_closed", extra={"provider": self.provider_name})
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0

    def record_failure(self) -> None:
        """Record failed execution, opening circuit if failure threshold is reached."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold or self.state == CircuitBreakerState.HALF_OPEN:
            if self.state != CircuitBreakerState.OPEN:
                logger.warning(
                    "circuit_breaker_opened",
                    extra={
                        "provider": self.provider_name,
                        "failure_count": self.failure_count,
                        "cooldown_seconds": self.cooldown_seconds,
                    },
                )
            self.state = CircuitBreakerState.OPEN
