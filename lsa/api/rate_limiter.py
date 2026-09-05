"""In-memory sliding window rate limiter for Living Systems Auditor API."""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict


class SlidingWindowRateLimiter:
    """Sliding window per-key rate limiter using in-memory timestamp logs.

    WARNING:
        This rate limiter stores timestamp histories strictly in-process memory.
        In a multi-replica or multi-worker deployment (such as multiple uvicorn
        worker processes or containers behind a round-robin load balancer), each
        process maintains an independent sliding window. This effectively multiplies
        the permitted request volume across the deployment. For strict rate limiting
        across distributed clusters, replace or back this limiter with a shared distributed
        store (e.g. Redis sliding window / token bucket).
    """

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


# Backward compatibility alias
TokenBucketRateLimiter = SlidingWindowRateLimiter

_GLOBAL_RATE_LIMITER = SlidingWindowRateLimiter()


def get_rate_limiter() -> SlidingWindowRateLimiter:
    return _GLOBAL_RATE_LIMITER
