"""Run both diplomacy packages; these are source models, not the HOI4 engine."""
from pathlib import Path
import json
import subprocess
import sys

from _support import ROOT

HERE = Path(__file__).resolve().parent
reports = {}

previous = subprocess.run(
    [sys.executable, str(HERE.parent / 'diplomacy_package_01/run_checks.py')],
    cwd=ROOT, capture_output=True, text=True, encoding='utf-8'
)
if previous.returncode:
    sys.stderr.write(previous.stdout + previous.stderr)
    raise SystemExit(previous.returncode)
reports['package_01'] = json.loads(previous.stdout)

for name in ('test_trade', 'test_treaty', 'test_investment', 'test_annex', 'test_source'):
    result = subprocess.run(
        [sys.executable, str(HERE / (name + '.py'))], cwd=ROOT,
        capture_output=True, text=True, encoding='utf-8'
    )
    if result.returncode:
        sys.stderr.write(name + ' failed\n' + result.stdout + result.stderr)
        raise SystemExit(result.returncode)
    reports[name] = json.loads(result.stdout)

total = reports['package_01']['symbolic_scenarios'] + sum(
    r.get('total_cases', r.get('total_scenarios', r.get('cases_passed', 0)))
    for name, r in reports.items() if name != 'package_01'
)
print(json.dumps({
    'all_passed': True, 'symbolic_scenarios': total,
    'proof_scope': 'actual-source bounded symbolic execution; not HOI4 runtime',
    'reports': reports,
}, indent=2))
