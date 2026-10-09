"""Prepare native activation/scoping controls; do not emulate a player decision click."""
from pathlib import Path
import argparse
import json

from build_native_probe import ROOT, load_parser, sha
from build_core_native_probe import canonical, render

NS = 'eon_private_uranium_state_activation'
MARKER = 'EON_PRIVATE_URANIUM_STATE_ACTIVATION'


def build(source, output, export_receipt=None, preparation_only=False, start_tag='NEP', start_delay_hours=30, after_enrichment=False):
    source, output = source.resolve(), output.resolve()
    assert source.is_dir() and output != source and not (output/'manifest.json').exists()
    assert not (output/'launch-receipt.json').exists()
    if not preparation_only:
        assert source != ROOT.resolve() and source not in output.parents
        assert export_receipt and export_receipt.is_file()
    parser = load_parser()
    rel = 'common/decisions/eon_uranium_decisions.txt'
    original = parser.one(parser.one(parser.ast((source/rel).read_bytes()), 'eon_uranium_category'), 'eon_uranium_expand_mine')
    state_target=parser.one(original,'state_target')
    assert state_target == 'any_owned_state', 'Native production selector must enumerate owned states'
    bindings, aliases = [], []
    for callback, suffix in (('complete_effect', 'begin'), ('remove_effect', 'complete')):
        body = parser.one(original, callback)
        bindings.append({'source_path': rel, 'selector': ['eon_uranium_category', 'eon_uranium_expand_mine', callback],
                         'alias': NS+'_'+suffix, 'source_ast_sha256': canonical(body)})
        aliases.append((NS+'_'+suffix, '=', body))
    assertions = []

    def check(label, predicate):
        assertions.append(label)
        return ('if = { limit = { '+predicate+' } add_to_variable = { global.'+NS+'_passes = 1 } '
                'log = "'+MARKER+' PASS '+label+'" } else = { add_to_variable = { global.'+NS+'_fails = 1 } '
                'log = "'+MARKER+' FAIL '+label+'" } ')

    def cv(var, value): return 'check_variable = { var = '+var+' value = '+str(value)+' compare = equals } '

    frame = 'tag = GER ROOT = { tag = GER } FROM = { state = 44 } '
    ordinary_start = ('log = "'+MARKER+' CALLBACK ordinary_begin" set_global_flag = '+NS+'_ordinary_complete_called '+
                      check('ordinary_complete_native_FROM_state44', frame)+
                      'set_variable = { '+NS+'_treasury_before = treasury } '+NS+'_begin = yes '+
                      'set_temp_variable = { '+NS+'_charge = '+NS+'_treasury_before } '
                      'subtract_from_temp_variable = { '+NS+'_charge = treasury } '+
                      check('ordinary_source_begin_deducts_exactly025',cv(NS+'_charge',.25)+'FROM = { has_state_flag = eon_uranium_mine_project } ')+
                      'country_event = { id = '+NS+'.2 hours = 32 } ')
    ordinary_end = ('log = "'+MARKER+' CALLBACK ordinary_remove" set_global_flag = '+NS+'_ordinary_remove_called '+
                    check('ordinary_remove_native_FROM_state44', frame)+
                    'set_variable = { '+NS+'_treasury_before = treasury } '+NS+'_complete = yes '+
                    'set_temp_variable = { '+NS+'_charge = '+NS+'_treasury_before } subtract_from_temp_variable = { '+NS+'_charge = treasury } '+
                    check('ordinary_source_remove_has_no_second_charge',cv(NS+'_charge',0))+
                    check('ordinary_source_remove_geometric_expansion','FROM = { '+cv('eon_uranium_capacity',7.5)+'NOT = { has_state_flag = eon_uranium_mine_project } } ')+
                    'clr_country_flag = '+NS+'_ordinary_armed FROM = { clr_state_flag = '+NS+'_ordinary_armed } ')
    replacement = {'days_remove': '1', 'ai_will_do': parser.ast('factor = 1000'),
                   'target_root_trigger': parser.ast('tag = GER has_country_flag = '+NS+'_ordinary_armed'),
                   'target_trigger': parser.ast('FROM = { state = 44 has_state_flag = '+NS+'_ordinary_armed }'),
                   'complete_effect': parser.ast(ordinary_start), 'remove_effect': parser.ast(ordinary_end)}
    ordinary = [(key, op, replacement.get(key, value)) for key, op, value in original]
    # A mission provides an actual native target FROM on timeout. The exact
    # source callbacks execute in that frame. Their contiguous execution here
    # tests native scopes/accounting, not a real construction calendar.
    timed_callback = ('log = "'+MARKER+' CALLBACK timed_timeout" set_global_flag = '+NS+'_timed_callback_called '+
                      check('timed_native_FROM_state44', frame)+
                      'set_variable = { '+NS+'_treasury_before = treasury } '+NS+'_begin = yes '+
                      'set_temp_variable = { '+NS+'_charge = '+NS+'_treasury_before } '
                      'subtract_from_temp_variable = { '+NS+'_charge = treasury } '+
                      check('timed_source_begin_deducts_exactly025', cv(NS+'_charge', .25)+'FROM = { has_state_flag = eon_uranium_mine_project } ')+
                      NS+'_complete = yes '+NS+'_complete = yes '+
                      check('timed_source_complete_geometric_once', 'FROM = { '+cv('eon_uranium_capacity', 7.5)+'NOT = { has_state_flag = eon_uranium_mine_project } } ')+
                      'set_temp_variable = { '+NS+'_charge = '+NS+'_treasury_before } subtract_from_temp_variable = { '+NS+'_charge = treasury } '+
                      check('timed_source_complete_no_second_charge', cv(NS+'_charge', .25))+
                      'clr_country_flag = '+NS+'_timed_armed FROM = { clr_state_flag = '+NS+'_timed_armed } ')
    mission = parser.ast('icon = generic_prospect_for_resources state_target = '+state_target+' '
                         'allowed = { always = yes } activation = { always = no } visible = { always = yes } '
                         'available = { always = no } target_root_trigger = { tag = GER has_country_flag = '+NS+'_timed_armed } '
                         'target_trigger = { FROM = { state = 44 has_state_flag = '+NS+'_timed_armed } } days_mission_timeout = 1 '
                         'ai_will_do = { factor = 0 } timeout_effect = { '+timed_callback+' }')
    observation_fields = {'treasury': 'treasury', 'capacity': 'global.'+NS+'_capacity',
                          'ordinary_complete': 'global.'+NS+'_ordinary_complete', 'ordinary_remove': 'global.'+NS+'_ordinary_remove',
                          'timed_callback': 'global.'+NS+'_timed_callback'}
    observations = []

    def observe(label):
        observations.append(label)
        booleans = ''.join('set_variable = { global.'+NS+'_'+suffix+' = 0 } if = { limit = { has_global_flag = '+NS+'_'+flag+' } '
                           'set_variable = { global.'+NS+'_'+suffix+' = 1 } } '
                           for suffix, flag in (('ordinary_complete', 'ordinary_complete_called'), ('ordinary_remove', 'ordinary_remove_called'), ('timed_callback', 'timed_callback_called')))
        return ('44 = { set_variable = { global.'+NS+'_capacity = eon_uranium_capacity } } '+booleans+
                'log = "'+MARKER+' OBS '+label+' ROOT=[ROOT.GetTag] THIS=[THIS.GetTag] '+
                ' '.join(k+'=[?'+v+']' for k, v in observation_fields.items())+'" ')

    def event(number, body):
        return ('country_event = { id = '+NS+'.'+str(number)+' hidden = yes is_triggered_only = yes immediate = { '
                'if = { limit = { NOT = { has_global_flag = '+NS+'_event_'+str(number)+' } } set_global_flag = '+NS+'_event_'+str(number)+' '
                +body+' } else = { log = "'+MARKER+' DUPLICATE_EVENT '+str(number)+'" } } }')

    first = (check('event1_GER_owns_state44', 'tag = GER ROOT = { tag = GER } 44 = { is_owned_by = GER is_controlled_by = GER } ')+
             check('no_native_callback_before_state_fixture_arm', 'NOT = { has_global_flag = '+NS+'_ordinary_complete_called } NOT = { has_global_flag = '+NS+'_ordinary_remove_called } NOT = { has_global_flag = '+NS+'_timed_callback_called } ')+
             'set_variable = { treasury = 10 } 44 = { clr_state_flag = eon_uranium_mine_project '
             'set_variable = { eon_uranium_reserve_kg = 2000000 } set_variable = { eon_uranium_capacity = 5 } '
             'set_variable = { eon_uranium_capacity_limit = 20 } } '+observe('before_ordinary_activation')+
             'set_country_flag = '+NS+'_ordinary_armed 44 = { set_state_flag = '+NS+'_ordinary_armed } '
             'log = "'+MARKER+' ARMED ordinary_native_AI_selection" '+
             'country_event = { id = '+NS+'.4 hours = 96 } ')
    second = (observe('after_ordinary_activation_wait')+
              check('ordinary_native_AI_selected_source_begin', 'has_global_flag = '+NS+'_ordinary_complete_called ')+
              check('ordinary_native_AI_selected_source_remove_after_one_day', 'has_global_flag = '+NS+'_ordinary_remove_called ')+
              'clr_country_flag = '+NS+'_ordinary_armed 44 = { clr_state_flag = '+NS+'_ordinary_armed } '
              'set_variable = { treasury = 10 } 44 = { clr_state_flag = eon_uranium_mine_project set_variable = { eon_uranium_capacity = 5 } } '
              'set_country_flag = '+NS+'_timed_armed 44 = { set_state_flag = '+NS+'_timed_armed } '
              'log = "'+MARKER+' ARMED timed_native_FROM_control" '
              'activate_targeted_decision = { target = 44 decision = '+NS+'_timed } '+
              # A one-day timed mission may process its callback on the next
              # country decision update after the counter reaches zero.
              'country_event = { id = '+NS+'.3 hours = 64 } ')
    third = (observe('after_native_timeout_wait')+
             check('timed_native_callback_fired', 'has_global_flag = '+NS+'_timed_callback_called ')+
             'clr_country_flag = '+NS+'_timed_armed 44 = { clr_state_flag = '+NS+'_timed_armed } '
             'log = "'+MARKER+' END passes=[?global.'+NS+'_passes] fails=[?global.'+NS+'_fails]" set_global_flag = '+NS+'_finished ')
    deadline = ('if = { limit = { NOT = { has_global_flag = '+NS+'_ordinary_complete_called } NOT = { has_global_flag = '+NS+'_finished } } '
                'clr_country_flag = '+NS+'_ordinary_armed 44 = { clr_state_flag = '+NS+'_ordinary_armed } '
                'log = "'+MARKER+' ABORT native_AI_selection_deadline96h" '
                'set_global_flag = '+NS+'_finished } ')
    startup_body = ('set_global_flag = '+NS+'_booted set_variable = { global.'+NS+'_passes = 0 } set_variable = { global.'+NS+'_fails = 0 } log = "'+MARKER+' STARTUP native_state_activation" '
                    'GER = { country_event = { id = '+NS+'.1 hours = '+str(1 if after_enrichment else start_delay_hours)+' } } ')
    condition = 'NOT = { has_global_flag = '+NS+'_booted } '
    if after_enrichment: condition += 'tag = GER has_global_flag = eon_private_uranium_enrichment_finished '
    startup = 'on_actions = { '+('on_daily' if after_enrichment else 'on_startup')+' = { effect = { if = { limit = { '+condition+' } '+startup_body+' } } } }'
    fixture = {'common/scripted_effects/'+NS+'_effects.txt': render(aliases),
               'common/decisions/categories/'+NS+'_categories.txt': NS+'_category = { allowed = { always = yes } visible = { tag = GER } }',
               'common/decisions/'+NS+'_decisions.txt': render([(NS+'_category', '=', [(NS+'_ordinary', '=', ordinary), (NS+'_timed', '=', mission)])]),
               'events/'+NS+'_events.txt': 'add_namespace = '+NS+'\n\n'+'\n\n'.join(event(n, body) for n, body in enumerate((first, second, third,deadline), 1)),
               'common/on_actions/'+NS+'_on_actions.txt': startup}
    output.mkdir(parents=True, exist_ok=True)
    for path, body in fixture.items():
        parser.ast(body)
        target = output/'mod'/path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((body.replace('\r\n', '\n').replace('\n', '\r\n')+'\r\n').encode('utf-8'))
    dependencies = (rel, 'common/scripted_effects/eon_uranium_effects.txt', 'common/scripted_triggers/eon_uranium_triggers.txt',
                    'common/resources/00_resources.txt', 'history/states/44-Sachsen.txt')
    assert all((source/path).is_file() for path in dependencies)
    docs = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation')
    manifest = {'schema': 1, 'kind': 'native_uranium_state_activation_control', 'marker': MARKER,'state_evidence_version':5,
                'source_root': str(source), 'fixture_root': str(output), 'preparation_only': preparation_only,
                'expected_native_start_tag': start_tag, 'expected_enabled_mods': ['mod/era_of_nations.mod'],
                'assertions': assertions, 'after_enrichment': after_enrichment,
                'observation_labels': observations, 'observation_fields': observation_fields,
                'minimum_total_native_hours': 92, 'callback_bindings': bindings,
                'timed_native_timeout_observation_delay_hours':64,'minimum_timed_timeout_observation_hours':60,
                'private_ordinary_source_ast_sha256': canonical(original),
                'state_target_selector_binding':{'source_path':rel,'selector':['eon_uranium_category','eon_uranium_expand_mine','state_target'],
                                                 'value':state_target,'source_ast_sha256':canonical(state_target)},
                'private_ordinary_fixture_ast_sha256':canonical(ordinary),'private_timed_fixture_ast_sha256':canonical(mission),
                'source_sha256': {path: sha(source/path) for path in dependencies},
                'fixture_sha256': {path: sha(output/'mod'/path) for path in fixture}, 'builder_sha256': sha(Path(__file__)),
                'installed_documentation_root': str(docs),
                'installed_documentation_sha256': {path: sha(docs/path) for path in ('dynamic_variables_documentation.md', 'effects_documentation.md', 'triggers_documentation.md')},
                'source_export_binding': None if not export_receipt else {'path': str(export_receipt.resolve()), 'sha256': sha(export_receipt)},
                'limits': ['A private ordinary state decision is selected by native AI (weight1000), with exact source complete/remove callbacks and one-day private timer.',
                           'Private one-day mission executes exact production mine callbacks in native ROOT/FROM target-state frame.',
                           'Begin and completion are contiguous in that timeout control; no full production construction calendar, human GUI, save/load or multiplayer.']}
    manifest['optional_callback_assertions'] = [label for label in assertions if label.startswith('ordinary_') or label.startswith('timed_source_') or label == 'timed_native_FROM_state44']
    manifest['optional_callback_assertions'] = [label for label in manifest['optional_callback_assertions'] if label not in ('ordinary_native_AI_selected_source_begin','ordinary_native_AI_selected_source_remove_after_one_day')]
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
    cli.add_argument('--after-enrichment', action='store_true')
    args = cli.parse_args()
    result = build(args.source_root, args.output, args.export_receipt, args.prepare_only, args.start_tag, args.start_delay_hours, args.after_enrichment)
    print(json.dumps({'state_activation_control_prepared': True, 'assertions': len(result['assertions']), 'native_game_behavior_tested': False}))


if __name__ == '__main__': main()
