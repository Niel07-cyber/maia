from collections.abc import Iterator
from datetime import date

import pytest
from fakes import ScriptedLLM, say
from fastapi import HTTPException
from fastapi.testclient import TestClient

from maia.agent.budget import BudgetedModel, BudgetExceededError
from maia.agent.llm import LLMResponse, Usage
from maia.api.limits import DAY, RateLimiter, get_rate_limiter
from maia.main import create_app


class Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


def test_visitors_are_limited_per_minute() -> None:
    clock = Clock()
    limiter = RateLimiter(per_minute=2, per_day=0, clock=clock)
    limiter.check("a")
    limiter.check("a")

    with pytest.raises(HTTPException) as refused:
        limiter.check("a")
    assert refused.value.status_code == 429

    limiter.check("b")  # other visitors are not affected
    clock.now += 61
    limiter.check("a")  # a minute later it works again


def test_visitors_are_limited_per_day() -> None:
    clock = Clock()
    limiter = RateLimiter(per_minute=0, per_day=3, clock=clock)
    for _ in range(3):
        limiter.check("a")
        clock.now += 120

    with pytest.raises(HTTPException, match="today's demo limit"):
        limiter.check("a")

    clock.now += DAY
    limiter.check("a")


def test_zero_means_no_limit() -> None:
    limiter = RateLimiter(per_minute=0, per_day=0)
    for _ in range(100):
        limiter.check("a")


@pytest.fixture
def limited_client() -> Iterator[TestClient]:
    app = create_app()
    limiter = RateLimiter(per_minute=1, per_day=0)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    with TestClient(app) as client:
        yield client


def test_the_api_returns_429_over_the_limit(limited_client: TestClient) -> None:
    files = {"audio": ("s.txt", b"x", "text/plain")}  # refused anyway: no model is called

    assert limited_client.post("/api/transcribe", files=files).status_code == 415
    over = limited_client.post("/api/transcribe", files=files)

    assert over.status_code == 429
    assert over.headers["Retry-After"] == "60"


def costly(text: str, cost: float) -> LLMResponse:
    return LLMResponse(text, usage=Usage(100, 10, cost))


def test_the_budget_stops_calls_for_the_rest_of_the_day() -> None:
    day = [date(2026, 11, 9)]
    llm = BudgetedModel(
        ScriptedLLM([costly("one", 0.6), costly("two", 0.6), costly("next day", 0.1)]),
        daily_budget_usd=1.0,
        today=lambda: day[0],
    )

    llm.complete([], [])
    llm.complete([], [])  # starts below the cap, so it is allowed to finish
    assert llm.spent_today == pytest.approx(1.2)

    with pytest.raises(BudgetExceededError, match="budget for today"):
        llm.complete([], [])

    day[0] = date(2026, 11, 10)
    assert llm.complete([], []).content == "next day"


def test_calls_without_a_known_price_still_work() -> None:
    llm = BudgetedModel(ScriptedLLM([say("hi")]), daily_budget_usd=1.0)

    assert llm.complete([], []).content == "hi"
    assert llm.spent_today == 0
