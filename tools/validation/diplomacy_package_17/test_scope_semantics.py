"""Current support AST regressions against exact old READ operands.

Native10/29 calibrate bare temporary READ and FLAG selectors only. Asset commands
remain observations; sixteen qualified project result WRITEs are not executed.
No game/source reader, file, fixture or condition is overwritten on disk.
"""
from pathlib import Path
from copy import deepcopy
import hashlib,importlib.util,json,sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/validation'))
from diplomacy_package_17._scope_repair import JOURNAL,game_before,test_before
executor=ROOT/'tools/validation/diplomacy_package_22/test_request.py'
text=executor.read_text(encoding='utf-8')
boundary='\ndef focus(name):'
assert text.count(boundary)==1
namespace={'__file__':str(executor),'__name__':'support_scope_ordered_definitions'}
exec(compile(text.split(boundary)[0],str(executor),'exec'),namespace)
class Adapter: pass
m=Adapter()
for key,val in namespace.items():setattr(m,key,val)
plan={'files':JOURNAL['support_reads']}
new_effects=deepcopy(m.model['effects']);new_triggers=deepcopy(m.model['capacity_triggers'])
original_effects=deepcopy(new_effects);original_triggers=deepcopy(new_triggers)
for path in plan['files']:
    target=original_effects if '/scripted_effects/' in path else original_triggers
    raw=game_before(path,(ROOT/path).read_bytes())
    target.update({key:val for key,op,val in m.model['ast'](raw.decode('utf-8-sig'))})
cases=[]
def state():
    result=m.state();result['countries']['B']['wars']={'C'}
    result['countries']['A']['flags'].add('aid_request_cd_@B')
    return result
def registry(effects,triggers):
    m.model['effects'].clear();m.model['effects'].update(deepcopy(effects))
    m.model['capacity_triggers'].clear();m.model['capacity_triggers'].update(deepcopy(triggers))
def candidate():registry(new_effects,new_triggers)
def originals():registry(original_effects,original_triggers)
def check(s,key,actor='B',peer='A',temporary=None,from_from=None):
    return m.check(s,[(key,'=','yes')],actor=actor,from_=peer,temporary=temporary,from_from=from_from)
def effect(s,key,actor='A',peer='B',temporary=None,from_from=None):
    m.effect(s,[(key,'=','yes')],actor=actor,from_=peer,temporary=temporary,from_from=from_from)
def wallet(s):return {c:d['variables']['treasury'] for c,d in s['countries'].items()}
def rhs(nodes,before,after):
    return [(k,o,rhs(v,before,after) if isinstance(v,list) else after if v==before else v) for k,o,v in nodes]
def investment_model():
    path=ROOT/'tools/validation/diplomacy_package_24/_model.py'
    spec=importlib.util.spec_from_file_location('support_cofund_islands',path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result

# Country names A/B are explicit native-country-ID fixtures; classification,
# industry, war and opinion inputs retain the existing suite's declared facts.
for family in ('advisers','services','foreign_cash','foreign_equipment','defence_formation'):
    originals();s=state();key=f'eon_{family}_policy_allowed'
    temporary={f'eon_{family}_policy_provider':'A'}
    before=check(s,key,temporary=temporary);candidate();after=check(s,key,temporary=temporary)
    assert before is False and after is True,(family,before,after)
    cases.append({'case':family+'_actual_policy_gate','old_current_source':before,'repaired_current_source':after})
originals();s=state();key='eon_support_request_policy_allowed';temp={'eon_support_request_policy_requester':'B'}
before=check(s,key,actor='A',peer='B',temporary=temp);candidate();after=check(s,key,actor='A',peer='B',temporary=temp)
assert before is False and after is True
cases.append({'case':'support_request_actual_policy_gate','old_current_source':before,'repaired_current_source':after})

for family,key in (('services','selection_ready'),('advisers','selection_ready'),('foreign_cash','offer_ready'),
                   ('foreign_equipment','offer_ready'),('defence_formation','offer_ready')):
    originals();s=state();temp={'eon_services_requested_kind':1} if family=='services' else None
    before=check(s,f'eon_{family}_{key}',actor='A',peer='B',temporary=temp,from_from='B')
    candidate();after=check(s,f'eon_{family}_{key}',actor='A',peer='B',temporary=temp,from_from='B')
    assert before is False and after is True,(family,before,after)
    cases.append({'case':family+'_actual_selection','old_current_source':before,'repaired_current_source':after})

# Actual service request/accept helpers: unchanged prices and native budget AST.
for kind,fee in ((1,3),(2,4)):
    candidate();s=state();effect(s,'eon_services_send_offer',temporary={'eon_services_requested_kind':kind},from_from='B')
    assert 'eon_services_pending' in s['countries']['A']['flags']
    assert check(s,'eon_services_response_ready',temporary={'eon_services_requested_kind':kind})
    effect(s,'eon_services_accept_offer',actor='B',peer='A',temporary={'eon_services_requested_kind':kind})
    assert wallet(s)=={'A':100+fee,'B':100-fee,'C':100,'D':100},wallet(s)
    first=wallet(s);effect(s,'eon_services_accept_offer',actor='B',peer='A',temporary={'eon_services_requested_kind':kind})
    assert wallet(s)==first
    # Leave admission predicates corrected, isolate the original fee operand.
    s=state();effect(s,'eon_services_send_offer',temporary={'eon_services_requested_kind':kind},from_from='B')
    new=deepcopy(m.model['effects']['eon_services_accept_offer'])
    m.model['effects']['eon_services_accept_offer']=original_effects['eon_services_accept_offer']
    effect(s,'eon_services_accept_offer',actor='B',peer='A',temporary={'eon_services_requested_kind':kind})
    assert wallet(s)=={'A':100,'B':100-fee,'C':100,'D':100},wallet(s)
    m.model['effects']['eon_services_accept_offer']=new
    cases.append({'case':'service_fee_'+str(fee)+'_actual_cash_primitive','old_fee_operand_cash':wallet(s),
                  'repaired_current_source_cash':first,'old_money_lost':fee})

candidate();s=state();s['countries']['B']['ideas'].add('military_services_logistics_idea')
assert not check(s,'eon_services_selection_ready',actor='A',peer='B',from_from='B',temporary={'eon_services_requested_kind':1})
new=deepcopy(m.model['capacity_triggers']['eon_services_selection_ready'])
def old_kind_branch(nodes):
    result=[]
    for k,o,v in nodes:
        if k=='if' and m.one(v,'limit')==[('check_variable','=',[('eon_services_requested_kind','=','1')])]:
            v=[('limit','=',[('check_variable','=',[('PREV.eon_services_requested_kind','=','1')])])]+[n for n in v if n[0]!='limit']
        elif isinstance(v,list):v=old_kind_branch(v)
        result.append((k,o,v))
    return result
m.model['capacity_triggers']['eon_services_selection_ready']=old_kind_branch(new)
assert check(s,'eon_services_selection_ready',actor='A',peer='B',from_from='B',temporary={'eon_services_requested_kind':1})
m.model['capacity_triggers']['eon_services_selection_ready']=new
cases.append({'case':'service_requested_kind_selection_duplicate_guard','old_kind_operand_allows_duplicate':True,'candidate_rejects_duplicate':True})

candidate();s=state();effect(s,'eon_services_send_offer',temporary={'eon_services_requested_kind':1},from_from='B')
assert check(s,'eon_services_response_kind_matches',temporary={'eon_services_requested_kind':1})
new=deepcopy(m.model['capacity_triggers']['eon_services_response_kind_matches'])
m.model['capacity_triggers']['eon_services_response_kind_matches']=original_triggers['eon_services_response_kind_matches']
assert not check(s,'eon_services_response_kind_matches',temporary={'eon_services_requested_kind':1})
m.model['capacity_triggers']['eon_services_response_kind_matches']=new
cases.append({'case':'service_response_kind','old_current_source':False,'repaired_current_source':True})

candidate();s=state();s['countries']['A']['variables']['treasury']=999998
effect(s,'eon_services_send_offer',temporary={'eon_services_requested_kind':1},from_from='B')
assert not check(s,'eon_services_response_ready',temporary={'eon_services_requested_kind':1})
new=deepcopy(m.model['capacity_triggers']['eon_services_response_ready'])
def old_fee_headroom(nodes):
    result=[]
    for k,o,v in nodes:
        if k=='add_to_temp_variable' and v==[('eon_services_projected_treasury','=','eon_services_fee')]:
            v=[('eon_services_projected_treasury','=','PREV.eon_services_fee')]
        elif isinstance(v,list):v=old_fee_headroom(v)
        result.append((k,o,v))
    return result
m.model['capacity_triggers']['eon_services_response_ready']=old_fee_headroom(new)
assert check(s,'eon_services_response_ready',temporary={'eon_services_requested_kind':1})
m.model['capacity_triggers']['eon_services_response_ready']=new
cases.append({'case':'service_provider_receipt_headroom','old_fee_operand_allows_overflow':True,'candidate_rejects_overflow':True})

for family in ('foreign_cash','foreign_equipment','defence_formation'):
    candidate();s=state()
    effect(s,f'eon_{family}_send_offer')
    assert f'eon_{family}_pending' in s['countries']['A']['flags']
    effect(s,f'eon_{family}_accept_offer',actor='B',peer='A')
    assert f'eon_{family}_consented' in s['countries']['A']['flags']
    key=f'eon_{family}_commit_ready'
    assert check(s,key,actor='A',peer='B')
    new=deepcopy(m.model['capacity_triggers'][key])
    m.model['capacity_triggers'][key]=original_triggers[key]
    assert not check(s,key,actor='A',peer='B')
    m.model['capacity_triggers'][key]=new
    effect(s,f'eon_{family}_commit_offer')
    assert f'eon_{family}_pending' not in s['countries']['A']['flags']
    first_cash=wallet(s);first_observers=deepcopy(s.get('native_equipment_calls',[])+s.get('native_formation_calls',[]))
    effect(s,f'eon_{family}_commit_offer')
    assert wallet(s)==first_cash and s.get('native_equipment_calls',[])+s.get('native_formation_calls',[])==first_observers
    if family=='foreign_cash':assert first_cash=={'A':93,'B':107,'C':100,'D':100},first_cash
    else:assert first_observers,('No observed native asset calls',family)
    cases.append({'case':family+'_actual_send_consent_commit_frame','old_commit_ready':False,'repaired_current_source_ready':True,
                  'candidate_cash':first_cash,'native_asset_calls_observed':len(first_observers),
                  'native_asset_transfer_proven':False,'repeated_commit_is_inert':True})

originals();s=m.state();m.complete(s)
assert 'eon_support_request_pending' not in s['countries']['A']['flags']
candidate();s=m.state();m.complete(s)
assert 'eon_support_request_pending' in s['countries']['A']['flags']
assert s['countries']['A']['variables']['eon_support_request_partner']=='B'
cases.append({'case':'support_request_actual_native_action_backend','old_current_source_request_created':False,
              'repaired_current_source_exact_pair_created':True,'native_UI_click_or_cost_proven':False})

def adviser_pair():
    s=state()
    for actor,direction,peer in (('A','outgoing','B'),('B','incoming','A')):
        s['countries'][actor]['flags'].update({f'eon_advisers_{direction}_owned',f'eon_advisers_{direction}_live'})
        s['countries'][actor]['variables'][f'eon_advisers_{direction}_partner']=peer
    s['countries']['B']['ideas'].add('eon_advisers_mission_idea')
    return s
for direction,actor,peer in (('incoming','B','A'),('outgoing','A','B')):
    originals();s=adviser_pair();before=check(s,f'eon_advisers_{direction}_pair_matches',actor=actor,peer=peer)
    candidate();after=check(s,f'eon_advisers_{direction}_pair_matches',actor=actor,peer=peer)
    assert not before and after
    cases.append({'case':f'advisers_{direction}_reciprocal_owned_pair','old_current_source':before,'repaired_current_source':after})
    originals();s=adviser_pair();effect(s,f'eon_advisers_clear_{direction}',actor=actor,peer=peer)
    opposite='outgoing' if direction=='incoming' else 'incoming'
    assert f'eon_advisers_{opposite}_owned' in s['countries'][peer]['flags']
    old={c:sorted(x for x in d['flags'] if x.startswith('eon_advisers_')) for c,d in s['countries'].items()}
    candidate();s=adviser_pair();effect(s,f'eon_advisers_clear_{direction}',actor=actor,peer=peer)
    assert not any(x.startswith('eon_advisers_') for d in s['countries'].values() for x in d['flags'])
    cases.append({'case':f'advisers_clear_{direction}_both_exact_parties','old_dangling_owned_flags':old,'repaired_current_source_removes_both':True})

# Financing records are independent of the still-unmodeled building callback.
# Extract exact existing contribution island AST; no replacement build algorithm.
investment=investment_model()
raw=(ROOT/'common/scripted_effects/eon_investment_project_effects.txt').read_bytes()
game=investment.ast(raw.decode('utf-8-sig'));complete=investment.one(game,'eon_investment_lifecycle_complete_unit')
def find(nodes,key):
    found=[]
    for k,o,v in nodes:
        if k==key:found.append((k,o,v))
        if isinstance(v,list):found.extend(find(v,key))
    return found
islands=find(complete,'var:eon_project_cofinancer^project');assert len(islands)==2
for result_code,island in ((1,islands[0]),(-1,islands[1])):
    def finance(candidate_operand):
        s=investment.state();s['entities'][1]['variables']['eon_project_cofinancer^0']=2
        s['entities'][2]['variables'].update(eon_construction_contributions=6,eon_investment_contribution_spent=0,eon_investment_contribution_losses=0)
        s['temp']={'project':0,'eon_project_spent_contribution':3}
        body=[island]
        if not candidate_operand:body=rhs(body,'eon_project_spent_contribution','PREV.eon_project_spent_contribution')
        investment.execute(body,s,investment.context(1))
        return {k:s['entities'][2]['variables'][k] for k in ('eon_construction_contributions','eon_investment_contribution_spent','eon_investment_contribution_losses')}
    old,new=finance(False),finance(True)
    if result_code==1:assert old=={'eon_construction_contributions':6,'eon_investment_contribution_spent':0,'eon_investment_contribution_losses':0} and new=={'eon_construction_contributions':3,'eon_investment_contribution_spent':3,'eon_investment_contribution_losses':0}
    else:assert old['eon_investment_contribution_losses']==0 and new['eon_investment_contribution_losses']==3
    cases.append({'case':'investment_exact_contribution_'+('spend' if result_code==1 else 'loss')+'_island','old_current_source':old,'repaired_current_source':new,'full_build_callback_proven':False})


# Exact current-source and test ownership guards reject bounded byte mutations.
boundary_cases=[]
candidate();s=state()
effect(s,'eon_foreign_equipment_send_offer')
effect(s,'eon_foreign_equipment_accept_offer',actor='B',peer='A')
assert check(s,'eon_foreign_equipment_commit_ready',actor='A',peer='B')
equipment_path='common/scripted_effects/eon_foreign_equipment_effects.txt'
old_equipment={key:val for key,op,val in m.model['ast'](game_before(equipment_path,(ROOT/equipment_path).read_bytes()).decode('utf-8-sig'))}
current_commit=deepcopy(m.model['effects']['eon_foreign_equipment_commit_offer'])
m.model['effects']['eon_foreign_equipment_commit_offer']=old_equipment['eon_foreign_equipment_commit_offer']
try:
    try:effect(s,'eon_foreign_equipment_commit_offer')
    except AssertionError as exc:assert 'equipment' in str(exc)
    else:raise AssertionError('Old equipment= effect silently accepted by current native-call observer')
finally:m.model['effects']['eon_foreign_equipment_commit_offer']=current_commit
cases.append({'case':'documented_type_field_on_actual_equipment_commit',
    'old_equipment_field_rejected_by_strict_observer':True,'current_native_calls_use_type':True,
    'native_stock_debit_delivery_proven':False})
for group,projection in (('support_reads',game_before),('equipment_field',game_before),('registry',game_before),('test_adapters',test_before)):
    for path,entry in JOURNAL[group].items():
        raw=(ROOT/path).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==entry['after_sha256']
        before=projection(path,raw)
        assert hashlib.sha256(before).hexdigest()==entry['before_sha256']
        for mutation in (raw+b'# unowned memory suffix\n',raw.replace(b'=',b'!',1)):
            assert mutation!=raw
            try:projection(path,mutation)
            except AssertionError:pass
            else:raise AssertionError(('Unowned byte mutation accepted',group,path))
            boundary_cases.append(group+':'+path)

# Dynamic VARIABLE suffixes retain native country aliases; country FLAGS do not.
candidate();s=state();ctx=m.model['switch'](m.model['context']('A'),'B')
s['temp']={'probe':11,'alias':'A'}
s['countries']['A']['variables']['probe']=99
s['countries']['B']['variables'].update({'stored_alias':'A','amount@A':7})
assert m.model['value'](s,ctx,'probe')==11 and m.model['value'](s,ctx,'PREV.probe')==99
assert m.model['value'](s,ctx,'amount@A')==m.model['value'](s,ctx,'amount@stored_alias')==m.model['value'](s,ctx,'amount@PREV')==7
assert m.model['flag_name'](s,ctx,'key@PREV')=='key@A'
assert all(m.model['flag_name'](s,ctx,'key@'+key)!='key@A' for key in ('A','alias','stored_alias'))
try:m.execute(m.model['ast']('set_temp_variable = { PREV.unverified = 1 }'),s,ctx)
except AssertionError as exc:assert 'Uncalibrated qualified temporary write' in str(exc)
else:raise AssertionError('Qualified temporary writer silently assumed')
boundary_cases.append('native10/29 shared read / persistent read / VARIABLE alias / FLAG distinction / uncalibrated writer boundary')

# Calibrated semantic assertions must reject the two former adapter behaviors.
for bad in (
    lambda result, frame, token: 0 if token == 'probe' and frame['scope'] == 'B' else m.model['value'](result,frame,token),
    lambda result, frame, token: result['temp'].get(token.split('.',1)[1],0) if token == 'PREV.probe' else m.model['value'](result,frame,token),
):
    assert not (bad(s,ctx,'probe') == 11 and bad(s,ctx,'PREV.probe') == 99)
    boundary_cases.append('memory-only old country-local or scoped-temp read adapter rejected')
bad_flag=lambda result,frame,name: name.split('@',1)[0]+'@'+str(m.model['country_ref'](result,frame,name.split('@',1)[1]))
assert bad_flag(s,ctx,'key@stored_alias') == 'key@A'
assert bad_flag(s,ctx,'key@stored_alias') != m.model['flag_name'](s,ctx,'key@stored_alias')
boundary_cases.append('memory-only old scalar FLAG selector adapter rejected')

# Four generic relation receipt sites remain explicit and distinct from national
# literal-peer wrappers. This is source evidence, not a native save-load claim.
raw=(ROOT/'common/scripted_effects/eon_diplomatic_relations_effects.txt').read_bytes()
import re
opinion=re.compile(rb'\b(?P<kind>add_opinion_modifier|remove_opinion_modifier)\s*=\s*\{(?P<body>[^{}]*)\}')
generic_receipts=0
for match in opinion.finditer(raw):
    if not re.search(rb'\bmodifier\s*=\s*no_diplomatic_ties\b',match['body']):continue
    assert re.search(rb'\btarget\s*=\s*PREV\b',match['body'])
    command=b'clr_country_flag' if match['kind']==b'remove_opinion_modifier' else b'set_country_flag'
    exact=b' set_country_flag = eon_diplomatic_relations_legacy_known@PREV '+command+b' = eon_diplomatic_relations_legacy_no_ties@PREV'
    assert raw[match.end():].startswith(exact)
    generic_receipts+=1
assert generic_receipts==4
print(json.dumps({'all_passed':True,'actual_ast_old_new_regressions':len(cases),'cases':cases,
    'strict_byte_and_adapter_boundary_cases':len(boundary_cases),'generic_receipt_sites':generic_receipts,
    'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in plan['files']},
    'equipment_field_source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in JOURNAL['equipment_field']},
    'test_adapter_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in JOURNAL['test_adapters']},
    'scope':'Current actual AST versus exact preserved old READ operands; native10/29-calibrated scalar reads/flags',
    'not_proven':['Native aid shipment/equipment delivery/resource debit/formation creation/adviser personnel',
        'Sixteen qualified state TEMP WRITEs (default model refuses; contribution islands avoid them)',
        'Full project building callback, campaign/save-load/multiplayer']},indent=2))
