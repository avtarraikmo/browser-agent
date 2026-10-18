# Task: example-domain-heading-link

Status: Draft (agent-reviewed, not human-approved)

- **Purpose:** smoke test that the agent runs Playwright/Chromium via `execute` and reports page facts.
- **Input:** `instruction.md`.
- **Truth (hidden):** heading is "Example Domain"; the link goes to an `iana.org` URL.
- **Verifier:** reads `answer_written` from `/logs/agent/summary.json`. Reward 1 only if the answer contains "Example Domain" and "iana.org" (case-insensitive); else 0. Missing or corrupt summary writes 0.
- **Fairness:** example.com is stable; needs outbound HTTPS from the container.
- **Invalid run:** no network from the container (infrastructure, not agent failure).
- **Not run yet:** needs Docker and model credentials.
