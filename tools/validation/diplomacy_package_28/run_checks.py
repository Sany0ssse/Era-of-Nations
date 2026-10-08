from pathlib import Path
import json,os,subprocess,sys
folder=Path(__file__).resolve().parent
reports={}
env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONUTF8='1')
for name in ('lifecycle','source'):
 result=subprocess.run([sys.executable,str(folder/('test_'+name+'.py'))],capture_output=True,text=True,encoding='utf-8',env=env)
 if result.returncode:
  sys.stderr.write(result.stdout+result.stderr);raise SystemExit(result.returncode)
 reports[name]=json.loads(result.stdout)
assert reports['lifecycle']['source_sha256']==reports['source']['source_sha256'],'Game sources changed during the checks'
print(json.dumps({'package':28,'all_passed':True,'reports':reports,'source_sha256':reports['source']['source_sha256'],
 'native_campaign_proven':False,'native_save_load_proven':False,'multiplayer_proven':False,
 'proof_scope':'Current action/decision/effect/trigger/on-action AST and exact source boundaries; external influence and Singapore helpers are witnessed, not simulated.'},indent=2))
