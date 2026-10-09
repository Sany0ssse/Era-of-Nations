"""Prepare a private uranium-only native rights classification probe; no launch."""
from pathlib import Path
import argparse
import json

from build_native_probe import ROOT, load_parser, sha

NS = 'eon_private_uranium_rights'
MARKER = 'EON_PRIVATE_URANIUM_RIGHTS'


def build(source, output, export_receipt=None, preparation_only=False, start_tag='NEP', after_core=False):
    source, output = source.resolve(), output.resolve()
    assert source.is_dir() and output != source and not (output/'manifest.json').exists()
    assert not (output/'launch-receipt.json').exists()
    if not preparation_only:
        assert source != ROOT.resolve() and source not in output.parents
        assert export_receipt and export_receipt.is_file()
    parser = load_parser()
    labels, observations, observation_roots = [], [], {}

    def check(label, predicate):
        assert label not in labels
        labels.append(label)
        return ('if = { limit = { '+predicate+' } add_to_variable = { global.'+NS+'_passes = 1 } '
                'log = "'+MARKER+' PASS '+label+'" } else = { add_to_variable = { global.'+NS+'_fails = 1 } '
                'log = "'+MARKER+' FAIL '+label+'" } ')

    def cv(var, value, compare='equals'):
        return 'check_variable = { var = '+var+' value = '+str(value)+' compare = '+compare+' } '

    fields = {'balance': 'resource@uranium', 'produced': 'resource_produced@uranium',
              'imported': 'resource_imported@uranium', 'exported': 'resource_exported@uranium',
              'consumed': 'resource_consumed@uranium', 'raw': 'eon_natural_uranium_stock_kg',
              'delivered': 'eon_uranium_last_delivered_kg', 'extracted': 'eon_uranium_last_extracted_kg',
              'rights_supply': 'eon_uranium_rights_supply_kg',
              'state_flow': 'global.'+NS+'_state_flow', 'state_reserve': 'global.'+NS+'_state_reserve'}

    def observe(label, actor='GER', root='GER'):
        assert label not in observations
        observations.append(label)
        observation_roots[label] = root
        snapshot = ('45 = { set_variable = { global.'+NS+'_state_flow = resource@uranium } '
                    'set_variable = { global.'+NS+'_state_reserve = eon_uranium_reserve_kg } } ')
        body = snapshot+'log = "'+MARKER+' OBS '+label+' ROOT=[ROOT.GetTag] THIS=[THIS.GetTag] '+' '.join(k+'=[?'+v+']' for k, v in fields.items())+'" '
        return body if actor == root else 'NEP = { '+body+' } '

    def queue(number, hours):
        return 'country_event = { id = '+NS+'.'+str(number)+' hours = '+str(hours)+' } '

    def event(number, body, actor='GER'):
        frame = 'tag = '+actor+' ROOT = { tag = '+actor+' } NEP = { exists = yes }'
        return ('country_event = { id = '+NS+'.'+str(number)+' hidden = yes is_triggered_only = yes immediate = { '
                'if = { limit = { NOT = { has_global_flag = '+NS+'_event_'+str(number)+' } } '
                'set_global_flag = '+NS+'_event_'+str(number)+' '+check('frame_'+str(number), frame)+
                'if = { limit = { '+frame+' } '+body+' } else = { log = "'+MARKER+' ABORT wrong_frame" } '
                '} else = { log = "'+MARKER+' DUPLICATE_EVENT '+str(number)+'" } } }')

    first = (check('state_owned_controlled_by_provider', '45 = { is_owned_by = GER is_controlled_by = GER }')+
             'set_country_flag = { flag = eon_uranium_import_attempted days = 30 value = 1 } '
             'NEP = { set_country_flag = { flag = eon_uranium_import_attempted days = 30 value = 1 } } '
             '45 = { clr_state_flag = eon_uranium_state_weekly_settled set_variable = { eon_uranium_reserve_kg = 2000000 } set_variable = { eon_uranium_capacity = 20 } '
             'set_variable = { eon_uranium_capacity_limit = 30 } eon_uranium_refresh_mine = yes } '+queue(2, 6))
    second = (observe('ger_before_rights')+observe('nep_before_rights', 'NEP')+
              check('provider_has_native_extraction', cv('resource_produced@uranium', 0, 'greater_than'))+
              'NEP = { set_variable = { '+NS+'_balance_before = resource@uranium } '
              'set_variable = { '+NS+'_produced_before = resource_produced@uranium } '
              'set_variable = { '+NS+'_imported_before = resource_imported@uranium } } '
              'give_resource_rights = { receiver = NEP state = 45 resources = { uranium } } '+
              check('native_uranium_only_rights_registered', 'NEP = { has_resources_rights = { state = 45 resources = { uranium } } }')+queue(3, 26))
    third = (observe('ger_after_rights')+observe('nep_after_rights', 'NEP')+
             check('native_rights_remain_registered_after_cache_wait', 'NEP = { has_resources_rights = { state = 45 resources = { uranium } } }')+
             'NEP = { '+check('rights_receiver_native_balance_positive', cv('resource@uranium', 0, 'greater_than'))+
             check('rights_receiver_does_not_control_provider_state', '45 = { NOT = { is_controlled_by = NEP } is_controlled_by = GER }')+' } '+
             observe('nep_before_material_settlement', 'NEP')+
             'NEP = { '+queue(5, 1)+' } ')
    # The production helper uses ROOT to identify the rights beneficiary. Invoke
    # it from a native event owned by NEP, never nested inside a GER-root event.
    fifth = ('clr_country_flag = eon_uranium_weekly_settled set_country_flag = eon_uranium_reactor_stock_in_kg '
             'clr_country_flag = enabled_nuclear_reactor_fuel_production '
             'set_variable = { eon_natural_uranium_stock_kg = 0 } set_variable = { var_reactor_material_stockpile = 0 } '
             'set_variable = { eon_depleted_uranium_stock_kg = 0 } set_variable = { enrichment_facilities = 0 } '
             'set_variable = { nuclear_fuel_consumption = 0 } eon_uranium_weekly_materials = yes '+
             observe('nep_after_material_settlement', 'NEP', 'NEP')+
             'remove_resource_rights = 45 GER = { '+queue(4, 26)+' } ')
    fourth = (observe('ger_after_rights_removed')+observe('nep_after_rights_removed', 'NEP')+
              check('native_rights_removed_after_cache_wait', 'NEP = { NOT = { has_resources_rights = { state = 45 resources = { uranium } } } }')+
              check('provider_native_extraction_restored', cv('resource_produced@uranium', 0, 'greater_than'))+
              'log = "'+MARKER+' END passes=[?global.'+NS+'_passes] fails=[?global.'+NS+'_fails]" set_global_flag = '+NS+'_finished')
    events = [event(number, body) for number, body in enumerate((first, second, third, fourth), 1)]
    events.append(event(5, fifth, 'NEP'))
    observations.remove('nep_after_material_settlement')
    observations.insert(observations.index('nep_before_material_settlement')+1, 'nep_after_material_settlement')
    start = ('set_global_flag = '+NS+'_booted set_variable = { global.'+NS+'_passes = 0 } '
             'set_variable = { global.'+NS+'_fails = 0 } log = "'+MARKER+' STARTUP native_resource_rights" GER = { '+queue(1, 1)+' } ')
    if after_core:
        startup = 'on_actions = { on_daily = { effect = { if = { limit = { tag = GER has_global_flag = eon_private_uranium_core_finished NOT = { has_global_flag = '+NS+'_booted } } '+start+' } } } }'
    else:
        startup = 'on_actions = { on_startup = { effect = { if = { limit = { NOT = { has_global_flag = '+NS+'_booted } } '+start+' } } } }'
    fixture = {'events/'+NS+'_events.txt': 'add_namespace = '+NS+'\n\n'+'\n\n'.join(events),
               'common/on_actions/'+NS+'_on_actions.txt': startup}
    output.mkdir(parents=True, exist_ok=True)
    for rel, body in fixture.items():
        parser.ast(body)
        target = output/'mod'/rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((body.replace('\r\n', '\n').replace('\n', '\r\n')+'\r\n').encode('utf-8'))
    dependencies = ['common/resources/00_resources.txt', 'common/scripted_effects/eon_uranium_effects.txt',
                    'common/scripted_effects/00_count_resource_rights_resources.txt',
                    'common/on_actions/00_resource_rights_on_actions.txt', 'history/states/45-Berlin.txt']
    docs = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation')
    manifest = {'schema': 1, 'kind': 'native_uranium_resource_rights', 'marker': MARKER,
                'source_root': str(source), 'fixture_root': str(output), 'preparation_only': preparation_only,
                'expected_native_start_tag': start_tag, 'expected_enabled_mods': ['mod/era_of_nations.mod'],
                'after_core': after_core, 'assertions': labels, 'observation_labels': observations,
                'observation_fields': fields, 'expected_root': 'GER',
                'expected_observation_roots': observation_roots,
                'expected_observation_actors': {label: 'NEP' if label.startswith('nep_') else 'GER' for label in observations},
                'minimum_total_native_hours': 48,
                'source_sha256': {rel: sha(source/rel) for rel in dependencies},
                'fixture_sha256': {rel: sha(output/'mod'/rel) for rel in fixture}, 'builder_sha256': sha(Path(__file__)),
                'installed_documentation_root': str(docs),
                'installed_documentation_sha256': {rel: sha(docs/rel) for rel in ('dynamic_variables_documentation.md', 'effects_documentation.md', 'triggers_documentation.md')},
                'source_export_binding': None if not export_receipt else {'path': str(export_receipt.resolve()), 'sha256': sha(export_receipt)},
                'limits': ['Native uranium-only rights classifier with controlled private state output.',
                           'Current production material credit is measured independently; native rights success does not prove that credit is correct.',
                           'No final-deposit two-country simultaneous cache proof, GUI click, royalty/GDP, campaign or multiplayer acceptance.']}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return manifest


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source-root', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--export-receipt', type=Path)
    cli.add_argument('--prepare-only', action='store_true')
    cli.add_argument('--start-tag', default='NEP')
    cli.add_argument('--after-core', action='store_true')
    args = cli.parse_args()
    manifest = build(args.source_root, args.output, args.export_receipt, args.prepare_only, args.start_tag, args.after_core)
    print(json.dumps({'rights_fixture_prepared': True, 'assertions': len(manifest['assertions']),
                      'observations': len(manifest['observation_labels']), 'native_behavior_tested': False}))


if __name__ == '__main__': main()
