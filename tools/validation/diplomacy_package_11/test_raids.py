"""Ordered source proof for authorized CT raids, not native runtime."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '77faaeb976af35b1185979ee85eabe7a6efc454a'
groups = Counter()

# Definitions only: previous scenarios execute and count in their own runner.
executor_path = ROOT / 'tools/validation/diplomacy_package_10/test_antiterror.py'
executor = executor_path.read_text(encoding='utf-8')
boundary = '\n# The actual native declaration callback must contribute once to both countries.'
assert executor.count(boundary) == 1, 'Ordered executor definition boundary changed'
source = {'__file__': str(executor_path), '__name__': 'raid_ordered_executor'}
exec(compile(executor.split(boundary)[0], str(executor_path), 'exec'), source)
model = source['model']
ast, one, context, switch = (source[name] for name in ('ast', 'one', 'context', 'switch'))
source_trigger, source_execute, source_value, source_compare = source['trigger'], source['execute'], model['value'], model['compare']

def read(path): return (ROOT / path).read_text(encoding='utf-8-sig')

def value(result, ctx, expression):
    if isinstance(expression, str) and expression.startswith('modifier@'):
        return result['countries'][ctx['scope']]['modifiers'].get(expression.split('@', 1)[1], 0)
    return source_value(result, ctx, expression)

def compare(left, operator, right):
    if operator not in ('=', '==', '!='):
        if isinstance(left, str) and left in COUNTRY_TAGS: left = COUNTRY_TAGS.index(left) + 1
        if isinstance(right, str) and right in COUNTRY_TAGS: right = COUNTRY_TAGS.index(right) + 1
    return source_compare(left, operator, right)

def state_scope(key, result, ctx):
    if key.startswith('var:'): candidate = model['country_ref'](result, ctx, key)
    else:
        try: candidate = int(key)
        except ValueError: return None
    return int(candidate) if isinstance(candidate, (int, float)) and int(candidate) in result['states'] else None

def trigger(nodes, result, ctx):
    index = 0
    while index < len(nodes):
        key, operator, val = nodes[index]; index += 1
        grouped = [(key, operator, val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        native_state = state_scope(key, result, ctx)
        if native_state is not None: passed = trigger(val, result, switch(ctx, native_state))
        elif key == 'owner':
            assert ctx['scope'] in result['states'], ('Owner requires an actual state scope', ctx)
            passed = trigger(val, result, switch(ctx, result['states'][ctx['scope']]['owner']))
        elif key == 'owns_state': passed = result['states'][int(value(result, ctx, val))]['owner'] == ctx['scope']
        elif key == 'country_exists': passed = val in result['countries'] and result['countries'][val]['exists']
        elif key == 'has_completed_focus': passed = val in result['countries'][ctx['scope']]['completed_focuses']
        elif key == 'has_government': passed = result['countries'][ctx['scope']]['government'] == val
        else: passed = source_trigger(grouped, result, ctx)
        if not passed: return False
    return True

def execute(nodes, result, ctx):
    index = 0
    while index < len(nodes):
        key, operator, val = nodes[index]; index += 1
        grouped = [(key, operator, val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        native_state = state_scope(key, result, ctx)
        if native_state is not None:
            execute(val, result, switch(ctx, native_state)); continue
        if key == 'owner':
            assert ctx['scope'] in result['states'], ('Owner requires an actual state scope', ctx)
            execute(val, result, switch(ctx, result['states'][ctx['scope']]['owner'])); continue
        country = result['countries'][ctx['scope']]
        if key == 'add_command_power':
            # Explicit capped native primitive fixture; script declarations and
            # surrounding guards are actual source, not an engine-cost claim.
            old = country['variables']['command_power']
            country['variables']['command_power'] = max(0, min(country['command_power_cap'], old + value(result, ctx, val)))
            result.setdefault('command_power_calls', []).append((ctx['scope'], value(result, ctx, val)))
        elif key == 'army_experience':
            old = country['variables']['army_experience']
            country['variables']['army_experience'] = max(0, min(country['army_experience_cap'], old + value(result, ctx, val)))
        elif key == 'random_list':
            assert result['random_choices'], 'No deterministic named random result supplied'
            choice = result['random_choices'].pop(0)
            if any(name == 'ct_sucess_chance' for name, op, body in val):
                desired = 'ct_sucess_chance' if choice == 'success' else '25' if choice == 'failure' else None
                selected = [(name, body) for name, op, body in val if name == desired]
            elif choice == 'ordinary_success': selected = [(name, body) for name, op, body in val if name == '85']
            else:
                selected = [(name, body) for name, op, body in val
                            if any(node[0] == 'country_event' and one(node[2], 'id') == choice for node in body)]
            assert len(selected) == 1, ('Named result does not uniquely select an actual branch', choice, selected)
            name, body = selected[0]
            result.setdefault('random_branches', []).append((ctx['scope'], name))
            execute(body, result, ctx)
        else: source_execute(grouped, result, ctx)

for namespace in (source, source['source'], source['source']['loader'], model):
    namespace['trigger'] = trigger; namespace['execute'] = execute; namespace['value'] = value; namespace['compare'] = compare

raid_effects = ast(read('common/scripted_effects/00_terrorism_scripted_effects.txt'))
model['effects']['complete_ct_raid'] = one(raid_effects, 'complete_ct_raid')
for registry, path in (('effects', 'common/scripted_effects/eon_ct_raid_effects.txt'),
                       ('capacity_triggers', 'common/scripted_triggers/eon_ct_raid_triggers.txt')):
    if (ROOT / path).exists():
        additions = {key: body for key, operator, body in ast(read(path))}
        assert not additions.keys() & model[registry].keys(), 'Raid helpers overwrite a prior helper'
        model[registry].update(additions)
decisions = ast(read('common/decisions/MDDC_Terrorist_again.txt'))
cancel_path = ROOT / 'common/decisions/eon_ct_raid_decisions.txt'
cancel_decisions = ast(cancel_path.read_text(encoding='utf-8-sig')) if cancel_path.exists() else []

def find(nodes, identity):
    found = []
    for key, operator, val in nodes:
        if key == identity: found.append(val)
        if isinstance(val, list): found.extend(find(val, identity))
    return found

def raid(identity):
    found = find(decisions, identity); assert len(found) == 1, (identity, len(found))
    return found[0]

# Inventory only is read from the committed baseline. All executed bodies below
# come from current game source; no historical scenario or model is executed.
baseline_result = subprocess.run(['git', 'show', BASELINE + ':common/decisions/MDDC_Terrorist_again.txt'],
                                 cwd=ROOT, capture_output=True, text=True, encoding='utf-8', check=True)
baseline_decisions = ast(baseline_result.stdout)
INVENTORY = []
def collect_inventory(nodes):
    for key, operator, body in nodes:
        if not isinstance(body, list): continue
        if key.startswith('GENERIC_terrorism_down_') and any(name == 'days_remove' for name, op, val in body):
            visible = one(body, 'visible')
            if any(isinstance(flag, str) and flag.startswith('anti_terror_agreement@') for flag in find(visible, 'has_country_flag')):
                target = [name for name, op, val in one(body, 'remove_effect') if name != 'log'][0]
                territory = int(one(one(one(body, 'highlight_states'), 'highlight_state_targets'), 'state'))
                INVENTORY.append({'slot': len(INVENTORY) + 1, 'decision': key, 'state': territory,
                                  'target': target, 'baseline_body': body})
        collect_inventory(body)
collect_inventory(baseline_decisions)
assert len(INVENTORY) == 31
COUNTRY_TAGS = ['A', 'B', 'C', 'D', 'ISI', 'ARM'] + sorted({entry['target'] for entry in INVENTORY})

def state(slot=1, domestic=False):
    result = source['state']()
    template = deepcopy(result['countries']['C'])
    for actor in COUNTRY_TAGS:
        if actor not in result['countries']: result['countries'][actor] = deepcopy(template)
    for actor, country in result['countries'].items():
        country.update(modifiers={'ct_effectiveness_modifier': 0}, command_power_cap=100, army_experience_cap=500,
                       government='democratic', completed_focuses={'ARM_invite_asala'}, original_tag=actor)
        country['variables'].update(terrorism=10, terrorism_mana=10, terrorism_hate=0, army_experience=0)
    result['countries']['ARW']['exists'] = False
    result['states'] = {entry['state']: {'owner': 'A' if domestic else 'B', 'controller': 'A' if domestic else 'B'} for entry in INVENTORY}
    row = INVENTORY[slot - 1]
    if 10 <= slot <= 17: result['countries']['A' if domestic else 'B']['original_tag'] = row['target']
    result['random_choices'] = ['success', 'ordinary_success']
    result['countries']['A']['flags'].update({'anti_terror_agreement@B', 'eon_ct_contribution@B'})
    result['countries']['B']['flags'].update({'anti_terror_agreement@A', 'eon_ct_contribution@A'})
    for actor in ('A', 'B'):
        result['countries'][actor]['variables'].update(ct_effectiveness_add=.05, ct_command_debuff=-5, costil_command_buff=5)
    return result

def check(result, nodes, actor='A'):
    result['temp'] = {}
    return trigger(nodes, result, context(actor))

def effect(result, nodes, actor='A'):
    result['temp'] = {}
    execute(nodes, result, context(actor))

def helper(result, name, actor='A'):
    effect(result, [('eon_ct_raid_' + name, '=', 'yes')], actor)

def native_hook(result, name, victim='A', subject=False, raids_first=True):
    hooks = one(ast(read('common/on_actions/eon_ct_raid_on_actions.txt')), 'on_actions')
    ctx = context(victim, 'D') if subject else context('D', victim)
    def current():
        result['temp'] = {}
        execute(one(one(hooks, name), 'effect'), result, ctx)
    if raids_first: current()
    source['native_hook'](result, name, victim, subject)
    if not raids_first: current()

def start(result, slot=1, actor='A', force=False):
    body = raid(INVENTORY[slot - 1]['decision'])
    guards = [val for key, operator, val in body if key in ('allowed', 'visible', 'available', 'custom_cost_trigger')]
    ready = all(check(result, guard, actor) for guard in guards)
    if ready or force: effect(result, one(body, 'complete_effect'), actor)
    return ready

def finish(result, slot=1, actor='A'):
    effect(result, one(raid(INVENTORY[slot - 1]['decision']), 'remove_effect'), actor)

def cancel(result, slot=1, actor='A', force=False):
    found = find(cancel_decisions, 'eon_cancel_ct_raid_' + str(slot)); assert len(found) == 1
    body = found[0]
    guards = [val for key, operator, val in body if key in ('allowed', 'visible', 'available')]
    ready = all(check(result, guard, actor) for guard in guards)
    assert one(body, 'cost') == '0'
    if ready or force: effect(result, one(body, 'complete_effect'), actor)
    return ready

def account(result, actor='A'):
    variables = result['countries'][actor]['variables']
    return variables['command_power'] + variables.get('eon_ct_raid_refund_due', 0)

def assert_pending(result, slot=1, actor='A', owner='B', paid=True, cancelled=False):
    country = result['countries'][actor]
    assert country['variables'].get('eon_ct_raid_owner_' + str(slot)) == owner
    assert 'eon_ct_raid_pending_' + str(slot) in country['flags']
    assert ('eon_ct_raid_paid_' + str(slot) in country['flags']) == paid
    assert ('eon_ct_raid_cancelled_' + str(slot) in country['flags']) == cancelled

def assert_clear(result, slot=1, actor='A'):
    country = result['countries'][actor]
    assert not country['flags'] & {'eon_ct_raid_' + part + '_' + str(slot) for part in ('pending', 'paid', 'cancelled', 'window')}
    assert country['variables'].get('eon_ct_raid_owner_' + str(slot), 0) == 0

def snapshot_external(result):
    return {actor: {key: deepcopy(value) for key, value in country.items() if key not in ('variables', 'flags')}
            | {'variables': {key: deepcopy(value) for key, value in country['variables'].items()
                             if not key.startswith('eon_ct_raid_') and key not in ('command_power', 'terrorism', 'terrorism_mana', 'terrorism_hate', 'army_experience')},
               'flags': {flag for flag in country['flags'] if not flag.startswith('eon_ct_raid_')}}
            for actor, country in result['countries'].items()}

focus = sys.argv[2] if len(sys.argv) == 3 and sys.argv[1] == '--focus' else None
assert focus in (None, 'owner', 'treaty', 'complete', 'cap'), ('Unknown focused proof', sys.argv[1:])

if focus in (None, 'cap'):
    result = state(); body = raid('GENERIC_terrorism_down_isis_191')
    effect(result, one(body, 'complete_effect'))
    assert result['countries']['A']['variables']['command_power'] == 75
    result['countries']['A']['variables']['command_power'] = 100
    result['countries']['A']['flags'].discard('anti_terror_agreement@B')
    result['countries']['B']['flags'].discard('anti_terror_agreement@A')
    effect(result, one(body, 'remove_effect'))
    assert result['countries']['A']['variables']['command_power'] == 100 and result['countries']['A']['variables'].get('eon_ct_raid_refund_due', 0) == 25, (
        'RED: invalid paid raid loses its command-power claim at the cap',
        result['countries']['A']['variables']['command_power'], result['countries']['A']['variables'].get('eon_ct_raid_refund_due', 0))
    groups['invalid_paid_raid_preserves_refund_claim_when_command_power_is_capped'] += 1

if focus in (None, 'complete'):
    result = state(); body = raid('GENERIC_terrorism_down_isis_191')
    effect(result, one(body, 'complete_effect'))
    effect(result, one(body, 'remove_effect'))
    assert result['countries']['SYR']['variables']['terrorism'] == 9
    original = deepcopy(result['countries']); branches = deepcopy(result['random_branches'])
    result['random_choices'] = ['success', 'ordinary_success']
    effect(result, one(body, 'remove_effect'))
    assert result['countries'] == original and result['random_branches'] == branches, (
        'RED: repeated original raid completion executes its outcome twice',
        result['countries']['SYR']['variables']['terrorism'], result['random_branches'])
    groups['original_raid_remove_callback_executes_outcome_once'] += 1

# The five-day native decision callback must recheck the paid raid's authorization.
for change in ('owner', 'treaty'):
    if focus is not None and focus != change: continue
    result = state(); body = raid('GENERIC_terrorism_down_isis_191')
    assert check(result, one(body, 'visible')) and check(result, one(body, 'custom_cost_trigger'))
    effect(result, one(body, 'complete_effect'))
    assert result['countries']['A']['variables']['command_power'] == 75
    if change == 'owner': result['states'][191]['owner'] = result['states'][191]['controller'] = 'C'
    else:
        result['countries']['A']['flags'].discard('anti_terror_agreement@B')
        result['countries']['B']['flags'].discard('anti_terror_agreement@A')
    before = {actor: country['variables'].get('terrorism', 0) for actor, country in result['countries'].items()}
    effect(result, one(body, 'remove_effect'))
    after = {actor: country['variables'].get('terrorism', 0) for actor, country in result['countries'].items()}
    assert after == before and not result.get('random_branches'), (
        'RED: five-day raid completion ignores lost authorization', change, before, after, result.get('random_branches'))
    groups['paid_raid_remove_rechecks_original_owner_and_treaty'] += 1

if focus is None:
    for row in INVENTORY:
        result = state(row['slot']); before = snapshot_external(result)
        assert start(result, row['slot']), ('Original national raid route is unavailable', row['slot'], row['decision'])
        assert_pending(result, row['slot'])
        assert result['countries']['A']['variables']['command_power'] == 75
        assert ('A', 'eon_ct_raid_window_' + str(row['slot']), 7) in result['timer_declarations']
        assert one(raid(row['decision']), 'days_remove') == '5' and one(raid(row['decision']), 'days_re_enable') == '35'
        finish(result, row['slot']); assert_clear(result, row['slot'])
        assert result['countries'][row['target']]['variables']['terrorism'] == 9
        assert result['countries']['A']['variables']['army_experience'] == 5
        assert result['countries']['A']['variables']['command_power'] == 75
        assert snapshot_external(result) == before
        countries = deepcopy(result['countries']); branches = deepcopy(result['random_branches'])
        finish(result, row['slot'])
        assert result['countries'] == countries and result['random_branches'] == branches
        groups['all31_actual_paid_routes_capture_state_owner_execute_proxy_outcome_and_clear_once'] += 1

    for slot in (1, 8, 10, 13):
        result = state(slot, domestic=True)
        result['countries']['A']['flags'].discard('anti_terror_agreement@B')
        result['countries']['B']['flags'].discard('anti_terror_agreement@A')
        assert start(result, slot); assert_pending(result, slot, owner='A')
        finish(result, slot); assert_clear(result, slot)
        assert result['countries'][INVENTORY[slot - 1]['target']]['variables']['terrorism'] == 9
        groups['domestic_ownership_needs_no_foreign_treaty_including_special_national_routes'] += 1

    for amount, expected in ((25, False), (25.01, True), (26, True)):
        result = state(); result['countries']['A']['variables']['command_power'] = amount
        before = deepcopy(result['countries'])
        assert start(result, force=True) == expected
        if expected:
            assert_pending(result)
            assert model['compare'](result['countries']['A']['variables']['command_power'], '=', amount - 25)
        else: assert result['countries'] == before
        groups['original_strict_CP_more_than25_and_fresh_paid_start_guard'] += 1

    for alteration in ('receiver treaty flag missing', 'actor treaty flag missing', 'direct owner war',
                       'actor absent', 'owner absent', 'slot pending', 'slot paid orphan', 'slot retired',
                       'terrorism zero', 'terrorism rebellion'):
        result = state(); a, b = result['countries']['A'], result['countries']['B']
        if alteration == 'receiver treaty flag missing': b['flags'].discard('anti_terror_agreement@A')
        elif alteration == 'actor treaty flag missing': a['flags'].discard('anti_terror_agreement@B')
        elif alteration == 'direct owner war': a['wars'].add('B'); b['wars'].add('A')
        elif alteration == 'actor absent': a['exists'] = False
        elif alteration == 'owner absent': b['exists'] = False
        elif alteration == 'slot pending': a['flags'].add('eon_ct_raid_pending_1')
        elif alteration == 'slot paid orphan': a['flags'].add('eon_ct_raid_paid_1')
        elif alteration == 'slot retired': a['flags'].add('eon_ct_raid_retired_1')
        elif alteration == 'terrorism zero': result['countries']['SYR']['variables']['terrorism'] = 0
        elif alteration == 'terrorism rebellion': result['countries']['SYR']['flags'].add('GENERIC_terrorism_rebeliion_flag')
        before = deepcopy(result['countries'])
        assert not start(result, force=True), ('Cached raid bypassed fresh admission', alteration)
        assert result['countries'] == before and not result.get('command_power_calls')
        groups['foreign_mutual_consent_liveness_and_slot_guards_rechecked_before_cost'] += 1

    for alteration in ('ASALA proxy alive', 'ASALA ARM focus absent', 'Red Brigades secondary state lost',
                       'Red Brigades owner original tag changed', 'Red Brigades government communist',
                       'Red Brigades rebellion only', 'Red Army government communist'):
        slot = 8 if alteration.startswith('ASALA') else 13 if alteration.startswith('Red Army') else 10
        result = state(slot)
        if alteration == 'ASALA proxy alive': result['countries']['ARW']['exists'] = True
        elif alteration == 'ASALA ARM focus absent': result['countries']['ARM']['completed_focuses'].clear()
        elif alteration == 'Red Brigades secondary state lost': result['states'][78]['owner'] = 'C'
        elif alteration == 'Red Brigades owner original tag changed': result['countries']['B']['original_tag'] = 'OTH'
        elif alteration == 'Red Brigades government communist': result['countries']['ITA']['government'] = 'communism'
        elif alteration == 'Red Brigades rebellion only': result['countries']['ITA']['flags'].add('GENERIC_terrorism_rebeliion_flag')
        elif alteration == 'Red Army government communist': result['countries']['GER']['government'] = 'communism'
        before = deepcopy(result['countries'])
        assert not start(result, slot, force=True), ('A national predicate was weakened', alteration)
        assert result['countries'] == before
        groups['ASALA_Italy_multiterritory_original_tag_and_native_NOR_national_filters'] += 1

    for alteration in ('owner changes to actor', 'owner changes to new ally', 'direct war', 'owner absent',
                       'actor treaty missing', 'owner treaty missing', 'proxy terrorism zero', 'proxy rebellion',
                       'window gone original callback'):
        result = state(); assert start(result)
        if alteration == 'owner changes to actor': result['states'][191]['owner'] = 'A'
        elif alteration == 'owner changes to new ally':
            result['states'][191]['owner'] = 'C'
            result['countries']['C']['flags'].add('anti_terror_agreement@A'); result['countries']['A']['flags'].add('anti_terror_agreement@C')
        elif alteration == 'direct war': result['countries']['A']['wars'].add('B'); result['countries']['B']['wars'].add('A')
        elif alteration == 'owner absent': result['countries']['B']['exists'] = False
        elif alteration == 'actor treaty missing': result['countries']['A']['flags'].discard('anti_terror_agreement@B')
        elif alteration == 'owner treaty missing': result['countries']['B']['flags'].discard('anti_terror_agreement@A')
        elif alteration == 'proxy terrorism zero': result['countries']['SYR']['variables']['terrorism'] = 0
        elif alteration == 'proxy rebellion': result['countries']['SYR']['flags'].add('GENERIC_terrorism_rebeliion_flag')
        elif alteration == 'window gone original callback': result['countries']['A']['flags'].discard('eon_ct_raid_window_1')
        before = {actor: country['variables']['terrorism'] for actor, country in result['countries'].items()}
        finish(result); assert_clear(result)
        assert {actor: country['variables']['terrorism'] for actor, country in result['countries'].items()} == before
        assert not result.get('random_branches') and account(result) == 100
        assert 'eon_ct_raid_retired_1' not in result['countries']['A']['flags']
        groups['consumed_original_callback_rechecks_frozen_owner_policy_treaty_and_window'] += 1

    for row in INVENTORY:
        result = state(row['slot']); assert start(result, row['slot'])
        assert cancel(result, row['slot']); assert_pending(result, row['slot'], paid=False, cancelled=True)
        assert account(result) == 100
        assert not start(result, row['slot'], force=True)
        before = deepcopy(result['countries'])
        assert not cancel(result, row['slot'], force=True)
        assert result['countries'] == before
        finish(result, row['slot']); assert_clear(result, row['slot'])
        assert not result.get('random_branches')
        result['random_choices'] = ['success', 'ordinary_success']
        assert start(result, row['slot']), ('Consumed cancellation cannot reopen its own native route', row['slot'])
        groups['all31_human_cancel_routes_refund_once_hold_identity_and_reopen_after_consumed_remove'] += 1

    for alteration in ('actor ai', 'not pending', 'unpaid pending', 'actor absent'):
        result = state()
        if alteration != 'not pending': assert start(result)
        if alteration == 'actor ai': result['countries']['A']['ai'] = True
        elif alteration == 'unpaid pending': result['countries']['A']['flags'].discard('eon_ct_raid_paid_1')
        elif alteration == 'actor absent': result['countries']['A']['exists'] = False
        before = deepcopy(result['countries'])
        assert not cancel(result, force=True), ('Cached free cancel bypassed fresh human paid ownership', alteration)
        assert result['countries'] == before
        groups['human_free_cancel_rechecks_liveness_pending_paid_and_AI_before_effect'] += 1

    for current_cp, cap, expected_cp, expected_due in ((75, 100, 100, 0), (90, 100, 100, 15),
                                                     (100, 100, 100, 25), (110, 100, 100, 35),
                                                     (75, 50, 50, 50)):
        result = state(); assert start(result)
        result['countries']['A']['variables']['command_power'] = current_cp
        result['countries']['A']['command_power_cap'] = cap
        before_total = current_cp + 25
        assert cancel(result)
        assert result['countries']['A']['variables']['command_power'] == expected_cp
        assert result['countries']['A']['variables'].get('eon_ct_raid_refund_due', 0) == expected_due
        assert account(result) == before_total
        helper(result, 'try_refund'); assert account(result) == before_total
        # Explicit new headroom and a larger native cap admit only the retained claim.
        result['countries']['A']['command_power_cap'] = 200
        helper(result, 'try_refund'); assert account(result) == before_total
        assert result['countries']['A']['variables'].get('eon_ct_raid_refund_due', 0) == 0
        assert_pending(result, paid=False, cancelled=True)
        finish(result); assert_clear(result)
        groups['observed_full_partial_capped_and_negative_credit_preserve_CP_plus_owned_claim'] += 1

    for changed in ('owner', 'treaty', 'proxy rebellion'):
        result = state(); assert start(result)
        if changed == 'owner': result['states'][191]['owner'] = 'C'
        elif changed == 'treaty': result['countries']['B']['flags'].discard('anti_terror_agreement@A')
        else: result['countries']['SYR']['flags'].add('GENERIC_terrorism_rebeliion_flag')
        helper(result, 'daily_cleanup'); assert_pending(result, paid=False, cancelled=True)
        assert account(result) == 100
        before = deepcopy(result['countries']); helper(result, 'daily_cleanup')
        assert result['countries'] == before
        finish(result); assert_clear(result)
        assert not result.get('random_branches')
        groups['daily_invalid_authorization_refunds_once_but_keeps_original_callback_lock'] += 1

    result = state(); assert start(result); assert start(result, 2)
    result['countries']['A']['flags'].discard('eon_ct_raid_window_1')
    helper(result, 'daily_cleanup'); assert_clear(result)
    assert 'eon_ct_raid_retired_1' in result['countries']['A']['flags']
    assert_pending(result, 2)
    assert not start(result, force=True)
    before = deepcopy(result['countries']); finish(result)
    assert result['countries'] == before and not result.get('random_branches')
    finish(result, 2); assert_clear(result, 2)
    assert result['countries']['SYR']['variables']['terrorism'] == 9
    for other in INVENTORY[1:]:
        result['countries']['B']['original_tag'] = other['target'] if 10 <= other['slot'] <= 17 else 'B'
        assert check(result, one(raid(other['decision']), 'available')), ('Watchdog disabled another slot', other['slot'])
    result['countries']['B']['original_tag'] = 'B'
    assert start(result, 3)
    groups['lost_callback_watchdog_retires_only_its_slot_before_late_original_remove'] += 1

    result = state(); assert start(result); assert start(result, 2)
    assert result['countries']['A']['variables']['command_power'] == 50
    before = deepcopy(result['countries']); assert not start(result, force=True)
    assert result['countries'] == before
    assert cancel(result); assert_pending(result, 2)
    finish(result); assert_clear(result)
    finish(result, 2); assert_clear(result, 2)
    assert result['countries']['SYR']['variables']['terrorism'] == 9
    assert result['countries']['A']['variables']['command_power'] == 75
    groups['independent_raid_slots_keep_owners_costs_and_callbacks_separate'] += 1

    result = state()
    result['countries']['A']['flags'].update({'eon_ct_raid_cancelled_1', 'eon_ct_raid_window_1'})
    result['countries']['A']['variables']['eon_ct_raid_owner_1'] = 'D'
    assert start(result); assert_pending(result)
    finish(result); assert_clear(result)
    assert result['countries']['SYR']['variables']['terrorism'] == 9
    groups['fresh_unreserved_slot_initialization_clears_orphan_terms_without_poisoning_new_raid'] += 1

    result = state(); before = deepcopy(result['countries'])
    finish(result)
    assert result['countries'] == before and not result.get('random_branches')
    assert not result.get('command_power_calls')
    groups['unknown_unpaid_legacy_callback_does_not_infer_outcome_or_refund'] += 1

    for hook, subject in (('on_annex', False), ('on_subject_annexed', True)):
        for victim in ('A', 'B'):
            for raids_first in (False, True):
                result = state(); assert start(result); assert start(result, 2)
                result['countries'][victim]['exists'] = False
                for territory in result['states'].values():
                    if territory['owner'] == victim: territory['owner'] = territory['controller'] = 'D'
                annexer_before = account(result, 'D')
                native_hook(result, hook, victim, subject, raids_first)
                assert account(result) == 100 and account(result, 'D') == annexer_before
                if victim == 'A':
                    assert_clear(result); assert_clear(result, 2)
                    assert result['countries']['A']['variables']['command_power'] == 50
                    assert result['countries']['A']['variables']['eon_ct_raid_refund_due'] == 50
                    assert {'eon_ct_raid_retired_1', 'eon_ct_raid_retired_2'} <= result['countries']['A']['flags']
                else:
                    assert_pending(result, paid=False, cancelled=True); assert_pending(result, 2, paid=False, cancelled=True)
                    assert result['countries']['A']['variables']['command_power'] == 100
                countries = deepcopy(result['countries']); native_hook(result, hook, victim, subject, not raids_first)
                assert result['countries'] == countries
                result['countries'][victim]['exists'] = True
                helper(result, 'daily_cleanup')
                assert account(result) == 100 and account(result, 'D') == annexer_before
                finish(result); finish(result, 2)
                assert not result.get('random_branches') and account(result) == 100
                if victim == 'A': assert not start(result, force=True)
                groups['native_annex_both_roles_hooks_orders_keep_refund_with_original_payer'] += 1

    result = state(); assert start(result)
    result['countries']['A']['flags'].discard('anti_terror_agreement@B')
    helper(result, 'daily_cleanup'); assert_pending(result, paid=False, cancelled=True)
    result['countries']['A']['flags'].add('anti_terror_agreement@B')
    helper(result, 'daily_cleanup'); assert_pending(result, paid=False, cancelled=True)
    finish(result); assert_clear(result)
    assert not result.get('random_branches') and account(result) == 100
    groups['restored_authorization_cannot_reactivate_a_daily_cancelled_paid_operation'] += 1

    for outer, nested in (('success', 'ordinary_success'),
                          ('success', 'counter_terrorism_raids.6'), ('success', 'counter_terrorism_raids.7'),
                          ('success', 'counter_terrorism_raids.8'), ('success', 'counter_terrorism_raids.9'),
                          ('success', 'counter_terrorism_raids.10'), ('failure', 'counter_terrorism_raids.1'),
                          ('failure', 'counter_terrorism_raids.4'), ('failure', 'counter_terrorism_raids.5')):
        result = state(); result['random_choices'] = [outer, nested]
        assert start(result); finish(result); assert_clear(result)
        target, actor = result['countries']['SYR']['variables'], result['countries']['A']['variables']
        assert target['terrorism'] == (9 if outer == 'success' else 11)
        assert actor['terrorism_mana'] == (9 if outer == 'success' else 11)
        assert actor['terrorism_hate'] == (0 if outer == 'success' else 1)
        assert actor['army_experience'] == (5 if outer == 'success' else 0)
        expected_events = [] if nested == 'ordinary_success' else [{'target': 'A', 'id': nested, 'from': 'A'}]
        assert result['events'] == expected_events
        assert len(result['random_branches']) == 2 and not result['random_choices']
        groups['deterministic_named_seam_executes_all_real_random_outcome_event_and_XP_branches'] += 1

    for modifier, expected in ((-.5, 50), (0, 50), (.5, 75), (1, 100)):
        result = state(); result['countries']['A']['modifiers']['ct_effectiveness_modifier'] = modifier
        assert start(result); finish(result)
        assert result['temp']['ct_sucess_chance'] == expected
        groups['unchanged_native_random_weight_formula_uses_original_ROOT_modifier_and_clamps'] += 1

    for outer, terror, mana, expected_terror, expected_mana in (('success', 1, 1, 1, 1), ('failure', 100, 100, 100, 100)):
        result = state(); result['random_choices'] = [outer, 'ordinary_success' if outer == 'success' else 'counter_terrorism_raids.4']
        result['countries']['SYR']['variables']['terrorism'] = terror
        result['countries']['A']['variables']['terrorism_mana'] = mana
        assert start(result); finish(result)
        assert result['countries']['SYR']['variables']['terrorism'] == expected_terror
        assert result['countries']['A']['variables']['terrorism_mana'] == expected_mana
        groups['actual_inherited_terrorism_and_mana_bounds_survive_lifecycle_wrapper'] += 1

    result = state()
    result['countries']['A']['variables'].update(treasury=246, debt=40, eon_aid_partner='D', eon_aid_amount=15,
                                               eon_aid_escrow=15, eon_support_refund_due=11,
                                               pending_assume_debt_offer='D', eon_consultation_partner='D', eon_consultation_topic=3)
    result['countries']['A']['flags'].update({'eon_aid_reserved', 'eon_aid_outgoing', 'eon_consultation_reserved',
                                            'eon_consultation_active', 'trade_agreement@D', 'mutual_investment_treaty_@D'})
    before = snapshot_external(result)
    assert start(result); assert cancel(result); finish(result)
    assert snapshot_external(result) == before and account(result) == 100
    assert not result.get('random_branches')
    groups['raid_start_cancel_and_refund_preserve_aid_economy_treaties_energy_and_other_dialogues'] += 1

source_paths = ['common/decisions/MDDC_Terrorist_again.txt', 'common/scripted_effects/eon_ct_raid_effects.txt',
                'common/scripted_triggers/eon_ct_raid_triggers.txt', 'common/decisions/eon_ct_raid_decisions.txt',
                'common/decisions/categories/eon_ct_raid_categories.txt', 'common/on_actions/eon_ct_raid_on_actions.txt',
                'localisation/english/eon_ct_raid_l_english.yml', 'localisation/russian/eon_ct_raid_l_russian.yml']

print(json.dumps({'all_passed': True, 'actual_source_scenarios': sum(groups.values()),
                  'adapter_semantics_cases': 0, 'total_cases': sum(groups.values()),
                  'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source_paths},
                  'groups': groups, 'baseline': BASELINE,
                  'proof_scope': 'ordered actual-source raid callbacks with named random-result and capped native primitive fixtures',
                  'not_proven': ['native decision/callback timing and re-enable', 'elapsed watchdog expiry', 'state scope binding',
                                 'native command power and XP caps', 'random probability', 'GUI', 'save/load', 'campaign']}, indent=2))
