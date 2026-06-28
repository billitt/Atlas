"""API security middleware: bearer auth, rate limiting, inference concurrency."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from api.config import API_RATE_LIMIT_RPS, MAX_CONCURRENT_INFERENCES
from protocols.auth import api_auth_token, bearer_authorized

# Global cap on simultaneous graph runs (single-GPU safety).
_inference_semaphore = asyncio.Semaphore(MAX_CONCURRENT_INFERENCES)


class _RateLimiter:
    """Simple per-client sliding-window limiter (mirrors Rust governor posture)."""

    def __init__(self, rps: int) -> None:
        self._rps = max(1, rps)
        self._events: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        now = time.monotonic()
        window = 1.0
        async with self._lock:
            bucket = self._events.setdefault(key, deque())
            while bucket and now - bucket[0] > window:
                bucket.popleft()
            if len(bucket) >= self._rps:
                return False
            bucket.append(now)
            return True


_rate_limiter = _RateLimiter(API_RATE_LIMIT_RPS)


def _client_key(request: Request) -> str:
    if request.client:
        return request.client.host
    return "unknown"


async def require_api_auth(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Reject /api/* requests when bearer token is configured and missing/invalid."""
    if not bearer_authorized(authorization, api_auth_token()):
        raise HTTPException(status_code=401, detail="Unauthorized")


async def enforce_rate_limit(request: Request) -> None:
    """Return 429 when the per-client rate limit is exceeded."""
    if not await _rate_limiter.allow(_client_key(request)):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


async def acquire_inference_slot() -> None:
    """Block until an inference slot is available (concurrency cap)."""
    await _inference_semaphore.acquire()


def release_inference_slot() -> None:
    _inference_semaphore.release()


AuthDep = Annotated[None, Depends(require_api_auth)]
RateLimitDep = Annotated[None, Depends(enforce_rate_limit)]
