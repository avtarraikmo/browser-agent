import sys
from pathlib import Path

# Make `tools` and `sandbox` importable when pytest runs from any directory.
sys.path.insert(0, str(Path(__file__).parent.parent))
