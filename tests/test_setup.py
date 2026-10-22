from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import embed_cli  # noqa: E402

SETUP = (ROOT / "sandbox" / "setup.sh").read_text()


def test_setup_embeds_every_agent_tool():
    # mda uploads only setup.sh to the bake sandbox, so each CLI is embedded in it.
    files = embed_cli.tool_files()
    assert any(f.name == "browser_cli.py" for f in files)
    embedded = dict(re.findall(r"^cat > /agent_tools/(\S+) <<'(\w+)'\n", SETUP, re.M))
    assert set(embedded) == {f.name for f in files}, "run: uv run python scripts/embed_cli.py"
    for f in files:
        m = re.search(rf"<<'{embedded[f.name]}'\n(.*?)^{embedded[f.name]}\n", SETUP, re.S | re.M)
        assert m and m.group(1) == f.read_text(), f"{f.name} drifted: run scripts/embed_cli.py"


def test_embed_block_is_current():
    assert embed_cli.render(embed_cli.tool_files()) in SETUP


def test_setup_does_not_read_sibling_files():
    assert 'dirname "$0"' not in SETUP
