"""Minimal per-platform circuit breaker, preserved from the original gateway.

* Opens after ``failure_threshold`` consecutive failures.
* Stays open for ``reset_timeout`` seconds, then allows a probe request.
* ``force_open`` / ``force_close`` back the maintenance endpoint.
"""

from __future__ import annotations

import time
from typing import Dict, Optional


class CircuitBreaker:
    def __init__(self, service_name: str, failure_threshold: int = 3, reset_timeout: int = 30):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.state = "CLOSED"          # CLOSED | OPEN | HALF_OPEN
        self.last_failure_time: Optional[float] = None
        self._forced_open_reason: Optional[str] = None

    @property
    def is_open(self) -> bool:
        if self._forced_open_reason:
            return True
        if self.state == "OPEN":
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.reset_timeout:
                self.state = "HALF_OPEN"
                return False
            return True
        return False

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = "CLOSED"
        self.last_failure_time = None
        self._forced_open_reason = None

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

    def force_open(self, reason: str = "maintenance") -> None:
        self._forced_open_reason = reason
        self.state = "OPEN"
        self.last_failure_time = time.time()

    def force_close(self) -> None:
        self._forced_open_reason = None
        self.record_success()

    def snapshot(self) -> Dict[str, object]:
        return {
            "platform": self.service_name,
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "reset_timeout_seconds": self.reset_timeout,
            "maintenance_reason": self._forced_open_reason,
        }


# One breaker per registered platform.
from .platforms import platform_keys  # noqa: E402  (import after class for clarity)

circuit_breakers: Dict[str, CircuitBreaker] = {
    key: CircuitBreaker(service_name=key) for key in platform_keys()
}


def get_breaker(platform: str) -> CircuitBreaker:
    if platform not in circuit_breakers:
        circuit_breakers[platform] = CircuitBreaker(service_name=platform)
    return circuit_breakers[platform]