"""Run prior diplomacy suites and ordered current equipment dispatch checks."""
from pathlib import Path
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
reports = {}
for name, path in (('package_18', HERE.parent / 'diplomacy_package_18/run_checks.py'),
                   ('equipment', HERE / 'test_equipment.py'), ('source', HERE / 'test_source.py')):
    result = subprocess.run([sys.executable, '-B', str(path)], cwd=ROOT,
                            capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        sys.stderr.write(name + ' failed\n' + result.stdout + result.stderr)
        raise SystemExit(result.returncode)
    reports[name] = json.loads(result.stdout)
assert reports['package_18']['symbolic_scenarios'] == 6539
assert reports['equipment']['actual_source_scenarios'] == 632
assert reports['equipment']['adapter_semantics_cases'] == 37
assert reports['source']['source_cases'] == 202
assert reports['equipment']['source_sha256'] == reports['source']['source_sha256'], 'Gameplay bytes differ between equipment behavior and source checks'
assert not reports['equipment']['native_stock_mutation_simulated']
assert not reports['equipment']['native_delivery_completion_proven']
for staged in (False, True):
    command = ['git', '-c', 'core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol', 'diff', '--check']
    if staged: command.insert(-1, '--cached')
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        sys.stderr.write(result.stdout + result.stderr); raise SystemExit(result.returncode)
print(json.dumps({'all_passed': True,
    'symbolic_scenarios': reports['package_18']['symbolic_scenarios'] + reports['equipment']['actual_source_scenarios'],
    'equipment_actual_source_scenarios': reports['equipment']['actual_source_scenarios'],
    'equipment_adapter_semantics_checks': reports['equipment']['adapter_semantics_cases'],
    'source_API_checks': reports['source']['source_API_cases'],
    'source_byte_adapter_boundary_checks': reports['source']['source_byte_adapter_boundary_cases'],
    'native_stock_mutation_simulated': False, 'native_delivery_completion_proven': False,
    'proof_scope': 'bounded ordered current-source equipment consent and native dispatch calls; not HOI4 shipment completion',
    'git_diff_whitespace_clean': True, 'reports': reports}, indent=2))
