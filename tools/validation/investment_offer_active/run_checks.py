"""Portable finite source-model validation. No native/game/process/Git operations."""
from pathlib import Path
import argparse,hashlib,json,runpy,sys
HERE=Path(__file__).resolve().parent
sha=lambda raw:hashlib.sha256(raw).hexdigest()
ADMISSION=runpy.run_path(str(HERE.parent/'ai_thinking_cost/source_admission.py'))
source_for_hash=ADMISSION['source_for_hash']
def verify_source(source,read=None):
 source=Path(source).resolve();catalog=json.loads((HERE/'catalog.json').read_bytes());read=read or (lambda p:p.read_bytes())
 assert source.is_dir(),'Explicit source-root must exist'
 ADMISSION['verify_pair'](source,read=read)
 for rel,h in catalog['required_source_sha256'].items():
  assert not Path(rel).is_absolute() and '..' not in Path(rel).parts
  assert sha(source_for_hash(read(source/rel),rel))==h,('Exact14 candidate/current11/unchanged source dependency required',rel)
 for rel,h in catalog['canonical_before_sha256'].items():assert sha((HERE/'before'/rel).read_bytes())==h,('Canonical before fixture drift',rel)
 manifest=(HERE/'manifest.json').read_bytes();assert sha(manifest)==catalog['candidate_manifest_sha256']
 return catalog
def verify_model_projection():
 journal=json.loads((HERE/'model-public-derivation.json').read_bytes());catalog=json.loads((HERE/'catalog.json').read_bytes());raw=(HERE/'_model.py').read_bytes()
 assert journal['origin_public_path']=='tools/validation/diplomacy_package_24/_model.py' and journal['derived']=='_model.py'
 assert len(journal['stages'])==10 and journal['native_model_equivalence_claim'] is False
 assert sha(raw)==journal['derived_sha256']
 for row in reversed(journal['stages']):
  before=bytes.fromhex(row['before_hex']);after=bytes.fromhex(row['after_hex']);offset=row['offset']
  assert 0<=offset<=len(raw) and raw[offset:offset+len(after)]==after,'Exact model adapter inverse required'
  raw=raw[:offset]+before+raw[offset+len(after):]
 assert sha(raw)==journal['origin_sha256']==catalog['upstream_public_model_sha256']
 return journal
def checks(source):
 catalog=verify_source(source);verify_model_projection();sys.path.insert(0,str(HERE))
 result=runpy.run_path(str(HERE/'test_contracts.py'),init_globals={'SOURCE_ROOT':Path(source).resolve(),'SOURCE_FOR_HASH':source_for_hash})
 report=result['report'];assert report['result']=='PASS' and report['checks']==3358 and len(report['cases'])==22
 assert report['native_acceptance'] is False and report['source_model_only'] is True
 assert report['ai_ordered_weights']['status']=='SOURCE_AST_EXPLICIT_25_AI_WEIGHTS_PASS_NATIVE_PENDING' and report['ai_ordered_weights']['checks']==3622 and report['ai_ordered_weights']['arithmetic_cases']==1236 and report['ai_ordered_weights']['opinion_policy_boundary_cases']==1056
 assert report['ai_ordered_weights']['original_modifiers']==25 and report['ai_ordered_weights']['ordinary_modifier_evaluation_passes']==1 and report['ai_ordered_weights']['negative_ast_mutations_rejected']==3 and report['ai_ordered_weights']['historical_compiler_AST_full_match'] is True
 assert report['ai_ordered_weights']['engine_rng_or_modifier_rounding_emulated'] is False and report['ai_ordered_weights']['native_accepted'] is False
 return {**report,'status':'PORTABLE_INVESTMENT_SOURCE_MODEL_PASS_NOT_NATIVE_ACCEPTANCE','source_after_sha256':{rel:sha((Path(source)/rel).read_bytes()) for rel in catalog['source_after_sha256']},'canonical_catalog_source_sha256':catalog['source_after_sha256'],'owned_hash_inverse_only':True,'investment_pair_cohort':ADMISSION['verify_pair'](source),'protected_current_eleven_sha256':catalog['protected_current_eleven_sha256'],'model_boundaries':catalog['model_boundaries'],'public_source_mutations':False,'profiles_or_game_launched':False}
def main():
 q=argparse.ArgumentParser(description=__doc__);q.add_argument('--source-root',type=Path,default=HERE.parents[2]);q.add_argument('--report',type=Path);a=q.parse_args();report=checks(a.source_root)
 if a.report is not None:
  assert not a.report.exists() and not a.report.is_symlink(),'Preserve previous report';a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode())
 print(json.dumps({'status':report['status'],'checks':report['checks'],'scenario_groups':len(report['cases']),'source_files':len(report['source_after_sha256']),'protected_current_source_files':len(report['protected_current_eleven_sha256']),'native_acceptance':False}))
if __name__=='__main__':main()
