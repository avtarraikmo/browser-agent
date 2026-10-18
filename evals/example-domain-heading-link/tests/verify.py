"""Score the final answer against the facts on example.com."""

from __future__ import annotations

import json
from pathlib import Path

SUMMARY = Path("/logs/agent/summary.json")
REWARD = Path("/logs/verifier/reward.txt")


def score(answer: str) -> int:
    text = answer.lower()
    return int("example domain" in text and "iana.org" in text)


def main() -> None:
    try:
        answer = json.loads(SUMMARY.read_text(encoding="utf-8")).get("answer_written") or ""
    except (OSError, ValueError):
        answer = ""
    REWARD.parent.mkdir(parents=True, exist_ok=True)
    REWARD.write_text(str(score(str(answer))), encoding="utf-8")


if __name__ == "__main__":
    main()
