"""Preserve every byte outside budget hooks and the market reset."""
from pathlib import Path
import subprocess
import unittest
from byte_compat import INSERTIONS, MARKET_RESET, restore_arsenal_budget

ROOT = Path(__file__).resolve().parents[3]
BASE = '2b6a26e76c80f7923d11ebc2c0694e882253fb32'


class PreservationTests(unittest.TestCase):
    def test_all_non_hook_bytes_equal_pre_packet_source(self):
        for path in INSERTIONS:
            with self.subTest(path=path):
                before = subprocess.check_output(['git', 'show', BASE+':'+path], cwd=ROOT)
                current = (ROOT/path).read_bytes()
                self.assertEqual(restore_arsenal_budget(path, current), before)

    def test_altered_and_duplicate_hook_cannot_be_normalized(self):
        for path, insertion in INSERTIONS.items():
            current = (ROOT/path).read_bytes()
            needle = b'= yes'
            self.assertEqual(insertion.count(needle), 1)
            altered = current.replace(insertion, insertion.replace(needle, b'= no'), 1)
            duplicate = current.replace(insertion, insertion+insertion, 1)
            for mutant in (altered, duplicate):
                with self.subTest(path=path, duplicate=mutant is duplicate):
                    with self.assertRaises(AssertionError): restore_arsenal_budget(path, mutant)

    def test_unrelated_money_edit_still_fails_the_remaining_byte_comparison(self):
        path = 'common/scripted_effects/00_money_system.txt'
        current = (ROOT/path).read_bytes()
        needle = b'calculate_interest_rate = yes'
        self.assertIn(needle, current)
        altered = current.replace(needle, b'calculate_interest_rate = no', 1)
        before = subprocess.check_output(['git', 'show', BASE+':'+path], cwd=ROOT)
        self.assertNotEqual(restore_arsenal_budget(path, altered), before)

    def test_market_reset_is_exactly_owned(self):
        path = 'common/scripted_effects/00_money_system.txt'
        current = (ROOT/path).read_bytes()
        for replacement in (b'', MARKET_RESET.replace(b'= 0', b'= 1'), MARKET_RESET*2):
            with self.subTest(replacement=replacement):
                with self.assertRaises(AssertionError):
                    restore_arsenal_budget(path, current.replace(MARKET_RESET, replacement, 1))


if __name__ == '__main__': unittest.main(verbosity=2)
