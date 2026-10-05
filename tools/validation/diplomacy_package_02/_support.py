"""Preserved source fixtures for the second diplomacy repair package."""
from functools import lru_cache
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASELINE = 'd4ec4a02a1a6dac362554ac85d4b001fbf32f488'


@lru_cache(maxsize=None)
def baseline(relative_path):
    return subprocess.check_output(
        ['git', 'show', BASELINE + ':' + relative_path], cwd=ROOT
    )
