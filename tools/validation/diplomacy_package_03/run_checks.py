"""Run all three diplomacy source packages; never substitute for HOI4 runtime."""
from pathlib import Path
import json
import subprocess
import sys

from _support import ROOT

HERE = Path(__file__).resolve().parent
reports = {}
targets = [
    ('package_02', HERE.parent / 'diplomacy_package_02/run_checks.py'),
    ('ordinary_alliance', HERE / 'test_ordinary_alliance.py'),
    ('source', HERE / 'test_source.py'),
]
for name, path in targets:
    result = subprocess.run([sys.executable, str(path)], cwd=ROOT,
                            capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        sys.stderr.write(name + ' failed\n' + result.stdout + result.stderr)
        raise SystemExit(result.returncode)
    reports[name] = json.loads(result.stdout)

for staged in (False, True):
    command = ['git', '-c', 'core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol',
               'diff', '--check']
    if staged: command.insert(-1, '--cached')
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        sys.stderr.write(result.stdout + result.stderr)
        raise SystemExit(result.returncode)

total = reports['package_02']['symbolic_scenarios'] + reports['ordinary_alliance']['total_cases']
print(json.dumps({
    'all_passed': True, 'symbolic_scenarios': total,
    'proof_scope': 'bounded actual-source execution with supplied native facts; not HOI4 runtime',
    'git_diff_whitespace_clean': True, 'reports': reports,
}, indent=2))
