"""Package 07 exact source boundaries and references; not HOI4 compilation."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '4406fc756cd91f6f2e7477d92fc87dac8c215572'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'diplomacy_package_03'))
from _support import ast, blocks, one

NEW = {
    'common/scripted_effects/eon_consultation_effects.txt',
    'common/scripted_triggers/eon_consultation_triggers.txt',
    'common/scripted_diplomatic_actions/eon_consultation_actions.txt',
    'common/on_actions/eon_consultation_on_actions.txt',
    'events/eon_consultation_events.txt',
    'localisation/english/eon_consultation_l_english.yml',
    'localisation/russian/eon_consultation_l_russian.yml',
}
NEW_ACTIONS = {
    'eon_open_economic_consultations',
    'eon_withdraw_consultation_request',
    'eon_end_economic_consultations',
    'eon_consultation_offer_economic_aid',
}
TREES = ('common', 'history', 'events', 'interface', 'gfx', 'localisation', 'music', 'map', 'sound',
         'portraits', 'tutorial', 'descriptions', 'scenario_tests', 'descriptor.mod', 'era_of_nations.mod', 'thumbnail.png')
groups, receipts, sources, helpers, helper_kinds = Counter(), [], {}, {}, {}
assert len(NEW) == 7 and len(NEW_ACTIONS) == 4

for path in sorted(NEW):
    data = (ROOT / path).read_bytes()
    assert b'\r' not in data and data.endswith(b'\n'), ('New source must use LF and final newline', path)
    assert data.startswith(b'\xef\xbb\xbf') == path.endswith('.yml'), ('New source BOM convention', path)
    assert '\ufffd' not in data.decode('utf-8-sig'), path
    if path.endswith('.txt'):
        blocks(data)
        sources[path] = ast(data)
    if '/scripted_effects/' in path or '/scripted_triggers/' in path:
        kind = 'scripted_triggers' if '/scripted_triggers/' in path else 'scripted_effects'
        for key, op, value in sources[path]:
            assert key.startswith('eon_consultation_'), ('Unowned new helper namespace', key)
            assert key not in helpers, ('Duplicate new helper ID', key)
            helpers[key], helper_kinds[key] = value, kind
    receipts.append({'path': path, 'sha256': hashlib.sha256(data).hexdigest()})
    groups['new_file_format_and_parse_boundaries'] += 1

structural_helpers = {'eon_consultation_record_role_current', 'eon_consultation_state_pair_consistent',
                      'eon_consultation_cancelled_response_current'}
assert structural_helpers <= helpers.keys(), ('Missing exclusive role and pair-bound invitation status guards', structural_helpers - helpers.keys())

# git diff hashes the tracked working-tree content against immutable baseline
# blobs. No existing gameplay file, including BOM/EOL/EOF bytes, may change.
baseline_paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, '--', *TREES], cwd=ROOT).decode().splitlines()
changed = subprocess.check_output(['git', 'diff', '--name-only', BASELINE, '--', *TREES], cwd=ROOT).decode().splitlines()
untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', *TREES], cwd=ROOT).decode().splitlines()
assert set(changed) | set(untracked) == NEW, ('Unexpected package 07 gameplay source boundary', changed, untracked)
assert not set(changed).intersection(baseline_paths), 'Existing gameplay bytes changed'
assert not NEW.intersection(baseline_paths), 'New consultation source overwrites old game files'
assert set(untracked) <= NEW
groups['all_existing_gameplay_bytes_preserved_and_exact_seven_additions'] += 1

old_actions = {b['key'] for path in baseline_paths
               if path.startswith('common/scripted_diplomatic_actions/') and path.endswith('.txt')
               for b in blocks(subprocess.check_output(['git', 'show', BASELINE + ':' + path], cwd=ROOT))
               if b['parent'] == 'scripted_diplomatic_actions' and b['depth'] == 1}
actions = [b['key'] for path in (ROOT / 'common/scripted_diplomatic_actions').glob('*.txt')
           for b in blocks(path.read_bytes()) if b['parent'] == 'scripted_diplomatic_actions' and b['depth'] == 1]
assert len(old_actions) == 58
assert len(actions) == len(set(actions)) == 62
assert set(actions) == old_actions | NEW_ACTIONS
groups['all_58_existing_native_action_IDs_and_four_additions'] += 1

native_actions = one(sources['common/scripted_diplomatic_actions/eon_consultation_actions.txt'], 'scripted_diplomatic_actions')
assert {k for k, op, value in native_actions} == NEW_ACTIONS
for key, op, body in native_actions:
    assert one(body, 'allowed') == ast('ROOT = { is_ai = no }'), ('Unsolicited AI initiation', key)
    assert one(body, 'cost') == '0', ('Consultation PP must be charged at fresh explicit send only', key)
    assert one(body, 'requires_acceptance') == 'no', ('Event invitation owns explicit agreement to talk', key)
    assert one(body, 'ai_desire') == ast('factor = 0'), ('Unexpected AI initiation desire', key)
    groups['human_native_entrypoints_zero_native_cost_and_no_AI_initiation'] += 1

locale = {}
for language in ('english', 'russian'):
    path = f'localisation/{language}/eon_consultation_l_{language}.yml'
    lines = (ROOT / path).read_text(encoding='utf-8-sig').splitlines()
    assert lines[0] == 'l_' + language + ':'
    rows = [re.fullmatch(r' ([\w.]+):0 "(.*)"', line).groups() for line in lines[1:]]
    assert len(rows) == len(dict(rows)), ('Duplicate consultation locale key', language)
    locale[language] = dict(rows)
assert locale['english'].keys() == locale['russian'].keys()
locale_counts = {}
for language in locale:
    locale_counts[language] = Counter()
    for path in (ROOT / 'localisation' / language).glob('*.yml'):
        locale_counts[language].update(re.findall(r'^ ([\w.]+):', path.read_text(encoding='utf-8-sig'), re.M))
for key in locale['english']:
    assert re.findall(r'\[.*?\]', locale['english'][key]) == re.findall(r'\[.*?\]', locale['russian'][key]), ('Bilingual placeholder mismatch', key)
    for language in locale:
        count = locale_counts[language][key]
        assert count == 1, ('Duplicate/missing global consultation locale', language, key, count)
    groups['unique_bilingual_locale_IDs_and_placeholders'] += 1
for key in NEW_ACTIONS:
    assert {key, key + '_desc'} <= locale['english'].keys(), ('Missing native action text', key)

events = {one(body, 'id'): body for key, op, body in sources['events/eon_consultation_events.txt'] if key == 'country_event'}
event_bodies = [body for key, op, body in sources['events/eon_consultation_events.txt'] if key == 'country_event']
assert len(events) == len(event_bodies), 'Duplicate consultation event identity'
notices = {f'eon_consultation.{n}' for n in range(20, 28)}
assert set(events) == notices | {'eon_consultation.0', 'eon_consultation.1', 'eon_consultation.10', 'eon_consultation.11', 'eon_consultation.12'}
for ident in sorted(notices):
    body = events[ident]
    assert one(body, 'is_triggered_only') == 'yes'
    option = one(body, 'option')
    assert [key for key, op, value in option] == ['name'], ('Queued acknowledgement mutates state', ident)
    for field in ('title', 'desc'):
        value = one(body, field)
        assert isinstance(value, str) and value in locale['english']
        assert '[' not in locale['english'][value], ('Queued notice reads mutable partner/topic', ident, field)
    assert one(option, 'name') in locale['english']
    groups['eight_static_results_and_inert_ACKs'] += 1

def rows(nodes):
    for row in nodes:
        yield row
        if isinstance(row[2], list): yield from rows(row[2])

# One explicit child makes negation unambiguous under native NOT/NOR:
# negate a conjunction by wrapping its members in an explicit AND block.
# The older source/model fixtures are not changed by this package guard.
for path, nodes in sources.items():
    for key, op, body in rows(nodes):
        if key == 'NOT':
            assert isinstance(body, list) and len(body) == 1, ('New NOT must have one explicit child/group', path, body)
            groups['all_new_negations_have_one_unambiguous_child_or_group'] += 1

# Structural identity is independent of deadlines/liveness. Exactly one role
# and its literal topic must be mirrored before a response or active-channel
# action can treat a record as current.
record_role = helpers['eon_consultation_record_role_current']
role_flags = ['eon_consultation_' + role for role in ('draft_owner', 'draft_recipient', 'outgoing', 'incoming', 'active')]
assert ('has_country_flag', '=', 'eon_consultation_reserved') in record_role
assert ('set_temp_variable', '=', ast('eon_consultation_role_count = 0')) in record_role
role_steps = [v for k, op, v in record_role if k == 'if']
assert len(role_steps) == len(role_flags)
for flag, step in zip(role_flags, role_steps):
    assert step == ast('limit = { has_country_flag = ' + flag + ' } add_to_temp_variable = { eon_consultation_role_count = 1 }')
    groups['all_five_roles_counted_once_in_fresh_invocation_frame'] += 1
assert ('check_variable', '=', ast('eon_consultation_role_count = 1')) in record_role
assert one(record_role, 'OR') == ast('''AND = { OR = { has_country_flag = eon_consultation_draft_owner has_country_flag = eon_consultation_draft_recipient } check_variable = { eon_consultation_topic = 0 } }
AND = { NOT = { OR = { has_country_flag = eon_consultation_draft_owner has_country_flag = eon_consultation_draft_recipient } }
OR = { check_variable = { eon_consultation_topic = 1 } check_variable = { eon_consultation_topic = 2 } check_variable = { eon_consultation_topic = 3 } } }''')
assert not any(k in ('exists', 'has_war_with') or (k == 'has_country_flag' and isinstance(v, str) and v.endswith('_window')) for k, op, v in rows(record_role))
groups['exclusive_role_exact_topic_and_no_liveness_or_expiry_conflation'] += 1

pair_guard = helpers['eon_consultation_state_pair_consistent']
assert pair_guard[0] == ('eon_consultation_record_role_current', '=', 'yes')
assert one(pair_guard, 'var:eon_consultation_partner') == ast('eon_consultation_record_role_current = yes check_variable = { eon_consultation_partner = PREV } check_variable = { eon_consultation_topic = PREV.eon_consultation_topic }')
complements = [('draft_owner', 'draft_recipient'), ('draft_recipient', 'draft_owner'),
               ('outgoing', 'incoming'), ('incoming', 'outgoing'), ('active', 'active')]
assert one(pair_guard, 'OR') == ast(' '.join('AND = { has_country_flag = eon_consultation_' + actor + ' var:eon_consultation_partner = { has_country_flag = eon_consultation_' + partner + ' } }' for actor, partner in complements))
groups['reciprocal_partner_topic_and_complementary_single_roles'] += 1
for helper in ('eon_consultation_draft_current', 'eon_consultation_response_pair_current', 'eon_consultation_withdraw_available',
               'eon_consultation_active_pair_current', 'eon_consultation_end_available'):
    assert ('eon_consultation_state_pair_consistent', '=', 'yes') in helpers[helper], ('Role corruption bypasses current pair gate', helper)
    groups['all_draft_reply_withdraw_active_and_end_paths_bind_consistent_pair'] += 1
assert helpers['eon_consultation_cancelled_response_current'] == ast('eon_consultation_response_pair_current = yes OR = { has_country_flag = eon_consultation_cancelled FROM = { has_country_flag = eon_consultation_cancelled } }')
groups['withdrawn_description_status_binds_immutable_response_pair'] += 1

definitions = {}
for kind in ('scripted_effects', 'scripted_triggers'):
    definitions[kind] = Counter()
    for path in (ROOT / 'common' / kind).glob('*.txt'):
        definitions[kind].update(k.decode('utf-8') for k in re.findall(rb'(?m)^[ \t]*([\w!]+)\s*=\s*{', path.read_bytes()))
for key, kind in helper_kinds.items():
    count = definitions[kind][key]
    assert count == 1, ('Duplicate global consultation helper definition', key, count)
    groups['unique_helper_IDs'] += 1

def refs(nodes, path):
    for key, op, value in rows(nodes):
        if key.startswith('eon_consultation_') and value in ('yes', 'no'):
            assert key in helpers, ('Missing consultation helper reference', path, key)
        if key in ('tooltip', 'custom_effect_tooltip', 'send_description', 'accept_description', 'reject_description', 'text', 'title', 'desc', 'name'):
            if isinstance(value, str) and value.startswith(('eon_consultation', 'eon_open_economic_consultations', 'eon_withdraw_consultation_request', 'eon_end_economic_consultations')):
                assert value in locale['english'], ('Missing consultation locale reference', path, value)
        if key == 'country_event':
            ident = one(value, 'id') if isinstance(value, list) else value
            if ident.startswith('eon_consultation.'): assert ident in events, ('Missing queued consultation event', path, ident)
for path, nodes in sources.items(): refs(nodes, path)
groups['helper_event_and_locale_references'] += 1

# A dialogue owns its own state and political preparation effort. Its positive
# result cannot become a resource, opinion, treaty, alliance or peace effect.
def effect_rows(nodes):
    for key, op, value in nodes:
        if key == 'limit':
            continue
        if key in ('if', 'else_if', 'else', 'hidden_effect', 'effect_tooltip', 'ROOT', 'THIS', 'FROM', 'PREV', 'every_country') or key.startswith('var:eon_consultation_'):
            assert isinstance(value, list), ('Expected effect block', key)
            yield from effect_rows(value)
        else:
            yield key, op, value

assert one(events['eon_consultation.0'], 'hidden') == 'yes'
assert one(events['eon_consultation.0'], 'immediate') == ast('eon_consultation_dispatch_draft = yes')
draft_options = [v for k, op, v in events['eon_consultation.1'] if k == 'option']
assert [one(body, 'name') for body in draft_options] == ['eon_consultation_topic_trade', 'eon_consultation_topic_energy', 'eon_consultation_topic_support', 'eon_consultation_cancel_agenda']
for topic, body in enumerate(draft_options[:3], 1):
    literal = ast('set_temp_variable = { eon_consultation_proposed_topic = ' + str(topic) + ' }')
    assert one(body, 'trigger') == literal + ast('eon_consultation_draft_send_ready = yes')
    effects = [row for row in body if row[0] not in ('name', 'trigger', 'ai_chance')]
    assert effects == literal + ast('eon_consultation_send_request = yes')
    assert one(body, 'ai_chance') == ast('factor = 0')
    groups['literal_human_agenda_input_fresh_click_and_disabled_AI_send'] += 1
for number, topic in ((10, 1), (11, 2), (12, 3)):
    invite = events['eon_consultation.' + str(number)]
    options = [v for k, op, v in invite if k == 'option']
    assert [one(body, 'name') for body in options] == ['eon_consultation_accept_talks', 'eon_consultation_decline_talks']
    literal = ast('set_temp_variable = { eon_consultation_response_topic = ' + str(topic) + ' }')
    descriptions = [v for k, op, v in invite if k == 'desc']
    assert len(descriptions) == 3, 'Invitation needs mutually exclusive current, cancelled and stale descriptions'
    description_triggers = [one(body, 'trigger') for body in descriptions]
    assert description_triggers[:2] == [literal + ast('eon_consultation_cancelled_response_current = yes'),
                                        literal + ast('eon_consultation_response_valid = yes')]
    assert description_triggers[2][:len(literal)] == literal
    exclusions = description_triggers[2][len(literal):]
    expected_exclusions = ast('NOT = { eon_consultation_cancelled_response_current = yes } NOT = { eon_consultation_response_valid = yes }')
    assert len(exclusions) == len(expected_exclusions) and all(row in exclusions for row in expected_exclusions)
    assert [one(body, 'text') for body in descriptions] == ['eon_consultation_cancelled_invite_desc',
                                                           'eon_consultation_' + {1: 'trade', 2: 'energy', 3: 'support'}[topic] + '_invite_desc',
                                                           'eon_consultation_stale_invite_desc']
    groups['literal_topic_mutually_exclusive_current_cancelled_stale_invitation_text'] += 1
    assert one(options[0], 'trigger') == literal + ast('eon_consultation_response_valid = yes')
    for body, effect_name in zip(options, ('eon_consultation_accept_request', 'eon_consultation_refuse_request')):
        effects = [row for row in body if row[0] not in ('name', 'trigger', 'ai_chance')]
        assert effects == literal + ast(effect_name + ' = yes')
    positive_chance = one(options[0], 'ai_chance')
    assert positive_chance[-1] == ast('modifier = { factor = 0 set_temp_variable = { eon_consultation_response_topic = ' + str(topic) + ' } NOT = { eon_consultation_response_valid = yes } }')[0]
    assert float(one(one(options[1], 'ai_chance'), 'factor')) > 0
    groups['immutable_event_topic_repeated_at_click_and_final_AI_invalid_gate'] += 1

native_mutators = {'set_variable', 'set_temp_variable', 'add_to_variable', 'add_to_temp_variable',
                   'subtract_from_variable', 'subtract_from_temp_variable', 'set_country_flag',
                   'clr_country_flag', 'clear_variable', 'add_political_power', 'country_event',
                   'custom_effect_tooltip', 'log'}
ttl, pp_debits = [], []
for helper, body in helpers.items():
    if helper_kinds[helper] != 'scripted_effects': continue
    for key, op, value in effect_rows(body):
        assert key in native_mutators or key in helpers, ('Undeclared non-consultation effect', helper, key)
        if key in ('set_variable', 'set_temp_variable', 'add_to_variable', 'add_to_temp_variable', 'subtract_from_variable', 'subtract_from_temp_variable'):
            assert all(k.startswith('eon_consultation_') for k, o, v in value), ('Another subsystem variable is mutated', helper, key)
        elif key == 'set_country_flag':
            flag = one(value, 'flag') if isinstance(value, list) else value
            assert flag.startswith('eon_consultation_'), ('Another subsystem flag is set', helper, flag)
            if isinstance(value, list): ttl.append((flag, one(value, 'days')))
        elif key in ('clr_country_flag', 'clear_variable'):
            assert value.startswith('eon_consultation_'), ('Another subsystem state is cleared', helper, value)
            assert not value.startswith('eon_consultation_retired_pair'), 'Expired invitation pair protection is cleared automatically'
        elif key == 'add_political_power': pp_debits.append((helper, value))
    groups['consultation_effect_owns_only_communication_state'] += 1
assert pp_debits == [('eon_consultation_send_request', '-10')], 'Political effort must be debited once by fresh send only'
assert one(one(helpers['eon_consultation_send_request'], 'if'), 'limit') == ast('eon_consultation_draft_send_ready = yes')
assert ('NOT', '=', ast('has_political_power < 10')) in helpers['eon_consultation_draft_send_ready'], 'Fractional PP below ten cannot fund a ten-PP request'
assert Counter(ttl) == Counter({('eon_consultation_draft_window', '7'): 2,
                               ('eon_consultation_response_window', '30'): 2,
                               ('eon_consultation_active_window', '30'): 2,
                               ('eon_consultation_recent_contact@FROM', '90'): 1,
                               ('eon_consultation_recent_contact@PREV', '90'): 1}), ('Unexpected draft/reply/active/cooldown deadlines', ttl)
groups['single_guarded_ten_PP_debit_and_declared_7_30_30_90_day_windows'] += 1

followup = one(native_actions, 'eon_consultation_offer_economic_aid')
assert one(followup, 'can_be_sent') == ast('eon_consultation_aid_followup_ready = yes')
assert one(followup, 'complete_effect') == ast('if = { limit = { eon_consultation_aid_followup_ready = yes } eon_aid_prepare_draft = yes }')
assert helpers['eon_consultation_aid_followup_ready'] == ast('eon_consultation_active_pair_current = yes check_variable = { eon_consultation_topic = 3 } eon_aid_gui_ready = yes')
for key, op, body in native_actions:
    for effect_name in ('on_sent_effect', 'complete_effect', 'reject_effect'):
        values = [v for k, o, v in body if k == effect_name]
        for value in values:
            for effect, o, v in effect_rows(value):
                assert effect in helpers or (key == 'eon_consultation_offer_economic_aid' and effect == 'eon_aid_prepare_draft'), ('Native action bypasses an existing agreement', key, effect)
groups['aid_followup_preserves_native_actor_target_guard_and_separate_grant_draft'] += 1

assert one(one(helpers['eon_consultation_end_active'], 'if'), 'limit') == ast('eon_consultation_state_pair_consistent = yes has_country_flag = eon_consultation_active')
daily = one(helpers['eon_consultation_daily_cleanup'], 'if')
invalid = one(daily, 'if')
assert one(invalid, 'limit') == ast('OR = { var:eon_consultation_partner = { exists = no } NOT = { eon_consultation_state_pair_consistent = yes } }')
assert [row for row in invalid if row[0] != 'limit'] == ast('eon_consultation_retire_pair = yes eon_consultation_release_pair = yes'), 'Invalid apparent-active state must retire known callback pair before clearing'
groups['structurally_invalid_or_dead_pair_retired_before_release_even_with_active_flag'] += 1
for helper in ('eon_consultation_cleanup_annexed_pair', 'eon_consultation_cleanup_annexed_owner'):
    cleanup = one(helpers[helper], 'if')
    retirement = one(cleanup, 'if')
    assert retirement == ast('limit = { NOT = { AND = { has_country_flag = eon_consultation_active eon_consultation_state_pair_consistent = yes } } } eon_consultation_retire_pair = yes')
    assert cleanup.index(('if', '=', retirement)) < cleanup.index(('eon_consultation_release_pair', '=', 'yes'))
    groups['annex_cleanup_treats_only_consistent_active_channel_as_consumed_reply'] += 1

hooks = one(sources['common/on_actions/eon_consultation_on_actions.txt'], 'on_actions')
assert [key for key, op, value in hooks] == ['on_daily', 'on_annex', 'on_subject_annexed']
assert one(one(hooks, 'on_daily'), 'effect') == ast('eon_consultation_daily_cleanup = yes')
for hook, dead in (('on_annex', 'FROM'), ('on_subject_annexed', 'ROOT')):
    effect = one(one(hooks, hook), 'effect')
    assert effect == ast('every_country = { limit = { exists = yes NOT = { tag = ' + dead + ' } } set_temp_variable = { eon_consultation_annexed_partner = ' + dead + ' } eon_consultation_cleanup_annexed_pair = yes } ' + dead + ' = { eon_consultation_cleanup_annexed_owner = yes }')
    groups['native_annex_actor_scope_and_only_consultation_cleanup'] += 1

native = {'checked': False}
docs = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation')
if docs.exists():
    effects = (docs / 'effects_documentation.md').read_text(encoding='utf-8-sig')
    triggers = (docs / 'triggers_documentation.md').read_text(encoding='utf-8-sig')
    for key in ('add_political_power', 'country_event', 'set_country_flag', 'clr_country_flag', 'set_variable', 'clear_variable'):
        assert '\n## ' + key + '\n' in effects, ('Unsupported native effect API', key)
        groups['installed_primary_native_effect_APIs'] += 1
    for key in ('has_political_power', 'has_opinion', 'has_war_with', 'is_ai', 'check_variable', 'has_country_flag',
                'if', 'set_temp_variable', 'add_to_temp_variable'):
        assert '\n## ' + key + '\n' in triggers, ('Unsupported native trigger API', key)
        groups['installed_primary_native_trigger_APIs'] += 1
    action_sample = (docs.parent / 'common/scripted_diplomatic_actions/scripted_diplomatic_actions.txt').read_text(encoding='utf-8-sig')
    assert 'root is the initiator of action and this is the target country' in action_sample
    assert 'root is the sender and this is receiver' in action_sample
    for key in ('allowed', 'cost', 'requires_acceptance', 'can_be_sent', 'complete_effect', 'send_description', 'ai_desire'):
        assert key + ' = ' in action_sample, ('Native scripted diplomacy field not in primary sample', key)
        groups['installed_primary_native_action_fields_and_scope'] += 1
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
                  'new_locale_keys_per_language': len(locale['english']),
                  'native_primary_documentation': native,
                  'not_proven': 'HOI4 compilation, native scope/callback timing, GUI, AI selection, save/load or campaign'}, indent=2))
