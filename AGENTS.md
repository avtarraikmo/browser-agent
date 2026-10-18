# AGENTS.md

Guidance for coding agents working on this repository. Read this before editing.

## What this is

A Managed Deep Agent (`managed-deepagents==0.9.3`, LangGraph under the hood) that
browses websites for users. The model drives headless
Chromium inside the managed sandbox. The agent definition is `agent.py`; its system
prompt is `instructions.md`.

## Layout

| Path | Role |
| --- | --- |
| `agent.py` | `define_deep_agent(name=..., model=...)` with no custom tools; installs trace redaction. `name` is the deploy id. |
| `instructions.md` | Always-loaded system prompt: browsing recipe, safety rules. |
| `skills/page-details/SKILL.md` | Read-only skill: reports the current page URL, login state, a summary that answers the user's actual ask, and available tabs/buttons. Uses only the read-only `page`/`snap`/`text`/`tabs` commands. |
| `identity.py` | Managed auth (`auth.langsmith_api_key()`); callers own their threads. |
| `sandbox/__init__.py` | Managed sandbox: network deny list. |
| `sandbox/setup.sh` | Bakes Playwright + Chromium into the sandbox snapshot and writes an embedded copy of `sandbox/agent_tools/browser_cli.py` to `/agent_tools` (`mda` uploads only this script, so siblings aren't available). |
| `sandbox/agent_tools/browser_cli.py` | Persistent browser CLI the model calls via `execute`; source of truth for the copy embedded in `setup.sh` (deployed at `/agent_tools/browser_cli.py`). |
| `tools/tracing.py` | Redacting LangSmith client, installed by `agent.py`. |
| `evals/` | Harbor eval workspace: `harbor-job.json` plus one dir per task (`instruction.md`, hidden `Task.md`, `tests/verify.py`). Eight tasks cover page facts (`example-domain-heading-link`), the `page-details` format, link following, private-address refusal, prompt injection, unreachable pages, login without credentials and password leakage (see the README table). Verifiers are pure offline functions over `summary.json` and the commands in `result.json`. |
| `.mda/` | Generated build output (git-ignored). Never edit by hand. |
| `.env` | Secrets (git-ignored). Never print, commit or log values. |
| `env.example` | Tracked list of variable names with placeholder values. Keep it free of real secrets. |

## Architecture

### Browsing

There are no custom browser tools and `playwright` is **not** a project dependency;
the server image has no browser and `mda` can't customize it (`[tool.mda]` only
supports `python-version`). The model runs `/agent_tools/browser_cli.py` commands through
deepagents' built-in `execute` tool (capped at 120s) in the sandbox, where `setup.sh`
installed Playwright and Chromium and wrote the CLI. `mda` uploads only `setup.sh` to
the bake sandbox, so the CLI is embedded in it (see the README). `mda deploy` / `mda dev` bake `setup.sh` once; threads clone the snapshot.
Chromium is in `/opt/playwright-browsers`, symlinked from `/root/.cache/ms-playwright`
by `setup.sh`: `execute` shells are non-login, so no env var is set and Playwright only
finds browsers at its default path. Don't rely on the model exporting
`PLAYWRIGHT_BROWSERS_PATH`. Lifecycle: there is no thread-end hook, so the sandbox's
idle and delete-after-stop TTLs in `sandbox/__init__.py` reclaim it.

The SDK gives **one sandbox per thread** (`thread:<thread_id>`); `scope` and `name`
are reserved. Browser state does not persist across threads. Custom tools get no
handle to the sandbox, so don't add tools that expect one and don't use the private
`runtime._resolve_managed_sandbox`.

### Skills

`skills/<name>/SKILL.md` files are discovered automatically for static agents and
synced to Context Hub on deploy; `agent.py` needs no wiring. `page-details` is read-only
(`page`/`snap`/`text`/`tabs`, no clicks or navigation) and `instructions.md` makes it
mandatory for every page reply: its format is the standard answer, and its Summary
answers what the user asked rather than giving a generic overview. Keep skills inside
the security invariants below.

### Security invariants (do not weaken)

1. **Credentials only on request, never repeated.** The model logs in only with
   credentials the user supplied in the thread; `instructions.md` forbids asking for
   others, repeating them, or storing them, and `browser_cli.py type` redacts typed
   text from its output. They do reach model context and traces (redacted by key).
2. **Network deny list.** `proxy_config.access_control.deny_list` blocks loopback,
   private, link-local (cloud metadata) and CGNAT ranges. The SDK documents it for
   outbound HTTPS only; verify plain HTTP before relying on it. There is no
   app-level URL check any more, so this list and the instructions are the guard.
3. **Page content is untrusted.** `instructions.md` tells the model to
   treat it as data. Keep that rule.
4. **Redacted traces.** `tools/tracing.py` scrubs keys in `_SENSITIVE_KEYS`
   (`resume`, `password`, `token`, ...) and applies `create_secret_anonymizer()`.
   Keep `agent.py` calling `tracing.install()`, and extend `_SENSITIVE_KEYS` if you
   add secret-bearing fields.

## Conventions

- Python >= 3.11, type hints, `from __future__ import annotations`. The agent has no custom
  tools (it browses through `execute`); if you add any, use async `@tool` and write the
  docstring for the model, since it is the model-facing description.
- Terse comments that explain *why*.
- Use `uv` for dependencies (`uv add`, then commit `uv.lock`). Declare direct imports
  in `pyproject.toml`.
- Do not edit `.mda/`, and never commit `.env`. Never put real values in `env.example`.
- After editing `browser_cli.py`, re-embed it between the `PYEOF` markers in
  `sandbox/setup.sh`; `tests/test_setup.py` fails on drift.
- If you change what the agent can do, update `instructions.md`, `skills/`, `README.md`,
  `docs/architecture.html` and this file together.

## Commands

```bash
uv sync
mda dev                              # local LangGraph dev server (bakes sandbox/setup.sh)
mda deploy                           # build to .mda/build and deploy to LangSmith
mda logs                             # deployed server logs
mda evals init -i                    # Harbor eval workspace
```

## Verifying changes

`uv run pytest` runs offline unit tests (trace redaction, sandbox deny list and
timeouts, key rules in `instructions.md`, the `page-details` skill, every eval task package and
verifier, and that the CLI
embedded in `setup.sh` matches `sandbox/agent_tools/browser_cli.py`). `uv run python -c "import agent, sandbox"` checks that
the definitions load. Real checks need a deployment or `mda dev`:

- Ask for a public page summary and confirm Chromium runs in the sandbox and the reply
  follows the `page-details` format (the model should `read_file` the skill first).
- Pass `Command(resume="x")` through `client._hide_run_inputs(...)` and confirm
  `resume` is `[REDACTED]`.

## Known gaps

- The eval tasks are unit-tested offline but have not been run through Harbor (needs
  Docker and model credentials).
- `setup.sh` bakes successfully on `mda dev` (it assumes a Debian/Ubuntu sandbox image
  with root) and the CLI works in a thread. The deny list is still untested end to end;
  check it, including plain HTTP, on a run.
- Skill use depends on `instructions.md` (the model reads `page-details` first); it is
  not enforced in code.
- A page or email can try to steer the model; the guards are the instructions and
  the deny list, not code.
- The managed LangGraph server's own checkpoints may hold interrupt resume values;
  trace redaction does not cover them.
