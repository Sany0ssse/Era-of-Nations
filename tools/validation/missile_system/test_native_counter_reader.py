"""Portable synthetic counter-reader regressions, without native game claims."""
import ast
from copy import deepcopy
from datetime import datetime, timedelta
import unittest

from analyze_native_probe import parse_log
from build_native_probe import MARKER, ROOT


TAGS = ('ger', 'fra', 'raj')
PHASES = ('baseline', 'reserve_added', 'loaded', 'after_day')
ASSERTION_SUFFIXES = (
    'reserve_added_nuclear_reserve', 'reserve_added_short_nuclear_reserve',
    'reserve_added_guided_reserve', 'reserve_added_ballistic_reserve',
    'frame_initial', 'history_registered', 'missile_base_techs_enabled',
    'initial_deployed_total_twelve_experiment', 'control_fighter_deployed',
    'owned_controlled_capital', 'rocket_site_ready', 'frame_after_day',
    'deployed_total_at_least_twelve_experiment', 'control_fighter_still_deployed',
    'deployed_nuclear_enum_positive', 'deployed_ballistic_enum_positive',
)


def current_manifest():
    # Read the exact getter map from the current builder without invoking build,
    # writing a fixture, or depending on an ignored private manifest/log.
    tree = ast.parse((ROOT / 'tools/validation/missile_system/build_native_probe.py').read_text(encoding='utf-8-sig'))
    build = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'build')
    counters = next(node.value for node in build.body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == 'counters' for target in node.targets))
    labels = [tag + '_' + phase for tag in TAGS for phase in PHASES]
    return dict(marker=MARKER,
                assertions=[tag + '_' + suffix for tag in TAGS for suffix in ASSERTION_SUFFIXES],
                observation_labels=labels,
                expected_observation_actors={label: label.split('_', 1)[0].upper() for label in labels},
                observation_fields=ast.literal_eval(counters),
                minimum_total_native_hours=24,
                deployment_method='private_history_merged_date_set_air_oob')


def synthetic(manifest, deployed=True):
    marker = manifest['marker']
    lines = [f'[2000.01.01.00] {marker} STARTUP native_missile_inventory_deployment']
    passed = failed = 0

    def check(tag, suffix, date, condition=True):
        nonlocal passed, failed
        passed += int(condition)
        failed += int(not condition)
        lines.append(f'[{date}] {marker} {"PASS" if condition else "FAIL"} {tag}_{suffix}')

    def observation(tag, phase, date):
        values = dict.fromkeys(manifest['observation_fields'], 0)
        values.update(all_deployed_planes=12 if deployed else 1,
                      control_fighter_deployed_archetype=1, control_fighter_deployed_enum=1,
                      control_fighter_deployed_model=1)
        if deployed:
            values.update(nuclear_deployed_archetype=2, nuclear_deployed_enum=2,
                          short_nuclear_deployed_archetype=4, ballistic_deployed_enum=7,
                          guided_deployed_archetype=2, guided_deployed_enum=2,
                          ballistic_deployed_archetype=3, nuclear_deployed_model=2,
                          short_nuclear_deployed_model=4, guided_deployed_model=2,
                          ballistic_deployed_model=3)
        if phase != 'baseline':
            values.update(nuclear_reserve=3, short_nuclear_reserve=5, guided_reserve=7, ballistic_reserve=11)
        actor = tag.upper()
        lines.append(f'[{date}] {marker} OBS {tag}_{phase} ROOT={actor} THIS={actor} ' +
                     ' '.join(f'{key}={value:.3f}' for key, value in values.items()))

    initial = '2000.01.01.00'
    for tag in TAGS:
        for suffix in ('frame_initial', 'history_registered', 'missile_base_techs_enabled'):
            check(tag, suffix, initial)
        observation(tag, 'baseline', initial)
        check(tag, 'initial_deployed_total_twelve_experiment', initial, deployed)
        check(tag, 'control_fighter_deployed', initial)
        observation(tag, 'reserve_added', initial)
        for field in ('nuclear_reserve', 'short_nuclear_reserve', 'guided_reserve', 'ballistic_reserve'):
            check(tag, 'reserve_added_' + field, initial)
        for suffix in ('owned_controlled_capital', 'rocket_site_ready'):
            check(tag, suffix, initial)
        observation(tag, 'loaded', initial)
    after = (datetime(2000, 1, 1) + timedelta(hours=25)).strftime('%Y.%m.%d.%H')
    for tag in TAGS:
        check(tag, 'frame_after_day', after)
        observation(tag, 'after_day', after)
        check(tag, 'deployed_total_at_least_twelve_experiment', after, deployed)
        check(tag, 'control_fighter_still_deployed', after)
        for suffix in ('deployed_nuclear_enum_positive', 'deployed_ballistic_enum_positive'):
            check(tag, suffix, after, deployed)
    lines.append(f'[{after}] {marker} END passes={passed} fails={failed}')
    return '\n'.join(lines)


class NativeCounterReader(unittest.TestCase):
    def setUp(self):
        self.manifest = current_manifest()
        self.log = synthetic(self.manifest)

    def rejected(self, text):
        with self.assertRaises(AssertionError):
            parse_log(text, self.manifest)

    def test_complete_synthetic_current_manifest_shape(self):
        self.assertEqual(len(self.manifest['assertions']), 48)
        self.assertEqual(len(self.manifest['observation_labels']), 12)
        self.assertEqual(len(self.manifest['observation_fields']), 24)
        self.assertTrue(all(isinstance(value, str) for value in self.manifest['observation_fields'].values()))
        parsed = parse_log(self.log, self.manifest)
        self.assertCountEqual(parsed['passed'], self.manifest['assertions'])
        self.assertEqual(parsed['failed'], [])
        self.assertEqual(len(parsed['observations']), 12)
        for tag in TAGS:
            self.assertEqual(parsed['native_counter_semantics'][tag]['elapsed_native_hours'], 25)
            self.assertEqual(parsed['observations'][tag + '_reserve_added']['nuclear_reserve'], 3)

    def test_wrong_missing_or_duplicate_field_is_rejected(self):
        for before, after in (
            ('nuclear_reserve=0.000', 'wrong_reserve=0.000'),
            ('nuclear_reserve=0.000 ', ''),
            ('nuclear_reserve=0.000', 'nuclear_reserve=0.000 nuclear_reserve=0.000'),
        ):
            with self.subTest(after=after):
                self.rejected(self.log.replace(before, after, 1))

    def test_missing_or_duplicate_observation_is_rejected(self):
        row = next(line for line in self.log.splitlines() if ' OBS ger_baseline ' in line)
        self.rejected(self.log.replace(row + '\n', '', 1))
        self.rejected(self.log + '\n' + row)

    def test_wrong_observation_label_or_actor_is_rejected(self):
        for before, after in (('OBS ger_baseline ', 'OBS unexpected_baseline '),
                              ('ROOT=GER THIS=GER', 'ROOT=GER THIS=FRA')):
            with self.subTest(after=after):
                self.rejected(self.log.replace(before, after, 1))

    def test_missing_or_duplicate_startup_is_rejected(self):
        row = self.log.splitlines()[0]
        self.rejected(self.log.replace(row + '\n', '', 1))
        self.rejected(self.log + '\n' + row)

    def test_missing_duplicate_or_wrong_summary_is_rejected(self):
        row = self.log.splitlines()[-1]
        self.rejected(self.log.replace('\n' + row, '', 1))
        self.rejected(self.log + '\n' + row)
        self.rejected(self.log.replace('END passes=48 fails=0', 'END passes=47 fails=0'))

    def test_missing_duplicate_or_unexpected_assertion_is_rejected(self):
        row = next(line for line in self.log.splitlines() if ' PASS ' in line)
        self.rejected(self.log.replace(row + '\n', '', 1))
        self.rejected(self.log + '\n' + row)
        self.rejected(self.log.replace('PASS ' + self.manifest['assertions'][0], 'PASS unexpected_assertion', 1))

    def test_native_failures_remain_reported_failures_with_zero_counters(self):
        failed = [tag + '_' + suffix for tag in TAGS for suffix in (
            'initial_deployed_total_twelve_experiment', 'deployed_total_at_least_twelve_experiment',
            'deployed_nuclear_enum_positive', 'deployed_ballistic_enum_positive')]
        text = synthetic(self.manifest, deployed=False)
        parsed = parse_log(text, self.manifest)
        self.assertCountEqual(parsed['failed'], failed)
        self.assertEqual(len(parsed['passed']), 36)
        self.assertEqual(len(parsed['failed']), 12)
        self.assertTrue(all(row['nuclear_deployed_archetype'] == row['short_nuclear_deployed_archetype'] == 0
                            for row in parsed['observations'].values()))

    def test_zero_deployed_fake_pass_is_rejected(self):
        text = synthetic(self.manifest, deployed=False).replace(' FAIL ', ' PASS ')
        self.rejected(text.replace('END passes=36 fails=12', 'END passes=48 fails=0'))

    def test_missing_fighter_control_is_rejected(self):
        self.rejected(self.log.replace('control_fighter_deployed_archetype=1.000',
                                       'control_fighter_deployed_archetype=0.000'))

    def test_negative_counter_is_rejected(self):
        self.rejected(self.log.replace('nuclear_equipment_in_armies=0.000',
                                       'nuclear_equipment_in_armies=-1.000', 1))

    def test_wrong_reserve_delta_pass_is_rejected(self):
        self.rejected(self.log.replace('guided_reserve=7.000', 'guided_reserve=8.000'))

    def test_contradictory_fail_is_rejected(self):
        text = self.log.replace('PASS ger_deployed_nuclear_enum_positive',
                                'FAIL ger_deployed_nuclear_enum_positive')
        self.rejected(text.replace('END passes=48 fails=0', 'END passes=47 fails=1'))

    def test_wrong_assertion_date_or_position_is_rejected(self):
        row = next(line for line in self.log.splitlines() if ' PASS ger_frame_initial' in line)
        self.rejected(self.log.replace(row, row.replace('2000.01.01.00', '2000.01.02.00')))
        self.rejected(self.log.replace(row + '\n', '', 1) + '\n' + row)

    def test_wrong_startup_summary_or_phase_date_is_rejected(self):
        first, last = self.log.splitlines()[0], self.log.splitlines()[-1]
        self.rejected(self.log.replace(first, first.replace('2000.01.01.00', '2000.01.03.00')))
        self.rejected(self.log.replace(last, last.replace('2000.01.02.01', '2000.01.01.00')))
        row = next(line for line in self.log.splitlines() if ' OBS ger_loaded ' in line)
        self.rejected(self.log.replace(row, row.replace('2000.01.01.00', '2000.01.01.01')))

    def test_wrong_root_frame_is_rejected(self):
        self.rejected(self.log.replace('ROOT=GER THIS=GER', 'ROOT=FRA THIS=GER', 1))

    def test_abort_and_duplicate_event_are_rejected(self):
        for signal in ('ABORT incomplete_country_probes', 'DUPLICATE_EVENT initial_GER'):
            with self.subTest(signal=signal):
                self.rejected(self.log + '\n' + self.manifest['marker'] + ' ' + signal)

    def test_short_native_elapsed_is_rejected(self):
        manifest = deepcopy(self.manifest)
        manifest['minimum_total_native_hours'] = 26
        with self.assertRaises(AssertionError):
            parse_log(self.log, manifest)

    def test_native_hour_24_is_normalized(self):
        text = self.log.replace('2000.01.02.01', '2000.01.01.24')
        parsed = parse_log(text, self.manifest)
        self.assertEqual({row['elapsed_native_hours'] for row in parsed['native_counter_semantics'].values()}, {24})


if __name__ == '__main__':
    unittest.main(verbosity=2)
