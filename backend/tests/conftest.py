"""Shared fixtures: settings, a scripted fake OpenRouter, and instant retries."""

from __future__ import annotations

import json
import re
from collections.abc import Callable

import httpx
import pytest

from council.config import Settings

MEMBERS = ("m1", "m2", "m3", "m4")
CHAIRMAN = "chair"
# Fake quality order used by the scripted reviewers: m1 is best, m4 is worst.
QUALITY = {f"ANSWER-{m}": i for i, m in enumerate(MEMBERS)}

Handler = Callable[[str, str], httpx.Response]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        api_key="test-key",
        council_models=MEMBERS,
        chairman_model=CHAIRMAN,
        max_concurrency=2,
        request_timeout=5.0,
        max_retries=1,
        allowed_origins=("http://localhost:5173",),
        max_prompt_chars=100,
    )


@pytest.fixture(autouse=True)
def instant_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Skip real backoff delays; the recorded delays are returned for assertions."""
    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr("council.openrouter.asyncio.sleep", fake_sleep)
    return delays


def reply(text: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


def scripted_reply(model: str, prompt: str) -> httpx.Response:
    """A well-behaved council: members answer, reviewers rank by QUALITY, chair rules."""
    if "peer-reviewing" in prompt:
        blocks = re.findall(r"=== (Response [A-Z]) ===\n(.*?)\n=== end of", prompt, re.S)
        ranked = sorted(blocks, key=lambda b: QUALITY[b[1]])
        lines = "\n".join(f"{n}. {label}" for n, (label, _) in enumerate(ranked, start=1))
        return reply(f"Thoughtful critique.\n\nFINAL RANKING:\n{lines}")
    if "Chairman" in prompt:
        return reply("FINAL VERDICT")
    return reply(f"ANSWER-{model}")


def make_client(handler: Handler) -> httpx.AsyncClient:
    """An AsyncClient whose requests are answered by `handler(model, prompt)`."""

    def route(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return handler(body["model"], body["messages"][-1]["content"])

    return httpx.AsyncClient(transport=httpx.MockTransport(route))
