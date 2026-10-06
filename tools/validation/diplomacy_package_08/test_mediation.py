"""Ordered source proof for consent-based mediation, not HOI4 runtime."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
import hashlib
import json

ROOT = Path(__file__).resolve().parents[3]
BASELINE = 'b86a187f8ff3dfc88a577db4b2c52525fd5cf2fd'
groups = Counter()
effect_path = ROOT / 'common/scripted_effects/eon_mediation_effects.txt'
assert effect_path.exists(), 'RED: consent-based mediation lifecycle helpers are not implemented'

# Definitions only: loading this prefix never executes 07's scenario loops.
source_executor_path = ROOT / 'tools/validation/diplomacy_package_07/test_consultations.py'
source_executor = source_executor_path.read_text(encoding='utf-8')
definition_boundary = '\n# Native NOT is NOR for its child predicates.'
assert source_executor.count(definition_boundary) == 1, 'Ordered executor definition boundary changed'
loader = {'__file__': str(source_executor_path), '__name__': 'mediation_ordered_executor'}
exec(compile(source_executor.split(definition_boundary)[0], str(source_executor_path), 'exec'), loader)
model = loader['model']
ast, one = loader['ast'], loader['one']
context, switch = loader['context'], loader['switch']
trigger, execute = loader['trigger'], loader['execute']
assert one(ast(effect_path.read_text(encoding='utf-8-sig')), 'eon_mediation_prepare_draft'), 'RED: mediation draft helper is missing'

source_trigger = trigger
source_compare = loader['compare']
def compare(left, operator, right):
    if operator not in ('=', '==', '!='):
        if isinstance(left, str) and left in ('A', 'B', 'C', 'D', 'E', 'F'): left = ord(left) - ord('A') + 1
        if isinstance(right, str) and right in ('A', 'B', 'C', 'D', 'E', 'F'): right = ord(right) - ord('A') + 1
    return source_compare(left, operator, right)
loader['compare'] = model['compare'] = compare

def trigger(nodes, result, ctx):
    index = 0
    while index < len(nodes):
        key, operator, val = nodes[index]; index += 1
        grouped = [(key, operator, val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        data = result['countries'][ctx['scope']]
        if key == 'has_war': passed = bool(data['wars']) == (val == 'yes')
        elif key == 'is_subject': passed = (data['overlord'] is not None) == (val == 'yes')
        elif key == 'has_war_together_with':
            # Shared participation in a native war is supplied explicitly; two
            # countries' common enemy alone does not prove a shared war object.
            passed = model['country_ref'](result, ctx, val) in data['co_war_partners']
        else: passed = source_trigger(grouped, result, ctx)
        if not passed: return False
    return True
loader['trigger'] = model['trigger'] = trigger

def read(path): return (ROOT / path).read_text(encoding='utf-8-sig')

model['effects'].update({key: body for key, operator, body in ast(read('common/scripted_effects/eon_mediation_effects.txt'))})
model['capacity_triggers'].update({key: body for key, operator, body in ast(read('common/scripted_triggers/eon_mediation_triggers.txt'))})
actions = one(ast(read('common/scripted_diplomatic_actions/eon_mediation_actions.txt')), 'scripted_diplomatic_actions')
events = model['get_event_map'](read('events/eon_mediation_events.txt'))
hooks = one(ast(read('common/on_actions/eon_mediation_on_actions.txt')), 'on_actions')
decisions = ast(read('common/decisions/eon_mediation_decisions.txt'))

def state():
    result = loader['state']()
    result['countries']['A']['wars'].add('B')
    result['countries']['B']['wars'].add('A')
    for data in result['countries'].values():
        data['overlord'] = None; data['co_war_partners'] = set()
    return result

def snapshot_other_state(result):
    return {actor: {
        'variables': {key: deepcopy(val) for key, val in data['variables'].items() if not key.startswith('eon_mediation_') and key != 'political_power'},
        'flags': {flag for flag in data['flags'] if not flag.startswith('eon_mediation_')},
        'arrays': deepcopy(data['arrays']), 'wars': deepcopy(data['wars']), 'ideas': deepcopy(data['ideas']),
        'faction': data['faction'], 'opinions': deepcopy(data['opinions']), 'overlord': data['overlord'],
        'co_war_partners': deepcopy(data['co_war_partners'])}
        for actor, data in result['countries'].items()}

def pp(result): return {actor: data['variables']['political_power'] for actor, data in result['countries'].items()}
def check(result, nodes, ctx, temporary=None):
    result['temp'] = dict(temporary or {})
    return trigger(nodes, result, ctx)
def effect(result, nodes, ctx, temporary=None):
    result['temp'] = dict(temporary or {})
    execute(nodes, result, ctx)
def helper(result, actor, name, other=None, temporary=None):
    effect(result, [('eon_mediation_' + name, '=', 'yes')], context(actor, other), temporary)

def action(result, name, actor='A', partner='C', force=False):
    body = one(actions, name); ctx = context(actor, scope=partner)
    ready = all(check(result, one(body, key), ctx) for key in ('allowed', 'visible', 'selectable', 'can_be_sent'))
    if ready or force: effect(result, one(body, 'complete_effect'), ctx)
    return ready

def find(nodes, identity):
    found = []
    for key, operator, val in nodes:
        if key == identity: found.append(val)
        if isinstance(val, list): found.extend(find(val, identity))
    return found

def decision(result, identity, actor='A', opponent='B', force=False):
    found = find(decisions, identity); assert len(found) == 1, (identity, len(found))
    body = found[0]; ctx = context(actor, opponent)
    guards = [val for key, operator, val in body if key in ('allowed', 'visible', 'target_root_trigger', 'target_trigger', 'available')]
    ready = all(check(result, guard, ctx) for guard in guards)
    if ready or force: effect(result, one(body, 'complete_effect'), ctx)
    return ready

def queued(result, identity, target, sender):
    found = [item for item in result['events'] if item == {'target': target, 'id': identity, 'from': sender}]
    assert len(found) == 1, (identity, target, sender, result['events'])
    return found[0]

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

def native_hook(result, name, actor, partner=None):
    effect(result, one(one(hooks, name), 'effect'), context(actor, partner))

def reserved(result, actor): return 'eon_mediation_reserved' in result['countries'][actor]['flags']
def clear_cooldown(result):
    for data in result['countries'].values():
        data['flags'] = {flag for flag in data['flags'] if not flag.startswith('eon_mediation_recent_contact@')}

def mediation_snapshot(result):
    return {actor: {'variables': {key: deepcopy(val) for key, val in data['variables'].items() if key.startswith('eon_mediation_')},
                    'flags': {flag for flag in data['flags'] if flag.startswith('eon_mediation_')}}
            for actor, data in result['countries'].items()}

TOPICS = {1: 'deescalation', 2: 'humanitarian'}
def draft(result, initiator='A', mediator='C'):
    assert action(result, 'eon_request_war_mediation', initiator, mediator)

def request(result, topic=1, initiator='A', opponent='B', mediator='C'):
    draft(result, initiator, mediator)
    assert decision(result, 'eon_select_mediation_' + TOPICS[topic] + '_opponent', initiator, opponent)
    queued(result, 'eon_mediation.' + str(9 + topic), mediator, initiator)

def answer_mediator(result, topic=1, accept=True, initiator='A', opponent='B', mediator='C', force=False):
    identity = 'eon_mediation.' + str(9 + topic)
    result['events'].remove(queued(result, identity, mediator, initiator))
    return option_effect(result, identity, 'eon_mediation_accept' if accept else 'eon_mediation_decline', mediator, initiator, force)

def answer_opponent(result, topic=1, accept=True, initiator='A', opponent='B', mediator='C', force=False):
    identity = 'eon_mediation.' + str(19 + topic)
    result['events'].remove(queued(result, identity, opponent, mediator))
    return option_effect(result, identity, 'eon_mediation_accept' if accept else 'eon_mediation_decline', opponent, mediator, force)

def assert_session(result, phase, topic=1, initiator='A', opponent='B', mediator='C'):
    members = (initiator, mediator) if phase == 0 else (initiator, opponent, mediator)
    for actor in members:
        data = result['countries'][actor]
        assert reserved(result, actor), (actor, phase)
        assert data['variables']['eon_mediation_party_a'] == initiator
        assert data['variables']['eon_mediation_party_b'] == (0 if phase == 0 else opponent)
        assert data['variables']['eon_mediation_mediator'] == mediator
        assert data['variables']['eon_mediation_phase'] == phase
        assert data['variables']['eon_mediation_topic'] == (0 if phase == 0 else topic)

def selected_desc(result, identity, actor, partner):
    selected = []
    for key, operator, val in events[identity]:
        if key != 'desc': continue
        if isinstance(val, str): selected.append(val)
        elif check(result, one(val, 'trigger'), context(actor, partner)): selected.append(one(val, 'text'))
    assert len(selected) == 1, ('Mediation descriptions must be exclusive', identity, selected)
    return selected[0]

def ai_weight(result, identity, name, actor, partner):
    tree = one(option(identity, name), 'ai_chance'); weight = float(one(tree, 'factor'))
    result['temp'] = {}
    for key, operator, body in tree:
        if key != 'modifier': continue
        if trigger([node for node in body if node[0] not in ('factor', 'add')], result, context(actor, partner)):
            for operation, op, operand in body:
                if operation == 'factor': weight *= loader['value'](result, context(actor, partner), operand)
                elif operation == 'add': weight += loader['value'](result, context(actor, partner), operand)
    return weight

# Native targeted selection is free until its fresh complete_effect sends the
# actual request. Fractional political effort below20 cannot cover exact20.
for effort in (19, 19.01, 19.99, 20):
    result = state(); before = snapshot_other_state(result); draft(result)
    result['countries']['A']['variables']['political_power'] = effort
    before_pp = pp(result)
    available = decision(result, 'eon_select_mediation_deescalation_opponent', force=True)
    assert available == (effort >= 20), ('Fractional PP can fund an exact20 cost', effort, available)
    assert pp(result) == {**before_pp, 'A': effort - 20 if effort >= 20 else effort}
    assert snapshot_other_state(result) == before
    if effort >= 20: assert_session(result, 1)
    else: assert_session(result, 0)
    groups['exact_twenty_effort_fractional_boundary'] += 1

# Each literal topic needs both explicit consents. Neither consent is a native
# peace action: the original war and independent economic state stay intact.
for topic in (1, 2):
    for outcome in ('mediator_refuses', 'opponent_refuses', 'both_accept'):
        result = state(); before = snapshot_other_state(result); before_pp = pp(result)
        draft(result); assert_session(result, 0)
        assert not reserved(result, 'B') and pp(result) == before_pp and not result['events']
        for actor in ('A', 'C'): assert (actor, 'eon_mediation_draft_window', 7) in result['timer_declarations']
        assert decision(result, 'eon_select_mediation_' + TOPICS[topic] + '_opponent')
        assert_session(result, 1, topic)
        assert pp(result) == {**before_pp, 'A': before_pp['A'] - 20}
        for actor in ('A', 'B', 'C'): assert (actor, 'eon_mediation_response_window', 30) in result['timer_declarations']
        for actor, other in (('A', 'C'), ('C', 'A'), ('B', 'C'), ('C', 'B')):
            assert (actor, 'eon_mediation_recent_contact@' + other, 90) in result['timer_declarations']
        assert answer_mediator(result, topic, outcome != 'mediator_refuses')
        if outcome == 'mediator_refuses':
            assert not any(reserved(result, actor) for actor in ('A', 'B', 'C'))
            assert not any(item['id'] in ('eon_mediation.20', 'eon_mediation.21') for item in result['events'])
        else:
            assert_session(result, 2, topic)
            assert answer_opponent(result, topic, outcome == 'both_accept')
            if outcome == 'both_accept':
                assert_session(result, 3, topic)
                for actor in ('A', 'B', 'C'): assert (actor, 'eon_mediation_active_window', 30) in result['timer_declarations']
            else: assert not any(reserved(result, actor) for actor in ('A', 'B', 'C'))
        assert snapshot_other_state(result) == before and pp(result) == {**before_pp, 'A': before_pp['A'] - 20}
        assert not result.get('political_macro_calls')
        settled = deepcopy(result['countries'])
        option_effect(result, 'eon_mediation.' + str(9 + topic), 'eon_mediation_accept', 'C', 'A', force=True)
        option_effect(result, 'eon_mediation.' + str(19 + topic), 'eon_mediation_accept', 'B', 'C', force=True)
        assert result['countries'] == settled
        groups['literal_two_consent_nonbinding_cycle'] += 1

for mutation in ('actor_ai', 'actor_dead', 'actor_peace', 'mediator_dead', 'mediator_subject', 'mediator_war', 'mediator_cowar', 'mediator_faction', 'actor_lock', 'mediator_lock', 'actor_retired', 'mediator_retired', 'actor_cooldown', 'mediator_cooldown', 'self'):
    result = state(); actor, mediator = 'A', 'C'
    if mutation == 'actor_ai': result['countries']['A']['ai'] = True
    elif mutation == 'actor_dead': result['countries']['A']['exists'] = False
    elif mutation == 'actor_peace': result['countries']['A']['wars'].clear()
    elif mutation == 'mediator_dead': result['countries']['C']['exists'] = False
    elif mutation == 'mediator_subject': result['countries']['C']['overlord'] = 'D'
    elif mutation == 'mediator_war': result['countries']['C']['wars'].add('A')
    elif mutation == 'mediator_cowar': result['countries']['C']['co_war_partners'].add('A')
    elif mutation == 'mediator_faction': result['countries']['C']['faction'] = result['countries']['A']['faction'] = 'fixture_faction'
    elif mutation.endswith('lock'): result['countries']['A' if mutation.startswith('actor') else 'C']['flags'].add('eon_mediation_reserved')
    elif mutation.endswith('retired'): result['countries']['A' if mutation.startswith('actor') else 'C']['flags'].add('eon_mediation_retired_pair@' + ('C' if mutation.startswith('actor') else 'A'))
    elif mutation.endswith('cooldown'): result['countries']['A' if mutation.startswith('actor') else 'C']['flags'].add('eon_mediation_recent_contact@' + ('C' if mutation.startswith('actor') else 'A'))
    else: mediator = actor
    before = deepcopy(result['countries']); before_pp = pp(result)
    assert not action(result, 'eon_request_war_mediation', actor, mediator, force=True), mutation
    assert result['countries'] == before and pp(result) == before_pp and not result['events']
    groups['fresh_native_draft_human_war_neutrality_and_pair_gates'] += 1

for mutation in ('actor_ai', 'actor_dead', 'opponent_dead', 'mediator_dead', 'actor_peace', 'opponent_peace', 'opponent_lock', 'mediator_subject', 'mediator_war_a', 'mediator_war_b', 'mediator_cowar_a', 'mediator_cowar_b', 'mediator_faction_a', 'mediator_faction_b', 'actor_window', 'mediator_window', 'actor_retired', 'opponent_retired', 'mediator_retired', 'opponent_cooldown', 'self_opponent', 'mediator_opponent'):
    result = state(); draft(result); opponent = 'B'
    if mutation == 'actor_ai': result['countries']['A']['ai'] = True
    elif mutation.endswith('dead'): result['countries'][{'actor_dead': 'A', 'opponent_dead': 'B', 'mediator_dead': 'C'}[mutation]]['exists'] = False
    elif mutation.endswith('peace'): result['countries']['A' if mutation.startswith('actor') else 'B']['wars'].clear()
    elif mutation == 'opponent_lock': result['countries']['B']['flags'].add('eon_mediation_reserved')
    elif mutation == 'mediator_subject': result['countries']['C']['overlord'] = 'D'
    elif mutation.startswith('mediator_war'): result['countries']['C']['wars'].add('A' if mutation.endswith('_a') else 'B')
    elif mutation.startswith('mediator_cowar'): result['countries']['C']['co_war_partners'].add('A' if mutation.endswith('_a') else 'B')
    elif mutation.startswith('mediator_faction'): result['countries']['C']['faction'] = result['countries']['A' if mutation.endswith('_a') else 'B']['faction'] = 'fixture_faction'
    elif mutation.endswith('window'): result['countries']['A' if mutation.startswith('actor') else 'C']['flags'].discard('eon_mediation_draft_window')
    elif mutation.endswith('retired'): result['countries'][{'actor_retired': 'A', 'opponent_retired': 'B', 'mediator_retired': 'C'}[mutation]]['flags'].add('eon_mediation_retired_pair@' + ('B' if mutation == 'mediator_retired' else 'C'))
    elif mutation == 'opponent_cooldown': result['countries']['B']['flags'].add('eon_mediation_recent_contact@C')
    elif mutation == 'self_opponent': opponent = 'A'
    else: opponent = 'C'
    before = deepcopy(result['countries']); before_pp = pp(result)
    assert not decision(result, 'eon_select_mediation_deescalation_opponent', opponent=opponent, force=True), mutation
    assert result['countries'] == before and pp(result) == before_pp and not result['events']
    groups['rendered_targeted_selection_fresh_actual_scope_gates'] += 1

result = state(); draft(result); before = deepcopy(result['countries']); before_pp = pp(result)
helper(result, 'A', 'send_request', 'B', {'eon_mediation_proposed_topic': 99})
assert result['countries'] == before and pp(result) == before_pp and not result['events']
groups['nonliteral_topic_cannot_send_or_spend'] += 1

# Before the first consent, none of the three participants can overwrite the
# current triple. The opponent's own event cannot be accepted before M agrees.
result = state(); request(result); current = deepcopy(result['countries'])
for actor, other in (('A', 'D'), ('B', 'D'), ('C', 'D'), ('D', 'C')):
    assert not action(result, 'eon_request_war_mediation', actor, other, force=True)
    assert result['countries'] == current
assert not decision(result, 'eon_select_mediation_humanitarian_opponent', force=True)
option_effect(result, 'eon_mediation.20', 'eon_mediation_accept', 'B', 'C', force=True)
assert result['countries'] == current
groups['serialized_triple_crossed_requests_and_consent_order'] += 1

for phase, identity, actor, sender in ((1, 11, 'C', 'A'), (1, 10, 'C', 'D'), (1, 10, 'B', 'A'), (2, 21, 'B', 'C'), (2, 20, 'B', 'A'), (2, 20, 'A', 'C'), (2, 10, 'C', 'A')):
    result = state(); request(result)
    if phase == 2: assert answer_mediator(result)
    before = deepcopy(result['countries']); before_pp = pp(result)
    option_effect(result, 'eon_mediation.' + str(identity), 'eon_mediation_accept', actor, sender, force=True)
    option_effect(result, 'eon_mediation.' + str(identity), 'eon_mediation_decline', actor, sender, force=True)
    assert result['countries'] == before and pp(result) == before_pp
    assert_session(result, phase)
    groups['wrong_topic_role_sender_and_prior_phase_callback'] += 1

for phase in (0, 1, 2, 3):
    for actor in (('A', 'C') if phase == 0 else ('A', 'B', 'C')):
        result = state()
        if phase == 0: draft(result)
        else:
            request(result)
            if phase >= 2: assert answer_mediator(result)
            if phase == 3: assert answer_opponent(result)
        before = snapshot_other_state(result); before_pp = pp(result)
        peer = 'C' if actor != 'C' else 'A'
        assert action(result, 'eon_withdraw_mediation', actor, peer)
        if phase in (1, 2):
            assert_session(result, phase)
            assert all('eon_mediation_cancelled' in result['countries'][country]['flags'] for country in ('A', 'B', 'C'))
            assert not action(result, 'eon_request_war_mediation', 'A', 'D', force=True)
            assert not action(result, 'eon_withdraw_mediation', actor, peer, force=True)
            if phase == 1: assert not answer_mediator(result, force=True)
            else: assert not answer_opponent(result, force=True)
        assert not any(reserved(result, country) for country in ('A', 'B', 'C'))
        assert snapshot_other_state(result) == before and pp(result) == before_pp
        assert not any(flag.startswith('eon_mediation_retired_pair@') for data in result['countries'].values() for flag in data['flags'])
        groups['every_participant_withdraws_at_each_legitimate_phase'] += 1

for phase in (1, 2):
    for mutation in ('peace', 'mediator_subject', 'mediator_faction_a', 'mediator_faction_b', 'mediator_cowar_a', 'mediator_cowar_b', 'mediator_war_a', 'mediator_war_b', 'actor_window', 'opponent_window', 'mediator_window', 'cancelled_actor', 'cancelled_opponent', 'cancelled_mediator'):
        result = state(); request(result)
        if phase == 2: assert answer_mediator(result)
        if mutation == 'peace': result['countries']['A']['wars'].discard('B'); result['countries']['B']['wars'].discard('A')
        elif mutation == 'mediator_subject': result['countries']['C']['overlord'] = 'D'
        elif mutation.startswith('mediator_faction'): result['countries']['C']['faction'] = result['countries']['A' if mutation.endswith('_a') else 'B']['faction'] = 'fixture_faction'
        elif mutation.startswith('mediator_cowar'): result['countries']['C']['co_war_partners'].add('A' if mutation.endswith('_a') else 'B')
        elif mutation.startswith('mediator_war'): result['countries']['C']['wars'].add('A' if mutation.endswith('_a') else 'B')
        elif mutation.endswith('window'): result['countries'][{'actor_window': 'A', 'opponent_window': 'B', 'mediator_window': 'C'}[mutation]]['flags'].discard('eon_mediation_response_window')
        else: result['countries'][{'cancelled_actor': 'A', 'cancelled_opponent': 'B', 'cancelled_mediator': 'C'}[mutation]]['flags'].add('eon_mediation_cancelled')
        before = snapshot_other_state(result); before_pp = pp(result)
        if phase == 1: assert not answer_mediator(result, force=True)
        else: assert not answer_opponent(result, force=True)
        assert not any(reserved(result, country) for country in ('A', 'B', 'C'))
        assert snapshot_other_state(result) == before and pp(result) == before_pp
        groups['original_consumed_answer_rechecks_conflict_neutrality_and_windows'] += 1

for phase in (1, 2):
    result = state(); request(result)
    if phase == 2: assert answer_mediator(result)
    result['countries']['C']['overlord'] = 'D'
    before = deepcopy(result['countries'])
    native_hook(result, 'on_daily', 'A')
    assert result['countries'] == before, 'A transient invalidity cannot clear an unconsumed response identity'
    result['countries']['C']['overlord'] = None
    if phase == 1: assert answer_mediator(result)
    else: assert answer_opponent(result)
    assert_session(result, phase + 1)
    groups['transient_pending_invalidity_retains_original_consent_identity'] += 1

def assert_retired_edges(result, initiator='A', opponent='B', mediator='C'):
    for actor, peer in ((initiator, mediator), (mediator, initiator), (opponent, mediator), (mediator, opponent)):
        assert 'eon_mediation_retired_pair@' + peer in result['countries'][actor]['flags'], (actor, peer)
    assert 'eon_mediation_retired_pair@' + opponent not in result['countries'][initiator]['flags']

# Expiring a free draft is safe to release: no invitation event was created.
for expired in ('A', 'C'):
    result = state(); draft(result)
    result['countries'][expired]['flags'].discard('eon_mediation_draft_window')
    before = snapshot_other_state(result); before_pp = pp(result)
    native_hook(result, 'on_daily', 'C' if expired == 'A' else 'A')
    assert not reserved(result, 'A') and not reserved(result, 'C')
    assert not any(flag.startswith('eon_mediation_retired_pair@') for data in result['countries'].values() for flag in data['flags'])
    assert snapshot_other_state(result) == before and pp(result) == before_pp
    draft(result); assert_session(result, 0)
    groups['free_draft_expiry_no_modal_and_no_retirement'] += 1

# Forced pending expiry preserves the unconsumed native callback identity by
# retiring both directions of both response edges, regardless of daily order.
for phase in (1, 2):
    for expired in ('A', 'B', 'C'):
        result = state(); request(result, 2)
        if phase == 2: assert answer_mediator(result, 2)
        result['countries'][expired]['flags'].discard('eon_mediation_response_window')
        before = snapshot_other_state(result); before_pp = pp(result)
        native_hook(result, 'on_daily', 'C' if expired != 'C' else 'A')
        assert not any(reserved(result, country) for country in ('A', 'B', 'C'))
        assert_retired_edges(result)
        clear_cooldown(result)
        assert not action(result, 'eon_request_war_mediation', 'A', 'C', force=True)
        # Changing only A cannot reuse old M->B. A free D/C draft is allowed,
        # but choosing B remains blocked without paying or notifying anyone.
        result['countries']['D']['wars'].add('B'); result['countries']['B']['wars'].add('D')
        draft(result, 'D', 'C'); copied = deepcopy(result['countries']); copied_pp = pp(result)
        assert not decision(result, 'eon_select_mediation_humanitarian_opponent', 'D', 'B', force=True)
        assert result['countries'] == copied and pp(result) == copied_pp
        assert action(result, 'eon_withdraw_mediation', 'D', 'C')
        # A/B can still discuss the same war through a different neutral M.
        result['countries']['D']['wars'].discard('B'); result['countries']['B']['wars'].discard('D')
        request(result, 1, mediator='D'); new_current = deepcopy(result['countries'])
        if phase == 1: answer_mediator(result, 2, force=True)
        else: answer_opponent(result, 2, force=True)
        assert result['countries'] == new_current
        assert snapshot_other_state(result) == before and pp(result) == {**before_pp, 'A': before_pp['A'] - 20}
        groups['forced_pending_expiry_bilateral_edges_and_changed_triples'] += 1

for vanished in ('A', 'B', 'C'):
    for phase in (1, 2, 3):
        result = state(); request(result)
        if phase >= 2: assert answer_mediator(result)
        if phase == 3: assert answer_opponent(result)
        result['countries'][vanished]['exists'] = False
        before = snapshot_other_state(result); before_pp = pp(result)
        native_hook(result, 'on_daily', 'A' if vanished != 'A' else 'C')
        assert not any(reserved(result, actor) for actor in ('A', 'B', 'C'))
        assert_retired_edges(result)
        result['countries'][vanished]['exists'] = True; clear_cooldown(result)
        assert not action(result, 'eon_request_war_mediation')
        assert snapshot_other_state(result) == before and pp(result) == before_pp
        groups['missing_participant_cleanup_and_tag_restoration'] += 1

for hook in ('on_annex', 'on_subject_annexed'):
    for victim in ('A', 'B', 'C'):
        for phase in (1, 2, 3):
            result = state(); request(result)
            if phase >= 2: assert answer_mediator(result)
            if phase == 3: assert answer_opponent(result)
            before = snapshot_other_state(result); before_pp = pp(result)
            result['countries'][victim]['exists'] = False
            native_hook(result, hook, 'D' if hook == 'on_annex' else victim, victim if hook == 'on_annex' else 'D')
            assert not any(reserved(result, actor) for actor in ('A', 'B', 'C'))
            result['countries'][victim]['exists'] = True; clear_cooldown(result)
            if phase < 3:
                assert_retired_edges(result)
                assert not action(result, 'eon_request_war_mediation')
                request(result, mediator='D'); new_current = deepcopy(result['countries'])
                if phase == 1: answer_mediator(result, force=True)
                else: answer_opponent(result, force=True)
                assert result['countries'] == new_current
            else:
                assert not any(flag.startswith('eon_mediation_retired_pair@') for data in result['countries'].values() for flag in data['flags'])
                draft(result)
            assert snapshot_other_state(result) == before
            assert pp(result) == {**before_pp, 'A': before_pp['A'] - 20 if phase < 3 else before_pp['A']}
            groups['native_annex_and_subject_all_three_victim_roles'] += 1

for invalidity in ('window_a', 'window_b', 'window_m', 'peace', 'mediator_subject', 'mediator_faction', 'mediator_cowar', 'mediator_war'):
    result = state(); request(result); assert answer_mediator(result); assert answer_opponent(result)
    if invalidity.startswith('window'): result['countries'][{'window_a': 'A', 'window_b': 'B', 'window_m': 'C'}[invalidity]]['flags'].discard('eon_mediation_active_window')
    elif invalidity == 'peace': result['countries']['A']['wars'].clear(); result['countries']['B']['wars'].clear()
    elif invalidity == 'mediator_subject': result['countries']['C']['overlord'] = 'D'
    elif invalidity == 'mediator_faction': result['countries']['C']['faction'] = result['countries']['B']['faction'] = 'fixture_faction'
    elif invalidity == 'mediator_cowar': result['countries']['C']['co_war_partners'].add('B')
    else: result['countries']['C']['wars'].add('A')
    before = snapshot_other_state(result); before_pp = pp(result)
    native_hook(result, 'on_daily', 'C')
    assert not any(reserved(result, actor) for actor in ('A', 'B', 'C'))
    assert not any(flag.startswith('eon_mediation_retired_pair@') for data in result['countries'].values() for flag in data['flags'])
    assert snapshot_other_state(result) == before and pp(result) == before_pp
    groups['consistent_active_mandate_expiry_or_invalidity_closes_normally'] += 1

for defect in ('member_phase', 'member_topic', 'duplicate_role', 'invalid_topic', 'missing_role', 'foreign_opponent'):
    result = state(); request(result)
    if defect == 'member_phase': result['countries']['B']['variables']['eon_mediation_phase'] = 3
    elif defect == 'member_topic': result['countries']['C']['variables']['eon_mediation_topic'] = 2
    elif defect == 'duplicate_role': result['countries']['C']['variables']['eon_mediation_party_b'] = 'C'
    elif defect == 'invalid_topic': result['countries']['C']['variables']['eon_mediation_topic'] = 99
    elif defect == 'missing_role': result['countries']['C']['flags'].discard('eon_mediation_reserved')
    else: result['countries']['B']['variables']['eon_mediation_party_b'] = 'D'
    before = deepcopy(result['countries']); before_other = snapshot_other_state(result); before_pp = pp(result)
    option_effect(result, 'eon_mediation.10', 'eon_mediation_accept', 'C', 'A', force=True)
    option_effect(result, 'eon_mediation.10', 'eon_mediation_decline', 'C', 'A', force=True)
    helper(result, 'C', 'end_active')
    assert result['countries'] == before
    native_hook(result, 'on_daily', 'A')
    assert not reserved(result, 'A')
    assert_retired_edges(result)
    # Only the original triad identity owns its other records. A mismatched
    # endpoint is left for its own cleanup rather than being overwritten.
    for actor in ('B', 'C'):
        original = before[actor]
        linked = all(original['variables'].get(key) == before['A']['variables'].get(key) for key in ('eon_mediation_party_a', 'eon_mediation_party_b', 'eon_mediation_mediator'))
        if linked and 'eon_mediation_reserved' in original['flags']: assert not reserved(result, actor)
    assert snapshot_other_state(result) == before_other and pp(result) == before_pp
    groups['corrupt_phase_topic_identity_cannot_consume_or_end_other_records'] += 1

# A stray fourth-country record is not an owner of the three named participants.
# Even identical copied pointers cannot authorize cleanup of their live session.
result = state(); request(result)
result['countries']['D']['variables'].update({key: val for key, val in result['countries']['A']['variables'].items() if key.startswith('eon_mediation_')})
result['countries']['D']['flags'].update({'eon_mediation_reserved', 'eon_mediation_response_window'})
owned = {actor: deepcopy(result['countries'][actor]) for actor in ('A', 'B', 'C')}
native_hook(result, 'on_daily', 'D')
assert not reserved(result, 'D')
assert {actor: result['countries'][actor] for actor in ('A', 'B', 'C')} == owned, 'A nonparticipant copied record can clear a live owned triad'
groups['nonparticipant_stray_record_cannot_clean_owned_live_triad'] += 1

for topic in (1, 2):
    for condition, expected in (('ordinary', 2), ('only_a_high', 2), ('only_b_high', 2), ('both_high', 3), ('a_low', .5), ('b_low', .5), ('both_low', .5), ('thresholds', 2), ('invalid', 0)):
        result = state(); request(result, topic); mediator = result['countries']['C']; mediator['ai'] = True
        if condition in ('only_a_high', 'both_high'): mediator['opinions']['A'] = 51
        if condition in ('only_b_high', 'both_high'): mediator['opinions']['B'] = 51
        if condition in ('a_low', 'both_low'): mediator['opinions']['A'] = -26
        if condition in ('b_low', 'both_low'): mediator['opinions']['B'] = -26
        if condition == 'thresholds': mediator['opinions'].update(A=50, B=-25)
        if condition == 'invalid': result['countries']['B']['flags'].discard('eon_mediation_response_window')
        identity = 'eon_mediation.' + str(9 + topic)
        before = deepcopy(result['countries'])
        assert ai_weight(result, identity, 'eon_mediation_accept', 'C', 'A') == expected, (topic, condition)
        assert ai_weight(result, identity, 'eon_mediation_decline', 'C', 'A') == 1
        assert result['countries'] == before
        groups['mediator_ai_reads_both_parties_native_scopes_and_invalidity'] += 1

for topic in (1, 2):
    for opinion, valid, expected in ((0, True, 2), (50, True, 2), (51, True, 4), (-25, True, 2), (-26, True, 1), (51, False, 0)):
        result = state(); request(result, topic); assert answer_mediator(result, topic)
        result['countries']['B']['ai'] = True; result['countries']['B']['opinions']['C'] = opinion
        if not valid: result['countries']['A']['flags'].discard('eon_mediation_response_window')
        identity = 'eon_mediation.' + str(19 + topic)
        before = deepcopy(result['countries'])
        assert ai_weight(result, identity, 'eon_mediation_accept', 'B', 'C') == expected
        assert ai_weight(result, identity, 'eon_mediation_decline', 'B', 'C') == 1
        assert result['countries'] == before
        groups['opponent_ai_mediator_opinion_boundaries_and_nonzero_decline'] += 1

for actor in ('A', 'B', 'C'):
    result = state(); request(result); result['countries'][actor]['ai'] = True
    before = deepcopy(result['countries'])
    assert not action(result, 'eon_withdraw_mediation', actor, 'C' if actor != 'C' else 'A', force=True)
    assert result['countries'] == before
    groups['native_withdrawal_remains_human_initiated'] += 1

for phase in (1, 2):
    for topic in (1, 2):
        for status in ('live', 'cancelled_other', 'expired_other', 'peace', 'wrong_topic'):
            result = state(); request(result, topic)
            if phase == 2: assert answer_mediator(result, topic)
            actor, sender = ('C', 'A') if phase == 1 else ('B', 'C')
            if status == 'cancelled_other': result['countries']['A']['flags'].add('eon_mediation_cancelled')
            elif status == 'expired_other': result['countries']['A']['flags'].discard('eon_mediation_response_window')
            elif status == 'peace': result['countries']['A']['wars'].clear(); result['countries']['B']['wars'].clear()
            rendered_topic = 3 - topic if status == 'wrong_topic' else topic
            identity = 'eon_mediation.' + str((9 if phase == 1 else 19) + rendered_topic)
            expected = ('eon_mediation_mediator_' if phase == 1 else 'eon_mediation_opponent_') + TOPICS[topic] + '_desc' if status == 'live' else 'eon_mediation_cancelled_desc' if status == 'cancelled_other' else 'eon_mediation_stale_desc'
            before = deepcopy(result['countries'])
            assert selected_desc(result, identity, actor, sender) == expected, (phase, topic, status)
            assert result['countries'] == before
            groups['literal_event_exclusive_live_cancelled_and_stale_descriptions'] += 1

for phase in (1, 2):
    result = state(); request(result)
    if phase == 2: assert answer_mediator(result)
    result['countries']['A']['flags'].discard('eon_mediation_response_window')
    native_hook(result, 'on_daily', 'C'); clear_cooldown(result)
    request(result, 2, mediator='D')
    assert action(result, 'eon_withdraw_mediation', 'A', 'D')
    current = deepcopy(result['countries'])
    identity = 'eon_mediation.10' if phase == 1 else 'eon_mediation.20'
    assert selected_desc(result, identity, 'C' if phase == 1 else 'B', 'A' if phase == 1 else 'C') == 'eon_mediation_stale_desc'
    if phase == 1: answer_mediator(result, force=True)
    else: answer_opponent(result, force=True)
    assert result['countries'] == current
    groups['unconsumed_old_invite_cannot_read_different_cancelled_triple'] += 1

# Result messages are inert even when an eligible later session is open.
result = state(); request(result); assert answer_mediator(result); assert answer_opponent(result)
assert action(result, 'eon_withdraw_mediation', 'B', 'C'); clear_cooldown(result)
request(result, 2); current = deepcopy(result['countries'])
for notice in range(30, 38): option_effect(result, 'eon_mediation.' + str(notice), 'eon_mediation_ack', 'A', 'C')
assert result['countries'] == current
groups['all_eight_static_result_acknowledgements_are_inert'] += 1

result = state()
for actor, other in (('A', 'D'), ('D', 'A')):
    result['countries'][actor]['flags'].update({'eon_consultation_reserved', 'eon_consultation_active', 'eon_consultation_active_window'})
    result['countries'][actor]['variables'].update(eon_consultation_partner=other, eon_consultation_topic=3)
result['countries']['A']['variables'].update(eon_aid_partner='D', eon_aid_amount=15, eon_aid_escrow=15, eon_support_refund_due=7,
                                           pending_assume_debt_offer='B', assuming_debt_value=40, assuming_debt_repayment_value=10)
result['countries']['D']['variables'].update(eon_aid_partner='A', eon_aid_amount=15)
result['countries']['A']['flags'].update({'eon_aid_reserved', 'eon_aid_outgoing', 'trade_agreement@D', 'mutual_investment_treaty_@D'})
result['countries']['D']['flags'].update({'eon_aid_reserved', 'eon_aid_incoming'})
before = snapshot_other_state(result); before_pp = pp(result)
request(result, 2); assert answer_mediator(result, 2); assert answer_opponent(result, 2)
assert action(result, 'eon_withdraw_mediation', 'C', 'A')
assert snapshot_other_state(result) == before and pp(result) == {**before_pp, 'A': before_pp['A'] - 20}
assert not result.get('political_macro_calls')
groups['mediation_preserves_live_aid_debt_consultations_treaties_energy_and_war'] += 1

for name in ('release_record', 'retire_response_edges'):
    result = state(); request(result)
    result['countries']['D']['variables'].update({key: val for key, val in result['countries']['A']['variables'].items() if key.startswith('eon_mediation_')})
    result['countries']['D']['flags'].update({'eon_mediation_reserved', 'eon_mediation_response_window'})
    owned = {actor: deepcopy(result['countries'][actor]) for actor in ('A', 'B', 'C')}; nonparticipant = deepcopy(result['countries']['D'])
    helper(result, 'D', name)
    assert {actor: result['countries'][actor] for actor in ('A', 'B', 'C')} == owned, name
    if name == 'release_record': assert not reserved(result, 'D')
    else: assert result['countries']['D'] == nonparticipant
    groups['direct_nonparticipant_release_and_retire_cannot_touch_owned_triad'] += 1

def six_country_state():
    result = state()
    for extra in ('E', 'F'): result['countries'][extra] = deepcopy(result['countries']['C'])
    for data in result['countries'].values(): data['opinions'].update(E=0, F=0)
    result['countries']['D']['wars'].add('E'); result['countries']['E']['wars'].add('D')
    return result

for cleanup in ('timer', 'annex', 'subject'):
    result = six_country_state(); request(result, 1); request(result, 2, 'D', 'E', 'F')
    assert_session(result, 1); assert_session(result, 1, 2, 'D', 'E', 'F')
    untouched = {actor: deepcopy(result['countries'][actor]) for actor in ('D', 'E', 'F')}
    if cleanup == 'timer':
        result['countries']['B']['flags'].discard('eon_mediation_response_window')
        native_hook(result, 'on_daily', 'C')
    else:
        result['countries']['C']['exists'] = False
        native_hook(result, 'on_annex' if cleanup == 'annex' else 'on_subject_annexed', 'D' if cleanup == 'annex' else 'C', 'C' if cleanup == 'annex' else 'D')
    assert not any(reserved(result, actor) for actor in ('A', 'B', 'C'))
    assert_retired_edges(result)
    assert {actor: result['countries'][actor] for actor in ('D', 'E', 'F')} == untouched
    assert answer_mediator(result, 2, initiator='D', opponent='E', mediator='F')
    assert answer_opponent(result, 2, initiator='D', opponent='E', mediator='F')
    assert_session(result, 3, 2, 'D', 'E', 'F')
    groups['independent_six_country_triads_survive_other_native_cleanup'] += 1

source_paths = ['common/scripted_effects/eon_mediation_effects.txt', 'common/scripted_triggers/eon_mediation_triggers.txt',
                'common/scripted_diplomatic_actions/eon_mediation_actions.txt', 'common/on_actions/eon_mediation_on_actions.txt',
                'events/eon_mediation_events.txt', 'common/decisions/eon_mediation_decisions.txt',
                'common/decisions/categories/eon_mediation_categories.txt', 'localisation/english/eon_mediation_l_english.yml',
                'localisation/russian/eon_mediation_l_russian.yml']

print(json.dumps({'all_passed': True, 'actual_source_scenarios': sum(groups.values()),
                  'adapter_semantics_cases': 0, 'total_cases': sum(groups.values()),
                  'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source_paths},
                  'groups': groups, 'baseline': BASELINE,
                  'proof_scope': 'ordered actual-source three-country mediation with supplied native facts',
                  'not_proven': ['native callbacks and timers', 'GUI', 'save/load', 'campaign']}, indent=2))
