# Task: page-details-format

Status: Draft (agent-reviewed, not human-approved)

- **Purpose:** every page reply uses the `page-details` skill's format (URL, Logged in, Summary, Actions available), even for a bare request.
- **Input:** `instruction.md` (no mention of the skill or the format).
- **Truth (hidden):** example.com shows no login or account controls, so "Logged in" must be No or Unclear, never Yes.
- **Verifier:** reads `answer_written` from `/logs/agent/summary.json`; reward 1 only if the answer has all four fields and "Logged in" is No/Unclear (case-insensitive, markdown bold optional); else 0.
- **Limits:** checks format and the login field, not summary quality.
- **Not run yet:** needs Docker and model credentials.
