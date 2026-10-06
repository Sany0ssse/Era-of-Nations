"""Exact military-service package footprint/API and old-source byte views.

Only source-preservation assertions use the baseline byte view; behavior tests
execute current game files. This is not native HOI4 compilation or runtime proof.
"""
from pathlib import Path
from functools import lru_cache
from collections import Counter
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASELINE = 'b1568ffc7ae3d0809be0912be68bb76ab4fb0e28'
EXISTING = {'events/00_Influence_events.txt'}
FX = 'common/scripted_effects/eon_services_effects.txt'
TR = 'common/scripted_triggers/eon_services_triggers.txt'
NA = 'common/scripted_diplomatic_actions/eon_services_actions.txt'
HOOKS = 'common/on_actions/eon_services_on_actions.txt'
EVENTS = 'events/eon_services_events.txt'
NEW = {FX, TR, NA, HOOKS, EVENTS} | {f'localisation/{language}/eon_services_l_{language}.yml' for language in ('english', 'russian')}
SOURCE_PATHS = sorted(EXISTING | NEW)
NEW_ACTION_IDS = {'eon_services_withdraw_offer', 'eon_services_end_logistics', 'eon_services_end_recon'}
OWNED_EVENTS = {'influence.501', 'influence.506'}
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

@lru_cache(maxsize=32)
def baseline_bytes(path): return subprocess.check_output(['git', 'show', BASELINE + ':' + path], cwd=ROOT)

def format_preserved(before, after, path):
    assert after.startswith(b'\xef\xbb\xbf') == before.startswith(b'\xef\xbb\xbf'), ('BOM changed', path)
    assert (b'\r\n' in after) == (b'\r\n' in before), ('Line endings changed', path)
    assert b'\r' not in after.replace(b'\r\n', b''), ('Mixed carriage returns', path)
    assert after.endswith(b'\n') == before.endswith(b'\n'), ('Final newline changed', path)

def locale_lines(data):
    result = {}
    for line in data.decode('utf-8-sig').splitlines(keepends=True):
        match = re.match(r'^ ([A-Za-z0-9_.]+):(?:\d+)?\s+', line)
        if match:
            assert match[1] not in result, ('Duplicate locale key', match[1])
            result[match[1]] = line
    return result

def event_blocks(data):
    result = {}
    for block in blocks(data, 0):
        if block['key'] != 'country_event': continue
        identity = one(ast(data[block['start']:block['end']])[0][2], 'id')
        assert identity not in result, ('Duplicate event ID', identity)
        result[identity] = block
    return result


def package17_original_bytes(path, actual):
    """Restore exactly two declared existing country-event bodies; no other bytes."""
    if path not in EXISTING: return actual
    original = baseline_bytes(path); format_preserved(original, actual, path)
    before, after = event_blocks(original), event_blocks(actual)
    assert before.keys() == after.keys(), ('Existing event IDs changed', path)
    restored = actual
    for identity in sorted(OWNED_EVENTS, key=lambda key: after[key]['start'], reverse=True):
        old, new = before[identity], after[identity]
        restored = restored[:new['start']] + original[old['start']:old['end']] + restored[new['end']:]
    assert restored == original, ('Unowned military-service source bytes changed', path)
    return original


@lru_cache(maxsize=32)
def package17_historical_existing(baseline):
    return frozenset(subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', baseline, '--', *sorted(EXISTING)], cwd=ROOT).decode().splitlines())


def check_owned_existing():
    for path in sorted(EXISTING): package17_original_bytes(path, (ROOT / path).read_bytes())


def historical_actions(actions):
    """Only older source preservation proofs omit the three separately checked IDs."""
    return [identity for identity in actions if identity not in NEW_ACTION_IDS]


# Literal whole-file patches are inserted after all owned adapter edits are frozen.
HISTORICAL_SOURCE_EDITS = {'tools/validation/diplomacy_package_02/test_source.py': [(177,
                                                           178,
                                                           '                                               '
                                                           "'eon_withdraw_antiterror_proposal', "
                                                           "'eon_ammo_withdraw_offer')))\n",
                                                           '                                               '
                                                           "'eon_withdraw_antiterror_proposal', "
                                                           "'eon_ammo_withdraw_offer', "
                                                           "'eon_services_withdraw_offer', "
                                                           "'eon_services_end_logistics', "
                                                           "'eon_services_end_recon')))\n")],
 'tools/validation/diplomacy_package_03/test_source.py': [(60,
                                                           60,
                                                           '',
                                                           'from diplomacy_package_17.test_source '
                                                           'import (\n'
                                                           '    NEW as LATER_PACKAGE17_NEW, '
                                                           'package17_original_bytes, '
                                                           'package17_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package17_historical_actions, '
                                                           'check_owned_existing as '
                                                           'check_later_package17_owned,\n'
                                                           ')\n'
                                                           'check_later_package17_owned()\n'),
                                                          (242,
                                                           243,
                                                           'tracked_changes = [path for path in '
                                                           'tracked_changes if path not in '
                                                           'LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n',
                                                           'tracked_changes = [path for path in '
                                                           'tracked_changes if path not in '
                                                           'LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'LATER_PACKAGE17_NEW]\n'),
                                                          (246,
                                                           247,
                                                           'untracked = [path for path in untracked if '
                                                           'path not in LATER_PACKAGE16_NEW]\n',
                                                           'untracked = [path for path in untracked if '
                                                           'path not in LATER_PACKAGE16_NEW | '
                                                           'LATER_PACKAGE17_NEW]\n')],
 'tools/validation/diplomacy_package_04/test_source.py': [(76,
                                                           76,
                                                           '',
                                                           'from diplomacy_package_17.test_source '
                                                           'import (\n'
                                                           '    NEW as LATER_PACKAGE17_NEW, '
                                                           'package17_original_bytes, '
                                                           'package17_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package17_historical_actions, '
                                                           'check_owned_existing as '
                                                           'check_later_package17_owned,\n'
                                                           ')\n'
                                                           'check_later_package17_owned()\n'),
                                                          (339,
                                                           340,
                                                           'tracked = [path for path in tracked if path '
                                                           'not in LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n',
                                                           'tracked = [path for path in tracked if path '
                                                           'not in LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'LATER_PACKAGE17_NEW]\n'),
                                                          (341,
                                                           342,
                                                           'untracked = [path for path in untracked if '
                                                           'path not in LATER_PACKAGE16_NEW]\n',
                                                           'untracked = [path for path in untracked if '
                                                           'path not in LATER_PACKAGE16_NEW | '
                                                           'LATER_PACKAGE17_NEW]\n')],
 'tools/validation/diplomacy_package_05/test_source.py': [(71,
                                                           71,
                                                           '',
                                                           'from diplomacy_package_17.test_source '
                                                           'import (\n'
                                                           '    NEW as LATER_PACKAGE17_NEW, '
                                                           'package17_original_bytes, '
                                                           'package17_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package17_historical_actions, '
                                                           'check_owned_existing as '
                                                           'check_later_package17_owned,\n'
                                                           ')\n'
                                                           'check_later_package17_owned()\n'),
                                                          (280,
                                                           281,
                                                           'changed = [path for path in changed if path '
                                                           'not in LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n',
                                                           'changed = [path for path in changed if path '
                                                           'not in LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'LATER_PACKAGE17_NEW]\n'),
                                                          (282,
                                                           283,
                                                           'untracked = [path for path in untracked if '
                                                           'path not in LATER_PACKAGE16_NEW]\n',
                                                           'untracked = [path for path in untracked if '
                                                           'path not in LATER_PACKAGE16_NEW | '
                                                           'LATER_PACKAGE17_NEW]\n')],
 'tools/validation/diplomacy_package_06/test_source.py': [(73,
                                                           73,
                                                           '',
                                                           'from diplomacy_package_17.test_source '
                                                           'import (\n'
                                                           '    NEW as LATER_PACKAGE17_NEW, '
                                                           'package17_original_bytes, '
                                                           'package17_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package17_historical_actions, '
                                                           'check_owned_existing as '
                                                           'check_later_package17_owned,\n'
                                                           ')\n'
                                                           'check_later_package17_owned()\n'),
                                                          (131,
                                                           132,
                                                           'def read(path): return '
                                                           'package14_original_bytes(path, (ROOT / '
                                                           'path).read_bytes())\n',
                                                           'def read(path): return '
                                                           'package14_original_bytes(path, '
                                                           'package17_original_bytes(path, (ROOT / '
                                                           'path).read_bytes()))\n'),
                                                          (454,
                                                           455,
                                                           'changed = [path for path in changed if path '
                                                           'not in LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n',
                                                           'changed = [path for path in changed if path '
                                                           'not in LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'LATER_PACKAGE17_NEW]\n'),
                                                          (456,
                                                           457,
                                                           'untracked = [path for path in untracked if '
                                                           'path not in LATER_PACKAGE16_NEW]\n',
                                                           'untracked = [path for path in untracked if '
                                                           'path not in LATER_PACKAGE16_NEW | '
                                                           'LATER_PACKAGE17_NEW]\n')],
 'tools/validation/diplomacy_package_07/test_source.py': [(71,
                                                           71,
                                                           '',
                                                           'from diplomacy_package_17.test_source '
                                                           'import (\n'
                                                           '    NEW as LATER_PACKAGE17_NEW, '
                                                           'package17_original_bytes, '
                                                           'package17_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package17_historical_actions, '
                                                           'check_owned_existing as '
                                                           'check_later_package17_owned,\n'
                                                           ')\n'
                                                           'check_later_package17_owned()\n'),
                                                          (133,
                                                           134,
                                                           'changed = [path for path in changed if path '
                                                           'not in LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n',
                                                           'changed = [path for path in changed if path '
                                                           'not in LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW]\n'),
                                                          (135,
                                                           136,
                                                           'untracked = [path for path in untracked if '
                                                           'path not in LATER_PACKAGE16_NEW]\n',
                                                           'untracked = [path for path in untracked if '
                                                           'path not in LATER_PACKAGE16_NEW | '
                                                           'LATER_PACKAGE17_NEW]\n')],
 'tools/validation/diplomacy_package_08/test_source.py': [(71,
                                                           71,
                                                           '',
                                                           'from diplomacy_package_17.test_source '
                                                           'import (\n'
                                                           '    NEW as LATER_PACKAGE17_NEW, '
                                                           'package17_original_bytes, '
                                                           'package17_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package17_historical_actions, '
                                                           'check_owned_existing as '
                                                           'check_later_package17_owned,\n'
                                                           ')\n'
                                                           'check_later_package17_owned()\n'),
                                                          (130,
                                                           131,
                                                           'changed = [path for path in changed if path '
                                                           'not in LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n',
                                                           'changed = [path for path in changed if path '
                                                           'not in LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW]\n'),
                                                          (132,
                                                           133,
                                                           'untracked = [path for path in untracked if '
                                                           'path not in LATER_PACKAGE16_NEW]\n',
                                                           'untracked = [path for path in untracked if '
                                                           'path not in LATER_PACKAGE16_NEW | '
                                                           'LATER_PACKAGE17_NEW]\n')],
 'tools/validation/diplomacy_package_09/test_source.py': [(59,
                                                           59,
                                                           '',
                                                           'from diplomacy_package_17.test_source '
                                                           'import (\n'
                                                           '    NEW as LATER_PACKAGE17_NEW, '
                                                           'package17_original_bytes, '
                                                           'package17_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package17_historical_actions, '
                                                           'check_owned_existing as '
                                                           'check_later_package17_owned,\n'
                                                           ')\n'
                                                           'check_later_package17_owned()\n'),
                                                          (113,
                                                           114,
                                                           'changed = [path for path in changed if path '
                                                           'not in LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n',
                                                           'changed = [path for path in changed if path '
                                                           'not in LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW]\n'),
                                                          (115,
                                                           116,
                                                           'untracked = [path for path in untracked if '
                                                           'path not in LATER_PACKAGE16_NEW]\n',
                                                           'untracked = [path for path in untracked if '
                                                           'path not in LATER_PACKAGE16_NEW | '
                                                           'LATER_PACKAGE17_NEW]\n')],
 'tools/validation/diplomacy_package_10/test_source.py': [(51,
                                                           51,
                                                           '',
                                                           'from diplomacy_package_17.test_source '
                                                           'import (\n'
                                                           '    NEW as LATER_PACKAGE17_NEW, '
                                                           'package17_original_bytes, '
                                                           'package17_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package17_historical_actions, '
                                                           'check_owned_existing as '
                                                           'check_later_package17_owned,\n'
                                                           ')\n'
                                                           'check_later_package17_owned()\n'),
                                                          (193,
                                                           194,
                                                           '    changed = [path for path in changed if '
                                                           'path not in LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n',
                                                           '    changed = [path for path in changed if '
                                                           'path not in LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW]\n'),
                                                          (195,
                                                           196,
                                                           '    untracked = [path for path in untracked '
                                                           'if path not in LATER_PACKAGE16_NEW]\n',
                                                           '    untracked = [path for path in untracked '
                                                           'if path not in LATER_PACKAGE16_NEW | '
                                                           'LATER_PACKAGE17_NEW]\n')],
 'tools/validation/diplomacy_package_11/test_source.py': [(44,
                                                           44,
                                                           '',
                                                           'from diplomacy_package_17.test_source '
                                                           'import (\n'
                                                           '    NEW as LATER_PACKAGE17_NEW, '
                                                           'package17_original_bytes, '
                                                           'package17_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package17_historical_actions, '
                                                           'check_owned_existing as '
                                                           'check_later_package17_owned,\n'
                                                           ')\n'
                                                           'check_later_package17_owned()\n'),
                                                          (207,
                                                           209,
                                                           '    untracked = [path for path in untracked '
                                                           'if path not in LATER_PACKAGE16_NEW]\n'
                                                           '    changed = [path for path in changed if '
                                                           'path not in LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n',
                                                           '    untracked = [path for path in untracked '
                                                           'if path not in LATER_PACKAGE16_NEW | '
                                                           'LATER_PACKAGE17_NEW]\n'
                                                           '    changed = [path for path in changed if '
                                                           'path not in LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW]\n')],
 'tools/validation/diplomacy_package_12/test_source.py': [(30,
                                                           30,
                                                           '',
                                                           'from diplomacy_package_17.test_source '
                                                           'import (\r\n'
                                                           '    NEW as LATER_PACKAGE17_NEW, '
                                                           'package17_original_bytes, '
                                                           'package17_historical_existing,\r\n'
                                                           '    historical_actions as '
                                                           'package17_historical_actions, '
                                                           'check_owned_existing as '
                                                           'check_later_package17_owned,\r\n'
                                                           ')\r\n'
                                                           'check_later_package17_owned()\r\n'),
                                                          (177,
                                                           178,
                                                           '    changed=[path for path in changed if '
                                                           'path not in '
                                                           '(package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE))-EXISTING '
                                                           '| package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\r\n',
                                                           '    changed=[path for path in changed if '
                                                           'path not in '
                                                           '(package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE))-EXISTING '
                                                           '| package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW]\r\n'),
                                                          (179,
                                                           180,
                                                           '    untracked = [path for path in untracked '
                                                           'if path not in LATER_PACKAGE16_NEW]\r\n',
                                                           '    untracked = [path for path in untracked '
                                                           'if path not in LATER_PACKAGE16_NEW | '
                                                           'LATER_PACKAGE17_NEW]\r\n')],
 'tools/validation/diplomacy_package_13/test_source.py': [(30,
                                                           30,
                                                           '',
                                                           'from diplomacy_package_17.test_source '
                                                           'import (\n'
                                                           '    NEW as LATER_PACKAGE17_NEW, '
                                                           'package17_original_bytes, '
                                                           'package17_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package17_historical_actions, '
                                                           'check_owned_existing as '
                                                           'check_later_package17_owned,\n'
                                                           ')\n'
                                                           'check_later_package17_owned()\n'),
                                                          (190,
                                                           191,
                                                           '    changed=[path for path in changed if '
                                                           'path not in '
                                                           '(package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE))-EXISTING '
                                                           '| package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n',
                                                           '    changed=[path for path in changed if '
                                                           'path not in '
                                                           '(package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE))-EXISTING '
                                                           '| package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW]\n'),
                                                          (192,
                                                           193,
                                                           '    untracked = [path for path in untracked '
                                                           'if path not in LATER_PACKAGE16_NEW]\n',
                                                           '    untracked = [path for path in untracked '
                                                           'if path not in LATER_PACKAGE16_NEW | '
                                                           'LATER_PACKAGE17_NEW]\n')],
 'tools/validation/diplomacy_package_14/test_source.py': [(26,
                                                           26,
                                                           '',
                                                           'from diplomacy_package_17.test_source '
                                                           'import (\n'
                                                           '    NEW as LATER_PACKAGE17_NEW, '
                                                           'package17_original_bytes, '
                                                           'package17_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package17_historical_actions, '
                                                           'check_owned_existing as '
                                                           'check_later_package17_owned,\n'
                                                           ')\n'
                                                           'check_later_package17_owned()\n'),
                                                          (206,
                                                           207,
                                                           '    changed=[path for path in changed if '
                                                           'path not in '
                                                           'package15_historical_existing(BASELINE)-EXISTING '
                                                           '| package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n',
                                                           '    changed=[path for path in changed if '
                                                           'path not in '
                                                           'package15_historical_existing(BASELINE)-EXISTING '
                                                           '| package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW]\n'),
                                                          (208,
                                                           209,
                                                           '    untracked = [path for path in untracked '
                                                           'if path not in LATER_PACKAGE16_NEW]\n',
                                                           '    untracked = [path for path in untracked '
                                                           'if path not in LATER_PACKAGE16_NEW | '
                                                           'LATER_PACKAGE17_NEW]\n')],
 'tools/validation/diplomacy_package_15/test_source.py': [(18,
                                                           18,
                                                           '',
                                                           'from diplomacy_package_17.test_source '
                                                           'import (\n'
                                                           '    NEW as LATER_PACKAGE17_NEW, '
                                                           'package17_original_bytes, '
                                                           'package17_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package17_historical_actions, '
                                                           'check_owned_existing as '
                                                           'check_later_package17_owned,\n'
                                                           ')\n'
                                                           'check_later_package17_owned()\n'),
                                                          (810,
                                                           812,
                                                           '    changed -= '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW\n'
                                                           '    added -= LATER_PACKAGE16_NEW\n',
                                                           '    changed -= '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW\n'
                                                           '    added -= LATER_PACKAGE16_NEW | '
                                                           'LATER_PACKAGE17_NEW\n')],
 'tools/validation/diplomacy_package_16/test_source.py': [(15,
                                                           15,
                                                           '',
                                                           'import sys as package17_sys\n'
                                                           'package17_sys.path.insert(0, str(ROOT / '
                                                           "'tools/validation'))\n"
                                                           'from diplomacy_package_17.test_source '
                                                           'import (\n'
                                                           '    NEW as LATER_PACKAGE17_NEW, '
                                                           'package17_original_bytes, '
                                                           'package17_historical_existing,\n'
                                                           '    package17_original_validator_bytes, '
                                                           'historical_actions as '
                                                           'package17_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package17_owned,\n'
                                                           ')\n'
                                                           'check_later_package17_owned()\n'),
                                                          (122,
                                                           122,
                                                           '',
                                                           '    actions = '
                                                           'package17_historical_actions(actions)\n'),
                                                          (608,
                                                           608,
                                                           '',
                                                           '    actual = '
                                                           'package17_original_validator_bytes(path, '
                                                           'actual)\n'),
                                                          (636,
                                                           636,
                                                           '',
                                                           '    changed -= '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW\n'
                                                           '    untracked -= LATER_PACKAGE17_NEW\n'),
                                                          (782,
                                                           782,
                                                           '',
                                                           '    native_ids = '
                                                           'package17_historical_actions(native_ids)\n')]}


def package17_original_validator_bytes(path, actual):
    if path not in HISTORICAL_SOURCE_EDITS: return actual
    original = baseline_bytes(path)
    lines = original.decode('utf-8').splitlines(keepends=True)
    for start, end, before, after in reversed(HISTORICAL_SOURCE_EDITS[path]):
        assert ''.join(lines[start:end]) == before, ('Historical source patch baseline drift', path, start)
        lines[start:end] = [after]
    assert actual == ''.join(lines).encode('utf-8'), ('Undeclared historical source validator edit', path)
    return original

def main():
    groups = Counter(); boundary_groups = set()
    def passed(group): groups[group] += 1
    for path in SOURCE_PATHS:
        assert (ROOT / path).is_file(), ('RED: military-service package source missing', path)
    check_owned_existing()
    for path in sorted(EXISTING):
        assert package17_original_bytes(path, (ROOT / path).read_bytes()) == baseline_bytes(path)
        passed('one_exact_existing_source_range_and_BOM_EOL_boundary')
    for path in sorted(NEW):
        data = (ROOT / path).read_bytes(); data.decode('utf-8-sig')
        assert data.endswith(b'\n') and b'\r' not in data.replace(b'\r\n', b'')
        if path.endswith('.yml'): assert data.startswith(b'\xef\xbb\xbf')
        else: ast(data)
        passed('seven_new_UTF8_script_or_BOM_localisation_files')
    trees = ('common', 'history', 'events', 'interface', 'gfx', 'localisation', 'music', 'map', 'sound',
             'portraits', 'tutorial', 'descriptions', 'scenario_tests', 'descriptor.mod', 'era_of_nations.mod', 'thumbnail.png')
    changed = set(subprocess.check_output(['git', 'diff', '--name-only', BASELINE, '--', *trees], cwd=ROOT).decode().splitlines())
    untracked = set(subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', *trees], cwd=ROOT).decode().splitlines())
    assert changed - NEW == EXISTING and (changed | untracked) - EXISTING == NEW, (changed, untracked)
    assert not subprocess.check_output(['git', 'diff', '--name-only', '--diff-filter=D', BASELINE, '--', *trees], cwd=ROOT).strip()
    passed('exact_full_gameplay_tree_one_existing_seven_new_without_unowned_deletions')
    raw = (ROOT / next(iter(EXISTING))).read_bytes(); old_raw = baseline_bytes(next(iter(EXISTING)))
    existing = {one(body, 'id'): body for key, op, body in ast(raw) if key == 'country_event'}
    original = {one(body, 'id'): body for key, op, body in ast(old_raw) if key == 'country_event'}
    assert existing.keys() == original.keys()
    passed('all_original_country_event_IDs_preserved')
    def option(nodes, identity):
        found = [body for key, op, body in nodes if key == 'option' and one(body, 'name') == identity]
        assert len(found) == 1, identity
        return found[0]
    for identity in ('influence.501', 'influence.506'):
        old, current = original[identity], existing[identity]
        for field in ('id', 'title', 'picture', 'is_triggered_only'):
            assert one(old, field) == one(current, field), (identity, field)
            passed('eight_existing_event_header_fields_unchanged')
        assert [one(body, 'name') for key, op, body in old if key == 'option'] == [one(body, 'name') for key, op, body in current if key == 'option']
        passed('two_original_event_option_ID_sets_and_order_preserved')
    assert one(existing['influence.501'], 'desc') == one(original['influence.501'], 'desc')
    assert one(existing['influence.506'], 'desc') == 'eon_services_legacy_desc'
    passed('original_selection_description_and_explicit_unsigned_legacy_description_alias')
    for identity in ('influence.501.c', 'influence.501.e'):
        assert option(existing['influence.501'], identity) == option(original['influence.501'], identity)
        passed('mercenary_and_cancel_choice_full_ordered_AST_unchanged')
    def option_raw(data, event_id, name):
        event = event_blocks(data)[event_id]
        segment = data[event['start']:event['end']]
        choices = [item for item in blocks(segment, 1) if item['key'] == 'option'
                   and one(ast(segment[item['start']:item['end']])[0][2], 'name') == name]
        assert len(choices) == 1, name
        block = choices[0]; return segment[block['start']:block['end']]
    for identity in ('influence.501.c', 'influence.501.e'):
        assert option_raw(raw, 'influence.501', identity) == option_raw(old_raw, 'influence.501', identity)
        passed('mercenary_and_cancel_choice_raw_bytes_unchanged')
    for suffix, kind in (('a', '1'), ('b', '2')):
        current = option(existing['influence.501'], 'influence.501.' + suffix)
        assert ('eon_services_send_offer', '=', 'yes') in list(rows(current))
        assert ('set_temp_variable', '=', [('eon_services_requested_kind', '=', kind)]) in list(rows(current))
        assert ('eon_services_selection_ready', '=', 'yes') in list(rows(one(current, 'trigger')))
        assert not any(key == 'set_country_flag' and value in ('military_services_sent_logistics', 'military_services_sent_recon') for key, op, value in current)
        passed('two_existing_service_choices_route_pair_scoped_admitted_request_kind')
    effects = {key: body for key, op, body in ast((ROOT / FX).read_bytes())}
    triggers = {key: body for key, op, body in ast((ROOT / TR).read_bytes())}
    for helper in ('send_offer', 'accept_offer', 'reject_offer', 'withdraw_offer', 'end_logistics', 'end_recon', 'legacy_close', 'daily_update', 'annex_update'):
        assert 'eon_services_' + helper in effects
        passed('nine_required_current_scripted_effect_API_definitions')
    for helper in ('policy_allowed', 'selection_ready', 'response_pending', 'response_ready', 'withdraw_available', 'end_logistics_available', 'end_recon_available'):
        assert 'eon_services_' + helper in triggers
        passed('seven_required_current_scripted_trigger_API_definitions')
    known = set(effects) | set(triggers)
    for path in (FX, TR, NA, HOOKS, EVENTS):
        for key, op, value in rows(ast((ROOT / path).read_bytes())):
            if key.startswith('eon_services_') and value in ('yes', 'no'):
                assert key in known, ('Unresolved helper', path, key)
        passed('five_new_current_helper_reference_sets_resolve')
    for helper in known:
        folder = 'scripted_effects' if helper in effects else 'scripted_triggers'
        pattern = rb'(?m)^' + re.escape(helper.encode()) + rb'\s*=\s*{'
        assert sum(len(re.findall(pattern, path.read_bytes())) for path in (ROOT / 'common' / folder).glob('*.txt')) == 1, ('Duplicate helper ID', helper)
        passed('every_owned_effect_and_trigger_definition_globally_unique')
    native = one(ast((ROOT / NA).read_bytes()), 'scripted_diplomatic_actions')
    assert {key for key, op, body in native} == NEW_ACTION_IDS
    passed('exact_three_owned_native_action_IDs')
    for identity in sorted(NEW_ACTION_IDS):
        body = one(native, identity)
        assert one(body, 'cost') == '0' and one(body, 'requires_acceptance') == 'no'
        assert one(body, 'allowed') == [('ROOT', '=', [('is_ai', '=', 'no')])]
        assert one(body, 'ai_desire') == [('factor', '=', '0')]
        for field in ('visible', 'selectable', 'can_be_sent'):
            assert one(body, field), (identity, field)
        passed('three_free_human_native_actions_with_fresh_guards')
    native_ids = [key for path in (ROOT / 'common/scripted_diplomatic_actions').glob('*.txt') for key, op, body in one(ast(path.read_bytes()), 'scripted_diplomatic_actions')]
    old_ids = [key for path in subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, '--', 'common/scripted_diplomatic_actions'], cwd=ROOT).decode().splitlines() if path.endswith('.txt') for key, op, body in one(ast(baseline_bytes(path)), 'scripted_diplomatic_actions')]
    assert len(old_ids) == len(set(old_ids)) == 66 and len(native_ids) == len(set(native_ids)) == 69
    assert set(native_ids) == set(old_ids) | NEW_ACTION_IDS
    passed('66_original_native_action_IDs_plus_three_unique_additions')
    responses = {one(body, 'id'): body for key, op, body in ast((ROOT / EVENTS).read_bytes()) if key == 'country_event'}
    assert {'eon_services.1', 'eon_services.6'} <= responses.keys()
    for response_id, suffix in (('eon_services.1', 'a'), ('eon_services.6', 'b'), ('eon_services.1', 'c'), ('eon_services.6', 'c')):
        assert one(option(responses[response_id], 'eon_services.1.' + suffix), 'ai_chance') == one(option(original['influence.506'], 'influence.506.' + suffix), 'ai_chance'), suffix
        passed('original_acceptance_AI_and_duplicated_typed_rejection_AI_AST_blocks_preserved')
        old_choice = option_raw(old_raw, 'influence.506', 'influence.506.' + suffix)
        new_choice = option_raw((ROOT / EVENTS).read_bytes(), response_id, 'eon_services.1.' + suffix)
        def field_raw(data, name):
            found = [item for item in blocks(data, 1) if item['key'] == name]; assert len(found) == 1, name
            field = found[0]; return data[field['start']:field['end']]
        assert field_raw(old_choice, 'ai_chance') == field_raw(new_choice, 'ai_chance')
        passed('original_acceptance_AI_and_duplicated_typed_rejection_AI_full_raw_bytes_preserved')
    for suffix in ('a', 'b', 'c'):
        current = option(existing['influence.506'], 'influence.506.' + suffix)
        assert ('eon_services_legacy_close', '=', 'yes') in list(rows(current))
        assert not any(key in ('modify_treasury_effect', 'add_timed_idea', 'change_influence_percentage', 'change_the_military_opinion', 'change_domestic_influence_percentage') for key, op, value in rows(current))
        passed('three_unsigned_legacy_options_close_only_without_fees_bonus_or_political_mutations')
        if suffix in ('a', 'b'):
            assert one(current, 'trigger') == [('always', '=', 'no')]
            passed('two_obsolete_legacy_acceptance_IDs_retained_but_not_shown_in_native_UI')
    accept = one(effects['eon_services_accept_offer'], 'if')
    settlement = next(body for key, op, body in accept if key == 'if')
    assert settlement[1] == ('FROM', '=', [('eon_services_clear_pending', '=', 'yes')])
    passed('provider_pending_record_consumed_before_authoritative_debit_credit_and_bonus')
    reject = one(effects['eon_services_reject_offer'], 'if')
    assert one(reject, 'limit') == [('eon_services_response_pending', '=', 'yes'), ('eon_services_response_kind_matches', '=', 'yes')]
    assert not any(key == 'set_temp_variable' and val == [('eon_services_requested_kind', '=', 'FROM.eon_services_kind')] for key, op, val in rows(reject))
    passed('typed_rejection_requires_frozen_pair_and_requested_kind_without_adopting_current_record_kind')
    for response_id, suffix, kind in (('eon_services.1', 'a', '1'), ('eon_services.6', 'b', '2')):
        body = responses[response_id]
        for name in ('eon_services.1.' + suffix, 'eon_services.1.c', 'eon_services.ack'):
            choice = option(body, name)
            assert ('set_temp_variable', '=', [('eon_services_requested_kind', '=', kind)]) in list(rows(choice))
            passed('six_typed_response_choices_and_ACK_fallbacks_supply_literal_event_kind')
    for kind, fee in (('1', '3'), ('2', '4')):
        assert ('set_temp_variable', '=', [('eon_services_fee', '=', fee)]) in list(rows(triggers['eon_services_response_ready']))
        passed('two_original_literal_upfront_prices_unchanged')
    assert ('set_temp_variable', '=', [('eon_services_policy_provider', '=', 'PREV.eon_services_selection_provider')]) in list(rows(triggers['eon_services_selection_ready']))
    passed('selection_provider_identity_uses_explicit_previous_country_temporary_scope')
    for path in (FX, TR, EVENTS):
        assert not any(key == 'set_temp_variable' and any(name == 'eon_services_kind' for name, op, val in value) for key, op, value in rows(ast((ROOT / path).read_bytes())))
        passed('permanent_frozen_service_kind_not_shadowed_by_temporary_option_input')
    for identity in ('eon_services_clear_logistics', 'eon_services_clear_recon'):
        clear = effects[identity]; guarded = one(clear, 'if')
        assert len(one(guarded, 'limit')) == 1 and one(guarded, 'limit')[0][0] == 'has_country_flag'
        assert not any(key == 'remove_ideas' for key, op, value in clear)
        assert one(guarded, 'remove_ideas') in ('military_services_logistics_idea', 'military_services_recon_idea')
        passed('two_bonus_removals_require_owned_marker_and_do_not_claim_unsigned_native_ideas')
    locales = {language: locale_lines((ROOT / f'localisation/{language}/eon_services_l_{language}.yml').read_bytes()) for language in ('english', 'russian')}
    assert locales['english'].keys() == locales['russian'].keys()
    passed('new_bilingual_locale_key_sets_match')
    for path in (TR, NA, EVENTS):
        for key, op, value in rows(ast((ROOT / path).read_bytes())):
            if key in ('tooltip', 'title', 'desc', 'name', 'send_description') and isinstance(value, str) and value.startswith('eon_services'):
                assert value in locales['english'], ('Unresolved localisation', path, value)
        passed('three_actual_tooltip_action_and_event_locale_reference_sets_resolve')
    for path in (FX, TR):
        nodes = ast((ROOT / path).read_bytes())
        assert not any(key in ('add_political_power', 'add_manpower', 'add_command_power', 'add_fuel', 'add_to_faction', 'declare_war_on', 'white_peace', 'set_rule', 'create_faction', 'create_unit') for key, op, value in rows(nodes))
        passed('owned_helpers_do_not_invent_manpower_fuel_units_wars_faction_or_PP_cost')
        assert not any(key == 'NOT' and len(value) != 1 for key, op, value in rows(nodes))
        passed('owned_native_NOT_blocks_have_unambiguous_single_child_NOR_semantics')
    hooks = one(ast((ROOT / HOOKS).read_bytes()), 'on_actions')
    assert one(one(hooks, 'on_daily'), 'effect') == [('eon_services_daily_update', '=', 'yes')]
    for hook in ('on_annex', 'on_subject_annexed'):
        assert any(key == 'eon_services_annex_update' for key, op, value in rows(one(hooks, hook)))
        passed('both_installed_native_annex_hooks_route_owned_cleanup')
    for identity, body in responses.items():
        if identity in ('eon_services.1', 'eon_services.6'): continue
        assert one(body, 'option') == [('name', '=', 'eon_services.ack')]
        passed('six_service_status_notifications_have_static_ACK_only_options')
    for path in ('common/scripted_guis/influence_scripted_gui.txt', 'common/scripted_triggers/99_ERI_scripted_triggers.txt',
                 'common/scripted_triggers/00_influence_scripted_triggers.txt'):
        assert (ROOT / path).read_bytes() == baseline_bytes(path)
        passed('original_entry_GUI_national_policy_and_influence_trigger_whole_bytes_unchanged')
    for path in sorted(EXISTING):
        try: package17_original_bytes(path, (ROOT / path).read_bytes() + b'\n# memory-only outside-range probe\n')
        except AssertionError: pass
        else: raise AssertionError(('Outside-range change accepted', path))
        passed('memory_only_existing_source_outside_range_mutation_rejected'); boundary_groups.add('memory_only_existing_source_outside_range_mutation_rejected')
    assert len(HISTORICAL_SOURCE_EDITS) == 15
    for path in sorted(HISTORICAL_SOURCE_EDITS):
        actual = (ROOT / path).read_bytes()
        assert package17_original_validator_bytes(path, actual) == baseline_bytes(path)
        before_lines = [line for line in baseline_bytes(path).splitlines() if b'groups[' in line and b'+=' in line or b'passed(' in line]
        after_lines = [line for line in actual.splitlines() if b'groups[' in line and b'+=' in line or b'passed(' in line]
        assert before_lines == after_lines, ('Historical assertion counters changed', path)
        passed('15_literal_whole_public_source_validator_journals_and_original_counter_lines')
        try: package17_original_validator_bytes(path, actual + b'\n# memory-only unowned validator probe\n')
        except AssertionError: pass
        else: raise AssertionError(('Undeclared older validator edit accepted', path))
        passed('memory_only_historical_source_whole_file_mutation_rejected'); boundary_groups.add('memory_only_historical_source_whole_file_mutation_rejected')
    paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, '--', 'tools/validation'], cwd=ROOT).decode().splitlines()
    unchanged = [path for path in paths if path not in HISTORICAL_SOURCE_EDITS]
    for path in unchanged:
        assert (ROOT / path).read_bytes() == baseline_bytes(path), ('Earlier behavior/helper/runner or unrelated public source changed', path)
    passed('all_other_prior_public_validation_files_whole_raw_bytes_unchanged')
    behavior = [path for path in unchanged if path.endswith('.py') and Path(path).name != 'test_source.py']
    assert len(behavior) == 43
    passed('all43_prior_behavior_executors_assertions_cases_and_runners_retained')
    installed = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV')
    effect_docs = (installed / 'documentation/effects_documentation.md').read_text(encoding='utf-8-sig')
    trigger_docs = (installed / 'documentation/triggers_documentation.md').read_text(encoding='utf-8-sig')
    for helper in ('set_temp_variable', 'check_variable', 'set_variable', 'clear_variable', 'set_country_flag', 'clr_country_flag', 'every_country', 'country_event', 'add_timed_idea', 'remove_ideas'):
        assert '\n## ' + helper + '\n' in effect_docs or '\n## ' + helper + '\n' in trigger_docs, helper
        passed('ten_installed_primary_effect_or_trigger_API_declarations')
    for helper in ('exists', 'has_war', 'has_war_with', 'has_idea', 'has_civil_war', 'num_of_military_factories'):
        assert '\n## ' + helper + '\n' in trigger_docs, helper
        passed('six_installed_primary_policy_trigger_API_declarations')
    assert 'Always true since variables are always valid scopes' in trigger_docs
    assert 'exists that checks if the country of the scope exists' in trigger_docs
    passed('native_variable_scope_validity_is_not_country_identity_resolution')
    hookdocs = (installed / 'common/on_actions/_documentation.md').read_text(encoding='utf-8-sig')
    for identity in ('on_daily', 'on_annex', 'on_subject_annexed'):
        assert identity in hookdocs, identity
        passed('three_installed_primary_on_action_hook_declarations')
    hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCE_PATHS}
    boundaries = sum(groups[group] for group in boundary_groups)
    print(json.dumps({'all_passed': True, 'baseline': BASELINE, 'source_API_cases': sum(groups.values()) - boundaries,
                      'source_byte_adapter_boundary_cases': boundaries, 'source_cases': sum(groups.values()), 'groups': dict(groups),
                      'source_sha256': hashes, 'historical_source_adapters': len(HISTORICAL_SOURCE_EDITS),
                      'prior_behavior_helper_runner_raw_byte_files': len(behavior), 'bilingual_locale_keys': len(locales['english']),
                      'proof_scope': 'bounded current source footprint/API and exact history retention; not native HOI4 runtime'}, indent=2))

if __name__ == '__main__': main()
