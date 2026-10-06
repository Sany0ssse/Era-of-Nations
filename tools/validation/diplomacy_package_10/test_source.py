"""Source and exact gameplay-boundary checks for the existing CT treaty lifecycle."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
import sys as package11_sys
package11_sys.path.insert(0, str(ROOT / 'tools/validation'))

# Package11 restores only its 31 enumerated raid decision ranges before old proofs.
from diplomacy_package_11.test_source import (
    NEW as LATER_PACKAGE11_NEW, EXISTING as LATER_PACKAGE11_EXISTING,
    check_owned_existing as check_later_package11_owned, package11_original_bytes,
)
check_later_package11_owned()

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
from diplomacy_package_20.test_source import (
    NEW as LATER_PACKAGE20_NEW, package20_original_bytes, package20_historical_existing,
    package20_original_validator_bytes, historical_actions as package20_historical_actions,
    check_owned_existing as check_later_package20_owned,
)
check_later_package20_owned()
BASELINE = '45dedfc85e7aece235f8fa1ab536326e6dce6923'
EXISTING = {
    'common/scripted_diplomatic_actions/MDC_terrorism.txt',
    'common/on_actions/00_terrorist_on_actions.txt',
}
NEW = {
    'common/scripted_effects/eon_ct_effects.txt',
    'common/scripted_triggers/eon_ct_triggers.txt',
    'common/scripted_diplomatic_actions/eon_ct_actions.txt',
    'common/on_actions/eon_ct_on_actions.txt',
    'localisation/english/eon_ct_l_english.yml',
    'localisation/russian/eon_ct_l_russian.yml',
}
NEW_ACTIONS = {'eon_withdraw_antiterror_proposal'}
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


def owned_select(data, block):
    if block['parent'] == 'scripted_diplomatic_actions' and block['depth'] == 1:
        return block['key'] if block['key'] in {'declare_anti_terror_agreement', 'cancel_anti_terror_agreement'} else None
    if block['key'] == 'if' and block['parent'] == 'for_each_loop' and block['depth'] == 5:
        body = data[block['start']:block['end']]
        if not re.search(rb'limit\s*=\s*{\s*has_country_flag\s*=\s*anti_terror_agreement@v\s*}', body):
            return None
        parents = [item['key'] for item in boundary_blocks(data)
                   if item['depth'] == 1 and item['start'] < block['start'] < item['end']]
        assert len(parents) == 1 and parents[0] in {'on_annex', 'on_subject_annexed'}
        return parents[0]
    return None


def package10_original_bytes(path, actual):
    """Restore only the exact two native treaty/two active annex blocks."""
    if path not in EXISTING:
        return actual
    old = subprocess.check_output(['git', 'show', BASELINE + ':' + path], cwd=ROOT)
    assert actual.startswith(b'\xef\xbb\xbf') == old.startswith(b'\xef\xbb\xbf'), path
    assert actual.endswith(b'\n') == old.endswith(b'\n'), path
    assert (b'\r\n' in actual) == (b'\r\n' in old), path
    assert b'\r' not in actual.replace(b'\r\n', b''), path
    original = {owned_select(old, block): block for block in boundary_blocks(old) if owned_select(old, block)}
    current = {owned_select(actual, block): block for block in boundary_blocks(actual) if owned_select(actual, block)}
    assert len(original) == len(current) == 2 and original.keys() == current.keys(), path
    restored = actual
    for name, block in sorted(current.items(), key=lambda item: item[1]['start'], reverse=True):
        previous = original[name]
        restored = restored[:block['start']] + old[previous['start']:previous['end']] + restored[block['end']:]
    assert restored == old, ('Unrelated package10 gameplay bytes changed', path)
    return restored


def check_owned_existing():
    for path in EXISTING:
        package10_original_bytes(path, (ROOT / path).read_bytes())


def historical_actions(actions):
    """Check full native uniqueness, then retain the original historical ID proof."""
    assert len(actions) == len(set(actions)), 'Duplicate native action ID'
    return [action for action in actions if action not in NEW_ACTIONS]


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


def main():
    groups, receipts, sources, helpers, kinds = Counter(), [], {}, {}, {}
    for path in sorted(NEW):
        assert (ROOT / path).is_file(), ('Missing required CT lifecycle source', path)
        data = (ROOT / path).read_bytes()
        assert b'\r' not in data and data.endswith(b'\n'), ('New LF/EOF convention', path)
        assert data.startswith(b'\xef\xbb\xbf') == path.endswith('.yml'), ('New BOM convention', path)
        assert '\ufffd' not in data.decode('utf-8-sig'), path
        if path.endswith('.txt'):
            boundary_blocks(data); sources[path] = ast(data)
        if '/scripted_effects/' in path or '/scripted_triggers/' in path:
            for key, operator, value in sources[path]:
                assert key.startswith('eon_ct_') and key not in helpers, ('Unowned/duplicate helper', key)
                helpers[key] = value
                kinds[key] = 'effects' if '/scripted_effects/' in path else 'triggers'
        receipts.append({'path': path, 'sha256': hashlib.sha256(data).hexdigest()})
        groups['new_source_encoding_braces_and_exact_namespace'] += 1
    check_owned_existing()
    for path in sorted(EXISTING):
        data = (ROOT / path).read_bytes()
        assert package10_original_bytes(path, data) == subprocess.check_output(['git', 'show', BASELINE + ':' + path], cwd=ROOT)
        receipts.append({'path': path, 'sha256': hashlib.sha256(data).hexdigest(), 'all_unowned_bytes_exact': True})
        groups['two_existing_native_or_annex_blocks_only_and_all_unowned_bytes_exact'] += 1
    trees = ('common', 'history', 'events', 'interface', 'gfx', 'localisation', 'music', 'map', 'sound',
             'portraits', 'tutorial', 'descriptions', 'scenario_tests', 'descriptor.mod', 'era_of_nations.mod', 'thumbnail.png')
    baseline_paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, '--', *trees], cwd=ROOT).decode().splitlines()
    changed = subprocess.check_output(['git', 'diff', '--name-only', BASELINE, '--', *trees], cwd=ROOT).decode().splitlines()
    changed = [path for path in changed if path not in LATER_PACKAGE11_EXISTING | LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | package14_historical_existing(BASELINE) | package15_historical_existing(BASELINE) | package16_historical_existing(BASELINE) | LATER_PACKAGE16_NEW | package17_historical_existing(BASELINE) | LATER_PACKAGE17_NEW | package18_historical_existing(BASELINE) | LATER_PACKAGE18_NEW | package19_historical_existing(BASELINE) | LATER_PACKAGE19_NEW | package20_historical_existing(BASELINE) | LATER_PACKAGE20_NEW]
    untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', *trees], cwd=ROOT).decode().splitlines()
    untracked = [path for path in untracked if path not in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | LATER_PACKAGE20_NEW]
    assert set(changed) | set(untracked) == EXISTING | NEW | LATER_PACKAGE11_NEW | LATER_PACKAGE12_NEW | LATER_PACKAGE13_NEW, ('Unowned gameplay changes', changed, untracked)
    assert set(changed).intersection(baseline_paths) == EXISTING
    assert not NEW.intersection(baseline_paths) and set(untracked) <= NEW | LATER_PACKAGE11_NEW | LATER_PACKAGE12_NEW | LATER_PACKAGE13_NEW
    assert len(baseline_paths) == 68294
    groups['all_68292_unrelated_existing_gameplay_files_byte_preserved_and_exact_six_additions'] += 1
    old_ids = {block['key'] for path in baseline_paths if path.startswith('common/scripted_diplomatic_actions/') and path.endswith('.txt')
               for block in boundary_blocks(subprocess.check_output(['git', 'show', BASELINE + ':' + path], cwd=ROOT))
               if block['parent'] == 'scripted_diplomatic_actions' and block['depth'] == 1}
    actual_ids = [block['key'] for path in (ROOT / 'common/scripted_diplomatic_actions').glob('*.txt')
                  for block in boundary_blocks(path.read_bytes()) if block['parent'] == 'scripted_diplomatic_actions' and block['depth'] == 1]
    actual_ids = package16_historical_actions(actual_ids)
    assert len(old_ids) == 64 and len(actual_ids) == len(set(actual_ids)) == 65
    assert set(actual_ids) == old_ids | NEW_ACTIONS
    groups['all_64_old_native_action_IDs_preserved_and_one_explicit_unique_addition'] += 1
    native_path = 'common/scripted_diplomatic_actions/MDC_terrorism.txt'
    old_native = subprocess.check_output(['git', 'show', BASELINE + ':' + native_path], cwd=ROOT)
    current_native = (ROOT / native_path).read_bytes()
    old_actions, actions = one(ast(old_native), 'scripted_diplomatic_actions'), one(ast(current_native), 'scripted_diplomatic_actions')
    for key in ('declare_anti_terror_agreement', 'cancel_anti_terror_agreement'):
        old, actual = one(old_actions, key), one(actions, key)
        for field in ('cost', 'allowed', 'requires_acceptance', 'show_acceptance_on_action_button', 'icon', 'send_description'):
            assert one(actual, field) == one(old, field), ('Existing native contract changed', key, field)
            groups['original_native_price_consent_icon_allowed_and_send_description_preserved'] += 1
        for field in ('ai_acceptance', 'ai_desire'):
            old_block = [block for block in boundary_blocks(old_native) if block['key'] == field and block['parent'] == key]
            actual_block = [block for block in boundary_blocks(current_native) if block['key'] == field and block['parent'] == key]
            assert len(old_block) == len(actual_block)
            if old_block:
                assert len(old_block) == 1
                before, after = old_block[0], actual_block[0]
                assert old_native[before['start']:before['end']] == current_native[after['start']:after['end']], ('Original political AI bytes changed', key, field)
                groups['original_AI_acceptance_and_desire_exact_bytes'] += 1
    declare, cancel = one(actions, 'declare_anti_terror_agreement'), one(actions, 'cancel_anti_terror_agreement')
    assert one(declare, 'cost') == one(cancel, 'cost') == '75'
    for field, helper in (('can_be_sent', 'eon_ct_send_ready'), ('can_be_accepted', 'eon_ct_response_valid'),
                          ('on_sent_effect', 'eon_ct_reserve_request'), ('complete_effect', 'eon_ct_complete_request'), ('reject_effect', 'eon_ct_reject_request')):
        assert one(declare, field) == ast(helper + ' = yes')
        groups['native_send_accept_complete_reject_entrypoints_call_fresh_owned_helpers'] += 1
    assert one(cancel, 'complete_effect') == ast('eon_ct_end_pair = yes')
    assert one(cancel, 'can_be_sent') == ast('eon_ct_end_ready = yes ROOT = { NOT = { has_political_power < 75 } }')
    groups['native_cancellation_same_75_PP_and_fresh_cleanup_helper'] += 1
    withdrawal_actions = one(sources['common/scripted_diplomatic_actions/eon_ct_actions.txt'], 'scripted_diplomatic_actions')
    assert {key for key, operator, value in withdrawal_actions} == NEW_ACTIONS
    withdrawal = one(withdrawal_actions, 'eon_withdraw_antiterror_proposal')
    assert one(withdrawal, 'allowed') == ast('ROOT = { is_ai = no }')
    assert one(withdrawal, 'cost') == '0' and one(withdrawal, 'requires_acceptance') == 'no'
    for field in ('visible', 'selectable', 'can_be_sent'): assert one(withdrawal, field) == ast('eon_ct_withdraw_ready = yes')
    assert one(withdrawal, 'complete_effect') == ast('if = { limit = { eon_ct_withdraw_ready = yes } eon_ct_withdraw_request = yes custom_effect_tooltip = eon_ct_withdraw_tt }')
    assert one(withdrawal, 'ai_desire') == ast('factor = 0')
    groups['one_free_human_sender_withdrawal_with_fresh_click_guard'] += 1
    locale, locale_counts = {}, {}
    expected_locale = NEW_ACTIONS | {'eon_withdraw_antiterror_proposal_desc', 'eon_withdraw_antiterror_proposal_send_desc', 'eon_ct_withdraw_tt', 'eon_ct_send_tt', 'eon_ct_end_tt'}
    for language in ('english', 'russian'):
        lines = (ROOT / f'localisation/{language}/eon_ct_l_{language}.yml').read_text(encoding='utf-8-sig').splitlines()
        assert lines[0] == 'l_' + language + ':'
        pairs = [re.fullmatch(r' ([\w.]+):0 "(.*)"', line).groups() for line in lines[1:]]
        assert len(pairs) == len(dict(pairs))
        locale[language] = dict(pairs)
        assert set(locale[language]) == expected_locale
        locale_counts[language] = Counter()
        for path in (ROOT / 'localisation' / language).glob('*.yml'):
            locale_counts[language].update(re.findall(r'^ ([\w.]+):', path.read_text(encoding='utf-8-sig'), re.M))
    for key in expected_locale:
        assert all(locale_counts[language][key] == 1 for language in ('english', 'russian')), ('Missing/duplicate locale', key)
        assert re.findall(r'\[.*?\]', locale['english'][key]) == re.findall(r'\[.*?\]', locale['russian'][key])
        groups['bilingual_locale_keys_unique_and_placeholders_matching'] += 1
    definitions = Counter()
    for folder in ('scripted_effects', 'scripted_triggers'):
        for path in (ROOT / 'common' / folder).glob('*.txt'):
            definitions.update(key for key, operator, value in ast(path.read_bytes()) if key in helpers)
    for key in helpers:
        assert definitions[key] == 1, ('Duplicate helper ID', key)
        groups['unique_global_owned_helper_IDs'] += 1
    checked_sources = list(sources.values()) + [declare, cancel]
    for nodes in checked_sources:
        for key, operator, value in rows(nodes):
            if key == 'NOT':
                assert isinstance(value, list) and len(value) == 1, ('Native NOT is NOR; use one explicit child', value)
                groups['all_owned_negations_have_one_explicit_child_or_group'] += 1
            if key.startswith('eon_ct_') and value == 'yes': assert key in helpers, ('Missing helper reference', key)
            if key in {'tooltip', 'custom_effect_tooltip'} and str(value).startswith('eon_ct_'): assert value in expected_locale, value
            if key in ('target', 'tag') and isinstance(value, str) and value.startswith('eon_ct_'): assert value.startswith('var:'), value
            if key in ('has_country_flag', 'set_country_flag', 'clr_country_flag'):
                flag = one(value, 'flag') if isinstance(value, list) else value
                if '@' in flag and flag.startswith(('eon_ct_', 'anti_terror_agreement')):
                    assert flag.rsplit('@', 1)[1] in ('ROOT', 'PREV'), ('Unsupported new pair suffix', flag)
    groups['owned_helpers_localisation_and_primary_backed_ROOT_PREV_pair_flags_resolve'] += 1
    wrappers = {'if', 'else_if', 'else', 'ROOT', 'THIS', 'PREV', 'FROM', 'every_country', 'for_each_loop'}
    mutators = {'set_variable', 'clear_variable', 'set_temp_variable', 'add_to_variable', 'set_country_flag', 'clr_country_flag',
                'add_opinion_modifier', 'reverse_add_opinion_modifier', 'remove_opinion_modifier', 'add_dynamic_modifier'}
    def effects_only(helper, nodes):
        for key, operator, value in nodes:
            if key in {'limit', 'array', 'value', 'index', 'break'}: continue
            if key in wrappers or key.startswith('var:'):
                effects_only(helper, value); continue
            assert key in mutators or (key in helpers and kinds[key] == 'effects'), ('Unowned effect or trigger used as effect', helper, key)
            if key == 'add_to_variable':
                assert helper in ('eon_ct_apply_contribution', 'eon_ct_remove_own_contribution')
                assert all(name in {'ct_effectiveness_add', 'ct_command_debuff', 'costil_command_buff'} for name, op, amount in value)
            if key == 'set_variable': assert all(name in {'eon_ct_partner', 'pending_antiterror_country'} for name, op, amount in value)
            if key == 'clear_variable': assert value in {'eon_ct_partner', 'pending_antiterror_country'}
            if key in ('set_country_flag', 'clr_country_flag'):
                flag = one(value, 'flag') if isinstance(value, list) else value
                assert flag.startswith(('eon_ct_', 'anti_terror_agreement')), ('Unowned flag write', helper, flag)
            if key in ('add_opinion_modifier', 'reverse_add_opinion_modifier', 'remove_opinion_modifier'):
                assert one(value, 'modifier') in {'counter_terror_cooperation_opinion', 'counter_terror_cooperation_reject'}
            if key == 'add_dynamic_modifier':
                assert helper == 'eon_ct_apply_contribution' and one(value, 'modifier') in {'costilb_modifier', 'ct_effectiveness'}
    for helper, body in helpers.items():
        if kinds[helper] == 'effects':
            effects_only(helper, body)
            groups['effects_own_only_pair_state_known_CT_components_no_money_PP_current_CP_or_war'] += 1
    assert helpers['eon_ct_hard_pair_valid'] == ast('exists = yes NOT = { tag = ROOT } ROOT = { exists = yes } NOT = { has_war_with = ROOT } has_opinion = { target = ROOT value > 9 } if = { limit = { is_in_faction = yes any_allied_country = { exists = yes } } NOT = { any_allied_country = { has_war_with = ROOT } } }')
    assert helpers['eon_ct_send_ready'] == ast('eon_ct_proposal_ready = yes ROOT = { NOT = { has_political_power < 75 } }')
    groups['original_hard_war_opinion_allied_war_policy_and_exact_75_affordability'] += 1
    ready = helpers['eon_ct_proposal_ready']
    assert one(ready, 'eon_ct_hard_pair_valid') == 'yes'
    sender = one(ready, 'ROOT')
    for body in (ready, sender):
        assert ('check_variable', '=', ast('pending_antiterror_country = 0')) in body
        for flag in ('eon_ct_outgoing', 'eon_ct_incoming'):
            assert ('NOT', '=', ast('has_country_flag = ' + flag)) in body
    assert 'jihadist_government' not in str([body for helper, body in helpers.items() if kinds[helper] == 'triggers'])
    groups['bilateral_pending_locks_legacy_unknown_pointer_preserved_and_no_new_human_AI_policy_ban'] += 1
    reserve = one(helpers['eon_ct_reserve_request'], 'if')
    assert one(reserve, 'limit') == ast('eon_ct_proposal_ready = yes')
    assert 'has_political_power' not in str(reserve), 'Native PP already paid at on_sent'
    assert reserve[1:3] == ast('eon_ct_clear_record = yes ROOT = { eon_ct_clear_record = yes }'), 'Fresh unreserved records must clear orphan cancellation before identity write'
    assert ('set_country_flag', '=', ast('flag = eon_ct_pending_window days = 30 value = 1')) in reserve
    sender_reservation = [value for key, operator, value in reserve if key == 'ROOT' and value != ast('eon_ct_clear_record = yes')]
    assert len(sender_reservation) == 1
    assert ('set_country_flag', '=', ast('flag = eon_ct_pending_window days = 30 value = 1')) in sender_reservation[0]
    groups['native_already_paid_send_reserves_both_original_30_day_records_without_PP_recharge'] += 1
    assert helpers['eon_ct_withdraw_ready'] == ast('ROOT = { is_ai = no has_country_flag = eon_ct_outgoing eon_ct_pending_pair_current = yes check_variable = { eon_ct_partner = PREV } NOT = { has_country_flag = eon_ct_cancelled } }')
    assert helpers['eon_ct_withdraw_request'] == ast('if = { limit = { eon_ct_withdraw_ready = yes } set_country_flag = eon_ct_cancelled ROOT = { set_country_flag = eon_ct_cancelled } }')
    groups['only_original_outgoing_human_can_cancel_and_both_locks_remain'] += 1
    assert one(one(helpers['eon_ct_clear_record'], 'if'), 'limit') == ast('has_country_flag = eon_ct_outgoing check_variable = { pending_antiterror_country = eon_ct_partner }')
    assert one(one(helpers['eon_ct_clear_record'], 'if'), 'clear_variable') == 'pending_antiterror_country'
    groups['compatibility_pointer_cleared_only_for_matching_original_outgoing_record'] += 1
    apply = one(helpers['eon_ct_apply_contribution'], 'if')
    remove = one(helpers['eon_ct_remove_own_contribution'], 'if')
    assert one(apply, 'limit') == ast('NOT = { has_country_flag = eon_ct_contribution@PREV }')
    assert one(remove, 'limit') == ast('OR = { has_country_flag = anti_terror_agreement@PREV has_country_flag = eon_ct_contribution@PREV }')
    for body, amounts in ((apply, ('0.05', '-5', '5')), (remove, ('-0.05', '5', '-5'))):
        changes = [value for key, operator, value in body if key == 'add_to_variable']
        assert changes == [ast(name + ' = ' + amount) for name, amount in zip(('ct_effectiveness_add', 'ct_command_debuff', 'costil_command_buff'), amounts)]
        groups['pair_component_granted_once_and_removed_once_with_original_three_deltas'] += 1
    assert one(one(helpers['eon_ct_complete_request'], 'if'), 'limit') == ast('eon_ct_response_current = yes')
    accepted = one(one(helpers['eon_ct_complete_request'], 'if'), 'if')
    assert accepted == ast('limit = { eon_ct_response_valid = yes } ROOT = { eon_ct_apply_contribution = yes } ROOT = { PREV = { eon_ct_apply_contribution = yes } }')
    groups['both_participants_contribute_only_after_fresh_original_native_consent'] += 1
    force = helpers['eon_ct_force_cleanup']
    assert force[-1] == ('eon_ct_release_record', '=', 'yes')
    assert one(one(force, 'if'), 'limit') == ast('eon_ct_record_owned = yes')
    assert one(one(force, 'if'), 'var:eon_ct_partner') == ast('set_country_flag = eon_ct_retired_pair@PREV PREV = { set_country_flag = eon_ct_retired_pair@PREV }')
    assert 'retired_pair' not in str(helpers['eon_ct_release_record'])
    groups['forced_unanswered_known_pair_retired_both_directions_before_clear_normal_release_keeps_reuse'] += 1
    hooks = one(sources['common/on_actions/eon_ct_on_actions.txt'], 'on_actions')
    assert one(hooks, 'on_daily') == ast('effect = { eon_ct_daily_cleanup = yes }')
    for action, target in (('on_annex', 'FROM'), ('on_subject_annexed', 'ROOT')):
        assert one(hooks, action) == ast('effect = { every_country = { limit = { exists = yes NOT = { tag = ' + target + ' } } set_temp_variable = { eon_ct_annexed_partner = ' + target + ' } eon_ct_cleanup_annexed_pair = yes } ' + target + ' = { eon_ct_cleanup_annexed_owner = yes } }')
        groups['native_annex_actor_scopes_handle_present_survivors_and_annexed_owner'] += 1
    annex = (ROOT / 'common/on_actions/00_terrorist_on_actions.txt').read_bytes()
    branches = [block for block in boundary_blocks(annex) if owned_select(annex, block)]
    for branch in branches:
        assert ast(annex[branch['start']:branch['end']]) == ast('if = { limit = { has_country_flag = anti_terror_agreement@v } set_temp_variable = { eon_ct_cleanup_partner = v } eon_ct_cleanup_active_pair = yes }')
        groups['old_active_annex_branches_cleanup_components_before_old_flags_are_lost'] += 1
    raid_path = 'common/decisions/MDDC_Terrorist_again.txt'
    raid_data = package11_original_bytes(raid_path, (ROOT / raid_path).read_bytes())
    assert raid_data == subprocess.check_output(['git', 'show', BASELINE + ':' + raid_path], cwd=ROOT)
    raid_count = sum('anti_terror_agreement' in str(body) for category, operator, decisions in ast(raid_data)
                     for key, operator, body in decisions if isinstance(body, list))
    assert raid_count == 31
    for path in ('common/scripted_effects/00_terrorism_scripted_effects.txt', 'common/dynamic_modifiers/terrorist_dynamic_modifiers.txt',
                 'common/dynamic_modifiers/costilb_modifier.txt', 'common/on_actions/00_costili.txt', 'common/factions/goals/faction_goals_short_term.txt',
                 'common/map_modes/terrorism_map_mode.txt', 'events/00_Terrorism_events.txt', 'common/scripted_triggers/99_GCC_scripted_triggers.txt'):
        assert (ROOT / path).read_bytes() == subprocess.check_output(['git', 'show', BASELINE + ':' + path], cwd=ROOT)
        groups['raid_national_tags_probabilities_AI_compensation_attache_and_downstream_sources_byte_preserved'] += 1
    native = {'checked': False}
    docs = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation')
    if docs.exists():
        effects, triggers = ((docs / (kind + '_documentation.md')).read_text(encoding='utf-8-sig') for kind in ('effects', 'triggers'))
        for key in mutators | {'for_each_loop'}:
            assert '\n## ' + key + '\n' in effects, ('Unsupported native effect', key)
            groups['installed_primary_effect_API'] += 1
        for key in ('check_variable', 'has_country_flag', 'if', 'has_political_power', 'has_opinion', 'exists', 'set_temp_variable'):
            assert '\n## ' + key + '\n' in triggers, ('Unsupported native trigger', key)
            groups['installed_primary_trigger_API'] += 1
        action_docs = (docs.parent / 'common/scripted_diplomatic_actions/scripted_diplomatic_actions.txt').read_text(encoding='utf-8-sig')
        for text in ('root is the initiator', 'this is the target country', 'cost = 10', 'on_sent_effect', 'can_be_accepted', 'complete_effect', 'reject_effect'):
            assert text in action_docs
            groups['installed_primary_native_action_scope_cost_and_callback_fields'] += 1
        arrays = (docs.parent / 'common/scripted_effects/CHI_scripted_effects.txt').read_text(encoding='utf-8-sig')
        assert 'array = global.countries' in arrays
        flag_sample = (docs.parent / 'common/decisions/NOR.txt').read_text(encoding='utf-8-sig')
        assert 'set_country_flag = NOR_already_asked_a_fascist@PREV' in flag_sample
        groups['installed_primary_country_array_and_PREV_pair_flag_examples'] += 2
        native = {'checked': True, 'path': str(docs), 'not_proven': 'native callbacks, cost timing, AI choices or runtime scope binding'}
    print(json.dumps({'all_passed': True, 'total_cases': sum(groups.values()), 'groups': groups, 'baseline': BASELINE,
                      'new_files': [item for item in receipts if item['path'] in NEW], 'owned_existing_files': [item for item in receipts if item['path'] in EXISTING],
                      'final_gameplay_sha256': {item['path']: item['sha256'] for item in receipts},
                      'existing_gameplay_files_byte_preserved': len(baseline_paths) - len(EXISTING), 'unique_native_action_IDs': len(actual_ids),
                      'new_helper_IDs': len(helpers), 'new_locale_keys_per_language': len(expected_locale), 'unchanged_raid_decisions': raid_count, 'later_package11_raid_boundary_checked_before_historical_byte_view': True,
                      'native_primary_documentation': native,
                      'not_proven': 'HOI4 compilation, native callback/cost timing, GUI/AI/save-load/campaign; unidentified legacy bonuses without flags and paid delayed raid cancellation are not repaired; arbitrary duplicate consumed popups not covered'}, indent=2))


if __name__ == '__main__':
    main()
