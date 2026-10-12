"""The three-stage council: answer, peer review, chairman's ruling."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import httpx

from .config import Settings
from .openrouter import ModelCallError, chat
from .ranking import (
    LABEL_LETTERS,
    LeaderboardEntry,
    aggregate,
    build_answer_messages,
    build_chairman_messages,
    build_review_messages,
    parse_ranking,
)

logger = logging.getLogger(__name__)

MIN_MEMBERS_FOR_PEER_REVIEW = 3  # with two members each reviewer would rank a single answer

Event = dict[str, Any]
Messages = list[dict[str, str]]
ModelCall = Callable[[str, Messages], Awaitable[str]]


class CouncilError(Exception):
    """The council could not reach any verdict. The message is safe to show to users."""


@dataclass(frozen=True)
class MemberAnswer:
    model: str
    answer: str | None
    error: str | None = None


@dataclass(frozen=True)
class Review:
    reviewer: str
    ranking: tuple[str, ...]  # model ids, best first; empty if the review was unusable
    error: str | None = None


async def run_council(
    client: httpx.AsyncClient,
    settings: Settings,
    prompt: str,
    *,
    peer_review: bool = True,
    rng: random.Random | None = None,
) -> AsyncIterator[Event]:
    """Run the council, yielding progress events and a final `complete` event.

    Raises `CouncilError` when no member can answer.
    """
    shuffler = rng or random.Random()
    gate = asyncio.Semaphore(settings.max_concurrency)

    async def call(model: str, messages: Messages) -> str:
        async with gate:
            return await chat(client, settings, model, messages)

    members = settings.council_models

    yield {"type": "stage", "stage": "answers", "models": list(members)}
    answers = await asyncio.gather(*(_ask_member(call, m, prompt) for m in members))
    yield {"type": "answers", "answers": [asdict(a) for a in answers]}

    answered = [a for a in answers if a.answer]
    if not answered:
        reasons = "; ".join(f"{a.model}: {a.error}" for a in answers)
        raise CouncilError(f"No council member could answer. {reasons}")

    reviews: list[Review] = []
    if peer_review and len(answered) >= MIN_MEMBERS_FOR_PEER_REVIEW:
        yield {"type": "stage", "stage": "reviews", "models": [a.model for a in answered]}
        reviews = list(
            await asyncio.gather(*(_review(call, a, answered, prompt, shuffler) for a in answered))
        )
    leaderboard = aggregate([a.model for a in answered], [r.ranking for r in reviews if r.ranking])
    winner = leaderboard[0].model if leaderboard[0].score is not None else None
    yield {
        "type": "reviews",
        "reviews": [asdict(r) for r in reviews],
        "leaderboard": [asdict(e) for e in leaderboard],
        "winner": winner,
    }

    yield {"type": "stage", "stage": "verdict", "models": [settings.chairman_model]}
    verdict, source, chairman_error = await _chairman_ruling(
        call, settings.chairman_model, prompt, leaderboard, answered
    )
    result = {
        "question": prompt,
        "individual_responses": [asdict(a) for a in answers],
        "reviews": [asdict(r) for r in reviews],
        "leaderboard": [asdict(e) for e in leaderboard],
        "winner": winner,
        "chairman": settings.chairman_model,
        "council_verdict": verdict,
        "verdict_source": source,
        "chairman_error": chairman_error,
    }
    yield {"type": "complete", "result": result}


async def collect_result(
    client: httpx.AsyncClient, settings: Settings, prompt: str, *, peer_review: bool = True
) -> dict[str, Any]:
    """Run the whole council and return only the final result."""
    async for event in run_council(client, settings, prompt, peer_review=peer_review):
        if event["type"] == "complete":
            return event["result"]
    raise CouncilError("The council ended without a verdict.")  # pragma: no cover


async def _ask_member(call: ModelCall, model: str, prompt: str) -> MemberAnswer:
    try:
        return MemberAnswer(model=model, answer=await call(model, build_answer_messages(prompt)))
    except ModelCallError as exc:
        logger.warning("member %s failed: %s", model, exc)
        return MemberAnswer(model=model, answer=None, error=str(exc))


async def _review(
    call: ModelCall,
    reviewer: MemberAnswer,
    answered: Sequence[MemberAnswer],
    prompt: str,
    shuffler: random.Random,
) -> Review:
    """`reviewer` ranks everyone else's answer, shown anonymised in random order."""
    others = [a for a in answered if a.model != reviewer.model]
    shuffler.shuffle(others)
    letters = list(LABEL_LETTERS[: len(others)])
    messages = build_review_messages(prompt, [a.answer or "" for a in others])
    try:
        reply = await call(reviewer.model, messages)
    except ModelCallError as exc:
        logger.warning("reviewer %s failed: %s", reviewer.model, exc)
        return Review(reviewer=reviewer.model, ranking=(), error=str(exc))

    parsed = parse_ranking(reply, letters)
    if parsed is None:
        return Review(reviewer=reviewer.model, ranking=(), error="could not parse a complete ranking")
    by_letter = dict(zip(letters, others, strict=True))
    return Review(reviewer=reviewer.model, ranking=tuple(by_letter[x].model for x in parsed))


async def _chairman_ruling(
    call: ModelCall,
    chairman: str,
    prompt: str,
    leaderboard: Sequence[LeaderboardEntry],
    answered: Sequence[MemberAnswer],
) -> tuple[str, str, str | None]:
    """Return (verdict text, source, chairman error). Falls back to the top answer."""
    text_by_model = {a.model: a.answer or "" for a in answered}
    ranked = [(entry, text_by_model[entry.model]) for entry in leaderboard]
    try:
        verdict = await call(chairman, build_chairman_messages(prompt, ranked))
    except ModelCallError as exc:
        logger.warning("chairman %s failed: %s", chairman, exc)
        return ranked[0][1], "fallback", str(exc)
    return verdict, "chairman", None
