"""Actual EDU decision/callback native controls; never launch or install a probe.

This source-bound fixture uses actual activate_decision/activate_targeted_decision.
It never copies complete_effect or directly calls the creation/admission helpers.
Formation/leave/leadership assertions remain failures if the native hooks do not
run. A passing model cannot substitute for these native controls.
"""
from pathlib import Path
import hashlib
import re
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/validation/diplomacy_package_02'))
from _treaty_support import ast,one

F='AUS'; A='SWE'; B='FIN'
SOURCE_PATHS=(
 'common/scripted_effects/eon_edu_effects.txt','common/scripted_triggers/eon_edu_triggers.txt',
 'common/decisions/eon_edu_decisions.txt','common/on_actions/eon_edu_on_actions.txt',
 'events/eon_edu_events.txt','localisation/english/eon_edu_l_english.yml',
 'localisation/russian/eon_edu_l_russian.yml','common/decisions/EU_voting_decisions.txt',
 'common/scripted_triggers/00_game_rule_triggers.txt','common/scripted_effects/00_eu_scripted_effects.txt',
 'common/scripted_effects/eon_eu_lifecycle_effects.txt','common/scripted_effects/eon_eu_membership_effects.txt',
 'common/scripted_triggers/eon_eu_membership_triggers.txt','common/scripted_triggers/eon_defensive_alliance_triggers.txt',
 'common/scripted_triggers/99_EU_scripted_triggers.txt','common/factions/templates/00_EU.txt',
 'common/scripted_triggers/00_influence_scripted_triggers.txt')

def build_edu(namespace,marker,*,terminal_effect='',source=ROOT):
    source=Path(source).resolve()
    assert re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',namespace)
    assert re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',marker)
    decisions={k:v for k,o,v in one(ast((source/SOURCE_PATHS[2]).read_text('utf-8-sig')),'EU_voting_category')}
    decisions['EU_create_EDU']=one(one(ast((source/SOURCE_PATHS[7]).read_text('utf-8-sig')),'EU_defense_category'),'EU_create_EDU')
    callbacks={'EU_create_EDU':'eon_edu_create_decision_effect','eon_edu_request_join':'eon_edu_request_join_effect',
      'eon_edu_accept_request':'eon_edu_accept_request_effect','eon_edu_reject_request':'eon_edu_reject_request_effect',
      'eon_edu_withdraw_request':'eon_edu_withdraw_request_effect'}
    for ident,helper in callbacks.items():
        assert one(decisions[ident],'complete_effect')==[(helper,'=','yes')],(ident,'callback drift')
    events,assertions,expectations,observations,elapsed={},[],{},[],[]
    prefix='global.'+namespace+'_edu_'
    def cv(name,value,compare='equals'):
        return f'check_variable = {{ var = {name} value = {value} compare = {compare} }} '
    def setv(name,value): return f'set_variable = {{ {name} = {value} }} '
    def scope(tag,body): return f'{tag} = {{ {body} }} '
    def schedule(tag,n,hours=2): return scope(tag,f'country_event = {{ id = {namespace}.{n} hours = {hours} }} ')
    def event(n,body):
        assert 3000<=n<=3099 and n not in events
        events[n]=f'country_event = {{ id = {namespace}.{n} hidden = yes is_triggered_only = yes immediate = {{ {body} }} }}\n'
    def check(label,predicate,why):
        label='edu_'+label; assert label not in expectations
        assertions.append(label); expectations[label]={'predicate':predicate,'expected':why}
        return (f'log = "{marker} BEGIN {label}" if = {{ limit = {{ {predicate} }} '
          f'log = "{marker} PASS {label}" add_to_variable = {{ global.{namespace}_passes = 1 }} }} '
          f'else = {{ log = "{marker} FAIL {label}" add_to_variable = {{ global.{namespace}_fails = 1 }} }} '
          f'log = "{marker} END {label}" ')
    def obs(label,values=''):
        label='EDU_'+label; assert label not in observations; observations.append(label)
        return f'log = "{marker} OBS {label} date=[?global.date] {values}" '
    def bool_obs(label,predicate):
        label='EDU_'+label; assert label not in observations; observations.append(label)
        return (f'if = {{ limit = {{ {predicate} }} log = "{marker} OBS {label} value=1" }} '
          f'else = {{ log = "{marker} OBS {label} value=0" }} ')
    def native_crisis_input(label):
        # Explicit fixture input, replacing the original readonly shadow write.
        # Actual getter/native trigger controls prove the input, not the setter.
        text=setv('eon_private_edu_original_threat','global.threat')
        text+=obs(label+'_THREAT_BEFORE','threat=[?global.threat] threshold=[?modifier@join_faction_tension]')
        text+=f'log = "{marker} TRACE EDU_{label}_DECLARED_NATIVE_CRISIS_INPUT actor=[?ROOT.id] scope=[?THIS.id] country_threat_points=100 boundary=artificial_private_crisis" '
        text+='add_threat = 100 '
        text+=obs(label+'_THREAT_AFTER','threat=[?global.threat] threshold=[?modifier@join_faction_tension]')
        text+=bool_obs(label+'_NATIVE_TENSION_GETTER_INCREASED','check_variable = { var = global.threat value = eon_private_edu_original_threat compare = greater_than } ')
        text+=bool_obs(label+'_NATIVE_TENSION_DIRECT_TRIGGER_ABOVE_99_PERCENT','threat > 0.99 ')
        text+=check(label.lower()+'_declared_native_crisis_input','threat > 0.99 '+cv('global.threat',0.99,'greater_than')+cv('global.threat','eon_private_edu_original_threat','greater_than_or_equals'),
          'Declared private country threat input reaches actual native world tension above99percent without reducing its original getter; readonly shadow writes cannot prove this condition')
        return text

    def prerequisite_diagnostics(label):
        text='set_temp_variable = { eon_private_edu_join_threshold = modifier@join_faction_tension } '
        text+=obs(label+'_COUNTERS','actor=[?ROOT.id] scope=[?THIS.id] sender=[?FROM.id] '
          'member_count=[?global.EU_member_count] registry_count=[?global.EU_member^num] '
          'threat=[?global.threat] threshold=[?eon_private_edu_join_threshold] '
          'foreign_holder=[?global.euforeignaffairs] intent=[?eon_edu_creation_intent] '
          'pending_actor=[?global.eon_edu_creation_actor] instance=[?global.eon_edu_instance]')
        gates=(('ACTIVE','eon_eu_is_active_member = yes'),
          ('RECOGNIZED','has_country_flag = eon_eu_membership_recognized'),
          ('MEMBER_IDEA','has_idea = EU_member'),
          ('IN_REGISTRY','is_in_array = { global.EU_member = THIS }'),
          ('LIVE','exists = yes'),('OWNS_STATE','any_owned_state = { always = yes }'),
          ('SOVEREIGN','is_subject = no'),('FACTIONLESS','is_in_faction = no'),
          ('JOIN_PERMISSION','has_rule = can_join_factions'),('NO_OFFENSIVE_WAR','has_offensive_war = no'),
          ('NO_BLR_NEUTRALITY','NOT = { has_idea = BLR_neutrality_politic }'),
          ('THREAT_THRESHOLD','check_variable = { var = global.threat value = eon_private_edu_join_threshold compare = greater_than_or_equals }'),
          ('SEC','has_idea = European_Security_Council'),('FOREIGN_MINISTER','has_idea = EU_foreign_minister'),
          ('INFLUENCE','influence_on_all_other_EU_members_25_percent = yes'),
          ('NO_EDU','NOT = { has_global_flag = EDU }'),
          ('NO_PENDING_ACTOR','check_variable = { global.eon_edu_creation_actor = 0 }'),
          ('DEFENSIVE_ELIGIBLE','eon_defensive_alliance_member_eligible = yes'),
          ('FOUNDER_ELIGIBLE','eon_edu_founder_eligible = yes'))
        for key,predicate in gates:text+=bool_obs(label+'_'+key,predicate+' ')
        return text

    def activate(ident,target=None):
        assert ident in callbacks
        return (f'activate_targeted_decision = {{ target = {target} decision = {ident} }} ' if target
                else f'activate_decision = {ident} ')
    def seed(tag):
        return scope(tag,'if = { limit = { NOT = { has_idea = EU_member } } '
          'set_country_flag = eon_eu_admission_commit add_ideas = EU_member } '
          'remove_ideas = EUU_voting_rights_suspended clr_country_flag = eon_edu_request_cooldown ')
    def nato_control(label):
        return check(label,scope('USA','is_in_faction = yes ')+scope('POL','is_in_faction_with = USA ')+
          scope('USA',scope('faction_leader',cv('THIS.id',prefix+'nato_leader'))),
          'Unrelated actual USA/POL faction and captured leader remain unchanged; no metadata/name substitute')
    def native_membership(label):
        return check(label,scope(F,'is_faction_leader = yes eon_edu_is_confirmed_member = yes ')+
          scope(A,'is_in_faction_with = AUS eon_edu_is_confirmed_member = yes '),
          'Real targeted accept decision completed actual membership and cohort after current pair consent')
    def clock(label): return obs(label,'raw=[?global.date]')

    body=obs('START','actor=[?THIS.id] founder=[?AUS.id] candidate=[?SWE.id] other=[?FIN.id]')
    body+=check('live_private_countries',' '.join(scope(t,'exists = yes is_subject = no any_owned_state = { always = yes } is_in_faction = no ') for t in (F,A,B)),
      'Actual Austria, Sweden and Finland are sovereign state owners outside factions before private setup; no forced NATO exit')
    body+=check('nato_positive_before_mutations',scope('USA','is_in_faction = yes ')+scope('POL','is_in_faction_with = USA '),
      'Positive actual unrelated NATO pair before EDU setup; factionless controls cannot pass')
    body+=scope('USA',scope('faction_leader',setv(prefix+'nato_leader','THIS.id')))
    # Declare lawful fixture origins; this is not historical/Article49 proof.
    body+='set_global_flag = { flag = eon_eu_daily_lifecycle_done days = 180 value = 1 } set_global_flag = eon_eu_registry_refreshing '
    body+='every_country = { set_country_flag = eon_eu_leaving_in_progress remove_ideas = EU_member clr_country_flag = eon_eu_leaving_in_progress eon_eu_clear_country_access = yes } '
    body+='clr_global_flag = eon_eu_dormant clr_global_flag = GAME_RULE_eu_disabled clr_global_flag = usoe_formed '
    body+=seed(F)+'clr_global_flag = eon_eu_registry_refreshing eon_eu_refresh_membership = yes '
    body+='add_ideas = European_Security_Council add_ideas = EU_foreign_minister '
    body+=prerequisite_diagnostics('FOUNDER_BEFORE_ANY_CALIBRATION')
    # Exact source-derived conjunction with only can_join excluded. This
    # declared fixture calibration cannot repair any other failed prerequisite.
    defensive=one(ast((source/'common/scripted_triggers/eon_defensive_alliance_triggers.txt').read_text('utf-8-sig')),'eon_defensive_alliance_member_eligible')
    edu=one(ast((source/'common/scripted_triggers/eon_edu_triggers.txt').read_text('utf-8-sig')),'eon_edu_founder_eligible')
    founder=one(edu,'custom_trigger_tooltip')
    assert defensive.count(('has_rule','=','can_join_factions'))==1
    assert founder.count(('eon_edu_candidate_eligible','=','yes'))==1
    def render_gate(nodes):
        return ' '.join(f'{key} {op} '+('{ '+render_gate(value)+' }' if isinstance(value,list) else value) for key,op,value in nodes)
    no_permission_gate=[node for node in defensive if node!=('has_rule','=','can_join_factions')]
    body+=native_crisis_input('INITIAL')
    body+=prerequisite_diagnostics('FOUNDER_AFTER_CONDITIONAL_NATIVE_TENSION_CALIBRATION')
    no_permission_gate+=[node for node in founder if node[0] not in ('tooltip','eon_edu_candidate_eligible')]
    no_permission_gate+=[('eon_eu_is_active_member','=','yes'),('NOT','=',[('has_rule','=','can_join_factions')])]
    no_permission_gate+=[('check_variable','=',[('global.EU_member_count','=','1')])]
    body+='if = { limit = { '+render_gate(no_permission_gate)+' } '
    body+=f'log = "{marker} TRACE EDU_DECLARED_INITIAL_PERMISSION_CALIBRATION actor=[?ROOT.id] scope=[?THIS.id] original_join_permission=0 all_other_founder_prerequisites=1" '
    body+='set_rule = { can_join_factions = yes } } '
    body+=prerequisite_diagnostics('FOUNDER_AFTER_CONDITIONAL_PERMISSION_CALIBRATION')
    body+=check('actual_founder_frontend_available','tag = AUS eon_edu_founder_eligible = yes '+cv('global.EU_member_count',1),
      'Production founder gate is actually available under one-use recognized single-founder input; no can_create permission bypass')
    body+=setv(prefix+'initial_attempt','eon_edu_creation_attempt_serial')+setv(prefix+'initial_formed','eon_edu_formed_hook_serial')
    body+=activate('EU_create_EDU')
    body+=obs('ACTUAL_CREATE_RETURN','actor=[?THIS.id] scope=[?ROOT.id] sender=[?FROM.id] attempt=[?eon_edu_creation_attempt_serial] result=[?eon_edu_creation_result] intent=[?eon_edu_creation_intent] instance=[?global.eon_edu_instance] formed=[?eon_edu_formed_hook_serial]')
    body+=check('actual_non_targeted_callback_attempt',cv('eon_edu_creation_attempt_serial',prefix+'initial_attempt','greater_than'),
      'Actual activate_decision executes production CREATE_DECISION actor callback; no copied complete_effect/helper fallback')
    body+=check('constructor_return_never_fabricates_identity',
      'OR = { AND = { '+cv('eon_edu_creation_result',1)+'is_in_faction = yes is_faction_leader = yes eon_edu_is_confirmed_member = yes } '
      +'AND = { '+cv('eon_edu_creation_result',3)+'is_in_faction = yes '+cv('eon_edu_creation_intent',0,'greater_than')+'NOT = { has_global_flag = EDU } '+cv('eon_edu_member_instance',0)+' } '
      +'AND = { '+cv('eon_edu_creation_result',2)+'NOT = { has_global_flag = EDU } '+cv('eon_edu_member_instance',0)+' } } ',
      'Immediate synchronous success, uncommitted pending callback or clean constructor failure are the only permitted states; eventual success remains required')
    body+=clock('CREATION_CLOCK')+schedule(F,3001); event(3000,body)

    body=clock('CREATION_AFTER_HOUR')+check('actual_formed_hook_commits_after_decision',
      'tag = AUS is_faction_leader = yes eon_edu_is_confirmed_member = yes '+cv('eon_edu_creation_result',1)+
      cv('eon_edu_creation_intent',0)+cv('global.eon_edu_creation_actor',0)+
      cv('eon_edu_formed_hook_serial',prefix+'initial_formed','greater_than'),
      'Actual native on_faction_formed commits bound actor/serial; missing or wrong-scope hooks fail the feature')
    body+=setv(prefix+'first_instance','global.eon_edu_instance')+seed(A)+seed(B)+'eon_eu_refresh_membership = yes '
    body+=scope(A,prerequisite_diagnostics('CANDIDATE_AFTER_LAWFUL_SEED'))+scope(B,prerequisite_diagnostics('OTHER_AFTER_LAWFUL_SEED'))
    body+=check('new_eu_members_not_auto_pulled',scope(A,'is_in_faction = no eon_edu_candidate_eligible = yes ')+scope(B,'is_in_faction = no eon_edu_candidate_eligible = yes '),
      'Explicit legal EU inputs are eligible and factionless; EU membership alone does not join the defence union')
    body+=nato_control('nato_unchanged_after_creation')+schedule(A,3002); event(3001,body)
    elapsed.append({'start_observation':'EDU_CREATION_CLOCK','end_observation':'EDU_CREATION_AFTER_HOUR','minimum_hours':1})

    body=check('request_country_event_pair','tag = SWE FROM = { tag = AUS } ','Actual event sends candidate from founder; decision target remains explicitly AUS')
    body+=activate('eon_edu_request_join',F)
    body+=check('actual_request_has_bound_target_and_positive_deadline',cv('eon_edu_request_leader','AUS.id')+cv('eon_edu_request_instance','global.eon_edu_instance')+'has_country_flag = eon_edu_request_deadline is_in_faction = no ',
      'Actual targeted request callback binds current actor to real leader and positive42-day flag without admission')
    body+=schedule(F,3003); event(3002,body)
    body=check('accept_country_event_pair','tag = AUS FROM = { tag = SWE } ','Actual responding leader receives candidate country-event source')
    body+=activate('eon_edu_accept_request',A)+native_membership('actual_agreed_admission')
    body+=scope(A,check('request_closed_once_after_actual_join',cv('eon_edu_request_result',1)+cv('eon_edu_request_instance',0)+'has_country_flag = eon_edu_request_cooldown ',
      'Actual agreed join closes candidate request, records outcome and applies one positive cooldown'))
    body+=setv(prefix+'candidate_leave_before','SWE.eon_edu_leave_hook_serial')
    body+=scope(A,'remove_from_faction = THIS create_faction = "Private EDU unrelated control" ')
    body+=clock('RAW_REMOVE_CLOCK')+schedule(F,3004); event(3003,body)

    body=clock('RAW_REMOVE_AFTER_HOUR')+check('scripted_remove_fires_real_leave_cleanup',
      scope(A,cv('eon_edu_leave_hook_serial',prefix+'candidate_leave_before','greater_than')+cv('eon_edu_member_instance',0)+'is_faction_leader = yes NOT = { eon_edu_is_confirmed_member = yes } '),
      'Actual scripted removal clears departed cohort before same-country unrelated faction creation; absent hook is failure')
    body+=scope(A,'dismantle_faction = yes clr_country_flag = eon_edu_request_cooldown ')
    body+=schedule(A,3005); event(3004,body)
    elapsed.append({'start_observation':'EDU_RAW_REMOVE_CLOCK','end_observation':'EDU_RAW_REMOVE_AFTER_HOUR','minimum_hours':1})
    body=activate('eon_edu_request_join',F)+check('new_request_after_prior_departure',cv('eon_edu_request_round',2)+cv('eon_edu_request_instance','global.eon_edu_instance'),
      'Explicit new round after privately clearing cooldown is a current independent request')+schedule(F,3006); event(3005,body)
    body=activate('eon_edu_accept_request',A)+native_membership('actual_second_agreed_admission')
    body+=setv(prefix+'leadership_before','SWE.eon_edu_leadership_hook_serial')+scope(A,'set_faction_leader = yes ')
    body+=clock('TRANSFER_CLOCK')+schedule(A,3007); event(3006,body)

    body=clock('TRANSFER_AFTER_HOUR')+check('actual_native_leadership_hook_reconciles',
      'tag = SWE is_faction_leader = yes eon_edu_is_confirmed_member = yes is_in_faction_with = AUS '+
      cv('eon_edu_leadership_hook_serial',prefix+'leadership_before','greater_than')+scope(F,'is_faction_leader = no eon_edu_is_confirmed_member = yes '),
      'Actual set_faction_leader dispatches on_assume_faction_leadership and preserves actual identity; missing callback fails')
    body+='leaving_EU = yes '
    body+=check('actual_eu_exit_transfers_before_military_departure',
      'is_in_faction = no NOT = { has_idea = EU_member } '+cv('eon_edu_departure_result',1)+
      scope(F,'is_faction_leader = yes eon_edu_is_confirmed_member = yes '),
      'Actual legacy leaving_EU invokes current-country helper, transfers to real active member and completes native departure')
    body+=nato_control('nato_unchanged_after_leader_eu_exit')+schedule(B,3008); event(3007,body)
    elapsed.append({'start_observation':'EDU_TRANSFER_CLOCK','end_observation':'EDU_TRANSFER_AFTER_HOUR','minimum_hours':1})

    body=activate('eon_edu_request_join',F)+check('second_country_has_independent_request',cv('eon_edu_request_leader','AUS.id')+'has_country_flag = eon_edu_request_deadline is_in_faction = no ',
      'Another country can request current successor-led union without a global donor/application lock')+schedule(F,3009); event(3008,body)
    body=activate('eon_edu_reject_request',B)+scope(B,check('actual_rejection_closes_without_admission',cv('eon_edu_request_result',2)+cv('eon_edu_request_instance',0)+'is_in_faction = no ',
      'Actual targeted rejection closes current request without a native join'))+schedule(B,3010); event(3009,body)
    body='clr_country_flag = eon_edu_request_cooldown '+activate('eon_edu_request_join',F)+activate('eon_edu_withdraw_request')
    body+=check('actual_withdrawal_closes_current_request',cv('eon_edu_request_result',3)+cv('eon_edu_request_instance',0)+'is_in_faction = no ',
      'Actual non-targeted withdrawal closes the current request without admission')
    body+='clr_country_flag = eon_edu_request_cooldown '+activate('eon_edu_request_join',F)
    body+=check('actual_request_before_timer_calibration','has_country_flag = eon_edu_request_deadline '+cv('eon_edu_request_instance','global.eon_edu_instance'),
      'A real current42-day request exists before declared private one-day clock calibration')
    body+='set_country_flag = { flag = eon_edu_request_deadline days = 1 value = 1 } '
    body+=clock('REQUEST_EXPIRY_CLOCK')+schedule(B,3011,30); event(3010,body)
    body=clock('REQUEST_EXPIRY_AFTER_DAY')+check('natural_calibrated_request_flag_really_expired','NOT = { has_country_flag = eon_edu_request_deadline } ',
      'Positive one-day calibrated request flag ends naturally before a manual production pulse; not natural42-day campaign proof')
    body+='eon_edu_daily_pulse = yes '
    body+=check('expired_request_production_pulse_finishes',cv('eon_edu_request_result',4)+cv('eon_edu_request_instance',0)+'is_in_faction = no ',
      'Current production daily protocol finishes expired request with an actual expiry result and no join')
    body+='clr_country_flag = eon_edu_request_cooldown '+activate('eon_edu_request_join',F)+schedule(F,3012); event(3011,body)
    elapsed.append({'start_observation':'EDU_REQUEST_EXPIRY_CLOCK','end_observation':'EDU_REQUEST_EXPIRY_AFTER_DAY','minimum_hours':24})

    body=activate('eon_edu_accept_request',B)+check('third_country_agreed_before_dismantle',scope(B,'is_in_faction_with = AUS eon_edu_is_confirmed_member = yes '+cv('eon_edu_request_result',1)),
      'Actual reply admits third country before native dismantle coverage test')
    body+=setv(prefix+'founder_leave_before','eon_edu_leave_hook_serial')+setv(prefix+'other_leave_before','FIN.eon_edu_leave_hook_serial')
    # Declared adversarial pending-intent input, not a claim that the engine
    # naturally delayed this constructor. Native mutations/hooks stay real.
    body+=scope(B,setv('influence_array^0',F)+setv('influence_array_val^0',30))
    body+='add_to_variable = { global.eon_edu_generation_counter = 1 } '+setv('global.eon_edu_creation_actor','THIS.id')
    body+=setv('eon_edu_creation_intent','global.eon_edu_generation_counter')
    body+='set_country_flag = { flag = eon_edu_creation_deadline days = 1 value = 1 } '+setv('eon_edu_creation_result',3)
    body+=native_crisis_input('PENDING_COUNTEREXAMPLE')
    body+=check('adversarial_pending_input_is_bound_and_policy_valid','eon_edu_creation_intent_bound = yes eon_edu_creation_policy_still_valid = yes ',
      'Declared private pending receipt has an actual bound actor, live flag and valid policy before real destroy/recreate; no-hook counterexample cannot be hidden behind an invalid candidate')
    body+='dismantle_faction = yes create_faction = "Private same founder unrelated control" '
    body+=clock('DISMANTLE_CLOCK')+schedule(F,3013); event(3012,body)
    body=clock('DISMANTLE_AFTER_HOUR')+check('native_dismantle_clears_all_actual_member_receipts',
      cv('eon_edu_leave_hook_serial',prefix+'founder_leave_before','greater_than')+cv('eon_edu_member_instance',0)+
      scope(B,'is_in_faction = no '+cv('eon_edu_leave_hook_serial',prefix+'other_leave_before','greater_than')+cv('eon_edu_member_instance',0)),
      'Actual dismantle invokes leave cleanup for leader and member; this strict requirement exposes pending-recreation identity bypass')
    body+=check('same_founder_unrelated_recreation_is_not_edu','is_faction_leader = yes NOT = { eon_edu_is_confirmed_member = yes } '+cv('eon_edu_creation_intent',0),
      'Actual same-founder unrelated faction remains distinct after dismantle/recreation; no founder/name/global-flag identity')
    body+=check('pending_destroy_recreate_never_commits_foreign_instance',
      cv('global.eon_edu_instance',prefix+'first_instance')+cv('global.eon_edu_creation_actor',0)+cv('eon_edu_creation_result',2),
      'Real leave cleanup consumes private pending intent before unrelated formed callback; even a later cleanup cannot hide an incorrectly advanced foreign-instance receipt')
    body+='eon_edu_daily_pulse = yes '
    body+=check('reconciliation_preserves_unknown_faction','is_faction_leader = yes NOT = { has_global_flag = EDU } ',
      'Production pulse closes stale receipt without dismantling actual unrelated faction')
    body+=setv(prefix+'blocked_attempt','eon_edu_creation_attempt_serial')+activate('EU_create_EDU')
    body+=check('existing_faction_blocks_actual_create_callback','is_faction_leader = yes NOT = { has_global_flag = EDU } '+cv('eon_edu_creation_result',0)+
      cv('eon_edu_creation_attempt_serial',prefix+'blocked_attempt','greater_than'),
      'Actual native activation may bypass frontend visibility but production guard rejects existing-faction actor without false receipt')
    body+='dismantle_faction = yes set_rule = { can_join_factions = no } '+activate('EU_create_EDU')
    body+=check('national_join_prohibition_blocks_actual_creation','is_in_faction = no NOT = { has_global_flag = EDU } '+cv('eon_edu_creation_result',0),
      'Explicit private national-rule restriction remains authoritative in the actual callback; no permission bypass')
    body+='set_rule = { can_join_factions = yes } '+scope(B,'leaving_EU = yes ')+'eon_eu_refresh_membership = yes '
    body+=nato_control('nato_unchanged_after_destroy_recreate')
    body+=native_crisis_input('FRESH_CREATION')
    body+=check('fresh_single_founder_available_after_unrelated_cleanup','eon_edu_founder_eligible = yes '+cv('global.EU_member_count',1),
      'After actual unrelated cleanup and restored observed joining permission, real founder gate is available')
    body+=activate('EU_create_EDU')+clock('RECREATE_CLOCK')+schedule(F,3014); event(3013,body)
    elapsed.append({'start_observation':'EDU_DISMANTLE_CLOCK','end_observation':'EDU_DISMANTLE_AFTER_HOUR','minimum_hours':1})

    body=clock('RECREATE_AFTER_HOUR')+check('new_authorized_decision_gets_fresh_instance',
      'is_faction_leader = yes eon_edu_is_confirmed_member = yes '+cv('global.eon_edu_instance',prefix+'first_instance','greater_than')+cv('eon_edu_creation_intent',0),
      'Fresh actual decision and actual formed hook obtain a new serial; unrelated recreation never inherits previous instance')
    body+=schedule(F,3015); event(3014,body)
    body=''
    body+=bool_obs('HAS_NCNS','has_dlc = "No Compromise, No Surrender" ')
    body+=bool_obs('ACTUAL_CURRENT_EDU_TEMPLATE','has_faction_template = faction_template_edu ')
    body+='if = { limit = { has_dlc = "No Compromise, No Surrender" has_faction_template = faction_template_edu } '
    body+='every_faction_member = { clear_variable = eon_edu_member_instance } clear_variable = eon_edu_member_instance clr_global_flag = EDU '
    body+='eon_edu_adopt_legacy_template = yes } '
    body+=bool_obs('LEGACY_ADOPT_SUPPORTED_PATH','has_dlc = "No Compromise, No Surrender" has_faction_template = faction_template_edu eon_edu_is_confirmed_member = yes '+cv('eon_edu_legacy_adoption_serial',0,'greater_than'))
    body+=bool_obs('LEGACY_ADOPT_UNAVAILABLE_PATH','NOT = { has_faction_template = faction_template_edu } ')
    body+='eon_eu_reset_institutional_laws = yes '
    body+=check('actual_archive_dismantles_confirmed_union_before_clear','is_in_faction = no NOT = { has_global_flag = EDU } '+cv('eon_edu_member_instance',0),
      'Actual shared archive seam dismantles confirmed native union before clearing receipts and unrelated laws')
    body+=nato_control('nato_unchanged_after_actual_archive')+obs('TERMINAL','instance=[?global.eon_edu_instance] counter=[?global.eon_edu_generation_counter]')+terminal_effect
    event(3015,body)
    elapsed.append({'start_observation':'EDU_RECREATE_CLOCK','end_observation':'EDU_RECREATE_AFTER_HOUR','minimum_hours':1})

    definitions='add_namespace = '+namespace+'\n'+''.join(events[n] for n in sorted(events))
    ast(definitions)
    return {'fixture_text':{f'events/{namespace}.txt':definitions},'entry_event_id':f'{namespace}.3000',
      'terminal_event_id':f'{namespace}.3015','entry_effect':schedule(F,3000),
      'assertions':assertions,'expectations':expectations,'observations':observations,
      'required_observations':observations,'required_elapsed_game_time':elapsed,'events':len(events),
      'production_dependency_paths':list(SOURCE_PATHS),
      'production_input_sha256':{rel:hashlib.sha256((source/rel).read_bytes()).hexdigest() for rel in SOURCE_PATHS},
      'contract':{'kind':'actual_native_edu_decision_and_hook_coverage','countries':[F,A,B],
        'actual_creation_callback_log':'EON_EDU CREATE_DECISION','required_creation_actor_observation':'EDU_ACTUAL_CREATE_RETURN',
        'required_hook_logs':['EON_EDU FORMED_HOOK','EON_EDU FORMED_COMMIT','EON_EDU LEAVE_HOOK','EON_EDU LEADERSHIP_HOOK'],
        'expected_authorized_formed_commits':2,
        'authorized_formed_commit_log':'EON_EDU FORMED_COMMIT',
        'legacy_adoption':'OBS-only conditional actual NCNS and actual template metadata; unavailable is never an adoption PASS',
        'missing_leave_hook_acceptance_blocker':True,'no_copied_complete_effect_or_create_helper':True},
      'limits':['Actual production non-targeted creation and targeted request/accept/reject/withdraw APIs; no UI clicks or native Ask/Invite consent claim.',
        'Lawful private EU origins use explicit one-use admission grants; one-founder setup makes existing influence gate vacuously truthful, not a diplomatic-influence campaign proof.',
        'Formation synchronization is observed as actually delivered; model-only deferred-callback coverage does not claim artificial native delayed delivery.',
        'Strict actual scripted remove/dismantle/leadership hook controls must pass; absent hooks fail EDU identity acceptance rather than relaxing the guard.',
        'A declared private policy-valid pending intent precedes actual dismantle/recreation to expose the no-leave-hook counterexample; this is not a claim of naturally delayed constructor delivery.',
        'Request timer is declared private one-day calibration with natural elapsed game-day proof, not a natural42-day contract campaign.',
        'Joining permission is initially required natively, privately disabled for a negative callback test and restored to its observed allowed value.',
        'Metadata adoption is conditional diagnostic only; no-DLC absence never becomes a fake positive adoption PASS.',
        'No campaign AI balance, multiplayer, save/reload, user popup or launcher proof; native constructor failure remains a guarded model boundary unless actually observed.']}
