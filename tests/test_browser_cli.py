from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

CLI = Path(__file__).parent.parent / "sandbox" / "agent_tools" / "browser_cli.py"
FAKE_PASSWORD = "FAKE-test-pass-9182"


@pytest.fixture(scope="module")
def cli():
    # Playwright only exists inside the sandbox; the functions under test take a page object.
    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = None
    with patch.dict(sys.modules, {"playwright": types.ModuleType("playwright"), "playwright.sync_api": sync_api}):
        spec = importlib.util.spec_from_file_location("browser_cli", CLI)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class FakeLoginPage:
    """Login form whose aria snapshot shows field values, as Chromium's does."""

    url = "https://example.com/login"

    def __init__(self, password_label: str = ' "Password" [invalid]', fail_eval: bool = False):
        self.values = {"#user": "", "#pw": ""}
        self.password_label = password_label
        self.fail_eval = fail_eval
        self.context = types.SimpleNamespace(pages=[self])

    def fill(self, selector: str, text: str) -> None:
        self.values[selector] = text

    def title(self) -> str:
        return "Sign in"

    def locator(self, selector: str):
        user, pw = (f": {v}" if v else "" for v in (self.values["#user"], self.values["#pw"]))
        tree = f'- textbox "Username"{user}\n- textbox{self.password_label}{pw}\n- button "Sign in"'
        return types.SimpleNamespace(aria_snapshot=lambda: tree)

    def inner_text(self, selector: str) -> str:
        return "Sign in\nUsername\nPassword"

    def eval_on_selector_all(self, selector: str, script: str):
        if self.fail_eval:
            raise RuntimeError("page navigated")
        return [self.values["#pw"]] if self.values["#pw"] else []


def _typed(page: FakeLoginPage) -> FakeLoginPage:
    page.fill("#user", "demo-user")
    page.fill("#pw", FAKE_PASSWORD)
    return page


@pytest.mark.parametrize("command", ["snap", "page_info"])
def test_snapshots_redact_typed_password(cli, command):
    out = getattr(cli, command)(_typed(FakeLoginPage()))
    assert FAKE_PASSWORD not in out
    assert "[REDACTED]" in json.loads(out)["snapshot"]
    assert "demo-user" in out


def test_unlabelled_password_field_is_redacted_by_value(cli):
    out = cli.snap(_typed(FakeLoginPage(password_label="")))
    assert FAKE_PASSWORD not in out
    assert "[REDACTED]" in out


def test_password_label_fallback_when_values_unreadable(cli):
    out = cli.snap(_typed(FakeLoginPage(fail_eval=True)))
    assert FAKE_PASSWORD not in out
    assert "[REDACTED]" in out


def test_empty_password_field_leaves_snapshot_intact(cli):
    page = FakeLoginPage()
    assert json.loads(cli.snap(page))["snapshot"] == page.locator("body").aria_snapshot()
