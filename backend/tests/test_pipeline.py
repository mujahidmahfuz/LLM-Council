"""End-to-end tests of the council pipeline against a scripted fake OpenRouter."""

from __future__ import annotations

import asyncio
import random
from dataclasses import replace

import httpx
import pytest

from council.config import Settings
from council.pipeline import CouncilError, collect_result, run_council
from tests.conftest import CHAIRMAN, make_client, reply, scripted_reply

pytestmark = pytest.mark.anyio


async def test_full_council_ranks_by_consensus(settings: Settings) -> None:
    async with make_client(scripted_reply) as client:
        result = await collect_result(client, settings, "What is 2+2?")

    board = {e["model"]: e for e in result["leaderboard"]}
    assert [e["model"] for e in result["leaderboard"]] == ["m1", "m2", "m3", "m4"]
    assert board["m1"]["score"] == 1.0
    assert board["m4"]["score"] == 0.0
    assert board["m2"]["score"] == pytest.approx(0.6667)
    assert all(e["votes"] == 3 for e in board.values())
    assert result["winner"] == "m1"
    assert result["chairman"] == CHAIRMAN
    assert result["council_verdict"] == "FINAL VERDICT"
    assert result["verdict_source"] == "chairman"
    assert result["chairman_error"] is None
    assert len(result["reviews"]) == 4
    assert [r["answer"] for r in result["individual_responses"]] == [f"ANSWER-m{i}" for i in range(1, 5)]


async def test_events_arrive_in_stage_order(settings: Settings) -> None:
    async with make_client(scripted_reply) as client:
        events = [e async for e in run_council(client, settings, "q")]

    assert [e["type"] for e in events] == ["stage", "answers", "stage", "reviews", "stage", "complete"]
    assert [e["stage"] for e in events if e["type"] == "stage"] == ["answers", "reviews", "verdict"]


async def test_reviewers_see_anonymous_answers_without_their_own(settings: Settings) -> None:
    review_prompts: dict[str, str] = {}

    def handler(model: str, prompt: str) -> httpx.Response:
        if "peer-reviewing" in prompt:
            review_prompts[model] = prompt
        return scripted_reply(model, prompt)

    async with make_client(handler) as client:
        await collect_result(client, settings, "q")

    assert set(review_prompts) == {"m1", "m2", "m3", "m4"}
    for reviewer, prompt in review_prompts.items():
        assert f"ANSWER-{reviewer}" not in prompt, "reviewer must not see its own answer"
        assert prompt.count("=== Response ") == 3  # exactly the three other members
        # only answer text appears: the model ids themselves never leak into the prompt
        assert "m1" not in prompt.replace("ANSWER-m1", "")


async def test_chairman_sees_answers_best_first_without_names(settings: Settings) -> None:
    chairman_prompts: list[str] = []

    def handler(model: str, prompt: str) -> httpx.Response:
        if model == CHAIRMAN:
            chairman_prompts.append(prompt)
        return scripted_reply(model, prompt)

    async with make_client(handler) as client:
        await collect_result(client, settings, "q")

    prompt = chairman_prompts[0]
    positions = [prompt.index(f"ANSWER-m{i}") for i in range(1, 5)]
    assert positions == sorted(positions)
    assert "peer-review score 1.00 from 3 reviewer(s)" in prompt


async def test_failed_member_is_reported_and_council_continues(settings: Settings) -> None:
    def handler(model: str, prompt: str) -> httpx.Response:
        if model == "m3" and "peer-reviewing" not in prompt and "Chairman" not in prompt:
            return httpx.Response(404)
        return scripted_reply(model, prompt)

    async with make_client(handler) as client:
        result = await collect_result(client, settings, "q")

    failed = next(r for r in result["individual_responses"] if r["model"] == "m3")
    assert failed["answer"] is None
    assert "HTTP 404" in failed["error"]
    assert {e["model"] for e in result["leaderboard"]} == {"m1", "m2", "m4"}
    assert len(result["reviews"]) == 3
    assert result["winner"] == "m1"


async def test_all_members_failing_raises(settings: Settings) -> None:
    async with make_client(lambda m, p: httpx.Response(401)) as client:
        with pytest.raises(CouncilError, match="No council member could answer") as info:
            await collect_result(client, settings, "q")
    assert "m1: HTTP 401" in str(info.value)


async def test_chairman_failure_falls_back_to_top_ranked_answer(settings: Settings) -> None:
    def handler(model: str, prompt: str) -> httpx.Response:
        return httpx.Response(503) if model == CHAIRMAN else scripted_reply(model, prompt)

    async with make_client(handler) as client:
        result = await collect_result(client, settings, "q")

    assert result["verdict_source"] == "fallback"
    assert result["council_verdict"] == "ANSWER-m1"
    assert "HTTP 503" in result["chairman_error"]


async def test_unparseable_review_is_dropped_but_others_count(settings: Settings) -> None:
    def handler(model: str, prompt: str) -> httpx.Response:
        if "peer-reviewing" in prompt and model == "m2":
            return reply("I refuse to rank these.")
        return scripted_reply(model, prompt)

    async with make_client(handler) as client:
        result = await collect_result(client, settings, "q")

    bad = next(r for r in result["reviews"] if r["reviewer"] == "m2")
    assert not bad["ranking"] and "parse" in bad["error"]
    assert result["winner"] == "m1"
    assert next(e for e in result["leaderboard"] if e["model"] == "m1")["votes"] == 2


async def test_failed_reviewer_call_is_recorded(settings: Settings) -> None:
    def handler(model: str, prompt: str) -> httpx.Response:
        if "peer-reviewing" in prompt and model == "m4":
            return httpx.Response(402)
        return scripted_reply(model, prompt)

    async with make_client(handler) as client:
        result = await collect_result(client, settings, "q")

    bad = next(r for r in result["reviews"] if r["reviewer"] == "m4")
    assert "HTTP 402" in bad["error"]


async def test_peer_review_can_be_skipped(settings: Settings) -> None:
    async with make_client(scripted_reply) as client:
        events = [e async for e in run_council(client, settings, "q", peer_review=False)]

    assert [e["stage"] for e in events if e["type"] == "stage"] == ["answers", "verdict"]
    result = events[-1]["result"]
    assert result["reviews"] == []
    assert result["winner"] is None
    assert all(e["score"] is None for e in result["leaderboard"])
    assert result["council_verdict"] == "FINAL VERDICT"


async def test_two_survivors_skip_peer_review(settings: Settings) -> None:
    def handler(model: str, prompt: str) -> httpx.Response:
        if model in {"m3", "m4"} and "Chairman" not in prompt:
            return httpx.Response(404)
        return scripted_reply(model, prompt)

    async with make_client(handler) as client:
        result = await collect_result(client, settings, "q")

    assert result["reviews"] == []
    assert result["winner"] is None
    assert result["council_verdict"] == "FINAL VERDICT"


async def test_single_survivor_still_gets_a_ruling(settings: Settings) -> None:
    def handler(model: str, prompt: str) -> httpx.Response:
        if model not in {"m2", CHAIRMAN}:
            return httpx.Response(404)
        return scripted_reply(model, prompt)

    async with make_client(handler) as client:
        result = await collect_result(client, settings, "q")

    assert [e["model"] for e in result["leaderboard"]] == ["m2"]
    assert result["council_verdict"] == "FINAL VERDICT"


async def test_concurrency_limit_is_respected(settings: Settings) -> None:
    active = peak = 0

    async def slow_route(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return reply("ANSWER-x")

    async with httpx.AsyncClient(transport=httpx.MockTransport(slow_route)) as client:
        await collect_result(client, replace(settings, max_concurrency=1), "q", peer_review=False)

    assert peak == 1


async def test_review_order_is_reproducible_with_a_seed(settings: Settings) -> None:
    async def shown_order(seed: int) -> list[str]:
        order: list[str] = []

        def handler(model: str, prompt: str) -> httpx.Response:
            if "peer-reviewing" in prompt and model == "m1":
                order.extend(part for part in prompt.split() if part.startswith("ANSWER-"))
            return scripted_reply(model, prompt)

        async with make_client(handler) as client:
            async for _ in run_council(client, settings, "q", rng=random.Random(seed)):
                pass
        return order

    first = await shown_order(7)
    assert len(first) == 3
    assert first == await shown_order(7)
