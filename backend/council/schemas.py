"""Response models for the HTTP API (they also drive the OpenAPI docs)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class MemberAnswerOut(BaseModel):
    model: str
    answer: str | None
    error: str | None = None


class ReviewOut(BaseModel):
    reviewer: str
    ranking: list[str]  # model ids, best first; empty when the review was unusable
    error: str | None = None


class LeaderboardEntryOut(BaseModel):
    model: str
    score: float | None  # 1.0 = ranked first by every reviewer, 0.0 = ranked last by all
    average_rank: float | None
    votes: int


class CouncilResult(BaseModel):
    question: str
    individual_responses: list[MemberAnswerOut]
    reviews: list[ReviewOut]
    leaderboard: list[LeaderboardEntryOut]
    winner: str | None
    chairman: str
    council_verdict: str
    verdict_source: Literal["chairman", "fallback"]
    chairman_error: str | None = None


class CouncilConfig(BaseModel):
    members: list[str]
    chairman: str
    max_prompt_chars: int
