"""Run current package27 source and actual-script scenario checks."""
from pathlib import Path
import json, subprocess, sys

folder=Path(__file__).resolve().parent
results=[]
for name in ('test_source.py','test_scope_semantics.py','test_settlement.py','test_rounding.py'):
    result=subprocess.run([sys.executable,'-B',str(folder/name)],capture_output=True,text=True,encoding='utf-8')
    if result.returncode:
        print(result.stdout,end='');print(result.stderr,end='',file=sys.stderr)
        raise SystemExit(result.returncode)
    results.append({'name':name,'result':json.loads(result.stdout)})
print(json.dumps({'package':27,'all_passed':True,'suites':results,
                  'native_campaign_verified':False},indent=2))
