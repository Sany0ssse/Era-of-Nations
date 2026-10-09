"""Prepare two source-bound final-shipment rights orders; never launch HOI4."""
from pathlib import Path
import argparse
import json

from build_native_probe import ROOT, load_parser, sha

NS = 'eon_private_uranium_final_rights'
MARKER = 'EON_PRIVATE_URANIUM_FINAL_RIGHTS'


def build(source, output, export_receipt=None, preparation_only=False, start_tag='NEP', after_rights=False):
    source, output = source.resolve(), output.resolve()
    assert source.is_dir() and output != source
    assert not (output/'manifest.json').exists() and not (output/'launch-receipt.json').exists()
    if not preparation_only:
        assert source != ROOT.resolve() and source not in output.parents
        assert export_receipt and export_receipt.is_file()
    parser = load_parser()
    assertions, observations, frames = [], [], {}
    fields = {'balance': 'resource@uranium', 'produced': 'resource_produced@uranium',
              'imported': 'resource_imported@uranium', 'exported': 'resource_exported@uranium',
              'raw': 'eon_natural_uranium_stock_kg', 'delivered': 'eon_uranium_last_delivered_kg',
              'extracted': 'eon_uranium_last_extracted_kg', 'rights_supply': 'eon_uranium_rights_supply_kg',
              'state_flow': 'global.'+NS+'_state_flow', 'state_reserve': 'global.'+NS+'_state_reserve',
              'state_extracted': 'global.'+NS+'_state_extracted', 'state_recipient': 'global.'+NS+'_state_recipient',
              'recipient_delivery_before': 'global.'+NS+'_recipient_delivery_before',
              'final_reserve_before': 'global.'+NS+'_final_reserve_before'}

    def cv(var, value, compare='equals'):
        return 'check_variable = { var = '+var+' value = '+str(value)+' compare = '+compare+' } '

    def check(label, predicate):
        assert label not in assertions
        assertions.append(label)
        return ('if = { limit = { '+predicate+' } add_to_variable = { global.'+NS+'_passes = 1 } '
                'log = "'+MARKER+' PASS '+label+'" } else = { add_to_variable = { global.'+NS+'_fails = 1 } '
                'log = "'+MARKER+' FAIL '+label+'" } ')

    def observe(label, root, actor=None):
        actor = actor or root
        observations.append(label)
        frames[label] = {'root': root, 'actor': actor}
        snapshot = ('45 = { set_variable = { global.'+NS+'_state_flow = resource@uranium } '
                    'set_variable = { global.'+NS+'_state_reserve = eon_uranium_reserve_kg } '
                    'set_variable = { global.'+NS+'_state_extracted = eon_uranium_state_last_extracted_kg } '
                    'set_variable = { global.'+NS+'_state_recipient = eon_uranium_state_last_rights_recipient } } ')
        body = snapshot+'log = "'+MARKER+' OBS '+label+' ROOT=[ROOT.GetTag] THIS=[THIS.GetTag] '+ ' '.join(k+'=[?'+v+']' for k, v in fields.items())+'" '
        return body if actor == root else actor+' = { '+body+' } '

    def queue(number, hours=None, target=None):
        body = 'country_event = { id = '+NS+'.'+str(number)+((' hours = '+str(hours)) if hours is not None else '')+' } '
        return body if not target else target+' = { '+body+' } '

    def event(number, actor, body):
        frame = 'tag = '+actor+' ROOT = { tag = '+actor+' }'
        return ('country_event = { id = '+NS+'.'+str(number)+' hidden = yes is_triggered_only = yes immediate = { '
                'if = { limit = { NOT = { has_global_flag = '+NS+'_event_'+str(number)+' } } '
                'set_global_flag = '+NS+'_event_'+str(number)+' '+check('frame_'+str(number), frame)+
                'if = { limit = { '+frame+' } '+body+' } else = { log = "'+MARKER+' ABORT wrong_frame" } '
                '} else = { log = "'+MARKER+' DUPLICATE_EVENT '+str(number)+'" } } }')

    def hold():
        # This blocks only automatic uranium settlement/imports in the private
        # test countries. Daily refresh and native trade cache stay enabled.
        return ''.join(tag+' = { set_country_flag = { flag = eon_uranium_weekly_settled days = 30 value = 1 } '
                       'set_country_flag = { flag = eon_uranium_import_attempted days = 30 value = 1 } } '
                       for tag in ('GER', 'NEP'))

    def fresh_mine():
        return (hold()+'NEP = { remove_resource_rights = 45 } '
                '45 = { set_state_owner_to = GER set_state_controller_to = GER '
                'set_variable = { eon_uranium_capacity = 0 } eon_uranium_refresh_mine = yes '
                'set_variable = { eon_uranium_reserve_kg = 2000000 } set_variable = { eon_uranium_capacity = 9 } '
                'set_variable = { eon_uranium_capacity_limit = 30 } '
                'set_variable = { eon_uranium_state_last_extracted_kg = 0 } '
                'set_state_flag = { flag = eon_uranium_state_weekly_settled days = 30 value = 1 } eon_uranium_refresh_mine = yes } ')

    def prepare_final():
        return ('45 = { clr_state_flag = eon_uranium_state_weekly_settled '
                'set_variable = { eon_uranium_reserve_kg = resource@uranium } '
                'multiply_variable = { eon_uranium_reserve_kg = 100 } '
                'set_variable = { global.'+NS+'_final_reserve_before = eon_uranium_reserve_kg } } '
                'NEP = { set_variable = { global.'+NS+'_recipient_delivery_before = resource@uranium } '
                'multiply_variable = { global.'+NS+'_recipient_delivery_before = 100 } } '+
                ''.join(tag+' = { clr_country_flag = eon_uranium_weekly_settled '
                        'set_country_flag = eon_uranium_reactor_stock_in_kg '
                        'clr_country_flag = enabled_nuclear_reactor_fuel_production '
                        'set_variable = { eon_natural_uranium_stock_kg = 0 } '
                        'set_variable = { var_reactor_material_stockpile = 0 } '
                        'set_variable = { eon_depleted_uranium_stock_kg = 0 } '
                        'set_variable = { enrichment_facilities = 0 } '
                        'set_variable = { nuclear_fuel_consumption = 0 } } '
                        for tag in ('GER', 'NEP')))

    def final_checks(order):
        return (check(order+'_recipient_credit_preserves_predepletion_delivery',
                      cv('NEP.eon_natural_uranium_stock_kg', 'global.'+NS+'_recipient_delivery_before')+
                      cv('NEP.eon_natural_uranium_stock_kg', 0, 'greater_than'))+
                check(order+'_shared_state_depletion_once', '45 = { '+cv('eon_uranium_reserve_kg', 0)+
                      cv('eon_uranium_applied_output', 0)+cv('resource@uranium', 0)+
                      cv('eon_uranium_state_last_extracted_kg', 'global.'+NS+'_final_reserve_before')+
                      cv('eon_uranium_state_last_rights_recipient', 'NEP.id')+' } '))

    first = (check('initial_provider_state_frame', '45 = { is_owned_by = GER is_controlled_by = GER }')+
             fresh_mine()+queue(2, 6))
    second = (observe('owner_first_before_rights', 'GER')+
              'give_resource_rights = { receiver = NEP state = 45 resources = { uranium } } '+queue(3, 26))
    third = (check('owner_first_rights_positive_native_delivery', 'NEP = { has_resources_rights = { state = 45 resources = { uranium } } '+cv('resource@uranium', 0, 'greater_than')+' } ')+
             prepare_final()+observe('owner_first_before_owner_settlement', 'GER')+
             observe('owner_first_recipient_before_owner', 'GER', 'NEP')+
             'eon_uranium_weekly_materials = yes '+observe('owner_first_after_owner_settlement', 'GER')+
             observe('owner_first_recipient_after_owner', 'GER', 'NEP')+queue(4, target='NEP'))
    fourth = (observe('owner_first_before_recipient_settlement', 'NEP')+
              'eon_uranium_weekly_materials = yes '+observe('owner_first_after_recipient_settlement', 'NEP')+
              queue(5, target='GER'))
    fifth = (final_checks('owner_first')+fresh_mine()+queue(6, 6))
    sixth = (observe('recipient_first_before_rights', 'GER')+
             'give_resource_rights = { receiver = NEP state = 45 resources = { uranium } } '+queue(7, 26))
    seventh = (check('recipient_first_rights_positive_native_delivery', 'NEP = { has_resources_rights = { state = 45 resources = { uranium } } '+cv('resource@uranium', 0, 'greater_than')+' } ')+
               prepare_final()+queue(8, target='NEP'))
    eighth = (observe('recipient_first_before_recipient_settlement', 'NEP')+
              'eon_uranium_weekly_materials = yes '+observe('recipient_first_after_recipient_settlement', 'NEP')+
              queue(9, target='GER'))
    ninth = (observe('recipient_first_before_owner_settlement', 'GER')+
             'eon_uranium_weekly_materials = yes '+observe('recipient_first_after_owner_settlement', 'GER')+
             final_checks('recipient_first')+'log = "'+MARKER+' END passes=[?global.'+NS+'_passes] fails=[?global.'+NS+'_fails]" '
             'set_global_flag = '+NS+'_finished')
    events = [event(number, actor, body) for number, actor, body in
              ((1, 'GER', first), (2, 'GER', second), (3, 'GER', third), (4, 'NEP', fourth),
               (5, 'GER', fifth), (6, 'GER', sixth), (7, 'GER', seventh), (8, 'NEP', eighth), (9, 'GER', ninth))]
    start = ('set_global_flag = '+NS+'_booted set_variable = { global.'+NS+'_passes = 0 } set_variable = { global.'+NS+'_fails = 0 } '
             'log = "'+MARKER+' STARTUP final_resource_rights" GER = { '+queue(1, 1)+' } ')
    if after_rights:
        startup = 'on_actions = { on_daily = { effect = { if = { limit = { tag = GER has_global_flag = eon_private_uranium_rights_finished NOT = { has_global_flag = '+NS+'_booted } } '+start+' } } } }'
    else:
        startup = 'on_actions = { on_startup = { effect = { if = { limit = { NOT = { has_global_flag = '+NS+'_booted } } '+start+' } } } }'
    fixture = {'events/'+NS+'_events.txt': 'add_namespace = '+NS+'\n\n'+'\n\n'.join(events),
               'common/on_actions/'+NS+'_on_actions.txt': startup}
    output.mkdir(parents=True, exist_ok=True)
    for rel, body in fixture.items():
        parser.ast(body)
        path = output/'mod'/rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((body.replace('\r\n', '\n').replace('\n', '\r\n')+'\r\n').encode('utf-8'))
    dependencies = ['common/resources/00_resources.txt', 'common/scripted_effects/eon_uranium_effects.txt',
                    'common/scripted_triggers/eon_uranium_triggers.txt',
                    'common/scripted_effects/00_count_resource_rights_resources.txt', 'history/states/45-Berlin.txt']
    docs = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation')
    manifest = {'schema': 1, 'kind': 'native_final_uranium_resource_rights', 'marker': MARKER,
                'source_root': str(source), 'fixture_root': str(output), 'preparation_only': preparation_only,
                'expected_native_start_tag': start_tag, 'expected_enabled_mods': ['mod/era_of_nations.mod'],
                'after_rights': after_rights,
                'assertions': assertions, 'observation_labels': observations, 'observation_fields': fields,
                'expected_observation_frames': frames, 'minimum_total_native_hours': 50,
                'source_sha256': {rel: sha(source/rel) for rel in dependencies},
                'fixture_sha256': {rel: sha(output/'mod'/rel) for rel in fixture}, 'builder_sha256': sha(Path(__file__)),
                'installed_documentation_root': str(docs),
                'installed_documentation_sha256': {rel: sha(docs/rel) for rel in ('dynamic_variables_documentation.md', 'effects_documentation.md', 'triggers_documentation.md')},
                'source_export_binding': None if not export_receipt else {'path': str(export_receipt.resolve()), 'sha256': sha(export_receipt)},
                'limits': ['Separate ordered native ROOT-country events invoke the actual public weekly helper.',
                           'Final reserve is observed native state output times100, avoiding a guessed extraction multiplier.',
                           'Private country/state hold flags prevent automatic weekly settlement during cache waits.',
                           'No claim about global unsold-export mass, human GUI, full calendar, save/load or multiplayer.']}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return manifest


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source-root', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--export-receipt', type=Path)
    cli.add_argument('--prepare-only', action='store_true')
    cli.add_argument('--start-tag', default='NEP')
    cli.add_argument('--after-rights', action='store_true')
    args = cli.parse_args()
    manifest = build(args.source_root, args.output, args.export_receipt, args.prepare_only, args.start_tag, args.after_rights)
    print(json.dumps({'final_rights_fixture_prepared': True, 'assertions': len(manifest['assertions']),
                      'observations': len(manifest['observation_labels']), 'native_behavior_tested': False}))


if __name__ == '__main__': main()
