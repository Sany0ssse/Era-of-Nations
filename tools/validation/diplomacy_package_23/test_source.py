"""Exact one-use Iran/USA normalization route and historical byte journals; not native runtime."""
from pathlib import Path
from functools import lru_cache
from collections import Counter
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASELINE = 'f56ec8b3cd35a0f34ecad9627cbb77991963fca0'
import sys as scope_sys
scope_sys.path.insert(0, str(ROOT/'tools/validation'))
from diplomacy_package_17._scope_repair import game_before, test_before
FOCUS_PATH = 'common/national_focus/Iran_Focus_Tree.txt'
EVENT_PATH = 'events/Iran.txt'
EXISTING = {FOCUS_PATH, EVENT_PATH} | {f'localisation/{language}/MD_focus_PER_l_{language}.yml' for language in ('english', 'russian')}
FX = 'common/scripted_effects/eon_per_usa_normalization_effects.txt'
TR = 'common/scripted_triggers/eon_per_usa_normalization_triggers.txt'
NA = 'common/scripted_diplomatic_actions/eon_per_usa_normalization_actions.txt'
HOOKS = 'common/on_actions/eon_per_usa_normalization_on_actions.txt'
EVENTS = 'events/eon_per_usa_normalization_events.txt'
NEW = {FX, TR, NA, HOOKS, EVENTS} | {f'localisation/{language}/eon_per_usa_normalization_l_{language}.yml' for language in ('english', 'russian')}
SOURCE_PATHS = sorted(EXISTING | NEW)
NEW_ACTION_IDS = {'eon_per_usa_normalization_withdraw_request'}
LEGACY_LOCALE_KEYS = {'iranian_focus.64.t', 'iranian_focus.64.d', 'iranian_focus.64.a', 'iranian_focus.64.b',
    'iranian_focus.65.d', 'iranian_focus.66.d', 'PER_all_negative_modifiers_TT', 'PER_agree_to_hand_off2_TT', 'PER_USA_ai_better_TT'}
parser_path = 'tools/validation/diplomacy_package_22/test_source.py'
parser_text = subprocess.check_output(['git', 'show', BASELINE+':'+parser_path], cwd=ROOT).decode('utf-8')
parser = {'__file__': str(ROOT/parser_path), '__name__': 'normalization_byte_parser'}
exec(compile(parser_text.split('def package22_original_bytes(', 1)[0], str(ROOT/parser_path), 'exec'), parser)
blocks, ast, one, rows = (parser[name] for name in ('blocks', 'ast', 'one', 'rows'))
event_blocks, option_block, option_raw, format_preserved = (parser[name] for name in ('event_blocks', 'option_block', 'option_raw', 'format_preserved'))

def event_blocks(data):
    # Iran's unrelated events contain native token arrays; inventory their IDs
    # without evaluating or reparsing any unowned event body.
    result = {}
    for block in blocks(data, 0):
        if block['key'] not in ('country_event', 'news_event'): continue
        segment = data[block['start']:block['end']]
        matches = re.findall(rb'(?m)^[ \t]*id\s*=\s*([A-Za-z0-9_.]+)', segment)
        assert matches
        identity = matches[0].decode(); assert identity not in result
        result[identity] = block
    return result

parser['event_blocks'] = event_blocks

@lru_cache(maxsize=128)
def baseline_bytes(path): return subprocess.check_output(['git', 'show', BASELINE+':'+path], cwd=ROOT)

def focus_reward(data):
    found = [block for block in blocks(data) if block['key'] == 'focus' and
        re.search(rb'\bid\s*=\s*PER_talks_with_the_americans\b', data[block['start']:block['end']])]
    assert len(found) == 1, ('Expected one named national focus', len(found))
    parent = found[0]; segment = data[parent['start']:parent['end']]
    field = [block for block in blocks(segment, 1) if block['key'] == 'completion_reward']
    assert len(field) == 1
    return {**field[0], 'start': parent['start']+field[0]['start'], 'end': parent['start']+field[0]['end']}

def package23_original_bytes(path, actual):
    """Inverse only the named focus reward, two consent options, one preview and eighteen locale rows."""
    actual = game_before(path, actual)
    if path not in EXISTING: return actual
    original = baseline_bytes(path); format_preserved(original, actual, path)
    if actual == original: return original
    restored = actual
    if path == FOCUS_PATH:
        before, after = focus_reward(original), focus_reward(actual)
        restored = actual[:after['start']]+original[before['start']:before['end']]+actual[after['end']:]
    elif path == EVENT_PATH:
        assert event_blocks(actual).keys() == event_blocks(original).keys(), 'Existing Iran event IDs changed'
        # This preview replacement is presentation-only, not ownership of event65 effects.
        before65 = option_raw(original, 'iranian_focus.65', 'iranian_focus.65.a')
        after65 = option_raw(restored, 'iranian_focus.65', 'iranian_focus.65.a')
        permitted = b'custom_effect_tooltip = PER_all_negative_modifiers_TT'
        replacement = b'custom_effect_tooltip = eon_per_usa_normalization_restoration_tt'
        assert before65.count(permitted) == 1 and after65.count(replacement) == 1
        assert after65.replace(replacement, permitted, 1) == before65, 'Unowned event65 effect/AI bytes changed'
        restored = restored.replace(after65, before65, 1)
        for suffix in ('b', 'a'):
            before = option_block(original, 'iranian_focus.64', 'iranian_focus.64.'+suffix)
            after = option_block(restored, 'iranian_focus.64', 'iranian_focus.64.'+suffix)
            restored = restored[:after['start']]+original[before['start']:before['end']]+restored[after['end']:]
    else:
        before_lines, after_lines = original.splitlines(keepends=True), actual.splitlines(keepends=True)
        assert len(before_lines) == len(after_lines), ('Locale row count changed', path)
        seen = set(); parts = []
        for before, after in zip(before_lines, after_lines):
            match = re.match(rb'\s*([A-Za-z0-9_.]+):', before); key = match[1].decode() if match else None
            if key in LEGACY_LOCALE_KEYS:
                assert re.match(rb'\s*([A-Za-z0-9_.]+):', after)[1].decode() == key
                assert key not in seen, ('Duplicate permitted row', path, key)
                seen.add(key); parts.append(before)
            else: parts.append(after)
        assert seen == LEGACY_LOCALE_KEYS, (path, seen)
        restored = b''.join(parts)
    assert restored == original, ('Unowned normalization source bytes changed', path)
    return original

@lru_cache(maxsize=32)
def package23_historical_existing(baseline):
    return frozenset(subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', baseline, '--', *sorted(EXISTING)], cwd=ROOT).decode().splitlines())

def check_owned_existing():
    for path in sorted(EXISTING): package23_original_bytes(path, (ROOT/path).read_bytes())

def historical_actions(actions): return [identity for identity in actions if identity not in NEW_ACTION_IDS]

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
                                                           "'eon_advisers_end_cooperation', "
                                                           "'eon_support_request_withdraw_request')))\n",
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
                                                           "'eon_support_request_withdraw_request', "
                                                           "'eon_per_usa_normalization_withdraw_request')))\n")],
 'tools/validation/diplomacy_package_03/test_source.py': [(95,
                                                           95,
                                                           '',
                                                           'from diplomacy_package_23.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE23_NEW, '
                                                           'package23_original_bytes, '
                                                           'package23_historical_existing,\n'
                                                           '    package23_original_validator_bytes, '
                                                           'historical_actions as package23_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package23_owned,\n'
                                                           ')\n'
                                                           'check_later_package23_owned()\n'),
                                                          (277,
                                                           278,
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
                                                           'LATER_PACKAGE22_NEW]\n',
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
                                                           'LATER_PACKAGE22_NEW | '
                                                           'package23_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE23_NEW]\n'),
                                                          (281,
                                                           282,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW | LATER_PACKAGE23_NEW]\n'),
                                                          (295,
                                                           296,
                                                           '    assert package10_original_bytes(unchanged, '
                                                           'package14_original_bytes(unchanged, '
                                                           'package21_original_bytes(unchanged, (ROOT / '
                                                           'unchanged).read_bytes()))) == baseline(unchanged), '
                                                           "'Preserved policy bytes changed: ' + unchanged\n",
                                                           '    assert package10_original_bytes(unchanged, '
                                                           'package14_original_bytes(unchanged, '
                                                           'package21_original_bytes(unchanged, '
                                                           'package23_original_bytes(unchanged, (ROOT / '
                                                           'unchanged).read_bytes())))) == baseline(unchanged), '
                                                           "'Preserved policy bytes changed: ' + unchanged\n")],
 'tools/validation/diplomacy_package_04/test_source.py': [(111,
                                                           111,
                                                           '',
                                                           'from diplomacy_package_23.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE23_NEW, '
                                                           'package23_original_bytes, '
                                                           'package23_historical_existing,\n'
                                                           '    package23_original_validator_bytes, '
                                                           'historical_actions as package23_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package23_owned,\n'
                                                           ')\n'
                                                           'check_later_package23_owned()\n'),
                                                          (374,
                                                           375,
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
                                                           'LATER_PACKAGE22_NEW]\n',
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
                                                           'LATER_PACKAGE22_NEW | '
                                                           'package23_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE23_NEW]\n'),
                                                          (376,
                                                           377,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW | LATER_PACKAGE23_NEW]\n')],
 'tools/validation/diplomacy_package_05/test_source.py': [(106,
                                                           106,
                                                           '',
                                                           'from diplomacy_package_23.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE23_NEW, '
                                                           'package23_original_bytes, '
                                                           'package23_historical_existing,\n'
                                                           '    package23_original_validator_bytes, '
                                                           'historical_actions as package23_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package23_owned,\n'
                                                           ')\n'
                                                           'check_later_package23_owned()\n'),
                                                          (316,
                                                           317,
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
                                                           'package21_required_old_paths) | LATER_PACKAGE22_NEW]\n',
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
                                                           'package21_required_old_paths) | LATER_PACKAGE22_NEW | '
                                                           '(package23_historical_existing(BASELINE) - '
                                                           'package21_required_old_paths) | LATER_PACKAGE23_NEW]\n'),
                                                          (318,
                                                           319,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW | LATER_PACKAGE23_NEW]\n')],
 'tools/validation/diplomacy_package_06/test_source.py': [(108,
                                                           108,
                                                           '',
                                                           'from diplomacy_package_23.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE23_NEW, '
                                                           'package23_original_bytes, '
                                                           'package23_historical_existing,\n'
                                                           '    package23_original_validator_bytes, '
                                                           'historical_actions as package23_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package23_owned,\n'
                                                           ')\n'
                                                           'check_later_package23_owned()\n'),
                                                          (490,
                                                           491,
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
                                                           'package21_required_old_paths) | LATER_PACKAGE22_NEW]\n',
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
                                                           'package21_required_old_paths) | LATER_PACKAGE22_NEW | '
                                                           '(package23_historical_existing(BASELINE) - '
                                                           'package21_required_old_paths) | LATER_PACKAGE23_NEW]\n'),
                                                          (492,
                                                           493,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW | LATER_PACKAGE23_NEW]\n')],
 'tools/validation/diplomacy_package_07/test_source.py': [(106,
                                                           106,
                                                           '',
                                                           'from diplomacy_package_23.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE23_NEW, '
                                                           'package23_original_bytes, '
                                                           'package23_historical_existing,\n'
                                                           '    package23_original_validator_bytes, '
                                                           'historical_actions as package23_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package23_owned,\n'
                                                           ')\n'
                                                           'check_later_package23_owned()\n'),
                                                          (168,
                                                           169,
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
                                                           'LATER_PACKAGE22_NEW]\n',
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
                                                           'LATER_PACKAGE22_NEW | '
                                                           'package23_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE23_NEW]\n'),
                                                          (170,
                                                           171,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW | LATER_PACKAGE23_NEW]\n')],
 'tools/validation/diplomacy_package_08/test_source.py': [(106,
                                                           106,
                                                           '',
                                                           'from diplomacy_package_23.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE23_NEW, '
                                                           'package23_original_bytes, '
                                                           'package23_historical_existing,\n'
                                                           '    package23_original_validator_bytes, '
                                                           'historical_actions as package23_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package23_owned,\n'
                                                           ')\n'
                                                           'check_later_package23_owned()\n'),
                                                          (165,
                                                           166,
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
                                                           'LATER_PACKAGE22_NEW]\n',
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
                                                           'LATER_PACKAGE22_NEW | '
                                                           'package23_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE23_NEW]\n'),
                                                          (167,
                                                           168,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW | LATER_PACKAGE23_NEW]\n')],
 'tools/validation/diplomacy_package_09/test_source.py': [(94,
                                                           94,
                                                           '',
                                                           'from diplomacy_package_23.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE23_NEW, '
                                                           'package23_original_bytes, '
                                                           'package23_historical_existing,\n'
                                                           '    package23_original_validator_bytes, '
                                                           'historical_actions as package23_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package23_owned,\n'
                                                           ')\n'
                                                           'check_later_package23_owned()\n'),
                                                          (148,
                                                           149,
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
                                                           'LATER_PACKAGE22_NEW]\n',
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
                                                           'LATER_PACKAGE22_NEW | '
                                                           'package23_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE23_NEW]\n'),
                                                          (150,
                                                           151,
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n',
                                                           'untracked = [path for path in untracked if path not in '
                                                           'LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW | LATER_PACKAGE23_NEW]\n')],
 'tools/validation/diplomacy_package_10/test_source.py': [(86,
                                                           86,
                                                           '',
                                                           'from diplomacy_package_23.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE23_NEW, '
                                                           'package23_original_bytes, '
                                                           'package23_historical_existing,\n'
                                                           '    package23_original_validator_bytes, '
                                                           'historical_actions as package23_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package23_owned,\n'
                                                           ')\n'
                                                           'check_later_package23_owned()\n'),
                                                          (228,
                                                           229,
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
                                                           'LATER_PACKAGE22_NEW]\n',
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
                                                           'LATER_PACKAGE22_NEW | '
                                                           'package23_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE23_NEW]\n'),
                                                          (230,
                                                           231,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW | LATER_PACKAGE23_NEW]\n')],
 'tools/validation/diplomacy_package_11/test_source.py': [(79,
                                                           79,
                                                           '',
                                                           'from diplomacy_package_23.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE23_NEW, '
                                                           'package23_original_bytes, '
                                                           'package23_historical_existing,\n'
                                                           '    package23_original_validator_bytes, '
                                                           'historical_actions as package23_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package23_owned,\n'
                                                           ')\n'
                                                           'check_later_package23_owned()\n'),
                                                          (242,
                                                           244,
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
                                                           'LATER_PACKAGE22_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW | LATER_PACKAGE23_NEW]\n'
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
                                                           'LATER_PACKAGE22_NEW | '
                                                           'package23_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE23_NEW]\n')],
 'tools/validation/diplomacy_package_12/test_source.py': [(65,
                                                           65,
                                                           '',
                                                           'from diplomacy_package_23.test_source import (\r\n'
                                                           '    NEW as LATER_PACKAGE23_NEW, '
                                                           'package23_original_bytes, '
                                                           'package23_historical_existing,\r\n'
                                                           '    package23_original_validator_bytes, '
                                                           'historical_actions as package23_historical_actions,\r\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package23_owned,\r\n'
                                                           ')\r\n'
                                                           'check_later_package23_owned()\r\n'),
                                                          (212,
                                                           213,
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
                                                           'LATER_PACKAGE22_NEW]\r\n',
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
                                                           'LATER_PACKAGE22_NEW | '
                                                           'package23_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE23_NEW]\r\n'),
                                                          (214,
                                                           215,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\r\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW | LATER_PACKAGE23_NEW]\r\n')],
 'tools/validation/diplomacy_package_13/test_source.py': [(65,
                                                           65,
                                                           '',
                                                           'from diplomacy_package_23.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE23_NEW, '
                                                           'package23_original_bytes, '
                                                           'package23_historical_existing,\n'
                                                           '    package23_original_validator_bytes, '
                                                           'historical_actions as package23_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package23_owned,\n'
                                                           ')\n'
                                                           'check_later_package23_owned()\n'),
                                                          (225,
                                                           226,
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
                                                           'LATER_PACKAGE22_NEW]\n',
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
                                                           'LATER_PACKAGE22_NEW | '
                                                           'package23_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE23_NEW]\n'),
                                                          (227,
                                                           228,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW | LATER_PACKAGE23_NEW]\n')],
 'tools/validation/diplomacy_package_14/test_source.py': [(61,
                                                           61,
                                                           '',
                                                           'from diplomacy_package_23.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE23_NEW, '
                                                           'package23_original_bytes, '
                                                           'package23_historical_existing,\n'
                                                           '    package23_original_validator_bytes, '
                                                           'historical_actions as package23_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package23_owned,\n'
                                                           ')\n'
                                                           'check_later_package23_owned()\n'),
                                                          (241,
                                                           242,
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
                                                           'LATER_PACKAGE22_NEW]\n',
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
                                                           'LATER_PACKAGE22_NEW | '
                                                           'package23_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE23_NEW]\n'),
                                                          (243,
                                                           244,
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW]\n',
                                                           '    untracked = [path for path in untracked if path not '
                                                           'in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW | LATER_PACKAGE23_NEW]\n')],
 'tools/validation/diplomacy_package_15/test_source.py': [(53,
                                                           53,
                                                           '',
                                                           'from diplomacy_package_23.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE23_NEW, '
                                                           'package23_original_bytes, '
                                                           'package23_historical_existing,\n'
                                                           '    package23_original_validator_bytes, '
                                                           'historical_actions as package23_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package23_owned,\n'
                                                           ')\n'
                                                           'check_later_package23_owned()\n'),
                                                          (845,
                                                           847,
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
                                                           'LATER_PACKAGE22_NEW\n',
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
                                                           'LATER_PACKAGE22_NEW | '
                                                           'package23_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE23_NEW\n'
                                                           '    added -= LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW | LATER_PACKAGE23_NEW\n')],
 'tools/validation/diplomacy_package_16/test_source.py': [(53,
                                                           53,
                                                           '',
                                                           'from diplomacy_package_23.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE23_NEW, '
                                                           'package23_original_bytes, '
                                                           'package23_historical_existing,\n'
                                                           '    package23_original_validator_bytes, '
                                                           'historical_actions as package23_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package23_owned,\n'
                                                           ')\n'
                                                           'check_later_package23_owned()\n'),
                                                          (676,
                                                           678,
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
                                                           'LATER_PACKAGE22_NEW\n',
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
                                                           'LATER_PACKAGE22_NEW | '
                                                           'package23_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE23_NEW\n'
                                                           '    untracked -= LATER_PACKAGE17_NEW | '
                                                           'LATER_PACKAGE18_NEW | LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW | LATER_PACKAGE23_NEW\n')],
 'tools/validation/diplomacy_package_17/test_source.py': [(47,
                                                           47,
                                                           '',
                                                           'from diplomacy_package_23.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE23_NEW, '
                                                           'package23_original_bytes, '
                                                           'package23_historical_existing,\n'
                                                           '    package23_original_validator_bytes, '
                                                           'historical_actions as package23_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package23_owned,\n'
                                                           ')\n'
                                                           'check_later_package23_owned()\n'),
                                                          (769,
                                                           771,
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
                                                           'LATER_PACKAGE21_NEW | LATER_PACKAGE22_NEW\n',
                                                           '    changed -= package18_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE18_NEW | '
                                                           'package19_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE19_NEW | '
                                                           'package20_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE20_NEW | '
                                                           '(package21_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE21_NEW | '
                                                           '(package22_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE22_NEW | '
                                                           '(package23_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE23_NEW\n'
                                                           '    untracked -= LATER_PACKAGE18_NEW | '
                                                           'LATER_PACKAGE19_NEW | LATER_PACKAGE20_NEW | '
                                                           'LATER_PACKAGE21_NEW | LATER_PACKAGE22_NEW | '
                                                           'LATER_PACKAGE23_NEW\n')],
 'tools/validation/diplomacy_package_18/test_source.py': [(37,
                                                           37,
                                                           '',
                                                           'from diplomacy_package_23.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE23_NEW, '
                                                           'package23_original_bytes, '
                                                           'package23_historical_existing,\n'
                                                           '    package23_original_validator_bytes, '
                                                           'historical_actions as package23_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package23_owned,\n'
                                                           ')\n'
                                                           'check_later_package23_owned()\n'),
                                                          (774,
                                                           776,
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
                                                           'LATER_PACKAGE22_NEW\n',
                                                           '    changed -= (package19_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE19_NEW | '
                                                           '(package20_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW | '
                                                           '(package22_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE22_NEW | '
                                                           '(package23_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE23_NEW\n'
                                                           '    untracked -= LATER_PACKAGE19_NEW | '
                                                           'LATER_PACKAGE20_NEW | LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW | LATER_PACKAGE23_NEW\n')],
 'tools/validation/diplomacy_package_19/test_source.py': [(31,
                                                           31,
                                                           '',
                                                           'from diplomacy_package_23.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE23_NEW, '
                                                           'package23_original_bytes, '
                                                           'package23_historical_existing,\n'
                                                           '    package23_original_validator_bytes, '
                                                           'historical_actions as package23_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package23_owned,\n'
                                                           ')\n'
                                                           'check_later_package23_owned()\n'),
                                                          (879,
                                                           881,
                                                           '    changed -= (package20_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW | '
                                                           '(package22_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE22_NEW\n'
                                                           '    untracked -= LATER_PACKAGE20_NEW | '
                                                           'LATER_PACKAGE21_NEW | LATER_PACKAGE22_NEW\n',
                                                           '    changed -= (package20_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE20_NEW | '
                                                           'package21_historical_existing(BASELINE) | '
                                                           'LATER_PACKAGE21_NEW | '
                                                           '(package22_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE22_NEW | '
                                                           '(package23_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE23_NEW\n'
                                                           '    untracked -= LATER_PACKAGE20_NEW | '
                                                           'LATER_PACKAGE21_NEW | LATER_PACKAGE22_NEW | '
                                                           'LATER_PACKAGE23_NEW\n')],
 'tools/validation/diplomacy_package_20/test_source.py': [(25,
                                                           25,
                                                           '',
                                                           'from diplomacy_package_23.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE23_NEW, '
                                                           'package23_original_bytes, '
                                                           'package23_historical_existing,\n'
                                                           '    package23_original_validator_bytes, '
                                                           'historical_actions as package23_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package23_owned,\n'
                                                           ')\n'
                                                           'check_later_package23_owned()\n'),
                                                          (992,
                                                           994,
                                                           '    changed -= (package21_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE21_NEW | '
                                                           '(package22_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE22_NEW\n'
                                                           '    untracked -= LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW\n',
                                                           '    changed -= (package21_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE21_NEW | '
                                                           '(package22_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE22_NEW | '
                                                           '(package23_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE23_NEW\n'
                                                           '    untracked -= LATER_PACKAGE21_NEW | '
                                                           'LATER_PACKAGE22_NEW | LATER_PACKAGE23_NEW\n')],
 'tools/validation/diplomacy_package_21/test_source.py': [(19,
                                                           19,
                                                           '',
                                                           'from diplomacy_package_23.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE23_NEW, '
                                                           'package23_original_bytes, '
                                                           'package23_historical_existing,\n'
                                                           '    package23_original_validator_bytes, '
                                                           'historical_actions as package23_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package23_owned,\n'
                                                           ')\n'
                                                           'check_later_package23_owned()\n'),
                                                          (1164,
                                                           1166,
                                                           '    changed -= (package22_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE22_NEW\n'
                                                           '    untracked -= LATER_PACKAGE22_NEW\n',
                                                           '    changed -= (package22_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE22_NEW | '
                                                           '(package23_historical_existing(BASELINE) - EXISTING) | '
                                                           'LATER_PACKAGE23_NEW\n'
                                                           '    untracked -= LATER_PACKAGE22_NEW | '
                                                           'LATER_PACKAGE23_NEW\n')],
 'tools/validation/diplomacy_package_22/test_source.py': [(11,
                                                           11,
                                                           '',
                                                           'import sys as package23_sys\n'
                                                           "package23_sys.path.insert(0,str(ROOT/'tools/validation'))\n"
                                                           'from diplomacy_package_23.test_source import (\n'
                                                           '    NEW as LATER_PACKAGE23_NEW, '
                                                           'package23_original_bytes, '
                                                           'package23_historical_existing,\n'
                                                           '    package23_original_validator_bytes, '
                                                           'historical_actions as package23_historical_actions,\n'
                                                           '    check_owned_existing as '
                                                           'check_later_package23_owned,\n'
                                                           ')\n'
                                                           'check_later_package23_owned()\n'),
                                                          (117,
                                                           117,
                                                           '',
                                                           '    actual = package23_original_bytes(path,actual)\n'),
                                                          (174,
                                                           174,
                                                           '',
                                                           '    actions = package23_historical_actions(actions)\n'),
                                                          (1504,
                                                           1504,
                                                           '',
                                                           '    actual = '
                                                           'package23_original_validator_bytes(path,actual)\n'),
                                                          (1520,
                                                           1520,
                                                           '',
                                                           '    changed -= (package23_historical_existing(BASELINE) '
                                                           '- EXISTING) | LATER_PACKAGE23_NEW\n'
                                                           '    untracked -= LATER_PACKAGE23_NEW\n'),
                                                          (1637,
                                                           1637,
                                                           '',
                                                           '    current_actions = '
                                                           'package23_historical_actions(current_actions)\n')]}


def package23_original_validator_bytes(path, actual):
    actual = test_before(path, actual)
    if path not in HISTORICAL_SOURCE_EDITS: return actual
    original = baseline_bytes(path); lines = original.decode('utf-8').splitlines(keepends=True)
    for start, end, before, after in reversed(HISTORICAL_SOURCE_EDITS[path]):
        assert ''.join(lines[start:end]) == before, ('Historical source baseline drift', path, start)
        lines[start:end] = [after]
    assert actual == ''.join(lines).encode('utf-8'), ('Undeclared historical source validator edit', path)
    return original

def main():
    groups = Counter(); boundary_groups = set()
    def passed(group): groups[group] += 1
    check_owned_existing()
    for path in sorted(EXISTING):
        assert package23_original_bytes(path, (ROOT/path).read_bytes()) == baseline_bytes(path)
        passed('four_existing_whole_byte_inverses_restore_only_named_reward_response_preview_and_locale_rows')
    trees = ('common', 'history', 'events', 'interface', 'gfx', 'localisation', 'music', 'map', 'sound')
    changed = set(subprocess.check_output(['git', 'diff', '--name-only', BASELINE, '--', *trees], cwd=ROOT).decode().splitlines())
    untracked = set(subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', *trees], cwd=ROOT).decode().splitlines())
    assert changed-NEW == EXISTING and (changed|untracked)-EXISTING == NEW, (changed, untracked)
    passed('exact_four_existing_and_seven_new_gameplay_paths_without_other_story_or_assets')
    for path in sorted(NEW):
        raw = (ROOT/path).read_bytes(); assert raw.startswith(b'\xef\xbb\xbf') == path.endswith('.yml')
        assert b'\r' not in raw and raw.endswith(b'\n')
        passed('seven_new_files_use_declared_LF_and_bilingual_locale_BOM')
    effects = dict((key, body) for key, operator, body in ast((ROOT/FX).read_bytes()))
    triggers = dict((key, body) for key, operator, body in ast((ROOT/TR).read_bytes()))
    prefix = 'eon_per_usa_normalization_'
    expected_effects = {prefix+name for name in ('clear_local_request', 'close_request_pair', 'prepare_request', 'accept_request',
        'decline_request', 'withdraw_request', 'daily_update', 'annex_update', 'clear_annexed_country')}
    expected_triggers = {prefix+name for name in ('policy_allowed', 'slot_ready', 'prepare_ready', 'request_pair_owned', 'menu_owned', 'menu_ready', 'withdraw_available')}
    assert set(effects) == expected_effects and set(triggers) == expected_triggers
    passed('exact_nine_effect_and_seven_trigger_helper_inventory')
    for helper in expected_effects|expected_triggers:
        pattern = rb'(?m)^[ \t]*'+helper.encode()+rb'[ \t]*=[ \t]*\{'
        folder = 'scripted_effects' if helper in expected_effects else 'scripted_triggers'
        assert sum(len(re.findall(pattern, path.read_bytes())) for path in (ROOT/'common'/folder).glob('*.txt')) == 1, helper
        passed('sixteen_new_helper_IDs_are_globally_unique')
    for path in (FX, TR, NA, HOOKS, EVENTS):
        nodes = ast((ROOT/path).read_bytes())
        for key, operator, val in rows(nodes):
            if key in expected_effects|expected_triggers: assert isinstance(val, list) or val in ('yes', 'no')
            elif isinstance(val, str) and key.startswith(prefix) and val in ('yes', 'no'):
                raise AssertionError(('Unknown namespace helper', path, key))
        passed('new_scalar_helper_references_resolve_and_keep_native_yes_no_contract')
    raw = (ROOT/EVENT_PATH).read_bytes(); original = baseline_bytes(EVENT_PATH)
    assert event_blocks(raw).keys() == event_blocks(original).keys()
    passed('all_original_Iran_country_and_news_event_IDs_are_retained')
    for suffix in ('a', 'b'):
        before, after = option_raw(original, 'iranian_focus.64', 'iranian_focus.64.'+suffix), option_raw(raw, 'iranian_focus.64', 'iranian_focus.64.'+suffix)
        old_ai = [block for block in blocks(before, 1) if block['key'] == 'ai_chance']
        new_ai = [block for block in blocks(after, 1) if block['key'] == 'ai_chance']
        assert len(old_ai) == len(new_ai) == 1
        assert before[old_ai[0]['start']:old_ai[0]['end']] == after[new_ai[0]['start']:new_ai[0]['end']]
        old_nodes, new_nodes = ast(before)[0][2], ast(after)[0][2]
        assert one(old_nodes, 'name') == one(new_nodes, 'name') and one(old_nodes, 'log') == one(new_nodes, 'log')
        passed('both_original_USA_option_names_logs_and_complete_AI_blocks_remain_raw_exact')
    accept = ast(option_raw(raw, 'iranian_focus.64', 'iranian_focus.64.a'))[0][2]
    decline = ast(option_raw(raw, 'iranian_focus.64', 'iranian_focus.64.b'))[0][2]
    assert one(one(one(accept, 'trigger'), 'custom_trigger_tooltip'), prefix+'menu_ready') == 'yes'
    assert one(accept, prefix+'accept_request') == 'yes'
    assert one(decline, prefix+'decline_request') == 'yes' and not any(key == 'trigger' for key, operator, val in decline)
    assert float(one(one(decline, 'ai_chance'), 'base')) == 1
    passed('existing_accept_has_owned_current_tooltip_gate_and_always_visible_decline_retains_positive_AI')
    reward = focus_reward((ROOT/FOCUS_PATH).read_bytes()); reward_nodes = ast((ROOT/FOCUS_PATH).read_bytes()[reward['start']:reward['end']])[0][2]
    assert one(reward_nodes, prefix+'prepare_request') == 'yes'
    assert not any(key == 'country_event' for key, operator, val in rows(reward_nodes))
    before_reward = focus_reward(baseline_bytes(FOCUS_PATH)); old_reward = ast(baseline_bytes(FOCUS_PATH)[before_reward['start']:before_reward['end']])[0][2]
    assert one(reward_nodes, 'log') == one(old_reward, 'log')
    passed('actual_named_focus_delegates_owned_prepare_without_changing_cost_available_or_AI')
    policy = triggers[prefix+'policy_allowed']
    assert [(key, val) for key, operator, val in policy if key == 'country_exists'] == [('country_exists', 'PER'), ('country_exists', 'USA')]
    for actor, peer in (('PER', 'USA'), ('USA', 'PER')):
        body = one(policy, actor)
        assert one(body, 'exists') == 'yes'
        assert one(one(body, 'NOT'), 'has_war_with') == peer
        assert one(body, 'has_opinion_modifier') == [('target', '=', peer), ('modifier', '=', 'no_diplomatic_ties')]
        passed('fresh_policy_requires_both_current_countries_direct_peace_and_directed_absence_marker')
    for helper in ('emerging_hardline_shiite_are_in_power', 'emerging_moderate_shiite_are_in_power'):
        assert one(one(policy, 'PER'), helper) == 'no'; passed('existing_Iranian_political_predicates_are_retained_without_new_rank_or_ideology_rule')
    prepare = effects[prefix+'prepare_request']; branch = one(prepare, 'if')
    assert one(one(branch, 'limit'), prefix+'prepare_ready') == 'yes'
    assert one(branch, 'set_variable') == [(prefix+'partner', '=', 'USA')]
    usa = one(branch, 'USA'); assert one(usa, 'set_variable') == [(prefix+'partner', '=', 'PER')]
    assert one(usa, 'country_event') == [('id', '=', 'iranian_focus.64'), ('days', '=', '1')]
    assert ('set_country_flag', '=', [('flag', '=', prefix+'live'), ('days', '=', '30'), ('value', '=', '1')]) in usa
    for actor, nodes in (('PER', branch), ('USA', usa)):
        assert ('set_country_flag', '=', prefix+'pending') in nodes and ('set_country_flag', '=', prefix+'request_issued') in nodes
        passed('request_freezes_both_country_IDs_pending_and_permanent_issuance_before_one_delayed_USA_reply')
    owned = triggers[prefix+'request_pair_owned']
    assert {key for key, operator, val in owned} == {'PER', 'USA'}
    for actor, peer in (('PER', 'USA'), ('USA', 'PER')):
        body = one(owned, actor)
        assert ('has_country_flag', '=', prefix+'pending') in body
        assert ('check_variable', '=', [(prefix+'partner', '>', '0')]) in body
        assert ('check_variable', '=', [(prefix+'partner', '=', peer)]) in body
        passed('pair_ownership_requires_own_pending_and_positive_exact_reciprocal_country_IDs')
    menu = triggers[prefix+'menu_owned']
    assert one(menu, 'tag') == 'USA' and one(one(menu, 'ROOT'), 'tag') == 'USA' and one(one(menu, 'FROM'), 'tag') == 'PER'
    assert one(menu, prefix+'request_pair_owned') == 'yes'
    passed('USA_callback_is_bound_to_native_ROOT_USA_FROM_PER_and_owned_fixed_pair')
    committed = one(effects[prefix+'accept_request'], 'if')
    assert one(one(committed, 'limit'), prefix+'menu_ready') == 'yes'
    commands = [row for row in committed if row[0] != 'limit']; assert commands[0] == (prefix+'close_request_pair', '=', 'yes')
    assert ('set_country_flag', '=', 'USA_iranian_friendship') in commands
    assert ('set_country_flag', '=', 'eon_per_usa_relations_restored') in commands
    assert ('set_variable', '=', [('eon_per_usa_relations_partner', '=', 'PER')]) in commands
    per = [val for key, operator, val in commands if key == 'PER' and any(name == 'set_country_flag' for name, op, value in val)]
    assert len(per) == 1 and ('set_country_flag', '=', 'eon_per_usa_relations_restored') in per[0]
    assert ('set_variable', '=', [('eon_per_usa_relations_partner', '=', 'USA')]) in per[0]
    passed('consent_consumes_both_initial_records_before_permanent_receipts_and_national_friendship')
    originals = [('set_temp_variable', '=', [('percent_change', '=', '2.00')]), ('set_temp_variable', '=', [('tag_index', '=', 'USA')]),
        ('set_temp_variable', '=', [('influence_target', '=', 'PER')]), ('change_influence_percentage', '=', 'yes')]
    index = commands.index(originals[0]); assert commands[index:index+4] == originals
    assert commands[-1] == ('PER', '=', [('country_event', '=', [('id', '=', 'iranian_focus.65'), ('days', '=', '1')])])
    passed('exact_existing_two_percent_national_macro_parameters_and_sender_frame_are_retained_once')
    removals = [val for key, operator, val in rows(ast((ROOT/FX).read_bytes())) if key == 'remove_opinion_modifier']
    assert len(removals) == 2 and {tuple(tuple(row) for row in val) for val in removals} == {
        (('target', '=', 'USA'), ('modifier', '=', 'no_diplomatic_ties')), (('target', '=', 'PER'), ('modifier', '=', 'no_diplomatic_ties'))}
    passed('only_two_directed_absence_markers_can_be_removed_and_no_historical_grievances')
    forbidden = {'modify_treasury_effect', 'add_manpower', 'add_equipment_to_stockpile', 'send_equipment', 'create_unit',
        'division_template', 'delete_unit_template_and_units', 'diplomatic_relation', 'remove_ideas', 'add_ideas', 'add_timed_idea'}
    for path in (FX, TR, NA, HOOKS, EVENTS):
        assert not any(key in forbidden for key, operator, val in rows(ast((ROOT/path).read_bytes())))
        passed('normalization_has_no_fees_units_assets_military_access_or_physical_embassy_effects')
    for key, operator, val in rows(ast((ROOT/FX).read_bytes())):
        if key in ('clr_country_flag', 'clear_variable'):
            assert val in {prefix+'pending', prefix+'live', prefix+'cancelled', prefix+'partner'}, val
    assert not any(key.startswith('var:') for key, operator, val in rows(ast((ROOT/FX).read_bytes())))
    passed('cleanup_erases_only_local_initial_fields_never_issuance_receipts_or_arbitrary_partner_scope')
    pair_close = effects[prefix+'close_request_pair']
    for key, operator, branch in pair_close:
        actor = one(one(branch, 'limit'), 'tag'); peer = 'USA' if actor == 'PER' else 'PER'
        local_guard = one(one(branch, 'if'), 'limit'); foreign = one(one(branch, 'if'), peer)
        peer_guard = one(one(foreign, 'if'), 'limit')
        for nodes, expected in ((local_guard, peer), (peer_guard, actor)):
            assert ('has_country_flag', '=', prefix+'pending') in nodes
            assert ('check_variable', '=', [(prefix+'partner', '>', '0')]) in nodes
            assert ('check_variable', '=', [(prefix+'partner', '=', expected)]) in nodes
            passed('counterpart_cleanup_requires_both_local_and_foreign_owned_positive_reciprocal_IDs')
    action = one(one(ast((ROOT/NA).read_bytes()), 'scripted_diplomatic_actions'), prefix+'withdraw_request')
    assert one(action, 'cost') == '0' and one(action, 'requires_acceptance') == one(action, 'show_acceptance_on_action_button') == 'no'
    assert one(action, 'can_be_sent') == [(prefix+'withdraw_available', '=', 'yes')]
    assert one(action, 'complete_effect') == [(prefix+'withdraw_request', '=', 'yes')]
    assert one(action, 'allowed') == [('ROOT', '=', [('tag', '=', 'PER'), ('is_ai', '=', 'no')])]
    assert one(one(triggers[prefix+'withdraw_available'], 'ROOT'), 'tag') == 'PER'
    assert one(triggers[prefix+'withdraw_available'], 'tag') == 'USA'
    passed('one_native_free_human_PER_withdrawal_uses_ROOT_initiator_THIS_USA_and_fresh_pair_gate')
    for actor, body in (('USA', triggers[prefix+'withdraw_available']), ('PER', one(triggers[prefix+'withdraw_available'], 'PER'))):
        assert ('has_country_flag', '=', prefix+'request_issued') in body
        assert ('NOT', '=', [('has_country_flag', '=', 'eon_per_usa_relations_restored')]) in body
        passed('withdrawal_requires_issued_unrestored_ownership_on_both_current_countries')
    hooks = one(ast((ROOT/HOOKS).read_bytes()), 'on_actions')
    assert {key for key, operator, val in hooks} == {'on_daily', 'on_annex', 'on_subject_annexed'}
    assert one(one(hooks, 'on_daily'), 'effect') == [(prefix+'daily_update', '=', 'yes')]
    for hook, victim in (('on_annex', 'FROM'), ('on_subject_annexed', 'ROOT')):
        body = one(one(hooks, hook), 'effect')
        scan = one(body, 'every_country')
        assert one(scan, 'set_temp_variable') == [(prefix+'annexed_partner', '=', victim)]
        assert one(body, victim) == [(prefix+'clear_annexed_country', '=', 'yes')]
        passed('both_native_annex_frames_pass_explicit_annexed_identity_and_clear_only_initial_request_fields')
    notices = {one(body, 'id'): body for key, operator, body in ast((ROOT/EVENTS).read_bytes()) if key == 'country_event'}
    assert set(notices) == {'eon_per_usa_normalization.1', 'eon_per_usa_normalization.2'}
    for identity, body in notices.items():
        assert one(body, 'is_triggered_only') == 'yes'
        assert [row for row in one(body, 'option') if row[0] not in ('name', 'ai_chance')] == []
        pattern = rb'\bid\s*=\s*'+re.escape(identity.encode())+rb'\s*(?:#|\r?$)'
        assert sum(len(re.findall(pattern, path.read_bytes(), re.M)) for path in (ROOT/'events').glob('*.txt')) == 1
        passed('two_new_notice_IDs_are_globally_unique_inert_information_only')
    locales = {}
    for language in ('english', 'russian'):
        raw_locale = (ROOT/f'localisation/{language}/eon_per_usa_normalization_l_{language}.yml').read_bytes()
        text = raw_locale.decode('utf-8-sig'); assert text.splitlines()[0] == 'l_'+language+':'
        entries = [re.fullmatch(r' ([\w.]+):(?:\d+)? "(.*)"', line).groups() for line in text.splitlines()[1:]]
        assert len(entries) == len(dict(entries)) == 11; locales[language] = dict(entries)
        passed('eleven_unique_new_locale_keys_in_each_declared_language')
        legacy_text = (ROOT/f'localisation/{language}/MD_focus_PER_l_{language}.yml').read_text(encoding='utf-8-sig')
        legacy_entries = dict(re.findall(r'^ ([\w.]+):(?:\d+)? "(.*)"$', legacy_text, re.M))
        ai = legacy_entries['PER_USA_ai_better_TT']
        assert '20' not in ai and '§Y' not in ai
        assert ('Sanctions require a separate review.' in ai) if language == 'english' else ('Санкции требуют отдельного рассмотрения.' in ai)
        passed('named_existing_AI_tooltip_promises_no_twenty_percent_or_automatic_sanctions_removal')
    assert locales['english'].keys() == locales['russian'].keys()
    for key in locales['english']:
        assert re.findall(r'\[.*?\]', locales['english'][key]) == re.findall(r'\[.*?\]', locales['russian'][key])
        passed('new_bilingual_placeholder_references_match')
    for path in (FX, TR, NA, EVENTS):
        for key, operator, val in rows(ast((ROOT/path).read_bytes())):
            if key in ('name', 'title', 'desc', 'tooltip', 'send_description', 'custom_effect_tooltip') and isinstance(val, str) and val.startswith(('eon_per_usa_normalization.', prefix)):
                assert val in locales['english'], (path, val)
        passed('new_notice_action_and_tooltip_localization_references_resolve')
    for helper in ('prepare_tt', 'menu_ready_tt', 'restoration_tt'):
        assert prefix+helper in locales['english']; passed('owned_focus_response_and_preview_tooltips_are_bilingual')
    old_actions = []
    for path in subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, '--', 'common/scripted_diplomatic_actions'], cwd=ROOT).decode().splitlines():
        for key, operator, val in ast(baseline_bytes(path)):
            if key == 'scripted_diplomatic_actions': old_actions.extend(name for name, op, body in val)
    current_actions = []
    for path in (ROOT/'common/scripted_diplomatic_actions').glob('*.txt'):
        for key, operator, val in ast(path.read_bytes()):
            if key == 'scripted_diplomatic_actions': current_actions.extend(name for name, op, body in val)
    assert len(old_actions) == len(set(old_actions)) == 75 and len(current_actions) == len(set(current_actions)) == 76
    assert set(current_actions)-set(old_actions) == NEW_ACTION_IDS and set(old_actions) <= set(current_actions)
    passed('all_seventy_five_previous_action_IDs_plus_one_new_unique_withdrawal_are_retained')
    protected = ['common/scripted_triggers/00_political_triggers.txt', 'common/scripted_effects/00_influence_scripted_effects.txt',
        'common/ai_strategy/USA.txt', 'common/opinion_modifiers/generic_modifiers.txt']
    protected += subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, '--', 'common/scripted_guis', 'common/decisions'], cwd=ROOT).decode().splitlines()
    old_game = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, '--', 'common', 'events', 'localisation'], cwd=ROOT).decode().splitlines()
    protected += [path for path in old_game if any(stem in path for stem in ('eon_services_', 'eon_foreign_cash_', 'eon_foreign_equipment_', 'eon_defence_formation_', 'eon_advisers_', 'eon_support_request_'))]
    for path in sorted(set(protected)):
        assert game_before(path, (ROOT/path).read_bytes()) == baseline_bytes(path), path
    passed('all_previous_channels_current_USA_AI_political_macros_opinions_GUI_and_sanction_decisions_remain_raw_exact')
    for path in sorted(EXISTING):
        try: package23_original_bytes(path, (ROOT/path).read_bytes()+b'# unowned memory mutation\n')
        except AssertionError: pass
        else: raise AssertionError(('Unowned gameplay suffix accepted', path))
        passed('memory_only_whole_gameplay_suffix_mutation_rejected'); boundary_groups.add('memory_only_whole_gameplay_suffix_mutation_rejected')
    assert set(HISTORICAL_SOURCE_EDITS) == {f'tools/validation/diplomacy_package_{index:02}/test_source.py' for index in range(2, 23)}
    for path in HISTORICAL_SOURCE_EDITS:
        current, before = (ROOT/path).read_bytes(), baseline_bytes(path)
        assert package23_original_validator_bytes(path, current) == before
        counters = lambda data: [line for line in data.splitlines() if b'groups[' in line and b'+=' in line or b'passed(' in line]
        assert counters(test_before(path, current)) == counters(before)
        passed('twenty_one_literal_whole_historical_source_journals_preserve_original_assertion_counter_lines')
        try: package23_original_validator_bytes(path, current+b'# unowned memory mutation\n')
        except AssertionError: pass
        else: raise AssertionError(('Unowned historical validator suffix accepted', path))
        passed('memory_only_whole_historical_validator_suffix_mutation_rejected'); boundary_groups.add('memory_only_whole_historical_validator_suffix_mutation_rejected')
    public_paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, '--', 'tools/validation'], cwd=ROOT).decode().splitlines()
    untouched = [path for path in public_paths if path not in HISTORICAL_SOURCE_EDITS]
    behavior = [path for path in untouched if path.endswith('.py') and Path(path).name != 'test_source.py']
    assert (len(public_paths), len(untouched), len(behavior)) == (98, 77, 55)
    for path in untouched: assert test_before(path, (ROOT/path).read_bytes()) == baseline_bytes(path), path
    passed('fifty_five_prior_behavior_helper_runner_and_seventy_seven_other_public_files_remain_raw_byte_exact')
    installed = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV')
    effects_doc = (installed/'documentation/effects_documentation.md').read_text(encoding='utf-8-sig')
    triggers_doc = (installed/'documentation/triggers_documentation.md').read_text(encoding='utf-8-sig')
    for helper in ('country_event', 'set_country_flag', 'set_variable', 'clr_country_flag', 'clear_variable', 'remove_opinion_modifier'):
        assert '\n## '+helper+'\n' in effects_doc; passed('installed_native_effect_declarations_verify_supported_primitives_not_engine_completion')
    for helper in ('country_exists', 'has_country_flag', 'has_opinion_modifier', 'has_war_with', 'is_in_array', 'exists'):
        assert '\n## '+helper+'\n' in triggers_doc; passed('installed_native_trigger_declarations_verify_explicit_country_and_policy_queries')
    native_action = (installed/'common/scripted_diplomatic_actions/scripted_diplomatic_actions.txt').read_text(encoding='utf-8-sig')
    assert 'root is the initiator of action and this is the target country' in native_action
    passed('native_action_ROOT_initiator_THIS_target_frame_is_primary_metadata')
    boundary_cases = sum(groups[key] for key in boundary_groups)
    print(json.dumps({'all_passed': True, 'baseline': BASELINE, 'source_cases': sum(groups.values()),
        'source_API_cases': sum(groups.values())-boundary_cases, 'source_byte_adapter_boundary_cases': boundary_cases, 'groups': dict(groups),
        'source_sha256': {path: hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in SOURCE_PATHS},
        'protected_dependencies_sha256': {path: hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in ('common/scripted_triggers/00_political_triggers.txt', 'tools/validation/diplomacy_package_22/test_request.py')},
        'historical_source_adapters': len(HISTORICAL_SOURCE_EDITS), 'prior_behavior_helper_runner_raw_byte_files': len(behavior),
        'prior_other_public_raw_byte_files': len(untouched), 'bilingual_locale_keys': len(locales['english']),
        'named_existing_locale_rows': len(LEGACY_LOCALE_KEYS)*2, 'new_historical_caller_projection': False,
        'prior_scope': 'unchanged_children_with_historical_AB4_caller_view', 'native_runtime': False,
        'native_physical_mission_presence_proven': False, 'immutable_event_generation_proven': False,
        'proof_scope': 'exact bounded current national normalization source, current dependency bytes and literal prior source inverses; native campaign, physical missions, save/load and callback generations unverified'}, indent=2))

if __name__ == '__main__': main()
