"""Portable actual current AI thinking islands; finite source checks only."""
from pathlib import Path
import argparse,hashlib,json,runpy
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def checks(source):
 source=Path(source).resolve()
 admission=runpy.run_path(str(HERE/'source_admission.py'))
 assert admission['verify_all_current'](source)=='after','Current two-file after cohort required'
 assert sha((source/admission['CATALOG']['humanitarian_path']).read_bytes())==admission['ROWS'][admission['CATALOG']['humanitarian_path']]['candidate_sha256']
 econ=runpy.run_path(str(HERE/'test_investment_cache.py'),init_globals={'SOURCE_ROOT':source})['tests']()
 aid=runpy.run_path(str(HERE/'test_humanitarian_score.py'),init_globals={'SOURCE_ROOT':source})['report']
 rejected=[]
 for rel,row in admission['ROWS'].items():
  raw=(source/rel).read_bytes()
  for label,bad in [('foreign_after',raw+b'\n# foreign\n'),('foreign_before',(HERE/'before'/rel).read_bytes()+b'\n# foreign\n')]:
   try:admission['source_for_hash'](bad,rel)
   except AssertionError:rejected.append(rel+':'+label)
   else:raise AssertionError('Foreign byte edit admitted')
 pair=admission['PAIR'];raws={rel:(source/rel).read_bytes() for rel in pair}
 first=sorted(pair)[0];raws[first]=(HERE/'before'/first).read_bytes()
 try:admission['verify_pair'](source,read=lambda p:raws[p.relative_to(source).as_posix()])
 except AssertionError:rejected.append('mixed_investment_pair')
 else:raise AssertionError('Mixed investment pair admitted')
 return {'status':'ACTUAL_CURRENT_AI_THINKING_AST_PASS_NOT_NATIVE','investment_cache':econ,
  'humanitarian_score':aid,'admission_negative_controls':rejected,
  'source_sha256':{rel:sha((source/rel).read_bytes()) for rel in admission['ROWS']},
  'checks':econ['checks']+aid['checks']+len(rejected),'native_acceptance':False,
  'full_callback_arrays_executed':False,'native_TEMP_scope_or_lifetime_proven':False,
  'FPS_or_speedup_proven':False,'canonical_projection_or_read_shim_used':False}
def main():
 q=argparse.ArgumentParser(description=__doc__);q.add_argument('--source-root',type=Path,default=ROOT);a=q.parse_args()
 print(json.dumps(checks(a.source_root),ensure_ascii=False))
if __name__=='__main__':main()
