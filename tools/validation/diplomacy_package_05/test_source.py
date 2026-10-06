"""Exact package05 boundaries and primary native APIs; not HOI4 compilation."""
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
BASELINE = '688f1116fbcb377215181edca6af50f36538532e'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'diplomacy_package_03'))
from _support import ast, blocks, format_preserved, one
groups = Counter()
receipts = []

def before(path): return subprocess.check_output(['git', 'show', BASELINE + ':' + path], cwd=ROOT)

def restore(after, old, select):
    previous = {select(old, b): b for b in blocks(old) if select(old, b)}
    current = {select(after, b): b for b in blocks(after) if select(after, b)}
    assert previous.keys() == current.keys(), (previous.keys(), current.keys())
    for key, b in sorted(current.items(), key=lambda item: item[1]['start'], reverse=True):
        prior = previous[key]
        after = after[:b['start']] + old[prior['start']:prior['end']] + after[b['end']:]
    return after

def record(path, old, after):
    format_preserved(old, after)
    receipts.append({'path': path, 'sha256': hashlib.sha256(after).hexdigest(), 'unrelated_bytes_exact': True})
    groups['exact_owned_existing_boundaries'] += 1

path = 'events/00_Energy_market_events.txt'
old, after = before(path), (ROOT / path).read_bytes()
def event_select(data, b):
    if b['key'] == 'country_event' and b['depth'] == 0:
        ident = one(ast(data[b['start']:b['end']])[0][2], 'id')
        return ident if ident in ('energy_selling.1', 'energy_selling.4') else None
assert restore(after, old, event_select) == old, 'Unrelated energy events changed'
record(path, old, after)
old_events = {one(body, 'id'): body for key, op, body in ast(old) if key == 'country_event'}
events = {one(body, 'id'): body for key, op, body in ast(after) if key == 'country_event'}
assert old_events.keys() == events.keys()
for ident in ('energy_selling.1', 'energy_selling.4'):
    names = [one(v, 'name') for k, o, v in events[ident] if k == 'option']
    assert names == [ident + '.a', ident + '.b', 'eon_energy_counter_offer']
    assert one(events[ident], 'immediate') == ast('eon_energy_evaluate_offer = yes eon_energy_prepare_ai_counter = yes')
    groups['preserved_event_ids_and_three_response_options'] += 1

path = 'common/scripted_effects/eon_energy_contract_effects.txt'
old, after = before(path), (ROOT / path).read_bytes()
owned_helpers = {'eon_energy_clear_pending', 'eon_energy_invalidate_pair_pending', 'eon_energy_send_offer',
                 'eon_energy_validate_offer', 'eon_energy_finish_response', 'eon_energy_accept_offer'}
assert restore(after, old, lambda d, b: b['key'] if b['depth'] == 0 and b['key'] in owned_helpers else None) == old
record(path, old, after)
old_accept, accept = one(ast(old), 'eon_energy_accept_offer'), one(ast(after), 'eon_energy_accept_offer')
assert one(old_accept, 'if') == one(accept, 'if'), 'Bilateral acceptance accounting changed'
groups['accepted_delivery_accounting_exact'] += 1

path = 'common/scripted_guis/01_energy_gui.txt'
old, after = before(path), (ROOT / path).read_bytes()
addition = (b'\t\t\tcountry_view_flag_button_click_enabled = {\n'
            b'\t\t\t\tcustom_trigger_tooltip = { tooltip = eon_energy_counter_partner_locked_tt NOT = { has_country_flag = eon_energy_counter_draft_owner } }\n'
            b'\t\t\t}\n')
assert after.count(addition) == 1 and addition not in old
restored = after.replace(addition, b'')
def gui_select(data, b):
    if b['depth'] == 3 and b['parent'] in ('effects', 'triggers') and b['key'] in {
            'confirm_energy_sell_click', 'confirm_energy_sell_click_enabled', 'country_view_flag_button_click'}:
        return b['key']
    if b['key'] == 'country_list_flag_button_click' and b['parent'] == 'effects':
        gui = next(x for x in blocks(data) if x['key'] == 'energy_sell_country_selection_gui')
        if gui['start'] < b['start'] < gui['end']: return 'energy_country_selection'
assert restore(restored, old, gui_select) == old, 'Unrelated generation/nuclear GUI bytes changed'
record(path, old, after)

for lang in ('english', 'russian'):
    path = f'localisation/{lang}/eon_energy_contract_l_{lang}.yml'
    old, after = before(path), (ROOT / path).read_bytes()
    pattern = rb'(?m)^ eon_energy_offer_cancelled_desc:0 "[^\r\n]*"'
    prior, current = re.findall(pattern, old), re.findall(pattern, after)
    assert len(prior) == len(current) == 1 and after.replace(current[0], prior[0]) == old
    record(path, old, after)

new = {
    'common/scripted_effects/eon_energy_ai_effects.txt',
    'common/scripted_effects/eon_energy_negotiation_effects.txt',
    'common/scripted_triggers/eon_energy_negotiation_triggers.txt',
    'common/scripted_diplomatic_actions/eon_energy_negotiation_actions.txt',
    'events/eon_energy_negotiation_events.txt',
    'localisation/english/eon_energy_negotiation_l_english.yml',
    'localisation/russian/eon_energy_negotiation_l_russian.yml',
}
helper_ids = []
for path in sorted(new):
    data = (ROOT / path).read_bytes()
    assert b'\r' not in data and data.endswith(b'\n') and '\ufffd' not in data.decode('utf-8-sig')
    assert data.startswith(b'\xef\xbb\xbf') == path.endswith('.yml')
    if path.endswith('.txt'): blocks(data)
    if '/scripted_effects/' in path or '/scripted_triggers/' in path:
        helper_ids += [k for k, o, v in ast(data)]
    groups['new_file_format'] += 1
assert len(helper_ids) == len(set(helper_ids))
for helper in helper_ids:
    directory = 'scripted_triggers' if helper in {k for k, o, v in ast((ROOT / 'common/scripted_triggers/eon_energy_negotiation_triggers.txt').read_bytes())} else 'scripted_effects'
    count = sum(len(re.findall(rb'(?m)^' + helper.encode() + rb'\s*=\s*{', p.read_bytes()))
                for p in (ROOT / 'common' / directory).glob('*.txt'))
    assert count == 1, ('Duplicate helper ID', helper, count)
    groups['unique_native_helper_ids'] += 1

# Extraction must retain the prior policy in order; the only policy change is
# replacing the last raw-GW bonus with its explicitly bounded 0..20 form.
ai = ast((ROOT / 'common/scripted_effects/eon_energy_ai_effects.txt').read_bytes())
def rename(nodes):
    names = {'eon_energy_offer_amount': 'eon_energy_ai_amount', 'eon_energy_offer_price': 'eon_energy_ai_price',
             'eon_energy_offer_quantity': 'eon_energy_ai_quantity'}
    return [(names.get(k, k), o, rename(v) if isinstance(v, list) else names.get(v, v)) for k, o, v in nodes]
bonus = ast('set_temp_variable = { eon_energy_ai_volume_bonus = eon_energy_ai_quantity } '
            'clamp_temp_variable = { var = eon_energy_ai_volume_bonus min = 0 max = 20 } '
            'add_to_variable = { eon_energy_ai_accept_chance = eon_energy_ai_volume_bonus }')
for ident, helper in (('energy_selling.1', 'eon_energy_assess_import_offer'), ('energy_selling.4', 'eon_energy_assess_export_offer')):
    original = one(old_events[ident], 'immediate')
    raw_quantity = 'eon_energy_offer_amount' if ident.endswith('.1') else 'eon_energy_offer_quantity'
    assert original[-1] == ast('add_to_variable = { eon_energy_ai_accept_chance = ' + raw_quantity + ' }')[0]
    assert one(ai, helper) == rename(original[:-1]) + bonus, 'Additional AI policy change'
    groups['exact_prior_ai_policy_except_bounded_bonus'] += 1

actions = one(ast((ROOT / 'common/scripted_diplomatic_actions/eon_energy_negotiation_actions.txt').read_bytes()), 'scripted_diplomatic_actions')
assert {k for k, o, v in actions} == {'eon_withdraw_energy_offer', 'eon_resume_energy_counter_offer'}
for key, op, body in actions:
    assert one(body, 'requires_acceptance') == 'no' and one(body, 'cost') == '0'
    assert one(body, 'ai_desire') == ast('factor = 0')
    groups['zero_cost_manual_action_structure'] += 1

notices = {one(v, 'id'): v for k, o, v in ast((ROOT / 'events/eon_energy_negotiation_events.txt').read_bytes()) if k == 'country_event'}
assert set(notices) == {f'eon_energy_negotiation.{i}' for i in (10, 11, 12, 13, 14, 15, 16, 17, 19)}
locale = {}
for lang in ('english', 'russian'):
    text = (ROOT / f'localisation/{lang}/eon_energy_negotiation_l_{lang}.yml').read_text(encoding='utf-8-sig')
    assert text.splitlines()[0] == 'l_' + lang + ':'
    rows = [re.fullmatch(r' ([\w.]+):0 "(.*)"', line).groups() for line in text.splitlines()[1:]]
    assert len(rows) == len(dict(rows)); locale[lang] = dict(rows)
assert locale['english'].keys() == locale['russian'].keys()
for key in locale['english']:
    assert re.findall(r'\[.*?\]', locale['english'][key]) == re.findall(r'\[.*?\]', locale['russian'][key])
    for lang in locale:
        count = sum(len(re.findall(r'^ ' + re.escape(key) + ':', p.read_text(encoding='utf-8-sig'), re.M))
                    for p in (ROOT / 'localisation' / lang).glob('*.yml'))
        assert count == 1, ('Locale ID collision', key, lang, count)
    groups['unique_bilingual_locale_ids'] += 1
for ident, body in notices.items():
    assert isinstance(one(body, 'desc'), str)
    assert '[' not in locale['english'][one(body, 'desc')], 'Notice uses mutable terms'
    option = one(body, 'option')
    assert [k for k, o, v in option] == ['name'], 'Notice changes state'
    for key in ('title', 'desc'): assert one(body, key) in locale['english']
    assert one(option, 'name') in locale['english']
    groups['static_reason_notice_identity_and_inert_ack'] += 1

docs = Path(r'D:\SteamLibrary\steamapps\common\Hearts of Iron IV\documentation')
native = {'checked': False}
if docs.exists():
    effects = (docs / 'effects_documentation.md').read_text(encoding='utf-8-sig')
    triggers = (docs / 'triggers_documentation.md').read_text(encoding='utf-8-sig')
    for key in ('clamp_temp_variable', 'round_temp_variable', 'country_event'):
        assert '\n## ' + key + '\n' in effects
        groups['installed_primary_api'] += 1
    for key in ('all_of', 'if', 'set_temp_variable', 'multiply_temp_variable'):
        assert '\n## ' + key + '\n' in triggers
        groups['installed_primary_api'] += 1
    assert '\n## floor_temp_variable\n' not in effects
    assert one(one(ai, 'eon_energy_prepare_ai_counter'), 'if')
    native = {'checked': True, 'path': str(docs), 'round_then_correct_nonnegative_floor': True}

trees = ('common', 'history', 'events', 'interface', 'gfx', 'localisation', 'music', 'map', 'sound')
# Package06 protects these exact later aid/debt files against551d; the energy
# block, helper, AI policy and locale assertions above are unchanged.
later_package06_new = {
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
later_package06_existing = {
    'common/scripted_diplomatic_actions/00_scripted_diplomatic_actions.txt',
    'common/scripted_guis/influence_scripted_gui.txt',
    'events/00_Influence_events.txt',
    'localisation/english/MDC_scripted_diplomatic_actions_l_english.yml',
    'localisation/russian/MDDC_scripted_diplomatic_actions_l_russian.yml',
}
later_package06_paths = later_package06_new | later_package06_existing
# Package 07 separately proves only these additions against 4406; no old range is relaxed.
later_package07_new = {
    'common/scripted_effects/eon_consultation_effects.txt',
    'common/scripted_triggers/eon_consultation_triggers.txt',
    'common/scripted_diplomatic_actions/eon_consultation_actions.txt',
    'common/on_actions/eon_consultation_on_actions.txt',
    'events/eon_consultation_events.txt',
    'localisation/english/eon_consultation_l_english.yml',
    'localisation/russian/eon_consultation_l_russian.yml',
}
# Package 08 independently protects the exact nine-file addition and old game bytes.
later_package08_new = {
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
package21_required_old_paths = {r['path'] for r in receipts} | new | later_package06_paths | later_package07_new | later_package08_new | LATER_PACKAGE09_NEW | LATER_PACKAGE10_NEW | LATER_PACKAGE11_NEW | LATER_PACKAGE12_NEW | LATER_PACKAGE13_NEW
changed = subprocess.check_output(['git', 'diff', '--name-only', BASELINE, '--', *trees], cwd=ROOT).decode().splitlines()
changed = [path for path in changed if path not in LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | package14_historical_existing(BASELINE) | package15_historical_existing(BASELINE) | package16_historical_existing(BASELINE) | LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | package18_historical_existing(BASELINE) | LATER_PACKAGE18_NEW | package19_historical_existing(BASELINE) | LATER_PACKAGE19_NEW | package20_historical_existing(BASELINE) | LATER_PACKAGE20_NEW | (package21_historical_existing(BASELINE) - package21_required_old_paths) | LATER_PACKAGE21_NEW | (package22_historical_existing(BASELINE) - package21_required_old_paths) | LATER_PACKAGE22_NEW]
untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', *trees], cwd=ROOT).decode().splitlines()
untracked = [path for path in untracked if path not in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | LATER_PACKAGE22_NEW]
assert set(changed) | set(untracked) == {r['path'] for r in receipts} | new | later_package06_paths | later_package07_new | later_package08_new | LATER_PACKAGE09_NEW | LATER_PACKAGE10_NEW | LATER_PACKAGE11_NEW | LATER_PACKAGE12_NEW | LATER_PACKAGE13_NEW, ('Unexpected gameplay changes', changed, untracked)
groups['whole_gameplay_git_boundary'] += 1
print(json.dumps({'all_passed': True, 'total_cases': sum(groups.values()), 'groups': groups,
                  'baseline': BASELINE, 'owned_existing_files': receipts, 'native_primary_documentation': native,
                  'not_proven': 'native engine compilation, trigger timing, GUI, campaign or save/load'}, indent=2))
