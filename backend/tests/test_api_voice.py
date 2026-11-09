from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from maia.agent.llm import ModelUnavailableError
from maia.api.deps import get_transcriber
from maia.api.voice import MAX_AUDIO_BYTES
from maia.main import create_app


class FakeTranscriber:
    def __init__(self, text: str = "Left pad is 4 mm.", fail: bool = False) -> None:
        self.text = text
        self.fail = fail
        self.received: list[tuple[bytes, str]] = []

    def transcribe(self, audio: bytes, filename: str) -> str:
        if self.fail:
            raise ModelUnavailableError("503 busy")
        self.received.append((audio, filename))
        return self.text


@pytest.fixture
def transcriber() -> FakeTranscriber:
    return FakeTranscriber()


@pytest.fixture
def client(transcriber: FakeTranscriber) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_transcriber] = lambda: transcriber
    with TestClient(app) as test_client:
        yield test_client


def test_a_recording_becomes_text(client: TestClient, transcriber: FakeTranscriber) -> None:
    response = client.post(
        "/api/transcribe", files={"audio": ("speech.webm", b"fake-audio", "audio/webm;codecs=opus")}
    )

    assert response.status_code == 200
    assert response.json() == {"text": "Left pad is 4 mm."}
    assert transcriber.received == [(b"fake-audio", "speech.webm")]


def test_only_audio_is_accepted(client: TestClient) -> None:
    response = client.post("/api/transcribe", files={"audio": ("notes.txt", b"hi", "text/plain")})

    assert response.status_code == 415


def test_long_recordings_are_refused(client: TestClient) -> None:
    response = client.post(
        "/api/transcribe",
        files={"audio": ("speech.webm", b"x" * (MAX_AUDIO_BYTES + 1), "audio/webm")},
    )

    assert response.status_code == 413


def test_silence_is_reported(transcriber: FakeTranscriber, client: TestClient) -> None:
    transcriber.text = ""

    response = client.post("/api/transcribe", files={"audio": ("s.webm", b"x", "audio/webm")})

    assert response.status_code == 422
    assert "No speech" in response.json()["detail"]


def test_an_outage_asks_the_technician_to_type(
    transcriber: FakeTranscriber, client: TestClient
) -> None:
    transcriber.fail = True

    response = client.post("/api/transcribe", files={"audio": ("s.webm", b"x", "audio/webm")})

    assert response.status_code == 503
    assert "Please type" in response.json()["detail"]
