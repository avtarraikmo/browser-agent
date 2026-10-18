from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_setup_embeds_current_browser_cli():
    # mda uploads only setup.sh to the bake sandbox, so the CLI is embedded in it.
    setup = (ROOT / "sandbox" / "setup.sh").read_text()
    cli = (ROOT / "sandbox" / "agent_tools" / "browser_cli.py").read_text()
    m = re.search(r"<<'PYEOF'\n(.*?)^PYEOF\n", setup, re.S | re.M)
    assert m and m.group(1) == cli, "run: re-embed sandbox/agent_tools/browser_cli.py in setup.sh"


def test_setup_does_not_read_sibling_files():
    assert 'dirname "$0"' not in (ROOT / "sandbox" / "setup.sh").read_text()
