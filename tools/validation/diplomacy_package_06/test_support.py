"""Actual-source economic support checks; bounded execution, not HOI4 runtime."""
from pathlib import Path
from copy import deepcopy
from collections import Counter
import contextlib
import hashlib
import io
import json
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '551d7100f6c35cd062a36520f6a7eed199b13a2e'
sys.path.insert(0, str(ROOT / 'tools/validation/diplomacy_package_01'))
with contextlib.redirect_stdout(io.StringIO()):
    model = runpy.run_path(str(ROOT / 'tools/validation/diplomacy_package_01/test_energy.py'))
ast, one = model['ast'], model['one']
environment = model['execute'].__globals__
base_execute = model['execute']
base_trigger = model['trigger']
base_country_ref = model['country_ref']
base_compare = model['compare']
base_value = model['value']
context, switch = model['context'], model['switch']
groups = Counter()

def read(path): return (ROOT / path).read_text(encoding='utf-8-sig')
def baseline(path):
    return subprocess.check_output(['git', 'show', BASELINE + ':' + path], cwd=ROOT).decode('utf-8-sig')

# Expand the actual treasury clamp rather than copying its arithmetic.
environment['effects']['modify_treasury_effect'] = one(ast(read('common/scripted_effects/00_budget_effects.txt')), 'modify_treasury_effect')

def country_ref(state, ctx, token):
    if token.startswith('event_target:'):
        return state.get('event_targets', {}).get(token.split(':', 1)[1])
    return base_country_ref(state, ctx, token)

environment['country_ref'] = country_ref

def compare(left, operator, right):
    # Native stored country IDs are positive numbers. Symbolic country labels
    # retain identity but need their positive ordinal for native >0 existence.
    if operator not in ('=', '==', '!='):
        if isinstance(left, str) and left in ('A', 'B', 'C', 'D'): left = ord(left) - ord('A') + 1
        if isinstance(right, str) and right in ('A', 'B', 'C', 'D'): right = ord(right) - ord('A') + 1
    return base_compare(left, operator, right)

environment['compare'] = compare

def value(state, ctx, expression):
    if isinstance(expression, str) and 'opinion@' in expression:
        if '.' in expression:
            actor, tail = expression.split('.', 1)
            return value(state, switch(ctx, country_ref(state, ctx, actor)), tail)
        target = country_ref(state, ctx, expression.split('@', 1)[1])
        return state['countries'][ctx['scope']].get('opinions', {}).get(target, 0)
    return base_value(state, ctx, expression)

environment['value'] = value

def trigger(nodes, state, ctx):
    index = 0
    while index < len(nodes):
        key, op, val = nodes[index]; index += 1
        grouped = [(key, op, val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        owner = state['countries'][ctx['scope']]
        if key == 'tooltip': passed = True
        elif key == 'ai_has_same_organization': passed = owner.get('same_organization', False) == (val == 'yes')
        elif key == 'is_subject_of': passed = owner.get('overlord') == country_ref(state, ctx, val)
        elif key == 'is_in_faction': passed = bool(owner.get('allies', [])) == (val == 'yes')
        elif key == 'any_allied_country': passed = any(trigger(val, state, switch(ctx, ally)) for ally in owner.get('allies', []))
        elif key == 'has_country_leader': passed = owner.get('leader') == one(val, 'name')
        elif key == 'has_opinion':
            target = country_ref(state, ctx, one(val, 'target'))
            operator, wanted = next((o, v) for k, o, v in val if k == 'value')
            passed = model['compare'](owner.get('opinions', {}).get(target, 0), operator, float(wanted))
        elif key == 'has_idea': passed = val in owner.get('ideas', set())
        elif key == 'has_political_power': passed = model['compare'](owner['variables'].get('political_power', 0), op, float(val))
        elif key == 'has_government': passed = owner.get('government', 'democratic') == val
        elif key in ('has_autocratic_government_or_in_coalition', 'has_totalitarian_government_or_in_coalition'):
            passed = owner.get(key, False) == (val == 'yes')
        elif key.startswith('event_target:'):
            target = country_ref(state, ctx, key)
            passed = target in state['countries'] and trigger(val, state, switch(ctx, target))
        else: passed = base_trigger(grouped, state, ctx)
        if not passed: return False
    return True

environment['trigger'] = trigger

def execute(nodes, state, ctx):
    index = 0
    while index < len(nodes):
        key, op, val = nodes[index]; index += 1
        grouped = [(key, op, val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        if key == 'effect_tooltip': continue  # Preview only, no actual transfer.
        if key == 'else':
            assert val == [('custom_effect_tooltip', '=', 'recently_refused_economic_aid_tt')]
            continue  # Legacy malformed tooltip-only branch has no cash effect.
        if key in ('change_influence_percentage', 'add_ruling_outlook_popularity', 'add_opinion_modifier', 'reverse_add_opinion_modifier'):
            state.setdefault('external_calls', []).append((ctx['scope'], key, deepcopy(val), deepcopy(state['temp'])))
        elif key == 'add_political_power':
            variables = state['countries'][ctx['scope']]['variables']
            variables['political_power'] = variables.get('political_power', 0) + float(val)
        elif key == 'save_event_target_as':
            state.setdefault('event_targets', {})[val] = ctx['scope']
        elif key.startswith('event_target:'):
            target = country_ref(state, ctx, key)
            if target in state['countries']: execute(val, state, switch(ctx, target))
        elif key == 'divide_temp_variable':
            variable, _, rhs = val[0]
            state['temp'][variable] = state['temp'].get(variable, 0) / model['value'](state, ctx, rhs)
        elif key == 'every_country':
            limits = [v for k, o, v in val if k == 'limit']
            for actor, data in state['countries'].items():
                inner = switch(ctx, actor)
                if data['exists'] and (not limits or trigger(limits[0], state, inner)):
                    execute([n for n in val if n[0] != 'limit'], state, inner)
        elif key == 'update_dirty_influence_var': state['ui_updates'] += 1
        else: base_execute(grouped, state, ctx)

environment['execute'] = execute

def state(wallet=100, recipient_wallet=0):
    result = model['state']()
    for country in result['countries'].values():
        country['variables'].update(treasury=0, debt=40, gdp_total=100, debt_ratio=.5, political_power=300,
                                    interest_rate=5, num_of_civilian_factories=50)
        country.update(influencer=True, leader='Ordinary President', opinions={'A': 100, 'B': 100, 'C': 100, 'D': 100},
                       allies=[], ideas=set(), original_tag='OTH')
        country['arrays']['influence_array'] = ['A', 'C', 'D', 'B']
    result['countries']['B']['variables'].update(gdp_total=50, num_of_civilian_factories=20)
    result['countries']['A']['variables']['treasury'] = wallet
    result['countries']['B']['variables']['treasury'] = recipient_wallet
    return result

def cash(result): return {c: result['countries'][c]['variables']['treasury'] for c in ('A', 'B')}
def event_option(events, event, name):
    return next(v for k, o, v in events[event] if k == 'option' and one(v, 'name') == name)

legacy = model['get_event_map'](baseline('events/00_Influence_events.txt'))
def old_choose(result, option): execute(event_option(legacy, 'influence.1', option), result, context('A', 'B'))
def old_reply(result, accepted=True):
    execute(event_option(legacy, 'News_influence.0', 'News_influence.0.' + ('a' if accepted else 'b')), result, context('B', 'A'))

result = state(1); old_choose(result, 'influence.1.a')
assert cash(result) == {'A': -4.0, 'B': 0}
groups['literal_baseline_defects'] += 1
result = state(); old_choose(result, 'influence.1.a'); old_choose(result, 'influence.1.c'); old_reply(result)
assert cash(result) == {'A': 60.0, 'B': 5.0}
groups['literal_baseline_defects'] += 1
result = state(100, 999999); old_choose(result, 'influence.1.a'); old_reply(result)
assert cash(result) == {'A': 95.0, 'B': 1000000.0}
groups['literal_baseline_defects'] += 1
result = state(); old_choose(result, 'influence.1.c'); result['countries']['A']['variables']['treasury'] = 999990; old_reply(result, False)
assert cash(result) == {'A': 1000000.0, 'B': 0}
groups['literal_baseline_defects'] += 1

effect_path = ROOT / 'common/scripted_effects/eon_aid_effects.txt'
assert effect_path.exists(), 'RED: aid send/settlement helpers are not implemented'
helpers = ast(effect_path.read_text(encoding='utf-8-sig'))
assert one(helpers, 'eon_aid_send_offer'), 'RED: eon_aid_send_offer is missing'

for path in ('common/scripted_effects/eon_aid_effects.txt', 'common/scripted_effects/eon_support_effects.txt'):
    environment['effects'].update({k: v for k, o, v in ast(read(path))})
for path in ('common/scripted_triggers/eon_aid_triggers.txt', 'common/scripted_triggers/eon_debt_support_triggers.txt',
             'common/scripted_triggers/99_ERI_scripted_triggers.txt', 'common/scripted_triggers/00_debt_ratio_triggers.txt'):
    environment['capacity_triggers'].update({k: v for k, o, v in ast(read(path))})
environment['capacity_triggers']['is_influencer'] = one(ast(read('common/scripted_triggers/00_influence_scripted_triggers.txt')), 'is_influencer')
events = model['get_event_map'](read('events/00_Influence_events.txt'))
native_actions = one(ast(read('common/scripted_diplomatic_actions/00_scripted_diplomatic_actions.txt')), 'scripted_diplomatic_actions')
debt = one(native_actions, 'diplo_action_assume_debt')
aid_gui = one(one(ast(read('common/scripted_guis/influence_scripted_gui.txt')), 'scripted_gui'), 'scripted_influence_option_buttons')
aid_click = one(one(aid_gui, 'effects'), 'opt_aid_button_click')
aid_enabled = one(one(aid_gui, 'triggers'), 'opt_aid_button_click_enabled')

def check(result, nodes, ctx, temporary=None):
    result['temp'] = dict(temporary or {})
    return trigger(nodes, result, ctx)
def effect(result, nodes, ctx, temporary=None):
    result['temp'] = dict(temporary or {})
    execute(nodes, result, ctx)
def helper(result, actor, name, other=None, scope=None, temporary=None):
    effect(result, [(name, '=', 'yes')], context(actor, other, scope=scope), temporary)
def owned_cash(result):
    return sum(d['variables'].get('treasury', 0) + d['variables'].get('eon_aid_escrow', 0)
               + d['variables'].get('eon_support_refund_due', 0) for d in result['countries'].values())
def pending(result, actor): return 'eon_aid_reserved' in result['countries'][actor]['flags']
def assert_no_aid(result, *actors):
    for actor in actors:
        owner = result['countries'][actor]
        active_flags = {'eon_aid_reserved', 'eon_aid_draft_owner', 'eon_aid_draft_recipient',
                        'eon_aid_outgoing', 'eon_aid_incoming', 'eon_aid_cancelled'}
        assert not active_flags.intersection(owner['flags']), (actor, owner)
        assert not {k: v for k, v in owner['variables'].items() if k.startswith('eon_aid_') and v}, (actor, owner)

def open_draft(result, donor='A', recipient='B'):
    ctx = context(donor, scope=recipient)
    enabled = check(result, aid_enabled, ctx)
    effect(result, aid_click, ctx)
    return enabled
def queued(result, identity, actor, sender=None):
    matches = [entry for entry in result['events'] if entry['id'] == identity and entry['target'] == actor
               and (sender is None or entry['from'] == sender)]
    assert len(matches) == 1, (identity, actor, sender, result['events'])
    return matches[0]
def consume_immediate(result, identity, actor, sender):
    entry = queued(result, identity, actor, sender); result['events'].remove(entry)
    effect(result, one(events[identity], 'immediate'), context(actor, sender))
def choose(result, amount, donor='A', recipient='B', force=False):
    name = 'influence.1.' + {5: 'a', 15: 'b', 35: 'c'}[amount]
    option = event_option(events, 'influence.1', name)
    ctx = context(donor, recipient)
    guards = [v for k, o, v in option if k == 'trigger']
    enabled = not guards or check(result, guards[0], ctx)
    if enabled or force: effect(result, option, ctx)
    return enabled
def offer(result, amount=5, donor='A', recipient='B'):
    assert open_draft(result, donor, recipient)
    consume_immediate(result, 'influence.0', recipient, donor)
    entry = queued(result, 'influence.1', donor, recipient); result['events'].remove(entry)
    assert choose(result, amount, donor, recipient)
    queued(result, 'News_influence.0', recipient, donor)
def reply(result, accepted=True, recipient='B', donor='A', force=False, consume=True):
    option = event_option(events, 'News_influence.0', 'News_influence.0.' + ('a' if accepted else 'b'))
    ctx = context(recipient, donor)
    guards = [v for k, o, v in option if k == 'trigger']
    enabled = not guards or check(result, guards[0], ctx)
    if enabled or force:
        if consume:
            entry = queued(result, 'News_influence.0', recipient, donor); result['events'].remove(entry)
        effect(result, option, ctx)
    return enabled

# Existing saves may contain the old prepaid denomination flags without a new
# reservation. Identifiable legacy sums are refunded once; the pair is then
# quarantined because old queued modal counts/generations cannot be recovered.
for tier in ('small', 'medium', 'high'):
    result = state(65)
    result['countries']['B']['flags'].add('sending_' + tier + '_billion_@A')
    frozen = deepcopy(result['countries'])
    assert not open_draft(result, 'A', 'B'), 'Known prepaid flags must block a new same-pair modal'
    assert result['countries'] == frozen
    groups['legacy_known_pending_blocks_same_pair_before_recovery'] += 1

for accepted in (False, True):
    for tiers, held in ((('small',), 5), (('medium',), 15), (('high',), 35), (('small', 'high'), 40)):
        result = state(100 - held)
        for tier in tiers: result['countries']['B']['flags'].add('sending_' + tier + '_billion_@A')
        result['events'].append({'target': 'B', 'id': 'News_influence.0', 'from': 'A'})
        before_pp = result['countries']['B']['variables']['political_power']
        reply(result, accepted=accepted, force=True)
        assert cash(result) == {'A': 100, 'B': 0}, 'Legacy prepaid aid was not refunded'
        assert result['countries']['B']['variables']['political_power'] == before_pp
        assert result.get('external_calls', []) == []
        assert not {flag for flag in result['countries']['B']['flags'] if flag.startswith('sending_')}
        assert 'eon_aid_legacy_quarantined@A' in result['countries']['B']['flags']
        frozen = deepcopy(result['countries'])
        reply(result, accepted=accepted, force=True, consume=False)
        assert result['countries'] == frozen, 'Repeated legacy callback refunded twice'
        assert not open_draft(result, 'A', 'B'), 'Quarantined legacy pair must not admit a new modal'
        assert result['countries'] == frozen
        result['countries']['C']['variables'].update(gdp_total=50, num_of_civilian_factories=20)
        assert open_draft(result, 'A', 'C'), 'Different pair remains usable'
        groups['legacy_prepaid_recovery_once_without_political_rewards'] += 1

for accepted in (False, True):
    result = state(95)
    result['countries']['C']['variables']['treasury'] = 100
    offer(result, 15, donor='C', recipient='B')
    pending_c = deepcopy(result['countries']['C'])
    frozen_pair = {k: deepcopy(v) for k, v in result['countries']['B']['variables'].items() if k.startswith('eon_aid_')}
    result['countries']['B']['flags'].add('sending_small_billion_@A')
    result['events'].append({'target': 'B', 'id': 'News_influence.0', 'from': 'A'})
    reply(result, accepted=accepted, force=True)
    assert result['countries']['A']['variables']['treasury'] == 100
    assert result['countries']['C'] == pending_c
    assert {k: v for k, v in result['countries']['B']['variables'].items() if k.startswith('eon_aid_')} == frozen_pair
    assert pending(result, 'B') and pending(result, 'C')
    assert result.get('external_calls', []) == []
    assert reply(result, donor='C', recipient='B')
    assert result['countries']['B']['variables']['treasury'] == 15
    groups['legacy_reply_preserves_other_pair_reservation'] += 1

result = state(999990)
result['countries']['B']['flags'].add('sending_high_billion_@A')
result['events'].append({'target': 'B', 'id': 'News_influence.0', 'from': 'A'})
reply(result, accepted=False, force=True)
assert result['countries']['A']['variables']['treasury'] == 1000000
assert result['countries']['A']['variables']['eon_support_refund_due'] == 25
groups['legacy_refund_preserves_cap_overflow_claim'] += 1

result = state(65)
result['countries']['A']['exists'] = False
result['countries']['B']['flags'].add('sending_high_billion_@A')
result['events'].append({'target': 'B', 'id': 'News_influence.0', 'from': 'A'})
reply(result, accepted=True, force=True)
assert cash(result) == {'A': 65, 'B': 0}
assert result['countries']['A']['variables']['eon_support_refund_due'] == 35
groups['legacy_deceased_donor_claim_is_retained'] += 1

legacy_hooks = one(ast(read('common/on_actions/eon_support_on_actions.txt')), 'on_actions')
before_legacy_assets = owned_cash(result)
effect(result, one(one(legacy_hooks, 'on_annex'), 'effect'), context('C', 'A'))
assert result['countries']['A']['variables'].get('eon_support_refund_due', 0) == 0
assert result['countries']['C']['variables']['treasury'] == 35
assert owned_cash(result) == before_legacy_assets
frozen = deepcopy(result['countries'])
effect(result, one(one(legacy_hooks, 'on_annex'), 'effect'), context('C', 'A'))
assert result['countries'] == frozen
groups['legacy_deceased_donor_claim_transfers_once'] += 1

# A country that disappears may later be recreated with the same native tag.
# A response still queued before cleanup must not authorize a new same-pair
# generation. Retire only that pair; a different partner remains usable.
retirement_hooks = one(ast(read('common/on_actions/eon_support_on_actions.txt')), 'on_actions')
for cleanup in ('annex', 'daily then annex'):
    result = state(); offer(result, 15)
    result['countries']['B']['exists'] = False
    if cleanup == 'daily then annex':
        effect(result, one(one(retirement_hooks, 'on_daily'), 'effect'), context('A'))
    effect(result, one(one(retirement_hooks, 'on_annex'), 'effect'), context('C', 'B'))
    result['countries']['B']['exists'] = True
    result['countries']['A']['flags'].discard('recently_sent_aid@B')  # 30 days may have elapsed.
    assert not open_draft(result, 'A', 'B'), 'Cleaned aid callback pair can be reused after country recreation'
    result['countries']['C']['variables'].update(gdp_total=50, num_of_civilian_factories=20)
    offer(result, 5, donor='A', recipient='C')
    frozen = deepcopy(result['countries'])
    reply(result, accepted=True, recipient='B', donor='A', force=True)
    assert result['countries'] == frozen and pending(result, 'A') and pending(result, 'C')
    groups['retired_aid_pair_blocks_revived_tag_old_callback'] += 1

for cleanup in ('daily', 'annex'):
    result = state(); result['countries']['B']['variables']['debt'] = 100
    old_ctx = context('A', scope='B')
    effect(result, one(debt, 'on_sent_effect'), old_ctx)
    result['countries']['B']['exists'] = False
    if cleanup == 'daily': effect(result, one(one(retirement_hooks, 'on_daily'), 'effect'), context('A'))
    else: effect(result, one(one(retirement_hooks, 'on_annex'), 'effect'), context('C', 'B'))
    result['countries']['B']['exists'] = True
    assert not check(result, one(debt, 'can_be_sent'), old_ctx), 'Cleaned debt callback pair can be reused after country recreation'
    other_ctx = context('A', scope='C')
    assert check(result, one(debt, 'can_be_sent'), other_ctx), 'Retiring a debt pair must not create a global lock'
    effect(result, one(debt, 'on_sent_effect'), other_ctx)
    frozen = deepcopy(result['countries'])
    effect(result, one(debt, 'complete_effect'), old_ctx)
    assert result['countries'] == frozen, 'Retired debt callback changed a different partner request'
    groups['retired_debt_pair_blocks_revived_tag_old_callback'] += 1

# The donor may disappear as well. Native victim/successor scopes must retire
# its own outgoing callback pair before clearing ownership, in both annex hooks.
for hook in ('on_annex', 'on_subject_annexed'):
    result = state(); offer(result, 15)
    result['countries']['A']['exists'] = False
    ctx = context('C', 'A') if hook == 'on_annex' else context('A', 'C')
    total = owned_cash(result)
    effect(result, one(one(retirement_hooks, hook), 'effect'), ctx)
    assert owned_cash(result) == total
    assert result['countries']['C']['variables']['treasury'] == 15
    assert_no_aid(result, 'A', 'B')
    result['countries']['A']['exists'] = True
    result['countries']['A']['flags'].discard('recently_sent_aid@B')
    assert not open_draft(result, 'A', 'B'), 'Recreated aid donor can reuse its old callback pair'
    result['countries']['C']['variables'].update(gdp_total=50, num_of_civilian_factories=20)
    offer(result, 5, donor='A', recipient='C')
    frozen = deepcopy(result['countries'])
    reply(result, recipient='B', donor='A', force=True)
    assert result['countries'] == frozen
    groups['revived_donor_aid_pair_retirement_and_assets'] += 1

    result = state(); result['countries']['B']['variables']['debt'] = 100
    old_ctx = context('A', scope='B')
    effect(result, one(debt, 'on_sent_effect'), old_ctx)
    result['countries']['A']['exists'] = False
    effect(result, one(one(retirement_hooks, hook), 'effect'), ctx)
    result['countries']['A']['exists'] = True
    assert not check(result, one(debt, 'can_be_sent'), old_ctx), 'Recreated debt donor can reuse its old callback pair'
    other_ctx = context('A', scope='C')
    assert check(result, one(debt, 'can_be_sent'), other_ctx)
    effect(result, one(debt, 'on_sent_effect'), other_ctx)
    frozen = deepcopy(result['countries'])
    effect(result, one(debt, 'complete_effect'), old_ctx)
    assert result['countries'] == frozen
    groups['revived_donor_debt_pair_retirement'] += 1

for alteration in ('valid', 'last eligible influencer slot', 'eighth influencer slot', 'no donor influence',
                   'target GDP boundary', 'equal factories', 'donor war', 'recipient war',
                   'donor absent', 'recipient absent', 'low donor cash', 'pair cooldown',
                   'ERI transitional', 'ERI ordinary leader', 'other legacy donor'):
    result = state()
    donor, recipient = result['countries']['A'], result['countries']['B']
    if alteration == 'last eligible influencer slot': recipient['arrays']['influence_array'] = ['C'] * 6 + ['A']
    elif alteration == 'eighth influencer slot': recipient['arrays']['influence_array'] = ['C'] * 7 + ['A']
    elif alteration == 'no donor influence': recipient['arrays']['influence_array'] = ['C', 'D']
    elif alteration == 'target GDP boundary': recipient['variables']['gdp_total'] = 200
    elif alteration == 'equal factories': recipient['variables']['num_of_civilian_factories'] = 50
    elif alteration == 'donor war': donor['wars'].add('B')
    elif alteration == 'recipient war': recipient['wars'].add('A')
    elif alteration == 'donor absent': donor['exists'] = False
    elif alteration == 'recipient absent': recipient['exists'] = False
    elif alteration == 'low donor cash': donor['variables']['treasury'] = 4
    elif alteration == 'pair cooldown': donor['flags'].add('recently_sent_aid@B')
    elif alteration.startswith('ERI'):
        donor.update(original_tag='ERI', leader='Eritrean Transitional Government' if alteration == 'ERI transitional' else 'Ordinary President')
        donor['flags'].add('ETH_transitional_government_FLAG')
    elif alteration == 'other legacy donor': recipient['flags'].add('sending_small_billion_@C')
    valid = alteration in ('valid', 'last eligible influencer slot', 'ERI ordinary leader', 'other legacy donor')
    assert open_draft(result) == valid, alteration
    assert pending(result, 'A') == pending(result, 'B') == valid
    assert cash(result) == {'A': 4 if alteration == 'low donor cash' else 100, 'B': 0}
    groups['actual_aid_national_policy_and_country_facts'] += 1

for amount, influence, modifier in ((5, 3, 'given_gift_small'), (15, 5, 'given_gift_medium'), (35, 7, 'given_gift_high')):
    for accepted in (False, True):
        result = state(100, 10); total = owned_cash(result)
        offer(result, amount)
        assert cash(result) == {'A': 100 - amount, 'B': 10}
        assert result['countries']['A']['variables']['eon_aid_escrow'] == amount
        assert result['countries']['B']['variables']['eon_aid_amount'] == amount
        assert result['countries']['B']['variables']['debt'] == 40
        assert result.get('external_calls', []) == [], 'Selection must not apply political consequences'
        assert owned_cash(result) == total
        assert pending(result, 'A') and pending(result, 'B')
        assert reply(result, accepted)
        assert cash(result) == ({'A': 100 - amount, 'B': 10 + amount} if accepted else {'A': 100, 'B': 10})
        assert owned_cash(result) == total
        assert_no_aid(result, 'A', 'B')
        calls = result.get('external_calls', [])
        if accepted:
            changes = [call for call in calls if call[1] == 'change_influence_percentage']
            assert len(changes) == 1 and changes[0][0] == 'B'
            assert changes[0][3]['percent_change'] == influence
            assert changes[0][3]['tag_index'] == 'A' and changes[0][3]['influence_target'] == 'B'
            opinions = [call for call in calls if call[1] == 'add_opinion_modifier']
            assert len(opinions) == 1 and one(opinions[0][2], 'modifier') == modifier
        else:
            assert result['countries']['B']['variables']['political_power'] == 350
            assert len([call for call in calls if call[1] == 'add_ruling_outlook_popularity']) == 1
        saved = deepcopy(result['countries']); saved_calls = deepcopy(calls)
        reply(result, accepted, force=True, consume=False)
        assert result['countries'] == saved and result.get('external_calls', []) == saved_calls
        groups['literal_aid_accept_refuse_and_duplicate'] += 1

for wallet in (1, 4, 5, 14, 15, 34, 35, 100):
    for amount in (5, 15, 35):
        result = state(100)
        assert open_draft(result)
        consume_immediate(result, 'influence.0', 'B', 'A')
        entry = queued(result, 'influence.1', 'A', 'B'); result['events'].remove(entry)
        result['countries']['A']['variables']['treasury'] = wallet
        assert choose(result, amount, force=True) == (wallet >= amount)
        assert owned_cash(result) == wallet
        assert result['countries']['A']['variables']['treasury'] == (wallet - amount if wallet >= amount else wallet)
        if wallet >= amount:
            assert pending(result, 'A') and pending(result, 'B')
        else:
            assert_no_aid(result, 'A', 'B')
            assert not [event for event in result['events'] if event['id'] == 'News_influence.0']
        groups['fresh_wallet_denomination_guard'] += 1

for actor, receiver in (('A', 'B'), ('A', 'C'), ('C', 'B'), ('B', 'A')):
    result = state(); offer(result, 5)
    result['countries']['C']['variables']['treasury'] = 100
    frozen = deepcopy(result['countries']); total = owned_cash(result)
    open_draft(result, actor, receiver)
    choose(result, 35, actor, receiver, force=True)
    assert result['countries'] == frozen, 'Overlapping/stale amount selection changed original offer'
    assert owned_cash(result) == total
    assert reply(result)
    assert cash(result) == {'A': 95, 'B': 5}
    groups['overlap_and_stale_denomination_are_inert'] += 1

for alteration in ('recipient cap', 'war', 'recipient amount', 'donor amount', 'donor absent', 'recipient absent',
                   'influencer lost', 'recipient GDP grown', 'donor factories lost', 'national restriction'):
    result = state(); offer(result, 35)
    donor, recipient = result['countries']['A'], result['countries']['B']
    if alteration == 'recipient cap': recipient['variables']['treasury'] = 999990
    elif alteration == 'war': recipient['wars'].add('A')
    elif alteration == 'recipient amount': recipient['variables']['eon_aid_amount'] = 5
    elif alteration == 'donor amount': donor['variables']['eon_aid_amount'] = 15
    elif alteration == 'donor absent': donor['exists'] = False
    elif alteration == 'recipient absent': recipient['exists'] = False
    elif alteration == 'influencer lost': recipient['arrays']['influence_array'] = ['C', 'D', 'B']
    elif alteration == 'recipient GDP grown': recipient['variables']['gdp_total'] = 200
    elif alteration == 'donor factories lost': donor['variables']['num_of_civilian_factories'] = 20
    elif alteration == 'national restriction':
        donor.update(original_tag='ERI', leader='Eritrean Transitional Government'); donor['flags'].add('ETH_transitional_government_FLAG')
    total = owned_cash(result); before_target_cash = recipient['variables']['treasury']
    assert not reply(result, accepted=True, force=True), alteration
    assert recipient['variables']['treasury'] == before_target_cash
    assert result.get('external_calls', []) == []
    # A deceased donor must retain the claim for later annex inheritance.
    # Consuming an invalid reply may not silently discard its held ownership.
    assert owned_cash(result) == total, alteration
    assert_no_aid(result, 'A', 'B')
    groups['response_invalidated_without_political_rewards'] += 1

for target, sender, helper_name in (('C', 'A', 'eon_aid_accept_offer'), ('B', 'C', 'eon_aid_refuse_offer'),
                                    ('A', 'B', 'eon_aid_accept_offer'), ('B', 'C', 'eon_aid_finish_response')):
    result = state(); offer(result, 15)
    before = deepcopy(result['countries']); calls = deepcopy(result.get('external_calls', []))
    helper(result, target, helper_name, sender)
    assert result['countries'] == before and result.get('external_calls', []) == calls
    assert pending(result, 'A') and pending(result, 'B')
    groups['wrong_pair_and_wrong_role_callbacks'] += 1

result = state(); assert open_draft(result)
consume_immediate(result, 'influence.0', 'B', 'A')
before = owned_cash(result)
effect(result, event_option(events, 'influence.1', 'influence.1.e'), context('A', 'B'))
assert owned_cash(result) == before and cash(result) == {'A': 100, 'B': 0}
assert result.get('external_calls', []) == []
assert_no_aid(result, 'A', 'B')
groups['draft_cancel_has_no_financial_or_political_effects'] += 1

withdraw_actions = one(ast(read('common/scripted_diplomatic_actions/eon_support_actions.txt')), 'scripted_diplomatic_actions')
withdraw = one(withdraw_actions, 'eon_withdraw_economic_aid')
for wallet_after_send, expected_wallet, expected_ledger in ((65, 100, 0), (999990, 1000000, 25), (1000000, 1000000, 35)):
    for accepted in (False, True):
        result = state(); offer(result, 35)
        result['countries']['A']['variables']['treasury'] = wallet_after_send
        total = owned_cash(result)
        assert check(result, one(withdraw, 'can_be_sent'), context('A', scope='B'))
        effect(result, one(withdraw, 'complete_effect'), context('A', scope='B'))
        donor = result['countries']['A']['variables']
        assert donor['treasury'] == expected_wallet and donor.get('eon_support_refund_due', 0) == expected_ledger
        assert donor['eon_aid_escrow'] == 0 and owned_cash(result) == total
        assert pending(result, 'A') and pending(result, 'B')
        assert 'eon_aid_cancelled' in result['countries']['A']['flags'] and 'eon_aid_cancelled' in result['countries']['B']['flags']
        frozen = deepcopy(result['countries'])
        effect(result, one(withdraw, 'complete_effect'), context('A', scope='B'))
        assert result['countries'] == frozen
        open_draft(result, 'A', 'C'); assert result['countries'] == frozen
        reply(result, accepted=accepted, force=True)
        assert_no_aid(result, 'A', 'B')
        assert result.get('external_calls', []) == []
        assert owned_cash(result) == total
        groups['withdrawal_refund_and_serialized_old_reply'] += 1

for recipient_wallet, accepted, expected_cash, expected_due in (
        (999965, True, {'A': 65, 'B': 1000000}, 0),
        (999966, True, {'A': 100, 'B': 999966}, 0),
        (999990, False, {'A': 100, 'B': 999990}, 0)):
    result = state(100, recipient_wallet); offer(result, 35)
    total = owned_cash(result)
    reply(result, accepted=accepted, force=True)
    assert cash(result) == expected_cash and owned_cash(result) == total
    assert result['countries']['A']['variables'].get('eon_support_refund_due', 0) == expected_due
    groups['literal_recipient_capacity_never_clamps_gift'] += 1

def ai_weight(result, identity, name, ctx):
    option = event_option(events, identity, name)
    guards = [v for k, o, v in option if k == 'trigger']
    result['temp'] = {}
    if guards and not trigger(guards[0], result, ctx): return 0
    body = one(option, 'ai_chance')
    weight = 0
    for key, op, val in body:
        if key in ('base', 'factor'): weight = float(value(result, ctx, val))
        elif key == 'modifier':
            conditions = [n for n in val if n[0] not in ('factor', 'add')]
            if trigger(conditions, result, ctx):
                for action, _, amount in val:
                    if action == 'factor': weight *= float(value(result, ctx, amount))
                    elif action == 'add': weight += float(value(result, ctx, amount))
        else: raise AssertionError(('Unknown AI arithmetic', key))
    return weight

for wallet, expected_positive in ((1, ['e']), (5, ['a', 'e']), (15, ['a', 'b', 'e']), (35, ['a', 'b', 'c', 'e'])):
    result = state(); assert open_draft(result)
    consume_immediate(result, 'influence.0', 'B', 'A')
    result['countries']['A']['variables']['treasury'] = wallet
    scores = {suffix: ai_weight(result, 'influence.1', 'influence.1.' + suffix, context('A', 'B')) for suffix in ('a', 'b', 'c', 'e')}
    assert [suffix for suffix, score in scores.items() if score > 0] == expected_positive, scores
    groups['actual_ai_affordable_tiers_and_cancel_fallback'] += 1

for interest, ratio, domestic, invalid in ((5, .5, 50, False), (3, 2, 50, False), (20, .4, 50, False),
                                         (5, .5, 0, False), (5, .5, 50, True)):
    result = state(); offer(result, 5)
    result['countries']['B']['variables'].update(interest_rate=interest, debt_ratio=ratio, domestic_influence_amount=domestic, gdp_per_capita=10)
    if invalid: result['countries']['B']['wars'].add('A')
    scores = {suffix: ai_weight(result, 'News_influence.0', 'News_influence.0.' + suffix, context('B', 'A')) for suffix in ('a', 'b')}
    assert max(scores.values()) > 0, 'Both recipient AI responses have zero weight'
    if interest < 4 or ratio < .5 or domestic <= 0 or invalid:
        assert scores['a'] == 0 and scores['b'] > 0, scores
    groups['actual_ai_recipient_fail_safes_never_both_zero'] += 1

# Execute every native policy gate from its current helper, with explicit country
# facts. These are source fixtures, not claims about real-country admissibility.
debt_context = context('A', scope='B')
for alteration in ('valid', 'donor absent', 'target absent', 'war', 'too large GDP', 'low target debt ratio',
                   'high donor debt ratio', 'low opinion', 'insufficient cash', 'pending donor request',
                   'ERI transitional', 'ERI ordinary leader', 'all allies at war', 'one peaceful ally',
                   'subject large GDP and low debt ratio'):
    result = state(); result['countries']['B']['variables']['debt'] = 100
    donor, recipient = result['countries']['A'], result['countries']['B']
    if alteration == 'donor absent': donor['exists'] = False
    elif alteration == 'target absent': recipient['exists'] = False
    elif alteration == 'war': recipient['wars'].add('A')
    elif alteration == 'too large GDP': recipient['variables']['gdp_total'] = 200
    elif alteration == 'low target debt ratio': recipient['variables']['debt_ratio'] = .25
    elif alteration == 'high donor debt ratio': donor['variables']['debt_ratio'] = .75
    elif alteration == 'low opinion': recipient['opinions']['A'] = 49
    elif alteration == 'insufficient cash': donor['variables']['treasury'] = 24
    elif alteration == 'pending donor request': donor['variables']['pending_assume_debt_offer'] = 'C'
    elif alteration.startswith('ERI'):
        donor.update(original_tag='ERI', leader='Eritrean Transitional Government' if alteration == 'ERI transitional' else 'Ordinary President')
        donor['flags'].add('ETH_transitional_government_FLAG')
    elif alteration in ('all allies at war', 'one peaceful ally'):
        recipient['allies'] = ['C', 'D']; result['countries']['C']['wars'].add('A')
        if alteration == 'all allies at war': result['countries']['D']['wars'].add('A')
    elif alteration == 'subject large GDP and low debt ratio':
        recipient.update(overlord='A'); recipient['variables'].update(gdp_total=1000, debt_ratio=0)
    valid = alteration in ('valid', 'ERI ordinary leader', 'one peaceful ally', 'subject large GDP and low debt ratio')
    assert check(result, one(debt, 'can_be_sent'), debt_context) == valid, alteration
    before = cash(result)
    effect(result, one(debt, 'on_sent_effect'), debt_context)
    assert cash(result) == before, 'Debt proposal must not debit or credit'
    assert donor['variables'].get('assuming_debt_value', 0) == (25 if valid else 0), alteration
    expected_pending = 'B' if valid else ('C' if alteration == 'pending donor request' else 0)
    assert donor['variables'].get('pending_assume_debt_offer', 0) == expected_pending, alteration
    groups['actual_debt_policy_send_guards'] += 1

for current_debt, wallet, expected in ((100, 100, 25), (200, 100, 25), (5, 100, 5), (0, 100, 0), (100, 24, 0), (5, 5, 5)):
    result = state(); result['countries']['B']['variables']['debt'] = 100
    effect(result, one(debt, 'on_sent_effect'), debt_context)
    result['countries']['A']['variables']['treasury'] = wallet
    result['countries']['B']['variables']['debt'] = current_debt
    before = deepcopy(result['countries'])
    effect(result, one(debt, 'complete_effect'), debt_context)
    assert result['countries']['A']['variables']['treasury'] == wallet - expected
    assert result['countries']['B']['variables']['debt'] == current_debt - expected
    assert result['countries']['B']['variables']['treasury'] == before['B']['variables']['treasury']
    assert result['countries']['A']['variables']['debt'] == before['A']['variables']['debt']
    frozen = deepcopy(result['countries']); effect(result, one(debt, 'complete_effect'), debt_context)
    assert result['countries'] == frozen, 'Duplicate debt response changed settled money'
    groups['literal_debt_cash_equals_relief'] += 1

# Only the changed cash/cooldown fail-safes are isolated here. Their actual AST
# runs with supplied PP/interest/current cash rather than modeling the rest of AI.
ai_desire = one(debt, 'ai_desire')
modifiers = [v for k, o, v in ai_desire if k == 'modifier']
cash_guard, cooldown_guard = modifiers[-2:]
for wallet, expected in ((24, True), (25, False), (100, False)):
    result = state(wallet); result['countries']['B']['variables']['debt'] = 100
    assert check(result, [n for n in cash_guard if n[0] != 'factor'], debt_context) == expected
    groups['actual_ai_cash_fail_safe'] += 1
for recent, expected in ((False, False), (True, True)):
    result = state(); result['countries']['B']['variables']['debt'] = 100
    if recent: result['countries']['A']['flags'].add('AI_recently_sent_debt_assumption_offer_@B')
    assert check(result, [n for n in cooldown_guard if n[0] != 'factor'], debt_context) == expected
    groups['actual_ai_recent_offer_fail_safe'] += 1

for wallet, claim, expected_wallet, expected_due in (
        (100, 35, 135, 0), (999990, 35, 1000000, 25),
        (1000000, 35, 1000000, 35), (1000000, 1000035, 1000000, 1000035),
        (999995, 5, 1000000, 0), (999999, 5, 1000000, 4)):
    result = state(wallet)
    helper(result, 'A', 'eon_support_queue_refund', temporary={'eon_support_refund_amount': claim})
    donor = result['countries']['A']['variables']
    assert donor['treasury'] == expected_wallet and donor.get('eon_support_refund_due', 0) == expected_due
    assert owned_cash(result) == wallet + claim
    settled = deepcopy(result['countries'])
    helper(result, 'A', 'eon_support_release_refund')
    assert result['countries'] == settled, 'No headroom must retain refund exactly'
    if expected_due:
        donor['treasury'] -= 10
        helper(result, 'A', 'eon_support_release_refund')
        assert donor['treasury'] == expected_wallet - 10 + min(10, expected_due)
        assert donor.get('eon_support_refund_due', 0) == max(0, expected_due - 10)
        assert owned_cash(result) == wallet + claim - 10
    groups['literal_refund_cap_and_retained_assets'] += 1

hooks = one(ast(read('common/on_actions/eon_support_on_actions.txt')), 'on_actions')
daily = one(one(hooks, 'on_daily'), 'effect')
for dead_target in (False, True):
    result = state(); result['countries']['B']['variables']['debt'] = 100
    effect(result, one(debt, 'on_sent_effect'), debt_context)
    result['countries']['B']['exists'] = not dead_target
    before = cash(result)
    effect(result, daily, context('A'))
    assert cash(result) == before
    assert result['countries']['A']['variables'].get('pending_assume_debt_offer', 0) == (0 if dead_target else 'B')
    groups['daily_debt_live_or_dead_target'] += 1

for hook, victim, mode in ((h, v, m) for h in ('on_annex', 'on_subject_annexed')
                           for v in ('A', 'B') for m in ('draft', 'offer', 'reply-before-annex', 'daily-before-annex')):
    result = state()
    if mode == 'draft':
        assert open_draft(result)
    else:
        offer(result, 35)
    result['countries']['C']['variables']['treasury'] = 999990
    result['countries'][victim]['variables']['eon_support_refund_due'] = 7
    result['countries']['D']['variables'].update(pending_assume_debt_offer='C', assuming_debt_value=25)
    result['countries'][victim]['exists'] = False
    total = owned_cash(result)
    if mode == 'reply-before-annex':
        reply(result, True, force=True)
        assert owned_cash(result) == total
    elif mode == 'daily-before-annex':
        effect(result, daily, context('B' if victim == 'A' else 'A'))
        assert owned_cash(result) == total
    ctx = context('C', victim) if hook == 'on_annex' else context(victim, 'C')
    effect(result, one(one(hooks, hook), 'effect'), ctx)
    assert owned_cash(result) == total, (hook, victim, mode)
    assert_no_aid(result, 'A', 'B')
    assert result['countries'][victim]['variables'].get('eon_support_refund_due', 0) == 0
    expected_assets = 7 + (35 if victim == 'A' and mode != 'draft' else 0)
    successor = result['countries']['C']['variables']
    assert successor['treasury'] == 999990 + min(10, expected_assets)
    assert successor.get('eon_support_refund_due', 0) == max(0, expected_assets - 10)
    assert result['countries']['D']['variables']['pending_assume_debt_offer'] == 'C'
    before = deepcopy(result['countries'])
    effect(result, one(one(hooks, hook), 'effect'), ctx)
    assert result['countries'] == before, 'Repeated annex hook transferred support assets twice'
    groups['native_annex_roles_and_callback_order_assets'] += 1

# Aid and debt repayment retain separate consent flows. Repaying outstanding
# debt neither approves a cash gift nor spends its already held donor escrow.
result = state(); offer(result, 15)
result['countries']['C']['variables'].update(treasury=100, gdp_total=100, debt_ratio=.5)
result['countries']['B']['variables']['debt'] = 100
debt_other_context = context('C', scope='B')
assert check(result, one(debt, 'can_be_sent'), debt_other_context)
effect(result, one(debt, 'on_sent_effect'), debt_other_context)
effect(result, one(debt, 'complete_effect'), debt_other_context)
assert result['countries']['C']['variables']['treasury'] == 75
assert result['countries']['B']['variables']['debt'] == 75
assert cash(result) == {'A': 85, 'B': 0}
assert pending(result, 'A') and pending(result, 'B')
assert reply(result)
assert cash(result) == {'A': 85, 'B': 15}
assert result['countries']['B']['variables']['debt'] == 75
groups['independent_aid_and_debt_consent'] += 1

# Static notices acknowledge a past result. They cannot finalize or overwrite a
# newer draft/offer, including a third-country agreement opened in the meantime.
notice_events = model['get_event_map'](read('events/eon_support_events.txt'))
for identity in notice_events:
    result = state(); offer(result, 5); assert reply(result)
    result['countries']['C']['variables'].update(gdp_total=50, num_of_civilian_factories=20)
    assert open_draft(result, 'A', 'C')
    frozen = deepcopy(result['countries'])
    effect(result, one(notice_events[identity], 'option'), context('A', 'B'))
    assert result['countries'] == frozen
    assert pending(result, 'A') and pending(result, 'C')
    groups['static_old_acknowledgement_preserves_new_draft'] += 1

source_paths = (
    'common/scripted_effects/00_budget_effects.txt',
    'common/scripted_effects/eon_aid_effects.txt',
    'common/scripted_effects/eon_support_effects.txt',
    'common/scripted_triggers/eon_aid_triggers.txt',
    'common/scripted_triggers/eon_debt_support_triggers.txt',
    'common/scripted_triggers/00_influence_scripted_triggers.txt',
    'common/scripted_triggers/00_debt_ratio_triggers.txt',
    'common/scripted_triggers/99_ERI_scripted_triggers.txt',
    'common/scripted_diplomatic_actions/00_scripted_diplomatic_actions.txt',
    'common/scripted_diplomatic_actions/eon_support_actions.txt',
    'common/scripted_guis/influence_scripted_gui.txt',
    'common/on_actions/eon_support_on_actions.txt',
    'events/00_Influence_events.txt',
    'events/eon_support_events.txt',
)
print(json.dumps({'all_passed': True, 'total_cases': sum(groups.values()), 'groups': groups,
                  'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source_paths},
                  'proof_scope': 'ordered actual-source aid/debt/refund/native-hook branches and treasury helper; bounded model',
                  'fixtures': ['country GDP/debt/treasury/PP/factories, actual seven influencer slots, relations, leader, war and liveness',
                               'native ROOT/FROM/THIS/PREV contexts supplied explicitly; queued event ID/target/from retained',
                               'influence/opinion/party helpers witnessed at actual callers; their complete arithmetic is not modeled',
                               'ordinary annex treasury/debt inheritance remains outside the support asset model'],
                  'not_proven': ['HOI4 scheduling/scopes', 'GUI', 'save/load', 'campaign', 'full influence arithmetic',
                                 'unknown repeated same-tier legacy debits without surviving transaction records']}, indent=2))
