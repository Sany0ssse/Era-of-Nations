"""Exact cash-aid footprint and historical byte views; not native HOI4 runtime."""
from pathlib import Path
from functools import lru_cache
from collections import Counter
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '0a8063bf3bc732fbc7ab453b116ddf61e5c090d4'
EXISTING = {'events/00_War_events.txt'}
FX = 'common/scripted_effects/eon_foreign_cash_effects.txt'
TR = 'common/scripted_triggers/eon_foreign_cash_triggers.txt'
NA = 'common/scripted_diplomatic_actions/eon_foreign_cash_actions.txt'
HOOKS = 'common/on_actions/eon_foreign_cash_on_actions.txt'
EVENTS = 'events/eon_foreign_cash_events.txt'
NEW = {FX, TR, NA, HOOKS, EVENTS} | {f'localisation/{language}/eon_foreign_cash_l_{language}.yml' for language in ('english', 'russian')}
SOURCE_PATHS = sorted(EXISTING | NEW)
NEW_ACTION_IDS = {'eon_foreign_cash_withdraw_offer'}
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

def package18_original_bytes(path, actual):
    """Restore one named option; headers, other options and every outside byte stay exact."""
    if path not in EXISTING: return actual
    original = baseline_bytes(path); format_preserved(original, actual, path)
    assert event_blocks(original).keys() == event_blocks(actual).keys(), ('Existing event IDs changed', path)
    old = option_block(original, 'AB_mobilization.4', 'AB_mobilization.4.c')
    new = option_block(actual, 'AB_mobilization.4', 'AB_mobilization.4.c')
    restored = actual[:new['start']] + original[old['start']:old['end']] + actual[new['end']:]
    assert restored == original, ('Unowned foreign-support source bytes changed', path)
    return original

@lru_cache(maxsize=32)
def package18_historical_existing(baseline):
    return frozenset(subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', baseline, '--', *sorted(EXISTING)], cwd=ROOT).decode().splitlines())

def check_owned_existing():
    for path in sorted(EXISTING): package18_original_bytes(path, (ROOT / path).read_bytes())

def historical_actions(actions):
    return [identity for identity in actions if identity not in NEW_ACTION_IDS]

# Literal whole-file journals are populated only after all owned adapters are final.
HISTORICAL_SOURCE_EDITS = {'tools/validation/diplomacy_package_02/test_source.py': [(177,
                                                           178,
                                                           '                                               '
                                                           "'eon_withdraw_antiterror_proposal', "
                                                           "'eon_ammo_withdraw_offer', "
                                                           "'eon_services_withdraw_offer', "
                                                           "'eon_services_end_logistics', "
                                                           "'eon_services_end_recon')))\n",
                                                           '                                               '
                                                           "'eon_withdraw_antiterror_proposal', "
                                                           "'eon_ammo_withdraw_offer', "
                                                           "'eon_services_withdraw_offer', "
                                                           "'eon_services_end_logistics', 'eon_services_end_recon', "
                                                           "'eon_foreign_cash_withdraw_offer')))\n")],
 'tools/validation/diplomacy_package_03/test_source.py': [(65,
                                                           65,
                                                           '',
                                                           'from diplomacy_package_18.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE18_NEW, '
                                                           'package18_original_bytes, '
                                                           'package18_historical_existing,\n'
                                                           '    package18_original_validator_bytes, '
                                                           'historical_actions as package18_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package18_owned,\n'
                                                           ')\n'
                                                           'check_later_package18_owned()\n'),
                                                          (247,
                                                           248,
                                                           'tracked_changes = [path for path in tracked_changes if '
                                                           'path not in LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW]\n',
                                                           'tracked_changes = [path for path in tracked_changes if '
                                                           'path not in LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW]\n'),
                                                          (251,
                                                           252,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n')],
 'tools/validation/diplomacy_package_04/test_source.py': [(81,
                                                           81,
                                                           '',
                                                           'from diplomacy_package_18.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE18_NEW, '
                                                           'package18_original_bytes, '
                                                           'package18_historical_existing,\n'
                                                           '    package18_original_validator_bytes, '
                                                           'historical_actions as package18_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package18_owned,\n'
                                                           ')\n'
                                                           'check_later_package18_owned()\n'),
                                                          (344,
                                                           345,
                                                           'tracked = [path for path in tracked if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW]\n',
                                                           'tracked = [path for path in tracked if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW]\n'),
                                                          (346,
                                                           347,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n')],
 'tools/validation/diplomacy_package_05/test_source.py': [(76,
                                                           76,
                                                           '',
                                                           'from diplomacy_package_18.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE18_NEW, '
                                                           'package18_original_bytes, '
                                                           'package18_historical_existing,\n'
                                                           '    package18_original_validator_bytes, '
                                                           'historical_actions as package18_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package18_owned,\n'
                                                           ')\n'
                                                           'check_later_package18_owned()\n'),
                                                          (285,
                                                           286,
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW]\n',
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW]\n'),
                                                          (287,
                                                           288,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n')],
 'tools/validation/diplomacy_package_06/test_source.py': [(78,
                                                           78,
                                                           '',
                                                           'from diplomacy_package_18.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE18_NEW, '
                                                           'package18_original_bytes, '
                                                           'package18_historical_existing,\n'
                                                           '    package18_original_validator_bytes, '
                                                           'historical_actions as package18_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package18_owned,\n'
                                                           ')\n'
                                                           'check_later_package18_owned()\n'),
                                                          (459,
                                                           460,
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW]\n',
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW]\n'),
                                                          (461,
                                                           462,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n')],
 'tools/validation/diplomacy_package_07/test_source.py': [(76,
                                                           76,
                                                           '',
                                                           'from diplomacy_package_18.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE18_NEW, '
                                                           'package18_original_bytes, '
                                                           'package18_historical_existing,\n'
                                                           '    package18_original_validator_bytes, '
                                                           'historical_actions as package18_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package18_owned,\n'
                                                           ')\n'
                                                           'check_later_package18_owned()\n'),
                                                          (138,
                                                           139,
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW]\n',
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
                                                           'LATER_PACKAGE18_NEW]\n'),
                                                          (140,
                                                           141,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n')],
 'tools/validation/diplomacy_package_08/test_source.py': [(76,
                                                           76,
                                                           '',
                                                           'from diplomacy_package_18.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE18_NEW, '
                                                           'package18_original_bytes, '
                                                           'package18_historical_existing,\n'
                                                           '    package18_original_validator_bytes, '
                                                           'historical_actions as package18_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package18_owned,\n'
                                                           ')\n'
                                                           'check_later_package18_owned()\n'),
                                                          (135,
                                                           136,
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW]\n',
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
                                                           'LATER_PACKAGE18_NEW]\n'),
                                                          (137,
                                                           138,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n')],
 'tools/validation/diplomacy_package_09/test_source.py': [(64,
                                                           64,
                                                           '',
                                                           'from diplomacy_package_18.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE18_NEW, '
                                                           'package18_original_bytes, '
                                                           'package18_historical_existing,\n'
                                                           '    package18_original_validator_bytes, '
                                                           'historical_actions as package18_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package18_owned,\n'
                                                           ')\n'
                                                           'check_later_package18_owned()\n'),
                                                          (118,
                                                           119,
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW]\n',
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
                                                           'LATER_PACKAGE18_NEW]\n'),
                                                          (120,
                                                           121,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n')],
 'tools/validation/diplomacy_package_10/test_source.py': [(56,
                                                           56,
                                                           '',
                                                           'from diplomacy_package_18.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE18_NEW, '
                                                           'package18_original_bytes, '
                                                           'package18_historical_existing,\n'
                                                           '    package18_original_validator_bytes, '
                                                           'historical_actions as package18_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package18_owned,\n'
                                                           ')\n'
                                                           'check_later_package18_owned()\n'),
                                                          (198,
                                                           199,
                                                           '    changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE11_EXISTING | LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW]\n',
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
                                                           'LATER_PACKAGE18_NEW]\n'),
                                                          (200,
                                                           201,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n')],
 'tools/validation/diplomacy_package_11/test_source.py': [(49,
                                                           49,
                                                           '',
                                                           'from diplomacy_package_18.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE18_NEW, '
                                                           'package18_original_bytes, '
                                                           'package18_historical_existing,\n'
                                                           '    package18_original_validator_bytes, '
                                                           'historical_actions as package18_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package18_owned,\n'
                                                           ')\n'
                                                           'check_later_package18_owned()\n'),
                                                          (212,
                                                           214,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW]\n'
                                                           '    changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW]\n',
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
                                                           'LATER_PACKAGE18_NEW]\n')],
 'tools/validation/diplomacy_package_12/test_source.py': [(35,
                                                           35,
                                                           '',
                                                           'from diplomacy_package_18.test_source import (\r\n'
                                                           '    NEW as LATER_PACKAGE18_NEW, '
                                                           'package18_original_bytes, '
                                                           'package18_historical_existing,\r\n'
                                                           '    package18_original_validator_bytes, '
                                                           'historical_actions as package18_historical_actions,\r\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package18_owned,\r\n'
                                                           ')\r\n'
                                                           'check_later_package18_owned()\r\n'),
                                                          (182,
                                                           183,
                                                           '    changed=[path for path in changed if path not in '
                                                           '(package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE))-EXISTING | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW]\r\n',
                                                           '    changed=[path for path in changed if path not in '
                                                           '(package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE))-EXISTING | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW]\r\n'),
                                                          (184,
                                                           185,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW]\r\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\r\n')],
 'tools/validation/diplomacy_package_13/test_source.py': [(35,
                                                           35,
                                                           '',
                                                           'from diplomacy_package_18.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE18_NEW, '
                                                           'package18_original_bytes, '
                                                           'package18_historical_existing,\n'
                                                           '    package18_original_validator_bytes, '
                                                           'historical_actions as package18_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package18_owned,\n'
                                                           ')\n'
                                                           'check_later_package18_owned()\n'),
                                                          (195,
                                                           196,
                                                           '    changed=[path for path in changed if path not in '
                                                           '(package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE))-EXISTING | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW]\n',
                                                           '    changed=[path for path in changed if path not in '
                                                           '(package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE))-EXISTING | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW]\n'),
                                                          (197,
                                                           198,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n')],
 'tools/validation/diplomacy_package_14/test_source.py': [(31,
                                                           31,
                                                           '',
                                                           'from diplomacy_package_18.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE18_NEW, '
                                                           'package18_original_bytes, '
                                                           'package18_historical_existing,\n'
                                                           '    package18_original_validator_bytes, '
                                                           'historical_actions as package18_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package18_owned,\n'
                                                           ')\n'
                                                           'check_later_package18_owned()\n'),
                                                          (211,
                                                           212,
                                                           '    changed=[path for path in changed if path not in '
                                                           'package15_historical_existing(BASELINE)-EXISTING | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW]\n',
                                                           '    changed=[path for path in changed if path not in '
                                                           'package15_historical_existing(BASELINE)-EXISTING | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW]\n'),
                                                          (213,
                                                           214,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW]\n')],
 'tools/validation/diplomacy_package_15/test_source.py': [(23,
                                                           23,
                                                           '',
                                                           'from diplomacy_package_18.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE18_NEW, '
                                                           'package18_original_bytes, '
                                                           'package18_historical_existing,\n'
                                                           '    package18_original_validator_bytes, '
                                                           'historical_actions as package18_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package18_owned,\n'
                                                           ')\n'
                                                           'check_later_package18_owned()\n'),
                                                          (815,
                                                           817,
                                                           '    changed -= package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW\n'
                                                           '    added -= LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW\n',
                                                           '    changed -= package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW\n'
                                                           '    added -= LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW\n')],
 'tools/validation/diplomacy_package_16/test_source.py': [(23,
                                                           23,
                                                           '',
                                                           'from diplomacy_package_18.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE18_NEW, '
                                                           'package18_original_bytes, '
                                                           'package18_historical_existing,\n'
                                                           '    package18_original_validator_bytes, '
                                                           'historical_actions as package18_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package18_owned,\n'
                                                           ')\n'
                                                           'check_later_package18_owned()\n'),
                                                          (646,
                                                           648,
                                                           '    changed -= package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW\n'
                                                           '    untracked -= LATER_PACKAGE17_NEW\n',
                                                           '    changed -= package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW\n'
                                                           '    untracked -= LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW\n')],
 'tools/validation/diplomacy_package_17/test_source.py': [(15,
                                                           15,
                                                           '',
                                                           'import sys as package18_sys\n'
                                                           'package18_sys.path.insert(0, str(ROOT / '
                                                           "'tools/validation'))\n"
                                                           'from diplomacy_package_18.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE18_NEW, '
                                                           'package18_original_bytes, '
                                                           'package18_historical_existing,\n'
                                                           '    package18_original_validator_bytes, '
                                                           'historical_actions as package18_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package18_owned,\n'
                                                           ')\n'
                                                           'check_later_package18_owned()\n'),
                                                          (123,
                                                           123,
                                                           '',
                                                           '    actions = package18_historical_actions(actions)\n'),
                                                          (705,
                                                           705,
                                                           '',
                                                           '    actual = package18_original_validator_bytes(path, '
                                                           'actual)\n'),
                                                          (733,
                                                           733,
                                                           '',
                                                           '    changed -= package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW\n'
                                                           '    untracked -= LATER_PACKAGE18_NEW\n'),
                                                          (807,
                                                           807,
                                                           '',
                                                           '    native_ids = '
                                                           'package18_historical_actions(native_ids)\n'),
                                                          (905,
                                                           906,
                                                           '        assert (ROOT / path).read_bytes() == '
                                                           "baseline_bytes(path), ('Earlier behavior/helper/runner "
                                                           "or unrelated public source changed', path)\n",
                                                           '        assert package18_original_validator_bytes(path, '
                                                           '(ROOT / path).read_bytes()) == baseline_bytes(path), '
                                                           "('Earlier behavior/helper/runner or unrelated public "
                                                           "source changed', path)\n")]}

def package18_original_validator_bytes(path, actual):
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
    for path in SOURCE_PATHS: assert (ROOT / path).is_file(), ('Cash-aid source missing', path)
    check_owned_existing()
    raw = (ROOT / 'events/00_War_events.txt').read_bytes(); original = baseline_bytes('events/00_War_events.txt')
    assert package18_original_bytes('events/00_War_events.txt', raw) == original
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
    assert changed - NEW == EXISTING and (changed | untracked) - EXISTING == NEW, (changed, untracked)
    assert not subprocess.check_output(['git', 'diff', '--name-only', '--diff-filter=D', BASELINE, '--', *trees], cwd=ROOT).strip()
    passed('exact_gameplay_tree_one_existing_seven_new_no_unowned_deletions')
    before_events, after_events = event_blocks(original), event_blocks(raw)
    assert before_events.keys() == after_events.keys()
    passed('all_original_country_event_IDs_retained')
    for suffix in ('a', 'b', 'd'):
        assert option_raw(raw, 'AB_mobilization.4', 'AB_mobilization.4.' + suffix) == option_raw(original, 'AB_mobilization.4', 'AB_mobilization.4.' + suffix)
        passed('three_troop_equipment_and_refusal_options_whole_raw_bytes_unchanged')
    old_choice = option_raw(original, 'AB_mobilization.4', 'AB_mobilization.4.c')
    choice_raw = option_raw(raw, 'AB_mobilization.4', 'AB_mobilization.4.c')
    old_choice_ast, choice = ast(old_choice)[0][2], ast(choice_raw)[0][2]
    assert one(choice, 'name') == one(old_choice_ast, 'name') and one(choice, 'log') == one(old_choice_ast, 'log')
    passed('cash_choice_existing_name_and_log_ID_preserved')
    assert field_raw(choice_raw, 'ai_chance') == field_raw(old_choice, 'ai_chance')
    passed('original_donor_cash_choice_AI_weight_full_raw_block_unchanged')
    assert ('eon_foreign_cash_send_offer', '=', 'yes') in choice
    assert ('eon_foreign_cash_offer_ready', '=', 'yes') in list(rows(one(choice, 'trigger')))
    assert not any(key in ('modify_treasury_effect', 'change_influence_percentage', 'country_event') for key, op, val in rows(choice))
    passed('existing_cash_choice_only_offers_a_pair_guarded_unfunded_proposal')
    effects = {key: body for key, op, body in ast((ROOT / FX).read_bytes())}
    triggers = {key: body for key, op, body in ast((ROOT / TR).read_bytes())}
    expected_effects = {'eon_foreign_cash_' + key for key in ('clear_pending', 'retire_pending_pair', 'send_offer', 'accept_offer',
        'commit_offer', 'reject_offer', 'withdraw_offer', 'daily_update', 'annex_update', 'clear_annexed_country')}
    expected_triggers = {'eon_foreign_cash_' + key for key in ('policy_allowed', 'partner_identified', 'cash_available',
        'offer_ready', 'response_pending', 'response_open', 'response_ready', 'commit_pending', 'commit_ready', 'withdraw_available')}
    assert effects.keys() == expected_effects and triggers.keys() == expected_triggers
    passed('exact_ten_effect_and_ten_trigger_API_definition_sets')
    known = set(effects) | set(triggers)
    for helper in sorted(known):
        folder = 'scripted_effects' if helper in effects else 'scripted_triggers'
        pattern = rb'(?m)^' + re.escape(helper.encode()) + rb'\s*=\s*{'
        assert sum(len(re.findall(pattern, path.read_bytes())) for path in (ROOT / 'common' / folder).glob('*.txt')) == 1, helper
        passed('twenty_owned_helpers_globally_unique')
    for path in (FX, TR, NA, HOOKS, EVENTS):
        for key, op, value in rows(ast((ROOT / path).read_bytes())):
            if key.startswith('eon_foreign_cash_') and value in ('yes', 'no'): assert key in known, (path, key)
        passed('five_current_helper_reference_sets_resolve')
    accept = one(effects['eon_foreign_cash_accept_offer'], 'if')
    assert one(accept, 'limit') == [('eon_foreign_cash_response_open', '=', 'yes')]
    assert not any(key in ('modify_treasury_effect', 'change_influence_percentage') for key, op, val in rows(accept))
    passed('recipient_assent_requires_open_pair_and_has_no_cash_or_influence_effect')
    accepted = next(val for key, op, val in accept if key == 'if')
    assert one(accepted, 'limit') == [('eon_foreign_cash_response_ready', '=', 'yes')]
    assert one(accepted, 'FROM') == [('set_country_flag', '=', 'eon_foreign_cash_consented'), ('country_event', '=', [('id', '=', 'eon_foreign_cash.2')])]
    passed('fresh_recipient_assent_marks_consent_once_before_queueing_provider_commit')
    commit_outer = one(effects['eon_foreign_cash_commit_offer'], 'if')
    assert one(commit_outer, 'limit') == [('eon_foreign_cash_commit_pending', '=', 'yes')]
    settlement = next(val for key, op, val in commit_outer if key == 'if')
    assert one(settlement, 'limit') == [('eon_foreign_cash_commit_ready', '=', 'yes')]
    assert settlement[1] == ('eon_foreign_cash_clear_pending', '=', 'yes')
    passed('provider_commit_requires_exact_consented_pair_and_fresh_readiness_then_consumes_before_effects')
    original_settlement = [row for row in old_choice_ast if row[0] not in ('name', 'log', 'ai_chance')]
    assert settlement[2:2+len(original_settlement)] == original_settlement
    passed('original_minus_seven_plus_seven_three_percent_and_AB7_ordered_settlement_AST_exact')
    assert sum(key == 'modify_treasury_effect' for key, op, val in rows(ast((ROOT / FX).read_bytes()))) == 2
    assert sum(key == 'change_influence_percentage' for key, op, val in rows(ast((ROOT / FX).read_bytes()))) == 1
    passed('only_two_treasury_calls_and_one_original_influence_call_in_the_commit_branch')
    for operation in ('offer_ready', 'commit_ready'):
        body = triggers['eon_foreign_cash_' + operation]
        receiver_scope = one(body, 'FROM')
        assert receiver_scope == [('set_temp_variable', '=', [('eon_foreign_cash_policy_provider', '=', 'PREV.eon_foreign_cash_selection_provider')]),
            ('eon_foreign_cash_policy_allowed', '=', 'yes'), ('eon_foreign_cash_cash_available', '=', 'yes')] + (
            [('var:eon_foreign_cash_policy_provider', '=', [('NOT', '=', [('has_country_flag', '=', 'eon_foreign_cash_retired_pair@PREV')])])]
            if operation == 'offer_ready' else [])
        passed('offer_and_provider_commit_use_explicit_previous_country_provider_identity_and_fresh_policy_cash')
    response_ready = triggers['eon_foreign_cash_response_ready']
    assert ('set_temp_variable', '=', [('eon_foreign_cash_policy_provider', '=', 'FROM')]) in response_ready
    assert ('eon_foreign_cash_policy_allowed', '=', 'yes') in response_ready and ('eon_foreign_cash_cash_available', '=', 'yes') in response_ready
    passed('recipient_frame_uses_explicit_original_provider_and_fresh_policy_cash')
    policy = triggers['eon_foreign_cash_policy_allowed']
    assert ('has_defensive_war', '=', 'yes') in policy
    assert one(policy, 'OR') == [('has_idea', '=', key) for key in ('non_power', 'minor_power', 'regional_power')]
    provider_policy = one(policy, 'var:eon_foreign_cash_policy_provider')
    assert one(provider_policy, 'OR') == [('has_idea', '=', key) for key in ('large_power', 'great_power', 'superpower')]
    assert ('has_country_flag', '=', 'aid_request_cd_@PREV') in provider_policy
    assert one(provider_policy, 'has_opinion') == [('target', '=', 'PREV'), ('value', '>', '49')]
    passed('original_rank_defensive_war_request_marker_and_opinion_requirements_rechecked_with_pair_no_enemy_guard')
    capacity = triggers['eon_foreign_cash_cash_available']
    assert ('check_variable', '=', [('treasury', '>=', '-1000000')]) in capacity
    assert ('add_to_temp_variable', '=', [('eon_foreign_cash_projected_treasury', '=', '7')]) in capacity
    assert ('check_variable', '=', [('eon_foreign_cash_projected_treasury', '<=', '1000000')]) in capacity
    assert one(capacity, 'var:eon_foreign_cash_policy_provider') == [('check_variable', '=', [('treasury', '>=', '7')]), ('check_variable', '=', [('treasury', '<=', '1000000')])]
    passed('full_gift_cash_capacity_guards_avoid_both_negative_donor_and_unrelated_native_clamp_losses')
    native = one(ast((ROOT / NA).read_bytes()), 'scripted_diplomatic_actions')
    assert {key for key, op, value in native} == NEW_ACTION_IDS
    native_body = one(native, 'eon_foreign_cash_withdraw_offer')
    assert one(native_body, 'cost') == '0' and one(native_body, 'requires_acceptance') == 'no'
    assert one(native_body, 'allowed') == [('ROOT', '=', [('is_ai', '=', 'no')])]
    assert one(native_body, 'ai_desire') == [('factor', '=', '0')]
    for field in ('visible', 'selectable', 'can_be_sent'):
        assert one(native_body, field) == [('eon_foreign_cash_withdraw_available', '=', 'yes')]
        passed('three_fresh_native_free_withdraw_guards')
    passed('exact_one_free_human_withdraw_action')
    native_paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, '--', 'common/scripted_diplomatic_actions'], cwd=ROOT).decode().splitlines()
    old_ids = [key for path in native_paths if path.endswith('.txt') for key, op, body in one(ast(baseline_bytes(path)), 'scripted_diplomatic_actions')]
    current_ids = [key for path in (ROOT / 'common/scripted_diplomatic_actions').glob('*.txt') for key, op, body in one(ast(path.read_bytes()), 'scripted_diplomatic_actions')]
    assert len(old_ids) == len(set(old_ids)) == 69 and len(current_ids) == len(set(current_ids)) == 70
    assert set(current_ids) == set(old_ids) | NEW_ACTION_IDS
    passed('69_original_native_actions_plus_one_unique_cash_withdrawal')
    events = {one(body, 'id'): body for key, op, body in ast((ROOT / EVENTS).read_bytes()) if key == 'country_event'}
    assert events.keys() == {'eon_foreign_cash.' + str(i) for i in range(1, 8)}
    assert one(events['eon_foreign_cash.2'], 'hidden') == 'yes'
    assert one(events['eon_foreign_cash.2'], 'immediate') == [('eon_foreign_cash_commit_offer', '=', 'yes')]
    passed('seven_new_event_IDs_and_hidden_provider_commit_frame')
    for identity, body in events.items():
        pattern = rb'(?m)^\s*id\s*=\s*' + re.escape(identity.encode()) + rb'(?![A-Za-z0-9_.])'
        assert sum(len(re.findall(pattern, path.read_bytes())) for path in (ROOT / 'events').glob('*.txt')) == 1, identity
        passed('seven_new_event_definitions_globally_unique')
        if identity not in ('eon_foreign_cash.1', 'eon_foreign_cash.2'):
            assert one(body, 'option') == [('name', '=', 'eon_foreign_cash.ack')]
            passed('five_notifications_have_static_ACK_only')
    response_choices = [body for key, op, body in events['eon_foreign_cash.1'] if key == 'option']
    assert [one(body, 'name') for body in response_choices] == ['eon_foreign_cash.1.a', 'eon_foreign_cash.1.b', 'eon_foreign_cash.ack']
    assert one(response_choices[0], 'trigger') == [('eon_foreign_cash_response_ready', '=', 'yes')]
    assert one(response_choices[1], 'trigger') == [('eon_foreign_cash_response_open', '=', 'yes')]
    assert one(response_choices[2], 'trigger') == [('NOT', '=', [('eon_foreign_cash_response_open', '=', 'yes')])]
    passed('recipient_accept_decline_and_already_closed_ACK_admission_uses_owned_frame')
    for helper in ('reject_offer', 'withdraw_offer'):
        body = one(effects['eon_foreign_cash_' + helper], 'if')
        expected = 'response_open' if helper == 'reject_offer' else 'withdraw_available'
        assert one(body, 'limit') == [('eon_foreign_cash_' + expected, '=', 'yes')]
        passed('reject_and_withdraw_require_matching_open_or_unconsented_record')
    assert ('FROM', '=', [('NOT', '=', [('has_country_flag', '=', 'eon_foreign_cash_consented')])]) in triggers['eon_foreign_cash_response_open']
    assert ('NOT', '=', [('has_country_flag', '=', 'eon_foreign_cash_consented')]) in one(triggers['eon_foreign_cash_withdraw_available'], 'ROOT')
    passed('consent_blocks_both_decline_and_withdraw_until_conditional_execution')
    clear = effects['eon_foreign_cash_clear_pending']
    assert clear == [('clr_country_flag', '=', 'eon_foreign_cash_' + suffix) for suffix in ('pending', 'live', 'cancelled', 'consented')] + [('clear_variable', '=', 'eon_foreign_cash_partner')]
    passed('cleanup_owns_exactly_four_cash_flags_and_one_partner_variable')
    hooks = one(ast((ROOT / HOOKS).read_bytes()), 'on_actions')
    assert one(one(hooks, 'on_daily'), 'effect') == [('eon_foreign_cash_daily_update', '=', 'yes')]
    for hook in ('on_annex', 'on_subject_annexed'):
        assert any(key == 'eon_foreign_cash_annex_update' for key, op, val in rows(one(hooks, hook)))
        passed('both_installed_annex_hooks_route_explicit_annexed_country_to_cash_cleanup')
    for path in (FX, TR):
        nodes = list(rows(ast((ROOT / path).read_bytes())))
        assert not any(key in ('add_political_power', 'add_manpower', 'add_command_power', 'add_fuel', 'add_ideas', 'add_timed_idea',
                              'add_equipment_to_stockpile', 'send_equipment', 'create_unit', 'delete_unit_template_and_units',
                              'declare_war_on', 'white_peace', 'add_to_faction', 'create_faction', 'set_rule') for key, op, val in nodes)
        passed('cash_helpers_do_not_change_PP_personnel_equipment_units_wars_factions_or_paid_service_ideas')
        assert not any(key == 'NOT' and len(val) != 1 for key, op, val in nodes)
        passed('native_NOT_blocks_have_single_child_unambiguous_NOR_semantics')
        for key, op, val in nodes:
            if key in ('clr_country_flag', 'clear_variable'): assert val.startswith('eon_foreign_cash_'), (path, key, val)
        passed('owned_clear_operations_cannot_remove_inherited_request_cooldown_or_other_diplomatic_fields')
    untouched = ('common/scripted_diplomatic_actions/MDDC_AB_ask_foreign_support.txt',
                 'events/00_Influence_events.txt', 'common/scripted_effects/00_influence_scripted_effects.txt',
                 'common/scripted_effects/00_budget_effects.txt', 'common/scripted_guis/influence_scripted_gui.txt')
    for path in untouched:
        assert (ROOT / path).read_bytes() == baseline_bytes(path)
        passed('five_original_AB_entry_mercenary_service_GUI_influence_macro_and_budget_source_files_raw_unchanged')
    entry = one(one(ast(baseline_bytes(untouched[0])), 'scripted_diplomatic_actions'), 'AB_ask_foreign_support')
    assert one(entry, 'cost') == '50' and one(entry, 'requires_acceptance') == 'no'
    assert ('set_country_flag', '=', [('flag', '=', 'aid_request_cd_@ROOT'), ('days', '=', '360'), ('value', '=', '1')]) in list(rows(entry))
    passed('unchanged_AB_entry_nominal_50_PP_360_day_marker_declarations_only_not_unique_ownership_or_native_charge_proof')
    influence = one(ast(baseline_bytes('common/scripted_effects/00_influence_scripted_effects.txt')), 'change_influence_percentage')
    assert any(key == 'ROOT' and any(child == 'has_resources_rights' for child, op, val in rows(body)) for key, op, body in rows(influence) if isinstance(body, list))
    passed('original_influence_macro_native_ROOT_dependency_requires_provider_commit_frame')
    locales = {language: locale_lines((ROOT / f'localisation/{language}/eon_foreign_cash_l_{language}.yml').read_bytes()) for language in ('english', 'russian')}
    assert locales['english'].keys() == locales['russian'].keys()
    passed('bilingual_localisation_key_sets_exactly_match')
    for path in (TR, NA, EVENTS, 'events/00_War_events.txt'):
        for key, op, val in rows(ast((ROOT / path).read_bytes())):
            if key in ('tooltip', 'custom_effect_tooltip', 'title', 'desc', 'name', 'send_description') and isinstance(val, str) and val.startswith('eon_foreign_cash'):
                assert val in locales['english'], ('Unresolved localisation', path, val)
        passed('four_current_tooltip_action_choice_event_localisation_reference_sets_resolve')
    try: package18_original_bytes('events/00_War_events.txt', raw + b'\n# memory-only outside-range probe\n')
    except AssertionError: pass
    else: raise AssertionError('Unowned outside game bytes accepted')
    passed('memory_only_game_source_outside_named_cash_option_mutation_rejected'); boundary_groups.add('memory_only_game_source_outside_named_cash_option_mutation_rejected')
    assert set(HISTORICAL_SOURCE_EDITS) == {f'tools/validation/diplomacy_package_{i:02}/test_source.py' for i in range(2, 18)}
    for path in sorted(HISTORICAL_SOURCE_EDITS):
        actual = (ROOT / path).read_bytes()
        assert package18_original_validator_bytes(path, actual) == baseline_bytes(path)
        original_counters = [line for line in baseline_bytes(path).splitlines() if b'groups[' in line and b'+=' in line or b'passed(' in line]
        current_counters = [line for line in actual.splitlines() if b'groups[' in line and b'+=' in line or b'passed(' in line]
        assert original_counters == current_counters, ('Historical counter lines changed', path)
        passed('sixteen_literal_whole_source_validator_journals_and_all_original_counter_lines')
        try: package18_original_validator_bytes(path, actual + b'\n# memory-only undeclared validator probe\n')
        except AssertionError: pass
        else: raise AssertionError(('Undeclared historical source bytes accepted', path))
        passed('memory_only_whole_historical_source_mutation_rejected'); boundary_groups.add('memory_only_whole_historical_source_mutation_rejected')
    public_paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, '--', 'tools/validation'], cwd=ROOT).decode().splitlines()
    unchanged = [path for path in public_paths if path not in HISTORICAL_SOURCE_EDITS]
    for path in unchanged: assert (ROOT / path).read_bytes() == baseline_bytes(path), ('Prior public behavior/helper/runner or unrelated source changed', path)
    passed('all_other_prior_public_validation_files_whole_raw_bytes_unchanged')
    behavior = [path for path in unchanged if path.endswith('.py') and Path(path).name != 'test_source.py']
    assert len(behavior) == 45 and len(unchanged) == 62
    passed('enumerated_45_prior_behavior_helpers_runners_and_62_other_public_files_raw_byte_exact')
    installed = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV')
    effect_docs = (installed / 'documentation/effects_documentation.md').read_text(encoding='utf-8-sig')
    trigger_docs = (installed / 'documentation/triggers_documentation.md').read_text(encoding='utf-8-sig')
    for helper in ('set_temp_variable', 'check_variable', 'set_variable', 'clear_variable', 'set_country_flag', 'clr_country_flag', 'every_country', 'country_event'):
        assert '\n## ' + helper + '\n' in effect_docs or '\n## ' + helper + '\n' in trigger_docs
        passed('eight_installed_primary_effect_and_trigger_API_declarations')
    for helper in ('exists', 'has_war_with', 'has_idea', 'has_opinion', 'has_defensive_war'):
        assert '\n## ' + helper + '\n' in trigger_docs
        passed('five_installed_primary_policy_trigger_API_declarations')
    defensive_doc = trigger_docs.split('\n## has_defensive_war\n', 1)[1].split('\n## ', 1)[0]
    assert 'Supported Scopes: COUNTRY' in defensive_doc and 'is country at defensive war' in defensive_doc
    passed('defensive_war_is_a_country_classification_separate_from_generic_war_fixture')
    hookdocs = (installed / 'common/on_actions/_documentation.md').read_text(encoding='utf-8-sig')
    for identity in ('on_daily', 'on_annex', 'on_subject_annexed'):
        assert identity in hookdocs
        passed('three_installed_native_hook_declarations')
    hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCE_PATHS}
    boundaries = sum(groups[group] for group in boundary_groups)
    print(json.dumps({'all_passed': True, 'baseline': BASELINE, 'source_API_cases': sum(groups.values()) - boundaries,
        'source_byte_adapter_boundary_cases': boundaries, 'source_cases': sum(groups.values()), 'groups': dict(groups),
        'source_sha256': hashes, 'historical_source_adapters': len(HISTORICAL_SOURCE_EDITS),
        'prior_behavior_helper_runner_raw_byte_files': len(behavior), 'prior_other_public_raw_byte_files': len(unchanged),
        'bilingual_locale_keys': len(locales['english']), 'native_runtime': False,
        'proof_scope': 'exact current-source cash footprint/API and literal historical byte retention; not HOI4 runtime'}, indent=2))

if __name__ == '__main__': main()
