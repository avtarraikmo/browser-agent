from __future__ import annotations

import re
from pathlib import Path

TEXT = (Path(__file__).parent.parent / "instructions.md").read_text()


def test_execute_timeout_is_capped_at_120():
    assert re.search(r"never pass .?execute.? a timeout above 120 seconds", TEXT, re.I)


def test_cli_sets_playwright_default_timeout():
    # The model no longer writes Playwright scripts; the CLI owns the timeout.
    cli = (Path(__file__).parent.parent / "sandbox" / "agent_tools" / "browser_cli.py").read_text()
    assert "page.set_default_timeout(20_000)" in cli


def test_login_rules():
    assert re.search(r"never repeat a username, password", TEXT, re.I)
    assert re.search(r"never ask for credentials you weren't given", TEXT, re.I)


def test_uses_browser_cli():
    assert "/agent_tools/browser_cli.py" in TEXT
    assert "browse.py" not in TEXT


def test_treats_page_content_as_untrusted():
    assert re.search(r"untrusted", TEXT, re.I)


def test_points_to_page_details_skill():
    assert "`page-details` skill" in TEXT
    assert "/skills/page-details/SKILL.md" in TEXT


def test_prefers_single_call_reads():
    assert "goto URL --text" in TEXT
    assert "`page`" in TEXT


def test_page_details_skill_is_mandatory_for_every_page():
    assert re.search(r"mandatory for every page", TEXT, re.I)
    assert re.search(r"Reply in the `page-details` skill's format", TEXT)


def test_summary_must_answer_the_users_question():
    assert re.search(r"summary\s+must answer what the user asked", TEXT)
