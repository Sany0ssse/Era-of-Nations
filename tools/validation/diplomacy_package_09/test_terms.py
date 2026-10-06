"""Ordered actual-source negotiated mandate terms; not HOI4 runtime."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
import hashlib
import json

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '3b6efd83f9b1a62c7348f52d232ff0f08583a92c'
groups = Counter()
effect_path = ROOT / 'common/scripted_effects/eon_mediation_terms_effects.txt'
assert effect_path.exists(), 'RED: negotiated mediation terms helpers are not implemented'

# Load only the 08 definitions prefix. Its nested definitions loaders also stop
# before their first scenario loops; previous packages run/count separately.
source_executor_path = ROOT / 'tools/validation/diplomacy_package_08/test_mediation.py'
source_executor = source_executor_path.read_text(encoding='utf-8')
definition_boundary = '\n# Native targeted selection is free until its fresh complete_effect sends the'
assert source_executor.count(definition_boundary) == 1, 'Ordered mediation definition boundary changed'
source = {'__file__': str(source_executor_path), '__name__': 'terms_ordered_executor'}
exec(compile(source_executor.split(definition_boundary)[0], str(source_executor_path), 'exec'), source)
model = source['model']
ast, one = source['ast'], source['one']
context, switch = source['context'], source['switch']
assert one(ast(effect_path.read_text(encoding='utf-8-sig')), 'eon_mediation_terms_send_offer'), 'RED: literal negotiated offer helper is missing'

def read(path): return (ROOT / path).read_text(encoding='utf-8-sig')
model['effects'].update({key: body for key, operator, body in ast(read('common/scripted_effects/eon_mediation_terms_effects.txt'))})
model['capacity_triggers'].update({key: body for key, operator, body in ast(read('common/scripted_triggers/eon_mediation_terms_triggers.txt'))})
events = model['get_event_map'](read('events/eon_mediation_terms_events.txt'))
decisions = ast(read('common/decisions/eon_mediation_terms_decisions.txt'))
hooks = one(ast(read('common/on_actions/eon_mediation_terms_on_actions.txt')), 'on_actions')
check, pp = source['check'], source['pp']
execute_source = source['execute']
def execute(nodes, result, ctx):
    index = 0
    while index < len(nodes):
        key, operator, val = nodes[index]; index += 1
        grouped = [(key, operator, val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        if key == 'set_country_flag' and isinstance(val, list):
            flag = model['flag_name'](result, ctx, one(val, 'flag'))
            result.setdefault('current_timer_declarations', {})[(ctx['scope'], flag)] = source['loader']['value'](result, ctx, one(val, 'days'))
        elif key == 'clr_country_flag':
            flag = model['flag_name'](result, ctx, val)
            result.setdefault('current_timer_declarations', {}).pop((ctx['scope'], flag), None)
        execute_source(grouped, result, ctx)
# Each layer resolves recursive execution through these explicit module globals.
source['execute'] = source['loader']['execute'] = model['execute'] = execute

def effect(result, nodes, ctx, temporary=None):
    result['temp'] = dict(temporary or {})
    execute(nodes, result, ctx)
def helper(result, actor, name, other=None, temporary=None):
    effect(result, [('eon_mediation_terms_' + name, '=', 'yes')], context(actor, other), temporary)
def active_base(topic=1, initiator='A', opponent='B', mediator='C', result=None):
    result = result or source['state']()
    source['request'](result, topic, initiator, opponent, mediator)
    assert source['answer_mediator'](result, topic, initiator=initiator, opponent=opponent, mediator=mediator)
    assert source['answer_opponent'](result, topic, initiator=initiator, opponent=opponent, mediator=mediator)
    source['assert_session'](result, 3, topic, initiator, opponent, mediator)
    return result
def snapshot_base(result):
    return {actor: {'variables': {key: deepcopy(val) for key, val in data['variables'].items() if key.startswith('eon_mediation_') and not key.startswith('eon_mediation_terms_')},
                    'flags': {flag for flag in data['flags'] if flag.startswith('eon_mediation_') and not flag.startswith('eon_mediation_terms_')}}
            for actor, data in result['countries'].items()}
def snapshot_other_state(result):
    return {actor: {
        'variables': {key: deepcopy(val) for key, val in data['variables'].items() if not key.startswith('eon_mediation_terms_')},
        'flags': {flag for flag in data['flags'] if not flag.startswith('eon_mediation_terms_')},
        'arrays': deepcopy(data['arrays']), 'wars': deepcopy(data['wars']), 'ideas': deepcopy(data['ideas']),
        'faction': data['faction'], 'opinions': deepcopy(data['opinions']), 'overlord': data['overlord'],
        'co_war_partners': deepcopy(data['co_war_partners'])}
        for actor, data in result['countries'].items()}
def snapshot_external(result):
    return {actor: {**data,
                    'variables': {key: val for key, val in data['variables'].items() if not key.startswith('eon_mediation_')},
                    'flags': {flag for flag in data['flags'] if not flag.startswith('eon_mediation_')}}
            for actor, data in snapshot_other_state(result).items()}
def base_windows(result):
    return {actor: days for (actor, flag), days in result.get('current_timer_declarations', {}).items()
            if flag == 'eon_mediation_active_window' and flag in result['countries'][actor]['flags']}
def find(nodes, identity):
    found = []
    for key, operator, val in nodes:
        if key == identity: found.append(val)
        if isinstance(val, list): found.extend(find(val, identity))
    return found
def decision(result, identity, actor='A', force=False):
    found = find(decisions, identity); assert len(found) == 1, (identity, len(found))
    body = found[0]; ctx = context(actor)
    guards = [val for key, operator, val in body if key in ('allowed', 'visible', 'available')]
    ready = all(check(result, guard, ctx) for guard in guards)
    if ready or force: effect(result, one(body, 'complete_effect'), ctx)
    return ready
def offer(result, topic=1, duration=30, initiator='A', opponent='B', mediator='C'):
    assert decision(result, 'eon_mediation_terms_' + {1: 'deescalation', 2: 'humanitarian'}[topic] + '_' + str(duration), initiator)
    source['queued'](result, event_id(topic, duration, 1), mediator, initiator)
def event_id(topic, duration, stage):
    return 'eon_mediation_terms.' + str((10 if stage == 1 else 20) + (topic - 1) * 3 + (30, 60, 90).index(duration))
def option(identity, name):
    found = [val for key, operator, val in events[identity] if key == 'option' and one(val, 'name') == name]
    assert len(found) == 1, (identity, name)
    return found[0]
def option_effect(result, identity, name, actor, partner, force=False):
    body = option(identity, name); ctx = context(actor, partner)
    guards = [val for key, operator, val in body if key == 'trigger']
    ready = not guards or check(result, guards[0], ctx)
    if ready or force: effect(result, body, ctx)
    return ready
def response(result, topic=1, duration=30, stage=1, accept=True, initiator='A', opponent='B', mediator='C', force=False):
    identity = event_id(topic, duration, stage)
    actor, sender = (mediator, initiator) if stage == 1 else (opponent, mediator)
    result['events'].remove(source['queued'](result, identity, actor, sender))
    return option_effect(result, identity, 'eon_mediation_terms_accept' if accept else 'eon_mediation_terms_decline', actor, sender, force)
def terms_reserved(result, actor): return 'eon_mediation_terms_reserved' in result['countries'][actor]['flags']
def assert_terms(result, stage, topic=1, duration=30, initiator='A', opponent='B', mediator='C'):
    for actor in (initiator, opponent, mediator):
        data = result['countries'][actor]
        assert terms_reserved(result, actor)
        for key, wanted in (('a', initiator), ('b', opponent), ('m', mediator), ('topic', topic), ('duration', duration), ('stage', stage)):
            assert data['variables']['eon_mediation_terms_' + key] == wanted, (actor, key, wanted, data['variables'])
def native_daily(result, actor):
    effect(result, one(one(hooks, 'on_daily'), 'effect'), context(actor))

# Six literal agreements preserve the existing mandate through the first
# consent and replace its topic/window only after the second consent.
for topic in (1, 2):
    for duration in (30, 60, 90):
        result = active_base(); before = snapshot_other_state(result); before_external = snapshot_external(result)
        previous_windows = base_windows(result); before_pp = pp(result)
        offer(result, topic, duration); assert_terms(result, 1, topic, duration)
        assert snapshot_other_state(result) == before and base_windows(result) == previous_windows and pp(result) == before_pp
        assert response(result, topic, duration, 1); assert_terms(result, 2, topic, duration)
        assert snapshot_other_state(result) == before and base_windows(result) == previous_windows and pp(result) == before_pp
        assert response(result, topic, duration, 2)
        assert not any(terms_reserved(result, actor) for actor in ('A', 'B', 'C'))
        source['assert_session'](result, 3, topic)
        assert base_windows(result) == {'A': duration, 'B': duration, 'C': duration}
        assert snapshot_external(result) == before_external and pp(result) == before_pp
        assert not result.get('political_macro_calls')
        groups['six_literal_topics_and_exact_renewal_after_both_consents'] += 1

for topic in (1, 2):
    for duration in (30, 60, 90):
        for refusal_stage in (1, 2):
            result = active_base(); before = snapshot_other_state(result); windows = base_windows(result)
            offer(result, topic, duration)
            if refusal_stage == 2: assert response(result, topic, duration, 1)
            assert response(result, topic, duration, refusal_stage, accept=False)
            assert not any(terms_reserved(result, actor) for actor in ('A', 'B', 'C'))
            assert snapshot_other_state(result) == before and base_windows(result) == windows
            assert not any(flag.startswith('eon_mediation_terms_retired_pair@') for data in result['countries'].values() for flag in data['flags'])
            # This original refusal has consumed its modal. A new normal offer
            # is allowed without permanent singleton history or a false reset.
            offer(result, 3 - topic, 90 if duration != 90 else 30)
            assert_terms(result, 1, 3 - topic, 90 if duration != 90 else 30)
            groups['each_literal_mediator_or_opponent_refusal_keeps_old_mandate'] += 1

result = active_base()
for topic, duration in ((2, 60), (1, 90), (2, 30)):
    before = snapshot_external(result); before_pp = pp(result)
    offer(result, topic, duration); assert response(result, topic, duration, 1); assert response(result, topic, duration, 2)
    source['assert_session'](result, 3, topic)
    assert base_windows(result) == {'A': duration, 'B': duration, 'C': duration}
    assert snapshot_external(result) == before and pp(result) == before_pp
groups['successive_consumed_rounds_allow_legitimate_new_terms'] += 1

for stage in (1, 2):
    result = active_base(); offer(result, 2, 60)
    if stage == 2: assert response(result, 2, 60, 1)
    before = deepcopy(result['countries']); windows = base_windows(result); before_pp = pp(result)
    for actor in ('A', 'B', 'C'):
        assert not decision(result, 'eon_mediation_terms_deescalation_90', actor, force=True)
        assert result['countries'] == before and base_windows(result) == windows and pp(result) == before_pp
    groups['pending_second_offer_and_noninitiator_sends_are_inert'] += 1

for mutation in ('actor_ai', 'actor_dead', 'opponent_dead', 'mediator_dead', 'peace', 'mediator_subject', 'mediator_faction', 'mediator_cowar', 'actor_base_window', 'opponent_base_window', 'mediator_base_window', 'actor_terms_lock', 'opponent_terms_lock', 'mediator_terms_lock', 'retired_a_m', 'retired_m_a', 'retired_b_m', 'retired_m_b', 'wrong_initiator', 'pending_base'):
    result = active_base(); actor = 'A'
    if mutation == 'actor_ai': result['countries']['A']['ai'] = True
    elif mutation.endswith('dead'): result['countries'][{'actor_dead': 'A', 'opponent_dead': 'B', 'mediator_dead': 'C'}[mutation]]['exists'] = False
    elif mutation == 'peace': result['countries']['A']['wars'].clear(); result['countries']['B']['wars'].clear()
    elif mutation == 'mediator_subject': result['countries']['C']['overlord'] = 'D'
    elif mutation == 'mediator_faction': result['countries']['C']['faction'] = result['countries']['B']['faction'] = 'fixture_faction'
    elif mutation == 'mediator_cowar': result['countries']['C']['co_war_partners'].add('A')
    elif mutation.endswith('base_window'): result['countries'][{'actor_base_window': 'A', 'opponent_base_window': 'B', 'mediator_base_window': 'C'}[mutation]]['flags'].discard('eon_mediation_active_window')
    elif mutation.endswith('terms_lock'): result['countries'][{'actor_terms_lock': 'A', 'opponent_terms_lock': 'B', 'mediator_terms_lock': 'C'}[mutation]]['flags'].add('eon_mediation_terms_reserved')
    elif mutation.startswith('retired'):
        owner, peer = {'retired_a_m': ('A', 'C'), 'retired_m_a': ('C', 'A'), 'retired_b_m': ('B', 'C'), 'retired_m_b': ('C', 'B')}[mutation]
        result['countries'][owner]['flags'].add('eon_mediation_terms_retired_pair@' + peer)
    elif mutation == 'wrong_initiator': actor = 'B'
    else:
        for owner in ('A', 'B', 'C'): result['countries'][owner]['variables']['eon_mediation_phase'] = 2
    before = deepcopy(result['countries']); windows = base_windows(result); before_pp = pp(result)
    assert not decision(result, 'eon_mediation_terms_humanitarian_90', actor, force=True), mutation
    assert result['countries'] == before and base_windows(result) == windows and pp(result) == before_pp
    assert not any(item['id'].startswith('eon_mediation_terms.') for item in result['events'])
    groups['fresh_free_send_guards_active_human_neutrality_and_bilateral_quarantine'] += 1

for topic, duration in ((0, 30), (3, 60), (1, 0), (2, 45), (1, 120)):
    result = active_base(); before = deepcopy(result['countries']); windows = base_windows(result)
    helper(result, 'A', 'send_offer', temporary={'eon_mediation_terms_proposed_topic': topic, 'eon_mediation_terms_proposed_duration': duration})
    assert result['countries'] == before and base_windows(result) == windows
    groups['nonliteral_offer_inputs_cannot_open_or_change_mandate'] += 1

for stage, rendered_topic, rendered_duration, actor, sender in ((1, 1, 90, 'C', 'A'), (1, 2, 30, 'C', 'A'), (1, 2, 60, 'C', 'D'), (1, 2, 60, 'B', 'A'), (2, 1, 60, 'B', 'C'), (2, 2, 90, 'B', 'C'), (2, 2, 60, 'B', 'A'), (2, 2, 60, 'A', 'C')):
    result = active_base(); offer(result, 2, 60)
    if stage == 2: assert response(result, 2, 60, 1)
    before = deepcopy(result['countries']); windows = base_windows(result)
    for name in ('eon_mediation_terms_accept', 'eon_mediation_terms_decline'):
        option_effect(result, event_id(rendered_topic, rendered_duration, stage), name, actor, sender, force=True)
    assert result['countries'] == before and base_windows(result) == windows
    groups['wrong_literal_tuple_role_or_sender_callbacks_do_not_attach'] += 1

result = active_base(); offer(result, 2, 60); before = deepcopy(result['countries'])
option_effect(result, event_id(2, 60, 2), 'eon_mediation_terms_accept', 'B', 'C', force=True)
assert result['countries'] == before
assert response(result, 2, 60, 1); before = deepcopy(result['countries'])
option_effect(result, event_id(2, 60, 1), 'eon_mediation_terms_accept', 'C', 'A', force=True)
assert result['countries'] == before
groups['strict_two_consent_order_and_consumed_prior_stage_are_inert'] += 1

for stage in (1, 2):
    for actor in ('A', 'B', 'C'):
        result = active_base(); before = snapshot_other_state(result); windows = base_windows(result)
        offer(result, 2, 90)
        if stage == 2: assert response(result, 2, 90, 1)
        assert decision(result, 'eon_cancel_mediation_terms', actor)
        assert_terms(result, stage, 2, 90)
        assert all('eon_mediation_terms_cancelled' in result['countries'][owner]['flags'] for owner in ('A', 'B', 'C'))
        assert not decision(result, 'eon_mediation_terms_deescalation_30', force=True)
        assert not decision(result, 'eon_cancel_mediation_terms', actor, force=True)
        assert not response(result, 2, 90, stage, force=True)
        assert not any(terms_reserved(result, owner) for owner in ('A', 'B', 'C'))
        assert snapshot_other_state(result) == before and base_windows(result) == windows
        offer(result, 1, 30)
        groups['every_participant_cancel_keeps_lock_until_original_answer_consumed'] += 1

for stage in (1, 2):
    for invalidity in ('peace', 'mediator_subject', 'mediator_war', 'actor_base_window', 'opponent_terms_window', 'mediator_terms_window'):
        result = active_base(); offer(result, 2, 90)
        if stage == 2: assert response(result, 2, 90, 1)
        if invalidity == 'peace': result['countries']['A']['wars'].clear(); result['countries']['B']['wars'].clear()
        elif invalidity == 'mediator_subject': result['countries']['C']['overlord'] = 'D'
        elif invalidity == 'mediator_war': result['countries']['C']['wars'].add('A')
        elif invalidity == 'actor_base_window': result['countries']['A']['flags'].discard('eon_mediation_active_window')
        else: result['countries']['B' if invalidity.startswith('opponent') else 'C']['flags'].discard('eon_mediation_terms_response_window')
        before = snapshot_other_state(result); windows = base_windows(result)
        assert not response(result, 2, 90, stage, force=True)
        assert not any(terms_reserved(result, owner) for owner in ('A', 'B', 'C'))
        assert snapshot_other_state(result) == before and base_windows(result) == windows
        groups['consumed_original_answer_rechecks_base_and_overlay_windows'] += 1

for orphan in ('A', 'B', 'C'):
    result = active_base(); result['countries'][orphan]['flags'].add('eon_mediation_terms_cancelled')
    before_external = snapshot_external(result); before_pp = pp(result)
    offer(result, 2, 60)
    assert response(result, 2, 60, 1), ('An unreserved orphan cancellation poisons a fresh offer', orphan)
    assert response(result, 2, 60, 2)
    source['assert_session'](result, 3, 2)
    assert base_windows(result) == {'A': 60, 'B': 60, 'C': 60}
    assert snapshot_external(result) == before_external and pp(result) == before_pp
    groups['fresh_unreserved_record_initialization_clears_orphan_cancellation'] += 1

def ai_weight(result, identity, name, actor, partner):
    tree = one(option(identity, name), 'ai_chance'); weight = float(one(tree, 'factor'))
    result['temp'] = {}
    for key, operator, body in tree:
        if key != 'modifier': continue
        if source['trigger']([node for node in body if node[0] not in ('factor', 'add')], result, context(actor, partner)):
            for operation, op, operand in body:
                if operation == 'factor': weight *= source['loader']['value'](result, context(actor, partner), operand)
                elif operation == 'add': weight += source['loader']['value'](result, context(actor, partner), operand)
    return weight

for stage, hostile, expected in ((1, False, 3), (1, True, .5), (2, False, 4), (2, True, 1)):
    result = active_base(); offer(result, 1, 60)
    if stage == 1: result['countries']['C']['opinions'].update(A=-26 if hostile else 51, B=51)
    else:
        assert response(result, 1, 60, 1)
        result['countries']['B']['opinions']['C'] = -26 if hostile else 51
    actor, sender = ('C', 'A') if stage == 1 else ('B', 'C')
    identity = event_id(1, 60, stage)
    assert ai_weight(result, identity, 'eon_mediation_terms_accept', actor, sender) == expected, ('Terms AI does not retain existing mediation opinion weighting', stage, hostile)
    assert ai_weight(result, identity, 'eon_mediation_terms_decline', actor, sender) == 1
    groups['existing_mediation_ai_positive_and_hostile_opinion_weights'] += 1

def assert_terms_retired(result, initiator='A', opponent='B', mediator='C'):
    for owner, peer in ((initiator, mediator), (mediator, initiator), (opponent, mediator), (mediator, opponent)):
        assert 'eon_mediation_terms_retired_pair@' + peer in result['countries'][owner]['flags'], (owner, peer)
    assert not any(flag.startswith('eon_mediation_retired_pair@') for data in result['countries'].values() for flag in data['flags'])

for stage in (1, 2):
    for expired in ('A', 'B', 'C'):
        result = active_base(); offer(result, 2, 90)
        if stage == 2: assert response(result, 2, 90, 1)
        result['countries'][expired]['flags'].discard('eon_mediation_terms_response_window')
        before = snapshot_other_state(result); windows = base_windows(result)
        native_daily(result, 'C' if expired != 'C' else 'A')
        assert not any(terms_reserved(result, actor) for actor in ('A', 'B', 'C'))
        assert_terms_retired(result)
        assert snapshot_other_state(result) == before and base_windows(result) == windows
        assert not decision(result, 'eon_mediation_terms_deescalation_30', force=True)
        # Closing and reopening a base08 mandate is still permitted. Only the
        # unanswered09 response edges remain quarantined against the old event.
        assert source['action'](result, 'eon_withdraw_mediation', 'A', 'C'); source['clear_cooldown'](result)
        active_base(result=result); new_base = snapshot_other_state(result); new_windows = base_windows(result)
        assert not decision(result, 'eon_mediation_terms_humanitarian_60', force=True)
        assert not response(result, 2, 90, stage, force=True)
        assert snapshot_other_state(result) == new_base and base_windows(result) == new_windows
        groups['forced_overlay_expiry_retires_terms_only_and_preserves_future_base'] += 1

# The existing08 native withdrawal/annex paths call the first-line09 hook before
# any underlying country identity is erased. Test both overlay stages and roles.
for stage in (1, 2):
    for actor in ('A', 'B', 'C'):
        result = active_base(); offer(result, 2, 60)
        if stage == 2: assert response(result, 2, 60, 1)
        before = snapshot_external(result); before_pp = pp(result)
        assert source['action'](result, 'eon_withdraw_mediation', actor, 'C' if actor != 'C' else 'A')
        assert not any(terms_reserved(result, owner) or source['reserved'](result, owner) for owner in ('A', 'B', 'C'))
        assert_terms_retired(result)
        assert snapshot_external(result) == before and pp(result) == before_pp
        source['clear_cooldown'](result); active_base(result=result); current = snapshot_other_state(result)
        assert not response(result, 2, 60, stage, force=True)
        assert snapshot_other_state(result) == current
        groups['existing_native_participant_withdrawal_preclear_hook_keeps_old_terms_inert'] += 1

for hook in ('on_annex', 'on_subject_annexed'):
    for stage in (1, 2):
        for victim in ('A', 'B', 'C'):
            result = active_base(); offer(result, 1, 90)
            if stage == 2: assert response(result, 1, 90, 1)
            before = snapshot_external(result); before_pp = pp(result)
            result['countries'][victim]['exists'] = False
            source['native_hook'](result, hook, 'D' if hook == 'on_annex' else victim, victim if hook == 'on_annex' else 'D')
            assert not any(terms_reserved(result, actor) or source['reserved'](result, actor) for actor in ('A', 'B', 'C'))
            assert_terms_retired(result)
            result['countries'][victim]['exists'] = True; source['clear_cooldown'](result)
            active_base(result=result); current = snapshot_other_state(result)
            assert not response(result, 1, 90, stage, force=True)
            assert snapshot_other_state(result) == current
            assert snapshot_external(result) == {**before, 'A': {**before['A'], 'variables': {**before['A']['variables'], 'political_power': before_pp['A'] - 20}}}
            groups['native_annex_all_participants_both_terms_stages_preclear_hook'] += 1

for order in ('terms_first', 'base_first'):
    for stage in (1, 2):
        result = active_base(); offer(result, 2, 90)
        if stage == 2: assert response(result, 2, 90, 1)
        result['countries']['B']['flags'].discard('eon_mediation_active_window')
        before = snapshot_external(result); before_pp = pp(result)
        if order == 'terms_first':
            base_before = snapshot_base(result); native_daily(result, 'C')
            assert snapshot_base(result) == base_before
            source['native_hook'](result, 'on_daily', 'A')
        else:
            source['native_hook'](result, 'on_daily', 'A'); native_daily(result, 'C')
        assert not any(terms_reserved(result, actor) or source['reserved'](result, actor) for actor in ('A', 'B', 'C'))
        assert_terms_retired(result)
        assert snapshot_external(result) == before and pp(result) == before_pp
        groups['base_and_overlay_expiry_native_daily_orders_preserve_identity_before_clear'] += 1

for defect in ('stage', 'topic', 'duration', 'member', 'missing_reservation', 'base_identity'):
    result = active_base(); offer(result, 2, 60)
    if defect == 'stage': result['countries']['B']['variables']['eon_mediation_terms_stage'] = 1.5
    elif defect == 'topic': result['countries']['C']['variables']['eon_mediation_terms_topic'] = 1
    elif defect == 'duration': result['countries']['B']['variables']['eon_mediation_terms_duration'] = 90
    elif defect == 'member': result['countries']['C']['variables']['eon_mediation_terms_m'] = 'D'
    elif defect == 'missing_reservation': result['countries']['C']['flags'].discard('eon_mediation_terms_reserved')
    else: result['countries']['C']['variables']['eon_mediation_party_b'] = 'D'
    before = deepcopy(result['countries']); before_base = snapshot_base(result); windows = base_windows(result)
    option_effect(result, event_id(2, 60, 1), 'eon_mediation_terms_accept', 'C', 'A', force=True)
    # A structural mismatch cannot silently rewrite the base. If only the base
    # changed, its consumed invalid response may release the overlay normally.
    assert snapshot_base(result) == before_base and base_windows(result) == windows
    native_daily(result, 'A')
    if defect != 'base_identity': assert_terms_retired(result)
    assert snapshot_base(result) == before_base and base_windows(result) == windows
    groups['corrupt_overlay_or_base_never_commits_into_another_identity'] += 1

for operation in ('daily', 'release_record', 'retire_response_edges', 'before_base_clear'):
    result = active_base(); offer(result, 2, 60)
    result['countries']['D']['variables'].update({key: val for key, val in result['countries']['A']['variables'].items() if key.startswith('eon_mediation_terms_')})
    result['countries']['D']['flags'].update({'eon_mediation_terms_reserved', 'eon_mediation_terms_response_window'})
    original = {actor: deepcopy(result['countries'][actor]) for actor in ('A', 'B', 'C')}
    if operation == 'daily': native_daily(result, 'D')
    else: helper(result, 'D', operation)
    assert {actor: result['countries'][actor] for actor in ('A', 'B', 'C')} == original
    if operation != 'retire_response_edges': assert not terms_reserved(result, 'D')
    groups['stray_nonparticipant_overlay_cannot_release_or_retire_owned_records'] += 1

def selected_desc(result, identity, actor, sender):
    selected = []
    for key, operator, val in events[identity]:
        if key != 'desc': continue
        if isinstance(val, str): selected.append(val)
        elif check(result, one(val, 'trigger'), context(actor, sender)): selected.append(one(val, 'text'))
    assert len(selected) == 1, ('Terms descriptions must be exclusive', identity, selected)
    return selected[0]

for stage in (1, 2):
    for topic in (1, 2):
        for duration in (30, 60, 90):
            result = active_base(); offer(result, topic, duration)
            if stage == 2: assert response(result, topic, duration, 1)
            actor, sender = ('C', 'A') if stage == 1 else ('B', 'C')
            identity = event_id(topic, duration, stage)
            role = 'mediator' if stage == 1 else 'opponent'
            expected = 'eon_mediation_terms_' + role + '_' + {1: 'deescalation', 2: 'humanitarian'}[topic] + '_' + str(duration) + '_desc'
            assert selected_desc(result, identity, actor, sender) == expected
            assert ai_weight(result, identity, 'eon_mediation_terms_accept', actor, sender) == 2
            assert ai_weight(result, identity, 'eon_mediation_terms_decline', actor, sender) == 1
            # Another literal's unconsumed UI cannot silently adopt these terms.
            wrong_duration = 90 if duration != 90 else 30
            assert selected_desc(result, event_id(topic, wrong_duration, stage), actor, sender) == 'eon_mediation_terms_stale_desc'
            assert ai_weight(result, event_id(topic, wrong_duration, stage), 'eon_mediation_terms_accept', actor, sender) == 0
            result['countries']['A']['flags'].add('eon_mediation_terms_cancelled')
            assert selected_desc(result, identity, actor, sender) == 'eon_mediation_terms_cancelled_desc'
            assert ai_weight(result, identity, 'eon_mediation_terms_accept', actor, sender) == 0
            assert ai_weight(result, identity, 'eon_mediation_terms_decline', actor, sender) == 1
            groups['all_literal_event_descriptions_ai_invalidity_and_nonzero_decline'] += 1

for stage in (1, 2):
    result = active_base(); offer(result, 2, 90)
    if stage == 2: assert response(result, 2, 90, 1)
    result['countries']['A']['flags'].discard('eon_mediation_terms_response_window')
    native_daily(result, 'C')
    # Same08 war can use a different mediator and negotiate a fresh different09
    # identity, while the original unconsumed modal stays in the event queue.
    assert source['action'](result, 'eon_withdraw_mediation', 'A', 'C'); source['clear_cooldown'](result)
    active_base(mediator='D', result=result); offer(result, 1, 60, mediator='D')
    assert decision(result, 'eon_cancel_mediation_terms', 'A')
    current = deepcopy(result['countries']); windows = base_windows(result)
    old_actor, old_sender = ('C', 'A') if stage == 1 else ('B', 'C')
    assert selected_desc(result, event_id(2, 90, stage), old_actor, old_sender) == 'eon_mediation_terms_stale_desc'
    assert not response(result, 2, 90, stage, force=True)
    assert result['countries'] == current and base_windows(result) == windows
    groups['old_unconsumed_terms_do_not_read_new_cancelled_identity'] += 1

result = active_base(); offer(result, 2, 60); assert response(result, 2, 60, 1); assert response(result, 2, 60, 2)
offer(result, 1, 90); before = deepcopy(result['countries']); windows = base_windows(result)
for number in range(30, 36): option_effect(result, 'eon_mediation_terms.' + str(number), 'eon_mediation_terms_ack', 'A', 'C')
assert result['countries'] == before and base_windows(result) == windows
groups['all_six_static_acknowledgements_cannot_renew_later_mandate'] += 1

def six_country_state():
    result = source['state']()
    for extra in ('E', 'F'): result['countries'][extra] = deepcopy(result['countries']['C'])
    for data in result['countries'].values(): data['opinions'].update(E=0, F=0)
    result['countries']['D']['wars'].add('E'); result['countries']['E']['wars'].add('D')
    return result

for cleanup in ('terms_expiry', 'base_withdrawal', 'base_annex', 'base_subject'):
    result = six_country_state(); active_base(result=result); active_base(2, 'D', 'E', 'F', result)
    offer(result, 2, 90); offer(result, 1, 60, 'D', 'E', 'F')
    untouched = {actor: deepcopy(result['countries'][actor]) for actor in ('D', 'E', 'F')}
    second_windows = {actor: days for actor, days in base_windows(result).items() if actor in ('D', 'E', 'F')}
    if cleanup == 'terms_expiry': result['countries']['B']['flags'].discard('eon_mediation_terms_response_window'); native_daily(result, 'A')
    elif cleanup == 'base_withdrawal': assert source['action'](result, 'eon_withdraw_mediation', 'C', 'A')
    else:
        result['countries']['C']['exists'] = False
        source['native_hook'](result, 'on_annex' if cleanup == 'base_annex' else 'on_subject_annexed', 'D' if cleanup == 'base_annex' else 'C', 'C' if cleanup == 'base_annex' else 'D')
    assert not any(terms_reserved(result, actor) for actor in ('A', 'B', 'C'))
    assert_terms_retired(result)
    assert {actor: result['countries'][actor] for actor in ('D', 'E', 'F')} == untouched
    assert {actor: days for actor, days in base_windows(result).items() if actor in ('D', 'E', 'F')} == second_windows
    assert response(result, 1, 60, 1, initiator='D', opponent='E', mediator='F')
    assert response(result, 1, 60, 2, initiator='D', opponent='E', mediator='F')
    source['assert_session'](result, 3, 1, 'D', 'E', 'F')
    assert all(base_windows(result)[actor] == 60 for actor in ('D', 'E', 'F'))
    groups['independent_six_country_overlay_and_base_survive_other_cleanup'] += 1

result = source['state']()
for actor, peer in (('A', 'D'), ('D', 'A')):
    result['countries'][actor]['flags'].update({'eon_consultation_reserved', 'eon_consultation_active', 'eon_consultation_active_window'})
    result['countries'][actor]['variables'].update(eon_consultation_partner=peer, eon_consultation_topic=3)
result['countries']['A']['variables'].update(eon_aid_partner='D', eon_aid_amount=15, eon_aid_escrow=15, eon_support_refund_due=11,
                                           pending_assume_debt_offer='B', assuming_debt_value=40, assuming_debt_repayment_value=10)
result['countries']['A']['flags'].update({'eon_aid_reserved', 'eon_aid_outgoing', 'trade_agreement@D', 'mutual_investment_treaty_@D'})
result['countries']['D']['variables'].update(eon_aid_partner='A', eon_aid_amount=15)
result['countries']['D']['flags'].update({'eon_aid_reserved', 'eon_aid_incoming'})
active_base(result=result); before = snapshot_external(result); before_pp = pp(result)
result['countries']['A']['variables']['political_power'] = 0
before['A']['variables']['political_power'] = 0; before_pp['A'] = 0
offer(result, 2, 90); assert response(result, 2, 90, 1); assert response(result, 2, 90, 2)
assert snapshot_external(result) == before and pp(result) == before_pp
assert not result.get('political_macro_calls')
groups['free_terms_renewal_preserves_aid_debt_energy_treaties_and_zero_pp'] += 1

source_paths = ['common/scripted_effects/eon_mediation_terms_effects.txt', 'common/scripted_triggers/eon_mediation_terms_triggers.txt',
                'common/decisions/eon_mediation_terms_decisions.txt', 'common/decisions/categories/eon_mediation_terms_categories.txt',
                'common/on_actions/eon_mediation_terms_on_actions.txt', 'events/eon_mediation_terms_events.txt',
                'localisation/english/eon_mediation_terms_l_english.yml', 'localisation/russian/eon_mediation_terms_l_russian.yml',
                'common/scripted_effects/eon_mediation_effects.txt']

print(json.dumps({'all_passed': True, 'actual_source_scenarios': sum(groups.values()),
                  'adapter_semantics_cases': 0, 'total_cases': sum(groups.values()),
                  'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source_paths},
                  'groups': groups, 'baseline': BASELINE,
                  'proof_scope': 'ordered actual-source negotiated mediation terms with supplied native facts',
                  'not_proven': ['native callbacks and timers', 'GUI', 'save/load', 'campaign']}, indent=2))
