from pathlib import Path
import re, hashlib, json, subprocess
from functools import lru_cache
from _support import ROOT as root, baseline
TOKEN=re.compile(rb'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|[=<>!]+|[^\s{}=<>!#"]+')
def blocks(data):
    tokens=[m for m in TOKEN.finditer(data) if not m[0].startswith(b'#')]; stack=[]; result=[]
    for i,t in enumerate(tokens):
        if t[0]==b'{':
            b={'key':tokens[i-2][0].decode().lstrip('\ufeff'),'start':tokens[i-2].start(),'brace':t.start(),'depth':len(stack),'parent':stack[-1]['key'] if stack else None}
            stack.append(b); result.append(b)
        elif t[0]==b'}':
            assert stack; stack.pop()['end']=t.end()
    assert not stack; return result
def selected(data,key,parent,index=0):
    return [b for b in blocks(data) if b['key']==key and b['parent']==parent][index]
def restore_body(data,before,key,parent,index=0):
    now=selected(data,key,parent,index); old=selected(before,key,parent,index)
    return data[:now['brace']+1]+before[old['brace']+1:old['end']-1]+data[now['end']-1:]

PACKAGE05_BASELINE = '688f1116fbcb377215181edca6af50f36538532e'
package05_receipt = []


@lru_cache(maxsize=None)
def package05_before(path):
    return subprocess.check_output(['git', 'show', PACKAGE05_BASELINE + ':' + path], cwd=root)


def without_package05(path, after):
    """Prove only named 05 ranges changed, then retain the historical 01 proof."""
    scoped = {'common/scripted_guis/01_energy_gui.txt',
              'events/00_Energy_market_events.txt',
              'common/scripted_effects/eon_energy_contract_effects.txt',
              'localisation/english/eon_energy_contract_l_english.yml',
              'localisation/russian/eon_energy_contract_l_russian.yml'}
    if path not in scoped:
        return after
    old = package05_before(path)
    assert old.startswith(b'\xef\xbb\xbf') == after.startswith(b'\xef\xbb\xbf'), path
    assert old.endswith(b'\n') == after.endswith(b'\n'), path
    if b'\r\n' in old:
        assert after.count(b'\r\n') == after.count(b'\n'), path
    else:
        assert b'\r' not in after, path
    after.decode('utf-8-sig')
    restored = after
    if path.endswith('01_energy_gui.txt'):
        added = [b for b in blocks(restored)
                 if b['key'] == 'country_view_flag_button_click_enabled'
                 and b['parent'] == 'triggers' and b['depth'] == 3]
        assert not any(b['key'] == 'country_view_flag_button_click_enabled' for b in blocks(old))
        assert len(added) == 1, 'Package05 partner selection guard identity changed'
        block = added[0]
        start = restored.rfind(b'\n', 0, block['start']) + 1
        assert restored[start:block['start']] == b'\t\t\t'
        assert restored[block['end']:block['end'] + 1] == b'\n'
        restored = restored[:start] + restored[block['end'] + 1:]
        for key, parent, index in (
            ('confirm_energy_sell_click_enabled', 'triggers', 0),
            ('confirm_energy_sell_click', 'effects', 0),
            ('country_view_flag_button_click', 'effects', 0),
            ('country_list_flag_button_click', 'effects', 0),
        ):
            restored = restore_body(restored, old, key, parent, index)
    elif path.endswith('00_Energy_market_events.txt'):
        def event_map(data):
            return {re.search(rb'\bid\s*=\s*([^\s{}]+)', data[b['start']:b['end']])[1]: b
                    for b in blocks(data) if b['key'] == 'country_event' and b['depth'] == 0}
        prior, current = event_map(old), event_map(restored)
        assert prior.keys() == current.keys(), 'Package05 existing event IDs changed'
        for ident, block in sorted(current.items(), key=lambda row: row[1]['start'], reverse=True):
            if ident in (b'energy_selling.1', b'energy_selling.4'):
                original = prior[ident]
                restored = restored[:block['start']] + old[original['start']:original['end']] + restored[block['end']:]
    elif path.endswith('eon_energy_contract_effects.txt'):
        for key in ('eon_energy_clear_pending', 'eon_energy_invalidate_pair_pending',
                    'eon_energy_send_offer', 'eon_energy_validate_offer',
                    'eon_energy_finish_response', 'eon_energy_accept_offer'):
            restored = restore_body(restored, old, key, None)
    else:
        pattern = rb'(?m)^ eon_energy_offer_cancelled_desc:0 "[^\r\n]*"'
        original, current = re.findall(pattern, old), re.findall(pattern, restored)
        assert len(original) == len(current) == 1, path
        restored = restored.replace(current[0], original[0], 1)
    assert restored == old, ('Unrelated package05 bytes changed', path)
    package05_receipt.append({'path': path, 'baseline': PACKAGE05_BASELINE,
                              'owned_ranges_only': True})
    return restored

files=['common/scripted_guis/01_energy_gui.txt','events/00_Energy_market_events.txt','common/on_actions/00_costili.txt']
receipt=[]
for rel in files:
    before=baseline(rel); actual=(root/rel).read_bytes(); after=without_package05(rel,actual)
    assert before.startswith(b'\xef\xbb\xbf')==after.startswith(b'\xef\xbb\xbf')
    assert b'\r' not in after
    blocks(after)
    if rel.endswith('01_energy_gui.txt'):
        restored=restore_body(after,before,'confirm_energy_sell_click','effects')
        restored=restore_body(restored,before,'confirm_energy_sell_click_enabled','triggers')
        # Package 04 checks these exact later deltas against bb018ea1 separately.
        for key in ('increase_energy_ammount_number_click_enabled',
                    'decrease_energy_ammount_number_click_enabled'):
            restored=restore_body(restored,before,key,'triggers')
        restored=restore_body(restored,before,'country_list_flag_button_click','effects',0)
        assert restored==before,'Unrelated GUI bytes changed'
    elif rel.endswith('00_Energy_market_events.txt'):
        def eventid(data,b):
            return re.search(rb'\bid\s*=\s*([^\s{}]+)',data[b['start']:b['end']])[1]
        old={eventid(before,b):b for b in blocks(before) if b['key']=='country_event' and b['depth']==0}
        new={eventid(after,b):b for b in blocks(after) if b['key']=='country_event' and b['depth']==0}
        assert old.keys()==new.keys(),'Event ID migration forbidden'
        restored=after
        for eid,b in sorted(new.items(),key=lambda row:row[1]['start'],reverse=True):
            if eid in {f'energy_selling.{i}'.encode() for i in range(1,6)}:
                original=old[eid]; restored=restored[:b['start']]+before[original['start']:original['end']]+restored[b['end']:]
        if restored!=before:
            first=next(i for i,(a,b) in enumerate(zip(restored,before)) if a!=b)
            raise AssertionError(('Other events changed',first,restored[first-80:first+180],before[first-80:first+180]))
    else:
        restored=after
        # Later package 02 appends three independently checked pair cleanups.
        # Remove exactly those additions before proving package 01's old boundary.
        # Package 02 checks their full delta against d4ec4a02 separately.
        for target in (b'FROM',b'ROOT'):
            addition=(b'\n\t\t\t\t\tset_temp_variable = { eon_trade_treaty_partner = '+target+b' }'
                      b'\n\t\t\t\t\teon_trade_treaty_cleanup_annexed_pair = yes'
                      b'\n\t\t\t\t\tset_temp_variable = { eon_investment_treaty_partner = '+target+b' }'
                      b'\n\t\t\t\t\teon_investment_treaty_cleanup_annexed_pair = yes'
                      b'\n\t\t\t\t\tset_temp_variable = { eon_investment_annexed_partner = '+target+b' }'
                      b'\n\t\t\t\t\teon_investment_project_cleanup_annexed_pair = yes')
            if addition in restored:
                assert restored.count(addition)==1; restored=restored.replace(addition,b'')
        addition=(b'\n\t\t\t\teon_trade_treaty_clear_pending = yes'
                  b'\n\t\t\t\teon_investment_treaty_clear_pending = yes'
                  b'\n\t\t\t\teon_investment_clear_offer = yes')
        if addition in restored:
            assert restored.count(addition)==2; restored=restored.replace(addition,b'')
        for target in (b'FROM',b'ROOT'):
            addition=b'\n\t\t\t\t\tset_temp_variable = { eon_energy_pair_partner = '+target+b' }\n\t\t\t\t\teon_energy_clear_pair_pending = yes\n\t\t\t\t\teon_energy_framework_cleanup_annexed_pair = yes'
            assert restored.count(addition)==1; restored=restored.replace(addition,b'')
        addition=b'\n\t\t\t\teon_energy_clear_pending = yes\n\t\t\t\teon_energy_framework_clear_pending = yes'
        assert restored.count(addition)==2; restored=restored.replace(addition,b'')
        original=next(b for b in blocks(before) if b['key']=='on_monthly' and b'check_variable = { energy_balance < -1 }' in before[b['start']:b['end']])
        current=next(b for b in blocks(restored) if b['key']=='on_monthly' and b'check_variable = { energy_balance < -1 }' in restored[b['start']:b['end']])
        restored=restored[:current['start']]+before[original['start']:original['end']]+restored[current['end']:]
        assert restored==before,'Unrelated on_actions bytes changed'
    receipt.append({'path':rel,'before_sha256':hashlib.sha256(before).hexdigest(),'after_sha256':hashlib.sha256(actual).hexdigest(),'bom_preserved':True,'lf_preserved':True,'unrelated_bytes_exact':True})
for rel in ['common/scripted_effects/eon_energy_contract_effects.txt','localisation/english/eon_energy_contract_l_english.yml','localisation/russian/eon_energy_contract_l_russian.yml']:
    data=(root/rel).read_bytes()
    without_package05(rel, data)
    if rel.endswith('.yml'):
        assert data.startswith(b'\xef\xbb\xbf'); assert data.count(b'\r\n')==data.count(b'\n')
    else: blocks(data)
    receipt.append({'path':rel,'new':True,'sha256':hashlib.sha256(data).hexdigest(),'bom':data.startswith(b'\xef\xbb\xbf'),'eol':'CRLF' if b'\r\n' in data else 'LF'})
def loc_keys(lang):
    text=(root/f'localisation/{lang}/eon_energy_contract_l_{lang}.yml').read_text(encoding='utf-8-sig')
    assert '\ufffd' not in text
    result={}
    for line in text.splitlines()[1:]:
        m=re.fullmatch(r' ([a-zA-Z0-9_.]+):0 "(.*)"',line); assert m,line
        assert m[1] not in result; result[m[1]]=m[2]
    return result
en=loc_keys('english'); ru=loc_keys('russian'); assert en.keys()==ru.keys()
for key in en:
    assert re.findall(r'\[.*?\]',en[key])==re.findall(r'\[.*?\]',ru[key]),('Localization placeholder mismatch',key)
report={'method':'exact reversible byte comparison of owned blocks, braces/IDs/BOM/EOL and localization placeholders; not engine parser','files':receipt,'localization_keys':len(en),'ru_placeholders_equal_en':True,'later_package05_boundaries':package05_receipt}

# Preserve byte format in every existing gameplay file touched by this package.
existing = [
    'common/decisions/China.txt', 'common/factions/rules/joining_rules.txt',
    'common/on_actions/00_on_actions.txt', 'common/on_actions/00_costili.txt',
    'common/scripted_diplomatic_actions/00_scripted_diplomatic_actions.txt',
    'common/scripted_diplomatic_actions/MDDC_energy_contract_scripted_diplomatic_actions.txt',
    'common/scripted_effects/00_CSTO_effects.txt', 'common/scripted_effects/00_NATO_effects.txt',
    'common/scripted_guis/01_energy_gui.txt', 'events/00_Energy_market_events.txt',
    'localisation/english/MDC_diplomatic_actions_l_english.yml',
    'localisation/english/MDC_scripted_diplomatic_actions_l_english.yml',
    'localisation/russian/MDC_diplomatic_actions_l_russian.yml',
    'localisation/russian/MDDC_scripted_diplomatic_actions_l_russian.yml',
]
for rel in existing:
    before, after = baseline(rel), (root / rel).read_bytes()
    assert before.startswith(b'\xef\xbb\xbf') == after.startswith(b'\xef\xbb\xbf'), ('BOM changed', rel)
    assert before.endswith(b'\n') == after.endswith(b'\n'), ('EOF changed', rel)
    if b'\r\n' in before:
        assert after.count(b'\r\n') == after.count(b'\n'), ('Mixed/non-original EOL', rel)
    else:
        assert b'\r' not in after, ('Original LF changed', rel)
    after.decode('utf-8-sig')
    if rel.endswith('.txt'): blocks(after)

new_scripts = [
    'common/scripted_effects/eon_energy_contract_effects.txt',
    'common/scripted_effects/eon_energy_framework_effects.txt',
    'common/scripted_triggers/eon_energy_framework_triggers.txt',
]
for rel in new_scripts:
    blocks((root / rel).read_bytes())

native_rel = 'common/on_actions/00_on_actions.txt'
native_before, native_after = baseline(native_rel), (root / native_rel).read_bytes()
# The source also contains an earlier empty hook; preserve it and select the
# last, meaningful callback, as the alliance source model does.
assert restore_body(native_after, native_before, 'on_leave_faction', 'on_actions', -1) == native_before, 'Unrelated native on_actions changed'

# All scripted action IDs must be unique across the whole existing action layer.
action_ids = []
for p in sorted((root / 'common/scripted_diplomatic_actions').glob('*.txt')):
    action_ids.extend(b['key'] for b in blocks(p.read_bytes())
                      if b['parent'] == 'scripted_diplomatic_actions' and b['depth'] == 1)
assert len(action_ids) == len(set(action_ids)), ('Duplicate action IDs', action_ids)
assert action_ids.count('negotiate_operative_release') == 1
assert action_ids.count('negotiate_operative_exchange') == 1

def locale_keys(path):
    text = path.read_text(encoding='utf-8-sig')
    found = {}
    for line in text.splitlines():
        m = re.match(r'\s+([\w.]+):(?:\d+)?\s*"(.*)"\s*$', line)
        if m:
            assert m[1] not in found, ('Duplicate key within file', path, m[1])
            found[m[1]] = m[2]
    return found

new_keys = {}
for stem in ('eon_diplomacy_contracts', 'eon_energy_contract'):
    pair = {}
    for lang in ('english', 'russian'):
        p = root / 'localisation' / lang / (stem + '_l_' + lang + '.yml')
        assert p.read_bytes().startswith(b'\xef\xbb\xbf'), ('New locale lacks BOM', p)
        pair[lang] = locale_keys(p)
    assert pair['english'].keys() == pair['russian'].keys()
    for key in pair['english']:
        assert re.findall(r'\[.*?\]', pair['english'][key]) == re.findall(r'\[.*?\]', pair['russian'][key]), key
    new_keys.update(pair['english'])

for lang in ('english', 'russian'):
    # Check only the added/migrated keys, preserving inherited unrelated duplicates.
    counts = {}
    for p in (root / 'localisation' / lang).glob('*.yml'):
        for line in p.read_text(encoding='utf-8-sig').splitlines():
            m = re.match(r'\s+([\w.]+):(?:\d+)?\s*"', line)
            if m: counts[m[1]] = counts.get(m[1], 0) + 1
    exchange = ['base_negotiate_operative_exchange', 'NEGOTIATE_OPERATIVE_EXCHANGE_TITLE',
                'NEGOTIATE_OPERATIVE_EXCHANGE_ACTION_DESC', 'DIPLO_ACTION_NEGOTIATE_OPERATIVE_EXCHANGE_DESC',
                'DIPLO_ACTION_NEGOTIATE_OPERATIVE_EXCHANGE_ACCEPT_TITLE', 'DIPLO_ACTION_NEGOTIATE_OPERATIVE_EXCHANGE_ACCEPT_DESC',
                'DIPLO_ACTION_NEGOTIATE_OPERATIVE_EXCHANGE_REJECT_TITLE', 'DIPLO_ACTION_NEGOTIATE_OPERATIVE_EXCHANGE_REJECT_DESC']
    for key in list(new_keys) + exchange:
        assert counts.get(key) == 1, ('Missing/duplicate added key', lang, key, counts.get(key))
    for key in ['NEGOTIATE_OPERATIVE_RELEASE_TITLE', 'NEGOTIATE_OPERATIVE_RELEASE_ACTION_DESC',
                'DIPLO_ACTION_NEGOTIATE_OPERATIVE_RELEASE_DESC', 'DIPLO_ACTION_NEGOTIATE_OPERATIVE_RELEASE_ACCEPT_TITLE',
                'DIPLO_ACTION_NEGOTIATE_OPERATIVE_RELEASE_ACCEPT_DESC', 'DIPLO_ACTION_NEGOTIATE_OPERATIVE_RELEASE_REJECT_TITLE',
                'DIPLO_ACTION_NEGOTIATE_OPERATIVE_RELEASE_REJECT_DESC']:
        assert counts.get(key) == 1, ('Ransom key migration incomplete', lang, key)

report.update(existing_formats_preserved=len(existing), new_scripts_balanced=len(new_scripts),
              unique_scripted_action_ids=len(action_ids), added_locale_keys_per_language=len(new_keys),
              added_exchange_keys_per_language=len(exchange))
print(json.dumps(report, indent=2))
