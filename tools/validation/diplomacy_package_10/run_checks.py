"""Run prior diplomacy proof and antiterror lifecycle checks separately."""
from pathlib import Path
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
reports = {}
for name, path in (('package_09', HERE.parent / 'diplomacy_package_09/run_checks.py'),
                   ('antiterror', HERE / 'test_antiterror.py'),
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
                  'symbolic_scenarios': reports['package_09']['symbolic_scenarios'] + reports['antiterror']['actual_source_scenarios'],
                  'antiterror_actual_source_scenarios': reports['antiterror']['actual_source_scenarios'],
                  'antiterror_adapter_semantics_checks': reports['antiterror']['adapter_semantics_cases'],
                  'proof_scope': 'bounded ordered actual-source antiterror cooperation; not HOI4 runtime',
                  'git_diff_whitespace_clean': True, 'reports': reports}, indent=2))
