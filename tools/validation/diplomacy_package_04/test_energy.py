"""Execute current energy AI, GUI capacity and commercial callbacks from source.

Economy, ideas and callback delivery are supplied inputs. This is not HOI4.
The inherited lifecycle checks execute first with their output suppressed.
"""
from copy import deepcopy
from pathlib import Path
import contextlib
import hashlib
import io
import json
import runpy
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'diplomacy_package_01'))
with contextlib.redirect_stdout(io.StringIO()):
    model = runpy.run_path(str(ROOT / 'tools/validation/diplomacy_package_01/test_energy.py'))

execute, base_trigger = model['execute'], model['trigger']
ast, one, context, switch = [model[n] for n in ('ast', 'one', 'context', 'switch')]
value = model['value']
def trigger(nodes, state, ctx):
    """Add AI country facts; delegate native math/control flow to package 01."""
    results = []
    index = 0
    while index < len(nodes):
        key, op, val = nodes[index]
        index += 1
        country = state['countries'][ctx['scope']]
        if key == 'has_idea':
            result = val in country.get('ideas', set())
        elif key == 'any_other_country':
            result = any(trigger(val, state, switch(ctx, tag))
                         for tag, data in state['countries'].items()
                         if tag != ctx['scope'] and data['exists'])
        else:
            group = [(key, op, val)]
            if key == 'if':
                while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                    group.append(nodes[index])
                    index += 1
            result = base_trigger(group, state, ctx)
        results.append(result)
    return all(results)


execute.__globals__['trigger'] = trigger
gui_root = one(ast((ROOT / 'common/scripted_guis/01_energy_gui.txt').read_text(encoding='utf-8-sig')), 'scripted_gui')
gui = one(gui_root, 'energy_scripted_gui')
gui_triggers = one(gui, 'triggers')
selection = one(one(gui_root, 'energy_sell_country_selection_gui'), 'effects')


def state():
    result = model['state']()
    for country in result['countries'].values():
        country['ideas'] = set()
        country['variables'].update(energy_balance=1000, energy_sum=1200,
                                    energy_consumption=200, display_income=10,
                                    display_expense=5)
    model['framework'](result, 'A', 'B')
    return result


def ai_reply(s, sender='A', recipient='B'):
    amount = s['countries'][recipient]['variables']['eon_energy_offer_amount']
    event_id = 'energy_selling.1' if amount > 0 else 'energy_selling.4'
    event = model['events'][event_id]
    s['temp'] = {}
    execute(one(event, 'immediate'), s, context(recipient, sender))
    weights = {}
    for key, op, option in event:
        if key != 'option':
            continue
        chance = one(option, 'ai_chance')
        weight = float(one(chance, 'base'))
        for k, o, modifier in chance:
            if k == 'modifier' and trigger([n for n in modifier if n[0] != 'factor'], s, context(recipient, sender)):
                weight *= float(one(modifier, 'factor'))
        weights[one(option, 'name')] = weight
    assert weights[event_id + '.a'] + weights[event_id + '.b'] > 0, 'AI must retain a possible response'
    return event_id, weights, s['countries'][recipient]['variables']['eon_energy_ai_accept_chance']


def gui_enabled(s, name):
    s['temp'] = {}
    return trigger(one(gui_triggers, name), s, context('A'))


cases = []
# Execute only the two contractual aggregation fragments from the actual energy
# calculator, retaining one shared temporary environment between country calls.
energy_body = one(ast((ROOT / 'common/scripted_effects/!_energy_effects.txt').read_text(encoding='utf-8-sig')), 'calculate_energy_use')
contract_loops = [(index, block) for index, (key, op, block) in enumerate(energy_body)
                  if key == 'for_each_loop' and one(block, 'array') == 'energy_contracts_ammount']
assert len(contract_loops) == 2
export_index, export_loop = contract_loops[0]
import_index, import_loop = contract_loops[1]
assert energy_body[export_index + 1] == ('multiply_temp_variable', '=', [('all_sell_energy_use', '=', '-1')])
export_fragment = energy_body[export_index:export_index + 2]
import_fragment = energy_body[import_index:import_index + 5]
assert import_fragment[-1] == ('set_variable', '=', [('all_buy_energy_generation_display_var', '=', 'all_buy_energy_generation')])
native_resets = [node for node in energy_body[:export_index]
                 if node[0] == 'set_temp_variable' and node[2][0][0] in ('all_sell_energy_use', 'all_buy_energy_generation')]
s = state()
model['record'](s, 'A', 'B', 16, .05)
model['record'](s, 'A', 'C', -8, .05)
model['record'](s, 'B', 'A', -16, .05)
model['record'](s, 'B', 'D', 4, .05)
model['record'](s, 'C', 'D', -2, .05)
s['temp'] = {'all_sell_energy_use': 47, 'all_buy_energy_generation': 33}
for country, expected_export, expected_import in (('A', 8, 16), ('B', 16, 4), ('C', 2, 0), ('D', 0, 0), ('A', 8, 16)):
    s['countries'][country]['variables'].update(energy_balance=0, energy_sum=0)
    execute(native_resets, s, context(country))
    execute(export_fragment, s, context(country))
    execute(import_fragment, s, context(country))
    assert s['temp']['all_sell_energy_use'] == expected_export, (country, s['temp'], expected_export)
    assert s['temp']['all_buy_energy_generation'] == expected_import, (country, s['temp'], expected_import)
    assert s['countries'][country]['variables']['energy_balance'] == expected_import
    assert s['countries'][country]['variables']['energy_sum'] == expected_import
    assert s['countries'][country]['variables']['all_buy_energy_generation_display_var'] == expected_import
    cases.append(f'actual calculator contract aggregation country={country} exports={expected_export} imports={expected_import}')
assert len(native_resets) == 2, 'Both contractual aggregators must reset before traversing country records'

# A real old-source failure: a surplus seller accepts 8 but rejects 16/32 at .06.
# The new source must accept feasible volumes without the signed-volume penalty.
for quantity in (8, 16, 32, 64, 100):
    for price in (.05, .06, .1):
        for direction in (-1, 1):
            s = state()
            exporter, importer = ('A', 'B') if direction < 0 else ('B', 'A')
            s['countries'][exporter]['variables'].update(energy_balance=100, energy_sum=300, energy_consumption=200)
            s['countries'][importer]['variables'].update(energy_balance=-100, energy_sum=100, energy_consumption=200)
            signed = direction * quantity
            model['propose'](s, 'A', 'B', signed, price)
            event, weights, score = ai_reply(s)
            assert weights[event + '.a'] == 100 and weights[event + '.b'] == 0, (signed, price, score, weights)
            before = model['snapshot_arrays'](s)
            assert before['A']['energy_contractors'] == []
            execute(model['options'][event + '.a'], s, context('B', 'A'))
            model['assert_pair'](s, 'A', 'B', signed, price)
            paid = model['money'](s)
            assert model['compare'](paid[exporter][0], '=', quantity * price)
            assert model['compare'](paid[importer][1], '=', quantity * price)
            repeated = model['snapshot_arrays'](s)
            execute(model['options'][event + '.a'], s, context('B', 'A'))
            assert model['snapshot_arrays'](s) == repeated and model['money'](s) == paid
            cases.append(f'AI source and weekly payment direction={direction} quantity={quantity} price={price}')

# Four existing buyer buffers and their existing strict (0, 11) tolerance.
# Supply/cache values are internally consistent, and another supplier exists.
for idea, factor in ((None, 1.2), ('heavy_power_restrictions_spirit', 1.4),
                     ('some_power_restrictions_spirit', 1.3), ('some_additional_consumption_spirit', 1.1)):
    for quantity, expected in ((5, 5), (8, 58), (16, 16)):
        s = state()
        buyer = s['countries']['B']
        supply = factor * 200 - 5
        buyer['variables'].update(energy_sum=supply, energy_consumption=200,
                                  energy_balance=supply - 200, energy_temp=17)
        buyer['ideas'] = {idea} if idea else set()
        model['propose'](s, 'A', 'B', -quantity, .05)
        event, weights, score = ai_reply(s)
        assert model['compare'](score, '=', expected), (idea, quantity, score, expected)
        assert buyer['variables']['energy_temp'] == 17, 'AI need arithmetic must not mutate a persistent namesake'
        assert weights[event + '.a'] == 100 and weights[event + '.b'] == 0
        cases.append(f'buyer need policy={idea} quantity={quantity} score={expected}')

# Existing free-export refusal and expensive/deficit-buyer policy stay unchanged.
for signed, price, income, expense, accepted in ((8, 0, 10, 5, False),
                                                (-8, 0, 10, 5, True),
                                                (-8, .2, 10, 5, False),
                                                (-8, .05, 5, 10, False)):
    s = state()
    buyer = 'B' if signed < 0 else 'A'
    s['countries'][buyer]['variables'].update(energy_sum=0, energy_consumption=100,
                                             energy_balance=-100, display_income=income,
                                             display_expense=expense)
    model['pair'](s, 'A', 'B', -4, .04)
    before = model['snapshot_arrays'](s)
    model['propose'](s, 'A', 'B', signed, price)
    event, weights, score = ai_reply(s)
    assert (weights[event + '.a'] > 0) == accepted, (signed, price, income, score)
    if not accepted:
        execute(model['options'][event + '.b'], s, context('B', 'A'))
        assert model['snapshot_arrays'](s) == before
        assert not model['locked'](s, 'A') and not model['locked'](s, 'B')
    cases.append(f'existing policy signed={signed} price={price} budget={income - expense} accepted={accepted}')

# GUI changes use proposed next amount and recover the replaced record's capacity.
for signed, button in ((8, 'increase_energy_ammount_number_click_enabled'),
                       (-8, 'decrease_energy_ammount_number_click_enabled')):
    for supplier_balance, allowed in ((0, False), (1, True), (1.001, True), (.999, False)):
        s = state()
        model['pair'](s, 'A', 'B', signed, .05)
        supplier = 'B' if signed > 0 else 'A'
        s['countries'][supplier]['variables']['energy_balance'] = supplier_balance
        s['countries']['A']['variables'].update(energy_selling_selected_TAG='B', temp_energy_ammount=signed)
        before = deepcopy(s['countries'])
        assert gui_enabled(s, button) == allowed, (signed, supplier_balance, allowed)
        assert s['countries'] == before, 'GUI triggers may write only temporary variables'
        cases.append(f'GUI replacement {signed} next step supply remainder={supplier_balance} allowed={allowed}')

# Capacity may fall under a selected active amount. The player must still be
# able to reduce the number step by step, even before it becomes fulfillable.
for direction in (-1, 1):
    for destination, supplier_balance in ((13, -3), (0, -100)):
        s = state()
        signed = direction * 16
        supplier = 'A' if direction < 0 else 'B'
        model['pair'](s, 'A', 'B', signed, .04)
        s['countries'][supplier]['variables']['energy_balance'] = supplier_balance
        s['countries']['A']['variables'].update(energy_selling_selected_TAG='B', temp_energy_ammount=signed)
        toward_zero = 'increase_energy_ammount_number_click' if direction < 0 else 'decrease_energy_ammount_number_click'
        increasing_commitment = 'decrease_energy_ammount_number_click' if direction < 0 else 'increase_energy_ammount_number_click'
        assert not gui_enabled(s, increasing_commitment + '_enabled')
        assert not gui_enabled(s, 'confirm_energy_sell_click_enabled')
        for unused in range(16 - destination):
            assert gui_enabled(s, toward_zero + '_enabled'), (direction, destination, s['countries']['A']['variables'])
            execute(one(model['gui'], toward_zero), s, context('A'))
        assert s['countries']['A']['variables']['temp_energy_ammount'] == direction * destination
        assert gui_enabled(s, 'confirm_energy_sell_click_enabled')
        model['propose'](s, 'A', 'B', direction * destination, .05)
        if destination:
            model['response'](s, 'B', 'A')
            model['assert_pair'](s, 'A', 'B', direction * destination, .05)
        else:
            assert s['countries']['A']['arrays']['energy_contractors'] == []
            assert s['countries']['B']['arrays']['energy_contractors'] == []
        cases.append(f'actual GUI reduces infeasible selection direction={direction} destination={destination}')

# Direct dispatch uses the same bound as GUI, and exact maximum is inclusive.
for direction in (-1, 1):
    for quantity, allowed in ((32, True), (33, False)):
        s = state()
        supplier = 'A' if direction < 0 else 'B'
        s['countries'][supplier]['variables']['energy_balance'] = 32
        s['countries']['A']['variables'].update(energy_selling_selected_TAG='B', temp_energy_ammount=direction * quantity)
        assert gui_enabled(s, 'confirm_energy_sell_click_enabled') == allowed
        model['propose'](s, 'A', 'B', direction * quantity, .05)
        assert model['locked'](s, 'A') == allowed and model['locked'](s, 'B') == allowed
        assert bool(s['events']) == allowed
        assert s['countries']['A']['arrays']['energy_contractors'] == []
        cases.append(f'direct dispatch maximum direction={direction} quantity={quantity} allowed={allowed}')

# New selected country resets stale volume, while existing selection preserves it.
for existing in (False, True):
    s = state()
    if existing:
        model['pair'](s, 'A', 'B', -8, .07)
    s['countries']['A']['variables'].update(temp_energy_ammount=32, temp_energy_price=.11)
    s['countries']['A']['arrays']['temp_energy_sell_selection_countries'] = ['B']
    s['temp'] = {'i': 0}
    execute(one(selection, 'country_list_flag_button_click'), s, context('A'))
    assert s['countries']['A']['variables']['temp_energy_ammount'] == (-8 if existing else 0)
    assert model['compare'](s['countries']['A']['variables']['temp_energy_price'], '=', .07 if existing else .05)
    cases.append('select ' + ('existing' if existing else 'new') + ' partner volume and price')

# Capacity is rechecked at acceptance, including direction reversal/replacement.
for direction in (-1, 1):
    for late in ('capacity drop', 'framework withdrawal', 'valid replacement', 'duplicate supplier', 'supplier misaligned'):
        s = state()
        old, new = direction * 8, direction * 16
        model['pair'](s, 'A', 'B', old, .04)
        supplier = 'A' if direction < 0 else 'B'
        s['countries'][supplier]['variables']['energy_balance'] = 8
        model['propose'](s, 'A', 'B', new, .05)
        assert model['locked'](s, 'A') and model['locked'](s, 'B')
        if late == 'capacity drop':
            s['countries'][supplier]['variables']['energy_balance'] = 7
        elif late == 'framework withdrawal':
            s['countries']['B']['flags'].discard('energy_agreement@A')
        elif late == 'duplicate supplier':
            partner = 'B' if supplier == 'A' else 'A'
            model['record'](s, supplier, partner, -8, .04)
        elif late == 'supplier misaligned':
            s['countries'][supplier]['arrays']['energy_contracts_price'].append(.07)
        before = model['snapshot_arrays'](s)
        model['response'](s, 'B', 'A')
        if late == 'valid replacement':
            model['assert_pair'](s, 'A', 'B', new, .05)
        else:
            assert model['snapshot_arrays'](s) == before, (direction, late)
        assert not model['locked'](s, 'A') and not model['locked'](s, 'B')
        cases.append(f'acceptance capacity direction={direction} change={late}')

# Removing a replaced import reduces the future supplier's available capacity.
# Reversing direction therefore uses current balance minus the old positive8.
for direction in (-1, 1):
    for late_balance, accepted in ((24, True), (23, False)):
        s = state()
        model['pair'](s, 'A', 'B', -direction * 8, .04)
        supplier = 'A' if direction < 0 else 'B'
        s['countries'][supplier]['variables']['energy_balance'] = 24
        model['propose'](s, 'A', 'B', direction * 16, .05)
        assert model['locked'](s, 'A') and model['locked'](s, 'B')
        s['countries'][supplier]['variables']['energy_balance'] = late_balance
        before = model['snapshot_arrays'](s)
        model['response'](s, 'B', 'A')
        if accepted:
            model['assert_pair'](s, 'A', 'B', direction * 16, .05)
        else:
            assert model['snapshot_arrays'](s) == before
        cases.append(f'direction reversal removes old import direction={direction} balance={late_balance} accepted={accepted}')

# A third country's existing export remains committed during pair replacement.
for quantity, allowed in ((24, True), (25, False)):
    s = state()
    model['pair'](s, 'A', 'B', -8, .04)
    model['pair'](s, 'A', 'C', -4, .07)
    s['countries']['A']['variables']['energy_balance'] = 16
    before_c = deepcopy(s['countries']['C']['arrays'])
    model['propose'](s, 'A', 'B', -quantity, .05)
    assert model['locked'](s, 'A') == allowed
    if allowed:
        model['response'](s, 'B', 'A')
        model['assert_pair'](s, 'A', 'B', -quantity, .05)
    else:
        model['assert_pair'](s, 'A', 'B', -8, .04)
    assert s['countries']['C']['arrays'] == before_c
    model['assert_pair'](s, 'A', 'C', -4, .07)
    cases.append(f'replacement preserves third-party delivery quantity={quantity} allowed={allowed}')

# Zero remains a lawful unilateral termination even during a supplier shortage.
for direction in (-1, 1):
    s = state()
    model['pair'](s, 'A', 'B', direction * 8, .05)
    s['countries']['A']['variables']['energy_balance'] = -100
    s['countries']['B']['variables']['energy_balance'] = -100
    model['propose'](s, 'A', 'B', 0, .05)
    assert s['countries']['A']['arrays']['energy_contractors'] == []
    assert s['countries']['B']['arrays']['energy_contractors'] == []
    cases.append(f'zero termination remains available prior direction={direction}')

paths = ('common/scripted_guis/01_energy_gui.txt', 'events/00_Energy_market_events.txt',
         'common/scripted_effects/eon_energy_contract_effects.txt',
         'common/scripted_triggers/eon_energy_capacity_triggers.txt',
         'common/scripted_effects/!_energy_effects.txt')
print(json.dumps({'test_level': 'actual-source bounded execution; not engine/campaign/save-load proof',
                  'total_cases': len(cases), 'cases': cases,
                  'actual_ai_immediate_and_both_option_weights_executed': True,
                  'inherited_lifecycle_cases_passed': len(model['cases']),
                  'source_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}}, indent=2))
