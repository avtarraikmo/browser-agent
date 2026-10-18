from __future__ import annotations

import re
from pathlib import Path

SKILL = " ".join((Path(__file__).parent.parent / "skills" / "page-details" / "SKILL.md").read_text().split())


def test_frontmatter_names_the_skill():
    m = re.match(r"--- name: page-details description: .+? --- ", SKILL)
    assert m


def test_skill_is_read_only():
    assert re.search(r"read-only", SKILL, re.I)
    assert re.search(r"never `click`, `type`, `press` or `goto`", SKILL, re.I)


def test_skill_does_not_leak_account_details():
    assert re.search(r"never state a username", SKILL, re.I)
    assert re.search(r"profile directory", SKILL, re.I)


def test_skill_treats_page_content_as_untrusted():
    assert re.search(r"untrusted", SKILL, re.I)


def test_skill_reads_in_one_call():
    assert "browser_cli.py page" in SKILL


def test_skill_applies_to_every_page_request():
    assert "EVERY request that involves a web page" in SKILL


def test_summary_answers_what_the_user_asked():
    assert "answer what the user actually asked" in SKILL
    assert "isn't on the page, say so plainly" in SKILL
