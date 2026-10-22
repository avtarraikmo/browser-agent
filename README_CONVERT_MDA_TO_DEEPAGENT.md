# Moving from MDA to plain Deep Agents

This repo is a Managed Deep Agent: `managed-deepagents` (`mda`) wraps the open-source
[`deepagents`](https://github.com/langchain-ai/deepagents) library (0.7.28 resolved in
`uv.lock`) and supplies the sandbox, auth, skills sync, build and deploy around it. Moving
to plain Deep Agents means owning those pieces yourself. This file lists what changes.
It is a plan, not a record of work done; nothing here has been implemented or tested.

## What MDA does for us today

| Concern | Today (MDA) | Where |
| --- | --- | --- |
| Agent construction | `define_deep_agent(name, model)` | `agent.py` |
| Sandbox | `define_sandbox(...)`: one sandbox per thread, snapshot baked from `setup.sh`, idle/delete TTLs, proxy deny list | `sandbox/__init__.py`, `sandbox/setup.sh` |
| Instructions | `instructions.md` loaded as the system prompt | `instructions.md` |
| Skills | `skills/*/SKILL.md` discovered and synced to Context Hub on deploy | `skills/` |
| Auth | `define_identity(auth=auth.langsmith_api_key())`, private threads | `identity.py` |
| Build and deploy | `mda dev`, `mda deploy`, `mda logs`, `mda evals init` | `.vscode/launch.json`, README |
| Trace redaction | custom LangSmith client installed at import | `tools/tracing.py` (no MDA dependency) |

## Steps

### 1. Dependencies (`pyproject.toml`)

- Replace `managed-deepagents==0.9.3` with `deepagents` (pin a version) and add the sandbox
  provider package you choose (step 3).
- Drop `[tool.mda]`. Set the Python version via `requires-python` and your runtime image.
- Add `langgraph-cli[inmem]` for `langgraph dev` / `langgraph build`.
- Run `uv lock` and commit `uv.lock`.

### 2. Agent definition (`agent.py`)

Replace `define_deep_agent` with `deepagents.create_deep_agent`, and export a compiled graph:

```python
from deepagents import create_deep_agent
from tools import tracing

tracing.install()

agent = create_deep_agent(
    model="openai:gpt-6-luna",
    system_prompt=open("instructions.md").read(),
    backend=make_backend,          # sandbox-backed, see step 3
    skills=["/skills/"],           # see step 4
    checkpointer=...,              # LangGraph server supplies one when deployed
)
```

Check the exact signature against the pinned `deepagents` version. The built-in `execute`
tool only exists when the backend supports command execution, so browsing keeps working
without custom tools if the backend does.

### 3. Sandbox (biggest piece)

MDA gives one sandbox per thread, a baked snapshot, TTL cleanup and the network deny list.
Plain Deep Agents give you a backend interface and leave provisioning to you.

- **Pick a provider**: a LangSmith sandbox, Daytona, Modal, Runloop or Docker. Each
  has a `deepagents` backend or an easy adapter.
- **Image instead of `setup.sh`**: build a Dockerfile (or provider snapshot) that
  runs what `sandbox/setup.sh` does now: install Playwright and Chromium, symlink
  `/root/.cache/ms-playwright`, and `COPY sandbox/agent_tools/browser_cli.py /agent_tools/browser_cli.py`.
  Because you control the build context, the sibling-file problem with `mda` goes away.
  Keep
  the `--help` and warm-up smoke steps as `RUN` lines.
- **Per-thread lifecycle**: create (or look up) a sandbox keyed by `thread_id`, reuse it
  across turns, and delete it on idle. MDA handled all three; the factory passed to `backend=`
  now owns the first, and TTLs move to the provider or a cron job. Browser state must stay
  per-thread.
- **Network deny list (security invariant 2)**: MDA's `proxy_config.access_control.deny_list`
  has no equivalent in the library. Reimplement with provider egress rules, a container
  network policy or an egress proxy blocking loopback, RFC 1918, link-local
  (`169.254.0.0/16`), CGNAT (`100.64.0.0/10`) and IPv6 equivalents. Verify plain HTTP as
  well as HTTPS; this was already an open gap.
- **Command timeout**: the 120s `default_timeout` becomes a backend or `execute` setting.
- Delete `sandbox/__init__.py` once its settings are moved, and update `tests/test_sandbox.py`
  to test the new source of the deny list.

### 4. Skills and instructions

- `instructions.md` is read as-is. It already refers to `/agent_tools/browser_cli.py`,
  which does not change.
- Skills: pass the `skills=` source paths to `create_deep_agent` and make
  `skills/page-details/SKILL.md` readable by the backend (copy into the sandbox image or a
  state/store backend). Context Hub sync on deploy goes away unless you add it.
- `instructions.md` still depends on the model reading `page-details` first; this is
  unchanged and still not enforced in code.

### 5. Auth and threads (`identity.py`)

`define_identity` and `auth.langsmith_api_key()` are MDA APIs. With `langgraph dev` /
`langgraph build`, declare a custom auth handler in `langgraph.json`
(`"auth": {"path": "./auth.py:auth"}`) that validates `x-api-key` against LangSmith, and add
`@auth.on` handlers so callers only see their own threads (MDA applied these for us).
Delete `identity.py` afterward.

### 6. Server config and deploy

- Add `langgraph.json`: `{"dependencies": ["."], "graphs": {"browser-agent": "./agent.py:agent"}, "env": ".env", "auth": {...}}`.
  The graph id replaces MDA's `name`, which is the deploy id.
- Replace `mda dev` with `langgraph dev` (update `.vscode/launch.json`, README and AGENTS.md).
- Replace `mda deploy` with LangSmith Deployment from the repo, or `langgraph build` plus
  your own image. `mda logs` becomes the deployment's logs in LangSmith.
- Secrets still come from `.env`, never committed; keep `env.example` in sync.

### 7. Trace redaction (security invariant 4)

`tools/tracing.py` has no MDA dependency, so it carries over. Keep `tracing.install()`
in `agent.py` and re-verify with the `Command(resume="x")` check in AGENTS.md. MDA's
interrupt-resume checkpoint caveat changes: you now own the checkpointer and decide what it stores.

### 8. Evals

`mda evals init` generated the Harbor workspace in `evals/`. The task packages and offline
verifiers don't depend on MDA, but `evals/harbor-job.json` and the README commands
(`harbor view .mda/evals/jobs`) point at `.mda/`. Repoint them at the new endpoint and
output directory, and re-run (the tasks have never run through Harbor).

### 9. Tests and docs

- `tests/test_sandbox.py`: rewrite for the new deny-list source.
- `tests/test_setup.py`: replace the `setup.sh` copy test with one that the Dockerfile
  copies `sandbox/agent_tools/browser_cli.py`.
- Update `README.md`, `AGENTS.md` (layout table, "Browsing", commands, known gaps) and
  `docs/architecture.html` together, as AGENTS.md requires. Remove `.mda/` from `.gitignore`
  once it is no longer produced.

## Order of work

1. Dependencies and `create_deep_agent` running locally with `langgraph dev`, local Docker backend.
2. Sandbox image and per-thread lifecycle; confirm `browser_cli.py goto` works in a thread.
3. Egress deny list; verify metadata IP and plain HTTP are blocked.
4. Auth handlers and thread isolation.
5. Deploy, then evals, then delete MDA files and docs references.

## Risks

- **Deny list regression**: easy to lose silently. Treat step 3 as a gate before any deploy.
- **Sandbox cost and leaks**: without MDA's TTLs, abandoned sandboxes keep running.
- **Auth gaps**: a missing `@auth.on` handler exposes other users' threads.
- **Version drift**: `deepagents` APIs move quickly; pin it and check signatures here.
