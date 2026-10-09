"""Synthetic native-reader rejection and fixture-source grammar tests only."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util
import json
import sys
import tempfile
import unittest

from build_native_probe import (ROOT, build, p, sha, expense_reference, weekly_instrumentation,
                                restore_weekly_instrumentation, MONEY_REL, WEEKLY_REL, NS, HOOK)
from analyze_native_probe import analyze, parse_log


def synthetic(manifest):
    marker = manifest['marker']
    lines = [f'[2000.01.01.00] {marker} STARTUP native_nuclear_arsenal_upkeep']

    def checks(tag, phase, date):
        if phase == 'full_before':
            suffixes = ['initial_frame', 'refresh_free', 'arsenal_positive', 'default_full_ready']
        elif phase == 'safety':
            suffixes = ['safety_blocks', 'safety_cost']
        elif phase == 'resume':
            suffixes = ['refresh_does_not_recover']
        else:
            suffixes = [phase+'_'+suffix for suffix in ('frame', 'remaining', 'readiness', 'duplicate_blocked')]
        suffixes += [phase+'_'+suffix for suffix in ('rate_repeatable', 'budget_once', 'income_preserved')]
        lines.extend(f'[{date}] {marker} PASS {tag.lower()}_{suffix}' for suffix in suffixes)

    def observation(label):
        tag = manifest['expected_observation_actors'][label]
        phase = label.split('_', 1)[1]
        step = int(phase.removeprefix('week_')) if phase.startswith('week_') else 0
        date = '2000.01.'+f'{8+(step-1)*7:02d}'+'.12' if step else '2000.01.03.08'
        safety = int(phase == 'safety')
        full_cost = .00228
        cost = full_cost*.35 if safety else full_cost
        remaining = 4-step if step else 4 if phase == 'resume' else 0
        ready = int(phase == 'full_before' or step == 4)
        fields = dict(step=step, ready=ready, safety=safety, total=10, reserve=8,
                      deployed=2, cost=cost, expense=1+cost, remaining=remaining,
                      full_cost=full_cost, full_expense=1+full_cost,
                      treasury=10, treasury_before=10, base_expense=1,
                      rate_before=1+cost, rate_after=1+cost, gdp_pc=40,
                      workforce_gdp=.06, mining=.4 if tag == 'GER' else 0,
                      agrar=.56 if tag == 'GER' else 0, income=3, income_before=3,
                      latch=int(step > 0))
        if step:
            for stage in manifest['weekly_trace_stages']:
                trace = dict(weeks=step-1, remaining=5-step if stage == 'production_before' else 4-step,
                             cost=cost, expense=1+cost, treasury=10, active=1,
                             latch=int(stage != 'production_before'))
                lines.append(f'[{date}] {marker} TRACE {stage} ROOT={tag} THIS={tag} '+
                             ' '.join(f'{key}={value:.9f}' for key, value in trace.items()))
        checks(tag, phase, date)
        lines.append(f'[{date}] {marker} OBS {label} ROOT={tag} THIS={tag} '+
                     ' '.join(f'{key}={value:.9f}' for key, value in fields.items()))

    # Setup phases execute in one immediate country event. Later callbacks
    # execute chronologically, with each assertion preceding its own OBS.
    for tag in manifest['observed_countries']:
        for phase in ('full_before', 'safety', 'resume'):
            observation(tag.lower()+'_'+phase)
    for step in range(1, 5):
        for tag in manifest['observed_countries']:
            observation(tag.lower()+f'_week_{step}')
    lines.append(f'[2000.01.29.12] {marker} END passes={len(manifest["assertions"])} fails=0')
    return '\n'.join(lines)


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='upkeep-reader-', dir=ROOT/'.local')
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name).resolve()
        assert ROOT.resolve() in self.path.parents, 'Cleanup must remain inside the workspace'
        self.manifest = build(ROOT, self.path/'fixture', preparation_only=True)
        self.log = synthetic(self.manifest)

    def test_complete_synthetic_log_has_four_real_spaced_weekly_pulses(self):
        parsed = parse_log(self.log, self.manifest)
        self.assertEqual(parsed['failed'], [])
        self.assertEqual(parsed['weekly_interval_native_hours'], {tag: [168]*3 for tag in ('GER', 'FRA', 'RAJ')})
        self.assertTrue(parsed['budget_component_replaced_once'])

    def test_fixture_is_actual_ast_and_uses_documented_native_grammar(self):
        spec = importlib.util.spec_from_file_location('arsenal_fixture_grammar', ROOT/'tools/validation/diplomacy_completion/check_native_grammar.py')
        grammar = importlib.util.module_from_spec(spec); sys.modules[spec.name] = grammar
        spec.loader.exec_module(grammar)
        for relative in self.manifest['fixture_sha256']:
            raw = (self.path/'fixture/mod'/relative).read_bytes()
            self.assertEqual(grammar.inspect(p.ast(raw)), [])
        observer = p.one(p.ast((self.path/'fixture/mod/common/on_actions/zz_eon_private_upkeep.txt').read_bytes()), 'on_actions')
        weekly = p.one(p.one(observer, 'on_weekly'), 'effect')
        self.assertEqual(len([node for node in weekly if node[0] == 'if']), 4)
        self.assertEqual(len(self.manifest['assertions']), 132)
        self.assertEqual(len(self.manifest['observation_labels']), 21)

    def test_fixture_uses_same_input_budget_and_scaled_integer_delta(self):
        source = (self.path/'fixture/mod/events/eon_private_upkeep_events.txt').read_text(encoding='utf-8')
        weekly = (self.path/'fixture/mod/common/on_actions/zz_eon_private_upkeep.txt').read_text(encoding='utf-8')
        joined = source+weekly
        self.assertEqual(joined.count('eon_private_upkeep_expense_reference = yes'), 21)
        self.assertEqual(joined.count('set_variable = { additional_income_rate = eon_private_upkeep_income_before }'), 21)
        self.assertEqual(joined.count('multiply_variable = { eon_private_upkeep_delta = 1000000 }'), 45)
        self.assertNotIn('value = 0.00001', source)
        self.assertNotIn('value = -0.00001', source)
        self.assertEqual(joined.count('value = 11 compare = less_than'), 45)
        self.assertEqual(joined.count('value = -11 compare = greater_than'), 45)
        self.assertEqual(self.manifest['fixture_version'], 4)
        self.assertEqual(self.manifest['budget_reference_mode'], 'same_input_exact_hook_inverse')
        for tag in ('ger', 'fra', 'raj'):
            self.assertIn(tag+'_full_before_budget_once', self.manifest['assertions'])

    def test_private_reference_removes_only_exact_hook_and_preserves_other_body(self):
        raw = (ROOT/MONEY_REL).read_bytes()
        reference = expense_reference(raw)
        original = p.one(p.ast(raw), 'calculate_additional_expense_rate')
        expected = original[:1]+original[3:]
        self.assertEqual(p.ast(reference), expected)
        self.assertIn('add_to_variable = { additional_income_rate = energy_selling_income }', reference)
        self.assertIn('GER_subventions_mining', reference)
        helper = (self.path/f'fixture/mod/common/scripted_effects/{NS}_expense_reference.txt').read_bytes()
        self.assertEqual(helper, (f'{NS}_expense_reference = {{'+reference+'}\n').encode('utf-8'))
        with self.assertRaises(AssertionError): expense_reference(raw.replace(HOOK.encode(), b'', 1))
        with self.assertRaises(AssertionError): expense_reference(raw.replace(HOOK.encode(), HOOK.replace('weekly_cost', 'altered_cost').encode(), 1))

    def test_private_weekly_copy_has_exact_inverse_and_preserves_bom_eol(self):
        raw = (ROOT/WEEKLY_REL).read_bytes()
        instrumented, changes = weekly_instrumentation(raw)
        self.assertEqual(changes, self.manifest['private_weekly_replacements'])
        self.assertEqual(restore_weekly_instrumentation(instrumented, changes), raw)
        self.assertEqual(instrumented.startswith(b'\xef\xbb\xbf'), raw.startswith(b'\xef\xbb\xbf'))
        self.assertEqual(instrumented.count(b'\r\n'), raw.count(b'\r\n'))
        self.assertEqual((self.path/'fixture/mod'/WEEKLY_REL).read_bytes(), instrumented)
        with self.assertRaises(AssertionError): restore_weekly_instrumentation(instrumented.replace(b'production_after', b'changed_after', 1), changes)

    def test_older_fixture_manifest_cannot_be_relabelled_as_fresh_native_proof(self):
        manifest = deepcopy(self.manifest); manifest['fixture_version'] = 2
        with self.assertRaises(AssertionError): parse_log(self.log, manifest)

    def test_frozen_preparation_cannot_be_overwritten(self):
        with self.assertRaises(AssertionError): build(ROOT, self.path/'fixture', preparation_only=True)

    def test_duplicate_missing_or_extra_assertion_is_rejected(self):
        marker, label = self.manifest['marker'], self.manifest['assertions'][0]
        variants = [self.log+'\n'+marker+' PASS '+label,
                    self.log.replace(marker+' PASS '+label, 'other text', 1),
                    self.log+'\n'+marker+' PASS unexpected']
        for text in variants:
            with self.subTest(text=text[-80:]), self.assertRaises(AssertionError): parse_log(text, self.manifest)

    def test_assertions_outside_run_or_wrong_phase_date_are_rejected(self):
        rows = self.log.splitlines()
        assertions = [row for row in rows if ' PASS ' in row]
        variants = ['\n'.join([row for row in rows if ' PASS ' not in row]+assertions)]
        first = next(row for row in rows if ' PASS ger_initial_frame' in row)
        variants.append(self.log.replace(first, first.replace('2000.01.03.08', '2000.01.04.08')))
        week = next(row for row in rows if ' PASS ger_week_1_frame' in row)
        variants.append(self.log.replace(week+'\n', '', 1)+'\n'+week)
        safety = next(row for row in rows if ' PASS ger_safety_blocks' in row)
        full = next(row for row in rows if ' OBS ger_full_before ' in row)
        variants.append(self.log.replace(safety+'\n', '', 1).replace(full, safety+'\n'+full, 1))
        for log in variants:
            with self.subTest(log=log[-80:]), self.assertRaises(AssertionError): parse_log(log, self.manifest)

    def test_startup_end_and_immediate_phase_dates_are_bound(self):
        rows = self.log.splitlines()
        first, last = rows[0], rows[-1]
        variants = [self.log.replace(first, first.replace('2000.01.01.00', '2099.01.01.00')),
                    self.log.replace(last, last.replace('2000.01.29.12', '1999.01.01.00'))]
        delayed = []
        for row in rows:
            if 'ger_safety' in row: row = row.replace('2000.01.03.08', '2000.01.04.08')
            if 'ger_resume' in row or 'PASS ger_refresh_does_not_recover' in row:
                row = row.replace('2000.01.03.08', '2000.01.05.08')
            delayed.append(row)
        variants.append('\n'.join(delayed))
        for log in variants:
            with self.subTest(log=log[-80:]), self.assertRaises(AssertionError): parse_log(log, self.manifest)

    def test_numeric_records_require_exact_finite_tokens(self):
        row = next(line for line in self.log.splitlines() if ' OBS ger_full_before ' in line)
        trace = next(line for line in self.log.splitlines() if 'TRACE production_before ROOT=GER' in line)
        variants = [self.log.replace(row, row.replace(' cost=', ' Xcost=')),
                    self.log.replace(row, row.replace('cost=0.002280000', 'cost=0.002280000e999')),
                    self.log.replace(row, row+' unexpected=NaN'),
                    self.log.replace(trace, trace.replace('cost=0.002280000', 'cost=0.002280000oops')),
                    self.log.replace(trace, trace.replace('cost=0.002280000', 'cost=NaN'))]
        for log in variants:
            self.assertNotEqual(log, self.log)
            with self.assertRaises(AssertionError): parse_log(log, self.manifest)

    def test_wrong_country_or_duplicate_observation_is_rejected(self):
        variants = [self.log.replace('ROOT=GER THIS=GER', 'ROOT=RAJ THIS=GER', 1),
                    self.log.replace('ROOT=FRA THIS=FRA', 'ROOT=FRA THIS=RAJ', 1)]
        row = next(line for line in self.log.splitlines() if 'OBS ger_resume ' in line)
        variants.append(self.log.replace(row, row+'\n'+row))
        for text in variants:
            with self.assertRaises(AssertionError): parse_log(text, self.manifest)

    def test_fake_rapid_progress_and_wrong_weekly_order_are_rejected(self):
        variants = [self.log.replace('2000.01.15.12', '2000.01.09.12'),
                    self.log.replace('2000.01.08.12', '2000.01.03.08')]
        rows = self.log.splitlines()
        one = next(i for i, line in enumerate(rows) if 'OBS ger_week_1 ' in line)
        two = next(i for i, line in enumerate(rows) if 'OBS ger_week_2 ' in line)
        rows[one], rows[two] = rows[two], rows[one]
        variants.append('\n'.join(rows))
        for text in variants:
            with self.assertRaises(AssertionError): parse_log(text, self.manifest)

    def test_wrong_budget_safety_price_or_direct_charge_is_rejected(self):
        safety = next(line for line in self.log.splitlines() if 'OBS ger_safety ' in line)
        full = next(line for line in self.log.splitlines() if 'OBS ger_full_before ' in line)
        variants = [self.log.replace(safety, safety.replace('cost=0.000798000', 'cost=0.002280000')),
                    self.log.replace(safety, safety.replace('expense=1.000798000', 'expense=1.001596000')),
                    self.log.replace(safety, safety.replace('treasury=10.000000000', 'treasury=9.000000000')),
                    self.log.replace(full, full.replace('total=10.000000000', 'total=9.000000000'))]
        for text in variants:
            self.assertNotEqual(text, self.log)
            with self.assertRaises(AssertionError): parse_log(text, self.manifest)

    def test_incorrect_readiness_or_remaining_count_is_rejected(self):
        last = next(line for line in self.log.splitlines() if 'OBS raj_week_4 ' in line)
        first = next(line for line in self.log.splitlines() if 'OBS ger_week_1 ' in line)
        for text in (self.log.replace(last, last.replace('ready=1.000000000', 'ready=0.000000000')),
                     self.log.replace(first, first.replace('remaining=3.000000000', 'remaining=0.000000000'))):
            with self.assertRaises(AssertionError): parse_log(text, self.manifest)

    def test_inflated_manifest_tolerance_is_rejected(self):
        manifest = deepcopy(self.manifest); manifest['numeric_tolerance'] = 1
        with self.assertRaises(AssertionError): parse_log(self.log, manifest)

    def test_changing_existing_budget_is_allowed_only_with_exact_same_input_component(self):
        rows = self.log.splitlines()
        for index, row in enumerate(rows):
            if 'OBS ger_safety ' in row:
                rows[index] = row.replace('base_expense=1.000000000', 'base_expense=1.020000000').replace(
                    'expense=1.000798000', 'expense=1.020798000').replace(
                    'rate_before=1.000798000', 'rate_before=1.020798000').replace(
                    'rate_after=1.000798000', 'rate_after=1.020798000')
        parsed = parse_log('\n'.join(rows), self.manifest)
        self.assertTrue(parsed['budget_component_replaced_once'])
        # Same-input strict check still rejects a missing/double component.
        changed = '\n'.join(rows).replace('base_expense=1.020000000', 'base_expense=1.021000000', 1)
        with self.assertRaises(AssertionError): parse_log(changed, self.manifest)

    def test_missing_or_wrong_native_latch_and_upstream_order_are_rejected(self):
        first = next(line for line in self.log.splitlines() if 'OBS ger_week_1 ' in line)
        trace = next(line for line in self.log.splitlines() if 'TRACE production_after ROOT=GER' in line)
        variants = [self.log.replace(first, first.replace('latch=1.000000000', 'latch=0.000000000')),
                    self.log.replace(trace, trace.replace('latch=1.000000000', 'latch=0.000000000')),
                    self.log.replace(trace, trace.replace('remaining=3.000000000', 'remaining=2.000000000')),
                    self.log.replace(trace, '')]
        rows = self.log.splitlines()
        before = next(i for i, line in enumerate(rows) if 'TRACE production_before ROOT=GER' in line)
        after = next(i for i, line in enumerate(rows) if 'TRACE production_after ROOT=GER' in line)
        rows[before], rows[after] = rows[after], rows[before]
        variants.append('\n'.join(rows))
        for log in variants:
            with self.assertRaises(AssertionError): parse_log(log, self.manifest)

    def test_legacy_v3_budget_rule_is_preserved_without_drift_allowance(self):
        manifest = deepcopy(self.manifest)
        manifest.update(fixture_version=3, budget_baseline_refreshes=3)
        legacy_fields = ['step','ready','safety','total','reserve','deployed','cost','expense',
                         'remaining','full_cost','full_expense','treasury','treasury_before']
        manifest['observation_fields'] = legacy_fields
        rows = []
        for row in self.log.splitlines():
            if ' TRACE ' in row: continue
            if ' OBS ' in row:
                row = row.split(' base_expense=')[0]
            rows.append(row)
        legacy = '\n'.join(rows)
        self.assertTrue(parse_log(legacy, manifest)['budget_component_replaced_once'])
        safety = next(line for line in rows if 'OBS ger_safety ' in line)
        changed = legacy.replace(safety, safety.replace('expense=1.000798000', 'expense=1.020798000'))
        with self.assertRaises(AssertionError): parse_log(changed, manifest)

    def test_native_failure_remains_failure(self):
        label = self.manifest['assertions'][0]
        log = self.log.replace('PASS '+label, 'FAIL '+label, 1)
        log = log.replace(f'passes={len(self.manifest["assertions"])} fails=0',
                          f'passes={len(self.manifest["assertions"])-1} fails=1')
        self.assertEqual(parse_log(log, self.manifest)['failed'], [label])

    def test_native_hour_24_is_normalized(self):
        log = self.log
        for day in (8, 15, 22, 29):
            log = log.replace(f'2000.01.{day:02d}.12', f'2000.01.{day-1:02d}.24')
        parsed = parse_log(log, self.manifest)
        self.assertEqual(parsed['weekly_interval_native_hours']['GER'], [168]*3)

    def binding_fixture(self):
        source = self.path/'source'; source.mkdir()
        for relative in self.manifest['source_sha256']:
            path = source/relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT/relative).read_bytes())
        for relative in self.manifest['fixture_sha256']:
            path = source/relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((self.path/'fixture/mod'/relative).read_bytes())
        export = self.path/'export.json'; export.write_text('{"synthetic":true}', encoding='utf-8')
        manifest = deepcopy(self.manifest)
        manifest.update(source_root=str(source), preparation_only=False,
                        source_export_binding=dict(path=str(export), sha256=sha(export)))
        manifest_path = self.path/'fixture/manifest.json'
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        user = self.path/'userdata'; (user/'logs').mkdir(parents=True); (user/'mod').mkdir()
        game_log = user/'logs/game.log'; game_log.write_text(self.log, encoding='utf-8')
        (user/'logs/error.log').write_text('', encoding='utf-8')
        (user/'logs/system.log').write_text('Active Mod Count: 1\nActive Mod: Synthetic upkeep fixture\n', encoding='utf-8')
        (user/'dlc_load.json').write_text(json.dumps(dict(enabled_mods=['mod/era_of_nations.mod'])), encoding='utf-8')
        (user/'mod/era_of_nations.mod').write_text('name="Synthetic upkeep fixture"\npath="'+source.as_posix()+'"\n', encoding='utf-8')
        exe = self.path/'synthetic-executable.txt'; exe.write_text('this is not a game executable', encoding='utf-8')
        instant = (datetime.now(timezone.utc)-timedelta(seconds=2)).isoformat()
        start = dict(pid=12345, exe=str(exe), arguments=['-start_tag=NEP'], process_start_utc=instant)
        start_path = self.path/'start.json'; start_path.write_text(json.dumps(start), encoding='utf-8')
        launch = dict(schema=1, pid=12345, exe=str(exe), exe_sha256=sha(exe),
                      source_root=str(source), manifest_sha256=sha(manifest_path), embedded_fixture=True,
                      embedded_root=str(source), enabled_mods=['mod/era_of_nations.mod'], user_dir=str(user),
                      game_log=str(game_log), source_export_receipt_sha256=sha(export), start_receipt=str(start_path),
                      process_start_utc=instant, embedded_source_sha256=manifest['fixture_sha256'])
        launch_path = self.path/'launch.json'; launch_path.write_text(json.dumps(launch), encoding='utf-8')
        return manifest_path, launch_path, game_log

    def test_synthetic_bound_shape_exercises_receipt_validator_only(self):
        result = analyze(*self.binding_fixture())
        self.assertTrue(result['native_nuclear_arsenal_upkeep_probe_passed'])
        self.assertFalse(result['actual_raid_launch_verified'])
        # This test's fabricated executable, PID and log are explicitly synthetic.

    def test_wrong_manifest_pid_source_fixture_or_export_hash_is_rejected(self):
        paths = self.binding_fixture(); manifest_path, launch_path, log = paths
        original = launch_path.read_text(encoding='utf-8')
        for key, value in (('manifest_sha256', '0'*64), ('pid', 54321),
                           ('source_export_receipt_sha256', '0'*64), ('embedded_source_sha256', {})):
            receipt = json.loads(original); receipt[key] = value
            launch_path.write_text(json.dumps(receipt), encoding='utf-8')
            with self.subTest(key=key), self.assertRaises(AssertionError): analyze(*paths)
        launch_path.write_text(original, encoding='utf-8')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        changed = Path(manifest['source_root'])/'common/scripted_effects/eon_nuclear_arsenal_effects.txt'
        changed.write_bytes(changed.read_bytes()+b'\n# Changed after launch\n')
        with self.assertRaises(AssertionError): analyze(*paths)

    def test_changed_private_reference_or_source_outside_trace_fails_binding(self):
        paths = self.binding_fixture()
        manifest = json.loads(paths[0].read_text(encoding='utf-8'))
        source = Path(manifest['source_root'])
        path = source/WEEKLY_REL
        original = path.read_bytes()
        path.write_bytes(original.replace(b'worker_requirements_variable_gdpc_converging = yes', b'worker_requirements_variable_gdpc_converging = no', 1))
        with self.assertRaises(AssertionError): analyze(*paths)
        path.write_bytes(original)
        reference = source/f'common/scripted_effects/{NS}_expense_reference.txt'
        reference.write_bytes(reference.read_bytes()+b'\n# changed\n')
        with self.assertRaises(AssertionError): analyze(*paths)

    def test_selected_native_script_error_prevents_acceptance(self):
        paths = self.binding_fixture()
        (paths[2].parent/'error.log').write_text('Invalid eon_nuclear_arsenal_ready trigger', encoding='utf-8')
        self.assertFalse(analyze(*paths)['native_nuclear_arsenal_upkeep_probe_passed'])


if __name__ == '__main__': unittest.main(verbosity=2)
