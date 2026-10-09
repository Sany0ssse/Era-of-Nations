"""Prepare source-bound native material/project fixtures; never launch HOI4.

The private mining decision keeps production FROM/ROOT scopes and callbacks.
Only its clock is accelerated to one day and its AI selection is disabled.
GUI and enrichment mission callbacks are copied as exact parsed AST bodies.
"""
from copy import deepcopy
from pathlib import Path
import argparse
import hashlib
import json
import re

from build_native_probe import ROOT, load_parser, sha

NS = 'eon_private_uranium_core'
MARKER = 'EON_PRIVATE_URANIUM_CORE'


def canonical(nodes):
    return hashlib.sha256(json.dumps(nodes, separators=(',', ':')).encode()).hexdigest()


def render(nodes):
    def scalar(value):
        if re.search(r'\s|[{}#"]', value):
            return '"'+value.replace('\\', '\\\\').replace('"', '\\"')+'"'
        return value
    result = []
    for key, operator, value in nodes:
        if key == '__item__':
            result.append(scalar(value))
        else:
            result.append(key+' '+operator+' '+(' { '+render(value)+' } ' if isinstance(value, list) else scalar(value)))
    return '\n'.join(result)


def build(source, output, export_receipt=None, preparation_only=False, start_tag='NEP', materials_only=False, after_enrichment=False):
    source, output = source.resolve(), output.resolve()
    assert source.is_dir() and output != source
    assert not (output/'manifest.json').exists() and not (output/'launch-receipt.json').exists()
    if not preparation_only:
        assert source != ROOT.resolve() and source not in output.parents
        assert export_receipt and export_receipt.is_file()
    parser = load_parser()
    dependencies, bindings, aliases, labels, observations = {}, [], [], [], []

    def hook(rel, selector, alias=None):
        raw = (source/rel).read_bytes()
        dependencies[rel] = hashlib.sha256(raw).hexdigest()
        nodes = parser.ast(raw)
        for part in selector:
            nodes = parser.one(nodes, part)
        if alias:
            name = NS+'_'+alias
            bindings.append({'source_path': rel, 'selector': selector,
                             'source_ast_sha256': canonical(nodes), 'alias': name})
            aliases.append((name, '=', nodes))
            return name+' = yes '
        return deepcopy(nodes)

    core = 'common/scripted_effects/eon_uranium_effects.txt'
    for rel in (core, 'common/scripted_triggers/eon_uranium_triggers.txt',
                'common/scripted_effects/eon_uranium_geology.txt',
                'common/scripted_effects/!_energy_effects.txt',
                'common/scripted_effects/00_missiles_scripted_effects.txt',
                'common/scripted_effects/eon_nuclear_fuel_trade_effects.txt',
                'common/scripted_effects/00_money_system.txt',
                'common/resources/00_resources.txt', 'common/on_actions/eon_uranium_on_actions.txt',
                'history/states/45-Berlin.txt'):
        if (source/rel).exists(): dependencies[rel] = sha(source/rel)
    for path in (source/'common/scripted_effects').glob('eon_uranium*.txt'):
        dependencies[path.relative_to(source).as_posix()] = sha(path)
    resources = parser.one(parser.ast((source/'common/resources/00_resources.txt').read_bytes()), 'resources')
    assert [key for key, op, value in resources][-1] == 'uranium' and len(resources) == 7
    gui = 'common/scripted_guis/01_energy_gui.txt'
    click1 = '' if materials_only else hook(gui, ['scripted_gui', 'energy_scripted_gui', 'effects', 'build_enrichment_facility_button_click'], 'gui_single')
    click3 = '' if materials_only else hook(gui, ['scripted_gui', 'energy_scripted_gui', 'effects', 'build_enrichment_facility_button_shift_click'], 'gui_triple')
    generic = 'common/decisions/generic.txt'
    timeout = '' if materials_only else hook(generic, ['GENERIC_economic_category', 'energy_building_enrichment_facilities', 'timeout_effect'], 'mission_timeout')
    cancel = '' if materials_only else hook(generic, ['GENERIC_economic_category', 'energy_building_enrichment_facilities', 'complete_effect'], 'mission_cancel')
    mine_path = 'common/decisions/eon_uranium_decisions.txt'
    mine_nodes = hook(mine_path, ['eon_uranium_category', 'eon_uranium_expand_mine'])
    mine_begin = hook(mine_path, ['eon_uranium_category', 'eon_uranium_expand_mine', 'complete_effect'], 'mine_source_begin')
    mine_complete = hook(mine_path, ['eon_uranium_category', 'eon_uranium_expand_mine', 'remove_effect'], 'mine_source_complete')

    def cv(name, value, compare='equals'):
        return 'check_variable = { var = '+name+' value = '+str(value)+' compare = '+compare+' }'

    def check(label, predicate):
        assert label not in labels
        labels.append(label)
        return ('if = { limit = { '+predicate+' } add_to_variable = { global.'+NS+'_passes = 1 } '
                'log = "'+MARKER+' PASS '+label+'" } else = { add_to_variable = { global.'+NS+'_fails = 1 } '
                'log = "'+MARKER+' FAIL '+label+'" }')

    fields = {'balance': 'resource@uranium', 'produced': 'resource_produced@uranium',
              'imported': 'resource_imported@uranium', 'exported': 'resource_exported@uranium',
              'consumed': 'resource_consumed@uranium', 'raw': 'eon_natural_uranium_stock_kg',
              'fuel': 'var_reactor_material_stockpile', 'tails': 'eon_depleted_uranium_stock_kg',
              'feed': 'eon_uranium_last_feed_kg', 'last_fuel': 'eon_uranium_last_fuel_kg',
              'delivered': 'eon_uranium_last_delivered_kg', 'extracted': 'eon_uranium_last_extracted_kg',
              'capacity': 'eon_enrichment_capacity_kg', 'facilities': 'enrichment_facilities',
              'treasury': 'treasury', 'state_flow': 'global.'+NS+'_state_flow',
              'state_reserve': 'global.'+NS+'_state_reserve', 'state_capacity': 'global.'+NS+'_state_capacity',
              'fraction_before': NS+'_fraction_before', 'fraction_after': NS+'_fraction_after'}

    def observe(label):
        assert label not in observations
        observations.append(label)
        snapshot = ('45 = { set_variable = { global.'+NS+'_state_flow = resource@uranium } '
                    'set_variable = { global.'+NS+'_state_reserve = eon_uranium_reserve_kg } '
                    'set_variable = { global.'+NS+'_state_capacity = eon_uranium_capacity } } ')
        return snapshot+'log = "'+MARKER+' OBS '+label+' ROOT=[ROOT.GetTag] THIS=[THIS.GetTag] '+ ' '.join(k+'=[?'+v+']' for k, v in fields.items())+'"'

    def queue(number, hours):
        return 'country_event = { id = '+NS+'.'+str(number)+' hours = '+str(hours)+' }'

    def reset(raw=0, fuel=0, facilities=1, consumption=0):
        return ('clr_country_flag = eon_uranium_weekly_settled '
                'set_country_flag = eon_uranium_reactor_stock_in_kg '
                'set_country_flag = enabled_nuclear_reactor_fuel_production '
                'set_country_flag = { flag = eon_uranium_import_attempted days = 30 value = 1 } '+
                ' '.join('set_variable = { '+k+' = '+str(v)+' }' for k, v in {
                    'eon_natural_uranium_stock_kg': raw, 'var_reactor_material_stockpile': fuel,
                    'eon_depleted_uranium_stock_kg': 0, 'enrichment_facilities': facilities,
                    'number_of_damaged_enrichment_facilities': 0, 'nuclear_fuel_consumption': consumption}.items()))

    def event(number, body):
        frame = 'tag = GER ROOT = { tag = GER }'
        return ('country_event = { id = '+NS+'.'+str(number)+' hidden = yes is_triggered_only = yes immediate = { '
                'if = { limit = { NOT = { has_global_flag = '+NS+'_event_'+str(number)+' } } '
                'set_global_flag = '+NS+'_event_'+str(number)+' '+check('frame_'+str(number), frame)+
                ' if = { limit = { '+frame+' } '+body+' } else = { log = "'+MARKER+' ABORT wrong_country_frame" } '
                '} else = { log = "'+MARKER+' DUPLICATE_EVENT '+str(number)+'" } } }')

    # Trace around the original state decision callbacks; the source callback
    # bodies themselves remain unmodified and keep native FROM = target state.
    start_wrapper = ('set_variable = { '+NS+'_mine_treasury_before = treasury } '+mine_begin+
                     'set_temp_variable = { '+NS+'_mine_treasury_delta = '+NS+'_mine_treasury_before } '
                     'subtract_from_temp_variable = { '+NS+'_mine_treasury_delta = treasury } ')
    completion_wrapper = ('set_variable = { '+NS+'_mine_treasury_before = treasury } '+mine_complete+
                          'set_temp_variable = { '+NS+'_mine_treasury_delta = treasury } '
                          'subtract_from_temp_variable = { '+NS+'_mine_treasury_delta = '+NS+'_mine_treasury_before } ')
    start_wrapper += ('if = { limit = { '+cv(NS+'_mine_stage', 1)+' } '+
                     check('mine_first_native_FROM_and_upfront_payment', 'FROM = { has_state_flag = eon_uranium_mine_project is_owned_by = ROOT is_controlled_by = ROOT } '+cv(NS+'_mine_treasury_delta', 0.25))+
                     ' } else = { '+check('mine_second_native_FROM_and_upfront_payment', 'FROM = { has_state_flag = eon_uranium_mine_project is_owned_by = ROOT is_controlled_by = ROOT } '+cv(NS+'_mine_treasury_delta', 0.25))+' }')
    completion_wrapper += ('if = { limit = { '+cv(NS+'_mine_stage', 1)+' } '+
                           check('mine_completion_geometric_capacity_no_second_charge', cv(NS+'_mine_treasury_delta', 0)+' FROM = { '+cv('eon_uranium_capacity', 7.5)+' NOT = { has_state_flag = eon_uranium_mine_project } }')+
                           'set_global_flag = '+NS+'_mine_first_completed } else = { '+
                           check('mine_lost_state_refund_and_capacity_preserved', cv(NS+'_mine_treasury_delta', 0.25)+' FROM = { '+cv('eon_uranium_capacity', 5)+' NOT = { has_state_flag = eon_uranium_mine_project } }')+
                           'set_global_flag = '+NS+'_mine_second_completed }')
    aliases.extend([(NS+'_mine_begin_wrapper', '=', parser.ast(start_wrapper)),
                    (NS+'_mine_complete_wrapper', '=', parser.ast(completion_wrapper))])
    mine_replacement = {'days_remove': '1', 'ai_will_do': parser.ast('factor = 0'),
                        'complete_effect': parser.ast(NS+'_mine_begin_wrapper = yes'),
                        'remove_effect': parser.ast(NS+'_mine_complete_wrapper = yes')}
    private_mine = [(key, op, mine_replacement.get(key, value)) for key, op, value in mine_nodes]

    first = ('eon_uranium_initialize = yes '+observe('baseline')+
             check('initial_state_frame', '45 = { is_owned_by = GER is_controlled_by = GER }')+
             check('initial_country_has_no_uranium_flow_or_import', cv('resource@uranium', 0)+' '+cv('resource_imported@uranium', 0))+
             '45 = { set_variable = { '+NS+'_fraction_before = resource@uranium } '
             'add_resource = { type = uranium amount = 0.1 } set_variable = { '+NS+'_fraction_after = resource@uranium } '
             'ROOT = { set_variable = { '+NS+'_fraction_before = PREV.'+NS+'_fraction_before } '
             'set_variable = { '+NS+'_fraction_after = PREV.'+NS+'_fraction_after } } '
             'add_resource = { type = uranium amount = -0.1 } } '+observe('fractional_resource_observation')+
             reset(raw=9000)+'eon_uranium_project_fuel = yes eon_uranium_project_fuel = yes '+
             check('repeated_projection_preserves_raw_and_fuel', cv('eon_natural_uranium_stock_kg', 9000)+' '+cv('var_reactor_material_stockpile', 0))+
             'nuclear_reactor_fuel_consumption = yes '+observe('raw_to_fuel')+
             check('stock_only_conversion_ratio9', cv('eon_natural_uranium_stock_kg', 0)+' '+cv('eon_uranium_last_feed_kg', 9000)+' '+cv('var_reactor_material_stockpile', 1000)+' '+cv('eon_depleted_uranium_stock_kg', 8000))+
             'nuclear_reactor_fuel_consumption = yes '+
             check('native_duplicate_week_does_not_credit_twice', cv('var_reactor_material_stockpile', 1000)+' '+cv('eon_depleted_uranium_stock_kg', 8000))+
             reset(facilities=999)+'nuclear_reactor_fuel_consumption = yes '+
             check('native_no_feed_has_no_fuel_or_tails', cv('var_reactor_material_stockpile', 0)+' '+cv('eon_depleted_uranium_stock_kg', 0))+
             reset(raw=900000, facilities=2)+'nuclear_reactor_fuel_consumption = yes '
             'set_temp_variable = { '+NS+'_conserved = eon_natural_uranium_stock_kg } '
             'add_to_temp_variable = { '+NS+'_conserved = var_reactor_material_stockpile } '
             'add_to_temp_variable = { '+NS+'_conserved = eon_depleted_uranium_stock_kg } '+
             check('native_capacity_processing_conserves_900000kg', cv(NS+'_conserved', 900000)+' '+cv('eon_natural_uranium_stock_kg', 0, 'greater_than'))+
             reset(raw=9000, consumption=1154)+'nuclear_reactor_fuel_consumption = yes '+
             check('reactor_cannot_consume_unavailable_fuel', cv('var_reactor_material_stockpile', 0)+' '+cv('eon_uranium_last_reactor_use_kg', 1000))+
             'remove_mission = energy_building_enrichment_facilities clr_country_flag = eon_enrichment_project_paid '
             'set_technology = { nuclear_technology = 1 } '
             'if = { limit = { NOT = { is_in_array = { global.enrichment_countries = THIS.id } } } add_to_array = { global.enrichment_countries = THIS.id } } '
             'set_variable = { enrichment_facilities = 0 } set_variable = { industrial_complex_total = 200 } set_variable = { treasury = 100 } '+click3+' '+
             check('actual_gui_triple_reserves75_and_starts_mission', cv('treasury', 25)+' '+cv('eon_enrichment_project_count', 3)+' '+cv('enrichment_facilities', 0)+' has_country_flag = eon_enrichment_project_paid has_active_mission = energy_building_enrichment_facilities')+
             click3+' '+check('actual_repeated_gui_cannot_charge_twice', cv('treasury', 25)+' '+cv('eon_enrichment_project_escrow', 75))+
             timeout+' '+timeout+' '+
             check('actual_mission_timeout_completes_once_and_cannot_fall_to_legacy', cv('enrichment_facilities', 3)+' '+cv('treasury', 25)+' NOT = { has_country_flag = eon_enrichment_project_paid }')+
             'remove_mission = energy_building_enrichment_facilities set_variable = { industrial_complex_total = 200 } set_variable = { treasury = 100 } '+click1+' '+
             check('actual_gui_single_reserves25', cv('treasury', 75)+' '+cv('eon_enrichment_project_count', 1))+
             cancel+' '+cancel+' '+timeout+' '+
             check('actual_cancel_and_stale_timeout_refund_once', cv('treasury', 100)+' '+cv('enrichment_facilities', 3)+' NOT = { has_country_flag = eon_enrichment_project_paid }')+
             'remove_mission = energy_building_enrichment_facilities '
             'set_variable = { industrial_complex_total = 40 } set_variable = { treasury = 75 } set_variable = { enrichment_facilities = 1 } '+click3+' '+
             check('actual_gui_triple_rejects_capacity_overshoot', cv('enrichment_facilities', 1)+' '+cv('treasury', 75)+' NOT = { has_country_flag = eon_enrichment_project_paid }')+
             'set_variable = { enrichment_facilities = 0 } set_variable = { treasury = 74.99 } '+click3+' '+
             check('actual_gui_rejects_insufficient_upfront_funds', cv('treasury', 74.99)+' NOT = { has_country_flag = eon_enrichment_project_paid }')+
             reset()+'45 = { clr_state_flag = eon_uranium_state_weekly_settled set_variable = { eon_uranium_reserve_kg = 10000 } set_variable = { eon_uranium_capacity = 20 } '
             'set_variable = { eon_uranium_capacity_limit = 30 } set_variable = { eon_uranium_applied_output = 200 } '
             'add_resource = { type = uranium amount = 200 } } '+queue(2, 6))
    second = (reset()+observe('finite_deposit_before')+'nuclear_reactor_fuel_consumption = yes '+observe('finite_deposit_after')+
              check('native_depletion_clips_to_remaining_10000kg', cv('eon_uranium_last_extracted_kg', 10000)+' 45 = { '+cv('eon_uranium_reserve_kg', 0)+' '+cv('eon_uranium_applied_output', 0)+' }')+
              check('native_depleted_mine_final_delivery_positive_and_finite', cv('eon_uranium_last_delivered_kg', 0, 'greater_than')+' '+cv('eon_uranium_last_delivered_kg', 10000, 'less_than_or_equals'))+
              '45 = { clr_state_flag = eon_uranium_state_weekly_settled set_variable = { eon_uranium_reserve_kg = 180000 } set_variable = { eon_uranium_capacity = 18 } '
              'eon_uranium_refresh_mine = yes set_state_owner_to = CAN set_state_controller_to = GER } '
              'create_import = { resource = uranium amount = 8 exporter = CAN } '+queue(3, 6))
    third = (reset()+'set_variable = { '+NS+'_can_raw_before = CAN.eon_natural_uranium_stock_kg } '
             '45 = { set_variable = { '+NS+'_reserve_before = eon_uranium_reserve_kg } } '+observe('captured_deposit_before')+
             check('native_captured_deposit_frame', '45 = { is_owned_by = CAN is_controlled_by = GER }')+
             check('native_import_8_delivered_to_second_representative_country', cv('resource_imported@uranium', 8, 'greater_than_or_equals'))+
             'nuclear_reactor_fuel_consumption = yes '+observe('captured_deposit_after')+
             '45 = { set_temp_variable = { '+NS+'_reserve_loss = '+NS+'_reserve_before } '
             'subtract_from_temp_variable = { '+NS+'_reserve_loss = eon_uranium_reserve_kg } } '+
             check('native_captured_deposit_conserves_state_reserve', cv('eon_uranium_last_extracted_kg', NS+'_reserve_loss')+' '+cv('eon_uranium_last_delivered_kg', 0, 'greater_than')+' '+cv('CAN.eon_natural_uranium_stock_kg', NS+'_can_raw_before'))+
             '45 = { set_state_owner_to = GER set_state_controller_to = GER set_variable = { eon_uranium_reserve_kg = 2000000 } '
             'set_variable = { eon_uranium_capacity = 5 } set_variable = { eon_uranium_capacity_limit = 15 } eon_uranium_refresh_mine = yes } '
             'set_variable = { treasury = 10 } set_variable = { '+NS+'_mine_stage = 1 } '
             'activate_targeted_decision = { target = 45 decision = '+NS+'_mine } '+queue(4, 32))
    fourth = (check('native_first_accelerated_decision_callback_finished', 'has_global_flag = '+NS+'_mine_first_completed')+
              '45 = { set_variable = { eon_uranium_capacity = 5 } eon_uranium_refresh_mine = yes } '
              'set_variable = { '+NS+'_mine_stage = 2 } set_variable = { treasury = 10 } '
              'activate_targeted_decision = { target = 45 decision = '+NS+'_mine } '
              '45 = { set_state_owner_to = CAN set_state_controller_to = CAN } '+queue(5, 32))
    fifth = (check('native_lost_state_accelerated_decision_callback_finished', 'has_global_flag = '+NS+'_mine_second_completed')+
             '45 = { set_state_owner_to = GER set_state_controller_to = GER set_variable = { eon_uranium_capacity = 0 } eon_uranium_refresh_mine = yes } '+queue(6, 6))
    sixth = (observe('final')+'log = "'+MARKER+' END passes=[?global.'+NS+'_passes] fails=[?global.'+NS+'_fails]" set_global_flag = '+NS+'_finished')
    if materials_only:
        first = first[:first.index('remove_mission = energy_building_enrichment_facilities')]+first[first.rindex(reset()+'45 = {'):]
        labels[:] = [label for label in labels if not label.startswith(('actual_gui_', 'actual_repeated_gui_', 'actual_mission_', 'actual_cancel_'))]
    else:
        # activate_mission is queued by the engine. Observe its active state
        # after a genuine native wait before invoking the source timeout.
        split_at = first.index(click3)+len(click3)
        triple_completion = observe('actual_gui_triple_after_native_wait')+first[split_at:]
        observations.remove('actual_gui_triple_after_native_wait')
        observations.insert(observations.index('raw_to_fuel')+1, 'actual_gui_triple_after_native_wait')
        first = first[:split_at]+queue(7, 2)
    events = [event(index, body) for index, body in enumerate((first, second, third, fourth, fifth, sixth), 1)]
    if not materials_only: events.append(event(7, triple_completion))
    start = ('set_global_flag = '+NS+'_booted set_variable = { global.'+NS+'_passes = 0 } set_variable = { global.'+NS+'_fails = 0 } '
             'log = "'+MARKER+' STARTUP source_bound_core" GER = { '+queue(1, 1)+' } ')
    if after_enrichment:
        startup = 'on_actions = { on_daily = { effect = { if = { limit = { tag = GER has_global_flag = eon_private_uranium_enrichment_finished NOT = { has_global_flag = '+NS+'_booted } } '+start+' } } } }'
    else:
        startup = 'on_actions = { on_startup = { effect = { if = { limit = { NOT = { has_global_flag = '+NS+'_booted } } '+start+' } } } }'
    fixture = {
        'common/scripted_effects/'+NS+'_effects.txt': render(aliases),
        'common/decisions/'+NS+'_decisions.txt': render([(NS+'_category', '=', [(NS+'_mine', '=', private_mine)])]),
        'common/decisions/categories/'+NS+'_categories.txt': NS+'_category = { icon = generic_prospect_for_resources allowed = { always = yes } visible = { tag = GER } }',
        'events/'+NS+'_events.txt': 'add_namespace = '+NS+'\n\n'+'\n\n'.join(events),
        'common/on_actions/'+NS+'_on_actions.txt': startup,
    }
    output.mkdir(parents=True, exist_ok=True)
    for rel, body in fixture.items():
        parser.ast(body)
        path = output/'mod'/rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((body.replace('\r\n', '\n').replace('\n', '\r\n')+'\r\n').encode('utf-8'))
    alias_ast = parser.ast((output/'mod'/'common/scripted_effects'/f'{NS}_effects.txt').read_bytes())
    for binding in bindings:
        assert canonical(parser.one(alias_ast, binding['alias'])) == binding['source_ast_sha256']
    assert all(sha(source/rel) == digest for rel, digest in dependencies.items()), 'Source changed during preparation'
    manifest = {'schema': 1, 'kind': 'native_source_bound_uranium_core', 'marker': MARKER,
                'source_root': str(source), 'fixture_root': str(output), 'preparation_only': preparation_only,
                'expected_native_start_tag': start_tag, 'expected_enabled_mods': ['mod/era_of_nations.mod'],
                'materials_only': materials_only, 'after_enrichment': after_enrichment,
                'assertions': labels, 'observation_labels': observations, 'observation_fields': fields,
                'expected_root': 'GER', 'expected_actor': 'GER', 'minimum_total_native_hours': 72,
                'native_unit_kg_per_week': 100,
                'source_sha256': dependencies, 'callback_bindings': bindings,
                'private_mine_decision_source_ast_sha256': canonical(mine_nodes),
                'private_mine_decision_changes': ['days_remove = 1', 'ai_will_do = 0', 'callback tracing outside exact source bodies'],
                'fixture_sha256': {rel: sha(output/'mod'/rel) for rel in fixture}, 'builder_sha256': sha(Path(__file__)),
                'source_export_binding': None if not export_receipt else {'path': str(export_receipt.resolve()), 'sha256': sha(export_receipt)},
                'limits': ['Controlled stock/resource/state fixtures; not a balanced campaign.',
                           ('Mining callbacks only; native GUI/mission behavior is outside this materials-only family.' if materials_only else
                            'Exact GUI and enrichment mission AST callbacks invoked; no human click or full730/1095-day wait.'),
                           'Mining clock accelerated to one day; production begin/remove effects and native target scopes retained.',
                           'Fractional add_resource support is observed; a zero delta is reported, never silently accepted as fractional proof.',
                           'No save/load, multiplayer or rendered GUI acceptance.']}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return manifest


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source-root', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--export-receipt', type=Path)
    cli.add_argument('--prepare-only', action='store_true')
    cli.add_argument('--start-tag', default='NEP')
    cli.add_argument('--materials-only', action='store_true')
    cli.add_argument('--after-enrichment', action='store_true')
    args = cli.parse_args()
    manifest = build(args.source_root, args.output, args.export_receipt, args.prepare_only, args.start_tag, args.materials_only, args.after_enrichment)
    print(json.dumps({'core_fixture_prepared': True, 'assertions': len(manifest['assertions']),
                      'observations': len(manifest['observation_labels']), 'source_bound_callbacks': len(manifest['callback_bindings']),
                      'manifest': str(args.output/'manifest.json'), 'native_behavior_tested': False}))


if __name__ == '__main__': main()
