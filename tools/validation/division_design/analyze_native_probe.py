"""Read a complete private native trace; source tests are not gameplay proof."""
from pathlib import Path
import argparse, hashlib, json, re

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def analyze(manifest_path, game_log, error_log):
    assert manifest_path.is_file(), 'Require an existing manifest'
    assert game_log.is_file(), 'Require an existing game log'
    assert error_log.is_file(), 'Require an existing error log'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    marker=manifest['marker']
    text=game_log.read_text(encoding='utf-8-sig',errors='replace')
    matched=re.findall(re.escape(marker)+r' (PASS|FAIL) ([A-Za-z0-9_]+)',text)
    expected=manifest['assertions']
    assert len(expected)==len(set(expected))
    actual=[name for status,name in matched]
    assert len(actual)==len(set(actual)), 'Repeated assertions must not inflate a result'
    assert set(actual)==set(expected), {'missing':sorted(set(expected)-set(actual)), 'unexpected':sorted(set(actual)-set(expected))}
    failures=[name for status,name in matched if status=='FAIL']
    endings=re.findall(re.escape(marker)+r' END passes=([0-9.]+) fails=([0-9.]+)',text)
    assert len(endings)==1, 'Require exactly one completed native run'
    assert tuple(float(n) for n in endings[0])==(len(expected)-len(failures),len(failures))
    assert not failures, failures
    assert marker+' ABORT' not in text
    errors=error_log.read_text(encoding='utf-8-sig',errors='replace')
    related=[line for line in errors.splitlines() if re.search(
        r'eon_regimental|division_design|eon_native_division|MAX_REGIMENTAL|EON_REGIMENT|EON_DIVISION',line,re.I)]
    assert not related, related[:20]
    source=Path(manifest['source_root'])
    for rel,digest in manifest['source_sha256'].items():
        assert sha(source/rel)==digest, 'Source changed after preparation: '+rel
    for rel,digest in manifest['fixture_sha256'].items():
        assert sha(source/rel)==digest, 'Fixture changed: '+rel
    return {'passed':True,'assertions':len(expected),'failed':0,'countries':manifest['countries'],
            'marker':marker,'manifest_sha256':sha(manifest_path),'game_log_sha256':sha(game_log),
            'error_log_sha256':sha(error_log),
            'related_script_errors':0,'source_sha256':manifest['source_sha256'],
            'limits':manifest['limits']}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--game-log',type=Path,required=True)
    p.add_argument('--error-log',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    assert not a.output.exists(), 'Preserve previous results'
    result=analyze(a.manifest,a.game_log,a.error_log)
    a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':True,'assertions':result['assertions'],'failed':0,'limits':result['limits']}))
