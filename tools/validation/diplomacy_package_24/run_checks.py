"""Package 24 only: prior byte/ROI expectations are intentionally not rewritten."""
from pathlib import Path
import json
import os
import subprocess
import sys

here=Path(__file__).resolve().parent
reports={}
for name in ('test_projects','test_comparisons','test_source'):
    result=subprocess.run([sys.executable,str(here/'run_current_v2.py'),'--test',name],cwd=here.parents[2],
        capture_output=True,text=True,encoding='utf-8',env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    if result.returncode:
        sys.stderr.write(name+' failed\n'+result.stdout+result.stderr)
        raise SystemExit(result.returncode)
    reports[name]=json.loads(result.stdout)
print(json.dumps({'all_passed':True,'symbolic_scenarios':reports['test_projects']['cases_passed'],
    'native_comparison_scenarios':reports['test_comparisons']['cases_passed'],
    'source_checks':reports['test_source']['source_checks'],
    'historical_validators':'Package02 original ROI and byte-boundary tests do not apply to the new protocol; they are unchanged.',
    'reports':reports,'legacy_pending_entry_projected':True,'current_v2_entry_proven_by_this_suite':False,'unchanged_live_protocol24_inner_verified':True},indent=2))
