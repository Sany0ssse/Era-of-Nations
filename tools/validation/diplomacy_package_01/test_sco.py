"""Source-driven SCO membership checks. No HOI4 campaign/engine simulation claim."""
from pathlib import Path
from copy import deepcopy
from itertools import product
import contextlib, io, runpy, json, hashlib

from _support import ROOT as root, baseline
work=Path(__file__).resolve().parent
with contextlib.redirect_stdout(io.StringIO()):
    base=runpy.run_path(str(work/'test_alliances.py'))
parse,block,raw_block=base['parse'],base['block'],base['raw_block']
Model,changed,observable=base['Model'],base['changed'],base['observable']
data=(root/'common/decisions/China.txt').read_bytes(); before=baseline('common/decisions/China.txt')
decision=raw_block(data,'apply_to_join_as_a_member')
old_decision=raw_block(before,'apply_to_join_as_a_member')
remove=block(decision,'remove_effect'); complete=block(decision,'complete_effect')
available=block(decision,'available'); old_available=block(old_decision,'available')
exit_effect=block(raw_block(data,'give_up_membership_status'),'complete_effect')
is_sco=block((root/'common/scripted_triggers/99_CHI_scripted_triggers.txt').read_bytes(),'is_sco')
assert available==old_available
new_limit=dict(remove[0][1])['limit']
assert new_limit[4:]==available, 'Existing application eligibility must be rechecked literally'
assert block(decision,'complete_effect')==block(old_decision,'complete_effect'), 'Retry/Voter flow changed'
for name in ['cost','days_remove']:
    import re
    pattern=(name+r'\s*=\s*(\d+)').encode()
    assert re.search(pattern,decision).group(1)==re.search(pattern,old_decision).group(1)

class SCOModel(Model):
    def trigger(self,nodes,stack):
        c=self.s['countries'][stack[-1]]
        for key,value in nodes:
            if key=='is_sco': passed=self.trigger(is_sco,stack)==(value=='yes')
            elif key=='is_subject': passed=c['subject']==(value=='yes')
            elif key=='is_in_faction': passed=(c['faction'] is not None)==(value=='yes')
            elif key=='has_government': passed=c['government']==value
            elif key=='has_completed_focus': passed=value in c['focuses']
            elif key=='has_war_with': passed=self.ref(value,stack) in c['wars']
            elif key=='original_tag': passed=c['original_tag']==value
            elif key in ['emerging_communist_state_are_in_power','emerging_reactionaries_are_in_power']:
                passed=key in c['political_macros'] # Explicit fixture inputs for these existing macro predicates.
            elif key=='AND': passed=self.trigger(value,stack)
            elif key=='if':
                condition=dict(value)['limit']
                passed=not self.trigger(condition,stack) or self.trigger([(k,v) for k,v in value if k!='limit'],stack)
            else: passed=super().trigger([(key,value)],stack)
            if not passed: return False
        return True

    def execute(self,nodes,stack):
        # Preserve all source branch/scoping execution in the base model;
        # only abstract the existing GUI refresh and notification effect.
        if len(nodes)==1 and nodes[0][0]=='SCO_dirty_update':
            self.s['dirty_updates']+=1; return
        if len(nodes)==1 and nodes[0][0]=='country_event':
            value=nodes[0][1]
            self.s['events'].append((stack[-1],dict(value)['id'] if isinstance(value,list) else value)); return
        # Base execute dispatches a block in one pass. Register the existing
        # refresh effect as an interpreted marker that returns to this override.
        super().execute(nodes,stack)

# Abstract the existing refresh macro as a witnessed invocation marker.
effects=deepcopy(changed)
effects['SCO_dirty_update']=[('set_temp_variable',[('eon_SCO_dirty_called','1')])]

def fixture(kind='sco_member', observer=True, nested=False, array_count=0, app_faction=None, chi_faction=None):
    s=base['state']('CSTO', app_faction,False,False,True,False,nested)
    def fresh(faction,ideas): return {'faction':faction,'ideas':set(ideas),'flags':set(),'sharing':set(),'temp':{}}
    s['countries']['CHI']=fresh(chi_faction,[kind] if kind else [])
    s['countries']['SOV']=fresh('CSTO',['CSTO_member'])
    s['leaders']['CSTO']='SOV'
    s['templates']['SCO']='faction_template_sco'; s['leaders']['SCO']='CHI'
    s['templates']['ChinaOther']='faction_template_other'; s['leaders']['ChinaOther']='CHI'
    s['arrays']['global.sco_members']=['CHI']+['APP']*array_count
    if observer:s['countries']['APP']['ideas'].add('sco_observer')
    for tag,c in s['countries'].items():
        c.update({'subject':False,'government':'communism','focuses':set(),'wars':set(),'original_tag':tag,'political_macros':set()})
    s['dirty_updates']=0
    return s

def run(nodes,s):
    model=SCOModel(s,effects,offer_callback=True)
    model.execute(nodes,['APP'])
    s['dirty_updates']+=int(s['countries']['APP']['temp'].pop('eon_SCO_dirty_called',0))
    return model

counts={'eligibility':0,'political_conditions':0,'civil_military':0,'exit':0,'retry':0,'rules':0,'callback_integration':0}
for veto,subject,observer,kind,war_chi,war_sov,dominance,nested in product([False,True],[False,True],[False,True],['sco_member','sco_member_econ','sco_member_pol','sco_member_mil',None],[False,True],[False,True],[False,True],[False,True]):
    s=fixture(kind,observer,nested,array_count=2); app=s['countries']['APP']; chi=s['countries']['CHI']
    if veto:app['flags'].add('SCO_membership_rejected')
    app['subject']=subject
    if war_chi:app['wars'].add('CHI')
    if war_sov:app['wars'].add('SOV')
    if dominance:chi['focuses'].add('CHI_Chinese_Dominance')
    initial=observable(s); run(remove,s)
    accepted=not veto and not subject and observer and kind is not None and not war_chi and (dominance or not war_sov)
    if accepted:
        assert s['arrays']['global.sco_members'].count('APP')==1 and kind in app['ideas'] and 'sco_observer' not in app['ideas']
        assert len(s['news'])==1 and s['news'][0]==('APP','sco.7') and s['dirty_updates']==1
        assert 'ORIGIN' not in s['arrays']['global.sco_members']
        once=observable(s); run(remove,s); assert observable(s)==once
    else: assert observable(s)==initial
    counts['eligibility']+=1

for actor_government,chi_government,asean,undermine,ukr,communist,reactionary,ukr_focus in product(['communism','democratic'],['communism','democratic'],[False,True],[False,True],[False,True],[False,True],[False,True],[False,True]):
    s=fixture(); app=s['countries']['APP']; chi=s['countries']['CHI']
    app['government']=actor_government; chi['government']=chi_government
    if asean:app['ideas'].add('ASEAN_Member')
    if undermine:chi['focuses'].add('CHI_Undermine_ASEAN')
    if ukr:app['original_tag']='UKR'
    if communist:app['political_macros'].add('emerging_communist_state_are_in_power')
    if reactionary:app['political_macros'].add('emerging_reactionaries_are_in_power')
    if ukr_focus:app['focuses'].update(['UKR_commie_china_trade','UKR_party_regions_inaguration'])
    initial=observable(s); run(remove,s)
    accepted=not(chi_government=='communism' and actor_government=='democratic') and (not asean or undermine) and (not ukr or ((communist or reactionary) and ukr_focus))
    assert ('sco_member' in app['ideas'])==accepted
    if not accepted:assert observable(s)==initial
    counts['political_conditions']+=1

for app_faction,chi_faction,split,military,nested in product([None,'CSTO','unrelated','SCO'],[None,'SCO','ChinaOther'],[False,True],[False,True],[False,True]):
    s=fixture(nested=nested,app_faction=app_faction,chi_faction=chi_faction); app=s['countries']['APP']; chi=s['countries']['CHI']
    if split:chi['focuses'].add('CHI_Split_CSTO')
    if military:chi['focuses'].add('CHI_An_Alliance_to_Rival_NATO')
    if app_faction=='CSTO':
        app['ideas'].add('CSTO_member'); app['sharing'].add('CSTO_Tech_Share')
        s['arrays']['global.CSTO_member'].extend(['APP','APP'])
    run(remove,s)
    expected=None if split and app_faction=='CSTO' else app_faction
    if military and chi_faction=='SCO' and expected in [None,'SCO']:expected='SCO'
    assert app['faction']==expected and 'sco_member' in app['ideas']
    if split and app_faction=='CSTO':
        assert 'CSTO_member' not in app['ideas'] and 'CSTO_Tech_Share' not in app['sharing']
        assert 'APP' not in s['arrays']['global.CSTO_member']; counts['callback_integration']+=1
    assert s['countries']['ORIGIN']['faction'] is None
    counts['civil_military']+=1

all_kinds=['sco_member','sco_member_econ','sco_member_pol','sco_member_mil']
for mask,array_count,faction,nested in product(range(16),range(3),[None,'SCO','unrelated','ChinaOther'],[False,True]):
    s=fixture(None,False,nested,array_count,faction,'ChinaOther'); app=s['countries']['APP']
    app['ideas'].update(kind for i,kind in enumerate(all_kinds) if mask&(1<<i))
    # Reject a misleading faction shared with China unless it has the SCO template.
    run(exit_effect,s)
    assert not set(all_kinds)&app['ideas'] and 'APP' not in s['arrays']['global.sco_members']
    assert app['faction']==(None if faction=='SCO' and (mask or array_count) else faction)
    assert s['dirty_updates']==int(bool(mask or array_count)) and len(s['news'])==int(bool(mask or array_count))
    once=observable(s); run(exit_effect,s); assert observable(s)==once
    counts['exit']+=1

for old_veto,dominance,nested in product([False,True],repeat=3):
    s=fixture(nested=nested); app=s['countries']['APP']; chi=s['countries']['CHI']
    if old_veto:app['flags'].add('SCO_membership_rejected')
    if dominance:chi['focuses'].add('CHI_Chinese_Dominance')
    run(complete,s)
    assert 'SCO_membership_rejected' not in app['flags']
    assert s['events']==([('CHI','sco.2')] if dominance else [('CHI','sco.2'),('SOV','sco.2')])
    counts['retry']+=1

rules=(root/'common/factions/rules/joining_rules.txt').read_bytes(); old_rules=baseline('common/factions/rules/joining_rules.txt')
for name in ['joining_rule_sco','joining_rule_sco_eco','joining_rule_sco_political','joining_rule_sco_mil']:
    newbody=raw_block(rules,name); oldbody=raw_block(old_rules,name)
    assert newbody.replace(b'is_sco = yes',b'has_idea = sco_member')==oldbody
    # Only the final trigger is parsed; AI+100 replacement is verified byte-for-byte.
    trigger=block(newbody,'trigger')
    for kind in all_kinds+[None]:
        s=fixture(kind,False); s['countries']['APP']['ideas']=({kind} if kind else set())
        assert SCOModel(s,effects).trigger(trigger,['APP'])==(kind is not None); counts['rules']+=1

# Unrelated source material remains exactly unchanged, even in the two large files.
for name in ['apply_to_join_as_a_member','give_up_membership_status']:
    new_span=re.search(name.encode()+rb'\s*=\s*\{',data).start(); old_span=re.search(name.encode()+rb'\s*=\s*\{',before).start()
    # Whole-decision normalization removes the only changed decisions for comparison.
def strip_blocks(source,names):
    out=source
    for name in names:
        match=re.search(name.encode()+rb'\s*=\s*\{',out); start=match.start()
        raw=raw_block(out,name); opening=match.end(); end=opening+len(raw)+1
        out=out[:start]+out[end:]
    return out
assert strip_blocks(data,['apply_to_join_as_a_member','give_up_membership_status'])==strip_blocks(before,['apply_to_join_as_a_member','give_up_membership_status'])
names=['joining_rule_sco','joining_rule_sco_eco','joining_rule_sco_political','joining_rule_sco_mil']
assert strip_blocks(rules,names)==strip_blocks(old_rules,names)
integration=counts.pop('callback_integration')
report={'test_level':'source-driven symbolic branch model; not game/campaign proof','case_counts':counts,'total_cases':sum(counts.values()),'csto_callback_integration_cases_within_civil_military':integration,
        'preserved':['application complete_effect/retry/voter flow','200 PP and 90 days','all existing eligibility conditions repeated as AST','other China decisions unchanged','other faction rules unchanged','civil membership independent of unrelated faction'],
        'limits':['Existing macro predicates for Ukrainian political paths are fixture inputs, not reimplemented.', 'SCO_dirty_update is witnessed as one call; the full GUI redraw is not emulated.', 'Affirmative votes and request generations remain outside this bounded repair.', 'Story sco.10 and focus paths remain unmodified exceptions.', 'Native admission/template/technology callback order requires a new campaign check.'],
        'source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ['common/decisions/China.txt','common/factions/rules/joining_rules.txt']}}
print(json.dumps(report,indent=2))
