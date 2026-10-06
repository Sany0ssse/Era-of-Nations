"""Run the unchanged preceding package and actual one-use national normalization checks."""
from pathlib import Path
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
reports = {}
commands = (('package_22', [sys.executable, '-B', str(HERE.parent/'diplomacy_package_22/run_checks.py')]),
            ('relations', [sys.executable, '-B', str(HERE/'test_relations.py')]),
            ('source', [sys.executable, '-B', str(HERE/'test_source.py')]))
for name, command in commands:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        sys.stderr.write(name+' failed\n'+result.stdout+result.stderr)
        raise SystemExit(result.returncode)
    reports[name] = json.loads(result.stdout)
assert reports['package_22']['symbolic_scenarios'] == 7508
assert reports['package_22']['request_actual_source_scenarios'] == 94
assert reports['package_22']['prior_compatibility_scenarios'] == 7414
assert reports['package_22']['prior_scope'] == 'unchanged_children_with_historical_AB4_caller_view'
assert reports['relations']['actual_source_scenarios'] == 147 and reports['relations']['adapter_semantics_cases'] == 12
assert reports['source']['source_cases'] == 152
assert reports['relations']['source_sha256'] == reports['source']['source_sha256'], 'Current gameplay bytes differ between checks'
assert reports['relations']['protected_dependencies_sha256'] == reports['source']['protected_dependencies_sha256']
assert not reports['relations']['new_historical_caller_projection'] and not reports['relations']['native_resource_mutation_simulated']
for staged in (False, True):
    command = ['git', '-c', 'core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol', 'diff', '--check']
    if staged: command.insert(-1, '--cached')
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        sys.stderr.write(result.stdout+result.stderr); raise SystemExit(result.returncode)
print(json.dumps({'all_passed': True, 'symbolic_scenarios': 7508+reports['relations']['actual_source_scenarios'],
    'previous_package_scenarios': 7508, 'prior_current_initial_request_scenarios': 94, 'prior_compatibility_scenarios': 7414,
    'prior_scope': 'unchanged_children_with_historical_AB4_caller_view', 'new_historical_caller_projection': False,
    'relations_actual_source_scenarios': reports['relations']['actual_source_scenarios'],
    'relations_adapter_semantics_checks': reports['relations']['adapter_semantics_cases'],
    'source_API_checks': reports['source']['source_API_cases'], 'source_byte_adapter_boundary_checks': reports['source']['source_byte_adapter_boundary_cases'],
    'actual_current_game_sha256': reports['source']['source_sha256'],
    'protected_dependencies_sha256': reports['source']['protected_dependencies_sha256'],
    'native_runtime': False, 'native_physical_mission_presence_proven': False, 'native_resource_mutation_simulated': False,
    'immutable_event_generation_proven': False,
    'proof_scope': '147 actual one-use national normalization scenarios plus the unchanged preceding7508 scenario report; earlier declared caller compatibility remains bounded, native campaign and physical embassy presence unverified',
    'git_diff_whitespace_clean': True, 'reports': reports}, indent=2))
