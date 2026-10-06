"""Exact package06 source preservation and references; not HOI4 compilation."""
from collections import Counter
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

# Package09 independently owns exactly these eight additions and one pre-clear hook.
LATER_PACKAGE09_NEW = {
    'common/scripted_effects/eon_mediation_terms_effects.txt',
    'common/scripted_triggers/eon_mediation_terms_triggers.txt',
    'common/decisions/eon_mediation_terms_decisions.txt',
    'common/decisions/categories/eon_mediation_terms_categories.txt',
    'common/on_actions/eon_mediation_terms_on_actions.txt',
    'events/eon_mediation_terms_events.txt',
    'localisation/english/eon_mediation_terms_l_english.yml',
    'localisation/russian/eon_mediation_terms_l_russian.yml',
}

ROOT = Path(__file__).resolve().parents[3]

# Package10 restores only its two treaty/two annex ranges before old byte assertions.
import sys as package10_sys
package10_sys.path.insert(0, str(ROOT / 'tools/validation'))
from diplomacy_package_10.test_source import (
    NEW as LATER_PACKAGE10_NEW, EXISTING as LATER_PACKAGE10_EXISTING,
    check_owned_existing, package10_original_bytes, historical_actions,
)
check_owned_existing()

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
from diplomacy_package_21.test_source import (
    NEW as LATER_PACKAGE21_NEW, package21_original_bytes, package21_historical_existing,
    package21_original_validator_bytes, historical_actions as package21_historical_actions,
    check_owned_existing as check_later_package21_owned,
)
check_later_package21_owned()
from diplomacy_package_22.test_source import (
    NEW as LATER_PACKAGE22_NEW, package22_original_bytes, package22_historical_existing,
    package22_original_validator_bytes, historical_actions as package22_historical_actions,
    check_owned_existing as check_later_package22_owned,
)
check_later_package22_owned()
BASELINE = '551d7100f6c35cd062a36520f6a7eed199b13a2e'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'diplomacy_package_03'))
from _support import ast, blocks, format_preserved, one

groups = Counter()
receipts = []
EXISTING = {
    'common/scripted_diplomatic_actions/00_scripted_diplomatic_actions.txt',
    'common/scripted_guis/influence_scripted_gui.txt',
    'events/00_Influence_events.txt',
    'localisation/english/MDC_scripted_diplomatic_actions_l_english.yml',
    'localisation/russian/MDDC_scripted_diplomatic_actions_l_russian.yml',
}
NEW = {
    'common/scripted_effects/eon_aid_effects.txt',
    'common/scripted_effects/eon_support_effects.txt',
    'common/scripted_triggers/eon_aid_triggers.txt',
    'common/scripted_triggers/eon_debt_support_triggers.txt',
    'common/on_actions/eon_support_on_actions.txt',
    'common/scripted_diplomatic_actions/eon_support_actions.txt',
    'events/eon_support_events.txt',
    'localisation/english/eon_support_l_english.yml',
    'localisation/russian/eon_support_l_russian.yml',
}
assert len(EXISTING) == 5 and len(NEW) == 9
# Package 07 independently proves these seven additions and all previous game bytes.
LATER_PACKAGE07_NEW = {
    'common/scripted_effects/eon_consultation_effects.txt',
    'common/scripted_triggers/eon_consultation_triggers.txt',
    'common/scripted_diplomatic_actions/eon_consultation_actions.txt',
    'common/on_actions/eon_consultation_on_actions.txt',
    'events/eon_consultation_events.txt',
    'localisation/english/eon_consultation_l_english.yml',
    'localisation/russian/eon_consultation_l_russian.yml',
}
LATER_PACKAGE07_ACTIONS = {
    'eon_open_economic_consultations', 'eon_withdraw_consultation_request',
    'eon_end_economic_consultations', 'eon_consultation_offer_economic_aid',
}

# Package 08 independently protects the exact nine-file addition and old game bytes.
LATER_PACKAGE08_NEW = {
    'common/scripted_effects/eon_mediation_effects.txt',
    'common/scripted_triggers/eon_mediation_triggers.txt',
    'common/scripted_diplomatic_actions/eon_mediation_actions.txt',
    'common/decisions/eon_mediation_decisions.txt',
    'common/decisions/categories/eon_mediation_categories.txt',
    'common/on_actions/eon_mediation_on_actions.txt',
    'events/eon_mediation_events.txt',
    'localisation/english/eon_mediation_l_english.yml',
    'localisation/russian/eon_mediation_l_russian.yml',
}
LATER_PACKAGE08_ACTIONS = {'eon_request_war_mediation', 'eon_withdraw_mediation'}

@lru_cache(maxsize=None)
def before(path):
    return subprocess.check_output(['git', 'show', BASELINE + ':' + path], cwd=ROOT)

def read(path): return package14_original_bytes(path, package17_original_bytes(path, (ROOT / path).read_bytes()))
def parsed(path): return ast(read(path))
def restore(after, old, selector):
    previous = {selector(old, b): b for b in blocks(old) if selector(old, b)}
    current = {selector(after, b): b for b in blocks(after) if selector(after, b)}
    assert previous.keys() == current.keys(), ('Owned block identities changed', previous.keys(), current.keys())
    for key, block in sorted(current.items(), key=lambda item: item[1]['start'], reverse=True):
        prior = previous[key]
        after = after[:block['start']] + old[prior['start']:prior['end']] + after[block['end']:]
    return after

def record(path, old, current):
    format_preserved(old, current)
    assert '\ufffd' not in current.decode('utf-8-sig'), path
    receipts.append({'path': path, 'sha256': hashlib.sha256(current).hexdigest(), 'unrelated_bytes_exact': True})
    groups['exact_existing_file_boundaries'] += 1

def debt_selector(data, b):
    return b['key'] if b['key'] == 'diplo_action_assume_debt' and b['parent'] == 'scripted_diplomatic_actions' and b['depth'] == 1 else None
path = 'common/scripted_diplomatic_actions/00_scripted_diplomatic_actions.txt'
old, current = before(path), read(path)
assert restore(current, old, debt_selector) == old, 'Unrelated native action bytes changed'
record(path, old, current)
old_debt = one(one(ast(old), 'scripted_diplomatic_actions'), 'diplo_action_assume_debt')
debt = one(one(ast(current), 'scripted_diplomatic_actions'), 'diplo_action_assume_debt')

path = 'common/scripted_guis/influence_scripted_gui.txt'
old, current = before(path), read(path)
def gui_selector(data, b):
    if b['depth'] != 3 or (b['key'], b['parent']) not in {
            ('opt_aid_button_click', 'effects'), ('opt_aid_button_click_enabled', 'triggers')}:
        return None
    gui = next(p for p in blocks(data) if p['key'] == 'scripted_influence_option_buttons' and p['depth'] == 1)
    return b['key'] if gui['start'] < b['start'] < gui['end'] else None
assert restore(current, old, gui_selector) == old, 'Unrelated influence GUI/AI bytes changed'
record(path, old, current)
old_gui = one(one(ast(old), 'scripted_gui'), 'scripted_influence_option_buttons')
gui = one(one(ast(current), 'scripted_gui'), 'scripted_influence_option_buttons')
old_enabled = one(one(old_gui, 'triggers'), 'opt_aid_button_click_enabled')
assert one(one(gui, 'effects'), 'opt_aid_button_click') == ast('eon_aid_prepare_draft = yes')
assert one(one(gui, 'triggers'), 'opt_aid_button_click_enabled') == old_enabled + ast('custom_trigger_tooltip = { tooltip = eon_aid_prepare_ready_tt eon_aid_gui_ready = yes }')
groups['GUI_effect_and_enabled_guard_delegate'] += 1

path = 'events/00_Influence_events.txt'
old, current = before(path), read(path)
AID_EVENTS = {'influence.0', 'influence.1', 'News_influence.0'}
def event_selector(data, b):
    if b['key'] != 'country_event' or b['depth'] != 0: return None
    ident = one(ast(data[b['start']:b['end']])[0][2], 'id')
    return ident if ident in AID_EVENTS else None
assert restore(current, old, event_selector) == old, 'Unrelated national/military influence events changed'
record(path, old, current)
old_events = {one(v, 'id'): v for k, op, v in ast(old) if k == 'country_event'}
aid_events = {one(v, 'id'): v for k, op, v in ast(current) if k == 'country_event'}
assert old_events.keys() == aid_events.keys(), 'Existing event IDs changed'
for ident in ('influence.1', 'News_influence.0'):
    old_names = [one(v, 'name') for k, op, v in old_events[ident] if k == 'option']
    new_names = [one(v, 'name') for k, op, v in aid_events[ident] if k == 'option']
    assert new_names == old_names, ('Existing aid response IDs changed', ident)
    groups['existing_aid_event_and_option_IDs'] += 1

for lang, stem in (('english', 'MDC'), ('russian', 'MDDC')):
    path = f'localisation/{lang}/{stem}_scripted_diplomatic_actions_l_{lang}.yml'
    old, current = before(path), read(path)
    pattern = rb'(?m)^ DIPLO_ACTION_ASSUME_DEBT_ACTION_DESC:(?:\d+)? "[^\r\n]*"'
    previous, present = re.findall(pattern, old), re.findall(pattern, current)
    assert len(previous) == len(present) == 1, path
    prefix = previous[0].split(b'"', 1)[0]
    assert present[0] == prefix + b'"$eon_debt_support_action_desc$"', ('Unexpected debt ACTION_DESC alias', path)
    assert current.replace(present[0], previous[0]) == old, 'Unrelated old diplomacy locale bytes changed'
    record(path, old, current)

# No native cost, settlement, rejection or recipient political policy changes.
for key in ('allowed', 'can_be_accepted', 'cost', 'requires_acceptance', 'show_acceptance_on_action_button', 'icon',
            'complete_effect', 'reject_effect', 'accept_title', 'reject_title', 'ai_acceptance'):
    assert one(debt, key) == one(old_debt, key), ('Existing debt behavior changed', key)
    groups['debt_financial_consent_and_acceptance_policy_exact'] += 1
assert one(debt, 'selectable') == ast('eon_debt_offer_existing_policy = yes eon_debt_offer_pair_available = yes')
policy = one(parsed('common/scripted_triggers/eon_debt_support_triggers.txt'), 'eon_debt_offer_existing_policy')
assert policy == one(old_debt, 'selectable'), 'Original debt national policy was rewritten'
extra = ast('eon_debt_offer_existing_policy = yes eon_debt_offer_pair_available = yes NOT = { has_war_with = ROOT }')
assert one(debt, 'can_be_sent') == extra + one(old_debt, 'can_be_sent')
sent = deepcopy(one(debt, 'on_sent_effect'))
sent_if = one(sent, 'if')
assert one(sent_if, 'limit') == extra + one(one(old_debt, 'on_sent_effect'), 'if')[0][2]
for index, row in enumerate(sent_if):
    if row[0] == 'limit': sent_if[index] = (row[0], row[1], row[2][len(extra):])
assert sent == one(old_debt, 'on_sent_effect'), 'Debt snapshot/cooling flag effects changed'
groups['debt_exact_policy_and_fresh_send_guards'] += 1

old_desire, desire = one(old_debt, 'ai_desire'), one(debt, 'ai_desire')
assert desire[:-2] == old_desire[:-2], 'Other debt AI desire politics changed'
assert desire[-2] == ast('modifier = { factor = 0 set_temp_variable = { tmp = debt } multiply_temp_variable = { tmp = 0.25 } check_variable = { var = ROOT.treasury value = tmp compare = less_than } }')[0]
expected_last = deepcopy(old_desire[-1])
conditions = one(expected_last[2], 'OR')
assert conditions[0] == ast('ROOT = { NOT = { has_country_flag = AI_recently_sent_debt_assumption_offer_@PREV } }')[0]
conditions[0] = ast('ROOT = { has_country_flag = AI_recently_sent_debt_assumption_offer_@PREV }')[0]
assert desire[-1] == expected_last, 'Additional debt cooling-period policy changes'
for key, value in (('send_description', 'eon_debt_support_send_desc'), ('accept_description', 'eon_debt_support_accept_desc'),
                   ('reject_description', 'eon_debt_support_reject_desc')):
    assert one(debt, key) == value
    groups['debt_description_references'] += 1
groups['two_narrow_debt_AI_corrections'] += 2

# Expanded policy binds the original seven influence slots, GDP multiplier,
# factory threshold and ERI donor restriction to the frozen donor country.
influence_native_path = 'common/scripted_triggers/00_influence_scripted_triggers.txt'
eri_native_path = 'common/scripted_triggers/99_ERI_scripted_triggers.txt'
for path in (influence_native_path, eri_native_path):
    assert read(path) == before(path), 'Inherited native policy helper bytes changed'
    groups['unchanged_native_aid_policy_helpers'] += 1
native_influencer = one(ast(before(influence_native_path)), 'is_influencer')
slots = one(one(native_influencer, 'custom_trigger_tooltip'), 'OR')
assert slots == ast(' '.join(f'check_variable = {{ influence_array^{i} = ROOT }}' for i in range(7)))
assert old_enabled == ast('''is_influencer = yes
custom_trigger_tooltip = { set_temp_variable = { gdp_total_temp = ROOT.gdp_total } multiply_temp_variable = { gdp_total_temp = 2 }
check_variable = { gdp_total_temp > THIS.gdp_total } tooltip = gdp_total_cannot_be_double_ours }
custom_trigger_tooltip = { tooltip = more_civs_than_other check_variable = { num_of_civilian_factories < ROOT.num_of_civilian_factories } }
custom_trigger_tooltip = { tooltip = influence_aid_button_TT ROOT = { NOT = { has_country_flag = recently_sent_aid@PREV } } }
ERI_is_not_transitional_government = yes''')
aid_policy = one(parsed('common/scripted_triggers/eon_aid_triggers.txt'), 'eon_aid_national_policy_allowed')
expected_aid_policy = ast('''exists = yes NOT = { tag = eon_aid_policy_donor } NOT = { has_war_with = eon_aid_policy_donor }
OR = { ''' + ' '.join(f'check_variable = {{ influence_array^{i} = eon_aid_policy_donor }}' for i in range(7)) + ''' }
var:eon_aid_policy_donor = { exists = yes NOT = { has_war_with = PREV } set_temp_variable = { eon_aid_policy_gdp_limit = gdp_total }
multiply_temp_variable = { eon_aid_policy_gdp_limit = 2 }
set_temp_variable = { eon_aid_policy_donor_civs = num_of_civilian_factories }
if = { limit = { original_tag = ERI has_country_flag = ETH_transitional_government_FLAG }
NOT = { has_country_leader = { name = "Eritrean Transitional Government" } } } }
check_variable = { eon_aid_policy_gdp_limit > gdp_total }
check_variable = { num_of_civilian_factories < eon_aid_policy_donor_civs }''')
assert aid_policy == expected_aid_policy, 'Expanded aid national policy or donor scope changed'
native_eri_if = one(one(ast(before(eri_native_path)), 'ERI_is_not_transitional_government'), 'if')
expanded_eri_if = one(one(aid_policy, 'var:eon_aid_policy_donor'), 'if')
assert one(expanded_eri_if, 'limit') == one(one(native_eri_if, 'limit'), 'ROOT')
assert [row for row in expanded_eri_if if row[0] != 'limit'] == one(native_eri_if, 'ROOT')
groups['seven_influence_slots_frozen_donor_GDP_civs_ERI_scope'] += 1

helpers, helper_kinds = {}, {}
for path in sorted(NEW):
    data = read(path)
    assert b'\r' not in data and data.endswith(b'\n'), ('New source must use LF with final newline', path)
    assert data.startswith(b'\xef\xbb\xbf') == path.endswith('.yml'), ('New source BOM convention changed', path)
    assert '\ufffd' not in data.decode('utf-8-sig'), path
    if path.endswith('.txt'): blocks(data)
    if '/scripted_effects/' in path or '/scripted_triggers/' in path:
        kind = 'scripted_triggers' if '/scripted_triggers/' in path else 'scripted_effects'
        for key, op, value in ast(data):
            assert key not in helpers, ('Duplicate new helper ID', key)
            helpers[key], helper_kinds[key] = value, kind
    groups['new_file_format_and_parse_boundaries'] += 1
definitions = {}
for kind in ('scripted_effects', 'scripted_triggers'):
    definitions[kind] = Counter()
    for file in (ROOT / 'common' / kind).glob('*.txt'):
        definitions[kind].update(key.decode('utf-8') for key in
                                re.findall(rb'(?m)^[ \t]*([\w!]+)\s*=\s*{', file.read_bytes()))
for helper, kind in helper_kinds.items():
    count = definitions[kind][helper]
    assert count == 1, ('Duplicate global helper definition', helper, count)
    groups['unique_helper_definition_IDs'] += 1

# These persistent flags resolve only identifiable legacy debits and block
# old unconsumed replies from binding a newer request after partner revival.
assert helpers['eon_debt_offer_pair_available'] == ast('custom_trigger_tooltip = { tooltip = eon_debt_retired_pair_available_tt ROOT = { NOT = { has_country_flag = eon_debt_retired_pair@PREV } } }')
assert helpers['eon_aid_legacy_pair_available'] == ast('''custom_trigger_tooltip = { tooltip = eon_aid_legacy_pair_available_tt NOT = { OR = {
has_country_flag = sending_small_billion_@eon_aid_policy_donor
has_country_flag = sending_medium_billion_@eon_aid_policy_donor
has_country_flag = sending_high_billion_@eon_aid_policy_donor
has_country_flag = eon_aid_legacy_quarantined@eon_aid_policy_donor } } }''')
assert helpers['eon_aid_retired_pair_available'] == ast('''custom_trigger_tooltip = { tooltip = eon_aid_retired_pair_available_tt
NOT = { has_country_flag = eon_aid_retired_pair@eon_aid_policy_donor }
var:eon_aid_policy_donor = { NOT = { has_country_flag = eon_aid_retired_pair@PREV } } }''')
for gate in ('eon_aid_legacy_pair_available', 'eon_aid_retired_pair_available'):
    assert (gate, '=', 'yes') in helpers['eon_aid_gui_ready']
    assert (gate, '=', 'yes') in one(helpers['eon_aid_draft_send_ready'], 'var:eon_aid_partner')
    groups['legacy_and_retired_pairs_blocked_before_new_offer'] += 1
for wrapper, current_name in (('eon_aid_accept_offer', 'eon_aid_accept_current_offer'),
                              ('eon_aid_refuse_offer', 'eon_aid_refuse_current_offer')):
    assert helpers[wrapper] == ast('eon_aid_cancel_legacy_offer = yes if = { limit = { check_variable = { eon_aid_legacy_resolved = 0 } } ' + current_name + ' = yes }')
    groups['legacy_reply_runs_before_current_transaction'] += 1
legacy = helpers['eon_aid_cancel_legacy_offer']
assert one(one(legacy, 'if'), 'limit') == ast('has_country_flag = eon_aid_legacy_quarantined@FROM')
legacy_refund = one(legacy, 'else_if')
flags = ['sending_' + tier + '_billion_@FROM' for tier in ('small', 'medium', 'high')]
assert one(one(legacy_refund, 'limit'), 'OR') == [('has_country_flag', '=', flag) for flag in flags]
amount_nodes = [v for k, o, v in legacy_refund if k == 'if']
assert len(amount_nodes) == 3
for body, flag, amount in zip(amount_nodes, flags, (5, 15, 35)):
    assert body == ast('limit = { has_country_flag = ' + flag + ' } add_to_temp_variable = { eon_support_refund_amount = ' + str(amount) + ' }')
clears = [i for i, row in enumerate(legacy_refund) if row[0] == 'clr_country_flag']
assert [legacy_refund[i][2] for i in clears] == flags
quarantine = legacy_refund.index(('set_country_flag', '=', 'eon_aid_legacy_quarantined@FROM'))
refund = next(i for i, row in enumerate(legacy_refund) if row[0] == 'FROM')
assert max(clears) < quarantine < refund, 'Legacy refund must follow flag removal and quarantine'
groups['legacy_identifiable_tier_refund_and_quarantine_order'] += 1

def leaves(nodes):
    for row in nodes:
        yield row
        if isinstance(row[2], list): yield from leaves(row[2])
for body in helpers.values():
    assert not any(k == 'clr_country_flag' and isinstance(v, str) and
                   v.startswith(('eon_aid_legacy_quarantined', 'eon_aid_retired_pair', 'eon_debt_retired_pair'))
                   for k, o, v in leaves(body)), 'Persistent pair protection was cleared automatically'
groups['pair_quarantine_and_retirement_flags_never_auto_clear'] += 1
for helper in ('eon_support_daily_cleanup', 'eon_support_cleanup_annexed_pair'):
    body = helpers[helper]
    branches = [v for k, o, v in body if k == 'if']
    assert len(branches) == 2
    for branch, flag, clear in zip(branches,
                                   ('eon_debt_retired_pair@PREV', 'eon_aid_retired_pair@PREV'),
                                   ('eon_support_clear_debt_pending', 'eon_aid_clear_pending')):
        mark = next(i for i, row in enumerate(branch) if isinstance(row[2], list) and
                    ('set_country_flag', '=', flag) in list(leaves(row[2])))
        cleanup = branch.index((clear, '=', 'yes'))
        assert mark < cleanup, 'Pair retirement must precede erased transaction identity'
        groups['retire_dead_pair_before_clearing_marker'] += 1
hooks = one(parsed('common/on_actions/eon_support_on_actions.txt'), 'on_actions')
assert [key for key, op, value in hooks] == ['on_daily', 'on_annex', 'on_subject_annexed']
assert one(one(hooks, 'on_daily'), 'effect') == ast('eon_support_daily_cleanup = yes')
for hook, dead, successor in (('on_annex', 'FROM', 'ROOT'), ('on_subject_annexed', 'ROOT', 'FROM')):
    effect = one(one(hooks, hook), 'effect')
    assert effect == ast('every_country = { limit = { exists = yes NOT = { tag = ' + dead + ' } } set_temp_variable = { eon_support_annexed_partner = ' + dead + ' } eon_support_cleanup_annexed_pair = yes } set_temp_variable = { eon_support_successor = ' + successor + ' } ' + dead + ' = { eon_support_transfer_annexed_assets = yes }')
    groups['annex_hooks_exact_native_actor_scope_and_asset_owner'] += 1

action = one(parsed('common/scripted_diplomatic_actions/eon_support_actions.txt'), 'scripted_diplomatic_actions')
assert [key for key, op, value in action] == ['eon_withdraw_economic_aid']
withdraw = one(action, 'eon_withdraw_economic_aid')
assert one(withdraw, 'requires_acceptance') == 'no' and one(withdraw, 'cost') == '0'
assert one(withdraw, 'ai_desire') == ast('factor = 0')
assert one(withdraw, 'can_be_sent') == ast('eon_aid_offer_withdraw_available = yes')
assert one(withdraw, 'complete_effect') == ast('if = { limit = { eon_aid_offer_withdraw_available = yes } ROOT = { eon_aid_withdraw_offer = yes } }')
groups['zero_cost_sender_withdrawal_guard_and_effect'] += 1
baseline_paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE], cwd=ROOT).decode().splitlines()
old_action_ids = {b['key'] for path in baseline_paths if path.startswith('common/scripted_diplomatic_actions/') and path.endswith('.txt')
                  for b in blocks(before(path)) if b['parent'] == 'scripted_diplomatic_actions' and b['depth'] == 1}
action_ids = [b['key'] for path in (ROOT / 'common/scripted_diplomatic_actions').glob('*.txt')
              for b in blocks(path.read_bytes()) if b['parent'] == 'scripted_diplomatic_actions' and b['depth'] == 1]
package10_all_actions = action_ids
action_ids = package16_historical_actions(historical_actions(action_ids))
assert len(old_action_ids) == 57 and len(action_ids) == len(set(action_ids)) == 64
assert set(action_ids) == old_action_ids | {'eon_withdraw_economic_aid'} | LATER_PACKAGE07_ACTIONS | LATER_PACKAGE08_ACTIONS
action_ids = package10_all_actions
groups['all57_previous_action_IDs_and_one_addition'] += 1

locale = {}
for language in ('english', 'russian'):
    text = read(f'localisation/{language}/eon_support_l_{language}.yml').decode('utf-8-sig')
    assert text.splitlines()[0] == 'l_' + language + ':'
    rows = [re.fullmatch(r' ([\w.]+):0 "(.*)"', line).groups() for line in text.splitlines()[1:]]
    assert len(rows) == len(dict(rows)), 'Duplicate new locale key'
    locale[language] = dict(rows)
assert locale['english'].keys() == locale['russian'].keys()
locale_counts = {}
for language in locale:
    locale_counts[language] = Counter()
    for file in (ROOT / 'localisation' / language).glob('*.yml'):
        locale_counts[language].update(re.findall(r'^ ([\w.]+):', file.read_text(encoding='utf-8-sig'), re.M))
for key in locale['english']:
    assert re.findall(r'\[.*?\]', locale['english'][key]) == re.findall(r'\[.*?\]', locale['russian'][key]), ('Bilingual placeholders mismatch', key)
    for language in locale:
        count = locale_counts[language][key]
        assert count == 1, ('Duplicate/missing locale ID', language, key, count)
    groups['unique_bilingual_locale_IDs_and_placeholders'] += 1
assert {'eon_withdraw_economic_aid', 'eon_withdraw_economic_aid_desc', 'eon_debt_support_action_desc'} <= locale['english'].keys()
notices = {one(value, 'id'): value for key, op, value in parsed('events/eon_support_events.txt') if key == 'country_event'}
assert set(notices) == {f'eon_support.{i}' for i in (10, 11, 12, 13, 14)}
for ident, body in notices.items():
    assert one(body, 'is_triggered_only') == 'yes'
    assert isinstance(one(body, 'desc'), str)
    option = one(body, 'option')
    assert [key for key, op, value in option] == ['name'], 'Notice acknowledgement changes state'
    for field in ('title', 'desc'): assert one(body, field) in locale['english']
    assert '[' not in locale['english'][one(body, 'desc')], 'Queued notice reads mutable terms'
    assert one(option, 'name') in locale['english']
    groups['five_static_notice_IDs_and_inert_ACKs'] += 1

def refs(nodes, path):
    for key, op, value in nodes:
        if key.startswith(('eon_aid_', 'eon_support_', 'eon_debt_')) and value in ('yes', 'no'):
            assert key in helpers, ('Missing new helper reference', path, key)
        if key in ('tooltip', 'custom_effect_tooltip', 'send_description', 'accept_description', 'reject_description', 'text', 'title', 'desc', 'name'):
            if isinstance(value, str) and value.startswith(('eon_aid_', 'eon_support_', 'eon_debt_', 'eon_withdraw_economic_aid')):
                assert value in locale['english'], ('Missing displayed locale reference', path, value)
        if key == 'country_event':
            ident = one(value, 'id') if isinstance(value, list) else value
            if ident.startswith('eon_support.'): assert ident in notices, ('Missing queued notice', path, ident)
        if isinstance(value, list): refs(value, path)
for path in sorted(NEW):
    if path.endswith('.txt'): refs(parsed(path), path)
refs(debt, 'diplo_action_assume_debt')
for ident in AID_EVENTS: refs(aid_events[ident], ident)
refs(one(one(gui, 'effects'), 'opt_aid_button_click'), 'aid GUI effect')
refs(one(one(gui, 'triggers'), 'opt_aid_button_click_enabled'), 'aid GUI trigger')
groups['new_helper_event_and_locale_references'] += 1

native = {'checked': False}
docs = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation')
if docs.exists():
    effects = (docs / 'effects_documentation.md').read_text(encoding='utf-8-sig')
    triggers = (docs / 'triggers_documentation.md').read_text(encoding='utf-8-sig')
    for key in ('clamp_temp_variable', 'every_country', 'country_event', 'subtract_from_temp_variable', 'set_temp_variable'):
        assert '\n## ' + key + '\n' in effects, ('Unsupported native effect', key)
        groups['installed_primary_native_APIs'] += 1
    for key in ('if', 'set_temp_variable', 'multiply_temp_variable', 'add_to_temp_variable', 'check_variable'):
        assert '\n## ' + key + '\n' in triggers, ('Unsupported native trigger', key)
        groups['installed_primary_native_APIs'] += 1
    hook_docs = docs.parent / 'common/on_actions/_documentation.md'
    hook_examples = docs.parent / 'common/on_actions/03_wtt_on_actions.txt'
    if hook_docs.exists() and hook_examples.exists():
        listing = hook_docs.read_text(encoding='utf-8-sig')
        examples = hook_examples.read_text(encoding='utf-8-sig')
        for name in ('on_daily', 'on_annex', 'on_subject_annexed'):
            assert '- `' + name + '`' in listing, ('Native hook not documented', name)
            groups['installed_primary_on_action_listing'] += 1
        assert '#ROOT is subject FROM is overlord' in examples
        assert '#ROOT is winner #FROM gets annexed' in examples
        groups['installed_primary_annex_scope_comments'] += 2
    native = {'checked': True, 'path': str(docs), 'effect_and_trigger_api_presence': True,
              'not_proven': 'native on_action callback timing and annex/subject scopes'}

TREES = ('common', 'history', 'events', 'interface', 'gfx', 'localisation', 'music', 'map', 'sound')
package21_required_old_paths = EXISTING | NEW | LATER_PACKAGE07_NEW | LATER_PACKAGE08_NEW | LATER_PACKAGE09_NEW | LATER_PACKAGE10_NEW | LATER_PACKAGE11_NEW | LATER_PACKAGE12_NEW | LATER_PACKAGE13_NEW
changed = subprocess.check_output(['git', 'diff', '--name-only', BASELINE, '--', *TREES], cwd=ROOT).decode().splitlines()
changed = [path for path in changed if path not in LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | package14_historical_existing(BASELINE) | package15_historical_existing(BASELINE) | package16_historical_existing(BASELINE) | LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | package18_historical_existing(BASELINE) | LATER_PACKAGE18_NEW | package19_historical_existing(BASELINE) | LATER_PACKAGE19_NEW | package20_historical_existing(BASELINE) | LATER_PACKAGE20_NEW | (package21_historical_existing(BASELINE) - package21_required_old_paths) | LATER_PACKAGE21_NEW | (package22_historical_existing(BASELINE) - package21_required_old_paths) | LATER_PACKAGE22_NEW]
untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', *TREES], cwd=ROOT).decode().splitlines()
untracked = [path for path in untracked if path not in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | LATER_PACKAGE22_NEW]
assert set(changed) | set(untracked) == EXISTING | NEW | LATER_PACKAGE07_NEW | LATER_PACKAGE08_NEW | LATER_PACKAGE09_NEW | LATER_PACKAGE10_NEW | LATER_PACKAGE11_NEW | LATER_PACKAGE12_NEW | LATER_PACKAGE13_NEW, ('Unexpected package06 gameplay scope', changed, untracked)
assert set(untracked) <= NEW | LATER_PACKAGE07_NEW | LATER_PACKAGE08_NEW | LATER_PACKAGE09_NEW | LATER_PACKAGE10_NEW | LATER_PACKAGE11_NEW | LATER_PACKAGE12_NEW | LATER_PACKAGE13_NEW, ('Unowned new source', untracked)
assert not set(NEW).intersection(baseline_paths), 'New support file overwrites original source'
groups['exact14_file_whole_gameplay_boundary'] += 1
print(json.dumps({'all_passed': True, 'total_cases': sum(groups.values()), 'groups': groups,
                  'baseline': BASELINE, 'owned_existing_files': receipts,
                  'new_files': sorted(NEW), 'new_helper_IDs': len(helpers), 'unique_action_IDs': len(action_ids),
                  'new_locale_keys_per_language': len(locale['english']), 'native_primary_documentation': native,
                  'not_proven': 'HOI4 compilation, native callback timing/scopes, GUI, campaign or save/load'}, indent=2))
