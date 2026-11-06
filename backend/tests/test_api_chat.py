from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager

import pytest
from fakes import ScriptedLLM, UnavailableLLM, call, say
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from maia.agent.agent import MaintenanceAgent
from maia.agent.llm import ChatModel
from maia.agent.sessions import ConversationStore
from maia.api.deps import get_agent, get_conversation_store, get_transaction
from maia.db.models import Part, WorkOrder
from maia.main import create_app
from maia.manual.embeddings import Embedder

Transaction = Callable[[], AbstractContextManager[Session]]

WORK_ORDER = call(
    "create_work_order",
    vehicle_id="RV200-014",
    asset_id="RV200-014-B2",
    procedure_code="PROC-BRK-01",
    priority="high",
    description="Replace brake pads",
    parts=[{"part_number": "BP-2207", "quantity": 2}],
)


@pytest.fixture
def make_client(
    embedder: Embedder, transaction: Transaction
) -> Iterator[Callable[[ChatModel], TestClient]]:
    """Build an API client whose agent uses the given model and the test database."""
    apps: list[FastAPI] = []

    def build(llm: ChatModel) -> TestClient:
        app = create_app()
        store = ConversationStore()
        app.dependency_overrides[get_agent] = lambda: MaintenanceAgent(llm, embedder, transaction)
        app.dependency_overrides[get_conversation_store] = lambda: store
        app.dependency_overrides[get_transaction] = lambda: transaction
        apps.append(app)
        return TestClient(app)

    yield build
    for app in apps:
        app.dependency_overrides.clear()


def start_session(client: TestClient) -> str:
    response = client.post("/api/sessions")
    assert response.status_code == 201
    session_id: str = response.json()["session_id"]
    return session_id


def test_message_returns_the_agent_reply(make_client: Callable[[ChatModel], TestClient]) -> None:
    client = make_client(ScriptedLLM([say("Which vehicle?")]))
    session_id = start_session(client)

    response = client.post(f"/api/sessions/{session_id}/messages", json={"text": "Hi"})

    assert response.status_code == 200
    assert response.json() == {"text": "Which vehicle?", "events": [], "pending": []}


def test_write_action_is_pending_until_confirmed(
    depot: Session, make_client: Callable[[ChatModel], TestClient]
) -> None:
    client = make_client(ScriptedLLM([WORK_ORDER, say("Work order opened.")]))
    session_id = start_session(client)

    reply = client.post(f"/api/sessions/{session_id}/messages", json={"text": "Open it"}).json()
    assert reply["pending"][0]["tool"] == "create_work_order"
    assert depot.scalar(select(func.count()).select_from(WorkOrder)) == 0

    confirmed = client.post(
        f"/api/sessions/{session_id}/confirmation", json={"approved": True}
    ).json()

    assert confirmed["text"] == "Work order opened."
    assert confirmed["events"] == [{"name": "create_work_order", "ok": True, "confirmed": True}]
    assert depot.scalar(select(func.count()).select_from(WorkOrder)) == 1


def test_unknown_session_is_404(make_client: Callable[[ChatModel], TestClient]) -> None:
    client = make_client(ScriptedLLM([]))

    response = client.post("/api/sessions/nope/messages", json={"text": "Hi"})

    assert response.status_code == 404


def test_empty_message_is_rejected(make_client: Callable[[ChatModel], TestClient]) -> None:
    client = make_client(ScriptedLLM([]))
    session_id = start_session(client)

    response = client.post(f"/api/sessions/{session_id}/messages", json={"text": ""})

    assert response.status_code == 422


def test_model_outage_returns_a_clean_503(make_client: Callable[[ChatModel], TestClient]) -> None:
    client = make_client(UnavailableLLM())
    session_id = start_session(client)

    response = client.post(f"/api/sessions/{session_id}/messages", json={"text": "Hi"})

    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]


def test_demo_reset_restores_stock(
    depot: Session, make_client: Callable[[ChatModel], TestClient]
) -> None:
    depot.get_one(Part, "BP-2207").quantity_reserved = 2
    client = make_client(ScriptedLLM([]))

    response = client.post("/api/demo/reset")

    assert response.status_code == 200
    assert depot.get_one(Part, "BP-2207").quantity_reserved == 0


def test_store_forgets_the_oldest_conversation() -> None:
    store = ConversationStore(max_conversations=2)
    first = store.create()
    store.create()
    store.create()

    assert store.get(first.session_id) is None
