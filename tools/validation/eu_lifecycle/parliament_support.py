"""Additive actual-source EP/Council native stages; never install or launch."""
from pathlib import Path
import hashlib, json, os, re, sys
ROOT = Path(os.environ.get('EON_WORKSPACE_ROOT', Path(__file__).resolve().parents[3])).resolve()
sys.path.insert(0, str(ROOT / 'tools/validation/diplomacy_package_02'))
from _treaty_support import ast, one

SOURCE_PATHS = (
 'common/scripted_guis/01_european_union_guis.txt', 'common/decisions/EU_voting_decisions.txt',
 'common/scripted_effects/eon_eu_parliament_effects.txt', 'common/scripted_triggers/eon_eu_parliament_triggers.txt',
 'common/scripted_effects/eon_eu_voting_effects.txt', 'common/scripted_triggers/eon_eu_voting_triggers.txt',
 'common/scripted_effects/99_EU_voting_scripted_effects.txt', 'common/scripted_triggers/99_EU_voting_scripted_triggers.txt',
 'common/scripted_effects/00_eu_scripted_effects.txt', 'common/scripted_effects/eon_eu_membership_effects.txt',
 'common/scripted_triggers/eon_eu_membership_triggers.txt', 'common/scripted_effects/eon_eu_lifecycle_effects.txt',
 'common/scripted_effects/eon_eu_institutions_effects.txt', 'common/scripted_triggers/eon_eu_institutions_triggers.txt',
 'common/synchronized_dynamic_tokens/eon_eu_parliament_tokens.txt', 'common/synchronized_dynamic_tokens/eon_eu_legislative_tokens.txt',
)
MEMBERS = ('GER', 'FRA', 'ITA', 'HOL', 'SPR', 'CZE')

def render(nodes):
    def value(v):
        if isinstance(v, list): return '{ ' + render(v) + ' }'
        return json.dumps(v, ensure_ascii=False) if any(ch.isspace() for ch in v) or '"' in v else v
    result = ' '.join(value(v) if k == '__item__' else f'{k} {op} {value(v)}' for k, op, v in nodes)
    assert ast(result) == nodes
    return result + ' '

def build_parliament(namespace, marker, *, source=ROOT, terminal_effect=''):
    source = Path(source).resolve()
    assert re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', namespace)
    assert re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', marker)
    for path in SOURCE_PATHS: assert (source / path).is_file(), path
    gui = one(ast((source / SOURCE_PATHS[0]).read_text('utf-8-sig')), 'scripted_gui')
    root_gui = one(gui, 'european_union_gui')
    ep_gui = one(gui, 'european_parliament_dynamic_lists')
    council_gui = one(gui, 'european_council_voting_dynamic_lists')
    missions = one(ast((source / SOURCE_PATHS[1]).read_text('utf-8-sig')), 'EU_voting_category')
    proposal = render(one(one(ep_gui, 'effects'), 'eu_parliament_available_reforms_button_click'))
    proposal_enabled = render(one(one(ep_gui, 'triggers'), 'eu_parliament_available_reforms_button_click_enabled'))
    influence = render(one(one(root_gui, 'effects'), 'PG_party_1_influence_click'))
    influence_enabled = render(one(one(root_gui, 'triggers'), 'PG_party_1_influence_click_enabled'))
    council_proposal = render(one(one(council_gui, 'effects'), 'eu_council_available_reforms_button_click'))
    ep_result = one(missions, 'EU_parliament_focus_EUXXX_approve')
    ep_timer = one(missions, 'EU_parliament_focus_EUXXX_approve_timer')
    result_timeout, result_complete = render(one(ep_result, 'timeout_effect')), render(one(ep_result, 'complete_effect'))
    timer_timeout = render(one(ep_timer, 'timeout_effect'))
    # Derive the exact positive/zero source-weight conditions. This adapter calls
    # the extracted actual effect under its actual source AI gate; it does not
    # claim that the game's scripted-GUI scheduler selected a click itself.
    weight = one(one(one(root_gui, 'ai_weights'), 'PG_party_1_influence_click'), 'ai_will_do')
    assert one(weight, 'factor') == '1'
    ai_gate = 'is_ai = yes '
    for key, _, node in weight:
        if key == 'modifier':
            assert one(node, 'factor') == '0'
            ai_gate += 'NOT = { ' + render([n for n in node if n[0] != 'factor']) + '} '

    prefix = 'global.' + namespace + '_ep_'
    events, assertions, expectations, observations = {}, [], {}, []
    def cv(name, v, cmp='equals'): return f'check_variable = {{ var = {name} value = {v} compare = {cmp} }} '
    def sv(name, v): return f'set_variable = {{ {name} = {v} }} '
    def scope(tag, body): return f'{tag} = {{ {body} }} '
    def contains(array, v, yes=True):
        return ('' if yes else 'NOT = { ') + f'is_in_array = {{ array = {array} value = {v} }} ' + ('' if yes else '} ')
    def check(label, predicate, why):
        label = 'parliament_' + label; assert label not in expectations
        assertions.append(label); expectations[label] = {'predicate': predicate, 'expected': why}
        return (f'log = "{marker} BEGIN {label}" if = {{ limit = {{ {predicate} }} '
                f'log = "{marker} PASS {label}" add_to_variable = {{ global.{namespace}_passes = 1 }} }} '
                f'else = {{ log = "{marker} FAIL {label}" add_to_variable = {{ global.{namespace}_fails = 1 }} }} '
                f'log = "{marker} END {label}" ')
    def obs(label):
        label = 'PARLIAMENT_' + label; observations.append(label)
        return (f'log = "{marker} OBS {label} date=[?global.date] agenda=[?global.current_active_agenda_disp] '
                'round=[?global.eon_eu_ep_instance] council=[?global.current_active_vote_disp] '
                'support=[?global.active_MEP_Support] majority=[?global.MEP_Majority]" ')
    def schedule(number, hours=2): return scope('NEP', f'country_event = {{ id = {namespace}.{number} hours = {hours} }} ')
    def event(number, body):
        assert 7200 <= number <= 7399 and number not in events
        events[number] = f'country_event = {{ id = {namespace}.{number} hidden = yes is_triggered_only = yes immediate = {{ {body} }} }}\n'

    # Independent artificial source-input setup. No save, Workshop or launcher
    # mutation; no consequence here is evidence of historical country behavior.
    body = obs('SETUP')
    body += 'set_global_flag = { flag = eon_eu_daily_lifecycle_done days = 180 value = 1 } '
    body += 'eon_eu_ep_close_round = yes eon_eu_archive_council_round = yes '
    body += 'set_global_flag = eon_eu_registry_refreshing every_country = { set_country_flag = eon_eu_leaving_in_progress remove_ideas = EU_member clr_country_flag = eon_eu_leaving_in_progress eon_eu_clear_country_access = yes remove_ideas = EU_commission_president } '
    body += 'clr_global_flag = eon_eu_dormant clr_global_flag = GAME_RULE_eu_disabled clr_global_flag = usoe_formed '
    body += f'set_global_flag = {namespace}_parliament_trace ' + sv(prefix + 'daily_callbacks', 0)
    body += 'set_global_flag = { flag = EP_AI_hold_their_vote days = 90 value = 1 } '
    for tag in MEMBERS:
        body += scope(tag, 'set_country_flag = eon_eu_admission_commit add_ideas = EU_member remove_ideas = EUU_voting_rights_suspended remove_ideas = EUU_cfr_eu clr_country_flag = focus_EU101_yes clr_country_flag = focus_EU101_QMV_yes clr_country_flag = focus_EU201_yes clr_country_flag = focus_EU201_QMV_yes set_variable = { eurosceptic = 0 } set_variable = { MEP_Total = 100 } set_political_power = 2000 clear_array = ruling_party add_to_array = { ruling_party = 0 } clr_country_flag = delay_next_parliament_vote ')
    body += 'clr_global_flag = eon_eu_registry_refreshing eon_eu_refresh_membership = yes GER = { eon_eu_appoint_office_1 = yes } '
    body += 'clear_array = global.EU_potential_votes clear_array = global.EU_council_votes clear_array = global.EU_passed_votes '
    body += 'add_to_array = { global.EU_potential_votes = 101 } add_to_array = { global.EU_potential_votes = 201 } '
    body += 'clr_global_flag = focus_EU101_EP_approval clr_global_flag = focus_EU201_EP_approval clr_global_flag = delay_next_council_vote '
    body += sv('global.MEP_Total', 600) + sv('global.MEP_Majority', 301)
    for group in range(24): body += sv(f'global.MEP_PG_party_{group}', {0: 120, 1: 200, 2: 280}.get(group, 0))
    body += sv('global.current_active_agenda_disp', 0)
    body += check('declared_current_six_member_commission_origin', 'eon_eu_union_active = yes ' + cv('global.EU_member_count', 6) + scope('GER', 'eon_eu_is_active_member = yes has_idea = EU_commission_president ' + cv('global.eucomission', 'THIS.id')),
                  'Six sovereign source members and current Commission origin are explicit private test inputs established by actual membership/office helpers')
    # Shared 998/999 trigger regression; no budget approval/enactment is fabricated.
    for law in (998, 999):
        body += sv('global.current_active_agenda_disp', law) + sv('global.pass_vote_mission_ender', 1)
        body += check(f'special_{law}_actual_available_branch_preserved', 'eon_eu_ep_special_context = yes NOT = { eon_eu_ep_ordinary_context = yes } ' + render(one(ep_result, 'available')),
                      f'Actual shared mission available branch for {law} retains original pass_vote_mission_ender behavior; full fiscal budget/MFF execution is outside this legislative trace')
    body += sv('global.current_active_agenda_disp', 0) + sv('global.pass_vote_mission_ender', 0)
    body += scope('NEP', 'set_temp_variable = { v = 101 } ' + proposal)
    body += check('outsider_actual_proposal_inert', cv('global.current_active_agenda_disp', 0) + cv('global.EU_council_votes^num', 0), 'Actual extracted GUI callback rejects outsider actor without starting or queuing a law')
    body += scope('FRA', 'add_ideas = EUU_voting_rights_suspended set_temp_variable = { v = 101 } ' + proposal + 'remove_ideas = EUU_voting_rights_suspended ')
    body += check('suspended_actual_proposal_inert', cv('global.current_active_agenda_disp', 0), 'Actual callback rejects a suspended member')
    body += scope('FRA', 'set_temp_variable = { v = 101 } ' + check('actual_gui_numeric_proposal_enabled', proposal_enabled, 'Actual numeric row v and actor scope satisfy real source GUI gate') + proposal + proposal)
    body += check('actual_proposal_starts_once_exact_fee', cv('global.current_active_agenda_disp', 101) + cv('global.eon_eu_ep_agenda', 101) + scope('FRA', cv('political_power', 1800)) + scope('GER', 'has_active_mission = EU_parliament_focus_EUXXX_approve ') + scope('HOL', 'has_active_mission = EU_parliament_focus_EUXXX_approve_timer '), 'Two actual clicks create one fixed-ID round and one existing200PP debit')
    body += scope('ITA', check('actual_source_ai_weight_and_gui_influence_gate', ai_gate + influence_enabled, 'Actual AI country satisfies extracted GUI and source zero-modifier gates; adapter does not claim GUI scheduler selection') + influence + influence)
    body += check('actual_group_influence_unique_support_and_fee', cv('global.active_MEP_Support', 320) + scope('ITA', cv('political_power', 1600)), 'Actual politicalgroup callback adds canonical200 seats and charges400PP once despite replay')
    body += sv(prefix + 'first_instance', 'global.eon_eu_ep_instance')
    body += scope('GER', result_timeout + result_complete) + scope('HOL', timer_timeout)
    body += check('positive_current_round_generic_callbacks_inert', cv('global.eon_eu_ep_instance', prefix + 'first_instance') + cv('global.current_active_agenda_disp', 101) + cv('global.EU_council_votes^num', 0) + 'has_global_flag = eon_eu_ep_deadline ' + scope('GER', 'has_active_mission = EU_parliament_focus_EUXXX_approve ') + scope('HOL', 'has_active_mission = EU_parliament_focus_EUXXX_approve_timer '), 'Actual fixed callbacks read current mutable bindings but cannot capture/enact/remove controls during a positive original deadline')
    body += obs('STAGE1_START') + schedule(7201, 337)
    event(7200, body)

    body = obs('STAGE1_NATURAL_END')
    body += check('natural_ep_fourteen_days_unique_council_handoff', cv(prefix + 'daily_callbacks', 14, 'greater_than_or_equals') + cv('global.current_active_agenda_disp', 0) + cv('global.EU_council_votes^num', 1) + contains('global.EU_council_votes', 101) + 'has_global_flag = focus_EU101_EP_approval ' + contains('global.EU_potential_votes', 101, False) + contains('global.EU_passed_votes', 101, False) + scope('GER', 'NOT = { has_idea = EUU_cfr_eu }'), 'After at least336 real game hours and14 actual daily callbacks, native missions/flags plus actual source reconciliation hand EP101 to Council once without enactment; no manual deadline expiry occurred')
    body += scope('FRA', 'set_temp_variable = { v = 101 } ' + council_proposal)
    for tag in MEMBERS: body += scope(tag, 'eon_eu_support_council_vote = yes ')
    body += check('actual_council_after_ep_uses_live_canonical_ballots', cv('global.current_active_vote_disp', 101) + cv('global.EU_active_vote_yes', 6) + scope('GER', 'has_active_mission = EU_voting_mission_focus_EUXXX_QMV_result '), 'Actual extracted Council GUI callback starts the approved agenda and all six actual canonical cast helpers consent')
    body += obs('COUNCIL_START') + schedule(7202, 337)
    event(7201, body)

    body = obs('COUNCIL_NATURAL_END')
    body += check('natural_council_fourteen_days_actual_law_enacted_once', cv(prefix + 'daily_callbacks', 28, 'greater_than_or_equals') + cv('global.current_active_vote_disp', 0) + cv('global.EU_passed_votes^num', 1) + contains('global.EU_passed_votes', 101) + contains('global.EU_council_votes', 101, False) + ''.join(scope(t, 'has_idea = EUU_cfr_eu ') for t in MEMBERS), 'A second at least336 actual hours completes the real named101 law effect and a single passed receipt across the six eligible countries')
    for tag in MEMBERS: body += scope(tag, 'clr_country_flag = delay_next_parliament_vote set_political_power = 2000 ')
    body += scope('FRA', 'set_temp_variable = { v = 201 } ' + proposal)
    body += scope('ITA', influence)
    body += check('repeated_ep_stage_new_instance_same_native_ids', cv('global.current_active_agenda_disp', 201) + cv('global.eon_eu_ep_instance', prefix + 'first_instance', 'greater_than') + scope('GER', 'has_active_mission = EU_parliament_focus_EUXXX_approve ') + 'has_global_flag = eon_eu_ep_deadline ', 'Reused fixed mission IDs activate for a distinct second EP stage under fire_only_once=no without reopening original101')
    body += sv(prefix + 'second_instance', 'global.eon_eu_ep_instance')
    body += scope('GER', result_timeout + result_complete) + scope('HOL', timer_timeout)
    body += check('overwritten_newer_vars_old_generic_wakeups_inert', cv('global.eon_eu_ep_instance', prefix + 'second_instance') + cv('global.current_active_agenda_disp', 201) + cv('global.EU_council_votes^num', 0) + scope('HOL', 'has_active_mission = EU_parliament_focus_EUXXX_approve_timer '), 'Country vars now describe newer201. Generic old fixed-ID callback cannot remove or resolve its positive current controls; no fictional immutable var payload is assumed')
    body += obs('REPEAT_START') + schedule(7203, 337)
    event(7202, body)

    body = obs('REPEAT_NATURAL_END')
    body += check('repeated_ep_native_fourteen_days_completes_once', cv(prefix + 'daily_callbacks', 42, 'greater_than_or_equals') + cv('global.current_active_agenda_disp', 0) + cv('global.EU_council_votes^num', 1) + contains('global.EU_council_votes', 201) + 'has_global_flag = focus_EU201_EP_approval ' + cv('global.EU_passed_votes^num', 1) + contains('global.EU_passed_votes', 101), 'Actual second fixed-ID EP mission completes after another336 hours; 201 is pending Council and previously enacted101 remains once')
    body += f'clr_global_flag = {namespace}_parliament_trace clr_global_flag = EP_AI_hold_their_vote ' + terminal_effect
    event(7203, body)
    texts = {f'events/{namespace}.txt': f'add_namespace = {namespace}\n' + ''.join(events.values())}
    for text in texts.values(): ast(text)
    pins = {path: hashlib.sha256((source / path).read_bytes()).hexdigest() for path in SOURCE_PATHS}
    return {'fixture_text': texts, 'entry_event_id': f'{namespace}.7200', 'terminal_event_id': f'{namespace}.7203', 'entry_effect': schedule(7200), 'events': len(events), 'assertions': assertions, 'expectations': expectations, 'observations': observations,
            'on_daily_effect': f'if = {{ limit = {{ has_global_flag = {namespace}_parliament_trace }} NEP = {{ add_to_variable = {{ {prefix}daily_callbacks = 1 }} log = "{marker} TRACE PARLIAMENT_SOURCE_DAILY_RECONCILE date=[?global.date] count=[?{prefix}daily_callbacks]" eon_eu_ep_capture_deadline_outcome = yes eon_eu_ep_reconcile_owner = yes eon_eu_capture_council_deadline_outcome = yes eon_eu_reconcile_council_vote_owner = yes set_global_flag = {{ flag = EP_AI_hold_their_vote days = 2 value = 1 }} }} }} ',
            'production_dependency_paths': list(SOURCE_PATHS), 'production_input_sha256': pins,
            'required_elapsed_game_time': [{'start_observation': 'PARLIAMENT_STAGE1_START', 'end_observation': 'PARLIAMENT_STAGE1_NATURAL_END', 'minimum_hours': 336}, {'start_observation': 'PARLIAMENT_COUNCIL_START', 'end_observation': 'PARLIAMENT_COUNCIL_NATURAL_END', 'minimum_hours': 336}, {'start_observation': 'PARLIAMENT_REPEAT_START', 'end_observation': 'PARLIAMENT_REPEAT_NATURAL_END', 'minimum_hours': 336}],
            'limits': ['Declared six-country registry,600 seats,24 politicalgroups and2000PP are private inputs. Source memberships and office are established by real production helpers.', 'Three actual native14-day stages use real fixed mission scheduling and natural positive flags. Actual on_daily invokes only the source EP/Council capture/reconciliation helpers under an explicit private flag and counts/logs callbacks; no manual deadline expiry occurs. The full production coordinator remains frozen, so this is source-helper scheduling rather than a full campaign.', 'Existing EP_AI_hold_their_vote is a declared private proposal killswitch refreshed by the narrow daily fixture to keep unsolicited parallel proposals out of this isolated trace.', 'Extracted GUI callbacks and actual source AI weighting gates are executed by a fixture adapter; real mouse/scripted-GUI AI scheduler selection and multiplayer are not proven.', '998/999 preserve exact selected source AST plus native shared available gate. Full fiscal budget/MFF execution, all47-law campaign behavior and long campaigns are not proven.']}
