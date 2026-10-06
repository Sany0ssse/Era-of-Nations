"""Exact national formation resource/create footprint and historical byte views; not native HOI4 runtime."""
from pathlib import Path
from functools import lru_cache
from collections import Counter
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASELINE = 'de8de2feda0e02b3a80a51ae6df3d9571358f823'
import sys as package21_sys
package21_sys.path.insert(0,str(ROOT/'tools/validation'))
from diplomacy_package_21.test_source import (
    NEW as LATER_PACKAGE21_NEW, package21_original_bytes, package21_historical_existing,
    package21_original_validator_bytes, historical_actions as package21_historical_actions,
    check_owned_existing as check_later_package21_owned,
)
check_later_package21_owned()
EXISTING = {'events/00_War_events.txt'} | {f'localisation/{language}/MD_decisions_l_{language}.yml' for language in ('english', 'russian')}
LEGACY_LOCALE_KEYS = {'AB_mobilization.4.a', 'AB_mobilization.5.t', 'AB_mobilization.5.desc'}
FX = 'common/scripted_effects/eon_defence_formation_effects.txt'
TR = 'common/scripted_triggers/eon_defence_formation_triggers.txt'
NA = 'common/scripted_diplomatic_actions/eon_defence_formation_actions.txt'
HOOKS = 'common/on_actions/eon_defence_formation_on_actions.txt'
EVENTS = 'events/eon_defence_formation_events.txt'
NEW = {FX, TR, NA, HOOKS, EVENTS} | {f'localisation/{language}/eon_defence_formation_l_{language}.yml' for language in ('english', 'russian')}
SOURCE_PATHS = sorted(EXISTING | NEW)
NEW_ACTION_IDS = {'eon_defence_formation_withdraw_offer'}
TOKEN = re.compile(rb'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|[=<>!]+|[^\s{}=<>!#"]+')

def blocks(data, depth=None):
    tokens = [match for match in TOKEN.finditer(data) if not match[0].startswith(b'#')]
    stack, result = [], []
    for index, token in enumerate(tokens):
        if token[0] == b'{':
            item = {'key': tokens[index-2][0].decode('utf-8').lstrip('\ufeff'),
                    'start': tokens[index-2].start(), 'depth': len(stack)}
            stack.append(item)
        elif token[0] == b'}':
            assert stack, 'Extra closing brace'
            item = stack.pop(); item['end'] = token.end()
            if depth is None or item['depth'] == depth: result.append(item)
    assert not stack, 'Unclosed block'
    return result

def ast(data):
    if isinstance(data, str): data = data.encode('utf-8')
    tokens = [match[0].decode('utf-8').strip('"').lstrip('\ufeff') for match in TOKEN.finditer(data) if not match[0].startswith(b'#')]
    index = 0
    def body():
        nonlocal index
        result = []
        while index < len(tokens) and tokens[index] != '}':
            key = tokens[index]; index += 1
            assert index < len(tokens) and tokens[index] in ('=', '==', '>', '<', '>=', '<=', '!='), key
            operator = tokens[index]; index += 1
            if tokens[index] == '{':
                index += 1; value = body(); assert tokens[index] == '}'; index += 1
            else: value = tokens[index]; index += 1
            result.append((key, operator, value))
        return result
    result = body(); assert index == len(tokens), 'Unexpected closing brace'
    return result

def one(nodes, key):
    found = [value for name, operator, value in nodes if name == key]
    assert len(found) == 1, (key, len(found))
    return found[0]

def rows(nodes):
    for row in nodes:
        yield row
        if isinstance(row[2], list): yield from rows(row[2])

@lru_cache(maxsize=128)
def baseline_bytes(path): return subprocess.check_output(['git', 'show', BASELINE + ':' + path], cwd=ROOT)

def format_preserved(before, after, path):
    assert after.startswith(b'\xef\xbb\xbf') == before.startswith(b'\xef\xbb\xbf'), ('BOM changed', path)
    assert (b'\r\n' in after) == (b'\r\n' in before), ('Line endings changed', path)
    assert b'\r' not in after.replace(b'\r\n', b''), ('Mixed carriage returns', path)
    assert after.endswith(b'\n') == before.endswith(b'\n'), ('Final newline changed', path)

def event_blocks(data):
    result = {}
    for block in blocks(data, 0):
        if block['key'] != 'country_event': continue
        identity = one(ast(data[block['start']:block['end']])[0][2], 'id')
        assert identity not in result, ('Duplicate event ID', identity)
        result[identity] = block
    return result

def option_block(data, event_id, name):
    event = event_blocks(data)[event_id]
    segment = data[event['start']:event['end']]
    choices = [item for item in blocks(segment, 1) if item['key'] == 'option'
               and one(ast(segment[item['start']:item['end']])[0][2], 'name') == name]
    assert len(choices) == 1, name
    block = dict(choices[0]); block['start'] += event['start']; block['end'] += event['start']
    return block

def option_raw(data, event_id, name):
    block = option_block(data, event_id, name)
    return data[block['start']:block['end']]

def field_raw(data, name):
    found = [item for item in blocks(data, 1) if item['key'] == name]
    assert len(found) == 1, name
    block = found[0]; return data[block['start']:block['end']]

def package20_original_bytes(path, actual):
    actual = package21_original_bytes(path,actual)
    """Restore exactly two named choices or three named locale lines, rejecting every other byte change."""
    if path not in EXISTING: return actual
    original = baseline_bytes(path); format_preserved(original, actual, path)
    if path == 'events/00_War_events.txt':
        assert event_blocks(original).keys() == event_blocks(actual).keys(), ('Existing event IDs changed', path)
        restored = actual
        for identity, name in (('AB_mobilization.5', 'AB_mobilization.5.a'), ('AB_mobilization.4', 'AB_mobilization.4.a')):
            old = option_block(original, identity, name); new = option_block(restored, identity, name)
            restored = restored[:new['start']] + original[old['start']:old['end']] + restored[new['end']:]
    else:
        original_lines = original.splitlines(keepends=True); actual_lines = actual.splitlines(keepends=True)
        assert len(original_lines) == len(actual_lines), ('Locale line count changed', path)
        seen = set(); restored_lines = []
        for before, after in zip(original_lines, actual_lines):
            match = re.match(rb'\s*([A-Za-z0-9_.]+):', before)
            key = match[1].decode() if match else None
            if key in LEGACY_LOCALE_KEYS:
                assert re.match(rb'\s*([A-Za-z0-9_.]+):', after)[1].decode() == key
                seen.add(key); restored_lines.append(before)
            else: restored_lines.append(after)
        assert seen == LEGACY_LOCALE_KEYS, ('Incomplete legacy locale key set', path)
        restored = b''.join(restored_lines)
    assert restored == original, ('Unowned national-formation source bytes changed', path)
    return original

@lru_cache(maxsize=32)
def package20_historical_existing(baseline):
    return frozenset(subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', baseline, '--', *sorted(EXISTING)], cwd=ROOT).decode().splitlines())

def check_owned_existing():
    for path in sorted(EXISTING): package20_original_bytes(path, (ROOT / path).read_bytes())

def historical_actions(actions):
    actions = package21_historical_actions(actions)
    return [identity for identity in actions if identity not in NEW_ACTION_IDS]

HISTORICAL_SOURCE_EDITS = {'tools/validation/diplomacy_package_02/test_source.py': [(177,
                                                           178,
                                                           '                                               '
                                                           "'eon_withdraw_antiterror_proposal', "
                                                           "'eon_ammo_withdraw_offer', "
                                                           "'eon_services_withdraw_offer', "
                                                           "'eon_services_end_logistics', 'eon_services_end_recon', "
                                                           "'eon_foreign_cash_withdraw_offer', "
                                                           "'eon_foreign_equipment_withdraw_offer')))\n",
                                                           '                                               '
                                                           "'eon_withdraw_antiterror_proposal', "
                                                           "'eon_ammo_withdraw_offer', "
                                                           "'eon_services_withdraw_offer', "
                                                           "'eon_services_end_logistics', 'eon_services_end_recon', "
                                                           "'eon_foreign_cash_withdraw_offer', "
                                                           "'eon_foreign_equipment_withdraw_offer', "
                                                           "'eon_defence_formation_withdraw_offer')))\n")],
 'tools/validation/diplomacy_package_03/test_source.py': [(77,
                                                           77,
                                                           '',
                                                           'from diplomacy_package_20.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE20_NEW, '
                                                           'package20_original_bytes, '
                                                           'package20_historical_existing,\n'
                                                           '    package20_original_validator_bytes, '
                                                           'historical_actions as package20_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package20_owned,\n'
                                                           ')\n'
                                                           'check_later_package20_owned()\n'),
                                                          (259,
                                                           260,
                                                           'tracked_changes = [path for path in tracked_changes if '
                                                           'path not in LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW]\n',
                                                           'tracked_changes = [path for path in tracked_changes if '
                                                           'path not in LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW]\n'),
                                                          (263,
                                                           264,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n')],
 'tools/validation/diplomacy_package_04/test_source.py': [(93,
                                                           93,
                                                           '',
                                                           'from diplomacy_package_20.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE20_NEW, '
                                                           'package20_original_bytes, '
                                                           'package20_historical_existing,\n'
                                                           '    package20_original_validator_bytes, '
                                                           'historical_actions as package20_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package20_owned,\n'
                                                           ')\n'
                                                           'check_later_package20_owned()\n'),
                                                          (356,
                                                           357,
                                                           'tracked = [path for path in tracked if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW]\n',
                                                           'tracked = [path for path in tracked if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW]\n'),
                                                          (358,
                                                           359,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n')],
 'tools/validation/diplomacy_package_05/test_source.py': [(88,
                                                           88,
                                                           '',
                                                           'from diplomacy_package_20.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE20_NEW, '
                                                           'package20_original_bytes, '
                                                           'package20_historical_existing,\n'
                                                           '    package20_original_validator_bytes, '
                                                           'historical_actions as package20_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package20_owned,\n'
                                                           ')\n'
                                                           'check_later_package20_owned()\n'),
                                                          (297,
                                                           298,
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW]\n',
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW]\n'),
                                                          (299,
                                                           300,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n')],
 'tools/validation/diplomacy_package_06/test_source.py': [(90,
                                                           90,
                                                           '',
                                                           'from diplomacy_package_20.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE20_NEW, '
                                                           'package20_original_bytes, '
                                                           'package20_historical_existing,\n'
                                                           '    package20_original_validator_bytes, '
                                                           'historical_actions as package20_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package20_owned,\n'
                                                           ')\n'
                                                           'check_later_package20_owned()\n'),
                                                          (471,
                                                           472,
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW]\n',
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW]\n'),
                                                          (473,
                                                           474,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n')],
 'tools/validation/diplomacy_package_07/test_source.py': [(88,
                                                           88,
                                                           '',
                                                           'from diplomacy_package_20.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE20_NEW, '
                                                           'package20_original_bytes, '
                                                           'package20_historical_existing,\n'
                                                           '    package20_original_validator_bytes, '
                                                           'historical_actions as package20_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package20_owned,\n'
                                                           ')\n'
                                                           'check_later_package20_owned()\n'),
                                                          (150,
                                                           151,
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW]\n',
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW]\n'),
                                                          (152,
                                                           153,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n')],
 'tools/validation/diplomacy_package_08/test_source.py': [(88,
                                                           88,
                                                           '',
                                                           'from diplomacy_package_20.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE20_NEW, '
                                                           'package20_original_bytes, '
                                                           'package20_historical_existing,\n'
                                                           '    package20_original_validator_bytes, '
                                                           'historical_actions as package20_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package20_owned,\n'
                                                           ')\n'
                                                           'check_later_package20_owned()\n'),
                                                          (147,
                                                           148,
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW]\n',
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW]\n'),
                                                          (149,
                                                           150,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n')],
 'tools/validation/diplomacy_package_09/test_source.py': [(76,
                                                           76,
                                                           '',
                                                           'from diplomacy_package_20.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE20_NEW, '
                                                           'package20_original_bytes, '
                                                           'package20_historical_existing,\n'
                                                           '    package20_original_validator_bytes, '
                                                           'historical_actions as package20_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package20_owned,\n'
                                                           ')\n'
                                                           'check_later_package20_owned()\n'),
                                                          (130,
                                                           131,
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW]\n',
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW]\n'),
                                                          (132,
                                                           133,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n')],
 'tools/validation/diplomacy_package_10/test_source.py': [(68,
                                                           68,
                                                           '',
                                                           'from diplomacy_package_20.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE20_NEW, '
                                                           'package20_original_bytes, '
                                                           'package20_historical_existing,\n'
                                                           '    package20_original_validator_bytes, '
                                                           'historical_actions as package20_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package20_owned,\n'
                                                           ')\n'
                                                           'check_later_package20_owned()\n'),
                                                          (210,
                                                           211,
                                                           '    changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE11_EXISTING | LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW]\n',
                                                           '    changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE11_EXISTING | LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW]\n'),
                                                          (212,
                                                           213,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n')],
 'tools/validation/diplomacy_package_11/test_source.py': [(61,
                                                           61,
                                                           '',
                                                           'from diplomacy_package_20.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE20_NEW, '
                                                           'package20_original_bytes, '
                                                           'package20_historical_existing,\n'
                                                           '    package20_original_validator_bytes, '
                                                           'historical_actions as package20_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package20_owned,\n'
                                                           ')\n'
                                                           'check_later_package20_owned()\n'),
                                                          (224,
                                                           226,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n'
                                                           '    changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n'
                                                           '    changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW]\n')],
 'tools/validation/diplomacy_package_12/test_source.py': [(47,
                                                           47,
                                                           '',
                                                           'from diplomacy_package_20.test_source import (\r\n'
                                                           '    NEW as LATER_PACKAGE20_NEW, '
                                                           'package20_original_bytes, '
                                                           'package20_historical_existing,\r\n'
                                                           '    package20_original_validator_bytes, '
                                                           'historical_actions as package20_historical_actions,\r\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package20_owned,\r\n'
                                                           ')\r\n'
                                                           'check_later_package20_owned()\r\n'),
                                                          (194,
                                                           195,
                                                           '    changed=[path for path in changed if path not in '
                                                           '(package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE))-EXISTING | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW]\r\n',
                                                           '    changed=[path for path in changed if path not in '
                                                           '(package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE))-EXISTING | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW]\r\n'),
                                                          (196,
                                                           197,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\r\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\r\n')],
 'tools/validation/diplomacy_package_13/test_source.py': [(47,
                                                           47,
                                                           '',
                                                           'from diplomacy_package_20.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE20_NEW, '
                                                           'package20_original_bytes, '
                                                           'package20_historical_existing,\n'
                                                           '    package20_original_validator_bytes, '
                                                           'historical_actions as package20_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package20_owned,\n'
                                                           ')\n'
                                                           'check_later_package20_owned()\n'),
                                                          (207,
                                                           208,
                                                           '    changed=[path for path in changed if path not in '
                                                           '(package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE))-EXISTING | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW]\n',
                                                           '    changed=[path for path in changed if path not in '
                                                           '(package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE))-EXISTING | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW]\n'),
                                                          (209,
                                                           210,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n')],
 'tools/validation/diplomacy_package_14/test_source.py': [(43,
                                                           43,
                                                           '',
                                                           'from diplomacy_package_20.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE20_NEW, '
                                                           'package20_original_bytes, '
                                                           'package20_historical_existing,\n'
                                                           '    package20_original_validator_bytes, '
                                                           'historical_actions as package20_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package20_owned,\n'
                                                           ')\n'
                                                           'check_later_package20_owned()\n'),
                                                          (223,
                                                           224,
                                                           '    changed=[path for path in changed if path not in '
                                                           'package15_historical_existing(BASELINE)-EXISTING | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW]\n',
                                                           '    changed=[path for path in changed if path not in '
                                                           'package15_historical_existing(BASELINE)-EXISTING | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW]\n'),
                                                          (225,
                                                           226,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n')],
 'tools/validation/diplomacy_package_15/test_source.py': [(35,
                                                           35,
                                                           '',
                                                           'from diplomacy_package_20.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE20_NEW, '
                                                           'package20_original_bytes, '
                                                           'package20_historical_existing,\n'
                                                           '    package20_original_validator_bytes, '
                                                           'historical_actions as package20_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package20_owned,\n'
                                                           ')\n'
                                                           'check_later_package20_owned()\n'),
                                                          (827,
                                                           829,
                                                           '    changed -= package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW\n'
                                                           '    added -= LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW\n',
                                                           '    changed -= package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW\n'
                                                           '    added -= LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW\n')],
 'tools/validation/diplomacy_package_16/test_source.py': [(35,
                                                           35,
                                                           '',
                                                           'from diplomacy_package_20.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE20_NEW, '
                                                           'package20_original_bytes, '
                                                           'package20_historical_existing,\n'
                                                           '    package20_original_validator_bytes, '
                                                           'historical_actions as package20_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package20_owned,\n'
                                                           ')\n'
                                                           'check_later_package20_owned()\n'),
                                                          (658,
                                                           660,
                                                           '    changed -= package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW\n'
                                                           '    untracked -= LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW\n',
                                                           '    changed -= package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW\n'
                                                           '    untracked -= LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW\n')],
 'tools/validation/diplomacy_package_17/test_source.py': [(29,
                                                           29,
                                                           '',
                                                           'from diplomacy_package_20.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE20_NEW, '
                                                           'package20_original_bytes, '
                                                           'package20_historical_existing,\n'
                                                           '    package20_original_validator_bytes, '
                                                           'historical_actions as package20_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package20_owned,\n'
                                                           ')\n'
                                                           'check_later_package20_owned()\n'),
                                                          (749,
                                                           751,
                                                           '    changed -= package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW\n'
                                                           '    untracked -= LATER_PACKAGE18_NEW | '
                                                           'LATER_PACKAGE19_NEW\n',
                                                           '    changed -= package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW\n'
                                                           '    untracked -= LATER_PACKAGE18_NEW | '
                                                           'LATER_PACKAGE19_NEW | LATER_PACKAGE20_NEW\n')],
 'tools/validation/diplomacy_package_18/test_source.py': [(19,
                                                           19,
                                                           '',
                                                           'from diplomacy_package_20.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE20_NEW, '
                                                           'package20_original_bytes, '
                                                           'package20_historical_existing,\n'
                                                           '    package20_original_validator_bytes, '
                                                           'historical_actions as package20_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package20_owned,\n'
                                                           ')\n'
                                                           'check_later_package20_owned()\n'),
                                                          (756,
                                                           758,
                                                           '    changed -= (package19_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE19_NEW\n'
                                                           '    untracked -= LATER_PACKAGE19_NEW\n',
                                                           '    changed -= (package19_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE19_NEW | '
                                                           '(package20_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE20_NEW\n'
                                                           '    untracked -= LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW\n')],
 'tools/validation/diplomacy_package_19/test_source.py': [(11,
                                                           11,
                                                           '',
                                                           'import sys as package20_sys\n'
                                                           'package20_sys.path.insert(0, str(ROOT / '
                                                           "'tools/validation'))\n"
                                                           'from diplomacy_package_20.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE20_NEW, '
                                                           'package20_original_bytes, '
                                                           'package20_historical_existing,\n'
                                                           '    package20_original_validator_bytes, '
                                                           'historical_actions as package20_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package20_owned,\n'
                                                           ')\n'
                                                           'check_later_package20_owned()\n'),
                                                          (103,
                                                           103,
                                                           '',
                                                           '    if path in EXISTING and actual == '
                                                           'baseline_bytes(path): return actual\n'
                                                           '    actual = package20_original_bytes(path, actual)\n'),
                                                          (121,
                                                           121,
                                                           '',
                                                           '    actions = package20_historical_actions(actions)\n'),
                                                          (819,
                                                           819,
                                                           '',
                                                           '    actual = package20_original_validator_bytes(path, '
                                                           'actual)\n'),
                                                          (842,
                                                           843,
                                                           '    raw = (ROOT / '
                                                           "'events/00_War_events.txt').read_bytes(); original = "
                                                           "baseline_bytes('events/00_War_events.txt')\n",
                                                           '    raw = '
                                                           "package20_original_bytes('events/00_War_events.txt', "
                                                           "(ROOT / 'events/00_War_events.txt').read_bytes()); "
                                                           "original = baseline_bytes('events/00_War_events.txt')\n"),
                                                          (855,
                                                           855,
                                                           '',
                                                           '    changed -= (package20_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE20_NEW\n'
                                                           '    untracked -= LATER_PACKAGE20_NEW\n'),
                                                          (1015,
                                                           1016,
                                                           '        assert (ROOT / path).read_bytes() == '
                                                           'baseline_bytes(path)\n',
                                                           '        assert package20_original_bytes(path, (ROOT / '
                                                           'path).read_bytes()) == baseline_bytes(path)\n'),
                                                          (1037,
                                                           1037,
                                                           '',
                                                           '    current_ids = '
                                                           'package20_historical_actions(current_ids)\n'),
                                                          (1079,
                                                           1080,
                                                           '    for path in unchanged: assert (ROOT / '
                                                           "path).read_bytes() == baseline_bytes(path), ('Prior "
                                                           'public behavior/helper/runner or unrelated source '
                                                           "changed', path)\n",
                                                           '    for path in unchanged: assert '
                                                           'package20_original_validator_bytes(path, (ROOT / '
                                                           "path).read_bytes()) == baseline_bytes(path), ('Prior "
                                                           'public behavior/helper/runner or unrelated source '
                                                           "changed', path)\n")]}


def package20_original_validator_bytes(path, actual):
    actual = package21_original_validator_bytes(path,actual)
    if path not in HISTORICAL_SOURCE_EDITS: return actual
    original = baseline_bytes(path)
    lines = original.decode('utf-8').splitlines(keepends=True)
    for start, end, before, after in reversed(HISTORICAL_SOURCE_EDITS[path]):
        assert ''.join(lines[start:end]) == before, ('Historical source baseline drift', path, start)
        lines[start:end] = [after]
    assert actual == ''.join(lines).encode('utf-8'), ('Undeclared historical source validator edit', path)
    return original

def locale_lines(data):
    result = {}
    for line in data.decode('utf-8-sig').splitlines(keepends=True):
        match = re.match(r'^ ([A-Za-z0-9_.]+):(?:\d+)?\s+', line)
        if match:
            assert match[1] not in result, ('Duplicate locale key', match[1])
            result[match[1]] = line
    return result

def main():
    groups = Counter(); boundary_groups = set()
    def passed(group): groups[group] += 1
    check_owned_existing()
    passed('two_named_war_options_and_three_named_lines_per_legacy_locale_are_the_only_inherited_changes')
    raw = (ROOT / 'events/00_War_events.txt').read_bytes(); original = baseline_bytes('events/00_War_events.txt')
    effects = {key: body for key, op, body in ast((ROOT / FX).read_bytes())}
    triggers = {key: body for key, op, body in ast((ROOT / TR).read_bytes())}
    events = {one(body,'id'):body for key,op,body in ast((ROOT / EVENTS).read_bytes()) if key == 'country_event'}
    trees = ('common/scripted_effects','common/scripted_triggers','common/scripted_diplomatic_actions','common/on_actions','events','localisation')
    changed = set(subprocess.check_output(['git','diff','--name-only',BASELINE,'--',*trees],cwd=ROOT).decode().splitlines())
    untracked = set(subprocess.check_output(['git','ls-files','--others','--exclude-standard','--',*trees],cwd=ROOT).decode().splitlines())
    changed -= (package21_historical_existing(BASELINE) - EXISTING) | LATER_PACKAGE21_NEW
    untracked -= LATER_PACKAGE21_NEW
    assert changed - NEW == EXISTING and (changed | untracked) - EXISTING == NEW, (changed,untracked)
    passed('exact_three_existing_and_seven_new_gameplay_paths')
    for path in NEW:
        data = (ROOT / path).read_bytes()
        assert data.startswith(b'\xef\xbb\xbf') == path.endswith('.yml')
        assert b'\r' not in data.replace(b'\r\n',b'') and b'\n' not in data.replace(b'\r\n',b'')
        passed('seven_new_files_preserve_declared_CRLF_and_locale_BOM')
    before = ast(option_raw(original,'AB_mobilization.4','AB_mobilization.4.a'))[0][2]
    choice = ast(option_raw(raw,'AB_mobilization.4','AB_mobilization.4.a'))[0][2]
    assert one(choice,'name') == one(before,'name') and one(choice,'log') == one(before,'log')
    assert field_raw(option_raw(raw,'AB_mobilization.4','AB_mobilization.4.a'),'ai_chance') == field_raw(option_raw(original,'AB_mobilization.4','AB_mobilization.4.a'),'ai_chance')
    passed('original_choice_ID_log_and_AI_block_whole_raw_bytes_preserved')
    assert one(choice,'eon_defence_formation_send_offer') == 'yes'
    assert any(key == 'eon_defence_formation_offer_ready' for key,op,val in rows(one(choice,'trigger')))
    assert {key for key,op,val in choice} == {'name','trigger','log','custom_effect_tooltip','eon_defence_formation_send_offer','ai_chance'}
    passed('existing_choice_only_offers_guarded_unsigned_support')
    legacy = ast(option_raw(raw,'AB_mobilization.5','AB_mobilization.5.a'))[0][2]
    assert {key for key,op,val in legacy} <= {'name','log','custom_effect_tooltip'}
    assert one(legacy,'name') == 'AB_mobilization.5.a'
    passed('old_AB5_acknowledgement_cannot_create_template_unit_idea_or_resource_calls')
    expected_effects = {'eon_defence_formation_'+name for name in ('ensure_template','clear_pending','retire_pending_pair','send_offer','accept_offer','commit_offer','reject_offer','withdraw_offer','daily_update','annex_update','clear_annexed_country')}
    expected_triggers = {'eon_defence_formation_'+name for name in ('template_usable','recipient_ready','equipment_available','requirements_ready','policy_allowed','partner_identified','offer_ready','response_pending','response_open','response_ready','commit_pending','commit_ready','withdraw_available')}
    assert set(effects) == expected_effects and set(triggers) == expected_triggers
    passed('exact_owned_effect_and_trigger_API_definition_sets')
    definitions = Counter()
    for directory in ('common/scripted_effects','common/scripted_triggers'):
        for path in (ROOT / directory).glob('*.txt'):
            for block in blocks(path.read_bytes(),0):
                if block['key'] in expected_effects | expected_triggers: definitions[block['key']] += 1
    for key in expected_effects | expected_triggers:
        assert definitions[key] == 1,key
        passed('twenty_four_owned_helper_IDs_globally_unique')
    for path in (FX,TR,NA,HOOKS,EVENTS):
        for key,op,val in rows(ast((ROOT/path).read_bytes())):
            if key in expected_effects | expected_triggers:
                if not isinstance(val,list): assert val in ('yes','no')
            elif key.startswith('eon_defence_formation_') and not isinstance(val,list) and val in ('yes','no'):
                raise AssertionError(('Undefined formation helper call',key,path))
        passed('five_current_helper_callsite_sources_parse_and_resolve')
    prefix = 'eon_defence_formation_'
    amounts = {'Inf_equipment':1623,'command_control_equipment':150,'artillery_equipment':36,'L_AT_Equipment':76,'AA_Equipment':50}
    available = triggers[prefix+'equipment_available']
    assert available == [('has_equipment','=',[(key,'>',str(amount-1))]) for key,amount in amounts.items()]
    passed('all_five_full_template_equipment_count_guards_exact')
    recipient = triggers[prefix+'recipient_ready']
    assert ('has_manpower','>','5479') in recipient
    assert ('any_owned_state','=',[('is_owned_and_controlled_by','=','PREV')]) in recipient
    assert (prefix+'template_usable','=','yes') in recipient
    passed('recipient_own_5480_manpower_controlled_owned_state_and_template_collision_guards')
    usable = triggers[prefix+'template_usable']
    assert any(key == 'has_template' and val == 'EON Local Defence Formation' for key,op,val in rows(usable))
    assert any(key == 'has_country_flag' and val == prefix+'template_owned' for key,op,val in rows(usable))
    passed('reserved_template_requires_absence_or_explicit_owned_marker')
    unit_bytes = (ROOT/'common/units/MD_land_units.txt').read_bytes()
    units = {block['key']:unit_bytes[block['start']:block['end']] for block in blocks(unit_bytes,1)}
    original_template = one(ast(option_raw(original,'AB_mobilization.5','AB_mobilization.5.a'))[0][2],'division_template')
    demands = Counter(); personnel = 0
    for section in ('regiments','support'):
        for unit,op,position in one(original_template,section):
            body = units[unit]; personnel += int(re.search(rb'\bmanpower\s*=\s*([0-9]+)',body)[1])
            need = ast(field_raw(body,'need'))[0][2]
            demands.update({key:int(quantity) for key,op,quantity in need})
    assert personnel == 5480 and dict(demands) == amounts
    passed('5480_personnel_and_five_equipment_quantities_derive_from_actual_existing_subunit_definitions')
    ensure = effects[prefix+'ensure_template']
    created = [val for key,op,val in rows(ensure) if key == 'division_template']; assert len(created) == 1
    template = created[0]
    assert one(template,'name') == 'EON Local Defence Formation' and one(template,'is_locked') == 'yes'
    for section in ('regiments','support','priority'):
        assert one(template,section) == one(original_template,section)
    assert any(key == 'has_template' and val == 'EON Local Defence Formation' for key,op,val in rows(ensure))
    assert any(key == 'set_country_flag' and val == prefix+'template_owned' for key,op,val in rows(ensure))
    passed('new_locked_template_preserves_actual_composition_and_only_owns_its_new_name')
    commit = effects[prefix+'commit_offer']
    resource_calls = [(key,val) for key,op,val in rows(commit) if key in ('add_manpower','add_equipment_to_stockpile')]
    assert [(key,one(val,'type'),one(val,'amount')) for key,val in resource_calls if key == 'add_equipment_to_stockpile'] == [('add_equipment_to_stockpile',key,str(-amount)) for key,amount in amounts.items()]
    assert [(key,val) for key,val in resource_calls if key == 'add_manpower'] == [('add_manpower','-5480')]
    assert all(not any(key == 'producer' for key,op,value in val) for effect,val in resource_calls if effect == 'add_equipment_to_stockpile')
    passed('five_exact_all_creator_donor_resource_calls_and_one_recipient_own_personnel_call')
    spawn = [(val) for key,op,val in rows(commit) if key == 'create_unit']; assert len(spawn) == 1
    assert one(spawn[0],'owner') == 'PREV' and one(spawn[0],'count') == '1'
    division = one(spawn[0],'division')
    assert 'EON Local Defence Formation' in division and 'start_experience_factor = 0.4' in division
    assert any(key == 'random_owned_controlled_state' for key,op,val in rows(commit))
    passed('one_recipient_owned_create_call_in_owned_controlled_state_with_original_experience')
    flattened = list(rows(commit)); clear_index = next(i for i,row in enumerate(flattened) if row[0] == prefix+'clear_pending')
    assert all(clear_index < i for i,(key,op,val) in enumerate(flattened) if key in ('add_manpower','add_equipment_to_stockpile','division_template','create_unit'))
    assert any(key == prefix+'commit_pending' for key,op,val in flattened) and any(key == prefix+'commit_ready' for key,op,val in flattened)
    passed('exact_consented_pair_and_fresh_requirements_then_consume_before_every_native_resource_or_create_call')
    influence = [(key,op,val) for key,op,val in flattened if key in ('set_temp_variable','change_influence_percentage')]
    assert [('set_temp_variable','=',[('percent_change','=','3')]),('set_temp_variable','=',[('tag_index','=','ROOT')]),('set_temp_variable','=',[('influence_target','=','FROM')]),('change_influence_percentage','=','yes')] == influence[-4:]
    passed('original_three_percent_influence_macro_keeps_native_provider_ROOT_and_recipient_FROM')
    for name in ('send_offer','accept_offer'):
        assert not any(key in ('add_manpower','add_equipment_to_stockpile','division_template','create_unit','change_influence_percentage') for key,op,val in rows(effects[prefix+name]))
        passed('proposal_and_assent_have_no_resource_template_create_or_influence_calls')
    for path in (FX,TR,NA,HOOKS,EVENTS):
        nodes = ast((ROOT/path).read_bytes())
        assert not any(key in ('modify_treasury_effect','add_political_power','add_command_power','add_fuel','send_equipment','add_ideas','add_timed_idea','delete_unit','delete_units','delete_unit_template_and_units','transfer_units_fraction','add_to_faction','declare_war_on','white_peace') for key,op,val in rows(nodes))
        assert not any(key == 'country_event' and (val == 'AB_mobilization.5' or isinstance(val,list) and any(name == 'id' and value == 'AB_mobilization.5' for name,op,value in val)) for key,op,val in rows(nodes))
        passed('five_sources_have_no_cash_donor_personnel_mission_idea_foreign_command_deletion_refund_or_AB5_queue')
    clear = effects[prefix+'clear_pending']
    assert ('clr_country_flag','=',prefix+'template_owned') not in clear
    assert {val for key,op,val in clear if key == 'clr_country_flag'} == {prefix+name for name in ('pending','live','cancelled','consented')}
    assert ('clear_variable','=',prefix+'partner') in clear
    passed('pending_cleanup_does_not_destroy_retained_owned_template_or_formation')
    accept = effects[prefix+'accept_offer']
    assert any(key == prefix+'response_open' for key,op,val in rows(accept))
    assert any(key == 'set_country_flag' and val == prefix+'consented' for key,op,val in rows(accept))
    assert any(key == 'country_event' and isinstance(val,list) and one(val,'id') == 'eon_defence_formation.2' for key,op,val in rows(accept))
    passed('recipient_marks_consent_once_and_queues_hidden_provider_execution')
    assert set(events) == {'eon_defence_formation.'+str(i) for i in range(1,8)}
    assert one(events['eon_defence_formation.2'],'hidden') == 'yes' and one(one(events['eon_defence_formation.2'],'immediate'),prefix+'commit_offer') == 'yes'
    passed('seven_new_events_with_hidden_provider_commit_frame')
    event_ids = Counter()
    for path in (ROOT/'events').glob('*.txt'):
        data = path.read_bytes()
        for block in blocks(data,0):
            if block['key'] in ('country_event','news_event'):
                identity = re.search(rb'\bid\s*=\s*([A-Za-z0-9_.]+)',data[block['start']:block['end']])
                assert identity, path
                event_ids[identity[1].decode()] += 1
    for identity in events:
        assert event_ids[identity] == 1; passed('seven_new_event_IDs_globally_unique')
    hooks = one(ast((ROOT/HOOKS).read_bytes()),'on_actions')
    assert {key for key,op,val in hooks} == {'on_daily','on_annex','on_subject_annexed'}
    for key,op,val in hooks:
        assert not any(effect in ('create_unit','delete_unit','add_manpower','add_equipment_to_stockpile') for effect,op,value in rows(val))
        passed('three_hooks_only_clean_pending_diplomatic_records_without_native_assets')
    actions = one(ast((ROOT/NA).read_bytes()),'scripted_diplomatic_actions')
    assert {key for key,op,val in actions} == NEW_ACTION_IDS
    action = one(actions,next(iter(NEW_ACTION_IDS)))
    assert one(action,'cost') == '0' and one(action,'requires_acceptance') == 'no'
    for section in ('allowed','visible','selectable','can_be_sent'):
        expected = [('ROOT','=',[('is_ai','=','no')])] if section == 'allowed' else [(prefix+'withdraw_available','=','yes')]
        assert one(action,section) == expected; passed('four_native_free_withdraw_admission_blocks_use_exact_human_and_owned_pair_guards')
    assert one(one(action,'complete_effect'),prefix+'withdraw_offer') == 'yes'
    passed('one_zero_cost_native_withdrawal_only_closes_unsigned_proposal')
    old_action_ids = []
    for path in subprocess.check_output(['git','ls-tree','-r','--name-only',BASELINE,'--','common/scripted_diplomatic_actions'],cwd=ROOT).decode().splitlines():
        for key,op,val in ast(baseline_bytes(path)):
            if key == 'scripted_diplomatic_actions': old_action_ids += [name for name,op,body in val]
    current_ids = []
    for path in (ROOT/'common/scripted_diplomatic_actions').glob('*.txt'):
        for key,op,val in ast(path.read_bytes()):
            if key == 'scripted_diplomatic_actions': current_ids += [name for name,op,body in val]
    current_ids = package21_historical_actions(current_ids)
    assert len(old_action_ids) == len(set(old_action_ids)) == 71 and len(current_ids) == len(set(current_ids)) == 72
    passed('71_existing_native_actions_plus_one_unique_formation_withdrawal')
    preserved = ('common/scripted_diplomatic_actions/MDDC_AB_ask_foreign_support.txt','common/ideas/Generic Tree_ideas.txt','common/units/MD_land_units.txt','common/scripted_effects/00_influence_scripted_effects.txt','common/scripted_effects/00_budget_effects.txt','events/00_Influence_events.txt','common/scripted_guis/influence_scripted_gui.txt')
    old_game = subprocess.check_output(['git','ls-tree','-r','--name-only',BASELINE,'--','common/on_actions','common/scripted_diplomatic_actions','common/scripted_effects','common/scripted_triggers','events','localisation'],cwd=ROOT).decode().splitlines()
    preserved += tuple(sorted(path for path in old_game if 'eon_foreign_cash_' in path or 'eon_foreign_equipment_' in path))
    for path in preserved:
        assert package21_original_bytes(path,(ROOT/path).read_bytes()) == baseline_bytes(path),path
        passed('prior_cash_equipment_entry_legacy_mission_unit_and_policy_sources_whole_raw_unchanged')
    entry = ast((ROOT/'common/scripted_diplomatic_actions/MDDC_AB_ask_foreign_support.txt').read_bytes())
    entry_body = one(one(entry,'scripted_diplomatic_actions'),'AB_ask_foreign_support')
    assert one(entry_body,'cost') == '50' and any(key == 'set_country_flag' and isinstance(val,list) and one(val,'days') == '360' for key,op,val in rows(entry_body))
    passed('inherited_50_PP_and_360_day_request_marker_are_nominal_declarations_not_cost_receipt_proof')
    locales = {}
    for language in ('english','russian'):
        data = (ROOT/f'localisation/{language}/eon_defence_formation_l_{language}.yml').read_text(encoding='utf-8-sig')
        locales[language] = {match[1]:match[2] for match in re.finditer(r'^\s*([A-Za-z0-9_.]+):[0-9]*\s*"(.*)"\s*$',data,re.M)}
    assert locales['english'].keys() == locales['russian'].keys()
    passed('bilingual_localisation_key_sets_exactly_match')
    for path in (FX,NA,EVENTS):
        for key,op,val in rows(ast((ROOT/path).read_bytes())):
            if key in ('custom_effect_tooltip','tooltip','send_description','title','desc','name') and isinstance(val,str) and (val.startswith('eon_defence_formation.') or val.startswith(prefix)):
                assert val in locales['english'],val
        passed('three_current_tooltip_action_event_locale_reference_sets_resolve')
    for path in EXISTING:
        data = (ROOT/path).read_bytes()
        try: package20_original_bytes(path,data+b'# unowned memory mutation\n')
        except AssertionError: pass
        else: raise AssertionError(('Undeclared source mutation accepted',path))
        passed('memory_only_game_source_outside_two_options_or_three_locale_lines_rejected'); boundary_groups.add('memory_only_game_source_outside_two_options_or_three_locale_lines_rejected')
    assert set(HISTORICAL_SOURCE_EDITS) == {f'tools/validation/diplomacy_package_{i:02}/test_source.py' for i in range(2,20)}
    for path in sorted(HISTORICAL_SOURCE_EDITS):
        actual = (ROOT/path).read_bytes(); original = baseline_bytes(path)
        assert package20_original_validator_bytes(path,actual) == original
        counters = lambda data:[line for line in data.splitlines() if b'groups[' in line and b'+=' in line or b'passed(' in line]
        assert counters(actual) == counters(original)
        passed('eighteen_literal_whole_source_validator_journals_and_all_original_counter_lines')
        try: package20_original_validator_bytes(path,actual+b'# unowned memory mutation\n')
        except AssertionError: pass
        else: raise AssertionError(('Undeclared historical source mutation accepted',path))
        passed('memory_only_whole_historical_source_mutation_rejected'); boundary_groups.add('memory_only_whole_historical_source_mutation_rejected')
    public_paths = subprocess.check_output(['git','ls-tree','-r','--name-only',BASELINE,'--','tools/validation'],cwd=ROOT).decode().splitlines()
    untouched = [path for path in public_paths if path not in HISTORICAL_SOURCE_EDITS]
    for path in untouched: assert package21_original_validator_bytes(path,(ROOT/path).read_bytes()) == baseline_bytes(path),path
    behavior = [path for path in untouched if path.endswith('.py') and Path(path).name != 'test_source.py']
    assert len(untouched) == 68 and len(behavior) == 49
    passed('49_prior_behavior_helper_runners_and68_other_public_files_are_whole_raw_byte_exact')
    installed = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV')
    effect_docs = (installed/'documentation/effects_documentation.md').read_text(encoding='utf-8-sig')
    trigger_docs = (installed/'documentation/triggers_documentation.md').read_text(encoding='utf-8-sig')
    for name in ('add_manpower','add_equipment_to_stockpile','division_template','create_unit','random_owned_controlled_state'):
        assert '\n## '+name+'\n' in effect_docs; passed('five_installed_native_resource_template_create_and_state_effect_declarations')
    for name in ('has_manpower','has_equipment','has_template','any_owned_state','is_owned_and_controlled_by','has_defensive_war'):
        assert '\n## '+name+'\n' in trigger_docs; passed('six_installed_native_resource_template_state_policy_trigger_declarations')
    stock_doc = effect_docs.split('\n## add_equipment_to_stockpile\n',1)[1].split('\n## ',1)[0]
    assert 'all creators' in stock_doc and 'negative' in stock_doc
    passed('aggregate_stock_guard_matches_all_creator_removal_declaration_without_variant_conservation_claim')
    hashes = {path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in SOURCE_PATHS}
    boundaries = sum(groups[key] for key in boundary_groups)
    print(json.dumps({'all_passed':True,'baseline':BASELINE,'source_cases':sum(groups.values()),'source_API_cases':sum(groups.values())-boundaries,
        'source_byte_adapter_boundary_cases':boundaries,'groups':dict(groups),'source_sha256':hashes,
        'historical_source_adapters':len(HISTORICAL_SOURCE_EDITS),'prior_behavior_helper_runner_raw_byte_files':len(behavior),
        'prior_other_public_raw_byte_files':len(untouched),'bilingual_locale_keys':len(locales['english']),
        'native_runtime':False,'proof_scope':'exact national-defence-formation calls and literal byte retention; not native resource consumption or spawn success'},indent=2))

if __name__ == '__main__': main()
