"""Additive source-bound Council native probe module.

Generates private fixture text only; never installs files or launches the game. The generated
module adds only events to the existing five-asset lifecycle fixture. Actual
native mission callbacks and a declared private on_daily production fallback
are the scheduler paths; original canonical deadlines are never cleared.
"""
from pathlib import Path
import hashlib, json, re, sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/validation/diplomacy_package_02'))
from _treaty_support import ast, one

MEMBERS = ('GER', 'FRA', 'ITA', 'HOL', 'SPR', 'CZE')
RESULT = 'EU_voting_mission_focus_EUXXX_QMV_result'
TIMER = RESULT + '_timer'
DEPENDENCIES = (
 'common/scripted_effects/eon_eu_voting_effects.txt',
 'common/scripted_triggers/eon_eu_voting_triggers.txt',
 'common/scripted_guis/01_european_union_guis.txt',
 'common/decisions/EU_voting_decisions.txt',
 'common/synchronized_dynamic_tokens/eon_eu_legislative_tokens.txt',
 'common/scripted_effects/99_EU_voting_scripted_effects.txt',
 'common/scripted_triggers/99_EU_voting_scripted_triggers.txt',
 'common/scripted_triggers/99_EU_scripted_triggers.txt',
 'common/scripted_effects/00_eu_scripted_effects.txt',
 'common/scripted_effects/eon_eu_lifecycle_effects.txt',
 'common/scripted_effects/eon_eu_membership_effects.txt',
 'common/scripted_triggers/eon_eu_membership_triggers.txt',
 'common/scripted_effects/eon_eu_institutions_effects.txt',
 'common/scripted_triggers/eon_eu_institutions_triggers.txt',
)

def render(nodes):
    def value(v):
        if isinstance(v, list): return '{ ' + render(v) + ' }'
        return json.dumps(v, ensure_ascii=False) if re.search(r'[\s{}"]', v) else v
    return ' '.join(value(v) if k == '__item__' else f'{k} {op} {value(v)}' for k, op, v in nodes)

def walk(nodes):
    for node in nodes:
        yield node
        if isinstance(node[2], list): yield from walk(node[2])

def source_contract(source):
    source = Path(source).resolve()
    texts = {p: (source / p).read_text('utf-8-sig') for p in DEPENDENCIES}
    fx = ast(texts[DEPENDENCIES[0]])
    gui = one(one(ast(texts[DEPENDENCIES[2]]), 'scripted_gui'), 'european_council_voting_dynamic_lists')
    proposal = one(one(gui, 'effects'), 'eu_council_available_reforms_button_click')
    assert proposal == [('eon_eu_start_council_proposal', '=', 'yes')], 'Actual GUI proposal callback drifted'
    missions = one(ast(texts[DEPENDENCIES[3]]), 'EU_voting_category')
    for ident, helper in ((RESULT, 'eon_eu_council_result_timeout'), (TIMER, 'eon_eu_council_timer_timeout')):
        fields = one(missions, ident)
        assert one(fields, 'days_mission_timeout') == '14', 'Native source mission must retain the actual14-day clock'
        assert one(fields, 'timeout_effect') == [(helper, '=', 'yes')], 'Native timeout must execute the production callback'
    assert texts[DEPENDENCIES[4]].split() == [RESULT, TIMER], 'Exactly the queried fixed clocks must be synchronized'
    for helper in ('eon_eu_archive_council_round', 'eon_eu_capture_council_deadline_outcome', 'eon_eu_reconcile_council_vote_owner'):
        assert one(fx, helper), ('Missing candidate helper', helper)
    life = ast(texts['common/scripted_effects/eon_eu_lifecycle_effects.txt'])
    daily = list(walk(one(life, 'eon_eu_daily_lifecycle_pulse')))
    daily_keys = [k for k, _, _ in daily]
    assert daily_keys.index('eon_eu_capture_council_deadline_outcome') < daily_keys.index('eon_eu_refresh_membership'), 'Deadline capture must precede membership refresh'
    assert daily_keys.index('eon_eu_reconcile_council_vote_owner') > daily_keys.index('eon_eu_daily_institutions_pulse'), 'Owner reconciliation must follow institution reconciliation'
    assert 'eon_eu_archive_council_round' in [k for k, _, _ in walk(one(life, 'eon_eu_reset_institutional_laws'))], 'Archive must consume the canonical round'
    return {'proposal_callback': render(proposal),
            'production_input_sha256': {p: hashlib.sha256((source / p).read_bytes()).hexdigest() for p in DEPENDENCIES}}

def core_valid_round_setup(agenda, *, owner='ITA', clear_ballots=True):
    """Suggested controlled-core setup; never fabricates serial/deadline/outcome.

The caller must already have an actual recognized live member registry. Office
and agenda availability are declared fixture inputs. Initial native AI ballots
are explicitly cleared only for existing isolated threshold controls, not for
the full-cycle acceptance module below.
"""
    assert agenda in (101, 103) and owner in MEMBERS
    text = 'eon_eu_archive_council_round = yes '
    text += 'every_country = { remove_ideas = EU_commission_president } '
    text += f'{owner} = {{ eon_eu_appoint_office_1 = yes set_variable = {{ eurosceptic = 0 }} '
    text += 'clr_country_flag = delay_player_next_council_vote clear_array = influence_array clear_array = influence_array_val '
    text += f'clr_global_flag = delay_next_council_vote add_to_array = {{ array = global.EU_council_votes value = {agenda} }} '
    text += f'set_temp_variable = {{ v = {agenda} }} eon_eu_start_council_proposal = yes }} '
    if clear_ballots:
        text += 'clear_array = global.EU_active_vote_supporters clear_array = global.EU_active_vote_rejecters clear_array = global.eon_eu_council_abstainers eon_eu_recount_council_vote = yes '
    return text

def build_council(namespace, marker, *, terminal_effect='', source=ROOT):
    source = Path(source).resolve()
    assert re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', namespace)
    assert re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', marker)
    bound = source_contract(source)
    events, labels, expectations, observations, elapsed, calibrations = {}, [], {}, [], [], []
    prefix = 'global.' + namespace + '_council_private_'
    trace_flag = namespace + '_council_scheduler_trace'
    def cv(var, value, compare='equals'):
        return f'check_variable = {{ var = {var} value = {value} compare = {compare} }} '
    def setv(var, value): return f'set_variable = {{ {var} = {value} }} '
    def scope(tag, body): return f'{tag} = {{ {body} }} '
    def schedule(number, hours, tag='NEP'): return scope(tag, f'country_event = {{ id = {namespace}.{number} hours = {hours} }} ')
    def event(number, body):
        assert 7000 <= number <= 7199 and number not in events
        events[number] = f'country_event = {{ id = {namespace}.{number} hidden = yes is_triggered_only = yes immediate = {{ {body} }} }}\n'
    def check(label, predicate, why):
        label = 'council_native_' + label
        assert label not in expectations
        labels.append(label); expectations[label] = {'predicate': predicate, 'expected': why}
        return (f'log = "{marker} BEGIN {label}" if = {{ limit = {{ {predicate} }} '
                f'log = "{marker} PASS {label}" add_to_variable = {{ global.{namespace}_passes = 1 }} }} '
                f'else = {{ log = "{marker} FAIL {label}" add_to_variable = {{ global.{namespace}_fails = 1 }} }} log = "{marker} END {label}" ')
    def obs(label, values=''):
        label = 'COUNCIL_' + label
        assert label not in observations; observations.append(label)
        return f'log = "{marker} OBS {label} raw=[?global.date] {values}" '
    def state(label):
        return obs(label, 'agenda=[?global.current_active_vote_disp] round_agenda=[?global.eon_eu_council_round_agenda] instance=[?global.eon_eu_council_vote_instance] owner=[?global.eon_eu_council_vote_owner] outcome_instance=[?global.eon_eu_council_outcome_instance] outcome_agenda=[?global.eon_eu_council_outcome_agenda] outcome_yes=[?global.eon_eu_council_outcome_yes] yes=[?global.EU_active_vote_yes] no=[?global.EU_active_vote_no] voters=[?global.eon_eu_voters]')
    def clocks(label):
        text = obs(label, 'deadline_day=[?global.eon_eu_council_vote_deadline_day] current_day=[?global.num_days]')
        for tag in ('FRA', 'ITA', 'GER', 'HOL'):
            text += scope(tag, obs(label + '_' + tag, 'result_days=[?days_mission_timeout@' + RESULT + '] timer_days=[?days_mission_timeout@' + TIMER + '] country_instance=[?eon_eu_council_mission_instance] country_agenda=[?eon_eu_council_mission_agenda]'))
        return text
    def seed(tag):
        return scope(tag, 'eon_eu_clear_country_access = yes set_country_flag = eon_eu_admission_commit add_ideas = EU_member remove_ideas = EUU_voting_rights_suspended '
                     'set_variable = { eurosceptic = 0 } set_variable = { breach_of_EU_value = 0 } set_variable = { gdp_total = 100 } '
                     'clear_array = influence_array clear_array = influence_array_val ')
    def law_reset():
        # Declared isolated previous-law input cleanup, never a user save edit.
        text = 'eon_eu_archive_council_round = yes remove_from_array = { array = global.EU_passed_votes value = 101 } '
        text += 'every_country = { remove_ideas = EUU_cfr_eu clr_country_flag = focus_EU101_QMV_yes clr_country_flag = focus_EU101_yes clr_country_flag = delay_player_next_council_vote } '
        return text + 'clr_global_flag = delay_next_council_vote '
    def propose(owner):
        return scope(owner, 'add_political_power = 2000 add_to_array = { array = global.EU_council_votes value = 101 } set_temp_variable = { v = 101 } '
                     + bound['proposal_callback'] + ' ')
    def cast(yes=MEMBERS, no=()):
        return ''.join(scope(t, 'eon_eu_support_council_vote = yes ') for t in yes) + ''.join(scope(t, 'eon_eu_reject_council_vote = yes ') for t in no)
    def law_passed():
        return 'is_in_array = { array = global.EU_passed_votes value = 101 } ' + ''.join(scope(t, 'has_idea = EUU_cfr_eu ') for t in MEMBERS)
    def calibrate(tag, ident, days):
        calibrations.append({'country': tag, 'mission': ident, 'private_days': days, 'method': 'actual documented remaining clock + additive delta, no restart'})
        return scope(tag, f'set_temp_variable = {{ eon_council_private_delta = {days} }} subtract_from_temp_variable = {{ eon_council_private_delta = days_mission_timeout@{ident} }} '
                     f'add_days_mission_timeout = {{ mission = {ident} days = eon_council_private_delta }} ')
    def legacy_input(result_days=None, timer_days=None):
        text = law_reset() + setv('global.current_active_vote_disp', 101) + setv('global.EUXXX_council_agenda', 101)
        text += scope('GER', 'eon_eu_appoint_office_1 = yes ')
        if result_days is not None:
            text += scope('GER', f'activate_mission = {RESULT} ') + calibrate('GER', RESULT, result_days)
        if timer_days is not None:
            text += scope('HOL', f'activate_mission = {TIMER} ') + calibrate('HOL', TIMER, timer_days)
        return text

    # This private scheduled seam intentionally leaves the broad production
    # coordinator locked: its office AI would fill the deliberate vacancy.
    # Both callbacks below are the exact source-bound production helpers. The
    # existing separate WORLD trace still owns full-coordinator acceptance.
    # Repeating route observations are not required-once checkpoint labels.
    on_daily = 'if = { limit = { has_global_flag = ' + trace_flag + ' } '
    on_daily += f'add_to_variable = {{ {prefix}daily_callbacks = 1 }} '
    on_daily += setv(prefix + 'before_agenda', 'global.current_active_vote_disp')
    on_daily += setv(prefix + 'before_deadline_positive', 0)
    on_daily += setv(prefix + 'before_snapshot_current', 0)
    on_daily += 'if = { limit = { has_global_flag = eon_eu_council_vote_deadline } '
    on_daily += setv(prefix + 'before_deadline_positive', 1)
    on_daily += f'add_to_variable = {{ {prefix}daily_open_callbacks = 1 }} }} '
    on_daily += 'if = { limit = { eon_eu_council_deadline_outcome_current = yes } '
    on_daily += setv(prefix + 'before_snapshot_current', 1) + '} '
    on_daily += (f'log = "{marker} OBS COUNCIL_DAILY_BEFORE raw=[?global.date] '
                 f'callback=[?{prefix}daily_callbacks] agenda=[?global.current_active_vote_disp] '
                 f'instance=[?global.eon_eu_council_vote_instance] positive=[?{prefix}before_deadline_positive] '
                 f'snapshot_current=[?{prefix}before_snapshot_current]" ')
    on_daily += 'eon_eu_capture_council_deadline_outcome = yes eon_eu_reconcile_council_vote_owner = yes '
    on_daily += 'if = { limit = { ' + cv(prefix + 'before_agenda', 101) + cv(prefix + 'before_deadline_positive', 0)
    on_daily += f'}} add_to_variable = {{ {prefix}daily_elapsed_callbacks = 1 }} }} '
    on_daily += 'if = { limit = { ' + cv(prefix + 'before_snapshot_current', 0) + 'eon_eu_council_deadline_outcome_current = yes } '
    on_daily += f'add_to_variable = {{ {prefix}daily_captured_snapshots = 1 }} }} '
    on_daily += 'if = { limit = { ' + cv(prefix + 'before_agenda', 101) + cv(prefix + 'before_deadline_positive', 0) + cv('global.current_active_vote_disp', 0)
    on_daily += f'}} add_to_variable = {{ {prefix}daily_resolutions = 1 }} }} '
    on_daily += (f'log = "{marker} OBS COUNCIL_DAILY_AFTER raw=[?global.date] '
                 f'callback=[?{prefix}daily_callbacks] agenda=[?global.current_active_vote_disp] '
                 f'instance=[?global.eon_eu_council_vote_instance] outcome_instance=[?global.eon_eu_council_outcome_instance] '
                 f'outcome_agenda=[?global.eon_eu_council_outcome_agenda] outcome_yes=[?global.eon_eu_council_outcome_yes] '
                 f'elapsed_callbacks=[?{prefix}daily_elapsed_callbacks] '
                 f'captured_snapshots=[?{prefix}daily_captured_snapshots] resolutions=[?{prefix}daily_resolutions]" }} ')

    body = obs('START')
    body += check('actual_private_sovereign_country_inputs', ''.join(scope(t, 'exists = yes is_subject = no any_owned_state = { always = yes } ') for t in MEMBERS), 'Representative native countries exist before private fixture admission; no synthetic country IDs')
    body += 'set_global_flag = { flag = eon_eu_daily_lifecycle_done days = 180 value = 1 } set_global_flag = eon_eu_registry_refreshing '
    body += ''.join(setv(prefix + name, 0) for name in ('daily_callbacks', 'daily_open_callbacks', 'daily_elapsed_callbacks', 'daily_captured_snapshots', 'daily_resolutions'))
    body += 'set_global_flag = ' + trace_flag + ' '
    body += 'every_country = { set_country_flag = eon_eu_leaving_in_progress remove_ideas = EU_member clr_country_flag = eon_eu_leaving_in_progress eon_eu_clear_country_access = yes } '
    body += 'clr_global_flag = eon_eu_dormant clr_global_flag = GAME_RULE_eu_disabled '
    body += ''.join(seed(t) for t in MEMBERS) + 'clr_global_flag = eon_eu_registry_refreshing eon_eu_refresh_membership = yes eon_eu_close_institutions = yes '
    body += check('fixture_admission_guard_and_registry', 'has_global_flag = eon_eu_admission_guard_ready ' + cv('global.EU_member_count', 6) + ''.join(scope(t, 'eon_eu_is_active_member = yes has_country_flag = eon_eu_membership_recognized ') for t in MEMBERS), 'Explicit one-use private admissions pass actual production callbacks, without disabling the guard')
    body += law_reset() + scope('FRA', 'eon_eu_appoint_office_1 = yes ') + schedule(7010, 2, 'FRA'); event(7000, body)
    body = check('proposal_country_event_root_is_actual_actor', 'tag = FRA ROOT = { tag = FRA } ', 'Actual frontend script is invoked with native ROOT=FRA, not a scoped country under NEP ROOT')
    body += propose('FRA')
    body += check('actual_proposal_opens_real_fourteen_day_round', 'has_global_flag = eon_eu_council_vote_deadline eon_eu_council_round_identity_current = yes ' + cv('global.eon_eu_council_vote_owner', 'FRA.id') + scope('FRA', 'has_active_mission = ' + RESULT + ' ' + cv('days_mission_timeout@' + RESULT, 14)), 'Source GUI callback invokes guarded actual proposal, canonical identity and native14-day mission; no handseeded clock/outcome')
    body += cast() + check('actual_source_ballots_produce_pass_before_deadline', cv('global.EU_active_vote_yes', 6) + cv('global.eon_eu_council_open_outcome_yes', 1), 'All six actual guarded callbacks compute the open tally; no private pass/fail variable writes')
    body += setv(prefix + 'original_deadline_day', 'global.eon_eu_council_vote_deadline_day') + state('REAL14_START') + clocks('REAL14_START_CLOCK')
    body += schedule(7001, 145, 'FRA'); event(7010, body)

    body = state('TRANSFER_AFTER_SIX_DAYS') + clocks('TRANSFER_BEFORE_CLOCK')
    body += check('original_window_still_open_after_six_days', 'has_global_flag = eon_eu_council_vote_deadline ' + cv('global.current_active_vote_disp', 101), 'Actual six days elapse with the original14-day window still positive')
    body += scope('FRA', 'remove_ideas = EU_commission_president ') + scope('ITA', 'eon_eu_appoint_office_1 = yes ') + 'eon_eu_reconcile_council_vote_owner = yes '
    body += check('lawful_transfer_preserves_original_deadline', cv('global.eon_eu_council_vote_owner', 'ITA.id') + cv('global.eon_eu_council_vote_deadline_day', prefix + 'original_deadline_day') + scope('ITA', 'has_active_mission = ' + RESULT + ' ' + cv('days_mission_timeout@' + RESULT, 0, 'greater_than') + cv('days_mission_timeout@' + RESULT, 9, 'less_than')), 'Source handoff keeps original flag/date and arms current owner with remaining time, rather than a fresh14-day mandate')
    body += clocks('TRANSFER_AFTER_CLOCK') + schedule(7002, 217, 'ITA'); event(7001, body)
    elapsed.append({'start_observation': 'COUNCIL_REAL14_START', 'end_observation': 'COUNCIL_TRANSFER_AFTER_SIX_DAYS', 'minimum_hours': 144})

    body = state('REAL14_AFTER_FIFTEEN_DAYS') + clocks('REAL14_END_CLOCK')
    body += check('natural_real14_source_timeout_applies_law_once', 'NOT = { has_global_flag = eon_eu_council_vote_deadline } ' + cv('global.current_active_vote_disp', 0) + law_passed() + scope('ITA', 'has_country_flag = focus_EU101_QMV_yes '), 'Actual native mission callbacks or declared scheduled production daily fallback enact EU101 on lawful successor after original14-day deadline; private event invokes no finishing helper in this trace')
    body += check('successor_new_proposal_has_actual_actor_root', 'tag = ITA ROOT = { tag = ITA } ', 'Second source proposal uses actual native successor ROOT=ITA')
    body += law_reset() + propose('ITA') + cast()
    body += setv(prefix + 'fresh_instance', 'global.eon_eu_council_vote_instance') + setv(prefix + 'fresh_deadline_day', 'global.eon_eu_council_vote_deadline_day')
    body += scope('ITA', 'eon_eu_council_result_timeout = yes eon_eu_council_result_complete = yes ') + scope('HOL', 'eon_eu_council_timer_timeout = yes ')
    body += check('overwritten_same_owner_generic_old_wakeups_are_inert', 'has_global_flag = eon_eu_council_vote_deadline ' + cv('global.current_active_vote_disp', 101) + cv('global.eon_eu_council_vote_instance', prefix + 'fresh_instance') + cv('global.eon_eu_council_vote_deadline_day', prefix + 'fresh_deadline_day') + 'NOT = { is_in_array = { array = global.EU_passed_votes value = 101 } } ' + scope('ITA', 'has_active_mission = ' + RESULT + ' ' + cv('eon_eu_council_mission_instance', 'global.eon_eu_council_vote_instance') + cv('days_mission_timeout@' + RESULT, 0, 'greater_than')) + scope('HOL', 'has_active_mission = ' + TIMER + ' '), 'Adversarial direct generic wakeups see NEW mutable owner vars but cannot enact or remove actual positive new-round missions; immutable queued payload is not claimed')
    body += cast(MEMBERS[:3], MEMBERS[3:]) + check('three_of_six_failure_is_computed_while_open', cv('global.EU_active_vote_yes', 3) + cv('global.EU_active_vote_no', 3) + cv('global.eon_eu_council_open_outcome_yes', 0), 'Actual callbacks compute a failed3/6 tally before vacancy and natural expiry')
    body += scope('ITA', 'remove_ideas = EU_commission_president ') + 'eon_eu_reconcile_office_holders = yes '
    body += state('VACANCY14_START') + clocks('VACANCY14_START_CLOCK') + schedule(7003, 361); event(7002, body)
    elapsed.append({'start_observation': 'COUNCIL_REAL14_START', 'end_observation': 'COUNCIL_REAL14_AFTER_FIFTEEN_DAYS', 'minimum_hours': 336})

    body = state('VACANCY14_AFTER_FIFTEEN_DAYS') + clocks('VACANCY14_END_CLOCK')
    body += check('native_deadline_snapshots_failure_during_vacancy', 'NOT = { has_global_flag = eon_eu_council_vote_deadline } ' + cv('global.current_active_vote_disp', 101) + 'eon_eu_council_deadline_outcome_current = yes ' + cv('global.eon_eu_council_outcome_yes', 0), 'Actual native timeout or declared scheduled production daily fallback witnesses natural expiry and freezes failure; no synthetic deadline expiry or private-event capture')
    body += scope('HOL', 'eon_eu_support_council_vote = yes ') + scope('SPR', 'eon_eu_abstain_council_vote = yes ') + 'eon_eu_council_ai_pulse = yes '
    body += check('late_actual_ballot_and_ai_callbacks_are_closed', cv('global.EU_active_vote_yes', 3) + cv('global.EU_active_vote_no', 3) + cv('global.eon_eu_council_abstainers^num', 0), 'Support/abstain/AI actual source callbacks cannot change the deadline tally after natural expiry')
    body += scope('HOL', 'leaving_EU = yes ') + scope('SPR', 'leaving_EU = yes ') + 'eon_eu_recount_council_vote = yes '
    body += check('later_membership_loss_cannot_turn_failure_into_pass', cv('global.eon_eu_voters', 4) + cv('global.EU_active_vote_yes', 3) + cv('global.eon_eu_yes_fraction', .75) + 'eon_eu_council_vote_passes = no ' + cv('global.eon_eu_council_outcome_yes', 0), 'Live3/4 electorate changes would pass ordinary QMV, but source frozen3/6 deadline failure remains authoritative')
    body += scope('GER', 'eon_eu_appoint_office_1 = yes ') + 'eon_eu_reconcile_council_vote_owner = yes '
    body += check('resumed_authority_finishes_frozen_failure_without_law', cv('global.current_active_vote_disp', 0) + 'NOT = { is_in_array = { array = global.EU_passed_votes value = 101 } } ' + ''.join(scope(t, 'NOT = { has_idea = EUU_cfr_eu } ') for t in MEMBERS[:3]), 'Actual lawful successor finishes once and cannot re-evaluate live counts into law')
    body += seed('HOL') + seed('SPR') + 'eon_eu_refresh_membership = yes '
    body += legacy_input(5, 3) + cast()
    body += check('legacy_dual_actual_native_clocks_before_migration', scope('GER', 'has_active_mission = ' + RESULT + ' ' + cv('days_mission_timeout@' + RESULT, 5)) + scope('HOL', 'has_active_mission = ' + TIMER + ' ' + cv('days_mission_timeout@' + TIMER, 3)) + 'NOT = { has_global_flag = eon_eu_council_vote_clock_started } ', 'Declared old-save native mission inputs are calibrated additively5/3 only after activation, without restarting an existing timer')
    body += 'eon_eu_reconcile_council_vote_owner = yes '
    body += check('legacy_dual_earliest_clock_is_preserved_by_source', 'has_global_flag = eon_eu_council_vote_deadline eon_eu_council_round_identity_current = yes ' + scope('GER', cv('days_mission_timeout@' + RESULT, 3)), 'Actual source adopts earliest3-day clock and calibrates real result mission; no fresh14-day deadline')
    body += state('LEGACY_DUAL_START') + clocks('LEGACY_DUAL_START_CLOCK') + schedule(7004, 73); event(7003, body)
    elapsed.append({'start_observation': 'COUNCIL_VACANCY14_START', 'end_observation': 'COUNCIL_VACANCY14_AFTER_FIFTEEN_DAYS', 'minimum_hours': 336})

    body = state('LEGACY_DUAL_AFTER_THREE_DAYS') + clocks('LEGACY_DUAL_END_CLOCK')
    body += check('legacy_dual_natural_expiry_finishes_at_earliest_original_time', cv('global.current_active_vote_disp', 0) + 'NOT = { has_global_flag = eon_eu_council_vote_deadline } ' + law_passed(), 'Source-adopted real3-day deadline expires naturally and scheduled source mission/daily continuation completes; no private-event finishing call')
    body += legacy_input(None, 1) + cast() + 'eon_eu_reconcile_council_vote_owner = yes '
    body += check('legacy_sole_timer_transfers_clock_without_enactment', 'has_global_flag = eon_eu_council_vote_deadline ' + cv('global.current_active_vote_disp', 101) + scope('GER', 'has_active_mission = ' + RESULT + ' ' + cv('days_mission_timeout@' + RESULT, 1)) + 'NOT = { is_in_array = { array = global.EU_passed_votes value = 101 } } ', 'A sole native member timer provides one-day clock while only current Commission owns law authority')
    body += state('LEGACY_SOLE_START') + clocks('LEGACY_SOLE_START_CLOCK') + schedule(7005, 30); event(7004, body)
    elapsed.append({'start_observation': 'COUNCIL_LEGACY_DUAL_START', 'end_observation': 'COUNCIL_LEGACY_DUAL_AFTER_THREE_DAYS', 'minimum_hours': 72})

    body = state('LEGACY_SOLE_AFTER_ONE_DAY') + clocks('LEGACY_SOLE_END_CLOCK')
    body += check('legacy_sole_native_clock_really_finishes', cv('global.current_active_vote_disp', 0) + law_passed(), 'Actual source-armed one-day clock expires naturally; completion is by actual mission callback or declared scheduled source daily continuation')
    body += check('actual_private_on_daily_calls_production_fallback', cv(prefix + 'daily_callbacks', 28, 'greater_than_or_equals') + cv(prefix + 'daily_open_callbacks', 0, 'greater_than'), 'Actual merged native on_daily runs both source helpers throughout the genuine windows; route counters distinguish fallback from mission completion rather than assuming callback order')
    body += obs('DAILY_FALLBACK_ROUTE_RECEIPT', 'callbacks=[?' + prefix + 'daily_callbacks] open=[?' + prefix + 'daily_open_callbacks] elapsed=[?' + prefix + 'daily_elapsed_callbacks] snapshots=[?' + prefix + 'daily_captured_snapshots] resolutions=[?' + prefix + 'daily_resolutions]')
    body += setv(prefix + 'daily_callbacks_at_disable', prefix + 'daily_callbacks') + 'clr_global_flag = ' + trace_flag + ' '
    body += legacy_input(1, None) + cast()
    body += check('legacy_callback_before_first_migration_remains_original', 'NOT = { has_global_flag = eon_eu_council_vote_clock_started } ' + scope('GER', 'has_active_mission = ' + RESULT + ' ' + cv('days_mission_timeout@' + RESULT, 1)), 'Old-save original1-day result clock remains unadopted; no manual migration/capture before its native callback')
    body += state('LEGACY_PRE_DAILY_START') + clocks('LEGACY_PRE_DAILY_START_CLOCK') + schedule(7006, 30); event(7005, body)
    elapsed.append({'start_observation': 'COUNCIL_LEGACY_SOLE_START', 'end_observation': 'COUNCIL_LEGACY_SOLE_AFTER_ONE_DAY', 'minimum_hours': 24})

    body = state('LEGACY_PRE_DAILY_AFTER_ONE_DAY') + clocks('LEGACY_PRE_DAILY_END_CLOCK')
    body += check('native_original_legacy_callback_has_no_daily_fallback', cv(prefix + 'daily_callbacks', prefix + 'daily_callbacks_at_disable') + 'NOT = { has_global_flag = ' + trace_flag + ' } ', 'Private source daily fallback is disabled before this original native timeout and its counter remains unchanged; this control cannot pass through first daily migration')
    body += check('genuine_legacy_native_callback_before_daily_never_restarts_clock', cv('global.current_active_vote_disp', 0) + 'NOT = { has_global_flag = eon_eu_council_vote_deadline } ' + law_passed(), 'Actual native old result timeout before first manual/daily migration supplies elapsed receipt and resolves without new14-day flag')
    body += obs('TERMINAL') + terminal_effect; event(7006, body)
    elapsed.append({'start_observation': 'COUNCIL_LEGACY_PRE_DAILY_START', 'end_observation': 'COUNCIL_LEGACY_PRE_DAILY_AFTER_ONE_DAY', 'minimum_hours': 24})

    contract = {'countries': list(MEMBERS), 'reserved_event_range': [7000, 7199],
                'real_fourteen_day_traces': 2, 'fixed_mission_ids': [RESULT, TIMER],
                'canonical_deadline_manually_expired': False, 'outcome_values_written_by_fixture': False,
                'true_scheduler_result_required': True, 'adversarial_wakeup_is_direct_source_call': True,
                'claim_of_immutable_callback_payload': False, 'ui_click_verified': False,
                'original_golden144_predicates_unchanged': True,
                'baseline_v12_contract_sha256': '0a8c1fd1f2c8704b9a81573b7151cb2dd00265607c5711ef31ef20b858113602'}
    contract['daily_fallback'] = {'effect_field': 'on_daily_effect', 'private_trace_flag': trace_flag,
                                  'source_helpers_in_order': ['eon_eu_capture_council_deadline_outcome', 'eon_eu_reconcile_council_vote_owner'],
                                  'repeated_before_observation': 'COUNCIL_DAILY_BEFORE', 'repeated_after_observation': 'COUNCIL_DAILY_AFTER',
                                  'callback_counter': prefix + 'daily_callbacks', 'minimum_callbacks_at_checkpoint': 28,
                                  'route_receipt_observation': 'COUNCIL_DAILY_FALLBACK_ROUTE_RECEIPT',
                                  'last_legacy_case_fallback_disabled': True, 'full_world_coordinator_claim': False}
    module = {'fixture_text': {f'events/{namespace}.txt': 'add_namespace = ' + namespace + '\n' + ''.join(events.values())},
              'entry_event_id': f'{namespace}.7000', 'terminal_event_id': f'{namespace}.7006', 'entry_effect': schedule(7000, 2),
              'on_daily_effect': on_daily,
              'assertions': labels, 'expectations': expectations,
              'assertion_records': [{'label': n, **expectations[n]} for n in labels],
              'observations': observations, 'required_observations': observations,
              'required_elapsed_game_time': elapsed, 'events': len(events),
              'production_dependency_paths': list(DEPENDENCIES), 'production_input_sha256': bound['production_input_sha256'],
              'calibrations': calibrations, 'contract': contract,
              'limits': ['Private recognized member/office/agenda availability inputs, not Article49 or EP pipeline acceptance',
                         'Source GUI callback AST is executed as script; actual UI click/rendering is still a separate acceptance gate',
                         'Two actual14-day windows plus native3/1/1-day old-save calibrations; no manual canonical expiry or synthetic outcome',
                         'Positive newer-window adversarial wakeup uses direct current source callbacks, not a proven queued native payload',
                         'Broad coordinator lock held180days; merged private actual on_daily calls the exact two source Council helpers, with before/after route receipts; full world coordinator scheduling is separate',
                         'Last original legacy timeout-before-first-migration trace disables that private fallback and requires unchanged actual daily counter',
                         'No game/source/public tool/config/Workshop/save action from this builder']}
    validate_contract(module, namespace)
    return module

def validate_contract(module, namespace):
    fixture = module['fixture_text']
    assert set(fixture) == {f'events/{namespace}.txt'}, 'Must merge into the existing five assets'
    text = fixture[f'events/{namespace}.txt']
    daily = module.get('on_daily_effect', '')
    daily_nodes = list(walk(ast(daily)))
    daily_body = one(ast(daily), 'if')
    assert one(daily_body, 'limit') == [('has_global_flag', '=', namespace + '_council_scheduler_trace')], 'Daily fallback must be private-trace gated'
    daily_keys = [k for k, _, _ in daily_nodes]
    for helper in ('eon_eu_capture_council_deadline_outcome', 'eon_eu_reconcile_council_vote_owner'):
        assert daily_keys.count(helper) == 1, 'Scheduled daily fallback must execute each actual source helper exactly once'
    assert daily_keys.index('eon_eu_capture_council_deadline_outcome') < daily_keys.index('eon_eu_reconcile_council_vote_owner'), 'Daily capture must precede reconciliation'
    assert ('has_global_flag', '=', namespace + '_council_scheduler_trace') in daily_nodes, 'Daily fallback must be private-trace gated'
    labels = module['assertions']
    assert len(labels) == len(set(labels)) and set(module['expectations']) == set(labels)
    assert len(module['observations']) == len(set(module['observations']))
    for key, _, body in ast(text):
        if key != 'country_event': continue
        number = int(one(body, 'id').split('.')[-1]); assert 7000 <= number <= 7199
        for k, _, v in walk(body):
            if k == 'clr_global_flag': assert v != 'eon_eu_council_vote_deadline', 'Never manually expire canonical clock'
            if k in ('set_variable', 'add_to_variable', 'set_global_flag'):
                assert not any(n[0].startswith('global.eon_eu_council_') for n in v) if isinstance(v, list) else True, 'Never seed canonical identity/deadline/computed result'
                if k == 'set_global_flag' and isinstance(v, list): assert one(v, 'flag') != 'eon_eu_council_vote_deadline', 'Real proposal owns its14-day flag'
    for k, _, v in daily_nodes:
        if k == 'clr_global_flag': assert v != 'eon_eu_council_vote_deadline', 'Never manually expire canonical clock'
        if k in ('set_variable', 'add_to_variable') and isinstance(v, list):
            assert not any(n[0].startswith('global.eon_eu_council_') for n in v), 'Never seed canonical identity/deadline/computed result'
        if k == 'set_global_flag' and isinstance(v, list):
            assert one(v, 'flag') != 'eon_eu_council_vote_deadline', 'Real proposal owns its14-day flag'
    final_setup = next(body for key, _, body in ast(text) if key == 'country_event' and one(body, 'id') == namespace + '.7005')
    assert ('clr_global_flag', '=', namespace + '_council_scheduler_trace') in list(walk(final_setup)), 'Disable daily fallback before last legacy native callback'
    native_checks = module['expectations']
    counter_predicate = native_checks['council_native_actual_private_on_daily_calls_production_fallback']['predicate']
    counter_comparisons = [v for k, _, v in walk(ast(counter_predicate)) if k == 'check_variable']
    assert [('var', '=', 'global.' + namespace + '_council_private_daily_callbacks'), ('value', '=', '28'), ('compare', '=', 'greater_than_or_equals')] in counter_comparisons, 'Actual native daily counter remains bounded at28'
    starts = {row['start_observation']: row['minimum_hours'] for row in module['required_elapsed_game_time']}
    assert starts['COUNCIL_REAL14_START'] >= 336 and starts['COUNCIL_VACANCY14_START'] >= 336, 'Two genuine14-day minima remain strict'
