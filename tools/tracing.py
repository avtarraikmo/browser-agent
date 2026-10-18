"""Redact secrets from LangSmith traces before they leave the process.

`fill_with_user_input` pauses with `interrupt()`; the human's answer comes back as
`Command(resume=<value>)`, which LangGraph traces as run input
(`{"resume": "<password>"}`). The tools never return that value to the model, but
the trace would still record it, so it is scrubbed here, client-side, before upload.
"""

from __future__ import annotations

import json
import re
from typing import Any

import langsmith as ls
from langsmith import Client
from langsmith.anonymizer import create_secret_anonymizer

REDACTED = "[REDACTED]"

# `resume` carries human answers to interrupts (passwords, codes, usernames).
_SENSITIVE_KEYS = frozenset({"resume", "password", "passwd", "secret", "token", "otp", "code"})

_detect_secrets = create_secret_anonymizer()

_SHELL_WORD = r"""(?:'[^']*'|"(?:\\.|[^"\\])*"|[^\s'"])+"""
# `browser_cli.py type SEL TEXT`: TEXT is whatever the model typed, often a password.
_TYPED_TEXT = re.compile(rf"(browser_cli\.py\s+type\s+(?:--enter\s+)?{_SHELL_WORD}\s+(?:--enter\s+)?){_SHELL_WORD}")
# Snapshot lines end with the field's value; tool output carries them raw or JSON-escaped.
_PASSWORD_TEXTBOX = re.compile(
    r'(textbox +\\*"[^"\n]*?password[^"\n]*?\\*"(?: *\[[^\]\n]*\])*: ?).+?(?=\\n|\n|"[,}]|$)', re.IGNORECASE
)


def _scrub_text(text: str) -> str:
    # Tool-call arguments arrive as JSON strings, where a regex can't tell where the command ends.
    if text.lstrip().startswith(("{", "[")):
        try:
            parsed = json.loads(text)
        except ValueError:
            pass
        else:
            scrubbed = _scrub(parsed)
            return json.dumps(scrubbed) if scrubbed != parsed else text
    scrubbed = _PASSWORD_TEXTBOX.sub(rf"\g<1>{REDACTED}", _TYPED_TEXT.sub(rf"\g<1>{REDACTED}", text))
    return scrubbed if scrubbed != text else text


def _scrub(node: Any) -> Any:
    if isinstance(node, dict):
        return {
            key: REDACTED if str(key).lower() in _SENSITIVE_KEYS else _scrub(value)
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [_scrub(item) for item in node]
    if isinstance(node, str):
        return _scrub_text(node)
    return node


def anonymize(data: Any) -> Any:
    return _detect_secrets(_scrub(data))


def install() -> None:
    """Route all LangChain/LangGraph tracing in this process through a redacting client."""
    ls.configure(client=Client(anonymizer=anonymize))
