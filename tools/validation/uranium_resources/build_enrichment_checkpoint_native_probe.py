"""Prepare five staged native enrichment events with exact source callbacks."""
from pathlib import Path
import argparse
import json

from build_native_probe import ROOT, load_parser, sha
from build_core_native_probe import canonical, render

NS = 'eon_private_uranium_enrichment'
MARKER = 'EON_PRIVATE_URANIUM_ENRICHMENT'


def build(source, output, export_receipt=None, preparation_only=False, start_tag='NEP', start_delay_hours=30):
    source, output = source.resolve(), output.resolve()
    assert source.is_dir() and output != source
    assert not (output/'manifest.json').exists() and not (output/'launch-receipt.json').exists()
    if not preparation_only:
        assert source != ROOT.resolve() and source not in output.parents
        assert export_receipt and export_receipt.is_file()
    parser = load_parser()
    aliases, bindings, dependencies, assertions, observations, checkpoints = [], [], {}, [], [], []

    def hook(rel, selector, name):
        raw = (source/rel).read_bytes()
        dependencies[rel] = sha(source/rel)
        nodes = parser.ast(raw)
        for part in selector: nodes = parser.one(nodes, part)
        alias = NS+'_'+name
        aliases.append((alias, '=', nodes))
        bindings.append({'source_path': rel, 'selector': selector, 'alias': alias,
                         'source_ast_sha256': canonical(nodes)})
        return alias+' = yes '

    gui = 'common/scripted_guis/01_energy_gui.txt'
    click3 = hook(gui, ['scripted_gui', 'energy_scripted_gui', 'effects', 'build_enrichment_facility_button_shift_click'], 'gui_triple')
    click1 = hook(gui, ['scripted_gui', 'energy_scripted_gui', 'effects', 'build_enrichment_facility_button_click'], 'gui_single')
    generic = 'common/decisions/generic.txt'
    timeout = hook(generic, ['GENERIC_economic_category', 'energy_building_enrichment_facilities', 'timeout_effect'], 'mission_timeout')
    cancel = hook(generic, ['GENERIC_economic_category', 'energy_building_enrichment_facilities', 'complete_effect'], 'mission_cancel')
    for rel in ('common/scripted_effects/eon_uranium_effects.txt', 'common/scripted_triggers/eon_uranium_triggers.txt',
                'common/scripted_effects/!_energy_effects.txt', 'common/scripted_effects/00_missiles_scripted_effects.txt',
                'common/scripted_effects/00_money_system.txt', 'common/resources/00_resources.txt'):
        dependencies[rel] = sha(source/rel)

    def cv(var, value, compare='equals'):
        return 'check_variable = { var = '+var+' value = '+str(value)+' compare = '+compare+' } '

    def check(label, predicate):
        assertions.append(label)
        return ('if = { limit = { '+predicate+' } add_to_variable = { global.'+NS+'_passes = 1 } '
                'log = "'+MARKER+' PASS '+label+'" } else = { add_to_variable = { global.'+NS+'_fails = 1 } '
                'log = "'+MARKER+' FAIL '+label+'" } ')

    def step(label, body):
        checkpoints.append(label)
        return ('log = "'+MARKER+' CHECKPOINT BEFORE '+label+' ROOT=[ROOT.GetTag] THIS=[THIS.GetTag]" '+body+
                'log = "'+MARKER+' CHECKPOINT AFTER '+label+' ROOT=[ROOT.GetTag] THIS=[THIS.GetTag]" ')

    fields = {'treasury': 'treasury', 'facilities': 'enrichment_facilities',
              'count': 'eon_enrichment_project_count', 'escrow': 'eon_enrichment_project_escrow',
              'timer': 'enrichment_facility_time', 'paid': NS+'_paid', 'active': NS+'_active',
              'allowed_no_active': NS+'_allowed_no_active', 'allowed_yes_active': NS+'_allowed_yes_active',
              'money_delta': NS+'_money_delta'}

    def observe(label):
        observations.append(label)
        booleans = {NS+'_paid': 'has_country_flag = eon_enrichment_project_paid',
                    NS+'_active': 'has_active_mission = energy_building_enrichment_facilities',
                    NS+'_allowed_no_active': 'has_active_mission = '+NS+'_allowed_no',
                    NS+'_allowed_yes_active': 'has_active_mission = '+NS+'_allowed_yes'}
        snapshot = ''.join('set_variable = { '+name+' = 0 } if = { limit = { '+predicate+' } set_variable = { '+name+' = 1 } } '
                           for name, predicate in booleans.items())
        return snapshot+'log = "'+MARKER+' OBS '+label+' ROOT=[ROOT.GetTag] THIS=[THIS.GetTag] '+ ' '.join(k+'=[?'+v+']' for k, v in fields.items())+'" '

    def measure(body, charge=False):
        before = NS+'_treasury_before'
        return ('set_variable = { '+before+' = treasury } '+body+
                'set_variable = { '+NS+'_money_delta = '+(''+before if charge else 'treasury')+' } '
                'subtract_from_variable = { '+NS+'_money_delta = '+('treasury' if charge else before)+' } ')

    def queue(number):
        return 'country_event = { id = '+NS+'.'+str(number)+' hours = 2 } '

    def remove():
        return 'if = { limit = { has_active_mission = energy_building_enrichment_facilities } remove_mission = energy_building_enrichment_facilities } '

    def event(number, body):
        frame = 'tag = GER ROOT = { tag = GER }'
        return ('country_event = { id = '+NS+'.'+str(number)+' hidden = yes is_triggered_only = yes immediate = { '
                'if = { limit = { NOT = { has_global_flag = '+NS+'_event_'+str(number)+' } } '
                'set_global_flag = '+NS+'_event_'+str(number)+' '+check('frame_'+str(number), frame)+
                'if = { limit = { '+frame+' } '+body+' } else = { log = "'+MARKER+' ABORT wrong_frame" } '
                '} else = { log = "'+MARKER+' DUPLICATE_EVENT '+str(number)+'" } } }')

    active = 'has_active_mission = energy_building_enrichment_facilities '
    inactive = 'NOT = { '+active+'} '
    paid = 'has_country_flag = eon_enrichment_project_paid '
    unpaid = 'NOT = { '+paid+'} '
    first = (step('initialize', 'eon_uranium_initialize = yes ')+
             step('initial_guarded_remove', remove())+
             step('set_technology', 'set_technology = { nuclear_technology = 1 } ')+
             step('register_enrichment_array', 'if = { limit = { NOT = { is_in_array = { global.enrichment_countries = THIS.id } } } add_to_array = { global.enrichment_countries = THIS.id } } ')+
             step('set_fixture_counts', 'clr_country_flag = eon_enrichment_project_paid set_variable = { enrichment_facilities = 0 } '
                  'set_variable = { industrial_complex_total = 200 } set_variable = { treasury = 100 } ')+
             step('activate_private_loadtime_controls',
                  'activate_mission = '+NS+'_allowed_no activate_mission = '+NS+'_allowed_yes ')+
             observe('before_triple')+step('actual_gui_triple', measure(click3, charge=True))+observe('after_triple_call')+
             check('triple_immediate_charge_exactly75', cv(NS+'_money_delta', 75))+queue(2))
    second = (observe('triple_after_native_wait')+
              check('triple_paid_project_kept_after_native_wait', cv('eon_enrichment_project_count', 3)+cv('eon_enrichment_project_escrow', 75)+cv('enrichment_facilities', 0)+paid)+
              check('triple_native_mission_active_after_wait', active)+
              check('private_allowed_yes_native_mission_registered', 'has_active_mission = '+NS+'_allowed_yes ')+
              step('actual_timeout_twice', measure(timeout+timeout))+observe('after_timeout')+
              check('timeout_completed_once_without_second_payment', cv('enrichment_facilities', 3)+cv(NS+'_money_delta', 0)+unpaid)+
              step('guarded_remove_after_timeout', remove())+queue(3))
    third = (check('removed_first_mission_before_new_activation', inactive)+
             step('set_single_fixture_counts', 'set_variable = { industrial_complex_total = 200 } set_variable = { treasury = 100 } ')+
             step('actual_gui_single', measure(click1, charge=True))+observe('after_single_call')+
             check('single_immediate_charge_exactly25', cv(NS+'_money_delta', 25))+queue(4))
    fourth = (observe('single_after_native_wait')+
              check('single_paid_project_kept_after_native_wait', cv('eon_enrichment_project_count', 1)+cv('eon_enrichment_project_escrow', 25)+cv('enrichment_facilities', 3)+paid)+
              check('single_native_mission_active_after_wait', active)+
              step('actual_cancel_twice_and_stale_timeout', measure(cancel+cancel+timeout))+observe('after_cancel')+
              check('cancel_refunded_exactly25_once_and_stale_timeout_cannot_build', cv(NS+'_money_delta', 25)+cv('enrichment_facilities', 3)+unpaid)+
              'set_variable = { '+NS+'_after_cancel_treasury = treasury } '+
              step('guarded_remove_after_cancel', remove())+queue(5))
    fifth = (observe('final')+check('final_native_mission_removed_and_no_unpaid_build', inactive+unpaid+cv('enrichment_facilities', 3))+
             'log = "'+MARKER+' END passes=[?global.'+NS+'_passes] fails=[?global.'+NS+'_fails]" set_global_flag = '+NS+'_finished')
    events = [event(index, body) for index, body in enumerate((first, second, third, fourth, fifth), 1)]
    mission = parser.one(parser.one(parser.ast((source/generic).read_bytes()), 'GENERIC_economic_category'), 'energy_building_enrichment_facilities')
    controls = []
    for allowed in ('no', 'yes'):
        replacement = {'allowed': parser.ast('always = '+allowed)}
        control = [(key, op, replacement.get(key, value)) for key, op, value in mission]
        control += parser.ast('activation = { always = no } ai_will_do = { factor = 0 }')
        controls.append((NS+'_allowed_'+allowed, '=', control))
    fixture = {'common/scripted_effects/'+NS+'_effects.txt': render(aliases),
               'common/decisions/'+NS+'_loadtime_controls.txt': render([('GENERIC_economic_category', '=', controls)]),
               'events/'+NS+'_events.txt': 'add_namespace = '+NS+'\n\n'+'\n\n'.join(events),
               'common/on_actions/'+NS+'_on_actions.txt':
               'on_actions = { on_startup = { effect = { if = { limit = { NOT = { has_global_flag = '+NS+'_booted } } '
               'set_global_flag = '+NS+'_booted set_variable = { global.'+NS+'_passes = 0 } set_variable = { global.'+NS+'_fails = 0 } '
               'log = "'+MARKER+' STARTUP staged_enrichment" '
               'NEP = { set_country_flag = { flag = eon_uranium_import_attempted days = 30 value = 1 } } '
               'GER = { set_country_flag = { flag = eon_uranium_import_attempted days = 30 value = 1 } '
               'country_event = { id = '+NS+'.1 hours = '+str(start_delay_hours)+' } } } } } }'}
    output.mkdir(parents=True, exist_ok=True)
    for rel, body in fixture.items():
        parser.ast(body)
        path = output/'mod'/rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((body.replace('\r\n', '\n').replace('\n', '\r\n')+'\r\n').encode('utf-8'))
    docs = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation')
    manifest = {'schema': 1, 'kind': 'native_staged_uranium_enrichment', 'marker': MARKER, 'enrichment_evidence_version': 2,
                'source_root': str(source), 'fixture_root': str(output), 'preparation_only': preparation_only,
                'expected_native_start_tag': start_tag, 'expected_enabled_mods': ['mod/era_of_nations.mod'],
                'assertions': assertions, 'observation_labels': observations, 'observation_fields': fields,
                'checkpoints': checkpoints, 'minimum_total_native_hours': 4,
                'loadtime_control_source_ast_sha256': canonical(mission),
                'loadtime_control_overrides': ['allowed=yes/no', 'activation.always=no', 'ai_will_do.factor=0'],
                'source_sha256': dependencies, 'callback_bindings': bindings,
                'fixture_sha256': {rel: sha(output/'mod'/rel) for rel in fixture}, 'builder_sha256': sha(Path(__file__)),
                'installed_documentation_root': str(docs),
                'installed_documentation_sha256': {rel: sha(docs/rel) for rel in ('dynamic_variables_documentation.md', 'effects_documentation.md', 'triggers_documentation.md')},
                'source_export_binding': None if not export_receipt else {'path': str(export_receipt.resolve()), 'sha256': sha(export_receipt)},
                'limits': ['Five separate native events with before/after fault-isolation markers.',
                           'Exact GUI/mission source callbacks; guarded removal only when native mission active.',
                           'Real native waits separate activation, removal and next activation; no mission calendar acceleration.',
                           'Private load-time clones differ only in allowed; activation and AI selection disabled in both.',
                           'Callback costs/refunds measured within one native event; unrelated inter-event treasury changes recorded separately.',
                           'No physical mine/trade proof, human click, full730/1095-day completion, save/load or multiplayer.']}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return manifest


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source-root', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--export-receipt', type=Path)
    cli.add_argument('--prepare-only', action='store_true')
    cli.add_argument('--start-tag', default='NEP')
    cli.add_argument('--start-delay-hours', type=int, default=30)
    args = cli.parse_args()
    assert args.start_delay_hours >= 1
    manifest = build(args.source_root, args.output, args.export_receipt, args.prepare_only, args.start_tag, args.start_delay_hours)
    print(json.dumps({'enrichment_checkpoint_fixture_prepared': True, 'assertions': len(manifest['assertions']),
                      'observations': len(manifest['observation_labels']), 'checkpoints': len(manifest['checkpoints']),
                      'native_behavior_tested': False}))


if __name__ == '__main__': main()
