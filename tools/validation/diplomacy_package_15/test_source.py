"""Exact COM network contract, native API and bounded byte proofs; not HOI4 runtime."""
from pathlib import Path
from functools import lru_cache
from collections import Counter
import re
import subprocess
import json
import hashlib

ROOT=Path(__file__).resolve().parents[3]
import sys as package16_sys
package16_sys.path.insert(0, str(ROOT/'tools/validation'))
from diplomacy_package_16.test_source import (
    NEW as LATER_PACKAGE16_NEW, package16_original_bytes, package16_historical_existing,
    package16_original_validator_bytes,
    historical_actions as package16_historical_actions, check_owned_existing as check_later_package16_owned,
)
check_later_package16_owned()
from diplomacy_package_17.test_source import (
    NEW as LATER_PACKAGE17_NEW, package17_original_bytes, package17_historical_existing,
    historical_actions as package17_historical_actions, check_owned_existing as check_later_package17_owned,
)
check_later_package17_owned()
BASELINE='3f044a30711e7dba015969a9a5bd2b0229703a3c'
BASE=BASELINE
TOKEN=re.compile(rb'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|[=<>!]+|[^\s{}=<>!#"]+')
FX='common/scripted_effects/eon_satellite_effects.txt'
EXT='common/scripted_effects/eon_satellite_extended_effects.txt'
TR='common/scripted_triggers/eon_satellite_triggers.txt'
ETR='common/scripted_triggers/eon_satellite_extended_triggers.txt'
NFX='common/scripted_effects/00_missiles_scripted_effects.txt'
NTR='common/scripted_triggers/MD_missile_scripted_triggers.txt'
ACTION='common/scripted_diplomatic_actions/MD_missile_scripted_diplomatic_actions.txt'

def blocks(data,depth=0,key_filter=None):
    tokens=[m for m in TOKEN.finditer(data) if not m[0].startswith(b'#')]
    stack=[];out={}
    for i,t in enumerate(tokens):
        if t[0]==b'{':
            item={'key':tokens[i-2][0].decode('utf-8').lstrip('\ufeff'),'start':tokens[i-2].start(),'depth':len(stack)}
            stack.append(item)
        elif t[0]==b'}':
            assert stack
            item=stack.pop();item['end']=t.end()
            if item['depth']==depth and (key_filter is None or item['key']==key_filter):
                assert item['key'] not in out,item['key'];out[item['key']]=item
    assert not stack
    return out

@lru_cache(maxsize=64)
def baseline_bytes(path): return subprocess.check_output(['git','show',BASELINE+':'+path],cwd=ROOT)
def old(path): return baseline_bytes(path)
def block(path,key,depth=0):
    data=old(path);b=blocks(data,depth)[key]
    return data[b['start']:b['end']].decode('utf-8')
def once(text,a,b):
    assert text.count(a)==1,(a,text.count(a));return text.replace(a,b,1)

def service(role):
    prefix='eon_sat_com'+('_mil' if role=='mil' else '')
    return f'''{prefix}_service_to_prev = {{
 exists = yes PREV = {{ exists = yes }} NOT = {{ tag = PREV }}
 NOT = {{ check_variable = {{ THIS.id = eon_sat_removed_country }} }}
 PREV = {{ NOT = {{ check_variable = {{ THIS.id = eon_sat_removed_country }} }} }}
 NOT = {{ has_war_with = PREV }}
 {prefix}_valid_level = yes PREV = {{ {prefix}_valid_level = yes }}
 OR = {{ check_variable = {{ var_COM_{role}_system_idx > 0 }} AND = {{ check_variable = {{ var_COM_{role}_system_idx = 0 }} check_variable = {{ var_COM_{role}_sat_system_num > 0 }} }} }}
 check_variable = {{ var_COM_{role}_receiver_cap > 0 }}
 OR = {{ check_variable = {{ THIS.var_COM_{role}_system_idx = PREV.var_COM_{role}_system_idx }} check_variable = {{ THIS.var_COM_{role}_system_idx > PREV.var_COM_{role}_system_idx }} }}
 is_in_array = {{ array = COM_{role}_treaty_array value = PREV.id }}
 is_in_array = {{ array = PREV.COM_{role}_access_array value = THIS.id }}
}}'''

OWN_SYNC='''eon_sat_com_sync_own = {
 if = { limit = { exists = yes NOT = { check_variable = { THIS.id = eon_sat_removed_country } } }
  eon_sat_com_canonical_access = yes
  eon_sat_com_canonical_treaties = yes
  eon_sat_com_mil_canonical_access = yes
  eon_sat_com_mil_canonical_treaties = yes
  update_COM_system_stats = yes
  if = { limit = { eon_sat_com_valid_level = yes } calculate_COM_civ_gui_vars = yes }
  if = { limit = { eon_sat_com_mil_valid_level = yes } calculate_COM_mil_gui_vars = yes }
 }
}'''

def aggregate(role):
    path=EXT if role=='mil' else FX
    key='eon_sat_refresh_com'+('_mil' if role=='mil' else '')
    text=block(path,key)
    prefix='eon_sat_com'+('_mil' if role=='mil' else '')
    data=text.encode('utf-8');guard=blocks(data,3,'limit')['limit']
    text=(data[:guard['start']]+f'limit = {{ {prefix}_service_to_prev = yes }}'.encode('utf-8')+data[guard['end']:]).decode('utf-8')
    return once(text,key+' = {','eon_sat_com_apply_'+role+' = {')

def reciprocal_guard(role,work,frame='PREV'):
    return f'''exists = yes NOT = {{ tag = PREV }}
     NOT = {{ check_variable = {{ THIS.id = eon_sat_removed_country }} }}
     is_in_array = {{ array = COM_{role}_treaty_array value = PREV.id }}
     NOT = {{ is_in_array = {{ array = {frame}.{work} value = THIS.id }} }}'''

def network():
    providers='eon_sat_com_network_providers';actors='eon_sat_com_network_actors';bases='eon_sat_com_network_bases'
    text='''eon_sat_com_network_refresh = {
 if = { limit = { exists = yes NOT = { check_variable = { THIS.id = eon_sat_removed_country } } }
'''
    for work in (providers,actors,bases):text+=f'  clear_array = {work}\n'
    text+=f'  add_to_array = {{ array = {providers} value = THIS.id }}\n'
    text+='  eon_sat_com_canonical_access = yes\n  eon_sat_com_mil_canonical_access = yes\n'
    for role in ('civ','mil'):
        text+=f'''  for_each_scope_loop = {{ array = COM_{role}_access_array
   if = {{ limit = {{ {reciprocal_guard(role,providers)} }} add_to_array = {{ array = PREV.{providers} value = THIS.id }} }}
  }}
'''
    text+=f'''  for_each_scope_loop = {{ array = {providers}
   eon_sat_com_canonical_treaties = yes
   eon_sat_com_mil_canonical_treaties = yes
   if = {{ limit = {{ NOT = {{ is_in_array = {{ array = PREV.{actors} value = THIS.id }} }} }} add_to_array = {{ array = PREV.{actors} value = THIS.id }} }}
'''
    for role in ('civ','mil'):
        text+=f'''   for_each_scope_loop = {{ array = COM_{role}_treaty_array
    if = {{ limit = {{ exists = yes NOT = {{ tag = PREV }}
     NOT = {{ check_variable = {{ THIS.id = eon_sat_removed_country }} }}
     is_in_array = {{ array = COM_{role}_access_array value = PREV.id }}
     NOT = {{ is_in_array = {{ array = PREV.PREV.{actors} value = THIS.id }} }}
    }} add_to_array = {{ array = PREV.PREV.{actors} value = THIS.id }} }}
   }}
'''
    text+='  }\n'
    text+=f'''  for_each_scope_loop = {{ array = {actors}
   if = {{ limit = {{ NOT = {{ is_in_array = {{ array = PREV.{bases} value = THIS.id }} }} }} add_to_array = {{ array = PREV.{bases} value = THIS.id }} }}
'''
    for role in ('civ','mil'):
        text+=f'''   for_each_scope_loop = {{ array = COM_{role}_access_array
    if = {{ limit = {{ {reciprocal_guard(role,bases,'PREV.PREV')} }} add_to_array = {{ array = PREV.PREV.{bases} value = THIS.id }} }}
   }}
'''
    text+='  }\n'
    text+=f'  for_each_scope_loop = {{ array = {bases} eon_sat_com_sync_own = yes }}\n'
    text+=f'  for_each_scope_loop = {{ array = {actors} eon_sat_com_apply_civ = yes eon_sat_com_apply_mil = yes }}\n'
    for work in (providers,actors,bases):text+=f'  clear_array = {work}\n'
    return text+' }\n}'

def lifecycle(role):
    path=EXT if role=='mil' else FX
    prefix='eon_sat_com'+('_mil' if role=='mil' else '')
    result={}
    for kind in ('request','offer'):
        key=prefix+'_begin_'+kind;text=block(path,key)
        head=f' if = {{ limit = {{ {prefix}_{kind}_ready = yes }}\n'
        # Original ready grant body is retained byte-for-byte inside a fresh new-ready gate.
        text=once(text,head,f' if = {{ limit = {{ {prefix}_new_ready = yes }}\n  eon_sat_com_sync_own = yes\n  PREV = {{ eon_sat_com_sync_own = yes }}\n'+head)
        text=text[:-1]+' }\n}'
        result[key]=text
        key=prefix+'_accept_'+kind;text=block(path,key)
        auth=f'  if = {{ limit = {{ {prefix}_{kind}_authorized = yes }}'
        text=once(text,auth,'  eon_sat_com_sync_own = yes\n  PREV = { eon_sat_com_sync_own = yes }\n'+auth)
        text=once(text,'flag = recently_accepted_mil_com_@PREV',f'flag = eon_sat_com_{role}_accepted@PREV')
        result[key]=text
    key=prefix+'_revoke';result[key]=block(path,key)  # Entry wrapper supplies fresh network after original removal.
    key='eon_sat_refresh_com'+('_mil' if role=='mil' else '')
    result[key]=key+' = { eon_sat_com_network_refresh = yes }'
    key='eon_sat_extended_daily_cleanup' if role=='mil' else 'eon_sat_daily_cleanup'
    text=block(path,key);line=f' {prefix}_cleanup = yes'
    fresh=f''' if = {{ limit = {{ has_country_flag = {prefix}_pending check_variable = {{ {prefix}_partner > 0 }} }}
  var:{prefix}_partner = {{ eon_sat_com_network_refresh = yes }}
 }}
 eon_sat_com_network_refresh = yes
'''
    result[key]=once(text,line,fresh+line)
    return result

def native_fx():
    out={}
    for role in ('mil','civ'):
        key='add_treaty_COM_'+role+'_receiver_num';text=block(NFX,key)
        head=f' for_each_scope_loop = {{ array = COM_{role}_treaty_array\n'
        helper='eon_sat_com'+('_mil' if role=='mil' else '')+'_service_to_prev'
        text=once(text,head,head+f'  if = {{ limit = {{ PREV = {{ {helper} = yes }} }}\n')
        tail=f' }}\n add_to_variable = {{ var_COM_{role}_receiver_num = var_treaty_COM_{role}_receiver_num }}'
        text=once(text,tail,'  }\n'+tail)
        out[key]=text
        key='COM_'+role+'_button_update';text=block(NFX,key)
        out[key]=text[:-1]+' eon_sat_com_network_refresh = yes\n}'
    return out

def native_ai(role):
    helper='eon_sat_com'+('_mil' if role=='mil' else '')+'_service_to_prev'
    key='NOT_share_COM_'+role+'_satellites_above_network_traffic_limit'
    demand=('''   add_to_temp_variable = { temp1 = THIS.num_battalions }
   add_to_temp_variable = { temp1 = THIS.num_ships }
   add_to_temp_variable = { temp1 = THIS.num_deployed_planes }''' if role=='mil' else '''   set_temp_variable = { temp2 = THIS.num_controlled_states }
   multiply_temp_variable = { temp2 = 100 }
   add_to_temp_variable = { temp1 = temp2 }''')
    return key,f'''{key} = {{
 if = {{ limit = {{ check_variable = {{ ROOT.var_COM_{role}_receiver_cap > 0 }} }}
  set_temp_variable = {{ temp1 = ROOT.var_COM_{role}_receiver_num }}
  if = {{ limit = {{ NOT = {{ ROOT = {{ {helper} = yes }} }} }}
{demand}
  }}
  divide_temp_variable = {{ temp1 = ROOT.var_COM_{role}_receiver_cap }}
  check_variable = {{ temp1 > 1.249 }}
 }}
 else = {{ always = yes }}
}}'''

def replacements():
    result={FX:lifecycle('civ'),EXT:lifecycle('mil'),NFX:native_fx(),NTR:dict(native_ai(r) for r in ('mil','civ')),ACTION:{}}
    for role in ('mil','civ'):
        key='revoke_'+role+'_com_access';text=block(ACTION,key,1)
        before='ROOT = { has_country_flag = recently_accepted_mil_com_@PREV }'
        after=f'ROOT = {{ OR = {{ has_country_flag = eon_sat_com_{role}_accepted@PREV has_country_flag = recently_accepted_mil_com_@PREV }} }}'
        result[ACTION][key]=once(text,before,after)
    return result

APPENDED={FX:[OWN_SYNC,aggregate('civ'),network()],EXT:[aggregate('mil')],TR:[service('civ')],ETR:[service('mil')]}

def build():
    changes=replacements();out={}
    for path in sorted(set(changes)|set(APPENDED)):
        data=old(path);depth=1 if path==ACTION else 0;owned=blocks(data,depth);text=data
        eol=b'\r\n' if b'\r\n' in data else b'\n'
        for key,newtext in sorted(changes.get(path,{}).items(),key=lambda item:owned[item[0]]['start'],reverse=True):
            b=owned[key];newbytes=newtext.replace('\r\n','\n').encode('utf-8').replace(b'\n',eol)
            text=text[:b['start']]+newbytes+text[b['end']:]
        if path in APPENDED:
            suffix='\n'+'\n\n'.join(APPENDED[path])+'\n'
            text+=suffix.encode('utf-8').replace(b'\n',eol)
        blocks(text,depth)
        out[path]=text
    return out



def ast(data):
    if isinstance(data, str): data = data.encode('utf-8')
    tokens = [match[0].decode().strip('"').lstrip('\ufeff') for match in TOKEN.finditer(data) if not match[0].startswith(b'#')]
    index = 0
    def body():
        nonlocal index
        result = []
        while index < len(tokens) and tokens[index] != '}':
            key = tokens[index]; index += 1
            if index == len(tokens) or tokens[index] not in ('=', '==', '<', '>', '<=', '>=', '!='):
                result.append(('__item__', '=', key)); continue
            operator = tokens[index]; index += 1
            assert index < len(tokens), ('Missing value', key)
            if tokens[index] == '{':
                index += 1; value = body()
                assert index < len(tokens) and tokens[index] == '}', ('Unclosed block', key)
                index += 1
            else:
                value = tokens[index]; index += 1
            result.append((key, operator, value))
        return result
    result = body(); assert index == len(tokens), 'Extra closing brace'
    return result


def one(nodes, key):
    values = [value for name, operator, value in nodes if name == key]
    assert len(values) == 1, (key, len(values))
    return values[0]


def rows(nodes):
    for row in nodes:
        yield row
        if isinstance(row[2], list): yield from rows(row[2])





LOCALE_EDITS = {
  "localisation/english/eon_satellite_l_english.yml": [
    "eon_sat_com_granted_tt",
    " eon_sat_com_granted_tt:0 \"Record civilian communications access with current consent and recalculate its existing bonuses together with other providers. Partner demand uses the existing 100 receivers per controlled state for every consenting recipient. A provider with no usable system, a weaker system or direct war gives no foreign service bonus while consent remains dormant. Revocation removes that provider's grant; service recovery cannot recreate a revoked agreement. First-tier service also requires a positive count of the corresponding satellites in the provider's current system statistics.\"",
    " eon_sat_com_granted_tt:0 \"Record civilian communications access with current consent and recalculate its existing bonuses together with other providers. Partner demand uses the existing 100 receivers per controlled state for each recipient currently eligible for that provider's civilian communications service. A provider with no usable system, a weaker system or direct war gives no foreign service bonus while consent remains dormant. Revocation removes that provider's grant; service recovery cannot recreate a revoked agreement. First-tier service also requires a positive count of the corresponding satellites in the provider's current system statistics.\""
  ],
  "localisation/english/eon_satellite_extended_l_english.yml": [
    "eon_sat_com_mil_granted_tt",
    " eon_sat_com_mil_granted_tt:0 \"Record military communications access with current consent and recalculate its existing bonuses together with other providers. A provider without usable or sufficiently advanced service, or at direct war with the recipient, gives no foreign service bonus while consent remains dormant. Revocation removes that provider's grant; service recovery cannot recreate a revoked agreement. Military communications demand uses the existing battalion, ship and deployed-plane counts of every recipient with a recorded mutual agreement, including dormant agreements. First-tier service also requires a positive count of the corresponding satellites in the provider's current system statistics.\"",
    " eon_sat_com_mil_granted_tt:0 \"Record military communications access with current consent and recalculate its existing bonuses together with other providers. A provider without usable or sufficiently advanced service, or at direct war with the recipient, gives no foreign service bonus while consent remains dormant. Revocation removes that provider's grant; service recovery cannot recreate a revoked agreement. Military communications demand uses the existing battalion, ship and deployed-plane counts of each recipient currently eligible for that provider's military communications service. First-tier service also requires a positive count of the corresponding satellites in the provider's current system statistics.\""
  ],
  "localisation/russian/eon_satellite_l_russian.yml": [
    "eon_sat_com_granted_tt",
    " eon_sat_com_granted_tt:0 \"\u0417\u0430\u0444\u0438\u043a\u0441\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f \u043a \u0433\u0440\u0430\u0436\u0434\u0430\u043d\u0441\u043a\u043e\u0439 \u0441\u0432\u044f\u0437\u0438 \u0441 \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u043c \u0441\u043e\u0433\u043b\u0430\u0441\u0438\u0435\u043c \u0438 \u043f\u0435\u0440\u0435\u0441\u0447\u0438\u0442\u0430\u0442\u044c \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u044e\u0449\u0438\u0435 \u0431\u043e\u043d\u0443\u0441\u044b \u0432\u043c\u0435\u0441\u0442\u0435 \u0441 \u0434\u0440\u0443\u0433\u0438\u043c\u0438 \u043f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440\u0430\u043c\u0438. \u041d\u0430\u0433\u0440\u0443\u0437\u043a\u0430 \u043f\u0430\u0440\u0442\u043d\u0451\u0440\u043e\u0432 \u0441\u043e\u0445\u0440\u0430\u043d\u044f\u0435\u0442 \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u044e\u0449\u0438\u0435 100 \u043f\u0440\u0438\u0451\u043c\u043d\u0438\u043a\u043e\u0432 \u043d\u0430 \u043a\u0430\u0436\u0434\u0443\u044e \u043a\u043e\u043d\u0442\u0440\u043e\u043b\u0438\u0440\u0443\u0435\u043c\u0443\u044e \u043e\u0431\u043b\u0430\u0441\u0442\u044c \u043a\u0430\u0436\u0434\u043e\u0433\u043e \u0441\u043e\u0433\u043b\u0430\u0441\u0438\u0432\u0448\u0435\u0433\u043e\u0441\u044f \u043f\u043e\u043b\u0443\u0447\u0430\u0442\u0435\u043b\u044f. \u041e\u0442\u0441\u0443\u0442\u0441\u0442\u0432\u0438\u0435 \u043f\u0440\u0438\u0433\u043e\u0434\u043d\u043e\u0439 \u0441\u0438\u0441\u0442\u0435\u043c\u044b, \u0431\u043e\u043b\u0435\u0435 \u0441\u043b\u0430\u0431\u0430\u044f \u0441\u0438\u0441\u0442\u0435\u043c\u0430 \u0438\u043b\u0438 \u043f\u0440\u044f\u043c\u0430\u044f \u0432\u043e\u0439\u043d\u0430 \u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e \u0438\u0441\u043a\u043b\u044e\u0447\u0430\u044e\u0442 \u0431\u043e\u043d\u0443\u0441 \u0447\u0443\u0436\u043e\u0439 \u0443\u0441\u043b\u0443\u0433\u0438 \u043f\u0440\u0438 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0438\u0438 \u0441\u043e\u0433\u043b\u0430\u0441\u0438\u044f. \u041e\u0442\u0437\u044b\u0432 \u0443\u0434\u0430\u043b\u044f\u0435\u0442 \u043f\u0440\u0435\u0434\u043e\u0441\u0442\u0430\u0432\u043b\u0435\u043d\u0438\u0435 \u0434\u043e\u0441\u0442\u0443\u043f\u0430 \u044d\u0442\u0438\u043c \u043f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440\u043e\u043c; \u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u0443\u0441\u043b\u0443\u0433\u0438 \u043d\u0435 \u0432\u043e\u0441\u0441\u043e\u0437\u0434\u0430\u0451\u0442 \u043e\u0442\u043e\u0437\u0432\u0430\u043d\u043d\u043e\u0435 \u0441\u043e\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u0435. \u0414\u043b\u044f \u0443\u0441\u043b\u0443\u0433\u0438 \u043f\u0435\u0440\u0432\u043e\u0433\u043e \u0443\u0440\u043e\u0432\u043d\u044f \u0442\u0435\u043a\u0443\u0449\u0438\u0435 \u043f\u043e\u043a\u0430\u0437\u0430\u0442\u0435\u043b\u0438 \u0441\u0438\u0441\u0442\u0435\u043c\u044b \u043f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a\u0430 \u0442\u0430\u043a\u0436\u0435 \u0434\u043e\u043b\u0436\u043d\u044b \u043f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0442\u044c \u043d\u0430\u043b\u0438\u0447\u0438\u0435 \u0441\u043e\u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0443\u044e\u0449\u0438\u0445 \u0441\u043f\u0443\u0442\u043d\u0438\u043a\u043e\u0432.\"",
    " eon_sat_com_granted_tt:0 \"\u0417\u0430\u0444\u0438\u043a\u0441\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f \u043a \u0433\u0440\u0430\u0436\u0434\u0430\u043d\u0441\u043a\u043e\u0439 \u0441\u0432\u044f\u0437\u0438 \u0441 \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u043c \u0441\u043e\u0433\u043b\u0430\u0441\u0438\u0435\u043c \u0438 \u043f\u0435\u0440\u0435\u0441\u0447\u0438\u0442\u0430\u0442\u044c \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u044e\u0449\u0438\u0435 \u0431\u043e\u043d\u0443\u0441\u044b \u0432\u043c\u0435\u0441\u0442\u0435 \u0441 \u0434\u0440\u0443\u0433\u0438\u043c\u0438 \u043f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440\u0430\u043c\u0438. \u041d\u0430\u0433\u0440\u0443\u0437\u043a\u0430 \u043f\u0430\u0440\u0442\u043d\u0451\u0440\u043e\u0432 \u0441\u043e\u0445\u0440\u0430\u043d\u044f\u0435\u0442 \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u044e\u0449\u0438\u0435 100 \u043f\u0440\u0438\u0451\u043c\u043d\u0438\u043a\u043e\u0432 \u043d\u0430 \u043a\u0430\u0436\u0434\u0443\u044e \u043a\u043e\u043d\u0442\u0440\u043e\u043b\u0438\u0440\u0443\u0435\u043c\u0443\u044e \u043e\u0431\u043b\u0430\u0441\u0442\u044c \u043a\u0430\u0436\u0434\u043e\u0433\u043e \u043f\u043e\u043b\u0443\u0447\u0430\u0442\u0435\u043b\u044f, \u0441\u043e\u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0443\u044e\u0449\u0435\u0433\u043e \u0442\u0435\u043a\u0443\u0449\u0438\u043c \u0443\u0441\u043b\u043e\u0432\u0438\u044f\u043c \u043f\u043e\u043b\u0443\u0447\u0435\u043d\u0438\u044f \u0433\u0440\u0430\u0436\u0434\u0430\u043d\u0441\u043a\u043e\u0439 \u0443\u0441\u043b\u0443\u0433\u0438 \u044d\u0442\u043e\u0433\u043e \u043f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a\u0430. \u041e\u0442\u0441\u0443\u0442\u0441\u0442\u0432\u0438\u0435 \u043f\u0440\u0438\u0433\u043e\u0434\u043d\u043e\u0439 \u0441\u0438\u0441\u0442\u0435\u043c\u044b, \u0431\u043e\u043b\u0435\u0435 \u0441\u043b\u0430\u0431\u0430\u044f \u0441\u0438\u0441\u0442\u0435\u043c\u0430 \u0438\u043b\u0438 \u043f\u0440\u044f\u043c\u0430\u044f \u0432\u043e\u0439\u043d\u0430 \u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e \u0438\u0441\u043a\u043b\u044e\u0447\u0430\u044e\u0442 \u0431\u043e\u043d\u0443\u0441 \u0447\u0443\u0436\u043e\u0439 \u0443\u0441\u043b\u0443\u0433\u0438 \u043f\u0440\u0438 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0438\u0438 \u0441\u043e\u0433\u043b\u0430\u0441\u0438\u044f. \u041e\u0442\u0437\u044b\u0432 \u0443\u0434\u0430\u043b\u044f\u0435\u0442 \u043f\u0440\u0435\u0434\u043e\u0441\u0442\u0430\u0432\u043b\u0435\u043d\u0438\u0435 \u0434\u043e\u0441\u0442\u0443\u043f\u0430 \u044d\u0442\u0438\u043c \u043f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440\u043e\u043c; \u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u0443\u0441\u043b\u0443\u0433\u0438 \u043d\u0435 \u0432\u043e\u0441\u0441\u043e\u0437\u0434\u0430\u0451\u0442 \u043e\u0442\u043e\u0437\u0432\u0430\u043d\u043d\u043e\u0435 \u0441\u043e\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u0435. \u0414\u043b\u044f \u0443\u0441\u043b\u0443\u0433\u0438 \u043f\u0435\u0440\u0432\u043e\u0433\u043e \u0443\u0440\u043e\u0432\u043d\u044f \u0442\u0435\u043a\u0443\u0449\u0438\u0435 \u043f\u043e\u043a\u0430\u0437\u0430\u0442\u0435\u043b\u0438 \u0441\u0438\u0441\u0442\u0435\u043c\u044b \u043f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a\u0430 \u0442\u0430\u043a\u0436\u0435 \u0434\u043e\u043b\u0436\u043d\u044b \u043f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0442\u044c \u043d\u0430\u043b\u0438\u0447\u0438\u0435 \u0441\u043e\u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0443\u044e\u0449\u0438\u0445 \u0441\u043f\u0443\u0442\u043d\u0438\u043a\u043e\u0432.\""
  ],
  "localisation/russian/eon_satellite_extended_l_russian.yml": [
    "eon_sat_com_mil_granted_tt",
    " eon_sat_com_mil_granted_tt:0 \"\u0417\u0430\u043f\u0438\u0441\u0430\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f \u043a \u0441\u0438\u0441\u0442\u0435\u043c\u0435 \u0432\u043e\u0435\u043d\u043d\u043e\u0439 \u0441\u043f\u0443\u0442\u043d\u0438\u043a\u043e\u0432\u043e\u0439 \u0441\u0432\u044f\u0437\u0438 \u0441 \u0442\u0435\u043a\u0443\u0449\u0438\u043c \u0441\u043e\u0433\u043b\u0430\u0441\u0438\u0435\u043c \u0438 \u043f\u0435\u0440\u0435\u0441\u0447\u0438\u0442\u0430\u0442\u044c \u0435\u0451 \u0434\u0435\u0439\u0441\u0442\u0432\u0443\u044e\u0449\u0438\u0435 \u0431\u043e\u043d\u0443\u0441\u044b \u0432\u043c\u0435\u0441\u0442\u0435 \u0441 \u0434\u0440\u0443\u0433\u0438\u043c\u0438 \u043f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a\u0430\u043c\u0438. \u041f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a \u0431\u0435\u0437 \u043f\u0440\u0438\u0433\u043e\u0434\u043d\u043e\u0439 \u0438\u043b\u0438 \u0434\u043e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u043e \u0440\u0430\u0437\u0432\u0438\u0442\u043e\u0439 \u0443\u0441\u043b\u0443\u0433\u0438 \u043b\u0438\u0431\u043e \u0432\u043e\u044e\u044e\u0449\u0438\u0439 \u043d\u0435\u043f\u043e\u0441\u0440\u0435\u0434\u0441\u0442\u0432\u0435\u043d\u043d\u043e \u0441 \u043f\u043e\u043b\u0443\u0447\u0430\u0442\u0435\u043b\u0435\u043c \u043d\u0435 \u0434\u0430\u0451\u0442 \u0438\u043d\u043e\u0441\u0442\u0440\u0430\u043d\u043d\u043e\u0433\u043e \u0431\u043e\u043d\u0443\u0441\u0430 \u043f\u0440\u0438 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0438\u0438 \u043d\u0435\u0430\u043a\u0442\u0438\u0432\u043d\u043e\u0433\u043e \u0441\u043e\u0433\u043b\u0430\u0441\u0438\u044f. \u041e\u0442\u0437\u044b\u0432 \u0443\u0434\u0430\u043b\u044f\u0435\u0442 \u0440\u0430\u0437\u0440\u0435\u0448\u0435\u043d\u0438\u0435 \u044d\u0442\u043e\u0433\u043e \u043f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a\u0430; \u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u0443\u0441\u043b\u0443\u0433\u0438 \u043d\u0435 \u0441\u043e\u0437\u0434\u0430\u0451\u0442 \u043e\u0442\u043e\u0437\u0432\u0430\u043d\u043d\u043e\u0435 \u0441\u043e\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u0435 \u0437\u0430\u043d\u043e\u0432\u043e. \u0412\u043e\u0435\u043d\u043d\u044b\u0439 \u0441\u043f\u0440\u043e\u0441 \u043d\u0430 \u0441\u0432\u044f\u0437\u044c \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0435\u0442 \u0434\u0435\u0439\u0441\u0442\u0432\u0443\u044e\u0449\u0438\u0435 \u043a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u0430 \u0431\u0430\u0442\u0430\u043b\u044c\u043e\u043d\u043e\u0432, \u043a\u043e\u0440\u0430\u0431\u043b\u0435\u0439 \u0438 \u0440\u0430\u0437\u0432\u0451\u0440\u043d\u0443\u0442\u044b\u0445 \u0441\u0430\u043c\u043e\u043b\u0451\u0442\u043e\u0432 \u043a\u0430\u0436\u0434\u043e\u0433\u043e \u043f\u043e\u043b\u0443\u0447\u0430\u0442\u0435\u043b\u044f \u0441 \u0437\u0430\u043f\u0438\u0441\u0430\u043d\u043d\u044b\u043c \u0432\u0437\u0430\u0438\u043c\u043d\u044b\u043c \u0441\u043e\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u0435\u043c, \u0432\u043a\u043b\u044e\u0447\u0430\u044f \u043d\u0435\u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0435 \u0441\u043e\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u044f. \u0414\u043b\u044f \u0443\u0441\u043b\u0443\u0433\u0438 \u043f\u0435\u0440\u0432\u043e\u0433\u043e \u0443\u0440\u043e\u0432\u043d\u044f \u0442\u0435\u043a\u0443\u0449\u0438\u0435 \u043f\u043e\u043a\u0430\u0437\u0430\u0442\u0435\u043b\u0438 \u0441\u0438\u0441\u0442\u0435\u043c\u044b \u043f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a\u0430 \u0442\u0430\u043a\u0436\u0435 \u0434\u043e\u043b\u0436\u043d\u044b \u043f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0442\u044c \u043d\u0430\u043b\u0438\u0447\u0438\u0435 \u0441\u043e\u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0443\u044e\u0449\u0438\u0445 \u0441\u043f\u0443\u0442\u043d\u0438\u043a\u043e\u0432.\"",
    " eon_sat_com_mil_granted_tt:0 \"\u0417\u0430\u043f\u0438\u0441\u0430\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f \u043a \u0441\u0438\u0441\u0442\u0435\u043c\u0435 \u0432\u043e\u0435\u043d\u043d\u043e\u0439 \u0441\u043f\u0443\u0442\u043d\u0438\u043a\u043e\u0432\u043e\u0439 \u0441\u0432\u044f\u0437\u0438 \u0441 \u0442\u0435\u043a\u0443\u0449\u0438\u043c \u0441\u043e\u0433\u043b\u0430\u0441\u0438\u0435\u043c \u0438 \u043f\u0435\u0440\u0435\u0441\u0447\u0438\u0442\u0430\u0442\u044c \u0435\u0451 \u0434\u0435\u0439\u0441\u0442\u0432\u0443\u044e\u0449\u0438\u0435 \u0431\u043e\u043d\u0443\u0441\u044b \u0432\u043c\u0435\u0441\u0442\u0435 \u0441 \u0434\u0440\u0443\u0433\u0438\u043c\u0438 \u043f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a\u0430\u043c\u0438. \u041f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a \u0431\u0435\u0437 \u043f\u0440\u0438\u0433\u043e\u0434\u043d\u043e\u0439 \u0438\u043b\u0438 \u0434\u043e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u043e \u0440\u0430\u0437\u0432\u0438\u0442\u043e\u0439 \u0443\u0441\u043b\u0443\u0433\u0438 \u043b\u0438\u0431\u043e \u0432\u043e\u044e\u044e\u0449\u0438\u0439 \u043d\u0435\u043f\u043e\u0441\u0440\u0435\u0434\u0441\u0442\u0432\u0435\u043d\u043d\u043e \u0441 \u043f\u043e\u043b\u0443\u0447\u0430\u0442\u0435\u043b\u0435\u043c \u043d\u0435 \u0434\u0430\u0451\u0442 \u0438\u043d\u043e\u0441\u0442\u0440\u0430\u043d\u043d\u043e\u0433\u043e \u0431\u043e\u043d\u0443\u0441\u0430 \u043f\u0440\u0438 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0438\u0438 \u043d\u0435\u0430\u043a\u0442\u0438\u0432\u043d\u043e\u0433\u043e \u0441\u043e\u0433\u043b\u0430\u0441\u0438\u044f. \u041e\u0442\u0437\u044b\u0432 \u0443\u0434\u0430\u043b\u044f\u0435\u0442 \u0440\u0430\u0437\u0440\u0435\u0448\u0435\u043d\u0438\u0435 \u044d\u0442\u043e\u0433\u043e \u043f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a\u0430; \u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u0443\u0441\u043b\u0443\u0433\u0438 \u043d\u0435 \u0441\u043e\u0437\u0434\u0430\u0451\u0442 \u043e\u0442\u043e\u0437\u0432\u0430\u043d\u043d\u043e\u0435 \u0441\u043e\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u0435 \u0437\u0430\u043d\u043e\u0432\u043e. \u0412\u043e\u0435\u043d\u043d\u044b\u0439 \u0441\u043f\u0440\u043e\u0441 \u043d\u0430 \u0441\u0432\u044f\u0437\u044c \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0435\u0442 \u0434\u0435\u0439\u0441\u0442\u0432\u0443\u044e\u0449\u0438\u0435 \u043a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u0430 \u0431\u0430\u0442\u0430\u043b\u044c\u043e\u043d\u043e\u0432, \u043a\u043e\u0440\u0430\u0431\u043b\u0435\u0439 \u0438 \u0440\u0430\u0437\u0432\u0451\u0440\u043d\u0443\u0442\u044b\u0445 \u0441\u0430\u043c\u043e\u043b\u0451\u0442\u043e\u0432 \u043a\u0430\u0436\u0434\u043e\u0433\u043e \u043f\u043e\u043b\u0443\u0447\u0430\u0442\u0435\u043b\u044f, \u0441\u043e\u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0443\u044e\u0449\u0435\u0433\u043e \u0442\u0435\u043a\u0443\u0449\u0438\u043c \u0443\u0441\u043b\u043e\u0432\u0438\u044f\u043c \u043f\u043e\u043b\u0443\u0447\u0435\u043d\u0438\u044f \u0432\u043e\u0435\u043d\u043d\u043e\u0439 \u0443\u0441\u043b\u0443\u0433\u0438 \u044d\u0442\u043e\u0433\u043e \u043f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a\u0430. \u0414\u043b\u044f \u0443\u0441\u043b\u0443\u0433\u0438 \u043f\u0435\u0440\u0432\u043e\u0433\u043e \u0443\u0440\u043e\u0432\u043d\u044f \u0442\u0435\u043a\u0443\u0449\u0438\u0435 \u043f\u043e\u043a\u0430\u0437\u0430\u0442\u0435\u043b\u0438 \u0441\u0438\u0441\u0442\u0435\u043c\u044b \u043f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a\u0430 \u0442\u0430\u043a\u0436\u0435 \u0434\u043e\u043b\u0436\u043d\u044b \u043f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0442\u044c \u043d\u0430\u043b\u0438\u0447\u0438\u0435 \u0441\u043e\u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0443\u044e\u0449\u0438\u0445 \u0441\u043f\u0443\u0442\u043d\u0438\u043a\u043e\u0432.\""
  ]
}
LOCALES=set(LOCALE_EDITS)
SCRIPT_PATHS={FX,EXT,TR,ETR,NFX,NTR,ACTION}
EXISTING=SCRIPT_PATHS|LOCALES
NEW=set()


@lru_cache(maxsize=1)
def expected_scripts():
    return build()


def expected_locale(path):
    original=baseline_bytes(path);key,before,after=LOCALE_EDITS[path]
    assert original.startswith(b'\xef\xbb\xbf')
    text=original.decode('utf-8-sig')
    assert text.count(before)==1 and before.startswith(' '+key+':0 ')
    text=text.replace(before,after,1)
    return b'\xef\xbb\xbf'+text.encode('utf-8')


def package15_original_bytes(path,actual):
    """Strict eleven-path restoration, before fourteen/thirteen/twelve proofs."""
    if path not in EXISTING:return actual
    original=baseline_bytes(path)
    assert actual.startswith(b'\xef\xbb\xbf')==original.startswith(b'\xef\xbb\xbf'),path
    assert (b'\r\n' in actual)==(b'\r\n' in original) and b'\r' not in actual.replace(b'\r\n',b''),path
    assert actual.endswith(b'\n')==original.endswith(b'\n'),path
    expected=expected_locale(path) if path in LOCALES else expected_scripts()[path]
    assert actual==expected,('Unexpected bytes outside/inside exact package15 contract',path)
    return original


@lru_cache(maxsize=32)
def package15_historical_existing(baseline):
    return frozenset(subprocess.check_output(['git','ls-tree','-r','--name-only',baseline,'--',*sorted(EXISTING)],cwd=ROOT).decode().splitlines())


def check_owned_existing():
    for path in sorted(EXISTING):package15_original_bytes(path,(ROOT/path).read_bytes())


# Filled only from separately reviewed exact coherent-fixture journal; no gameplay restoration.
BEHAVIOR_FIXTURE_EDITS = {
  "tools/validation/diplomacy_package_12/test_satellites.py": [
    [
      27,
      27,
      "",
      "    if expression.startswith('PREV.PREV.'):\n        parts = expression.split('.')\n        depth = 0\n        while depth < len(parts) and parts[depth] == 'PREV': depth += 1\n        assert depth < len(parts) and depth <= len(ctx['previous']), ('Missing native previous-scope frame', expression, ctx)\n        actor = ctx['previous'][depth - 1]\n        assert actor in result['countries'], ('Missing native previous country', expression, ctx)\n        return result['countries'][actor], '.'.join(parts[depth:])\n"
    ],
    [
      37,
      38,
      "    if isinstance(expression, str) and expression.startswith('global.'):\n",
      "    if isinstance(expression, str) and expression.startswith(('global.', 'PREV.PREV.')):\n"
    ],
    [
      39,
      39,
      "",
      "        if field == 'id':\n            return next(actor for actor, country in result['countries'].items() if country is data)\n"
    ],
    [
      148,
      149,
      "             'add_treaty_COM_civ_receiver_num', 'update_COM_system_stats', 'add_treaty_COM_mil_receiver_num'):\n",
      "             'add_treaty_COM_civ_receiver_num', 'update_COM_system_stats', 'add_treaty_COM_mil_receiver_num',\n             'calculate_COM_mil_gui_vars', 'calculate_COM_civ_gui_vars'):\n"
    ],
    [
      174,
      174,
      "",
      "def com_physical_fixture(result):\n    # Native table declarations and explicit shared constellation/getter facts.\n    for key, op, nodes in one(ast(read('common/scripted_effects/00_missiles_models.txt')), 'set_all_sat_system_tech'):\n        if key == 'add_to_array' and len(nodes) == 1:\n            field, assignment, literal = nodes[0]\n            if field.startswith('global.COM_') and field.endswith(('_min_array', '_max_array')):\n                result['global']['arrays'].setdefault(field.removeprefix('global.'), []).append(float(literal))\n    for actor, country in result['countries'].items():\n        country['variables'].update(var_COM_mil_system_idx=0 if actor == 'A' else 3,\n            var_COM_mil_sat_system_max=10, num_battalions=0, num_ships=0, num_deployed_planes=0)\n        for suffix in ('access_array', 'treaty_array', 'access_system_idx_array'):\n            country['arrays']['COM_mil_' + suffix] = []\n        country['arrays']['COM_satellite_array'] = [0, 0, 0, 10, 0, 0, 0, 0]\n        country['arrays']['COM_sat_receiver_tech_array'] = [100] * 8\n    for actor in result['countries']:\n        result['temp'] = {}\n        execute([('eon_sat_com_sync_own', '=', 'yes'), ('eon_sat_com_apply_civ', '=', 'yes'), ('eon_sat_com_apply_mil', '=', 'yes')], result, context(actor))\n\ndef set_com_count_fixture(result, actor, count):\n    # A changed cached count fixture must agree with physical native inventory.\n    result['countries'][actor]['arrays']['COM_satellite_array'] = [0, 0, 0, count, 0, 0, 0, 0]\n    for role in ('mil', 'civ'):\n        result['countries'][actor]['variables']['var_COM_' + role + '_sat_system_num'] = count\n    result['temp'] = {}\n    execute([('eon_sat_com_sync_own', '=', 'yes'), ('eon_sat_com_apply_civ', '=', 'yes'), ('eon_sat_com_apply_mil', '=', 'yes')], result, context(actor))\n\n"
    ],
    [
      186,
      187,
      "                result['global']['arrays'][name + '_max_array'] = [0, .1, .2, .3, .4, .5, .6, .7]\n",
      "                if family != 'COM': result['global']['arrays'][name + '_max_array'] = [0, .1, .2, .3, .4, .5, .6, .7]\n"
    ],
    [
      190,
      190,
      "",
      "    com_physical_fixture(result)\n"
    ],
    [
      227,
      227,
      "",
      "    declarations = len(result.get('timer_declarations', []))\n"
    ],
    [
      228,
      228,
      "",
      "    if accepted and family == 'com':\n        # Report actual fresh installation, not a cached gate sampled before\n        # the callback's own physical synchronization.\n        return native_ready and (actor, 'eon_sat_com_civ_accepted@' + partner, 180) in result.get('timer_declarations', [])[declarations:]\n"
    ],
    [
      273,
      275,
      "                             if not key.startswith(('eon_sat_', 'var_GNSS_civ_', 'var_COM_civ_', 'temp_GNSS_civ_', 'temp_COM_civ_'))\n                             and key not in ('pending_civ_access_country', 'pending_civ_com_access_country', 'var_treaty_COM_civ_receiver_num', 'var_sat_network_traffic_civ')},\n",
      "                             if not key.startswith(('eon_sat_', 'var_GNSS_civ_', 'var_COM_civ_', 'var_COM_mil_', 'temp_GNSS_civ_', 'temp_COM_civ_'))\n                             and key not in ('pending_civ_access_country', 'pending_civ_com_access_country', 'var_treaty_COM_civ_receiver_num', 'var_sat_network_traffic_civ', 'var_treaty_COM_mil_receiver_num', 'var_sat_network_traffic_mil')},\n"
    ],
    [
      317,
      317,
      "",
      "    result['countries']['A']['variables']['var_COM_civ_system_idx'] = 3\n"
    ],
    [
      339,
      340,
      "            provider_base = {factor: result['countries'][provider]['variables']['var_' + upper + '_civ_' + factor]\n",
      "            provider_base = {factor: (result['global']['arrays']['COM_civ_' + factor + '_max_array'][result['countries'][provider]['variables']['var_COM_civ_system_idx']]\n                                      if family == 'com' else result['countries'][provider]['variables']['var_' + upper + '_civ_' + factor])\n"
    ],
    [
      352,
      352,
      "",
      "                if family == 'com': expected = min(expected, result['global']['arrays']['COM_civ_' + factor + '_max_array'][result['countries'][provider]['variables']['var_COM_civ_system_idx']])\n"
    ],
    [
      514,
      514,
      "",
      "                if family == 'com': set_com_count_fixture(result, 'B', 0)\n"
    ],
    [
      523,
      524,
      "            helper(result, 'eon_sat_refresh_' + family)\n",
      "            helper(result, 'eon_sat_com_apply_civ' if family == 'com' else 'eon_sat_refresh_gnss')\n"
    ],
    [
      532,
      532,
      "",
      "                if family == 'com' and eligible: expected = min(expected, result['global']['arrays']['COM_civ_' + factor + '_max_array'][max(result['countries'][provider]['variables']['var_COM_civ_system_idx'] for provider in eligible)])\n"
    ],
    [
      537,
      538,
      "        helper(result, 'eon_sat_refresh_' + family, 'B'); helper(result, 'eon_sat_refresh_' + family, 'C')\n",
      "        helper(result, 'eon_sat_com_apply_civ' if family == 'com' else 'eon_sat_refresh_gnss', 'B'); helper(result, 'eon_sat_com_apply_civ' if family == 'com' else 'eon_sat_refresh_gnss', 'C')\n"
    ],
    [
      539,
      540,
      "        helper(result, 'eon_sat_refresh_' + family)\n",
      "        helper(result, 'eon_sat_com_apply_civ' if family == 'com' else 'eon_sat_refresh_gnss')\n"
    ],
    [
      557,
      558,
      "            if level == 0: result['countries']['B']['variables']['var_' + upper + '_civ_sat_system_num'] = 0\n",
      "            if level == 0:\n                result['countries']['B']['variables']['var_' + upper + '_civ_sat_system_num'] = 0\n                if family == 'com': set_com_count_fixture(result, 'B', 0)\n            if family == 'com': helper(result, 'eon_sat_com_sync_own', 'B')\n"
    ],
    [
      585,
      587,
      "    for traffic, capacity, existing_load, target_states, expected in ((1.25, 1000, 1000, 1, True), (.9, 1000, 900, 3, False),\n                                                                  (.9, 1000, 900, 4, True), (1, 1000, 1000, 10, False)):\n",
      "    for traffic, capacity, existing_load, target_states, expected in ((1.25, 1000, 1250, 1, True), (.9, 1000, 900, 3, False),\n                                                                  (.9, 1000, 900, 4, True), (1, 1000, 1000, 10, True)):\n"
    ],
    [
      594,
      595,
      "        groups['unchanged_COM_AI_load_policy_native_current_and_projected_thresholds_are_soft_facts'] += 1\n",
      "        groups['COM_AI_load_policy_native_projected_thresholds_remain_soft_facts'] += 1\n"
    ],
    [
      597,
      598,
      "    for country in result['countries'].values():\n",
      "    for actor, country in result['countries'].items():\n"
    ],
    [
      599,
      600,
      "        country['arrays']['COM_mil_access_array'] = ['C']\n",
      "        country['arrays']['COM_mil_access_array'] = [{'A': 'B', 'B': 'C', 'C': 'D', 'D': 'A'}[actor]]\n        country['arrays']['COM_mil_access_system_idx_array'] = [6]\n        country['arrays']['COM_mil_treaty_array'] = [{'A': 'D', 'B': 'A', 'C': 'B', 'D': 'C'}[actor]]\n"
    ]
  ],
  "tools/validation/diplomacy_package_13/test_satellites.py": [
    [
      85,
      85,
      "",
      "    for actor in result['countries']:\n        result['temp'] = {}\n        execute([('eon_sat_com_sync_own', '=', 'yes'), ('eon_sat_com_apply_civ', '=', 'yes'), ('eon_sat_com_apply_mil', '=', 'yes')], result, context(actor))\n"
    ],
    [
      125,
      125,
      "",
      "    declarations = len(result.get('timer_declarations', []))\n"
    ],
    [
      126,
      126,
      "",
      "    if accepted and family == 'com_mil':\n        return (actor, 'eon_sat_com_mil_accepted@' + peer, 180) in result.get('timer_declarations', [])[declarations:]\n"
    ],
    [
      230,
      230,
      "",
      "            if family == 'com_mil': source['set_com_count_fixture'](result, provider, 2)\n"
    ],
    [
      241,
      241,
      "",
      "        if family == 'com_mil': source['set_com_count_fixture'](result, 'B', 2)\n"
    ],
    [
      244,
      245,
      "        helper(result, 'eon_sat_refresh_' + family)\n",
      "        helper(result, 'eon_sat_com_apply_mil' if family == 'com_mil' else 'eon_sat_refresh_' + family)\n"
    ],
    [
      257,
      257,
      "",
      "                if family == 'com_mil': source['set_com_count_fixture'](result, country, 0)\n"
    ],
    [
      267,
      267,
      "",
      "            if family == 'com_mil': source['set_com_count_fixture'](result, country, 0)\n"
    ],
    [
      268,
      269,
      "        helper(result, 'eon_sat_refresh_' + family)\n",
      "        helper(result, 'eon_sat_com_apply_mil' if family == 'com_mil' else 'eon_sat_refresh_' + family)\n"
    ],
    [
      280,
      280,
      "",
      "            if family == 'com_mil': source['set_com_count_fixture'](result, provider, 2)\n"
    ],
    [
      282,
      282,
      "",
      "            if family == 'com_mil': source['set_com_count_fixture'](result, provider, 0)\n"
    ],
    [
      285,
      285,
      "",
      "            if family == 'com_mil': source['set_com_count_fixture'](result, provider, 2)\n"
    ],
    [
      293,
      293,
      "",
      "        if family == 'com_mil': source['set_com_count_fixture'](result, 'B', 2)\n"
    ],
    [
      295,
      295,
      "",
      "        if family == 'com_mil': source['set_com_count_fixture'](result, 'B', 0)\n"
    ],
    [
      299,
      299,
      "",
      "        if family == 'com_mil': source['set_com_count_fixture'](result, 'B', 2)\n"
    ],
    [
      308,
      308,
      "",
      "        if family == 'com_mil': source['set_com_count_fixture'](result, 'B', 2)\n"
    ],
    [
      309,
      310,
      "        helper(result, 'eon_sat_refresh_' + family)\n",
      "        helper(result, 'eon_sat_com_apply_mil' if family == 'com_mil' else 'eon_sat_refresh_' + family)\n"
    ],
    [
      312,
      312,
      "",
      "        if family == 'com_mil': source['set_com_count_fixture'](result, 'B', 0)\n"
    ],
    [
      316,
      316,
      "",
      "        if family == 'com_mil': source['set_com_count_fixture'](result, 'B', 2)\n"
    ],
    [
      321,
      321,
      "",
      "        if family == 'com_mil': source['set_com_count_fixture'](result, 'B', 4)\n"
    ],
    [
      426,
      427,
      "            provider_before = values(result, family, provider)\n",
      "            provider_before = values(result, family, provider, base=family == 'com_mil')\n"
    ],
    [
      435,
      436,
      "            accepted_flag = 'recently_accepted_' + service + '_' + upper.lower() + '_@B'\n",
      "            accepted_flag = ('eon_sat_com_mil_accepted@B' if family == 'com_mil' else 'recently_accepted_' + service + '_' + upper.lower() + '_@B')\n"
    ],
    [
      477,
      477,
      "",
      "            if family == 'com_mil': source['set_com_count_fixture'](result, 'B', 0 if level == 0 else 10)\n"
    ],
    [
      511,
      512,
      "            helper(result, 'eon_sat_refresh_' + family)\n",
      "            helper(result, 'eon_sat_com_apply_mil' if family == 'com_mil' else 'eon_sat_refresh_' + family)\n"
    ],
    [
      525,
      526,
      "        helper(result, 'eon_sat_refresh_' + family)\n",
      "        helper(result, 'eon_sat_com_apply_mil' if family == 'com_mil' else 'eon_sat_refresh_' + family)\n"
    ]
  ],
  "tools/validation/diplomacy_package_14/test_satellites.py": [
    [
      89,
      89,
      "",
      "        civilian['set_com_count_fixture'](result, actor, 0)\n"
    ],
    [
      105,
      105,
      "",
      "    if upper == 'COM':\n        civilian['set_com_count_fixture'](result, provider, count)\n        civilian['helper'](result, 'eon_sat_com_sync_own', recipient)\n"
    ],
    [
      148,
      149,
      "        civilian['helper'](result, 'eon_sat_refresh_' + family)\n",
      "        civilian['helper'](result, 'eon_sat_com_apply_civ' if family == 'com' else 'eon_sat_refresh_gnss')\n"
    ],
    [
      164,
      165,
      "        civilian['helper'](result, 'eon_sat_refresh_' + family)\n",
      "        civilian['helper'](result, 'eon_sat_com_apply_civ' if family == 'com' else 'eon_sat_refresh_gnss')\n"
    ],
    [
      177,
      177,
      "",
      "            if upper == 'COM': civilian['set_com_count_fixture'](result, provider, 0)\n"
    ],
    [
      180,
      180,
      "",
      "            if upper == 'COM': civilian['set_com_count_fixture'](result, provider, 2)\n"
    ],
    [
      187,
      187,
      "",
      "        if upper == 'COM': civilian['set_com_count_fixture'](result, 'B', 0)\n"
    ],
    [
      191,
      191,
      "",
      "        if upper == 'COM': civilian['set_com_count_fixture'](result, 'B', 2)\n"
    ],
    [
      201,
      201,
      "",
      "        if upper == 'COM': civilian['set_com_count_fixture'](result, 'B', 0)\n"
    ],
    [
      205,
      205,
      "",
      "        if upper == 'COM': civilian['set_com_count_fixture'](result, 'B', 2)\n"
    ],
    [
      209,
      209,
      "",
      "        if upper == 'COM': civilian['set_com_count_fixture'](result, 'B', 4)\n"
    ],
    [
      226,
      226,
      "",
      "        if family == 'com':\n            for factor in FACTORS[upper]: result['countries']['A']['variables']['var_COM_civ_' + factor + '_base'] = .01\n"
    ],
    [
      228,
      228,
      "",
      "        if upper == 'COM': civilian['set_com_count_fixture'](result, 'C', 2)\n"
    ],
    [
      232,
      233,
      "        civilian['helper'](result, 'eon_sat_refresh_' + family)\n",
      "        civilian['helper'](result, 'eon_sat_com_apply_civ' if family == 'com' else 'eon_sat_refresh_gnss')\n"
    ],
    [
      237,
      238,
      "        civilian['helper'](result, 'eon_sat_refresh_' + family)\n",
      "        civilian['helper'](result, 'eon_sat_com_apply_civ' if family == 'com' else 'eon_sat_refresh_gnss')\n"
    ],
    [
      242,
      243,
      "        assert_values(result, upper, bounds)\n",
      "        assert_values(result, upper, civilian_expected(result, family, 'C') if family == 'com' else bounds)\n"
    ],
    [
      248,
      248,
      "",
      "        if upper == 'COM': civilian['set_com_count_fixture'](result, 'C', 2)\n"
    ],
    [
      250,
      251,
      "        civilian['helper'](result, 'eon_sat_refresh_' + family)\n",
      "        if family == 'com':\n            for actor, base in (('A', .01), ('B', .03), ('C', .03)):\n                for factor in FACTORS[upper]: result['countries'][actor]['variables']['var_COM_civ_' + factor + '_base'] = base\n        civilian['helper'](result, 'eon_sat_com_apply_civ' if family == 'com' else 'eon_sat_refresh_gnss')\n"
    ],
    [
      255,
      256,
      "        civilian['helper'](result, 'eon_sat_refresh_' + family)\n",
      "        civilian['helper'](result, 'eon_sat_com_apply_civ' if family == 'com' else 'eon_sat_refresh_gnss')\n"
    ],
    [
      259,
      260,
      "        assert_values(result, upper, {factor: result['global']['arrays'][upper + '_civ_' + factor + '_max_array'][0] for factor in FACTORS[upper]})\n",
      "        assert_values(result, upper, civilian_expected(result, family) if family == 'com' else {factor: result['global']['arrays'][upper + '_civ_' + factor + '_max_array'][0] for factor in FACTORS[upper]})\n"
    ],
    [
      282,
      282,
      "",
      "            if upper == 'COM': civilian['set_com_count_fixture'](result, 'C', 2)\n"
    ],
    [
      332,
      333,
      "        for current, cap, existing, demand, expected in ((1.25, 1000, 1000, 100, True),\n",
      "        for current, cap, existing, demand, expected in ((1.25, 1000, 1250, 100, True),\n"
    ],
    [
      335,
      340,
      "                                                        (1, 1000, 1000, 1000, False),\n                                                        (1.249, 1000, 1000, 1000, False),\n                                                        (1.24901, 1000, 1000, 1000, True),\n                                                        (.999, 1000, 1000, 249, False),\n                                                        (.999, 1000, 1000, 249.1, True)):\n",
      "                                                        (1, 1000, 1000, 1000, True),\n                                                        (1.249, 1000, 1249, 1000, True),\n                                                        (1.24901, 1000, 1249.01, 1000, True),\n                                                        (1, 1000, 1000, 249, False),\n                                                        (1, 1000, 1000, 249.1, True)):\n"
    ],
    [
      347,
      351,
      "            if current < 1:\n                assert result['native_temp_divisions'] == [('B', 'temp1', cap)]\n            else: assert not result.get('native_temp_divisions')\n            groups['positive_COM_capacities_preserve_original_native_current_and_projected_traffic_thresholds'] += 1\n",
      "            assert result['native_temp_divisions'] == [('B', 'temp1', cap)]\n            groups['positive_COM_capacities_use_current_native_demand_and_literal_projected_threshold'] += 1\n"
    ],
    [
      382,
      383,
      "                        if not key.startswith(('var_GNSS_', 'var_COM_', 'var_SPY_', 'eon_sat_', 'pending_'))}\n",
      "                        if not key.startswith(('var_GNSS_', 'var_COM_', 'var_SPY_', 'var_treaty_COM_', 'var_sat_network_traffic_', 'eon_sat_', 'pending_'))}\n"
    ]
  ]
}


def package15_original_behavior_bytes(path,actual):
    if path not in BEHAVIOR_FIXTURE_EDITS:return actual
    original=baseline_bytes(path);expected=original.decode('utf-8').splitlines(keepends=True)
    for start,end,before,after in reversed(BEHAVIOR_FIXTURE_EDITS[path]):
        assert ''.join(expected[start:end])==before,('Original historical fixture seam',path,start,end)
        expected[start:end]=after.splitlines(keepends=True)
    assert actual==''.join(expected).encode('utf-8'),('Historical assertions/cases changed outside exact fixture journal',path)
    return original


def main():
    groups=Counter();hashes={};sources={}
    check_owned_existing()
    assert package15_original_bytes('unowned/sentinel.txt',b'immutable sentinel')==b'immutable sentinel'
    groups['byte_inverse_passthrough_outside_exact_eleven_gameplay_paths']+=1
    for path in sorted(EXISTING):
        actual=(ROOT/path).read_bytes();original=baseline_bytes(path)
        hashes[path]=hashlib.sha256(actual).hexdigest()
        assert package15_original_bytes(path,actual)==original
        groups['eleven_owned_paths_strict_whole_file_contract_and_inverse_BOM_EOL']+=1
        try:package15_original_bytes(path,actual+b'\n# unowned outer mutation\n')
        except AssertionError:pass
        else:raise AssertionError(('Unowned outer mutation accepted',path))
        groups['eleven_memory_only_unowned_outer_mutation_rejection_cases_no_files_written']+=1
        if path in SCRIPT_PATHS:sources[path]=ast(actual)
    trees=('common','history','events','interface','gfx','localisation','music','map','sound','portraits','tutorial','descriptions','scenario_tests','descriptor.mod','era_of_nations.mod','thumbnail.png')
    before=set(subprocess.check_output(['git','ls-tree','-r','--name-only',BASELINE,'--',*trees],cwd=ROOT).decode().splitlines())
    assert len(before)==68321,len(before)
    changed=set(subprocess.check_output(['git','diff','--name-only',BASELINE,'--',*trees],cwd=ROOT).decode().splitlines())
    added=set(subprocess.check_output(['git','ls-files','--others','--exclude-standard','--',*trees],cwd=ROOT).decode().splitlines())
    changed -= package16_historical_existing(BASELINE) | LATER_PACKAGE16_NEW | package17_historical_existing(BASELINE) | LATER_PACKAGE17_NEW
    added -= LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW
    assert changed==EXISTING and not added,(changed^EXISTING,added)
    assert not set(subprocess.check_output(['git','diff','--name-only','--diff-filter=D',BASELINE,'--',*trees],cwd=ROOT).decode().splitlines())
    groups['exact_full_gameplay_tree_eleven_changed_no_new_deleted_unowned_bytes']+=1
    expected_ids={key for values in APPENDED.values() for text in values for key in blocks(text.encode('utf-8'))}
    assert len(expected_ids)==6
    definitions=Counter()
    for folder in ('scripted_effects','scripted_triggers'):
        for path in (ROOT/'common'/folder).glob('*.txt'):
            definitions.update(key for key,op,value in ast(path.read_bytes()) if key in expected_ids)
    for key in sorted(expected_ids):
        assert definitions[key]==1,('New helper definition collision',key)
        groups['six_appended_helper_global_identity_uniqueness']+=1
    fx_nodes=one(sources[FX],'eon_sat_com_network_refresh')
    network_body=one(fx_nodes,'if')
    assert one(network_body,'limit')==ast('exists = yes NOT = { check_variable = { THIS.id = eon_sat_removed_country } }')
    loops=[value for key,op,value in network_body if key=='for_each_scope_loop']
    assert one(loops[-2],'array')=='eon_sat_com_network_bases'
    assert loops[-2]==ast('array = eon_sat_com_network_bases eon_sat_com_sync_own = yes')
    assert loops[-1]==ast('array = eon_sat_com_network_actors eon_sat_com_apply_civ = yes eon_sat_com_apply_mil = yes')
    groups['snapshot_all_bases_before_both_aggregates_no_per_aggregate_recompute_race']+=1
    scratch=('eon_sat_com_network_providers','eon_sat_com_network_actors','eon_sat_com_network_bases')
    assert [v for k,o,v in network_body if k=='clear_array']==list(scratch)*2
    all_network_rows=list(rows(network_body))
    assert not any(k in ('every_country','every_possible_country','ROOT') or 'ROOT.' in str(v) for k,o,v in all_network_rows)
    for k,o,v in all_network_rows:
        if k=='add_to_array':
            target=one(v,'array')
            assert target in (scratch[0],'PREV.'+scratch[0],'PREV.'+scratch[1],'PREV.PREV.'+scratch[1],'PREV.'+scratch[2],'PREV.PREV.'+scratch[2]),target
    groups['three_initiating_scope_work_arrays_cleared_twice_nested_PREV_ownership_no_global_daily_ROOT']+=1
    graph={}
    for path in (FX,EXT):
        for key,op,value in sources[path]:
            if isinstance(value,list):graph[key]={name for name,operator,node in rows(value) if name.startswith('eon_sat_') and not isinstance(node,list) and node=='yes'}
    graph.update({key:{name for name,op,v in rows(value) if name.startswith('eon_sat_') and v=='yes'} for key,operator,value in sources[NFX] if key in ('update_COM_system_stats','add_treaty_COM_civ_receiver_num','add_treaty_COM_mil_receiver_num')})
    for path in (TR,ETR):
        for key,op,value in sources[path]:
            if isinstance(value,list):graph[key]={name for name,operator,node in rows(value) if name.startswith('eon_sat_') and not isinstance(node,list) and node=='yes'}
    graph['eon_sat_com_sync_own'].add('update_COM_system_stats')
    graph['update_COM_system_stats'].update(('add_treaty_COM_civ_receiver_num','add_treaty_COM_mil_receiver_num'))
    def visit(key,trail):
        assert key not in trail,('Recursive scripted helper path',trail,key)
        for child in graph.get(key,set()):visit(child,trail+(key,))
    for key in expected_ids:
        if key in graph:visit(key,())
        groups['six_helper_paths_acyclic_canonical_stats_leafs_never_enter_refresh']+=1
    own=one(sources[FX],'eon_sat_com_sync_own');own_body=one(own,'if')
    assert [row for row in own_body if row[0] not in ('limit','if')]==ast('eon_sat_com_canonical_access = yes eon_sat_com_canonical_treaties = yes eon_sat_com_mil_canonical_access = yes eon_sat_com_mil_canonical_treaties = yes update_COM_system_stats = yes')
    valid_calcs=[v for k,o,v in own_body if k=='if']
    assert valid_calcs==[ast('limit = { eon_sat_com_valid_level = yes } calculate_COM_civ_gui_vars = yes'),ast('limit = { eon_sat_com_mil_valid_level = yes } calculate_COM_mil_gui_vars = yes')]
    groups['unchanged_own_stats_physical_i_arrays_then_two_independently_guarded_native_calculators']+=1
    for role,path,trpath in (('civ',FX,TR),('mil',EXT,ETR)):
        p='eon_sat_com'+('_mil' if role=='mil' else '')
        guard=one(sources[trpath],p+'_service_to_prev')
        assert ('check_variable','=',ast('var_COM_'+role+'_receiver_cap > 0')) in guard
        assert ('is_in_array','=',ast('array = COM_'+role+'_treaty_array value = PREV.id')) in guard
        assert ('is_in_array','=',ast('array = PREV.COM_'+role+'_access_array value = THIS.id')) in guard
        assert not any('bonus' in str(v) or 'traffic' in str(v) for k,o,v in rows(guard))
        assert one(sources[path],'eon_sat_refresh_com'+('_mil' if role=='mil' else ''))==ast('eon_sat_com_network_refresh = yes')
        groups['two_literal_reciprocal_service_execution_positive_capacity_no_congestion_oscillation']+=1
        apply=one(sources[path],'eon_sat_com_apply_'+role)
        access_loop=next(v for k,o,v in apply if k=='for_each_scope_loop')
        assert one(one(access_loop,'if'),'limit')==ast(p+'_service_to_prev = yes')
        groups['two_native_aggregate_floors_and_tier_caps_preserved_separate_service_guard']+=1
        load=one(sources[NFX],'add_treaty_COM_'+role+'_receiver_num')
        assert one(one(one(load,'for_each_scope_loop'),'if'),'limit')==ast('PREV = { '+p+'_service_to_prev = yes }')
        groups['two_native_demand_weight_formulas_guarded_by_same_service_condition']+=1
        for kind,number in (('request',1),('offer',2)):
            begin=one(sources[path],p+'_begin_'+kind)
            outer=one(begin,'if')
            assert one(outer,'limit')==ast(p+'_new_ready = yes')
            assert outer[1:3]==ast('eon_sat_com_sync_own = yes PREV = { eon_sat_com_sync_own = yes }')
            accept=one(sources[path],p+'_accept_'+kind);owned=one(accept,'if')
            assert one(owned,'limit')==ast(p+'_record_matches = yes check_variable = { '+p+'_kind = '+str(number)+' }')
            assert owned[1:3]==ast('eon_sat_com_sync_own = yes PREV = { eon_sat_com_sync_own = yes }')
            flags=[one(v,'flag') for k,o,v in rows(accept) if k=='set_country_flag' and isinstance(v,list)]
            assert flags==['eon_sat_com_'+role+'_accepted@PREV']
            groups['four_owned_send_reply_outer_identity_guard_before_fresh_stats_typed180_day_write']+=1
        daily=one(sources[path],'eon_sat_extended_daily_cleanup' if role=='mil' else 'eon_sat_daily_cleanup')
        cleanup_index=next(i for i,row in enumerate(daily) if row[0]==p+'_cleanup')
        assert daily[cleanup_index-1]==('eon_sat_com_network_refresh','=','yes')
        partner=next(v for k,o,v in daily if k=='if')
        assert one(partner,'limit')==ast('has_country_flag = '+p+'_pending check_variable = { '+p+'_partner > 0 }')
        assert one(partner,'var:'+p+'_partner')==ast('eon_sat_com_network_refresh = yes')
        groups['two_daily_pending_partner_sequential_graph_before_fresh_authorization_other_family_order_exact']+=1
        ai=one(sources[NTR],'NOT_share_COM_'+role+'_satellites_above_network_traffic_limit')
        numerator=one(ai,'if')
        assert one(numerator,'limit')==ast('check_variable = { ROOT.var_COM_'+role+'_receiver_cap > 0 }')
        current=next(v for k,o,v in numerator if k=='if')
        assert one(current,'limit')==ast('NOT = { ROOT = { '+p+'_service_to_prev = yes } }')
        assert ('check_variable','=',ast('temp1 > 1.249')) in numerator
        assert one(ai,'else')==ast('always = yes')
        assert not any(k in ('set_variable','add_to_variable','subtract_from_variable','multiply_variable','divide_variable','set_country_flag','clear_variable') for k,o,v in rows(ai))
        assert not any('var_sat_network_traffic' in str(v) for k,o,v in rows(ai))
        groups['two_AI_all_positive_traffic_projections_existing_client_once_strict1249_temporary_only']+=1
        action=one(one(sources[ACTION],'scripted_diplomatic_actions'),'revoke_'+role+'_com_access')
        oldaction=one(one(ast(baseline_bytes(ACTION)),'scripted_diplomatic_actions'),'revoke_'+role+'_com_access')
        assert {k for k,o,v in action}=={k for k,o,v in oldaction}
        modifier=next(v for k,o,v in one(action,'ai_desire') if k=='modifier' and ('add','=','-1000') in v)
        assert one(modifier,'ROOT')==ast('OR = { has_country_flag = eon_sat_com_'+role+'_accepted@PREV has_country_flag = recently_accepted_mil_com_@PREV }')
        groups['two_native_revoke_AI_weights_unchanged_typed_OR_readonly_legacy_actor_scope']+=1
    for path in SCRIPT_PATHS:
        owned_nodes=(one(sources[path],'scripted_diplomatic_actions') if path==ACTION else sources[path])
        owned_ids=set(replacements().get(path,{}))|{key for text in APPENDED.get(path,()) for key in blocks(text.encode('utf-8'))}
        for key,op,value in owned_nodes:
            if key not in owned_ids:continue
            for k,o,v in rows(value):
                if k=='NOT':assert isinstance(v,list) and len(v)==1,(path,key,v)
        groups['seven_owned_script_ranges_native_NOT_single_child_NOR_guard']+=1
    changed_existing_blocks=0
    for path,names in replacements().items():
        before_data=baseline_bytes(path);actual_data=(ROOT/path).read_bytes()
        before_blocks=blocks(before_data,1 if path==ACTION else 0)
        now_blocks=blocks(actual_data,1 if path==ACTION else 0)
        for key in names:
            a=before_blocks[key];b=now_blocks[key]
            changed_existing_blocks+=before_data[a['start']:a['end']]!=actual_data[b['start']:b['end']]
    assert changed_existing_blocks==20
    native=one(sources[ACTION],'scripted_diplomatic_actions');old_native=one(ast(baseline_bytes(ACTION)),'scripted_diplomatic_actions')
    assert len(native)==len(old_native) and {k for k,o,v in native}=={k for k,o,v in old_native}
    global_native=[key for path in (ROOT/'common/scripted_diplomatic_actions').glob('*.txt') for key,op,value in one(ast(path.read_bytes()),'scripted_diplomatic_actions')]
    global_native = package16_historical_actions(global_native)
    assert len(global_native)==len(set(global_native))==65
    groups['all65_native_IDs_no_added_action_or_cost_visibility_acceptance_changes']+=1
    untouched=('update_COM_system_stats','calculate_COM_mil_gui_vars','calculate_COM_civ_gui_vars','update_sat_systems_stats','check_sat_systems_min_sat_num','add_satellite_from_payload')
    for key in untouched:
        assert one(sources[NFX],key)==one(ast(baseline_bytes(NFX)),key)
        groups['six_whole_native_stats_calculators_capacity_sums_GUI_fullentry_raw_inventory_news_downgrade_preserved']+=1
    for key in ('COM_mil_button_update','COM_civ_button_update'):
        assert one(sources[NFX],key)==one(ast(baseline_bytes(NFX)),key)+ast('eon_sat_com_network_refresh = yes')
        groups['two_GUI_selector_original_body_exact_one_final_network_entry']+=1
    for path in ('common/scripted_effects/00_missiles_models.txt','common/scripted_guis/missiles_scripted_gui.txt','common/on_actions/01_on_actions.txt','common/on_actions/eon_satellite_on_actions.txt','common/on_actions/eon_satellite_extended_on_actions.txt','events/missiles_events.txt'):
        assert (ROOT/path).read_bytes()==baseline_bytes(path)
        groups['six_original_tables_GUI_weekly_annex_news_source_files_unchanged']+=1
    locales={}
    for path in LOCALES:
        data=(ROOT/path).read_bytes();pairs=re.findall(r'^ ([\w.]+):0 "(.*)"$',data.decode('utf-8-sig'),re.M)
        assert len(pairs)==len(dict(pairs))==(34 if 'extended' in path else 18)
        locales[path]=dict(pairs)
        groups['four_bilingual_files_single_granted_row_only_keys18_34_BOM_LF']+=1
    for name in ('eon_satellite','eon_satellite_extended'):
        en=locales['localisation/english/'+name+'_l_english.yml'];ru=locales['localisation/russian/'+name+'_l_russian.yml']
        assert en.keys()==ru.keys()
        for key in en:
            assert re.findall(r'\[.*?\]|\$[\w.]+\$',en[key])==re.findall(r'\[.*?\]|\$[\w.]+\$',ru[key])
            groups['52_existing_bilingual_keys_placeholders_preserved']+=1
    for package in ('01','02'):
        path='tools/validation/diplomacy_package_'+package+'/test_source.py'
        assert package16_original_validator_bytes(path,(ROOT/path).read_bytes())==baseline_bytes(path),path
        groups['source01_02_entire_validator_byte_unchanged']+=1
    for path in sorted(BEHAVIOR_FIXTURE_EDITS):
        actual=(ROOT/path).read_bytes();original=baseline_bytes(path)
        assert package15_original_behavior_bytes(path,actual)==original
        groups['three_exact_public_historical_fixture_executor_scope_journals_whole_original_bytes_inverse']+=1
        before_increments=[line for line in original.decode('utf-8').splitlines() if 'groups[' in line and '+=' in line]
        after_increments=[line for line in actual.decode('utf-8').splitlines() if 'groups[' in line and '+=' in line]
        label_renames={
            'tools/validation/diplomacy_package_12/test_satellites.py': ('unchanged_COM_AI_load_policy_native_current_and_projected_thresholds_are_soft_facts','COM_AI_load_policy_native_projected_thresholds_remain_soft_facts'),
            'tools/validation/diplomacy_package_14/test_satellites.py': ('positive_COM_capacities_preserve_original_native_current_and_projected_traffic_thresholds','positive_COM_capacities_use_current_native_demand_and_literal_projected_threshold'),
        }
        if path in label_renames:
            before_label,after_label=label_renames[path]
            assert sum(before_label in line for line in before_increments)==1
            before_increments=[line.replace(before_label,after_label) for line in before_increments]
        assert before_increments==after_increments,('Original actual-source scenario definitions changed',path)
        groups['three_historical_actual_source_scenario_group_increments_retained']+=1
    installed=Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV')
    effects=(installed/'documentation/effects_documentation.md').read_text(encoding='utf-8-sig')
    triggers=(installed/'documentation/triggers_documentation.md').read_text(encoding='utf-8-sig')
    for name in ('for_each_scope_loop','clear_array','add_to_array','force_update_dynamic_modifier','set_temp_variable','divide_temp_variable','add_to_temp_variable'):
        assert '\n## '+name+'\n' in effects
        groups['seven_installed_primary_effect_API_definitions']+=1
    for name in ('if','set_temp_variable','divide_temp_variable','is_in_array','check_variable'):
        assert '\n## '+name+'\n' in triggers
        groups['five_installed_primary_trigger_API_definitions']+=1
    fin=(installed/'common/national_focus/finland.txt').read_text(encoding='utf-8-sig')
    prc=(installed/'common/national_focus/china_communist_sea.txt').read_text(encoding='utf-8-sig')
    assert re.search(r'add_to_array\s*=\s*{\s*PREV\.PREV\.FIN_[\w]+_array\s*=\s*THIS',fin)
    assert 'array = PREV.PREV.PRC_northern_target_states_array' in prc
    groups['two_shipped_primary_nested_PREV_PREV_country_array_references']+=2
    boundary=groups['byte_inverse_passthrough_outside_exact_eleven_gameplay_paths']+groups['eleven_memory_only_unowned_outer_mutation_rejection_cases_no_files_written']
    print(json.dumps({'all_passed':True,'total_cases':sum(groups.values()),'source_API_cases':sum(groups.values())-boundary,'source_byte_adapter_boundary_cases':boundary,'groups':groups,'baseline':BASELINE,'baseline_gameplay_files':len(before),'existing_gameplay_files_byte_preserved':len(before)-len(EXISTING),'owned_existing_gameplay_files':len(EXISTING),'new_gameplay_files':0,'owned_old_block_boundaries':22,'changed_existing_blocks':changed_existing_blocks,'unchanged_owned_revoke_blocks':2,'appended_scripted_helper_IDs':6,'native_action_count':65,'new_locale_keys':0,'final_gameplay_sha256':hashes,'runtime_verified':False},indent=2))


if __name__=='__main__':
    main()
