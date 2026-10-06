"""Source/API and exact extended satellite contract boundaries; not HOI4 runtime."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
import sys as package14_sys
package14_sys.path.insert(0, str(ROOT / 'tools/validation'))

# Package14 proves its six files before restoring nine blocks/eight locale lines.
from diplomacy_package_14.test_source import (
    EXISTING as LATER_PACKAGE14_EXISTING, check_owned_existing as check_later_package14_owned,
    package14_original_bytes, package14_historical_existing,
)
check_later_package14_owned()

# Package15 strictly restores eleven current COM network files before older proofs.
from diplomacy_package_15.test_source import (
    check_owned_existing as check_later_package15_owned,
    package15_original_bytes, package15_historical_existing,
)
check_later_package15_owned()
from diplomacy_package_16.test_source import (
    NEW as LATER_PACKAGE16_NEW, package16_original_bytes, package16_historical_existing,
    historical_actions as package16_historical_actions, check_owned_existing as check_later_package16_owned,
)
check_later_package16_owned()
from diplomacy_package_17.test_source import (
    NEW as LATER_PACKAGE17_NEW, package17_original_bytes, package17_historical_existing,
    historical_actions as package17_historical_actions, check_owned_existing as check_later_package17_owned,
)
check_later_package17_owned()
BASELINE = '150cb6f114f7f8896495f57206a1a854af06e056'
EXISTING = {
    'common/scripted_diplomatic_actions/MD_missile_scripted_diplomatic_actions.txt',
    'common/scripted_effects/00_missiles_scripted_effects.txt',
}
NEW = {
    'common/scripted_effects/eon_satellite_extended_effects.txt',
    'common/scripted_triggers/eon_satellite_extended_triggers.txt',
    'common/decisions/eon_satellite_extended_decisions.txt',
    'common/decisions/categories/eon_satellite_extended_categories.txt',
    'common/on_actions/eon_satellite_extended_on_actions.txt',
    'localisation/english/eon_satellite_extended_l_english.yml',
    'localisation/russian/eon_satellite_extended_l_russian.yml',
}
FAMILIES={'gnss_mil':('GNSS','mil','pending_mil_access_country'),
          'com_mil':('COM','mil','pending_mil_com_access_country'),
          'spy_mil':('SPY','mil','pending_mil_spy_access_country'),
          'spy_civ':('SPY','civ','pending_civ_spy_access_country')}
NATIVE_IDS={kind+'_'+role+'_'+upper.lower()+'_access' for upper,role,legacy in FAMILIES.values() for kind in ('request','offer','revoke')}
OLD_HELPERS={'add_'+kind+'_'+upper+'_'+role+'_vars' for upper,role,legacy in FAMILIES.values() for kind in ('access','offer_access')}
OLD_HELPERS|={'add_treaty_COM_mil_receiver_num','update_COM_system_stats'}
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


def package13_original_bytes(path, actual):
    """Restore only twelve enumerated native actions or ten satellite effect blocks."""
    actual = package16_original_bytes(path, actual)
    actual=package14_original_bytes(path,actual)
    if path not in EXISTING:
        return actual
    old = subprocess.check_output(['git','show',BASELINE + ':' + path],cwd=ROOT)
    assert actual.startswith(b'\xef\xbb\xbf') == old.startswith(b'\xef\xbb\xbf'), path
    assert actual.endswith(b'\n') == old.endswith(b'\n'), path
    assert (b'\r\n' in actual) == (b'\r\n' in old), path
    assert b'\r' not in actual.replace(b'\r\n',b''), path
    if '/scripted_diplomatic_actions/' in path:
        names,depth,parent = NATIVE_IDS,1,'scripted_diplomatic_actions'
    else:
        names,depth,parent = OLD_HELPERS,0,None
    original = {block['key']:block for block in boundary_blocks(old)
                if block['depth']==depth and block['parent']==parent and block['key'] in names}
    current = {block['key']:block for block in boundary_blocks(actual)
               if block['depth']==depth and block['parent']==parent and block['key'] in names}
    assert original.keys()==current.keys()==names and len(original)==len(current)==len(names),path
    restored = actual
    for name,block in sorted(current.items(),key=lambda item:item[1]['start'],reverse=True):
        before=original[name]
        restored=restored[:block['start']]+old[before['start']:before['end']]+restored[block['end']:]
    assert restored==old,('Unrelated package13 gameplay bytes changed',path)
    return restored


def check_owned_existing():
    for path in EXISTING:
        package13_original_bytes(path,(ROOT/path).read_bytes())


def native_suffix(family):
    upper,role,legacy=FAMILIES[family]
    return role+'_'+upper.lower()


def native_id(kind,family):
    return kind+'_'+native_suffix(family)+'_access'


def main():
    groups,receipts,sources,helpers,kinds=Counter(),[],{},{},{}
    for path in sorted(NEW):
        assert (ROOT/path).is_file(),('Missing civilian satellite lifecycle source',path)
        data=(ROOT/path).read_bytes()
        assert b'\r' not in data and data.endswith(b'\n'),('New LF/EOF convention',path)
        assert data.startswith(b'\xef\xbb\xbf')==path.endswith('.yml'),('New BOM convention',path)
        assert '\ufffd' not in data.decode('utf-8-sig'),path
        if path.endswith('.txt'):
            boundary_blocks(data);sources[path]=ast(package15_original_bytes(path,data))
        if '/scripted_effects/' in path or '/scripted_triggers/' in path:
            for key,operator,value in sources[path]:
                assert key.startswith('eon_sat_') and key not in helpers,('Unowned/duplicate helper',key)
                helpers[key]=value
                kinds[key]='effects' if '/scripted_effects/' in path else 'triggers'
        receipts.append({'path':path,'sha256':hashlib.sha256(data).hexdigest()})
        groups['new_encoding_braces_and_owned_namespace']+=1
    check_owned_existing()
    assert package13_original_bytes('unowned/path.txt',b'private immutable sentinel')==b'private immutable sentinel'
    groups['original_byte_adapter_passthrough_outside_exact_owned_paths']+=1
    for path in sorted(EXISTING):
        actual=(ROOT/path).read_bytes()
        probe=actual+b'# private memory-only outside-range boundary probe\n'
        try:
            package13_original_bytes(path,probe)
        except AssertionError:
            pass
        else:
            raise AssertionError(('Boundary adapter silently accepts changed unowned bytes',path))
        groups['original_byte_adapter_rejects_unowned_outer_byte_change_no_files_written']+=1
    for path in sorted(EXISTING):
        data=(ROOT/path).read_bytes()
        old=subprocess.check_output(['git','show',BASELINE+':'+path],cwd=ROOT)
        assert package13_original_bytes(path,data)==old
        sources[path]=ast(package14_original_bytes(path,data))
        receipts.append({'path':path,'sha256':hashlib.sha256(data).hexdigest(),'all_unowned_bytes_exact':True})
        groups['only_enumerated_existing_twelve_native_or_ten_effect_ranges_changed']+=1
    trees=('common','history','events','interface','gfx','localisation','music','map','sound',
           'portraits','tutorial','descriptions','scenario_tests','descriptor.mod','era_of_nations.mod','thumbnail.png')
    baseline_paths=subprocess.check_output(['git','ls-tree','-r','--name-only',BASELINE,'--',*trees],cwd=ROOT).decode().splitlines()
    changed=subprocess.check_output(['git','diff','--name-only',BASELINE,'--',*trees],cwd=ROOT).decode().splitlines()
    changed=[path for path in changed if path not in (package14_historical_existing(BASELINE) | package15_historical_existing(BASELINE))-EXISTING | package16_historical_existing(BASELINE) | LATER_PACKAGE16_NEW | package17_historical_existing(BASELINE) | LATER_PACKAGE17_NEW]
    untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard','--',*trees],cwd=ROOT).decode().splitlines()
    untracked = [path for path in untracked if path not in LATER_PACKAGE16_NEW | LATER_PACKAGE17_NEW]
    assert set(changed)|set(untracked)==EXISTING|NEW,('Unowned gameplay edits',changed,untracked)
    assert set(changed).intersection(baseline_paths)==EXISTING
    assert not NEW.intersection(baseline_paths) and set(untracked)<=NEW
    assert len(baseline_paths)==68314
    groups['all_68312_unrelated_existing_gameplay_files_byte_preserved_and_exact_seven_additions']+=1
    action_path='common/scripted_diplomatic_actions/MD_missile_scripted_diplomatic_actions.txt'
    old_actions=one(ast(subprocess.check_output(['git','show',BASELINE+':'+action_path],cwd=ROOT)),'scripted_diplomatic_actions')
    actions=one(sources[action_path],'scripted_diplomatic_actions')
    assert [key for key,op,value in actions]==[key for key,op,value in old_actions]
    for family in FAMILIES:
        selectable=one(one(actions,native_id('revoke',family)),'selectable')
        assert one(one(selectable,'custom_trigger_tooltip'),'tooltip')=='eon_sat_'+family+'_revoke_tt', ('Revocation tooltip must explain current unconditional termination, not new-grant prerequisites',family)
        groups['revocation_dedicated_tooltip_not_peace_tier_or_pending_grant_requirements']+=1
    protected=('visible','cost','requires_acceptance','show_acceptance_on_action_button','icon',
               'send_description','receive_description','accept_title','accept_description',
               'reject_title','reject_description','ai_desire','ai_acceptance')
    old_raw=subprocess.check_output(['git','show',BASELINE+':'+action_path],cwd=ROOT)
    new_raw=package15_original_bytes(action_path,(ROOT/action_path).read_bytes())
    old_bound,new_bound=boundary_blocks(old_raw),boundary_blocks(new_raw)
    for ident in sorted(NATIVE_IDS):
        before,now=one(old_actions,ident),one(actions,ident)
        for field in protected:
            old_rows=[row for row in before if row[0]==field]
            new_rows=[row for row in now if row[0]==field]
            assert new_rows==old_rows,('Original action visibility/identity/cost/AI field changed',ident,field)
            blocks_old=[b for b in old_bound if b['key']==field and b['parent']==ident and b['depth']==2]
            blocks_new=[b for b in new_bound if b['key']==field and b['parent']==ident and b['depth']==2]
            if blocks_old:
                assert len(blocks_old)==len(blocks_new)==1
                x,y=blocks_old[0],blocks_new[0]
                assert old_raw[x['start']:x['end']]==new_raw[y['start']:y['end']],('Original visibility/AI bytes changed',ident,field)
            groups['original_native_visibility_identity_cost_AI_fields_preserved']+=1
    native_ids=[];baseline_ids=[]
    for path in baseline_paths:
        if path.startswith('common/scripted_diplomatic_actions/') and path.endswith('.txt'):
            before=subprocess.check_output(['git','show',BASELINE+':'+path],cwd=ROOT)
            actual=(ROOT/path).read_bytes()
            assert package13_original_bytes(path,actual)==before,('Unowned native action bytes changed',path)
            baseline_ids.extend(b['key'] for b in boundary_blocks(before) if b['depth']==1 and b['parent']=='scripted_diplomatic_actions')
    for path in (ROOT/'common/scripted_diplomatic_actions').glob('*.txt'):
        native_ids.extend(b['key'] for b in boundary_blocks(path.read_bytes()) if b['depth']==1 and b['parent']=='scripted_diplomatic_actions')
    native_ids = package16_historical_actions(native_ids)
    assert len(native_ids)==len(set(native_ids))==len(baseline_ids)==len(set(baseline_ids))==65
    assert set(native_ids)==set(baseline_ids)
    groups['all_65_native_action_IDs_preserved_all_unowned_native_bytes_exact']+=1
    category=one(sources['common/decisions/categories/eon_satellite_extended_categories.txt'],'eon_satellite_extended_agreements')
    assert {key for key,op,value in category}=={'icon','allowed','visible'}
    assert one(category,'icon')=='generic_foreign_policy' and one(category,'allowed')==ast('always = yes')
    assert one(category,'visible')==ast('is_ai = no OR = { '+' '.join('has_country_flag = eon_sat_'+family+'_pending' for family in FAMILIES)+' }')
    groups['four_extended_family_pending_only_human_category_no_target_state_scope']+=1
    decisions=one(sources['common/decisions/eon_satellite_extended_decisions.txt'],'eon_satellite_extended_agreements')
    assert {key for key,op,value in decisions}=={'eon_withdraw_'+native_suffix(family)+'_proposal' for family in FAMILIES}
    for family in FAMILIES:
        body=one(decisions,'eon_withdraw_'+native_suffix(family)+'_proposal')
        assert {key for key,op,value in body}=={'icon','allowed','visible','available','cost','complete_effect','ai_will_do'}
        assert one(body,'icon')=='generic_decision' and one(body,'allowed')==ast('always = yes')
        assert one(body,'visible')==ast('is_ai = no eon_sat_'+family+'_withdraw_ready = yes')
        assert one(body,'available')==ast('eon_sat_'+family+'_withdraw_ready = yes')
        assert one(body,'complete_effect')==ast('if = { limit = { eon_sat_'+family+'_withdraw_ready = yes } custom_effect_tooltip = eon_sat_'+family+'_withdraw_tt eon_sat_'+family+'_withdraw = yes }')
        assert one(body,'cost')=='0' and one(body,'ai_will_do')==ast('factor = 0')
        groups['fresh_guarded_actor_only_free_human_proposal_withdrawal_decision']+=1
    hooks=one(sources['common/on_actions/eon_satellite_extended_on_actions.txt'],'on_actions')
    assert {key for key,op,value in hooks}=={'on_daily','on_annex','on_subject_annexed'}
    assert one(hooks,'on_daily')==ast('effect = { set_temp_variable = { eon_sat_removed_country = 0 } eon_sat_extended_daily_cleanup = yes }')
    groups['daily_removal_sentinel_reset_and_current_country_cleanup']+=1
    for event,scope in (('on_annex','FROM'),('on_subject_annexed','ROOT')):
        assert one(hooks,event)==ast('effect = { set_temp_variable = { eon_sat_removed_country = '+scope+' } '+scope+' = { eon_sat_extended_cleanup_annexed_owner = yes } every_country = { limit = { exists = yes NOT = { tag = '+scope+' } } eon_sat_extended_daily_cleanup = yes } }')
        groups['annex_native_victim_scope_first_then_live_survivors_excluding_removed_country']+=1
    locale,locale_counts={},{}
    expected_locale={'eon_satellite_extended_agreements','eon_satellite_extended_agreements_desc'}
    expected_locale|={'eon_withdraw_'+native_suffix(family)+'_proposal'+suffix for family in FAMILIES for suffix in ('','_desc')}
    expected_locale|={'eon_sat_'+family+'_'+suffix+'_tt' for family in FAMILIES for suffix in ('available','proposal','closed','withdraw','granted','revoke')}
    assert len(expected_locale)==34
    for language in ('english','russian'):
        data=(ROOT/f'localisation/{language}/eon_satellite_extended_l_{language}.yml').read_text(encoding='utf-8-sig')
        assert data.splitlines()[0]=='l_'+language+':'
        pairs=re.findall(r'^ ([\w.]+):0 "(.*)"$',data,re.M)
        assert len(pairs)==len(dict(pairs)) and len(pairs)==34
        locale[language]=dict(pairs)
        assert locale[language].keys()==expected_locale
        locale_counts[language]=Counter()
        for path in (ROOT/'localisation'/language).glob('*.yml'):
            locale_counts[language].update(re.findall(r'^ ([\w.]+):',path.read_text(encoding='utf-8-sig'),re.M))
    for key in sorted(expected_locale):
        assert all(locale_counts[language][key]==1 for language in locale),('Duplicate/missing locale ID',key)
        assert re.findall(r'\[.*?\]|\$[\w.]+\$',locale['english'][key])==re.findall(r'\[.*?\]|\$[\w.]+\$',locale['russian'][key]),('Bilingual placeholder mismatch',key)
        for reference in re.findall(r'\$([\w.]+)\$',locale['english'][key]):
            assert all(locale_counts[language][reference]>0 for language in locale),('Unresolved localisation macro',reference)
        groups['34_unique_bilingual_locale_IDs_parity_placeholders_and_resolved_macros']+=1
    expected_helpers={'eon_sat_extended_daily_cleanup','eon_sat_extended_cleanup_annexed_owner'}
    fx_names={'begin_request','accept_request','reject_request','begin_offer','accept_offer','reject_offer',
              'clear','force_close','withdraw','cleanup','canonical_access','canonical_treaties',
              'remove_access_peer','remove_treaty_peer','revoke'}
    trigger_names={'valid_level','pair_live','record_matches','new_ready','withdraw_ready',
                   'request_terms','request_ready','request_authorized','offer_terms','offer_ready',
                   'offer_authorized','revoke_ready'}
    expected_helpers|={'eon_sat_'+family+'_'+name for family in FAMILIES for name in fx_names|trigger_names}
    expected_helpers|={'eon_sat_refresh_'+family for family in FAMILIES}
    assert set(helpers)==expected_helpers and len(helpers)==114
    groups['exact_114_owned_helper_IDs_no_unreviewed_helpers']+=1
    definitions=Counter()
    for folder in ('scripted_effects','scripted_triggers'):
        for path in (ROOT/'common'/folder).glob('*.txt'):
            definitions.update(key for key,op,value in ast(path.read_bytes()) if key in helpers)
    for key in sorted(expected_helpers):
        assert definitions[key]==1,('Duplicate helper ID',key)
        groups['global_owned_helper_ID_uniqueness']+=1
    def contract(key,text,group):
        assert helpers[key]==ast(text),('Owned source contract changed',key)
        groups[group]+=1
    bonus_fields={'gnss_mil':('army_speed_factor','air_cas_efficiency','air_nav_efficiency','air_strategic_bomber_bombing_factor','positioning','naval_hit_chance'),
                  'com_mil':('max_command_power','army_org_factor','planning_speed','air_escort_efficiency','air_intercept_efficiency','naval_coordination'),
                  'spy_mil':('max_planning_factor','recon_factor','air_weather_penalty','spotting_chance','convoy_raiding_efficiency_factor','convoy_escort_efficiency'),
                  'spy_civ':('research_speed_factor','civilian_intel_factor','army_intel_factor','navy_intel_factor','airforce_intel_factor','root_out_resistance_effectiveness_factor')}
    for family in FAMILIES:
        upper,role,legacy=FAMILIES[family];prefix='eon_sat_'+family+'_';idx='var_'+upper+'_'+role+'_system_idx'
        usable='OR = { check_variable = { '+idx+' > 0 } AND = { check_variable = { '+idx+' = 0 } check_variable = { var_'+upper+'_'+role+'_sat_system_num > 0 } } }'
        access=upper+'_'+role+'_access_array';treaty=upper+'_'+role+'_treaty_array';tiers=upper+'_'+role+'_access_system_idx_array'
        cooldown='recently_accepted_'+native_suffix(family)+'_@PREV'
        group='literal_family_partner_direction_level_guards_and_independent_original_consent'
        contract(prefix+'valid_level','OR = { '+' '.join('check_variable = { '+idx+' = '+str(level)+' }' for level in range(8))+' }',group)
        contract(prefix+'pair_live','exists = yes PREV = { exists = yes } NOT = { tag = PREV } NOT = { has_war_with = PREV }',group)
        contract(prefix+'record_matches','has_country_flag = '+prefix+'pending check_variable = { '+prefix+'partner = PREV.id }',group)
        contract(prefix+'new_ready',prefix+'pair_live = yes NOT = { has_country_flag = '+prefix+'pending } NOT = { has_country_flag = '+prefix+'quarantine@PREV } check_variable = { '+legacy+' = 0 }',group)
        contract(prefix+'withdraw_ready','exists = yes is_ai = no has_country_flag = '+prefix+'pending NOT = { has_country_flag = '+prefix+'cancelled }',group)
        contract(prefix+'request_terms',prefix+'pair_live = yes PREV = { '+prefix+'valid_level = yes '+usable+' } '+prefix+'valid_level = yes OR = { check_variable = { PREV.'+idx+' = '+idx+' } check_variable = { PREV.'+idx+' > '+idx+' } } NOT = { is_in_array = { array = '+access+' value = PREV.id } } NOT = { is_in_array = { array = PREV.'+treaty+' value = THIS.id } }',group)
        contract(prefix+'offer_terms',prefix+'pair_live = yes '+prefix+'valid_level = yes '+usable+' PREV = { '+prefix+'valid_level = yes } OR = { check_variable = { '+idx+' = PREV.'+idx+' } check_variable = { '+idx+' > PREV.'+idx+' } } NOT = { is_in_array = { array = PREV.'+access+' value = THIS.id } } NOT = { is_in_array = { array = '+treaty+' value = PREV.id } }',group)
        for kind,number in (('request',1),('offer',2)):
            contract(prefix+kind+'_ready',prefix+'new_ready = yes '+prefix+kind+'_terms = yes',group)
            level=('PREV.' if kind=='request' else '')+idx
            contract(prefix+kind+'_authorized',prefix+'record_matches = yes check_variable = { '+prefix+'kind = '+str(number)+' } has_country_flag = '+prefix+'window NOT = { has_country_flag = '+prefix+'cancelled } '+prefix+kind+'_terms = yes check_variable = { '+prefix+'level = '+level+' }',group)
            contract(prefix+'begin_'+kind,'if = { limit = { '+prefix+kind+'_ready = yes } '+prefix+'clear = yes set_variable = { '+prefix+'partner = PREV.id } set_variable = { '+prefix+'kind = '+str(number)+' } set_variable = { '+prefix+'level = '+level+' } set_variable = { '+legacy+' = PREV.id } set_country_flag = '+prefix+'pending set_country_flag = { flag = '+prefix+'window days = 30 value = 1 } custom_effect_tooltip = '+prefix+'proposal_tt }','fresh_send_owned_legacy_pointer_once_actor_only_30_day_reservation')
            grant=('PREV = { add_to_array = { array = '+treaty+' value = PREV.id } } add_to_array = { array = '+access+' value = PREV.id }' if kind=='request' else 'add_to_array = { array = '+treaty+' value = PREV.id } PREV = { add_to_array = { array = '+access+' value = PREV.id } }')
            accepted_flag='' if family=='gnss_mil' and kind=='request' else 'set_country_flag = { flag = '+cooldown+' days = 180 value = 1 } '
            contract(prefix+'accept_'+kind,'if = { limit = { '+prefix+'record_matches = yes check_variable = { '+prefix+'kind = '+str(number)+' } } if = { limit = { '+prefix+kind+'_authorized = yes } '+prefix+'clear = yes '+grant+' '+accepted_flag+'eon_sat_refresh_'+family+' = yes PREV = { eon_sat_refresh_'+family+' = yes } custom_effect_tooltip = '+prefix+'granted_tt } else = { '+prefix+'clear = yes custom_effect_tooltip = '+prefix+'closed_tt } }','fresh_authorized_original_callback_pair_grant_consumed_release_and_existing_cooldown')
            contract(prefix+'reject_'+kind,'if = { limit = { '+prefix+'record_matches = yes check_variable = { '+prefix+'kind = '+str(number)+' } } '+prefix+'clear = yes }','original_literal_direction_reply_consumption_no_peer_or_unknown_legacy_pointer_clear')
            action=one(actions,native_id(kind,family))
            assert {row[0] for row in action}=={row[0] for row in one(old_actions,native_id(kind,family))}|{'on_sent_effect'}|({'reject_effect'} if family=='com_mil' and kind=='request' else set()), (native_id(kind,family),{row[0] for row in action},{row[0] for row in one(old_actions,native_id(kind,family))}|{'on_sent_effect'}|({'reject_effect'} if family=='com_mil' and kind=='request' else set()))
            assert one(action,'selectable')==ast('custom_trigger_tooltip = { tooltip = '+prefix+'available_tt ROOT = { '+prefix+kind+'_ready = yes } }')
            for field,helper in (('on_sent_effect','begin'),('complete_effect','accept'),('reject_effect','reject')):
                assert one(action,field)==ast('ROOT = { '+prefix+helper+'_'+kind+' = yes }')
            groups['twelve_owned_native_selectable_send_reply_only_correct_ROOT_actor_PREV_peer_wrappers']+=1
        contract(prefix+'revoke_ready','exists = yes PREV = { exists = yes } NOT = { tag = PREV } OR = { is_in_array = { array = '+treaty+' value = PREV.id } is_in_array = { array = PREV.'+access+' value = THIS.id } }','live_pair_existing_identity_unconditional_termination_not_new_grant_eligibility')
        revoke=one(actions,native_id('revoke',family))
        assert {row[0] for row in revoke}=={row[0] for row in one(old_actions,native_id('revoke',family))}
        assert one(revoke,'selectable')==ast('custom_trigger_tooltip = { tooltip = '+prefix+'revoke_tt ROOT = { '+prefix+'revoke_ready = yes } }')
        assert one(revoke,'complete_effect')==ast('ROOT = { '+prefix+'revoke = yes }')
        assert one(revoke,'reject_effect')==ast('ROOT = { }')
        groups['twelve_owned_native_selectable_send_reply_only_correct_ROOT_actor_PREV_peer_wrappers']+=1
        contract(prefix+'clear','if = { limit = { has_country_flag = '+prefix+'pending check_variable = { '+legacy+' = '+prefix+'partner } } clear_variable = '+legacy+' } clr_country_flag = '+prefix+'pending clr_country_flag = '+prefix+'window clr_country_flag = '+prefix+'cancelled clear_variable = '+prefix+'partner clear_variable = '+prefix+'kind clear_variable = '+prefix+'level','clear_only_owned_matching_compatibility_pointer_no_unknown_legacy_migration')
        contract(prefix+'force_close','if = { limit = { has_country_flag = '+prefix+'pending } if = { limit = { check_variable = { '+prefix+'partner > 0 } } set_temp_variable = { '+prefix+'closing_partner = '+prefix+'partner } var:'+prefix+'closing_partner = { PREV = { set_country_flag = '+prefix+'quarantine@PREV } } } '+prefix+'clear = yes }','forced_unconsumed_reply_actor_pair_quarantine_before_identity_erase')
        contract(prefix+'withdraw','if = { limit = { '+prefix+'withdraw_ready = yes } set_country_flag = '+prefix+'cancelled custom_effect_tooltip = '+prefix+'withdraw_tt }','withdrawal_keeps_original_reservation_no_reply_or_recipient_outgoing_mutation')
        contract(prefix+'cleanup','if = { limit = { has_country_flag = '+prefix+'pending } if = { limit = { OR = { NOT = { has_country_flag = '+prefix+'window } NOT = { check_variable = { '+prefix+'partner > 0 } } AND = { check_variable = { eon_sat_removed_country > 0 } check_variable = { '+prefix+'partner = eon_sat_removed_country } } } } '+prefix+'force_close = yes } else = { set_temp_variable = { '+prefix+'cleanup_partner = '+prefix+'partner } var:'+prefix+'cleanup_partner = { if = { limit = { NOT = { exists = yes } } PREV = { '+prefix+'force_close = yes } } else = { PREV = { if = { limit = { NOT = { OR = { '+prefix+'request_authorized = yes '+prefix+'offer_authorized = yes } } } set_country_flag = '+prefix+'cancelled } } } } } }','daily_forced_expiry_removed_peer_quarantine_and_transient_service_invalidation_latch')
        contract(prefix+'canonical_access','clear_array = '+prefix+'access_work clear_array = '+tiers+' for_each_scope_loop = { array = '+access+' if = { limit = { exists = yes NOT = { tag = PREV } is_in_array = { array = '+treaty+' value = PREV.id } NOT = { is_in_array = { array = PREV.'+prefix+'access_work value = THIS.id } } } add_to_array = { array = PREV.'+prefix+'access_work value = THIS.id } if = { limit = { '+prefix+'valid_level = yes } add_to_array = { array = PREV.'+tiers+' value = THIS.'+idx+' } } else = { add_to_array = { array = PREV.'+tiers+' value = 0 } } } } clear_array = '+access+' for_each_loop = { array = '+prefix+'access_work value = '+prefix+'access_value index = '+prefix+'access_index add_to_array = { array = '+access+' value = '+prefix+'access_value } } clear_array = '+prefix+'access_work','canonical_live_reciprocal_provider_ID_dedup_and_ordered_current_tiers_scratch_no_source_iteration_mutation')
        contract(prefix+'canonical_treaties','clear_array = '+prefix+'treaty_work for_each_scope_loop = { array = '+treaty+' if = { limit = { exists = yes NOT = { tag = PREV } is_in_array = { array = '+access+' value = PREV.id } NOT = { is_in_array = { array = PREV.'+prefix+'treaty_work value = THIS.id } } } add_to_array = { array = PREV.'+prefix+'treaty_work value = THIS.id } } } clear_array = '+treaty+' for_each_loop = { array = '+prefix+'treaty_work value = '+prefix+'treaty_value index = '+prefix+'treaty_index add_to_array = { array = '+treaty+' value = '+prefix+'treaty_value } } clear_array = '+prefix+'treaty_work','canonical_live_reciprocal_recipient_ID_dedup_preserves_dormant_consent')
        for direction,array,peer in (('access',access,'provider'),('treaty',treaty,'recipient')):
            contract(prefix+'remove_'+direction+'_peer','clear_array = '+prefix+'remove_work for_each_scope_loop = { array = '+array+' if = { limit = { NOT = { check_variable = { THIS.id = eon_sat_revoke_'+peer+' } } } add_to_array = { array = PREV.'+prefix+'remove_work value = THIS.id } } } clear_array = '+array+' for_each_loop = { array = '+prefix+'remove_work value = '+prefix+'remove_value index = '+prefix+'remove_index add_to_array = { array = '+array+' value = '+prefix+'remove_value } } clear_array = '+prefix+'remove_work','identity_filter_removes_all_same_provider_grants_no_ambiguous_equal_tier_value_removal')
        contract(prefix+'revoke','if = { limit = { '+prefix+'revoke_ready = yes } set_temp_variable = { eon_sat_revoke_provider = THIS.id } set_temp_variable = { eon_sat_revoke_recipient = PREV.id } '+prefix+'remove_treaty_peer = yes PREV = { '+prefix+'remove_access_peer = yes } set_country_flag = { flag = recently_revoke_'+native_suffix(family)+'_access_@PREV days = 180 value = 1 } eon_sat_refresh_'+family+' = yes PREV = { eon_sat_refresh_'+family+' = yes } }','current_provider_recipient_identity_termination_original_cooldown_and_both_service_refresh')
        fields=bonus_fields[family];stem='var_'+upper+'_'+role+'_'
        resets=' '.join('set_variable = { '+stem+field+' = '+stem+field+'_base }' for field in fields)
        additions=' '.join('add_to_variable = { PREV.'+stem+field+' = THIS.'+stem+field+'_base }' for field in fields)
        clamps=' '.join('clamp_variable = { var = '+stem+field+(' min = global.' if family=='spy_mil' and field=='air_weather_penalty' else ' max = global.')+upper+'_'+role+'_'+field+'_max_array^'+prefix+'highest }' for field in fields)
        contract('eon_sat_refresh_'+family,prefix+'canonical_access = yes '+prefix+'canonical_treaties = yes '+resets+' set_temp_variable = { '+prefix+'highest = -1 } for_each_scope_loop = { array = '+access+' if = { limit = { exists = yes '+prefix+'valid_level = yes '+usable+' NOT = { has_war_with = PREV } PREV = { '+prefix+'valid_level = yes } OR = { check_variable = { THIS.'+idx+' = PREV.'+idx+' } check_variable = { THIS.'+idx+' > PREV.'+idx+' } } } '+additions+' if = { limit = { check_variable = { THIS.'+idx+' > '+prefix+'highest } } set_temp_variable = { '+prefix+'highest = THIS.'+idx+' } } } } if = { limit = { check_variable = { '+prefix+'highest > -1 } } '+clamps+' } if = { limit = { exists = yes } force_update_dynamic_modifier = yes }','current_THIS_recipient_provider_own_valid_level_existing_bonus_bases_total_then_clamp_original_global_tables')
    contract('eon_sat_extended_daily_cleanup',' '.join('eon_sat_'+family+'_cleanup = yes eon_sat_refresh_'+family+' = yes' for family in FAMILIES),'daily_independent_four_family_pending_and_current_service_refresh')
    contract('eon_sat_extended_cleanup_annexed_owner',' '.join('eon_sat_'+family+'_force_close = yes '+' '.join('clear_array = '+upper+'_'+role+'_'+name+'_array' for name in ('access','access_system_idx','treaty')) for family,(upper,role,legacy) in FAMILIES.items()),'annex_owner_pending_quarantine_before_own_extended_array_erase')
    old_fx=sources['common/scripted_effects/00_missiles_scripted_effects.txt']
    for family,(upper,role,legacy) in FAMILIES.items():
        assert one(old_fx,'add_access_'+upper+'_'+role+'_vars')==ast('eon_sat_refresh_'+family+' = yes')
        assert one(old_fx,'add_offer_access_'+upper+'_'+role+'_vars')==ast('PREV = { eon_sat_refresh_'+family+' = yes }')
        groups['eight_preserved_original_aggregate_helper_IDs_current_recipient_REFRESH_scope']+=1
    assert one(old_fx,'add_treaty_COM_mil_receiver_num')==ast('eon_sat_com_mil_canonical_treaties = yes set_variable = { var_treaty_COM_mil_receiver_num = 0 } for_each_scope_loop = { array = COM_mil_treaty_array add_to_variable = { PREV.var_treaty_COM_mil_receiver_num = THIS.num_battalions } add_to_variable = { PREV.var_treaty_COM_mil_receiver_num = THIS.num_ships } add_to_variable = { PREV.var_treaty_COM_mil_receiver_num = THIS.num_deployed_planes } } add_to_variable = { var_COM_mil_receiver_num = var_treaty_COM_mil_receiver_num }')
    groups['all_unique_consensual_COM_military_recipients_original_battalion_ship_plane_receiver_sum']+=1
    fx_path='common/scripted_effects/00_missiles_scripted_effects.txt'
    original_fx=subprocess.check_output(['git','show',BASELINE+':'+fx_path],cwd=ROOT)
    current_fx=(ROOT/fx_path).read_bytes()
    before_block=next(block for block in boundary_blocks(original_fx) if block['key']=='update_COM_system_stats' and block['depth']==0)
    after_block=next(block for block in boundary_blocks(current_fx) if block['key']=='update_COM_system_stats' and block['depth']==0)
    before_shared=original_fx[before_block['start']:before_block['end']].decode()
    after_shared=current_fx[after_block['start']:after_block['end']].decode()
    expected_shared=before_shared
    for role in ('mil','civ'):
        before_coverage=('\tif = { limit = { check_variable = { var_COM_'+role+'_sat_system_num > var_COM_'+role+'_sat_system_max } }\n'
                         '\t\tset_variable = { var_COM_'+role+'_coverage = 1.0 }\n\t}\n\telse = {\n'
                         '\t\tset_variable = { var_COM_'+role+'_coverage = var_COM_'+role+'_sat_system_num }\n'
                         '\t\tdivide_variable = { var_COM_'+role+'_coverage = var_COM_'+role+'_sat_system_max }\n\t}')
        after_coverage=('\tif = { limit = { check_variable = { var_COM_'+role+'_sat_system_max > 0 } check_variable = { var_COM_'+role+'_sat_system_num > var_COM_'+role+'_sat_system_max } }\n'
                        '\t\tset_variable = { var_COM_'+role+'_coverage = 1.0 }\n\t}\n\telse = {\n'
                        '\t\tif = { limit = { check_variable = { var_COM_'+role+'_sat_system_max > 0 } }\n'
                        '\t\t\tset_variable = { var_COM_'+role+'_coverage = var_COM_'+role+'_sat_system_num }\n'
                        '\t\t\tdivide_variable = { var_COM_'+role+'_coverage = var_COM_'+role+'_sat_system_max }\n\t\t}\n'
                        '\t\telse = { set_variable = { var_COM_'+role+'_coverage = 0 } }\n\t}')
        assert expected_shared.count(before_coverage)==1
        expected_shared=expected_shared.replace(before_coverage,after_coverage,1)
        groups['both_shared_COM_coverage_positive_max_guard_and_zero_fallback_only']+=1
    marker='\t\tset_variable = { var_sat_network_traffic_mil = 0 }\n'
    assert expected_shared.count(marker)==1
    expected_shared=expected_shared.replace(marker,marker+'\t\tset_variable = { var_COM_mil_sat_system_bonus = 0 }\n',1)
    groups['zero_military_capacity_removes_stale_bonus_without_resource_payment']+=1
    marker='\t\tif = { limit = { check_variable = { var_sat_network_traffic_civ > 1 } }\n\t\t\tset_temp_variable = { temp3 = var_sat_network_traffic_mil }'
    assert expected_shared.count(marker)==1
    expected_shared=expected_shared.replace(marker,marker.replace('traffic_civ >','traffic_mil >'),1)
    assert after_shared==expected_shared,'Shared COM changed outside exact two coverage/zero military bonus/military traffic gate edits'
    groups['shared_COM_exact_four_small_fixes_original_capacity_loop_and_all_other_bytes_preserved']+=1
    initial=subprocess.check_output(['git','show','347cfd22e65a812ae609264ff1a043cbdc87145d:'+fx_path],cwd=ROOT)
    initial_block=next(block for block in boundary_blocks(initial) if block['key']=='update_COM_system_stats' and block['depth']==0)
    assert initial[initial_block['start']:initial_block['end']]==before_shared.encode()
    assert 'add_to_variable = { var_COM_mil_receiver_cap = temp1 }' in before_shared
    assert 'add_to_variable = { var_COM_civ_receiver_cap = temp2 }' in before_shared
    groups['corrected_false_capacity_overwrite_claim_both_original_accumulators_already_sum_identical_since347']+=1
    civilian_files={'common/scripted_effects/eon_satellite_effects.txt','common/scripted_triggers/eon_satellite_triggers.txt',
                    'common/decisions/eon_satellite_decisions.txt','common/decisions/categories/eon_satellite_categories.txt',
                    'common/on_actions/eon_satellite_on_actions.txt','localisation/english/eon_satellite_l_english.yml',
                    'localisation/russian/eon_satellite_l_russian.yml'}
    for path in sorted(civilian_files):
        assert package14_original_bytes(path,(ROOT/path).read_bytes())==subprocess.check_output(['git','show',BASELINE+':'+path],cwd=ROOT),('Previous civilian package12 gameplay changed',path)
        groups['all_previous_package12_civilian_gameplay_files_byte_exact']+=1
    for path in sorted(NEW):
        if not path.endswith('.txt'): continue
        nodes=sources[path]
        for key,op,value in rows(nodes):
            if key=='NOT':
                assert isinstance(value,list) and len(value)==1,('Native NOT is NOR: one explicit child/group required',path,value)
            if key.startswith('eon_sat_') and op=='=' and value=='yes':
                assert key in helpers,('Unresolved helper reference',path,key)
            if key in ('tooltip','custom_effect_tooltip'):
                assert value in expected_locale,('Unresolved new tooltip reference',path,value)
        groups['new_native_single_child_NOT_helper_and_tooltip_references']+=1
    allowed_variable_writes={legacy for upper,role,legacy in FAMILIES.values()}
    allowed_variable_writes|={'var_'+FAMILIES[family][0]+'_'+FAMILIES[family][1]+'_'+field for family,fields in bonus_fields.items() for field in fields}
    allowed_arrays={upper+'_'+role+'_'+suffix+'_array' for upper,role,legacy in FAMILIES.values() for suffix in ('access','access_system_idx','treaty')}
    mutators={'if','else','limit','PREV','for_each_scope_loop','for_each_loop','array','value','index',
              'set_variable','clear_variable','set_temp_variable','clear_array','add_to_array',
              'add_to_variable','clamp_variable','set_country_flag','clr_country_flag',
              'force_update_dynamic_modifier','custom_effect_tooltip'}
    trigger_structure={'check_variable','has_country_flag','exists','is_ai','tag','has_war_with','is_in_array',
                       'NOT','AND','OR','PREV','array','value','set_temp_variable'}
    def effect_rows(nodes):
        for key,op,value in nodes:
            if key=='limit':continue
            yield key,op,value
            if isinstance(value,list) and key in ('if','else','PREV','for_each_scope_loop','for_each_loop') or isinstance(value,list) and key.startswith('var:'):
                yield from effect_rows(value)
    for helper in sorted(helpers):
        body=helpers[helper]
        assert not any(key=='ROOT' or isinstance(value,str) and 'ROOT.' in value for key,op,value in rows(body)),('Helper must use current THIS/PREV rather than fixed native ROOT',helper)
        if kinds[helper]=='effects':
            for key,op,value in effect_rows(body):
                assert key in mutators or key.startswith('var:eon_sat_') or key in helpers and kinds[key]=='effects',('Unreviewed side effect or trigger as effect',helper,key)
                if key in ('set_variable','add_to_variable'):
                    assert all(name.removeprefix('PREV.').startswith('eon_sat_') or name.removeprefix('PREV.') in allowed_variable_writes for name,operator,amount in value),('Unowned persistent variable writes',helper,value)
                if key=='clear_variable':assert value.startswith('eon_sat_') or value in allowed_variable_writes,('Unowned variable clear',helper,value)
                if key=='set_temp_variable':assert all(name.startswith('eon_sat_') for name,operator,amount in value),('Unowned temp state',helper,value)
                if key=='clear_array':assert value.startswith('eon_sat_') or value in allowed_arrays,('Unowned array clear',helper,value)
                if key=='add_to_array':assert one(value,'array').removeprefix('PREV.').startswith('eon_sat_') or one(value,'array').removeprefix('PREV.') in allowed_arrays,('Unowned array write',helper,value)
                if key in ('set_country_flag','clr_country_flag'):
                    flag=one(value,'flag') if isinstance(value,list) else value
                    assert flag.startswith('eon_sat_') or flag in {'recently_accepted_'+native_suffix(name)+'_@PREV' for name in FAMILIES} or flag in {'recently_revoke_'+native_suffix(name)+'_access_@PREV' for name in FAMILIES},('Unowned flag write',helper,flag)
                    if '@' in flag:assert flag.endswith('@PREV'),('Unproved country-valued flag suffix',helper,flag)
                if key=='force_update_dynamic_modifier':assert value=='yes'
        else:
            for key,op,value in rows(body):
                if isinstance(value,list):
                    assert key in trigger_structure or key in helpers and kinds[key]=='triggers',('Unowned trigger/side effect in trigger',helper,key)
        groups['owned_extended_helper_current_scope_no_cash_CP_PP_war_other_family_or_operation_mutation']+=1
    protected_files=('common/scripted_effects/00_missiles_models.txt',
                     'common/scripted_guis/missiles_scripted_gui.txt',
                     'common/scripted_triggers/MD_missile_scripted_triggers.txt')
    for path in protected_files:
        assert package14_original_bytes(path,(ROOT/path).read_bytes())==subprocess.check_output(['git','show',BASELINE+':'+path],cwd=ROOT),('Original capability tables/GUI/national AI policy modified',path)
        groups['original_global_capability_tables_GUI_array_IDs_and_AI_policy_byte_unchanged']+=1
    models=ast((ROOT/'common/scripted_effects/00_missiles_models.txt').read_bytes())
    primary_ui=(ROOT/'localisation/english/MD_missiles_l_english.yml').read_text(encoding='utf-8-sig')
    first_tier_labels={'gnss_mil':'GNSS 5 m','com_mil':'56 kbits/s','spy_mil':'5 m GSD','spy_civ':'5 m GSD'}
    for family,(upper,role,legacy) in FAMILIES.items():
        system_array=upper+'_'+role+'_systems_array'
        assert one(old_fx,'set_'+upper+'_'+role+'_systems')==ast('clear_array = '+system_array+' '+' '.join('add_to_array = { '+system_array+' = '+str(index)+' }' for index in range(8)))
        assert re.search(r'^ '+upper+'_'+role+'_idx_0_loc: "'+re.escape(first_tier_labels[family])+r'"$',primary_ui,re.M),('Native first tier has a usable system label',family)
        system_num='var_'+upper+'_'+role+'_sat_system_num'
        stats=one(old_fx,'update_'+upper+'_system_stats')
        if upper=='COM':
            assert ('set_variable','=',ast(system_num+' = 0')) in list(rows(stats))
            assert ('add_to_variable','=',ast(system_num+' = COM_satellite_array^i')) in list(rows(stats))
        else:
            assert ('set_variable','=',ast(system_num+' = '+upper+'_satellite_array^var_'+upper+'_'+role+'_system_idx')) in list(rows(stats))
        groups['four_native_level_zero_system_arrays_UI_labels_and_provider_own_satellite_count_source']+=1
    for family,fields in bonus_fields.items():
        for field in fields:
            array='global.'+FAMILIES[family][0]+'_'+FAMILIES[family][1]+'_'+field+'_max_array'
            assignments=[value for key,op,value in rows(models) if key=='add_to_array' and isinstance(value,list) and any(name==array for name,operator,amount in value)]
            assert len(assignments)==8,('Guarded 0..7 level must match original global table length',array,len(assignments))
            first_bound=float(one(assignments[0],array))
            assert first_bound<0 if family=='spy_mil' and field=='air_weather_penalty' else first_bound>0,('Native first-tier cap must be usable with its original sign',array,first_bound)
            groups['literal_eight_levels_and_nonzero_original_level_zero_cap_bounds']+=1
    installed=Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV')
    assert installed.is_dir(),'Installed primary HOI4 documentation unavailable'
    effects=(installed/'documentation/effects_documentation.md').read_text(encoding='utf-8-sig')
    triggers=(installed/'documentation/triggers_documentation.md').read_text(encoding='utf-8-sig')
    for key in ('set_variable','clear_variable','set_temp_variable','multiply_temp_variable','add_to_variable',
                'add_to_array','clear_array','for_each_loop','for_each_scope_loop','clamp_variable',
                'set_country_flag','clr_country_flag','force_update_dynamic_modifier'):
        assert '\n## '+key+'\n' in effects,('Unsupported native effect',key)
        groups['installed_primary_effect_API_documentation']+=1
    for key in ('check_variable','has_country_flag','exists','is_ai','tag','has_war_with','is_in_array'):
        assert '\n## '+key+'\n' in triggers,('Unsupported native trigger',key)
        groups['installed_primary_trigger_API_documentation']+=1
    assert "value = value_name #optional (default 'v')" in effects and "index = index_name #optional (default 'i')" in effects
    assert 'default is end. otherwise elements are shifted' in effects
    assert 'changes scope to current element in each iteration' in effects
    assert 'Removes an element from an array using value or index' in effects
    assert not any(key=='remove_from_array' for body in helpers.values() for key,op,value in rows(body))
    groups['documented_array_append_custom_loop_variables_scope_change_identity_copy_filter_without_duplicate_removal_assumption']+=1
    docs=(installed/'common/scripted_diplomatic_actions/scripted_diplomatic_actions.txt').read_text(encoding='utf-8-sig')
    for phrase in ('root is the initiator of action and this is the target country',
                   'root is the sender and this is receiver','on_sent_effect','complete_effect','reject_effect','requires_acceptance'):
        assert phrase in docs
        groups['installed_primary_native_diplomatic_actor_target_send_accept_reject_consent_API']+=1
    sample=(installed/'common/scripted_effects/00_scripted_effects.txt').read_text(encoding='utf-8-sig')
    assert re.search(r'set_temp_variable\s*=\s*{\s*new_country\s*=\s*this\s*}\s*PREV\s*=\s*{\s*every_controlled_state\s*=\s*{\s*limit\s*=\s*{\s*occupied_country_tag\s*=\s*country_to_initiate\s*}\s*var:new_country\s*=\s*{',sample)
    operation=(installed/'common/scripted_effects/operation_strat_effects.txt').read_text(encoding='utf-8-sig')
    assert 'set_temp_variable = { captor = operative_captor }' in operation and 'set_variable = { rescue_operative_from = captor }' in operation
    groups['installed_primary_country_valued_temp_visibility_across_country_state_operative_frames']+=2
    chi=(installed/'common/scripted_effects/CHI_scripted_effects.txt').read_text(encoding='utf-8-sig')
    assert re.search(r'for_each_scope_loop\s*=\s*{\s*array\s*=\s*global.countries',chi)
    assert 'is_core_of = PREV' in chi
    groups['installed_primary_country_array_scope_loop_and_native_PREV_usage']+=1
    nor=(installed/'common/decisions/NOR.txt').read_text(encoding='utf-8-sig')
    assert 'set_country_flag = NOR_already_asked_a_fascist@PREV' in nor
    groups['installed_primary_PREV_country_valued_pair_flag_suffix']+=1
    sprites=(installed/'interface/decisions.gfx').read_text(encoding='utf-8-sig')
    assert 'name = "GFX_decision_generic_decision"' in sprites
    assert any(b'GFX_decision_category_generic_foreign_policy' in path.read_bytes() for path in (ROOT/'interface').glob('*.gfx'))
    hookdocs=(installed/'common/on_actions/_documentation.md').read_text(encoding='utf-8-sig')
    assert '- '+chr(96)+'on_daily'+chr(96) in hookdocs
    assert '- '+chr(96)+'on_annex'+chr(96) in hookdocs and '- '+chr(96)+'on_subject_annexed'+chr(96) in hookdocs
    groups['installed_primary_existing_sprites_and_daily_annex_hook_IDs']+=1
    print(json.dumps({'all_passed':True,'total_cases':sum(groups.values()),'groups':groups,
                      'baseline':BASELINE,'baseline_gameplay_files':len(baseline_paths),
                      'existing_gameplay_files_byte_preserved':len(baseline_paths)-len(EXISTING),
                      'new_gameplay_files':len(NEW),'native_action_count':len(native_ids),
                      'owned_native_action_count':len(NATIVE_IDS),'owned_existing_effect_count':len(OLD_HELPERS),
                      'helper_count':len(helpers),'new_locale_keys':len(expected_locale),
                      'final_gameplay_sha256':{r['path']:r['sha256'] for r in receipts},
                      'runtime_verified':False},indent=2))


if __name__=='__main__':
    main()
