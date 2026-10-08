"""Run strict channel tests and emit an exact current-source receipt."""
from pathlib import Path
import json
import subprocess
import sys
import unittest

import _support as s

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern='test_*.py')
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    energy_process = subprocess.run([sys.executable, '-B', str(Path(__file__).parent / 'test_energy_editor.py')], cwd=s.ROOT, capture_output=True, text=True)
    energy = None
    if energy_process.returncode == 0:
        lines = [line for line in energy_process.stdout.splitlines() if line.startswith('{')]
        assert len(lines) == 1, 'Missing or ambiguous energy editor receipt'
        energy = json.loads(lines[0])
        current = s.hashes()
        assert energy['all_passed'] and energy['assertions'] > 0
        assert all(current[path] == digest for path, digest in energy['source_sha256'].items()), 'Energy and lifecycle used different source versions'
    else:
        print(energy_process.stdout, file=sys.stderr)
        print(energy_process.stderr, file=sys.stderr)
    successful = result.wasSuccessful() and energy is not None
    print(json.dumps({'schema': 1, 'scope': 'actual source AST and declared dependency boundaries; no native/rendered UI/MP/save proof', 'tests': result.testsRun, 'energy_editor': energy, 'success': successful, 'files': s.hashes()}, sort_keys=True))
    sys.exit(0 if successful else 1)
