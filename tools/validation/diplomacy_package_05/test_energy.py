"""Execute current bounded energy negotiations from ordered game source.

Economy, country policy and callback delivery are supplied inputs. This source
model does not prove HOI4 event consumption, GUI rendering or save/load.
"""
from pathlib import Path
from copy import deepcopy
import contextlib
import hashlib
import io
import json
import runpy
import sys

ROOT = Path(__file__).resolve().parents[3]
with contextlib.redirect_stdout(io.StringIO()):
    previous = runpy.run_path(str(ROOT / 'tools/validation/diplomacy_package_04/test_energy.py'))
model = previous['model']
ast, one, execute, context = [model[name] for name in ('ast', 'one', 'execute', 'context')]
state = previous['state']
trigger = previous['trigger']

for event_id in ('energy_selling.1', 'energy_selling.4'):
    names = [one(option, 'name') for key, op, option in model['events'][event_id] if key == 'option']
    assert 'eon_energy_counter_offer' in names, f'{event_id}: actual counteroffer option is required'

cases = []

# Load only the bounded energy notice namespace, retaining actual event IDs.
events = dict(model['events'])
for path in sorted((ROOT / 'events').glob('*energy*negotiation*.txt')):
    events.update(model['get_event_map'](path.read_text(encoding='utf-8-sig')))
for path in sorted((ROOT / 'events').glob('*Energy*negotiation*.txt')):
    events.update(model['get_event_map'](path.read_text(encoding='utf-8-sig')))

gui_root = one(ast((ROOT / 'common/scripted_guis/01_energy_gui.txt').read_text(encoding='utf-8-sig')), 'scripted_gui')
gui_triggers = one(one(gui_root, 'energy_scripted_gui'), 'triggers')
selection = one(one(gui_root, 'energy_sell_country_selection_gui'), 'effects')


def event_id(s, recipient):
    amount = s['countries'][recipient]['variables']['eon_energy_offer_amount']
    return 'energy_selling.1' if amount > 0 else 'energy_selling.4'


def option_body(identity, name):
    found = [body for key, op, body in events[identity] if key == 'option' and one(body, 'name') == name]
    assert len(found) == 1, (identity, name, len(found))
    return found[0]


def respond(s, recipient, sender, suffix, identity=None):
    """Delivered event identity is explicit; disabled native options do not run."""
    identity = identity or event_id(s, recipient)
    name = 'eon_energy_counter_offer' if suffix == 'c' else identity + '.' + suffix
    option = option_body(identity, name)
    s['temp'] = {}
    guards = [body for key, op, body in option if key == 'trigger']
    available = not guards or trigger(guards[0], s, context(recipient, sender))
    if available:
        execute(option, s, context(recipient, sender))
    return available


def effect(s, actor, name, other=None):
    s['temp'] = {}
    execute([(name, '=', 'yes')], s, context(actor, other))


def clicked(s, actor, name):
    s['temp'] = {}
    execute(one(model['gui'], name), s, context(actor))


def enabled(s, actor, name):
    s['temp'] = {}
    return trigger(one(gui_triggers, name + '_enabled'), s, context(actor))


def frozen(s, actor):
    return {key: deepcopy(val) for key, val in s['countries'][actor]['variables'].items()
            if key.startswith('eon_energy_offer_')}


def new_pair(sign, third=True, old=True):
    s = state()
    if old:
        model['pair'](s, 'A', 'B', sign * 8, .04)
    if third:
        model['framework'](s, 'A', 'C')
        model['pair'](s, 'A', 'C', -3, .07)
    model['propose'](s, 'A', 'B', sign * 16, .06)
    assert model['locked'](s, 'A') and model['locked'](s, 'B')
    return s


def assert_payment(s, sign, pair_weekly, third=True):
    paid = model['money'](s)
    a_income = (.21 if third else 0) + (pair_weekly if sign < 0 else 0)
    a_expense = pair_weekly if sign > 0 else 0
    b_income = pair_weekly if sign > 0 else 0
    b_expense = pair_weekly if sign < 0 else 0
    expected = {'A': (a_income, a_expense), 'B': (b_income, b_expense),
                'C': (0, .21 if third else 0), 'D': (0, 0)}
    for actor, amounts in expected.items():
        assert all(model['compare'](actual, '=', wanted) for actual, wanted in zip(paid[actor], amounts)), (actor, paid, expected)


def begin_counter(s, recipient='B', sender='A'):
    old = model['snapshot_arrays'](s)
    identity = event_id(s, recipient)
    assert respond(s, recipient, sender, 'c', identity)
    assert 'eon_energy_counter_draft_owner' in s['countries'][recipient]['flags']
    assert 'eon_energy_counter_awaiting' in s['countries'][sender]['flags']
    assert model['locked'](s, recipient) and model['locked'](s, sender)
    assert model['snapshot_arrays'](s) == old
    return identity


def send_counter(s, actor, partner, signed, price):
    s['countries'][actor]['variables'].update(energy_selling_selected_TAG=partner,
                                              temp_energy_ammount=signed, temp_energy_price=price)
    assert enabled(s, actor, 'confirm_energy_sell_click'), (actor, signed, price)
    clicked(s, actor, 'confirm_energy_sell_click')
    assert 'eon_energy_outgoing_offer' in s['countries'][actor]['flags']
    assert 'eon_energy_incoming_offer' in s['countries'][partner]['flags']
    assert 'eon_energy_counter_draft_owner' not in s['countries'][actor]['flags']
    assert 'eon_energy_counter_awaiting' not in s['countries'][partner]['flags']
    assert s['countries'][actor]['variables']['eon_energy_offer_amount'] == signed
    assert model['compare'](s['countries'][actor]['variables']['eon_energy_offer_price'], '=', price)


def notice(s, identity, target):
    assert any(item['id'] == identity and item['target'] == target for item in s['events']), (identity, target, s['events'])


def native_action(name):
    found = []
    for path in sorted((ROOT / 'common/scripted_diplomatic_actions').glob('*.txt')):
        text = path.read_text(encoding='utf-8-sig')
        if name not in text:
            continue
        nodes = ast(text)
        found.extend(body for key, op, container in nodes if key == 'scripted_diplomatic_actions'
                     for action, op, body in container if action == name)
    assert len(found) == 1, (name, len(found))
    return found[0]


def current_option_weights(s, recipient, sender, identity):
    """Interpret only actual option availability/modifiers, preserving temp state."""
    weights = {}
    ctx = context(recipient, sender)
    for key, op, body in events[identity]:
        if key != 'option':
            continue
        guards = [nodes for name, op, nodes in body if name == 'trigger']
        if guards and not trigger(guards[0], s, ctx):
            weights[one(body, 'name')] = 0
            continue
        chance = one(body, 'ai_chance')
        weight = float(one(chance, 'base'))
        for name, op, modifier in chance:
            if name == 'modifier' and trigger([node for node in modifier if node[0] != 'factor'], s, ctx):
                weight *= float(one(modifier, 'factor'))
        weights[one(body, 'name')] = weight
    return weights


withdraw_action = native_action('eon_withdraw_energy_offer')
resume_action = native_action('eon_resume_energy_counter_offer')


def action(s, actor, target, body):
    ctx = context(actor, scope=target)
    s['temp'] = {}
    for field in ('selectable', 'can_be_sent'):
        conditions = [nodes for key, op, nodes in body if key == field]
        if conditions and not trigger(conditions[0], s, ctx):
            return False
    execute(one(body, 'complete_effect'), s, ctx)
    return True


# Each initial sign and final response uses independent old/new price facts.
# Original pair contributes .32; accepted 12/.05 counter contributes .60.
for sign in (-1, 1):
    for accepted in (False, True):
        s = new_pair(sign)
        old = model['snapshot_arrays'](s)
        assert_payment(s, sign, .32)
        original = begin_counter(s)
        assert s['countries']['B']['variables']['energy_selling_selected_TAG'] == 'A'
        assert s['countries']['B']['variables']['temp_energy_ammount'] == -sign * 16
        assert model['compare'](s['countries']['B']['variables']['temp_energy_price'], '=', .06)
        assert_payment(s, sign, .32)
        # A duplicated consumed native option cannot turn a live editor back
        # into another offer, or reject/accept the still unchanged old terms.
        draft = deepcopy(s['countries'])
        for suffix in ('a', 'b', 'c'):
            respond(s, 'B', 'A', suffix, original)
            assert s['countries'] == draft, ('draft duplicate option', sign, suffix)
        send_counter(s, 'B', 'A', -sign * 12, .05)
        assert model['snapshot_arrays'](s) == old
        assert_payment(s, sign, .32)
        assert s['countries']['A']['variables']['eon_energy_offer_amount'] == sign * 12
        assert s['countries']['A']['variables']['eon_energy_offer_counter_depth'] == 1
        assert s['countries']['B']['variables']['eon_energy_offer_counter_depth'] == 1
        fixed = frozen(s, 'A')
        s['countries']['B']['variables'].update(temp_energy_ammount=999, temp_energy_price=999,
                                               energy_selling_selected_TAG='D')
        assert frozen(s, 'A') == fixed
        assert respond(s, 'A', 'B', 'a' if accepted else 'b')
        assert not model['locked'](s, 'A') and not model['locked'](s, 'B')
        if accepted:
            model['assert_pair'](s, 'A', 'B', sign * 12, .05)
            assert_payment(s, sign, .60)
        else:
            assert model['snapshot_arrays'](s) == old
            assert_payment(s, sign, .32)
        model['assert_pair'](s, 'A', 'C', -3, .07)
        cases.append(f'human counter sign={sign} accepted={accepted} old_weekly=.32 new_weekly=.60')

# Multiple human rounds reverse authorship, while delivery/payment changes once.
for sign in (-1, 1):
    s = new_pair(sign)
    before = model['snapshot_arrays'](s)
    begin_counter(s)
    send_counter(s, 'B', 'A', -sign * 12, .05)
    begin_counter(s, 'A', 'B')
    send_counter(s, 'A', 'B', sign * 10, .07)
    begin_counter(s, 'B', 'A')
    send_counter(s, 'B', 'A', -sign * 12, .05)
    assert s['countries']['A']['variables']['eon_energy_offer_counter_depth'] == 3
    assert s['countries']['B']['variables']['eon_energy_offer_counter_depth'] == 3
    assert model['snapshot_arrays'](s) == before
    assert_payment(s, sign, .32)
    assert respond(s, 'A', 'B', 'a')
    model['assert_pair'](s, 'A', 'B', sign * 12, .05)
    assert_payment(s, sign, .60)
    cases.append(f'three consumed human counter rounds preserve terms until final agreement sign={sign}')

# Old response identities must not act while their editor reserves the pair.
# Direct helper calls test effect guards in addition to option availability.
for sign in (-1, 1):
    s = new_pair(sign)
    begin_counter(s)
    before = deepcopy(s['countries'])
    for helper in ('eon_energy_accept_offer', 'eon_energy_finish_response', 'eon_energy_refuse_offer', 'eon_energy_prepare_counter_draft'):
        effect(s, 'B', helper, 'A')
        assert s['countries'] == before, (helper, sign)
    assert not action(s, 'A', 'B', resume_action)
    assert action(s, 'B', 'A', resume_action)
    assert model['snapshot_arrays'](s) == {actor: data['arrays'] for actor, data in before.items()}
    assert s['countries']['B']['variables']['energy_selling_selected_TAG'] == 'A'
    cases.append(f'old callbacks guarded and only editor owner may resume sign={sign}')

# The editor fixes the partner. Selection clicks cannot overwrite it with C.
for sign in (-1, 1):
    s = new_pair(sign)
    begin_counter(s)
    s['countries']['B']['arrays']['temp_energy_sell_selection_countries'] = ['C']
    fixed = frozen(s, 'B')
    s['temp'] = {'i': 0}
    execute(one(selection, 'country_list_flag_button_click'), s, context('B'))
    assert s['countries']['B']['variables']['energy_selling_selected_TAG'] == 'A'
    assert frozen(s, 'B') == fixed
    s['countries']['B']['variables']['energy_selling_selected_TAG'] = 'C'
    assert not enabled(s, 'B', 'confirm_energy_sell_click')
    before = model['snapshot_arrays'](s)
    clicked(s, 'B', 'confirm_energy_sell_click')
    assert model['snapshot_arrays'](s) == before and model['locked'](s, 'A')
    cases.append(f'counter editor keeps reserved partner sign={sign}')

# Draft controls may lower an infeasible proposal after a supplier capacity loss.
# Zero, a negative price or a direction reversal cannot submit a counter and
# must not be interpreted as terminating the still active eight-GW contract.
for sign in (-1, 1):
    for amount, price in ((0, .05), (sign * 12, .05), (-sign * 12, -.01)):
        s = new_pair(sign)
        begin_counter(s)
        s['countries']['B']['variables'].update(temp_energy_ammount=amount, temp_energy_price=price)
        before = model['snapshot_arrays'](s)
        assert not enabled(s, 'B', 'confirm_energy_sell_click'), (sign, amount, price)
        clicked(s, 'B', 'confirm_energy_sell_click')
        assert model['snapshot_arrays'](s) == before and model['locked'](s, 'A') and model['locked'](s, 'B')
        assert_payment(s, sign, .32)
        cases.append(f'invalid draft amount={amount} price={price} leaves old delivery sign={sign}')
    s = new_pair(sign)
    begin_counter(s)
    supplier = 'A' if sign < 0 else 'B'
    s['countries'][supplier]['variables']['energy_balance'] = 8
    s['countries']['B']['variables']['temp_energy_ammount'] = -sign * 32
    toward_zero = 'increase_energy_ammount_number_click' if sign > 0 else 'decrease_energy_ammount_number_click'
    for unused in range(16):
        assert enabled(s, 'B', toward_zero)
        clicked(s, 'B', toward_zero)
    assert s['countries']['B']['variables']['temp_energy_ammount'] == -sign * 16
    assert enabled(s, 'B', 'confirm_energy_sell_click')
    clicked(s, 'B', 'confirm_energy_sell_click')
    assert respond(s, 'A', 'B', 'a')
    model['assert_pair'](s, 'A', 'B', sign * 16, .06)
    assert_payment(s, sign, .96)
    cases.append(f'draft reduces selected32 to feasible16 after capacity change sign={sign}')

# Withdrawing an unconsumed proposal keeps the old callback serialized. Its
# response consumes cancellation, never installs the withdrawn offered terms.
for sign in (-1, 1):
    for suffix in ('a', 'b', 'c'):
        s = new_pair(sign)
        original = event_id(s, 'B')
        before = model['snapshot_arrays'](s)
        assert not action(s, 'B', 'A', withdraw_action), 'Recipient must not withdraw another country\'s offer'
        assert action(s, 'A', 'B', withdraw_action)
        for actor in ('A', 'B'):
            assert 'eon_energy_offer_cancelled' in s['countries'][actor]['flags'] and model['locked'](s, actor)
        assert model['snapshot_arrays'](s) == before
        assert_payment(s, sign, .32)
        frozen_before = {actor: frozen(s, actor) for actor in ('A', 'B')}
        model['propose'](s, 'A', 'B', sign * 20, .08)
        model['propose'](s, 'A', 'C', -4, .08)
        assert {actor: frozen(s, actor) for actor in ('A', 'B')} == frozen_before
        # Counter is unavailable on the cancelled proposal. A cancellation
        # response a/b consumes it; selecting the unavailable c does nothing.
        available = respond(s, 'B', 'A', suffix, original)
        if suffix == 'c':
            assert not available and model['locked'](s, 'A')
            assert respond(s, 'B', 'A', 'b', original)
        assert model['snapshot_arrays'](s) == before
        assert not model['locked'](s, 'A') and not model['locked'](s, 'B')
        assert_payment(s, sign, .32)
        model['propose'](s, 'A', 'B', sign * 20, .08)
        assert model['locked'](s, 'A') and model['locked'](s, 'B')
        cases.append(f'withdraw retains pending callback lock and later releases sign={sign} option={suffix}')

# The original modal was consumed before draft state. Abandoning that editor
# may release both reservations immediately, without changing current delivery.
for sign in (-1, 1):
    for actor, partner in (('A', 'B'), ('B', 'A')):
        s = new_pair(sign)
        begin_counter(s)
        old = model['snapshot_arrays'](s)
        assert action(s, actor, partner, withdraw_action)
        assert model['snapshot_arrays'](s) == old
        assert not model['locked'](s, 'A') and not model['locked'](s, 'B')
        assert_payment(s, sign, .32)
        assert not action(s, actor, partner, resume_action)
        model['propose'](s, 'A', 'B', sign * 20, .08)
        assert model['locked'](s, 'A') and model['locked'](s, 'B')
        cases.append(f'consumed modal permits immediate draft abandonment sign={sign} actor={actor}')

# Existing lifecycle invalidation must release an editor immediately: its old
# modal was consumed, so no future answer exists to clear cancelled draft locks.
cancel_framework_action = native_action('cancel_energy_agreement')
for sign in (-1, 1):
    for actor, partner in (('A', 'B'), ('B', 'A')):
        s = new_pair(sign)
        begin_counter(s)
        s['temp'] = {}
        execute([('set_temp_variable', '=', [('eon_energy_pair_partner', '=', partner)]),
                 ('eon_energy_end_pair', '=', 'yes')], s, context(actor))
        for participant in ('A', 'B'):
            assert not model['locked'](s, participant)
            assert 'eon_energy_offer_cancelled' not in s['countries'][participant]['flags']
        assert s['countries']['B']['arrays']['energy_contractors'] == []
        model['assert_pair'](s, 'A', 'C', -3, .07)
        assert_payment(s, sign, 0)
        model['propose'](s, 'A', 'B', sign * 16, .06)
        assert model['locked'](s, 'A') and model['locked'](s, 'B')
        cases.append(f'existing end_pair clears consumed draft immediately sign={sign} actor={actor}')
    for has_old_contract in (False, True):
        s = new_pair(sign, old=has_old_contract)
        begin_counter(s)
        assert action(s, 'A', 'B', cancel_framework_action)
        for participant, partner in (('A', 'B'), ('B', 'A')):
            assert not model['locked'](s, participant)
            assert 'energy_agreement@' + partner not in s['countries'][participant]['flags']
        assert s['countries']['B']['arrays']['energy_contractors'] == []
        model['assert_pair'](s, 'A', 'C', -3, .07)
        assert_payment(s, sign, 0)
        assert not action(s, 'B', 'A', resume_action)
        model['propose'](s, 'A', 'C', -4, .08)
        assert model['locked'](s, 'A') and model['locked'](s, 'C')
        cases.append(f'framework cancellation drains consumed draft sign={sign} old_contract={has_old_contract}')

# Every old accepted/refused/ended and new informational notice remains inert
# while a new same-pair negotiation owns current variables/reservations.
notices = {identity: event for identity, event in events.items()
           if identity in ('energy_selling.2', 'energy_selling.3', 'energy_selling.5') or identity.startswith('eon_energy_negotiation.')}
assert all('eon_energy_negotiation.' + str(number) in notices for number in (10, 11, 12, 13, 14, 15, 16, 17, 19))
for identity, event in notices.items():
    s = new_pair(-1)
    fixed = deepcopy(s['countries'])
    for key, op, body in event:
        if key in ('immediate', 'option'):
            execute(body, s, context('A', 'B'))
            assert s['countries'] == fixed, ('notice changed pending proposal', identity)
    cases.append('effect-free old/current notice ' + identity)

# Legal/economic state changes while editing cannot start a replacement. A
# war or agreement removal retains authoritative existing arrays for cleanup;
# no response restores a snapshot that another effect has deliberately removed.
for sign in (-1, 1):
    for change in ('capacity drop', 'framework A', 'framework B', 'war', 'annex A',
                   'annex B', 'record A removed', 'record B changed', 'duplicate A', 'misaligned B'):
        s = new_pair(sign)
        begin_counter(s)
        supplier = 'A' if sign < 0 else 'B'
        if change == 'capacity drop':
            s['countries'][supplier]['variables']['energy_balance'] = 3
        elif change.startswith('framework '):
            actor = change[-1]
            peer = 'B' if actor == 'A' else 'A'
            s['countries'][actor]['flags'].discard('energy_agreement@' + peer)
        elif change == 'war':
            s['countries']['A']['wars'].add('B')
            s['countries']['B']['wars'].add('A')
        elif change.startswith('annex '):
            s['countries'][change[-1]]['exists'] = False
        elif change == 'record A removed':
            for name in s['countries']['A']['arrays']:
                if name.startswith('energy_contract'):
                    s['countries']['A']['arrays'][name] = []
        elif change == 'record B changed':
            s['countries']['B']['arrays']['energy_contracts_price'][0] = .09
        elif change == 'duplicate A':
            model['record'](s, 'A', 'B', sign * 8, .04)
        else:
            s['countries']['B']['arrays']['energy_contracts_price'].append(.09)
        before = model['snapshot_arrays'](s)
        s['countries']['B']['variables'].update(temp_energy_ammount=-sign * 12, temp_energy_price=.05)
        assert not enabled(s, 'B', 'confirm_energy_sell_click'), (sign, change)
        clicked(s, 'B', 'confirm_energy_sell_click')
        assert model['snapshot_arrays'](s) == before
        cases.append(f'counter send guard preserves current record sign={sign} change={change}')

# A sent counter remains frozen, but final acceptance checks current capacity,
# framework, liveness, records and mirror consistency again.
for sign in (-1, 1):
    for change in ('capacity', 'framework', 'war', 'record changed', 'mirror changed'):
        s = new_pair(sign)
        begin_counter(s)
        send_counter(s, 'B', 'A', -sign * 12, .05)
        supplier = 'A' if sign < 0 else 'B'
        if change == 'capacity':
            s['countries'][supplier]['variables']['energy_balance'] = 3
        elif change == 'framework':
            s['countries']['A']['flags'].discard('energy_agreement@B')
        elif change == 'war':
            s['countries']['A']['wars'].add('B')
            s['countries']['B']['wars'].add('A')
        elif change == 'record changed':
            s['countries']['B']['arrays']['energy_contracts_price'][0] = .09
        else:
            s['countries']['B']['variables']['eon_energy_offer_amount'] = -sign * 13
        before = model['snapshot_arrays'](s)
        respond(s, 'A', 'B', 'a')
        assert model['snapshot_arrays'](s) == before
        cases.append(f'counter acceptance repeats current-state check sign={sign} change={change}')

# AI examines candidate terms without replacing the original snapshot. It may
# counter once, using the existing .05 benchmark rather than an arbitrary price.
for signed, price, expected_counter_amount in ((1, .04, -1), (-16, .20, 16)):
    s = state()
    model['pair'](s, 'A', 'B', 8 if signed > 0 else -8, .04)
    s['countries']['B']['ai'] = True
    if signed < 0:
        s['countries']['B']['variables'].update(energy_balance=-100, energy_sum=100, energy_consumption=200)
    model['propose'](s, 'A', 'B', signed, price)
    initial = {actor: frozen(s, actor) for actor in ('A', 'B')}
    identity, weights, score = previous['ai_reply'](s)
    assert weights[identity + '.a'] == 0 and weights['eon_energy_counter_offer'] == 100
    assert s['countries']['B']['variables']['eon_energy_counter_amount'] == expected_counter_amount
    assert model['compare'](s['countries']['B']['variables']['eon_energy_counter_price'], '=', .05)
    assert {actor: frozen(s, actor) for actor in ('A', 'B')} == initial
    old = model['snapshot_arrays'](s)
    assert respond(s, 'B', 'A', 'c', identity)
    assert model['snapshot_arrays'](s) == old
    assert s['countries']['A']['variables']['eon_energy_offer_amount'] == signed
    assert model['compare'](s['countries']['A']['variables']['eon_energy_offer_price'], '=', .05)
    assert respond(s, 'A', 'B', 'a')
    model['assert_pair'](s, 'A', 'B', signed, .05)
    cases.append(f'AI price counter original_signed={signed} original_price={price} new_price=.05')

# Production changed after an initial feasible dispatch. AI may reduce quantity
# to the latest supplier limit in either direction, without inventing supply.
for sign in (-1, 1):
    for latest_balance, expected_quantity in ((16, 16), (16.7, 16), (.9, 0)):
        s = state()
        s['countries']['B']['ai'] = True
        supplier = 'A' if sign < 0 else 'B'
        s['countries'][supplier]['variables']['energy_balance'] = 32
        if sign < 0:
            s['countries']['B']['variables'].update(energy_balance=-100, energy_sum=100, energy_consumption=200)
        model['propose'](s, 'A', 'B', sign * 32, .05)
        s['countries'][supplier]['variables']['energy_balance'] = latest_balance
        initial = {actor: frozen(s, actor) for actor in ('A', 'B')}
        identity, weights, score = previous['ai_reply'](s)
        if expected_quantity:
            assert weights['eon_energy_counter_offer'] == 100 and weights[identity + '.a'] == 0, (sign, latest_balance, weights)
            assert abs(s['countries']['B']['variables']['eon_energy_counter_amount']) == expected_quantity
            assert respond(s, 'B', 'A', 'c', identity)
            assert s['countries']['A']['variables']['eon_energy_offer_amount'] == sign * expected_quantity
            assert respond(s, 'A', 'B', 'a')
            model['assert_pair'](s, 'A', 'B', sign * expected_quantity, .05)
        else:
            assert weights['eon_energy_counter_offer'] == 0 and weights[identity + '.b'] == 100
            assert {actor: frozen(s, actor) for actor in ('A', 'B')} == initial
            assert respond(s, 'B', 'A', 'b', identity)
            assert s['countries']['A']['arrays']['energy_contractors'] == []
        cases.append(f'AI current capacity clamps whole GW sign={sign} balance={latest_balance} quantity={expected_quantity}')

# Candidate preview is not authority to send. A further fall between preview
# and choosing c must re-run source assessment/capacity and safely reject.
for sign in (-1, 1):
    s = state()
    s['countries']['B']['ai'] = True
    supplier = 'A' if sign < 0 else 'B'
    s['countries'][supplier]['variables']['energy_balance'] = 32
    if sign < 0:
        s['countries']['B']['variables'].update(energy_balance=-100, energy_sum=100, energy_consumption=200)
    model['propose'](s, 'A', 'B', sign * 32, .05)
    s['countries'][supplier]['variables']['energy_balance'] = 16
    identity, weights, score = previous['ai_reply'](s)
    assert weights['eon_energy_counter_offer'] == 100
    before = model['snapshot_arrays'](s)
    s['countries'][supplier]['variables']['energy_balance'] = .9
    assert respond(s, 'B', 'A', 'c', identity)
    assert model['snapshot_arrays'](s) == before
    assert not model['locked'](s, 'A') and not model['locked'](s, 'B')
    notice(s, 'eon_energy_negotiation.13', 'A')
    cases.append(f'AI counter revalidates latest capacity after preview sign={sign}')

# At depth one an AI retains acceptance/refusal and never automatically loops.
for signed, price in ((1, .04), (-16, .20)):
    s = state()
    s['countries']['B']['ai'] = True
    if signed < 0:
        s['countries']['B']['variables'].update(energy_balance=-100, energy_sum=100, energy_consumption=200)
    model['propose'](s, 'A', 'B', signed, price)
    for actor in ('A', 'B'):
        s['countries'][actor]['variables']['eon_energy_offer_counter_depth'] = 1
    identity, weights, score = previous['ai_reply'](s)
    assert weights['eon_energy_counter_offer'] == 0 and weights[identity + '.b'] == 100
    assert s['countries']['B']['variables']['eon_energy_counter_ready'] == 0
    cases.append(f'AI avoids second automatic counter signed={signed} price={price}')

# Option weights must reconstruct capacity from actual frozen FROM terms. The
# shared temporary frame may still contain another candidate's supplier/amount.
for sign in (-1, 1):
    for current_supply, feasible in ((16, True), (15, False)):
        s = state()
        s['countries']['B']['ai'] = True
        supplier = 'A' if sign < 0 else 'B'
        s['countries'][supplier]['variables']['energy_balance'] = 16
        if sign < 0:
            s['countries']['B']['variables'].update(energy_balance=-100, energy_sum=100, energy_consumption=200)
        model['propose'](s, 'A', 'B', sign * 16, .05)
        for actor in ('A', 'B'):
            s['countries'][actor]['variables']['eon_energy_offer_counter_depth'] = 1
        identity, unused_weights, score = previous['ai_reply'](s)
        s['countries'][supplier]['variables']['energy_balance'] = current_supply
        s['temp'].update(eon_energy_capacity_partner='C', eon_energy_capacity_amount=0,
                         eon_energy_projected_balance=10000,
                         eon_energy_capacity_quantity=0)
        weights = current_option_weights(s, 'B', 'A', identity)
        assert weights[identity + '.a'] == (100 if feasible else 0), (sign, current_supply, weights)
        assert weights[identity + '.b'] == (0 if feasible else 100)
        assert weights['eon_energy_counter_offer'] == 0
        cases.append(f'AI weight capacity reads original frozen supplier despite stale temps sign={sign} supply={current_supply}')

# A huge proposed free export must not override the existing free-sale refusal
# through raw quantity. One priced counter is permitted before final refusal.
s = state()
s['countries']['B']['ai'] = True
s['countries']['B']['variables']['energy_balance'] = 2000
model['propose'](s, 'A', 'B', 1051, 0)
identity, weights, score = previous['ai_reply'](s)
assert score <= 0 and weights[identity + '.a'] == 0
assert weights['eon_energy_counter_offer'] == 100
assert s['countries']['B']['variables']['eon_energy_counter_price'] == .05
for actor in ('A', 'B'):
    s['countries'][actor]['variables']['eon_energy_offer_counter_depth'] = 1
identity, weights, score = previous['ai_reply'](s)
assert score <= 0 and weights[identity + '.a'] == 0 and weights[identity + '.b'] == 100
assert respond(s, 'B', 'A', 'b', identity)
notice(s, 'eon_energy_negotiation.16', 'A')
assert s['countries']['A']['arrays']['energy_contractors'] == []
cases.append('bounded volume bonus prevents1051GW free sale overriding refusal')

# Current deficit preference is a reason about the existing budget position,
# not a new solvency/contract affordability formula. Frozen notices are discrete
# event IDs, so pending fields are safely cleared before acknowledging them.
for signed, price, budget, expected_notice in ((-16, .05, (1, 2), 14),
                                              (-16, .20, (10, 5), 15),
                                              (1, .04, (10, 5), 17)):
    s = state()
    s['countries']['B']['ai'] = True
    s['countries']['B']['variables'].update(display_income=budget[0], display_expense=budget[1])
    model['propose'](s, 'A', 'B', signed, price)
    for actor in ('A', 'B'):
        s['countries'][actor]['variables']['eon_energy_offer_counter_depth'] = 1
    identity, weights, score = previous['ai_reply'](s)
    assert weights[identity + '.b'] == 100 and score <= 0, (signed, price, budget, score, weights)
    old = model['snapshot_arrays'](s)
    assert respond(s, 'B', 'A', 'b', identity)
    notice(s, 'eon_energy_negotiation.' + str(expected_notice), 'A')
    assert model['snapshot_arrays'](s) == old
    assert not model['locked'](s, 'A') and not model['locked'](s, 'B')
    cases.append(f'AI refusal notice={expected_notice} signed={signed} price={price} budget={budget}')

def fresh_option_weights(s, identity, recipient='B', sender='A'):
    """Reevaluate actual option conditions without repeating event immediate.

    Native delivery timing is unproven. This models a state change between the
    initial assessment and the response so a cached counter cannot block cleanup.
    """
    weights = {}
    for key, op, option in events[identity]:
        if key != 'option':
            continue
        s['temp'] = {}
        guards = [body for name, op, body in option if name == 'trigger']
        if guards and not trigger(guards[0], s, context(recipient, sender)):
            weights[one(option, 'name')] = 0
            continue
        chance = one(option, 'ai_chance')
        weight = float(one(chance, 'base'))
        for name, op, modifier in chance:
            if name == 'modifier' and trigger([node for node in modifier if node[0] != 'factor'],
                                             s, context(recipient, sender)):
                weight *= float(one(modifier, 'factor'))
        weights[one(option, 'name')] = weight
    return weights


# A previously available AI counter must not suppress the acknowledgement path
# once ordinary withdrawal or changed structural conditions invalidate it. The
# cached counter-ready value deliberately survives: immediate is not repeated.
for change in ('withdrawal', 'framework', 'war', 'record changed'):
    s = state()
    s['countries']['B']['ai'] = True
    model['propose'](s, 'A', 'B', 1, .04)
    identity, initial_weights, score = previous['ai_reply'](s)
    assert initial_weights == {identity + '.a': 0, identity + '.b': 0,
                               'eon_energy_counter_offer': 100}
    assert s['countries']['B']['variables']['eon_energy_counter_ready'] == 1
    if change == 'withdrawal':
        assert action(s, 'A', 'B', withdraw_action)
    elif change == 'framework':
        s['countries']['A']['flags'].discard('energy_agreement@B')
    elif change == 'war':
        s['countries']['A']['wars'].add('B')
        s['countries']['B']['wars'].add('A')
    else:
        model['record'](s, 'A', 'B', -3, .07)
    old = model['snapshot_arrays'](s)
    weights = fresh_option_weights(s, identity)
    assert weights == {identity + '.a': 0, identity + '.b': 100,
                       'eon_energy_counter_offer': 0}, ('cached counter must allow final response', change, weights)
    assert respond(s, 'B', 'A', 'b', identity)
    assert model['snapshot_arrays'](s) == old
    assert not model['locked'](s, 'A') and not model['locked'](s, 'B')
    notice(s, 'eon_energy_negotiation.' + ('11' if change == 'withdrawal' else '12'), 'A')
    cases.append('fresh AI option weights release invalidated cached counter after ' + change)


# Human event options may have been rendered before a later condition change.
# Execute the actual c effect after that change, without assuming a second
# native option-trigger evaluation. Its consumed modal must either own a draft
# or drain the invalid matching request, never leave unanswerable reservations.
for sign in (-1, 1):
    for change in ('withdrawal', 'framework', 'war', 'record changed'):
        s = new_pair(sign)
        identity = event_id(s, 'B')
        counter = option_body(identity, 'eon_energy_counter_offer')
        s['temp'] = {}
        assert trigger(one(counter, 'trigger'), s, context('B', 'A'))
        if change == 'withdrawal':
            assert action(s, 'A', 'B', withdraw_action)
        elif change == 'framework':
            s['countries']['A']['flags'].discard('energy_agreement@B')
        elif change == 'war':
            s['countries']['A']['wars'].add('B')
            s['countries']['B']['wars'].add('A')
        else:
            model['record'](s, 'A', 'B', sign * 3, .07)
        old = model['snapshot_arrays'](s)
        s['temp'] = {}
        execute(counter, s, context('B', 'A'))
        assert model['snapshot_arrays'](s) == old
        assert 'eon_energy_counter_draft_owner' not in s['countries']['B']['flags']
        assert not model['locked'](s, 'A') and not model['locked'](s, 'B'), ('consumed stale-rendered counter must drain request', sign, change)
        notice(s, 'eon_energy_negotiation.' + ('11' if change == 'withdrawal' else '12'), 'A')
        cases.append(f'consumed stale-rendered human counter drains invalid proposal sign={sign} change={change}')


paths = ('common/scripted_guis/01_energy_gui.txt', 'events/00_Energy_market_events.txt',
         'common/scripted_effects/eon_energy_contract_effects.txt',
         'common/scripted_effects/eon_energy_negotiation_effects.txt',
         'common/scripted_effects/eon_energy_ai_effects.txt',
         'common/scripted_triggers/eon_energy_negotiation_triggers.txt',
         'common/scripted_diplomatic_actions/eon_energy_negotiation_actions.txt',
         'events/eon_energy_negotiation_events.txt')
print(json.dumps({'test_level': 'actual-source bounded execution; not engine/campaign/save-load proof',
                  'total_cases': len(cases), 'cases': cases,
                  'native_option_trigger_guards_executed': True,
                  'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}}, indent=2))
