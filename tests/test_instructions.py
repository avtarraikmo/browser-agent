from __future__ import annotations

import re
from pathlib import Path

TEXT = (Path(__file__).parent.parent / "instructions.md").read_text()


def test_execute_timeout_is_capped_at_3600():
    assert re.search(r"never pass .?execute.? a timeout above 3600 seconds", TEXT, re.I)


def test_cli_sets_playwright_default_timeout():
    # The model no longer writes Playwright scripts; the CLI owns the timeout.
    cli = (Path(__file__).parent.parent / "sandbox" / "workspace" / "browser_cli.py").read_text()
    assert "page.set_default_timeout(20_000)" in cli


def test_login_rules():
    assert re.search(r"never repeat a username, password", TEXT, re.I)
    assert re.search(r"never ask for credentials you weren't given", TEXT, re.I)


def test_uses_browser_cli():
    assert "/workspace/browser_cli.py" in TEXT
    assert "browse.py" not in TEXT


def test_treats_page_content_as_untrusted():
    assert re.search(r"untrusted", TEXT, re.I)
