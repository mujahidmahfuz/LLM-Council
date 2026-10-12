"""HTTP-level tests of the FastAPI app with a mocked OpenRouter."""

from __future__ import annotations

import json
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient

from council.config import Settings
from main import create_app
from tests.conftest import Handler, make_client, scripted_reply


def client_for(settings: Settings, handler: Handler = scripted_reply) -> TestClient:
    return TestClient(create_app(settings, client_factory=lambda: make_client(handler)))


def events_of(response: httpx.Response) -> list[dict]:
    return [json.loads(line) for line in response.text.splitlines()]


def test_health_reports_configuration(settings: Settings) -> None:
    assert client_for(settings).get("/health").json() == {"status": "ok", "configured": True}
    unconfigured = replace(settings, api_key=None)
    assert client_for(unconfigured).get("/health").json()["configured"] is False


def test_config_lists_the_round_table_without_secrets(settings: Settings) -> None:
    response = client_for(settings).get("/config")
    assert response.json() == {
        "members": ["m1", "m2", "m3", "m4"],
        "chairman": "chair",
        "max_prompt_chars": 100,
    }
    assert "test-key" not in response.text


def test_ask_council_returns_full_result(settings: Settings) -> None:
    response = client_for(settings).post("/ask-council", json={"prompt": "  Why is the sky blue?  "})
    body = response.json()
    assert response.status_code == 200
    assert body["question"] == "Why is the sky blue?"
    assert body["winner"] == "m1"
    assert body["council_verdict"] == "FINAL VERDICT"
    assert len(body["individual_responses"]) == 4


def test_peer_review_flag_is_honoured(settings: Settings) -> None:
    body = client_for(settings).post("/ask-council", json={"prompt": "q", "peer_review": False}).json()
    assert body["reviews"] == [] and body["winner"] is None


@pytest.mark.parametrize("prompt", ["", "   ", None, 5])
def test_invalid_prompts_are_rejected(settings: Settings, prompt: object) -> None:
    assert client_for(settings).post("/ask-council", json={"prompt": prompt}).status_code == 422


def test_missing_prompt_is_rejected(settings: Settings) -> None:
    assert client_for(settings).post("/ask-council", json={}).status_code == 422


def test_overlong_prompt_is_rejected(settings: Settings) -> None:
    response = client_for(settings).post("/ask-council", json={"prompt": "x" * 101})
    assert response.status_code == 422
    assert "too long" in response.json()["detail"]


def test_missing_api_key_is_a_503_with_a_hint(settings: Settings) -> None:
    response = client_for(replace(settings, api_key=None)).post("/ask-council", json={"prompt": "q"})
    assert response.status_code == 503
    assert "OPENROUTER_API_KEY" in response.json()["detail"]


def test_total_failure_is_a_502(settings: Settings) -> None:
    client = client_for(settings, lambda m, p: httpx.Response(401))
    response = client.post("/ask-council", json={"prompt": "q"})
    assert response.status_code == 502
    assert "No council member could answer" in response.json()["detail"]


def test_stream_emits_ndjson_events_ending_in_complete(settings: Settings) -> None:
    response = client_for(settings).post("/ask-council/stream", json={"prompt": "q"})
    assert response.headers["content-type"].startswith("application/x-ndjson")
    events = events_of(response)
    assert [e["type"] for e in events] == ["stage", "answers", "stage", "reviews", "stage", "complete"]
    assert events[-1]["result"]["winner"] == "m1"


def test_stream_reports_total_failure_as_error_event(settings: Settings) -> None:
    client = client_for(settings, lambda m, p: httpx.Response(401))
    events = events_of(client.post("/ask-council/stream", json={"prompt": "q"}))
    assert events[-1]["type"] == "error"
    assert "No council member could answer" in events[-1]["message"]


def test_stream_hides_unexpected_crash_details(settings: Settings) -> None:
    def explode(model: str, prompt: str) -> httpx.Response:
        raise RuntimeError("secret internals")

    events = events_of(client_for(settings, explode).post("/ask-council/stream", json={"prompt": "q"}))
    assert events[-1] == {"type": "error", "message": "The council hit an internal error."}


def test_stream_validates_before_streaming(settings: Settings) -> None:
    client = client_for(replace(settings, api_key=None))
    assert client.post("/ask-council/stream", json={"prompt": "q"}).status_code == 503


def test_cors_allows_only_configured_origins(settings: Settings) -> None:
    client = client_for(settings)
    headers = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
    allowed = client.options("/ask-council", headers={**headers, "Origin": "http://localhost:5173"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    denied = client.options("/ask-council", headers={**headers, "Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in denied.headers
