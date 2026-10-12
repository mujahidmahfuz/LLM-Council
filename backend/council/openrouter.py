"""Minimal async OpenRouter chat-completions client with bounded retries."""

from __future__ import annotations

import asyncio
import logging

import httpx

from .config import Settings

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
BACKOFF_BASE_SECONDS = 1.5
MAX_RETRY_AFTER_SECONDS = 20.0

_STATUS_HINTS = {
    401: "invalid or missing API key",
    402: "insufficient credits for this model",
    403: "request refused (key lacks access or content was flagged)",
    404: "model not found (it may have left the free tier)",
    429: "rate limited",
}


class ModelCallError(Exception):
    """A single model call failed. The message is safe to show to end users."""


def _retry_delay(attempt: int, response: httpx.Response | None) -> float:
    if response is not None:
        retry_after = response.headers.get("retry-after", "")
        if retry_after.isdigit():
            return min(float(retry_after), MAX_RETRY_AFTER_SECONDS)
    return BACKOFF_BASE_SECONDS * (2**attempt)


def _describe_status(response: httpx.Response) -> str:
    status = response.status_code
    hint = _STATUS_HINTS.get(status, "upstream error")
    return f"HTTP {status}: {hint}"


def _extract_text(response: httpx.Response) -> str:
    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ModelCallError("malformed response from OpenRouter") from exc
    if not isinstance(content, str) or not content.strip():
        raise ModelCallError("model returned an empty answer")
    return content.strip()


async def chat(
    client: httpx.AsyncClient,
    settings: Settings,
    model: str,
    messages: list[dict[str, str]],
) -> str:
    """Send `messages` to `model` and return the reply text.

    Retries rate limits, 5xx errors and timeouts with exponential backoff.
    Raises `ModelCallError` on any failure.
    """
    if not settings.api_key:
        raise ModelCallError("OpenRouter API key is not configured")

    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/mujahidmahfuz/LLM-Council",
        "X-Title": "LLM Council",
    }
    body = {"model": model, "messages": messages}
    url = f"{settings.base_url}/chat/completions"

    last_error = "unknown error"
    for attempt in range(settings.max_retries + 1):
        response: httpx.Response | None = None
        try:
            response = await client.post(url, headers=headers, json=body, timeout=settings.request_timeout)
        except httpx.TimeoutException:
            last_error = f"timed out after {settings.request_timeout:g}s"
        except httpx.HTTPError as exc:
            last_error = f"network error ({type(exc).__name__})"
        else:
            if response.status_code == 200:
                return _extract_text(response)
            last_error = _describe_status(response)
            if response.status_code not in RETRYABLE_STATUS:
                break

        if attempt < settings.max_retries:
            delay = _retry_delay(attempt, response)
            logger.warning("%s failed (%s); retrying in %.1fs", model, last_error, delay)
            await asyncio.sleep(delay)

    raise ModelCallError(last_error)
