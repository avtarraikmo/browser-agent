#!/usr/bin/env python3
"""browser_cli.py - persistent browser CLI for agents. Runs INSIDE the sandbox.

Chromium is launched once with a CDP port and stays alive between `execute` calls;
each call attaches over CDP on localhost, does one action, and disconnects.
Cookies, tabs and page state persist; the profile dir survives Chrome restarts.

Usage:  browser_cli.py goto URL | snap | text | click SEL | type SEL TEXT [--enter]
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
    for _ in range(40):
        if cdp_up():
            return
        time.sleep(0.25)
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
            return snap(p)
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
    for name in ("snap", "text", "tabs", "restart", "stop"):
        sub.add_parser(name)
    s = sub.add_parser("goto"); s.add_argument("url")
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
