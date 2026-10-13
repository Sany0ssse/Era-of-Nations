"""Run exact old test bodies through an explicit finite legacy-entry source view."""
from pathlib import Path
import argparse,hashlib,io,json,sys,types,contextlib
import investment_offer_source as view
HERE=Path(__file__).resolve().parent
sha=lambda raw:hashlib.sha256(raw).hexdigest()

def model_module(root):
 raw=(HERE/'_model.py').read_bytes();assert sha(raw)==view.PUBLIC_FILES['_model'],'Original model drift'
 text=raw.decode('utf-8');eol='\r\n' if '\r\n' in text else '\n'
 before='ROOT = Path(__file__).resolve().parents[3]';assert text.count(before)==1;text=text.replace(before,'ROOT = SOURCE_ROOT',1)
 before="    return ast((ROOT / relative).read_text(encoding='utf-8-sig'))";assert text.count(before)==1
 text=text.replace(before,"    return ast(legacy_source_bytes(ROOT, relative).decode('utf-8-sig'))",1)
 module=types.ModuleType('_model');module.__file__=str(HERE/'_model.py');module.__dict__.update(SOURCE_ROOT=root,legacy_source_bytes=view.legacy_source_bytes)
 exec(compile(text,module.__file__,'exec'),module.__dict__);sys.modules['_model']=module
 return module

def run(name,root):
 cohort=view.verify_cohort(root);model=model_module(root);inner=view.live_protocol24_inner(root,model.ast,model.one)
 raw=(HERE/(name+'.py')).read_bytes();assert sha(raw)==view.PUBLIC_FILES[name],'Unchanged original test body required'
 text=raw.decode('utf-8');projection_count=0
 if name=='test_source':
  # Historical-byte boundary section only; later current AST/native grammar reads stay live.
  marker='source_paths=existing+[';assert text.count(marker)==1;boundary,live=text.split(marker,1)
  for before,after in [
   ("(ROOT/path).read_bytes()","legacy_source_bytes(ROOT,path)"),
   ("(ROOT/path).read_text(encoding='utf-8-sig')","legacy_source_bytes(ROOT,path).decode('utf-8-sig')")]:
   projection_count+=boundary.count(before);boundary=boundary.replace(before,after)
  assert projection_count==5,'Exact historical-byte reader count required'
  text=boundary+marker+live
 out=io.StringIO()
 with contextlib.redirect_stdout(out):exec(compile(text,str(HERE/(name+'.py')),'exec'),{'__name__':'__main__','__file__':str(HERE/(name+'.py')),'legacy_source_bytes':view.legacy_source_bytes})
 result=json.loads(out.getvalue());result['pending_entry_projection']={'cohort':cohort,'original_test_sha256':sha(raw),'original_model_sha256':view.PUBLIC_FILES['_model'],'historical_source_reader_count':projection_count,**inner}
 if name=='test_source':
  result['check_groups']=['Legacy-entry projected boundary: '+label if i<6 else label for i,label in enumerate(result['check_groups'])]
  result['legacy_original_proof_scope']=result['proof_scope']
 result['proof_scope']='Unchanged protocol24 regression through exact canonical-before pending entry; actual live lifecycle/ROI helper and executor inner ASTs certified separately. Current v2 entry belongs to investment_offer_active; no native acceptance.'
 return result

def main():
 q=argparse.ArgumentParser(description=__doc__);q.add_argument('--test',choices=['test_projects','test_comparisons','test_source'],required=True);q.add_argument('--source-root',type=Path,default=HERE.parents[2]);a=q.parse_args()
 print(json.dumps(run(a.test,a.source_root.resolve()),indent=2))
if __name__=='__main__':main()
