"""Managed LangSmith sandbox declaration.

MDA owns the run-scoped name and reuse across turns (one sandbox per thread). A new
thread boots a fresh sandbox from the baked snapshot; idle TTLs below delete it. Delete this directory to run without a sandbox.

`sandbox/setup.sh` installs Playwright and Chromium; `mda deploy` and `mda dev`
bake it once and new threads clone the snapshot without re-running it. The agent
browses by running the `browser_cli.py` commands that setup.sh installs, through the
built-in `execute` tool.
"""

from managed_deepagents import define_sandbox

sandbox = define_sandbox(
    # No thread-end hook exists, so TTLs reclaim the thread's sandbox: stopped after
    # 5 idle minutes, then deleted a minute later (both must be multiples of 60).
    idle_ttl_seconds=300,
    delete_after_stop_seconds=60,
    # Default per-command timeout, in seconds.
    default_timeout=120,
    proxy_config={
        # Network-level SSRF guard: the browser must not reach loopback, private
        # networks or cloud metadata endpoints.
        "access_control": {
            "deny_list": [
                "127.0.0.0/8",
                "10.0.0.0/8",
                "172.16.0.0/12",
                "192.168.0.0/16",
                "169.254.0.0/16",  # link-local, incl. cloud metadata 169.254.169.254
                "100.64.0.0/10",  # carrier-grade NAT
                "::1/128",
                "fc00::/7",
                "fe80::/10",
                "localhost",
            ],
        },
    },
)
