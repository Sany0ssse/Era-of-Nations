"""Run all checks for this packet and optionally save an immutable receipt."""
from pathlib import Path
import argparse, hashlib, json, subprocess, sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
TESTS=('test_ai_templates.py','test_ai_boundaries.py','test_technology_refs.py',
       'test_regimental_support.py','test_tutorial.py','test_native_fixture.py')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.output:
        assert not args.output.exists(), 'Preserve an earlier receipt'
    results=[]
    for name in TESTS:
        path=HERE/name
        done=subprocess.run([sys.executable,str(path)],cwd=ROOT,capture_output=True,text=True)
        results.append({'name':name,'exit_code':done.returncode,'output':done.stdout+done.stderr,
                        'test_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        print(name+': '+('PASS' if done.returncode==0 else 'FAIL'))
        if done.returncode:
            print(done.stdout+done.stderr)
    receipt={'passed':all(x['exit_code']==0 for x in results),'groups':len(results),
             'kind':'actual_source_checks_only','results':results}
    if args.output:
        args.output.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    sys.exit(0 if receipt['passed'] else 1)
