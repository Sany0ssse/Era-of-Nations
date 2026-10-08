"""Run package25 suites without changing game or launcher state."""
from pathlib import Path
import subprocess,sys,json,os
root=Path(__file__).resolve().parent
reports={}
for name in ('test_delivery.py','test_source.py'):
    result=subprocess.run([sys.executable,'-B',str(root/name)],check=True,capture_output=True,text=True,
                          env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    reports[name.removeprefix('test_').removesuffix('.py')]=json.loads(result.stdout)
print(json.dumps({'package':25,'reports':reports,'native_campaign_verified':False},indent=2))
