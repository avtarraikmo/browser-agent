#!/usr/bin/env bash
# Baked once by `mda deploy` / `mda dev`; new threads clone the resulting snapshot.
# Installs Playwright and Chromium (with its system libraries) and the browser_cli.py
# CLI for browsing from the sandbox's `execute` tool, then warms up Chromium once.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
# Keep browser binaries in a shared location so every user of the sandbox finds them.
export PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers

if ! command -v pip3 >/dev/null 2>&1; then
  apt-get update
  apt-get install -y --no-install-recommends python3 python3-pip
fi

# --break-system-packages: Debian/Ubuntu images mark the system Python as externally managed.
pip3 install --break-system-packages playwright
playwright install --with-deps chromium

echo "export PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH}" > /etc/profile.d/playwright.sh
chmod -R a+rX "${PLAYWRIGHT_BROWSERS_PATH}"

# `execute` shells are non-login, so profile.d is never sourced and Playwright
# looks in the default cache, not /opt. Link it there so launch works with no env var.
mkdir -p /root/.cache
ln -sfn "${PLAYWRIGHT_BROWSERS_PATH}" /root/.cache/ms-playwright

# Install the browser_cli.py CLI the agent calls via `execute`.
# `mda` uploads only this script to the builder (as /tmp/mda-setup.sh), so sibling
# files aren't available: the CLI is embedded below. Keep it identical to
# sandbox/agent_tools/browser_cli.py (tests/test_setup.py enforces that).
mkdir -p /agent_tools
cat > /agent_tools/browser_cli.py <<'PYEOF'
#!/usr/bin/env python3
"""browser_cli.py - persistent browser CLI for agents. Runs INSIDE the sandbox.

Chromium is launched once with a CDP port and stays alive between `execute` calls;
each call attaches over CDP on localhost, does one action, and disconnects.
Cookies, tabs and page state persist; the profile dir survives Chrome restarts.

Usage:  browser_cli.py goto URL [--text] | page | snap | text | click SEL | type SEL TEXT [--enter]
                | press KEY | shot [PATH] | tabs | restart | stop
Env:    BROWSE_PROFILE (default /agent_tools/.browse-profile), BROWSE_PORT (default 9222)
Needs:  playwright + chromium already installed in the sandbox.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

PORT = int(os.environ.get("BROWSE_PORT", "9222"))
PROFILE = os.environ.get("BROWSE_PROFILE", "/agent_tools/.browse-profile")
CDP = f"http://127.0.0.1:{PORT}"
MAX_OUT = 6000  # chars returned to the agent per call


# ------------------------------------------------------------------ chrome
def cdp_up() -> bool:
    try:
        urllib.request.urlopen(f"{CDP}/json/version", timeout=1.5)
        return True
    except Exception:
        return False


def launch_chrome(pw) -> None:
    subprocess.Popen(
        [pw.chromium.executable_path, "--headless=new", "--no-sandbox", "--disable-gpu",
         f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}",
         "--window-size=1280,800", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,  # survive after this command exits
    )
    for _ in range(200):  # 10s total, polled every 50ms
        if cdp_up():
            return
        time.sleep(0.05)
    sys.exit(json.dumps({"error": "ChromeStartFailed"}))


def kill_chrome() -> None:
    subprocess.run(["pkill", "-f", f"remote-debugging-port={PORT}"], capture_output=True)
    for _ in range(20):
        if not cdp_up():
            return
        time.sleep(0.25)


def get_page(pw):
    if not cdp_up():
        launch_chrome(pw)
    browser = pw.chromium.connect_over_cdp(CDP)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.pages[-1] if ctx.pages else ctx.new_page()
    page.set_default_timeout(20_000)
    return page


# ---------------------------------------------------------------- commands
def snap(page) -> str:
    tree = page.locator("body").aria_snapshot()
    return json.dumps({"url": page.url, "title": page.title(), "snapshot": tree[:MAX_OUT]})


def page_info(page) -> str:
    """URL, title, snapshot, body text and open tabs in one call (read-only)."""
    return json.dumps({
        "url": page.url,
        "title": page.title(),
        "snapshot": page.locator("body").aria_snapshot()[:MAX_OUT],
        "text": page.inner_text("body")[:MAX_OUT],
        "tabs": [{"url": pg.url, "title": pg.title()} for pg in page.context.pages],
    })


def run(a) -> str:
    with sync_playwright() as pw:  # exiting disconnects; Chrome keeps running
        if a.cmd == "restart":
            kill_chrome()
            launch_chrome(pw)
            return json.dumps({"status": "restarted"})
        if a.cmd == "stop":
            kill_chrome()
            return json.dumps({"status": "stopped"})

        p = get_page(pw)
        if a.cmd == "goto":
            p.goto(a.url, wait_until="domcontentloaded")
            return page_info(p) if a.with_text else snap(p)
        if a.cmd == "page":
            return page_info(p)
        if a.cmd == "snap":
            return snap(p)
        if a.cmd == "text":
            return p.inner_text("body")[:MAX_OUT]
        if a.cmd == "click":
            p.click(a.selector)
            p.wait_for_load_state("domcontentloaded")
            return snap(p)
        if a.cmd == "type":
            p.fill(a.selector, a.text)
            if a.enter:
                p.keyboard.press("Enter")
                p.wait_for_load_state("domcontentloaded")
            # Never echo typed text back (it may be a password) into the model context.
            out = snap(p)
            return out.replace(json.dumps(a.text)[1:-1], "[REDACTED]") if a.text else out
        if a.cmd == "press":
            p.keyboard.press(a.key)
            return snap(p)
        if a.cmd == "shot":
            p.screenshot(path=a.path)
            return json.dumps({"saved": a.path})
        if a.cmd == "tabs":
            return json.dumps([{"url": pg.url, "title": pg.title()} for pg in p.context.pages])
    return json.dumps({"error": "unknown command"})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("snap", "text", "tabs", "page", "restart", "stop"):
        sub.add_parser(name)
    s = sub.add_parser("goto"); s.add_argument("url"); s.add_argument("--text", dest="with_text", action="store_true")
    s = sub.add_parser("click"); s.add_argument("selector")
    s = sub.add_parser("type"); s.add_argument("selector"); s.add_argument("text"); s.add_argument("--enter", action="store_true")
    s = sub.add_parser("press"); s.add_argument("key")
    s = sub.add_parser("shot"); s.add_argument("path", nargs="?", default="/agent_tools/shot.png")
    a = ap.parse_args()
    try:
        print(run(a))
    except Exception as e:  # return errors as data so the agent can recover
        print(json.dumps({"error": type(e).__name__, "detail": str(e)[:500]}))
        sys.exit(1)


if __name__ == "__main__":
    main()
PYEOF
chmod a+rx /agent_tools/browser_cli.py

# Fail the bake now if the script or Playwright import is broken.
python3 /agent_tools/browser_cli.py --help >/dev/null

# Best-effort warm-up: launch Chromium once against the CLI's profile dir so the
# first-run profile setup is baked into the snapshot and threads skip it. Only
# about:blank is loaded, so no page state is saved. Stop it and clear lock files so
# a clone starts clean; a failure here must not block the bake.
if timeout 60 python3 /agent_tools/browser_cli.py snap >/dev/null 2>&1; then
  python3 /agent_tools/browser_cli.py stop >/dev/null 2>&1 || true
  rm -f /agent_tools/.browse-profile/Singleton*
  echo "browser warm-up ok"
else
  pkill -f remote-debugging-port=9222 >/dev/null 2>&1 || true
  rm -f /agent_tools/.browse-profile/Singleton*
  echo "browser warm-up skipped (launch failed)"
fi
