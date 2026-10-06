"""Package 09 source/API boundaries; not HOI4 compilation."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

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
BASELINE = '3b6efd83f9b1a62c7348f52d232ff0f08583a92c'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'diplomacy_package_03'))
from _support import ast, blocks, one

NEW = {
    'common/scripted_effects/eon_mediation_terms_effects.txt',
    'common/scripted_triggers/eon_mediation_terms_triggers.txt',
    'common/decisions/eon_mediation_terms_decisions.txt',
    'common/decisions/categories/eon_mediation_terms_categories.txt',
    'common/on_actions/eon_mediation_terms_on_actions.txt',
    'events/eon_mediation_terms_events.txt',
    'localisation/english/eon_mediation_terms_l_english.yml',
    'localisation/russian/eon_mediation_terms_l_russian.yml',
}
EXISTING = 'common/scripted_effects/eon_mediation_effects.txt'
CHOICES = [('deescalation', 1, 30), ('deescalation', 1, 60), ('deescalation', 1, 90),
           ('humanitarian', 2, 30), ('humanitarian', 2, 60), ('humanitarian', 2, 90)]
NEW_DECISIONS = {'eon_mediation_terms_' + topic + '_' + str(days) for topic, number, days in CHOICES} | {'eon_cancel_mediation_terms'}
TREES = ('common', 'history', 'events', 'interface', 'gfx', 'localisation', 'music', 'map', 'sound',
         'portraits', 'tutorial', 'descriptions', 'scenario_tests', 'descriptor.mod', 'era_of_nations.mod', 'thumbnail.png')
groups, receipts, sources, helpers, kinds = Counter(), [], {}, {}, {}
assert (ROOT / 'common/scripted_effects/eon_mediation_terms_effects.txt').exists(), 'RED: the consent-based mediation terms lifecycle is not implemented'

def rows(nodes):
    for row in nodes:
        yield row
        if isinstance(row[2], list): yield from rows(row[2])

for path in sorted(NEW):
    data = (ROOT / path).read_bytes()
    assert b'\r' not in data and data.endswith(b'\n'), ('New source LF/final newline', path)
    assert data.startswith(b'\xef\xbb\xbf') == path.endswith('.yml'), ('New game BOM convention', path)
    assert '\ufffd' not in data.decode('utf-8-sig'), path
    if path.endswith('.txt'):
        blocks(data)
        sources[path] = ast(data)
    if '/scripted_effects/' in path or '/scripted_triggers/' in path:
        kind = 'scripted_triggers' if '/scripted_triggers/' in path else 'scripted_effects'
        for key, op, value in sources[path]:
            assert key.startswith('eon_mediation_terms_') and key not in helpers, ('Unowned/duplicate new helper', key)
            helpers[key], kinds[key] = value, kind
    receipts.append({'path': path, 'sha256': hashlib.sha256(data).hexdigest()})
    groups['new_file_format_parse_and_owned_namespace'] += 1

before = subprocess.check_output(['git', 'show', BASELINE + ':' + EXISTING], cwd=ROOT)
actual = (ROOT / EXISTING).read_bytes()
marker = b'eon_mediation_clear_record = {\n'
hook = b' eon_mediation_terms_before_base_clear = yes\n'
assert before.count(marker) == 1 and hook not in before
assert actual == before.replace(marker, marker + hook, 1), 'Only first pre-clear hook may change package08 gameplay source'
receipts.append({'path': EXISTING, 'sha256': hashlib.sha256(actual).hexdigest(), 'all_other_bytes_exact': True})
groups['existing_package08_exact_single_insertion_before_any_identity_erase'] += 1
baseline_paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, '--', *TREES], cwd=ROOT).decode().splitlines()
changed = subprocess.check_output(['git', 'diff', '--name-only', BASELINE, '--', *TREES], cwd=ROOT).decode().splitlines()
changed = [path for path in changed if path not in LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | package14_historical_existing(BASELINE) | package15_historical_existing(BASELINE) | package16_historical_existing(BASELINE) | LATER_PACKAGE16_NEW | package17_historical_existing(BASELINE) | LATER_PACKAGE17_NEW | package18_historical_existing(BASELINE) | LATER_PACKAGE18_NEW | package19_historical_existing(BASELINE) | LATER_PACKAGE19_NEW | package20_historical_existing(BASELINE) | LATER_PACKAGE20_NEW]
untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', *TREES], cwd=ROOT).decode().splitlines()
untracked = [path for path in untracked if path not in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | LATER_PACKAGE20_NEW]
assert set(changed) | set(untracked) == NEW | {EXISTING} | LATER_PACKAGE10_NEW | LATER_PACKAGE11_NEW | LATER_PACKAGE12_NEW | LATER_PACKAGE13_NEW, ('Unowned gameplay changes', changed, untracked)
assert set(changed).intersection(baseline_paths) == {EXISTING}
assert not NEW.intersection(baseline_paths) and set(untracked) <= NEW | LATER_PACKAGE10_NEW | LATER_PACKAGE11_NEW | LATER_PACKAGE12_NEW | LATER_PACKAGE13_NEW
assert len(baseline_paths) == 68286
groups['all_68285_unrelated_gameplay_files_byte_preserved_and_exact_eight_additions'] += 1

old_actions = {b['key'] for path in baseline_paths if path.startswith('common/scripted_diplomatic_actions/') and path.endswith('.txt')
               for b in blocks(subprocess.check_output(['git', 'show', BASELINE + ':' + path], cwd=ROOT))
               if b['parent'] == 'scripted_diplomatic_actions' and b['depth'] == 1}
actions = [b['key'] for path in (ROOT / 'common/scripted_diplomatic_actions').glob('*.txt')
           for b in blocks(path.read_bytes()) if b['parent'] == 'scripted_diplomatic_actions' and b['depth'] == 1]
package10_all_actions = actions
actions = package16_historical_actions(historical_actions(actions))
assert len(actions) == len(set(actions)) == len(old_actions) == 64 and set(actions) == old_actions
actions = package10_all_actions
groups['all_64_native_action_IDs_and_bytes_preserved'] += 1

category = one(sources['common/decisions/categories/eon_mediation_terms_categories.txt'], 'eon_mediation_terms_category')
assert one(category, 'icon') == 'generic_foreign_policy' and one(category, 'allowed') == ast('always = yes')
assert one(category, 'visible') == ast('is_ai = no OR = { eon_mediation_terms_base_current = yes eon_mediation_terms_owner_known = yes }')
decisions = one(sources['common/decisions/eon_mediation_terms_decisions.txt'], 'eon_mediation_terms_category')
assert {key for key, op, value in decisions} == NEW_DECISIONS
for key, op, body in decisions:
    assert one(body, 'allowed') == ast('always = yes') and one(body, 'cost') == '0'
    assert one(body, 'ai_will_do') == ast('factor = 0')
    assert not any(k.startswith('target') or k == 'state_trigger' for k, o, v in body), 'Terms use acting THIS/ROOT normal decisions'
    groups['seven_free_human_normal_decisions_no_target_scope_or_AI_initiation'] += 1
for name, topic, days in CHOICES:
    body = one(decisions, 'eon_mediation_terms_' + name + '_' + str(days))
    literal = ast('set_temp_variable = { eon_mediation_terms_proposed_topic = ' + str(topic) + ' } set_temp_variable = { eon_mediation_terms_proposed_duration = ' + str(days) + ' }')
    assert one(body, 'visible') == ast('is_ai = no eon_mediation_terms_base_current = yes check_variable = { eon_mediation_party_a = THIS }')
    assert one(body, 'available') == literal + ast('eon_mediation_terms_send_ready = yes')
    assert one(body, 'complete_effect') == literal + ast('eon_mediation_terms_send_offer = yes')
    groups['six_literal_topic_duration_inputs_repeated_at_fresh_click'] += 1
cancel = one(decisions, 'eon_cancel_mediation_terms')
assert one(cancel, 'visible') == ast('is_ai = no eon_mediation_terms_owner_known = yes')
assert one(cancel, 'available') == ast('eon_mediation_terms_cancel_ready = yes')
assert one(cancel, 'complete_effect') == ast('eon_mediation_terms_cancel_offer = yes')
groups['active_or_pending_category_and_participant_cancel_available'] += 1

locale, locale_counts = {}, {}
for language in ('english', 'russian'):
    lines = (ROOT / f'localisation/{language}/eon_mediation_terms_l_{language}.yml').read_text(encoding='utf-8-sig').splitlines()
    assert lines[0] == 'l_' + language + ':'
    pairs = [re.fullmatch(r' ([\w.]+):0 "(.*)"', line).groups() for line in lines[1:]]
    assert len(pairs) == len(dict(pairs)), ('Duplicate locale ID', language)
    locale[language] = dict(pairs)
    locale_counts[language] = Counter()
    for path in (ROOT / 'localisation' / language).glob('*.yml'):
        locale_counts[language].update(re.findall(r'^ ([\w.]+):', path.read_text(encoding='utf-8-sig'), re.M))
assert locale['english'].keys() == locale['russian'].keys()
for key in locale['english']:
    assert re.findall(r'\[.*?\]', locale['english'][key]) == re.findall(r'\[.*?\]', locale['russian'][key]), ('Placeholder mismatch', key)
    assert all(locale_counts[language][key] == 1 for language in locale), ('Duplicate global locale', key)
    groups['unique_bilingual_locale_IDs_and_placeholders'] += 1
for key in NEW_DECISIONS | {'eon_mediation_terms_category'}:
    assert {key, key + '_desc'} <= locale['english'].keys()

event_bodies = [body for key, op, body in sources['events/eon_mediation_terms_events.txt'] if key == 'country_event']
events = {one(body, 'id'): body for body in event_bodies}
notices = {f'eon_mediation_terms.{n}' for n in range(30, 36)}
assert len(events) == len(event_bodies) == 18
assert set(events) == notices | {f'eon_mediation_terms.{n}' for n in (*range(10, 16), *range(20, 26))}
for ident, body in events.items():
    assert {key for key, op, value in body} == {'id', 'title', 'desc', 'picture', 'is_triggered_only', 'option'}, ('Hidden pre-consent event mutation', ident)
    assert one(body, 'is_triggered_only') == 'yes'
    if ident in notices:
        option = one(body, 'option')
        assert [key for key, op, value in option] == ['name']
        for field in ('title', 'desc'):
            text = one(body, field)
            assert isinstance(text, str) and text in locale['english'] and '[' not in locale['english'][text]
        assert one(option, 'name') in locale['english']
        groups['six_static_results_and_inert_ACKs'] += 1
for role, start in (('mediator', 10), ('opponent', 20)):
    for offset, (name, topic, days) in enumerate(CHOICES):
        invite = events['eon_mediation_terms.' + str(start + offset)]
        literal = ast('set_temp_variable = { eon_mediation_terms_response_topic = ' + str(topic) + ' } set_temp_variable = { eon_mediation_terms_response_duration = ' + str(days) + ' }')
        options = [value for key, op, value in invite if key == 'option']
        assert [one(body, 'name') for body in options] == ['eon_mediation_terms_accept', 'eon_mediation_terms_decline']
        assert one(options[0], 'trigger') == literal + ast('eon_mediation_terms_' + role + '_response_valid = yes')
        assert one(options[1], 'trigger') == literal + ast('always = yes')
        for body, response in zip(options, ('accept', 'refuse')):
            assert [row for row in body if row[0] not in ('name', 'trigger', 'ai_chance')] == literal + ast('eon_mediation_terms_' + response + '_' + role + ' = yes')
        descriptions = [value for key, op, value in invite if key == 'desc']
        assert len(descriptions) == 3
        assert [one(body, 'trigger') for body in descriptions] == [literal + ast('eon_mediation_terms_cancelled_current = yes'),
            literal + ast('eon_mediation_terms_' + role + '_response_valid = yes NOT = { eon_mediation_terms_cancelled_current = yes }'),
            literal + ast('NOT = { eon_mediation_terms_' + role + '_response_valid = yes } NOT = { eon_mediation_terms_cancelled_current = yes }')]
        assert one(options[0], 'ai_chance')[-1] == ast('modifier = { factor = 0 ' + 'set_temp_variable = { eon_mediation_terms_response_topic = ' + str(topic) + ' } set_temp_variable = { eon_mediation_terms_response_duration = ' + str(days) + ' } NOT = { eon_mediation_terms_' + role + '_response_valid = yes } }')[0]
        assert float(one(one(options[1], 'ai_chance'), 'factor')) > 0
        groups['twelve_literal_stage_consent_current_cancelled_stale_UI_final_AI_gate'] += 1

definitions = {}
for kind in ('scripted_effects', 'scripted_triggers'):
    definitions[kind] = Counter()
    for path in (ROOT / 'common' / kind).glob('*.txt'):
        definitions[kind].update(k.decode('utf-8') for k in re.findall(rb'(?m)^[ \t]*([\w!]+)\s*=\s*{', path.read_bytes()))
for key, kind in kinds.items():
    assert definitions[kind][key] == 1, ('Duplicate helper definition', key)
    groups['unique_helper_IDs'] += 1
event_counts = Counter()
for path in (ROOT / 'events').glob('*.txt'):
    event_counts.update(re.findall(r'\bid\s*=\s*(eon_mediation_terms\.[\w]+)', path.read_text(encoding='utf-8-sig')))
for ident in events:
    assert event_counts[ident] == 1, ('Duplicate global event', ident)
    groups['unique_global_terms_event_IDs'] += 1
for ident in NEW_DECISIONS:
    assert sum(len(re.findall(rb'\b' + ident.encode() + rb'\s*=\s*{', path.read_bytes())) for path in (ROOT / 'common/decisions').glob('*.txt')) == 1
    groups['unique_global_terms_decision_IDs'] += 1
for path, nodes in sources.items():
    for key, op, value in rows(nodes):
        if key.startswith('eon_mediation_terms_') and value in ('yes', 'no'):
            assert key in helpers, ('Missing terms helper', path, key)
        if key == 'NOT':
            assert isinstance(value, list) and len(value) == 1, ('Native NOT/NOR requires one explicit child/group', path, value)
            groups['all_new_negations_have_one_explicit_child_or_group'] += 1
        if key in ('tooltip', 'custom_effect_tooltip', 'text', 'title', 'desc', 'name') and isinstance(value, str) and value.startswith(('eon_mediation_terms', 'eon_cancel_mediation_terms')):
            assert value in locale['english'], ('Missing locale reference', path, value)
        if key == 'country_event':
            ident = one(value, 'id') if isinstance(value, list) else value
            if ident.startswith('eon_mediation_terms.'): assert ident in events
        if key in ('tag', 'has_war_with', 'has_war_together_with', 'is_in_faction_with') and isinstance(value, str) and 'eon_mediation_' in value:
            assert value.startswith('var:'), ('Variable country target needs explicit native syntax', path, value)
        if key in ('flag', 'set_country_flag', 'has_country_flag') and isinstance(value, str) and value.startswith('eon_mediation_terms_') and '@' in value:
            assert value.endswith('@PREV'), ('Pair flag needs explicit country scope', path, value)
groups['owned_helpers_event_locale_refs_and_native_target_syntax'] += 1

# The semantic ownership checks below are separate from native runtime proof.
def effect_rows(nodes):
    for key, op, value in nodes:
        if key == 'limit': continue
        if key in ('if', 'else_if', 'else', 'hidden_effect', 'effect_tooltip', 'ROOT', 'THIS', 'FROM', 'PREV', 'every_country') or key.startswith('var:eon_mediation_terms_'):
            assert isinstance(value, list), ('Expected effect scope/group', key)
            yield from effect_rows(value)
        else: yield key, op, value

mutators = {'set_variable', 'set_temp_variable', 'set_country_flag', 'clr_country_flag', 'clear_variable', 'country_event'}
ttl = []
for helper, body in helpers.items():
    if kinds[helper] != 'scripted_effects': continue
    for key, op, value in effect_rows(body):
        assert key in mutators or (key in helpers and kinds[key] == 'scripted_effects'), ('Terms call an unowned resource/peace/treaty effect or trigger-as-effect', helper, key)
        if key in ('set_variable', 'set_temp_variable'):
            assert all(k.startswith('eon_mediation_terms_') or (helper == 'eon_mediation_terms_apply_accepted' and k == 'eon_mediation_topic') for k, o, v in value), ('Unowned variable mutation', helper, value)
        elif key == 'set_country_flag':
            flag = one(value, 'flag') if isinstance(value, list) else value
            assert flag.startswith('eon_mediation_terms_') or (helper == 'eon_mediation_terms_apply_accepted' and flag == 'eon_mediation_active_window'), ('Unowned flag mutation', helper, flag)
            if isinstance(value, list): ttl.append((flag, one(value, 'days')))
        elif key in ('clr_country_flag', 'clear_variable'):
            assert value.startswith('eon_mediation_terms_') or (helper == 'eon_mediation_terms_apply_accepted' and value == 'eon_mediation_active_window')
            assert not value.startswith('eon_mediation_terms_retired_pair'), 'Forced unanswered protection is never automatically cleared'
    groups['effects_own_only_terms_and_final_agreed_topic_window_no_PP_or_resources'] += 1
assert Counter(ttl) == Counter({('eon_mediation_terms_response_window', '30'): 4,
                               ('eon_mediation_active_window', '30'): 1,
                               ('eon_mediation_active_window', '60'): 1,
                               ('eon_mediation_active_window', '90'): 1})
groups['four_reply_window_writes_and_three_literal_final_duration_branches'] += 1

assert helpers['eon_mediation_terms_owner_known'] == ast('has_country_flag = eon_mediation_terms_reserved OR = { check_variable = { eon_mediation_terms_a = THIS } check_variable = { eon_mediation_terms_b = THIS } check_variable = { eon_mediation_terms_m = THIS } }')
assert helpers['eon_mediation_terms_origin_linked'] == ast('has_country_flag = eon_mediation_terms_reserved ' + ' '.join('check_variable = { eon_mediation_terms_' + actor + ' = PREV.eon_mediation_terms_' + actor + ' }' for actor in ('a', 'b', 'm')))
assert helpers['eon_mediation_terms_origin_matches'] == ast('eon_mediation_terms_origin_linked = yes ' + ' '.join('check_variable = { eon_mediation_terms_' + field + ' = PREV.eon_mediation_terms_' + field + ' }' for field in ('topic', 'duration', 'stage')))
assert helpers['eon_mediation_terms_record_current'] == ast('''eon_mediation_terms_owner_known = yes
check_variable = { eon_mediation_terms_a > 0 } check_variable = { eon_mediation_terms_b > 0 } check_variable = { eon_mediation_terms_m > 0 }
NOT = { check_variable = { eon_mediation_terms_a = eon_mediation_terms_b } }
NOT = { check_variable = { eon_mediation_terms_a = eon_mediation_terms_m } }
NOT = { check_variable = { eon_mediation_terms_b = eon_mediation_terms_m } }
OR = { check_variable = { eon_mediation_terms_stage = 1 } check_variable = { eon_mediation_terms_stage = 2 } }
OR = { check_variable = { eon_mediation_terms_topic = 1 } check_variable = { eon_mediation_terms_topic = 2 } }
OR = { check_variable = { eon_mediation_terms_duration = 30 } check_variable = { eon_mediation_terms_duration = 60 } check_variable = { eon_mediation_terms_duration = 90 } }''')
assert helpers['eon_mediation_terms_state_consistent'] == ast('eon_mediation_terms_record_current = yes ' + ' '.join('var:eon_mediation_terms_' + actor + ' = { eon_mediation_terms_origin_matches = yes eon_mediation_terms_record_current = yes }' for actor in ('a', 'b', 'm')))
assert helpers['eon_mediation_terms_base_current'] == ast('eon_mediation_state_consistent = yes check_variable = { eon_mediation_phase = 3 } eon_mediation_conflict_current = yes has_country_flag = eon_mediation_active_window NOT = { has_country_flag = eon_mediation_cancelled } ' + ' '.join('var:eon_mediation_' + actor + ' = { has_country_flag = eon_mediation_active_window NOT = { has_country_flag = eon_mediation_cancelled } }' for actor in ('party_a', 'party_b', 'mediator')))
assert helpers['eon_mediation_terms_base_matches'] == ast('eon_mediation_terms_base_current = yes check_variable = { eon_mediation_party_a = eon_mediation_terms_a } check_variable = { eon_mediation_party_b = eon_mediation_terms_b } check_variable = { eon_mediation_mediator = eon_mediation_terms_m }')
groups['three_distinct_owned_mirrored_terms_records_and_all_live_original_active_windows'] += 1
assert one(one(helpers['eon_mediation_terms_send_offer'], 'if'), 'limit') == ast('eon_mediation_terms_send_ready = yes')
send = helpers['eon_mediation_terms_send_ready']
assert ('exists', '=', 'yes') in send and ('is_ai', '=', 'no') in send
assert ('eon_mediation_terms_base_current', '=', 'yes') in send
assert ('check_variable', '=', ast('eon_mediation_party_a = THIS')) in send
assert ('NOT', '=', ast('has_country_flag = eon_mediation_terms_reserved')) in send
for actor in ('party_b', 'mediator'):
    bodies = [value for key, op, value in send if key == 'var:eon_mediation_' + actor]
    assert ast('NOT = { has_country_flag = eon_mediation_terms_reserved }') in bodies
assert helpers['eon_mediation_terms_pair_available'] == ast('var:eon_mediation_terms_actor_a = { NOT = { has_country_flag = eon_mediation_terms_retired_pair@PREV } PREV = { NOT = { has_country_flag = eon_mediation_terms_retired_pair@PREV } } }')
groups['fresh_human_A_send_one_outstanding_offer_and_terms_only_pair_retirement'] += 1
assert helpers['eon_mediation_terms_literal_current'] == ast('check_variable = { eon_mediation_terms_topic = eon_mediation_terms_response_topic } check_variable = { eon_mediation_terms_duration = eon_mediation_terms_response_duration } OR = { check_variable = { eon_mediation_terms_response_topic = 1 } check_variable = { eon_mediation_terms_response_topic = 2 } } OR = { check_variable = { eon_mediation_terms_response_duration = 30 } check_variable = { eon_mediation_terms_response_duration = 60 } check_variable = { eon_mediation_terms_response_duration = 90 } }')
for role, own, origin, stage in (('mediator', 'm', 'a', 1), ('opponent', 'b', 'm', 2)):
    assert helpers['eon_mediation_terms_' + role + '_pair_current'] == ast('eon_mediation_terms_state_consistent = yes check_variable = { eon_mediation_terms_' + own + ' = THIS } check_variable = { eon_mediation_terms_' + origin + ' = FROM } check_variable = { eon_mediation_terms_stage = ' + str(stage) + ' } eon_mediation_terms_literal_current = yes')
    assert helpers['eon_mediation_terms_' + role + '_response_valid'] == ast('eon_mediation_terms_' + role + '_pair_current = yes eon_mediation_terms_offer_valid = yes')
    for response in ('accept', 'refuse'):
        wrapper = one(helpers['eon_mediation_terms_' + response + '_' + role], 'if')
        assert one(wrapper, 'limit') == ast('eon_mediation_terms_' + role + '_pair_current = yes')
        assert one(one(wrapper, 'if'), 'limit') == ast('eon_mediation_terms_' + role + '_response_valid = yes')
    groups['M_then_B_identity_original_FROM_stage_and_literal_response_rechecked'] += 1
assert helpers['eon_mediation_terms_offer_valid'] == ast('eon_mediation_terms_base_matches = yes has_country_flag = eon_mediation_terms_response_window NOT = { has_country_flag = eon_mediation_terms_cancelled } ' + ' '.join('var:eon_mediation_terms_' + actor + ' = { has_country_flag = eon_mediation_terms_response_window NOT = { has_country_flag = eon_mediation_terms_cancelled } }' for actor in ('a', 'b', 'm')))
groups['all_three_reply_windows_and_cancellation_flags_block_stale_acceptance'] += 1

apply = helpers['eon_mediation_terms_apply_accepted']
assert apply[:2] == ast('set_variable = { eon_mediation_topic = eon_mediation_terms_topic } clr_country_flag = eon_mediation_active_window')
assert apply[2:] == ast('if = { limit = { check_variable = { eon_mediation_terms_duration = 30 } } set_country_flag = { flag = eon_mediation_active_window days = 30 value = 1 } } else_if = { limit = { check_variable = { eon_mediation_terms_duration = 60 } } set_country_flag = { flag = eon_mediation_active_window days = 60 value = 1 } } else_if = { limit = { check_variable = { eon_mediation_terms_duration = 90 } } set_country_flag = { flag = eon_mediation_active_window days = 90 value = 1 } }')
commit = one(one(helpers['eon_mediation_terms_accept_opponent'], 'if'), 'if')
assert [row for row in commit if row[0] != 'limit'] == ast('var:eon_mediation_terms_a = { eon_mediation_terms_apply_accepted = yes } var:eon_mediation_terms_m = { eon_mediation_terms_apply_accepted = yes } eon_mediation_terms_apply_accepted = yes eon_mediation_terms_notice_34 = yes eon_mediation_terms_release_record = yes')
groups['final_B_consent_updates_all_three_topics_literal_windows_without_partial_guard'] += 1

assert helpers['eon_mediation_terms_force_cleanup'] == ast('eon_mediation_terms_retire_response_edges = yes eon_mediation_terms_release_record = yes')
assert helpers['eon_mediation_terms_before_base_clear'] == ast('if = { limit = { has_country_flag = eon_mediation_terms_reserved } eon_mediation_terms_force_cleanup = yes }')
release = one(helpers['eon_mediation_terms_release_record'], 'if')
assert one(release, 'limit') == ast('has_country_flag = eon_mediation_terms_reserved')
peers = one(release, 'if')
assert one(peers, 'limit') == ast('eon_mediation_terms_owner_known = yes')
for actor in ('a', 'b', 'm'):
    assert one(peers, 'var:eon_mediation_terms_' + actor) == ast('if = { limit = { NOT = { tag = PREV } eon_mediation_terms_origin_linked = yes } eon_mediation_terms_clear_record = yes }')
assert [key for key, op, value in release] == ['limit', 'if', 'eon_mediation_terms_clear_record']
retire = one(helpers['eon_mediation_terms_retire_response_edges'], 'if')
assert one(retire, 'limit') == ast('eon_mediation_terms_owner_known = yes')
edges = [value for key, op, value in retire if key == 'if']
assert len(edges) == 2
for actor, edge in zip(('a', 'b'), edges):
    assert edge == ast('limit = { check_variable = { eon_mediation_terms_actor_' + actor + ' > 0 } check_variable = { eon_mediation_terms_actor_m > 0 } } var:eon_mediation_terms_actor_m = { var:eon_mediation_terms_actor_' + actor + ' = { set_country_flag = eon_mediation_terms_retired_pair@PREV PREV = { set_country_flag = eon_mediation_terms_retired_pair@PREV } } }')
    groups['owner_bound_both_terms_edges_bidirectional_PREV_tombstones_before_release'] += 1
groups['normal_release_no_retirement_or_recursive_base_clear'] += 1
hooks = one(sources['common/on_actions/eon_mediation_terms_on_actions.txt'], 'on_actions')
assert hooks == ast('on_daily = { effect = { eon_mediation_terms_daily_cleanup = yes } }')
groups['daily_overlay_and_pre_clear_hook_no_duplicate_annex_handlers'] += 1

# Only dependency definitions are loaded into the historical 08 executor. Its
# original scenarios/assertions and model semantics remain byte-identical.
adapter_path = 'tools/validation/diplomacy_package_08/test_mediation.py'
adapter = (ROOT / adapter_path).read_bytes()
original = subprocess.check_output(['git', 'show', BASELINE + ':' + adapter_path], cwd=ROOT)
addition = b"# Package09 dependency adapter: load only the new helpers needed by the single pre-clear hook.\nfor registry, path in (('effects', 'common/scripted_effects/eon_mediation_terms_effects.txt'),\n                       ('capacity_triggers', 'common/scripted_triggers/eon_mediation_terms_triggers.txt')):\n    dependencies = {key: body for key, operator, body in ast(read(path))}\n    assert not dependencies.keys() & model[registry].keys(), 'New terms helpers overwrite an existing helper'\n    model[registry].update(dependencies)\n"
if b'\r\n' in original: addition = addition.replace(b'\n', b'\r\n')
assert adapter.count(addition) == 1 and adapter.replace(addition, b'', 1) == original
groups['historical08_dependency_only_adapter_preserves_all_original_model_and_assertions'] += 1

native = {'checked': False}
docs = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation')
if docs.exists():
    effects = (docs / 'effects_documentation.md').read_text(encoding='utf-8-sig')
    triggers = (docs / 'triggers_documentation.md').read_text(encoding='utf-8-sig')
    for key in ('country_event', 'set_country_flag', 'clr_country_flag', 'set_variable', 'set_temp_variable', 'clear_variable'):
        assert '\n## ' + key + '\n' in effects, ('Unsupported native effect', key)
        groups['installed_primary_native_effect_API'] += 1
    for key in ('check_variable', 'has_country_flag', 'if', 'is_ai', 'set_temp_variable'):
        assert '\n## ' + key + '\n' in triggers
        groups['installed_primary_native_trigger_API'] += 1
    decision_docs = (docs.parent / 'common/decisions/_documentation.md').read_text(encoding='utf-8-sig')
    assert '- Scope: THIS = Country\n' in decision_docs
    for key in ('allowed', 'visible', 'available'): assert '`' + key + '`:' in decision_docs
    flags = (docs.parent / 'common/decisions/NOR.txt').read_text(encoding='utf-8-sig')
    assert 'set_country_flag = NOR_already_asked_a_fascist@PREV' in flags and 'has_country_flag = NOR_already_asked_a_fascist@PREV' in flags
    sprites = (docs.parent / 'interface/decisions.gfx').read_text(encoding='utf-8-sig')
    assert 'name = "GFX_decision_generic_decision"' in sprites
    assert any(b'GFX_decision_category_generic_foreign_policy' in path.read_bytes() for path in (ROOT / 'interface').glob('*.gfx'))
    hook_docs = (docs.parent / 'common/on_actions/_documentation.md').read_text(encoding='utf-8-sig')
    assert '- `on_daily`' in hook_docs
    groups['installed_primary_normal_decision_PREV_flags_existing_sprites_and_daily_API'] += 5
    # Native source stores an unqualified country-valued temp in one scope and
    # reads it through var: after returning to PREV and entering a state scope.
    scope_sample = (docs.parent / 'common/scripted_effects/00_scripted_effects.txt').read_text(encoding='utf-8-sig')
    assert re.search(r'set_temp_variable\s*=\s*{\s*new_country\s*=\s*this\s*}\s*PREV\s*=\s*{\s*every_controlled_state\s*=\s*{\s*limit\s*=\s*{\s*occupied_country_tag\s*=\s*country_to_initiate\s*}\s*var:new_country\s*=\s*{', scope_sample)
    operation_sample = (docs.parent / 'common/scripted_effects/operation_strat_effects.txt').read_text(encoding='utf-8-sig')
    assert 'set_temp_variable = { captor = operative_captor }' in operation_sample
    assert 'set_variable = { rescue_operative_from = captor }' in operation_sample
    groups['installed_primary_unqualified_temp_visibility_across_native_country_state_and_operative_scopes'] += 2
    native = {'checked': True, 'path': str(docs), 'not_proven': 'native event callback timing or runtime scope binding'}

print(json.dumps({'all_passed': True, 'total_cases': sum(groups.values()), 'groups': groups, 'baseline': BASELINE,
                  'new_files': [r for r in receipts if r['path'] in NEW], 'owned_existing_files': [r for r in receipts if r['path'] == EXISTING],
                  'final_gameplay_sha256': {r['path']: r['sha256'] for r in receipts},
                  'existing_gameplay_files_byte_preserved': len(baseline_paths) - 1,
                  'unique_native_action_IDs': len(actions), 'new_helper_IDs': len(helpers), 'new_decision_IDs': len(NEW_DECISIONS),
                  'new_locale_keys_per_language': len(locale['english']), 'native_primary_documentation': native,
                  'not_proven': 'HOI4 compilation, native callback scopes/timing, GUI, AI probability, arbitrary duplicates of consumed events, save/load or campaign'}, indent=2))
