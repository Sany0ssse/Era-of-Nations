"""Prepare a private native missile inventory/deployment probe; never launch.

The air OOB is registered through private country history, as required by the
installed set_air_oob documentation. Test missiles do not establish research UI,
manual silo loading, or raid firing.
"""
from pathlib import Path
import argparse
import hashlib
import json

from test_launch import ROOT, TOKEN, ast

NS = 'eon_private_missile_probe'
MARKER = 'EON_PRIVATE_MISSILE_PROBE'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def merge_block(text, fragment, path):
    """Insert at an exact block path while retaining all original bytes."""
    tokens = [match for match in TOKEN.finditer(text) if not match[0].startswith('#')]
    stack, closes = [], []
    for index, token in enumerate(tokens):
        if token[0] == '{':
            assert index >= 2 and tokens[index-1][0] == '='
            stack.append(tokens[index-2][0].lstrip('\ufeff'))
        elif token[0] == '}':
            assert stack
            if tuple(stack) == tuple(path):
                closes.append(token.start())
            stack.pop()
    assert not stack and len(closes) == 1, ('Expected one original block', path, len(closes))
    position = closes[0]
    result = text[:position]+fragment+text[position:]
    assert result[:position]+result[position+len(fragment):] == text
    ast(result)
    return result


def merge_history(text, fragment, date='2000.1.1'):
    """Register last inside the original date, preserving its other commands.

    Duplicate dates are used in vanilla history; this merge does not assume
    they are ignored. It avoids ambiguity about which air OOB is registered
    last under the documented replacement rule. Comments/quotes remain intact.
    """
    return merge_block(text, fragment, (date,))


def build(source, output, export_receipt=None, preparation_only=False, start_tag='NEP', start_delay_hours=30):
    source, output = source.resolve(), output.resolve()
    assert source.is_dir() and source != output
    assert not (output / 'manifest.json').exists() and not (output / 'launch-receipt.json').exists()
    if not preparation_only:
        assert source != ROOT.resolve() and source not in output.parents
        assert export_receipt and export_receipt.is_file()
    fixture, assertions, observations, observation_actors = {}, [], [], {}
    counters = {
        'all_deployed_planes': 'num_deployed_planes',
        'nuclear_reserve': 'num_equipment@nuclear_missile_equipment',
        'short_nuclear_reserve': 'num_equipment@nuclear_ballistic_missile_equipment',
        'guided_reserve': 'num_equipment@guided_missile_equipment',
        'ballistic_reserve': 'num_equipment@ballistic_missile_equipment',
        'nuclear_deployed_archetype': 'num_deployed_planes_with_type@nuclear_missile_equipment',
        'nuclear_deployed_enum': 'num_deployed_planes_with_type@nuclear_missile',
        'short_nuclear_deployed_archetype': 'num_deployed_planes_with_type@nuclear_ballistic_missile_equipment',
        'ballistic_deployed_enum': 'num_deployed_planes_with_type@ballistic_missile',
        'guided_deployed_archetype': 'num_deployed_planes_with_type@guided_missile_equipment',
        'guided_deployed_enum': 'num_deployed_planes_with_type@missile',
        'ballistic_deployed_archetype': 'num_deployed_planes_with_type@ballistic_missile_equipment',
        'nuclear_equipment_in_armies': 'num_equipment_in_armies@nuclear_missile_equipment',
        'short_nuclear_equipment_in_armies': 'num_equipment_in_armies@nuclear_ballistic_missile_equipment',
        'guided_equipment_in_armies': 'num_equipment_in_armies@guided_missile_equipment',
        'ballistic_equipment_in_armies': 'num_equipment_in_armies@ballistic_missile_equipment',
        'nuclear_deployed_model': 'num_deployed_planes_with_type@nuclear_missile_equipment_1',
        'short_nuclear_deployed_model': 'num_deployed_planes_with_type@nuclear_ballistic_missile_equipment_1',
        'guided_deployed_model': 'num_deployed_planes_with_type@guided_missile_equipment_1',
        'ballistic_deployed_model': 'num_deployed_planes_with_type@ballistic_missile_equipment_1',
        'control_fighter_deployed_archetype': 'num_deployed_planes_with_type@small_plane_airframe',
        'control_fighter_deployed_enum': 'num_deployed_planes_with_type@fighter',
        'control_fighter_deployed_model': 'num_deployed_planes_with_type@small_plane_airframe_1',
        'control_fighter_equipment_in_armies': 'num_equipment_in_armies@small_plane_airframe',
    }

    def cv(var, amount, compare='equals'):
        return 'check_variable = { var = '+var+' value = '+str(amount)+' compare = '+compare+' } '

    def check(label, predicate):
        assert label not in assertions
        assertions.append(label)
        return ('if = { limit = { '+predicate+' } add_to_variable = { global.'+NS+'_passes = 1 } '
                'log = "'+MARKER+' PASS '+label+'" } else = { add_to_variable = { global.'+NS+'_fails = 1 } '
                'log = "'+MARKER+' FAIL '+label+'" } ')

    def obs(tag, phase):
        label = tag.lower()+'_'+phase
        assert label not in observations
        observations.append(label)
        observation_actors[label] = tag
        return ('log = "'+MARKER+' OBS '+label+' ROOT=[ROOT.GetTag] THIS=[THIS.GetTag] '+
                ' '.join(name+'=[?'+var+']' for name, var in counters.items())+'" ')

    events, boot = [], []
    history_sources, state_sources = {}, {}
    control_model, control_name = 'small_plane_airframe_1', 'Private fighter control'
    # The modules are copied from FRA's historical Mirage F1, not an empty BBA
    # airframe. The corresponding current-mod technologies are granted below.
    control_modules = ('fixed_main_weapon_slot = weap_a2a_hardpoint_1 '
                       'fixed_gun_slot = weap_multi_gun_1 '
                       'engine_type_slot = engine_light_single_1 '
                       'avionics_type_slot = avionics_manned_2 '
                       'wingform_type_slot = wing_swept '
                       'special_slot_type_1 = spec_countermeasures_1')
    models = (('nuclear_missile_equipment_1', 'Private nuclear test', 2, 3),
              ('nuclear_ballistic_missile_equipment_1', 'Private short nuclear test', 4, 5),
              ('guided_missile_equipment_1', 'Private cruise test', 2, 7),
              ('ballistic_missile_equipment_1', 'Private ballistic test', 3, 11))
    for index, (tag, capital) in enumerate((('GER', 45), ('FRA', 56), ('RAJ', 431)), 1):
        oob_name = NS+'_'+tag.lower()
        history_file, = (source/'history/countries').glob(tag+' - *.txt')
        history_rel = history_file.relative_to(source).as_posix()
        history_sources[history_rel] = sha(history_file)
        state_file, = (source/'history/states').glob(str(capital)+'-*.txt')
        state_rel = state_file.relative_to(source).as_posix()
        state_sources[state_rel] = sha(state_file)
        state_text = state_file.read_bytes().decode('utf-8')
        state_newline = '\r\n' if '\r\n' in state_text else '\n'
        fixture[state_rel] = merge_block(state_text, state_newline+'\t\t\trocket_site = 10'+state_newline,
                                        ('state', 'history', 'buildings'))
        # History registration is necessary: runtime load_oob does not create
        # air wings. This private override retains the entire original history.
        history_text = history_file.read_bytes().decode('utf-8')
        history_newline = '\r\n' if '\r\n' in history_text else '\n'
        history_fragment = (history_newline+'\t# Private native missile probe: final commands in the original dated block.'+history_newline+
            '\tif = { limit = { has_dlc = "Gotterdammerung" } complete_special_project = sp:sp_missile_project '+
            'complete_special_project = sp:sp_nuclear_warhead_program } '+
            'set_technology = { ICBM = 1 IRBM = 1 GLCM = 1 ICBM1 = 1 NIRBM1 = 1 IRBM1 = 1 GLCM1 = 1 '+
            'early_airframe_designs = 1 gen_3_light = 1 early_weapons = 1 air_weapons_1 = 1 '+
            'avionics_1 = 1 countermeasures_1 = 1 popup = no } '+
            ' '.join('create_equipment_variant = { type = '+model+' name = "'+name+'" }' for model, name, count, added in models)+' '+
            'create_equipment_variant = { type = '+control_model+' name = "'+control_name+'" modules = { '+control_modules+' } } '+
            'set_air_oob = "'+oob_name+'" '+
            'set_country_flag = '+NS+'_history_registered '+
            'set_variable = { '+NS+'_history_registration = 1 } '+
            'log = "'+MARKER+' HISTORY registered '+tag+' THIS=[THIS.GetTag]"'+history_newline)
        fixture[history_rel] = merge_history(history_text, history_fragment)
        wings = ''
        for model, name, count, added in models:
            # Seed distinct understrength nuclear wing entries with one item
            # each. Production retains its original delivery capacities; this
            # fixture never assumes that a wing's nominal size is one.
            amount = 1 if model.startswith('nuclear_') else count
            repeats = count if amount == 1 else 1
            wings += (model+' = { owner = "'+tag+'" amount = '+str(amount)+' version_name = "'+name+'" } name = "'+name+'" ')*repeats
        fixture['history/units/'+oob_name+'.txt'] = (
            'air_wings = { '+str(capital)+' = { '+wings+
            control_model+' = { owner = "'+tag+'" amount = 1 version_name = "'+control_name+'" } name = "'+control_name+'" } }\n')
        save_baseline = ' '.join('set_variable = { '+NS+'_baseline_'+name+' = '+var+' }' for name, var in counters.items())+' '
        reserve = ('set_technology = { ICBM1 = 1 NIRBM1 = 1 IRBM1 = 1 GLCM1 = 1 popup = no } '+
                   ' '.join('add_equipment_to_stockpile = { type = '+model+' amount = '+str(added)+' producer = THIS variant_name = "'+name+'" }'
                            for model, name, count, added in models)+' ')
        checks = ''
        for name, added in (('nuclear_reserve', 3), ('short_nuclear_reserve', 5), ('guided_reserve', 7), ('ballistic_reserve', 11)):
            checks += ('set_temp_variable = { '+NS+'_delta = '+counters[name]+' } '
                       'subtract_from_temp_variable = { '+NS+'_delta = '+NS+'_baseline_'+name+' } '+
                       check(tag.lower()+'_reserve_added_'+name, cv(NS+'_delta', added)))
        # Air units must already exist before baseline. Unsupported runtime
        # load_oob is deliberately absent; history is the sole deployment path.
        body = (check(tag.lower()+'_frame_initial', 'tag = '+tag+' ROOT = { tag = '+tag+' }')+
                check(tag.lower()+'_history_registered', NS+'_history_registration_ready = yes')+
                check(tag.lower()+'_missile_base_techs_enabled', 'has_tech = ICBM has_tech = IRBM has_tech = GLCM')+
                obs(tag, 'baseline')+
                check(tag.lower()+'_initial_deployed_total_twelve_experiment', cv(counters['all_deployed_planes'], 12))+
                check(tag.lower()+'_control_fighter_deployed', cv(counters['control_fighter_deployed_archetype'], 0, 'greater_than'))+
                save_baseline+reserve+obs(tag, 'reserve_added')+checks+
                str(capital)+' = { '+check(tag.lower()+'_owned_controlled_capital', 'is_owned_by = '+tag+' is_controlled_by = '+tag)+
                check(tag.lower()+'_rocket_site_ready', cv('non_damaged_building_level@rocket_site', 9, 'greater_than'))+' } '+
                obs(tag, 'loaded')+
                'country_event = { id = '+NS+'.'+str(index+3)+' hours = 25 } ')
        events.append('country_event = { id = '+NS+'.'+str(index)+' hidden = yes is_triggered_only = yes immediate = { '
                      'if = { limit = { NOT = { has_country_flag = '+NS+'_initial } } set_country_flag = '+NS+'_initial '+body+
                      '} else = { log = "'+MARKER+' DUPLICATE_EVENT initial_'+tag+'" } } }')
        later = (check(tag.lower()+'_frame_after_day', 'tag = '+tag+' ROOT = { tag = '+tag+' }')+
                 obs(tag, 'after_day')+
                 check(tag.lower()+'_deployed_total_at_least_twelve_experiment', cv(counters['all_deployed_planes'], 11, 'greater_than'))+
                 check(tag.lower()+'_control_fighter_still_deployed', cv(counters['control_fighter_deployed_archetype'], 0, 'greater_than'))+
                 check(tag.lower()+'_deployed_nuclear_enum_positive', cv(counters['nuclear_deployed_enum'], 0, 'greater_than'))+
                 check(tag.lower()+'_deployed_ballistic_enum_positive', cv(counters['ballistic_deployed_enum'], 0, 'greater_than'))+
                 'set_global_flag = '+NS+'_'+tag.lower()+'_done ')
        if index == 3:
            later += ('if = { limit = { has_global_flag = '+NS+'_ger_done has_global_flag = '+NS+'_fra_done } '
                      'log = "'+MARKER+' END passes=[?global.'+NS+'_passes] fails=[?global.'+NS+'_fails]" '
                      'set_global_flag = '+NS+'_finished } else = { log = "'+MARKER+' ABORT incomplete_country_probes" } ')
        events.append('country_event = { id = '+NS+'.'+str(index+3)+' hidden = yes is_triggered_only = yes immediate = { '
                      'if = { limit = { NOT = { has_country_flag = '+NS+'_after_day } } set_country_flag = '+NS+'_after_day '+later+
                      '} else = { log = "'+MARKER+' DUPLICATE_EVENT after_day_'+tag+'" } } }')
        boot.append('if = { limit = { tag = '+tag+' } country_event = { id = '+NS+'.'+str(index)+' hours = '+str(start_delay_hours)+' } } ')
    fixture['events/'+NS+'_events.txt'] = 'add_namespace = '+NS+'\n'+'\n'.join(events)+'\n'
    fixture['common/scripted_triggers/'+NS+'_triggers.txt'] = (
        NS+'_history_registration_ready = { has_country_flag = '+NS+'_history_registered '+
        cv(NS+'_history_registration', 1)+'}\n')
    fixture['common/on_actions/'+NS+'_on_actions.txt'] = (
        'on_actions = { on_startup = { effect = { if = { limit = { NOT = { has_global_flag = '+NS+'_booted } } '
        'set_global_flag = '+NS+'_booted set_variable = { global.'+NS+'_passes = 0 } set_variable = { global.'+NS+'_fails = 0 } '
        'log = "'+MARKER+' STARTUP native_missile_inventory_deployment" every_country = { '+''.join(boot)+'} } } } }\n')
    output.mkdir(parents=True, exist_ok=True)
    for rel, text in fixture.items():
        ast(text)
        path = output / 'mod' / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode('utf-8'))
    deps = ('common/raids/nuclear_raids.txt', 'common/raids/eon_tactical_nuclear_missile_raid.txt',
            'common/scripted_triggers/00_raids_triggers.txt',
            'common/units/MD_air_units.txt', 'common/units/equipment/MD_nuclear_missiles.txt',
            'common/units/equipment/MD_ballistic_missiles.txt', 'common/units/equipment/MD_guided_missiles.txt',
            'common/technologies/ballistic_missiles.txt', 'common/technologies/cruise_missiles.txt',
            'common/technologies/BBA_aircraft.txt', 'common/units/equipment/MD_plane_airframes.txt',
            'common/buildings/00_buildings.txt')
    docs = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation')
    manifest = {'schema': 1, 'kind': 'native_missile_inventory_deployment', 'marker': MARKER,
                'source_root': str(source), 'fixture_root': str(output), 'preparation_only': preparation_only,
                'expected_native_start_tag': start_tag, 'expected_enabled_mods': ['mod/era_of_nations.mod'],
                'assertions': assertions, 'observation_labels': observations,
                'expected_observation_actors': observation_actors, 'observation_fields': counters,
                'minimum_total_native_hours': 24, 'callback_bindings': [],
                'source_sha256': {rel: sha(source/rel) for rel in deps},
                'private_country_history_source_sha256': history_sources,
                'private_state_history_source_sha256': state_sources,
                'deployment_method': 'private_history_merged_date_set_air_oob',
                'history_registration_date': '2000.1.1',
                'history_registration_flag': NS+'_history_registered',
                'expected_private_starting_aircraft': {'nuclear': 2, 'short_nuclear': 4, 'guided': 2, 'ballistic': 3, 'control_fighter': 1},
                'fixture_sha256': {rel: sha(output/'mod'/rel) for rel in fixture},
                'builder_sha256': sha(Path(__file__)), 'installed_documentation_root': str(docs),
                'installed_documentation_sha256': {rel: sha(docs/rel) for rel in ('effects_documentation.md', 'dynamic_variables_documentation.md', 'triggers_documentation.md')},
                'source_export_binding': None if not export_receipt else {'path': str(export_receipt.resolve()), 'sha256': sha(export_receipt)},
                'limits': ['Private history set_air_oob deployment tests native type recognition, not a human silo-loading click.',
                           'No actual raid preparation/launch, automatic one_use_only consumption, missile defence, submarine loading, campaign, save/load or multiplayer proof.',
                           'Total12 is an experiment about native counter inclusion, not an assumption that the total-aircraft getter includes missiles.',
                           'Counter observations determine deployed-inventory semantics; no undeclared assumption about their inclusion.']}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source-root', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--export-receipt', type=Path)
    cli.add_argument('--prepare-only', action='store_true')
    cli.add_argument('--start-tag', default='NEP')
    cli.add_argument('--start-delay-hours', default=30, type=int)
    args = cli.parse_args()
    result = build(args.source_root, args.output, args.export_receipt, args.prepare_only, args.start_tag, args.start_delay_hours)
    print(json.dumps({'prepared': True, 'assertions': len(result['assertions']), 'native_tested': False,
                      'manifest': str(args.output/'manifest.json')}))
