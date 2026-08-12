"""Tests for CircuitBreaker state machine."""

import time

from ai_intel.llm import CircuitBreaker, CircuitBreakerState


def test_circuit_breaker_state_transitions() -> None:
    cb = CircuitBreaker(provider_name="gemini", failure_threshold=3, cooldown_seconds=0.1)
    assert cb.can_execute() is True
    assert cb.state == CircuitBreakerState.CLOSED

    # Record 2 failures -> remains CLOSED
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.can_execute() is True

    # 3rd failure -> state switches to OPEN
    cb.record_failure()
    assert cb.state == CircuitBreakerState.OPEN
    assert cb.can_execute() is False

    # Wait for cooldown to elapse
    time.sleep(0.12)

    # Probing check -> switches to HALF_OPEN
    assert cb.can_execute() is True
    assert cb.state == CircuitBreakerState.HALF_OPEN

    # Success during HALF_OPEN -> resets to CLOSED
    cb.record_success()
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.failure_count == 0
