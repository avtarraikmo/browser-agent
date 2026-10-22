"""Fail unless the reply follows the page-details format and reports not logged in."""

from __future__ import annotations

import json
import re
from pathlib import Path

SUMMARY = Path("/logs/agent/summary.json")
RESULT = Path("/logs/agent/result.json")
REWARD = Path("/logs/verifier/reward.txt")


def commands_run(result: object) -> list[str]:
    """Every `execute` command string the agent issued, from tool-call arguments."""
    messages = result.get("messages") if isinstance(result, dict) else None
    out: list[str] = []
    for message in messages if isinstance(messages, list) else []:
        if not isinstance(message, dict) or message.get("type") not in {"ai", "AIMessage"}:
            continue
        for call in message.get("tool_calls") or []:
            args = call.get("args") if isinstance(call, dict) else None
            command = args.get("command") if isinstance(args, dict) else None
            if isinstance(command, str):
                out.append(command)
    return out


def score(answer: str, commands: list[str]) -> int:
    checks = (
        r"URL:\**\s*https?://(www\.)?example\.com",
        r"Logged in:\**\s*(No|Unclear)\b",  # example.com has no account UI; "Yes" is wrong
        r"Summary:",
        r"Actions available",
    )
    return int(all(re.search(p, answer, re.I) for p in checks))


def _read(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def main() -> None:
    summary = _read(SUMMARY)
    answer = summary.get("answer_written") if isinstance(summary, dict) else ""
    reward = score(str(answer or ""), commands_run(_read(RESULT)))
    REWARD.parent.mkdir(parents=True, exist_ok=True)
    REWARD.write_text(str(reward), encoding="utf-8")


if __name__ == "__main__":
    main()
