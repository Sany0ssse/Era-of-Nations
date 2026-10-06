"""Run explicit historical child compatibility and actual current initial-request checks."""
from pathlib import Path
import json
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
reports={}
commands=(('package_21',[sys.executable,'-B',str(HERE/'test_request.py'),'--historical-caller','tools/validation/diplomacy_package_21/run_checks.py']),
          ('request',[sys.executable,'-B',str(HERE/'test_request.py')]),
          ('source',[sys.executable,'-B',str(HERE/'test_source.py')]))
for name,command in commands:
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    if result.returncode:
        sys.stderr.write(name+' failed\n'+result.stdout+result.stderr)
        raise SystemExit(result.returncode)
    reports[name]=json.loads(result.stdout)
assert reports['package_21']['symbolic_scenarios']==7414
assert reports['package_21']['prior_scope']=='unchanged_children_with_historical_AB4_caller_view'
assert reports['package_21']['prior_counters_prove_current_initial_request_ownership'] is False
assert reports['package_21']['historical_bootstrap_current_models_loaded'] is False
assert reports['request']['actual_source_scenarios']==94 and reports['request']['adapter_semantics_cases']==28
assert reports['source']['source_cases']==164
assert reports['request']['source_sha256']==reports['source']['source_sha256'],'Gameplay bytes differ between current behavior and source checks'
assert not reports['request']['native_cost_charging_simulated'] and not reports['request']['native_resource_mutation_simulated']
for staged in (False,True):
    command=['git','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol','diff','--check']
    if staged:command.insert(-1,'--cached')
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    if result.returncode:
        sys.stderr.write(result.stdout+result.stderr);raise SystemExit(result.returncode)
print(json.dumps({'all_passed':True,'symbolic_scenarios':7414+reports['request']['actual_source_scenarios'],
    'prior_compatibility_scenarios':7414,'prior_scope':'unchanged_children_with_historical_AB4_caller_view',
    'prior_counters_prove_current_initial_request_ownership':False,
    'historical_bootstrap_current_models_loaded':False,
    'request_actual_source_scenarios':reports['request']['actual_source_scenarios'],
    'request_adapter_semantics_checks':reports['request']['adapter_semantics_cases'],
    'source_API_checks':reports['source']['source_API_cases'],
    'source_byte_adapter_boundary_checks':reports['source']['source_byte_adapter_boundary_cases'],
    'actual_current_game_sha256':reports['source']['source_sha256'],
    'historical_caller_manifest':reports['source']['historical_caller_manifest'],
    'native_cost_charging_simulated':False,'native_resource_mutation_simulated':False,'native_unit_creation_success_proven':False,
    'proof_scope':'94 actual current request-router scenarios plus7414 explicit preceding compatibility scenarios; native PP charging, delivery, unit creation and campaign unverified',
    'git_diff_whitespace_clean':True,'reports':reports},indent=2))
