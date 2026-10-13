"""Public full-builder contracts; temporary source inputs and no game process."""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
import build_native_probe as NEW
import analyze_native_probe as ANALYZER

def synthetic_additive(name, start):
    """Only a composition test fixture; no actual legislative behavior claim."""
    def build(namespace, marker, *, source, terminal_effect=''):
        relative = 'common/scripted_triggers/eon_eu_financial_triggers.txt'
        labels = [name + '_synthetic_composition_control']
        observations = [name.upper() + '_SYNTHETIC_START', name.upper() + '_SYNTHETIC_END']
        text = ('add_namespace = ' + namespace + '\n' +
                f'country_event = {{ id = {namespace}.{start} hidden = yes is_triggered_only = yes immediate = {{ '
                f'log = "{marker} OBS {observations[0]} value=1" '
                f'NEP = {{ country_event = {{ id = {namespace}.{start+1} hours = 2 }} }} }} }}\n' +
                f'country_event = {{ id = {namespace}.{start+1} hidden = yes is_triggered_only = yes immediate = {{ '
                f'log = "{marker} OBS {observations[1]} value=1" ' + terminal_effect + '} }\n')
        return {'fixture_text': {f'events/{namespace}.txt': text},
                'entry_event_id': f'{namespace}.{start}', 'terminal_event_id': f'{namespace}.{start+1}',
                'entry_effect': f'NEP = {{ country_event = {{ id = {namespace}.{start} hours = 2 }} }} ',
                'events': 2, 'assertions': labels,
                'expectations': {labels[0]: {'predicate': 'always = yes', 'expected': 'Synthetic module composition only'}},
                'observations': observations,
                'production_dependency_paths': [relative],
                'production_input_sha256': {relative: hashlib.sha256((source / relative).read_bytes()).hexdigest()},
                'required_elapsed_game_time': [{'start_observation': observations[0], 'end_observation': observations[1], 'minimum_hours': 1}],
                'limits': ['Synthetic composition control; not production Council/EP acceptance.']}
    return build

class FullBuilder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='synthetic-v14-', dir=ROOT/'.local')
        cls.base = Path(cls.temp.name)
        cls.source = cls.base / 'source'
        extension = NEW.build_extension(NEW.NS, NEW.MARK_V14, source=ROOT)
        edu = NEW.build_edu(NEW.NS, NEW.MARK_V14, source=ROOT)
        paths = set(extension['production_dependency_paths']) | set(edu['production_dependency_paths'])
        paths.add('common/decisions/EU_POTEF_decisions.txt')
        for area in ('membership', 'voting', 'institutions'):
            for kind in ('effects', 'triggers'):
                paths.add(f'common/scripted_{kind}/eon_eu_{area}_{kind}.txt')
        paths.update(('common/scripted_effects/eon_eu_lifecycle_effects.txt', 'common/scripted_triggers/eon_eu_financial_triggers.txt'))
        for relative in paths:
            target = cls.source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        cls.paths = paths
        cls.validated = NEW.build_v14(cls.source, cls.base / 'unused-validation-output', validate_only=True, additional_module_builders={})
        cls.written = NEW.build_v14(cls.source, cls.base / 'written-template', additional_module_builders={})
    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
    def output(self, label):
        return self.base / label
    def synthetic_analysis(self, name):
        """Parser/receipt simulation only; these lines never come from a game."""
        area = self.output(name)
        area.mkdir()
        effective = area / 'effective-source'
        for relative in self.paths:
            target = effective / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.source / relative, target)
        for relative in self.written['fixture_sha256']:
            target = effective / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.base / 'written-template/mod' / relative, target)
        manifest = json.loads(json.dumps(self.written))
        manifest['source_root'] = str(effective)
        manifest['limits'].append('SYNTHETIC FULL-MANIFEST ANALYZER CONTRACT: generated log text, no native execution or gameplay proof.')
        path = area / 'manifest.synthetic.json'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        marker = manifest['marker']
        lines = [marker + ' STARTUP fixture_version=14', marker + ' RUN_BEGIN']
        for label in manifest['assertions']:
            lines.extend(marker + ' ' + state + ' ' + label for state in ('BEGIN', 'PASS', 'END'))
        contract = manifest['faction_identity_diagnostic']
        atomic = {}
        for field in ('required_native_preconditions', 'structure_positive_labels', 'clock_advance_labels', 'natural_flag_positive_labels'):
            atomic.update(dict.fromkeys(contract.get(field, []), 1))
        for field in ('structure_negative_labels', 'marker_positive_labels', 'marker_negative_labels',
                      'control_positive_labels', 'control_negative_labels', 'natural_flag_negative_labels'):
            atomic.update(dict.fromkeys(contract.get(field, []), 0))
        atomic[contract['no_dlc_label']] = 0
        def callback_rows():
            rows = []
            for index, action in enumerate(manifest['extension_callback_contract']['actions']):
                actor = '1078.' + str(100 + index)
                target = '1080.22'
                before = {'actor': actor, 'scope': actor, 'sender': target, 'target': target, 'expected_actor': actor,
                          'answer': 0, 'electorate': 6, 'yes': 0, 'no': 0, 'abstain': 0,
                          'approvals': 0, 'rejections': 0, 'abstentions': 0, 'queue': 0,
                          'notice': 10 + index, 'project': 8 + index}
                after = before.copy()
                for key in ('answer', action['increment_array'], action['increment_counter']):
                    after[key] += 1
                def payload(values):
                    return ' '.join(key + '=' + str(value) for key, value in values.items())
                rows.extend((marker + ' OBS ' + action['before_observation'] + ' ' + payload(before),
                             marker + ' TRACE ' + action['requested_trace'] + ' ' + payload(before),
                             marker + ' OBS ' + action['raw_after_observation'] + ' ' + payload(after),
                             marker + ' OBS ' + action['after_observation'] + ' ' + payload(after)))
            return rows
        def stamp(value):
            if value.hour == 0:
                return '[' + (value - timedelta(days=1)).strftime('%Y.%m.%d') + '.24] '
            return '[' + value.strftime('%Y.%m.%d.%H') + '] '
        for index, label in enumerate(manifest['required_observations']):
            timestamp = stamp(datetime(2000, 1, 1) + timedelta(hours=index * 400))
            payload = 'value=' + str(atomic.get(label, 1))
            if label in ('NATO_NEXT_NATIVE_HOUR_NAMES', 'NATO_AFTER_EU_EXIT_NAMES'):
                payload = 'usa=NATO pol=NATO'
            if label == 'EDU_START':
                lines.extend(timestamp + row for row in callback_rows())
                payload = 'actor=1078.5 founder=1078.5'
            elif label == 'EDU_ACTUAL_CREATE_RETURN':
                payload = 'actor=1078.5 scope=1078.5 sender=1080.22'
            lines.append(timestamp + marker + ' OBS ' + label + ' ' + payload)
            if label == 'EDU_START':
                pair = ' actor=1078.5 scope=1078.5 sender=1080.22'
                lines.extend(timestamp + trace + pair for trace in (
                    'EON_EDU CREATE_DECISION', 'EON_EDU FORMED_HOOK', 'EON_EDU FORMED_COMMIT',
                    'EON_EDU LEAVE_HOOK', 'EON_EDU LEADERSHIP_HOOK',
                    'EON_EDU FORMED_HOOK', 'EON_EDU FORMED_COMMIT'))
        lines.append(marker + ' RUN_END passes=' + str(len(manifest['assertions'])) + ' fails=0')
        game, errors, baseline = (area / label for label in ('game.synthetic.log', 'error.synthetic.log', 'baseline.synthetic.log'))
        game.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        errors.write_text('', encoding='utf-8')
        baseline.write_text('', encoding='utf-8')
        return manifest, path, game, errors, baseline
    def test_validate_and_write_propagate_complete_contracts(self):
        keys = ('assertions', 'expectations', 'events', 'core_assertions', 'native_modules',
                'baseline_v12_contract_sha256', 'fixture_version', 'marker', 'native_builder_inputs',
                'additive_module_contract', 'coordinator_isolation_contract', 'edu_trace_source_contract', 'extension_callback_contract',
                'diagnostic_observations', 'extension_calibrations', 'edu_native_callback_contract',
                'required_elapsed_game_time', 'faction_identity_diagnostic', 'required_observations')
        for field in keys:
            self.assertEqual(self.validated[field], self.written[field], field)
        persisted = json.loads((self.base / 'written-template/manifest.json').read_text())
        self.assertEqual(persisted, self.written)
        self.assertEqual(self.validated['fixture_version'], 14)
        self.assertEqual(self.validated['marker'], 'EON_EU_NATIVE_V14')
        self.assertFalse(self.output('unused-validation-output').exists())
    def test_original144_golden_and16_additional_are_preserved(self):
        baseline = [name for name in self.validated['assertions'][:160] if name not in NEW.ADMISSION_BOUNDARY_ASSERTIONS]
        contract = {'assertions': baseline, 'expectations': {name: self.validated['expectations'][name] for name in baseline}}
        digest = hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(len(baseline), 144)
        self.assertEqual(digest, NEW.BASELINE_V12_SHA256)
        predicate = self.validated['expectations']['actual_original_startup_has_fifteen_recognized_members_once']['predicate']
        self.assertIn('fixture_version value = 14', predicate)
        self.assertEqual(self.validated['core_assertions'], 160)
        self.assertEqual(len(self.validated['assertions']), 318)
        self.assertEqual(self.validated['native_modules']['edu']['assertions'], 41)
        self.assertEqual(self.validated['native_modules']['extension']['assertions'], 114)
    def test_whole_controlled_chain_hold_is_bound_and_shortening_rejected(self):
        contract=self.written['coordinator_isolation_contract']
        self.assertEqual(contract['declared_hold_days'],180)
        self.assertEqual(contract['release_before_module'],'world_scheduler')
        text=self.validated['fixture_text'][f'events/{NEW.NS}.txt']
        hold='set_global_flag = { flag = eon_eu_daily_lifecycle_done days = 180 value = 1 }'
        self.assertIn(hold,text)
        world=NEW.build_world_scheduler(NEW.NS,NEW.MARK_V14)['fixture_text'][f'events/{NEW.NS}.txt']
        self.assertIn(contract['world_release_effect'],world)
        self.assertNotIn('days = 180',world)
        original=NEW.CONTROLLED_COORDINATOR_HOLD_DAYS
        try:
            NEW.CONTROLLED_COORDINATOR_HOLD_DAYS=90
            with self.assertRaisesRegex(AssertionError,'whole-chain isolation hold'):
                NEW.build_v14(self.source,self.output('rejected-short-coordinator-hold'),validate_only=True,additional_module_builders={})
        finally:NEW.CONTROLLED_COORDINATOR_HOLD_DAYS=original
        self.assertFalse(self.output('rejected-short-coordinator-hold').exists())
    def test_isolated_core_rounds_use_actual_proposal_authority_without_changing_golden144(self):
        text=self.validated['fixture_text'][f'events/{NEW.NS}.txt']
        first=text.index('BEGIN duplicate_council_yes_is_idempotent')
        prefix=text[:first]
        self.assertIn('eon_eu_start_council_proposal = yes',prefix)
        self.assertIn('eon_eu_appoint_office_1 = yes',prefix)
        first_ai=text.index('BEGIN native_council_ai_dispatch_answers_each_eligible_member_once')
        self.assertIn('eon_eu_start_council_proposal = yes',text[first:first_ai])
        self.assertEqual(self.validated['baseline_v12_contract_sha256'],NEW.BASELINE_V12_SHA256)
    def test_five_fixture_paths_and_all_copied_source_bytes_bound(self):
        self.assertEqual(len(self.written['fixture_sha256']), 5)
        self.assertEqual(set(self.written['source_sha256']), self.paths)
        for relative, digest in self.written['source_sha256'].items():
            self.assertEqual(digest, hashlib.sha256((self.source / relative).read_bytes()).hexdigest())
        for relative, digest in self.written['fixture_sha256'].items():
            path = self.base / 'written-template/mod' / relative
            self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(path.read_text('utf-8'), self.validated['fixture_text'][relative])
        text = self.validated['fixture_text'][f'events/{NEW.NS}.txt']
        self.assertEqual(text.count('RUN_END'), 1)
        self.assertNotIn('EON_EU_NATIVE_V13', text)
        startup = self.validated['fixture_text'][f'common/on_actions/{NEW.NS}.txt']
        self.assertIn('STARTUP fixture_version=14', startup)
    def test_callback24_and_conditional_diagnostics_are_carried(self):
        contract = self.validated['extension_callback_contract']
        self.assertEqual(contract['schema'], 1)
        self.assertEqual(len(contract['actions']), 24)
        optional = self.validated['diagnostic_observations']
        self.assertGreater(len(optional), 0)
        self.assertFalse(set(optional) & set(self.validated['required_observations']))
        for action in contract['actions']:
            for key in ('before_observation', 'raw_after_observation', 'after_observation'):
                self.assertIn(action[key], optional)
            self.assertNotIn(action['calibration_before_observation'], self.validated['required_observations'])
        self.assertEqual(self.validated['edu_native_callback_contract']['authorized_formed_commit_log'], 'EON_EDU FORMED_COMMIT')
    def test_plain_edu_prefix_binds_actual_effects_bytes(self):
        contract = self.written['edu_trace_source_contract']
        self.assertEqual(contract['prefix'], 'EON_EDU')
        self.assertEqual(tuple(contract['labels']), NEW.EDU_TRACE_LABELS)
        self.assertEqual(contract['sha256'], self.written['source_sha256'][contract['path']])
        path = self.source / contract['path']
        original = path.read_bytes()
        try:
            path.write_bytes(original.replace(b'EON_EDU CREATE_DECISION', b'[EON EDU] CREATE_DECISION', 1))
            with self.assertRaisesRegex(AssertionError, 'plain EON_EDU'):
                NEW.build_v14(self.source, self.output('rejected-old-trace'), additional_module_builders={})
            self.assertFalse(self.output('rejected-old-trace').exists())
        finally:
            path.write_bytes(original)
    def test_actual_public_input_hashes_are_bound_without_private_runtime_paths(self):
        inputs=self.written['native_builder_inputs']
        self.assertEqual(set(inputs),{'builder','extension','edu','diagnostic','source_ast','core_council'})
        for value in inputs.values():
            self.assertEqual(value['sha256'],hashlib.sha256(Path(value['path']).read_bytes()).hexdigest())
            self.assertTrue(Path(value['path']).is_relative_to(ROOT/'tools/validation'))
        text=(ROOT/'tools/validation/eu_lifecycle/build_native_probe.py').read_text('utf-8')
        self.assertNotIn('PRIVATE_INPUTS',text)
        self.assertNotIn('.local/edu-prototype',text)
    def test_additive_both_required_and_order_is_extension_edu_council_ep_world(self):
        builders = {'council': synthetic_additive('council', 7000), 'parliament': synthetic_additive('parliament', 7200)}
        result = NEW.build_v14(self.source, self.output('unused-additive'), validate_only=True,
                           additional_module_builders=builders, required_additional_modules=('council', 'parliament'))
        self.assertEqual(list(result['native_modules']), ['extension', 'edu', 'council', 'parliament', 'world_scheduler', 'faction_identity_diagnostic'])
        self.assertTrue(result['additive_module_contract']['acceptance_ready'])
        self.assertEqual(len(result['fixture_text']), 5)
        self.assertEqual(result['events'], self.validated['events'] + 4)
        self.assertEqual(set(result['native_builder_inputs']) - set(self.written['native_builder_inputs']), {'council', 'parliament'})
        events = {next(v for k, _, v in fields if k == 'id'): fields for k, _, fields in NEW.ast(result['fixture_text'][f'events/{NEW.NS}.txt']) if k == 'country_event'}
        def body(ident):
            return NEW.render_source_ast(next(v for k, _, v in events[f'{NEW.NS}.{ident}'] if k == 'immediate'))
        self.assertIn(f'id = {NEW.NS}.7000', body(3015))
        self.assertIn(f'id = {NEW.NS}.7200', body(7001))
        self.assertIn(f'id = {NEW.NS}.6000', body(7201))
    def test_required_additive_cannot_be_silently_omitted(self):
        self.assertFalse(self.validated['additive_module_contract']['acceptance_ready'])
        for builders, required in (({}, ('council',)), ({'council': synthetic_additive('council', 7000)}, ('council', 'parliament'))):
            with self.assertRaisesRegex(AssertionError, 'Required Council/EP module omitted'):
                NEW.build_v14(self.source, self.output('omitted-module'), validate_only=True,
                          additional_module_builders=builders, required_additional_modules=required)
        self.assertFalse(self.output('omitted-module').exists())
    def test_unknown_additive_and_wrong_event_range_are_rejected(self):
        with self.assertRaisesRegex(AssertionError, 'Unreviewed additive module'):
            NEW.build_v14(self.source, self.output('unknown-module'), validate_only=True,
                      additional_module_builders={'other': synthetic_additive('other', 7000)})
        with self.assertRaisesRegex(AssertionError, 'Module event outside reserved range: council'):
            NEW.build_v14(self.source, self.output('wrong-range'), validate_only=True,
                      additional_module_builders={'council': synthetic_additive('council', 7200)})
    def daily_module(self, name, start, effect):
        synthetic = synthetic_additive(name, start)
        def builder(namespace, marker, *, source, terminal_effect=''):
            module = synthetic(namespace, marker, source=source, terminal_effect=terminal_effect)
            relative = 'common/scripted_effects/eon_eu_voting_effects.txt'
            module['production_dependency_paths'].append(relative)
            module['production_input_sha256'][relative] = hashlib.sha256((source / relative).read_bytes()).hexdigest()
            module['on_daily_effect'] = effect
            return module
        return builder
    def test_additive_on_daily_merges_actual_helpers_private_observers_and_exact_proposal_hold(self):
        hook = ('if = { limit = { has_global_flag = ' + NEW.NS + '_council_scheduler_trace } '
                'eon_eu_recount_council_vote = yes add_to_variable = { global.' + NEW.NS + '_council_daily_callbacks = 1 } '
                'log = "PRIVATE SYNTHETIC DAILY OBSERVER" } ')
        ep_hook = ('if = { limit = { has_global_flag = ' + NEW.NS + '_parliament_trace } '
                   'set_global_flag = { flag = EP_AI_hold_their_vote days = 2 value = 1 } '
                   'eon_eu_recount_council_vote = yes } ')
        builders = {'council': self.daily_module('council', 7000, hook),
                    'parliament': self.daily_module('parliament', 7200, ep_hook)}
        result = NEW.build_v14(self.source, self.output('unused-daily-additive'), validate_only=True,
                           additional_module_builders=builders, required_additional_modules=('council', 'parliament'))
        daily = result['fixture_text'][f'common/on_actions/{NEW.NS}.txt']
        self.assertIn(hook, daily)
        self.assertIn(ep_hook, daily)
        self.assertIn(NEW.NS + '_world_scheduler_trace', daily)
        for name, text in (('council', hook), ('parliament', ep_hook)):
            contract = result['native_modules'][name]['daily_observer_contract']
            self.assertEqual(contract['sha256'], hashlib.sha256(text.encode()).hexdigest())
            self.assertEqual(contract['source_helpers'], ['eon_eu_recount_council_vote'])
        self.assertEqual(result['native_modules']['parliament']['daily_observer_contract']['declared_proposal_holds'], ['EP_AI_hold_their_vote'])
    def test_additive_daily_manual_deadline_unknown_helper_and_unbound_counter_are_rejected(self):
        bodies = (
            ('set_global_flag = { flag = eon_eu_vote_deadline days = 1 value = 1 } eon_eu_recount_council_vote = yes ', 'Daily flag writes'),
            ('clr_country_flag = eon_eu_withdrawal_deadline eon_eu_recount_council_vote = yes ', 'actual source-bound'),
            ('eon_nonexistent_helper = yes ', 'actual source-bound'),
            ('set_variable = { global.EU_member_count = 0 } eon_eu_recount_council_vote = yes ', 'private counters'),
            ('set_global_flag = { flag = EP_AI_hold_their_vote days = 1 value = 1 } eon_eu_recount_council_vote = yes ', 'Daily flag writes'))
        for body, expected in bodies:
            hook = 'if = { limit = { has_global_flag = ' + NEW.NS + '_council_scheduler_trace } ' + body + '} '
            with self.assertRaisesRegex(AssertionError, expected):
                NEW.build_v14(self.source, self.output('rejected-daily-mutant'), validate_only=True,
                          additional_module_builders={'council': self.daily_module('council', 7000, hook)})
        self.assertFalse(self.output('rejected-daily-mutant').exists())
    def test_duplicate_diagnostic_and_required_label_mutants_are_rejected(self):
        original = NEW.build_extension
        def mutant(*args, **kwargs):
            value = original(*args, **kwargs)
            value['diagnostic_observations'].append(value['diagnostic_observations'][0])
            return value
        try:
            NEW.build_extension = mutant
            with self.assertRaisesRegex(AssertionError, 'Duplicate optional diagnostic label'):
                NEW.build_v14(self.source, self.output('dup-diagnostic'), validate_only=True, additional_module_builders={})
        finally:
            NEW.build_extension = original
        def overlap(*args, **kwargs):
            value = original(*args, **kwargs)
            value['diagnostic_observations'].append(value['observations'][0])
            return value
        try:
            NEW.build_extension = overlap
            with self.assertRaisesRegex(AssertionError, 'cannot masquerade'):
                NEW.build_v14(self.source, self.output('overlap-diagnostic'), validate_only=True, additional_module_builders={})
        finally:
            NEW.build_extension = original
    def test_default_acceptance_requires_both_real_public_modules(self):
        self.assertEqual(set(NEW.default_additive_builders()),{'council','parliament'})
        # A missing actual module is fatal; structural omission requires {}.
        original=NEW.default_additive_builders
        try:
            NEW.default_additive_builders=lambda:{'council':synthetic_additive('council',7000)}
            with self.assertRaisesRegex(AssertionError,'Required Council/EP module omitted'):
                NEW.build_v14(self.source,self.output('rejected-missing-default'),validate_only=True)
        finally:NEW.default_additive_builders=original
    def test_synthetic_full_written_manifest_reaches_all24_analyzer_actions_and_hour24(self):
        manifest, path, game, errors, _ = self.synthetic_analysis('full-manifest-control')
        result = ANALYZER.analyze(path, game, errors)
        self.assertTrue(result['passed'], result['problems'])
        self.assertEqual(result['assertions_passed'], 318)
        self.assertEqual(len(result['extension_callback_evidence']['actions']), 24)
        self.assertTrue(result['extension_callback_evidence']['passed'])
        self.assertTrue(result['edu_callback_evidence']['passed'])
        self.assertEqual(result['diagnostic_result']['status'], 'native_goal_storage_unsupported')
        self.assertIn('.24] ', game.read_text('utf-8'))
        self.assertTrue(all(value['elapsed_hours'] >= value['minimum_hours'] for value in result['elapsed_game_time']))
        action = manifest['extension_callback_contract']['actions'][0]
        text = game.read_text('utf-8')
        game.write_text(text.replace(' TRACE ' + action['requested_trace'], ' TRACE CALLBACK_MISSING', 1), encoding='utf-8')
        mutated = ANALYZER.analyze(path, game, errors)
        self.assertFalse(mutated['passed'])
        self.assertFalse(mutated['extension_callback_evidence']['passed'])
    def test_synthetic_full_written_manifest_six_token_warnings_remain_fatal_even_in_baseline(self):
        _, path, game, errors, baseline = self.synthetic_analysis('full-token-controls')
        for token in ('EU_exit', 'EU_exit_three_month', 'EU_voting_mission_focus_EUXXX_QMV_result', 'EU_voting_mission_focus_EUXXX_QMV_result_timer', 'EU_parliament_focus_EUXXX_approve', 'EU_parliament_focus_EUXXX_approve_timer'):
            warning = '[07:01:02][no_game_date][scopedvariable.cpp:560]: Token ' + token + ' is a dynamic token, this can cause OOS depending on how it is used, please add it as a synchronized dynamic token\n'
            errors.write_text(warning, encoding='utf-8')
            baseline.write_text(warning.replace('07:01:02', '05:01:02'), encoding='utf-8')
            result = ANALYZER.analyze(path, game, errors, baseline)
            self.assertFalse(result['passed'])
            self.assertEqual(result['related_script_errors'], 1)
            self.assertEqual(result['preexisting_related_script_errors'], [])
            self.assertTrue(result['extension_callback_evidence']['passed'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
