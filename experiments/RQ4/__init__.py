"""CNL-P, NL and RISEN experiments."""
from pathlib import Path
import sys

_repository_root = Path(__file__).resolve().parents[2]
if str(_repository_root) not in sys.path:
    sys.path.insert(0, str(_repository_root))
from experiments._bootstrap import configure_source_paths
REPOSITORY_ROOT = configure_source_paths()
