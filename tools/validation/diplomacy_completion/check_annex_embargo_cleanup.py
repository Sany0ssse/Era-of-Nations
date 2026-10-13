"""Execute the narrow annex cleanup which failed in native probe 08."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
PATH='common/on_actions/00_costili.txt'
BASELINE='f2832b6bfd980066163d0a69a6306169c992c5d7'
LEGACY_SHA256='d9926b76681318590660883b468756f926711ae633a40813c5734fc353fe01cb'
sys.path.insert(0,str(ROOT/'tools/validation'))
from peace_settlement.legacy_source_compat import restore_consensual_annex_guards
spec=importlib.util.spec_from_file_location('eon_annex_cleanup_ast',ROOT/'tools/validation/diplomacy_package_03/_support.py')
parser=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=parser
spec.loader.exec_module(parser)

class CleanupModel(parser.Model):
    def trigger(self,nodes,stack=None):
        stack=[self.current] if stack is None else stack
        return all(node[2] in self.countries[stack[-1]].dynamic_modifiers
                   if node[0]=='has_dynamic_modifier' else super(CleanupModel,self).trigger([node],stack)
                   for node in nodes)
    def effect(self,nodes,stack=None):
        stack=[self.current] if stack is None else stack
        for key,op,value in nodes:
            if key=='remove_dynamic_modifier':
                modifier=parser.one(value,'modifier')
                owner=self.countries[stack[-1]]
                assert modifier in owner.dynamic_modifiers, 'Attempt to remove absent modifier'
                owner.dynamic_modifiers.remove(modifier)
                self.removals.append(stack[-1])
            elif key=='clear_variable':
                self.countries[stack[-1]].variables.pop(value,None)
            else:
                super().effect([(key,op,value)],stack)

def assert_historical_annex_source(raw,before):
    # Preservation only: inverse the already accepted two exact peace guards.
    # Runtime/model assertions below still parse the complete current source.
    assert hashlib.sha256(before).hexdigest()==LEGACY_SHA256, 'Whole legacy baseline changed'
    preservation=restore_consensual_annex_guards(raw)
    newline=b'\r\n' if b'\r\n' in before else b'\n'
    old=b'\t\t\t\tremove_dynamic_modifier = {\tmodifier = embargo_dynamic_modifier\t}'
    new=newline.join((b'\t\t\t\tif = {',
        b'\t\t\t\t\tlimit = { has_dynamic_modifier = embargo_dynamic_modifier }',
        b'\t\t\t\t\tremove_dynamic_modifier = {\tmodifier = embargo_dynamic_modifier\t}',
        b'\t\t\t\t}'))
    assert before.count(old)==preservation.count(new)==2
    assert preservation.replace(new,old)==before, 'Unrelated legacy bytes changed'
    return preservation

def main():
    raw=(ROOT/PATH).read_bytes()
    before=subprocess.check_output(['git','show',BASELINE+':'+PATH],cwd=ROOT)
    assert_historical_annex_source(raw,before)
    actions=parser.one(parser.ast(raw),'on_actions')
    cases=0
    for hook,scope,target in (('on_annex','FROM',2),('on_subject_annexed','ROOT',1)):
        candidates=[]
        for key,_,hook_body in actions:
            if key!=hook:
                continue
            scoped=parser.maybe(parser.maybe(hook_body,'effect',[]),scope,[])
            if scoped and scoped[0]==('revoke_sanctions_non_exist_country','=','yes'):
                candidates.append(scoped)
        assert len(candidates)==1, (hook,len(candidates))
        body=candidates[0]
        assert body[0]==('revoke_sanctions_non_exist_country','=','yes')
        assert [n[0] for n in body[1:]]==['if','clear_variable','clear_variable']
        for present in (False,True):
            model=CleanupModel(root=1,from_=2,current=1)
            model.removals=[]
            for ident,country in model.countries.items():
                country.dynamic_modifiers={'unrelated_modifier'}
                country.variables.update(treasury=700+ident,embargo_modifier_value=4,
                                         embargo_modifier_value_minus=-4)
            if present:
                model.countries[target].dynamic_modifiers.add('embargo_dynamic_modifier')
            outside={ident:(dict(country.variables),set(country.dynamic_modifiers))
                     for ident,country in model.countries.items() if ident!=target}
            # The already completed revoke helper is outside this narrow repair.
            actual=[(scope,'=',body[1:])]
            for _ in range(2):
                model.effect(actual,[1])
                assert model.removals==([target] if present else [])
                owner=model.countries[target]
                assert owner.variables=={'treasury':700+target}
                assert owner.dynamic_modifiers=={'unrelated_modifier'}
                assert outside=={ident:(dict(country.variables),set(country.dynamic_modifiers))
                                 for ident,country in model.countries.items() if ident!=target}
                cases+=1
    print(json.dumps({'checks_passed':True,'cases':cases,'source_sha256':{PATH:hashlib.sha256(raw).hexdigest()},
        'baseline_commit':BASELINE,'native_annex_cleanup_proven':False,
        'proof_scope':'actual post-revoke cleanup, source-frame and byte preservation; revoke helper and native annex hook order outside scope'},indent=2))

if __name__=='__main__':
    main()
