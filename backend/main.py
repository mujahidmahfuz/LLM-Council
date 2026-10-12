"""FastAPI entrypoint: `uvicorn main:app --reload` from the backend directory."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from council.config import Settings, load_env_files, load_settings
from council.pipeline import CouncilError, collect_result, run_council
from council.schemas import CouncilConfig, CouncilResult

logger = logging.getLogger("council")

ClientFactory = Callable[[], httpx.AsyncClient]


class PromptRequest(BaseModel):
    prompt: str = Field(min_length=1)
    peer_review: bool = True

    @field_validator("prompt", mode="before")
    @classmethod
    def _strip_prompt(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


def create_app(settings: Settings, client_factory: ClientFactory = httpx.AsyncClient) -> FastAPI:
    """Build the API. `client_factory` lets tests inject a mocked HTTP transport."""
    app = FastAPI(title="LLM Council", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    def validated(request: PromptRequest) -> PromptRequest:
        if not settings.is_configured:
            raise HTTPException(
                status_code=503,
                detail="OpenRouter API key missing. Set OPENROUTER_API_KEY in backend/.env.",
            )
        if len(request.prompt) > settings.max_prompt_chars:
            raise HTTPException(
                status_code=422,
                detail=f"Prompt is too long (limit {settings.max_prompt_chars} characters).",
            )
        return request

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {"status": "ok", "configured": settings.is_configured}

    @app.get("/config", response_model=CouncilConfig)
    async def council_config() -> CouncilConfig:
        return CouncilConfig(
            members=list(settings.council_models),
            chairman=settings.chairman_model,
            max_prompt_chars=settings.max_prompt_chars,
        )

    @app.post("/ask-council", response_model=CouncilResult)
    async def ask_council(request: PromptRequest) -> dict[str, Any]:
        request = validated(request)
        try:
            async with client_factory() as client:
                return await collect_result(client, settings, request.prompt, peer_review=request.peer_review)
        except CouncilError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/ask-council/stream")
    async def ask_council_stream(request: PromptRequest) -> StreamingResponse:
        request = validated(request)

        async def events() -> AsyncIterator[str]:
            try:
                async with client_factory() as client:
                    async for event in run_council(
                        client, settings, request.prompt, peer_review=request.peer_review
                    ):
                        yield json.dumps(event) + "\n"
            except CouncilError as exc:
                yield json.dumps({"type": "error", "message": str(exc)}) + "\n"
            except Exception:
                logger.exception("council run crashed")
                yield json.dumps({"type": "error", "message": "The council hit an internal error."}) + "\n"

        return StreamingResponse(events(), media_type="application/x-ndjson")

    return app


load_env_files()
app = create_app(load_settings())
