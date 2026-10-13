"""Source-independent tests of receipt integrity, not native gameplay tests."""
from pathlib import Path
from datetime import datetime, timedelta
import json
import tempfile
import unittest
from unittest.mock import patch

from analyze_native_probe import analyze, sha, faction_diagnostic_result
from build_native_probe import build_v14 as build, MARK_V14 as MARK, ROOT, production_callback, build_world_scheduler, validate_output_paths
from extension_support import build_extension
import hashlib
from faction_identity_diagnostic import build_diagnostic


class NativeReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='eon-eu-receipt-test-')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source, self.private, self.docs = (root / name for name in ('source', 'fixture', 'docs'))
        for directory in (self.source, self.private, self.docs):
            directory.mkdir()
        self.source_file = self.source / 'production.txt'
        self.source_file.write_text('unchanged production\n', encoding='utf-8')
        self.fixture_file = self.private / 'probe.txt'
        self.fixture_file.write_text('unchanged fixture\n', encoding='utf-8')
        (self.source / 'probe.txt').write_bytes(self.fixture_file.read_bytes())
        self.doc_file = self.docs / 'effects_documentation.md'
        self.doc_file.write_text('bound native documentation\n', encoding='utf-8')
        self.manifest = root / 'manifest.json'
        self.manifest.write_text(json.dumps({
            'kind': 'native_eu_lifecycle', 'schema': 1, 'marker': MARK,
            'assertions': ['first', 'second'],
            'expectations': {label: {'predicate': 'always = yes', 'expected': 'synthetic receipt'} for label in ('first', 'second')},
            'source_root': str(self.source), 'fixture_root': str(self.private),
            'documentation_root': str(self.docs),
            'source_sha256': {'production.txt': sha(self.source_file)},
            'fixture_sha256': {'probe.txt': sha(self.fixture_file)},
            'documentation_sha256': {'effects_documentation.md': sha(self.doc_file)},
            'required_observations': ['FINAL_STATE'], 'countries': ['NEP'],
            'limits': ['Synthetic analyzer fixture; never a gameplay result.'],
        }), encoding='utf-8')
        self.game, self.errors = root / 'game.log', root / 'error.log'
        self.trace = '\n'.join(MARK + ' ' + record for record in (
            'STARTUP', 'RUN_BEGIN', 'BEGIN first', 'PASS first', 'END first',
            'BEGIN second', 'PASS second', 'END second', 'OBS FINAL_STATE count=2', 'RUN_END passes=2 fails=0')) + '\n'
        self.game.write_text(self.trace, encoding='utf-8')
        self.errors.write_text('', encoding='utf-8')

    def result(self, baseline=None):
        return analyze(self.manifest, self.game, self.errors, baseline)

    def test_complete_synthetic_receipt_is_accepted(self):
        self.assertTrue(self.result()['passed'])

    def test_missing_triplet_is_rejected(self):
        self.game.write_text(self.trace.replace(MARK + ' PASS first\n', ''), encoding='utf-8')
        self.assertFalse(self.result()['passed'])

    def test_duplicate_and_interleaved_records_are_rejected(self):
        for replacement in (self.trace + MARK + ' PASS first\n', self.trace.replace('PASS first', 'BEGIN second')):
            self.game.write_text(replacement, encoding='utf-8')
            self.assertFalse(self.result()['passed'])

    def test_record_order_and_final_counters_are_bound(self):
        self.game.write_text(self.trace.replace('passes=2', 'passes=3'), encoding='utf-8')
        self.assertFalse(self.result()['passed'])
        swapped = self.trace.replace('first', 'placeholder').replace('second', 'first').replace('placeholder', 'second')
        self.game.write_text(swapped, encoding='utf-8')
        self.assertFalse(self.result()['passed'])

    def test_failed_assertion_and_abort_are_rejected(self):
        self.game.write_text(self.trace.replace('PASS first', 'FAIL first').replace('passes=2 fails=0', 'passes=1 fails=1'), encoding='utf-8')
        self.assertEqual(['first'], self.result()['failed_assertions'])
        self.assertFalse(self.result()['passed'])
        self.game.write_text(self.trace + MARK + ' ABORT fixture_gate\n', encoding='utf-8')
        self.assertFalse(self.result()['passed'])

    def test_source_fixture_and_documentation_bytes_are_bound(self):
        for path in (self.source_file, self.fixture_file, self.source / 'probe.txt', self.doc_file):
            before = path.read_bytes()
            path.write_bytes(before + b'tampered\n')
            self.assertFalse(self.result()['passed'], str(path))
            path.write_bytes(before)
        self.assertTrue(self.result()['passed'])

    def test_observation_and_startup_must_occur_once(self):
        for record in ('STARTUP', 'OBS FINAL_STATE count=2'):
            self.game.write_text(self.trace + MARK + ' ' + record + '\n', encoding='utf-8')
            self.assertFalse(self.result()['passed'])

    def test_new_namespace_error_cannot_be_hidden_by_baseline(self):
        message = '[12:34:56] eon_eu_membership_effects.txt:42: unknown effect\n'
        self.errors.write_text(message, encoding='utf-8')
        baseline = self.errors.parent / 'baseline.log'
        baseline.write_text(message, encoding='utf-8')
        self.assertFalse(self.result(baseline)['passed'])

    def test_legacy_baseline_is_explicit_and_multiplicity_limited(self):
        message = '[12:34:56] 00_eu_scripted_effects.txt:5: preexisting diagnostic\n'
        self.errors.write_text(message, encoding='utf-8')
        self.assertFalse(self.result()['passed'])
        baseline = self.errors.parent / 'baseline.log'
        baseline.write_text(message.replace('12:34:56', '10:00:00'), encoding='utf-8')
        self.assertTrue(self.result(baseline)['passed'])
        self.errors.write_text(message * 2, encoding='utf-8')
        self.assertFalse(self.result(baseline)['passed'])

    def require_legacy_file_error_rejected(self, relative):
        self.errors.write_text('[12:34:56][no_game_date][effect.cpp:358]: Error: '
                               '"Unknown effect-type" in file: "' + relative + '" near line: 19\n',
                               encoding='utf-8')
        result = self.result()
        self.assertFalse(result['passed'])
        self.assertEqual(result['related_script_errors'], 1)

    def test_changed_legacy_eu_decision_compile_error_is_rejected(self):
        self.require_legacy_file_error_rejected('common/decisions/EU_voting_decisions.txt')

    def test_changed_legacy_eu_event_compile_error_is_rejected(self):
        self.require_legacy_file_error_rejected('events/EU_events.txt')

    def test_changed_legacy_world_callback_compile_error_is_rejected(self):
        self.require_legacy_file_error_rejected('common/on_actions/01_on_actions.txt')

    def test_changed_legacy_international_gui_compile_error_is_rejected(self):
        self.require_legacy_file_error_rejected('common/scripted_guis/international_systems_scripted_gui.txt')

    def test_changed_legacy_eu_vote_trigger_compile_error_is_rejected(self):
        self.require_legacy_file_error_rejected('common/scripted_triggers/99_EU_voting_scripted_triggers.txt')

    def test_builder_refuses_production_output_and_reusing_receipts(self):
        with self.assertRaises(AssertionError):
            build(self.source, self.source / '.local' / 'bad', self.docs, validate_only=True)
        with self.assertRaises(AssertionError):
            build(self.source, self.private, self.docs, validate_only=True)
        with self.assertRaises(AssertionError):
            build(self.source, self.source.parent / 'nonprivate', self.docs, validate_only=True)

    def test_authoritative_template_requires_opt_in_and_exact_private_checkout_route(self):
        output = ROOT / '.local' / 'uncreated-native-v13-template-path-contract'
        with self.assertRaises(AssertionError):
            validate_output_paths(ROOT, output)
        self.assertEqual((ROOT.resolve(), output.resolve()),
                         validate_output_paths(ROOT, output, authoritative_template=True))
        self.assertFalse(output.exists(), 'Path validation never creates a template')
        for unsafe in (ROOT / 'common' / '.local' / 'probe', ROOT / '.local',
                       self.source.parent / '.local' / 'outsider'):
            with self.assertRaises(AssertionError):
                validate_output_paths(ROOT, unsafe, authoritative_template=True)
        with self.assertRaises(AssertionError):
            validate_output_paths(self.source, self.source / '.local' / 'probe', authoritative_template=True)

    def test_authoritative_template_rejects_production_fixture_collision(self):
        fixture = self.source / 'events' / 'eon_native_eu_probe.txt'
        fixture.parent.mkdir()
        fixture.write_text('existing fixture must remain untouched', encoding='utf-8')
        with patch('build_native_probe.ROOT', self.source):
            with self.assertRaises(AssertionError):
                validate_output_paths(self.source, self.source / '.local' / 'probe', authoritative_template=True)
        self.assertEqual('existing fixture must remain untouched', fixture.read_text(encoding='utf-8'))

    def test_authoritative_template_rejects_even_inward_private_symlink(self):
        private = self.source / '.local'
        target = private / 'real'
        target.mkdir(parents=True)
        link = private / 'linked'
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError as error:
            self.skipTest('Host does not grant test symlink creation: ' + str(error))
        with patch('build_native_probe.ROOT', self.source):
            with self.assertRaises(AssertionError):
                validate_output_paths(self.source, link / 'probe', authoritative_template=True)

    def test_authoritative_template_validate_only_uses_exact_source_without_writing(self):
        output = ROOT / '.local' / 'uncreated-native-v13-template-build-contract'
        result = build(ROOT, output, self.docs, validate_only=True, authoritative_template=True, additional_module_builders={})
        self.assertEqual(5, len(result['fixture_text']))
        self.assertEqual(160, result['core_assertions'])
        self.assertEqual(318, len(result['assertions']))
        self.assertFalse(output.exists(), 'Validate-only must not write inside the checkout')

    def test_nato_diagnostics_preserve_strict_precondition_and_exit_checks(self):
        result = build(ROOT, self.source.parent / '.local' / 'uncreated', self.docs, validate_only=True, additional_module_builders={})
        self.assertEqual(160, result['core_assertions'])
        self.assertEqual(318, len(result['assertions']))
        self.assertEqual(116, result['events'])
        self.assertEqual(5, len(result['fixture_text']))
        self.assertIn('common/factions/goals/eon_native_eu_probe_faction_identity_diagnostic.txt', result['fixture_text'])
        self.assertEqual(1, result['fixture_text']['events/eon_native_eu_probe.txt'].count('RUN_END'))
        for label in ('agreed_exit_fixture_is_in_nato_before_edu',
                      'eu_exit_does_not_remove_unrelated_nato_despite_edu'):
            predicate = result['expectations'][label]['predicate']
            self.assertIn('is_in_faction = yes is_in_faction_with = USA', predicate)
            self.assertIn('var = THIS.id value = global.eon_native_eu_probe_nato_leader_before_exit', predicate)
            self.assertIn('OR = { NOT = { has_dlc = "No Compromise, No Surrender" } has_faction_template = faction_template_nato }', predicate)
        text = result['fixture_text']['events/eon_native_eu_probe.txt']
        for stage in ('NATO_BEFORE_SETUP', 'NATO_AFTER_CREATE', 'NATO_AFTER_JOIN',
                      'NATO_NEXT_NATIVE_HOUR', 'NATO_AFTER_EU_EXIT'):
            for suffix in ('POL_WITH_USA', 'USA_NATO_TEMPLATE', 'POL_NATO_TEMPLATE',
                           'USA_LEADER_TOKEN', 'POL_LEADER_TOKEN'):
                self.assertIn('OBS ' + stage + '_' + suffix, text)
        self.assertIn('has_dlc = "No Compromise, No Surrender"', text)
        self.assertIn('faction_leader = { add_to_faction = POL', text)
        self.assertIn('NATO_ADMISSION_CLOCK', text)
        self.assertIn('AGREED_EXIT_DELAYED_CLOCK', text)
        self.assertIn('var = global.date value = global.eon_native_eu_probe_nato_admission_date compare = greater_than',
                      result['expectations']['agreed_exit_fixture_is_in_nato_before_edu']['predicate'])
        self.assertIn('var = global.date value = global.eon_native_eu_probe_agreed_exit_date compare = greater_than',
                      result['expectations']['agreed_exit_effect_survives_next_native_hour']['predicate'])
        # Metadata false must never trigger departure from an existing actual
        # shared NATO. The conditional setup uses actual membership instead.
        self.assertIn('NOT = { is_in_faction = yes POL = { is_in_faction_with = USA } }', text)
        self.assertNotIn('NOT = { has_faction_template = faction_template_nato } } if', text)
        self.assertLess(text.index('NATO_AFTER_JOIN'), text.index('NATO_NEXT_NATIVE_HOUR'))
        self.assertLess(text.index('NATO_NEXT_NATIVE_HOUR'), text.index('BEGIN agreed_exit_fixture_is_in_nato_before_edu'))

    def test_v14_requires_exact_startup_version_without_rejecting_v14_prefix(self):
        manifest = json.loads(self.manifest.read_text(encoding='utf-8'))
        manifest['fixture_version'] = 14
        self.manifest.write_text(json.dumps(manifest), encoding='utf-8')
        self.assertFalse(self.result()['passed'])
        current = self.trace.replace(MARK + ' STARTUP', MARK + ' STARTUP fixture_version=14')
        self.game.write_text(current, encoding='utf-8')
        self.assertTrue(self.result()['passed'])
        self.game.write_text(current + 'EON_EU_NATIVE_V1 OBS stale old_version\n', encoding='utf-8')
        self.assertFalse(self.result()['passed'])

    def test_new_changed_legacy_authority_sources_cannot_hide_errors(self):
        for relative in ('common/decisions/EU_POTEF_decisions.txt',
                         'common/decisions/Belarus.txt', 'events/Hungary.txt'):
            self.require_legacy_file_error_rejected(relative)

    def test_actual_history_boundary_precedes_private_admission_and_counter_is_incremented(self):
        result = build(ROOT, self.source.parent / '.local' / 'history-only', self.docs, validate_only=True, additional_module_builders={})
        text = result['fixture_text']['events/eon_native_eu_probe.txt']
        initial = 'BEGIN actual_original_startup_has_fifteen_recognized_members_once'
        self.assertLess(text.index(initial), text.index('set_country_flag = eon_eu_admission_commit'))
        predicate = result['expectations']['actual_original_startup_has_fifteen_recognized_members_once']['predicate']
        for value in ('value = 15', 'eon_eu_admission_guard_ready', 'eon_eu_membership_recognized',
                      'global.eon_native_eu_probe_startup_count value = 1',
                      'global.eon_native_eu_probe_fixture_version value = 14'):
            self.assertIn(value, predicate)
        self.assertNotIn('set_global_flag = eon_eu_admission_guard_ready', text)
        self.assertIn('eon_eu_clear_country_access = yes set_country_flag = eon_eu_admission_commit add_ideas = EU_member', text)
        startup = result['fixture_text']['common/on_actions/eon_native_eu_probe.txt']
        self.assertIn('add_to_variable = { global.eon_native_eu_probe_startup_count = 1 }', startup)
        self.assertNotIn('set_variable = { global.eon_native_eu_probe_startup_count', startup)

    def test_production_callbacks_are_extracted_exactly_and_required(self):
        with self.assertRaises(AssertionError):
            production_callback(ROOT, 'common/decisions/EU_POTEF_decisions.txt', 'invented_mission', 'timeout_effect')
        with self.assertRaises(AssertionError):
            production_callback(ROOT, 'common/decisions/EU_POTEF_decisions.txt', 'EU_POTEF_term', 'invented_callback')
        text = production_callback(ROOT, 'common/decisions/EU_POTEF_decisions.txt', 'EU_POTEF_term', 'timeout_effect')
        self.assertIn('eon_eu_potef_term_current = yes', text)
        self.assertIn('activate_mission = EU_POTEF_election_campaign', text)
        self.assertIn('else = { remove_mission = EU_POTEF_term', text)

    def test_fresh_edu_error_is_fatal_even_when_listed_in_old_baseline(self):
        message = '[12:34:56] eon_edu_identity_effects.txt:42: unknown effect\n'
        self.errors.write_text(message, encoding='utf-8')
        baseline = self.errors.parent / 'edu-baseline.log'
        baseline.write_text(message, encoding='utf-8')
        result = self.result(baseline)
        self.assertFalse(result['passed'])
        self.assertEqual(1, result['related_script_errors'])
        self.assertEqual([], result['preexisting_related_script_errors'])

    def test_shared_game_rule_compile_errors_are_not_ignored(self):
        for relative in ('common/scripted_triggers/00_game_rule_triggers.txt',
                         'common/game_rules/00_game_rules.txt',
                         'common/on_actions/00_game_rules_on_actions.txt'):
            self.require_legacy_file_error_rejected(relative)

    def test_extension_native_module_requires_actual_decision_activation_and_bound_sources(self):
        module = build_extension('eon_native_eu_probe', MARK, source=ROOT, terminal_effect='log = "test_terminal"')
        self.assertEqual(114, len(module['assertions']))
        self.assertEqual(47, module['events'])
        self.assertEqual('eon_native_eu_probe.2000', module['entry_event_id'])
        self.assertEqual('eon_native_eu_probe.2046', module['terminal_event_id'])
        self.assertEqual(set(module['assertions']), set(module['expectations']))
        text = next(iter(module['fixture_text'].values()))
        self.assertIn('activate_decision = eon_eu_notify_withdrawal', text)
        self.assertIn('activate_targeted_decision = { target = POL decision = eon_eu_extension_approve', text)
        self.assertNotIn('eon_eu_extension_approve = yes', text)
        self.assertNotIn('set_global_flag = eon_eu_admission_guard_ready', text)
        self.assertIn('days_mission_timeout@EU_exit', text)
        self.assertIn('days_mission_timeout@EU_exit_three_month', text)
        self.assertEqual({24, 48}, {item['minimum_hours'] for item in module['required_elapsed_game_time']})
        self.assertEqual(6, len(module['calibrations']))
        for relative, digest in module['production_input_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), digest)

    def test_extension_external_terminal_event_is_not_remapped_as_an_internal_event(self):
        module = build_extension('eon_native_eu_probe', MARK, source=ROOT,
                                 terminal_effect='AUS = { country_event = { id = eon_native_eu_probe.3000 hours = 2 } } ')
        text = next(iter(module['fixture_text'].values()))
        self.assertIn('id = eon_native_eu_probe.3000 hours = 2', text)
        self.assertEqual(47, module['events'])

    def test_integrated_modules_keep_golden_core_and_source_pins_in_one_terminal_trace(self):
        result = build(ROOT, self.source.parent / '.local' / 'integrated-contract', self.docs, validate_only=True, additional_module_builders={})
        self.assertEqual({'extension': (114, 47), 'edu': (41, 16),
                          'world_scheduler': (3, 3), 'faction_identity_diagnostic': (0, 5)},
                         {name: (module['assertions'], module['events']) for name, module in result['native_modules'].items()})
        self.assertEqual('0a8c1fd1f2c8704b9a81573b7151cb2dd00265607c5711ef31ef20b858113602', result['baseline_v12_contract_sha256'])
        self.assertEqual(set(result['assertions']), set(result['expectations']))
        self.assertEqual(len(result['required_observations']), len(set(result['required_observations'])))
        text = result['fixture_text']['events/eon_native_eu_probe.txt']
        self.assertLess(text.index('BEGIN extension_countries_live'), text.index('BEGIN edu_live_private_countries'))
        self.assertLess(text.index('BEGIN edu_live_private_countries'), text.index('BEGIN world_scheduler_prepared_live_commission_and_ep_vacancy'))
        self.assertLess(text.index('BEGIN world_scheduler_prepared_live_commission_and_ep_vacancy'), text.index('BEGIN ' + result['assertions'][-1]))
        self.assertEqual(1, text.count('RUN_END'))
        self.assertEqual(22, len(result['required_elapsed_game_time']))
        for module in result['native_modules'].values():
            for relative, digest in module['production_input_sha256'].items():
                self.assertEqual(sha(ROOT / relative), digest)

    def add_synthetic_edu_callback_contract(self):
        contract = {
            'start_observation': 'EDU_START', 'end_observation': 'EDU_TERMINAL',
            'required_creation_actor_observation': 'EDU_ACTUAL_CREATE_RETURN',
            'actual_creation_callback_log': '[EON EDU] CREATE_DECISION',
            'required_hook_logs': ['[EON EDU] FORMED_HOOK', '[EON EDU] FORMED_COMMIT',
                                   '[EON EDU] LEAVE_HOOK', '[EON EDU] LEADERSHIP_HOOK'],
            'expected_authorized_formed_commits': 2,
        }
        manifest = json.loads(self.manifest.read_text(encoding='utf-8'))
        manifest['edu_native_callback_contract'] = contract
        manifest['required_observations'] = ['EDU_START', 'EDU_ACTUAL_CREATE_RETURN', 'EDU_TERMINAL', 'FINAL_STATE']
        self.manifest.write_text(json.dumps(manifest), encoding='utf-8')
        rows = [MARK + ' OBS EDU_START actor=5078.99577 founder=5078.99577',
                '[EON EDU] CREATE_DECISION actor=5078.99577 scope=5078.99577 sender=0',
                '[EON EDU] FORMED_HOOK actor=5078.99577 scope=5078.99577 sender=0',
                '[EON EDU] FORMED_COMMIT actor=5078.99577 scope=5078.99577',
                MARK + ' OBS EDU_ACTUAL_CREATE_RETURN actor=5078.99577 scope=5078.99577 sender=8.93754',
                '[EON EDU] LEAVE_HOOK actor=11.7353 scope=11.7353 sender=5078.99577',
                '[EON EDU] LEADERSHIP_HOOK actor=11.7353 scope=11.7353 sender=5078.99577',
                '[EON EDU] FORMED_COMMIT actor=5078.99577 scope=5078.99577',
                MARK + ' OBS EDU_TERMINAL instance=2']
        text = self.trace.replace(MARK + ' OBS FINAL_STATE', '\n'.join(rows) + '\n' + MARK + ' OBS FINAL_STATE')
        self.game.write_text(text, encoding='utf-8')
        return text

    def test_edu_actor_and_hooks_need_actual_window_but_sender_is_observational(self):
        self.add_synthetic_edu_callback_contract()
        result = self.result()
        self.assertTrue(result['passed'])
        self.assertTrue(result['edu_callback_evidence']['passed'])
        self.assertEqual('0', result['edu_callback_evidence']['creation_callback_contexts'][0]['sender'])
        self.assertEqual('8.93754', result['edu_callback_evidence']['creation_context']['sender'])

    def test_edu_wrong_callback_actor_scope_is_rejected(self):
        text = self.add_synthetic_edu_callback_contract()
        self.game.write_text(text.replace('CREATE_DECISION actor=5078.99577 scope=5078.99577',
                                          'CREATE_DECISION actor=11.7353 scope=11.7353'), encoding='utf-8')
        self.assertFalse(self.result()['passed'])

    def test_edu_missing_hook_cannot_be_satisfied_by_log_after_trace(self):
        text = self.add_synthetic_edu_callback_contract()
        hook = '[EON EDU] LEADERSHIP_HOOK actor=11.7353 scope=11.7353 sender=5078.99577'
        self.game.write_text(text.replace(hook + '\n', '') + hook + '\n', encoding='utf-8')
        self.assertFalse(self.result()['passed'])

    def test_extra_foreign_edu_formed_commit_is_rejected(self):
        text = self.add_synthetic_edu_callback_contract()
        self.game.write_text(text.replace(MARK + ' OBS EDU_TERMINAL',
                                          '[EON EDU] FORMED_COMMIT actor=11.7353 scope=11.7353\n' + MARK + ' OBS EDU_TERMINAL'), encoding='utf-8')
        self.assertFalse(self.result()['passed'])

    def test_extension_native_module_uses_mutated_actual_frontend_gate(self):
        baseline = build_extension('eon_native_eu_probe', MARK, source=ROOT)
        source = self.source / 'native-extension-input'
        for relative in baseline['production_dependency_paths']:
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())
        path = source / 'common/decisions/eon_eu_withdrawal_extension_decisions.txt'
        text = path.read_text(encoding='utf-8-sig')
        self.assertIn('eon_eu_extension_can_propose = yes', text)
        path.write_text(text.replace('eon_eu_extension_can_propose = yes',
                                     'native_test_rejected_gate = yes', 1), encoding='utf-8')
        changed = build_extension('eon_native_eu_probe', MARK, source=source)
        events = next(iter(changed['fixture_text'].values()))
        self.assertIn('native_test_rejected_gate = yes', events)
        self.assertNotEqual(baseline['production_input_sha256'][path.relative_to(source).as_posix()],
                            changed['production_input_sha256'][path.relative_to(source).as_posix()])

    def test_world_scheduler_trace_has_no_post_unlock_helper_or_clock_consumption(self):
        module = build_world_scheduler('eon_native_eu_probe', MARK)
        self.assertEqual(3, module['events'])
        self.assertEqual(3, len(module['assertions']))
        self.assertEqual([48, 384], [item['minimum_hours'] for item in module['required_elapsed_game_time']])
        text = next(iter(module['fixture_text'].values()))
        self.assertIn('hours = 49', text)
        self.assertIn('hours = 385', text)
        before, after = text.split('clr_global_flag = eon_eu_daily_lifecycle_done', 1)
        self.assertIn('eon_eu_appoint_office_1 = yes', before)
        for forbidden in ('eon_eu_daily_institutions_pulse', 'eon_eu_daily_lifecycle_pulse',
                          'clr_global_flag = eon_eu_office_ballot_deadline',
                          'eon_eu_open_office_ballot', 'eon_eu_resolve_office_ballot',
                          'eon_eu_cast_office_yes'):
            self.assertNotIn(forbidden, after)
        self.assertIn('eon_native_eu_probe_world_daily_callbacks = 1', module['on_daily_effect'])
        self.assertIn('eon_eu_office_id value = 2', module['expectations']['world_scheduler_actual_on_daily_opens_ep_ballot']['predicate'])
        self.assertIn('has_idea = EU_parliament_president', module['expectations']['world_scheduler_natural_fourteen_day_window_ai_fills_one_ep_chair']['predicate'])

    def add_elapsed_contract(self, start='2000.01.05.07', end='2000.01.05.08', *, prefix=True):
        manifest = json.loads(self.manifest.read_text(encoding='utf-8'))
        manifest['required_observations'] = ['CLOCK_START', 'CLOCK_END', 'FINAL_STATE']
        manifest['required_elapsed_game_time'] = [{'start_observation': 'CLOCK_START',
                                                  'end_observation': 'CLOCK_END', 'minimum_hours': 1}]
        self.manifest.write_text(json.dumps(manifest), encoding='utf-8')
        clock = '\n'.join((('[12:34:56][' + stamp + '][effect.cpp:1]: ') if prefix else '[12:34:56] ') +
                          MARK + ' OBS ' + label + ' date=synthetic'
                          for label, stamp in (('CLOCK_START', start), ('CLOCK_END', end))) + '\n'
        self.game.write_text(self.trace.replace(MARK + ' OBS FINAL_STATE', clock + MARK + ' OBS FINAL_STATE'), encoding='utf-8')

    def test_elapsed_game_hour_requires_positive_native_timestamp_advance(self):
        self.add_elapsed_contract()
        result = self.result()
        self.assertTrue(result['passed'])
        self.assertEqual(1, result['elapsed_game_time'][0]['elapsed_hours'])

    def test_same_tick_delay_claim_is_rejected(self):
        self.add_elapsed_contract(end='2000.01.05.07')
        self.assertFalse(self.result()['passed'])

    def test_wall_clock_or_absent_game_date_cannot_prove_delay(self):
        self.add_elapsed_contract(prefix=False)
        self.assertFalse(self.result()['passed'])

    def test_backwards_game_date_cannot_prove_delay(self):
        self.add_elapsed_contract(end='2000.01.05.06')
        self.assertFalse(self.result()['passed'])

    def test_named_nato_receipt_rejects_unrelated_or_factionless_state(self):
        manifest = json.loads(self.manifest.read_text(encoding='utf-8'))
        manifest['required_observations'] = ['NATO_NAMES', 'FINAL_STATE']
        manifest['required_named_factions'] = [{'observation': 'NATO_NAMES', 'members': ['usa', 'pol'],
                                              'allowed_names': ['NATO', 'НАТО']}]
        self.manifest.write_text(json.dumps(manifest), encoding='utf-8')
        for names, expected in (('usa=NATO pol=NATO', True), ('usa=НАТО pol=НАТО', True),
                                ('usa=NATO pol=', False), ('usa=Other Alliance pol=Other Alliance', False)):
            self.game.write_text(self.trace.replace(MARK + ' OBS FINAL_STATE', MARK + ' OBS NATO_NAMES ' + names + '\n' + MARK + ' OBS FINAL_STATE'), encoding='utf-8')
            self.assertEqual(expected, self.result()['passed'], names)

    def diagnostic_rows(self):
        diagnostic = build_diagnostic('eon_native_eu_probe', MARK)
        contract = diagnostic['contract']
        values = dict.fromkeys(diagnostic['observations'], 'value=1')
        for field in ('structure_negative_labels', 'marker_negative_labels', 'control_negative_labels',
                      'natural_flag_negative_labels'):
            values.update(dict.fromkeys(contract[field], 'value=0'))
        values[contract['no_dlc_label']] = 'value=0'
        rows = {label: [('[12:34:56][2000.01.06.08][effect.cpp:1]: ' + MARK + ' OBS ' + label + ' ' + value, value)]
                for label, value in values.items()}
        for index, label in enumerate(contract['clock_labels']):
            date = datetime(2000, 1, 6, 8) + timedelta(hours=12 * index)
            value = 'raw=synthetic start=synthetic previous=synthetic'
            rows[label] = [(f'[12:34:56][{date:%Y.%m.%d.%H}][effect.cpp:1]: {MARK} OBS {label} {value}', value)]
        return diagnostic, rows

    def test_diagnostic_supported_requires_actual_structure_and_clocks(self):
        diagnostic, rows = self.diagnostic_rows()
        result = faction_diagnostic_result(diagnostic['contract'], rows)
        self.assertTrue(result['supported'])
        self.assertEqual('native_goal_identity_supported', result['status'])
        self.assertTrue(result['controls_valid'])

    def test_unsupported_goal_storage_is_explicitly_negative_not_pass(self):
        diagnostic, rows = self.diagnostic_rows()
        contract = diagnostic['contract']
        for label in contract['marker_positive_labels'] + contract['control_positive_labels']:
            rows[label] = [('synthetic native observation', 'value=0')]
        result = faction_diagnostic_result(contract, rows)
        self.assertFalse(result['supported'])
        self.assertEqual('native_goal_storage_unsupported', result['status'])
        self.assertTrue(result['controls_valid'])

    def test_failed_faction_mutation_control_cannot_prove_goal_support(self):
        diagnostic, rows = self.diagnostic_rows()
        rows[diagnostic['contract']['structure_positive_labels'][0]] = [('synthetic native observation', 'value=0')]
        result = faction_diagnostic_result(diagnostic['contract'], rows)
        self.assertFalse(result['supported'])
        self.assertEqual('invalid_native_controls', result['status'])

    def test_missing_or_same_tick_diagnostic_clock_is_invalid(self):
        diagnostic, rows = self.diagnostic_rows()
        label = diagnostic['contract']['clock_labels'][1]
        rows[label] = [('[12:34:57][2000.01.06.08][effect.cpp:1]: synthetic clock', 'raw=synthetic')]
        self.assertEqual('invalid_native_controls', faction_diagnostic_result(diagnostic['contract'], rows)['status'])

    def test_diagnostic_malformed_atomic_value_is_not_boolean_success(self):
        diagnostic, rows = self.diagnostic_rows()
        label = diagnostic['contract']['marker_positive_labels'][0]
        rows[label] = [('synthetic native observation', 'value=2')]
        result = faction_diagnostic_result(diagnostic['contract'], rows)
        self.assertFalse(result['supported'])
        self.assertIn(label, result['malformed_atomic_observations'])

    def test_core_pass_and_diagnostic_acceptance_remain_separate(self):
        diagnostic, rows = self.diagnostic_rows()
        contract = diagnostic['contract']
        for label in contract['marker_positive_labels'] + contract['control_positive_labels']:
            rows[label] = [(MARK + ' OBS ' + label + ' value=0', 'value=0')]
        manifest = json.loads(self.manifest.read_text(encoding='utf-8'))
        manifest['required_observations'] = diagnostic['observations'] + ['FINAL_STATE']
        manifest['faction_identity_diagnostic'] = contract
        self.manifest.write_text(json.dumps(manifest), encoding='utf-8')
        records = '\n'.join(rows[label][0][0] for label in diagnostic['observations']) + '\n'
        self.game.write_text(self.trace.replace(MARK + ' OBS FINAL_STATE', records + MARK + ' OBS FINAL_STATE'), encoding='utf-8')
        result = self.result()
        self.assertTrue(result['passed'])
        self.assertFalse(result['diagnostic_result']['supported'])
        self.assertEqual('native_goal_storage_unsupported', result['diagnostic_result']['status'])


if __name__ == '__main__':
    unittest.main()
