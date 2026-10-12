"""Pilot study: the council vs single models on objective IoT questions.

Run from the repo root (needs a real OpenRouter key in backend/.env or key.env):

    python experiments/pilot.py

Writes experiments/results/pilot_raw.json. Analysis lives in analyze.py.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))

from council.config import load_env_files, load_settings  # noqa: E402
from council.pipeline import CouncilError, run_council  # noqa: E402

FORMAT_HINT = "Reply with `ANSWER: <letter>` on the first line, then one or two sentences of reasoning."
ANSWER_PATTERN = re.compile(r"ANSWER:\s*\**\s*\(?([A-D])\b", re.IGNORECASE)


def extract_letter(text: str | None) -> str | None:
    """The last `ANSWER: X` in `text`, or None."""
    found = ANSWER_PATTERN.findall(text or "")
    return found[-1].upper() if found else None


def build_prompt(item: dict) -> str:
    options = "\n".join(f"{key}) {value}" for key, value in item["options"].items())
    return f"{item['question']}\n{options}\n\n{FORMAT_HINT}"


async def run_one(client: httpx.AsyncClient, settings, item: dict) -> dict:
    started = time.monotonic()
    record = {"id": item["id"], "topic": item["topic"], "truth": item["answer"]}
    result = None
    try:
        async for event in run_council(client, settings, build_prompt(item)):
            if event["type"] == "complete":
                result = event["result"]
    except CouncilError as exc:
        return {**record, "error": str(exc), "seconds": round(time.monotonic() - started, 1)}

    return {
        **record,
        "members": {r["model"]: extract_letter(r["answer"]) for r in result["individual_responses"]},
        "leaderboard": result["leaderboard"],
        "reviews": result["reviews"],
        "agreement": result["agreement"],
        "winner": result["winner"],
        "chairman_letter": extract_letter(result["council_verdict"]),
        "verdict_source": result["verdict_source"],
        "verdict": result["council_verdict"],
        "seconds": round(time.monotonic() - started, 1),
    }


async def main() -> None:
    load_env_files()
    settings = load_settings()
    if not settings.is_configured:
        sys.exit("No OpenRouter key configured.")
    items = json.loads((HERE / "iot_questions.json").read_text(encoding="utf-8"))
    only = {part.strip() for part in sys.argv[2].split(",")} if sys.argv[1:2] == ["--only"] else None
    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    raw_path = out_dir / "pilot_raw.json"

    # Keep earlier good rows so the pilot can be completed over several days
    # (the free OpenRouter tier allows 50 free-model requests per day).
    kept: dict[str, dict] = {}
    if raw_path.exists():
        previous = json.loads(raw_path.read_text(encoding="utf-8"))
        kept = {r["id"]: r for r in previous["rows"] if "error" not in r}

    todo = [i for i in items if (only is None or i["id"] in only) and i["id"] not in kept]
    async with httpx.AsyncClient() as client:
        for item in todo:
            row = await run_one(client, settings, item)
            status = row.get("error", f"chairman={row.get('chairman_letter')} truth={row['truth']}")
            print(f"{row['id']}: {status} ({row['seconds']}s)", flush=True)
            if "error" not in row:
                kept[row["id"]] = row

    order = {item["id"]: n for n, item in enumerate(items)}
    rows = sorted(kept.values(), key=lambda r: order[r["id"]])
    payload = {
        "members": list(settings.council_models),
        "chairman": settings.chairman_model,
        "rows": rows,
    }
    raw_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"saved {len(rows)} scored rows")


if __name__ == "__main__":
    asyncio.run(main())
