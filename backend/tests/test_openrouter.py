"""Tests for the OpenRouter client: parsing, retries and error mapping."""

from __future__ import annotations

from dataclasses import replace

import httpx
import pytest

from council.config import Settings
from council.openrouter import ModelCallError, chat
from tests.conftest import make_client, reply

MESSAGES = [{"role": "user", "content": "hi"}]

pytestmark = pytest.mark.anyio


async def test_returns_stripped_text(settings: Settings) -> None:
    async with make_client(lambda m, p: reply("  hello  ")) as client:
        assert await chat(client, settings, "m", MESSAGES) == "hello"


async def test_sends_model_messages_and_auth_header(settings: Settings) -> None:
    seen: list[httpx.Request] = []

    def route(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return reply("ok")

    async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as client:
        await chat(client, settings, "vendor/model", MESSAGES)

    request = seen[0]
    assert request.headers["authorization"] == "Bearer test-key"
    assert request.url.path.endswith("/chat/completions")
    assert b'"model":"vendor/model"' in request.content.replace(b" ", b"")


async def test_missing_key_fails_without_a_request(settings: Settings) -> None:
    calls: list[str] = []
    async with make_client(lambda m, p: calls.append(m) or reply("x")) as client:
        with pytest.raises(ModelCallError, match="not configured"):
            await chat(client, replace(settings, api_key=None), "m", MESSAGES)
    assert calls == []


async def test_retries_rate_limit_then_succeeds(settings: Settings, instant_sleep: list[float]) -> None:
    responses = iter([httpx.Response(429), reply("finally")])
    async with make_client(lambda m, p: next(responses)) as client:
        assert await chat(client, settings, "m", MESSAGES) == "finally"
    assert instant_sleep == [1.5]


async def test_honours_retry_after_header_with_a_cap(settings: Settings, instant_sleep: list[float]) -> None:
    responses = iter([httpx.Response(429, headers={"retry-after": "999"}), reply("ok")])
    async with make_client(lambda m, p: next(responses)) as client:
        await chat(client, settings, "m", MESSAGES)
    assert instant_sleep == [20.0]


async def test_gives_up_after_max_retries(settings: Settings) -> None:
    attempts: list[str] = []

    def handler(model: str, prompt: str) -> httpx.Response:
        attempts.append(model)
        return httpx.Response(503)

    async with make_client(handler) as client:
        with pytest.raises(ModelCallError, match="HTTP 503"):
            await chat(client, settings, "m", MESSAGES)
    assert len(attempts) == settings.max_retries + 1


@pytest.mark.parametrize("status", [401, 402, 404])
async def test_client_errors_are_not_retried(settings: Settings, status: int) -> None:
    attempts: list[str] = []

    def handler(model: str, prompt: str) -> httpx.Response:
        attempts.append(model)
        return httpx.Response(status)

    async with make_client(handler) as client:
        with pytest.raises(ModelCallError, match=f"HTTP {status}"):
            await chat(client, settings, "m", MESSAGES)
    assert len(attempts) == 1


async def test_error_message_never_contains_the_api_key(settings: Settings) -> None:
    async with make_client(lambda m, p: httpx.Response(401, text="Bearer test-key rejected")) as client:
        with pytest.raises(ModelCallError) as info:
            await chat(client, settings, "m", MESSAGES)
    assert "test-key" not in str(info.value)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"error": "nope"}),
    ],
)
async def test_malformed_payload_is_an_error(settings: Settings, response: httpx.Response) -> None:
    async with make_client(lambda m, p: response) as client:
        with pytest.raises(ModelCallError, match="malformed"):
            await chat(client, settings, "m", MESSAGES)


@pytest.mark.parametrize("content", [None, "", "   "])
async def test_empty_answer_is_an_error(settings: Settings, content: str | None) -> None:
    body = httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    async with make_client(lambda m, p: body) as client:
        with pytest.raises(ModelCallError, match="empty"):
            await chat(client, settings, "m", MESSAGES)


async def test_timeouts_are_retried_then_reported(settings: Settings) -> None:
    def route(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as client:
        with pytest.raises(ModelCallError, match="timed out after 5s"):
            await chat(client, settings, "m", MESSAGES)


async def test_network_errors_are_reported(settings: Settings) -> None:
    def route(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as client:
        with pytest.raises(ModelCallError, match="network error"):
            await chat(client, replace(settings, max_retries=0), "m", MESSAGES)
