"""Ordered adviser-service source checks; legacy unit/personnel effects remain opaque observers."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '00bab1d58dae8f16c3d74c78be6db241cab5b2b6'
groups = Counter()
adapter_cases = Counter()
executor_path = ROOT/'tools/validation/diplomacy_package_20/test_formation.py'
executor_text = executor_path.read_text(encoding='utf-8')
boundary = '\ndef focus(name):'
assert executor_text.count(boundary) == 1, 'Ordered definition boundary changed'
source = {'__file__':str(executor_path),'__name__':'advisers_ordered_executor'}
exec(compile(executor_text.split(boundary)[0],str(executor_path),'exec'),source)
model = source['model']
read,option,effect,check,one = (source[name] for name in ('read','option','effect','check','one'))
source_execute,source_trigger,source_state = source['execute'],source['trigger'],source['state']
PREFIX = 'eon_advisers_'
IDEA = PREFIX+'mission_idea'
NAMESPACES = (source,source['source'],source['source']['source'],source['source']['source']['source'],
              source['source']['source']['source']['source'],source['source']['source']['source']['source']['source'],
              source['source']['source']['source']['source']['source']['loader'],model)

def execute(nodes,result,ctx):
    index = 0
    while index < len(nodes):
        key,operator,val = nodes[index]; index += 1
        grouped = [(key,operator,val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if','else'):
                grouped.append(nodes[index]); index += 1
        if key in ('change_influence_percentage','change_the_military_opinion','change_domestic_influence_percentage'):
            provider = result['countries'][ctx['from']] if ctx['from'] in result['countries'] else None
            result.setdefault('adviser_macro_contexts',[]).append({'effect':key,'root':ctx['root'],'from':ctx['from'],
                'scope':ctx['scope'],'temporaries':deepcopy(result.setdefault('scope_temps',{}).get(ctx['scope'],{})),
                'provider_pending_at_call':provider is not None and PREFIX+'pending' in provider['flags']})
            source_execute(grouped,result,ctx)
        elif key == 'modify_treasury_effect':
            provider = result['countries'][ctx['scope']]
            result.setdefault('adviser_fee_calls',[]).append({'root':ctx['root'],'from':ctx['from'],'scope':ctx['scope'],
                'amount':model['value'](result,ctx,'treasury_change'),
                'pending_at_call':PREFIX+'pending' in provider['flags'],
                'partner_at_call':provider['variables'].get(PREFIX+'partner',0)})
            source_execute(grouped,result,ctx)
        elif key == 'add_ideas' and val == IDEA:
            result['countries'][ctx['scope']]['ideas'].add(val)
            result.setdefault('adviser_idea_calls',[]).append((ctx['root'],ctx['from'],ctx['scope'],key,val))
        elif key in ('add_timed_idea','remove_ideas') and (val == IDEA or isinstance(val,list) and one(val,'idea') == IDEA):
            result.setdefault('adviser_idea_calls',[]).append((ctx['root'],ctx['from'],ctx['scope'],key,deepcopy(val)))
            source_execute(grouped,result,ctx)
        elif key == 'capital_scope':
            identity = result['countries'][ctx['scope']]['capital_state_fixture']
            assert identity in result['states'], ('Unknown capital-state fixture',identity)
            execute(val,result,model['switch'](ctx,identity))
        elif key == 'delete_unit_template_and_units':
            assert one(val,'division_template') == 'Grey Men'
            result.setdefault('legacy_adviser_deletion_calls',[]).append(
                {'root':ctx['root'],'from':ctx['from'],'scope':ctx['scope'],'parameters':deepcopy(val)})
        else: source_execute(grouped,result,ctx)
        # No native stock, personnel, unit or template mutations are simulated.

for namespace in NAMESPACES:
    namespace['execute'] = execute
for registry,path in (('effects','common/scripted_effects/eon_advisers_effects.txt'),
                      ('capacity_triggers','common/scripted_triggers/eon_advisers_triggers.txt')):
    if (ROOT/path).exists():
        additions = {key:body for key,op,body in model['ast'](read(path))}
        assert not additions.keys() & model[registry].keys(), 'Advisers overwrite earlier helper IDs'
        model[registry].update(additions)

def state(resources=True):
    result = source_state(resources=resources)
    for index,(actor,country) in enumerate(result['countries'].items(),101):
        country['capital_state_fixture'] = index
        country['civil_war'] = True
        country['wars'] = set()
        result['states'].setdefault(index,{'owner':actor,'controller':actor})
    return result

def event_choice(identity,name): return option(model['get_event_map'](read('events/00_Influence_events.txt')),identity,name)
def calls(result): return result.get('native_formation_calls',[])
def cash(result): return {actor:country['variables']['treasury'] for actor,country in result['countries'].items()}

def focus(name):
    if name == 'unfunded_creation':
        result = state(resources=False); result['countries']['A']['variables']['treasury'] = 1
        effect(result,event_choice('influence.502','influence.502.a'),actor='B',from_='A')
        assert not calls(result), ('Unfunded legacy acceptance must not invoke template or unit creation',calls(result))
        groups['unfunded_legacy_acceptance_issues_no_native_creation_calls'] += 1
    elif name == 'replayed_creation':
        result = state(); body = event_choice('influence.502','influence.502.a')
        effect(result,body,actor='B',from_='A'); first = deepcopy(calls(result))
        effect(result,body,actor='B',from_='A')
        assert calls(result) == first, ('Legacy acceptance replay repeats native creation',len(first),len(calls(result)))
        groups['legacy_acceptance_replay_cannot_repeat_native_creation'] += 1
    elif name == 'replayed_payment':
        result = state(); body = event_choice('influence.503','influence.503.a')
        effect(result,body,actor='A',from_='B'); first = cash(result)
        effect(result,body,actor='A',from_='B')
        assert cash(result) == first, ('Legacy payment replay repeats a fee',first,cash(result))
        groups['legacy_payment_replay_cannot_repeat_treasury_fee'] += 1
    elif name == 'unowned_personnel_return':
        result = state()
        effect(result,event_choice('influence.505','influence.505.a'),actor='A',from_='B')
        assert not calls(result), ('Unowned legacy return must not add fixed personnel',calls(result))
        groups['unowned_legacy_return_issues_no_native_personnel_credit'] += 1
    elif name == 'global_return_broadcast':
        result = state()
        for actor in ('A','D'): result['countries'][actor]['flags'].add('military_services_sent_mercenaries')
        ideas = one(model['ast'](read('common/ideas/Generic Tree_ideas.txt')),'ideas')
        country_ideas = one(ideas,'country')
        body = one(one(country_ideas,'grey_men_foreign_idea'),'on_remove')
        effect(result,body,actor='B',from_='A')
        replies = [item for item in result['events'] if item['id'] == 'influence.505']
        assert not replies, ('Removing one legacy recipient idea must not broadcast return to unrelated globally flagged providers',replies)
        groups['legacy_idea_removal_cannot_broadcast_unowned_provider_return'] += 1
    else: raise AssertionError(('Unknown focus',name))

def flags(result,actor='A'): return result['countries'][actor]['flags']
def vars_(result,actor='A'): return result['countries'][actor]['variables']
def pending(result,actor='A'): return PREFIX+'pending' in flags(result,actor)
def outgoing(result,actor='A'): return PREFIX+'outgoing_owned' in flags(result,actor)
def incoming(result,actor='B'): return PREFIX+'incoming_owned' in flags(result,actor)
def snapshot(result): return {key:deepcopy(val) for key,val in result.items() if key not in ('temp','scope_temps','observed_tooltips')}
def resources(result): return {actor:{key:deepcopy(country[key]) for key in ('equipment_stock','available_manpower','templates','native_unit_inventory')}
                              for actor,country in result['countries'].items()}
def unrelated(result):
    return {actor:{key:deepcopy(val) for key,val in country.items() if key not in ('flags','variables','flag_values','ideas')}
        | {'flags':{key for key in country['flags'] if not key.startswith(PREFIX) and key not in ('sent_grey_men_epochs','refused_military_aid')},
           'flag_values':{key:val for key,val in country['flag_values'].items() if not key.startswith(PREFIX) and key not in ('sent_grey_men_epochs','refused_military_aid')},
           'variables':{key:deepcopy(val) for key,val in country['variables'].items() if not key.startswith(PREFIX) and key != 'treasury'},
           'ideas':country['ideas']-{IDEA}} for actor,country in result['countries'].items()}
def queued(result,identity): return [item for item in result['events'] if item['id'] == identity]
def send(result,provider='A',receiver='B',force=False):
    body = event_choice('influence.501','influence.501.c')
    ready = check(result,one(body,'trigger'),actor=provider,from_=receiver,from_from=receiver)
    if ready or force: effect(result,body,actor=provider,from_=receiver,from_from=receiver)
    return ready
def reply(result,provider='A',receiver='B',accepted=True,force=False):
    events = model['get_event_map'](read('events/eon_advisers_events.txt'))
    body = option(events,'eon_advisers.1','eon_advisers.1.'+('a' if accepted else 'b'))
    ready = check(result,one(body,'trigger'),actor=receiver,from_=provider)
    if ready or force: effect(result,body,actor=receiver,from_=provider)
    return ready
def action(result,name='withdraw_offer',actor='A',partner='B',force=False):
    actions = one(model['ast'](read('common/scripted_diplomatic_actions/eon_advisers_actions.txt')),'scripted_diplomatic_actions')
    body = one(actions,PREFIX+name)
    ready = all(check(result,one(body,key),actor=actor,from_=None,scope=partner) for key in ('allowed','visible','selectable','can_be_sent'))
    if ready or force: effect(result,one(body,'complete_effect'),actor=actor,from_=None,scope=partner)
    return ready
def native_hook(result,name,actor='A',from_='B'):
    hooks = one(model['ast'](read('common/on_actions/eon_advisers_on_actions.txt')),'on_actions')
    effect(result,one(one(hooks,name),'effect'),actor=actor,from_=from_)
def daily(result):
    for actor,country in result['countries'].items():
        if country['exists']: native_hook(result,'on_daily',actor,None)
def helper(result,name,actor='A',from_='B'):
    effect(result,[(PREFIX+name,'=','yes')],actor=actor,from_=from_)
def establish(result,provider='A',receiver='B'):
    assert send(result,provider,receiver)
    assert reply(result,provider,receiver)
    assert outgoing(result,provider) and incoming(result,receiver)
def alteration(result,name,provider='A',receiver='B'):
    donor,client = result['countries'][provider],result['countries'][receiver]
    if name == 'funds_low': donor['variables']['treasury'] = 1.499
    elif name == 'funds_above_cap': donor['variables']['treasury'] = 1000000.001
    elif name == 'provider_dead': donor['exists'] = False
    elif name == 'receiver_dead': client['exists'] = False
    elif name == 'receiver_peace': client['wars'].clear();client['civil_war'] = False
    elif name == 'direct_war': donor['wars'].add(receiver);client['wars'].add(provider)
    elif name == 'influence_lost': client['arrays']['influence_array'] = []
    elif name == 'industry_lost': donor['variables']['num_of_military_factories'] = 10;donor['ideas'].discard('defense_industry');donor['flags'].discard('can_sent_military_aid')
    elif name == 'ERI_forbidden': donor['original_tag'] = 'ERI';donor['flags'].add('ETH_transitional_government_FLAG');donor['leader'] = 'Eritrean Transitional Government'
    elif name == 'AI_government_mismatch': donor['ai'] = True; donor['government'] = 'communist';client['government'] = 'democratic'
    elif name == 'receiver_legacy_idea': client['ideas'].add('grey_men_foreign_idea')
    elif name == 'receiver_unowned_idea': client['ideas'].add(IDEA)
    else: raise AssertionError(('Unknown alteration',name))

def lifecycle():
    for name in ('unfunded_creation','replayed_creation','replayed_payment','unowned_personnel_return','global_return_broadcast'): focus(name)
    for provider,receiver in (('A','B'),('D','C'),('B','A'),('C','D')):
        result = state(resources=False);before_cash=cash(result);before_resources=resources(result);before_unrelated=unrelated(result)
        assert send(result,provider,receiver) and pending(result,provider)
        assert cash(result)==before_cash and resources(result)==before_resources and not calls(result)
        assert vars_(result,provider)[PREFIX+'partner']==receiver and PREFIX+'live' in flags(result,provider)
        assert not outgoing(result,provider) and not incoming(result,receiver)
        assert len(queued(result,'eon_advisers.1'))==1
        assert (provider,PREFIX+'live',30.0) in result['timer_declarations']
        assert reply(result,provider,receiver)
        assert cash(result)[provider]==before_cash[provider]-1.5 and cash(result)[receiver]==before_cash[receiver]
        assert not pending(result,provider) and outgoing(result,provider) and incoming(result,receiver)
        assert vars_(result,provider)[PREFIX+'outgoing_partner']==receiver and vars_(result,receiver)[PREFIX+'incoming_partner']==provider
        assert IDEA in result['countries'][receiver]['ideas'] and 'sent_grey_men_epochs' in flags(result,provider)
        assert (provider,PREFIX+'outgoing_live',60.0) in result['timer_declarations']
        assert (receiver,PREFIX+'incoming_live',60.0) in result['timer_declarations']
        assert resources(result)==before_resources and unrelated(result)==before_unrelated and not calls(result)
        assert result['adviser_fee_calls']==[{'root':receiver,'from':provider,'scope':provider,'amount':-1.5,'pending_at_call':False,'partner_at_call':0}]
        macro = result['adviser_macro_contexts']
        assert len(macro)==2 and [(item['effect'],item['root'],item['from'],item['scope']) for item in macro]==[
            ('change_influence_percentage',receiver,provider,receiver),('change_the_military_opinion',receiver,provider,provider)]
        assert macro[0]['temporaries']['percent_change']==4 and macro[0]['temporaries']['tag_index']==provider and macro[0]['temporaries']['influence_target']==receiver
        assert macro[1]['temporaries']['temp_opinion']==4 and not any(item['provider_pending_at_call'] for item in macro)
        after = snapshot(result); reply(result,provider,receiver,force=True);reply(result,provider,receiver,accepted=False,force=True)
        assert snapshot(result)==after
        groups['four_provider_client_orientations_one_fee_owned_60_day_service_and_native_macro_contexts']+=1
    for amount in (1.5,1.500001,1000000):
        result=state();vars_(result)['treasury']=amount;establish(result)
        assert abs(vars_(result)['treasury']-(amount-1.5))<1e-8
        groups['full_fee_boundaries_without_recipient_cash_credit']+=1
    blocked = ('funds_low','funds_above_cap','provider_dead','receiver_dead','receiver_peace','direct_war','influence_lost','industry_lost','ERI_forbidden','AI_government_mismatch','receiver_legacy_idea','receiver_unowned_idea')
    for name in blocked:
        for stage in ('selection','acceptance'):
            result=state()
            if stage=='acceptance': assert send(result)
            alteration(result,name);before_cash=cash(result);before_resources=resources(result)
            if stage=='selection': assert not send(result,force=True),(stage,name)
            else: assert not reply(result,force=True),(stage,name)
            assert cash(result)==before_cash and resources(result)==before_resources and not calls(result) and not outgoing(result)
            assert not result.get('adviser_macro_contexts') and not result.get('adviser_fee_calls')
            groups['fresh_budget_national_policy_and_foreign_idea_guards_at_offer_and_acceptance']+=1
    for accepted in (True,False):
        for provider,receiver in (('A','C'),('D','B'),('B','A')):
            result=state();assert send(result);before=snapshot(result)
            assert not reply(result,provider,receiver,accepted=accepted,force=True)
            assert snapshot(result)==before
            groups['wrong_provider_or_client_callbacks_leave_pending_and_assets_exact']+=1
    result=state();assert send(result);after=snapshot(result)
    for receiver in ('B','C','D'):
        assert not send(result,receiver=receiver,force=True) and snapshot(result)==after
        groups['one_provider_pending_slot_cannot_be_overwritten']+=1
    result=state();assert send(result);assert send(result,provider='D');assert reply(result)
    before_cash=cash(result);assert not reply(result,provider='D',force=True)
    assert cash(result)==before_cash and vars_(result,'B')[PREFIX+'incoming_partner']=='A' and outgoing(result,'A') and not outgoing(result,'D')
    groups['competing_providers_fresh_recheck_allows_only_one_incoming_paid_service']+=1
    result=state();establish(result);before=snapshot(result)
    assert not send(result,receiver='C',force=True) and snapshot(result)==before
    groups['one_provider_active_outgoing_slot_cannot_fund_second_client']+=1
    for name in ('influence_lost','industry_lost','ERI_forbidden','AI_government_mismatch','funds_low','funds_above_cap'):
        result=state();establish(result);alteration(result,name);before_cash=cash(result);daily(result)
        assert outgoing(result) and incoming(result) and IDEA in result['countries']['B']['ideas'] and cash(result)==before_cash
        groups['paid_service_survives_later_entry_policy_and_budget_changes']+=1
    for actor,partner in (('A','B'),('B','A')):
        result=state();establish(result);before_cash=cash(result);before_resources=resources(result)
        assert action(result,'end_cooperation',actor,partner)
        assert not outgoing(result) and not incoming(result) and IDEA not in result['countries']['B']['ideas']
        assert cash(result)==before_cash and resources(result)==before_resources
        after=snapshot(result);action(result,'end_cooperation',actor,partner,force=True);assert snapshot(result)==after
        groups['either_owned_party_may_end_service_once_without_cash_or_personnel_refund']+=1
    for actor,partner in (('A','C'),('D','B'),('B','D')):
        result=state();establish(result);before=snapshot(result)
        assert not action(result,'end_cooperation',actor,partner,force=True) and snapshot(result)==before
        groups['wrong_pair_native_end_cannot_remove_a_foreign_service']+=1
    for name in ('receiver_peace','direct_war','provider_dead','receiver_dead','provider_timer','client_timer'):
        result=state();establish(result);before_cash=cash(result)
        if name=='provider_timer': flags(result).discard(PREFIX+'outgoing_live')
        elif name=='client_timer': flags(result,'B').discard(PREFIX+'incoming_live')
        else: alteration(result,name)
        daily(result)
        assert not outgoing(result) and not incoming(result) and IDEA not in result['countries']['B']['ideas'] and cash(result)==before_cash
        groups['owned_service_expiry_peace_direct_war_and_party_death_clean_without_refund']+=1
    for name in ('on_annex','on_subject_annexed'):
        for actor,other in (('A','B'),('B','A'),('D','A'),('D','B')):
            result=state();establish(result);before_cash=cash(result);before_resources=resources(result)
            native_hook(result,name,actor,other)
            affected = (other if name=='on_annex' else actor) in ('A','B')
            assert outgoing(result)==(not affected) and incoming(result)==(not affected)
            assert cash(result)==before_cash and resources(result)==before_resources
            groups['both_annex_frames_clean_only_matching_service_without_native_assets']+=1
    for name in ('withdrawal','expiry','dead_provider','dead_client'):
        result=state();assert send(result);before_cash=cash(result)
        if name=='withdrawal':
            assert action(result) and pending(result) and PREFIX+'cancelled' in flags(result)
            assert not reply(result,force=True)
        else:
            if name=='expiry': flags(result).discard(PREFIX+'live')
            elif name=='dead_provider': result['countries']['A']['exists']=False
            else: result['countries']['B']['exists']=False
            if name=='dead_provider': helper(result,'daily_update',actor='A',from_=None)
            daily(result)
        assert not pending(result) and cash(result)==before_cash and not outgoing(result)
        before=snapshot(result);reply(result,force=True);reply(result,accepted=False,force=True);assert snapshot(result)==before
        if name=='expiry':
            assert PREFIX+'retired_pair@B' in flags(result)
            assert not send(result,force=True)
        groups['unsigned_owned_withdrawal_expiry_death_and_late_reply_are_unpaid']+=1
    result=state();assert send(result);assert reply(result,accepted=False)
    assert not pending(result) and 'refused_military_aid' in flags(result,'B')
    assert len(result['adviser_macro_contexts'])==1 and result['adviser_macro_contexts'][0]['effect']=='change_domestic_influence_percentage'
    assert result['adviser_macro_contexts'][0]['root']=='B' and result['adviser_macro_contexts'][0]['scope']=='B'
    assert any(item[1]=='refused_military_aid' and item[2]==180 for item in result['timer_declarations'])
    after=snapshot(result);reply(result,accepted=False,force=True);assert snapshot(result)==after
    groups['current_valid_rejection_keeps_original_domestic_penalty_and_180_day_recipient_timer_once']+=1
    for name in ('funds_low','receiver_peace','industry_lost'):
        result=state();assert send(result);alteration(result,name);before_cash=cash(result)
        reply(result,accepted=False,force=True)
        assert cash(result)==before_cash and not result.get('adviser_macro_contexts') and 'refused_military_aid' not in flags(result,'B')
        groups['stale_unfunded_or_policy_invalid_decline_closes_without_original_rejection_penalty']+=1
    for phase in ('pending','active'):
        result=state();seed={}
        for actor in result['countries']:
            for field in ('eon_services_partner','eon_foreign_cash_partner','eon_foreign_equipment_partner','eon_defence_formation_partner'):
                vars_(result,actor)[field]='D' if actor!='D' else 'C'
            flags(result,actor).update({'eon_services_pending','eon_foreign_cash_pending','eon_foreign_equipment_pending','eon_defence_formation_pending'})
            if actor=='D': flags(result,actor).add('military_services_sent_mercenaries')
            result['countries'][actor]['ideas'].add('grey_men_foreign_idea') if actor=='D' else None
            seed[actor]=(deepcopy({key:val for key,val in vars_(result,actor).items() if not key.startswith(PREFIX) and key!='treasury'}),{key for key in flags(result,actor) if not key.startswith(PREFIX)},resources(result)[actor])
        assert send(result)
        if phase=='active': assert reply(result)
        else: assert action(result)
        daily(result)
        for actor,(variables,oldflags,oldresources) in seed.items():
            assert {key:val for key,val in vars_(result,actor).items() if not key.startswith(PREFIX) and key!='treasury'}==variables
            assert oldflags <= flags(result,actor) and resources(result)[actor]==oldresources
        groups['pending_and_paid_adviser_channel_preserve_legacy_and_other_support_ledgers']+=1
    for name in ('funds_low','receiver_peace','cancelled'):
        result=state();assert send(result)
        if name=='cancelled':assert action(result)
        else:alteration(result,name)
        event=model['get_event_map'](read('events/eon_advisers_events.txt'))['eon_advisers.1']
        eligible=[]
        for key,op,body in event:
            if key!='option':continue
            if check(result,one(body,'trigger'),actor='B',from_='A'):
                eligible.append((one(body,'name'),float(one(one(body,'ai_chance'),'base'))))
        assert eligible==[('eon_advisers.1.b',10.0)],(name,eligible)
        reply(result,accepted=False,force=True)
        assert not pending(result) and not result.get('adviser_macro_contexts')
        groups['invalid_current_offer_has_only_positive_weight_decline_and_no_stale_penalty']+=1
    for wrong in (0,-1,999,'A',101):
        result=state();flags(result).update({PREFIX+'pending',PREFIX+'live'});vars_(result)[PREFIX+'partner']=wrong
        before_cash=cash(result);before_resources=resources(result);daily(result)
        assert not pending(result) and PREFIX+'quarantined' in flags(result) and cash(result)==before_cash and resources(result)==before_resources
        assert not send(result,force=True) and not result.get('adviser_macro_contexts')
        groups['malformed_or_self_pending_partner_quarantines_only_own_channel_without_spend']+=1
    for field,value in (('live',None),('cancelled',None),('partner','B')):
        result=state()
        if value is None:flags(result).add(PREFIX+field)
        else:vars_(result)[PREFIX+field]=value
        before_cash=cash(result);daily(result)
        assert not pending(result) and PREFIX+'quarantined' in flags(result) and vars_(result).get(PREFIX+'partner',0)==0 and cash(result)==before_cash
        groups['pending_orphan_field_without_owned_record_quarantines_channel']+=1
    for direction in ('incoming','outgoing'):
        for wrong in (0,-1,999,'A',101):
            actor='B' if direction=='incoming' else 'A'
            result=state();flags(result,actor).add(PREFIX+direction+'_owned');flags(result,actor).add(PREFIX+direction+'_live')
            vars_(result,actor)[PREFIX+direction+'_partner']=wrong
            if direction=='incoming':result['countries'][actor]['ideas'].add(IDEA)
            before_cash=cash(result);daily(result)
            # 'A' is a real foreign identity from recipient B but lacks a reciprocal owned outgoing record.
            assert PREFIX+direction+'_owned' not in flags(result,actor) and vars_(result,actor).get(PREFIX+direction+'_partner',0)==0
            assert cash(result)==before_cash and not calls(result)
            groups['malformed_owned_active_records_clear_locally_without_resources_or_foreign_ownership']+=1
    for operation in ('daily','annex','explicit_incoming'):
        result=state();result['countries']['B']['ideas'].add(IDEA)
        flags(result,'B').add(PREFIX+'incoming_live');vars_(result,'B')[PREFIX+'incoming_partner']='A'
        before_cash=cash(result)
        if operation=='daily':daily(result)
        elif operation=='annex':native_hook(result,'on_annex','D','B')
        else:helper(result,'clear_incoming',actor='B')
        assert IDEA in result['countries']['B']['ideas'] and not incoming(result) and cash(result)==before_cash
        groups['unowned_adviser_idea_is_preserved_by_orphan_daily_annex_and_explicit_cleanup']+=1
    for operation in ('daily','explicit_outgoing','annex'):
        result=state();establish(result,'D','B')
        flags(result).update({PREFIX+'outgoing_owned',PREFIX+'outgoing_live'});vars_(result)[PREFIX+'outgoing_partner']='B'
        before_cash=cash(result)
        if operation=='daily':daily(result)
        elif operation=='explicit_outgoing':helper(result,'clear_outgoing',actor='A')
        else:native_hook(result,'on_annex','C','A')
        assert not outgoing(result,'A') and outgoing(result,'D') and incoming(result,'B') and vars_(result,'B')[PREFIX+'incoming_partner']=='D'
        assert IDEA in result['countries']['B']['ideas'] and cash(result)==before_cash
        groups['foreign_reciprocal_service_survives_mismatched_outgoing_daily_end_and_annex']+=1
    for operation in ('daily','explicit_incoming','annex'):
        result=state();establish(result,'A','D')
        flags(result,'B').update({PREFIX+'incoming_owned',PREFIX+'incoming_live'});vars_(result,'B')[PREFIX+'incoming_partner']='A';result['countries']['B']['ideas'].add(IDEA)
        before_cash=cash(result)
        if operation=='daily':daily(result)
        elif operation=='explicit_incoming':helper(result,'clear_incoming',actor='B')
        else:native_hook(result,'on_annex','C','B')
        assert outgoing(result,'A') and incoming(result,'D') and vars_(result,'A')[PREFIX+'outgoing_partner']=='D' and not incoming(result,'B')
        assert IDEA in result['countries']['D']['ideas'] and cash(result)==before_cash
        groups['foreign_reciprocal_service_survives_mismatched_incoming_daily_end_and_annex']+=1
    result=state();establish(result);establish(result,'B','A');before_cash=cash(result)
    assert action(result,'end_cooperation','A','B') and not outgoing(result,'A') and not outgoing(result,'B') and not incoming(result,'A') and not incoming(result,'B')
    assert cash(result)==before_cash
    groups['bidirectional_owned_pair_end_clears_both_services_without_double_spend_or_refund']+=1
    result=state();establish(result);establish(result,'B','C');establish(result,'C','A');before_cash=cash(result)
    assert action(result,'end_cooperation','A','B')
    assert not outgoing(result,'A') and not incoming(result,'B') and outgoing(result,'B') and incoming(result,'C') and outgoing(result,'C') and incoming(result,'A')
    assert cash(result)==before_cash
    groups['three_country_adviser_cycle_end_preserves_two_other_reciprocal_services']+=1
    for name in ('military_services_sent_mercenaries','eon_advisers_quarantined','eon_advisers_live','eon_advisers_cancelled','eon_advisers_outgoing_live'):
        result=state();flags(result).add(name);before=snapshot(result)
        assert not send(result,force=True) and snapshot(result)==before
        groups['legacy_provider_or_orphan_slot_markers_block_new_proposals_without_migration']+=1
    result=state();assert send(result);flags(result,'B').add('refused_military_aid');before_macros=len(result.get('adviser_macro_contexts',[]))
    assert reply(result,accepted=False) and not pending(result)
    assert len(result.get('adviser_macro_contexts',[]))==before_macros
    groups['existing_receiver_refusal_marker_does_not_repeat_domestic_adjustment']+=1
    result=state();establish(result);assert send(result,'B','D');before_cash=cash(result)
    assert action(result,'end_cooperation','A','B')
    assert pending(result,'B') and vars_(result,'B')[PREFIX+'partner']=='D' and cash(result)==before_cash
    assert reply(result,'B','D') and outgoing(result,'B') and incoming(result,'D')
    groups['ending_one_owned_service_preserves_the_other_actor_unsigned_third_party_proposal']+=1

def adapter_semantics():
    # Explicit primitive and frame probes; these do not recount old suites.
    for scope,from_ in (('B','A'),('C','D')):
        result=state();effect(result,[('set_temp_variable','=',[('probe','=','9')]),('FROM','=',[('set_temp_variable','=',[('probe','=','3')])])],actor=scope,from_=from_)
        assert result['scope_temps'][scope]['probe']==9 and result['scope_temps'][from_]['probe']==3
        adapter_cases['temporaries_are_per_country_and_FROM_switch_preserves_ROOT']+=1
    for amount,expected in ((-1.5,98.5),(-1000001,-999901),(1000001,1000000)):
        result=state();effect(result,[('set_temp_variable','=',[('treasury_change','=',str(amount))]),('modify_treasury_effect','=','yes')],actor='A',from_='B')
        assert vars_(result)['treasury']==expected and vars_(result,'B')['treasury']==100
        adapter_cases['actual_known_treasury_helper_arithmetic_and_clamp_not_native_assets']+=1
    for timer in (30,60,180):
        result=state();effect(result,[('set_country_flag','=',[('flag','=','probe'),('days','=',str(timer)),('value','=','1')])],actor='A')
        assert ("A","probe",float(timer)) in result['timer_declarations'] and 'probe' in flags(result)
        assert not result.get('clock_elapsed_days')
        adapter_cases['native_timer_declarations_do_not_simulate_elapsed_time']+=1
    result=state();effect(result,[('add_timed_idea','=',[('idea','=',IDEA),('days','=','60')]),('remove_ideas','=',IDEA)],actor='B',from_='A')
    assert IDEA not in result['countries']['B']['ideas'] and ('B',IDEA,60.0) in result['idea_timer_declarations']
    adapter_cases['explicit_idea_set_and_timer_observation_do_not_prove_native_bonus_application']+=1
    for native in ('add_manpower','create_unit','division_template'):
        result=state();before=resources(result)
        val='1000' if native=='add_manpower' else [('owner','=','ROOT'),('division','=','opaque'),('count','=','1')] if native=='create_unit' else [('name','=','Opaque fixture template')]
        effect(result,[(native,'=',val)],actor='A',from_='B')
        assert resources(result)==before and len(calls(result))==1
        adapter_cases['native_personnel_template_and_unit_commands_only_append_call_observations']+=1
    for token in (0,-1,999,'A',101,'B'):
        result=state();vars_(result)[PREFIX+'partner']=token
        ready=check(result,[(PREFIX+'partner_identified','=','yes')],actor='A',from_='B')
        assert ready==(token=='B')
        adapter_cases['partner_identity_requires_existing_country_frame_and_exact_nonself_identifier']+=1

def main():
    if len(sys.argv)>1:
        assert len(sys.argv)==3 and sys.argv[1]=='--focus';focus(sys.argv[2])
    else:lifecycle();adapter_semantics()
    paths = ['events/00_Influence_events.txt','common/ideas/Generic Tree_ideas.txt',
        'localisation/english/events_l_english.yml','localisation/english/MD_influence_l_english.yml',
        'localisation/russian/replace/replaced_from_events_l_russian.yml','localisation/russian/replace/replaced_from_MD_influence_l_russian.yml',
        'localisation/english/MDC_focus_GENERIC_l_english.yml','localisation/russian/MDDC_focus_GENERIC_l_russian.yml',
        'common/scripted_effects/eon_advisers_effects.txt','common/scripted_triggers/eon_advisers_triggers.txt',
        'common/scripted_diplomatic_actions/eon_advisers_actions.txt','common/on_actions/eon_advisers_on_actions.txt',
        'events/eon_advisers_events.txt','common/ideas/eon_advisers_ideas.txt',
        'localisation/english/eon_advisers_l_english.yml','localisation/russian/eon_advisers_l_russian.yml']
    print(json.dumps({'all_passed':True,'actual_source_scenarios':sum(groups.values()),'groups':dict(groups),
        'adapter_semantics_cases':sum(adapter_cases.values()),
        'adapter_groups':dict(adapter_cases),
        'source_sha256':{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in paths},
        'native_resource_mutation_simulated':False,'native_unit_creation_success_proven':False,
        'proof_scope':'ordered current-source advisory proposal and paired paid lifecycle; known treasury arithmetic and native political call frames, not playable/native outcomes'},indent=2))

if __name__ == '__main__': main()
