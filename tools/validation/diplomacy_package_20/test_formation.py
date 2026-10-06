"""Observe current-source national defence formation calls; not native inventory or spawn success."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = 'de8de2feda0e02b3a80a51ae6df3d9571358f823'
groups = Counter()
adapter_cases = Counter()
EQUIPMENT = {'Inf_equipment': 1623, 'command_control_equipment': 150,
             'artillery_equipment': 36, 'L_AT_Equipment': 76, 'AA_Equipment': 50}
PERSONNEL = 5480
TEMPLATE = 'EON Local Defence Formation'

# Import only interpreter definitions. Earlier scenario loops run independently.
executor_path = ROOT / 'tools/validation/diplomacy_package_19/test_equipment.py'
executor_text = executor_path.read_text(encoding='utf-8')
boundary = '\ndef focus(name):'
assert executor_text.count(boundary) == 1, 'Ordered definition boundary changed'
source = {'__file__': str(executor_path), '__name__': 'formation_ordered_executor'}
exec(compile(executor_text.split(boundary)[0], str(executor_path), 'exec'), source)
model = source['model']
read, option, effect, check, one = (source[name] for name in ('read', 'option', 'effect', 'check', 'one'))
source_trigger, source_execute, source_state = source['trigger'], source['execute'], source['state']

def trigger(nodes, result, ctx):
    index = 0
    while index < len(nodes):
        key, operator, val = nodes[index]; index += 1
        grouped = [(key, operator, val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        if key == 'has_manpower':
            stored = result['countries'][ctx['scope']]['available_manpower']
            assert isinstance(stored, int) and not isinstance(stored, bool) and stored >= 0
            passed = model['compare'](stored, operator, model['value'](result, ctx, val))
        elif key == 'has_equipment':
            assert isinstance(val, list) and len(val) == 1
            archetype, comparison, wanted = val[0]
            assert archetype in EQUIPMENT, ('Unknown formation stored-count query', archetype)
            stored = result['countries'][ctx['scope']]['equipment_stock'][archetype]
            assert isinstance(stored, int) and not isinstance(stored, bool) and stored >= 0
            passed = model['compare'](stored, comparison, model['value'](result, ctx, wanted))
        elif key == 'has_template':
            passed = val in result['countries'][ctx['scope']]['templates']
        elif key == 'any_owned_state':
            passed = any(trigger(val, result, model['switch'](ctx, identity))
                         for identity, state in result['states'].items() if state['owner'] == ctx['scope'])
        elif key == 'is_owned_and_controlled_by':
            target = model['country_ref'](result, ctx, val)
            state = result['states'][ctx['scope']]
            passed = state['owner'] == target and state['controller'] == target
        else: passed = source_trigger(grouped, result, ctx)
        if not passed: return False
    return True

def observe(result, ctx, key, val, **extra):
    provider = result['countries'][ctx['root']]
    result.setdefault('native_formation_calls', []).append({
        'effect': key, 'root': ctx['root'], 'from': ctx['from'], 'scope': ctx['scope'],
        'parameters': deepcopy(val),
        'provider_pending_at_call': 'eon_defence_formation_pending' in provider['flags'],
        'provider_partner_at_call': provider['variables'].get('eon_defence_formation_partner', 0), **extra})

def execute(nodes, result, ctx):
    index = 0
    while index < len(nodes):
        key, operator, val = nodes[index]; index += 1
        grouped = [(key, operator, val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        if key == 'add_manpower':
            observe(result, ctx, key, val, amount=model['value'](result, ctx, val))
        elif key == 'add_equipment_to_stockpile':
            archetype = one(val, 'type')
            assert archetype in EQUIPMENT
            fields = {name: value for name, op, value in val}
            observe(result, ctx, key, val, equipment=archetype,
                    amount=model['value'](result, ctx, fields['amount']),
                    producer=model['country_ref'](result, ctx, fields['producer']) if 'producer' in fields else None)
        elif key == 'division_template': observe(result, ctx, key, val, name=one(val, 'name'))
        elif key == 'random_owned_controlled_state':
            eligible = [identity for identity, state in result['states'].items()
                        if state['owner'] == ctx['scope'] and state['controller'] == ctx['scope']]
            limits = [body for name, op, body in val if name == 'limit']
            if limits: eligible = [identity for identity in eligible if trigger(limits[0], result, model['switch'](ctx, identity))]
            # Explicit deterministic selection fixture, not native randomness or placement proof.
            if eligible: execute([node for node in val if node[0] != 'limit'], result, model['switch'](ctx, eligible[0]))
        elif key == 'create_unit':
            observe(result, ctx, key, val, owner=model['country_ref'](result, ctx, one(val, 'owner')))
        elif key == 'add_ideas':
            assert val == 'AB_foreign_peacekeepers', ('Unexpected legacy idea call', val)
            result.setdefault('legacy_formation_idea_calls', []).append(
                {'root': ctx['root'], 'from': ctx['from'], 'scope': ctx['scope'], 'idea': val})
        else: source_execute(grouped, result, ctx)
        # Native resources, templates and units remain opaque observations.

for namespace in (source, source['source'], source['source']['source'], source['source']['source']['source'],
                  source['source']['source']['source']['source'],
                  source['source']['source']['source']['source']['loader'], model):
    namespace['trigger'] = trigger; namespace['execute'] = execute
for registry, path in (('effects', 'common/scripted_effects/eon_defence_formation_effects.txt'),
                       ('capacity_triggers', 'common/scripted_triggers/eon_defence_formation_triggers.txt')):
    if (ROOT / path).exists():
        additions = {key: body for key, op, body in model['ast'](read(path))}
        assert not additions.keys() & model[registry].keys(), 'Formation helper overwrites earlier definition'
        model[registry].update(additions)

def state(resources=True):
    result = source_state()
    for country in result['countries'].values():
        country['equipment_stock'].update({key: value * (3 if resources else 0) for key, value in EQUIPMENT.items()})
        country['available_manpower'] = PERSONNEL * (3 if resources else 0)
        country['templates'] = set()
        country['native_unit_inventory'] = {'legacy_foreign_unit'}
    result['states'] = {101: {'owner': 'A', 'controller': 'A'}, 102: {'owner': 'B', 'controller': 'B'},
                        103: {'owner': 'C', 'controller': 'C'}}
    return result

def formation_option():
    return option(model['get_event_map'](read('events/00_War_events.txt')), 'AB_mobilization.4', 'AB_mobilization.4.a')

def old_callback(result): effect(result, formation_option(), actor='A', from_='B')

def calls(result): return result.get('native_formation_calls', [])

def focus(name):
    if name == 'resource_calls_without_consent':
        result = state(); old_callback(result)
        assert not calls(result), ('No native formation resource calls before recipient consent', calls(result))
        groups['no_native_formation_resource_calls_before_consent'] += 1
    elif name == 'replay':
        result = state(); old_callback(result); first = deepcopy(calls(result)); old_callback(result)
        assert calls(result) == first, ('Unsigned callback replay repeats resource calls', len(first), len(calls(result)))
        groups['unsigned_formation_callback_does_not_repeat_native_calls'] += 1
    elif name == 'unavailable_resource_calls':
        result = state(resources=False); old_callback(result)
        assert not calls(result), ('No native resource calls with absent explicit resource fixtures', calls(result))
        groups['no_native_formation_resource_calls_without_explicit_resources'] += 1
    elif name == 'legacy_free_creation':
        result = state()
        body = option(model['get_event_map'](read('events/00_War_events.txt')), 'AB_mobilization.5', 'AB_mobilization.5.a')
        effect(result, body, actor='B', from_='A')
        assert not calls(result), ('Legacy acknowledgement must not create a free template or formation', calls(result))
        groups['legacy_acknowledgement_has_no_native_template_or_unit_creation'] += 1
    else: raise AssertionError(('Unknown focus', name))

def flags(result, actor='A'): return result['countries'][actor]['flags']
def vars_(result, actor='A'): return result['countries'][actor]['variables']
def pending(result, actor='A'): return 'eon_defence_formation_pending' in flags(result, actor)
def consented(result, actor='A'): return 'eon_defence_formation_consented' in flags(result, actor)
def snapshot(result): return {key:deepcopy(val) for key,val in result.items() if key not in ('temp','scope_temps','observed_tooltips')}
def resource_facts(result):
    return {'countries': {actor:{key:deepcopy(country[key]) for key in ('equipment_stock','available_manpower','templates','native_unit_inventory')}
                          for actor,country in result['countries'].items()}, 'states':deepcopy(result['states'])}
def unrelated(result):
    return {actor:{key:deepcopy(val) for key,val in country.items() if key not in ('variables','flags','flag_values')}
        | {'variables':{key:deepcopy(val) for key,val in country['variables'].items() if not key.startswith('eon_defence_formation_')},
           'flags':{key for key in country['flags'] if not key.startswith('eon_defence_formation_')},
           'flag_values':{key:val for key,val in country['flag_values'].items() if not key.startswith('eon_defence_formation_')}}
        for actor,country in result['countries'].items()}
def queued(result, identity): return [item for item in result['events'] if item['id'] == identity]
def send(result, provider='A', receiver='B', force=False):
    body = formation_option(); ready = check(result,one(body,'trigger'),actor=provider,from_=receiver)
    if ready or force: effect(result,body,actor=provider,from_=receiver)
    return ready
def reply(result, provider='A', receiver='B', accepted=True, force=False):
    events = model['get_event_map'](read('events/eon_defence_formation_events.txt'))
    body = option(events,'eon_defence_formation.1','eon_defence_formation.1.'+('a' if accepted else 'b'))
    ready = check(result,one(body,'trigger'),actor=receiver,from_=provider)
    if ready or force: effect(result,body,actor=receiver,from_=provider)
    return ready
def commit(result, provider='A', receiver='B'):
    events = model['get_event_map'](read('events/eon_defence_formation_events.txt'))
    effect(result,one(events['eon_defence_formation.2'],'immediate'),actor=provider,from_=receiver)
def action(result, actor='A', partner='B', force=False):
    actions = one(model['ast'](read('common/scripted_diplomatic_actions/eon_defence_formation_actions.txt')),'scripted_diplomatic_actions')
    body = one(actions,'eon_defence_formation_withdraw_offer')
    ready = all(check(result,one(body,key),actor=actor,from_=None,scope=partner) for key in ('allowed','visible','selectable','can_be_sent'))
    if ready or force: effect(result,one(body,'complete_effect'),actor=actor,from_=None,scope=partner)
    return ready
def native_hook(result, name, actor='A', from_='B'):
    hooks = one(model['ast'](read('common/on_actions/eon_defence_formation_on_actions.txt')),'on_actions')
    effect(result,one(one(hooks,name),'effect'),actor=actor,from_=from_)
def daily(result):
    for actor,country in result['countries'].items():
        if country['exists']: native_hook(result,'on_daily',actor,None)
def assert_batch(result, provider='A', receiver='B', template_created=True):
    observed = calls(result)
    assert len(observed) == (8 if template_created else 7),observed
    for call,(archetype,count) in zip(observed[:5],EQUIPMENT.items()):
        assert call['effect'] == 'add_equipment_to_stockpile' and call['scope'] == provider
        assert call['equipment'] == archetype and call['amount'] == -count and call['producer'] is None
        assert call['parameters'] == [('type','=',archetype),('amount','=',str(-count))]
    assert observed[5]['effect'] == 'add_manpower' and observed[5]['scope'] == receiver and observed[5]['amount'] == -PERSONNEL
    if template_created: assert observed[6]['effect'] == 'division_template' and observed[6]['scope'] == receiver and observed[6]['name'] == TEMPLATE
    spawn = observed[-1]
    assert spawn['effect'] == 'create_unit' and spawn['owner'] == receiver and one(spawn['parameters'],'count') == '1'
    assert result['states'][spawn['scope']] == {'owner':receiver,'controller':receiver}
    assert all(call['root'] == provider and call['from'] == receiver and not call['provider_pending_at_call'] and call['provider_partner_at_call'] == 0 for call in observed)
    assert result['foreign_cash_political_contexts'] == [{'root':provider,'from':receiver,'scope':provider}]
    assert len(result['political_macro_calls']) == 1
    assert not queued(result,'AB_mobilization.5') and not result.get('legacy_formation_idea_calls')
    assert not pending(result,provider) and not consented(result,provider)

def alteration(result, name):
    provider,receiver = result['countries']['A'],result['countries']['B']
    if name.startswith('stock_'): provider['equipment_stock'][name[6:]] = EQUIPMENT[name[6:]]-1
    elif name == 'recipient_manpower': receiver['available_manpower'] = PERSONNEL-1
    elif name == 'recipient_land_lost': result['states'][102]['controller'] = 'C'
    elif name == 'recipient_only_foreign_controlled_land': result['states'][102]['owner'] = 'C'
    elif name == 'template_collision': receiver['templates'].add(TEMPLATE)
    elif name == 'donor_rank': provider['ideas'] -= {'large_power','great_power','superpower'}
    elif name == 'receiver_rank': receiver['ideas'] -= {'non_power','minor_power','regional_power'}
    elif name == 'defensive_war_lost': receiver['defensive_war'] = False
    elif name == 'request_marker_lost': provider['flags'].discard('aid_request_cd_@B')
    elif name == 'opinion_lost': provider['opinions']['B'] = 49
    elif name == 'direct_war': provider['wars'].add('B'); receiver['wars'].add('A')
    elif name == 'donor_annexed': provider['exists'] = False
    elif name == 'receiver_annexed': receiver['exists'] = False
    elif name == 'live_expired': provider['flags'].discard('eon_defence_formation_live')
    elif name == 'cancelled': provider['flags'].add('eon_defence_formation_cancelled')
    else: raise AssertionError(('Unknown alteration',name))

def scenarios():
    for name in ('resource_calls_without_consent','replay','unavailable_resource_calls','legacy_free_creation'): focus(name)
    for mode in ('absent','owned','zero_donor_personnel','exact_resources','absent_with_prior_owned_marker'):
        result = state(); receiver = result['countries']['B']
        if mode == 'owned': receiver['templates'].add(TEMPLATE); flags(result,'B').add('eon_defence_formation_template_owned')
        if mode == 'absent_with_prior_owned_marker': flags(result,'B').add('eon_defence_formation_template_owned')
        if mode == 'zero_donor_personnel': result['countries']['A']['available_manpower'] = 0
        if mode == 'exact_resources':
            result['countries']['A']['equipment_stock'].update(EQUIPMENT); receiver['available_manpower'] = PERSONNEL
        receiver['templates'].add('Foreign Peacekeepers'); receiver['ideas'].add('AB_foreign_peacekeepers')
        facts = resource_facts(result); other = unrelated(result)
        assert send(result) and pending(result) and vars_(result)['eon_defence_formation_partner'] == 'B'
        assert queued(result,'eon_defence_formation.1') == [{'target':'B','id':'eon_defence_formation.1','from':'A'}]
        assert ('A','eon_defence_formation_live',30) in result['timer_declarations']
        assert not calls(result) and resource_facts(result) == facts and unrelated(result) == other
        assert reply(result) and consented(result) and not calls(result) and resource_facts(result) == facts
        assert queued(result,'eon_defence_formation.2') == [{'target':'A','id':'eon_defence_formation.2','from':'B'}]
        waiting = snapshot(result)
        assert not reply(result,force=True) and not reply(result,accepted=False,force=True) and not action(result,force=True)
        assert snapshot(result) == waiting
        commit(result); assert_batch(result,template_created=(mode != 'owned'))
        assert resource_facts(result) == facts and unrelated(result) == other
        completed = snapshot(result); commit(result); reply(result,force=True); reply(result,accepted=False,force=True)
        assert snapshot(result) == completed
        daily(result); receiver['defensive_war'] = False; daily(result)
        assert resource_facts(result) == facts and calls(result) == completed['native_formation_calls']
        groups['five_explicit_template_and_resource_fixtures_commit_exact_national_owner_calls_without_native_fixture_mutation'] += 1
    invalid = ['stock_'+key for key in EQUIPMENT] + ['recipient_manpower','recipient_land_lost','recipient_only_foreign_controlled_land','template_collision','donor_rank','receiver_rank','defensive_war_lost','request_marker_lost','opinion_lost','direct_war','donor_annexed','receiver_annexed']
    for phase in ('offer','response','commit'):
        for name in invalid + ([] if phase == 'offer' else ['live_expired','cancelled']):
            result = state()
            if phase != 'offer': assert send(result)
            if phase == 'commit': assert reply(result)
            alteration(result,name); facts = resource_facts(result); other = unrelated(result)
            if phase == 'offer': assert not send(result,force=True) and not pending(result)
            elif phase == 'response': assert not reply(result,force=True) and not pending(result)
            else: commit(result); assert not pending(result)
            assert not calls(result) and not result.get('political_macro_calls') and resource_facts(result) == facts and unrelated(result) == other
            groups['fresh_'+phase+'_full_equipment_recipient_personnel_land_template_and_policy_failure_issues_no_native_batch'] += 1
    for phase in ('response','commit'):
        for owned in (False,True):
            result = state(); assert send(result)
            if phase == 'commit': assert reply(result)
            result['countries']['B']['templates'].add(TEMPLATE)
            if owned: flags(result,'B').add('eon_defence_formation_template_owned')
            facts = resource_facts(result)
            if phase == 'response':
                assert reply(result,force=True) == owned
                if owned: commit(result)
            else: commit(result)
            if owned: assert_batch(result,template_created=False)
            else: assert not calls(result)
            assert resource_facts(result) == facts
            groups['fresh_owned_template_reuse_or_unowned_collision_at_response_and_commit_without_fixture_auto_creation'] += 1
    for phase in ('offer','response','commit'):
        for amount in (PERSONNEL,PERSONNEL+1):
            result = state()
            if phase != 'offer': assert send(result)
            if phase == 'commit': assert reply(result)
            result['countries']['B']['available_manpower'] = amount
            result['countries']['A']['available_manpower'] = 0
            if phase == 'offer': assert send(result)
            if phase != 'commit': assert reply(result)
            facts = resource_facts(result); commit(result); assert_batch(result)
            assert resource_facts(result) == facts
            groups['six_recipient_manpower_native_boundary_fixtures_and_zero_donor_manpower_are_eligible'] += 1
    result = state(); assert send(result); initial = snapshot(result)
    assert not send(result,force=True) and not send(result,receiver='C',force=True) and snapshot(result) == initial
    groups['one_pending_provider_pair_cannot_be_replaced_by_duplicate_or_other_partner_offer'] += 1
    for provider,receiver in (('A','C'),('C','B'),('A','A')):
        result = state(); assert send(result); initial = snapshot(result)
        assert not reply(result,provider,receiver,force=True) and not reply(result,provider,receiver,accepted=False,force=True)
        assert snapshot(result) == initial
        groups['wrong_partner_provider_or_self_response_is_inert'] += 1
        result = state(); assert send(result); assert reply(result); initial = snapshot(result)
        commit(result,provider,receiver); assert snapshot(result) == initial
        groups['wrong_partner_provider_or_self_hidden_commit_is_inert'] += 1
    result = state(); assert send(result); initial = snapshot(result); commit(result)
    assert snapshot(result) == initial
    groups['provider_commit_without_recipient_consent_is_inert'] += 1
    result = state(); assert send(result); assert reply(result,accepted=False) and not pending(result) and not calls(result)
    assert send(result,receiver='C'); initial = snapshot(result)
    reply(result,force=True); reply(result,accepted=False,force=True); commit(result)
    assert snapshot(result) == initial
    groups['declined_old_partner_callbacks_cannot_consume_later_other_partner_proposal'] += 1
    result = state(); assert send(result); facts = resource_facts(result); assert action(result)
    assert pending(result) and 'eon_defence_formation_cancelled' in flags(result) and resource_facts(result) == facts
    assert not reply(result,force=True) and not pending(result) and not calls(result)
    groups['free_unsigned_withdraw_and_matching_old_reply_close_without_native_assets'] += 1
    for actor,partner in (('C','B'),('A','C'),('B','A')):
        result = state(); assert send(result); initial = snapshot(result)
        assert not action(result,actor,partner,force=True) and snapshot(result) == initial
        groups['wrong_native_withdraw_actor_or_partner_is_inert'] += 1
    for hook in ('on_annex','on_subject_annexed'):
        for victim in ('A','B'):
            for extinct in (False,True):
                for accepted in (False,True):
                    result = state(); assert send(result)
                    if accepted: assert reply(result)
                    flags(result,victim).add('eon_defence_formation_template_owned')
                    result['countries'][victim]['templates'].update({TEMPLATE,'Foreign Peacekeepers'})
                    if extinct: result['countries'][victim]['exists'] = False
                    facts = resource_facts(result)
                    native_hook(result,hook,actor='C' if hook == 'on_annex' else victim,from_=victim if hook == 'on_annex' else 'C')
                    assert not pending(result) and not calls(result) and resource_facts(result) == facts
                    assert 'eon_defence_formation_template_owned' in flags(result,victim)
                    groups['sixteen_annex_frames_before_or_after_disappearance_clear_only_pending_proposals_preserving_native_fixtures'] += 1
    for name in ('live_expired','donor_annexed','receiver_annexed'):
        result = state(); assert send(result); alteration(result,name); facts = resource_facts(result)
        effect(result,[('eon_defence_formation_daily_update','=','yes')],actor='A',from_=None)
        assert not pending(result) and not calls(result) and resource_facts(result) == facts
        assert 'eon_defence_formation_retired_pair@B' in flags(result)
        groups['known_expired_or_dead_pending_pair_is_retired_without_assets'] += 1
    malformed = ('orphan_live','orphan_cancelled','orphan_consented','orphan_partner','missing_partner','self_partner','unknown_partner')
    for mode in malformed:
        result = state(); facts = resource_facts(result)
        if mode.startswith('orphan_'):
            if mode == 'orphan_partner': vars_(result)['eon_defence_formation_partner'] = 'B'
            else: flags(result).add('eon_defence_formation_'+mode[7:])
        else:
            flags(result).update({'eon_defence_formation_pending','eon_defence_formation_live'})
            if mode == 'self_partner': vars_(result)['eon_defence_formation_partner'] = 'A'
            elif mode == 'unknown_partner': vars_(result)['eon_defence_formation_partner'] = 999
        daily(result)
        assert not pending(result) and 'eon_defence_formation_quarantined' in flags(result) and not calls(result) and resource_facts(result) == facts
        groups['seven_malformed_pair_records_quarantine_only_owned_proposal_channel_without_native_assets'] += 1
    for name in ('recipient_manpower','recipient_land_lost','template_collision','stock_Inf_equipment','defensive_war_lost'):
        result = state(); assert send(result); alteration(result,name); initial = snapshot(result); daily(result)
        assert snapshot(result) == initial and pending(result) and not calls(result)
        groups['daily_transient_living_prerequisite_loss_waits_for_fresh_response_without_native_effects'] += 1
    result = state(); flags(result,'B').add('eon_defence_formation_template_owned'); result['countries']['B']['templates'].add(TEMPLATE)
    initial = snapshot(result); daily(result); assert snapshot(result) == initial
    groups['retained_template_marker_alone_is_valid_without_pending_proposal_or_quarantine'] += 1
    result = state(); assert send(result); assert send(result,provider='D',receiver='B')
    assert reply(result) and reply(result,provider='D',receiver='B'); commit(result)
    first = deepcopy(calls(result)); result['countries']['B']['available_manpower'] = PERSONNEL-1
    commit(result,provider='D',receiver='B')
    assert calls(result) == first and not pending(result,'D')
    groups['two_donors_same_recipient_recheck_explicit_changed_personnel_between_native_batches_without_auto_debit'] += 1
    result = state(); assert send(result); assert send(result,provider='D',receiver='B')
    assert reply(result) and reply(result,provider='D',receiver='B'); commit(result)
    first = deepcopy(calls(result)); result['countries']['D']['equipment_stock']['AA_Equipment'] = 49
    commit(result,provider='D',receiver='B')
    assert calls(result) == first and not pending(result,'D')
    groups['two_donors_same_recipient_recheck_explicit_changed_second_donor_stock_without_shared_escrow'] += 1
    result = state(); flags(result).update({'eon_foreign_cash_pending','eon_foreign_cash_live','eon_foreign_equipment_pending','eon_foreign_equipment_live','eon_foreign_equipment_packet_small_arms'})
    vars_(result).update({'eon_foreign_cash_partner':'C','eon_foreign_equipment_partner':'C'})
    other = unrelated(result); assert send(result) and reply(result); commit(result); assert_batch(result)
    assert unrelated(result) == other
    groups['existing_cash_and_equipment_offer_records_are_independent_and_unchanged'] += 1
    # Native primitives remain distinct adapter checks, never counted as gameplay scenarios.
    for archetype,count in EQUIPMENT.items():
        for stored in (0,count-1,count,count+1):
            result = state(); result['countries']['A']['equipment_stock'][archetype] = stored
            assert check(result,[('has_equipment','=',[(archetype,'>',str(count-1))])],actor='A') == (stored >= count)
            adapter_cases['five_equipment_stored_integer_query_boundaries'] += 1
    for stored in (0,PERSONNEL-1,PERSONNEL,PERSONNEL+1):
        result = state(); result['countries']['B']['available_manpower'] = stored
        assert check(result,[('has_manpower','>',str(PERSONNEL-1))],actor='B') == (stored >= PERSONNEL)
        adapter_cases['recipient_available_personnel_integer_query_boundaries'] += 1
    for controlled in (False,True):
        result = state(); result['states'][102]['controller'] = 'B' if controlled else 'C'
        assert check(result,[('any_owned_state','=',[('is_owned_and_controlled_by','=','PREV')])],actor='B') == controlled
        adapter_cases['owned_and_controlled_state_fixture_classification'] += 1
    for present in (False,True):
        result = state()
        if present: result['countries']['B']['templates'].add(TEMPLATE)
        assert check(result,[('has_template','=',TEMPLATE)],actor='B') == present
        adapter_cases['explicit_template_presence_fixture'] += 1
    result = state(); facts = resource_facts(result)
    effect(result,[('add_manpower','=','-5480'),('add_equipment_to_stockpile','=',[('type','=','Inf_equipment'),('amount','=','-1623')]),
                   ('division_template','=',[('name','=',TEMPLATE)]),('random_owned_controlled_state','=',[('create_unit','=',[('division','=',TEMPLATE),('owner','=','PREV'),('count','=','1')])])],actor='B',from_='A')
    assert len(calls(result)) == 4 and resource_facts(result) == facts
    adapter_cases['resource_template_and_create_observers_never_simulate_native_stock_personnel_template_or_unit_mutation'] += 1

def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--focus': focus(sys.argv[2])
    else:
        assert len(sys.argv) == 1, 'Unknown arguments'
        scenarios()
    paths = ['events/00_War_events.txt', 'common/scripted_effects/eon_defence_formation_effects.txt',
             'common/scripted_triggers/eon_defence_formation_triggers.txt', 'common/scripted_diplomatic_actions/eon_defence_formation_actions.txt',
             'common/on_actions/eon_defence_formation_on_actions.txt', 'events/eon_defence_formation_events.txt',
             'localisation/english/eon_defence_formation_l_english.yml', 'localisation/russian/eon_defence_formation_l_russian.yml',
             'localisation/english/MD_decisions_l_english.yml','localisation/russian/MD_decisions_l_russian.yml']
    print(json.dumps({'all_passed': True, 'actual_source_scenarios': sum(groups.values()), 'groups': dict(groups),
        'adapter_semantics_cases': sum(adapter_cases.values()), 'adapter_groups':dict(adapter_cases),
        'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths if (ROOT / path).exists()},
        'native_resource_mutation_simulated': False, 'native_unit_creation_success_proven': False,
        'proof_scope': 'ordered current-source national defence formation resource and create calls; not native unit completion'}, indent=2))

if __name__ == '__main__': main()
