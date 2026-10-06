"""Exact ammunition package footprint/API and old-source byte views.

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
BASELINE = '0e70f281145041d9e707089623ef5ecb610b744f'
import sys as package17_sys
package17_sys.path.insert(0, str(ROOT / 'tools/validation'))
from diplomacy_package_17.test_source import (
    NEW as LATER_PACKAGE17_NEW, package17_original_bytes, package17_historical_existing,
    package17_original_validator_bytes, historical_actions as package17_historical_actions,
    check_owned_existing as check_later_package17_owned,
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
from diplomacy_package_23.test_source import (
    NEW as LATER_PACKAGE23_NEW, package23_original_bytes, package23_historical_existing,
    package23_original_validator_bytes, historical_actions as package23_historical_actions,
    check_owned_existing as check_later_package23_owned,
)
check_later_package23_owned()
ACTION = 'common/scripted_diplomatic_actions/MDC_send_ammo.txt'
FX = 'common/scripted_effects/eon_ammo_effects.txt'
TR = 'common/scripted_triggers/eon_ammo_triggers.txt'
NA = 'common/scripted_diplomatic_actions/eon_ammo_actions.txt'
HOOKS = 'common/on_actions/eon_ammo_on_actions.txt'
EVENTS = 'events/eon_ammo_events.txt'
LOCALES = {f'localisation/{language}/MDC_ammo_l_{language}.yml' for language in ('english', 'russian')}
EXISTING = {ACTION} | LOCALES
NEW = {FX, TR, NA, HOOKS, EVENTS} | {f'localisation/{language}/eon_ammo_l_{language}.yml' for language in ('english', 'russian')}
SOURCE_PATHS = sorted(EXISTING | NEW)
LOCALE_KEYS = {'Sda_send_ammo_send_desc', 'Sda_send_ammo_receive_desc', 'Sda_send_ammo_accept_desc',
               'Sda_send_ammo_accept_title', 'Sda_send_ammo_reject_desc', 'Sda_send_ammo_tt_has_enough'}
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

def package16_original_bytes(path, actual):
    """Restore only the declared native Send_ammo range or six locale rows."""
    if path not in EXISTING: return actual
    original = baseline_bytes(path); format_preserved(original, actual, path)
    if path == ACTION:
        old = [item for item in blocks(original, 1) if item['key'] == 'Send_ammo']
        new = [item for item in blocks(actual, 1) if item['key'] == 'Send_ammo']
        assert len(old) == len(new) == 1
        before, after = old[0], new[0]
        restored = actual[:after['start']] + original[before['start']:before['end']] + actual[after['end']:]
    else:
        before, after = locale_lines(original), locale_lines(actual)
        assert before.keys() == after.keys(), ('Existing locale IDs changed', path)
        restored = actual.decode('utf-8-sig')
        for key in LOCALE_KEYS:
            assert key in before and key in after
            assert restored.count(after[key]) == 1
            restored = restored.replace(after[key], before[key], 1)
        restored = (b'\xef\xbb\xbf' if original.startswith(b'\xef\xbb\xbf') else b'') + restored.encode('utf-8')
    assert restored == original, ('Unowned ammunition source bytes changed', path)
    return original

@lru_cache(maxsize=32)
def package16_historical_existing(baseline):
    return frozenset(subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', baseline, '--', *sorted(EXISTING)], cwd=ROOT).decode().splitlines())

def check_owned_existing():
    for path in sorted(EXISTING): package16_original_bytes(path, (ROOT / path).read_bytes())

def historical_actions(actions):
    """Only older source proofs omit the single separately checked addition."""
    actions = package17_historical_actions(actions)
    return [identity for identity in actions if identity != 'eon_ammo_withdraw_offer']


# Frozen literal source-only changes; no old behavior file is restored or edited.
HISTORICAL_SOURCE_EDITS = {'tools/validation/diplomacy_package_02/test_source.py': [(177,
                                                           178,
                                                           '                                               '
                                                           "'eon_withdraw_antiterror_proposal')))\n",
                                                           '                                               '
                                                           "'eon_withdraw_antiterror_proposal', "
                                                           "'eon_ammo_withdraw_offer')))\n")],
 'tools/validation/diplomacy_package_03/test_source.py': [(55,
                                                           55,
                                                           '',
                                                           'from diplomacy_package_16.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE16_NEW, '
                                                           'package16_original_bytes, '
                                                           'package16_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package16_historical_actions, check_owned_existing as '
                                                           'check_later_package16_owned,\n'
                                                           ')\n'
                                                           'check_later_package16_owned()\n'),
                                                          (237,
                                                           238,
                                                           'tracked_changes = [path for path in tracked_changes '
                                                           'if path not in LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE)]\n',
                                                           'tracked_changes = [path for path in tracked_changes '
                                                           'if path not in LATER_PACKAGE10_EXISTING | '
                                                           'LATER_PACKAGE11_EXISTING | LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n'),
                                                          (241,
                                                           241,
                                                           '',
                                                           'untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW]\n'),
                                                          (304,
                                                           305,
                                                           'actions = historical_actions(actions)\n',
                                                           'actions = '
                                                           'package16_historical_actions(historical_actions(actions))\n')],
 'tools/validation/diplomacy_package_04/test_source.py': [(71,
                                                           71,
                                                           '',
                                                           'from diplomacy_package_16.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE16_NEW, '
                                                           'package16_original_bytes, '
                                                           'package16_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package16_historical_actions, check_owned_existing as '
                                                           'check_later_package16_owned,\n'
                                                           ')\n'
                                                           'check_later_package16_owned()\n'),
                                                          (334,
                                                           335,
                                                           'tracked = [path for path in tracked if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE)]\n',
                                                           'tracked = [path for path in tracked if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n'),
                                                          (336,
                                                           336,
                                                           '',
                                                           'untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW]\n')],
 'tools/validation/diplomacy_package_05/test_source.py': [(66,
                                                           66,
                                                           '',
                                                           'from diplomacy_package_16.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE16_NEW, '
                                                           'package16_original_bytes, '
                                                           'package16_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package16_historical_actions, check_owned_existing as '
                                                           'check_later_package16_owned,\n'
                                                           ')\n'
                                                           'check_later_package16_owned()\n'),
                                                          (275,
                                                           276,
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE)]\n',
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n'),
                                                          (277,
                                                           277,
                                                           '',
                                                           'untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW]\n')],
 'tools/validation/diplomacy_package_06/test_source.py': [(68,
                                                           68,
                                                           '',
                                                           'from diplomacy_package_16.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE16_NEW, '
                                                           'package16_original_bytes, '
                                                           'package16_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package16_historical_actions, check_owned_existing as '
                                                           'check_later_package16_owned,\n'
                                                           ')\n'
                                                           'check_later_package16_owned()\n'),
                                                          (365,
                                                           366,
                                                           'action_ids = historical_actions(action_ids)\n',
                                                           'action_ids = '
                                                           'package16_historical_actions(historical_actions(action_ids))\n'),
                                                          (449,
                                                           450,
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE)]\n',
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n'),
                                                          (451,
                                                           451,
                                                           '',
                                                           'untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW]\n')],
 'tools/validation/diplomacy_package_07/test_source.py': [(66,
                                                           66,
                                                           '',
                                                           'from diplomacy_package_16.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE16_NEW, '
                                                           'package16_original_bytes, '
                                                           'package16_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package16_historical_actions, check_owned_existing as '
                                                           'check_later_package16_owned,\n'
                                                           ')\n'
                                                           'check_later_package16_owned()\n'),
                                                          (128,
                                                           129,
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE)]\n',
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n'),
                                                          (130,
                                                           130,
                                                           '',
                                                           'untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW]\n'),
                                                          (143,
                                                           144,
                                                           'actions = historical_actions(actions)\n',
                                                           'actions = '
                                                           'package16_historical_actions(historical_actions(actions))\n')],
 'tools/validation/diplomacy_package_08/test_source.py': [(66,
                                                           66,
                                                           '',
                                                           'from diplomacy_package_16.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE16_NEW, '
                                                           'package16_original_bytes, '
                                                           'package16_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package16_historical_actions, check_owned_existing as '
                                                           'check_later_package16_owned,\n'
                                                           ')\n'
                                                           'check_later_package16_owned()\n'),
                                                          (125,
                                                           126,
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE)]\n',
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n'),
                                                          (127,
                                                           127,
                                                           '',
                                                           'untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW]\n'),
                                                          (140,
                                                           141,
                                                           'actions = historical_actions(actions)\n',
                                                           'actions = '
                                                           'package16_historical_actions(historical_actions(actions))\n')],
 'tools/validation/diplomacy_package_09/test_source.py': [(54,
                                                           54,
                                                           '',
                                                           'from diplomacy_package_16.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE16_NEW, '
                                                           'package16_original_bytes, '
                                                           'package16_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package16_historical_actions, check_owned_existing as '
                                                           'check_later_package16_owned,\n'
                                                           ')\n'
                                                           'check_later_package16_owned()\n'),
                                                          (108,
                                                           109,
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE)]\n',
                                                           'changed = [path for path in changed if path not in '
                                                           'LATER_PACKAGE10_EXISTING | LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n'),
                                                          (110,
                                                           110,
                                                           '',
                                                           'untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW]\n'),
                                                          (122,
                                                           123,
                                                           'actions = historical_actions(actions)\n',
                                                           'actions = '
                                                           'package16_historical_actions(historical_actions(actions))\n')],
 'tools/validation/diplomacy_package_10/test_source.py': [(46,
                                                           46,
                                                           '',
                                                           'from diplomacy_package_16.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE16_NEW, '
                                                           'package16_original_bytes, '
                                                           'package16_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package16_historical_actions, check_owned_existing as '
                                                           'check_later_package16_owned,\n'
                                                           ')\n'
                                                           'check_later_package16_owned()\n'),
                                                          (188,
                                                           189,
                                                           '    changed = [path for path in changed if path not '
                                                           'in LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE)]\n',
                                                           '    changed = [path for path in changed if path not '
                                                           'in LATER_PACKAGE11_EXISTING | '
                                                           'LATER_PACKAGE12_EXISTING | LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n'),
                                                          (190,
                                                           190,
                                                           '',
                                                           '    untracked = [path for path in untracked if path '
                                                           'not in LATER_PACKAGE16_NEW]\n'),
                                                          (200,
                                                           200,
                                                           '',
                                                           '    actual_ids = '
                                                           'package16_historical_actions(actual_ids)\n')],
 'tools/validation/diplomacy_package_11/test_source.py': [(39,
                                                           39,
                                                           '',
                                                           'from diplomacy_package_16.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE16_NEW, '
                                                           'package16_original_bytes, '
                                                           'package16_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package16_historical_actions, check_owned_existing as '
                                                           'check_later_package16_owned,\n'
                                                           ')\n'
                                                           'check_later_package16_owned()\n'),
                                                          (202,
                                                           203,
                                                           '    changed = [path for path in changed if path not '
                                                           'in LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE)]\n',
                                                           '    untracked = [path for path in untracked if path '
                                                           'not in LATER_PACKAGE16_NEW]\n'
                                                           '    changed = [path for path in changed if path not '
                                                           'in LATER_PACKAGE12_EXISTING | '
                                                           'LATER_PACKAGE13_EXISTING | '
                                                           'package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE) | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n'),
                                                          (212,
                                                           213,
                                                           '            assert package12_original_bytes(path, '
                                                           "(ROOT / path).read_bytes()) == old, ('Old native "
                                                           "action bytes changed', path)\n",
                                                           '            assert package12_original_bytes(path, '
                                                           'package16_original_bytes(path, (ROOT / '
                                                           "path).read_bytes())) == old, ('Old native action "
                                                           "bytes changed', path)\n"),
                                                          (218,
                                                           218,
                                                           '',
                                                           '    actual_native_ids = '
                                                           'package16_historical_actions(actual_native_ids)\n')],
 'tools/validation/diplomacy_package_12/test_source.py': [(25,
                                                           25,
                                                           '',
                                                           'from diplomacy_package_16.test_source import (\r\n'
                                                           '    NEW as LATER_PACKAGE16_NEW, '
                                                           'package16_original_bytes, '
                                                           'package16_historical_existing,\r\n'
                                                           '    historical_actions as '
                                                           'package16_historical_actions, check_owned_existing as '
                                                           'check_later_package16_owned,\r\n'
                                                           ')\r\n'
                                                           'check_later_package16_owned()\r\n'),
                                                          (111,
                                                           111,
                                                           '',
                                                           '    actual = package16_original_bytes(path, '
                                                           'actual)\r\n'),
                                                          (171,
                                                           172,
                                                           '    changed=[path for path in changed if path not in '
                                                           '(package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE))-EXISTING]\r\n',
                                                           '    changed=[path for path in changed if path not in '
                                                           '(package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE))-EXISTING | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\r\n'),
                                                          (173,
                                                           173,
                                                           '',
                                                           '    untracked = [path for path in untracked if path '
                                                           'not in LATER_PACKAGE16_NEW]\r\n'),
                                                          (214,
                                                           214,
                                                           '',
                                                           '    native_ids = '
                                                           'package16_historical_actions(native_ids)\r\n')],
 'tools/validation/diplomacy_package_13/test_source.py': [(25,
                                                           25,
                                                           '',
                                                           'from diplomacy_package_16.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE16_NEW, '
                                                           'package16_original_bytes, '
                                                           'package16_historical_existing,\n'
                                                           '    historical_actions as '
                                                           'package16_historical_actions, check_owned_existing as '
                                                           'check_later_package16_owned,\n'
                                                           ')\n'
                                                           'check_later_package16_owned()\n'),
                                                          (104,
                                                           104,
                                                           '',
                                                           '    actual = package16_original_bytes(path, '
                                                           'actual)\n'),
                                                          (184,
                                                           185,
                                                           '    changed=[path for path in changed if path not in '
                                                           '(package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE))-EXISTING]\n',
                                                           '    changed=[path for path in changed if path not in '
                                                           '(package14_historical_existing(BASELINE) | '
                                                           'package15_historical_existing(BASELINE))-EXISTING | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n'),
                                                          (186,
                                                           186,
                                                           '',
                                                           '    untracked = [path for path in untracked if path '
                                                           'not in LATER_PACKAGE16_NEW]\n'),
                                                          (227,
                                                           227,
                                                           '',
                                                           '    native_ids = '
                                                           'package16_historical_actions(native_ids)\n')],
 'tools/validation/diplomacy_package_14/test_source.py': [(20,
                                                           20,
                                                           '',
                                                           'from diplomacy_package_16.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE16_NEW, '
                                                           'package16_original_bytes, '
                                                           'package16_historical_existing,\n'
                                                           '    package16_original_validator_bytes,\n'
                                                           '    historical_actions as '
                                                           'package16_historical_actions, check_owned_existing as '
                                                           'check_later_package16_owned,\n'
                                                           ')\n'
                                                           'check_later_package16_owned()\n'),
                                                          (200,
                                                           201,
                                                           '    changed=[path for path in changed if path not in '
                                                           'package15_historical_existing(BASELINE)-EXISTING]\n',
                                                           '    changed=[path for path in changed if path not in '
                                                           'package15_historical_existing(BASELINE)-EXISTING | '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW]\n'),
                                                          (202,
                                                           202,
                                                           '',
                                                           '    untracked = [path for path in untracked if path '
                                                           'not in LATER_PACKAGE16_NEW]\n'),
                                                          (207,
                                                           208,
                                                           '            '
                                                           'data=package15_original_bytes(path,(ROOT/path).read_bytes());assert '
                                                           "data==baseline_bytes(path),('Native "
                                                           "visibility_cost_consent_AI_weights_or_scope_modified',path)\n",
                                                           '            '
                                                           'data=package15_original_bytes(path,package16_original_bytes(path,(ROOT/path).read_bytes()));assert '
                                                           "data==baseline_bytes(path),('Native "
                                                           "visibility_cost_consent_AI_weights_or_scope_modified',path)\n"),
                                                          (308,
                                                           309,
                                                           '        assert '
                                                           '(ROOT/path).read_bytes()==baseline_bytes(path),path\n',
                                                           '        assert '
                                                           'package16_original_validator_bytes(path,(ROOT/path).read_bytes())==baseline_bytes(path),path\n')],
 'tools/validation/diplomacy_package_15/test_source.py': [(10,
                                                           10,
                                                           '',
                                                           'import sys as package16_sys\n'
                                                           'package16_sys.path.insert(0, '
                                                           "str(ROOT/'tools/validation'))\n"
                                                           'from diplomacy_package_16.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE16_NEW, '
                                                           'package16_original_bytes, '
                                                           'package16_historical_existing,\n'
                                                           '    package16_original_validator_bytes,\n'
                                                           '    historical_actions as '
                                                           'package16_historical_actions, check_owned_existing as '
                                                           'check_later_package16_owned,\n'
                                                           ')\n'
                                                           'check_later_package16_owned()\n'),
                                                          (802,
                                                           802,
                                                           '',
                                                           '    changed -= '
                                                           'package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW\n'
                                                           '    added -= LATER_PACKAGE16_NEW\n'),
                                                          (922,
                                                           922,
                                                           '',
                                                           '    global_native = '
                                                           'package16_historical_actions(global_native)\n'),
                                                          (948,
                                                           949,
                                                           '        assert '
                                                           '(ROOT/path).read_bytes()==baseline_bytes(path),path\n',
                                                           '        assert '
                                                           'package16_original_validator_bytes(path,(ROOT/path).read_bytes())==baseline_bytes(path),path\n')]}


def package16_original_validator_bytes(path, actual):
    actual = package17_original_validator_bytes(path, actual)
    if path not in HISTORICAL_SOURCE_EDITS: return actual
    original = baseline_bytes(path)
    lines = original.decode('utf-8').splitlines(keepends=True)
    for start, end, before, after in reversed(HISTORICAL_SOURCE_EDITS[path]):
        assert ''.join(lines[start:end]) == before, ('Historical source patch baseline drift', path, start)
        lines[start:end] = [after]
    assert actual == ''.join(lines).encode('utf-8'), ('Undeclared historical source validator edit', path)
    return original

def main():
    groups = Counter()
    def passed(group): groups[group] += 1
    for path in SOURCE_PATHS:
        assert (ROOT / path).is_file(), ('RED: ammunition package source missing', path)
    check_owned_existing()
    for path in sorted(EXISTING):
        assert package16_original_bytes(path, (ROOT / path).read_bytes()) == baseline_bytes(path)
        passed('three_exact_existing_source_range_and_BOM_EOL_boundaries')
    for path in sorted(NEW):
        data = (ROOT / path).read_bytes(); data.decode('utf-8-sig')
        assert data.endswith(b'\n') and b'\r' not in data.replace(b'\r\n', b'')
        if path.endswith('.yml'): assert data.startswith(b'\xef\xbb\xbf')
        else: ast(data)
        passed('seven_new_UTF8_source_or_BOM_locale_files')
    trees = ('common', 'history', 'events', 'interface', 'gfx', 'localisation', 'music', 'map', 'sound',
             'portraits', 'tutorial', 'descriptions', 'scenario_tests', 'descriptor.mod', 'era_of_nations.mod', 'thumbnail.png')
    changed = set(subprocess.check_output(['git', 'diff', '--name-only', BASELINE, '--', *trees], cwd=ROOT).decode().splitlines())
    untracked = set(subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', *trees], cwd=ROOT).decode().splitlines())
    changed -= package17_historical_existing(BASELINE) | LATER_PACKAGE17_NEW | package18_historical_existing(BASELINE) | LATER_PACKAGE18_NEW | package19_historical_existing(BASELINE) | LATER_PACKAGE19_NEW | package20_historical_existing(BASELINE) | LATER_PACKAGE20_NEW | package21_historical_existing(BASELINE) | LATER_PACKAGE21_NEW | package22_historical_existing(BASELINE) | LATER_PACKAGE22_NEW | package23_historical_existing(BASELINE) | LATER_PACKAGE23_NEW
    untracked -= LATER_PACKAGE17_NEW | LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | LATER_PACKAGE22_NEW | LATER_PACKAGE23_NEW
    assert changed - NEW == EXISTING and (changed | untracked) - EXISTING == NEW, (changed, untracked)
    assert not subprocess.check_output(['git', 'diff', '--name-only', '--diff-filter=D', BASELINE, '--', *trees], cwd=ROOT).strip()
    passed('exact_full_gameplay_tree_three_existing_seven_new_no_unowned_deletions')
    action_nodes = ast((ROOT / ACTION).read_bytes())
    current = one(one(action_nodes, 'scripted_diplomatic_actions'), 'Send_ammo')
    original_nodes = ast(baseline_bytes(ACTION))
    original = one(one(original_nodes, 'scripted_diplomatic_actions'), 'Send_ammo')
    assert one(action_nodes, '@Ammo_send_qty') == one(original_nodes, '@Ammo_send_qty') == '100000'
    passed('native_literal_100000_quantity_unchanged')
    for key in ('allowed', 'visible', 'requires_acceptance', 'show_acceptance_on_action_button', 'icon', 'ai_acceptance'):
        assert one(current, key) == one(original, key), ('Existing native field/AI policy changed', key)
        passed('six_original_native_field_and_acceptance_AI_AST_policies_unchanged')
    current_desire = one(current, 'ai_desire')
    guard = ('modifier', '=', [('add', '=', '-20000'), ('NOT', '=', [('eon_ammo_gui_ready', '=', 'yes')])])
    assert current_desire.count(guard) == 1, 'One explicit technical AI admission guard is required'
    assert [row for row in current_desire if row != guard] == one(original, 'ai_desire')
    passed('all_original_AI_desire_weights_and_order_unchanged_with_one_explicit_technical_guard')
    assert one(current, 'selectable') == [('OR', '=', [('eon_ammo_response_pending', '=', 'yes'), ('eon_ammo_gui_ready', '=', 'yes')])]
    assert one(current, 'can_be_sent') == [('eon_ammo_gui_ready', '=', 'yes')]
    assert one(current, 'can_be_accepted') == [('eon_ammo_response_ready', '=', 'yes')]
    passed('pending_modal_reachable_strict_new_send_and_fresh_acceptance_guards')
    for key, helper in (('on_sent_effect', 'eon_ammo_send_offer'), ('complete_effect', 'eon_ammo_accept_offer'), ('reject_effect', 'eon_ammo_reject_offer')):
        assert one(current, key) == [(helper, '=', 'yes')]
        passed('three_exact_native_effect_helpers_no_unguarded_debit_delivery_refund')
    effects = {key: value for key, operator, value in ast((ROOT / FX).read_bytes())}
    triggers = {key: value for key, operator, value in ast((ROOT / TR).read_bytes())}
    for helper in ('send_offer', 'accept_offer', 'reject_offer', 'withdraw_offer', 'daily_cleanup', 'queue_refund', 'release_refund',
                   'refund_escrow', 'clear_pending', 'retire_pending_pair', 'cleanup_annexed_pair', 'transfer_annexed_assets'):
        assert 'eon_ammo_' + helper in effects
        passed('twelve_required_scripted_effect_API_definitions')
    for helper in ('existing_policy', 'recipient_capacity', 'partner_identified', 'gui_ready', 'response_pending', 'response_ready', 'withdraw_available'):
        assert 'eon_ammo_' + helper in triggers
        passed('seven_required_scripted_trigger_API_definitions')
    known = set(effects) | set(triggers)
    for path in (FX, TR, NA, HOOKS, EVENTS, ACTION):
        nodes = ast((ROOT / path).read_bytes())
        for key, operator, value in rows(nodes):
            if key.startswith('eon_ammo_') and value in ('yes', 'no'):
                assert key in known, ('Unknown ammunition helper reference', path, key)
        passed('six_actual_scripted_helper_reference_sets_resolve')
    new_english = locale_lines((ROOT / 'localisation/english/eon_ammo_l_english.yml').read_bytes())
    new_russian = locale_lines((ROOT / 'localisation/russian/eon_ammo_l_russian.yml').read_bytes())
    assert new_english.keys() == new_russian.keys()
    passed('new_bilingual_locale_key_sets_match')
    assert len(effects) == 12 and len(triggers) == 7
    passed('exact_nineteen_owned_helper_IDs_no_unreviewed_additions')
    for helper in known:
        folder = 'scripted_effects' if helper in effects else 'scripted_triggers'
        pattern = rb'(?m)^' + re.escape(helper.encode('utf-8')) + rb'\s*=\s*{'
        count = sum(len(re.findall(pattern, path.read_bytes()))
                    for path in (ROOT / 'common' / folder).glob('*.txt'))
        assert count == 1, ('Duplicate helper', helper, count)
        passed('nineteen_global_owned_helper_IDs_unique')

    # Literal native equations, not the stale monthly cache, define current room.
    native_capacity_path = 'common/scripted_effects/00_ammo_mechanics_effects.txt'
    native_capacity_bytes = (ROOT / native_capacity_path).read_bytes()
    assert native_capacity_bytes == baseline_bytes(native_capacity_path)
    for name, literal in (('@base_max_ammo_limit', '10000'), ('@base_max_ammo_limit_per_supply_node', '100000')):
        assert re.findall(rb'(?m)^\s*' + name.encode() + rb'\s*=\s*(\d+)', native_capacity_bytes) == [literal.encode()]
    native_capacity_block = next(item for item in blocks(native_capacity_bytes, 0) if item['key'] == 'count_max_ammo_limit')
    capacity_nodes = ast(native_capacity_bytes[native_capacity_block['start']:native_capacity_block['end']])
    assert one(capacity_nodes, 'count_max_ammo_limit') == [
        ('set_variable', '=', [('max_ammo_limit', '=', 'num_of_supply_nodes')]),
        ('multiply_variable', '=', [('max_ammo_limit', '=', '@base_max_ammo_limit_per_supply_node')]),
        ('add_to_variable', '=', [('max_ammo_limit', '=', '@base_max_ammo_limit')]),
        ('round_variable', '=', 'max_ammo_limit'),
        ('clamp_variable', '=', [('var', '=', 'max_ammo_limit'), ('min', '=', '@base_max_ammo_limit'), ('max', '=', '1000000000')])]
    capacity = [
        ('set_temp_variable', '=', [('eon_ammo_capacity', '=', 'num_of_supply_nodes')]),
        ('multiply_temp_variable', '=', [('eon_ammo_capacity', '=', '100000')]),
        ('add_to_temp_variable', '=', [('eon_ammo_capacity', '=', '10000')]),
        ('round_temp_variable', '=', 'eon_ammo_capacity'),
        ('clamp_temp_variable', '=', [('var', '=', 'eon_ammo_capacity'), ('min', '=', '10000'), ('max', '=', '1000000000')])]
    assert triggers['eon_ammo_recipient_capacity'] == capacity + [
        ('set_temp_variable', '=', [('eon_ammo_projected_stock', '=', 'ammo_stock')]),
        ('add_to_temp_variable', '=', [('eon_ammo_projected_stock', '=', '100000')]),
        ('check_variable', '=', [('eon_ammo_projected_stock', '<=', 'eon_ammo_capacity')])]
    release = one(effects['eon_ammo_release_refund'], 'if')
    assert release[1:6] == capacity
    passed('unchanged_native_storage_equation_exact_fresh_recipient_and_refund_capacity')
    # Select the guarded credit branch by its physical write; there are two ifs.
    credit = next(body for key, op, body in release if key == 'if'
                  and any(k == 'add_to_variable' for k, o, v in body))
    assert credit[1:] == [
        ('set_variable', '=', [('max_ammo_limit', '=', 'eon_ammo_capacity')]),
        ('add_to_variable', '=', [('ammo_stock', '=', 'eon_ammo_refund_credit')]),
        ('subtract_from_variable', '=', [('eon_ammo_refund_claim', '=', 'eon_ammo_refund_credit')])]
    accept_rows = list(rows(effects['eon_ammo_accept_offer']))
    assert ('set_variable', '=', [('max_ammo_limit', '=', 'eon_ammo_capacity')]) in accept_rows
    assert ('set_variable', '=', [('ammo_stock', '=', 'max_ammo_limit')]) not in list(rows(effects['eon_ammo_release_refund']))
    passed('fresh_maximum_cache_updated_before_successful_delivery_or_positive_credit_without_trimming_stock')

    policy = triggers['eon_ammo_existing_policy']
    old_selectable = one(original, 'selectable')
    assert one(policy, 'if') == one(old_selectable, 'if')
    assert [('has_war', '=', 'yes'), ('NOT', '=', [('has_war_with', '=', 'ROOT')])] == one(old_selectable, 'THIS')
    assert policy[:5] == [('exists', '=', 'yes'), ('NOT', '=', [('tag', '=', 'ROOT')]),
                         ('ROOT', '=', [('exists', '=', 'yes')]), ('has_war', '=', 'yes'),
                         ('NOT', '=', [('has_war_with', '=', 'ROOT')])]
    passed('original_ally_world_tension_and_direct_war_policy_exact_with_live_distinct_country_guards')
    assert triggers['eon_ammo_partner_identified'] == [
        ('check_variable', '=', [('eon_ammo_partner', '>', '0')]),
        ('var:eon_ammo_partner', '=', [
            ('OR', '=', [('exists', '=', 'yes'), ('exists', '=', 'no')]),
            ('NOT', '=', [('tag', '=', 'PREV')]),
            ('check_variable', '=', [('THIS.id', '=', 'PREV.eon_ammo_partner')])])]
    assert not any(key in ('always', 'scope_exists') for key, op, value in rows(triggers['eon_ammo_partner_identified']))
    passed('country_only_exists_and_exact_ID_identification_including_dead_known_country_not_variable_scope_validity')
    for flag in ('eon_ammo_pending', 'eon_ammo_live', 'eon_ammo_cancelled', 'Ammo_diplo_AI_debounce', 'eon_ammo_retired_pair@PREV'):
        assert ('NOT', '=', [('has_country_flag', '=', flag)]) in list(rows(triggers['eon_ammo_gui_ready']))
    for var in ('eon_ammo_partner', 'eon_ammo_escrow'):
        assert ('check_variable', '=', [(var, '=', '0')]) in list(rows(triggers['eon_ammo_gui_ready']))
    passed('legacy_debounce_and_every_partial_record_block_new_send_without_inferred_migration')
    refund = one(effects['eon_ammo_refund_escrow'], 'if')
    assert refund[2:4] == [('clear_variable', '=', 'eon_ammo_escrow'), ('eon_ammo_queue_refund', '=', 'yes')]
    success = next(body for key, op, body in one(effects['eon_ammo_accept_offer'], 'if') if key == 'if')
    assert success[1:4] == [('ROOT', '=', [('clear_variable', '=', 'eon_ammo_escrow')]),
                            ('set_variable', '=', [('max_ammo_limit', '=', 'eon_ammo_capacity')]),
                            ('add_to_variable', '=', [('ammo_stock', '=', '100000')])]
    passed('held_ownership_zeroed_before_authoritative_refund_queue_or_delivery')
    old_desire_blocks = [b for b in blocks(baseline_bytes(ACTION), 3) if b['key'] == 'modifier']
    new_desire_blocks = [b for b in blocks((ROOT / ACTION).read_bytes(), 3) if b['key'] == 'modifier']
    old_raw = baseline_bytes(ACTION); new_raw = (ROOT / ACTION).read_bytes()
    assert [old_raw[b['start']:b['end']] for b in old_desire_blocks] == [
        new_raw[b['start']:b['end']] for b in new_desire_blocks
        if b'eon_ammo_gui_ready' not in new_raw[b['start']:b['end']]]
    old_accept = next(b for b in blocks(old_raw, 2) if b['key'] == 'ai_acceptance')
    new_accept = next(b for b in blocks(new_raw, 2) if b['key'] == 'ai_acceptance')
    assert old_raw[old_accept['start']:old_accept['end']] == new_raw[new_accept['start']:new_accept['end']]
    passed('original_acceptance_block_and_every_original_desire_modifier_raw_bytes_preserved')

    new_action = one(ast((ROOT / NA).read_bytes()), 'scripted_diplomatic_actions')
    assert [key for key, op, value in new_action] == ['eon_ammo_withdraw_offer']
    withdraw = one(new_action, 'eon_ammo_withdraw_offer')
    assert one(withdraw, 'cost') == '0' and one(withdraw, 'requires_acceptance') == 'no'
    assert one(withdraw, 'allowed') == [('ROOT', '=', [('is_ai', '=', 'no')])]
    assert one(withdraw, 'complete_effect') == [('eon_ammo_withdraw_offer', '=', 'yes')]
    for field in ('visible', 'selectable', 'can_be_sent'):
        assert one(withdraw, field) == [('eon_ammo_withdraw_available', '=', 'yes')]
    passed('one_free_human_sender_withdrawal_native_action_with_three_fresh_guards')
    native_ids = [key for path in (ROOT / 'common/scripted_diplomatic_actions').glob('*.txt')
                  for key, op, val in one(ast(path.read_bytes()), 'scripted_diplomatic_actions')]
    old_ids = [key for path in subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, '--',
               'common/scripted_diplomatic_actions'], cwd=ROOT).decode().splitlines() if path.endswith('.txt')
               for key, op, val in one(ast(baseline_bytes(path)), 'scripted_diplomatic_actions')]
    native_ids = package17_historical_actions(native_ids)
    assert len(old_ids) == len(set(old_ids)) == 65 and len(native_ids) == len(set(native_ids)) == 66
    assert set(native_ids) == set(old_ids) | {'eon_ammo_withdraw_offer'}
    passed('all65_existing_native_IDs_plus_one_unique_addition_no_migration')
    hooks = one(ast((ROOT / HOOKS).read_bytes()), 'on_actions')
    assert one(one(hooks, 'on_daily'), 'effect') == [('eon_ammo_daily_cleanup', '=', 'yes')]
    for hook, victim, successor in (('on_annex', 'FROM', 'ROOT'), ('on_subject_annexed', 'ROOT', 'FROM')):
        body = one(one(hooks, hook), 'effect')
        assert body[-2:] == [('set_temp_variable', '=', [('eon_ammo_successor', '=', successor)]),
                            (victim, '=', [('eon_ammo_transfer_annexed_assets', '=', 'yes')])]
        assert ('set_temp_variable', '=', [('eon_ammo_annexed_partner', '=', victim)]) in list(rows(body))
        passed('two_native_annex_roles_successor_and_victim_not_reversed')
    for helper in ('eon_ammo_cleanup_annexed_pair', 'eon_ammo_transfer_annexed_assets'):
        calls = list(rows(effects[helper]))
        assert not any(key in ('eon_ammo_release_refund', 'add_to_variable', 'subtract_from_variable') for key, op, val in calls)
        passed('annex_held_asset_cleanup_queues_only_no_physical_credit_before_native_inheritance')
    transfer = effects['eon_ammo_transfer_annexed_assets']
    clears = [i for i, row in enumerate(transfer) if row[0] == 'clear_variable']
    assert len(clears) == 2 and max(clears) < len(transfer) - 1
    passed('annex_claim_and_actual_escrow_zero_before_successor_queue_including_orphan_ownership')
    notice_nodes = ast((ROOT / EVENTS).read_bytes())
    notices = [body for key, op, body in notice_nodes if key == 'country_event']
    assert {one(body, 'id') for body in notices} == {f'eon_ammo.{i}' for i in range(1, 5)}
    for body in notices:
        assert one(body, 'option') == [('name', '=', 'eon_ammo.ack')]
        assert one(body, 'is_triggered_only') == 'yes' and one(body, 'picture') == 'GFX_handgun'
        passed('four_static_ACK_only_notices_no_mutable_later_effect')
    for path in (FX, TR):
        assert not any(key in ('add_political_power', 'add_command_power', 'add_treasury', 'add_to_faction',
            'declare_war_on', 'white_peace', 'set_rule', 'create_faction') for key, op, val in rows(ast((ROOT / path).read_bytes())))
        for key, op, val in rows(ast((ROOT / path).read_bytes())):
            if key == 'NOT': assert len(val) == 1, ('Ambiguous multi-child native NOR', path, val)
        passed('owned_helpers_no_economy_war_faction_or_PP_mutation_and_unambiguous_native_NOT')

    # Source-only adapter invariants are separate from actual gameplay scenarios.
    boundary_groups = set()
    for path in EXISTING:
        try: package16_original_bytes(path, (ROOT / path).read_bytes() + b'\n# memory-only unowned mutation\n')
        except AssertionError: pass
        else: raise AssertionError(('Outside-range change accepted', path))
        passed('memory_only_existing_source_outside_range_mutation_rejected')
        boundary_groups.add('memory_only_existing_source_outside_range_mutation_rejected')
    for path in sorted(HISTORICAL_SOURCE_EDITS):
        actual = (ROOT / path).read_bytes()
        assert package16_original_validator_bytes(path, actual) == baseline_bytes(path)
        original_increments = [line for line in baseline_bytes(path).splitlines() if b"groups[" in line and b'+=' in line or b"passed(" in line]
        actual_increments = [line for line in actual.splitlines() if b"groups[" in line and b'+=' in line or b"passed(" in line]
        assert original_increments == actual_increments, ('Historical assertion counters changed', path)
        passed('fourteen_exact_literal_whole_source_validator_journals_and_original_counter_lines')
        try: package16_original_validator_bytes(path, actual + b'\n# unowned memory-only probe\n')
        except AssertionError: pass
        else: raise AssertionError(('Undeclared older validator edit accepted', path))
        passed('memory_only_historical_source_whole_file_mutation_rejected')
        boundary_groups.add('memory_only_historical_source_whole_file_mutation_rejected')
    source01_path = 'tools/validation/diplomacy_package_01/test_source.py'
    assert (ROOT / source01_path).read_bytes() == baseline_bytes(source01_path)
    passed('source01_complete_public_validator_bytes_unchanged')
    behavior_paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, '--', 'tools/validation'], cwd=ROOT).decode().splitlines()
    behavior_paths = [path for path in behavior_paths if path.endswith('.py') and
                      Path(path).name != 'test_source.py']
    for path in behavior_paths:
        assert (ROOT / path).read_bytes() == baseline_bytes(path), ('Earlier behavior/runner changed', path)
    passed('all_prior_behavior_executors_assertions_cases_and_runners_whole_bytes_unchanged')
    installed = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV')
    effect_docs = (installed / 'documentation/effects_documentation.md').read_text(encoding='utf-8-sig')
    trigger_docs = (installed / 'documentation/triggers_documentation.md').read_text(encoding='utf-8-sig')
    for helper in ('round_temp_variable', 'set_temp_variable', 'clamp_temp_variable', 'add_to_variable',
                   'subtract_from_variable', 'clear_variable', 'set_country_flag', 'modify_country_flag',
                   'every_country', 'country_event'):
        assert '\n## ' + helper + '\n' in effect_docs
        passed('ten_installed_primary_effect_API_declarations')
    for helper in ('round_temp_variable', 'clamp_temp_variable', 'exists', 'check_variable', 'is_ally_with', 'has_war', 'has_war_with'):
        assert '\n## ' + helper + '\n' in trigger_docs
        passed('seven_installed_primary_trigger_API_declarations')
    assert 'Always true since variables are always valid scopes' in trigger_docs
    assert 'exists that checks if the country of the scope exists' in trigger_docs
    passed('primary_variable_scope_validity_is_not_country_identity_resolution')
    sprites = list((ROOT / 'interface').glob('*.gfx')) + list((installed / 'interface').glob('*.gfx'))
    assert any(b'GFX_handgun' in path.read_bytes() for path in sprites)
    passed('existing_native_handgun_notification_sprite_resolves')
    assert len(new_english) == len(new_russian) == 14
    for nodes in (ast((ROOT / TR).read_bytes()), ast((ROOT / NA).read_bytes()), notice_nodes):
        for key, op, val in rows(nodes):
            if key in ('tooltip', 'title', 'desc', 'name', 'send_description') and isinstance(val, str) and val.startswith('eon_ammo'):
                assert val in new_english and val in new_russian, ('Unresolved locale', val)
    passed('fourteen_new_bilingual_keys_all_actual_tooltip_action_notice_references_resolve')
    hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCE_PATHS}
    boundary_cases = sum(groups[group] for group in boundary_groups)
    print(json.dumps({'all_passed': True, 'total_cases': sum(groups.values()),
        'source_API_cases': sum(groups.values()) - boundary_cases,
        'source_byte_adapter_boundary_cases': boundary_cases, 'groups': dict(groups),
        'baseline': BASELINE, 'owned_existing_gameplay_files': len(EXISTING), 'new_gameplay_files': len(NEW),
        'native_action_count': len(native_ids), 'new_locale_keys': len(new_english),
        'prior_behavior_and_runner_files_byte_unchanged': len(behavior_paths),
        'historical_source_adapters': len(HISTORICAL_SOURCE_EDITS),
        'source_sha256': hashes, 'runtime_verified': False}, indent=2))

if __name__ == '__main__': main()
