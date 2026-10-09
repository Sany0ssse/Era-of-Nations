"""Exact source islands and retained identities; no native compilation claim."""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import subprocess
import sys
import model as b
from model import m

ROOT=b.ROOT
sys.path.insert(0, str(ROOT / 'tools/validation/debt_default_accounting'))
from byte_compat import restore_before_default_repair
BASE='58b27099dc9fdf0eda383fd917167f015564c529'
journal=json.loads((Path(__file__).parent/'_source_islands.json').read_text(encoding='utf-8-sig'))
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def blob(path): return subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT)
def reconstruct(before,entry):
    assert sha(before)==entry['before'],'Baseline drift'
    edits=sorted(entry['edits'],key=lambda e:(e['start'],e['end']))
    for index,e in enumerate(edits):
        assert before[e['start']:e['end']]==bytes.fromhex(e['before'])
        assert e['end']>=e['start']
        if index: assert edits[index-1]['end']<=e['start'],'Overlapping islands'
    result=before
    for e in reversed(edits): result=result[:e['start']]+bytes.fromhex(e['after'])+result[e['end']:]
    assert sha(result)==entry['after'],'Journal after hash'
    return result

boundaries=0
def validate_bytes(actual,expected,path):
    actual = restore_before_default_repair(actual, path)
    assert actual==expected,('Outside approved bailout islands or altered owned island',path)
for path,entry in journal.items():
    before=blob(path); expected=reconstruct(before,entry); current=(ROOT/path).read_bytes()
    validate_bytes(current,expected,path)
    assert current.startswith(b'\xef\xbb\xbf')==before.startswith(b'\xef\xbb\xbf'),('BOM',path)
    assert current.count(b'\r\n')==before.count(b'\r\n')==0,('LF changed',path)
    assert b'\r' not in current,('New CR',path)
    # Whole-byte comparison rejects outside comment/notice and inside island edits.
    probes=[current+b'\n']
    for e in entry['edits']:
        needle=bytes.fromhex(e['after'])
        assert needle and needle in current
        at=current.index(needle)
        probes.append(current[:at]+b' '+current[at:])
    for altered in probes:
        try: validate_bytes(altered,expected,path)
        except AssertionError: boundaries+=1
        else: raise AssertionError(('Byte mutant accepted',path))
    historical_current = restore_before_default_repair(current, path)
    before_ast=m.ast(before.decode('utf-8-sig')); current_ast=m.ast(historical_current.decode('utf-8-sig'))
    if path.startswith('events/'):
        ids=lambda nodes:[m.one(v,'id') for k,o,v in nodes if k in ('country_event','news_event')]
        assert ids(before_ast)==ids(current_ast),'Legacy event IDs changed'
    else:
        old={k:v for category,op,body in before_ast if isinstance(body,list) for k,o,v in body}
        new={k:v for category,op,body in current_ast if isinstance(body,list) for k,o,v in body}
        for key in ('bankruptcy_seek_bailout_from_imf','debt_default_pay_10_from_treasury','debt_default_pay_50_from_treasury'):
            assert new[key]==old[key],('Unowned IMF/default decision touched',key)

def walk(nodes):
    for k,o,v in nodes:
        yield k,o,v
        if isinstance(v,list): yield from walk(v)

# Both actual route4 callbacks must reset the shared input before selecting an
# overlord. Visibility alone did not prevent native40 availability evaluation.
def validate_overlord_scope(decision):
    reset=('set_temp_variable','=',[('eon_debt_bailout_donor','=','0')])
    for callback in ('available','complete_effect'):
        nodes=m.one(decision,callback)
        assert nodes[0]==reset,('Fresh donor input missing',callback)
        assert [n[0] for n in nodes]==(['set_temp_variable','if','else'] if callback=='available' else ['set_temp_variable','if']),('Unprotected callback statement',callback)
        guarded=m.one(nodes,'if')
        assert m.one(guarded,'limit')==[('is_subject','=','yes')],('Overlord guard changed',callback)
        assert guarded[1]==('overlord','=',[('set_temp_variable','=',[('eon_debt_bailout_donor','=','THIS.id')])]),('Donor actor/frame changed',callback)
        if callback=='available':
            assert m.one(nodes,'else')==[('always','=','no')],'Independent route must be disabled'

overlord=b.DECISIONS[b.ROUTES[3]]
validate_overlord_scope(overlord)
overlord_source_mutants=0
for callback in ('available','complete_effect'):
    for mutation in ('missing_reset','wrong_role','hoisted_scope'):
        bad=deepcopy(overlord); nodes=m.one(bad,callback)
        if mutation=='missing_reset': nodes.pop(0)
        elif mutation=='wrong_role': m.one(m.one(nodes,'if'),'limit')[:]=[('is_subject','=','no')]
        else:
            guarded=m.one(nodes,'if'); nodes.insert(1,guarded.pop(1))
        try: validate_overlord_scope(bad)
        except AssertionError: overlord_source_mutants+=1
        else: raise AssertionError(('Overlord structural mutant accepted',callback,mutation))
bad=deepcopy(overlord); m.one(bad,'available').pop()
try: validate_overlord_scope(bad)
except AssertionError: overlord_source_mutants+=1
else: raise AssertionError('Missing fail-closed branch accepted')

old_events={m.one(v,'id'):v for k,o,v in m.ast(blob('events/00_Econ_events.txt').decode('utf-8-sig')) if k in ('country_event','news_event')}
financial={'set_variable','add_to_variable','subtract_from_variable','clamp_variable','add_autonomy_ratio','change_influence_percentage'}
legacy=('bankruptcy.1','bankruptcy.2','bankruptcy.3','bankruptcy.4','bankruptcy.5','News_bankruptcy.1','News_bankruptcy.2','News_bankruptcy.3')
for ident in legacy:
    event=b.EVENTS[ident]
    assert not any(k in financial for k,o,v in walk(event)),('Legacy financial command',ident)
    old_names=[m.one(v,'name') for k,o,v in old_events[ident] if k=='option']
    names=[m.one(v,'name') for k,o,v in event if k=='option']
    assert old_names==names,('Retired option ID lost',ident)

for kind,oldid in enumerate(('bankruptcy.1','bankruptcy.2','bankruptcy.3','bankruptcy.5'),1):
    oldopts=[v for k,o,v in old_events[oldid] if k=='option']
    event=b.EVENTS[f'eon_debt_bailout.{kind}']; opts=[v for k,o,v in event if k=='option']
    assert not any(k=='trigger' for k,o,v in event),'Response must not vanish on cancellation'
    assert len(opts)==3
    for ix in (0,1):
        ai=m.one(opts[ix],'ai_chance'); orig=m.one(oldopts[ix],'ai_chance')
        assert (ai[:-1] if ix==0 else ai)==orig,(kind,'Original AI policy changed')
        expected=[('set_temp_variable','=',[('eon_debt_bailout_response_kind','=',str(kind))])]
        assert m.one(opts[ix],'trigger')[0]==expected[0],(kind,'Expected literal kind missing')
    assert m.one(opts[0],'ai_chance')[-1][0]=='modifier'
    assert not any(k in financial for k,o,v in walk(opts[2])),'Stale ACK has financial action'
for ident in ('eon_debt_bailout.10','eon_debt_bailout.11','eon_debt_bailout.12'):
    assert not any(k in financial or k in m.effects for k,o,v in walk(b.EVENTS[ident])),('Result notice has effect',ident)

paths=('common/scripted_effects/eon_debt_bailout_effects.txt','common/scripted_triggers/eon_debt_bailout_triggers.txt',
       'events/eon_debt_bailout_events.txt','common/on_actions/eon_debt_bailout_on_actions.txt')
for path in paths:
    data=m.ast(m.read(path))
    for k,o,v in walk(data):
        if k in ('has_country_flag','set_country_flag','clr_country_flag') and isinstance(v,str) and '@' in v:
            assert v.endswith('@PREV'),('Unsupported scalar flag suffix',path,v)
        if k.startswith('eon_debt_bailout_') and isinstance(v,str) and v in ('yes','no'):
            assert k in m.effects or k in m.triggers,('Undefined helper',path,k)
        if k in ('set_variable','clear_variable','add_to_variable','subtract_from_variable'):
            assert not (v=='debt_bailout' or isinstance(v,list) and any(n[0]=='debt_bailout' for n in v)),('IMF shared field mutation',path)

# Installed trigger docs explicitly allow temporary math in a trigger. All
# new predicates are parsed; native validity is still a separate acceptance.
docs=Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation/triggers_documentation.md')
if docs.exists():
    text=docs.read_text(encoding='utf-8-sig')
    for command in ('set_temp_variable','multiply_temp_variable','clamp_temp_variable'):
        assert '\n## '+command+'\n' in text.replace('\r\n','\n'),command
for k,o,v in walk(m.ast(m.read('common/scripted_triggers/eon_debt_bailout_triggers.txt'))):
    assert k not in ('set_variable','subtract_from_variable','add_to_variable','country_event','add_political_power','add_autonomy_ratio'),('Effect inside trigger',k)

locales={}
for language in ('english','russian'):
    raw=(ROOT/f'localisation/{language}/eon_debt_bailout_l_{language}.yml').read_bytes()
    assert raw.startswith(b'\xef\xbb\xbf') and b'\r' not in raw,('New locale encoding',language)
    lines=raw.decode('utf-8-sig').splitlines(); assert lines[0]=='l_'+language+':'
    values={}
    for line in lines[1:]:
        key,quoted=line.strip().split(':0 ',1); assert key not in values; values[key]=json.loads(quoted)
    locales[language]=values
assert locales['english'].keys()==locales['russian'].keys()
for language in ('english','russian'):
    path=ROOT/f'localisation/{language}/replace/eon_debt_bailout_replace_l_{language}.yml'
    raw=path.read_bytes(); assert raw.startswith(b'\xef\xbb\xbf') and b'\r' not in raw
    lines=raw.decode('utf-8-sig').splitlines(); assert lines[0]=='l_'+language+':'
    replaced={}
    for line in lines[1:]:
        key,quoted=line.strip().split(':0 ',1); assert key not in replaced; replaced[key]=json.loads(quoted)
    expected={route+'_'+suffix for route in b.ROUTES for suffix in ('desc','tt')}
    assert replaced.keys()==expected,('Old description override missing',language)
    for route,amount in zip(b.ROUTES,('20%','15%','10%','50%')):
        assert amount in replaced[route+'_desc'],(language,route,'Wrong offer fraction')
    assert '0.35' in replaced[b.ROUTES[3]+'_desc'] or '0,35' in replaced[b.ROUTES[3]+'_desc'],('Hidden autonomy',language)
for ident,event in b.EVENTS.items():
    if ident.startswith('eon_debt_bailout.') or ident in legacy:
        for k,o,v in walk(event):
            if k in ('title','desc','name','custom_effect_tooltip') and isinstance(v,str) and v.startswith('eon_debt_bailout_'):
                assert v in locales['english'],('Missing locale',ident,v)
for value in ('eon_debt_bailout_request_terms_tt','eon_debt_bailout_overlord_terms_tt','eon_debt_bailout_withdraw_request','eon_debt_bailout_withdraw_request_desc'):
    assert value in locales['english'],value
print(json.dumps({'byte_islands':sum(len(e['edits']) for e in journal.values()),'byte_mutants_rejected':boundaries,
                  'actual_overlord_callbacks_guarded':2,'overlord_structural_mutants_rejected':overlord_source_mutants,
                  'retired_event_ids':8,'routes':4,'localisation_keys_per_language':len(locales['english']),
                  'old_description_overrides_per_language':8,
                  'native_compilation_verified':False},indent=2))
