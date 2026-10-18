from __future__ import annotations

import re
from pathlib import Path

SKILL = (Path(__file__).parent.parent / "skills" / "page-details" / "SKILL.md").read_text()


def test_frontmatter_names_the_skill():
    m = re.match(r"---\nname: page-details\ndescription: .+\n---\n", SKILL)
    assert m


def test_skill_is_read_only():
    assert re.search(r"read-only", SKILL, re.I)
    assert re.search(r"never `click`, `type`, `press` or `goto`", SKILL, re.I)


def test_skill_does_not_leak_account_details():
    assert re.search(r"never state a username", SKILL, re.I)
    assert re.search(r"profile directory", SKILL, re.I)


def test_skill_treats_page_content_as_untrusted():
    assert re.search(r"untrusted", SKILL, re.I)
