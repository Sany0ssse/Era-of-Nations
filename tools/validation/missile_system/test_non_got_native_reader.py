"""Synthetic evidence rejection tests; these are not native game runs."""
from copy import deepcopy
import unittest

from analyze_non_got_history_native_probe import parse_log


class NonGotNativeReader(unittest.TestCase):
    def setUp(self):
        self.manifest = dict(marker='PRIVATE_READER_TEST', assertions=['startup', 'later'],
                             observed_countries=['USA', 'GER', 'BRA', 'UKR'],
                             expected_native_start_tag='NEP', minimum_total_native_hours=48,
                             history_rows={tag: dict(launchers=value) for tag, value in
                                           [('USA', 7), ('GER', 3), ('BRA', 6), ('UKR', None)]})
        self.log = '\n'.join([
            '[2000.01.01.12] PRIVATE_READER_TEST STARTUP native_no_got_missile_history',
            '[2000.01.01.13] PRIVATE_READER_TEST PASS startup',
            *[f'[2000.01.01.13] PRIVATE_READER_TEST OBS {tag.lower()}_initial ROOT=NEP THIS={tag} launchers={value}'
              for tag, value in [('USA', 7), ('GER', 3), ('BRA', 6), ('UKR', 0)]],
            '[2000.01.03.13] PRIVATE_READER_TEST PASS later',
            '[2000.01.03.13] PRIVATE_READER_TEST OBS observer_later ROOT=NEP THIS=NEP launchers=0',
            '[2000.01.03.13] PRIVATE_READER_TEST END passes=2 fails=0',
        ])

    def test_complete_synthetic_reader_shape(self):
        result = parse_log(self.log, self.manifest)
        self.assertEqual(result['failed'], [])
        self.assertEqual(result['elapsed_native_hours'], {tag: 48 for tag in ('USA', 'GER', 'BRA', 'UKR')})

    def test_duplicate_assertion_cannot_pass(self):
        with self.assertRaises(AssertionError):
            parse_log(self.log + '\nPRIVATE_READER_TEST PASS startup', self.manifest)

    def test_missing_assertion_cannot_pass(self):
        with self.assertRaises(AssertionError):
            parse_log(self.log.replace('PRIVATE_READER_TEST PASS startup', 'other text'), self.manifest)

    def test_wrong_country_or_observer_cannot_pass(self):
        for before, after in [('ROOT=NEP THIS=USA', 'ROOT=USA THIS=USA'), ('THIS=GER', 'THIS=BRA')]:
            with self.subTest(after=after), self.assertRaises(AssertionError):
                parse_log(self.log.replace(before, after), self.manifest)

    def test_short_native_elapsed_or_late_initial_snapshot_cannot_pass(self):
        for before, after in [('2000.01.03.13', '2000.01.02.13'), ('2000.01.01.13', '2000.01.02.13')]:
            with self.subTest(after=after), self.assertRaises(AssertionError):
                parse_log(self.log.replace(before, after), self.manifest)

    def test_wrong_source_launcher_cap_cannot_pass(self):
        with self.assertRaises(AssertionError):
            parse_log(self.log.replace('THIS=USA launchers=7', 'THIS=USA launchers=8'), self.manifest)

    def test_native_failure_remains_a_reported_failure(self):
        text = self.log.replace('PASS later', 'FAIL later').replace('passes=2 fails=0', 'passes=1 fails=1')
        self.assertEqual(parse_log(text, self.manifest)['failed'], ['later'])

    def test_native_hour_24_is_normalized(self):
        manifest = deepcopy(self.manifest)
        manifest['minimum_total_native_hours'] = 35
        text = self.log.replace('2000.01.03.13', '2000.01.02.24')
        self.assertEqual(parse_log(text, manifest)['elapsed_native_hours']['USA'], 35)


if __name__ == '__main__':
    unittest.main(verbosity=2)
