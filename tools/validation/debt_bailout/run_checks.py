"""Run current bailout source and lifecycle checks with structured receipts."""
from pathlib import Path
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
reports = {}
for name in ('test_lifecycle.py', 'test_source.py'):
    result = subprocess.run([sys.executable, '-B', str(HERE / name)],
                            capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        sys.stderr.write(result.stdout + result.stderr)
        raise SystemExit(result.returncode)
    reports[name] = json.loads(result.stdout)
print(json.dumps({'checks_passed': True, 'reports': reports,
                  'native_campaign_proven': False}, indent=2))
