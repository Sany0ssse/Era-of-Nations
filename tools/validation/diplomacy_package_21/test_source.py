"""Exact paid advisory-service footprint and historical byte views; not native HOI4 runtime."""
from pathlib import Path
from functools import lru_cache
from collections import Counter
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '00bab1d58dae8f16c3d74c78be6db241cab5b2b6'
import sys as package22_sys
package22_sys.path.insert(0,str(ROOT/'tools/validation'))
from diplomacy_package_22.test_source import (
    NEW as LATER_PACKAGE22_NEW, package22_original_bytes, package22_historical_existing,
    package22_original_validator_bytes, historical_actions as package22_historical_actions,
    check_owned_existing as check_later_package22_owned,
)
check_later_package22_owned()
EXISTING = {
    'events/00_Influence_events.txt','common/ideas/Generic Tree_ideas.txt',
    'localisation/english/events_l_english.yml','localisation/english/MD_influence_l_english.yml',
    'localisation/russian/replace/replaced_from_events_l_russian.yml',
    'localisation/russian/replace/replaced_from_MD_influence_l_russian.yml',
    'localisation/english/MDC_focus_GENERIC_l_english.yml',
    'localisation/russian/MDDC_focus_GENERIC_l_russian.yml'}
CHOICES = (('influence.501','influence.501.c'),('influence.502','influence.502.a'),
           ('influence.502','influence.502.b'),('influence.503','influence.503.a'),
           ('influence.505','influence.505.a'))
LEGACY_LOCALE_KEYS = {'influence.'+str(i)+'.'+suffix for i in (502,503,505) for suffix in ('t','d')} | {'influence.502.a','influence.502.b','influence.503.a','influence.505.a'}
AID_TOOLTIP_COUNTS = {'localisation/english/MD_influence_l_english.yml':2,
                      'localisation/russian/replace/replaced_from_MD_influence_l_russian.yml':1}
FX = 'common/scripted_effects/eon_advisers_effects.txt'
TR = 'common/scripted_triggers/eon_advisers_triggers.txt'
NA = 'common/scripted_diplomatic_actions/eon_advisers_actions.txt'
HOOKS = 'common/on_actions/eon_advisers_on_actions.txt'
EVENTS = 'events/eon_advisers_events.txt'
IDEAS = 'common/ideas/eon_advisers_ideas.txt'
NEW = {FX, TR, NA, HOOKS, EVENTS, IDEAS} | {f'localisation/{language}/eon_advisers_l_{language}.yml' for language in ('english', 'russian')}
SOURCE_PATHS = sorted(EXISTING | NEW)
NEW_ACTION_IDS = {'eon_advisers_withdraw_offer','eon_advisers_end_cooperation'}
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

def named_block(data,key):
    found = [item for item in blocks(data) if item['key'] == key]
    assert len(found) == 1, (key,len(found))
    return found[0]

def legacy_on_remove(data):
    idea = named_block(data,'grey_men_foreign_idea')
    segment = data[idea['start']:idea['end']]
    block = named_block(segment,'on_remove')
    return {'start':idea['start']+block['start'],'end':idea['start']+block['end']}

def package21_original_bytes(path,actual):
    actual = package22_original_bytes(path,actual)
    """Inverse only declared choices, locale lines and the global old return broadcast."""
    if path not in EXISTING: return actual
    original = baseline_bytes(path); format_preserved(original,actual,path)
    if path == 'events/00_Influence_events.txt':
        assert event_blocks(original).keys() == event_blocks(actual).keys()
        restored = actual
        for identity,name in reversed(CHOICES):
            before = option_block(original,identity,name); after = option_block(restored,identity,name)
            restored = restored[:after['start']]+original[before['start']:before['end']]+restored[after['end']:]
    elif path == 'common/ideas/Generic Tree_ideas.txt':
        before = legacy_on_remove(original); after = legacy_on_remove(actual)
        old_body = original[before['start']:before['end']]; new_body = actual[after['start']:after['end']]
        old_nodes = ast(old_body)[0][2]; new_nodes = ast(new_body)[0][2]
        assert [key for key,op,val in old_nodes] == ['every_country','delete_unit_template_and_units']
        assert new_nodes == [old_nodes[1]], 'Only the old global return broadcast may be removed'
        assert field_raw(old_body,'delete_unit_template_and_units') == field_raw(new_body,'delete_unit_template_and_units'), 'Legacy shared deletion remainder changed'
        restored = actual[:after['start']]+old_body+actual[after['end']:]
    else:
        original_lines = original.splitlines(keepends=True); actual_lines = actual.splitlines(keepends=True)
        assert len(original_lines) == len(actual_lines),('Locale line count changed',path)
        allowed = LEGACY_LOCALE_KEYS if Path(path).name in ('MDC_focus_GENERIC_l_english.yml','MDDC_focus_GENERIC_l_russian.yml') else {'influence.501.c','influence.501.d'}
        if path in AID_TOOLTIP_COUNTS:
            allowed = allowed | {'aid_military_button_TT'}
            assert sum(bool(re.match(rb'\s*aid_military_button_TT:',line)) for line in original_lines) == AID_TOOLTIP_COUNTS[path]
        seen = set(); restored_lines = []
        for before,after in zip(original_lines,actual_lines):
            match = re.match(rb'\s*([A-Za-z0-9_.]+):',before); key = match[1].decode() if match else None
            if key in allowed:
                assert re.match(rb'\s*([A-Za-z0-9_.]+):',after)[1].decode() == key
                seen.add(key); restored_lines.append(before)
            else: restored_lines.append(after)
        assert seen == allowed,('Incomplete legacy locale key set',path)
        restored = b''.join(restored_lines)
    assert restored == original,('Unowned adviser source bytes changed',path)
    return original

@lru_cache(maxsize=32)
def package21_historical_existing(baseline):
    return frozenset(subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', baseline, '--', *sorted(EXISTING)], cwd=ROOT).decode().splitlines())

def check_owned_existing():
    for path in sorted(EXISTING): package21_original_bytes(path, package22_original_bytes(path,(ROOT / path).read_bytes()))

def historical_actions(actions):
    actions = package22_historical_actions(actions)
    return [identity for identity in actions if identity not in NEW_ACTION_IDS]

HISTORICAL_SOURCE_EDITS = {'tools/validation/diplomacy_package_02/test_source.py': [(177,
                                                           178,
                                                           '                                               '
                                                           "'eon_withdraw_antiterror_proposal', "
                                                           "'eon_ammo_withdraw_offer', "
                                                           "'eon_services_withdraw_offer', "
                                                           "'eon_services_end_logistics', 'eon_services_end_recon', "
                                                           "'eon_foreign_cash_withdraw_offer', "
                                                           "'eon_foreign_equipment_withdraw_offer', "
                                                           "'eon_defence_formation_withdraw_offer')))\n",
                                                           '                                               '
                                                           "'eon_withdraw_antiterror_proposal', "
                                                           "'eon_ammo_withdraw_offer', "
                                                           "'eon_services_withdraw_offer', "
                                                           "'eon_services_end_logistics', 'eon_services_end_recon', "
                                                           "'eon_foreign_cash_withdraw_offer', "
                                                           "'eon_foreign_equipment_withdraw_offer', "
                                                           "'eon_defence_formation_withdraw_offer', "
                                                           "'eon_advisers_withdraw_offer', "
                                                           "'eon_advisers_end_cooperation')))\n")],
 'tools/validation/diplomacy_package_03/test_source.py': [(83,
                                                           83,
                                                           '',
                                                           'from diplomacy_package_21.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE21_NEW, '
                                                           'package21_original_bytes, '
                                                           'package21_historical_existing,\n'
                                                           '    package21_original_validator_bytes, '
                                                           'historical_actions as package21_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package21_owned,\n'
                                                           ')\n'
                                                           'check_later_package21_owned()\n'),
                                                          (265,
                                                           266,
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
                                                           'LATER_PACKAGE20_NEW]\n',
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
                                                           'LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW]\n'),
                                                          (269,
                                                           270,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n'),
                                                          (283,
                                                           284,
                                                           '    assert package10_original_bytes(unchanged, '
                                                           'package14_original_bytes(unchanged, (ROOT / '
                                                           'unchanged).read_bytes())) == baseline(unchanged), '
                                                           "'Preserved policy bytes changed: ' + unchanged\n",
                                                           '    assert package10_original_bytes(unchanged, '
                                                           'package14_original_bytes(unchanged, '
                                                           'package21_original_bytes(unchanged, (ROOT / '
                                                           'unchanged).read_bytes()))) == baseline(unchanged), '
                                                           "'Preserved policy bytes changed: ' + unchanged\n")],
 'tools/validation/diplomacy_package_04/test_source.py': [(99,
                                                           99,
                                                           '',
                                                           'from diplomacy_package_21.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE21_NEW, '
                                                           'package21_original_bytes, '
                                                           'package21_historical_existing,\n'
                                                           '    package21_original_validator_bytes, '
                                                           'historical_actions as package21_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package21_owned,\n'
                                                           ')\n'
                                                           'check_later_package21_owned()\n'),
                                                          (362,
                                                           363,
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
                                                           'LATER_PACKAGE20_NEW]\n',
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
                                                           'LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW]\n'),
                                                          (364,
                                                           365,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n')],
 'tools/validation/diplomacy_package_05/test_source.py': [(94,
                                                           94,
                                                           '',
                                                           'from diplomacy_package_21.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE21_NEW, '
                                                           'package21_original_bytes, '
                                                           'package21_historical_existing,\n'
                                                           '    package21_original_validator_bytes, '
                                                           'historical_actions as package21_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package21_owned,\n'
                                                           ')\n'
                                                           'check_later_package21_owned()\n'),
                                                          (302,
                                                           302,
                                                           '',
                                                           "package21_required_old_paths = {r['path'] for r in "
                                                           'receipts} | new | later_package06_paths | '
                                                           'later_package07_new | later_package08_new | '
                                                           'LATER_PACKAGE09_NEW | LATER_PACKAGE10_NEW | '
                                                           'LATER_PACKAGE11_NEW | LATER_PACKAGE12_NEW | '
                                                           'LATER_PACKAGE13_NEW\n'),
                                                          (303,
                                                           304,
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
                                                           'LATER_PACKAGE20_NEW]\n',
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
                                                           'LATER_PACKAGE20_NEW | '
                                                           '(package21_historical_existing(BASELINE) - '
                                                           'package21_required_old_paths) | LATER_PACKAGE21_NEW]\n'),
                                                          (305,
                                                           306,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n')],
 'tools/validation/diplomacy_package_06/test_source.py': [(96,
                                                           96,
                                                           '',
                                                           'from diplomacy_package_21.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE21_NEW, '
                                                           'package21_original_bytes, '
                                                           'package21_historical_existing,\n'
                                                           '    package21_original_validator_bytes, '
                                                           'historical_actions as package21_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package21_owned,\n'
                                                           ')\n'
                                                           'check_later_package21_owned()\n'),
                                                          (476,
                                                           476,
                                                           '',
                                                           'package21_required_old_paths = EXISTING | NEW | '
                                                           'LATER_PACKAGE07_NEW | LATER_PACKAGE08_NEW | '
                                                           'LATER_PACKAGE09_NEW | LATER_PACKAGE10_NEW | '
                                                           'LATER_PACKAGE11_NEW | LATER_PACKAGE12_NEW | '
                                                           'LATER_PACKAGE13_NEW\n'),
                                                          (477,
                                                           478,
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
                                                           'LATER_PACKAGE20_NEW]\n',
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
                                                           'LATER_PACKAGE20_NEW | '
                                                           '(package21_historical_existing(BASELINE) - '
                                                           'package21_required_old_paths) | LATER_PACKAGE21_NEW]\n'),
                                                          (479,
                                                           480,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n')],
 'tools/validation/diplomacy_package_07/test_source.py': [(94,
                                                           94,
                                                           '',
                                                           'from diplomacy_package_21.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE21_NEW, '
                                                           'package21_original_bytes, '
                                                           'package21_historical_existing,\n'
                                                           '    package21_original_validator_bytes, '
                                                           'historical_actions as package21_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package21_owned,\n'
                                                           ')\n'
                                                           'check_later_package21_owned()\n'),
                                                          (156,
                                                           157,
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
                                                           'LATER_PACKAGE20_NEW]\n',
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
                                                           'LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW]\n'),
                                                          (158,
                                                           159,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n')],
 'tools/validation/diplomacy_package_08/test_source.py': [(94,
                                                           94,
                                                           '',
                                                           'from diplomacy_package_21.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE21_NEW, '
                                                           'package21_original_bytes, '
                                                           'package21_historical_existing,\n'
                                                           '    package21_original_validator_bytes, '
                                                           'historical_actions as package21_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package21_owned,\n'
                                                           ')\n'
                                                           'check_later_package21_owned()\n'),
                                                          (153,
                                                           154,
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
                                                           'LATER_PACKAGE20_NEW]\n',
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
                                                           'LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW]\n'),
                                                          (155,
                                                           156,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n')],
 'tools/validation/diplomacy_package_09/test_source.py': [(82,
                                                           82,
                                                           '',
                                                           'from diplomacy_package_21.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE21_NEW, '
                                                           'package21_original_bytes, '
                                                           'package21_historical_existing,\n'
                                                           '    package21_original_validator_bytes, '
                                                           'historical_actions as package21_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package21_owned,\n'
                                                           ')\n'
                                                           'check_later_package21_owned()\n'),
                                                          (136,
                                                           137,
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
                                                           'LATER_PACKAGE20_NEW]\n',
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
                                                           'LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW]\n'),
                                                          (138,
                                                           139,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n')],
 'tools/validation/diplomacy_package_10/test_source.py': [(74,
                                                           74,
                                                           '',
                                                           'from diplomacy_package_21.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE21_NEW, '
                                                           'package21_original_bytes, '
                                                           'package21_historical_existing,\n'
                                                           '    package21_original_validator_bytes, '
                                                           'historical_actions as package21_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package21_owned,\n'
                                                           ')\n'
                                                           'check_later_package21_owned()\n'),
                                                          (216,
                                                           217,
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
                                                           'LATER_PACKAGE20_NEW]\n',
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
                                                           'LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW]\n'),
                                                          (218,
                                                           219,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n')],
 'tools/validation/diplomacy_package_11/test_source.py': [(67,
                                                           67,
                                                           '',
                                                           'from diplomacy_package_21.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE21_NEW, '
                                                           'package21_original_bytes, '
                                                           'package21_historical_existing,\n'
                                                           '    package21_original_validator_bytes, '
                                                           'historical_actions as package21_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package21_owned,\n'
                                                           ')\n'
                                                           'check_later_package21_owned()\n'),
                                                          (230,
                                                           232,
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
                                                           'LATER_PACKAGE20_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n'
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
                                                           'LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW]\n')],
 'tools/validation/diplomacy_package_12/test_source.py': [(53,
                                                           53,
                                                           '',
                                                           'from diplomacy_package_21.test_source import (\r\n'
                                                           '    NEW as LATER_PACKAGE21_NEW, '
                                                           'package21_original_bytes, '
                                                           'package21_historical_existing,\r\n'
                                                           '    package21_original_validator_bytes, '
                                                           'historical_actions as package21_historical_actions,\r\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package21_owned,\r\n'
                                                           ')\r\n'
                                                           'check_later_package21_owned()\r\n'),
                                                          (200,
                                                           201,
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
                                                           'LATER_PACKAGE20_NEW]\r\n',
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
                                                           'LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW]\r\n'),
                                                          (202,
                                                           203,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\r\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\r\n')],
 'tools/validation/diplomacy_package_13/test_source.py': [(53,
                                                           53,
                                                           '',
                                                           'from diplomacy_package_21.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE21_NEW, '
                                                           'package21_original_bytes, '
                                                           'package21_historical_existing,\n'
                                                           '    package21_original_validator_bytes, '
                                                           'historical_actions as package21_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package21_owned,\n'
                                                           ')\n'
                                                           'check_later_package21_owned()\n'),
                                                          (213,
                                                           214,
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
                                                           'LATER_PACKAGE20_NEW]\n',
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
                                                           'LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW]\n'),
                                                          (215,
                                                           216,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n')],
 'tools/validation/diplomacy_package_14/test_source.py': [(49,
                                                           49,
                                                           '',
                                                           'from diplomacy_package_21.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE21_NEW, '
                                                           'package21_original_bytes, '
                                                           'package21_historical_existing,\n'
                                                           '    package21_original_validator_bytes, '
                                                           'historical_actions as package21_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package21_owned,\n'
                                                           ')\n'
                                                           'check_later_package21_owned()\n'),
                                                          (229,
                                                           230,
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
                                                           'LATER_PACKAGE20_NEW]\n',
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
                                                           'LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW]\n'),
                                                          (231,
                                                           232,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n')],
 'tools/validation/diplomacy_package_15/test_source.py': [(41,
                                                           41,
                                                           '',
                                                           'from diplomacy_package_21.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE21_NEW, '
                                                           'package21_original_bytes, '
                                                           'package21_historical_existing,\n'
                                                           '    package21_original_validator_bytes, '
                                                           'historical_actions as package21_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package21_owned,\n'
                                                           ')\n'
                                                           'check_later_package21_owned()\n'),
                                                          (833,
                                                           835,
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
                                                           'LATER_PACKAGE20_NEW\n',
                                                           '    changed -= package16_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE16_NEW | '
                                                           'package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW\n'
                                                           '    added -= LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW\n')],
 'tools/validation/diplomacy_package_16/test_source.py': [(41,
                                                           41,
                                                           '',
                                                           'from diplomacy_package_21.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE21_NEW, '
                                                           'package21_original_bytes, '
                                                           'package21_historical_existing,\n'
                                                           '    package21_original_validator_bytes, '
                                                           'historical_actions as package21_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package21_owned,\n'
                                                           ')\n'
                                                           'check_later_package21_owned()\n'),
                                                          (664,
                                                           666,
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
                                                           'LATER_PACKAGE20_NEW\n',
                                                           '    changed -= package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW\n'
                                                           '    untracked -= LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW\n')],
 'tools/validation/diplomacy_package_17/test_source.py': [(35,
                                                           35,
                                                           '',
                                                           'from diplomacy_package_21.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE21_NEW, '
                                                           'package21_original_bytes, '
                                                           'package21_historical_existing,\n'
                                                           '    package21_original_validator_bytes, '
                                                           'historical_actions as package21_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package21_owned,\n'
                                                           ')\n'
                                                           'check_later_package21_owned()\n'),
                                                          (122,
                                                           122,
                                                           '',
                                                           '    if actual == baseline_bytes(path): return actual\n'
                                                           '    actual = package21_original_bytes(path,actual)\n'),
                                                          (755,
                                                           757,
                                                           '    changed -= package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW\n'
                                                           '    untracked -= LATER_PACKAGE18_NEW | '
                                                           'LATER_PACKAGE19_NEW | LATER_PACKAGE20_NEW\n',
                                                           '    changed -= package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW | '
                                                           '(package21_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE21_NEW\n'
                                                           '    untracked -= LATER_PACKAGE18_NEW | '
                                                           'LATER_PACKAGE19_NEW | LATER_PACKAGE20_NEW | '
                                                           'LATER_PACKAGE21_NEW\n'),
                                                          (760,
                                                           761,
                                                           '    raw = (ROOT / next(iter(EXISTING))).read_bytes(); '
                                                           'old_raw = baseline_bytes(next(iter(EXISTING)))\n',
                                                           '    raw = '
                                                           'package21_original_bytes(next(iter(EXISTING)),(ROOT / '
                                                           'next(iter(EXISTING))).read_bytes()); old_raw = '
                                                           'baseline_bytes(next(iter(EXISTING)))\n'),
                                                          (908,
                                                           909,
                                                           '        assert (ROOT / path).read_bytes() == '
                                                           'baseline_bytes(path)\n',
                                                           '        assert package21_original_bytes(path,(ROOT / '
                                                           'path).read_bytes()) == baseline_bytes(path)\n')],
 'tools/validation/diplomacy_package_18/test_source.py': [(25,
                                                           25,
                                                           '',
                                                           'from diplomacy_package_21.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE21_NEW, '
                                                           'package21_original_bytes, '
                                                           'package21_historical_existing,\n'
                                                           '    package21_original_validator_bytes, '
                                                           'historical_actions as package21_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package21_owned,\n'
                                                           ')\n'
                                                           'check_later_package21_owned()\n'),
                                                          (762,
                                                           764,
                                                           '    changed -= (package19_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE19_NEW | '
                                                           '(package20_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE20_NEW\n'
                                                           '    untracked -= LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW\n',
                                                           '    changed -= (package19_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE19_NEW | '
                                                           '(package20_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW\n'
                                                           '    untracked -= LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW\n'),
                                                          (914,
                                                           915,
                                                           '        assert (ROOT / path).read_bytes() == '
                                                           'baseline_bytes(path)\n',
                                                           '        assert package21_original_bytes(path,(ROOT / '
                                                           'path).read_bytes()) == baseline_bytes(path)\n')],
 'tools/validation/diplomacy_package_19/test_source.py': [(19,
                                                           19,
                                                           '',
                                                           'from diplomacy_package_21.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE21_NEW, '
                                                           'package21_original_bytes, '
                                                           'package21_historical_existing,\n'
                                                           '    package21_original_validator_bytes, '
                                                           'historical_actions as package21_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package21_owned,\n'
                                                           ')\n'
                                                           'check_later_package21_owned()\n'),
                                                          (867,
                                                           869,
                                                           '    changed -= (package20_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE20_NEW\n'
                                                           '    untracked -= LATER_PACKAGE20_NEW\n',
                                                           '    changed -= (package20_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW\n'
                                                           '    untracked -= LATER_PACKAGE20_NEW | '
                                                           'LATER_PACKAGE21_NEW\n')],
 'tools/validation/diplomacy_package_20/test_source.py': [(11,
                                                           11,
                                                           '',
                                                           'import sys as package21_sys\n'
                                                           "package21_sys.path.insert(0,str(ROOT/'tools/validation'))\n"
                                                           'from diplomacy_package_21.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE21_NEW, '
                                                           'package21_original_bytes, '
                                                           'package21_historical_existing,\n'
                                                           '    package21_original_validator_bytes, '
                                                           'historical_actions as package21_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package21_owned,\n'
                                                           ')\n'
                                                           'check_later_package21_owned()\n'),
                                                          (104,
                                                           104,
                                                           '',
                                                           '    actual = package21_original_bytes(path,actual)\n'),
                                                          (137,
                                                           137,
                                                           '',
                                                           '    actions = package21_historical_actions(actions)\n'),
                                                          (944,
                                                           944,
                                                           '',
                                                           '    actual = '
                                                           'package21_original_validator_bytes(path,actual)\n'),
                                                          (974,
                                                           974,
                                                           '',
                                                           '    changed -= (package21_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE21_NEW\n'
                                                           '    untracked -= LATER_PACKAGE21_NEW\n'),
                                                          (1119,
                                                           1119,
                                                           '',
                                                           '    current_ids = '
                                                           'package21_historical_actions(current_ids)\n'),
                                                          (1125,
                                                           1126,
                                                           '        assert (ROOT/path).read_bytes() == '
                                                           'baseline_bytes(path),path\n',
                                                           '        assert '
                                                           'package21_original_bytes(path,(ROOT/path).read_bytes()) '
                                                           '== baseline_bytes(path),path\n'),
                                                          (1161,
                                                           1162,
                                                           '    for path in untouched: assert '
                                                           '(ROOT/path).read_bytes() == baseline_bytes(path),path\n',
                                                           '    for path in untouched: assert '
                                                           'package21_original_validator_bytes(path,(ROOT/path).read_bytes()) '
                                                           '== baseline_bytes(path),path\n')]}


def package21_original_validator_bytes(path, actual):
    actual = package22_original_validator_bytes(path,actual)
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
    groups=Counter();boundary_groups=set()
    def passed(group): groups[group]+=1
    check_owned_existing()
    passed('only_five_inherited_options_one_global_broadcast_and_31_named_locale_lines_change')
    original=baseline_bytes('events/00_Influence_events.txt');raw=(ROOT/'events/00_Influence_events.txt').read_bytes()
    effects={key:body for key,op,body in ast((ROOT/FX).read_bytes())}
    triggers={key:body for key,op,body in ast((ROOT/TR).read_bytes())}
    events={one(body,'id'):body for key,op,body in ast((ROOT/EVENTS).read_bytes()) if key=='country_event'}
    trees=('common/scripted_effects','common/scripted_triggers','common/scripted_diplomatic_actions','common/on_actions','common/ideas','events','localisation')
    changed=set(subprocess.check_output(['git','diff','--name-only',BASELINE,'--',*trees],cwd=ROOT).decode().splitlines())
    untracked=set(subprocess.check_output(['git','ls-files','--others','--exclude-standard','--',*trees],cwd=ROOT).decode().splitlines())
    changed -= (package22_historical_existing(BASELINE) - EXISTING) | LATER_PACKAGE22_NEW
    untracked -= LATER_PACKAGE22_NEW
    assert changed-NEW==EXISTING and (changed|untracked)-EXISTING==NEW,(changed,untracked)
    passed('exact_eight_existing_and_eight_new_gameplay_paths')
    for path in NEW:
        data=package22_original_bytes(path,(ROOT/path).read_bytes())
        assert data.startswith(b'\xef\xbb\xbf')==path.endswith('.yml')
        assert b'\r' not in data.replace(b'\r\n',b'') and b'\n' not in data.replace(b'\r\n',b'')
        passed('eight_new_files_preserve_declared_CRLF_and_locale_BOM')
    before=ast(option_raw(original,'influence.501','influence.501.c'))[0][2]
    choice=ast(option_raw(raw,'influence.501','influence.501.c'))[0][2]
    assert one(choice,'name')==one(before,'name') and one(choice,'log')==one(before,'log')
    assert not any(key=='ai_chance' for key,op,val in before+choice)
    assert one(choice,'eon_advisers_send_offer')=='yes' and any(key=='eon_advisers_selection_ready' for key,op,val in rows(one(choice,'trigger')))
    passed('existing_choice_keeps_ID_log_absent_original_AI_and_only_sends_guarded_unsigned_offer')
    for identity,name in CHOICES[1:]:
        body=ast(option_raw(raw,identity,name))[0][2]
        assert {key for key,op,val in body}<={'name','log','ai_chance','custom_effect_tooltip'}
        assert one(body,'name')==name
        if identity=='influence.502': assert field_raw(option_raw(raw,identity,name),'ai_chance')==field_raw(option_raw(original,identity,name),'ai_chance')
        passed('four_old_callbacks_are_inert_resource_personnel_unit_payment_acknowledgements')
    prefix='eon_advisers_'
    expected_effects={prefix+name for name in ('clear_pending','retire_pending_pair','send_offer','accept_offer','reject_offer','withdraw_offer','clear_incoming_record','clear_outgoing_record','clear_incoming','clear_outgoing','end_cooperation','cleanup_active','daily_update','annex_update','clear_annexed_country')}
    expected_triggers={prefix+name for name in ('policy_allowed','partner_identified','incoming_partner_identified','outgoing_partner_identified','pending_slot_ready','outgoing_slot_ready','incoming_slot_ready','funds_available','requirements_ready','selection_ready','response_pending','response_ready','incoming_pair_matches','outgoing_pair_matches','withdraw_available','end_cooperation_available')}
    assert set(effects)==expected_effects and set(triggers)==expected_triggers
    passed('exact_15_effect_and_16_trigger_API_definition_sets')
    definitions=Counter()
    for directory in ('common/scripted_effects','common/scripted_triggers'):
        for path in (ROOT/directory).glob('*.txt'):
            for block in blocks(path.read_bytes(),0):
                if block['key'] in expected_effects|expected_triggers:definitions[block['key']]+=1
    for key in expected_effects|expected_triggers:
        assert definitions[key]==1,key;passed('31_owned_helper_IDs_are_globally_unique')
    for path in (FX,TR,NA,HOOKS,EVENTS):
        for key,op,val in rows(ast(package22_original_bytes(path,(ROOT/path).read_bytes()))):
            if key in expected_effects|expected_triggers:
                if not isinstance(val,list):assert val in ('yes','no')
            elif key.startswith(prefix) and not isinstance(val,list) and val in ('yes','no'):
                raise AssertionError(('Undefined adviser helper call',key,path))
        passed('five_current_sources_parse_and_resolve_helper_calls')
    assert triggers[prefix+'funds_available']==[('check_variable','=',[('treasury','>=','1.5')]),('check_variable','=',[('treasury','<=','1000000')])]
    passed('full_original_1_5_donor_fee_and_known_treasury_cap_guards')
    old_idea=one(one(one(ast(baseline_bytes('common/ideas/Generic Tree_ideas.txt')),'ideas'),'country'),'grey_men_foreign_idea')
    new_ideas=one(one(ast((ROOT/IDEAS).read_bytes()),'ideas'),'country')
    assert len(new_ideas)==1 and new_ideas[0][0]==prefix+'mission_idea'
    new_idea=new_ideas[0][2]
    assert one(new_idea,'modifier')==one(old_idea,'modifier')
    assert one(new_idea,'modifier')==[('special_forces_training_time_factor','=','-0.02'),('max_planning','=','0.08'),('special_forces_cap','=','0.01')]
    assert not any(key=='on_remove' for key,op,val in new_idea)
    assert one(new_idea,'cancel')==[('AND','=',[('has_civil_war','=','no'),('has_war','=','no')])]
    passed('new_isolated_idea_keeps_three_original_bonuses_and_peace_cancel_without_unit_deletion_or_global_return')
    accept=effects[prefix+'accept_offer'];flattened=list(rows(accept))
    assert any(key==prefix+'response_pending' for key,op,val in flattened) and any(key==prefix+'response_ready' for key,op,val in flattened)
    clear_index=next(i for i,row in enumerate(flattened) if row[0]==prefix+'clear_pending')
    fee_index=next(i for i,row in enumerate(flattened) if row[0]=='modify_treasury_effect')
    assert clear_index<fee_index and [(key,val) for key,op,val in flattened if key=='modify_treasury_effect']==[('modify_treasury_effect','yes')]
    assert ('set_temp_variable','=',[('treasury_change','=','-1.5')]) in flattened
    assert all(clear_index<i for i,(key,op,val) in enumerate(flattened) if key in ('add_timed_idea','change_influence_percentage','change_the_military_opinion'))
    passed('fresh_owned_pair_consumed_before_single_provider_expense_idea_and_political_calls')
    macro=[row for row in flattened if row[0] in ('set_temp_variable','change_influence_percentage','change_the_military_opinion')]
    assert [('set_temp_variable','=',[('percent_change','=','4')]),('set_temp_variable','=',[('tag_index','=','FROM')]),('set_temp_variable','=',[('influence_target','=','ROOT')]),('change_influence_percentage','=','yes'),('set_temp_variable','=',[('temp_opinion','=','4')]),('change_the_military_opinion','=','yes')]==macro[-6:]
    old_accept=ast(option_raw(original,'influence.502','influence.502.a'))[0][2]
    assert all(row in list(rows(old_accept)) for row in macro[-6:])
    assert any(key=='set_country_flag' and val=='sent_grey_men_epochs' for key,op,val in flattened)
    passed('original_receiver_ROOT_provider_FROM_four_influence_and_provider_internal_military_opinion_frames_preserved')
    for name in ('send_offer','withdraw_offer','end_cooperation','cleanup_active','daily_update','annex_update','clear_annexed_country'):
        assert not any(key in ('modify_treasury_effect','change_influence_percentage','change_the_military_opinion','change_domestic_influence_percentage') for key,op,val in rows(effects[prefix+name]))
        passed('unsigned_operations_and_owned_cleanup_do_not_spend_refund_or_reaward')
    for path in (FX,TR,NA,HOOKS,EVENTS,IDEAS):
        nodes=ast(package22_original_bytes(path,(ROOT/path).read_bytes()))
        assert not any(key in ('add_manpower','add_equipment_to_stockpile','send_equipment','division_template','create_unit','delete_unit','delete_units','delete_unit_template_and_units','transfer_units_fraction','add_political_power','add_fuel','add_to_faction','declare_war_on') for key,op,val in rows(nodes))
        assert not any(key=='country_event' and isinstance(val,list) and str(one(val,'id')).startswith('influence.') for key,op,val in rows(nodes))
        passed('six_new_sources_have_no_native_personnel_stock_units_foreign_command_or_legacy_callbacks')
    rejection=effects[prefix+'reject_offer']
    assert any(key==prefix+'response_ready' for key,op,val in rows(rejection))
    assert ('set_temp_variable','=',[('percent_change','=','2')]) in list(rows(rejection))
    assert ('set_country_flag','=',[('flag','=','refused_military_aid'),('value','=','1'),('days','=','180')]) in list(rows(rejection))
    passed('current_ready_owned_rejection_keeps_original_domestic_two_and_180_day_receiver_marker')
    clear=effects[prefix+'clear_pending']
    assert {val for key,op,val in clear if key=='clr_country_flag'}=={prefix+name for name in ('pending','live','cancelled')}
    assert ('clear_variable','=',prefix+'partner') in clear
    passed('pending_cleanup_does_not_clear_paid_active_or_unowned_legacy_state')
    for direction in ('incoming','outgoing'):
        body=effects[prefix+'clear_'+direction]
        assert any(key=='has_country_flag' and val==prefix+direction+'_owned' for key,op,val in rows(body))
        assert any(key=='check_variable' and any(field==prefix+('outgoing' if direction=='incoming' else 'incoming')+'_partner' for field,op,val in fields) for key,op,fields in rows(body) if key=='check_variable')
        passed('two_active_cleanup_directions_check_other_party_reciprocal_owned_pair')
    for path in (FX,EVENTS):
        declarations=[val for key,op,val in rows(ast(package22_original_bytes(path,(ROOT/path).read_bytes()))) if key=='set_country_flag' and isinstance(val,list)]
        if path==FX:
            assert [('flag','=',prefix+'live'),('days','=','30'),('value','=','1')] in declarations
            for direction in ('incoming','outgoing'): assert [('flag','=',prefix+direction+'_live'),('days','=','60'),('value','=','1')] in declarations
        passed('owned_pending_30_day_and_bilateral_active_60_day_native_timer_declarations')
    assert set(events)=={'eon_advisers.'+str(i) for i in range(1,8)}
    passed('seven_new_response_and_status_event_IDs')
    event_ids=Counter()
    for path in (ROOT/'events').glob('*.txt'):
        data=path.read_bytes()
        for block in blocks(data,0):
            if block['key'] in ('country_event','news_event'):
                identity=re.search(rb'\bid\s*=\s*([A-Za-z0-9_.]+)',data[block['start']:block['end']]);assert identity,path
                event_ids[identity[1].decode()]+=1
    for identity in events:
        assert event_ids[identity]==1;passed('seven_new_event_IDs_globally_unique')
    for name,factor in (('a','100'),('b','10')):
        option=next(val for key,op,val in events['eon_advisers.1'] if key=='option' and one(val,'name')=='eon_advisers.1.'+name)
        assert one(one(option,'ai_chance'),'base')==factor
        passed('accept_100_decline_10_weights_keep_invalid_current_offer_dismissible_by_AI')
    hooks=one(ast((ROOT/HOOKS).read_bytes()),'on_actions')
    assert {key for key,op,val in hooks}=={'on_daily','on_annex','on_subject_annexed'}
    for key,op,val in hooks:
        assert not any(key in ('create_unit','delete_unit','add_manpower','modify_treasury_effect') for key,op,val in rows(val))
        passed('three_cleanup_hooks_have_no_resources_spawn_or_refund')
    actions=one(ast((ROOT/NA).read_bytes()),'scripted_diplomatic_actions');assert {key for key,op,val in actions}==NEW_ACTION_IDS
    for identity,op,body in actions:
        assert one(body,'cost')=='0' and one(body,'requires_acceptance')=='no'
        helper=prefix+('withdraw_available' if identity.endswith('withdraw_offer') else 'end_cooperation_available')
        for section in ('allowed','visible','selectable','can_be_sent'):
            expected=[('ROOT','=',[('is_ai','=','no')])] if section=='allowed' else [(helper,'=','yes')]
            assert one(body,section)==expected;passed('eight_free_native_action_admission_blocks_use_human_and_exact_owned_pair_guards')
        assert one(one(body,'complete_effect'),identity)=='yes'
        passed('two_free_native_actions_only_withdraw_unsigned_or_end_owned_service')
    old_action_ids=[];current_ids=[]
    for path in subprocess.check_output(['git','ls-tree','-r','--name-only',BASELINE,'--','common/scripted_diplomatic_actions'],cwd=ROOT).decode().splitlines():
        for key,op,val in ast(baseline_bytes(path)):
            if key=='scripted_diplomatic_actions':old_action_ids.extend(name for name,op,body in val)
    for path in (ROOT/'common/scripted_diplomatic_actions').glob('*.txt'):
        for key,op,val in ast(path.read_bytes()):
            if key=='scripted_diplomatic_actions':current_ids.extend(name for name,op,body in val)
    current_ids=package22_historical_actions(current_ids)
    assert len(old_action_ids)==len(set(old_action_ids))==72 and len(current_ids)==len(set(current_ids))==74
    passed('72_prior_native_actions_and_two_unique_owned_adviser_actions')
    preserved=('events/00_War_events.txt','common/scripted_guis/influence_scripted_gui.txt','common/scripted_effects/00_influence_scripted_effects.txt','common/scripted_effects/00_budget_effects.txt','common/units/MD_land_units.txt')
    old_game=subprocess.check_output(['git','ls-tree','-r','--name-only',BASELINE,'--','common','events','localisation'],cwd=ROOT).decode().splitlines()
    preserved+=tuple(sorted(path for path in old_game if any(stem in path for stem in ('eon_services_','eon_foreign_cash_','eon_foreign_equipment_','eon_defence_formation_'))))
    for path in preserved:
        assert package22_original_bytes(path,(ROOT/path).read_bytes())==baseline_bytes(path),path
        passed('prior_entry_policy_budget_macro_domestic_reserves_and_four_support_channels_whole_raw_exact')
    locales={}
    for language in ('english','russian'):
        data=(ROOT/f'localisation/{language}/eon_advisers_l_{language}.yml').read_text(encoding='utf-8-sig')
        locales[language]={match[1]:match[2] for match in re.finditer(r'^\s*([A-Za-z0-9_.]+):[0-9]*\s*"(.*)"\s*$',data,re.M)}
    assert locales['english'].keys()==locales['russian'].keys();passed('bilingual_localisation_key_sets_exactly_match')
    for path,count in AID_TOOLTIP_COUNTS.items():
        lines=[line.decode('utf-8-sig') for line in package22_original_bytes(path,(ROOT/path).read_bytes()).splitlines() if re.match(rb'\s*aid_military_button_TT:',line)]
        assert len(lines)==count
        assert all(line != before.decode('utf-8-sig') for line in lines for before in baseline_bytes(path).splitlines() if re.match(rb'\s*aid_military_button_TT:',before))
        assert all('influence.501' not in line for line in lines)
        assert all(('advis' in line.lower() and 'brigade' not in line.lower()) if '/english/' in path else (any(word in line.lower() for word in ('консульт','советник')) and 'бригад' not in line.lower()) for line in lines)
        passed('three_effective_existing_aid_menu_tooltip_rows_have_updated_product_copy_with_exact_duplicate_counts')
    for path in (FX,NA,EVENTS,IDEAS):
        for key,op,val in rows(ast(package22_original_bytes(path,(ROOT/path).read_bytes()))):
            if key in ('custom_effect_tooltip','tooltip','send_description','title','desc','name') and isinstance(val,str) and (val.startswith('eon_advisers.') or val.startswith(prefix)):
                assert val in locales['english'],val
        passed('four_current_action_event_idea_tooltip_locale_reference_sets_resolve')
    for path in EXISTING:
        try:package21_original_bytes(path,package22_original_bytes(path,(ROOT/path).read_bytes())+b'# unowned memory mutation\n')
        except AssertionError:pass
        else:raise AssertionError(('Unowned source mutation accepted',path))
        passed('memory_only_game_source_outside_five_choices_broadcast_or_named_locale_lines_rejected');boundary_groups.add('memory_only_game_source_outside_five_choices_broadcast_or_named_locale_lines_rejected')
    assert set(HISTORICAL_SOURCE_EDITS)=={f'tools/validation/diplomacy_package_{i:02}/test_source.py' for i in range(2,21)}
    for path in sorted(HISTORICAL_SOURCE_EDITS):
        actual=package22_original_bytes(path,(ROOT/path).read_bytes());original=baseline_bytes(path)
        assert package21_original_validator_bytes(path,actual)==original
        counters=lambda data:[line for line in data.splitlines() if b'groups[' in line and b'+=' in line or b'passed(' in line]
        assert counters(actual)==counters(original);passed('19_literal_whole_source_journals_and_all_original_counter_lines_retained')
        try:package21_original_validator_bytes(path,actual+b'# unowned memory mutation\n')
        except AssertionError:pass
        else:raise AssertionError(('Unowned historical mutation accepted',path))
        passed('memory_only_whole_historical_source_mutation_rejected');boundary_groups.add('memory_only_whole_historical_source_mutation_rejected')
    public_paths=subprocess.check_output(['git','ls-tree','-r','--name-only',BASELINE,'--','tools/validation'],cwd=ROOT).decode().splitlines()
    untouched=[path for path in public_paths if path not in HISTORICAL_SOURCE_EDITS]
    for path in untouched:assert package22_original_bytes(path,(ROOT/path).read_bytes())==baseline_bytes(path),path
    behavior=[path for path in untouched if path.endswith('.py') and Path(path).name!='test_source.py']
    assert len(untouched)==71 and len(behavior)==51
    passed('51_prior_behavior_helper_runners_and71_other_public_files_whole_raw_exact')
    installed=Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV')
    effect_docs=(installed/'documentation/effects_documentation.md').read_text(encoding='utf-8-sig')
    for name in ('add_timed_idea','remove_ideas','set_country_flag','country_event'):
        assert '\n## '+name+'\n' in effect_docs;passed('four_native_timer_idea_and_event_declarations_verified_without_runtime_claim')
    hashes={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in SOURCE_PATHS}
    boundaries=sum(groups[key] for key in boundary_groups)
    print(json.dumps({'all_passed':True,'baseline':BASELINE,'source_cases':sum(groups.values()),'source_API_cases':sum(groups.values())-boundaries,
        'source_byte_adapter_boundary_cases':boundaries,'groups':dict(groups),'source_sha256':hashes,
        'historical_source_adapters':len(HISTORICAL_SOURCE_EDITS),'prior_behavior_helper_runner_raw_byte_files':len(behavior),
        'prior_other_public_raw_byte_files':len(untouched),'bilingual_locale_keys':len(locales['english']),
        'native_runtime':False,'proof_scope':'exact donor-funded advisory lifecycle and literal byte retention; not native political results or playable campaign'},indent=2))

if __name__ == '__main__': main()
