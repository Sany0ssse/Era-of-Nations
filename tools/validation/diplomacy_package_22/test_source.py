"""Exact initial support-request router and explicit historical caller views; not native HOI4 runtime."""
from pathlib import Path
from functools import lru_cache
from collections import Counter
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '0747ce626b79bc7796d6fbb61be9cbf8a6076de0'
EXISTING = {'events/00_War_events.txt','common/scripted_diplomatic_actions/MDDC_AB_ask_foreign_support.txt',
    'localisation/english/MD_decisions_l_english.yml','localisation/russian/MD_decisions_l_russian.yml'}
CHOICES = tuple(('AB_mobilization.4','AB_mobilization.4.'+suffix) for suffix in ('a','b','c','d'))
CURRENT_MENU_OPTION_SHA256 = {'AB_mobilization.4.a': '12945cd3d459e02e5a274dcc143019da05b92125ad17fb005fd6391eb1d25597',
 'AB_mobilization.4.b': 'a6cf3aa683c94fbf860de374672e706c6b69c86ddd22c1ac263ce720f183ac6f',
 'AB_mobilization.4.c': '01b28d0517209d1836fe932debea3db632eef42615e0f1bd9c6eb9492d46bfb3',
 'AB_mobilization.4.d': '21a37994984dd6312f53695fffbc99f589a6beecffa921382b4e54435d5e6e17'}
LEGACY_LOCALE_KEYS = {'AB_ask_foreign_support','AB_ask_foreign_support_d','AB_ASK_FOREIGN_SUPPORT_TOOLTIP',
    'AB_mobilization.4.t','AB_mobilization.4.desc','AB_mobilization.4.d'}
FX='common/scripted_effects/eon_support_request_effects.txt'
TR='common/scripted_triggers/eon_support_request_triggers.txt'
NA='common/scripted_diplomatic_actions/eon_support_request_actions.txt'
HOOKS='common/on_actions/eon_support_request_on_actions.txt'
EVENTS='events/eon_support_request_events.txt'
NEW={FX,TR,NA,HOOKS,EVENTS}|{f'localisation/{language}/eon_support_request_l_{language}.yml' for language in ('english','russian')}
SOURCE_PATHS=sorted(EXISTING|NEW)
NEW_ACTION_IDS={'eon_support_request_withdraw_request'}
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

def package22_original_bytes(path,actual):
    """Exact inverse of four owned menu choices, two action fields/new guard and twelve locale rows."""
    if path not in EXISTING:return actual
    original=baseline_bytes(path);format_preserved(original,actual,path)
    if actual==original:return original
    restored=actual
    if path=='events/00_War_events.txt':
        assert event_blocks(original).keys()==event_blocks(actual).keys()
        for identity,name in reversed(CHOICES):
            before=option_block(original,identity,name);after=option_block(restored,identity,name)
            restored=restored[:after['start']]+original[before['start']:before['end']]+restored[after['end']:]
    elif path.endswith('MDDC_AB_ask_foreign_support.txt'):
        for key in ('selectable','complete_effect'):
            before=named_block(original,key);after=named_block(restored,key)
            restored=restored[:after['start']]+original[before['start']:before['end']]+restored[after['end']:]
        inserted=b'\n\tcan_be_sent = { eon_support_request_action_ready = yes }\n'
        assert restored.count(inserted)==1,'Undeclared native guard insertion'
        restored=restored.replace(inserted,b'',1)
    else:
        old_lines=original.splitlines(keepends=True);new_lines=actual.splitlines(keepends=True)
        assert len(old_lines)==len(new_lines),(path,'Locale row count changed')
        seen=set();parts=[]
        for before,after in zip(old_lines,new_lines):
            match=re.match(rb'\s*([A-Za-z0-9_.]+):',before);key=match[1].decode() if match else None
            if key in LEGACY_LOCALE_KEYS:
                assert re.match(rb'\s*([A-Za-z0-9_.]+):',after)[1].decode()==key
                assert key not in seen,(path,key,'Duplicate permitted row')
                seen.add(key);parts.append(before)
            else:parts.append(after)
        assert seen==LEGACY_LOCALE_KEYS,(path,seen)
        restored=b''.join(parts)
    assert restored==original,('Unowned support request bytes changed',path)
    return original

def historical_caller_view(actual):
    path='events/00_War_events.txt'
    package22_original_bytes(path,actual)
    for identity,name in CHOICES:
        assert hashlib.sha256(option_raw(actual,identity,name)).hexdigest()==CURRENT_MENU_OPTION_SHA256[name],('Current menu option drift',name)
    original=baseline_bytes(path);restored=actual
    manifest={}
    for identity,name in reversed(CHOICES[:3]):
        before=option_block(original,identity,name);after=option_block(restored,identity,name)
        legacy=original[before['start']:before['end']]
        manifest[name]=hashlib.sha256(legacy).hexdigest()
        restored=restored[:after['start']]+legacy+restored[after['end']:]
    return restored,{'baseline':BASELINE,'projected_options_sha256':dict(sorted(manifest.items())),
        'actual_current_War_sha256':hashlib.sha256(actual).hexdigest(),
        'historical_caller_War_view_sha256':hashlib.sha256(restored).hexdigest(),
        'prior_scope':'unchanged_children_with_historical_AB4_caller_view'}

@lru_cache(maxsize=32)
def package22_historical_existing(baseline):
    return frozenset(subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', baseline, '--', *sorted(EXISTING)], cwd=ROOT).decode().splitlines())

def check_owned_existing():
    for path in sorted(EXISTING): package22_original_bytes(path, (ROOT / path).read_bytes())

def historical_actions(actions):
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
                                                           "'eon_defence_formation_withdraw_offer', "
                                                           "'eon_advisers_withdraw_offer', "
                                                           "'eon_advisers_end_cooperation')))\n",
                                                           '                                               '
                                                           "'eon_withdraw_antiterror_proposal', "
                                                           "'eon_ammo_withdraw_offer', "
                                                           "'eon_services_withdraw_offer', "
                                                           "'eon_services_end_logistics', 'eon_services_end_recon', "
                                                           "'eon_foreign_cash_withdraw_offer', "
                                                           "'eon_foreign_equipment_withdraw_offer', "
                                                           "'eon_defence_formation_withdraw_offer', "
                                                           "'eon_advisers_withdraw_offer', "
                                                           "'eon_advisers_end_cooperation', "
                                                           "'eon_support_request_withdraw_request')))\n")],
 'tools/validation/diplomacy_package_03/test_source.py': [(89,
                                                           89,
                                                           '',
                                                           'from diplomacy_package_22.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE22_NEW, '
                                                           'package22_original_bytes, '
                                                           'package22_historical_existing,\n'
                                                           '    package22_original_validator_bytes, '
                                                           'historical_actions as package22_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package22_owned,\n'
                                                           ')\n'
                                                           'check_later_package22_owned()\n'),
                                                          (271,
                                                           272,
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
                                                           'LATER_PACKAGE21_NEW]\n',
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
                                                           'LATER_PACKAGE21_NEW | '
                                                           'package22_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE22_NEW]\n'),
                                                          (275,
                                                           276,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n')],
 'tools/validation/diplomacy_package_04/test_source.py': [(105,
                                                           105,
                                                           '',
                                                           'from diplomacy_package_22.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE22_NEW, '
                                                           'package22_original_bytes, '
                                                           'package22_historical_existing,\n'
                                                           '    package22_original_validator_bytes, '
                                                           'historical_actions as package22_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package22_owned,\n'
                                                           ')\n'
                                                           'check_later_package22_owned()\n'),
                                                          (368,
                                                           369,
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
                                                           'LATER_PACKAGE21_NEW]\n',
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
                                                           'LATER_PACKAGE21_NEW | '
                                                           'package22_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE22_NEW]\n'),
                                                          (370,
                                                           371,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n')],
 'tools/validation/diplomacy_package_05/test_source.py': [(100,
                                                           100,
                                                           '',
                                                           'from diplomacy_package_22.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE22_NEW, '
                                                           'package22_original_bytes, '
                                                           'package22_historical_existing,\n'
                                                           '    package22_original_validator_bytes, '
                                                           'historical_actions as package22_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package22_owned,\n'
                                                           ')\n'
                                                           'check_later_package22_owned()\n'),
                                                          (310,
                                                           311,
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
                                                           'package21_required_old_paths) | LATER_PACKAGE21_NEW]\n',
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
                                                           'package21_required_old_paths) | LATER_PACKAGE21_NEW | '
                                                           '(package22_historical_existing(BASELINE) - '
                                                           'package21_required_old_paths) | LATER_PACKAGE22_NEW]\n'),
                                                          (312,
                                                           313,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n')],
 'tools/validation/diplomacy_package_06/test_source.py': [(102,
                                                           102,
                                                           '',
                                                           'from diplomacy_package_22.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE22_NEW, '
                                                           'package22_original_bytes, '
                                                           'package22_historical_existing,\n'
                                                           '    package22_original_validator_bytes, '
                                                           'historical_actions as package22_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package22_owned,\n'
                                                           ')\n'
                                                           'check_later_package22_owned()\n'),
                                                          (484,
                                                           485,
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
                                                           'package21_required_old_paths) | LATER_PACKAGE21_NEW]\n',
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
                                                           'package21_required_old_paths) | LATER_PACKAGE21_NEW | '
                                                           '(package22_historical_existing(BASELINE) - '
                                                           'package21_required_old_paths) | LATER_PACKAGE22_NEW]\n'),
                                                          (486,
                                                           487,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n')],
 'tools/validation/diplomacy_package_07/test_source.py': [(100,
                                                           100,
                                                           '',
                                                           'from diplomacy_package_22.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE22_NEW, '
                                                           'package22_original_bytes, '
                                                           'package22_historical_existing,\n'
                                                           '    package22_original_validator_bytes, '
                                                           'historical_actions as package22_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package22_owned,\n'
                                                           ')\n'
                                                           'check_later_package22_owned()\n'),
                                                          (162,
                                                           163,
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
                                                           'LATER_PACKAGE21_NEW]\n',
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
                                                           'LATER_PACKAGE21_NEW | '
                                                           'package22_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE22_NEW]\n'),
                                                          (164,
                                                           165,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n')],
 'tools/validation/diplomacy_package_08/test_source.py': [(100,
                                                           100,
                                                           '',
                                                           'from diplomacy_package_22.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE22_NEW, '
                                                           'package22_original_bytes, '
                                                           'package22_historical_existing,\n'
                                                           '    package22_original_validator_bytes, '
                                                           'historical_actions as package22_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package22_owned,\n'
                                                           ')\n'
                                                           'check_later_package22_owned()\n'),
                                                          (159,
                                                           160,
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
                                                           'LATER_PACKAGE21_NEW]\n',
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
                                                           'LATER_PACKAGE21_NEW | '
                                                           'package22_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE22_NEW]\n'),
                                                          (161,
                                                           162,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n')],
 'tools/validation/diplomacy_package_09/test_source.py': [(88,
                                                           88,
                                                           '',
                                                           'from diplomacy_package_22.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE22_NEW, '
                                                           'package22_original_bytes, '
                                                           'package22_historical_existing,\n'
                                                           '    package22_original_validator_bytes, '
                                                           'historical_actions as package22_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package22_owned,\n'
                                                           ')\n'
                                                           'check_later_package22_owned()\n'),
                                                          (142,
                                                           143,
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
                                                           'LATER_PACKAGE21_NEW]\n',
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
                                                           'LATER_PACKAGE21_NEW | '
                                                           'package22_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE22_NEW]\n'),
                                                          (144,
                                                           145,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n')],
 'tools/validation/diplomacy_package_10/test_source.py': [(80,
                                                           80,
                                                           '',
                                                           'from diplomacy_package_22.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE22_NEW, '
                                                           'package22_original_bytes, '
                                                           'package22_historical_existing,\n'
                                                           '    package22_original_validator_bytes, '
                                                           'historical_actions as package22_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package22_owned,\n'
                                                           ')\n'
                                                           'check_later_package22_owned()\n'),
                                                          (222,
                                                           223,
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
                                                           'LATER_PACKAGE21_NEW]\n',
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
                                                           'LATER_PACKAGE21_NEW | '
                                                           'package22_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE22_NEW]\n'),
                                                          (224,
                                                           225,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n')],
 'tools/validation/diplomacy_package_11/test_source.py': [(73,
                                                           73,
                                                           '',
                                                           'from diplomacy_package_22.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE22_NEW, '
                                                           'package22_original_bytes, '
                                                           'package22_historical_existing,\n'
                                                           '    package22_original_validator_bytes, '
                                                           'historical_actions as package22_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package22_owned,\n'
                                                           ')\n'
                                                           'check_later_package22_owned()\n'),
                                                          (236,
                                                           238,
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
                                                           'LATER_PACKAGE21_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n'
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
                                                           'LATER_PACKAGE21_NEW | '
                                                           'package22_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE22_NEW]\n'),
                                                          (247,
                                                           248,
                                                           '            assert package12_original_bytes(path, '
                                                           'package16_original_bytes(path, (ROOT / '
                                                           "path).read_bytes())) == old, ('Old native action bytes "
                                                           "changed', path)\n",
                                                           '            assert package12_original_bytes(path, '
                                                           'package16_original_bytes(path, '
                                                           'package22_original_bytes(path,(ROOT / '
                                                           "path).read_bytes()))) == old, ('Old native action bytes "
                                                           "changed', path)\n")],
 'tools/validation/diplomacy_package_12/test_source.py': [(59,
                                                           59,
                                                           '',
                                                           'from diplomacy_package_22.test_source import (\r\n'
                                                           '    NEW as LATER_PACKAGE22_NEW, '
                                                           'package22_original_bytes, '
                                                           'package22_historical_existing,\r\n'
                                                           '    package22_original_validator_bytes, '
                                                           'historical_actions as package22_historical_actions,\r\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package22_owned,\r\n'
                                                           ')\r\n'
                                                           'check_later_package22_owned()\r\n'),
                                                          (206,
                                                           207,
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
                                                           'LATER_PACKAGE21_NEW]\r\n',
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
                                                           'LATER_PACKAGE21_NEW | '
                                                           'package22_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE22_NEW]\r\n'),
                                                          (208,
                                                           209,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\r\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\r\n'),
                                                          (246,
                                                           247,
                                                           '            assert '
                                                           "package12_original_bytes(path,actual)==before,('Unowned "
                                                           "native action bytes changed',path)\r\n",
                                                           '            assert '
                                                           "package12_original_bytes(path,package22_original_bytes(path,actual))==before,('Unowned "
                                                           "native action bytes changed',path)\r\n")],
 'tools/validation/diplomacy_package_13/test_source.py': [(59,
                                                           59,
                                                           '',
                                                           'from diplomacy_package_22.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE22_NEW, '
                                                           'package22_original_bytes, '
                                                           'package22_historical_existing,\n'
                                                           '    package22_original_validator_bytes, '
                                                           'historical_actions as package22_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package22_owned,\n'
                                                           ')\n'
                                                           'check_later_package22_owned()\n'),
                                                          (219,
                                                           220,
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
                                                           'LATER_PACKAGE21_NEW]\n',
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
                                                           'LATER_PACKAGE21_NEW | '
                                                           'package22_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE22_NEW]\n'),
                                                          (221,
                                                           222,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n'),
                                                          (259,
                                                           260,
                                                           '            assert '
                                                           "package13_original_bytes(path,actual)==before,('Unowned "
                                                           "native action bytes changed',path)\n",
                                                           '            assert '
                                                           "package13_original_bytes(path,package22_original_bytes(path,actual))==before,('Unowned "
                                                           "native action bytes changed',path)\n")],
 'tools/validation/diplomacy_package_14/test_source.py': [(55,
                                                           55,
                                                           '',
                                                           'from diplomacy_package_22.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE22_NEW, '
                                                           'package22_original_bytes, '
                                                           'package22_historical_existing,\n'
                                                           '    package22_original_validator_bytes, '
                                                           'historical_actions as package22_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package22_owned,\n'
                                                           ')\n'
                                                           'check_later_package22_owned()\n'),
                                                          (235,
                                                           236,
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
                                                           'LATER_PACKAGE21_NEW]\n',
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
                                                           'LATER_PACKAGE21_NEW | '
                                                           'package22_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE22_NEW]\n'),
                                                          (237,
                                                           238,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n'),
                                                          (243,
                                                           244,
                                                           '            '
                                                           'data=package15_original_bytes(path,package16_original_bytes(path,(ROOT/path).read_bytes()));assert '
                                                           "data==baseline_bytes(path),('Native "
                                                           "visibility_cost_consent_AI_weights_or_scope_modified',path)\n",
                                                           '            '
                                                           'data=package15_original_bytes(path,package16_original_bytes(path,package22_original_bytes(path,(ROOT/path).read_bytes())));assert '
                                                           "data==baseline_bytes(path),('Native "
                                                           "visibility_cost_consent_AI_weights_or_scope_modified',path)\n")],
 'tools/validation/diplomacy_package_15/test_source.py': [(47,
                                                           47,
                                                           '',
                                                           'from diplomacy_package_22.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE22_NEW, '
                                                           'package22_original_bytes, '
                                                           'package22_historical_existing,\n'
                                                           '    package22_original_validator_bytes, '
                                                           'historical_actions as package22_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package22_owned,\n'
                                                           ')\n'
                                                           'check_later_package22_owned()\n'),
                                                          (839,
                                                           841,
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
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW\n',
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
                                                           'LATER_PACKAGE21_NEW | '
                                                           'package22_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE22_NEW\n'
                                                           '    added -= LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW\n')],
 'tools/validation/diplomacy_package_16/test_source.py': [(47,
                                                           47,
                                                           '',
                                                           'from diplomacy_package_22.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE22_NEW, '
                                                           'package22_original_bytes, '
                                                           'package22_historical_existing,\n'
                                                           '    package22_original_validator_bytes, '
                                                           'historical_actions as package22_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package22_owned,\n'
                                                           ')\n'
                                                           'check_later_package22_owned()\n'),
                                                          (670,
                                                           672,
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
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW\n',
                                                           '    changed -= package17_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE17_NEW | '
                                                           'package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW | '
                                                           'package22_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE22_NEW\n'
                                                           '    untracked -= LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW\n')],
 'tools/validation/diplomacy_package_17/test_source.py': [(41,
                                                           41,
                                                           '',
                                                           'from diplomacy_package_22.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE22_NEW, '
                                                           'package22_original_bytes, '
                                                           'package22_historical_existing,\n'
                                                           '    package22_original_validator_bytes, '
                                                           'historical_actions as package22_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package22_owned,\n'
                                                           ')\n'
                                                           'check_later_package22_owned()\n'),
                                                          (763,
                                                           765,
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
                                                           'LATER_PACKAGE21_NEW\n',
                                                           '    changed -= package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW | '
                                                           '(package21_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE21_NEW | '
                                                           '(package22_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE22_NEW\n'
                                                           '    untracked -= LATER_PACKAGE18_NEW | '
                                                           'LATER_PACKAGE19_NEW | LATER_PACKAGE20_NEW | '
                                                           'LATER_PACKAGE21_NEW | LATER_PACKAGE22_NEW\n')],
 'tools/validation/diplomacy_package_18/test_source.py': [(31,
                                                           31,
                                                           '',
                                                           'from diplomacy_package_22.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE22_NEW, '
                                                           'package22_original_bytes, '
                                                           'package22_historical_existing,\n'
                                                           '    package22_original_validator_bytes, '
                                                           'historical_actions as package22_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package22_owned,\n'
                                                           ')\n'
                                                           'check_later_package22_owned()\n'),
                                                          (139,
                                                           140,
                                                           '    for path in sorted(EXISTING): '
                                                           'package18_original_bytes(path, (ROOT / '
                                                           'path).read_bytes())\n',
                                                           '    for path in sorted(EXISTING): '
                                                           'package18_original_bytes(path, '
                                                           'package22_original_bytes(path,(ROOT / '
                                                           'path).read_bytes()))\n'),
                                                          (755,
                                                           756,
                                                           '    raw = '
                                                           "package19_original_bytes('events/00_War_events.txt', "
                                                           "(ROOT / 'events/00_War_events.txt').read_bytes()); "
                                                           "original = baseline_bytes('events/00_War_events.txt')\n",
                                                           '    raw = '
                                                           "package19_original_bytes('events/00_War_events.txt', "
                                                           "package22_original_bytes('events/00_War_events.txt',(ROOT "
                                                           "/ 'events/00_War_events.txt').read_bytes())); original = "
                                                           "baseline_bytes('events/00_War_events.txt')\n"),
                                                          (759,
                                                           760,
                                                           '        data = (ROOT / path).read_bytes(); '
                                                           "data.decode('utf-8-sig')\n",
                                                           '        data = package22_original_bytes(path,(ROOT / '
                                                           "path).read_bytes()); data.decode('utf-8-sig')\n"),
                                                          (768,
                                                           770,
                                                           '    changed -= (package19_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE19_NEW | '
                                                           '(package20_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW\n'
                                                           '    untracked -= LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW\n',
                                                           '    changed -= (package19_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE19_NEW | '
                                                           '(package20_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW | '
                                                           '(package22_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE22_NEW\n'
                                                           '    untracked -= LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW\n'),
                                                          (805,
                                                           806,
                                                           '        for key, op, value in rows(ast((ROOT / '
                                                           'path).read_bytes())):\n',
                                                           '        for key, op, value in '
                                                           'rows(ast(package22_original_bytes(path,(ROOT / '
                                                           'path).read_bytes()))):\n'),
                                                          (906,
                                                           907,
                                                           '        nodes = list(rows(ast((ROOT / '
                                                           'path).read_bytes())))\n',
                                                           '        nodes = '
                                                           'list(rows(ast(package22_original_bytes(path,(ROOT / '
                                                           'path).read_bytes()))))\n'),
                                                          (920,
                                                           921,
                                                           '        assert package21_original_bytes(path,(ROOT / '
                                                           'path).read_bytes()) == baseline_bytes(path)\n',
                                                           '        assert '
                                                           'package21_original_bytes(path,package22_original_bytes(path,(ROOT '
                                                           '/ path).read_bytes())) == baseline_bytes(path)\n'),
                                                          (933,
                                                           934,
                                                           '        for key, op, val in rows(ast((ROOT / '
                                                           'path).read_bytes())):\n',
                                                           '        for key, op, val in '
                                                           'rows(ast(package22_original_bytes(path,(ROOT / '
                                                           'path).read_bytes()))):\n'),
                                                          (943,
                                                           944,
                                                           '        actual = (ROOT / path).read_bytes()\n',
                                                           '        actual = package22_original_bytes(path,(ROOT / '
                                                           'path).read_bytes())\n'),
                                                          (955,
                                                           956,
                                                           '    for path in unchanged: assert '
                                                           'package19_original_validator_bytes(path, (ROOT / '
                                                           "path).read_bytes()) == baseline_bytes(path), ('Prior "
                                                           'public behavior/helper/runner or unrelated source '
                                                           "changed', path)\n",
                                                           '    for path in unchanged: assert '
                                                           'package19_original_validator_bytes(path, '
                                                           'package22_original_bytes(path,(ROOT / '
                                                           "path).read_bytes())) == baseline_bytes(path), ('Prior "
                                                           'public behavior/helper/runner or unrelated source '
                                                           "changed', path)\n")],
 'tools/validation/diplomacy_package_19/test_source.py': [(25,
                                                           25,
                                                           '',
                                                           'from diplomacy_package_22.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE22_NEW, '
                                                           'package22_original_bytes, '
                                                           'package22_historical_existing,\n'
                                                           '    package22_original_validator_bytes, '
                                                           'historical_actions as package22_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package22_owned,\n'
                                                           ')\n'
                                                           'check_later_package22_owned()\n'),
                                                          (134,
                                                           135,
                                                           '    for path in sorted(EXISTING): '
                                                           'package19_original_bytes(path, (ROOT / '
                                                           'path).read_bytes())\n',
                                                           '    for path in sorted(EXISTING): '
                                                           'package19_original_bytes(path, '
                                                           'package22_original_bytes(path,(ROOT / '
                                                           'path).read_bytes()))\n'),
                                                          (860,
                                                           861,
                                                           '    raw = '
                                                           "package20_original_bytes('events/00_War_events.txt', "
                                                           "(ROOT / 'events/00_War_events.txt').read_bytes()); "
                                                           "original = baseline_bytes('events/00_War_events.txt')\n",
                                                           '    raw = '
                                                           "package20_original_bytes('events/00_War_events.txt', "
                                                           "package22_original_bytes('events/00_War_events.txt',(ROOT "
                                                           "/ 'events/00_War_events.txt').read_bytes())); original = "
                                                           "baseline_bytes('events/00_War_events.txt')\n"),
                                                          (864,
                                                           865,
                                                           '        data = (ROOT / path).read_bytes(); '
                                                           "data.decode('utf-8-sig')\n",
                                                           '        data = package22_original_bytes(path,(ROOT / '
                                                           "path).read_bytes()); data.decode('utf-8-sig')\n"),
                                                          (873,
                                                           875,
                                                           '    changed -= (package20_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW\n'
                                                           '    untracked -= LATER_PACKAGE20_NEW | '
                                                           'LATER_PACKAGE21_NEW\n',
                                                           '    changed -= (package20_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW | '
                                                           '(package22_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE22_NEW\n'
                                                           '    untracked -= LATER_PACKAGE20_NEW | '
                                                           'LATER_PACKAGE21_NEW | LATER_PACKAGE22_NEW\n'),
                                                          (916,
                                                           917,
                                                           '        for key, op, value in rows(ast((ROOT / '
                                                           'path).read_bytes())):\n',
                                                           '        for key, op, value in '
                                                           'rows(ast(package22_original_bytes(path,(ROOT / '
                                                           'path).read_bytes()))):\n'),
                                                          (1013,
                                                           1014,
                                                           '        for key, op, val in rows(ast((ROOT / '
                                                           'path).read_bytes())):\n',
                                                           '        for key, op, val in '
                                                           'rows(ast(package22_original_bytes(path,(ROOT / '
                                                           'path).read_bytes()))):\n'),
                                                          (1018,
                                                           1019,
                                                           '        nodes = list(rows(ast((ROOT / '
                                                           'path).read_bytes())))\n',
                                                           '        nodes = '
                                                           'list(rows(ast(package22_original_bytes(path,(ROOT / '
                                                           'path).read_bytes()))))\n'),
                                                          (1035,
                                                           1036,
                                                           '        assert package20_original_bytes(path, (ROOT / '
                                                           'path).read_bytes()) == baseline_bytes(path)\n',
                                                           '        assert package20_original_bytes(path, '
                                                           'package22_original_bytes(path,(ROOT / '
                                                           'path).read_bytes())) == baseline_bytes(path)\n'),
                                                          (1088,
                                                           1089,
                                                           '        actual = (ROOT / path).read_bytes()\n',
                                                           '        actual = package22_original_bytes(path,(ROOT / '
                                                           'path).read_bytes())\n'),
                                                          (1100,
                                                           1101,
                                                           '    for path in unchanged: assert '
                                                           'package20_original_validator_bytes(path, (ROOT / '
                                                           "path).read_bytes()) == baseline_bytes(path), ('Prior "
                                                           'public behavior/helper/runner or unrelated source '
                                                           "changed', path)\n",
                                                           '    for path in unchanged: assert '
                                                           'package20_original_validator_bytes(path, '
                                                           'package22_original_bytes(path,(ROOT / '
                                                           "path).read_bytes())) == baseline_bytes(path), ('Prior "
                                                           'public behavior/helper/runner or unrelated source '
                                                           "changed', path)\n")],
 'tools/validation/diplomacy_package_20/test_source.py': [(19,
                                                           19,
                                                           '',
                                                           'from diplomacy_package_22.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE22_NEW, '
                                                           'package22_original_bytes, '
                                                           'package22_historical_existing,\n'
                                                           '    package22_original_validator_bytes, '
                                                           'historical_actions as package22_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package22_owned,\n'
                                                           ')\n'
                                                           'check_later_package22_owned()\n'),
                                                          (112,
                                                           112,
                                                           '',
                                                           '    if path in EXISTING and actual == '
                                                           'baseline_bytes(path): return actual\n'),
                                                          (143,
                                                           144,
                                                           '    for path in sorted(EXISTING): '
                                                           'package20_original_bytes(path, (ROOT / '
                                                           'path).read_bytes())\n',
                                                           '    for path in sorted(EXISTING): '
                                                           'package20_original_bytes(path, '
                                                           'package22_original_bytes(path,(ROOT / '
                                                           'path).read_bytes()))\n'),
                                                          (978,
                                                           979,
                                                           '    raw = (ROOT / '
                                                           "'events/00_War_events.txt').read_bytes(); original = "
                                                           "baseline_bytes('events/00_War_events.txt')\n",
                                                           '    raw = '
                                                           "package22_original_bytes('events/00_War_events.txt',(ROOT "
                                                           "/ 'events/00_War_events.txt').read_bytes()); original = "
                                                           "baseline_bytes('events/00_War_events.txt')\n"),
                                                          (985,
                                                           987,
                                                           '    changed -= (package21_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE21_NEW\n'
                                                           '    untracked -= LATER_PACKAGE21_NEW\n',
                                                           '    changed -= (package21_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE21_NEW | '
                                                           '(package22_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE22_NEW\n'
                                                           '    untracked -= LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW\n'),
                                                          (990,
                                                           991,
                                                           '        data = (ROOT / path).read_bytes()\n',
                                                           '        data = package22_original_bytes(path,(ROOT / '
                                                           'path).read_bytes())\n'),
                                                          (1020,
                                                           1021,
                                                           '        for key,op,val in '
                                                           'rows(ast((ROOT/path).read_bytes())):\n',
                                                           '        for key,op,val in '
                                                           'rows(ast(package22_original_bytes(path,(ROOT/path).read_bytes()))):\n'),
                                                          (1083,
                                                           1084,
                                                           '        nodes = ast((ROOT/path).read_bytes())\n',
                                                           '        nodes = '
                                                           'ast(package22_original_bytes(path,(ROOT/path).read_bytes()))\n'),
                                                          (1139,
                                                           1140,
                                                           '        assert '
                                                           'package21_original_bytes(path,(ROOT/path).read_bytes()) '
                                                           '== baseline_bytes(path),path\n',
                                                           '        assert '
                                                           'package21_original_bytes(path,package22_original_bytes(path,(ROOT/path).read_bytes())) '
                                                           '== baseline_bytes(path),path\n'),
                                                          (1141,
                                                           1142,
                                                           '    entry = '
                                                           "ast((ROOT/'common/scripted_diplomatic_actions/MDDC_AB_ask_foreign_support.txt').read_bytes())\n",
                                                           '    entry = '
                                                           "ast(package22_original_bytes('common/scripted_diplomatic_actions/MDDC_AB_ask_foreign_support.txt',(ROOT/'common/scripted_diplomatic_actions/MDDC_AB_ask_foreign_support.txt').read_bytes()))\n"),
                                                          (1152,
                                                           1153,
                                                           '        for key,op,val in '
                                                           'rows(ast((ROOT/path).read_bytes())):\n',
                                                           '        for key,op,val in '
                                                           'rows(ast(package22_original_bytes(path,(ROOT/path).read_bytes()))):\n'),
                                                          (1157,
                                                           1158,
                                                           '        data = (ROOT/path).read_bytes()\n',
                                                           '        data = '
                                                           'package22_original_bytes(path,(ROOT/path).read_bytes())\n'),
                                                          (1164,
                                                           1165,
                                                           '        actual = (ROOT/path).read_bytes(); original = '
                                                           'baseline_bytes(path)\n',
                                                           '        actual = '
                                                           'package22_original_bytes(path,(ROOT/path).read_bytes()); '
                                                           'original = baseline_bytes(path)\n'),
                                                          (1175,
                                                           1176,
                                                           '    for path in untouched: assert '
                                                           'package21_original_validator_bytes(path,(ROOT/path).read_bytes()) '
                                                           '== baseline_bytes(path),path\n',
                                                           '    for path in untouched: assert '
                                                           'package21_original_validator_bytes(path,package22_original_bytes(path,(ROOT/path).read_bytes())) '
                                                           '== baseline_bytes(path),path\n')],
 'tools/validation/diplomacy_package_21/test_source.py': [(11,
                                                           11,
                                                           '',
                                                           'import sys as package22_sys\n'
                                                           "package22_sys.path.insert(0,str(ROOT/'tools/validation'))\n"
                                                           'from diplomacy_package_22.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE22_NEW, '
                                                           'package22_original_bytes, '
                                                           'package22_historical_existing,\n'
                                                           '    package22_original_validator_bytes, '
                                                           'historical_actions as package22_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package22_owned,\n'
                                                           ')\n'
                                                           'check_later_package22_owned()\n'),
                                                          (127,
                                                           127,
                                                           '',
                                                           '    actual = package22_original_bytes(path,actual)\n'),
                                                          (168,
                                                           169,
                                                           '    for path in sorted(EXISTING): '
                                                           'package21_original_bytes(path, (ROOT / '
                                                           'path).read_bytes())\n',
                                                           '    for path in sorted(EXISTING): '
                                                           'package21_original_bytes(path, '
                                                           'package22_original_bytes(path,(ROOT / '
                                                           'path).read_bytes()))\n'),
                                                          (171,
                                                           171,
                                                           '',
                                                           '    actions = package22_historical_actions(actions)\n'),
                                                          (1123,
                                                           1123,
                                                           '',
                                                           '    actual = '
                                                           'package22_original_validator_bytes(path,actual)\n'),
                                                          (1153,
                                                           1153,
                                                           '',
                                                           '    changed -= (package22_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE22_NEW\n'
                                                           '    untracked -= LATER_PACKAGE22_NEW\n'),
                                                          (1156,
                                                           1157,
                                                           '        data=(ROOT/path).read_bytes()\n',
                                                           '        '
                                                           'data=package22_original_bytes(path,(ROOT/path).read_bytes())\n'),
                                                          (1185,
                                                           1186,
                                                           '        for key,op,val in '
                                                           'rows(ast((ROOT/path).read_bytes())):\n',
                                                           '        for key,op,val in '
                                                           'rows(ast(package22_original_bytes(path,(ROOT/path).read_bytes()))):\n'),
                                                          (1220,
                                                           1221,
                                                           '        nodes=ast((ROOT/path).read_bytes())\n',
                                                           '        '
                                                           'nodes=ast(package22_original_bytes(path,(ROOT/path).read_bytes()))\n'),
                                                          (1239,
                                                           1240,
                                                           '        declarations=[val for key,op,val in '
                                                           'rows(ast((ROOT/path).read_bytes())) if '
                                                           "key=='set_country_flag' and isinstance(val,list)]\n",
                                                           '        declarations=[val for key,op,val in '
                                                           'rows(ast(package22_original_bytes(path,(ROOT/path).read_bytes()))) '
                                                           "if key=='set_country_flag' and isinstance(val,list)]\n"),
                                                          (1280,
                                                           1280,
                                                           '',
                                                           '    '
                                                           'current_ids=package22_historical_actions(current_ids)\n'),
                                                          (1286,
                                                           1287,
                                                           '        assert '
                                                           '(ROOT/path).read_bytes()==baseline_bytes(path),path\n',
                                                           '        assert '
                                                           'package22_original_bytes(path,(ROOT/path).read_bytes())==baseline_bytes(path),path\n'),
                                                          (1294,
                                                           1295,
                                                           "        lines=[line.decode('utf-8-sig') for line in "
                                                           '(ROOT/path).read_bytes().splitlines() if '
                                                           "re.match(rb'\\s*aid_military_button_TT:',line)]\n",
                                                           "        lines=[line.decode('utf-8-sig') for line in "
                                                           'package22_original_bytes(path,(ROOT/path).read_bytes()).splitlines() '
                                                           "if re.match(rb'\\s*aid_military_button_TT:',line)]\n"),
                                                          (1301,
                                                           1302,
                                                           '        for key,op,val in '
                                                           'rows(ast((ROOT/path).read_bytes())):\n',
                                                           '        for key,op,val in '
                                                           'rows(ast(package22_original_bytes(path,(ROOT/path).read_bytes()))):\n'),
                                                          (1306,
                                                           1307,
                                                           '        '
                                                           "try:package21_original_bytes(path,(ROOT/path).read_bytes()+b'# "
                                                           "unowned memory mutation\\n')\n",
                                                           '        '
                                                           "try:package21_original_bytes(path,package22_original_bytes(path,(ROOT/path).read_bytes())+b'# "
                                                           "unowned memory mutation\\n')\n"),
                                                          (1312,
                                                           1313,
                                                           '        '
                                                           'actual=(ROOT/path).read_bytes();original=baseline_bytes(path)\n',
                                                           '        '
                                                           'actual=package22_original_bytes(path,(ROOT/path).read_bytes());original=baseline_bytes(path)\n'),
                                                          (1322,
                                                           1323,
                                                           '    for path in untouched:assert '
                                                           '(ROOT/path).read_bytes()==baseline_bytes(path),path\n',
                                                           '    for path in untouched:assert '
                                                           'package22_original_bytes(path,(ROOT/path).read_bytes())==baseline_bytes(path),path\n')]}


def package22_original_validator_bytes(path, actual):
    if path not in HISTORICAL_SOURCE_EDITS: return actual
    original = baseline_bytes(path)
    lines = original.decode('utf-8').splitlines(keepends=True)
    for start, end, before, after in reversed(HISTORICAL_SOURCE_EDITS[path]):
        assert ''.join(lines[start:end]) == before, ('Historical source baseline drift', path, start)
        lines[start:end] = [after]
    assert actual == ''.join(lines).encode('utf-8'), ('Undeclared historical source validator edit', path)
    return original

def main():
    groups=Counter();boundary_groups=set()
    def passed(group):groups[group]+=1
    check_owned_existing();passed('four_existing_paths_restore_exactly_four_menu_options_two_action_fields_one_guard_and_twelve_locale_rows')
    trees=('common/scripted_effects','common/scripted_triggers','common/scripted_diplomatic_actions','common/on_actions','events','localisation')
    changed=set(subprocess.check_output(['git','diff','--name-only',BASELINE,'--',*trees],cwd=ROOT).decode().splitlines())
    untracked=set(subprocess.check_output(['git','ls-files','--others','--exclude-standard','--',*trees],cwd=ROOT).decode().splitlines())
    assert changed-NEW==EXISTING and (changed|untracked)-EXISTING==NEW,(changed,untracked)
    passed('exact_four_existing_and_seven_new_gameplay_paths')
    for path in sorted(NEW):
        raw=(ROOT/path).read_bytes();assert raw.startswith(b'\xef\xbb\xbf')==path.endswith('.yml')
        assert b'\r' not in raw.replace(b'\r\n',b'') and b'\n' not in raw.replace(b'\r\n',b'')
        passed('seven_new_files_use_declared_CRLF_and_locale_BOM')
    effects={key:body for key,op,body in ast((ROOT/FX).read_bytes())}
    triggers={key:body for key,op,body in ast((ROOT/TR).read_bytes())}
    expected_effects={'eon_support_request_'+name for name in ('clear_pending','send_request','handoff_formation','handoff_equipment','handoff_cash','decline_request','withdraw_request','daily_update','annex_update','clear_annexed_country')}
    expected_triggers={'eon_support_request_'+name for name in ('partner_identified','policy_allowed','slot_ready','action_ready','menu_pending','menu_ready','withdraw_available')}
    assert set(effects)==expected_effects and set(triggers)==expected_triggers
    passed('exact_ten_effect_and_seven_trigger_helper_sets')
    definitions=Counter()
    for directory in ('common/scripted_effects','common/scripted_triggers'):
        for path in (ROOT/directory).glob('*.txt'):
            for block in blocks(path.read_bytes(),0):
                if block['key'] in expected_effects|expected_triggers:definitions[block['key']]+=1
    for key in expected_effects|expected_triggers:assert definitions[key]==1,key;passed('seventeen_new_helper_IDs_are_globally_unique')
    prefix='eon_support_request_'
    for path in (FX,TR,NA,HOOKS,EVENTS):
        for key,op,val in rows(ast((ROOT/path).read_bytes())):
            if key in expected_effects|expected_triggers and not isinstance(val,list):assert val in ('yes','no')
            elif key.startswith(prefix) and not isinstance(val,list) and val in ('yes','no'):raise AssertionError(('Undefined initial request helper',key,path))
        passed('five_new_sources_parse_and_resolve_owned_helper_calls')
    initial_path='common/scripted_diplomatic_actions/MDDC_AB_ask_foreign_support.txt'
    initial=(ROOT/initial_path).read_bytes();original_initial=baseline_bytes(initial_path)
    action=one(one(ast(initial),'scripted_diplomatic_actions'),'AB_ask_foreign_support')
    old_action=one(one(ast(original_initial),'scripted_diplomatic_actions'),'AB_ask_foreign_support')
    assert one(action,'cost')=='50' and one(action,'requires_acceptance')=='no'
    assert one(action,'can_be_sent')==[('eon_support_request_action_ready','=','yes')]
    assert ('eon_support_request_send_request','=','yes') in one(action,'complete_effect')
    assert not any(key in ('FROM','ROOT','THIS') for key,op,val in one(action,'complete_effect'))
    passed('native_completion_runs_in_documented_THIS_provider_scope_without_legacy_FROM_dependency_or_manual_PP_charge')
    for key in ('allowed','visible','on_sent_effect','reject_effect','ai_desire'):
        before=named_block(original_initial,key);after=named_block(initial,key)
        assert original_initial[before['start']:before['end']]==initial[after['start']:after['end']]
        passed('five_unchanged_native_action_fields_preserve_original_raw_AI_visibility_and_metadata')
    selectable=one(action,'selectable');tooltip=one(selectable,'custom_trigger_tooltip')
    assert one(tooltip,'tooltip')=='AB_ASK_FOREIGN_SUPPORT_TOOLTIP'
    assert ('eon_support_request_action_ready','=','yes') in one(tooltip,'THIS')
    passed('existing_tooltip_has_fresh_full_policy_slot_and_cooldown_readiness')
    raw=(ROOT/'events/00_War_events.txt').read_bytes();original=baseline_bytes('events/00_War_events.txt')
    for suffix,kind,child in (('a','formation','eon_defence_formation'),('b','equipment','eon_foreign_equipment')):
        name='AB_mobilization.4.'+suffix;body=ast(option_raw(raw,'AB_mobilization.4',name))[0][2]
        assert ('eon_support_request_handoff_'+kind,'=','yes') in body
        assert ('eon_support_request_menu_ready','=','yes') in list(rows(one(body,'trigger')))
        assert (child+'_offer_ready','=','yes') in list(rows(one(body,'trigger')))
        assert field_raw(option_raw(raw,'AB_mobilization.4',name),'ai_chance')==field_raw(option_raw(original,'AB_mobilization.4',name),'ai_chance')
        passed('existing_formation_and_equipment_menu_keep_raw_AI_and_require_owned_request_plus_unchanged_child_readiness')
    for suffix in ('c','d'):
        name='AB_mobilization.4.'+suffix;body=ast(option_raw(raw,'AB_mobilization.4',name))[0][2]
        assert field_raw(option_raw(raw,'AB_mobilization.4',name),'ai_chance')==field_raw(option_raw(original,'AB_mobilization.4',name),'ai_chance')
        if suffix=='c':assert ('eon_support_request_menu_ready','=','yes') in list(rows(one(body,'trigger'))) and ('eon_support_request_handoff_cash','=','yes') in body
        else:assert not any(key=='trigger' for key,op,val in body) and float(one(one(body,'ai_chance'),'base'))>0 and ('eon_support_request_decline_request','=','yes') in body
        passed('cash_and_always_visible_positive_decline_preserve_original_AI_and_guarded_owned_effects')
    for kind,child in (('formation','eon_defence_formation'),('equipment','eon_foreign_equipment'),('cash','eon_foreign_cash')):
        body=effects[prefix+'handoff_'+kind];branch=one(body,'if')
        assert one(branch,'limit')==[(prefix+'menu_ready','=','yes'),(child+'_offer_ready','=','yes')]
        assert branch[1:]==[(prefix+'clear_pending','=','yes'),(child+'_send_offer','=','yes')]
        passed('each_owned_initial_receipt_is_consumed_before_unchanged_selected_child_helper')
    clear=effects[prefix+'clear_pending']
    assert clear==[('clr_country_flag','=',prefix+'pending'),('clr_country_flag','=',prefix+'live'),('clr_country_flag','=',prefix+'cancelled'),('clear_variable','=',prefix+'partner')]
    passed('exact_initial_cleanup_fields_do_not_include_cooldown_child_records_or_legacy_state')
    send=one(effects[prefix+'send_request'],'if')
    assert one(send,'limit')==[(prefix+'action_ready','=','yes')]
    assert ('set_variable','=',[(prefix+'partner','=','ROOT')]) in send
    assert ('set_country_flag','=',[('flag','=',prefix+'live'),('days','=','30'),('value','=','1')]) in send
    assert ('set_country_flag','=',[('flag','=','aid_request_cd_@ROOT'),('days','=','360'),('value','=','1')]) in send
    assert ('country_event','=',[('id','=','AB_mobilization.4'),('days','=','1')]) in send
    passed('explicit_requester_frozen_once_before_provider_menu_with_30_day_response_360_day_pair_cooldown_and_one_day_native_delay')
    assert (prefix+'slot_ready','=','yes') in triggers[prefix+'action_ready']
    assert ('NOT','=',[('has_country_flag','=','aid_request_cd_@ROOT')]) in triggers[prefix+'action_ready']
    assert not any(key=='has_country_flag' and str(val).startswith('aid_request_cd_') for key,op,val in rows(triggers[prefix+'menu_ready']))
    passed('initial_cooldown_admission_is_separate_from_owned_response_readiness_after_timer_is_set')
    for helper in ('partner_identified','policy_allowed'):
        assert any(key=='check_variable' and any(op=='>' and val=='0' for field,op,val in fields) for key,op,fields in rows(triggers[prefix+helper]) if key=='check_variable')
        assert any(key=='check_variable' and any(field=='THIS.id' for field,op,val in fields) for key,op,fields in rows(triggers[prefix+helper]) if key=='check_variable')
        passed('positive_country_only_nonself_partner_identity_is_explicit')
    assert ('has_country_flag','=',prefix+'live') in triggers[prefix+'withdraw_available']
    assert ('NOT','=',[('has_country_flag','=',prefix+'cancelled')]) in triggers[prefix+'withdraw_available']
    passed('withdrawal_requires_live_exact_initial_pair_and_cannot_repeat')
    for path in (FX,TR,NA,HOOKS,EVENTS):
        flattened=list(rows(ast((ROOT/path).read_bytes())))
        assert not any(key in ('add_political_power','modify_treasury_effect','add_manpower','send_equipment','add_equipment_to_stockpile','division_template','create_unit','delete_unit','delete_units','delete_unit_template_and_units','add_to_faction','declare_war_on','add_fuel') for key,op,val in flattened)
        assert not any(isinstance(val,str) and ('retired_pair' in val or 'quarantined' in val) for key,op,val in flattened)
        passed('five_new_sources_add_no_assets_manual_PP_refund_permanent_pair_ban_or_quarantine')
    actions=one(ast((ROOT/NA).read_bytes()),'scripted_diplomatic_actions');assert {key for key,op,val in actions}==NEW_ACTION_IDS
    withdrawal=actions[0][2];assert one(withdrawal,'cost')=='0' and one(withdrawal,'requires_acceptance')=='no'
    assert (prefix+'withdraw_request','=','yes') in one(withdrawal,'complete_effect')
    passed('one_new_free_native_withdrawal_action_uses_same_provider_scope')
    events={one(body,'id'):body for key,op,body in ast((ROOT/EVENTS).read_bytes()) if key=='country_event'}
    assert set(events)=={'eon_support_request.1','eon_support_request.2'}
    for identity,body in events.items():
        choices=[val for key,op,val in body if key=='option'];assert len(choices)==1
        assert {key for key,op,val in choices[0]}=={'name','ai_chance'} and one(one(choices[0],'ai_chance'),'base')=='100'
        passed('two_new_notices_have_inert_acknowledgements')
    hooks=one(ast((ROOT/HOOKS).read_bytes()),'on_actions');assert {key for key,op,val in hooks}=={'on_daily','on_annex','on_subject_annexed'}
    passed('daily_and_both_native_annex_hook_frames_are_present')
    locales={}
    for language in ('english','russian'):
        text=(ROOT/f'localisation/{language}/eon_support_request_l_{language}.yml').read_text(encoding='utf-8-sig')
        locales[language]={match[1]:match[2] for match in re.finditer(r'^\s*([A-Za-z0-9_.]+):[0-9]*\s*"(.*)"\s*$',text,re.M)}
        assert len(locales[language])==8;passed('eight_new_product_localisation_keys_per_language')
    assert locales['english'].keys()==locales['russian'].keys();passed('bilingual_locale_keys_match')
    for path in (NA,EVENTS,'events/00_War_events.txt'):
        for key,op,val in rows(ast((ROOT/path).read_bytes())):
            if key in ('name','title','desc','tooltip','send_description','custom_effect_tooltip') and isinstance(val,str) and val.startswith(('eon_support_request.',prefix)):
                assert val in locales['english'],val
            if key=='tooltip' and val==prefix+'menu_available_tt':assert val in locales['english']
        passed('current_action_notice_and_menu_tooltip_references_resolve')
    old_actions=[];current_actions=[]
    for path in subprocess.check_output(['git','ls-tree','-r','--name-only',BASELINE,'--','common/scripted_diplomatic_actions'],cwd=ROOT).decode().splitlines():
        for key,op,val in ast(baseline_bytes(path)):
            if key=='scripted_diplomatic_actions':old_actions.extend(name for name,op,body in val)
    for path in (ROOT/'common/scripted_diplomatic_actions').glob('*.txt'):
        for key,op,val in ast(path.read_bytes()):
            if key=='scripted_diplomatic_actions':current_actions.extend(name for name,op,body in val)
    assert len(old_actions)==len(set(old_actions))==74 and len(current_actions)==len(set(current_actions))==75
    passed('74_existing_native_action_IDs_and_one_new_unique_withdrawal')
    old_game=subprocess.check_output(['git','ls-tree','-r','--name-only',BASELINE,'--','common','events','localisation'],cwd=ROOT).decode().splitlines()
    protected_game=[path for path in old_game if any(stem in path for stem in ('eon_services_','eon_foreign_cash_','eon_foreign_equipment_','eon_defence_formation_','eon_advisers_'))]
    for path in protected_game:assert (ROOT/path).read_bytes()==baseline_bytes(path),path;passed('all_previous_service_cash_equipment_formation_and_advisory_channel_bytes_are_unchanged')
    for path in EXISTING:
        try:package22_original_bytes(path,(ROOT/path).read_bytes()+b'# unowned memory mutation\n')
        except AssertionError:pass
        else:raise AssertionError(('Unowned gameplay mutation accepted',path))
        passed('memory_only_unowned_gameplay_suffix_rejected');boundary_groups.add('memory_only_unowned_gameplay_suffix_rejected')
    projected,manifest=historical_caller_view(raw)
    for identity,name in CHOICES[:3]:assert option_raw(projected,identity,name)==option_raw(original,identity,name);passed('only_three_historical_AB4_callers_project_to_exact_baseline_options')
    assert option_raw(projected,*CHOICES[3])==option_raw(raw,*CHOICES[3])
    passed('historical_projection_does_not_restore_decline_or_any_child_helper')
    for identity,name in CHOICES:
        segment=option_raw(raw,identity,name);assert b'= yes' in segment
        changed=raw.replace(segment,segment.replace(b'= yes',b'= no',1),1)
        try:historical_caller_view(changed)
        except AssertionError:pass
        else:raise AssertionError(('Current caller drift accepted by historical projection',name))
        passed('historical_projection_rejects_unowned_or_owned_current_option_drift');boundary_groups.add('historical_projection_rejects_unowned_or_owned_current_option_drift')
    for path in HISTORICAL_SOURCE_EDITS:
        current=(ROOT/path).read_bytes();before=baseline_bytes(path)
        assert package22_original_validator_bytes(path,current)==before
        counters=lambda data:[line for line in data.splitlines() if b'groups[' in line and b'+=' in line or b'passed(' in line]
        assert counters(current)==counters(before);passed('20_literal_whole_historical_source_journals_preserve_original_assertion_counter_lines')
        try:package22_original_validator_bytes(path,current+b'# unowned memory mutation\n')
        except AssertionError:pass
        else:raise AssertionError(('Unowned source validator mutation accepted',path))
        passed('memory_only_whole_historical_validator_suffix_rejected');boundary_groups.add('memory_only_whole_historical_validator_suffix_rejected')
    public_paths=subprocess.check_output(['git','ls-tree','-r','--name-only',BASELINE,'--','tools/validation'],cwd=ROOT).decode().splitlines()
    untouched=[path for path in public_paths if path not in HISTORICAL_SOURCE_EDITS]
    for path in untouched:assert (ROOT/path).read_bytes()==baseline_bytes(path),path
    behavior=[path for path in untouched if path.endswith('.py') and Path(path).name!='test_source.py']
    assert len(untouched)==74 and len(behavior)==53
    passed('53_prior_behavior_helper_runner_files_and74_other_public_files_remain_raw_byte_exact')
    installed=Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV')
    native=(installed/'common/scripted_diplomatic_actions/scripted_diplomatic_actions.txt').read_text(encoding='utf-8-sig')
    assert 'root is the initiator of action and this is the target country' in native and 'root is the sender and this is receiver' in native
    assert 'cost = 10 # pp cost, can be zero' in native and 'can_be_sent' in native
    passed('installed_native_action_scope_and_cost_declarations_are_primary_metadata_not_measured_charging')
    effect_docs=(installed/'documentation/effects_documentation.md').read_text(encoding='utf-8-sig')
    trigger_docs=(installed/'documentation/triggers_documentation.md').read_text(encoding='utf-8-sig')
    for name in ('country_event','set_country_flag'):
        assert '\n## '+name+'\n' in effect_docs;passed('native_event_and_timed_flag_declarations_verified_without_timer_completion_claim')
    for name in ('has_defensive_war','has_opinion','has_idea','exists'):
        assert '\n## '+name+'\n' in trigger_docs;passed('native_country_policy_declarations_verified')
    boundaries=sum(groups[key] for key in boundary_groups)
    print(json.dumps({'all_passed':True,'baseline':BASELINE,'source_cases':sum(groups.values()),'source_API_cases':sum(groups.values())-boundaries,
        'source_byte_adapter_boundary_cases':boundaries,'groups':dict(groups),'source_sha256':{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in SOURCE_PATHS},
        'historical_source_adapters':len(HISTORICAL_SOURCE_EDITS),'historical_caller_manifest':manifest,
        'prior_behavior_helper_runner_raw_byte_files':len(behavior),'prior_other_public_raw_byte_files':len(untouched),
        'bilingual_locale_keys':len(locales['english']),'native_runtime':False,
        'proof_scope':'actual current initial request router and unchanged child contract bytes; preceding callers use explicit historical views, native charging and campaign unverified'},indent=2))

if __name__=='__main__':main()
