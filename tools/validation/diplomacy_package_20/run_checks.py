"""Run prior diplomacy suites and bounded national defence formation checks."""
from pathlib import Path
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
reports = {}
for name,path in (('package_19',HERE.parent/'diplomacy_package_19/run_checks.py'),
                  ('formation',HERE/'test_formation.py'),('source',HERE/'test_source.py')):
    result = subprocess.run([sys.executable,'-B',str(path)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    if result.returncode:
        sys.stderr.write(name+' failed\n'+result.stdout+result.stderr)
        raise SystemExit(result.returncode)
    reports[name] = json.loads(result.stdout)
assert reports['package_19']['symbolic_scenarios'] == 7171
assert reports['formation']['actual_source_scenarios'] == 122
assert reports['formation']['adapter_semantics_cases'] == 29
assert reports['source']['source_cases'] == 155
assert reports['formation']['source_sha256'] == reports['source']['source_sha256'], 'Gameplay bytes differ between formation behavior and source checks'
assert not reports['formation']['native_resource_mutation_simulated']
assert not reports['formation']['native_unit_creation_success_proven']
for staged in (False,True):
    command = ['git','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol','diff','--check']
    if staged: command.insert(-1,'--cached')
    result = subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    if result.returncode:
        sys.stderr.write(result.stdout+result.stderr); raise SystemExit(result.returncode)
print(json.dumps({'all_passed':True,
    'symbolic_scenarios':reports['package_19']['symbolic_scenarios']+reports['formation']['actual_source_scenarios'],
    'formation_actual_source_scenarios':reports['formation']['actual_source_scenarios'],
    'formation_adapter_semantics_checks':reports['formation']['adapter_semantics_cases'],
    'source_API_checks':reports['source']['source_API_cases'],
    'source_byte_adapter_boundary_checks':reports['source']['source_byte_adapter_boundary_cases'],
    'native_resource_mutation_simulated':False,'native_unit_creation_success_proven':False,
    'proof_scope':'bounded ordered current-source consent and national formation resource/create calls; not native consumption or spawn success',
    'git_diff_whitespace_clean':True,'reports':reports},indent=2))
