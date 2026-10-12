"""Turn pilot_raw.json into accuracy numbers and charts.

    python experiments/analyze.py

Methods compared on the same questions and the same member answers:
  single model    each member alone (and their average)
  majority vote   most common letter among members (ties go to the earlier seat)
  council winner  the answer of the member the peers ranked first
  chairman        the council's final ruling
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RESULTS = Path(__file__).resolve().parent / "results"
INK, BLUE, GOLD, GREEN, GREY = "#1c2333", "#3b5bdb", "#d9a400", "#2b9348", "#b9c0d4"


def short(model: str) -> str:
    return model.split("/", 1)[-1].replace(":free", "")


def majority(letters: list[str | None]) -> str | None:
    counts = Counter(x for x in letters if x)
    if not counts:
        return None
    best = max(counts.values())
    return next(x for x in letters if x and counts[x] == best)


def main() -> None:
    data = json.loads((RESULTS / "pilot_raw.json").read_text(encoding="utf-8"))
    members, rows = data["members"], [r for r in data["rows"] if "error" not in r]
    n = len(rows)

    single = {m: sum(r["members"].get(m) == r["truth"] for r in rows) / n for m in members}
    answered = {m: sum(r["members"].get(m) is not None for r in rows) for m in members}
    maj = sum(majority([r["members"].get(m) for m in members]) == r["truth"] for r in rows) / n
    winner_ok = [
        r["winner"] is not None and r["members"].get(r["winner"]) == r["truth"] for r in rows
    ]
    chair = sum(r["chairman_letter"] == r["truth"] for r in rows) / n

    summary = {
        "questions_scored": n,
        "questions_failed": len(data["rows"]) - n,
        "single_model_accuracy": single,
        "single_model_answered": answered,
        "single_model_mean": float(np.mean(list(single.values()))),
        "single_model_best": max(single.values()),
        "majority_vote": maj,
        "council_winner": sum(winner_ok) / n,
        "chairman": chair,
        "mean_seconds_per_question": round(float(np.mean([r["seconds"] for r in rows])), 1),
    }
    (RESULTS / "pilot_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

    # Chart 1: accuracy by method
    labels = [short(m) for m in members] + ["Single model\n(average)", "Majority\nvote", "Council\nwinner", "Council\nchairman"]
    values = [single[m] for m in members] + [summary["single_model_mean"], maj, summary["council_winner"], chair]
    colors = [GREY] * len(members) + ["#7c93ff", BLUE, GOLD, GREEN]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    bars = ax.bar(range(len(values)), [v * 100 for v in values], color=colors, edgecolor=INK, lw=0.8)
    for bar, v in zip(bars, values, strict=True):
        ax.text(bar.get_x() + bar.get_width() / 2, v * 100 + 1.5, f"{v * 100:.0f}%", ha="center", fontsize=9.5)
    ax.set_xticks(range(len(values)))
    ax.set_xticklabels(labels, fontsize=8.5)
    ax.set_ylabel("Correct answers (%)")
    ax.set_ylim(0, 112)
    ax.set_title(f"Pilot: {n} IoT multiple-choice questions", fontsize=11, loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(RESULTS / "fig_accuracy.png", dpi=200, facecolor="white")
    plt.close(fig)

    # Chart 2: consensus score of each member on each question (cross = that member was wrong)
    grid = np.full((len(members), n), np.nan)
    wrong = np.zeros((len(members), n), dtype=bool)
    for j, r in enumerate(rows):
        scores = {e["model"]: e["score"] for e in r["leaderboard"]}
        for i, m in enumerate(members):
            if scores.get(m) is not None:
                grid[i, j] = scores[m]
            wrong[i, j] = r["members"].get(m) != r["truth"]
    fig, ax = plt.subplots(figsize=(10, 3.9))
    im = ax.imshow(grid, aspect="auto", cmap="YlGnBu", vmin=0, vmax=1)
    for i in range(len(members)):
        for j in range(n):
            if wrong[i, j]:
                ax.text(j, i, "X", ha="center", va="center", color="#d62839", fontsize=12, fontweight="bold")
            elif not np.isnan(grid[i, j]):
                ax.text(j, i, f"{grid[i, j] * 100:.0f}", ha="center", va="center", fontsize=8.5, color=INK)
    ax.set_xticks(range(n))
    ax.set_xticklabels([r["id"] for r in rows], fontsize=9)
    ax.set_yticks(range(len(members)))
    ax.set_yticklabels([short(m) for m in members], fontsize=9)
    ax.set_title("Consensus score per member (red X = that member answered wrongly)", fontsize=11, loc="left")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02, label="peer score")
    fig.tight_layout()
    fig.savefig(RESULTS / "fig_scores.png", dpi=200, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
