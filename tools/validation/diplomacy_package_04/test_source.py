"""Package04 exact byte boundaries, primary native APIs and locale references.

Preservation evidence is separate from the executed behavioural scenarios.
This does not compile HOI4 or establish native trigger evaluation timing.
"""
from collections import Counter
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
BASELINE = 'bb018ea1b6a083104b3fd797b83ad1127f77b1bf'
PACKAGE05_BASELINE = '688f1116fbcb377215181edca6af50f36538532e'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'diplomacy_package_03'))
from _support import ast, blocks, format_preserved, one

groups = Counter()
receipts = []


def before(path):
    return subprocess.check_output(['git', 'show', BASELINE + ':' + path], cwd=ROOT)


def restore(after, old, selector):
    previous = {selector(old, b): b for b in blocks(old) if selector(old, b)}
    current = {selector(after, b): b for b in blocks(after) if selector(after, b)}
    assert previous.keys() == current.keys(), ('Owned blocks changed identity', previous.keys(), current.keys())
    for key, b in sorted(current.items(), key=lambda item: item[1]['start'], reverse=True):
        prior = previous[key]
        after = after[:b['start']] + old[prior['start']:prior['end']] + after[b['end']:]
    return after


@lru_cache(maxsize=None)
def package05_before(path):
    return subprocess.check_output(['git', 'show', PACKAGE05_BASELINE + ':' + path], cwd=ROOT)


def without_package05(path, after):
    """Validate later named ranges against 688f before the original 04 bounds."""
    scoped = {'common/scripted_guis/01_energy_gui.txt',
              'events/00_Energy_market_events.txt',
              'common/scripted_effects/eon_energy_contract_effects.txt',
              'localisation/english/eon_energy_contract_l_english.yml',
              'localisation/russian/eon_energy_contract_l_russian.yml'}
    if path not in scoped:
        return after
    old = package05_before(path)
    format_preserved(old, after)
    restored = after
    if path.endswith('01_energy_gui.txt'):
        added = [b for b in blocks(restored)
                 if b['key'] == 'country_view_flag_button_click_enabled'
                 and b['parent'] == 'triggers' and b['depth'] == 3]
        assert not any(b['key'] == 'country_view_flag_button_click_enabled' for b in blocks(old))
        assert len(added) == 1, 'Package05 partner selection guard identity changed'
        block = added[0]
        start = restored.rfind(b'\n', 0, block['start']) + 1
        assert restored[start:block['start']] == b'\t\t\t'
        assert restored[block['end']:block['end'] + 1] == b'\n'
        restored = restored[:start] + restored[block['end'] + 1:]
        keys = {('confirm_energy_sell_click_enabled', 'triggers'),
                ('confirm_energy_sell_click', 'effects'),
                ('country_view_flag_button_click', 'effects')}
        def selector(data, b):
            if (b['key'], b['parent']) in keys and b['depth'] == 3:
                return b['key']
            if b['key'] == 'country_list_flag_button_click' and b['parent'] == 'effects':
                gui = next(p for p in blocks(data) if p['key'] == 'energy_sell_country_selection_gui')
                if gui['start'] < b['start'] < gui['end']:
                    return 'energy_country_selection'
            return None
        restored = restore(restored, old, selector)
    elif path.endswith('00_Energy_market_events.txt'):
        def selector(data, b):
            if b['key'] != 'country_event' or b['depth'] != 0:
                return None
            ident = re.search(rb'\bid\s*=\s*([^\s{}]+)', data[b['start']:b['end']])[1].decode()
            return ident if ident in ('energy_selling.1', 'energy_selling.4') else None
        restored = restore(restored, old, selector)
    elif path.endswith('eon_energy_contract_effects.txt'):
        keys = {'eon_energy_clear_pending', 'eon_energy_invalidate_pair_pending',
                'eon_energy_send_offer', 'eon_energy_validate_offer',
                'eon_energy_finish_response', 'eon_energy_accept_offer'}
        restored = restore(restored, old, lambda data, b: b['key']
                           if b['depth'] == 0 and b['key'] in keys else None)
    else:
        pattern = rb'(?m)^ eon_energy_offer_cancelled_desc:0 "[^\r\n]*"'
        original, current = re.findall(pattern, old), re.findall(pattern, restored)
        assert len(original) == len(current) == 1, path
        restored = restored.replace(current[0], original[0], 1)
    assert restored == old, ('Unrelated package05 bytes changed', path)
    groups['later_package05_owned_boundaries'] += 1
    return restored


def record(path, old, after):
    format_preserved(old, after)
    assert '\ufffd' not in after.decode('utf-8-sig')
    receipts.append({'path': path, 'sha256': hashlib.sha256(after).hexdigest(),
                     'unrelated_bytes_exact': True})
    groups['existing_owned_boundaries'] += 1


path = 'events/00_Energy_market_events.txt'
old, actual = before(path), (ROOT / path).read_bytes()
after = without_package05(path, actual)
def immediate_selector(data, block):
    if block['key'] != 'immediate' or block['parent'] != 'country_event':
        return None
    event = next(b for b in blocks(data) if b['key'] == 'country_event'
                 and b['start'] < block['start'] < b['end'] and b['depth'] == 0)
    ident = re.search(rb'\bid\s*=\s*([^\s{}]+)', data[event['start']:event['end']])[1].decode()
    return ident if ident in ('energy_selling.1', 'energy_selling.4') else None
assert restore(after, old, immediate_selector) == old, 'Other event bytes changed'
record(path, old, actual)

path = 'common/scripted_guis/01_energy_gui.txt'
old, actual = before(path), (ROOT / path).read_bytes()
after = without_package05(path, actual)
keys = {'increase_energy_ammount_number_click_enabled',
        'decrease_energy_ammount_number_click_enabled',
        'confirm_energy_sell_click_enabled', 'confirm_energy_sell_click'}
def gui_selector(data, block):
    if block['key'] in keys and block['depth'] == 3 and block['parent'] in ('effects', 'triggers'):
        return block['key']
    if block['key'] == 'country_list_flag_button_click' and block['parent'] == 'effects':
        gui = next(b for b in blocks(data) if b['key'] == 'energy_sell_country_selection_gui')
        if gui['start'] < block['start'] < gui['end']:
            return 'energy_country_selection'
    return None
assert restore(after, old, gui_selector) == old, 'Unrelated energy/nuclear GUI bytes changed'
record(path, old, actual)

path = 'common/scripted_effects/eon_energy_contract_effects.txt'
old, actual = before(path), (ROOT / path).read_bytes()
after = without_package05(path, actual)
assert restore(after, old, lambda data, b: b['key'] if b['depth'] == 0
               and b['key'] == 'eon_energy_validate_offer' else None) == old, 'Other lifecycle helper bytes changed'
record(path, old, actual)

path = 'common/scripted_effects/!_energy_effects.txt'
old, after = before(path), (ROOT / path).read_bytes()
anchor = b'calculate_energy_use = {\n'
addition = (b'\t# Shared temporary variables must start clean for every country calculation.\n'
            b'\tset_temp_variable = { all_sell_energy_use = 0 }\n'
            b'\tset_temp_variable = { all_buy_energy_generation = 0 }\n')
assert old.count(anchor) == 1 and after == old.replace(anchor, anchor + addition), 'Other calculator bytes changed'
record(path, old, after)

path = 'interface/MD_energy_scripted.gui'
old, after = before(path), (ROOT / path).read_bytes()
anchor = b'\t\t\t\t\ttext = "[?temp_energy_ammount]"\n'
addition = b'\t\t\t\t\tpdx_tooltip = "eon_energy_quantity_controls_tt"\n'
assert old.count(anchor) == 1 and after == old.replace(anchor, anchor + addition), 'Other interface bytes changed'
record(path, old, after)

locale = {}
for language in ('english', 'russian'):
    path = f'localisation/{language}/eon_energy_contract_l_{language}.yml'
    old, actual = before(path), (ROOT / path).read_bytes()
    after = without_package05(path, actual)
    assert after.startswith(b'\xef\xbb\xbf')
    def entries(data):
        text = data.decode('utf-8-sig')
        assert text.splitlines()[0] == 'l_' + language + ':'
        rows = [re.fullmatch(r' ([\w.]+):0 "(.*)"', line).groups() for line in text.splitlines()[1:]]
        assert len(rows) == len(dict(rows))
        return dict(rows)
    previous, current = entries(old), entries(after)
    assert current.keys() == previous.keys() | {'eon_energy_quantity_controls_tt', 'eon_energy_capacity_tt'}
    restored = after
    for key in ('eon_energy_quantity_controls_tt', 'eon_energy_capacity_tt'):
        pattern = rb'(?m)^ ' + key.encode() + rb':0 "[^\r\n]*"\r?\n'
        assert len(re.findall(pattern, restored)) == 1
        restored = re.sub(pattern, b'', restored)
    pattern = rb'(?m)^ eon_energy_offer_invalid_tt:0 "[^\r\n]*"'
    previous_line, current_line = re.findall(pattern, old), re.findall(pattern, restored)
    assert len(previous_line) == len(current_line) == 1
    assert restored.replace(current_line[0], previous_line[0]) == old, 'Unrelated energy locale bytes changed'
    locale[language] = current
    record(path, old, actual)
assert locale['english'].keys() == locale['russian'].keys()
for key in locale['english']:
    assert re.findall(r'\[.*?\]', locale['english'][key]) == re.findall(r'\[.*?\]', locale['russian'][key])
    for language in locale:
        count = sum(len(re.findall(r'^ ' + re.escape(key) + r':', p.read_text(encoding='utf-8-sig'), re.M))
                    for p in (ROOT / 'localisation' / language).glob('*.yml'))
        assert count == 1, ('Duplicate/missing energy locale', language, key, count)
    groups['unique_bilingual_locale_keys'] += 1

path = 'common/scripted_triggers/eon_energy_capacity_triggers.txt'
data = (ROOT / path).read_bytes()
assert not data.startswith(b'\xef\xbb\xbf') and b'\r' not in data and data.endswith(b'\n')
helpers = dict((key, body) for key, op, body in ast(data))
assert len(helpers) == 2 and set(helpers) == {'eon_energy_supplier_capacity_available',
                                         'eon_energy_proposed_capacity_available'}
blocks(data)
for helper in helpers:
    counts = sum(sum(key == helper for key, op, body in ast(p.read_bytes()))
                 for p in (ROOT / 'common/scripted_triggers').glob('eon_energy*.txt'))
    assert counts == 1, ('Duplicate helper', helper)
groups['new_script_format_helper_identity'] += len(helpers)

# Optional primary-document verification makes the supported trigger/effect
# distinction explicit on this host, without requiring a Steam install for CI.
docs = Path(r'D:\SteamLibrary\steamapps\common\Hearts of Iron IV\documentation')
native = {'checked': False}
if docs.exists():
    triggers = (docs / 'triggers_documentation.md').read_text(encoding='utf-8-sig')
    for key in ('all_of', 'if', 'set_temp_variable', 'add_to_temp_variable',
                'multiply_temp_variable', 'subtract_from_temp_variable', 'check_variable'):
        assert '\n## ' + key + '\n' in triggers, ('Unsupported native trigger', key)
        groups['installed_primary_trigger_api'] += 1
    assert '\n## for_each_loop\n' not in triggers
    native = {'checked': True, 'path': str(docs), 'all_of_if_and_temp_math': True}

game_trees = ('common', 'history', 'events', 'interface', 'gfx', 'localisation', 'music', 'map', 'sound')
owned = {r['path'] for r in receipts}
new = {path}
later_package05_new = {
    'common/scripted_effects/eon_energy_ai_effects.txt',
    'common/scripted_effects/eon_energy_negotiation_effects.txt',
    'common/scripted_triggers/eon_energy_negotiation_triggers.txt',
    'common/scripted_diplomatic_actions/eon_energy_negotiation_actions.txt',
    'events/eon_energy_negotiation_events.txt',
    'localisation/english/eon_energy_negotiation_l_english.yml',
    'localisation/russian/eon_energy_negotiation_l_russian.yml',
}
# Package06 validates its exact aid/debt ranges and new files against551d.
# No energy or other existing source ranges are relaxed here.
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
tracked = subprocess.check_output(['git', 'diff', '--name-only', BASELINE, '--', *game_trees], cwd=ROOT).decode().splitlines()
tracked = [path for path in tracked if path not in LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | package14_historical_existing(BASELINE) | package15_historical_existing(BASELINE) | package16_historical_existing(BASELINE) | LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | package18_historical_existing(BASELINE) | LATER_PACKAGE18_NEW | package19_historical_existing(BASELINE) | LATER_PACKAGE19_NEW]
untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', *game_trees], cwd=ROOT).decode().splitlines()
untracked = [path for path in untracked if path not in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]
assert set(tracked) <= owned | new | later_package05_new | later_package06_paths | later_package07_new | later_package08_new | LATER_PACKAGE09_NEW | LATER_PACKAGE10_NEW | LATER_PACKAGE11_NEW | LATER_PACKAGE12_NEW | LATER_PACKAGE13_NEW, ('Unowned package04 gameplay edits', tracked)
assert set(untracked) <= new | later_package05_new | later_package06_new | later_package07_new | later_package08_new | LATER_PACKAGE09_NEW | LATER_PACKAGE10_NEW | LATER_PACKAGE11_NEW | LATER_PACKAGE12_NEW | LATER_PACKAGE13_NEW, ('Unowned package04 gameplay additions', untracked)
groups['whole_gameplay_git_boundary'] += 1
print(json.dumps({'all_passed': True, 'total_cases': sum(groups.values()), 'groups': groups,
                  'baseline': BASELINE, 'owned_existing_files': receipts,
                  'native_primary_documentation': native,
                  'not_proven': 'native engine compilation, fixed-point arithmetic, GUI or campaign'}, indent=2))
