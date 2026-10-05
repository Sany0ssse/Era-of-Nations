"""Package04 exact byte boundaries, primary native APIs and locale references.

Preservation evidence is separate from the executed behavioural scenarios.
This does not compile HOI4 or establish native trigger evaluation timing.
"""
from collections import Counter
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = 'bb018ea1b6a083104b3fd797b83ad1127f77b1bf'
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


def record(path, old, after):
    format_preserved(old, after)
    assert '\ufffd' not in after.decode('utf-8-sig')
    receipts.append({'path': path, 'sha256': hashlib.sha256(after).hexdigest(),
                     'unrelated_bytes_exact': True})
    groups['existing_owned_boundaries'] += 1


path = 'events/00_Energy_market_events.txt'
old, after = before(path), (ROOT / path).read_bytes()
def immediate_selector(data, block):
    if block['key'] != 'immediate' or block['parent'] != 'country_event':
        return None
    event = next(b for b in blocks(data) if b['key'] == 'country_event'
                 and b['start'] < block['start'] < b['end'] and b['depth'] == 0)
    ident = re.search(rb'\bid\s*=\s*([^\s{}]+)', data[event['start']:event['end']])[1].decode()
    return ident if ident in ('energy_selling.1', 'energy_selling.4') else None
assert restore(after, old, immediate_selector) == old, 'Other event bytes changed'
record(path, old, after)

path = 'common/scripted_guis/01_energy_gui.txt'
old, after = before(path), (ROOT / path).read_bytes()
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
record(path, old, after)

path = 'common/scripted_effects/eon_energy_contract_effects.txt'
old, after = before(path), (ROOT / path).read_bytes()
assert restore(after, old, lambda data, b: b['key'] if b['depth'] == 0
               and b['key'] == 'eon_energy_validate_offer' else None) == old, 'Other lifecycle helper bytes changed'
record(path, old, after)

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
    old, after = before(path), (ROOT / path).read_bytes()
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
    record(path, old, after)
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
tracked = subprocess.check_output(['git', 'diff', '--name-only', BASELINE, '--', *game_trees], cwd=ROOT).decode().splitlines()
untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', *game_trees], cwd=ROOT).decode().splitlines()
assert set(tracked) <= owned | new, ('Unowned package04 gameplay edits', tracked)
assert set(untracked) <= new, ('Unowned package04 gameplay additions', untracked)
groups['whole_gameplay_git_boundary'] += 1
print(json.dumps({'all_passed': True, 'total_cases': sum(groups.values()), 'groups': groups,
                  'baseline': BASELINE, 'owned_existing_files': receipts,
                  'native_primary_documentation': native,
                  'not_proven': 'native engine compilation, fixed-point arithmetic, GUI or campaign'}, indent=2))
