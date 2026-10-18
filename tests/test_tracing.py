from __future__ import annotations

import copy
import json
from unittest.mock import patch

import pytest
from langgraph.types import Command
from langsmith import Client

from tools import tracing

# Fake value shaped like an OpenAI key, to exercise the secret detector.
FAKE_API_KEY = "sk-" + "a1B2c3D4" * 6


@pytest.fixture
def client() -> Client:
    # Dummy key and URL: nothing here talks to the network.
    return Client(
        api_key="test-key",
        api_url="http://localhost:1",
        anonymizer=tracing.anonymize,
        auto_batch_tracing=False,
    )


@pytest.mark.parametrize("key", sorted(tracing._SENSITIVE_KEYS))
def test_sensitive_keys_are_redacted(key):
    assert tracing._scrub({key: "hunter2"}) == {key: tracing.REDACTED}


def test_key_match_is_case_insensitive():
    assert tracing._scrub({"Password": "x", "RESUME": "y"}) == {
        "Password": tracing.REDACTED,
        "RESUME": tracing.REDACTED,
    }


def test_nested_dicts_and_lists_are_scrubbed():
    data = {"a": [{"token": "t", "ok": 1}], "b": {"c": {"otp": "123456"}}}
    assert tracing._scrub(data) == {
        "a": [{"token": tracing.REDACTED, "ok": 1}],
        "b": {"c": {"otp": tracing.REDACTED}},
    }


def test_non_sensitive_values_are_preserved():
    data = {"url": "https://example.com", "n": 3, "items": ["a", "b"], "none": None}
    assert tracing._scrub(data) == data


def test_scrub_does_not_mutate_input():
    data = {"password": "x", "nested": [{"token": "y"}]}
    original = copy.deepcopy(data)
    tracing._scrub(data)
    assert data == original


def test_anonymize_redacts_secret_shaped_strings():
    out = tracing.anonymize({"note": f"key is {FAKE_API_KEY}"})
    assert FAKE_API_KEY not in str(out)


def test_anonymize_redacts_sensitive_keys():
    assert tracing.anonymize({"resume": "hunter2"}) == {"resume": tracing.REDACTED}


def test_client_hides_command_resume(client):
    out = client._hide_run_inputs({"command": Command(resume="hunter2")})
    assert "hunter2" not in str(out)


def test_client_hides_resume_dict(client):
    out = client._hide_run_inputs({"resume": "hunter2"})
    assert out == {"resume": tracing.REDACTED}


def test_install_configures_redacting_client():
    with patch.object(tracing.ls, "configure") as configure:
        tracing.install()
    configure.assert_called_once()
    installed = configure.call_args.kwargs["client"]
    assert installed._hide_run_inputs({"password": "x"}) == {"password": tracing.REDACTED}


def test_agent_module_installs_tracing():
    # agent.py must keep calling tracing.install() (security invariant 4).
    import pathlib

    src = (pathlib.Path(__file__).parent.parent / "agent.py").read_text()
    assert "tracing.install()" in src


FAKE_TYPED = "FAKE-trace-pass-5520"


def test_anonymize_redacts_typed_text_in_execute_command():
    cmd = f"python3 /agent_tools/browser_cli.py type 'input[type=\"password\"]' '{FAKE_TYPED}' --enter"
    out = tracing.anonymize({"command": cmd, "timeout": 120})
    assert out == {
        "command": f"python3 /agent_tools/browser_cli.py type 'input[type=\"password\"]' {tracing.REDACTED} --enter",
        "timeout": 120,
    }


def test_anonymize_redacts_typed_text_in_json_tool_call_arguments():
    args = json.dumps({"command": f'python3 /agent_tools/browser_cli.py type "#pw" "{FAKE_TYPED}"', "timeout": 120})
    out = tracing.anonymize({"arguments": args})
    assert FAKE_TYPED not in str(out)
    assert json.loads(out["arguments"]) == {
        "command": f'python3 /agent_tools/browser_cli.py type "#pw" {tracing.REDACTED}',
        "timeout": 120,
    }


def test_anonymize_preserves_other_browser_commands():
    data = {"command": "python3 /agent_tools/browser_cli.py click 'text=Sign in'"}
    assert tracing.anonymize(copy.deepcopy(data)) == data


def test_anonymize_redacts_password_textbox_in_tool_output():
    snapshot = f'- textbox "Email": demo-user\n- textbox "Password" [invalid]: {FAKE_TYPED}\n- button "Sign in"'
    output = json.dumps({"url": "https://example.com/login", "snapshot": snapshot})
    out = tracing.anonymize({"content": output + "\n\n[Command succeeded with exit code 0]"})
    assert FAKE_TYPED not in str(out)
    assert f'textbox \\"Password\\" [invalid]: {tracing.REDACTED}\\n- button' in out["content"]
    assert "demo-user" in out["content"]
