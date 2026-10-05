"""Run package checks without mutating gameplay files or private receipts."""
from pathlib import Path
import json
import subprocess
import sys

from _support import ROOT

HERE = Path(__file__).resolve().parent
reports = {}
for name in ('test_alliances', 'test_sco', 'test_contracts', 'test_energy', 'test_framework', 'test_source'):
    result = subprocess.run([sys.executable, str(HERE / (name + '.py'))], cwd=ROOT,
                            capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        sys.stderr.write(name + ' failed\n' + result.stdout + result.stderr)
        raise SystemExit(result.returncode)
    reports[name] = json.loads(result.stdout)

# Preserve the game's BOM/CRLF files while still rejecting trailing spaces,
# tabs before indentation and blank lines at EOF, in both candidate layers.
for layer in ([], ['--cached']):
    whitespace = subprocess.run(['git', '-c', 'core.whitespace=trailing-space,space-before-tab,cr-at-eol',
                                 'diff', *layer, '--check'], cwd=ROOT, capture_output=True, text=True)
    if whitespace.returncode:
        sys.stderr.write(whitespace.stdout + whitespace.stderr)
        raise SystemExit(whitespace.returncode)
total = sum(r.get('total_cases', r.get('total_scenarios', r.get('cases_passed', 0))) for r in reports.values())
print(json.dumps({'all_passed': True, 'symbolic_scenarios': total,
                  'proof_scope': 'source validation and bounded symbolic models; not HOI4 runtime',
                  'git_diff_whitespace_clean': True, 'crlf_recognized_as_line_endings': True,
                  'reports': reports}, indent=2))
