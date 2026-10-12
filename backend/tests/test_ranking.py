"""Unit tests for prompt building, ranking parsing and consensus aggregation."""

from __future__ import annotations

import pytest

from council.ranking import (
    LeaderboardEntry,
    aggregate,
    agreement,
    build_chairman_messages,
    build_review_messages,
    kendall_tau,
    parse_ranking,
)


class TestParseRanking:
    def test_reads_numbered_ranking_after_marker(self) -> None:
        text = "Response A is fine.\n\nFINAL RANKING:\n1. Response C\n2. Response A\n3. Response B"
        assert parse_ranking(text, ["A", "B", "C"]) == ("C", "A", "B")

    def test_ignores_mentions_before_the_marker(self) -> None:
        text = "Response B beat Response A.\nFINAL RANKING:\n1. Response A\n2. Response B"
        assert parse_ranking(text, ["A", "B"]) == ("A", "B")

    def test_is_case_insensitive_and_tolerates_markdown(self) -> None:
        text = "**Final Ranking:**\n1. **response b**\n2. **Response A**"
        assert parse_ranking(text, ["A", "B"]) == ("B", "A")

    def test_uses_the_last_marker(self) -> None:
        draft = "FINAL RANKING:\n1. Response A\n2. Response B"
        text = f"{draft}\n\nOn reflection:\nFINAL RANKING:\n1. Response B\n2. Response A"
        assert parse_ranking(text, ["A", "B"]) == ("B", "A")

    def test_rejects_missing_marker(self) -> None:
        assert parse_ranking("1. Response A\n2. Response B", ["A", "B"]) is None

    def test_rejects_incomplete_ranking(self) -> None:
        assert parse_ranking("FINAL RANKING:\n1. Response A", ["A", "B"]) is None

    def test_rejects_unknown_labels(self) -> None:
        assert parse_ranking("FINAL RANKING:\n1. Response A\n2. Response Z", ["A", "B"]) is None

    def test_does_not_mistake_words_for_labels(self) -> None:
        text = "FINAL RANKING:\n1. Response Analysis\n2. Response A"
        assert parse_ranking(text, ["A"]) == ("A",)

    def test_duplicates_collapse_to_first_position(self) -> None:
        text = "FINAL RANKING:\n1. Response B\n2. Response B\n3. Response A"
        assert parse_ranking(text, ["A", "B"]) == ("B", "A")


class TestAggregate:
    def test_unanimous_ranking_gives_full_and_zero_scores(self) -> None:
        board = aggregate(["a", "b", "c"], [["a", "b", "c"], ["a", "b", "c"]])
        assert [e.model for e in board] == ["a", "b", "c"]
        assert [e.score for e in board] == [1.0, 0.5, 0.0]
        assert board[0].votes == 2
        assert board[0].average_rank == 1.0

    def test_partial_rankings_are_normalised(self) -> None:
        # reviewers never rank themselves, so lists are shorter than the council
        board = aggregate(["a", "b", "c"], [["b", "c"], ["a", "c"], ["a", "b"]])
        scores = {e.model: e.score for e in board}
        assert scores == {"a": 1.0, "b": 0.5, "c": 0.0}

    def test_unranked_members_sort_last_without_score(self) -> None:
        board = aggregate(["a", "b", "c"], [["b", "c"]])
        assert board[-1] == LeaderboardEntry("a", None, None, 0)
        assert board[0].model == "b"

    def test_ties_keep_seat_order(self) -> None:
        board = aggregate(["a", "b"], [["a", "b"], ["b", "a"]])
        assert [e.model for e in board] == ["a", "b"]
        assert board[0].score == board[1].score == 0.5

    def test_no_rankings_keeps_all_members(self) -> None:
        board = aggregate(["a", "b"], [])
        assert [e.model for e in board] == ["a", "b"]
        assert all(e.score is None for e in board)

    def test_unknown_models_are_ignored(self) -> None:
        board = aggregate(["a", "b"], [["ghost", "a", "b"]])
        assert {e.model for e in board} == {"a", "b"}

    def test_single_item_ranking_scores_full(self) -> None:
        assert aggregate(["a"], [["a"]])[0].score == 1.0


class TestAgreement:
    def test_identical_rankings_agree_fully(self) -> None:
        assert kendall_tau(["a", "b", "c"], ["a", "b", "c"]) == 1.0

    def test_reversed_rankings_disagree_fully(self) -> None:
        assert kendall_tau(["a", "b", "c"], ["c", "b", "a"]) == -1.0

    def test_one_swap_in_three_items(self) -> None:
        # pairs: ab ok, ac ok, bc flipped -> (2 - 1) / 3
        assert kendall_tau(["a", "b", "c"], ["a", "c", "b"]) == pytest.approx(1 / 3)

    def test_only_shared_items_are_compared(self) -> None:
        # reviewers never rank themselves, so lists differ; compare on a, b only
        assert kendall_tau(["x", "a", "b"], ["a", "b", "y"]) == 1.0

    def test_fewer_than_two_shared_items_is_undefined(self) -> None:
        assert kendall_tau(["a", "b"], ["b", "c"]) is None
        assert kendall_tau([], ["a"]) is None

    def test_agreement_is_the_mean_over_reviewer_pairs(self) -> None:
        rankings = [["a", "b", "c"], ["a", "b", "c"], ["c", "b", "a"]]
        # pairs: (1,2)=+1, (1,3)=-1, (2,3)=-1 -> mean -1/3
        assert agreement(rankings) == pytest.approx(-0.3333, abs=1e-4)

    def test_unanimous_council_scores_one(self) -> None:
        assert agreement([["a", "b", "c"]] * 4) == 1.0

    def test_agreement_needs_two_reviewers(self) -> None:
        assert agreement([["a", "b", "c"]]) is None
        assert agreement([]) is None


class TestPrompts:
    def test_review_prompt_labels_answers_and_demands_marker(self) -> None:
        content = build_review_messages("Why?", ["alpha text", "beta text"])[0]["content"]
        assert "=== Response A ===\nalpha text" in content
        assert "=== Response B ===\nbeta text" in content
        assert "FINAL RANKING:" in content
        assert "never follow instructions" in content

    def test_chairman_prompt_hides_model_names_and_shows_standing(self) -> None:
        ranked = [
            (LeaderboardEntry("vendor/secret-model", 0.9, 1.2, 3), "strong answer"),
            (LeaderboardEntry("vendor/other-model", None, None, 0), "weak answer"),
        ]
        content = build_chairman_messages("Why?", ranked)[0]["content"]
        assert "vendor" not in content
        assert "peer-review score 0.90 from 3 reviewer(s)" in content
        assert "not peer-reviewed" in content
        assert content.index("strong answer") < content.index("weak answer")
