"""In-memory sliding window rate limiter for Living Systems Auditor API."""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict


class TokenBucketRateLimiter:
    """Sliding window per-key rate limiter."""

    def __init__(self, requests_per_minute: int | None = None) -> None:
        if requests_per_minute is None:
            requests_per_minute = int(os.environ.get("LSA_RATE_LIMIT_PER_MINUTE", "60"))
        self.requests_per_minute = max(1, requests_per_minute)
        self._window_seconds = 60.0
        self._lock = threading.Lock()
        self._history: dict[str, list[float]] = defaultdict(list)

    def check_rate_limit(self, key: str) -> tuple[bool, int]:
        """Check if request for key is allowed within current window.

        Returns:
            (allowed: bool, retry_after: int)
        """
        now = time.time()
        window_start = now - self._window_seconds

        with self._lock:
            # Prune timestamps older than window
            timestamps = [t for t in self._history[key] if t > window_start]
            if len(timestamps) >= self.requests_per_minute:
                oldest_in_window = timestamps[0]
                retry_after = max(1, int(oldest_in_window + self._window_seconds - now))
                self._history[key] = timestamps
                return False, retry_after

            timestamps.append(now)
            self._history[key] = timestamps
            return True, 0

    def reset(self) -> None:
        """Clear all rate limit histories."""
        with self._lock:
            self._history.clear()


_GLOBAL_RATE_LIMITER = TokenBucketRateLimiter()


def get_rate_limiter() -> TokenBucketRateLimiter:
    return _GLOBAL_RATE_LIMITER
