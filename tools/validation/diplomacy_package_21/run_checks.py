"""Run preceding diplomacy suites and bounded donor-funded advisory checks."""
from pathlib import Path
import json
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
reports={}
for name,path in (('package_20',HERE.parent/'diplomacy_package_20/run_checks.py'),
                  ('advisers',HERE/'test_advisers.py'),('source',HERE/'test_source.py')):
    result=subprocess.run([sys.executable,'-B',str(path)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    if result.returncode:
        sys.stderr.write(name+' failed\n'+result.stdout+result.stderr)
        raise SystemExit(result.returncode)
    reports[name]=json.loads(result.stdout)
assert reports['package_20']['symbolic_scenarios']==7293
assert reports['advisers']['actual_source_scenarios']==121
assert reports['advisers']['adapter_semantics_cases']==18
assert reports['source']['source_cases']==190
assert reports['advisers']['source_sha256']==reports['source']['source_sha256'], 'Gameplay bytes differ between behavior and source checks'
assert not reports['advisers']['native_resource_mutation_simulated']
assert not reports['advisers']['native_unit_creation_success_proven']
for staged in (False,True):
    command=['git','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol','diff','--check']
    if staged:command.insert(-1,'--cached')
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    if result.returncode:
        sys.stderr.write(result.stdout+result.stderr);raise SystemExit(result.returncode)
print(json.dumps({'all_passed':True,
    'symbolic_scenarios':reports['package_20']['symbolic_scenarios']+reports['advisers']['actual_source_scenarios'],
    'advisers_actual_source_scenarios':reports['advisers']['actual_source_scenarios'],
    'advisers_adapter_semantics_checks':reports['advisers']['adapter_semantics_cases'],
    'source_API_checks':reports['source']['source_API_cases'],
    'source_byte_adapter_boundary_checks':reports['source']['source_byte_adapter_boundary_cases'],
    'native_resource_mutation_simulated':False,'native_unit_creation_success_proven':False,
    'proof_scope':'bounded current-source paid advisory lifecycle and known treasury arithmetic; native political outcomes and playable campaign unverified',
    'git_diff_whitespace_clean':True,'reports':reports},indent=2))
