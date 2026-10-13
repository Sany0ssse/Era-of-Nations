from pathlib import Path
import hashlib,importlib.util,json,re,unittest
ROOT=Path(__file__).resolve().parents[3]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
import edu_support as NEW
GOLDEN38='eef3d0c2a3c70e5c7deac754068cfc41792f37b8ad8a52428a34e86143d2949b'
ORIGINAL38=['edu_live_private_countries', 'edu_nato_positive_before_mutations', 'edu_actual_founder_frontend_available', 'edu_actual_non_targeted_callback_attempt', 'edu_constructor_return_never_fabricates_identity', 'edu_actual_formed_hook_commits_after_decision', 'edu_new_eu_members_not_auto_pulled', 'edu_nato_unchanged_after_creation', 'edu_request_country_event_pair', 'edu_actual_request_has_bound_target_and_positive_deadline', 'edu_accept_country_event_pair', 'edu_actual_agreed_admission', 'edu_request_closed_once_after_actual_join', 'edu_scripted_remove_fires_real_leave_cleanup', 'edu_new_request_after_prior_departure', 'edu_actual_second_agreed_admission', 'edu_actual_native_leadership_hook_reconciles', 'edu_actual_eu_exit_transfers_before_military_departure', 'edu_nato_unchanged_after_leader_eu_exit', 'edu_second_country_has_independent_request', 'edu_actual_rejection_closes_without_admission', 'edu_actual_withdrawal_closes_current_request', 'edu_actual_request_before_timer_calibration', 'edu_natural_calibrated_request_flag_really_expired', 'edu_expired_request_production_pulse_finishes', 'edu_third_country_agreed_before_dismantle', 'edu_adversarial_pending_input_is_bound_and_policy_valid', 'edu_native_dismantle_clears_all_actual_member_receipts', 'edu_same_founder_unrelated_recreation_is_not_edu', 'edu_pending_destroy_recreate_never_commits_foreign_instance', 'edu_reconciliation_preserves_unknown_faction', 'edu_existing_faction_blocks_actual_create_callback', 'edu_national_join_prohibition_blocks_actual_creation', 'edu_nato_unchanged_after_destroy_recreate', 'edu_fresh_single_founder_available_after_unrelated_cleanup', 'edu_new_authorized_decision_gets_fresh_instance', 'edu_actual_archive_dismantles_confirmed_union_before_clear', 'edu_nato_unchanged_after_actual_archive']
class Prerequisites(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.new=NEW.build_edu('private_eu','PRIVATE_EU',source=ROOT)
        cls.text=cls.new['fixture_text']['events/private_eu.txt']
    def test_original38_native_assertions_and_source_pins_preserved(self):
        contract={'assertions':[n for n in self.new['assertions'] if n in ORIGINAL38],
                  'expectations':{n:self.new['expectations'][n] for n in ORIGINAL38},
                  'required_elapsed_game_time':self.new['required_elapsed_game_time'],
                  'production_dependency_paths':self.new['production_dependency_paths']}
        actual=hashlib.sha256(json.dumps(contract,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.assertEqual(actual,GOLDEN38)
        self.assertEqual(len(self.new['assertions']),41)
        for relative in self.new['production_dependency_paths']:
            self.assertEqual(self.new['production_input_sha256'][relative],hashlib.sha256((ROOT/relative).read_bytes()).hexdigest())
        self.assertEqual(self.new['contract']['authorized_formed_commit_log'],'EON_EDU FORMED_COMMIT')
    def test_initial_prerequisites_precede_actual_constructor(self):
        self.assertLess(self.text.index('OBS EDU_FOUNDER_BEFORE_ANY_CALIBRATION_COUNTERS'),self.text.index('activate_decision = EU_create_EDU'))
        for suffix in ('ACTIVE','RECOGNIZED','MEMBER_IDEA','IN_REGISTRY','LIVE','OWNS_STATE','SOVEREIGN','FACTIONLESS','JOIN_PERMISSION','NO_OFFENSIVE_WAR','NO_BLR_NEUTRALITY','THREAT_THRESHOLD','SEC','FOREIGN_MINISTER','INFLUENCE','NO_EDU','NO_PENDING_ACTOR','DEFENSIVE_ELIGIBLE','FOUNDER_ELIGIBLE'):
            self.assertIn('EDU_FOUNDER_BEFORE_ANY_CALIBRATION_'+suffix,self.new['required_observations'])
        self.assertEqual(len(self.new['required_observations']),len(set(self.new['required_observations'])))
    def test_original_permission_negative_case_and_no_early_setup_change(self):
        before_create=self.text.split('activate_decision = EU_create_EDU',1)[0]
        self.assertEqual(before_create.count('set_rule = { can_join_factions = yes }'),1)
        self.assertLess(before_create.index('OBS EDU_FOUNDER_BEFORE_ANY_CALIBRATION_JOIN_PERMISSION'),before_create.index('set_rule = { can_join_factions = yes }'))
        self.assertLess(before_create.index('set_rule = { can_join_factions = yes }'),before_create.index('OBS EDU_FOUNDER_AFTER_CONDITIONAL_PERMISSION_CALIBRATION_JOIN_PERMISSION'))
        self.assertIn('set_rule = { can_join_factions = no }',self.text)
        self.assertIn('edu_national_join_prohibition_blocks_actual_creation',self.new['assertions'])
        self.assertIn('EDU_CANDIDATE_AFTER_LAWFUL_SEED_JOIN_PERMISSION',self.new['required_observations'])
        self.assertIn('EDU_OTHER_AFTER_LAWFUL_SEED_JOIN_PERMISSION',self.new['required_observations'])
    def test_actual_plain_source_trace_contract_is_explicit(self):
        self.assertEqual(self.new['contract']['actual_creation_callback_log'],'EON_EDU CREATE_DECISION')
        self.assertTrue(all(label.startswith('EON_EDU ') for label in self.new['contract']['required_hook_logs']))
        self.assertNotIn('[EON EDU]',self.text)
    def test_private_calibration_is_guarded_by_every_other_actual_source_gate(self):
        event=next(value for key,op,value in NEW.ast(self.text) if key=='country_event' and NEW.one(value,'id')=='private_eu.3000')
        body=NEW.one(event,'immediate')
        calibration=next(value for key,op,value in body if key=='if' and any(name=='set_rule' for name,op,val in value))
        gate=NEW.one(calibration,'limit')
        defensive=NEW.one(NEW.ast((ROOT/'common/scripted_triggers/eon_defensive_alliance_triggers.txt').read_text('utf-8-sig')),'eon_defensive_alliance_member_eligible')
        for node in defensive:
            if node!=('has_rule','=','can_join_factions'):self.assertIn(node,gate)
        self.assertIn(('NOT','=',[('has_rule','=','can_join_factions')]),gate)
        self.assertIn(('eon_eu_is_active_member','=','yes'),gate)
        self.assertIn(('check_variable','=',[('global.EU_member_count','=','1')]),gate)
        self.assertEqual(NEW.one(calibration,'set_rule'),[('can_join_factions','=','yes')])
    def test_documented_native_crisis_input_has_actual_getter_and_trigger_controls(self):
        events=[value for key,op,value in NEW.ast(self.text) if key=='country_event']
        effects=[val for event in events for key,op,val in NEW.one(event,'immediate') if key=='add_threat']
        self.assertEqual(effects,['100','100','100'])
        self.assertNotIn('set_variable = { global.threat =',self.text)
        for stage in ('INITIAL','PENDING_COUNTEREXAMPLE','FRESH_CREATION'):
            for suffix in ('THREAT_BEFORE','THREAT_AFTER','NATIVE_TENSION_GETTER_INCREASED','NATIVE_TENSION_DIRECT_TRIGGER_ABOVE_99_PERCENT'):
                self.assertIn('EDU_'+stage+'_'+suffix,self.new['required_observations'])
            predicate=self.new['expectations']['edu_'+stage.lower()+'_declared_native_crisis_input']['predicate']
            self.assertIn('threat > 0.99',predicate)
            self.assertIn('var = global.threat value = eon_private_edu_original_threat compare = greater_than_or_equals',predicate)
        self.assertLess(self.text.index('EDU_INITIAL_THREAT_BEFORE'),self.text.index('TRACE EDU_INITIAL_DECLARED_NATIVE_CRISIS_INPUT'))
        self.assertLess(self.text.index('TRACE EDU_INITIAL_DECLARED_NATIVE_CRISIS_INPUT'),self.text.index('EDU_INITIAL_THREAT_AFTER'))
if __name__=='__main__':unittest.main(verbosity=2)
