"""Prepare coastal native uranium/oil rights controls without launching the game."""
from pathlib import Path
import argparse
import json

from build_native_probe import ROOT, load_parser, sha

NS = 'eon_private_uranium_rights_connectivity'
MARKER = 'EON_PRIVATE_URANIUM_RIGHTS_CONNECTIVITY'


def build(source, output, export_receipt=None, preparation_only=False, start_tag='NEP', recipient='ENG'):
    source, output = source.resolve(), output.resolve()
    assert source.is_dir() and output != source and not (output/'manifest.json').exists()
    assert not (output/'launch-receipt.json').exists() and recipient in ('ENG', 'CAN')
    if not preparation_only:
        assert source != ROOT.resolve() and source not in output.parents
        assert export_receipt and export_receipt.is_file()
    parser = load_parser()
    assertions, observations, roots, actors = [], [], {}, {}

    def check(label, predicate):
        assertions.append(label)
        return ('if = { limit = { '+predicate+' } add_to_variable = { global.'+NS+'_passes = 1 } '
                'log = "'+MARKER+' PASS '+label+'" } else = { add_to_variable = { global.'+NS+'_fails = 1 } '
                'log = "'+MARKER+' FAIL '+label+'" } ')

    fields = {'uranium_balance': 'resource@uranium', 'uranium_produced': 'resource_produced@uranium',
              'uranium_imported': 'resource_imported@uranium', 'uranium_exported': 'resource_exported@uranium',
              'uranium_consumed': 'resource_consumed@uranium', 'oil_balance': 'resource@oil',
              'oil_produced': 'resource_produced@oil', 'oil_imported': 'resource_imported@oil',
              'oil_exported': 'resource_exported@oil', 'oil_consumed': 'resource_consumed@oil',
              'state_uranium': 'global.'+NS+'_state_uranium', 'state_oil': 'global.'+NS+'_state_oil',
              'raw': 'eon_natural_uranium_stock_kg', 'delivered': 'eon_uranium_last_delivered_kg',
              'rights_supply': 'eon_uranium_rights_supply_kg'}

    def observe(label, actor='GER', root='GER'):
        observations.append(label)
        roots[label], actors[label] = root, actor
        body = ('45 = { set_variable = { global.'+NS+'_state_uranium = resource@uranium } '
                'set_variable = { global.'+NS+'_state_oil = resource@oil } } '
                'log = "'+MARKER+' OBS '+label+' ROOT=[ROOT.GetTag] THIS=[THIS.GetTag] '+
                ' '.join(key+'=[?'+value+']' for key, value in fields.items())+'" ')
        return body if actor == root else actor+' = { '+body+' } '

    def queue(number, hours=1):
        return 'country_event = { id = '+NS+'.'+str(number)+' hours = '+str(hours)+' } '

    def event(number, body, actor='GER'):
        frame = 'tag = '+actor+' ROOT = { tag = '+actor+' } '
        return ('country_event = { id = '+NS+'.'+str(number)+' hidden = yes is_triggered_only = yes immediate = { '
                'if = { limit = { NOT = { has_global_flag = '+NS+'_event_'+str(number)+' } } '
                'set_global_flag = '+NS+'_event_'+str(number)+' '+check('frame_'+str(number), frame)+
                'if = { limit = { '+frame+' } '+body+' } else = { log = "'+MARKER+' ABORT wrong_frame" } '
                '} else = { log = "'+MARKER+' DUPLICATE_EVENT '+str(number)+'" } } }')

    hold = ('set_country_flag = { flag = eon_uranium_import_attempted days = 30 value = 1 } '
            'set_country_flag = { flag = eon_uranium_weekly_settled days = 30 value = 1 } '
            'add_equipment_to_stockpile = { type = convoy amount = 1000 producer = THIS } ')
    first = (check('provider_owns_controls_state45', '45 = { is_owned_by = GER is_controlled_by = GER } ')+
             check('coastal_receiver_exists_at_peace', recipient+' = { exists = yes NOT = { has_war_with = GER } } ')+
             '45 = { clr_state_flag = eon_uranium_state_weekly_settled '
             'set_variable = { eon_uranium_reserve_kg = 2000000 } set_variable = { eon_uranium_capacity = 20 } '
             'set_variable = { eon_uranium_capacity_limit = 30 } eon_uranium_refresh_mine = yes '
             'add_resource = { type = oil amount = 80 } } '+queue(2, 6))
    second = (observe('provider_before')+observe('receiver_before', recipient)+
              'give_resource_rights = { receiver = '+recipient+' state = 45 resources = { uranium oil } } '+
              check('native_both_resource_rights_registered', recipient+' = { has_resources_rights = { state = 45 resources = { uranium oil } } } ')+queue(3, 32))
    third = (observe('provider_after')+observe('receiver_after', recipient)+
             check('native_both_resource_rights_survive_cache_wait', recipient+' = { has_resources_rights = { state = 45 resources = { uranium oil } } } ')+
             recipient+' = { '+queue(4, 1)+' } ')
    fourth = ('clr_country_flag = eon_uranium_weekly_settled set_country_flag = eon_uranium_reactor_stock_in_kg '
              'clr_country_flag = enabled_nuclear_reactor_fuel_production '
              'set_variable = { eon_natural_uranium_stock_kg = 0 } set_variable = { var_reactor_material_stockpile = 0 } '
              'set_variable = { eon_depleted_uranium_stock_kg = 0 } set_variable = { enrichment_facilities = 0 } '
              'set_variable = { nuclear_fuel_consumption = 0 } '+observe('receiver_before_settlement', recipient, recipient)+
              'eon_uranium_weekly_materials = yes '+observe('receiver_after_settlement', recipient, recipient)+
              'log = "'+MARKER+' END passes=[?global.'+NS+'_passes] fails=[?global.'+NS+'_fails]" set_global_flag = '+NS+'_finished ')
    events = [event(1, first), event(2, second), event(3, third), event(4, fourth, recipient)]
    fixture = {'events/'+NS+'_events.txt': 'add_namespace = '+NS+'\n\n'+'\n\n'.join(events),
               'common/on_actions/'+NS+'_on_actions.txt':
               'on_actions = { on_startup = { effect = { if = { limit = { NOT = { has_global_flag = '+NS+'_booted } } '
               'set_global_flag = '+NS+'_booted set_variable = { global.'+NS+'_passes = 0 } set_variable = { global.'+NS+'_fails = 0 } '
               'log = "'+MARKER+' STARTUP coastal_resource_rights" GER = { '+hold+queue(1)+' } '+recipient+' = { '+hold+' } } } } }'}
    output.mkdir(parents=True, exist_ok=True)
    for rel, body in fixture.items():
        parser.ast(body)
        path = output/'mod'/rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((body.replace('\r\n', '\n').replace('\n', '\r\n')+'\r\n').encode('utf-8'))
    dependencies = ('common/resources/00_resources.txt', 'common/scripted_effects/eon_uranium_effects.txt',
                    'common/scripted_effects/00_count_resource_rights_resources.txt',
                    'common/on_actions/00_resource_rights_on_actions.txt', 'history/states/45-Berlin.txt')
    docs = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation')
    manifest = {'schema': 1, 'kind': 'native_uranium_rights_connectivity_control', 'marker': MARKER,
                'source_root': str(source), 'fixture_root': str(output), 'preparation_only': preparation_only,
                'expected_native_start_tag': start_tag, 'expected_enabled_mods': ['mod/era_of_nations.mod'],
                'recipient': recipient, 'assertions': assertions, 'observation_labels': observations,
                'observation_fields': fields, 'expected_observation_roots': roots, 'expected_observation_actors': actors,
                'minimum_total_native_hours': 26, 'source_sha256': {rel: sha(source/rel) for rel in dependencies},
                'fixture_sha256': {rel: sha(output/'mod'/rel) for rel in fixture}, 'builder_sha256': sha(Path(__file__)),
                'installed_documentation_root': str(docs),
                'installed_documentation_sha256': {rel: sha(docs/rel) for rel in ('dynamic_variables_documentation.md', 'effects_documentation.md', 'triggers_documentation.md')},
                'source_export_binding': None if not export_receipt else {'path': str(export_receipt.resolve()), 'sha256': sha(export_receipt)},
                'limits': ['Coastal beneficiary, peace and1000 additional convoys for each country; no asserted optimal route.',
                           'Oil native resource is a paired positive control; no inferred uranium delivery from legal rights alone.',
                           'Native classification probe and actual public material callback; no final deposit, royalties, human GUI, save/load or multiplayer.']}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return manifest


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source-root', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--export-receipt', type=Path)
    cli.add_argument('--prepare-only', action='store_true')
    cli.add_argument('--start-tag', default='NEP')
    cli.add_argument('--recipient', choices=('ENG', 'CAN'), default='ENG')
    args = cli.parse_args()
    result = build(args.source_root, args.output, args.export_receipt, args.prepare_only, args.start_tag, args.recipient)
    print(json.dumps({'coastal_rights_fixture_prepared': True, 'assertions': len(result['assertions']), 'native_game_behavior_tested': False}))


if __name__ == '__main__': main()
