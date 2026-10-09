"""Prepare country-mission classification and actual enrichment calendar controls."""
from pathlib import Path
import argparse
import json

from build_native_probe import ROOT, load_parser, sha
from build_core_native_probe import canonical, render

NS = 'eon_private_uranium_mission_calendar'
MARKER = 'EON_PRIVATE_URANIUM_MISSION_CALENDAR'
MISSION = 'energy_building_enrichment_facilities'


def resolve_binding(parser, source, binding):
    body = parser.ast((source/binding['source_path']).read_bytes())
    if binding.get('binding_kind') == 'event_option_effects':
        events = [value for key,op,value in body if key == 'country_event' and parser.one(value,'id') == binding['event_id']]
        assert len(events) == 1
        options = [value for key,op,value in events[0] if key == 'option' and parser.one(value,'name') == binding['option_name']]
        assert len(options) == 1 and binding['excluded_metadata'] == ['name','ai_chance']
        return [entry for entry in options[0] if entry[0] not in binding['excluded_metadata']]
    for key in binding['selector']: body = parser.one(body,key)
    return body


def build(source, output, export_receipt=None, preparation_only=False, start_tag='NEP', start_delay_hours=30):
    source, output = source.resolve(), output.resolve()
    assert source.is_dir() and output != source
    assert not (output/'manifest.json').exists() and not (output/'launch-receipt.json').exists()
    if not preparation_only:
        assert source != ROOT.resolve() and source not in output.parents
        assert export_receipt and export_receipt.is_file()
    p = load_parser()
    bindings, aliases, dependencies = [], [], {}
    def hook(rel, selector, name):
        dependencies[rel] = sha(source/rel)
        body = p.ast((source/rel).read_bytes())
        for key in selector: body = p.one(body, key)
        alias = NS+'_'+name
        bindings.append({'source_path': rel, 'selector': selector, 'alias': alias, 'source_ast_sha256': canonical(body)})
        aliases.append((alias, '=', body))
        return alias+' = yes '
    gui = 'common/scripted_guis/01_energy_gui.txt'
    click3 = hook(gui, ['scripted_gui', 'energy_scripted_gui', 'effects', 'build_enrichment_facility_button_shift_click'], 'triple')
    click1 = hook(gui, ['scripted_gui', 'energy_scripted_gui', 'effects', 'build_enrichment_facility_button_click'], 'single')
    generic = 'common/decisions/generic.txt'
    event_rel = 'events/00_Energy_events.txt'
    dependencies[event_rel] = sha(source/event_rel)
    cancel_binding = {'source_path':event_rel,'binding_kind':'event_option_effects','event_id':'energy.5',
                      'option_name':'energy.5.a','excluded_metadata':['name','ai_chance'],'alias':NS+'_cancel'}
    cancel_body = resolve_binding(p,source,cancel_binding)
    cancel_binding['source_ast_sha256'] = canonical(cancel_body)
    bindings.append(cancel_binding)
    aliases.append((cancel_binding['alias'],'=',cancel_body))
    cancel = cancel_binding['alias']+' = yes '
    timeout = hook(generic, ['GENERIC_economic_category', MISSION, 'timeout_effect'], 'stale_timeout')
    candidate = p.one(p.one(p.ast((source/generic).read_bytes()), 'GENERIC_economic_category'), MISSION)
    assert p.one(candidate, 'days_mission_timeout') == '730', 'This probe binds the literal730 production candidate'
    assert p.one(candidate, 'allowed') == p.ast('always = yes')
    assert p.one(candidate, 'activation') == p.ast('always = no')
    visible_body = p.one(candidate,'visible')
    visible_binding = {'source_path':generic,'selector':['GENERIC_economic_category',MISSION,'visible'],
                       'alias':NS+'_production_visible','source_ast_sha256':canonical(visible_body)}
    for rel in ('common/scripted_effects/eon_uranium_effects.txt', 'common/scripted_triggers/eon_uranium_triggers.txt',
                'common/scripted_effects/!_energy_effects.txt', 'common/scripted_effects/00_money_system.txt',
                'common/resources/00_resources.txt','common/synchronized_dynamic_tokens/eon_uranium_tokens.txt'):
        dependencies[rel] = sha(source/rel)
    controls = []
    for allowed in ('yes', 'no'):
        for clock in ('literal', 'dynamic'):
            ident = NS+'_'+allowed+'_'+clock
            timer = '730' if clock == 'literal' else 'ROOT.'+NS+'_timer'
            body = p.ast('icon = generic_construct_civ_factory allowed = { always = '+allowed+' } '
                         'activation = { always = no } visible = { tag = GER has_country_flag = '+NS+'_armed } '
                         'available = { always = yes } selectable_mission = yes fire_only_once = no '
                         'days_mission_timeout = '+timer+' ai_will_do = { factor = 0 } '
                         'timeout_effect = { log = "'+MARKER+' CONTROL_TIMEOUT '+allowed+'_'+clock+'" '
                         'set_country_flag = '+ident+'_expired }')
            controls.append((ident, '=', body))
    assertions, observations = [], []
    fields = {'treasury': 'treasury', 'facilities': 'enrichment_facilities', 'count': 'eon_enrichment_project_count',
              'escrow': 'eon_enrichment_project_escrow', 'paid': NS+'_paid', 'active': NS+'_active',
              'remaining': 'days_mission_timeout@'+MISSION, 'delta': NS+'_delta',
              'legacy_time':'enrichment_facility_time','single_flag':NS+'_single_flag',
              'triple_flag':NS+'_triple_flag','mission_visible':NS+'_mission_visible',
              'ack_pending':'new_enrichment_country'}
    for ident, op, body in controls:
        suffix = ident.removeprefix(NS+'_')
        fields[suffix+'_active'] = NS+'_'+suffix+'_active'
        fields[suffix+'_remaining'] = 'days_mission_timeout@'+ident
    def cv(var, value, compare='equals'):
        return 'check_variable = { var = '+var+' value = '+str(value)+' compare = '+compare+' } '
    def check(label, predicate):
        assertions.append(label)
        return ('if = { limit = { '+predicate+' } add_to_variable = { global.'+NS+'_passes = 1 } '
                'log = "'+MARKER+' PASS '+label+'" } else = { add_to_variable = { global.'+NS+'_fails = 1 } '
                'log = "'+MARKER+' FAIL '+label+'" } ')
    def observe(label):
        observations.append(label)
        booleans = {NS+'_paid': 'has_country_flag = eon_enrichment_project_paid',
                    NS+'_active': 'has_active_mission = '+MISSION,
                    NS+'_single_flag':'has_country_flag = single_enrichment_facility',
                    NS+'_triple_flag':'has_country_flag = build_three_enrichment_facility',
                    NS+'_mission_visible':visible_binding['alias']+' = yes'}
        for ident, op, body in controls: booleans[ident+'_active'] = 'has_active_mission = '+ident
        return (''.join('set_variable = { '+var+' = 0 } if = { limit = { '+predicate+' } set_variable = { '+var+' = 1 } } '
                        for var, predicate in booleans.items())+
                'log = "'+MARKER+' OBS '+label+' ROOT=[ROOT.GetTag] THIS=[THIS.GetTag] '+
                ' '.join(key+'=[?'+var+']' for key, var in fields.items())+'" ')
    def measure(body, charge=False):
        before = NS+'_before'
        return ('set_variable = { '+before+' = treasury } '+body+'set_variable = { '+NS+'_delta = '+(before if charge else 'treasury')+' } '
                'subtract_from_variable = { '+NS+'_delta = '+('treasury' if charge else before)+' } ')
    def queue(number, hours): return 'country_event = { id = '+NS+'.'+str(number)+' hours = '+str(hours)+' } '
    def remove(ident=MISSION): return 'remove_mission = '+ident+' '
    def adjust(days): return 'add_days_mission_timeout = { mission = '+MISSION+' days = '+str(days)+' } '
    active = 'has_active_mission = '+MISSION+' '
    inactive = 'NOT = { '+active+'} '
    paid = 'has_country_flag = eon_enrichment_project_paid '
    unpaid = 'NOT = { '+paid+'} '
    first = ('eon_uranium_initialize = yes '+remove()+
             'set_technology = { nuclear_technology = 1 } '
             'if = { limit = { NOT = { is_in_array = { global.enrichment_countries = THIS.id } } } add_to_array = { global.enrichment_countries = THIS.id } } '
             'clr_country_flag = eon_enrichment_project_paid clr_country_flag = single_enrichment_facility clr_country_flag = build_three_enrichment_facility '
             'set_variable = { eon_enrichment_project_count = 0 } set_variable = { eon_enrichment_project_escrow = 0 } '
             'set_variable = { enrichment_facilities = 0 } set_variable = { industrial_complex_total = 200 } set_variable = { treasury = 100 } '
             'set_variable = { '+NS+'_timer = 730 } '+observe('before_activation')+
             check('no_control_callback_before_arm', ' '.join('NOT = { has_country_flag = '+ident+'_expired } ' for ident, op, body in controls))+
             'set_country_flag = '+NS+'_armed '+''.join('activate_mission = '+ident+' ' for ident, op, body in controls)+
             measure(click3, charge=True)+observe('triple_start')+
             check('actual_triple_gui_charged75_once', cv(NS+'_delta',75)+cv('eon_enrichment_project_count',3)+cv('eon_enrichment_project_escrow',75)+paid)+queue(2,8))
    positive = cv('days_mission_timeout@'+MISSION,0,'greater_than')
    zero = cv('days_mission_timeout@'+MISSION,0)
    second = (observe('matrix_and_triple_poll')+check('actual_triple_native_timer_positive',positive)+
              check('actual_triple_remaining_includes365_extension',cv('days_mission_timeout@'+MISSION,1090,'greater_than_or_equals')+cv('days_mission_timeout@'+MISSION,1095,'less_than_or_equals'))+
              check('literal_allowed_yes_control_native_timer_positive',cv('days_mission_timeout@'+NS+'_yes_literal',0,'greater_than'))+
              ''.join(remove(ident) for ident, op, body in controls)+adjust(-729)+queue(3,32))
    third = (observe('triple_base_period_elapsed')+
             check('triple_not_finished_after_single_build_period',positive+paid+cv('enrichment_facilities',0)+cv('eon_enrichment_project_count',3))+
             check('triple_extension_still_has_positive_native_days',cv('days_mission_timeout@'+MISSION,350,'greater_than_or_equals')+cv('days_mission_timeout@'+MISSION,366,'less_than_or_equals'))+
             adjust(-365)+queue(4,32))
    fourth = (observe('triple_native_expired')+
              check('actual_triple_native_timeout_builds_three_once',zero+unpaid+cv('enrichment_facilities',3)+cv('eon_enrichment_project_count',0)+cv('eon_enrichment_project_escrow',0))+
              measure(timeout+timeout)+check('stale_triple_timeout_has_no_second_payment_or_build',cv(NS+'_delta',0)+cv('enrichment_facilities',3))+
              'set_variable = { treasury = 100 } set_variable = { industrial_complex_total = 200 } '+
              measure(click1,charge=True)+observe('cancel_single_start')+check('cancel_single_gui_charged25',cv(NS+'_delta',25))+
              'CAN = { country_event = { id = '+NS+'.9 hours = 8 } } ')
    fifth = (observe('cancel_single_poll')+check('cancel_single_native_timer_positive',positive+paid)+
             check('direct_cancel_has_foreign_CAN_frame','FROM = { tag = CAN } ')+
             'set_variable = { new_enrichment_country = CAN.id } '+
             measure(cancel+cancel+timeout)+observe('cancel_source_callbacks')+
             check('actual_cancel_callback_refunds25_once_and_removes_timer_without_stale_build',cv(NS+'_delta',25)+zero+unpaid+cv('enrichment_facilities',3))+
             check('direct_cancel_clears_legacy_time',cv('enrichment_facility_time',0))+
             check('direct_cancel_clears_single_and_triple_flags','NOT = { has_country_flag = single_enrichment_facility } NOT = { has_country_flag = build_three_enrichment_facility } ')+
             check('direct_cancel_hides_production_mission','NOT = { '+visible_binding['alias']+' = yes } ')+
             remove()+queue(6,8))
    sixth = (check('cancelled_native_timer_zero_before_restart',zero)+
             'set_variable = { treasury = 100 } set_variable = { industrial_complex_total = 200 } '+
             measure(click1,charge=True)+observe('calendar_single_start')+
             check('calendar_single_gui_charged25',cv(NS+'_delta',25)+paid+cv('eon_enrichment_project_count',1))+queue(7,8))
    seventh = (observe('calendar_single_poll')+check('calendar_single_native_timer_positive',positive+paid)+
               check('single_native_timer_has_no_triple_extension',cv('days_mission_timeout@'+MISSION,725,'greater_than_or_equals')+cv('days_mission_timeout@'+MISSION,730,'less_than_or_equals'))+
               # The source energy.5.a sends its actual energy.6 acknowledgement
               # after three days. Start the new project before that response,
               # keep its timer running, then observe survival before speeding
               # up the real native callback. The ACK tooltip is display-only.
               queue(10,96))
    after_ack=(observe('single_running_after_native_cancel_ack')+
               check('actual_energy6_acknowledgement_cleared_pending_partner',cv('new_enrichment_country',0))+
               check('new_single_project_survives_real_delayed_ack',positive+paid+cv('eon_enrichment_project_count',1)+cv('eon_enrichment_project_escrow',25)+cv('enrichment_facilities',3))+
               check('new_single_timer_still_has_expected_native_days_after_ack',cv('days_mission_timeout@'+MISSION,720,'greater_than_or_equals')+cv('days_mission_timeout@'+MISSION,730,'less_than_or_equals'))+
               # Native recorded counters are integer days. Bind each literal
               # adjustment to its observed value instead of assuming the old
               #730-day poll still describes the timer after the ACK wait.
               ''.join('if = { limit = { '+cv('days_mission_timeout@'+MISSION,days)+' } '+adjust(1-days)+' } ' for days in range(720,731))+
               observe('single_accelerated_after_ack')+
               check('post_ack_native_timer_accelerated_to_one_day',cv('days_mission_timeout@'+MISSION,1)+paid)+queue(8,64))
    eighth = (observe('single_native_expired')+
              check('actual_single_native_timeout_builds_one_once',zero+unpaid+cv('enrichment_facilities',4)+cv('eon_enrichment_project_count',0)+cv('eon_enrichment_project_escrow',0))+
              measure(timeout+timeout)+check('stale_single_timeout_has_no_second_payment_or_build',cv(NS+'_delta',0)+cv('enrichment_facilities',4))+
              'log = "'+MARKER+' END passes=[?global.'+NS+'_passes] fails=[?global.'+NS+'_fails]" '
              'set_global_flag = '+NS+'_finished set_global_flag = eon_private_uranium_enrichment_finished ')
    def event(number, body):
        return ('country_event = { id = '+NS+'.'+str(number)+' hidden = yes is_triggered_only = yes immediate = { '
                'if = { limit = { NOT = { has_global_flag = '+NS+'_event_'+str(number)+' } } set_global_flag = '+NS+'_event_'+str(number)+' '+
                check('event'+str(number)+'_native_GER_frame','tag = GER ROOT = { tag = GER } ')+
                'if = { limit = { tag = GER ROOT = { tag = GER } } '+body+' } else = { log = "'+MARKER+' ABORT wrong_frame" } '
                '} else = { log = "'+MARKER+' DUPLICATE_EVENT '+str(number)+'" } } }')
    events = [event(i,body) for i,body in enumerate((first,second,third,fourth,fifth,sixth,seventh,eighth),1)]
    events.append(event(10,after_ack))
    events.append('country_event = { id = '+NS+'.9 hidden = yes is_triggered_only = yes immediate = { '
                  'if = { limit = { tag = CAN ROOT = { tag = CAN } } GER = { country_event = { id = '+NS+'.5 hours = 0 } } } '
                  'else = { log = "'+MARKER+' ABORT wrong_cancel_dispatcher_frame" } } }')
    # Observations are evaluated in native chronological order. Event10 is
    # assembled after event8 only to keep the original eight callbacks stable.
    observations.remove('single_native_expired');observations.append('single_native_expired')
    fixture = {'common/scripted_effects/'+NS+'_effects.txt':render(aliases),
               'common/scripted_triggers/'+NS+'_triggers.txt':render([(visible_binding['alias'],'=',visible_body)]),
               'common/synchronized_dynamic_tokens/'+NS+'_tokens.txt':'\n'.join(ident for ident,op,body in controls),
               'common/decisions/'+NS+'_controls.txt':render([('GENERIC_economic_category','=',controls)]),
               'events/'+NS+'_events.txt':'add_namespace = '+NS+'\n\n'+'\n\n'.join(events),
               'common/on_actions/'+NS+'_on_actions.txt':
               'on_actions = { on_startup = { effect = { if = { limit = { NOT = { has_global_flag = '+NS+'_booted } } '
               'set_global_flag = '+NS+'_booted set_variable = { global.'+NS+'_passes = 0 } set_variable = { global.'+NS+'_fails = 0 } '
               'log = "'+MARKER+' STARTUP native_mission_calendar" GER = { '
               'set_country_flag = { flag = eon_uranium_import_attempted days = 30 value = 1 } '
               'country_event = { id = '+NS+'.1 hours = '+str(start_delay_hours)+' } } } } } }'}
    output.mkdir(parents=True,exist_ok=True)
    for rel,body in fixture.items():
        p.ast(body)
        path = output/'mod'/rel
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes((body.replace('\r\n','\n').replace('\n','\r\n')+'\r\n').encode('utf-8'))
    docs = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation')
    manifest = {'schema':1,'kind':'native_uranium_mission_calendar','marker':MARKER,'mission_calendar_evidence_version':4,'source_root':str(source),'fixture_root':str(output),
                'preparation_only':preparation_only,'expected_native_start_tag':start_tag,'expected_enabled_mods':['mod/era_of_nations.mod'],
                'assertions':assertions,'observation_labels':observations,'observation_fields':fields,'minimum_total_native_hours':152,
                'single_native_timeout_observation_delay_hours':64,'minimum_single_timeout_observation_hours':60,
                'direct_cancellation_event_option':'energy.5.a','cancellation_ack_observation_delay_hours':96,
                'minimum_cancellation_ack_observation_hours':92,'predicate_bindings':[visible_binding],
                'callback_bindings':bindings,'production_mission_ast_sha256':canonical(candidate),
                'matrix_ids':[ident for ident,op,body in controls], 'matrix_ast_sha256':canonical(controls),
                'source_sha256':dependencies,'fixture_sha256':{rel:sha(output/'mod'/rel) for rel in fixture},'builder_sha256':sha(Path(__file__)),
                'installed_documentation_root':str(docs),
                'installed_documentation_sha256':{rel:sha(docs/rel) for rel in ('effects_documentation.md','triggers_documentation.md','dynamic_variables_documentation.md')},
                'source_export_binding':None if not export_receipt else {'path':str(export_receipt.resolve()),'sha256':sha(export_receipt)},
                'limits':['Four private country mission controls distinguish allowed yes/no and literal730/dynamic ROOT.timer at load.',
                          'Production mission and begin effect remain unchanged; actual native remaining-days and accelerated calendar completion are observed.',
                          'GUI bodies and direct energy.5.a executable option effects execute from exact source aliases in a native foreign CAN FROM frame; no actual human click is claimed.',
                          'The immediate replacement project must remain paid and running after the actual delayed energy.6 acknowledgement clears the pending partner; effect_tooltip is display-only.',
                          'Cancellation native mission removal is explicit and does not claim engine-selected complete_effect.',
                          'No save/load, multiplayer or full campaign acceptance.']}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source-root',type=Path,required=True)
    cli.add_argument('--output',type=Path,required=True)
    cli.add_argument('--export-receipt',type=Path)
    cli.add_argument('--prepare-only',action='store_true')
    cli.add_argument('--start-tag',default='NEP')
    cli.add_argument('--start-delay-hours',type=int,default=30)
    args=cli.parse_args()
    result=build(args.source_root,args.output,args.export_receipt,args.prepare_only,args.start_tag,args.start_delay_hours)
    print(json.dumps({'mission_calendar_control_prepared':True,'assertions':len(result['assertions']),'native_game_behavior_tested':False}))


if __name__ == '__main__': main()
