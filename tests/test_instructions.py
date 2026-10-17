from __future__ import annotations

import re
from pathlib import Path

TEXT = (Path(__file__).parent.parent / "instructions.md").read_text()


def test_execute_timeout_is_capped_at_3600():
    assert re.search(r"never pass .?execute.? a timeout above 3600 seconds", TEXT, re.I)


def test_playwright_default_timeout_is_120s():
    assert "page.set_default_timeout(120_000)" in TEXT
    assert "30_000)" not in TEXT.split("set_default_timeout")[1][:12]


def test_forbids_credentials():
    assert re.search(r"credential|password", TEXT, re.I)


def test_treats_page_content_as_untrusted():
    assert re.search(r"untrusted", TEXT, re.I)
