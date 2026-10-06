"""Exact civilian first-tier, negative SPY base and projected COM AI source proof.

Historical restorations are byte views only; behavioral executors use current code.
"""
from pathlib import Path
from collections import Counter
from functools import lru_cache
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASELINE = 'f25dcfa040df4de947fe87e7a70f8f5fdd9ed659'
OWNED = {
 'common/scripted_triggers/eon_satellite_triggers.txt': {'eon_sat_gnss_request_terms','eon_sat_gnss_offer_terms','eon_sat_com_request_terms','eon_sat_com_offer_terms'},
 'common/scripted_effects/eon_satellite_effects.txt': {'eon_sat_refresh_gnss','eon_sat_refresh_com'},
 'common/scripted_effects/00_missiles_scripted_effects.txt': {'calculate_SPY_mil_gui_vars'},
 'common/scripted_triggers/MD_missile_scripted_triggers.txt': {'NOT_share_COM_mil_satellites_above_network_traffic_limit','NOT_share_COM_civ_satellites_above_network_traffic_limit'},
}
LOCALES = {f'localisation/{language}/eon_satellite_l_{language}.yml' for language in ('english','russian')}
EXISTING = set(OWNED) | LOCALES
NEW = set()
LOCALE_KEYS = {'eon_sat_'+family+'_'+suffix+'_tt' for family in ('gnss','com') for suffix in ('available','granted')}
LOCALE_SENTENCE = {
 'english': " First-tier service also requires a positive count of the corresponding satellites in the provider's current system statistics.",
 'russian': " \u0414\u043b\u044f \u0443\u0441\u043b\u0443\u0433\u0438 \u043f\u0435\u0440\u0432\u043e\u0433\u043e \u0443\u0440\u043e\u0432\u043d\u044f \u0442\u0435\u043a\u0443\u0449\u0438\u0435 \u043f\u043e\u043a\u0430\u0437\u0430\u0442\u0435\u043b\u0438 \u0441\u0438\u0441\u0442\u0435\u043c\u044b \u043f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a\u0430 \u0442\u0430\u043a\u0436\u0435 \u0434\u043e\u043b\u0436\u043d\u044b \u043f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0442\u044c \u043d\u0430\u043b\u0438\u0447\u0438\u0435 \u0441\u043e\u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0443\u044e\u0449\u0438\u0445 \u0441\u043f\u0443\u0442\u043d\u0438\u043a\u043e\u0432.",
}

TOKEN = re.compile(rb'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|[=<>!]+|[^\s{}=<>!#"]+')


def boundary_blocks(data):
    tokens = [match for match in TOKEN.finditer(data) if not match[0].startswith(b'#')]
    stack, result = [], []
    for index, token in enumerate(tokens):
        if token[0] == b'{':
            block = {'key': tokens[index - 2][0].decode().lstrip('\ufeff'),
                     'start': tokens[index - 2].start(), 'depth': len(stack),
                     'parent': stack[-1]['key'] if stack else None}
            stack.append(block); result.append(block)
        elif token[0] == b'}':
            assert stack, 'Extra closing brace'
            stack.pop()['end'] = token.end()
    assert not stack, 'Unclosed block'
    return result


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



@lru_cache(maxsize=64)
def baseline_bytes(path):
    return subprocess.check_output(['git','show',BASELINE+':'+path],cwd=ROOT)


def owned_blocks(data, path):
    found={block['key']:block for block in boundary_blocks(data)
           if block['depth']==0 and block['key'] in OWNED[path]}
    assert found.keys()==OWNED[path],('Owned identities changed',path,found.keys())
    assert sum(block['depth']==0 and block['key'] in OWNED[path] for block in boundary_blocks(data))==len(found),('Duplicate owned identity',path)
    return found


def expected_block(path, name, original):
    text=original.decode('utf-8')
    if path.endswith('eon_satellite_triggers.txt') or path.endswith('eon_satellite_effects.txt'):
        family='gnss' if 'gnss' in name else 'com'
        idx='var_'+family.upper()+'_civ_system_idx'
        marker='check_variable = { '+idx+' > 0 }'
        usable='OR = { '+marker+' AND = { check_variable = { '+idx+' = 0 } check_variable = { var_'+family.upper()+'_civ_sat_system_num > 0 } } }'
        assert text.count(marker)==1,(name,'Original provider guard')
        text=text.replace(marker,usable,1)
        if path.endswith('eon_satellite_effects.txt'):
            for before,after in (('eon_sat_'+family+'_highest = 0','eon_sat_'+family+'_highest = -1'),
                                 ('eon_sat_'+family+'_highest > 0','eon_sat_'+family+'_highest > -1')):
                assert text.count(before)==1,(name,before)
                text=text.replace(before,after,1)
    elif path.endswith('00_missiles_scripted_effects.txt'):
        before='clamp_variable = { var = var_SPY_mil_air_weather_penalty_base min = var_SPY_mil_air_weather_penalty_min }'
        after='clamp_variable = { var = var_SPY_mil_air_weather_penalty_base min = global.SPY_mil_air_weather_penalty_max_array^var_SPY_mil_system_idx max = var_SPY_mil_air_weather_penalty_min }'
        assert text.count(before)==1;text=text.replace(before,after,1)
    else:
        role='mil' if '_mil_' in name else 'civ'
        assert text.startswith(name+' = {\n') and text.endswith('\n}')
        original_body=text[len(name+' = {\n'):-2]
        text=(name+' = {\n\tif = {\n\t\tlimit = { check_variable = { ROOT.var_COM_'+role+'_receiver_cap > 0 } }\n'
              +original_body+'\n\t}\n\telse = { always = yes }\n}')
    return text.encode('utf-8')


def expected_locale(path, original):
    language='english' if '/english/' in path else 'russian'
    text=original.decode('utf-8-sig');sentence=LOCALE_SENTENCE[language]
    for key in sorted(LOCALE_KEYS):
        lines=re.findall(r'^ '+re.escape(key)+r':0 ".*"$',text,re.M)
        assert len(lines)==1,(path,key)
        text=text.replace(lines[0],lines[0][:-1]+sentence+'"',1)
    return b'\xef\xbb\xbf'+text.encode('utf-8')


def package14_original_bytes(path, actual):
    """Restore exactly nine named bodies and four named locale lines per language."""
    if path not in EXISTING:return actual
    old=baseline_bytes(path)
    assert actual.startswith(b'\xef\xbb\xbf')==old.startswith(b'\xef\xbb\xbf'),path
    assert actual.endswith(b'\n')==old.endswith(b'\n'),path
    assert (b'\r\n' in actual)==(b'\r\n' in old) and b'\r' not in actual.replace(b'\r\n',b''),path
    if path in LOCALES:
        assert actual==expected_locale(path,old),('Only literal four existing locale sentences may change',path)
        return old
    before,now=owned_blocks(old,path),owned_blocks(actual,path)
    restored=actual
    for name,block in sorted(now.items(),key=lambda item:item[1]['start'],reverse=True):
        original=before[name];old_body=old[original['start']:original['end']]
        current=actual[block['start']:block['end']]
        assert current==expected_block(path,name,old_body),('Unexpected changes inside owned block',path,name)
        restored=restored[:block['start']]+old_body+restored[block['end']:]
    assert restored==old,('Unrelated package14 gameplay bytes changed',path)
    return restored


@lru_cache(maxsize=32)
def package14_historical_existing(baseline):
    return frozenset(subprocess.check_output(['git','ls-tree','-r','--name-only',baseline,'--',*sorted(EXISTING)],cwd=ROOT).decode().splitlines())


def check_owned_existing():
    for path in sorted(EXISTING):package14_original_bytes(path,(ROOT/path).read_bytes())


def main():
    groups=Counter();hashes={};sources={};old_sources={}
    check_owned_existing()
    assert package14_original_bytes('unowned/path.txt',b'immutable sentinel')==b'immutable sentinel'
    groups['byte_adapter_passthrough_outside_exact_owned_paths']+=1
    for path in sorted(EXISTING):
        data=(ROOT/path).read_bytes();old=baseline_bytes(path)
        assert package14_original_bytes(path,data)==old
        assert b'\r' not in data and data.endswith(b'\n')
        assert data.startswith(b'\xef\xbb\xbf')==path.endswith('.yml')
        assert '\ufffd' not in data.decode('utf-8-sig')
        hashes[path]=hashlib.sha256(data).hexdigest()
        groups['all_six_existing_encoding_and_exact_literal_inside_outside_boundaries']+=1
        if path in OWNED:
            sources[path]=ast(data);old_sources[path]=ast(old)
            assert [key for key,op,value in sources[path]]==[key for key,op,value in old_sources[path]]
            for key in sorted(OWNED[path]):
                assert one(sources[path],key)==ast(expected_block(path,key,old[owned_blocks(old,path)[key]['start']:owned_blocks(old,path)[key]['end']]))[0][2]
                groups['exact_nine_owned_IDs_scope_and_all_unrelated_body_fields_preserved']+=1
        try:package14_original_bytes(path,data+b'# outside-range memory-only probe\n')
        except AssertionError:pass
        else:raise AssertionError(('Unowned outer bytes accepted',path))
        groups['byte_adapter_rejects_unowned_outer_file_edit_no_files_written']+=1
    trees=('common','history','events','interface','gfx','localisation','music','map','sound','portraits','tutorial','descriptions','scenario_tests','descriptor.mod','era_of_nations.mod','thumbnail.png')
    before=subprocess.check_output(['git','ls-tree','-r','--name-only',BASELINE,'--',*trees],cwd=ROOT).decode().splitlines()
    changed=subprocess.check_output(['git','diff','--name-only',BASELINE,'--',*trees],cwd=ROOT).decode().splitlines()
    untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard','--',*trees],cwd=ROOT).decode().splitlines()
    assert len(before)==68321 and set(changed)==EXISTING and not untracked and not NEW
    groups['all_68315_unrelated_gameplay_files_byte_preserved_no_gameplay_additions']+=1
    native=[]
    for path in before:
        if path.startswith('common/scripted_diplomatic_actions/') and path.endswith('.txt'):
            data=(ROOT/path).read_bytes();assert data==baseline_bytes(path),('Native visibility_cost_consent_AI_weights_or_scope_modified',path)
            native.extend(b['key'] for b in boundary_blocks(data) if b['depth']==1 and b['parent']=='scripted_diplomatic_actions')
    assert len(native)==len(set(native))==65
    groups['all_65_native_IDs_and_all_native_action_bytes_weights_and_lifecycle_preserved']+=1
    tr=sources['common/scripted_triggers/eon_satellite_triggers.txt'];fx=sources['common/scripted_effects/eon_satellite_effects.txt']
    original_fx=ast((ROOT/'common/scripted_effects/00_missiles_scripted_effects.txt').read_bytes())
    labels=(ROOT/'localisation/english/MD_missiles_l_english.yml').read_text(encoding='utf-8-sig')
    models=ast((ROOT/'common/scripted_effects/00_missiles_models.txt').read_bytes())
    bonus={'gnss':('production_speed_buildings_factor','production_speed_infrastructure_factor','local_resources_factor'),
           'com':('political_power_factor','decryption_factor','encryption_factor','intel_network_gain_factor','operation_outcome')}
    for family in ('gnss','com'):
        upper=family.upper();idx='var_'+upper+'_civ_system_idx';prefix='eon_sat_'+family+'_'
        usable=ast('OR = { check_variable = { '+idx+' > 0 } AND = { check_variable = { '+idx+' = 0 } check_variable = { var_'+upper+'_civ_sat_system_num > 0 } } }')[0]
        request=one(tr,prefix+'request_terms');offer=one(tr,prefix+'offer_terms')
        assert usable in one(request,'PREV') and usable in offer
        groups['two_family_request_PREV_provider_offer_current_provider_physical_first_tier_guard']+=1
        refresh=one(fx,'eon_sat_refresh_'+family)
        assert ('set_temp_variable','=',ast(prefix+'highest = -1')) in refresh
        loop=one(refresh,'for_each_scope_loop');provider=one(one(loop,'if'),'limit')
        assert usable in provider and ('NOT','=',ast('has_war_with = PREV')) in provider
        gated=[value for key,op,value in refresh if key=='if' and one(value,'limit')==ast('check_variable = { '+prefix+'highest > -1 }')]
        assert len(gated)==1 and sum(key=='clamp_variable' for key,op,value in gated[0])==len(bonus[family])
        groups['two_family_minus_one_sentinel_native_zero_caps_current_provider_recipient_scope']+=1
        array=upper+'_civ_systems_array'
        assert one(original_fx,'set_'+upper+'_civ_systems')==ast('clear_array = '+array+' '+' '.join('add_to_array = { '+array+' = '+str(i)+' }' for i in range(8)))
        label='GNSS 5 m' if family=='gnss' else '56 kbits/s'
        assert re.search(r'^ '+upper+'_civ_idx_0_loc: "'+re.escape(label)+r'"$',labels,re.M)
        groups['two_native_system_arrays_zero_to_seven_and_actual_first_tier_UI_labels']+=1
        for field in bonus[family]:
            name='global.'+upper+'_civ_'+field+'_max_array'
            values=[one(v,name) for key,op,v in rows(models) if key=='add_to_array' and isinstance(v,list) and any(k==name for k,o,n in v)]
            assert len(values)==8 and float(values[0])>0,(name,values)
            groups['eight_original_civil_modifier_tables_native_zero_entry_positive_cap']+=1
    spy=one(original_fx,'calculate_SPY_mil_gui_vars')
    clamp=ast('var = var_SPY_mil_air_weather_penalty_base min = global.SPY_mil_air_weather_penalty_max_array^var_SPY_mil_system_idx max = var_SPY_mil_air_weather_penalty_min')
    assert ('clamp_variable','=',clamp) in spy
    groups['negative_SPY_single_base_field_ordered_strongest_min_weakest_max_no_other_formula_change']+=1
    def table(name):return [float(one(v,name)) for k,o,v in rows(models) if k=='add_to_array' and isinstance(v,list) and any(a==name for a,b,c in v)]
    strong=table('global.SPY_mil_air_weather_penalty_max_array');weak=table('global.SPY_mil_air_weather_penalty_min_array')
    assert len(strong)==len(weak)==8
    for index,(lo,hi) in enumerate(zip(strong,weak)):
        assert lo<0 and lo<=hi<=0,(index,lo,hi)
        groups['eight_preserved_negative_SPY_native_table_bound_orderings']+=1
    ai=sources['common/scripted_triggers/MD_missile_scripted_triggers.txt']
    for role in ('mil','civ'):
        key='NOT_share_COM_'+role+'_satellites_above_network_traffic_limit';body=one(ai,key)
        assert {k for k,o,v in body}=={'if','else'}
        assert one(one(body,'if'),'limit')==ast('check_variable = { ROOT.var_COM_'+role+'_receiver_cap > 0 }')
        assert one(body,'else')==ast('always = yes')
        assert [row for row in one(body,'if') if row[0]!='limit']==one(old_sources['common/scripted_triggers/MD_missile_scripted_triggers.txt'],key)
        groups['two_native_conditional_AI_projection_no_nonpositive_division_original_positive_OR_policy_preserved']+=1
        action=(ROOT/'common/scripted_diplomatic_actions/MD_missile_scripted_diplomatic_actions.txt').read_text()
        assert action.count(key+' = yes')==2
        groups['two_original_soft_AI_offer_and_revoke_desire_callers_not_human_hard_bans']+=1
    locales={}
    for language in ('english','russian'):
        path=f'localisation/{language}/eon_satellite_l_{language}.yml';data=(ROOT/path).read_text(encoding='utf-8-sig')
        pairs=re.findall(r'^ ([\w.]+):0 "(.*)"$',data,re.M);assert len(pairs)==len(dict(pairs))==18
        locales[language]=dict(pairs)
        for key in LOCALE_KEYS:
            assert locales[language][key].endswith(LOCALE_SENTENCE[language])
            groups['eight_existing_locale_first_tier_sentences_only_native_text_preserved']+=1
    assert locales['english'].keys()==locales['russian'].keys()
    for key in locales['english']:
        assert re.findall(r'\[.*?\]|\$[\w.]+\$',locales['english'][key])==re.findall(r'\[.*?\]|\$[\w.]+\$',locales['russian'][key])
        groups['18_existing_bilingual_IDs_placeholders_and_macros_preserved']+=1
    for path,nodes in sources.items():
        for key,op,value in rows(nodes):
            if key=='NOT':assert isinstance(value,list) and len(value)==1,('Native NOT=NOR requires one explicit child',path,value)
        groups['four_script_native_single_child_NOT_no_logical_semantics_drift']+=1
    protected=('common/scripted_effects/00_missiles_models.txt','common/scripted_guis/missiles_scripted_gui.txt',
               'common/scripted_effects/eon_satellite_extended_effects.txt','common/scripted_triggers/eon_satellite_extended_triggers.txt',
               'common/decisions/eon_satellite_extended_decisions.txt','common/decisions/categories/eon_satellite_extended_categories.txt',
               'common/on_actions/eon_satellite_extended_on_actions.txt','localisation/english/eon_satellite_extended_l_english.yml','localisation/russian/eon_satellite_extended_l_russian.yml')
    for path in protected:
        assert (ROOT/path).read_bytes()==baseline_bytes(path),path
        groups['nine_protected_original_cap_tables_GUI_and_all_previous_extended13_files_byte_exact']+=1
    before_shared=one(old_sources['common/scripted_effects/00_missiles_scripted_effects.txt'],'update_COM_system_stats')
    assert one(original_fx,'update_COM_system_stats')==before_shared
    assert ('add_to_variable','=',ast('var_COM_mil_receiver_cap = temp1')) in list(rows(before_shared))
    assert ('add_to_variable','=',ast('var_COM_civ_receiver_cap = temp2')) in list(rows(before_shared))
    groups['original_shared_COM_both_capacity_sums_and13fixes_untouched_false_overwrite_claim_not_repeated']+=1
    old12_path='tools/validation/diplomacy_package_12/test_satellites.py'
    old12=baseline_bytes(old12_path).decode('utf-8');expected12=old12
    patches=[
        ("            elif mutation == 'provider dormant zero': result['countries']['B']['variables']['var_' + upper + '_civ_system_idx'] = 0\n",
         "            elif mutation == 'provider dormant zero':\n                result['countries']['B']['variables']['var_' + upper + '_civ_system_idx'] = 0\n                result['countries']['B']['variables']['var_' + upper + '_civ_sat_system_num'] = 0\n"),
        ("            result = state(); result['countries']['B']['variables']['var_' + upper + '_civ_system_idx'] = level\n            ready = send(result, family)",
         "            result = state(); result['countries']['B']['variables']['var_' + upper + '_civ_system_idx'] = level\n            if level == 0: result['countries']['B']['variables']['var_' + upper + '_civ_sat_system_num'] = 0\n            ready = send(result, family)"),
    ]
    for before_patch,after_patch in patches:
        assert expected12.count(before_patch)==1,('Original old12 fixture seam changed',before_patch)
        expected12=expected12.replace(before_patch,after_patch,1)
        groups['two_exact_old12_unavailable_first_tier_fixture_locations_three_statements_only']+=1
    assert (ROOT/old12_path).read_bytes()==expected12.encode('utf-8'),'Other old12 behavior fixtures/assertions/scenarios changed'
    groups['old12_whole_public_behavior_file_exact_after_only_two_literal_fixture_patches']+=1
    old13_path='tools/validation/diplomacy_package_13/test_satellites.py'
    assert (ROOT/old13_path).read_bytes()==baseline_bytes(old13_path),'Old13 actual behavior proof modified'
    groups['all_original_285_package13_behavior_cases_executor_and_assertions_byte_unchanged']+=1
    for package in ('01','02'):
        path='tools/validation/diplomacy_package_'+package+'/test_source.py'
        assert (ROOT/path).read_bytes()==baseline_bytes(path),path
        groups['source01_02_entire_public_validator_bytes_unchanged']+=1
    installed=Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV')
    effects=(installed/'documentation/effects_documentation.md').read_text(encoding='utf-8-sig')
    triggers=(installed/'documentation/triggers_documentation.md').read_text(encoding='utf-8-sig')
    for name in ('clamp_variable','set_temp_variable','add_to_temp_variable','multiply_temp_variable','divide_temp_variable','add_to_variable','for_each_scope_loop','force_update_dynamic_modifier'):
        assert '\n## '+name+'\n' in effects
        groups['eight_installed_primary_effect_APIs']+=1
    assert 'The order in which the operations are applied is Max( Min( var, max ), min ).' in effects
    assert '`if_zero` specifies the value to assign if the divisor is zero (default is zero).' in effects
    groups['installed_native_ordered_clamp_and_documented_zero_divisor_fallback_not_engine_crash_claim']+=2
    assert 'if = { limit = { <triggers> } <trigger> }' in triggers and '\n## check_variable\n' in triggers
    sample=(installed/'common/scripted_triggers/00_scripted_triggers.txt').read_text(encoding='utf-8-sig')
    assert re.search(r'has_any_tank_tech\s*=\s*{\s*if\s*=\s*{\s*limit\s*=\s*{\s*has_dlc\s*=\s*"No Step Back"',sample) and re.search(r'else\s*=\s*{\s*has_tech\s*=\s*gwtank',sample)
    groups['installed_primary_conditional_trigger_and_shipped_native_if_else_sample']+=1
    boundary_cases=groups['byte_adapter_passthrough_outside_exact_owned_paths']+groups['byte_adapter_rejects_unowned_outer_file_edit_no_files_written']
    print(json.dumps({'all_passed':True,'total_cases':sum(groups.values()),'source_API_cases':sum(groups.values())-boundary_cases,'source_byte_adapter_boundary_cases':boundary_cases,'groups':groups,'baseline':BASELINE,'baseline_gameplay_files':len(before),'existing_gameplay_files_byte_preserved':len(before)-len(EXISTING),'owned_existing_gameplay_files':len(EXISTING),'new_gameplay_files':0,'owned_top_level_blocks':sum(map(len,OWNED.values())),'native_action_count':65,'new_locale_keys':0,'locale_keys_per_language':18,'final_gameplay_sha256':hashes,'runtime_verified':False},indent=2))


if __name__=='__main__':
    main()
