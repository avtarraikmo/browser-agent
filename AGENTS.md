# AGENTS.md

Guidance for coding agents working on this repository. Read this before editing.

## What this is

A Managed Deep Agent (`managed-deepagents==0.9.3`, LangGraph under the hood) that
browses websites for users: it opens a page, summarizes it, and can log in with
the human supplying credentials. The agent definition is `agent.py`; its system
prompt is `instructions.md`; tools are in `tools/`.

## Layout

| Path | Role |
| --- | --- |
| `agent.py` | `define_deep_agent(name=..., model=..., tools=browser_tools)`. `name` is the deploy id. |
| `instructions.md` | Always-loaded system prompt: summarize flow, login flow, safety rules. |
| `identity.py` | Managed auth (`auth.langsmith_api_key()`); callers own their threads. |
| `sandbox/__init__.py` | Managed LangSmith sandbox declaration. **Not used by the browser tools.** |
| `tools/__init__.py` | Calls `tracing.install()` on import. Keep it. |
| `tools/browser_tools.py` | Playwright tools, per-user browser sessions, SSRF guard, credential flow. |
| `tools/tracing.py` | Redacting LangSmith client installed process-wide. |
| `.mda/` | Generated build output (git-ignored). Never edit by hand. |
| `.env` | Secrets (git-ignored). Never print, commit or log values. |

## Architecture

### Request flow

`mda dev` / `mda deploy` compiles the project into `.mda/build` and serves it on
a LangGraph server. A caller is authenticated by `identity.py`; the trusted user
lands in the run config as `config["configurable"]["langgraph_auth_user"]`. The
model calls tools from `browser_tools`; tools receive `config: RunnableConfig`
(injected by LangChain, hidden from the model-facing schema).

### Browser sessions (`tools/browser_tools.py`)

- One shared headless Chromium process (`_browser`, guarded by `_launch_lock`).
- `_sessions: dict[str, _Session]`. Each `_Session` holds one `BrowserContext`,
  the active `Page`, a per-user `asyncio.Lock`, and `last_used`.
- `_user_key(config)` returns `user:<identity>`, else `thread:<thread_id>`. It
  must never fall back to a constant, or users would share cookies and logins.
- Every tool does `session = await _session(config)` then
  `async with session.lock:`. `_session` also runs `_evict_idle()`, which closes
  contexts idle past `IDLE_TTL_S` (1800 s) and skips sessions with a call in flight.
- A browser relaunch resets every session's context/page (`_get_page`).
- State is in-process: restarts and multiple replicas reset or split sessions.

### Why not the managed sandbox

The SDK reuses one sandbox per thread (`thread:<thread_id>`); `scope` and `name`
are reserved and cannot be set. Custom tools get no handle to it (only
deepagents' built-in `execute`/file tools do). Do not reach for the private
`runtime._resolve_managed_sandbox`. Moving the browser into the sandbox was
considered and rejected: it would lose per-user persistence and require rebuilding
the guards below.

### Security invariants (do not weaken)

1. **SSRF guard.** `_is_public_url` allows only `http(s)` hosts whose resolved IPs
   are all `ip.is_global`. It runs in `navigate` *and* on every request through
   `_guard_route`, installed on each context with `context.route("**/*", ...)`.
   Any new code path that creates a context or page must keep the route installed.
2. **Credentials never reach the model.** Secrets are collected only by
   `fill_with_user_input` via `interrupt()` and typed with `page.fill`. Its return
   value must never include the value. Password fields force `secret=True`; secrets
   are refused on non-HTTPS pages; the origin is pinned across the interrupt.
   `ask_user` is for choices only. Never add a tool that returns field values.
3. **Page content is untrusted.** Tool output derived from pages is wrapped in
   `<untrusted_page_content>` and truncated. Keep the wrapping for new read tools.
4. **Redacted traces.** The human's answer is traced as `Command(resume=...)`.
   `tools/tracing.py` scrubs keys in `_SENSITIVE_KEYS` (`resume`, `password`,
   `token`, ...) and applies `create_secret_anonymizer()`. Keep `tools/__init__.py`
   importing `tracing`, and extend `_SENSITIVE_KEYS` if you add secret-bearing fields.
5. **Side effects before `interrupt()` re-run on resume.** Keep code ahead of an
   `interrupt()` call free of side effects (see `fill_with_user_input`).

## Conventions

- Python >= 3.11, async tools with `@tool`, type hints, `from __future__ import annotations`.
- Match the existing style: short docstrings (they are the model-facing tool
  descriptions, so write them for the model), terse comments explaining *why*.
- Add new browser tools to the `browser_tools` list at the bottom of the module.
- Use `uv` for dependencies (`uv add`, then commit `uv.lock`). Direct imports must
  be declared in `pyproject.toml`.
- Do not edit `.mda/`, and never commit `.env`.

## Commands

```bash
uv sync
uv run playwright install chromium   # once per machine
mda dev                              # local LangGraph dev server
mda deploy                           # build to .mda/build and deploy to LangSmith
mda logs                             # deployed server logs
mda evals init -i                    # Harbor eval workspace
```

## Verifying changes

There is no test suite yet. For browser-tool changes, smoke-test with a script
that calls the tools via `.ainvoke(args, config={"configurable": {...}})`, using
two different `langgraph_auth_user` identities. Check that:

- `navigate` to `http://127.0.0.1` is refused;
- a second identity does not see the first identity's open page;
- Playwright, the browser and contexts are closed at the end of the script.

For trace redaction, pass a `Command(resume="x")` payload through
`client._hide_run_inputs(...)` and confirm `resume` is `[REDACTED]`.

## Known gaps

- DNS rebinding: the SSRF check resolves DNS separately from Chromium's connect.
  A network-level egress block would be stronger.
- The managed LangGraph server's own checkpoints may hold interrupt resume values;
  trace redaction does not cover them.
- Eviction runs only on tool calls (no background reaper).
