"""A daily spending cap on the chat model, so a public demo cannot drain the API credit."""

import threading
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

from maia.agent.llm import ChatModel, LLMResponse, ModelUnavailableError


class BudgetExceededError(ModelUnavailableError):
    """The demo has spent its budget for today."""


class BudgetedModel:
    """Wraps a chat model and refuses new calls once today's spending reaches the cap."""

    def __init__(
        self,
        inner: ChatModel,
        daily_budget_usd: float,
        today: Callable[[], date] = lambda: datetime.now(UTC).date(),
    ) -> None:
        self.inner = inner
        self.daily_budget_usd = daily_budget_usd
        self.today = today
        self._day = today()
        self._spent = 0.0
        self._lock = threading.Lock()

    @property
    def spent_today(self) -> float:
        with self._lock:
            self._roll_over()
            return self._spent

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResponse:
        with self._lock:
            self._roll_over()
            if self._spent >= self.daily_budget_usd:
                raise BudgetExceededError(
                    "The demo has used its budget for today. Please come back tomorrow."
                )
        response = self.inner.complete(messages, tools)
        if response.usage and response.usage.cost_usd:
            with self._lock:
                self._spent += response.usage.cost_usd
        return response

    def _roll_over(self) -> None:
        if self.today() != self._day:
            self._day = self.today()
            self._spent = 0.0
