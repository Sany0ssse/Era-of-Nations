"""Read-only source fixtures for the first diplomacy repair package."""
from functools import lru_cache
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '15de79473f59ada089b98d1757a8c1fe34893f9b'


@lru_cache(maxsize=None)
def baseline(relative_path):
    """Read the preserved pre-package Git source; no private backups required."""
    return subprocess.check_output(
        ['git', 'show', BASELINE + ':' + relative_path], cwd=ROOT
    )
