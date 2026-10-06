"""Package 08 exact mediation source/API boundaries; not HOI4 compilation."""
from collections import Counter
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
BASELINE = 'b86a187f8ff3dfc88a577db4b2c52525fd5cf2fd'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'diplomacy_package_03'))
from _support import ast, blocks, one

NEW = {
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
NEW_ACTIONS = {'eon_request_war_mediation', 'eon_withdraw_mediation'}
NEW_DECISIONS = {'eon_select_mediation_deescalation_opponent', 'eon_select_mediation_humanitarian_opponent'}
TREES = ('common', 'history', 'events', 'interface', 'gfx', 'localisation', 'music', 'map', 'sound',
         'portraits', 'tutorial', 'descriptions', 'scenario_tests', 'descriptor.mod', 'era_of_nations.mod', 'thumbnail.png')
groups, receipts, sources, helpers, helper_kinds = Counter(), [], {}, {}, {}
assert len(NEW) == 9 and len(NEW_ACTIONS) == len(NEW_DECISIONS) == 2
assert (ROOT / 'common/scripted_effects/eon_mediation_effects.txt').exists(), 'RED: the consent-based mediation lifecycle is not implemented'

def rows(nodes):
    for row in nodes:
        yield row
        if isinstance(row[2], list): yield from rows(row[2])

for path in sorted(NEW):
    data = (ROOT / path).read_bytes()
    assert b'\r' not in data and data.endswith(b'\n'), ('New source must use LF and final newline', path)
    assert data.startswith(b'\xef\xbb\xbf') == path.endswith('.yml'), ('New source BOM convention', path)
    assert '\ufffd' not in data.decode('utf-8-sig'), path
    if path.endswith('.txt'):
        parse_data = data
        if path == 'common/scripted_effects/eon_mediation_effects.txt':
            before09 = subprocess.check_output(['git', 'show', '3b6efd83f9b1a62c7348f52d232ff0f08583a92c:' + path], cwd=ROOT)
            marker = b'eon_mediation_clear_record = {\n'
            hook = b' eon_mediation_terms_before_base_clear = yes\n'
            assert before09.count(marker) == 1
            assert data == before09.replace(marker, marker + hook, 1), 'Only package09 pre-clear hook may alter package08 source'
            parse_data = before09
            groups['package09_single_hook_exact_restore_before_original_assertions'] += 1
        blocks(parse_data)
        sources[path] = ast(parse_data)
    if '/scripted_effects/' in path or '/scripted_triggers/' in path:
        kind = 'scripted_triggers' if '/scripted_triggers/' in path else 'scripted_effects'
        for key, op, value in sources[path]:
            assert key.startswith('eon_mediation_'), ('Unowned new helper namespace', key)
            assert key not in helpers, ('Duplicate new helper ID', key)
            helpers[key], helper_kinds[key] = value, kind
    receipts.append({'path': path, 'sha256': hashlib.sha256(data).hexdigest()})
    groups['new_file_format_and_parse_boundaries'] += 1
assert 'eon_mediation_prepare_draft' in helpers

# Immutable blobs protect BOM/EOL/EOF as well as script content. No previous
# gameplay source may change, including all earlier package implementations.
baseline_paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, '--', *TREES], cwd=ROOT).decode().splitlines()
changed = subprocess.check_output(['git', 'diff', '--name-only', BASELINE, '--', *TREES], cwd=ROOT).decode().splitlines()
changed = [path for path in changed if path not in LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | package14_historical_existing(BASELINE) | package15_historical_existing(BASELINE) | package16_historical_existing(BASELINE) | LATER_PACKAGE16_NEW]
untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', *TREES], cwd=ROOT).decode().splitlines()
untracked = [path for path in untracked if path not in LATER_PACKAGE16_NEW]
assert set(changed) | set(untracked) == NEW | LATER_PACKAGE09_NEW | LATER_PACKAGE10_NEW | LATER_PACKAGE11_NEW | LATER_PACKAGE12_NEW | LATER_PACKAGE13_NEW, ('Unexpected package 08 gameplay source boundary', changed, untracked)
assert not set(changed).intersection(baseline_paths), 'Existing gameplay bytes changed'
assert not NEW.intersection(baseline_paths), 'New mediation source overwrites old game files'
assert set(untracked) <= NEW | LATER_PACKAGE09_NEW | LATER_PACKAGE10_NEW | LATER_PACKAGE11_NEW | LATER_PACKAGE12_NEW | LATER_PACKAGE13_NEW
groups['all_existing_gameplay_bytes_preserved_and_exact_nine_additions'] += 1

old_actions = {b['key'] for path in baseline_paths
               if path.startswith('common/scripted_diplomatic_actions/') and path.endswith('.txt')
               for b in blocks(subprocess.check_output(['git', 'show', BASELINE + ':' + path], cwd=ROOT))
               if b['parent'] == 'scripted_diplomatic_actions' and b['depth'] == 1}
actions = [b['key'] for path in (ROOT / 'common/scripted_diplomatic_actions').glob('*.txt')
           for b in blocks(path.read_bytes()) if b['parent'] == 'scripted_diplomatic_actions' and b['depth'] == 1]
package10_all_actions = actions
actions = package16_historical_actions(historical_actions(actions))
assert len(old_actions) == 62
assert len(actions) == len(set(actions)) == 64
assert set(actions) == old_actions | NEW_ACTIONS
actions = package10_all_actions
groups['all_62_existing_native_action_IDs_and_two_additions'] += 1

native_actions = one(sources['common/scripted_diplomatic_actions/eon_mediation_actions.txt'], 'scripted_diplomatic_actions')
assert {k for k, op, value in native_actions} == NEW_ACTIONS
for key, op, body in native_actions:
    assert one(body, 'allowed') == ast('ROOT = { is_ai = no }'), ('Unsolicited AI initiation', key)
    assert one(body, 'cost') == '0', ('Fresh opponent selection alone owns the PP debit', key)
    assert one(body, 'requires_acceptance') == 'no', ('Explicit invitations own consent', key)
    assert one(body, 'ai_desire') == ast('factor = 0'), ('Unexpected AI initiation desire', key)
    groups['human_native_entrypoints_zero_native_cost_and_no_AI_initiation'] += 1

category = one(sources['common/decisions/categories/eon_mediation_categories.txt'], 'eon_mediation_category')
assert one(category, 'icon') == 'generic_foreign_policy'
sprite_name = 'GFX_decision_category_' + one(category, 'icon')
assert any(sprite_name.encode() in path.read_bytes() for path in (ROOT / 'interface').glob('*.gfx')), 'Decision category sprite missing'
decisions = one(sources['common/decisions/eon_mediation_decisions.txt'], 'eon_mediation_category')
assert {k for k, op, value in decisions} == NEW_DECISIONS
for key, op, body in decisions:
    assert one(body, 'cost') == '0', ('Fresh helper must own the only PP debit', key)
    assert one(body, 'ai_will_do') == ast('factor = 0'), ('AI cannot originate mediation', key)
    sprite = ('GFX_decision_' + one(body, 'icon')).encode()
    sprite_sources = list((ROOT / 'interface').glob('*.gfx')) + list(Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/interface').glob('*.gfx'))
    assert any(sprite in path.read_bytes() for path in sprite_sources), ('Decision sprite absent from mod and installed base', key)
    groups['two_literal_targeted_decisions_zero_native_cost_and_AI_disabled'] += 1
groups['new_category_existing_sprite_and_exact_two_decisions'] += 1

locale = {}
for language in ('english', 'russian'):
    lines = (ROOT / f'localisation/{language}/eon_mediation_l_{language}.yml').read_text(encoding='utf-8-sig').splitlines()
    assert lines[0] == 'l_' + language + ':'
    pairs = [re.fullmatch(r' ([\w.]+):0 "(.*)"', line).groups() for line in lines[1:]]
    assert len(pairs) == len(dict(pairs)), ('Duplicate mediation locale key', language)
    locale[language] = dict(pairs)
assert locale['english'].keys() == locale['russian'].keys()
locale_counts = {}
for language in locale:
    locale_counts[language] = Counter()
    for path in (ROOT / 'localisation' / language).glob('*.yml'):
        locale_counts[language].update(re.findall(r'^ ([\w.]+):', path.read_text(encoding='utf-8-sig'), re.M))
for key in locale['english']:
    assert re.findall(r'\[.*?\]', locale['english'][key]) == re.findall(r'\[.*?\]', locale['russian'][key]), ('Bilingual placeholder mismatch', key)
    for language in locale:
        assert locale_counts[language][key] == 1, ('Duplicate/missing global mediation locale', language, key)
    groups['unique_bilingual_locale_IDs_and_placeholders'] += 1
for key in NEW_ACTIONS | NEW_DECISIONS | {'eon_mediation_category'}:
    assert {key, key + '_desc'} <= locale['english'].keys(), ('Missing entrypoint text', key)

event_bodies = [body for key, op, body in sources['events/eon_mediation_events.txt'] if key == 'country_event']
events = {one(body, 'id'): body for body in event_bodies}
assert len(events) == len(event_bodies), 'Duplicate mediation event identity'
notices = {f'eon_mediation.{n}' for n in range(30, 38)}
assert set(events) == notices | {'eon_mediation.10', 'eon_mediation.11', 'eon_mediation.20', 'eon_mediation.21'}
for ident in sorted(notices):
    body = events[ident]
    assert {key for key, op, value in body} == {'id', 'title', 'desc', 'picture', 'is_triggered_only', 'option'}, ('Static notice has a hidden mutation or extra event field', ident)
    assert one(body, 'is_triggered_only') == 'yes'
    option = one(body, 'option')
    assert [key for key, op, value in option] == ['name'], ('Queued acknowledgement mutates state', ident)
    for field in ('title', 'desc'):
        value = one(body, field)
        assert isinstance(value, str) and value in locale['english']
        assert '[' not in locale['english'][value], ('Queued notice reads mutable party or topic', ident, field)
    assert one(option, 'name') in locale['english']
    groups['eight_static_results_and_inert_ACKs'] += 1

# Native NOT is NOR. Negating a conjunction requires a single AND child;
# each new NOT has one explicit child/group so older model semantics cannot mask it.
for path, nodes in sources.items():
    for key, op, body in rows(nodes):
        if key == 'NOT':
            assert isinstance(body, list) and len(body) == 1, ('New NOT must have one explicit child/group', path, body)
            groups['all_new_negations_have_one_unambiguous_child_or_group'] += 1

definitions = {}
for kind in ('scripted_effects', 'scripted_triggers'):
    definitions[kind] = Counter()
    for path in (ROOT / 'common' / kind).glob('*.txt'):
        definitions[kind].update(k.decode('utf-8') for k in re.findall(rb'(?m)^[ \t]*([\w!]+)\s*=\s*{', path.read_bytes()))
for key, kind in helper_kinds.items():
    assert definitions[kind][key] == 1, ('Duplicate global mediation helper definition', key)
    groups['unique_helper_IDs'] += 1
for path, nodes in sources.items():
    for key, op, value in rows(nodes):
        if key.startswith('eon_mediation_') and value in ('yes', 'no'):
            assert key in helpers, ('Missing mediation helper reference', path, key)
        if key in ('tooltip', 'custom_effect_tooltip', 'send_description', 'accept_description', 'reject_description', 'text', 'title', 'desc', 'name'):
            if isinstance(value, str) and value.startswith(('eon_mediation', 'eon_request_war_mediation', 'eon_withdraw_mediation', 'eon_select_mediation')):
                assert value in locale['english'], ('Missing mediation locale reference', path, value)
        if key == 'country_event':
            ident = one(value, 'id') if isinstance(value, list) else value
            if ident.startswith('eon_mediation.'): assert ident in events, ('Missing queued mediation event', path, ident)
groups['helper_event_and_locale_references'] += 1

global_events = Counter()
for path in (ROOT / 'events').glob('*.txt'):
    global_events.update(re.findall(r'\bid\s*=\s*(eon_mediation\.[\w]+)', path.read_text(encoding='utf-8-sig')))
for ident in events:
    assert global_events[ident] == 1, ('Duplicate global mediation event', ident, global_events[ident])
    groups['unique_global_mediation_event_IDs'] += 1
for ident in NEW_DECISIONS:
    count = sum(len(re.findall(rb'\b' + ident.encode() + rb'\s*=\s*{', path.read_bytes())) for path in (ROOT / 'common/decisions').glob('*.txt'))
    assert count == 1, ('Duplicate global targeted decision', ident, count)
    groups['unique_global_mediation_targeted_decision_IDs'] += 1

def effect_rows(nodes):
    for key, op, value in nodes:
        if key == 'limit': continue
        if key in ('if', 'else_if', 'else', 'hidden_effect', 'effect_tooltip', 'ROOT', 'THIS', 'FROM', 'PREV', 'every_country') or key.startswith('var:eon_mediation_'):
            assert isinstance(value, list), ('Expected effect block', key)
            yield from effect_rows(value)
        else: yield key, op, value

native_mutators = {'set_variable', 'set_temp_variable', 'add_to_variable', 'add_to_temp_variable',
                   'subtract_from_variable', 'subtract_from_temp_variable', 'set_country_flag',
                   'clr_country_flag', 'clear_variable', 'add_political_power', 'country_event',
                   'custom_effect_tooltip', 'log'}
ttl, pp_debits = [], []
for helper, body in helpers.items():
    if helper_kinds[helper] != 'scripted_effects': continue
    for key, op, value in effect_rows(body):
        assert key in native_mutators or key in helpers, ('Undeclared non-mediation effect', helper, key)
        if key in helpers:
            assert helper_kinds[key] == 'scripted_effects', ('Trigger helper used as a native effect', helper, key)
        if key in ('set_variable', 'set_temp_variable', 'add_to_variable', 'add_to_temp_variable', 'subtract_from_variable', 'subtract_from_temp_variable'):
            assert all(k.startswith('eon_mediation_') for k, o, v in value), ('Another subsystem variable is mutated', helper, key)
        elif key == 'set_country_flag':
            flag = one(value, 'flag') if isinstance(value, list) else value
            assert flag.startswith('eon_mediation_'), ('Another subsystem flag is set', helper, flag)
            if isinstance(value, list): ttl.append((flag, one(value, 'days')))
        elif key in ('clr_country_flag', 'clear_variable'):
            assert value.startswith('eon_mediation_'), ('Another subsystem state is cleared', helper, value)
            assert not value.startswith('eon_mediation_retired_pair'), 'Expired invitation pair protection is cleared automatically'
        elif key == 'add_political_power': pp_debits.append((helper, value))
    groups['mediation_effect_owns_only_communication_state'] += 1
assert len(pp_debits) == 1 and pp_debits[0][1] == '-20', ('Exactly one fresh send helper must charge twenty PP', pp_debits)
for flag, days in ttl:
    assert (flag.startswith('eon_mediation_recent_contact@') and days == '90') or (flag == 'eon_mediation_draft_window' and days == '7') or (flag in ('eon_mediation_response_window', 'eon_mediation_active_window') and days == '30'), ('Unexpected deadline or cooldown', flag, days)
groups['single_twenty_PP_debit_and_declared_7_30_30_90_day_windows'] += 1

# Targeted decisions keep the actor in THIS/ROOT and the chosen opponent in FROM.
# Each literal is repeated in the visible readiness input and the actual effect.
for identity, topic in (('eon_select_mediation_deescalation_opponent', 1), ('eon_select_mediation_humanitarian_opponent', 2)):
    body = one(decisions, identity)
    literal = ast('set_temp_variable = { eon_mediation_proposed_topic = ' + str(topic) + ' }')
    assert one(body, 'allowed') == ast('always = yes'), 'Dynamic control is checked when visible/clicked'
    assert one(body, 'target_root_trigger') == ast('eon_mediation_draft_current = yes is_ai = no')
    assert one(body, 'target_trigger') == ast('eon_mediation_draft_current = yes FROM = { exists = yes has_war_with = PREV }')
    assert one(body, 'visible') == ast('eon_mediation_draft_current = yes is_ai = no FROM = { exists = yes has_war_with = PREV }')
    assert one(body, 'available') == literal + ast('eon_mediation_selection_ready = yes')
    assert one(body, 'complete_effect') == literal + ast('eon_mediation_send_request = yes')
    groups['literal_opponent_decision_actor_FROM_scope_and_repeated_fresh_input'] += 1
assert pp_debits == [('eon_mediation_send_request', '-20')]
assert one(one(helpers['eon_mediation_send_request'], 'if'), 'limit') == ast('eon_mediation_selection_ready = yes')
selection = helpers['eon_mediation_selection_ready']
assert ('eon_mediation_draft_current', '=', 'yes') in selection
assert ('is_ai', '=', 'no') in selection
assert ('NOT', '=', ast('has_political_power < 20')) in selection, 'Fractional PP below twenty cannot fund a request'
assert ('has_country_flag', '=', 'eon_mediation_draft_window') in selection
assert ('has_war_with', '=', 'FROM') in selection
assert one(selection, 'OR') == ast('check_variable = { eon_mediation_proposed_topic = 1 } check_variable = { eon_mediation_proposed_topic = 2 }')
opponent = one(selection, 'FROM')
assert ('exists', '=', 'yes') in opponent and ('has_war_with', '=', 'PREV') in opponent
assert ('NOT', '=', ast('has_country_flag = eon_mediation_reserved')) in opponent
groups['fresh_human_initiator_exact_affordability_reciprocal_war_and_free_opponent'] += 1

assert helpers['eon_mediation_neutral_to_actor'] == ast('exists = yes is_subject = no NOT = { tag = var:eon_mediation_actor_a } NOT = { has_war_with = var:eon_mediation_actor_a } NOT = { has_war_together_with = var:eon_mediation_actor_a } NOT = { is_in_faction_with = var:eon_mediation_actor_a }')
assert helpers['eon_mediation_conflict_current'] == ast('var:eon_mediation_party_a = { exists = yes has_war_with = var:eon_mediation_party_b } var:eon_mediation_party_b = { exists = yes has_war_with = var:eon_mediation_party_a } set_temp_variable = { eon_mediation_actor_a = eon_mediation_party_a } var:eon_mediation_mediator = { eon_mediation_neutral_to_actor = yes } set_temp_variable = { eon_mediation_actor_a = eon_mediation_party_b } var:eon_mediation_mediator = { eon_mediation_neutral_to_actor = yes }')
assert helpers['eon_mediation_request_valid'] == ast('eon_mediation_conflict_current = yes has_country_flag = eon_mediation_response_window NOT = { has_country_flag = eon_mediation_cancelled } ' + ' '.join('var:eon_mediation_' + actor + ' = { has_country_flag = eon_mediation_response_window NOT = { has_country_flag = eon_mediation_cancelled } }' for actor in ('party_a', 'party_b', 'mediator')))
groups['independent_neutral_mediator_on_both_sides_live_reciprocal_war_all_reply_windows_and_cancellation'] += 1

for action, guard, body_text in (
    ('eon_request_war_mediation', 'eon_mediation_open_ready', 'eon_mediation_prepare_draft = yes'),
    ('eon_withdraw_mediation', 'eon_mediation_withdraw_ready', 'ROOT = { eon_mediation_withdraw_record = yes }')):
    body = one(native_actions, action)
    assert one(body, 'can_be_sent') == ast(guard + ' = yes')
    assert one(body, 'complete_effect') == ast('if = { limit = { ' + guard + ' = yes } ' + body_text + ' }')
    groups['native_action_rechecks_exact_entry_guard_before_mutation'] += 1
assert one(one(helpers['eon_mediation_prepare_draft'], 'if'), 'limit') == ast('eon_mediation_open_ready = yes')
assert one(helpers['eon_mediation_open_ready'], 'ROOT') == ast('exists = yes is_ai = no has_war = yes NOT = { has_country_flag = eon_mediation_reserved }')
groups['draft_helper_repeats_live_human_origin_guard'] += 1

# Identity is structural and ignores time/liveness. A draft names exactly A/M,
# a request/mandate exactly A/B/M; all records mirror identities, phase and topic.
assert helpers['eon_mediation_origin_linked'] == ast('has_country_flag = eon_mediation_reserved check_variable = { eon_mediation_party_a = PREV.eon_mediation_party_a } check_variable = { eon_mediation_party_b = PREV.eon_mediation_party_b } check_variable = { eon_mediation_mediator = PREV.eon_mediation_mediator }')
assert helpers['eon_mediation_origin_matches'] == ast('eon_mediation_origin_linked = yes check_variable = { eon_mediation_phase = PREV.eon_mediation_phase } check_variable = { eon_mediation_topic = PREV.eon_mediation_topic }')
assert helpers['eon_mediation_owner_known'] == ast('has_country_flag = eon_mediation_reserved OR = { check_variable = { eon_mediation_party_a = THIS } check_variable = { eon_mediation_mediator = THIS } check_variable = { eon_mediation_party_b = THIS } }')
assert helpers['eon_mediation_record_current'] == ast('''eon_mediation_owner_known = yes
check_variable = { eon_mediation_party_a > 0 } check_variable = { eon_mediation_mediator > 0 }
NOT = { check_variable = { eon_mediation_party_a = eon_mediation_mediator } }
OR = {
 AND = { check_variable = { eon_mediation_phase = 0 } check_variable = { eon_mediation_topic = 0 } check_variable = { eon_mediation_party_b = 0 } }
 AND = { OR = { check_variable = { eon_mediation_phase = 1 } check_variable = { eon_mediation_phase = 2 } check_variable = { eon_mediation_phase = 3 } }
 OR = { check_variable = { eon_mediation_topic = 1 } check_variable = { eon_mediation_topic = 2 } }
 check_variable = { eon_mediation_party_b > 0 }
 NOT = { check_variable = { eon_mediation_party_b = eon_mediation_party_a } }
 NOT = { check_variable = { eon_mediation_party_b = eon_mediation_mediator } } }
}''')
assert helpers['eon_mediation_state_consistent'] == ast('eon_mediation_record_current = yes var:eon_mediation_party_a = { eon_mediation_origin_matches = yes eon_mediation_record_current = yes } var:eon_mediation_mediator = { eon_mediation_origin_matches = yes eon_mediation_record_current = yes } if = { limit = { check_variable = { eon_mediation_party_b > 0 } } var:eon_mediation_party_b = { eon_mediation_origin_matches = yes eon_mediation_record_current = yes } }')
groups['three_distinct_actor_roles_mirrored_exact_phase_topic_and_draft_two_actor_identity'] += 1

# A copied record on a nonparticipant may clear itself, but cannot erase or
# retire a real triad. Peer changes require owner membership before any scope.
release = one(helpers['eon_mediation_release_record'], 'if')
assert one(release, 'limit') == ast('has_country_flag = eon_mediation_reserved')
peers = one(release, 'if')
assert one(peers, 'limit') == ast('eon_mediation_owner_known = yes')
assert [key for key, op, value in release] == ['limit', 'if', 'eon_mediation_clear_record']
assert one(release, 'eon_mediation_clear_record') == 'yes'
peer_clears = [body for key, op, body in peers if key == 'if']
assert len(peer_clears) == 3
for actor, body in zip(('party_a', 'mediator', 'party_b'), peer_clears):
    assert body == ast('limit = { check_variable = { eon_mediation_' + actor + ' > 0 } } var:eon_mediation_' + actor + ' = { if = { limit = { NOT = { tag = PREV } eon_mediation_origin_linked = yes } eon_mediation_clear_record = yes } }')
    groups['owner_membership_and_matching_peer_before_remote_clear'] += 1
retire = one(helpers['eon_mediation_retire_response_edges'], 'if')
assert one(retire, 'limit') == ast('eon_mediation_owner_known = yes')
assert [row for row in retire if row[0] == 'set_temp_variable'] == ast('set_temp_variable = { eon_mediation_actor_a = eon_mediation_party_a } set_temp_variable = { eon_mediation_actor_b = eon_mediation_party_b } set_temp_variable = { eon_mediation_actor_m = eon_mediation_mediator }')
edges = [body for key, op, body in retire if key == 'if']
assert len(edges) == 2
for actor, body in zip(('a', 'b'), edges):
    assert body == ast('limit = { check_variable = { eon_mediation_actor_' + actor + ' > 0 } check_variable = { eon_mediation_actor_m > 0 } } var:eon_mediation_actor_m = { var:eon_mediation_actor_' + actor + ' = { set_country_flag = eon_mediation_retired_pair@PREV PREV = { set_country_flag = eon_mediation_retired_pair@PREV } } }')
    groups['owner_membership_two_callback_edges_with_frozen_scopes_and_bidirectional_PREV_tombstones'] += 1
assert helpers['eon_mediation_pair_available'] == ast('var:eon_mediation_actor_a = { NOT = { has_country_flag = eon_mediation_retired_pair@PREV } NOT = { has_country_flag = eon_mediation_recent_contact@PREV } PREV = { NOT = { has_country_flag = eon_mediation_retired_pair@PREV } NOT = { has_country_flag = eon_mediation_recent_contact@PREV } } }')
assert Counter(ttl) == Counter({('eon_mediation_draft_window', '7'): 1, ('eon_mediation_response_window', '30'): 1, ('eon_mediation_active_window', '30'): 1, ('eon_mediation_recent_contact@PREV', '90'): 4})
for path, nodes in sources.items():
    for key, op, value in rows(nodes):
        if key in ('tag', 'has_war_with', 'has_war_together_with', 'is_in_faction_with') and isinstance(value, str) and 'eon_mediation_' in value:
            assert value.startswith('var:'), ('Native country target must have explicit variable syntax', path, key, value)
            groups['native_country_targets_use_explicit_var_syntax'] += 1
        if key in ('flag', 'set_country_flag', 'has_country_flag') and isinstance(value, str) and value.startswith('eon_mediation_') and '@' in value:
            assert value.endswith('@PREV'), ('Native pair flag suffix must use an explicit country scope', path, value)
            groups['native_pair_flags_use_only_primary_backed_PREV_scopes'] += 1
groups['two_edges_pair_guards_exact_deadlines_and_four_reciprocal_cooldowns'] += 1

for role, origin, phase in (('mediator', 'party_a', 1), ('opponent', 'mediator', 2)):
    own_role = 'mediator' if role == 'mediator' else 'party_b'
    assert helpers['eon_mediation_' + role + '_pair_current'] == ast('eon_mediation_state_consistent = yes check_variable = { eon_mediation_' + own_role + ' = THIS } check_variable = { eon_mediation_' + origin + ' = FROM } check_variable = { eon_mediation_phase = ' + str(phase) + ' } check_variable = { eon_mediation_topic = eon_mediation_response_topic } OR = { check_variable = { eon_mediation_response_topic = 1 } check_variable = { eon_mediation_response_topic = 2 } }')
    assert helpers['eon_mediation_' + role + '_response_valid'] == ast('eon_mediation_' + role + '_pair_current = yes eon_mediation_request_valid = yes')
    for response in ('accept', 'refuse'):
        wrapper = one(helpers['eon_mediation_' + response + '_' + role], 'if')
        assert one(wrapper, 'limit') == ast('eon_mediation_' + role + '_pair_current = yes')
        assert one(one(wrapper, 'if'), 'limit') == ast('eon_mediation_' + role + '_response_valid = yes')
    groups['each_response_requires_named_receiver_original_FROM_phase_and_literal_topic'] += 1
for number, topic, role in ((10, 1, 'mediator'), (11, 2, 'mediator'), (20, 1, 'opponent'), (21, 2, 'opponent')):
    invite = events['eon_mediation.' + str(number)]
    assert {key for key, op, value in invite} == {'id', 'title', 'desc', 'picture', 'is_triggered_only', 'option'}, ('Invitation has hidden mutation before consent', number)
    assert one(invite, 'is_triggered_only') == 'yes'
    literal = ast('set_temp_variable = { eon_mediation_response_topic = ' + str(topic) + ' }')
    options = [value for key, op, value in invite if key == 'option']
    assert [one(body, 'name') for body in options] == ['eon_mediation_accept', 'eon_mediation_decline']
    assert one(options[0], 'trigger') == literal + ast('eon_mediation_' + role + '_response_valid = yes')
    assert one(options[1], 'trigger') == literal + ast('always = yes')
    for body, response in zip(options, ('accept', 'refuse')):
        effects = [row for row in body if row[0] not in ('name', 'trigger', 'ai_chance')]
        assert effects == literal + ast('eon_mediation_' + response + '_' + role + ' = yes')
    descriptions = [value for key, op, value in invite if key == 'desc']
    assert len(descriptions) == 3
    assert [one(body, 'trigger') for body in descriptions] == [
        literal + ast('eon_mediation_cancelled_current = yes'),
        literal + ast('eon_mediation_' + role + '_response_valid = yes NOT = { eon_mediation_cancelled_current = yes }'),
        literal + ast('NOT = { eon_mediation_' + role + '_response_valid = yes } NOT = { eon_mediation_cancelled_current = yes }')]
    positive_chance = one(options[0], 'ai_chance')
    assert positive_chance[-1] == ast('modifier = { factor = 0 set_temp_variable = { eon_mediation_response_topic = ' + str(topic) + ' } NOT = { eon_mediation_' + role + '_response_valid = yes } }')[0]
    assert float(one(one(options[1], 'ai_chance'), 'factor')) > 0
    groups['literal_sequential_consent_current_cancelled_stale_UI_and_final_AI_invalid_gate'] += 1

assert one(one(one(helpers['eon_mediation_accept_mediator'], 'if'), 'if'), 'set_variable') == ast('eon_mediation_phase = 2')
assert one(one(one(helpers['eon_mediation_accept_opponent'], 'if'), 'if'), 'set_variable') == ast('eon_mediation_phase = 3')
assert helpers['eon_mediation_force_cleanup'] == ast('eon_mediation_retire_response_edges = yes eon_mediation_release_record = yes')
assert one(one(helpers['eon_mediation_end_active'], 'if'), 'limit') == ast('eon_mediation_state_consistent = yes check_variable = { eon_mediation_phase = 3 }')
daily = one(helpers['eon_mediation_daily_cleanup'], 'if')
assert one(daily, 'if') == ast('limit = { NOT = { eon_mediation_state_consistent = yes } } eon_mediation_force_cleanup = yes')
for helper in ('eon_mediation_cleanup_annexed_pair', 'eon_mediation_cleanup_annexed_owner'):
    cleanup = one(helpers[helper], 'if')
    assert one(cleanup, 'if') == ast('limit = { eon_mediation_state_consistent = yes OR = { check_variable = { eon_mediation_phase = 0 } check_variable = { eon_mediation_phase = 3 } } } eon_mediation_release_record = yes')
    assert one(cleanup, 'else') == ast('eon_mediation_force_cleanup = yes')
    groups['annex_pending_or_malformed_forces_tombstone_consistent_draft_active_release'] += 1
groups['sequential_mediator_then_opponent_phase_and_invalid_cleanup_retire_before_erase'] += 1

hooks = one(sources['common/on_actions/eon_mediation_on_actions.txt'], 'on_actions')
assert [key for key, op, value in hooks] == ['on_daily', 'on_annex', 'on_subject_annexed']
assert one(one(hooks, 'on_daily'), 'effect') == ast('eon_mediation_daily_cleanup = yes')
for hook, dead in (('on_annex', 'FROM'), ('on_subject_annexed', 'ROOT')):
    assert one(one(hooks, hook), 'effect') == ast('every_country = { limit = { exists = yes NOT = { tag = ' + dead + ' } } set_temp_variable = { eon_mediation_annexed_partner = ' + dead + ' } eon_mediation_cleanup_annexed_pair = yes } ' + dead + ' = { eon_mediation_cleanup_annexed_owner = yes }')
    groups['native_annex_actor_scope_and_only_mediation_cleanup'] += 1

native = {'checked': False}
docs = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation')
if docs.exists():
    effects = (docs / 'effects_documentation.md').read_text(encoding='utf-8-sig')
    triggers = (docs / 'triggers_documentation.md').read_text(encoding='utf-8-sig')
    for key in ('add_political_power', 'country_event', 'set_country_flag', 'clr_country_flag', 'set_variable', 'clear_variable'):
        assert '\n## ' + key + '\n' in effects, ('Unsupported native effect API', key)
        groups['installed_primary_native_effect_APIs'] += 1
    for key in ('has_political_power', 'has_opinion', 'has_war_with', 'has_war_together_with', 'is_ai', 'is_subject', 'is_in_faction_with', 'has_country_flag', 'check_variable', 'if', 'set_temp_variable', 'add_to_temp_variable'):
        assert '\n## ' + key + '\n' in triggers, ('Unsupported native trigger API', key)
        groups['installed_primary_native_trigger_APIs'] += 1
    action_sample = (docs.parent / 'common/scripted_diplomatic_actions/scripted_diplomatic_actions.txt').read_text(encoding='utf-8-sig')
    assert 'root is the initiator of action and this is the target country' in action_sample
    for key in ('allowed', 'cost', 'requires_acceptance', 'can_be_sent', 'complete_effect', 'send_description', 'ai_desire'):
        assert key + ' = ' in action_sample, ('Native scripted diplomacy field absent from primary sample', key)
        groups['installed_primary_native_action_fields_and_scope'] += 1
    decision_sample = (docs.parent / 'common/decisions/_documentation.md').read_text(encoding='utf-8-sig')
    assert '- Scope: THIS = Country, FROM = Target Country/State' in decision_sample
    for key in ('allowed', 'visible', 'available', 'target_root_trigger', 'target_trigger'):
        assert '`' + key + '`:' in decision_sample
        groups['installed_primary_targeted_decision_fields_and_FROM_scope'] += 1
    native_decisions = docs.parent / 'common/decisions'
    flags_sample = (native_decisions / 'NOR.txt').read_text(encoding='utf-8-sig')
    variables_sample = (native_decisions / 'SWI.txt').read_text(encoding='utf-8-sig')
    assert 'set_country_flag = NOR_already_asked_a_fascist@PREV' in flags_sample
    assert 'has_country_flag = NOR_already_asked_a_fascist@PREV' in flags_sample
    assert 'has_war_with = var:SWI.SWI_angriest_country' in variables_sample
    assert 'tag = var:SWI.SWI_angriest_country' in variables_sample
    native_sprites = (docs.parent / 'interface/decisions.gfx').read_text(encoding='utf-8-sig')
    assert 'name = "GFX_decision_generic_decision"' in native_sprites
    groups['installed_primary_pair_flag_variable_country_target_and_decision_sprite_examples'] += 5
    hook_listing = (docs.parent / 'common/on_actions/_documentation.md').read_text(encoding='utf-8-sig')
    hook_examples = (docs.parent / 'common/on_actions/03_wtt_on_actions.txt').read_text(encoding='utf-8-sig')
    for key in ('on_daily', 'on_annex', 'on_subject_annexed'):
        assert '- `' + key + '`' in hook_listing
        groups['installed_primary_on_action_listing'] += 1
    assert '#ROOT is subject FROM is overlord' in hook_examples
    assert '#ROOT is winner #FROM gets annexed' in hook_examples
    groups['installed_primary_annex_scope_examples'] += 2
    native = {'checked': True, 'path': str(docs), 'not_proven': 'native callback/event timing or runtime scopes'}

print(json.dumps({'all_passed': True, 'total_cases': sum(groups.values()), 'groups': groups,
                  'baseline': BASELINE, 'new_files': receipts, 'existing_gameplay_files_preserved': len(baseline_paths),
                  'unique_action_IDs': len(actions), 'new_helper_IDs': len(helpers),
                  'new_targeted_decision_IDs': len(NEW_DECISIONS),
                  'new_locale_keys_per_language': len(locale['english']), 'native_primary_documentation': native,
                  'not_proven': 'HOI4 compilation, native scope/callback timing, decisions UI, AI selection, save/load or campaign'}, indent=2))
