"""Run current-source package26 suites without touching game/launcher/save state."""
from pathlib import Path
import json,os,subprocess,sys
folder=Path(__file__).resolve().parent
reports={}
commands=[('relations',folder/'test_relations.py'),('source',folder/'test_source.py'),
 ('legacy_registry',folder/'test_legacy_registry.py'),
 ('national_relations',folder.parent/'diplomacy_package_23/test_relations.py')]
for name,path in commands:
 result=subprocess.run([sys.executable,'-B',str(path)],check=True,capture_output=True,text=True,encoding='utf-8',
  env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
 reports[name]=json.loads(result.stdout)
assert reports['relations']['source_sha256']==reports['source']['source_sha256'],'Source changed between suites'
hashes={}
for report in reports.values():
 for group in ('source_sha256','protected_dependencies_sha256'):
  for path,digest in report.get(group,{}).items():
   assert path not in hashes or hashes[path]==digest,('Source changed between current suites',path)
   hashes[path]=digest
print(json.dumps({'package':26,'all_passed':True,'reports':reports,
 'current_checked_source_sha256':hashes,
 'historical_full_package23_runner_verified':False,
 'native_campaign_verified':False,'native_save_load_verified':False,'native_multiplayer_verified':False},indent=2))
