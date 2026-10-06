"""Run current prior diplomacy checks and ammunition proofs independently."""
from pathlib import Path
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
reports = {}
for name, path in (('package_15', HERE.parent / 'diplomacy_package_15/run_checks.py'),
                   ('ammo', HERE / 'test_ammo.py'), ('source', HERE / 'test_source.py')):
    result = subprocess.run([sys.executable, '-B', str(path)], cwd=ROOT,
                            capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        sys.stderr.write(name + ' failed\n' + result.stdout + result.stderr)
        raise SystemExit(result.returncode)
    reports[name] = json.loads(result.stdout)
assert reports['package_15']['symbolic_scenarios'] == 6148
assert reports['ammo']['source_sha256'] == reports['source']['source_sha256'], 'Gameplay bytes differ between behavior and source checks'
for staged in (False, True):
    command = ['git', '-c', 'core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol', 'diff', '--check']
    if staged: command.insert(-1, '--cached')
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        sys.stderr.write(result.stdout + result.stderr); raise SystemExit(result.returncode)
print(json.dumps({'all_passed': True,
    'symbolic_scenarios': reports['package_15']['symbolic_scenarios'] + reports['ammo']['actual_source_scenarios'],
    'ammo_actual_source_scenarios': reports['ammo']['actual_source_scenarios'],
    'ammo_adapter_semantics_checks': reports['ammo']['adapter_semantics_cases'],
    'source_API_checks': reports['source']['source_API_cases'],
    'source_byte_adapter_boundary_checks': reports['source']['source_byte_adapter_boundary_cases'],
    'proof_scope': 'bounded ordered current-source ammunition transfer; not HOI4 runtime',
    'git_diff_whitespace_clean': True, 'reports': reports}, indent=2))
