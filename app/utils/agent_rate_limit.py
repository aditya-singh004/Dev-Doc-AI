"""
Simple in-memory sliding-window rate limiter for /agent/run.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict

from app.config import settings


class AgentRateLimiter:
    def __init__(self) -> None:
        self._windows: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> None:
        """
        Raises RuntimeError if rate limit exceeded for this key.
        """
        limit = settings.AGENT_RATE_LIMIT_PER_MINUTE
        if limit <= 0:
            return
        now = time.time()
        window_start = now - 60.0
        with self._lock:
            dq = self._windows[key]
            while dq and dq[0] < window_start:
                dq.popleft()
            if len(dq) >= limit:
                raise RuntimeError(
                    f"Agent rate limit exceeded ({limit} requests per minute). Try again shortly."
                )
            dq.append(now)


agent_rate_limiter = AgentRateLimiter()
