"""Per-visitor rate limits for the endpoints that call a model (chat, voice) or reset data."""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from maia.config import get_settings

MINUTE = 60.0
DAY = 24 * 60 * 60.0


class RateLimiter:
    """Sliding windows of request times per visitor. In memory: fine for one server."""

    def __init__(
        self, per_minute: int, per_day: int, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.per_minute = per_minute
        self.per_day = per_day
        self.clock = clock
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, visitor: str) -> None:
        """Record a request, or raise 429 if the visitor is over a limit."""
        now = self.clock()
        with self._lock:
            times = self._requests[visitor]
            while times and times[0] <= now - DAY:
                times.popleft()
            last_minute = sum(1 for t in times if t > now - MINUTE)
            if self.per_minute and last_minute >= self.per_minute:
                raise _too_many("Too many messages. Wait a minute and try again.", 60)
            if self.per_day and len(times) >= self.per_day:
                raise _too_many(
                    "You have reached today's demo limit. Please come back tomorrow.", 3600
                )
            times.append(now)


def _too_many(detail: str, retry_after: int) -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS, detail, headers={"Retry-After": str(retry_after)}
    )


@lru_cache
def get_rate_limiter() -> RateLimiter:
    settings = get_settings()
    return RateLimiter(settings.rate_limit_per_minute, settings.rate_limit_per_day)


def rate_limit(
    request: Request, limiter: Annotated[RateLimiter, Depends(get_rate_limiter)]
) -> None:
    # Behind the reverse proxy, uvicorn's --proxy-headers puts the visitor's address here.
    limiter.check(request.client.host if request.client else "unknown")


RateLimited = Depends(rate_limit)
