"""Exact equipment-dispatch footprint and historical byte views; not native HOI4 runtime."""
from pathlib import Path
from functools import lru_cache
from collections import Counter
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASELINE = 'd17ccfb5c86ecb9f9ad9fff96894ffcf32e19ff0'
import sys as package20_sys
package20_sys.path.insert(0, str(ROOT / 'tools/validation'))
from diplomacy_package_20.test_source import (
    NEW as LATER_PACKAGE20_NEW, package20_original_bytes, package20_historical_existing,
    package20_original_validator_bytes, historical_actions as package20_historical_actions,
    check_owned_existing as check_later_package20_owned,
)
check_later_package20_owned()
EXISTING = {'events/00_War_events.txt'}
FX = 'common/scripted_effects/eon_foreign_equipment_effects.txt'
TR = 'common/scripted_triggers/eon_foreign_equipment_triggers.txt'
NA = 'common/scripted_diplomatic_actions/eon_foreign_equipment_actions.txt'
HOOKS = 'common/on_actions/eon_foreign_equipment_on_actions.txt'
EVENTS = 'events/eon_foreign_equipment_events.txt'
NEW = {FX, TR, NA, HOOKS, EVENTS} | {f'localisation/{language}/eon_foreign_equipment_l_{language}.yml' for language in ('english', 'russian')}
SOURCE_PATHS = sorted(EXISTING | NEW)
NEW_ACTION_IDS = {'eon_foreign_equipment_withdraw_offer'}
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

def package19_original_bytes(path, actual):
    if path in EXISTING and actual == baseline_bytes(path): return actual
    actual = package20_original_bytes(path, actual)
    """Restore one named option; headers, other options and every outside byte stay exact."""
    if path not in EXISTING: return actual
    original = baseline_bytes(path); format_preserved(original, actual, path)
    assert event_blocks(original).keys() == event_blocks(actual).keys(), ('Existing event IDs changed', path)
    old = option_block(original, 'AB_mobilization.4', 'AB_mobilization.4.b')
    new = option_block(actual, 'AB_mobilization.4', 'AB_mobilization.4.b')
    restored = actual[:new['start']] + original[old['start']:old['end']] + actual[new['end']:]
    assert restored == original, ('Unowned equipment-support source bytes changed', path)
    return original

@lru_cache(maxsize=32)
def package19_historical_existing(baseline):
    return frozenset(subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', baseline, '--', *sorted(EXISTING)], cwd=ROOT).decode().splitlines())

def check_owned_existing():
    for path in sorted(EXISTING): package19_original_bytes(path, (ROOT / path).read_bytes())

def historical_actions(actions):
    actions = package20_historical_actions(actions)
    return [identity for identity in actions if identity not in NEW_ACTION_IDS]

HISTORICAL_SOURCE_EDITS = {'tools/validation/diplomacy_package_02/test_source.py': [(177,
                                                           178,
                                                           '                                               '
                                                           "'eon_withdraw_antiterror_proposal', "
                                                           "'eon_ammo_withdraw_offer', "
                                                           "'eon_services_withdraw_offer', "
                                                           "'eon_services_end_logistics', 'eon_services_end_recon', "
                                                           "'eon_foreign_cash_withdraw_offer')))\n",
                                                           '                                               '
                                                           "'eon_withdraw_antiterror_proposal', "
                                                           "'eon_ammo_withdraw_offer', "
                                                           "'eon_services_withdraw_offer', "
                                                           "'eon_services_end_logistics', 'eon_services_end_recon', "
                                                           "'eon_foreign_cash_withdraw_offer', "
                                                           "'eon_foreign_equipment_withdraw_offer')))\n")],
 'tools/validation/diplomacy_package_03/test_source.py': [(71,
                                                           71,
                                                           '',
                                                           'from diplomacy_package_19.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE19_NEW, '
                                                           'package19_original_bytes, '
                                                           'package19_historical_existing,\n'
                                                           '    package19_original_validator_bytes, '
                                                           'historical_actions as package19_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package19_owned,\n'
                                                           ')\n'
                                                           'check_later_package19_owned()\n'),
                                                          (253,
                                                           254,
                                                           'tracked_changes = [path for path in tracked_changes if '
                                                           'path not in LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW]\n',
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
                                                           'LATER_PACKAGE19_NEW]\n'),
                                                          (257,
                                                           258,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n')],
 'tools/validation/diplomacy_package_04/test_source.py': [(87,
                                                           87,
                                                           '',
                                                           'from diplomacy_package_19.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE19_NEW, '
                                                           'package19_original_bytes, '
                                                           'package19_historical_existing,\n'
                                                           '    package19_original_validator_bytes, '
                                                           'historical_actions as package19_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package19_owned,\n'
                                                           ')\n'
                                                           'check_later_package19_owned()\n'),
                                                          (350,
                                                           351,
                                                           'tracked = [path for path in tracked if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW]\n',
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
                                                           'LATER_PACKAGE19_NEW]\n'),
                                                          (352,
                                                           353,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n')],
 'tools/validation/diplomacy_package_05/test_source.py': [(82,
                                                           82,
                                                           '',
                                                           'from diplomacy_package_19.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE19_NEW, '
                                                           'package19_original_bytes, '
                                                           'package19_historical_existing,\n'
                                                           '    package19_original_validator_bytes, '
                                                           'historical_actions as package19_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package19_owned,\n'
                                                           ')\n'
                                                           'check_later_package19_owned()\n'),
                                                          (291,
                                                           292,
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW]\n',
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
                                                           'LATER_PACKAGE19_NEW]\n'),
                                                          (293,
                                                           294,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n')],
 'tools/validation/diplomacy_package_06/test_source.py': [(84,
                                                           84,
                                                           '',
                                                           'from diplomacy_package_19.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE19_NEW, '
                                                           'package19_original_bytes, '
                                                           'package19_historical_existing,\n'
                                                           '    package19_original_validator_bytes, '
                                                           'historical_actions as package19_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package19_owned,\n'
                                                           ')\n'
                                                           'check_later_package19_owned()\n'),
                                                          (465,
                                                           466,
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW]\n',
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
                                                           'LATER_PACKAGE19_NEW]\n'),
                                                          (467,
                                                           468,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n')],
 'tools/validation/diplomacy_package_07/test_source.py': [(82,
                                                           82,
                                                           '',
                                                           'from diplomacy_package_19.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE19_NEW, '
                                                           'package19_original_bytes, '
                                                           'package19_historical_existing,\n'
                                                           '    package19_original_validator_bytes, '
                                                           'historical_actions as package19_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package19_owned,\n'
                                                           ')\n'
                                                           'check_later_package19_owned()\n'),
                                                          (144,
                                                           145,
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
                                                           'LATER_PACKAGE18_NEW]\n',
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
                                                           'LATER_PACKAGE19_NEW]\n'),
                                                          (146,
                                                           147,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n')],
 'tools/validation/diplomacy_package_08/test_source.py': [(82,
                                                           82,
                                                           '',
                                                           'from diplomacy_package_19.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE19_NEW, '
                                                           'package19_original_bytes, '
                                                           'package19_historical_existing,\n'
                                                           '    package19_original_validator_bytes, '
                                                           'historical_actions as package19_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package19_owned,\n'
                                                           ')\n'
                                                           'check_later_package19_owned()\n'),
                                                          (141,
                                                           142,
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
                                                           'LATER_PACKAGE18_NEW]\n',
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
                                                           'LATER_PACKAGE19_NEW]\n'),
                                                          (143,
                                                           144,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n')],
 'tools/validation/diplomacy_package_09/test_source.py': [(70,
                                                           70,
                                                           '',
                                                           'from diplomacy_package_19.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE19_NEW, '
                                                           'package19_original_bytes, '
                                                           'package19_historical_existing,\n'
                                                           '    package19_original_validator_bytes, '
                                                           'historical_actions as package19_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package19_owned,\n'
                                                           ')\n'
                                                           'check_later_package19_owned()\n'),
                                                          (124,
                                                           125,
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
                                                           'LATER_PACKAGE18_NEW]\n',
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
                                                           'LATER_PACKAGE19_NEW]\n'),
                                                          (126,
                                                           127,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n')],
 'tools/validation/diplomacy_package_10/test_source.py': [(62,
                                                           62,
                                                           '',
                                                           'from diplomacy_package_19.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE19_NEW, '
                                                           'package19_original_bytes, '
                                                           'package19_historical_existing,\n'
                                                           '    package19_original_validator_bytes, '
                                                           'historical_actions as package19_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package19_owned,\n'
                                                           ')\n'
                                                           'check_later_package19_owned()\n'),
                                                          (204,
                                                           205,
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
                                                           'LATER_PACKAGE18_NEW]\n',
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
                                                           'LATER_PACKAGE19_NEW]\n'),
                                                          (206,
                                                           207,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n')],
 'tools/validation/diplomacy_package_11/test_source.py': [(55,
                                                           55,
                                                           '',
                                                           'from diplomacy_package_19.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE19_NEW, '
                                                           'package19_original_bytes, '
                                                           'package19_historical_existing,\n'
                                                           '    package19_original_validator_bytes, '
                                                           'historical_actions as package19_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package19_owned,\n'
                                                           ')\n'
                                                           'check_later_package19_owned()\n'),
                                                          (218,
                                                           220,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n'
                                                           '    changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW]\n',
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
                                                           'LATER_PACKAGE19_NEW]\n')],
 'tools/validation/diplomacy_package_12/test_source.py': [(41,
                                                           41,
                                                           '',
                                                           'from diplomacy_package_19.test_source import (\r\n'
                                                           '    NEW as LATER_PACKAGE19_NEW, '
                                                           'package19_original_bytes, '
                                                           'package19_historical_existing,\r\n'
                                                           '    package19_original_validator_bytes, '
                                                           'historical_actions as package19_historical_actions,\r\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package19_owned,\r\n'
                                                           ')\r\n'
                                                           'check_later_package19_owned()\r\n'),
                                                          (188,
                                                           189,
                                                           '    changed=[path for path in changed if path not in '
                                                           '(package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE))-EXISTING | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW]\r\n',
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
                                                           'LATER_PACKAGE19_NEW]\r\n'),
                                                          (190,
                                                           191,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\r\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\r\n')],
 'tools/validation/diplomacy_package_13/test_source.py': [(41,
                                                           41,
                                                           '',
                                                           'from diplomacy_package_19.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE19_NEW, '
                                                           'package19_original_bytes, '
                                                           'package19_historical_existing,\n'
                                                           '    package19_original_validator_bytes, '
                                                           'historical_actions as package19_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package19_owned,\n'
                                                           ')\n'
                                                           'check_later_package19_owned()\n'),
                                                          (201,
                                                           202,
                                                           '    changed=[path for path in changed if path not in '
                                                           '(package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE))-EXISTING | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW]\n',
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
                                                           'LATER_PACKAGE19_NEW]\n'),
                                                          (203,
                                                           204,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n')],
 'tools/validation/diplomacy_package_14/test_source.py': [(37,
                                                           37,
                                                           '',
                                                           'from diplomacy_package_19.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE19_NEW, '
                                                           'package19_original_bytes, '
                                                           'package19_historical_existing,\n'
                                                           '    package19_original_validator_bytes, '
                                                           'historical_actions as package19_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package19_owned,\n'
                                                           ')\n'
                                                           'check_later_package19_owned()\n'),
                                                          (217,
                                                           218,
                                                           '    changed=[path for path in changed if path not in '
                                                           'package15_historical_existing(BASELINE)-EXISTING | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW]\n',
                                                           '    changed=[path for path in changed if path not in '
                                                           'package15_historical_existing(BASELINE)-EXISTING | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW]\n'),
                                                          (219,
                                                           220,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW]\n')],
 'tools/validation/diplomacy_package_15/test_source.py': [(29,
                                                           29,
                                                           '',
                                                           'from diplomacy_package_19.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE19_NEW, '
                                                           'package19_original_bytes, '
                                                           'package19_historical_existing,\n'
                                                           '    package19_original_validator_bytes, '
                                                           'historical_actions as package19_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package19_owned,\n'
                                                           ')\n'
                                                           'check_later_package19_owned()\n'),
                                                          (821,
                                                           823,
                                                           '    changed -= package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW\n'
                                                           '    added -= LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW\n',
                                                           '    changed -= package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW\n'
                                                           '    added -= LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW\n')],
 'tools/validation/diplomacy_package_16/test_source.py': [(29,
                                                           29,
                                                           '',
                                                           'from diplomacy_package_19.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE19_NEW, '
                                                           'package19_original_bytes, '
                                                           'package19_historical_existing,\n'
                                                           '    package19_original_validator_bytes, '
                                                           'historical_actions as package19_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package19_owned,\n'
                                                           ')\n'
                                                           'check_later_package19_owned()\n'),
                                                          (652,
                                                           654,
                                                           '    changed -= package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW\n'
                                                           '    untracked -= LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW\n',
                                                           '    changed -= package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW\n'
                                                           '    untracked -= LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW\n')],
 'tools/validation/diplomacy_package_17/test_source.py': [(23,
                                                           23,
                                                           '',
                                                           'from diplomacy_package_19.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE19_NEW, '
                                                           'package19_original_bytes, '
                                                           'package19_historical_existing,\n'
                                                           '    package19_original_validator_bytes, '
                                                           'historical_actions as package19_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package19_owned,\n'
                                                           ')\n'
                                                           'check_later_package19_owned()\n'),
                                                          (743,
                                                           745,
                                                           '    changed -= package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW\n'
                                                           '    untracked -= LATER_PACKAGE18_NEW\n',
                                                           '    changed -= package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW\n'
                                                           '    untracked -= LATER_PACKAGE18_NEW | '
                                                           'LATER_PACKAGE19_NEW\n')],
 'tools/validation/diplomacy_package_18/test_source.py': [(11,
                                                           11,
                                                           '',
                                                           'import sys as package19_sys\n'
                                                           'package19_sys.path.insert(0, str(ROOT / '
                                                           "'tools/validation'))\n"
                                                           'from diplomacy_package_19.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE19_NEW, '
                                                           'package19_original_bytes, '
                                                           'package19_historical_existing,\n'
                                                           '    package19_original_validator_bytes, '
                                                           'historical_actions as package19_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package19_owned,\n'
                                                           ')\n'
                                                           'check_later_package19_owned()\n'),
                                                          (103,
                                                           103,
                                                           '',
                                                           '    actual = package19_original_bytes(path, actual)\n'),
                                                          (121,
                                                           121,
                                                           '',
                                                           '    actions = package19_historical_actions(actions)\n'),
                                                          (709,
                                                           709,
                                                           '',
                                                           '    actual = package19_original_validator_bytes(path, '
                                                           'actual)\n'),
                                                          (732,
                                                           733,
                                                           '    raw = (ROOT / '
                                                           "'events/00_War_events.txt').read_bytes(); original = "
                                                           "baseline_bytes('events/00_War_events.txt')\n",
                                                           '    raw = '
                                                           "package19_original_bytes('events/00_War_events.txt', "
                                                           "(ROOT / 'events/00_War_events.txt').read_bytes()); "
                                                           "original = baseline_bytes('events/00_War_events.txt')\n"),
                                                          (745,
                                                           745,
                                                           '',
                                                           '    changed -= (package19_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE19_NEW\n'
                                                           '    untracked -= LATER_PACKAGE19_NEW\n'),
                                                          (842,
                                                           842,
                                                           '',
                                                           '    current_ids = '
                                                           'package19_historical_actions(current_ids)\n'),
                                                          (929,
                                                           930,
                                                           '    for path in unchanged: assert (ROOT / '
                                                           "path).read_bytes() == baseline_bytes(path), ('Prior "
                                                           'public behavior/helper/runner or unrelated source '
                                                           "changed', path)\n",
                                                           '    for path in unchanged: assert '
                                                           'package19_original_validator_bytes(path, (ROOT / '
                                                           "path).read_bytes()) == baseline_bytes(path), ('Prior "
                                                           'public behavior/helper/runner or unrelated source '
                                                           "changed', path)\n")]}


def package19_original_validator_bytes(path, actual):
    actual = package20_original_validator_bytes(path, actual)
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
    for path in SOURCE_PATHS: assert (ROOT / path).is_file(), ('Equipment-dispatch source missing', path)
    check_owned_existing()
    raw = package20_original_bytes('events/00_War_events.txt', (ROOT / 'events/00_War_events.txt').read_bytes()); original = baseline_bytes('events/00_War_events.txt')
    assert package19_original_bytes('events/00_War_events.txt', raw) == original
    passed('one_exact_named_option_byte_inverse_preserves_every_header_other_option_event_BOM_and_EOL')
    for path in sorted(NEW):
        data = (ROOT / path).read_bytes(); data.decode('utf-8-sig')
        assert data.endswith(b'\n') and b'\r' not in data.replace(b'\r\n', b'')
        assert data.startswith(b'\xef\xbb\xbf') == path.endswith('.yml')
        if not path.endswith('.yml'): ast(data)
        passed('seven_new_UTF8_scripts_or_BOM_bilingual_localisation_files')
    trees = ('common', 'history', 'events', 'interface', 'gfx', 'localisation', 'music', 'map', 'sound',
             'portraits', 'tutorial', 'descriptions', 'scenario_tests', 'descriptor.mod', 'era_of_nations.mod', 'thumbnail.png')
    changed = set(subprocess.check_output(['git', 'diff', '--name-only', BASELINE, '--', *trees], cwd=ROOT).decode().splitlines())
    untracked = set(subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', *trees], cwd=ROOT).decode().splitlines())
    changed -= (package20_historical_existing(BASELINE) - EXISTING) | LATER_PACKAGE20_NEW
    untracked -= LATER_PACKAGE20_NEW
    assert changed - NEW == EXISTING and (changed | untracked) - EXISTING == NEW, (changed, untracked)
    assert not subprocess.check_output(['git', 'diff', '--name-only', '--diff-filter=D', BASELINE, '--', *trees], cwd=ROOT).strip()
    passed('exact_gameplay_tree_one_existing_seven_new_no_unowned_deletions')
    before_events, after_events = event_blocks(original), event_blocks(raw)
    assert before_events.keys() == after_events.keys()
    passed('all_original_country_event_IDs_retained')
    for suffix in ('a', 'c', 'd'):
        assert option_raw(raw, 'AB_mobilization.4', 'AB_mobilization.4.' + suffix) == option_raw(original, 'AB_mobilization.4', 'AB_mobilization.4.' + suffix)
        passed('three_troop_cash_and_refusal_options_whole_raw_bytes_unchanged')
    old_choice = option_raw(original, 'AB_mobilization.4', 'AB_mobilization.4.b')
    choice_raw = option_raw(raw, 'AB_mobilization.4', 'AB_mobilization.4.b')
    old_choice_ast, choice = ast(old_choice)[0][2], ast(choice_raw)[0][2]
    assert one(choice, 'name') == one(old_choice_ast, 'name') and one(choice, 'log') == one(old_choice_ast, 'log')
    passed('equipment_choice_existing_name_and_log_ID_preserved')
    assert field_raw(choice_raw, 'ai_chance') == field_raw(old_choice, 'ai_chance')
    passed('original_donor_equipment_choice_AI_weight_full_raw_block_unchanged')
    assert ('eon_foreign_equipment_send_offer', '=', 'yes') in choice
    assert ('eon_foreign_equipment_offer_ready', '=', 'yes') in list(rows(one(choice, 'trigger')))
    assert not any(key in ('send_equipment', 'change_influence_percentage', 'country_event') for key, op, val in rows(choice))
    passed('existing_equipment_choice_only_offers_a_pair_guarded_unfunded_proposal')
    packets = [('medium_tank_amphibious_chassis', 250, 'apc'), ('medium_tank_flame_chassis', 250, 'ifv'),
        ('util_vehicle_equipment', 250, 'utility'), ('AA_Equipment', 250, 'manpads'), ('L_AT_Equipment', 250, 'atgm'),
        ('Inf_equipment', 1000, 'small_arms'), ('small_plane_suicide_airframe', 100, 'drone'),
        ('guided_missile_equipment', 100, 'cruise'), ('ballistic_missile_equipment', 100, 'ballistic')]
    effects = {key: body for key, op, body in ast((ROOT / FX).read_bytes())}
    triggers = {key: body for key, op, body in ast((ROOT / TR).read_bytes())}
    expected_effects = {'eon_foreign_equipment_' + name for name in ('freeze_manifest', 'show_manifest', 'clear_pending',
        'retire_pending_pair', 'send_offer', 'accept_offer', 'commit_offer', 'reject_offer', 'withdraw_offer',
        'daily_update', 'annex_update', 'clear_annexed_country')}
    expected_triggers = {'eon_foreign_equipment_' + name for name in ('bundle_available', 'manifest_valid', 'manifest_stocked',
        'policy_allowed', 'partner_identified', 'offer_ready', 'response_pending', 'response_open', 'response_ready',
        'commit_pending', 'commit_ready', 'withdraw_available')}
    assert effects.keys() == expected_effects and triggers.keys() == expected_triggers
    passed('exact_twelve_effect_and_twelve_trigger_API_sets')
    known = set(effects) | set(triggers)
    for helper in sorted(known):
        folder = 'scripted_effects' if helper in effects else 'scripted_triggers'
        pattern = rb'(?m)^' + re.escape(helper.encode()) + rb'\s*=\s*{'
        assert sum(len(re.findall(pattern, path.read_bytes())) for path in (ROOT / 'common' / folder).glob('*.txt')) == 1, helper
        passed('twenty_four_owned_helpers_globally_unique')
    for path in (FX, TR, NA, HOOKS, EVENTS):
        for key, op, value in rows(ast((ROOT / path).read_bytes())):
            if key.startswith('eon_foreign_equipment_') and value in ('yes', 'no'): assert key in known, (path, key)
        passed('five_current_helper_reference_sets_resolve')
    queries = [('has_equipment', '=', [(equipment, '>', str(amount - 1))]) for equipment, amount, suffix in packets]
    packet_flags = ['eon_foreign_equipment_packet_' + suffix for equipment, amount, suffix in packets]
    assert triggers['eon_foreign_equipment_bundle_available'] == [('OR', '=', queries)]
    assert triggers['eon_foreign_equipment_manifest_valid'] == [('OR', '=', [('has_country_flag', '=', flag) for flag in packet_flags])]
    passed('offer_requires_nonempty_subset_of_complete_original_packets_and_valid_manifest_requires_one_selected_type')
    stocked = triggers['eon_foreign_equipment_manifest_stocked']
    assert stocked[0] == ('eon_foreign_equipment_manifest_valid', '=', 'yes')
    assert stocked[1:] == [('if', '=', [('limit', '=', [('has_country_flag', '=', flag)]), query]) for flag, query in zip(packet_flags, queries)]
    passed('all_selected_full_stocks_rechecked_as_conjunction_without_shrink_or_unselected_expansion')
    freeze_expected = []
    for flag, query in zip(packet_flags, queries):
        freeze_expected += [('clr_country_flag', '=', flag), ('if', '=', [('limit', '=', [query]), ('set_country_flag', '=', flag)])]
    assert effects['eon_foreign_equipment_freeze_manifest'] == freeze_expected
    passed('nine_manifest_flags_frozen_from_current_complete_stored_count_queries_only')
    send = one(effects['eon_foreign_equipment_send_offer'], 'if')
    assert one(send, 'limit') == [('eon_foreign_equipment_offer_ready', '=', 'yes')]
    assert send[1] == ('eon_foreign_equipment_freeze_manifest', '=', 'yes')
    assert ('set_country_flag', '=', [('flag', '=', 'eon_foreign_equipment_live'), ('days', '=', '30'), ('value', '=', '1')]) in send
    passed('guarded_offer_freezes_manifest_before_one_pair_and_owned_thirty_day_reply_record')
    accept = one(effects['eon_foreign_equipment_accept_offer'], 'if')
    assert one(accept, 'limit') == [('eon_foreign_equipment_response_open', '=', 'yes')]
    assert not any(key in ('send_equipment', 'change_influence_percentage') for key, op, val in rows(accept))
    accepted = next(val for key, op, val in accept if key == 'if')
    assert one(accepted, 'limit') == [('eon_foreign_equipment_response_ready', '=', 'yes')]
    assert one(accepted, 'FROM') == [('set_country_flag', '=', 'eon_foreign_equipment_consented'), ('country_event', '=', [('id', '=', 'eon_foreign_equipment.2')])]
    passed('recipient_consent_has_no_equipment_or_influence_call_and_queues_provider_frame_once')
    outer = one(effects['eon_foreign_equipment_commit_offer'], 'if')
    assert one(outer, 'limit') == [('eon_foreign_equipment_commit_pending', '=', 'yes')]
    commit = next(val for key, op, val in outer if key == 'if')
    assert one(commit, 'limit') == [('eon_foreign_equipment_commit_ready', '=', 'yes')]
    consume = commit.index(('eon_foreign_equipment_clear_pending', '=', 'yes'))
    snapshots = []
    for flag, (equipment, amount, suffix) in zip(packet_flags, packets):
        dispatch = 'eon_foreign_equipment_dispatch_' + suffix
        snapshots += [('set_temp_variable', '=', [(dispatch, '=', '0')]),
            ('if', '=', [('limit', '=', [('has_country_flag', '=', flag)]), ('set_temp_variable', '=', [(dispatch, '=', '1')])])]
    assert commit[1:consume] == snapshots
    passed('all_nine_provider_temporary_dispatch_bits_initialized_and_snapshotted_before_owned_record_consumption')
    original_calls = [row for row in old_choice_ast if row[0] == 'send_equipment']
    assert len(original_calls) == 9
    for index, (equipment, amount, suffix) in enumerate(packets):
        original_call = original_calls[index]
        assert original_call == ('send_equipment', '=', [('equipment', '=', equipment), ('amount', '=', str(amount)), ('target', '=', 'FROM')])
        branch = commit[consume + 1 + index]
        assert branch == ('if', '=', [('limit', '=', [('check_variable', '=', [('eon_foreign_equipment_dispatch_' + suffix, '=', '1')])]), original_call])
        passed('nine_native_dispatch_calls_keep_original_equipment_full_amount_target_and_order_with_frozen_snapshot_guard')
    original_macro = [row for row in old_choice_ast if row[0] in ('set_temp_variable', 'change_influence_percentage')]
    assert len(original_macro) == 4 and commit[consume + 10:consume + 14] == original_macro
    passed('original_plus_three_influence_macro_parameter_sequence_after_selected_dispatch_calls_in_provider_frame')
    assert sum(key == 'send_equipment' for key, op, val in rows(ast((ROOT / FX).read_bytes()))) == 9
    assert not any(key == 'country_event' and (val == 'AB_mobilization.6' or isinstance(val, list) and one(val, 'id') == 'AB_mobilization.6') for key, op, val in rows(ast((ROOT / FX).read_bytes())))
    passed('only_nine_owned_native_dispatch_sites_and_no_original_arrival_claim_AB6_callback')
    for name in ('offer_ready', 'commit_ready'):
        body = triggers['eon_foreign_equipment_' + name]
        receiver = one(body, 'FROM')
        assert receiver[0] == ('set_temp_variable', '=', [('eon_foreign_equipment_policy_provider', '=', 'PREV.eon_foreign_equipment_selection_provider')])
        assert ('eon_foreign_equipment_policy_allowed', '=', 'yes') in receiver
        expected = 'bundle_available' if name == 'offer_ready' else 'manifest_stocked'
        assert ('var:eon_foreign_equipment_policy_provider', '=', [('eon_foreign_equipment_' + expected, '=', 'yes')]) in receiver
        passed('offer_and_commit_recheck_current_provider_stock_in_explicit_previous_country_identity_scope')
    ready = triggers['eon_foreign_equipment_response_ready']
    assert ('set_temp_variable', '=', [('eon_foreign_equipment_policy_provider', '=', 'FROM')]) in ready
    assert ('eon_foreign_equipment_policy_allowed', '=', 'yes') in ready
    assert ('var:eon_foreign_equipment_policy_provider', '=', [('eon_foreign_equipment_manifest_stocked', '=', 'yes')]) in ready
    passed('recipient_assent_rechecks_frozen_provider_manifest_in_country_scope')
    policy = triggers['eon_foreign_equipment_policy_allowed']
    assert ('has_defensive_war', '=', 'yes') in policy and ('NOT', '=', [('has_war_with', '=', 'eon_foreign_equipment_policy_provider')]) in policy
    assert one(policy, 'OR') == [('has_idea', '=', name) for name in ('non_power', 'minor_power', 'regional_power')]
    provider_policy = one(policy, 'var:eon_foreign_equipment_policy_provider')
    assert one(provider_policy, 'OR') == [('has_idea', '=', name) for name in ('large_power', 'great_power', 'superpower')]
    assert ('has_country_flag', '=', 'aid_request_cd_@PREV') in provider_policy
    assert one(provider_policy, 'has_opinion') == [('target', '=', 'PREV'), ('value', '>', '49')]
    passed('unchanged_AB_nominal_request_rank_opinion_and_defensive_war_policies_with_fresh_pair_no_enemy_guard')
    clear = effects['eon_foreign_equipment_clear_pending']
    assert clear == [('clr_country_flag', '=', 'eon_foreign_equipment_' + name) for name in ('pending', 'live', 'cancelled', 'consented')] + [
        ('clear_variable', '=', 'eon_foreign_equipment_partner')] + [('clr_country_flag', '=', flag) for flag in packet_flags]
    passed('cleanup_owns_only_equipment_state_and_nine_manifest_flags')
    display = one(effects['eon_foreign_equipment_show_manifest'], 'if')
    assert one(display, 'limit') == [('eon_foreign_equipment_response_pending', '=', 'yes')]
    assert display[1] == ('custom_effect_tooltip', '=', 'eon_foreign_equipment_manifest_header_tt')
    assert one(display, 'FROM') == [('if', '=', [('limit', '=', [('has_country_flag', '=', flag)]),
        ('custom_effect_tooltip', '=', 'eon_foreign_equipment_manifest_' + suffix + '_tt')]) for flag, (equipment, amount, suffix) in zip(packet_flags, packets)]
    passed('manifest_display_pair_guard_header_and_only_selected_literal_type_tooltips_have_no_asset_effect')
    locales = {language: locale_lines((ROOT / f'localisation/{language}/eon_foreign_equipment_l_{language}.yml').read_bytes()) for language in ('english', 'russian')}
    assert locales['english'].keys() == locales['russian'].keys()
    passed('bilingual_locale_key_sets_match')
    for equipment, amount, suffix in packets:
        for language in ('english', 'russian'):
            assert '§Y' + str(amount) + '§!' in locales[language]['eon_foreign_equipment_manifest_' + suffix + '_tt']
            passed('eighteen_manifest_tooltip_values_show_exact_original_full_amount_in_both_languages')
        pattern = rb'(?m)^\s*' + re.escape(equipment.encode()) + rb'\s*=\s*{'
        assert any(re.search(pattern, path.read_bytes()) for path in (ROOT / 'common/units/equipment').glob('*.txt')), equipment
        passed('nine_original_equipment_archetype_IDs_resolve_in_mod_equipment_or_duplicate_archetype_source')
    for path in (TR, NA, EVENTS, FX, 'events/00_War_events.txt'):
        for key, op, val in rows(ast((ROOT / path).read_bytes())):
            if key in ('tooltip', 'custom_effect_tooltip', 'title', 'desc', 'name', 'send_description') and isinstance(val, str) and val.startswith('eon_foreign_equipment'):
                assert val in locales['english'], (path, val)
        passed('five_current_tooltip_action_choice_event_manifest_locale_reference_sets_resolve')
    for path in (FX, TR):
        nodes = list(rows(ast((ROOT / path).read_bytes())))
        assert not any(key in ('modify_treasury_effect', 'add_political_power', 'add_manpower', 'add_command_power', 'add_fuel',
            'add_equipment_to_stockpile', 'add_ideas', 'add_timed_idea', 'create_unit', 'delete_unit_template_and_units',
            'declare_war_on', 'white_peace', 'add_to_faction', 'create_faction', 'set_rule') for key, op, val in nodes)
        passed('equipment_helpers_do_not_invent_cash_PP_personnel_stock_mutations_units_wars_or_services')
        assert not any(key == 'NOT' and len(val) != 1 for key, op, val in nodes)
        passed('native_NOT_blocks_single_child_unambiguous_NOR_semantics')
        for key, op, val in nodes:
            if key in ('clr_country_flag', 'clear_variable'): assert val.startswith('eon_foreign_equipment_')
        passed('clear_operations_cannot_remove_AB_request_marker_cash_or_other_diplomatic_fields')
    for path in ('common/scripted_diplomatic_actions/MDDC_AB_ask_foreign_support.txt', 'events/00_Influence_events.txt',
        'common/scripted_effects/00_influence_scripted_effects.txt', 'common/scripted_effects/00_budget_effects.txt',
        'common/scripted_guis/influence_scripted_gui.txt', 'localisation/english/MD_decisions_l_english.yml',
        'localisation/russian/MD_decisions_l_russian.yml') + tuple(sorted({
        'common/scripted_effects/eon_foreign_cash_effects.txt', 'common/scripted_triggers/eon_foreign_cash_triggers.txt',
        'common/scripted_diplomatic_actions/eon_foreign_cash_actions.txt', 'common/on_actions/eon_foreign_cash_on_actions.txt',
        'events/eon_foreign_cash_events.txt', 'localisation/english/eon_foreign_cash_l_english.yml', 'localisation/russian/eon_foreign_cash_l_russian.yml'})):
        assert package20_original_bytes(path, (ROOT / path).read_bytes()) == baseline_bytes(path)
        passed('fourteen_original_entry_cash_mercenary_service_GUI_macro_budget_and_AB6_locale_sources_whole_raw_unchanged')
    entry = one(one(ast(baseline_bytes('common/scripted_diplomatic_actions/MDDC_AB_ask_foreign_support.txt')), 'scripted_diplomatic_actions'), 'AB_ask_foreign_support')
    assert one(entry, 'cost') == '50' and one(entry, 'requires_acceptance') == 'no'
    assert ('set_country_flag', '=', [('flag', '=', 'aid_request_cd_@ROOT'), ('days', '=', '360'), ('value', '=', '1')]) in list(rows(entry))
    passed('AB_entry_50_PP_and_360_day_marker_are_unchanged_nominal_declarations_without_native_charge_or_unique_receipt_claim')
    influence = one(ast(baseline_bytes('common/scripted_effects/00_influence_scripted_effects.txt')), 'change_influence_percentage')
    assert any(key == 'ROOT' and any(child == 'has_resources_rights' for child, op, val in rows(body)) for key, op, body in rows(influence) if isinstance(body, list))
    passed('original_influence_ROOT_dependency_requires_preserved_provider_frame')
    native = one(ast((ROOT / NA).read_bytes()), 'scripted_diplomatic_actions')
    assert {key for key, op, value in native} == NEW_ACTION_IDS
    native_body = one(native, 'eon_foreign_equipment_withdraw_offer')
    assert one(native_body, 'cost') == '0' and one(native_body, 'requires_acceptance') == 'no'
    assert one(native_body, 'allowed') == [('ROOT', '=', [('is_ai', '=', 'no')])]
    assert one(native_body, 'ai_desire') == [('factor', '=', '0')]
    for field in ('visible', 'selectable', 'can_be_sent'):
        assert one(native_body, field) == [('eon_foreign_equipment_withdraw_available', '=', 'yes')]
        passed('three_fresh_native_free_withdraw_guards')
    passed('exact_one_free_human_withdraw_action')
    native_paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, '--', 'common/scripted_diplomatic_actions'], cwd=ROOT).decode().splitlines()
    old_ids = [key for path in native_paths if path.endswith('.txt') for key, op, body in one(ast(baseline_bytes(path)), 'scripted_diplomatic_actions')]
    current_ids = [key for path in (ROOT / 'common/scripted_diplomatic_actions').glob('*.txt') for key, op, body in one(ast(path.read_bytes()), 'scripted_diplomatic_actions')]
    current_ids = package20_historical_actions(current_ids)
    assert len(old_ids) == len(set(old_ids)) == 70 and len(current_ids) == len(set(current_ids)) == 71
    assert set(current_ids) == set(old_ids) | NEW_ACTION_IDS
    passed('70_original_native_actions_plus_one_unique_equipment_withdrawal')
    events = {one(body, 'id'): body for key, op, body in ast((ROOT / EVENTS).read_bytes()) if key == 'country_event'}
    assert events.keys() == {'eon_foreign_equipment.' + str(i) for i in range(1, 8)}
    assert one(events['eon_foreign_equipment.2'], 'hidden') == 'yes'
    assert one(events['eon_foreign_equipment.2'], 'immediate') == [('eon_foreign_equipment_commit_offer', '=', 'yes')]
    passed('seven_new_event_IDs_and_hidden_provider_commit_frame')
    for identity, body in events.items():
        pattern = rb'(?m)^\s*id\s*=\s*' + re.escape(identity.encode()) + rb'(?![A-Za-z0-9_.])'
        assert sum(len(re.findall(pattern, path.read_bytes())) for path in (ROOT / 'events').glob('*.txt')) == 1, identity
        passed('seven_new_event_definitions_globally_unique')
        if identity not in ('eon_foreign_equipment.1', 'eon_foreign_equipment.2'):
            assert one(body, 'option') == [('name', '=', 'eon_foreign_equipment.ack')]
            passed('five_notifications_have_static_ACK_only')
    choices = [body for key, op, body in events['eon_foreign_equipment.1'] if key == 'option']
    assert [one(body, 'name') for body in choices] == ['eon_foreign_equipment.1.a', 'eon_foreign_equipment.1.b', 'eon_foreign_equipment.ack']
    assert one(choices[0], 'trigger') == [('eon_foreign_equipment_response_ready', '=', 'yes')]
    assert one(choices[1], 'trigger') == [('eon_foreign_equipment_response_open', '=', 'yes')]
    assert one(choices[2], 'trigger') == [('NOT', '=', [('eon_foreign_equipment_response_open', '=', 'yes')])]
    passed('recipient_accept_decline_and_ACK_use_current_owned_response_frame_guards')
    for body in choices:
        assert ('eon_foreign_equipment_show_manifest', '=', 'yes') in body
        passed('all_three_recipient_options_render_the_same_owned_manifest_before_response_effects')
    try: package19_original_bytes('events/00_War_events.txt', raw + b'\n# memory-only outside-range probe\n')
    except AssertionError: pass
    else: raise AssertionError('Unowned outside game bytes accepted')
    passed('memory_only_game_source_outside_named_equipment_option_mutation_rejected'); boundary_groups.add('memory_only_game_source_outside_named_equipment_option_mutation_rejected')
    assert set(HISTORICAL_SOURCE_EDITS) == {f'tools/validation/diplomacy_package_{i:02}/test_source.py' for i in range(2, 19)}
    for path in sorted(HISTORICAL_SOURCE_EDITS):
        actual = (ROOT / path).read_bytes()
        assert package19_original_validator_bytes(path, actual) == baseline_bytes(path)
        original_counters = [line for line in baseline_bytes(path).splitlines() if b'groups[' in line and b'+=' in line or b'passed(' in line]
        current_counters = [line for line in actual.splitlines() if b'groups[' in line and b'+=' in line or b'passed(' in line]
        assert original_counters == current_counters, ('Historical counter lines changed', path)
        passed('seventeen_literal_whole_source_validator_journals_and_all_original_counter_lines')
        try: package19_original_validator_bytes(path, actual + b'\n# memory-only undeclared validator probe\n')
        except AssertionError: pass
        else: raise AssertionError(('Undeclared historical source bytes accepted', path))
        passed('memory_only_whole_historical_source_mutation_rejected'); boundary_groups.add('memory_only_whole_historical_source_mutation_rejected')
    public_paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, '--', 'tools/validation'], cwd=ROOT).decode().splitlines()
    unchanged = [path for path in public_paths if path not in HISTORICAL_SOURCE_EDITS]
    for path in unchanged: assert package20_original_validator_bytes(path, (ROOT / path).read_bytes()) == baseline_bytes(path), ('Prior public behavior/helper/runner or unrelated source changed', path)
    passed('all_other_prior_public_validation_files_whole_raw_bytes_unchanged')
    behavior = [path for path in unchanged if path.endswith('.py') and Path(path).name != 'test_source.py']
    assert len(behavior) == 47 and len(unchanged) == 65
    passed('enumerated_47_prior_behavior_helpers_runners_and_65_other_public_files_raw_byte_exact')
    installed = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV')
    effect_docs = (installed / 'documentation/effects_documentation.md').read_text(encoding='utf-8-sig')
    trigger_docs = (installed / 'documentation/triggers_documentation.md').read_text(encoding='utf-8-sig')
    for helper in ('set_temp_variable', 'check_variable', 'set_variable', 'clear_variable', 'set_country_flag', 'clr_country_flag', 'every_country', 'country_event'):
        assert '\n## ' + helper + '\n' in effect_docs or '\n## ' + helper + '\n' in trigger_docs
        passed('eight_installed_primary_effect_and_trigger_API_declarations')
    for helper in ('exists', 'has_war_with', 'has_idea', 'has_opinion', 'has_defensive_war', 'has_equipment'):
        assert '\n## ' + helper + '\n' in trigger_docs
        passed('six_installed_primary_policy_trigger_API_declarations')
    defensive_doc = trigger_docs.split('\n## has_defensive_war\n', 1)[1].split('\n## ', 1)[0]
    assert 'Supported Scopes: COUNTRY' in defensive_doc and 'is country at defensive war' in defensive_doc
    passed('defensive_war_is_a_country_classification_separate_from_generic_war_fixture')
    hookdocs = (installed / 'common/on_actions/_documentation.md').read_text(encoding='utf-8-sig')
    for identity in ('on_daily', 'on_annex', 'on_subject_annexed'):
        assert identity in hookdocs
        passed('three_installed_native_hook_declarations')
    send_doc = effect_docs.split('\n## send_equipment\n', 1)[1].split('\n## ', 1)[0]
    stock_doc = trigger_docs.split('\n## has_equipment\n', 1)[1].split('\n## ', 1)[0]
    assert 'Supported Scopes: COUNTRY' in send_doc and 'Sends to target scope specified amount of equipment.' in send_doc
    assert 'Supported Scopes: COUNTRY' in stock_doc and 'checks for amount of equipment stored' in stock_doc
    passed('installed_native_send_and_stored_count_declarations_not_completion_or_stock_variant_proof')
    hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCE_PATHS}
    boundaries = sum(groups[group] for group in boundary_groups)
    print(json.dumps({'all_passed': True, 'baseline': BASELINE, 'source_API_cases': sum(groups.values()) - boundaries,
        'source_byte_adapter_boundary_cases': boundaries, 'source_cases': sum(groups.values()), 'groups': dict(groups),
        'source_sha256': hashes, 'historical_source_adapters': len(HISTORICAL_SOURCE_EDITS),
        'prior_behavior_helper_runner_raw_byte_files': len(behavior), 'prior_other_public_raw_byte_files': len(unchanged),
        'bilingual_locale_keys': len(locales['english']), 'native_runtime': False,
        'proof_scope': 'exact current-source equipment dispatch footprint/API and literal historical byte retention; not HOI4 runtime'}, indent=2))

if __name__ == '__main__': main()
