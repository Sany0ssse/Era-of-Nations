"""Portable source checks for the 1.19 raid-planning define key correction.

Checks configuration and narrow byte preservation, not native scheduling or FPS.
The engine spelling/default was checked against the installed 1.19 source.
"""
from pathlib import Path
import hashlib
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
REL = 'common/defines/MD_defines.lua'
BEFORE_SHA = '660b5f703347e7c56d1b185ecf16e29eadc2a67a033d0beabf2f4cb5ee7b4bd7'
AFTER_SHA = '56037ffbb8c179ebc3331aa36b1956f97d5a1ed1f9a9052719a99f735cd5574b'
BAD = b'NDefines.NAI.RAIDS_CREATE_FREQUENCEY_DAYS = 30'
GOOD = b'NDefines.NAI.RAIDS_CREATE_FREQUENCY_DAYS = 30'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


class RaidPlanningKey(unittest.TestCase):
    def test_only_the_misspelled_key_changed(self):
        raw = (ROOT / REL).read_bytes()
        self.assertEqual(sha(raw), AFTER_SHA)
        self.assertEqual(raw.count(GOOD), 1)
        self.assertNotIn(BAD, raw)
        self.assertEqual(sha(raw.replace(GOOD, BAD, 1)), BEFORE_SHA)
        self.assertFalse(raw.startswith(b'\xef\xbb\xbf'))
        self.assertEqual(raw.count(b'\r\n'), 0)
        self.assertEqual(raw.count(b'\n'), 1183)

    def test_the_intended_monthly_interval_is_unique(self):
        assignments = []
        for path in sorted((ROOT / 'common/defines').glob('*.lua')):
            for line in path.read_text(encoding='utf-8-sig').splitlines():
                # Lua comments have no effect on the configured key.
                code = line.split('--', 1)[0]
                self.assertNotIn('RAIDS_CREATE_FREQUENCEY_DAYS', code)
                match = re.match(r'\s*NDefines\.NAI\.RAIDS_CREATE_FREQUENCY_DAYS\s*=\s*(\d+)\s*$', code)
                if match:
                    assignments.append((path.relative_to(ROOT).as_posix(), int(match.group(1))))
        self.assertEqual(assignments, [(REL, 30)])


if __name__ == '__main__':
    unittest.main()
