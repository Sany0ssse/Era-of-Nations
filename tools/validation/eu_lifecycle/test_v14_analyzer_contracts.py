from pathlib import Path
import hashlib,json,tempfile,unittest
from datetime import datetime
from analyze_native_probe import analyze,sha,NEW_ERRORS,LEGACY_ERRORS,game_timestamp

ROOT=Path(__file__).resolve().parents[3]
MARK='EON_EU_NATIVE_V13'
class TokenErrors(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='eon-private-token-analyzer-')
        self.addCleanup(self.temp.cleanup); area=Path(self.temp.name)
        self.source,self.fixture,self.docs=(area/n for n in ('source','fixture','docs'))
        for folder in (self.source,self.fixture,self.docs): folder.mkdir()
        (self.source/'production.txt').write_text('bound production\n')
        (self.fixture/'probe.txt').write_text('bound fixture\n')
        (self.source/'probe.txt').write_bytes((self.fixture/'probe.txt').read_bytes())
        (self.docs/'effects_documentation.md').write_text('bound documentation\n')
        self.manifest=area/'manifest.json'
        self.manifest.write_text(json.dumps({'kind':'native_eu_lifecycle','schema':1,'marker':MARK,
          'assertions':['first','second'],
          'expectations':{name:{'predicate':'always = yes','expected':'synthetic receipt'} for name in ('first','second')},
          'source_root':str(self.source),'fixture_root':str(self.fixture),'documentation_root':str(self.docs),
          'source_sha256':{'production.txt':sha(self.source/'production.txt')},
          'fixture_sha256':{'probe.txt':sha(self.fixture/'probe.txt')},
          'documentation_sha256':{'effects_documentation.md':sha(self.docs/'effects_documentation.md')},
          'required_observations':['FINAL_STATE'],'countries':['NEP'],'limits':['Synthetic private receipt, no native gameplay claim']}))
        self.game,self.errors,self.baseline=(area/n for n in ('game.log','error.log','baseline.log'))
        self.game.write_text('\n'.join(MARK+' '+line for line in ('STARTUP','RUN_BEGIN','BEGIN first','PASS first','END first',
          'BEGIN second','PASS second','END second','OBS FINAL_STATE count=2','RUN_END passes=2 fails=0'))+'\n')
        self.errors.write_text(''); self.baseline.write_text('')
    def result(self,baseline=None): return analyze(self.manifest,self.game,self.errors,baseline)
    def warning(self,token,time='07:07:02'):
        return f'[{time}][no_game_date][scopedvariable.cpp:560]: Token {token} is a dynamic token, this can cause OOS depending on how it is used, please add it as a synchronized dynamic token\n'
    def test_complete_control_is_accepted(self): self.assertTrue(self.result()['passed'])
    def test_exact_both_tokens_are_fatal_without_file_or_namespace(self):
        for token in ('EU_exit','EU_exit_three_month','EU_voting_mission_focus_EUXXX_QMV_result','EU_voting_mission_focus_EUXXX_QMV_result_timer','EU_parliament_focus_EUXXX_approve','EU_parliament_focus_EUXXX_approve_timer'):
            with self.subTest(token=token):
                self.errors.write_text(self.warning(token)); result=self.result()
                self.assertFalse(result['passed']); self.assertEqual(result['related_script_errors'],1)
    def test_same_tokens_remain_fatal_with_exact_baseline(self):
        for token in ('EU_exit','EU_exit_three_month','EU_voting_mission_focus_EUXXX_QMV_result','EU_voting_mission_focus_EUXXX_QMV_result_timer','EU_parliament_focus_EUXXX_approve','EU_parliament_focus_EUXXX_approve_timer'):
            with self.subTest(token=token):
                self.errors.write_text(self.warning(token)); self.baseline.write_text(self.warning(token,'05:48:01'))
                result=self.result(self.baseline)
                self.assertFalse(result['passed']); self.assertEqual(result['related_script_errors'],1)
                self.assertEqual(result['preexisting_related_script_errors'],[])
    def test_eon_namespace_error_cannot_be_baseline_excused(self):
        line='[07:01:02][no_game_date][effectbase.cpp:67]: Invalid eon_edu_on_leave in EU_voting_decisions.txt:53\n'
        self.errors.write_text(line); self.baseline.write_text(line.replace('07:01:02','05:01:02'))
        self.assertFalse(self.result(self.baseline)['passed'])
    def test_exact_legacy_counter_semantics_unchanged(self):
        line='[07:01:02][no_game_date][effectbase.cpp:67]: Legacy condition in EU_voting_decisions.txt:53\n'
        self.errors.write_text(line); self.baseline.write_text(line.replace('07:01:02','05:01:02'))
        self.assertTrue(self.result(self.baseline)['passed'])
        self.errors.write_text(line+line)
        self.assertEqual(self.result(self.baseline)['related_script_errors'],1)
        self.errors.write_text(line.replace(':53',':54'))
        self.assertEqual(self.result(self.baseline)['related_script_errors'],1)
    def test_unrelated_tokens_and_prefix_extensions_unchanged(self):
        for token in ('unrelated_resource','EU_exit_private','EU_exit_three_month_private','PRE_EU_exit','EU_voting_mission_focus_EUXXX_QMV_result_private','EU_voting_mission_focus_EUXXX_QMV_result_timer_private','OTHER_EU_voting_mission_focus_EUXXX_QMV_result','EU_parliament_focus_EUXXX_approve_private','EU_parliament_focus_EUXXX_approve_timer_private','OTHER_EU_parliament_focus_EUXXX_approve'):
            with self.subTest(token=token):
                self.errors.write_text(self.warning(token)); self.assertTrue(self.result()['passed'])
                self.assertFalse(NEW_ERRORS.search(self.warning(token)))
    def legacy_block(self,time='07:13:33'):
        fragments=(
          '[parser.cpp:1111]: Error: unexpected token in file: "memfile" near line: 1 ( EU_update_AI_focus_EUХартия )',
          "[effect.cpp:445]: Invalid effect 'EU_update_AI_focus_EUХартия' in memfile line : 1",
          '[parser.cpp:1111]: Error: unexpected token in file: "memfile" near line: 1 ( прав )',
          "[effect.cpp:445]: Invalid effect 'прав' in memfile line : 1",
          "[effect.cpp:445]: Invalid effect 'Союза_voting_modifier' in memfile line : 1",
          '[effect.cpp:358]: Error: "Unknown effect-type: EU_update_AI_focus_EUХартия, near line: 1',
          'Unknown effect-type: прав, near line: 1',
          'Unknown effect-type: Союза_voting_modifier, near line: 1" in file: "memfile" near line: 1')
        return '\n'.join(('['+time+'][2000.01.04.12]'+line if i<6 else line) for i,line in enumerate(fragments))+'\n'
    def test_full_exact_localized48_legacy_baseline_allowed(self):
        self.errors.write_text(self.legacy_block()*6,encoding='utf-8')
        self.baseline.write_text(self.legacy_block('05:57:51')*6,encoding='utf-8')
        result=self.result(self.baseline)
        self.assertTrue(result['passed']); self.assertEqual(result['related_script_errors'],0)
        self.assertEqual(len(result['preexisting_related_script_errors']),48)
    def test_extra_identical_legacy_occurrence_rejected(self):
        self.errors.write_text(self.legacy_block()*7,encoding='utf-8')
        self.baseline.write_text(self.legacy_block('05:57:51')*6,encoding='utf-8')
        result=self.result(self.baseline)
        self.assertFalse(result['passed']); self.assertEqual(result['related_script_errors'],8)
    def test_known_legacy_without_baseline_rejected(self):
        self.errors.write_text(self.legacy_block(),encoding='utf-8')
        result=self.result(); self.assertFalse(result['passed']); self.assertEqual(result['related_script_errors'],8)
    def test_localized_fragments_do_not_match_unrelated_effects(self):
        for line in ("Invalid effect 'прав' in unrelated.txt line : 1",
                     "Invalid effect 'other' in memfile line : 1",
                     'Error: unexpected token in file: "other" near line: 1 ( прав )',
                     'Unknown effect-type: unrelated, near line: 1'):
            with self.subTest(line=line): self.assertFalse(LEGACY_ERRORS.search(line))
    def test_exact_six_token_scope_and_calendar_conversion_are_explicit(self):
        source=(ROOT/'tools/validation/eu_lifecycle/analyze_native_probe.py').read_text('utf-8')
        self.assertIn('if hour == 24:',source)
        self.assertNotIn('if hour >= 24:',source)
        for token in ('EU_exit','EU_exit_three_month','EU_voting_mission_focus_EUXXX_QMV_result',
                      'EU_voting_mission_focus_EUXXX_QMV_result_timer','EU_parliament_focus_EUXXX_approve',
                      'EU_parliament_focus_EUXXX_approve_timer'):
            self.assertTrue(NEW_ERRORS.search(self.warning(token)))
            self.assertFalse(NEW_ERRORS.search(self.warning(token+'_unrelated')))
        self.assertIn('Counter',source)
    def test_actual_native108_hour24_endpoint_normalizes_calendar_only(self):
        line='[07:24:59][2000.01.12.24][effectbase.cpp:1783]: EON_EU_NATIVE_V13 OBS EXTENSION_OLD_SHORT_AFTER_DAY date=613.20287 queue=0 serial=11 main_days=0 short_days=0'
        self.assertEqual(game_timestamp(line),datetime(2000,1,13))
        self.assertEqual(game_timestamp('[07:12:54][2000.01.04.01] ordinary'),datetime(2000,1,4,1))
    def test_dec31_hour24_to_jan1_hour01_is_one_game_hour(self):
        before=game_timestamp('[23:59:59][2000.12.31.24]')
        after=game_timestamp('[00:00:00][2001.01.01.01]')
        self.assertEqual((after-before).total_seconds(),3600)
    def test_invalid_hour_or_calendar_stays_rejected(self):
        for date in ('2000.01.01.25','2000.02.30.24','2001.02.29.24','2000.13.01.24','9999.12.31.24'):
            with self.subTest(date=date): self.assertIsNone(game_timestamp('[07:24:59]['+date+']'))
    def test_actual30hour_endpoint_at24_meets24_but_not48(self):
        manifest=json.loads(self.manifest.read_text())
        manifest['required_observations']=['CLOCK_START','CLOCK_END','FINAL_STATE']
        manifest['required_elapsed_game_time']=[{'start_observation':'CLOCK_START','end_observation':'CLOCK_END','minimum_hours':24}]
        self.manifest.write_text(json.dumps(manifest))
        game=self.game.read_text().replace(MARK+' RUN_BEGIN',MARK+' RUN_BEGIN\n[07:00:00][2000.01.01.18]: '+MARK+' OBS CLOCK_START date=sourceclock')
        game=game.replace(MARK+' OBS FINAL_STATE','[07:01:00][2000.01.02.24]: '+MARK+' OBS CLOCK_END date=sourceclock\n'+MARK+' OBS FINAL_STATE')
        self.game.write_text(game)
        self.assertTrue(self.result()['passed'])
        manifest['required_elapsed_game_time'][0]['minimum_hours']=48
        self.manifest.write_text(json.dumps(manifest))
        self.assertFalse(self.result()['passed'])

class CallbackErrors(unittest.TestCase):
    setUp=TokenErrors.setUp
    result=TokenErrors.result
    def build_callback(self,calibrated=False):
        action={'decision':'eon_eu_extension_approve','actor_tag':'GER','target_tag':'POL',
          'before_observation':'ACTION_BEFORE','raw_after_observation':'ACTION_RAW_AFTER',
          'after_observation':'ACTION_AFTER','requested_trace':'ACTION_ACTIVATE_REQUESTED',
          'calibration_before_observation':'ACTION_CALIBRATION_BEFORE',
          'remove_requested_trace':'ACTION_REMOVE_REQUESTED',
          'calibration_requested_trace':'ACTION_CALIBRATION_ACTIVATE_REQUESTED',
          'active_after_remove_observation':'ACTION_ACTIVE_AFTER_REMOVE',
          'increment_array':'approvals','increment_counter':'yes'}
        manifest=json.loads(self.manifest.read_text())
        manifest['extension_callback_contract']={'schema':1,'actions':[action]}
        self.manifest.write_text(json.dumps(manifest))
        pair='actor=1078.234 scope=1078.234 sender=1080.125 target=1080.125 expected_actor=1078.234'
        def context(label,count):
            return MARK+' OBS '+label+' '+pair+f' answer={count} electorate=6 yes={count} no=0 abstain=0 approvals={count} rejections=0 abstentions=0 queue=0 notice=11 project=8'
        records=[context('ACTION_BEFORE',0),MARK+' TRACE ACTION_ACTIVATE_REQUESTED '+pair,
                 context('ACTION_RAW_AFTER',0 if calibrated else 1)]
        if calibrated:
            records += [context('ACTION_CALIBRATION_BEFORE',0),MARK+' TRACE ACTION_REMOVE_REQUESTED '+pair,
                        MARK+' OBS ACTION_ACTIVE_AFTER_REMOVE value=0',MARK+' TRACE ACTION_CALIBRATION_ACTIVATE_REQUESTED '+pair]
        records += [context('ACTION_AFTER',1)]
        self.game.write_text(self.game.read_text().replace(MARK+' RUN_END','\n'.join(records)+'\n'+MARK+' RUN_END'))
    def mutate(self,old,new):
        text=self.game.read_text(); self.assertIn(old,text); self.game.write_text(text.replace(old,new,1))
    def test_raw_native_delta_one_accepted(self):
        self.build_callback(); result=self.result(); self.assertTrue(result['passed'],result['problems'])
        self.assertEqual(result['extension_callback_evidence']['actions'][0]['committed_stage'],'initial_native_activation')
    def test_declared_calibration_retains_initial_noop_evidence(self):
        self.build_callback(True);result=self.result(); self.assertTrue(result['passed'],result['problems'])
        self.assertEqual(result['extension_callback_evidence']['raw_native_noops'],1)
        self.assertEqual(result['extension_callback_evidence']['actions'][0]['committed_stage'],'declared_selected_decision_removal_calibration')
    def test_existing_ai_response_cannot_substitute_native_delta(self):
        self.build_callback()
        self.mutate('ACTION_BEFORE actor=1078.234 scope=1078.234 sender=1080.125 target=1080.125 expected_actor=1078.234 answer=0 electorate=6 yes=0 no=0 abstain=0 approvals=0','ACTION_BEFORE actor=1078.234 scope=1078.234 sender=1080.125 target=1080.125 expected_actor=1078.234 answer=1 electorate=6 yes=1 no=0 abstain=0 approvals=1')
        self.assertFalse(self.result()['passed'])
    def test_duplicate_delta_two_is_rejected(self):
        self.build_callback(); text=self.game.read_text().replace('answer=1 electorate=6 yes=1 no=0 abstain=0 approvals=1','answer=2 electorate=6 yes=2 no=0 abstain=0 approvals=2');self.game.write_text(text)
        self.assertFalse(self.result()['passed'])
    def test_wrong_sender_in_actual_activation_rejected(self):
        self.build_callback();self.mutate('TRACE ACTION_ACTIVATE_REQUESTED actor=1078.234 scope=1078.234 sender=1080.125','TRACE ACTION_ACTIVATE_REQUESTED actor=1078.234 scope=1078.234 sender=1078.234')
        self.assertFalse(self.result()['passed'])
    def test_serial_change_rejected(self):
        self.build_callback();self.mutate('ACTION_AFTER actor=1078.234 scope=1078.234 sender=1080.125 target=1080.125 expected_actor=1078.234 answer=1 electorate=6 yes=1 no=0 abstain=0 approvals=1 rejections=0 abstentions=0 queue=0 notice=11 project=8','ACTION_AFTER actor=1078.234 scope=1078.234 sender=1080.125 target=1080.125 expected_actor=1078.234 answer=1 electorate=6 yes=1 no=0 abstain=0 approvals=1 rejections=0 abstentions=0 queue=0 notice=12 project=8')
        self.assertFalse(self.result()['passed'])
    def test_missing_actual_activation_trace_rejected(self):
        self.build_callback();self.mutate('TRACE ACTION_ACTIVATE_REQUESTED','TRACE NOT_ACTIVATED')
        self.assertFalse(self.result()['passed'])
    def test_duplicate_actual_activation_trace_rejected(self):
        self.build_callback();line=next(line for line in self.game.read_text().splitlines() if 'TRACE ACTION_ACTIVATE_REQUESTED ' in line);self.mutate(line,line+'\n'+line)
        self.assertFalse(self.result()['passed'])
    def test_calibration_requires_actual_removal(self):
        self.build_callback(True);self.mutate('TRACE ACTION_REMOVE_REQUESTED','TRACE REMOVE_MISSING')
        self.assertFalse(self.result()['passed'])
    def test_calibration_requires_native_selected_action_absent(self):
        self.build_callback(True);self.mutate('OBS ACTION_ACTIVE_AFTER_REMOVE value=0','OBS ACTION_ACTIVE_AFTER_REMOVE value=1')
        self.assertFalse(self.result()['passed'])
    def test_calibration_does_not_accept_missing_response(self):
        self.build_callback(True);self.mutate('ACTION_AFTER actor=1078.234 scope=1078.234 sender=1080.125 target=1080.125 expected_actor=1078.234 answer=1 electorate=6 yes=1 no=0 abstain=0 approvals=1','ACTION_AFTER actor=1078.234 scope=1078.234 sender=1080.125 target=1080.125 expected_actor=1078.234 answer=0 electorate=6 yes=0 no=0 abstain=0 approvals=0')
        self.assertFalse(self.result()['passed'])
    def test_raw_commit_cannot_be_recast_as_calibration(self):
        self.build_callback(True);self.mutate('ACTION_RAW_AFTER actor=1078.234 scope=1078.234 sender=1080.125 target=1080.125 expected_actor=1078.234 answer=0 electorate=6 yes=0 no=0 abstain=0 approvals=0','ACTION_RAW_AFTER actor=1078.234 scope=1078.234 sender=1080.125 target=1080.125 expected_actor=1078.234 answer=1 electorate=6 yes=1 no=0 abstain=0 approvals=1')
        self.assertFalse(self.result()['passed'])

class EduTraceErrors(unittest.TestCase):
    setUp=TokenErrors.setUp
    result=TokenErrors.result
    def build_edu_trace(self,old_contract=False):
        prefix='[EON EDU]' if old_contract else 'EON_EDU'
        contract={'start_observation':'EDU_START','end_observation':'EDU_TERMINAL',
          'required_creation_actor_observation':'EDU_ACTUAL_CREATE_RETURN',
          'actual_creation_callback_log':prefix+' CREATE_DECISION',
          'required_hook_logs':[prefix+' FORMED_HOOK',prefix+' FORMED_COMMIT',prefix+' LEAVE_HOOK',prefix+' LEADERSHIP_HOOK'],
          'expected_authorized_formed_commits':2}
        if not old_contract:contract['authorized_formed_commit_log']=prefix+' FORMED_COMMIT'
        manifest=json.loads(self.manifest.read_text());manifest['edu_native_callback_contract']=contract;self.manifest.write_text(json.dumps(manifest))
        # Actual v13 engine logs stripped square-bracket localization commands.
        actual='' if old_contract else 'EON_EDU'
        pair='actor=1078.5 scope=1078.5 sender=1080.2'
        records=[MARK+' OBS EDU_START actor=1078.5 founder=1078.5',actual+' CREATE_DECISION '+pair,
          MARK+' OBS EDU_ACTUAL_CREATE_RETURN '+pair,
          actual+' FORMED_HOOK '+pair,actual+' FORMED_COMMIT '+pair,
          actual+' LEAVE_HOOK '+pair,actual+' LEADERSHIP_HOOK '+pair,
          actual+' FORMED_HOOK '+pair,actual+' FORMED_COMMIT '+pair,MARK+' OBS EDU_TERMINAL state=closed']
        self.game.write_text(self.game.read_text().replace(MARK+' RUN_END','\n'.join(records)+'\n'+MARK+' RUN_END'))
    def test_plain_trace_requires_actual_bound_hooks(self):
        self.build_edu_trace();result=self.result();self.assertTrue(result['passed'],result['problems'])
        self.assertEqual(result['edu_callback_evidence']['hook_counts']['EON_EDU FORMED_COMMIT'],2)
    def test_old_engine_stripped_trace_history_remains_failure(self):
        self.build_edu_trace(True);result=self.result();self.assertFalse(result['passed'])
        self.assertFalse(result['edu_callback_evidence']['passed'])
    def test_missing_plain_hook_still_fails(self):
        self.build_edu_trace();self.game.write_text(self.game.read_text().replace('EON_EDU LEAVE_HOOK','OTHER LEAVE_HOOK'))
        self.assertFalse(self.result()['passed'])
    def test_foreign_commit_actor_cannot_satisfy_plain_hook_contract(self):
        self.build_edu_trace();self.game.write_text(self.game.read_text().replace('EON_EDU FORMED_COMMIT actor=1078.5 scope=1078.5','EON_EDU FORMED_COMMIT actor=1080.2 scope=1080.2',1))
        self.assertFalse(self.result()['passed'])

if __name__=='__main__': unittest.main(verbosity=2)
