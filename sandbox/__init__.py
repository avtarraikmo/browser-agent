"""Managed LangSmith sandbox declaration.

MDA owns the run-scoped name, reuse across turns (one sandbox per thread), and
lifecycle. Delete this directory to run without a sandbox.

`sandbox/setup.sh` installs Playwright and Chromium; `mda deploy` and `mda dev`
bake it once and new threads clone the snapshot without re-running it. The agent
browses by running Playwright scripts through the built-in `execute` tool.
"""

from managed_deepagents import bearer, connections, define_sandbox

# The caller's Google OAuth grant. Created once with:
#   mda connections create google --oauth google --client-id <ID> --scopes <...>
google = connections.get("google", {"type": "user"})

sandbox = define_sandbox(
    # Reclaim idle sandboxes after 10 minutes.
    idle_ttl_seconds=600,
    # Default per-command timeout, in seconds.
    default_timeout=600,
    proxy_config={
        # The sandbox proxy adds the user's token to Gmail API requests, so the
        # token never enters the sandbox or the model's context.
        "rules": [
            {
                "name": "google-gmail",
                "match_hosts": ["gmail.googleapis.com"],
                "headers": [{"name": "Authorization", "value": bearer(google)}],
            }
        ],
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
