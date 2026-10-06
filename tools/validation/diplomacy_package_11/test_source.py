"""Source/API and exact gameplay boundaries for paid existing CT raids; not HOI4 runtime."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
import sys as package12_sys
package12_sys.path.insert(0, str(ROOT / 'tools/validation'))

# Package12 restores only six civilian satellite actions/five effects before old proofs.
from diplomacy_package_12.test_source import (
    NEW as LATER_PACKAGE12_NEW, EXISTING as LATER_PACKAGE12_EXISTING,
    check_owned_existing as check_later_package12_owned, package12_original_bytes,
)
check_later_package12_owned()

# Package13 restores only twelve native/ten extended satellite effect ranges before old proofs.
from diplomacy_package_13.test_source import (
    NEW as LATER_PACKAGE13_NEW, EXISTING as LATER_PACKAGE13_EXISTING,
    check_owned_existing as check_later_package13_owned, package13_original_bytes,
)
check_later_package13_owned()

# Package14 proves its six files before restoring nine blocks/eight locale lines.
from diplomacy_package_14.test_source import (
    EXISTING as LATER_PACKAGE14_EXISTING, check_owned_existing as check_later_package14_owned,
    package14_original_bytes, package14_historical_existing,
)
check_later_package14_owned()

# Package15 strictly restores eleven current COM network files before older proofs.
from diplomacy_package_15.test_source import (
    check_owned_existing as check_later_package15_owned,
    package15_original_bytes, package15_historical_existing,
)
check_later_package15_owned()
from diplomacy_package_16.test_source import (
    NEW as LATER_PACKAGE16_NEW, package16_original_bytes, package16_historical_existing,
    historical_actions as package16_historical_actions, check_owned_existing as check_later_package16_owned,
)
check_later_package16_owned()
from diplomacy_package_17.test_source import (
    NEW as LATER_PACKAGE17_NEW, package17_original_bytes, package17_historical_existing,
    historical_actions as package17_historical_actions, check_owned_existing as check_later_package17_owned,
)
check_later_package17_owned()
from diplomacy_package_18.test_source import (
    NEW as LATER_PACKAGE18_NEW, package18_original_bytes, package18_historical_existing,
    package18_original_validator_bytes, historical_actions as package18_historical_actions,
    check_owned_existing as check_later_package18_owned,
)
check_later_package18_owned()
from diplomacy_package_19.test_source import (
    NEW as LATER_PACKAGE19_NEW, package19_original_bytes, package19_historical_existing,
    package19_original_validator_bytes, historical_actions as package19_historical_actions,
    check_owned_existing as check_later_package19_owned,
)
check_later_package19_owned()
BASELINE = '77faaeb976af35b1185979ee85eabe7a6efc454a'
EXISTING = {'common/decisions/MDDC_Terrorist_again.txt'}
NEW = {
    'common/scripted_effects/eon_ct_raid_effects.txt',
    'common/scripted_triggers/eon_ct_raid_triggers.txt',
    'common/decisions/eon_ct_raid_decisions.txt',
    'common/decisions/categories/eon_ct_raid_categories.txt',
    'common/on_actions/eon_ct_raid_on_actions.txt',
    'localisation/english/eon_ct_raid_l_english.yml',
    'localisation/russian/eon_ct_raid_l_russian.yml',
}
MAPPING = [
    ('GENERIC_terrorism_down_isis_191', '191', 'SYR'),
    ('GENERIC_terrorism_down_isis_193', '193', 'SYR'),
    ('GENERIC_terrorism_down_isis_995', '995', 'SYR'),
    ('GENERIC_terrorism_down_isis_166', '166', 'IRQ'),
    ('GENERIC_terrorism_down_isis_167', '167', 'IRQ'),
    ('GENERIC_terrorism_down_isis_168', '168', 'IRQ'),
    ('GENERIC_terrorism_down_isis_641', '641', 'IRQ'),
    ('GENERIC_terrorism_down_asala_935', '935', 'ARW'),
    ('GENERIC_terrorism_down_asala_163', '163', 'ARW'),
    ('GENERIC_terrorism_down_red_brigades_81', '81', 'ITA'),
    ('GENERIC_terrorism_down_red_brigades_78', '78', 'ITA'),
    ('GENERIC_terrorism_down_red_brigades_1060', '1060', 'ITA'),
    ('GENERIC_terrorism_down_red_army_faction_44', '44', 'GER'),
    ('GENERIC_terrorism_down_people_lib_league_30', '30', 'NOR'),
    ('GENERIC_terrorism_down_council_vtlava_1018', '1018', 'CZE'),
    ('GENERIC_terrorism_down_wild_commune_122', '122', 'HUN'),
    ('GENERIC_terrorism_down_12th_november_286', '286', 'AUS'),
    ('GENERIC_terrorism_down_isis_egy_216', '216', 'EGY'),
    ('GENERIC_terrorism_down_isis_nig_338', '338', 'NIG'),
    ('GENERIC_terrorism_down_isis_nig_339', '339', 'NIG'),
    ('GENERIC_terrorism_down_isis_nig_340', '340', 'NIG'),
    ('GENERIC_terrorism_down_isis_alg_381', '381', 'ALG'),
    ('GENERIC_terrorism_down_isis_tun_390', '390', 'TUN'),
    ('GENERIC_terrorism_down_isis_taj_723', '723', 'TAJ'),
    ('GENERIC_terrorism_down_sau', '177', 'SAU'),
    ('GENERIC_terrorism_down_uae', '180', 'UAE'),
    ('GENERIC_terrorism_down_isis_ing_1126', '1126', 'ING'),
    ('GENERIC_terrorism_down_isis_kbk_674', '674', 'KBK'),
    ('GENERIC_terrorism_down_isis_kcc_1125', '1125', 'KCC'),
    ('GENERIC_terrorism_down_isis_dag_671', '671', 'DAG'),
    ('GENERIC_terrorism_down_isis_che_672', '672', 'CHE'),
]
OWNED_IDS = {name for name, state, target in MAPPING}
TOKEN = re.compile(rb'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|[=<>!]+|[^\s{}=<>!#"]+')


def boundary_blocks(data):
    tokens = [match for match in TOKEN.finditer(data) if not match[0].startswith(b'#')]
    stack, result = [], []
    for index, token in enumerate(tokens):
        if token[0] == b'{':
            block = {'key': tokens[index - 2][0].decode().lstrip('\ufeff'),
                     'start': tokens[index - 2].start(), 'depth': len(stack),
                     'parent': stack[-1]['key'] if stack else None}
            stack.append(block); result.append(block)
        elif token[0] == b'}':
            assert stack, 'Extra closing brace'
            stack.pop()['end'] = token.end()
    assert not stack, 'Unclosed block'
    return result


def ast(data):
    if isinstance(data, str): data = data.encode('utf-8')
    tokens = [match[0].decode().strip('"').lstrip('\ufeff') for match in TOKEN.finditer(data) if not match[0].startswith(b'#')]
    index = 0
    def body():
        nonlocal index
        result = []
        while index < len(tokens) and tokens[index] != '}':
            key = tokens[index]; index += 1
            if index == len(tokens) or tokens[index] not in ('=', '==', '<', '>', '<=', '>=', '!='):
                result.append(('__item__', '=', key)); continue
            operator = tokens[index]; index += 1
            assert index < len(tokens), ('Missing value', key)
            if tokens[index] == '{':
                index += 1; value = body()
                assert index < len(tokens) and tokens[index] == '}', ('Unclosed block', key)
                index += 1
            else:
                value = tokens[index]; index += 1
            result.append((key, operator, value))
        return result
    result = body(); assert index == len(tokens), 'Extra closing brace'
    return result


def one(nodes, key):
    values = [value for name, operator, value in nodes if name == key]
    assert len(values) == 1, (key, len(values))
    return values[0]


def rows(nodes):
    for row in nodes:
        yield row
        if isinstance(row[2], list): yield from rows(row[2])


def package11_original_bytes(path, actual):
    """Restore only the enumerated 31 existing paid-raid decision blocks."""
    if path not in EXISTING:
        return actual
    old = subprocess.check_output(['git', 'show', BASELINE + ':' + path], cwd=ROOT)
    assert actual.startswith(b'\xef\xbb\xbf') == old.startswith(b'\xef\xbb\xbf'), path
    assert actual.endswith(b'\n') == old.endswith(b'\n'), path
    assert (b'\r\n' in actual) == (b'\r\n' in old), path
    assert b'\r' not in actual.replace(b'\r\n', b''), path
    original = {block['key']: block for block in boundary_blocks(old)
                if block['depth'] == 1 and block['key'] in OWNED_IDS}
    current = {block['key']: block for block in boundary_blocks(actual)
               if block['depth'] == 1 and block['key'] in OWNED_IDS}
    assert len(original) == len(current) == 31 and original.keys() == current.keys() == OWNED_IDS, path
    restored = actual
    for name, block in sorted(current.items(), key=lambda item: item[1]['start'], reverse=True):
        previous = original[name]
        restored = restored[:block['start']] + old[previous['start']:previous['end']] + restored[block['end']:]
    assert restored == old, ('Unrelated package11 gameplay bytes changed', path)
    return restored


def check_owned_existing():
    for path in EXISTING:
        package11_original_bytes(path, (ROOT / path).read_bytes())


def main():
    groups, receipts, sources, helpers, kinds = Counter(), [], {}, {}, {}
    for path in sorted(NEW):
        assert (ROOT / path).is_file(), ('Missing paid CT-raid lifecycle source', path)
        data = (ROOT / path).read_bytes()
        assert b'\r' not in data and data.endswith(b'\n'), ('New LF/EOF convention', path)
        assert data.startswith(b'\xef\xbb\xbf') == path.endswith('.yml'), ('New BOM convention', path)
        assert '\ufffd' not in data.decode('utf-8-sig'), path
        if path.endswith('.txt'):
            boundary_blocks(data); sources[path] = ast(data)
        if '/scripted_effects/' in path or '/scripted_triggers/' in path:
            for key, operator, value in sources[path]:
                assert key.startswith('eon_ct_raid_') and key not in helpers, ('Unowned/duplicate helper', key)
                helpers[key] = value
                kinds[key] = 'effects' if '/scripted_effects/' in path else 'triggers'
        receipts.append({'path': path, 'sha256': hashlib.sha256(data).hexdigest()})
        groups['new_source_encoding_braces_and_namespace'] += 1
    check_owned_existing()
    raid_path = next(iter(EXISTING))
    old_data = subprocess.check_output(['git', 'show', BASELINE + ':' + raid_path], cwd=ROOT)
    actual_data = (ROOT / raid_path).read_bytes()
    assert package11_original_bytes(raid_path, actual_data) == old_data
    receipts.append({'path': raid_path, 'sha256': hashlib.sha256(actual_data).hexdigest(), 'all_unowned_bytes_exact': True})
    groups['enumerated_31_existing_ranges_only_all_23_other_decisions_and_outer_bytes_exact'] += 1
    old_category, category = ast(old_data), ast(actual_data)
    assert len(old_category) == len(category) == 1 and old_category[0][0] == category[0][0]
    old_decisions, decisions = old_category[0][2], category[0][2]
    assert len(old_decisions) == len(decisions) == 54
    assert [key for key, op, value in old_decisions] == [key for key, op, value in decisions]
    groups['all_54_existing_decision_IDs_order_and_category_preserved'] += 1
    trees = ('common', 'history', 'events', 'interface', 'gfx', 'localisation', 'music', 'map', 'sound',
             'portraits', 'tutorial', 'descriptions', 'scenario_tests', 'descriptor.mod', 'era_of_nations.mod', 'thumbnail.png')
    baseline_paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, '--', *trees], cwd=ROOT).decode().splitlines()
    changed = subprocess.check_output(['git', 'diff', '--name-only', BASELINE, '--', *trees], cwd=ROOT).decode().splitlines()
    untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', *trees], cwd=ROOT).decode().splitlines()
    untracked = [path for path in untracked if path not in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]
    changed = [path for path in changed if path not in LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | package14_historical_existing(BASELINE) | package15_historical_existing(BASELINE) | package16_historical_existing(BASELINE) | LATER_PACKAGE16_NEW | package17_historical_existing(BASELINE) | LATER_PACKAGE17_NEW | package18_historical_existing(BASELINE) | LATER_PACKAGE18_NEW | package19_historical_existing(BASELINE) | LATER_PACKAGE19_NEW]
    assert set(changed) | set(untracked) == EXISTING | NEW | LATER_PACKAGE12_NEW | LATER_PACKAGE13_NEW, ('Unowned gameplay changes', changed, untracked)
    assert set(changed).intersection(baseline_paths) == EXISTING
    assert not NEW.intersection(baseline_paths) and set(untracked) <= NEW | LATER_PACKAGE12_NEW | LATER_PACKAGE13_NEW
    assert len(baseline_paths) == 68300
    groups['all_68299_unrelated_existing_gameplay_files_byte_preserved_exact_seven_additions'] += 1
    native_ids = []
    for path in baseline_paths:
        if path.startswith('common/scripted_diplomatic_actions/') and path.endswith('.txt'):
            old = subprocess.check_output(['git', 'show', BASELINE + ':' + path], cwd=ROOT)
            assert package12_original_bytes(path, package16_original_bytes(path, (ROOT / path).read_bytes())) == old, ('Old native action bytes changed', path)
            native_ids.extend(block['key'] for block in boundary_blocks(old)
                              if block['parent'] == 'scripted_diplomatic_actions' and block['depth'] == 1)
    actual_native_ids = [block['key'] for path in (ROOT / 'common/scripted_diplomatic_actions').glob('*.txt')
                         for block in boundary_blocks(path.read_bytes())
                         if block['parent'] == 'scripted_diplomatic_actions' and block['depth'] == 1]
    actual_native_ids = package16_historical_actions(actual_native_ids)
    assert len(native_ids) == len(set(native_ids)) == len(actual_native_ids) == len(set(actual_native_ids)) == 65
    assert actual_native_ids and set(actual_native_ids) == set(native_ids)
    groups['all_65_native_actions_and_all_native_action_files_byte_unchanged'] += 1
    expected_helpers = {'eon_ct_raid_owner_authorizes', 'eon_ct_raid_try_refund',
                        'eon_ct_raid_daily_cleanup', 'eon_ct_raid_cleanup_annexed_owner'}
    expected_helpers |= {'eon_ct_raid_' + helper + '_' + str(number)
                         for helper in ('policy', 'start_ready', 'authorization', 'cancel_ready',
                                        'clear', 'start', 'cancel', 'finish', 'cleanup')
                         for number in range(1, 32)}
    assert set(helpers) == expected_helpers and len(helpers) == 283
    groups['exact_283_owned_helper_IDs_no_missing_or_unreviewed_helpers'] += 1
    definitions = Counter()
    for folder in ('scripted_effects', 'scripted_triggers'):
        for path in (ROOT / 'common' / folder).glob('*.txt'):
            definitions.update(key for key, op, value in ast(path.read_bytes()) if key in helpers)
    for key in expected_helpers:
        assert definitions[key] == 1, ('Duplicate helper ID', key)
        groups['global_owned_helper_ID_uniqueness'] += 1
    owner_authorizes = ast('exists = yes var:eon_ct_raid_actor = { exists = yes OR = { tag = PREV AND = { NOT = { tag = PREV } NOT = { has_war_with = PREV } has_country_flag = anti_terror_agreement@PREV PREV = { has_country_flag = anti_terror_agreement@PREV } } } }')
    assert helpers['eon_ct_raid_owner_authorizes'] == owner_authorizes
    groups['existing_owner_and_actor_self_or_mirrored_treaty_direct_war_guard_PREV_scopes'] += 1
    old_blocks, current_blocks = boundary_blocks(old_data), boundary_blocks(actual_data)
    def field_bytes(data, blocks, decision, field):
        matches = [block for block in blocks if block['parent'] == decision and block['depth'] == 2 and block['key'] == field]
        assert len(matches) == 1, (decision, field)
        block = matches[0]
        return data[block['start']:block['end']]
    for number, (decision, state, target) in enumerate(MAPPING, 1):
        suffix = str(number)
        prefix = 'eon_ct_raid_'
        flag = lambda role: prefix + role + '_' + suffix
        helper = lambda role: prefix + role + '_' + suffix
        owner = flag('owner')
        before, actual = one(old_decisions, decision), one(decisions, decision)
        assert [row for row in actual if row[0] not in ('available', 'complete_effect', 'remove_effect')] == [
            row for row in before if row[0] not in ('complete_effect', 'remove_effect')]
        groups['all_original_raid_fields_preserved_except_three_owned_entrypoints'] += 1
        for field in ('visible', 'ai_will_do', 'custom_cost_trigger', 'highlight_states'):
            assert field_bytes(actual_data, current_blocks, decision, field) == field_bytes(old_data, old_blocks, decision, field)
            groups['original_national_visible_AI_weights_resource_gate_map_highlights_exact_bytes'] += 1
        assert one(actual, 'custom_cost_trigger') == ast('command_power > 25')
        assert one(actual, 'custom_cost_text') == 'command_power_more_than_25'
        assert one(actual, 'days_remove') == '5' and one(actual, 'days_re_enable') == '35'
        assert one(one(actual, 'highlight_states'), 'highlight_state_targets') == ast('state = ' + state)
        assert one(one(before, 'remove_effect'), target) == ast('complete_ct_raid = yes')
        groups['literal_state_target_original_strict_25CP_five_day_35_day_contract'] += 1
        assert helpers[helper('policy')] == one(before, 'visible'), ('Original native NOR policy changed', decision)
        groups['original_visible_copied_exactly_to_fresh_policy_including_dormant_ASALA_and_NOR'] += 1
        assert one(actual, 'available') == ast('custom_trigger_tooltip = { tooltip = eon_ct_raid_available_tt ' + helper('start_ready') + ' = yes }')
        groups['original_raid_availability_has_its_fresh_slot_guard_and_localized_reason'] += 1
        for field, method in (('complete_effect', 'start'), ('remove_effect', 'finish')):
            assert one(actual, field) == ast(helper(method) + ' = yes')
            groups['old_decision_three_entrypoints_delegate_its_exact_owned_slot'] += 1
        ready = ('exists = yes ' + helper('policy') + ' = yes command_power > 25 '
                 + ' '.join('NOT = { has_country_flag = ' + flag(role) + ' }' for role in ('pending', 'paid', 'retired'))
                 + ' set_temp_variable = { eon_ct_raid_actor = THIS } '
                 + state + ' = { owner = { eon_ct_raid_owner_authorizes = yes } }')
        assert helpers[helper('start_ready')] == ast(ready)
        groups['fresh_start_strict_affordability_owner_consent_no_pending_paid_or_retired_no_new_human_AI_bans'] += 1
        authorization = ('exists = yes has_country_flag = ' + flag('pending') + ' check_variable = { ' + owner + ' > 0 } '
                         + helper('policy') + ' = yes set_temp_variable = { eon_ct_raid_actor = THIS } '
                         + 'set_temp_variable = { eon_ct_raid_original_owner = ' + owner + ' } '
                         + state + ' = { owner = { check_variable = { eon_ct_raid_original_owner = THIS } eon_ct_raid_owner_authorizes = yes } }')
        assert helpers[helper('authorization')] == ast(authorization)
        assert 'command_power' not in str(helpers[helper('authorization')])
        groups['finish_rechecks_original_policy_frozen_owner_consent_without_second_CP_requirement'] += 1
        assert helpers[helper('cancel_ready')] == ast('exists = yes is_ai = no has_country_flag = ' + flag('pending') + ' has_country_flag = ' + flag('paid'))
        groups['manual_cancel_checks_current_human_own_exact_pending_paid_slot'] += 1
        clear = ' '.join('clr_country_flag = ' + flag(role) for role in ('pending', 'paid', 'cancelled', 'window')) + ' clear_variable = ' + owner
        assert helpers[helper('clear')] == ast(clear)
        groups['clear_erases_only_own_slot_preserves_retirement_refund_and_other_operations'] += 1
        start = ('if = { limit = { ' + helper('start_ready') + ' = yes } ' + helper('clear') + ' = yes '
                 + state + ' = { owner = { set_temp_variable = { eon_ct_raid_captured_owner = THIS } } } '
                 + 'set_variable = { ' + owner + ' = eon_ct_raid_captured_owner } '
                 + 'set_country_flag = ' + flag('pending') + ' set_country_flag = ' + flag('paid') + ' '
                 + 'set_country_flag = { flag = ' + flag('window') + ' days = 7 value = 1 } '
                 + 'add_command_power = -25 custom_effect_tooltip = eon_ct_raid_start_tt }')
        assert helpers[helper('start')] == ast(start)
        groups['fresh_guarded_single_debit_capture_real_owner_clear_orphans_seven_day_watchdog'] += 1
        cancel = ('if = { limit = { has_country_flag = ' + flag('pending') + ' } set_country_flag = ' + flag('cancelled') + ' '
                  + 'if = { limit = { has_country_flag = ' + flag('paid') + ' } clr_country_flag = ' + flag('paid')
                  + ' add_to_variable = { eon_ct_raid_refund_due = 25 } } eon_ct_raid_try_refund = yes }')
        assert helpers[helper('cancel')] == ast(cancel)
        groups['cancel_consumes_paid_once_queues_exact_25_and_keeps_callback_reservation'] += 1
        finish = ('if = { limit = { has_country_flag = ' + flag('pending') + ' } '
                  + 'if = { limit = { has_country_flag = ' + flag('paid') + ' has_country_flag = ' + flag('window') + ' '
                  + 'NOT = { has_country_flag = ' + flag('cancelled') + ' } ' + helper('authorization') + ' = yes } '
                  + helper('clear') + ' = yes ' + target + ' = { complete_ct_raid = yes } } '
                  + 'else = { ' + helper('cancel') + ' = yes ' + helper('clear') + ' = yes } }')
        assert helpers[helper('finish')] == ast(finish)
        groups['finish_consumes_ownership_before_original_literal_outcome_invalid_no_outcome_refund_once'] += 1
        cleanup = ('if = { limit = { has_country_flag = ' + flag('pending') + ' } '
                   + 'if = { limit = { NOT = { has_country_flag = ' + flag('window') + ' } } '
                   + helper('cancel') + ' = yes set_country_flag = ' + flag('retired') + ' ' + helper('clear') + ' = yes } '
                   + 'else_if = { limit = { NOT = { ' + helper('authorization') + ' = yes } } ' + helper('cancel') + ' = yes } }')
        assert helpers[helper('cleanup')] == ast(cleanup)
        groups['daily_invalid_cancel_retains_identity_watchdog_retires_before_release'] += 1
    refund = ('if = { limit = { exists = yes check_variable = { eon_ct_raid_refund_due > 0 } } '
              + 'set_temp_variable = { eon_ct_raid_refund_attempt = eon_ct_raid_refund_due } '
              + 'set_temp_variable = { eon_ct_raid_cp_before = command_power } '
              + 'add_command_power = eon_ct_raid_refund_attempt '
              + 'set_temp_variable = { eon_ct_raid_refund_received = command_power } '
              + 'subtract_from_temp_variable = { eon_ct_raid_refund_received = eon_ct_raid_cp_before } '
              + 'if = { limit = { check_variable = { eon_ct_raid_refund_received > eon_ct_raid_refund_attempt } } '
              + 'set_temp_variable = { eon_ct_raid_refund_received = eon_ct_raid_refund_attempt } } '
              + 'subtract_from_variable = { eon_ct_raid_refund_due = eon_ct_raid_refund_received } }')
    assert helpers['eon_ct_raid_try_refund'] == ast(refund)
    assert 'clamp' not in str(helpers['eon_ct_raid_try_refund']) and 'cap' not in str(helpers['eon_ct_raid_try_refund'])
    groups['refund_measures_real_CP_delta_bounded_above_allows_negative_for_overcap_claim_conservation_no_cap_guess'] += 1
    assert helpers['eon_ct_raid_daily_cleanup'] == ast(' '.join('eon_ct_raid_cleanup_' + str(number) + ' = yes' for number in range(1,32)) + ' eon_ct_raid_try_refund = yes')
    groups['daily_checks_all_31_independent_slots_then_tries_remaining_owned_claim'] += 1
    annex = ' '.join('if = { limit = { has_country_flag = eon_ct_raid_pending_' + str(number) + ' } eon_ct_raid_cancel_' + str(number) + ' = yes set_country_flag = eon_ct_raid_retired_' + str(number) + ' eon_ct_raid_clear_' + str(number) + ' = yes }' for number in range(1,32))
    assert helpers['eon_ct_raid_cleanup_annexed_owner'] == ast(annex)
    groups['annexed_operator_own_pending_slots_cancel_retire_clear_without_transfer_claim'] += 1
    actions = one(sources['common/decisions/eon_ct_raid_decisions.txt'], 'eon_ct_raid_operations')
    new_decision_ids = {'eon_cancel_ct_raid_' + str(number) for number in range(1,32)}
    assert len(actions) == len(new_decision_ids) == 31 and {key for key, op, body in actions} == new_decision_ids
    all_decision_ids = [block['key'] for path in (ROOT / 'common/decisions').glob('*.txt')
                        for block in boundary_blocks(path.read_bytes()) if block['depth'] == 1]
    for number in range(1,32):
        name = 'eon_cancel_ct_raid_' + str(number)
        body = one(actions, name)
        ready, cancel = 'eon_ct_raid_cancel_ready_' + str(number), 'eon_ct_raid_cancel_' + str(number)
        assert all_decision_ids.count(name) == 1, ('Duplicate new cancel ID', name)
        assert one(body, 'icon') == 'generic_decision' and one(body, 'allowed') == ast('always = yes')
        assert one(body, 'visible') == ast('is_ai = no ' + ready + ' = yes')
        assert one(body, 'available') == ast(ready + ' = yes') and one(body, 'cost') == '0'
        assert one(body, 'complete_effect') == ast('if = { limit = { ' + ready + ' = yes } custom_effect_tooltip = eon_ct_raid_cancel_tt ' + cancel + ' = yes }')
        assert one(body, 'ai_will_do') == ast('factor = 0')
        assert not any(key.startswith('target') or key == 'state_trigger' for key, op, value in body)
        groups['31_unique_free_current_human_normal_cancel_decisions_fresh_own_slot_guard'] += 1
    operations = one(sources['common/decisions/categories/eon_ct_raid_categories.txt'], 'eon_ct_raid_operations')
    assert one(operations, 'icon') == 'generic_foreign_policy' and one(operations, 'allowed') == ast('always = yes')
    category_visible = ('is_ai = no OR = { check_variable = { eon_ct_raid_refund_due > 0 } '
                        + ' '.join('has_country_flag = eon_ct_raid_pending_' + str(number) for number in range(1,32)) + ' }')
    assert one(operations, 'visible') == ast(category_visible)
    groups['human_category_visible_for_any_pending_slot_or_remaining_refund_claim'] += 1
    hooks = one(sources['common/on_actions/eon_ct_raid_on_actions.txt'], 'on_actions')
    assert one(hooks, 'on_daily') == ast('effect = { eon_ct_raid_daily_cleanup = yes }')
    assert {key for key, op, value in hooks} == {'on_daily','on_annex','on_subject_annexed'}
    for action, target in (('on_annex','FROM'), ('on_subject_annexed','ROOT')):
        assert one(hooks, action) == ast('effect = { ' + target + ' = { eon_ct_raid_cleanup_annexed_owner = yes } every_country = { limit = { exists = yes NOT = { tag = ' + target + ' } } eon_ct_raid_daily_cleanup = yes } }')
        groups['annex_correct_native_owner_scope_first_then_all_present_survivors_current_THIS_authorization'] += 1
    locale, locale_counts = {}, {}
    expected_locale = new_decision_ids | {name + '_desc' for name in new_decision_ids} | {
        'eon_ct_raid_operations', 'eon_ct_raid_operations_desc', 'eon_ct_raid_start_tt',
        'eon_ct_raid_cancel_tt', 'eon_ct_raid_refund_tt', 'eon_ct_raid_available_tt'}
    assert len(expected_locale) == 68
    for language in ('english','russian'):
        lines = (ROOT / f'localisation/{language}/eon_ct_raid_l_{language}.yml').read_text(encoding='utf-8-sig').splitlines()
        assert lines[0] == 'l_' + language + ':'
        entries = [re.fullmatch(r' ([\w.]+):0 "(.*)"', line).groups() for line in lines[1:]]
        assert len(entries) == len(dict(entries)), ('Duplicate new locale ID',language)
        locale[language] = dict(entries)
        assert set(locale[language]) == expected_locale
        locale_counts[language] = Counter()
        for path in (ROOT / 'localisation' / language).glob('*.yml'):
            locale_counts[language].update(re.findall(r'^ ([\w.]+):', path.read_text(encoding='utf-8-sig'), re.M))
    for key in expected_locale:
        assert all(locale_counts[language][key] == 1 for language in ('english','russian')), ('Missing/duplicate locale',key)
        assert re.findall(r'\[.*?\]|\$[\w.]+\$', locale['english'][key]) == re.findall(r'\[.*?\]|\$[\w.]+\$', locale['russian'][key])
        for reference in re.findall(r'\$([\w.]+)\$', locale['english'][key]):
            assert all(locale_counts[language][reference] > 0 for language in ('english','russian')), ('Unresolved old/new locale macro',reference)
        groups['68_bilingual_locale_keys_unique_matching_native_variable_and_old_label_macros_resolve'] += 1
    for number, (decision,state,target) in enumerate(MAPPING,1):
        name = 'eon_cancel_ct_raid_' + str(number)
        for language in ('english','russian'):
            assert '$' + decision + '$' in locale[language][name]
            assert re.findall(r'\$([\w.]+)\$', locale[language][name + '_desc']) == [decision, 'eon_ct_raid_cancel_tt']
        groups['cancel_label_and_description_keep_exact_original_raid_ID_reference'] += 1
    assert '[?eon_ct_raid_refund_due|1]' in locale['english']['eon_ct_raid_operations_desc']
    assert '$eon_ct_raid_refund_tt$' in locale['english']['eon_ct_raid_operations_desc']
    groups['remaining_owned_claim_visible_with_native_variable_format_and_refund_rules'] += 1
    # Original policy helpers intentionally retain old multi-child native NOR.
    for path,nodes in sources.items():
        if not path.endswith('.txt'): continue
        checked = [(key,op,value) for key,op,value in nodes if not key.startswith('eon_ct_raid_policy_')]
        for key,op,value in rows(checked):
            if key == 'NOT':
                assert isinstance(value,list) and len(value) == 1, ('New native NOT must have one child/group',path,value)
                groups['all_new_negations_single_child_original_NOR_policy_verbatim_exception'] += 1
            if key.startswith('eon_ct_raid_') and value == 'yes':
                assert key in helpers, ('Missing owned helper reference',key)
            if key in ('tooltip','custom_effect_tooltip') and isinstance(value,str) and value.startswith('eon_ct_raid_'):
                assert value in expected_locale, ('Missing tooltip locale',value)
            if key in ('has_country_flag','set_country_flag','clr_country_flag'):
                flag = one(value,'flag') if isinstance(value,list) else value
                if '@' in flag:
                    assert flag == 'anti_terror_agreement@PREV', ('Unreviewed pair flag suffix',flag)
    groups['new_helper_tooltip_and_primary_PREV_pair_flag_references_resolve'] += 1
    wrappers = {'if','else_if','else','owner'}
    mutators = {'set_variable','clear_variable','set_temp_variable','add_to_variable','subtract_from_variable',
                'subtract_from_temp_variable','set_country_flag','clr_country_flag','add_command_power','custom_effect_tooltip'}
    def effects_only(helper,nodes):
        for key,op,value in nodes:
            if key == 'limit': continue
            if key in wrappers or key.isdigit():
                effects_only(helper,value); continue
            if key in {target for name,state,target in MAPPING}:
                assert helper.startswith('eon_ct_raid_finish_')
                assert value == ast('complete_ct_raid = yes')
                continue
            assert key in mutators or (key in helpers and kinds[key] == 'effects'), ('Unowned effect or trigger used as effect',helper,key)
            if key == 'add_command_power':
                assert (helper.startswith('eon_ct_raid_start_') and value == '-25') or (
                    helper == 'eon_ct_raid_try_refund' and value == 'eon_ct_raid_refund_attempt')
            if key in ('set_variable','add_to_variable','subtract_from_variable','set_temp_variable','subtract_from_temp_variable'):
                assert all(name.startswith('eon_ct_raid_') for name,operator,amount in value), ('Unowned variable write',helper,value)
            if key == 'clear_variable': assert value.startswith('eon_ct_raid_owner_')
            if key in ('set_country_flag','clr_country_flag'):
                flag = one(value,'flag') if isinstance(value,list) else value
                assert flag.startswith('eon_ct_raid_') and '@' not in flag, ('Unowned flag write',helper,flag)
            if key == 'custom_effect_tooltip': assert value in expected_locale
    for helper,body in helpers.items():
        if kinds[helper] == 'effects':
            effects_only(helper,body)
            groups['new_effects_own_only_slot_claim_25CP_or_original_outcome_no_broad_cash_PP_war_treaty_AI_mutations'] += 1
    for path in ('common/scripted_effects/00_terrorism_scripted_effects.txt','events/00_Terrorism_events.txt',
                 'common/scripted_diplomatic_actions/MDC_terrorism.txt','common/on_actions/00_terrorist_on_actions.txt',
                 'common/scripted_effects/eon_ct_effects.txt','common/scripted_triggers/eon_ct_triggers.txt',
                 'common/on_actions/eon_ct_on_actions.txt','common/dynamic_modifiers/terrorist_dynamic_modifiers.txt',
                 'common/dynamic_modifiers/costilb_modifier.txt','common/on_actions/00_costili.txt'):
        assert (ROOT / path).read_bytes() == subprocess.check_output(['git','show',BASELINE + ':' + path],cwd=ROOT), ('Related unowned storyline/weights/treaty/compensation changed',path)
        groups['existing_random_raid_outcome_events_treaty_and_shared_AI_CP_compensation_byte_unchanged'] += 1
    native = {'checked':False}
    docs = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation')
    if docs.exists():
        effects,triggers = ((docs / (kind + '_documentation.md')).read_text(encoding='utf-8-sig') for kind in ('effects','triggers'))
        for key in mutators - {'custom_effect_tooltip'}:
            assert '\n## ' + key + '\n' in effects, ('Unsupported native effect',key)
            groups['installed_primary_effect_API'] += 1
        for key in ('check_variable','has_country_flag','exists','command_power','set_temp_variable','owns_state','has_war_with'):
            assert '\n## ' + key + '\n' in triggers, ('Unsupported native trigger',key)
            groups['installed_primary_trigger_API'] += 1
        decision_docs = (docs.parent / 'common/decisions/_documentation.md').read_text(encoding='utf-8-sig')
        for text in (chr(96)+'visible'+chr(96)+':', chr(96)+'available'+chr(96)+':',
                     'Scope: THIS = Country, FROM = Country/State (if targeted)', 'Checked each frame when the interface is refreshed'):
            assert text in decision_docs
            groups['installed_primary_country_decision_scope_available_UI_refresh_documentation'] += 1
        dynamic_docs = (docs / 'dynamic_variables_documentation.md').read_text(encoding='utf-8-sig')
        for section,detail in (('command_power','command power of country'),('owner','owner of the state')):
            match = re.search(r'(?m)^### ' + section + r'\n(.*?)(?=^### |\Z)',dynamic_docs,re.S|re.M)
            assert match and detail in match[1], ('Unsupported native dynamic variable',section)
            groups['installed_primary_country_CP_and_state_owner_dynamic_variables'] += 1
        assert 'Does not run the remove_effect or put the decision on cooldown' in effects
        groups['native_force_remove_does_not_settle_or_preserve_original_callback_cooldown'] += 1
        nor = (docs.parent / 'common/decisions/NOR.txt').read_text(encoding='utf-8-sig')
        assert 'set_country_flag = NOR_already_asked_a_fascist@PREV' in nor
        ita = (docs.parent / 'common/decisions/ITA.txt').read_text(encoding='utf-8-sig')
        assert 'add_command_power = ITA_vallo_alpino_cp_cost_negative' in ita
        chi = (docs.parent / 'common/decisions/CHI_decisions.txt').read_text(encoding='utf-8-sig')
        assert 'add_command_power = var:CHI_declare_war_zone_cp_cost' in chi
        groups['installed_primary_PREV_pair_flag_and_two_variable_CP_rhs_shipped_examples'] += 3
        scope_sample = (docs.parent / 'common/scripted_effects/00_scripted_effects.txt').read_text(encoding='utf-8-sig')
        assert re.search(r'set_temp_variable\s*=\s*{\s*new_country\s*=\s*this\s*}\s*PREV\s*=\s*{\s*every_controlled_state\s*=\s*{\s*limit\s*=\s*{\s*occupied_country_tag\s*=\s*country_to_initiate\s*}\s*var:new_country\s*=\s*{',scope_sample)
        operation_sample = (docs.parent / 'common/scripted_effects/operation_strat_effects.txt').read_text(encoding='utf-8-sig')
        assert 'set_temp_variable = { captor = operative_captor }' in operation_sample
        assert 'set_variable = { rescue_operative_from = captor }' in operation_sample
        groups['installed_primary_country_valued_temp_visibility_across_state_country_and_operative_frames'] += 2
        sprites = (docs.parent / 'interface/decisions.gfx').read_text(encoding='utf-8-sig')
        assert 'name = "GFX_decision_generic_decision"' in sprites
        assert any(b'GFX_decision_category_generic_foreign_policy' in path.read_bytes() for path in (ROOT / 'interface').glob('*.gfx'))
        hook_docs = (docs.parent / 'common/on_actions/_documentation.md').read_text(encoding='utf-8-sig')
        assert '- ' + chr(96) + 'on_daily' + chr(96) in hook_docs
        groups['installed_primary_existing_decision_category_sprites_and_daily_API'] += 3
        native = {'checked':True,'path':str(docs),'not_proven':'native ROOT/THIS decision callback timing, refund caps, save-load and playable campaigns'}

    print(json.dumps({'all_passed': True, 'total_cases': sum(groups.values()), 'groups': groups,
                      'baseline': BASELINE, 'final_gameplay_sha256': {item['path']: item['sha256'] for item in receipts},
                      'existing_gameplay_files_byte_preserved': len(baseline_paths)-len(EXISTING),
                      'unique_native_action_IDs': len(actual_native_ids), 'new_helper_IDs': len(helpers),
                      'owned_raid_decisions': len(MAPPING), 'unowned_raid_decisions_byte_preserved': 23,
                      'new_locale_keys_per_language': len(expected_locale), 'native_primary_documentation': native,
                      'new_files': [item for item in receipts if item['path'] in NEW],
                      'owned_existing_files': [item for item in receipts if item['path'] in EXISTING],
                      'not_proven': 'HOI4 compilation, decision/cancel timing, native CP cap and delta behavior, GUI/AI/save-load/campaign; arbitrary duplicate consumed callbacks outside guarantee'}, indent=2))



if __name__ == '__main__':
    main()
