"""Run previous source proof and the bounded mediation package separately."""
from pathlib import Path
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
reports = {}
for name, path in (('package_07', HERE.parent / 'diplomacy_package_07/run_checks.py'),
                   ('mediation', HERE / 'test_mediation.py'),
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
                  'symbolic_scenarios': reports['package_07']['symbolic_scenarios'] + reports['mediation']['actual_source_scenarios'],
                  'mediation_actual_source_scenarios': reports['mediation']['actual_source_scenarios'],
                  'mediation_adapter_semantics_checks': reports['mediation']['adapter_semantics_cases'],
                  'proof_scope': 'bounded ordered actual-source mediation; not HOI4 runtime',
                  'git_diff_whitespace_clean': True, 'reports': reports}, indent=2))
