"""Ordered actual-source consultations; no HOI4 runtime acceptance claim."""
from pathlib import Path
from copy import deepcopy
from collections import Counter
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '4406fc756cd91f6f2e7477d92fc87dac8c215572'
groups = Counter()
effect_path = ROOT / 'common/scripted_effects/eon_consultation_effects.txt'
assert effect_path.exists(), 'RED: consultation lifecycle helpers are not implemented'

# Load the existing ordered executor definitions without executing its scenario
# loops. The complete previous suite is counted separately by run_checks.py.
sys.path.insert(0, str(ROOT / 'tools/validation/diplomacy_package_01'))
engine_path = ROOT / 'tools/validation/diplomacy_package_01/test_energy.py'
engine_text = engine_path.read_text(encoding='utf-8')
marker = '\ncases=[]\n'
assert engine_text.count(marker) == 1, 'Existing interpreter scenario boundary changed'
model = {'__file__': str(engine_path), '__name__': 'consultation_source_executor'}
exec(compile(engine_text.split(marker)[0], str(engine_path), 'exec'), model)
ast, one = model['ast'], model['one']
assert one(ast(effect_path.read_text(encoding='utf-8-sig')), 'eon_consultation_prepare_draft'), 'RED: consultation preparation helper is missing'

def read(path): return (ROOT / path).read_text(encoding='utf-8-sig')
base_execute, base_trigger = model['execute'], model['trigger']
base_compare, base_value = model['compare'], model['value']
context, switch = model['context'], model['switch']

for stem in ('eon_aid', 'eon_support', 'eon_consultation'):
    model['effects'].update({k: v for k, o, v in ast(read('common/scripted_effects/' + stem + '_effects.txt'))})
model['effects']['modify_treasury_effect'] = one(ast(read('common/scripted_effects/00_budget_effects.txt')), 'modify_treasury_effect')
for stem in ('eon_aid', 'eon_consultation', '99_ERI_scripted', '00_influence_scripted'):
    model['capacity_triggers'].update({k: v for k, o, v in ast(read('common/scripted_triggers/' + stem + '_triggers.txt'))})

def compare(left, operator, right):
    if operator not in ('=', '==', '!='):
        if isinstance(left, str) and left in ('A', 'B', 'C', 'D'): left = ord(left) - ord('A') + 1
        if isinstance(right, str) and right in ('A', 'B', 'C', 'D'): right = ord(right) - ord('A') + 1
    return base_compare(left, operator, right)
model['compare'] = compare

def value(state, ctx, expression):
    if isinstance(expression, str) and 'opinion@' in expression:
        if '.' in expression:
            actor, tail = expression.split('.', 1)
            return value(state, switch(ctx, model['country_ref'](state, ctx, actor)), tail)
        target = model['country_ref'](state, ctx, expression.split('@', 1)[1])
        return state['countries'][ctx['scope']]['opinions'].get(target, 0)
    return base_value(state, ctx, expression)
model['value'] = value

def trigger(nodes, state, ctx):
    index = 0
    while index < len(nodes):
        key, operator, val = nodes[index]; index += 1
        grouped = [(key, operator, val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        country = state['countries'][ctx['scope']]
        if key == 'NOT': passed = not any(trigger([node], state, ctx) for node in val)
        elif key == 'tooltip': passed = True
        elif key == 'has_political_power': passed = compare(country['variables']['political_power'], operator, float(val))
        elif key == 'has_country_leader': passed = country['leader'] == one(val, 'name')
        elif key == 'has_idea': passed = val in country['ideas']
        elif key == 'has_opinion':
            target = model['country_ref'](state, ctx, one(val, 'target'))
            op, wanted = next((o, v) for k, o, v in val if k == 'value')
            passed = compare(country['opinions'].get(target, 0), op, float(wanted))
        elif key == 'is_in_faction_with':
            other = model['country_ref'](state, ctx, val)
            passed = country['faction'] is not None and country['faction'] == state['countries'][other]['faction']
        elif key == 'is_subject_of': passed = country.get('overlord') == model['country_ref'](state, ctx, val)
        else: passed = base_trigger(grouped, state, ctx)
        if not passed: return False
    return True
model['trigger'] = trigger

def execute(nodes, state, ctx):
    index = 0
    while index < len(nodes):
        key, operator, val = nodes[index]; index += 1
        grouped = [(key, operator, val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        country = state['countries'][ctx['scope']]
        if key == 'add_political_power': country['variables']['political_power'] += value(state, ctx, val)
        elif key == 'set_country_flag' and isinstance(val, list):
            name = model['flag_name'](state, ctx, one(val, 'flag'))
            days = one(val, 'days')
            state.setdefault('timer_declarations', []).append((ctx['scope'], name, float(value(state, ctx, days))))
            base_execute(grouped, state, ctx)
        elif key == 'every_country':
            limits = [v for k, o, v in val if k == 'limit']
            for actor, data in state['countries'].items():
                inner = switch(ctx, actor)
                if data['exists'] and (not limits or trigger(limits[0], state, inner)):
                    execute([n for n in val if n[0] != 'limit'], state, inner)
        elif key in ('change_influence_percentage', 'add_ruling_outlook_popularity', 'add_opinion_modifier', 'reverse_add_opinion_modifier'):
            state.setdefault('political_macro_calls', []).append((ctx['scope'], key, deepcopy(val), deepcopy(state['temp'])))
        elif key == 'update_dirty_influence_var': state['ui_updates'] += 1
        elif key == 'hidden_effect': execute(val, state, ctx)
        elif key == 'effect_tooltip': pass
        else: base_execute(grouped, state, ctx)
model['execute'] = execute

def state():
    result = model['state']()
    for actor, country in result['countries'].items():
        country['variables'].update(treasury=100, debt=40, political_power=40, gdp_total=100,
                                    debt_ratio=.5, interest_rate=5, num_of_civilian_factories=50)
        country.update(ideas={'non_power'}, faction=None, leader='Ordinary President',
                       opinions={'A': 0, 'B': 0, 'C': 0, 'D': 0}, original_tag='OTH')
        country['arrays']['influence_array'] = ['A', 'C', 'D', 'B']
    result['countries']['B']['variables'].update(gdp_total=50, num_of_civilian_factories=20)
    model['framework'](result, 'A', 'D'); model['pair'](result, 'A', 'D', -8, .04)
    return result

def snapshot_other_state(result):
    return {actor: {
        'variables': {k: deepcopy(v) for k, v in data['variables'].items() if not k.startswith('eon_consultation_') and k != 'political_power'},
        'flags': {f for f in data['flags'] if not f.startswith('eon_consultation_')},
        'arrays': deepcopy(data['arrays']), 'wars': deepcopy(data['wars']), 'ideas': deepcopy(data['ideas']),
        'faction': data['faction'], 'opinions': deepcopy(data['opinions'])}
        for actor, data in result['countries'].items()}
def pp(result): return {actor: data['variables']['political_power'] for actor, data in result['countries'].items()}
def check(result, nodes, ctx, temporary=None):
    result['temp'] = dict(temporary or {})
    return trigger(nodes, result, ctx)
def effect(result, nodes, ctx, temporary=None):
    result['temp'] = dict(temporary or {})
    execute(nodes, result, ctx)
def helper(result, actor, name, other=None, temporary=None):
    effect(result, [('eon_consultation_' + name, '=', 'yes')], context(actor, other), temporary)
def action(result, name, actor='A', partner='B', force=False):
    body = one(actions, name)
    ctx = context(actor, scope=partner)
    ready = all(check(result, one(body, key), ctx) for key in ('allowed', 'visible', 'selectable', 'can_be_sent'))
    if ready or force: effect(result, one(body, 'complete_effect'), ctx)
    return ready
def queued(result, identity, target, sender):
    found = [item for item in result['events'] if item == {'target': target, 'id': identity, 'from': sender}]
    assert len(found) == 1, (identity, target, sender, result['events'])
    return found[0]
def immediate(result, identity, target, sender):
    item = queued(result, identity, target, sender); result['events'].remove(item)
    effect(result, one(events[identity], 'immediate'), context(target, sender))
def option(identity, name):
    found = [v for k, o, v in events[identity] if k == 'option' and one(v, 'name') == name]
    assert len(found) == 1, (identity, name)
    return found[0]
def option_effect(result, identity, name, actor, partner, force=False):
    body = option(identity, name); ctx = context(actor, partner)
    guards = [v for k, o, v in body if k == 'trigger']
    ready = not guards or check(result, guards[0], ctx)
    if ready or force: effect(result, body, ctx)
    return ready
def reserved(result, actor): return 'eon_consultation_reserved' in result['countries'][actor]['flags']
def active(result, actor): return 'eon_consultation_active' in result['countries'][actor]['flags']
def clear_cooldown(result, a='A', b='B'):
    result['countries'][a]['flags'].discard('eon_consultation_recent_contact@' + b)
    result['countries'][b]['flags'].discard('eon_consultation_recent_contact@' + a)

# Native NOT is NOR for its child predicates. NAND requires an explicit AND
# child. Keep this correction local to 07 rather than silently changing older
# packages' interpreter and its historical proof scope.
for first, second in ((False, False), (False, True), (True, False), (True, True)):
    result = state(); flags = result['countries']['A']['flags']
    if first: flags.add('fixture_first')
    if second: flags.add('fixture_second')
    children = [('has_country_flag', '=', 'fixture_first'), ('has_country_flag', '=', 'fixture_second')]
    assert check(result, [('NOT', '=', children)], context('A')) == (not first and not second)
    assert check(result, [('NOT', '=', [('AND', '=', children)])], context('A')) == (not (first and second))
    groups['native_nor_and_explicit_nand_truth_table'] += 1

# HOI4 political power can be fractional. The exact10 cost must be covered,
# including a candidate that became unaffordable after its option was rendered.
for effort in (9, 9.01, 9.99, 10):
    result = state()
    effect(result, [('eon_consultation_prepare_draft', '=', 'yes')], context('A', scope='B'))
    result['countries']['A']['variables']['political_power'] = effort
    ctx = context('A', 'B'); temporary = {'eon_consultation_proposed_topic': 1}
    available = check(result, [('eon_consultation_draft_send_ready', '=', 'yes')], ctx, temporary)
    assert available == (effort >= 10), ('Fractional PP can fund an exact10 cost', effort, available)
    before_other = snapshot_other_state(result)
    effect(result, [('eon_consultation_send_request', '=', 'yes')], ctx, temporary)
    assert result['countries']['A']['variables']['political_power'] == (effort - 10 if effort >= 10 else effort)
    assert snapshot_other_state(result) == before_other
    assert ('eon_consultation_outgoing' in result['countries']['A']['flags']) == (effort >= 10)
    groups['exact_political_effort_fractional_boundary'] += 1

events = model['get_event_map'](read('events/eon_consultation_events.txt'))
aid_events = model['get_event_map'](read('events/00_Influence_events.txt'))
actions = one(ast(read('common/scripted_diplomatic_actions/eon_consultation_actions.txt')), 'scripted_diplomatic_actions')
hooks = one(ast(read('common/on_actions/eon_consultation_on_actions.txt')), 'on_actions')

def native_hook(result, name, actor, partner=None):
    effect(result, one(one(hooks, name), 'effect'), context(actor, partner))

TOPICS = {1: 'trade', 2: 'energy', 3: 'support'}
def draft(result, actor='A', partner='B'):
    assert action(result, 'eon_open_economic_consultations', actor, partner)
    immediate(result, 'eon_consultation.0', partner, actor)
    queued(result, 'eon_consultation.1', actor, partner)

def request(result, topic=1, actor='A', partner='B'):
    draft(result, actor, partner)
    result['events'].remove(queued(result, 'eon_consultation.1', actor, partner))
    assert option_effect(result, 'eon_consultation.1', 'eon_consultation_topic_' + TOPICS[topic], actor, partner)
    queued(result, 'eon_consultation.' + str(9 + topic), partner, actor)

def response(result, topic=1, accept=True, actor='B', partner='A', force=False):
    identity = 'eon_consultation.' + str(9 + topic)
    result['events'].remove(queued(result, identity, actor, partner))
    return option_effect(result, identity, 'eon_consultation_accept_talks' if accept else 'eon_consultation_decline_talks', actor, partner, force)

def selected_desc(result, identity, actor, partner):
    ctx = context(actor, partner)
    selected = []
    for key, operator, val in events[identity]:
        if key != 'desc': continue
        if isinstance(val, str): selected.append(val)
        elif check(result, one(val, 'trigger'), ctx): selected.append(one(val, 'text'))
    assert len(selected) == 1, ('Invitation descriptions must be exclusive', identity, selected)
    return selected[0]

# Forced cleanup of a malformed mirrored session must account for a pending
# modal on either side. An active flag on only one side is not proof that the
# original other-side invitation was consumed.
for actor_role, partner_role in (('active', 'incoming'), ('outgoing', 'active'),
                                  ('active', 'draft_recipient'), ('none', 'none')):
    result = state()
    for actor, partner, role in (('A', 'B', actor_role), ('B', 'A', partner_role)):
        data = result['countries'][actor]
        data['variables'].update(eon_consultation_partner=partner, eon_consultation_topic=3)
        data['flags'].add('eon_consultation_reserved')
        if role != 'none':
            data['flags'].add('eon_consultation_' + role)
            window = 'active' if role == 'active' else 'draft' if role.startswith('draft') else 'response'
            data['flags'].add('eon_consultation_' + window + '_window')
    result['events'].append({'target': 'B', 'id': 'eon_consultation.12', 'from': 'A'})
    before_other = snapshot_other_state(result); before_pp = pp(result)
    native_hook(result, 'on_daily', 'A')
    assert not reserved(result, 'A') and not reserved(result, 'B'), ('Malformed mirrored roles retained a permanent lock', actor_role, partner_role)
    assert 'eon_consultation_retired_pair@B' in result['countries']['A']['flags'] and 'eon_consultation_retired_pair@A' in result['countries']['B']['flags'], ('Forced mixed-role cleanup can reuse an unconsumed modal', actor_role, partner_role)
    clear_cooldown(result)
    assert not action(result, 'eon_open_economic_consultations')
    assert action(result, 'eon_open_economic_consultations', 'C', 'B')
    before_current = deepcopy(result['countries'])
    option_effect(result, 'eon_consultation.12', 'eon_consultation_accept_talks', 'B', 'A', force=True)
    assert result['countries'] == before_current
    assert snapshot_other_state(result) == before_other and pp(result) == before_pp
    groups['forced_malformed_mutual_roles'] += 1

# The old unconsumed A invitation survives forced expiry. A different D/B
# session must not make its description falsely claim that A withdrew it.
result = state(); request(result, 1)
result['countries']['B']['flags'].discard('eon_consultation_response_window')
native_hook(result, 'on_daily', 'B')
request(result, 2, 'D', 'B')
assert action(result, 'eon_withdraw_consultation_request', 'D', 'B')
assert selected_desc(result, 'eon_consultation.10', 'B', 'A') == 'eon_consultation_stale_invite_desc', 'Old invitation reads cancellation from a different current session'
assert selected_desc(result, 'eon_consultation.11', 'B', 'D') == 'eon_consultation_cancelled_invite_desc'
groups['stale_invitation_description_identity'] += 1

result = state(); request(result, 2)
assert selected_desc(result, 'eon_consultation.10', 'B', 'A') == 'eon_consultation_stale_invite_desc', 'Wrong topic invitation reads current unrelated terms'
assert selected_desc(result, 'eon_consultation.11', 'B', 'A') == 'eon_consultation_energy_invite_desc'
groups['stale_invitation_description_identity'] += 1

def assert_pair(result, actor='A', partner='B', topic=1, stage='pending'):
    for country, other in ((actor, partner), (partner, actor)):
        data = result['countries'][country]
        assert reserved(result, country)
        assert data['variables']['eon_consultation_partner'] == other
        assert data['variables']['eon_consultation_topic'] == topic
        if stage == 'active': assert active(result, country)
    if stage == 'pending':
        assert 'eon_consultation_outgoing' in result['countries'][actor]['flags']
        assert 'eon_consultation_incoming' in result['countries'][partner]['flags']
        assert not active(result, actor) and not active(result, partner)

def consultation_snapshot(result):
    return {country: {'variables': {k: deepcopy(v) for k, v in data['variables'].items() if k.startswith('eon_consultation_')},
                      'flags': {f for f in data['flags'] if f.startswith('eon_consultation_')}}
            for country, data in result['countries'].items()}

# Literal topics have complete independent yes/no paths. The proposal and the
# answer never alter a pre-existing power contract, debt or political relation.
for topic in (1, 2, 3):
    for accept in (False, True):
        result = state(); before = snapshot_other_state(result); initial_pp = pp(result)
        draft(result)
        assert pp(result) == initial_pp and snapshot_other_state(result) == before
        assert all(not active(result, actor) for actor in ('A', 'B'))
        for actor in ('A', 'B'): assert (actor, 'eon_consultation_draft_window', 7) in result['timer_declarations']
        result['events'].remove(queued(result, 'eon_consultation.1', 'A', 'B'))
        assert option_effect(result, 'eon_consultation.1', 'eon_consultation_topic_' + TOPICS[topic], 'A', 'B')
        assert_pair(result, topic=topic)
        assert pp(result) == {**initial_pp, 'A': initial_pp['A'] - 10}
        for actor, partner in (('A', 'B'), ('B', 'A')):
            assert (actor, 'eon_consultation_response_window', 30) in result['timer_declarations']
            assert (actor, 'eon_consultation_recent_contact@' + partner, 90) in result['timer_declarations']
        assert response(result, topic, accept)
        if accept:
            assert_pair(result, topic=topic, stage='active')
            for actor in ('A', 'B'): assert (actor, 'eon_consultation_active_window', 30) in result['timer_declarations']
        else: assert not reserved(result, 'A') and not reserved(result, 'B')
        settled = deepcopy(result['countries']); old_pp = pp(result)
        # A second execution while this original request is no longer pending
        # cannot create another channel or charge PP. No new same-pair modal is
        # introduced here: a native consumed modal is not arbitrarily duplicated.
        option_effect(result, 'eon_consultation.' + str(9 + topic), 'eon_consultation_accept_talks', 'B', 'A', force=True)
        option_effect(result, 'eon_consultation.1', 'eon_consultation_topic_' + TOPICS[topic], 'A', 'B', force=True)
        assert result['countries'] == settled and pp(result) == old_pp
        assert snapshot_other_state(result) == before
        assert not result.get('political_macro_calls')
        assert not action(result, 'eon_open_economic_consultations')
        groups['literal_topic_complete_yes_no_cycle'] += 1

# Sender chooses whether to hold talks. The candidate can change between GUI
# rendering and effect execution; each fresh action/effect gate is exercised.
for mutation in ('actor_ai', 'actor_war', 'partner_war', 'actor_absent', 'partner_absent', 'actor_reserved', 'partner_reserved', 'actor_cooldown', 'partner_cooldown', 'self'):
    result = state(); actor, partner = 'A', 'B'
    if mutation == 'actor_ai': result['countries']['A']['ai'] = True
    elif mutation == 'actor_war': result['countries']['A']['wars'].add('B')
    elif mutation == 'partner_war': result['countries']['B']['wars'].add('A')
    elif mutation.endswith('absent'): result['countries']['A' if mutation.startswith('actor') else 'B']['exists'] = False
    elif mutation.endswith('reserved'): result['countries']['A' if mutation.startswith('actor') else 'B']['flags'].add('eon_consultation_reserved')
    elif mutation.endswith('cooldown'): result['countries']['A' if mutation.startswith('actor') else 'B']['flags'].add('eon_consultation_recent_contact@' + ('B' if mutation.startswith('actor') else 'A'))
    else: partner = actor
    before = deepcopy(result['countries']); before_pp = pp(result)
    assert not action(result, 'eon_open_economic_consultations', actor, partner, force=True), mutation
    assert result['countries'] == before and pp(result) == before_pp and not result['events']
    groups['fresh_native_open_rechecks'] += 1

for mutation in ('actor_ai', 'actor_war', 'partner_war', 'partner_absent', 'actor_window', 'partner_window', 'actor_cooldown', 'partner_cooldown', 'invalid_topic'):
    result = state(); draft(result); topic = 1
    if mutation == 'actor_ai': result['countries']['A']['ai'] = True
    elif mutation == 'actor_war': result['countries']['A']['wars'].add('B')
    elif mutation == 'partner_war': result['countries']['B']['wars'].add('A')
    elif mutation == 'partner_absent': result['countries']['B']['exists'] = False
    elif mutation.endswith('window'): result['countries']['A' if mutation.startswith('actor') else 'B']['flags'].discard('eon_consultation_draft_window')
    elif mutation.endswith('cooldown'): result['countries']['A' if mutation.startswith('actor') else 'B']['flags'].add('eon_consultation_recent_contact@' + ('B' if mutation.startswith('actor') else 'A'))
    else: topic = 99
    before = snapshot_other_state(result); before_pp = pp(result)
    result['events'].remove(queued(result, 'eon_consultation.1', 'A', 'B'))
    assert not check(result, [('eon_consultation_draft_send_ready', '=', 'yes')], context('A', 'B'), {'eon_consultation_proposed_topic': topic})
    helper(result, 'A', 'send_request', 'B', {'eon_consultation_proposed_topic': topic})
    assert pp(result) == before_pp and snapshot_other_state(result) == before
    assert not reserved(result, 'A') and not reserved(result, 'B')
    assert not any(item['id'] in ('eon_consultation.10', 'eon_consultation.11', 'eon_consultation.12') for item in result['events'])
    if mutation != 'partner_absent':
        assert 'eon_consultation_retired_pair@B' not in result['countries']['A']['flags']
    groups['rendered_agenda_fresh_recheck_no_cost'] += 1

for late in (False, True):
    result = state(); draft(result); before = snapshot_other_state(result); before_pp = pp(result)
    if late:
        for actor in ('A', 'B'): result['countries'][actor]['flags'].discard('eon_consultation_draft_window')
    result['events'].remove(queued(result, 'eon_consultation.1', 'A', 'B'))
    assert option_effect(result, 'eon_consultation.1', 'eon_consultation_cancel_agenda', 'A', 'B')
    assert not reserved(result, 'A') and not reserved(result, 'B')
    assert snapshot_other_state(result) == before and pp(result) == before_pp
    # The original rendered agenda has now been consumed; opening it again is
    # safe and does not require a forced-cleanup tombstone.
    assert action(result, 'eon_open_economic_consultations')
    groups['consumed_normal_and_late_agenda_cancel'] += 1

# Countries hold one consultation at a time; another separate pair can still
# negotiate. Neither a crossed offer nor a third country overwrites a pointer.
result = state(); request(result, 3); original = deepcopy(result['countries'])
for actor, partner in (('A', 'C'), ('C', 'B'), ('B', 'A')):
    assert not action(result, 'eon_open_economic_consultations', actor, partner, force=True)
    assert result['countries'] == original
request(result, 2, 'C', 'D')
assert_pair(result, topic=3); assert_pair(result, 'C', 'D', 2)
groups['crossed_and_independent_pair_serialization'] += 1

for topic, wrong_event, actor, partner in ((1, 11, 'B', 'A'), (3, 12, 'B', 'C'), (2, 11, 'A', 'B')):
    result = state(); request(result, topic); before = deepcopy(result['countries']); before_pp = pp(result)
    option_effect(result, 'eon_consultation.' + str(wrong_event), 'eon_consultation_accept_talks', actor, partner, force=True)
    option_effect(result, 'eon_consultation.' + str(wrong_event), 'eon_consultation_decline_talks', actor, partner, force=True)
    assert result['countries'] == before and pp(result) == before_pp
    assert_pair(result, topic=topic)
    groups['wrong_topic_country_and_role_callbacks'] += 1

for actor in ('A', 'B'):
    result = state(); request(result, 2); before = snapshot_other_state(result); before_pp = pp(result)
    assert action(result, 'eon_withdraw_consultation_request')
    assert all('eon_consultation_cancelled' in result['countries'][country]['flags'] for country in ('A', 'B'))
    assert_pair(result, topic=2)
    assert not action(result, 'eon_open_economic_consultations', actor, 'C', force=True)
    assert not action(result, 'eon_withdraw_consultation_request', force=True)
    assert not response(result, 2, True, force=True)
    assert not reserved(result, 'A') and not reserved(result, 'B')
    assert snapshot_other_state(result) == before and pp(result) == before_pp
    assert action(result, 'eon_open_economic_consultations', actor, 'C')
    groups['withdrawn_request_drains_original_response'] += 1

for mutation in ('actor_war', 'partner_war', 'actor_absent', 'partner_absent', 'actor_window', 'partner_window'):
    result = state(); request(result, 3)
    if mutation == 'actor_war': result['countries']['A']['wars'].add('B')
    elif mutation == 'partner_war': result['countries']['B']['wars'].add('A')
    elif mutation.endswith('absent'): result['countries']['A' if mutation.startswith('actor') else 'B']['exists'] = False
    else: result['countries']['A' if mutation.startswith('actor') else 'B']['flags'].discard('eon_consultation_response_window')
    before = snapshot_other_state(result); before_pp = pp(result)
    assert not response(result, 3, True, force=True)
    assert not active(result, 'A') and not active(result, 'B')
    assert not reserved(result, 'A') and not reserved(result, 'B')
    assert pp(result) == before_pp and snapshot_other_state(result) == before
    groups['consumed_response_fresh_peace_existence_and_ttl'] += 1

# Expiry is a supplied native flag fact. Forced cleanup leaves the original
# event in the queue, so only this affected pair receives permanent tombstones.
for stage in ('hidden', 'agenda', 'pending'):
    for cleanup_actor in ('A', 'B'):
        result = state()
        if stage == 'hidden': assert action(result, 'eon_open_economic_consultations')
        elif stage == 'agenda': draft(result)
        else: request(result, 1)
        window = 'response' if stage == 'pending' else 'draft'
        result['countries'][cleanup_actor]['flags'].discard('eon_consultation_' + window + '_window')
        before = snapshot_other_state(result); before_pp = pp(result)
        native_hook(result, 'on_daily', cleanup_actor)
        assert not reserved(result, 'A') and not reserved(result, 'B')
        assert 'eon_consultation_retired_pair@B' in result['countries']['A']['flags']
        assert 'eon_consultation_retired_pair@A' in result['countries']['B']['flags']
        clear_cooldown(result)
        assert not action(result, 'eon_open_economic_consultations')
        draft(result, 'C', 'B'); current = deepcopy(result['countries'])
        if stage == 'hidden': immediate(result, 'eon_consultation.0', 'B', 'A')
        elif stage == 'agenda':
            result['events'].remove(queued(result, 'eon_consultation.1', 'A', 'B'))
            option_effect(result, 'eon_consultation.1', 'eon_consultation_topic_trade', 'A', 'B', force=True)
        else: response(result, 1, True, force=True)
        assert result['countries'] == current
        assert snapshot_other_state(result) == before and pp(result) == before_pp
        groups['forced_timer_cleanup_with_unconsumed_modal'] += 1

for expired_actor in ('A', 'B'):
    result = state(); request(result, 2); assert response(result, 2)
    before = snapshot_other_state(result); before_pp = pp(result)
    result['countries'][expired_actor]['flags'].discard('eon_consultation_active_window')
    native_hook(result, 'on_daily', 'A')
    assert not reserved(result, 'A') and not reserved(result, 'B')
    assert 'eon_consultation_retired_pair@B' not in result['countries']['A']['flags']
    clear_cooldown(result); request(result, 3)
    assert pp(result) == {**before_pp, 'A': before_pp['A'] - 10}
    current = deepcopy(result['countries'])
    for notice in range(20, 28): option_effect(result, 'eon_consultation.' + str(notice), 'eon_consultation_ack', 'A', 'B')
    assert result['countries'] == current and snapshot_other_state(result) == before
    groups['normal_active_expiry_and_inert_old_acknowledgements'] += 1

for closing_actor in ('A', 'B'):
    result = state(); request(result, 1); assert response(result)
    before = snapshot_other_state(result); before_pp = pp(result)
    assert action(result, 'eon_end_economic_consultations', closing_actor, 'B' if closing_actor == 'A' else 'A')
    assert not reserved(result, 'A') and not reserved(result, 'B')
    assert pp(result) == before_pp and snapshot_other_state(result) == before
    clear_cooldown(result); assert action(result, 'eon_open_economic_consultations')
    groups['either_party_free_normal_channel_close'] += 1

for war_actor in ('A', 'B'):
    result = state(); request(result, 1); assert response(result)
    result['countries'][war_actor]['wars'].add('B' if war_actor == 'A' else 'A')
    before = snapshot_other_state(result); before_pp = pp(result)
    native_hook(result, 'on_daily', 'A')
    assert not reserved(result, 'A') and not reserved(result, 'B')
    assert snapshot_other_state(result) == before and pp(result) == before_pp
    groups['active_channel_closes_on_either_war_fact'] += 1

for hook in ('on_annex', 'on_subject_annexed'):
    for victim in ('A', 'B'):
        for stage in ('agenda', 'pending', 'active'):
            result = state()
            if stage == 'agenda': draft(result)
            else:
                request(result, 3)
                if stage == 'active': assert response(result, 3)
            before = snapshot_other_state(result); before_pp = pp(result)
            result['countries'][victim]['exists'] = False
            if hook == 'on_annex': native_hook(result, hook, 'D', victim)
            else: native_hook(result, hook, victim, 'D')
            assert not reserved(result, 'A') and not reserved(result, 'B')
            result['countries'][victim]['exists'] = True
            clear_cooldown(result)
            if stage != 'active':
                assert 'eon_consultation_retired_pair@B' in result['countries']['A']['flags']
                assert 'eon_consultation_retired_pair@A' in result['countries']['B']['flags']
                assert not action(result, 'eon_open_economic_consultations')
                draft(result, 'C', 'B'); current = deepcopy(result['countries'])
                if stage == 'agenda': option_effect(result, 'eon_consultation.1', 'eon_consultation_topic_support', 'A', 'B', force=True)
                else: response(result, 3, True, force=True)
                assert result['countries'] == current
            else:
                assert 'eon_consultation_retired_pair@B' not in result['countries']['A']['flags']
                assert action(result, 'eon_open_economic_consultations')
            assert pp(result) == before_pp and snapshot_other_state(result) == before
            groups['native_annex_roles_pending_and_consumed_active'] += 1

# A malformed old A pointer must never clear B's separately owned C draft.
result = state(); draft(result, 'C', 'B')
result['countries']['A']['variables'].update(eon_consultation_partner='B', eon_consultation_topic=1)
result['countries']['A']['flags'].update({'eon_consultation_reserved', 'eon_consultation_outgoing', 'eon_consultation_response_window'})
current_b = deepcopy(result['countries']['B']); current_c = deepcopy(result['countries']['C'])
native_hook(result, 'on_daily', 'A')
assert not reserved(result, 'A')
assert result['countries']['B'] == {**current_b, 'flags': current_b['flags'] | {'eon_consultation_retired_pair@A'}}
assert result['countries']['C'] == current_c
groups['broken_reverse_pointer_preserves_unrelated_owned_session'] += 1

def ai_weight(result, identity, name, actor, partner):
    tree = one(option(identity, name), 'ai_chance')
    weight = float(one(tree, 'factor'))
    result['temp'] = {}
    for key, operator, body in tree:
        if key != 'modifier': continue
        if trigger([node for node in body if node[0] not in ('factor', 'add')], result, context(actor, partner)):
            for operation, op, operand in body:
                if operation == 'factor': weight *= value(result, context(actor, partner), operand)
                elif operation == 'add': weight += value(result, context(actor, partner), operand)
    return weight

for topic in (1, 2, 3):
    for condition, expected in (('ordinary', 2), ('opinion_50', 2), ('opinion_51', 4), ('opinion_minus25', 2), ('opinion_minus26', 0), ('same_faction', 3), ('topic_motive', 4), ('all_positive', 12), ('invalid', 0)):
        result = state(); request(result, topic); target = result['countries']['B']; target['ai'] = True
        if condition.startswith('opinion_'): target['opinions']['A'] = {'opinion_50': 50, 'opinion_51': 51, 'opinion_minus25': -25, 'opinion_minus26': -26}[condition]
        if condition in ('same_faction', 'all_positive'): target['faction'] = result['countries']['A']['faction'] = 'fixture_faction'
        if condition in ('topic_motive', 'all_positive'):
            if topic == 1: target['flags'].add('trade_agreement@A')
            elif topic == 2: target['flags'].add('energy_agreement@A')
            else: target['variables']['interest_rate'] = 8.01
        if condition == 'all_positive': target['opinions']['A'] = 51
        if condition == 'invalid': target['flags'].discard('eon_consultation_response_window')
        identity = 'eon_consultation.' + str(9 + topic)
        assert ai_weight(result, identity, 'eon_consultation_accept_talks', 'B', 'A') == expected, (topic, condition)
        assert ai_weight(result, identity, 'eon_consultation_decline_talks', 'B', 'A') == (2 if target['opinions']['A'] < 0 else 1)
        groups['literal_topic_ai_acceptance_and_nonzero_refusal'] += 1

for interest, ratio, expected in ((8, .75, 2), (8.01, .75, 4), (8, .751, 4)):
    result = state(); request(result, 3)
    result['countries']['B']['variables'].update(interest_rate=interest, debt_ratio=ratio)
    assert ai_weight(result, 'eon_consultation.12', 'eon_consultation_accept_talks', 'B', 'A') == expected
    groups['financial_ai_literal_motive_boundaries'] += 1

result = state(); draft(result)
for topic in (1, 2, 3): assert ai_weight(result, 'eon_consultation.1', 'eon_consultation_topic_' + TOPICS[topic], 'A', 'B') == 0
assert ai_weight(result, 'eon_consultation.1', 'eon_consultation_cancel_agenda', 'A', 'B') == 1
groups['human_initiation_donor_ai_cannot_send'] += 1

for topic in (1, 2):
    result = state(); request(result, topic); assert response(result, topic)
    before = deepcopy(result['countries']); before_pp = pp(result)
    assert not action(result, 'eon_consultation_offer_economic_aid', force=True)
    assert result['countries'] == before and pp(result) == before_pp
    groups['aid_followup_requires_financial_topic'] += 1

for reason in ('cash', 'influence', 'gdp', 'factories', 'national_eri', 'actor_war', 'partner_war', 'actor_aid_lock', 'partner_aid_lock', 'aid_cooldown', 'aid_legacy', 'aid_retired'):
    result = state(); request(result, 3); assert response(result, 3)
    donor, recipient = result['countries']['A'], result['countries']['B']
    if reason == 'cash': donor['variables']['treasury'] = 4.99
    elif reason == 'influence': recipient['arrays']['influence_array'] = ['C', 'D', 'B', 'C', 'D', 'B', 'C', 'A']
    elif reason == 'gdp': recipient['variables']['gdp_total'] = 200
    elif reason == 'factories': recipient['variables']['num_of_civilian_factories'] = 50
    elif reason == 'national_eri': donor['original_tag'] = 'ERI'; donor['flags'].add('ETH_transitional_government_FLAG'); donor['leader'] = 'Eritrean Transitional Government'
    elif reason == 'actor_war': donor['wars'].add('B')
    elif reason == 'partner_war': recipient['wars'].add('A')
    elif reason.endswith('aid_lock'): (donor if reason.startswith('actor') else recipient)['flags'].add('eon_aid_reserved')
    elif reason == 'aid_cooldown': donor['flags'].add('recently_sent_aid@B')
    elif reason == 'aid_legacy': recipient['flags'].add('sending_small_billion_@A')
    else: donor['flags'].add('eon_aid_retired_pair@B')
    before = deepcopy(result['countries']); before_pp = pp(result)
    assert not action(result, 'eon_consultation_offer_economic_aid', force=True), reason
    assert result['countries'] == before and pp(result) == before_pp
    assert not any(item['id'] == 'influence.0' for item in result['events'])
    groups['aid_followup_retains_actual_national_cash_and_pair_gates'] += 1

result = state(); request(result, 3); assert response(result, 3)
before_consultation = consultation_snapshot(result); before_pp = pp(result)
before_cash = {actor: data['variables']['treasury'] for actor, data in result['countries'].items()}
assert action(result, 'eon_consultation_offer_economic_aid')
assert consultation_snapshot(result) == before_consultation and pp(result) == before_pp
assert {actor: data['variables']['treasury'] for actor, data in result['countries'].items()} == before_cash
for actor, partner, role in (('A', 'B', 'draft_owner'), ('B', 'A', 'draft_recipient')):
    assert result['countries'][actor]['variables']['eon_aid_partner'] == partner
    assert result['countries'][actor]['variables']['eon_aid_amount'] == 0
    assert 'eon_aid_' + role in result['countries'][actor]['flags']
result['events'].remove(queued(result, 'influence.0', 'B', 'A'))
effect(result, one(aid_events['influence.0'], 'immediate'), context('B', 'A'))
result['events'].remove(queued(result, 'influence.1', 'A', 'B'))
aid_choice = next(body for key, operator, body in aid_events['influence.1'] if key == 'option' and one(body, 'name') == 'influence.1.a')
effect(result, aid_choice, context('A', 'B'))
assert result['countries']['A']['variables']['treasury'] == before_cash['A'] - 5
assert result['countries']['A']['variables']['eon_aid_escrow'] == 5
assert result['countries']['B']['variables']['treasury'] == before_cash['B']
aid_before_close = {actor: {'variables': {k: deepcopy(v) for k, v in data['variables'].items() if k.startswith('eon_aid_')},
                           'flags': {f for f in data['flags'] if f.startswith('eon_aid_')}} for actor, data in result['countries'].items()}
assert action(result, 'eon_end_economic_consultations')
assert aid_before_close == {actor: {'variables': {k: deepcopy(v) for k, v in data['variables'].items() if k.startswith('eon_aid_')},
                                  'flags': {f for f in data['flags'] if f.startswith('eon_aid_')}} for actor, data in result['countries'].items()}
result['events'].remove(queued(result, 'News_influence.0', 'B', 'A'))
aid_accept = next(body for key, operator, body in aid_events['News_influence.0'] if key == 'option' and one(body, 'name') == 'News_influence.0.a')
effect(result, aid_accept, context('B', 'A'))
assert result['countries']['A']['variables']['treasury'] == before_cash['A'] - 5
assert result['countries']['B']['variables']['treasury'] == before_cash['B'] + 5
assert not reserved(result, 'A') and not reserved(result, 'B')
assert 'eon_aid_reserved' not in result['countries']['A']['flags'] and 'eon_aid_reserved' not in result['countries']['B']['flags']
assert pp(result) == before_pp
assert model['money'](result)['A'] == (0.32, 0) and model['money'](result)['D'] == (0, 0.32)
groups['ordinary_aid_followup_separate_draft_escrow_and_acceptance'] += 1

result = state()
result['countries']['A']['variables'].update(eon_aid_partner='C', eon_aid_amount=5, eon_aid_escrow=5, eon_support_refund_due=17)
result['countries']['A']['flags'].update({'eon_aid_reserved', 'eon_aid_outgoing', 'trade_agreement@B', 'mutual_investment_treaty_@B'})
result['countries']['A']['variables']['pending_assume_debt_offer'] = 'D'
result['countries']['A']['variables'].update(assuming_debt_value=40, assuming_debt_repayment_value=10)
result['countries']['C']['variables'].update(eon_aid_partner='A', eon_aid_amount=5)
result['countries']['C']['flags'].update({'eon_aid_reserved', 'eon_aid_incoming'})
before = snapshot_other_state(result)
request(result, 3); assert response(result, 3)
assert action(result, 'eon_end_economic_consultations')
assert snapshot_other_state(result) == before
groups['talks_preserve_independent_aid_debt_and_existing_treaties'] += 1

# A malformed "active" marker cannot use the normal consumed-channel close
# path. Forced cleanup must retire an identity whose pending modal may survive.
for defect in ('multiple_roles', 'same_roles', 'wrong_draft_topic', 'wrong_active_topic', 'partner_pointer', 'partner_topic'):
    result = state()
    if defect == 'wrong_draft_topic':
        draft(result)
        for actor in ('A', 'B'): result['countries'][actor]['variables']['eon_consultation_topic'] = 1
    else:
        request(result, 3); assert response(result, 3)
        if defect == 'multiple_roles': result['countries']['A']['flags'].add('eon_consultation_outgoing')
        elif defect == 'same_roles':
            for actor in ('A', 'B'):
                result['countries'][actor]['flags'].discard('eon_consultation_active')
                result['countries'][actor]['flags'].add('eon_consultation_incoming')
        elif defect == 'wrong_active_topic':
            for actor in ('A', 'B'): result['countries'][actor]['variables']['eon_consultation_topic'] = 99
        elif defect == 'partner_pointer': result['countries']['B']['variables']['eon_consultation_partner'] = 'C'
        else: result['countries']['B']['variables']['eon_consultation_topic'] = 2
    before = deepcopy(result['countries']); before_other = snapshot_other_state(result); before_pp = pp(result)
    assert not action(result, 'eon_end_economic_consultations', force=True), defect
    helper(result, 'A', 'end_active')
    assert result['countries'] == before, ('Malformed end bypasses forced retirement', defect)
    native_hook(result, 'on_daily', 'A')
    assert not reserved(result, 'A')
    assert 'eon_consultation_retired_pair@B' in result['countries']['A']['flags'], defect
    assert 'eon_consultation_retired_pair@A' in result['countries']['B']['flags'], defect
    if defect == 'partner_pointer': assert reserved(result, 'B')
    else: assert not reserved(result, 'B')
    assert pp(result) == before_pp and snapshot_other_state(result) == before_other
    groups['exclusive_role_topic_and_safe_normal_end_boundaries'] += 1

for hook in ('on_annex', 'on_subject_annexed'):
    for victim in ('A', 'B'):
        result = state(); request(result, 3)
        result['countries']['A']['flags'].discard('eon_consultation_outgoing')
        result['countries']['A']['flags'].add('eon_consultation_active')
        result['countries']['A']['flags'].add('eon_consultation_active_window')
        before = snapshot_other_state(result); before_pp = pp(result)
        result['countries'][victim]['exists'] = False
        native_hook(result, hook, 'D' if hook == 'on_annex' else victim, victim if hook == 'on_annex' else 'D')
        assert not reserved(result, 'A') and not reserved(result, 'B')
        assert 'eon_consultation_retired_pair@B' in result['countries']['A']['flags']
        assert 'eon_consultation_retired_pair@A' in result['countries']['B']['flags']
        result['countries'][victim]['exists'] = True; clear_cooldown(result)
        assert not action(result, 'eon_open_economic_consultations')
        draft(result, 'C', 'B'); current = deepcopy(result['countries'])
        response(result, 3, True, force=True)
        assert result['countries'] == current
        assert snapshot_other_state(result) == before and pp(result) == before_pp
        groups['native_annex_mixed_active_unconsumed_pending_roles'] += 1

for stage in ('agenda', 'pending'):
    for expired_actor in ('A', 'B'):
        result = state()
        if stage == 'agenda': draft(result)
        else: request(result, 2)
        result['countries'][expired_actor]['flags'].discard('eon_consultation_' + ('draft' if stage == 'agenda' else 'response') + '_window')
        before = snapshot_other_state(result); before_pp = pp(result)
        # The engine supplies each country's daily callback independently. If
        # the other country runs first, the expired owner still cleans locally
        # on its next callback; a missing counterpart timer never funds a send.
        other = 'B' if expired_actor == 'A' else 'A'
        native_hook(result, 'on_daily', other)
        if stage == 'agenda':
            assert not check(result, [('eon_consultation_draft_send_ready', '=', 'yes')], context('A', 'B'), {'eon_consultation_proposed_topic': 2})
        else:
            assert not check(result, [('eon_consultation_response_valid', '=', 'yes')], context('B', 'A'), {'eon_consultation_response_topic': 2})
        native_hook(result, 'on_daily', expired_actor)
        assert not reserved(result, 'A') and not reserved(result, 'B')
        assert 'eon_consultation_retired_pair@B' in result['countries']['A']['flags']
        assert 'eon_consultation_retired_pair@A' in result['countries']['B']['flags']
        assert snapshot_other_state(result) == before and pp(result) == before_pp
        groups['mirrored_pending_window_expiry_and_daily_order'] += 1

for topic in (1, 2, 3):
    for fact in ('recipient_war', 'actor_war', 'recipient_ttl', 'actor_ttl', 'recipient_dead', 'actor_dead', 'matching_cancelled'):
        result = state(); request(result, topic)
        if fact.endswith('war'): result['countries']['B' if fact.startswith('recipient') else 'A']['wars'].add('A' if fact.startswith('recipient') else 'B')
        elif fact.endswith('ttl'): result['countries']['B' if fact.startswith('recipient') else 'A']['flags'].discard('eon_consultation_response_window')
        elif fact.endswith('dead'): result['countries']['B' if fact.startswith('recipient') else 'A']['exists'] = False
        else: result['countries']['A']['flags'].add('eon_consultation_cancelled')
        before = deepcopy(result['countries'])
        expected = 'eon_consultation_cancelled_invite_desc' if fact == 'matching_cancelled' else 'eon_consultation_stale_invite_desc'
        assert selected_desc(result, 'eon_consultation.' + str(9 + topic), 'B', 'A') == expected, (topic, fact)
        assert result['countries'] == before
        groups['exclusive_literal_invite_status_under_fresh_invalid_facts'] += 1

source_paths = ['common/scripted_effects/eon_consultation_effects.txt', 'common/scripted_triggers/eon_consultation_triggers.txt',
                'common/scripted_diplomatic_actions/eon_consultation_actions.txt', 'common/on_actions/eon_consultation_on_actions.txt',
                'events/eon_consultation_events.txt', 'localisation/english/eon_consultation_l_english.yml',
                'localisation/russian/eon_consultation_l_russian.yml', 'common/scripted_effects/eon_aid_effects.txt',
                'common/scripted_triggers/eon_aid_triggers.txt', 'common/scripted_effects/00_budget_effects.txt']
print(json.dumps({'all_passed': True, 'total_cases': sum(groups.values()), 'groups': groups,
                  'actual_source_scenarios': sum(groups.values()) - groups['native_nor_and_explicit_nand_truth_table'],
                  'adapter_semantics_cases': groups['native_nor_and_explicit_nand_truth_table'],
                  'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source_paths},
                  'proof_scope': 'ordered actual-source consultation lifecycle with supplied native country facts',
                  'not_proven': ['native callbacks and timer expiry', 'GUI', 'save/load', 'campaign']}, indent=2))
