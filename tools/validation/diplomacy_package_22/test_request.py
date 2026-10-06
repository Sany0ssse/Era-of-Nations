"""Ordered initial support-request source checks; native cost and asset completion remain unmodeled."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
import hashlib
import json
import contextlib
import io
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '0747ce626b79bc7796d6fbb61be9cbf8a6076de0'
groups = Counter()
adapter_cases = Counter()
def historical_script_manifest():
    paths=subprocess.check_output(['git','ls-tree','-r','--name-only',BASELINE,'--','tools/validation'],cwd=ROOT).decode().splitlines()
    protected={path for path in paths if path.endswith('.py') and Path(path).name!='test_source.py'}
    assert len(protected)==53,'Prior protected script inventory changed'
    return protected

def historical_caller_run(relative_path):
    """Explicitly run retained suites; only three prior behaviors use the named historical AB4 caller view."""
    original_read_text,original_run=Path.read_text,subprocess.run
    original_path_object,original_argv_object=sys.path,sys.argv
    original_path,original_argv=sys.path[:],sys.argv[:]
    current_models_loaded=any(name in globals() for name in ('model','source','executor_path'))
    projection=None;read_count=0
    output=io.StringIO()
    try:
        target=Path(relative_path)
        assert not target.is_absolute() and '..' not in target.parts,'Historical script must be a relative owned path'
        relative_path=target.as_posix()
        sys.path.insert(0,str(ROOT/'tools/validation'))
        import diplomacy_package_22.test_source as byte_views
        behavior_paths=historical_script_manifest()
        source_paths={f'tools/validation/diplomacy_package_{index:02}/test_source.py' for index in range(2,22)}
        pristine_source_paths={'tools/validation/diplomacy_package_01/test_source.py'}
        assert relative_path in behavior_paths|source_paths|pristine_source_paths,('Unapproved historical subprocess script',relative_path)
        original=subprocess.check_output(['git','show',BASELINE+':'+relative_path],cwd=ROOT)
        current=(ROOT/relative_path).read_bytes()
        if relative_path in behavior_paths|pristine_source_paths:assert current==original,('Protected historical script bytes changed',relative_path)
        else:assert byte_views.package22_original_validator_bytes(relative_path,current)==original
        projected_targets={f'tools/validation/diplomacy_package_{index:02}/'+name for index,name in ((18,'test_foreign_cash.py'),(19,'test_equipment.py'),(20,'test_formation.py'))}
        if relative_path in projected_targets:
            actual=(ROOT/'events/00_War_events.txt').read_bytes()
            projected,projection=byte_views.historical_caller_view(actual)
            assert projection['projected_options_sha256'].keys()=={'AB_mobilization.4.a','AB_mobilization.4.b','AB_mobilization.4.c'}
            def historical_read_text(path,*args,**kwargs):
                nonlocal read_count
                if path.resolve()==(ROOT/'events/00_War_events.txt').resolve():
                    assert not args and kwargs=={'encoding':'utf-8-sig'},'Unexpected historical caller reader parameters'
                    fresh=path.read_bytes();view,manifest=byte_views.historical_caller_view(fresh)
                    assert fresh==actual and view==projected and manifest==projection,'Gameplay bytes drifted during historical caller execution'
                    read_count+=1
                    return view.decode('utf-8-sig')
                return original_read_text(path,*args,**kwargs)
            Path.read_text=historical_read_text
        def historical_subprocess(command,*args,**kwargs):
            if isinstance(command,(tuple,list)) and command and str(command[0])==sys.executable:
                script_arguments=[str(arg) for arg in command[1:] if not str(arg).startswith('-')]
                assert len(script_arguments)==1,'Unapproved historical Python arguments'
                script_path=Path(script_arguments[0]).resolve()
                assert script_path.is_relative_to(ROOT.resolve()),'Historical Python script outside checkout'
                nested=script_path.relative_to(ROOT.resolve()).as_posix()
                assert nested in behavior_paths|source_paths|pristine_source_paths,('Unapproved nested historical script',nested)
                command=[sys.executable,'-B',str(Path(__file__).resolve()),'--historical-caller',nested]
            return original_run(command,*args,**kwargs)
        subprocess.run=historical_subprocess
        # A regular Python script places its own directory first for local helper imports.
        sys.path.insert(0,str((ROOT/relative_path).parent))
        sys.argv=[str(ROOT/relative_path)]
        with contextlib.redirect_stdout(output):runpy.run_path(str(ROOT/relative_path),run_name='__main__')
    finally:
        Path.read_text=original_read_text;subprocess.run=original_run
        original_path_object[:]=original_path;sys.path=original_path_object
        original_argv_object[:]=original_argv;sys.argv=original_argv_object
    result=json.loads(output.getvalue())
    result['historical_bootstrap_current_models_loaded']=current_models_loaded
    if relative_path in projected_targets:
        assert read_count>0,'Historical entry projection was not consumed'
        result['historical_caller_projection']=projection|{'script':relative_path,'projected_read_count':read_count,
            'script_sha256':hashlib.sha256(current).hexdigest(),'source_sha256_scope':'actual_current_files; execution of only three AB4 callers uses the declared historical option view'}
    if Path(relative_path).name=='run_checks.py':
        result['prior_scope']='unchanged_children_with_historical_AB4_caller_view'
        result['historical_projection_baseline']=BASELINE
        result['prior_counters_prove_current_initial_request_ownership']=False
    return result

if __name__=='__main__' and len(sys.argv)>1 and sys.argv[1]=='--historical-caller':
    assert len(sys.argv)==3,'Use --historical-caller with one whitelisted script path'
    assert not any(name in globals() for name in ('model','source','executor_path')),'Historical bootstrap loaded current models'
    print(json.dumps(historical_caller_run(sys.argv[2]),indent=2))
    raise SystemExit(0)

executor_path = ROOT/'tools/validation/diplomacy_package_21/test_advisers.py'
executor_text = executor_path.read_text(encoding='utf-8')
boundary = '\ndef focus(name):'
assert executor_text.count(boundary) == 1, 'Ordered definition boundary changed'
source = {'__file__':str(executor_path),'__name__':'request_ordered_executor'}
exec(compile(executor_text.split(boundary)[0],str(executor_path),'exec'),source)
model = source['model']
read,option,effect,check,one = (source[name] for name in ('read','option','effect','check','one'))
source_trigger,source_state,source_execute = source['source_trigger'],source['state'],source['execute']
PREFIX = 'eon_support_request_'
NAMESPACES = (source,*source['NAMESPACES'])
stock_types = set(source['source']['EQUIPMENT']) | set(source['source']['source']['PACKETS'])

def trigger(nodes,result,ctx):
    index = 0
    while index < len(nodes):
        key,operator,val = nodes[index]; index += 1
        grouped = [(key,operator,val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if','else'):
                grouped.append(nodes[index]); index += 1
        if key == 'has_equipment':
            assert isinstance(val,list) and len(val) == 1, 'One explicit stored-equipment query required'
            archetype,comparison,wanted = val[0]
            assert archetype in stock_types, ('Unsupported stock fixture type',archetype)
            stored = result['countries'][ctx['scope']]['equipment_stock'][archetype]
            assert isinstance(stored,int) and not isinstance(stored,bool) and stored >= 0
            ready = model['compare'](stored,comparison,model['value'](result,ctx,wanted))
        else: ready = source_trigger(grouped,result,ctx)
        if not ready: return False
    return True

def execute(nodes,result,ctx):
    index = 0
    while index < len(nodes):
        key,operator,val = nodes[index]; index += 1
        grouped = [(key,operator,val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if','else'):
                grouped.append(nodes[index]); index += 1
        if key in ('eon_defence_formation_send_offer','eon_foreign_equipment_send_offer','eon_foreign_cash_send_offer'):
            provider = result['countries'][ctx['scope']]
            result.setdefault('initial_handoff_calls',[]).append({'effect':key,'root':ctx['root'],'from':ctx['from'],
                'scope':ctx['scope'],'initial_pending_at_call':PREFIX+'pending' in provider['flags'],
                'initial_partner_at_call':provider['variables'].get(PREFIX+'partner',0)})
        if key == 'country_event':
            result.setdefault('initial_event_calls',[]).append({'root':ctx['root'],'from':ctx['from'],'scope':ctx['scope'],
                'parameters':deepcopy(val)})
        source_execute(grouped,result,ctx)

for namespace in NAMESPACES:
    namespace['trigger'] = trigger; namespace['execute'] = execute
for registry,path in (('effects','common/scripted_effects/eon_support_request_effects.txt'),
                      ('capacity_triggers','common/scripted_triggers/eon_support_request_triggers.txt')):
    if (ROOT/path).exists():
        additions = {key:body for key,op,body in model['ast'](read(path))}
        assert not additions.keys() & model[registry].keys(), 'Request helpers overwrite earlier IDs'
        model[registry].update(additions)

def state(resources=True):
    result = source_state(resources=resources)
    for country in result['countries'].values():
        country['flags'] = {flag for flag in country['flags'] if not flag.startswith('aid_request_cd_@')}
        country['civil_war'] = False
        for archetype in stock_types:
            maximum=max(source['source']['EQUIPMENT'].get(archetype,0),source['source']['source']['PACKETS'].get(archetype,0))
            country['equipment_stock'][archetype]=maximum*(3 if resources else 0)
    result['countries']['A']['ideas'] = {'large_power'}
    result['countries']['B']['ideas'] = {'minor_power'}
    return result

def action_body():
    path = 'common/scripted_diplomatic_actions/MDDC_AB_ask_foreign_support.txt'
    return one(one(model['ast'](read(path)),'scripted_diplomatic_actions'),'AB_ask_foreign_support')
def complete(result,requester='B',provider='A'):
    # Native sample documents ROOT sender / THIS receiver. FROM is an explicit legacy fixture.
    effect(result,one(action_body(),'complete_effect'),actor=requester,from_=provider,scope=provider)
def queued(result,identity): return [item for item in result['events'] if item['id'] == identity]
def menu(result,suffix,provider='A',requester='B'):
    events = model['get_event_map'](read('events/00_War_events.txt'))
    effect(result,option(events,'AB_mobilization.4','AB_mobilization.4.'+suffix),actor=provider,from_=requester)
def child_offers(result):
    identities = {'eon_defence_formation.1','eon_foreign_equipment.1','eon_foreign_cash.1'}
    return [item for item in result['events'] if item['id'] in identities]

def focus(name):
    if name == 'request_replay':
        result = state(); complete(result); first = deepcopy(queued(result,'AB_mobilization.4'))
        assert len(first) == 1, ('Fresh request must queue exactly one provider menu',first)
        complete(result)
        assert queued(result,'AB_mobilization.4') == first, ('Replayed completion creates a second request menu',result['events'])
        groups['native_completion_replay_cannot_duplicate_owned_initial_request'] += 1
    elif name == 'late_policy_loss':
        result = state(); result['countries']['B']['defensive_war'] = False
        complete(result)
        assert not queued(result,'AB_mobilization.4'), ('Late loss of the defensive-war condition still queues a request',result['events'])
        groups['late_defensive_war_loss_blocks_initial_completion'] += 1
    elif name == 'cooldown_bypass':
        result = state(); result['countries']['A']['flags'].add('aid_request_cd_@B')
        complete(result)
        assert not queued(result,'AB_mobilization.4'), ('A current pair cooldown is bypassed by the completion callback',result['events'])
        groups['fresh_pair_cooldown_blocks_initial_completion'] += 1
    elif name == 'unowned_decline':
        result = state(); menu(result,'d'); menu(result,'d')
        assert not queued(result,'AB_mobilization.8'), ('Unowned decline callbacks issue provider refusals',result['events'])
        groups['unowned_provider_decline_cannot_notify_requester'] += 1
    elif name == 'unowned_menu':
        result = state(); result['countries']['A']['flags'].add('aid_request_cd_@B')
        for suffix in ('a','b','c'): menu(result,suffix)
        assert not child_offers(result), ('A nominal annual cooldown alone authorizes unrelated menu handoffs',child_offers(result))
        groups['nominal_cooldown_without_owned_initial_request_cannot_handoff'] += 1
    elif name == 'multi_kind_handoff':
        result = state(); complete(result); menu(result,'a'); first = deepcopy(child_offers(result))
        assert len(first) == 1 and first[0]['id'] == 'eon_defence_formation.1', ('Valid initial request must hand off one selected form',first)
        menu(result,'b'); menu(result,'c'); menu(result,'a')
        assert child_offers(result) == first, ('Consumed initial request hands off multiple support forms',child_offers(result))
        groups['owned_initial_request_is_consumed_before_one_child_handoff'] += 1
    else: raise AssertionError(('Unknown focus',name))

FOCUSES = ('request_replay','late_policy_loss','cooldown_bypass','unowned_decline','unowned_menu','multi_kind_handoff')
def flags(result,actor='A'): return result['countries'][actor]['flags']
def variables(result,actor='A'): return result['countries'][actor]['variables']
def pending(result,actor='A'): return PREFIX+'pending' in flags(result,actor)
def request_fields(result,actor='A'):
    return {'flags':{flag for flag in flags(result,actor) if flag.startswith(PREFIX)},
            'partner':variables(result,actor).get(PREFIX+'partner',0)}
def money(result): return {actor:{key:country['variables'][key] for key in ('treasury','political_power')} for actor,country in result['countries'].items()}
def assets(result): return {actor:{key:deepcopy(country[key]) for key in ('equipment_stock','available_manpower','templates','native_unit_inventory')} for actor,country in result['countries'].items()}
def snapshot(result): return {key:deepcopy(val) for key,val in result.items() if key not in ('temp','scope_temps','observed_tooltips')}
def child_state(result):
    return {actor:{'flags':{flag for flag in country['flags'] if flag.startswith(('eon_foreign_cash_','eon_foreign_equipment_','eon_defence_formation_','eon_services_','eon_advisers_'))},
        'variables':{key:deepcopy(value) for key,value in country['variables'].items() if key.startswith(('eon_foreign_cash_','eon_foreign_equipment_','eon_defence_formation_','eon_services_','eon_advisers_'))},
        'ideas':deepcopy(country['ideas'])} for actor,country in result['countries'].items()}
def selectable(result,requester='B',provider='A'):
    body=action_body()
    return all(check(result,one(body,key),actor=requester,from_=None,scope=provider) for key in ('allowed','visible','selectable','can_be_sent'))
def menu_ready(result,suffix,provider='A',requester='B'):
    body=option(model['get_event_map'](read('events/00_War_events.txt')),'AB_mobilization.4','AB_mobilization.4.'+suffix)
    return check(result,one(body,'trigger'),actor=provider,from_=requester)
def withdraw(result,requester='B',provider='A',force=False):
    body=one(one(model['ast'](read('common/scripted_diplomatic_actions/eon_support_request_actions.txt')),'scripted_diplomatic_actions'),PREFIX+'withdraw_request')
    ready=all(check(result,one(body,key),actor=requester,from_=None,scope=provider) for key in ('allowed','visible','selectable','can_be_sent'))
    if ready or force: effect(result,one(body,'complete_effect'),actor=requester,from_=None,scope=provider)
    return ready
def native_hook(result,name,actor='A',from_='B'):
    hooks=one(model['ast'](read('common/on_actions/eon_support_request_on_actions.txt')),'on_actions')
    effect(result,one(one(hooks,name),'effect'),actor=actor,from_=from_)
def daily(result):
    for actor,country in result['countries'].items():
        if country['exists']: native_hook(result,'on_daily',actor,None)
def alteration(result,name,provider='A',requester='B'):
    donor,client=result['countries'][provider],result['countries'][requester]
    if name=='peace':client['defensive_war']=False
    elif name=='requester_rank':client['ideas'].clear()
    elif name=='provider_rank':donor['ideas'].clear()
    elif name=='opinion':donor['opinions'][requester]=49
    elif name=='provider_dead':donor['exists']=False
    elif name=='requester_dead':client['exists']=False
    elif name=='direct_war':donor['wars'].add(requester);client['wars'].add(provider)
    elif name=='cooldown':donor['flags'].add('aid_request_cd_@'+requester)
    else:raise AssertionError(name)
def setup_pair(result,provider='A',requester='B'):
    result['countries'][provider]['ideas']={'large_power'}
    result['countries'][requester]['ideas']={'minor_power'}
    result['countries'][requester]['defensive_war']=True
    result['countries'][provider]['opinions'][requester]=60
def initialise(result,requester='B',provider='A'):
    assert selectable(result,requester,provider)
    complete(result,requester,provider)
    assert pending(result,provider) and variables(result,provider)[PREFIX+'partner']==requester
def handoff(result,suffix,provider='A',requester='B'):
    assert menu_ready(result,suffix,provider,requester)
    prior=len(child_offers(result));menu(result,suffix,provider,requester)
    assert len(child_offers(result))==prior+1 and not pending(result,provider)
    observed=result['initial_handoff_calls'][-1]
    assert observed['root']==provider and observed['from']==requester and observed['scope']==provider
    assert observed['initial_pending_at_call'] is False and observed['initial_partner_at_call']==0
def child_reply(result,suffix,provider='A',requester='B',accepted=True):
    prefix={'a':'eon_defence_formation','b':'eon_foreign_equipment','c':'eon_foreign_cash'}[suffix]
    events=model['get_event_map'](read('events/'+prefix+'_events.txt'))
    choice=option(events,prefix+'.1',prefix+'.1.'+('a' if accepted else 'b'))
    assert check(result,one(choice,'trigger'),actor=requester,from_=provider)
    effect(result,choice,actor=requester,from_=provider)
def child_commit(result,suffix,provider='A',requester='B'):
    prefix={'a':'eon_defence_formation','b':'eon_foreign_equipment','c':'eon_foreign_cash'}[suffix]
    events=model['get_event_map'](read('events/'+prefix+'_events.txt'))
    effect(result,one(events[prefix+'.2'],'immediate'),actor=provider,from_=requester)

def lifecycle():
    for name in FOCUSES:focus(name)
    for suffix in ('a','b','c'):
        result=state();before=money(result),assets(result)
        initialise(result);handoff(result,suffix)
        assert (money(result),assets(result))==before
        assert not result.get('native_formation_calls') and not result.get('native_equipment_calls')
        assert 'aid_request_cd_@B' in flags(result)
        child_reply(result,suffix);before_commit=money(result),assets(result)
        assert (money(result),assets(result))==before_commit==before
        assert len(queued(result,{'a':'eon_defence_formation.2','b':'eon_foreign_equipment.2','c':'eon_foreign_cash.2'}[suffix]))==1
        child_commit(result,suffix);after=snapshot(result);child_commit(result,suffix)
        assert snapshot(result)==after and request_fields(result)=={'flags':set(),'partner':0}
        assert assets(result)==before[1], 'Opaque native observers cannot fabricate delivered assets'
        if suffix=='c':assert variables(result)['treasury']==before[0]['A']['treasury']-7 and variables(result,'B')['treasury']==before[0]['B']['treasury']+7
        elif suffix=='a':assert len(result.get('native_formation_calls',[]))==8
        else:assert len(result.get('native_equipment_calls',[]))==9
        groups['actual_request_handoff_child_consent_and_replay_safe_commit_three_existing_forms']+=1
    for suffix in ('a','b','c'):
        result=state();initialise(result);handoff(result,suffix);child_reply(result,suffix,accepted=False)
        assert request_fields(result)=={'flags':set(),'partner':0} and not result.get('native_formation_calls') and not result.get('native_equipment_calls')
        groups['each_child_decline_keeps_initial_consumption_without_resources']+=1
    for name in ('peace','requester_rank','provider_rank','opinion','provider_dead','requester_dead','direct_war','cooldown'):
        result=state();alteration(result,name);assert not selectable(result);complete(result)
        assert not pending(result) and not queued(result,'AB_mobilization.4')
        groups['fresh_native_admission_and_completion_recheck_each_current_policy']+=1
    for suffix in ('a','b','c'):
        for name in ('peace','requester_rank','provider_rank','opinion','provider_dead','requester_dead','direct_war'):
            result=state();initialise(result);alteration(result,name);before=child_state(result),money(result),assets(result)
            assert not menu_ready(result,suffix);menu(result,suffix)
            assert not child_offers(result) and pending(result) and (child_state(result),money(result),assets(result))==before
            menu(result,'d');assert not pending(result) and not queued(result,'AB_mobilization.8')
            groups['late_menu_policy_loss_blocks_all_forms_and_allows_unpenalised_close']+=1
    for suffix in ('a','b','c'):
        result=state(resources=False)
        if suffix=='c':variables(result)['treasury']=6.99
        initialise(result);assert not menu_ready(result,suffix);menu(result,suffix)
        assert pending(result) and not child_offers(result)
        groups['unchanged_selected_child_resource_readiness_precedes_initial_consumption']+=1
    result=state();initialise(result);before=money(result),assets(result);menu(result,'d');assert len(queued(result,'AB_mobilization.8'))==1
    after=snapshot(result);menu(result,'d');assert snapshot(result)==after and (money(result),assets(result))==before
    groups['owned_valid_decline_consumes_before_exactly_one_inherited_refusal_notice']+=1
    for partner in ('C','D',None):
        result=state();initialise(result);before=request_fields(result)
        for suffix in ('a','b','c','d'):menu(result,suffix,requester=partner)
        assert request_fields(result)==before and not child_offers(result) and not queued(result,'AB_mobilization.8')
        assert not withdraw(result,requester=partner,force=True)
        assert request_fields(result)==before
        groups['wrong_or_missing_requester_cannot_handoff_decline_or_withdraw_owned_pair']+=1
    result=state();setup_pair(result,'D','B');initialise(result);initialise(result,provider='D')
    assert pending(result,'A') and pending(result,'D') and len(queued(result,'AB_mobilization.4'))==2
    handoff(result,'c');assert pending(result,'D');menu(result,'d',provider='D')
    assert not pending(result,'D') and len(child_offers(result))==1
    groups['one_requester_can_ask_two_distinct_providers_without_cross_consumption']+=1
    result=state();setup_pair(result,'A','C');initialise(result);before=request_fields(result)
    assert not selectable(result,'C');complete(result,'C');assert request_fields(result)==before and len(queued(result,'AB_mobilization.4'))==1
    handoff(result,'c');assert selectable(result,'C');complete(result,'C');assert pending(result)
    groups['provider_single_initial_slot_blocks_second_requester_then_reopens_after_handoff']+=1
    result=state();initialise(result);before=money(result),assets(result);assert withdraw(result)
    assert pending(result) and PREFIX+'cancelled' in flags(result) and variables(result)[PREFIX+'partner']=='B'
    assert not withdraw(result,force=True);assert len(queued(result,'eon_support_request.1'))==1
    for suffix in ('a','b','c'):assert not menu_ready(result,suffix);menu(result,suffix)
    assert not child_offers(result);daily(result);assert pending(result)
    menu(result,'d');assert not pending(result) and not queued(result,'AB_mobilization.8') and (money(result),assets(result))==before
    assert 'aid_request_cd_@B' in flags(result)
    groups['free_withdrawal_retains_exact_pair_until_safe_close_without_refund_or_child_handoff']+=1
    for name in ('expiry','peace','direct_war','provider_dead','requester_dead'):
        result=state();initialise(result);before=child_state(result),money(result),assets(result)
        if name=='expiry':flags(result).remove(PREFIX+'live')
        else:alteration(result,name)
        if name=='provider_dead':native_hook(result,'on_daily','A',None)
        else:daily(result)
        assert request_fields(result)=={'flags':set(),'partner':0} and (child_state(result),money(result),assets(result))==before,(name,request_fields(result))
        assert 'aid_request_cd_@B' in flags(result)
        groups['expiry_unavailability_and_conflict_cleanup_only_initial_owned_fields']+=1
    for name in ('requester_rank','provider_rank','opinion'):
        result=state();initialise(result);alteration(result,name);before=request_fields(result);daily(result)
        assert request_fields(result)==before
        groups['rank_and_opinion_loss_blocks_response_but_does_not_erase_live_initial_record']+=1
    for stale_flags,partner in (({'live'},0),({'cancelled'},0),(set(),2),({'pending'},0),({'pending','live'},-1),({'pending','live'},999),({'pending','live'},1),({'pending','live'},101)):
        result=state();flags(result).update(PREFIX+flag for flag in stale_flags);variables(result)[PREFIX+'partner']=partner
        assert not selectable(result);complete(result);assert not queued(result,'AB_mobilization.4')
        daily(result);assert request_fields(result)=={'flags':set(),'partner':0}
        groups['orphan_invalid_noncountry_nonpositive_self_fields_block_send_and_clear_locally']+=1
    for hook,actor,from_ in (('on_annex','C','B'),('on_subject_annexed','B','C'),('on_annex','C','A'),('on_subject_annexed','A','C')):
        result=state();initialise(result);setup_pair(result,'D','C');initialise(result,requester='C',provider='D')
        before=child_state(result),money(result),assets(result);native_hook(result,hook,actor,from_)
        assert not pending(result,'A') and pending(result,'D') and (child_state(result),money(result),assets(result))==before
        groups['both_annex_frames_clear_only_matching_provider_or_annexed_initial_receipt']+=1
    for suffix in ('a','b','c'):
        result=state();initialise(result);handoff(result,suffix);before=child_state(result)
        native_hook(result,'on_annex','C','A');daily(result)
        assert child_state(result)==before
        groups['initial_cleanup_after_handoff_never_cancels_existing_child_contract']+=1
    for value in (49,50,300):
        result=state();variables(result,'B')['political_power']=value;before=money(result)
        assert one(action_body(),'cost')=='50';initialise(result);menu(result,'d');assert money(result)==before
        groups['native_50_PP_metadata_is_preserved_without_invented_callback_charge_or_refund']+=1
    result=state();initialise(result);before=money(result),assets(result)
    body=option(model['get_event_map'](read('events/00_War_events.txt')),'AB_mobilization.8','AB_mobilization.8.a')
    effect(result,body,actor='B',from_='A');effect(result,body,actor='B',from_='A')
    assert (money(result),assets(result))==before and pending(result)
    groups['inherited_request_refusal_acknowledgement_remains_inert']+=1
    result=state();effect(result,one(action_body(),'complete_effect'),actor='B',from_=None,scope='A')
    assert pending(result) and variables(result)[PREFIX+'partner']=='B' and queued(result,'AB_mobilization.4')==[{'target':'A','id':'AB_mobilization.4','from':'B'}]
    declaration=result['initial_event_calls'][-1]
    assert declaration['root']=='B' and declaration['scope']=='A' and declaration['parameters']==[('id','=','AB_mobilization.4'),('days','=','1')]
    groups['documented_ROOT_THIS_only_native_frame_creates_exact_requester_pair_without_FROM']+=1
    result=state();initialise(result);menu(result,'d');flags(result).remove('aid_request_cd_@B')
    initialise(result);assert len(queued(result,'AB_mobilization.4'))==2
    groups['explicit_later_cooldown_expiry_fixture_allows_renewal_without_permanent_pair_ban']+=1
    for suffix in ('a','b','c'):
        for mode in ('withdraw_close','expiry','annex_requester'):
            result=state();initialise(result);handoff(result,suffix);setup_pair(result,'A','C')
            initial_child=child_state(result);initialise(result,requester='C')
            if mode=='withdraw_close':assert withdraw(result,requester='C');menu(result,'d',requester='C')
            elif mode=='expiry':flags(result).remove(PREFIX+'live');daily(result)
            else:native_hook(result,'on_annex','D','C')
            assert not pending(result) and child_state(result)==initial_child
            child_reply(result,suffix);child_commit(result,suffix)
            assert not pending(result) and (result.get('native_formation_calls') if suffix=='a' else result.get('native_equipment_calls') if suffix=='b' else variables(result,'B')['treasury']==107)
            groups['a_later_initial_withdrawal_timeout_or_annex_never_cancels_previous_child_offer_or_consent']+=1
    for mode in ('withdraw','decline','expiry','annex'):
        result=state()
        flags(result).update({'eon_advisers_outgoing_owned','eon_advisers_outgoing_live'})
        variables(result)['eon_advisers_outgoing_partner']='B'
        flags(result,'B').update({'eon_advisers_incoming_owned','eon_advisers_incoming_live','eon_services_logistics_owned','eon_services_logistics_live'})
        variables(result,'B').update(eon_advisers_incoming_partner='A',eon_services_logistics_provider='A')
        result['countries']['B']['ideas'].update({'eon_advisers_mission_idea','miltary_logistics_idea'})
        before=child_state(result);initialise(result)
        if mode=='withdraw':assert withdraw(result);menu(result,'d')
        elif mode=='decline':menu(result,'d')
        elif mode=='expiry':flags(result).remove(PREFIX+'live');daily(result)
        else:native_hook(result,'on_subject_annexed','B','C')
        assert child_state(result)==before
        groups['explicit_preexisting_paid_advisory_and_logistics_ledger_fixtures_remain_isolated_from_initial_cleanup']+=1
    result=state();initialise(result);flags(result).remove(PREFIX+'live');before=len(queued(result,'eon_support_request.1'))
    assert not withdraw(result,force=True) and len(queued(result,'eon_support_request.1'))==before
    menu(result,'d');assert not pending(result) and not queued(result,'AB_mobilization.8')
    groups['expired_initial_pair_cannot_withdraw_or_emit_a_current_provider_refusal']+=1

def adapter_checks():
    for name in stock_types:
        result=state();stored=result['countries']['A']['equipment_stock'][name];before=assets(result)
        assert check(result,[('has_equipment','=',[(name,'>',str(stored-1))])],actor='A')
        assert not check(result,[('has_equipment','=',[(name,'>',str(stored))])],actor='A')
        assert assets(result)==before
        adapter_cases['integer_union_of_unchanged_equipment_and_formation_stock_queries']+=1
    for malformed in (-1,0.5,True,'1'):
        result=state();result['countries']['A']['equipment_stock']['medium_tank_amphibious_chassis']=malformed
        try:check(result,[('has_equipment','=',[('medium_tank_amphibious_chassis','>','0')])],actor='A')
        except AssertionError:pass
        else:raise AssertionError(('Malformed stored-equipment fixture accepted',malformed))
        adapter_cases['reject_noninteger_negative_boolean_or_text_stock_fixtures']+=1
    for target in ('tools/validation/diplomacy_package_22/test_request.py','tools/validation/diplomacy_package_22/test_source.py','tools/validation/diplomacy_package_20/README.md','../test.py',str(ROOT/'tools/validation/diplomacy_package_18/test_foreign_cash.py')):
        original_reader,original_run=Path.read_text,subprocess.run
        original_path,original_argv=sys.path[:],sys.argv[:]
        try:historical_caller_run(target)
        except AssertionError:pass
        else:raise AssertionError(('Unknown historical script accepted',target))
        assert Path.read_text is original_reader and subprocess.run is original_run
        assert sys.path==original_path and sys.argv==original_argv
        adapter_cases['historical_harness_rejects_unowned_absolute_traversal_or_nonscript_paths']+=1
    for index,name in ((18,'test_foreign_cash.py'),(19,'test_equipment.py'),(20,'test_formation.py')):
        target=f'tools/validation/diplomacy_package_{index:02}/'+name
        original_reader,original_run,original_run_path=Path.read_text,subprocess.run,runpy.run_path
        original_path,original_argv=sys.path[:],sys.argv[:]
        def fail_inside_target(*args,**kwargs):
            assert Path.read_text is not original_reader and subprocess.run is not original_run
            assert sys.path[0]==str((ROOT/target).parent)
            text=(ROOT/'events/00_War_events.txt').read_text(encoding='utf-8-sig')
            assert 'eon_support_request_handoff_formation' not in text and 'eon_support_request_decline_request' in text
            sys.path=['synthetic replacement path'];sys.argv=['synthetic replacement argv']
            raise RuntimeError('Explicit synthetic historical-entry failure')
        runpy.run_path=fail_inside_target
        try:
            try:historical_caller_run(target)
            except RuntimeError as error:assert str(error)=='Explicit synthetic historical-entry failure'
            else:raise AssertionError('Synthetic historical target did not fail')
        finally:runpy.run_path=original_run_path
        assert Path.read_text is original_reader and subprocess.run is original_run
        assert sys.path==original_path and sys.argv==original_argv
        adapter_cases['three_projected_callers_restore_readers_and_subprocess_after_synthetic_execution_failure']+=1
    original_run_path=runpy.run_path;original_reader,original_run=Path.read_text,subprocess.run
    def actual_source_stub(*args,**kwargs):
        assert Path.read_text is original_reader,'Historical source validator was projected'
        assert 'eon_support_request_handoff_formation' in (ROOT/'events/00_War_events.txt').read_text(encoding='utf-8-sig')
        print(json.dumps({'all_passed':True}))
    runpy.run_path=actual_source_stub
    try:
        result=historical_caller_run('tools/validation/diplomacy_package_21/test_source.py')
        assert result=={'all_passed':True,'historical_bootstrap_current_models_loaded':True}
    finally:runpy.run_path=original_run_path
    assert Path.read_text is original_reader and subprocess.run is original_run
    adapter_cases['historical_source_validator_entry_keeps_actual_gameplay_reader']+=1
    runpy.run_path=actual_source_stub
    try:
        result=historical_caller_run('tools/validation/diplomacy_package_01/test_source.py')
        assert result=={'all_passed':True,'historical_bootstrap_current_models_loaded':True}
    finally:runpy.run_path=original_run_path
    assert Path.read_text is original_reader and subprocess.run is original_run
    adapter_cases['pristine_package01_source_entry_is_explicitly_allowed_without_projection_or_journal']+=1
    def unknown_python_stub(*args,**kwargs):
        subprocess.run([sys.executable,str(ROOT/'tools/validation/diplomacy_package_22/test_request.py')])
    runpy.run_path=unknown_python_stub
    try:
        try:historical_caller_run('tools/validation/diplomacy_package_18/test_foreign_cash.py')
        except AssertionError:pass
        else:raise AssertionError('Unapproved nested Python entry accepted')
    finally:runpy.run_path=original_run_path
    assert Path.read_text is original_reader and subprocess.run is original_run
    adapter_cases['unapproved_nested_python_entry_fails_closed_and_restores_global_readers']+=1
    original_path_object,original_argv_object=sys.path,sys.argv
    original_path,original_argv=sys.path[:],sys.argv[:]
    def script_directory_stub(*args,**kwargs):
        target=ROOT/'tools/validation/diplomacy_package_02/test_treaty.py'
        assert sys.path[0]==str(target.parent) and sys.argv==[str(target)]
        assert (Path(sys.path[0])/'_treaty_support.py').exists()
        sys.path=['synthetic replacement path'];sys.argv=['synthetic replacement argv']
        print(json.dumps({'all_passed':True}))
    runpy.run_path=script_directory_stub
    try:
        result=historical_caller_run('tools/validation/diplomacy_package_02/test_treaty.py')
        assert result=={'all_passed':True,'historical_bootstrap_current_models_loaded':True}
    finally:runpy.run_path=original_run_path
    assert sys.path is original_path_object and sys.path==original_path and sys.argv is original_argv_object and sys.argv==original_argv
    assert Path.read_text is original_reader and subprocess.run is original_run
    adapter_cases['original_script_directory_and_full_path_argv_objects_restore_after_success']+=1
    result=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--historical-caller','tools/validation/diplomacy_package_01/test_source.py'],
        cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['historical_bootstrap_current_models_loaded'] is False
    adapter_cases['fresh_historical_CLI_dispatch_executes_source_before_loading_any_current_model']+=1

def report():
    paths=['common/scripted_diplomatic_actions/MDDC_AB_ask_foreign_support.txt','events/00_War_events.txt',
        'localisation/english/MD_decisions_l_english.yml','localisation/russian/MD_decisions_l_russian.yml',
        'common/scripted_effects/eon_support_request_effects.txt','common/scripted_triggers/eon_support_request_triggers.txt',
        'common/scripted_diplomatic_actions/eon_support_request_actions.txt','common/on_actions/eon_support_request_on_actions.txt',
        'events/eon_support_request_events.txt','localisation/english/eon_support_request_l_english.yml','localisation/russian/eon_support_request_l_russian.yml']
    return {'all_passed':True,'source_only':True,'native_runtime':False,'actual_source_scenarios':sum(groups.values()),'scenario_groups':dict(groups),
        'adapter_semantics_cases':sum(adapter_cases.values()),'adapter_groups':dict(adapter_cases),
        'native_cost_charging_simulated':False,'native_resource_mutation_simulated':False,'native_unit_creation_success_proven':False,
        'source_sha256':{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in paths if (ROOT/path).exists()}}

if __name__=='__main__':
    if len(sys.argv)>1:
        assert len(sys.argv)==3 and sys.argv[1]=='--focus' and sys.argv[2] in FOCUSES
        focus(sys.argv[2])
    else:lifecycle();adapter_checks()
    print(json.dumps(report(),indent=2))
