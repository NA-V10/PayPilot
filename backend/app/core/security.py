"""Authentication abstraction and a small in-memory rate limiter."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request, status

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class Principal:
    user_id: str
    name: str
    via: str  # "demo" | "api_key"


DEMO_USER_ID = "usr_demo"


def get_principal(
    settings: Settings = Depends(get_settings),
    x_paypilot_key: str | None = Header(default=None),
) -> Principal:
    """Resolve the caller.

    A real deployment swaps this for OAuth/session auth. When `PAYPILOT_API_KEY`
    is set, callers must present it; otherwise the single demo user is assumed.
    """
    if settings.paypilot_api_key:
        if x_paypilot_key != settings.paypilot_api_key:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid API key")
        return Principal(DEMO_USER_ID, "API client", "api_key")
    return Principal(DEMO_USER_ID, "Demo User", "demo")


class RateLimiter:
    """Sliding-window limiter keyed by client IP and route. Sufficient for a single process."""

    def __init__(self, max_calls: int, window_seconds: float) -> None:
        self.max_calls = max_calls
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def __call__(self, request: Request) -> None:
        key = f"{request.client.host if request.client else 'anon'}:{request.url.path}"
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.max_calls:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded. Try again shortly.")
        hits.append(now)

    def reset(self) -> None:
        self._hits.clear()


# Payment and agent execution endpoints are the ones worth protecting.
payment_rate_limit = RateLimiter(max_calls=30, window_seconds=60)
agent_rate_limit = RateLimiter(max_calls=60, window_seconds=60)
