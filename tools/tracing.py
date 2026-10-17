"""Redact secrets from LangSmith traces before they leave the process.

`fill_with_user_input` pauses with `interrupt()`; the human's answer comes back as
`Command(resume=<value>)`, which LangGraph traces as run input
(`{"resume": "<password>"}`). The tools never return that value to the model, but
the trace would still record it, so it is scrubbed here, client-side, before upload.
"""

from __future__ import annotations

import os
from typing import Any

import langsmith as ls
from langsmith import Client
from langsmith.anonymizer import create_secret_anonymizer

REDACTED = "[REDACTED]"

# `resume` carries human answers to interrupts (passwords, codes, usernames).
_SENSITIVE_KEYS = frozenset({"resume", "password", "passwd", "secret", "token", "otp", "code"})

_detect_secrets = create_secret_anonymizer()


def _scrub(node: Any) -> Any:
    if isinstance(node, dict):
        return {
            key: REDACTED if str(key).lower() in _SENSITIVE_KEYS else _scrub(value)
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [_scrub(item) for item in node]
    return node


def anonymize(data: Any) -> Any:
    return _detect_secrets(_scrub(data))


def install() -> None:
    """Route all LangChain/LangGraph tracing in this process through a redacting client."""
    ls.configure(client=Client(anonymizer=anonymize))


def run_metadata() -> dict[str, str]:
    """Root-run metadata naming the environment (`APP_ENV`, else `local`) that produced a trace."""
    # Passed to `define_deep_agent(metadata=...)`, not `ls.configure(metadata=...)`:
    # the latter sets a context var that LangGraph server runs don't inherit.
    # No `revision_id` here: the LangSmith client already copies
    # LANGSMITH_REVISION_ID into every run's `revision_id` metadata.
    return {"environment": os.environ.get("APP_ENV") or "local"}
