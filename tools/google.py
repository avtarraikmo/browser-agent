"""Connect the caller's Google account through MDA's managed OAuth.

The access token lives in Agent Auth and is injected into sandbox requests to
Gmail by the sandbox proxy (see `sandbox/__init__.py`). It is never returned by a
tool, written into the sandbox, or shown to the model, so it can't reach traces.
"""

from __future__ import annotations

from langchain_core.tools import tool
from managed_deepagents import connections

GOOGLE_CONNECTION = "google"


@tool
async def connect_google() -> str:
    """Connect the user's Google account so the sandbox can read their Gmail.

    If the user hasn't connected yet, this pauses and asks them to authorize with
    Google. Call it before any Gmail request. It never returns the credentials.
    """
    # Raises CredentialAuthorizationRequiredError when no grant exists; MDA turns
    # that into the user-facing OAuth authorization interrupt.
    await connections.get(GOOGLE_CONNECTION, {"type": "user"})
    return (
        "Google account connected. Gmail API requests to https://gmail.googleapis.com "
        "from the sandbox are authenticated automatically; do not add credentials."
    )
