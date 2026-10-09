"""Current debt accounting regressions; source proof is not native gameplay."""
from pathlib import Path
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
results = []
for name in ('test_source.py', 'test_accounting.py'):
    result = subprocess.run([sys.executable, '-B', str(HERE/name)],
                            capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        sys.stderr.write(result.stdout + result.stderr)
        raise SystemExit(result.returncode)
    results.append({'suite': name, 'result': json.loads(result.stdout)})
print(json.dumps({'all_passed': True, 'suites': results,
                  'native_campaign_verified': False, 'multiplayer_verified': False}, indent=2))
