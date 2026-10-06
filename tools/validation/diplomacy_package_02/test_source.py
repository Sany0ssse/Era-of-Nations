"""Exact owned-source boundaries and format checks; not an engine parser."""
import hashlib
import json
import re
import subprocess

from _support import ROOT, baseline

TOKEN = re.compile(rb'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|[=<>!]+|[^\s{}=<>!#"]+')


def blocks(data):
    tokens = [m for m in TOKEN.finditer(data) if not m[0].startswith(b'#')]
    stack, result = [], []
    for i, token in enumerate(tokens):
        if token[0] == b'{':
            item = {'key': tokens[i - 2][0].decode().lstrip('\ufeff'),
                    'start': tokens[i - 2].start(), 'depth': len(stack),
                    'parent': stack[-1]['key'] if stack else None}
            stack.append(item); result.append(item)
        elif token[0] == b'}':
            assert stack, 'Extra closing brace'
            stack.pop()['end'] = token.end()
    assert not stack, 'Unclosed block'
    return result


def restore_blocks(after, before, selector):
    current = {selector(after, b): b for b in blocks(after) if selector(after, b)}
    original = {selector(before, b): b for b in blocks(before) if selector(before, b)}
    assert current.keys() == original.keys(), (current.keys(), original.keys())
    for name, block in sorted(current.items(), key=lambda row: row[1]['start'], reverse=True):
        old = original[name]
        after = after[:block['start']] + before[old['start']:old['end']] + after[block['end']:]
    return after


def named(names, parent=None, depth=0):
    return lambda data, b: b['key'] if (b['key'] in names and b['parent'] == parent
                                      and b['depth'] == depth) else None


def check_format(before, after):
    assert before.startswith(b'\xef\xbb\xbf') == after.startswith(b'\xef\xbb\xbf')
    def eol(data):
        return ('CRLF' if b'\r\n' in data else 'LF',
                bool(data.replace(b'\r\n', b'').count(b'\n')),
                bool(data.replace(b'\r\n', b'').count(b'\r')))
    assert eol(before) == eol(after), 'Changed/mixed line endings'
    assert before.endswith(b'\n') == after.endswith(b'\n'), 'Changed EOF newline'
    after.decode('utf-8-sig')


owned = {
    'common/scripted_diplomatic_actions/00_scripted_diplomatic_actions.txt': named(
        {'propose_improved_trade_agreement', 'cancel_trade_agreement',
         'propose_mutual_investment_treaty', 'cancel_mutual_investment_treaty'},
        'scripted_diplomatic_actions', 1),
    'common/scripted_effects/00_investment_scripted_effects.txt': named(
        {'get_available_project', 'start_project_two', 'end_project'}),
    'common/scripted_guis/01_investment_scripted_gui.txt': lambda data, b: b['key'] if (
        b['depth'] == 3 and ((b['key'] == 'AC_build_button_click' and b['parent'] == 'effects')
                            or (b['key'] == 'AC_build_button_click_enabled' and b['parent'] == 'triggers'))
    ) else None,
    'common/scripted_triggers/00_investment_scripted_triggers.txt': named(
        {'currently_is_considering_a_project'}),
    'common/scripted_effects/00_ai_investment_scripted_effects.txt': named({
        'invest_cic', 'invest_mic', 'invest_nic', 'invest_infra', 'invest_offices',
        'invest_anti_air', 'invest_radar', 'invest_air_bases', 'invest_fuel_silo',
        'invest_internet_station', 'invest_biofuel_refinery', 'invest_fossil_powerplant',
        'invest_nuclear_powerplant', 'invest_agriculture_district', 'invest_rubber_refinery'}),
}


def event_selector(data, block):
    if block['key'] != 'country_event' or block['depth'] != 0:
        return None
    event_id = re.search(rb'\bid\s*=\s*([^\s{}]+)', data[block['start']:block['end']])[1].decode()
    return event_id if event_id in {'AC_event.3', 'AC_event.10', 'AC_event.11', 'AC_event.500'} else None


owned['events/00_AC_events.txt'] = event_selector
# Package 06 independently protects its debt block against the exact published
# package05 source. Restore only that later block before applying package02 bounds.
PACKAGE06_BASELINE = '551d7100f6c35cd062a36520f6a7eed199b13a2e'
receipt = []
for path, selector in owned.items():
    before, actual = baseline(path), (ROOT / path).read_bytes()
    check_format(before, actual)
    after = actual
    if path == 'common/scripted_diplomatic_actions/00_scripted_diplomatic_actions.txt':
        later = subprocess.check_output(['git', 'show', PACKAGE06_BASELINE + ':' + path], cwd=ROOT)
        after = restore_blocks(after, later, named({'diplo_action_assume_debt'}, 'scripted_diplomatic_actions', 1))
    assert restore_blocks(after, before, selector) == before, 'Unrelated bytes changed: ' + path
    receipt.append({'path': path, 'unrelated_bytes_exact': True,
                    'sha256': hashlib.sha256(actual).hexdigest()})

path = 'common/on_actions/00_costili.txt'
before, after = baseline(path), (ROOT / path).read_bytes()
check_format(before, after)
restored = after
for target in (b'FROM', b'ROOT'):
    addition = (b'\n\t\t\t\t\tset_temp_variable = { eon_trade_treaty_partner = ' + target + b' }'
                b'\n\t\t\t\t\teon_trade_treaty_cleanup_annexed_pair = yes'
                b'\n\t\t\t\t\tset_temp_variable = { eon_investment_treaty_partner = ' + target + b' }'
                b'\n\t\t\t\t\teon_investment_treaty_cleanup_annexed_pair = yes'
                b'\n\t\t\t\t\tset_temp_variable = { eon_investment_annexed_partner = ' + target + b' }'
                b'\n\t\t\t\t\teon_investment_project_cleanup_annexed_pair = yes')
    anchor = b'eon_energy_framework_cleanup_annexed_pair = yes' + addition
    assert restored.count(anchor) == 1, 'Missing/duplicate ordered annex cleanup'
    restored = restored.replace(addition, b'')
addition = (b'\n\t\t\t\teon_trade_treaty_clear_pending = yes'
            b'\n\t\t\t\teon_investment_treaty_clear_pending = yes'
            b'\n\t\t\t\teon_investment_clear_offer = yes')
assert restored.count(b'eon_energy_framework_clear_pending = yes' + addition) == 2
restored = restored.replace(addition, b'')
assert restored == before, 'Unrelated annex/on_actions bytes changed'
receipt.append({'path': path, 'unrelated_bytes_exact': True,
                'sha256': hashlib.sha256(after).hexdigest()})

for language in ('english', 'russian'):
    path = 'localisation/' + language + '/MD_investments_l_' + language + '.yml'
    before, after = baseline(path), (ROOT / path).read_bytes()
    check_format(before, after)
    pattern = rb'(?m)^ AC_event\.1\.d:.*$'
    old = re.findall(pattern, before); new = re.findall(pattern, after)
    assert len(old) == len(new) == 1
    assert after.replace(new[0], old[0]) == before, 'Unrelated project localisation changed'
    receipt.append({'path': path, 'unrelated_bytes_exact': True,
                    'sha256': hashlib.sha256(after).hexdigest()})

# Existing storyline helpers and all 332 callers remain outside this package.
assert baseline('common/scripted_effects/00_economic_effects.txt') == (
    ROOT / 'common/scripted_effects/00_economic_effects.txt').read_bytes()

new_keys = {}
for stem in ('eon_trade_treaty', 'eon_investment_treaty', 'eon_investment_project'):
    for folder in ('scripted_effects', 'scripted_triggers'):
        path = ROOT / 'common' / folder / (stem + '_' + folder.removeprefix('scripted_') + '.txt')
        data = path.read_bytes(); blocks(data); data.decode('utf-8-sig')
    pair = {}
    for language in ('english', 'russian'):
        path = ROOT / 'localisation' / language / (stem + '_l_' + language + '.yml')
        data = path.read_bytes(); assert data.startswith(b'\xef\xbb\xbf')
        text = data.decode('utf-8-sig'); assert '\ufffd' not in text
        assert text.splitlines()[0] == 'l_' + language + ':'
        entries = [re.fullmatch(r' ([\w.]+):(?:\d+)? "(.*)"', line).groups()
                   for line in text.splitlines()[1:]]
        assert len(entries) == len(text.splitlines()) - 1 and len(entries) == len(dict(entries))
        pair[language] = dict(entries)
    assert pair['english'].keys() == pair['russian'].keys()
    for key in pair['english']:
        assert re.findall(r'\[.*?\]', pair['english'][key]) == re.findall(r'\[.*?\]', pair['russian'][key])
    new_keys.update(pair['english'])

blocks((ROOT / 'common/scripted_localisation/eon_investment_project_scripted_localisation.txt').read_bytes())
for language in ('english', 'russian'):
    counts = dict.fromkeys(new_keys, 0)
    for path in (ROOT / 'localisation' / language).glob('*.yml'):
        for key in re.findall(r'^\s+([\w.]+):', path.read_text(encoding='utf-8-sig'), re.M):
            if key in counts: counts[key] += 1
    assert all(n == 1 for n in counts.values()), ('Missing/duplicate new locale', language, counts)

actions = [b['key'] for path in (ROOT / 'common/scripted_diplomatic_actions').glob('*.txt')
           for b in blocks(path.read_bytes()) if b['parent'] == 'scripted_diplomatic_actions' and b['depth'] == 1]
# Package 03 adds one separately validated ordinary-alliance action. Keep the
# original count and uniqueness checks when running an older package checkout.
assert len(actions) == len(set(actions)) == (54 + actions.count('eon_propose_defensive_alliance')
                                           + actions.count('eon_withdraw_energy_offer')
                                           + actions.count('eon_resume_energy_counter_offer')
                                           + actions.count('eon_withdraw_economic_aid')
                                           + sum(actions.count(key) for key in (
                                               'eon_open_economic_consultations',
                                               'eon_withdraw_consultation_request',
                                               'eon_end_economic_consultations',
                                               'eon_consultation_offer_economic_aid',
                                               'eon_request_war_mediation', 'eon_withdraw_mediation',
                                               'eon_withdraw_antiterror_proposal', 'eon_ammo_withdraw_offer')))
print(json.dumps({'all_passed': True, 'method': 'exact reversible source boundaries and format/locale/ID checks',
                  'owned_existing_files': receipt, 'new_locale_keys_per_language': len(new_keys),
                  'unique_action_ids': len(actions), 'not_proven': 'HOI4 engine parsing, UI or campaign'}, indent=2))
