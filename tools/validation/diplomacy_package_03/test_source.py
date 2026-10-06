"""Exact package-03 boundaries, preserved policy adapters and reference checks.

These assertions establish source preservation; they do not parse HOI4 itself.
"""
from collections import Counter
import hashlib
import json
import re
import subprocess

from _support import ROOT, BASELINE, ast, baseline, blocks, format_preserved, maybe, one, prime_baselines, source

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

groups = Counter()
receipt = []


def passed(group, count=1): groups[group] += count


def restore_named(after, before, selector):
    old = {selector(b): b for b in blocks(before) if selector(b)}
    new = {selector(b): b for b in blocks(after) if selector(b)}
    assert new.keys() == old.keys()
    for key, block in sorted(new.items(), key=lambda item: item[1]['start'], reverse=True):
        original = old[key]
        after = after[:block['start']] + before[original['start']:original['end']] + after[block['end']:]
    return after


def record(path, before, after):
    format_preserved(before, after)
    receipt.append({'path': path, 'unrelated_bytes_exact': True,
                    'sha256': hashlib.sha256(after).hexdigest()})
    passed('owned_existing_file_boundaries')


path = 'common/ideologies/00_ideologies.txt'
before, after = baseline(path), (ROOT / path).read_bytes()
assert before.count(b'can_create_factions = no') == after.count(b'can_create_factions = yes') == 5
assert after == before.replace(b'can_create_factions = no', b'can_create_factions = yes'), 'Other ideology bytes changed'
ideologies = one(ast(after), 'ideologies')
assert [key for key, op, value in ideologies] == ['democratic', 'communism', 'fascism', 'neutrality', 'nationalist']
for key, op, value in ideologies:
    assert one(one(value, 'rules'), 'can_create_factions') == 'yes'
record(path, before, after)

path = 'common/factions/templates/00_multiplayer.txt'
before, after = baseline(path), (ROOT / path).read_bytes()
teams = {'faction_template_teama', 'faction_template_teamb', 'faction_template_teamc', 'faction_template_teamD'}
def visible_selector(b): return b['parent'] if b['key'] == 'visible' and b['depth'] == 1 and b['parent'] in teams else None
assert restore_named(after, before, visible_selector) == before, 'Other TEAM bytes changed'
expected = ast('is_ai = no has_game_rule = { rule = allow_mp_optimizations option = yes }')
assert {key for key, op, value in ast(after)} == teams
for key, op, value in ast(after): assert one(value, 'visible') == expected
record(path, before, after)

path = 'common/scripted_triggers/00_game_rule_triggers.txt'
before, after = baseline(path), (ROOT / path).read_bytes()
native_keys = ('DIPLOMACY_CALL_ALLY_ENABLE_TRIGGER', 'DIPLOMACY_JOIN_ALLY_ENABLE_TRIGGER',
               'DIPLOMACY_JOIN_FACTION_ENABLE_TRIGGER', 'DIPLOMACY_OFFER_JOIN_FACTION_ENABLE_TRIGGER')
def native_selector(b): return b['key'] if b['depth'] == 0 and b['key'] in native_keys else None
assert restore_named(after, before, native_selector) == before, 'Other native diplomatic triggers changed'
guards = {
    native_keys[0]: '''if = { limit = { OR = { eon_defensive_alliance_is_member = yes FROM = { eon_defensive_alliance_is_member = yes } } }
        custom_trigger_tooltip = { tooltip = eon_defensive_alliance_call_tt eon_defensive_alliance_war_eligible = yes } }''',
    native_keys[1]: '''if = { limit = { OR = { eon_defensive_alliance_is_member = yes FROM = { eon_defensive_alliance_is_member = yes } } }
        custom_trigger_tooltip = { tooltip = eon_defensive_alliance_call_tt FROM = { eon_defensive_alliance_war_eligible = yes } } }''',
    native_keys[2]: '''if = { limit = { FROM = { eon_defensive_alliance_is_member = yes } }
        custom_trigger_tooltip = { tooltip = eon_defensive_alliance_join_tt eon_defensive_alliance_member_eligible = yes
            FROM = { is_subject = no has_offensive_war = no } } }''',
    native_keys[3]: '''if = { limit = { eon_defensive_alliance_is_member = yes }
        custom_trigger_tooltip = { tooltip = eon_defensive_alliance_join_tt is_subject = no has_offensive_war = no
            FROM = { eon_defensive_alliance_member_eligible = yes } } }''',
}
for key in native_keys:
    new, old = one(ast(after), key), one(ast(before), key)
    assert new == ast(guards[key]) + old, ('Native policy AST changed after its new guard', key)
    # The raw legacy suffix includes its comments and whitespace, not just AST.
    b = next(b for b in blocks(before) if native_selector(b) == key)
    a = next(b for b in blocks(after) if native_selector(b) == key)
    old_start = before.index(b'{', b['start']) + 1
    new_start = after.index(b'{', a['start']) + 1
    old_body = before[old_start:b['end']-1]
    assert after[new_start:a['end']-1].endswith(old_body), ('Native policy suffix bytes changed', key)
    passed('four_native_guard_contexts_and_exact_legacy_suffixes')
record(path, before, after)

# The scripted protocol must inherit both native organisation/country filters.
def rename(nodes, old, new):
    return [(new if key == old else key, op,
             rename(value, old, new) if isinstance(value, list) else new if value == old else value)
            for key, op, value in nodes]
native = ast(baseline(path))
expected_policy = [('ROOT', '=', rename(one(native, native_keys[3]), 'FROM', 'PREV'))]
expected_policy += rename(one(native, native_keys[2]), 'FROM', 'ROOT')
actual_policy = one(source('common/scripted_triggers/eon_defensive_alliance_native_policy_triggers.txt'),
                    'eon_defensive_alliance_offer_existing_policy')
assert actual_policy == expected_policy, 'Inherited native JOIN/OFFER policy was rewritten or mis-scoped'
passed('exact_baseline_join_offer_policy_scope_adapter')

new_paths = {
    'common/factions/templates/eon_defensive_alliance.txt',
    'common/factions/rules/eon_defensive_alliance_rules.txt',
    'common/scripted_triggers/eon_defensive_alliance_triggers.txt',
    'common/scripted_triggers/eon_defensive_alliance_offer_triggers.txt',
    'common/scripted_triggers/eon_defensive_alliance_native_policy_triggers.txt',
    'common/scripted_effects/eon_defensive_alliance_effects.txt',
    'common/scripted_effects/eon_defensive_alliance_offer_effects.txt',
    'common/scripted_diplomatic_actions/eon_defensive_alliance_action.txt',
    'common/on_actions/eon_defensive_alliance_on_actions.txt',
    'localisation/english/eon_defensive_alliance_l_english.yml',
    'localisation/russian/eon_defensive_alliance_l_russian.yml',
}
game_trees = ('common', 'history', 'events', 'interface', 'gfx', 'localisation', 'music', 'map', 'sound')
# Package 04 proves the exact later byte deltas against bb018ea1 in its own
# test_source.py; ordinary-alliance and national-policy boundaries remain exact.
later_energy_paths = {
    'common/scripted_guis/01_energy_gui.txt',
    'common/scripted_effects/eon_energy_contract_effects.txt',
    'common/scripted_effects/!_energy_effects.txt',
    'common/scripted_triggers/eon_energy_capacity_triggers.txt',
    'events/00_Energy_market_events.txt',
    'interface/MD_energy_scripted.gui',
    'localisation/english/eon_energy_contract_l_english.yml',
    'localisation/russian/eon_energy_contract_l_russian.yml',
}
# Package05 proves these later negotiation files against688f independently.
later_negotiation_paths = {
    'common/scripted_effects/eon_energy_ai_effects.txt',
    'common/scripted_effects/eon_energy_negotiation_effects.txt',
    'common/scripted_triggers/eon_energy_negotiation_triggers.txt',
    'common/scripted_diplomatic_actions/eon_energy_negotiation_actions.txt',
    'events/eon_energy_negotiation_events.txt',
    'localisation/english/eon_energy_negotiation_l_english.yml',
    'localisation/russian/eon_energy_negotiation_l_russian.yml',
}
later_energy_paths |= later_negotiation_paths
# Package06 validates these exact aid/debt paths against published551d source;
# every ordinary-alliance/national policy byte assertion above remains exact.
later_support_new_paths = {
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
later_support_existing_paths = {
    'common/scripted_diplomatic_actions/00_scripted_diplomatic_actions.txt',
    'common/scripted_guis/influence_scripted_gui.txt',
    'events/00_Influence_events.txt',
    'localisation/english/MDC_scripted_diplomatic_actions_l_english.yml',
    'localisation/russian/MDDC_scripted_diplomatic_actions_l_russian.yml',
}
later_support_paths = later_support_new_paths | later_support_existing_paths
# Package 07 proves these seven additions and every old game byte against 4406.
later_consultation_paths = {
    'common/scripted_effects/eon_consultation_effects.txt',
    'common/scripted_triggers/eon_consultation_triggers.txt',
    'common/scripted_diplomatic_actions/eon_consultation_actions.txt',
    'common/on_actions/eon_consultation_on_actions.txt',
    'events/eon_consultation_events.txt',
    'localisation/english/eon_consultation_l_english.yml',
    'localisation/russian/eon_consultation_l_russian.yml',
}
# Package 08 independently preserves every old game byte and owns exactly these additions.
later_mediation_paths = {
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
tracked_changes = subprocess.check_output(['git', 'diff', '--name-only', BASELINE, '--', *game_trees], cwd=ROOT).decode().splitlines()
tracked_changes = [path for path in tracked_changes if path not in LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | package14_historical_existing(BASELINE) | package15_historical_existing(BASELINE) | package16_historical_existing(BASELINE) | LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | package18_historical_existing(BASELINE) | LATER_PACKAGE18_NEW | package19_historical_existing(BASELINE) | LATER_PACKAGE19_NEW | package20_historical_existing(BASELINE) | LATER_PACKAGE20_NEW | package21_historical_existing(BASELINE) | LATER_PACKAGE21_NEW]
owned_paths = {item['path'] for item in receipt}
assert set(tracked_changes) <= owned_paths | new_paths | later_energy_paths | later_support_paths | later_consultation_paths | later_mediation_paths | LATER_PACKAGE09_NEW | LATER_PACKAGE10_NEW | LATER_PACKAGE11_NEW | LATER_PACKAGE12_NEW | LATER_PACKAGE13_NEW, ('Unowned gameplay changes', tracked_changes)
untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', *game_trees], cwd=ROOT).decode().splitlines()
untracked = [path for path in untracked if path not in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]
assert set(untracked) <= new_paths | later_negotiation_paths | later_support_new_paths | later_consultation_paths | later_mediation_paths | LATER_PACKAGE09_NEW | LATER_PACKAGE10_NEW | LATER_PACKAGE11_NEW | LATER_PACKAGE12_NEW | LATER_PACKAGE13_NEW | {'common/scripted_triggers/eon_energy_capacity_triggers.txt'}, ('Unowned new gameplay files', untracked)
baseline_paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, '--', *game_trees], cwd=ROOT).decode().splitlines()
assert not set(new_paths).intersection(baseline_paths), 'New files overwrite existing baseline sources'
passed('unchanged_tracked_gameplay_path_boundary')

# All national grants/bans, rank/law/AI thresholds, defaults and organisation hooks
# stay byte-identical. Wider git boundaries above also cover their other callers.
exact_paths = [p for p in baseline_paths if p.startswith(('common/ideas/', 'common/national_focus/', 'history/countries/',
                                                        'common/defines/', 'common/autonomous_states/', 'common/on_actions/',
                                                        'common/factions/rules/'))]
exact_paths += [p for p in baseline_paths if p.startswith('common/factions/templates/') and p != 'common/factions/templates/00_multiplayer.txt']
prime_baselines(exact_paths)
for unchanged in exact_paths:
    assert package10_original_bytes(unchanged, package14_original_bytes(unchanged, package21_original_bytes(unchanged, (ROOT / unchanged).read_bytes()))) == baseline(unchanged), 'Preserved policy bytes changed: ' + unchanged
passed('national_story_rules_thresholds_and_old_templates_exact_bytes', len(exact_paths))

helpers, helper_paths = {}, {}
for folder in ('scripted_effects', 'scripted_triggers'):
    for file in sorted((ROOT / 'common' / folder).glob('eon_defensive_alliance*_' + folder.removeprefix('scripted_') + '.txt')):
        data = file.read_bytes(); blocks(data)
        assert b'\r' not in data, 'New source has mixed CR/LF'
        for key, op, value in ast(data):
            assert key not in helpers, ('Duplicate helper ID', key)
            helpers[key], helper_paths[key] = value, file
member = helpers['eon_defensive_alliance_member_eligible']
assert not any(key == 'clamp_temp_variable' for key, op, value in member), 'Raw join threshold was capped'
assert ('set_temp_variable', '=', [('eon_defensive_alliance_join_tension', '=', 'modifier@join_faction_tension')]) in member
assert ('threat', '>=', 'eon_defensive_alliance_join_tension') in member
passed('raw_current_native_join_threshold_source')

old_templates = {key for p in baseline_paths if p.startswith('common/factions/templates/') and p.endswith('.txt')
                 for key, op, value in ast(baseline(p))}
assert len(old_templates) == 73
veto = one(helpers['eon_defensive_alliance_has_nonordinary_template'], 'OR')
assert all(key == 'has_faction_template' and op == '=' for key, op, value in veto)
assert len(veto) == len({v for k, op, v in veto}) == 72
assert {v for k, op, v in veto} == old_templates - {'faction_template_generic'}, 'Template-veto inventory drifted'
passed('template_inventory_and_generic_fallback_exception')

all_rules = {key for file in (ROOT / 'common/factions/rules').glob('*.txt') for key, op, value in ast(file.read_bytes())}
template = one(source('common/factions/templates/eon_defensive_alliance.txt'), 'eon_defensive_alliance_template')
rule_ids = [v for k, op, v in one(template, 'default_rules')]
assert rule_ids == ['eon_defensive_alliance_joining_rule', 'eon_defensive_alliance_call_rule']
assert all(key in all_rules for key in rule_ids)
for file in [ROOT / p for p in new_paths if p.endswith('.txt')]:
    def visit(nodes):
        for key, op, value in nodes:
            if key.startswith('eon_defensive_alliance_') and value in ('yes', 'no'):
                assert key in helpers, ('Missing helper reference', file, key)
            if isinstance(value, list): visit(value)
    visit(ast(file.read_bytes()))
passed('new_helper_and_default_rule_references', len(helpers) + len(rule_ids))

action = one(one(source('common/scripted_diplomatic_actions/eon_defensive_alliance_action.txt'), 'scripted_diplomatic_actions'),
             'eon_propose_defensive_alliance')
assert one(action, 'requires_acceptance') == one(action, 'show_acceptance_on_action_button') == 'yes'
assert one(action, 'cost') == '0'
assert one(action, 'on_sent_effect') == ast('if = { limit = { eon_defensive_alliance_offer_send_ready = yes } eon_defensive_alliance_offer_start = yes }')
assert one(action, 'complete_effect') == ast('if = { limit = { eon_defensive_alliance_offer_response_valid = yes } eon_defensive_alliance_offer_establish = yes } eon_defensive_alliance_offer_finish_response = yes')
assert one(action, 'reject_effect') == ast('eon_defensive_alliance_offer_finish_response = yes')
actions = [b['key'] for file in (ROOT / 'common/scripted_diplomatic_actions').glob('*.txt')
           for b in blocks(file.read_bytes()) if b['parent'] == 'scripted_diplomatic_actions' and b['depth'] == 1]
package10_all_actions = actions
actions = package16_historical_actions(historical_actions(actions))
assert len(actions) == len(set(actions)) == 64
later_action_ids = {'eon_withdraw_energy_offer', 'eon_resume_energy_counter_offer', 'eon_withdraw_economic_aid',
                    'eon_open_economic_consultations', 'eon_withdraw_consultation_request',
                    'eon_end_economic_consultations', 'eon_consultation_offer_economic_aid',
                    'eon_request_war_mediation', 'eon_withdraw_mediation'}
# Compare the retained 54 native actions and package03 alliance action against
# immutable original IDs, rather than against a filtered copy of current files.
original_action_ids = {
    b['key'] for p in baseline_paths
    if p.startswith('common/scripted_diplomatic_actions/') and p.endswith('.txt')
    for b in blocks(baseline(p)) if b['parent'] == 'scripted_diplomatic_actions' and b['depth'] == 1
} | {'eon_propose_defensive_alliance'}
assert len(original_action_ids) == 55
assert set(actions) - later_action_ids == original_action_ids
actions = package10_all_actions
passed('accepted_only_action_structure_and_unique_diplomatic_ids', len(actions))

locale = {}
for language in ('english', 'russian'):
    file = ROOT / f'localisation/{language}/eon_defensive_alliance_l_{language}.yml'
    data = file.read_bytes(); assert data.startswith(b'\xef\xbb\xbf') and b'\r' not in data
    text = data.decode('utf-8-sig'); assert '\ufffd' not in text
    lines = text.splitlines(); assert lines[0] == 'l_' + language + ':'
    entries = [re.fullmatch(r' ([\w.]+):(?:\d+)? "(.*)"', line).groups() for line in lines[1:]]
    assert len(entries) == len(dict(entries)), 'Duplicate new local key'
    locale[language] = dict(entries)
assert locale['english'].keys() == locale['russian'].keys()
for key in locale['english']:
    assert re.findall(r'\[.*?\]', locale['english'][key]) == re.findall(r'\[.*?\]', locale['russian'][key])
for language in locale:
    counts = dict.fromkeys(locale[language], 0)
    for file in (ROOT / 'localisation' / language).glob('*.yml'):
        for key in re.findall(r'^\s+([\w.]+):', file.read_text(encoding='utf-8-sig'), re.M):
            if key in counts: counts[key] += 1
    assert all(value == 1 for value in counts.values()), ('Missing/duplicate locale', language, counts)
for key in ('eon_defensive_alliance_name', 'eon_defensive_alliance_template', 'eon_defensive_alliance_template_desc',
            'eon_propose_defensive_alliance', 'eon_propose_defensive_alliance_desc', *rule_ids,
            *(key + '_desc' for key in rule_ids)):
    assert key in locale['english'], ('Missing displayed locale', key)
for value in (one(action, 'send_description'), *[key for key, op, value in one(action, 'ai_acceptance')]):
    assert value in locale['english']
for helper in helpers.values():
    def tooltips(nodes):
        for key, op, value in nodes:
            if key == 'tooltip' and value.startswith('eon_defensive_alliance_'): assert value in locale['english']
            if isinstance(value, list): tooltips(value)
    tooltips(helper)
passed('bilingual_unique_locale_keys_boms_and_placeholders', len(locale['english']))

print(json.dumps({'all_passed': True, 'total_cases': sum(groups.values()), 'groups': groups,
                  'owned_existing_files': receipt, 'baseline': BASELINE,
                  'unchanged_tracked_git_content_paths': len(baseline_paths) - len(owned_paths),
                  'preserved_policy_files_compared_as_raw_bytes': len(exact_paths),
                  'new_helper_ids': len(helpers), 'unique_action_ids': len(actions),
                  'new_locale_keys_per_language': len(locale['english']),
                  'not_proven': 'HOI4 native engine parsing, user interface or campaign'}, indent=2))
