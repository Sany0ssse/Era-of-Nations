"""Run previous diplomacy proof and the bounded consultation package."""
from pathlib import Path
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
reports = {}
for name, path in (('package_06', HERE.parent / 'diplomacy_package_06/run_checks.py'),
                   ('consultations', HERE / 'test_consultations.py'),
                   ('source', HERE / 'test_source.py')):
    result = subprocess.run([sys.executable, '-B', str(path)], cwd=ROOT,
                            capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        sys.stderr.write(name + ' failed\n' + result.stdout + result.stderr)
        raise SystemExit(result.returncode)
    reports[name] = json.loads(result.stdout)
for staged in (False, True):
    command = ['git', '-c', 'core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol', 'diff', '--check']
    if staged: command.insert(-1, '--cached')
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        sys.stderr.write(result.stdout + result.stderr); raise SystemExit(result.returncode)
print(json.dumps({'all_passed': True,
                  'symbolic_scenarios': reports['package_06']['symbolic_scenarios'] + reports['consultations']['actual_source_scenarios'],
                  'consultation_actual_source_scenarios': reports['consultations']['actual_source_scenarios'],
                  'consultation_adapter_semantics_checks': reports['consultations']['adapter_semantics_cases'],
                  'proof_scope': 'bounded actual-source consultations; not HOI4 runtime',
                  'git_diff_whitespace_clean': True, 'reports': reports}, indent=2))
