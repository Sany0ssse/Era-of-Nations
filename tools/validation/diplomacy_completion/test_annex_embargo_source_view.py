"""Hostile byte controls for the exact peace/embargo historical source view."""
from pathlib import Path
import hashlib
import inspect
import subprocess
import unittest

from check_annex_embargo_cleanup import (
    ROOT, PATH, BASELINE, LEGACY_SHA256, assert_historical_annex_source, main,
)
from peace_settlement.legacy_source_compat import BASE_SHA, GUARD, ANCHORS


class HistoricalAnnexEmbargoView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current = (ROOT / PATH).read_bytes()
        cls.legacy = subprocess.check_output(
            ['git', 'show', BASELINE + ':' + PATH], cwd=ROOT)

    def reject(self, candidate, legacy=None):
        with self.assertRaises(AssertionError):
            assert_historical_annex_source(
                candidate, self.legacy if legacy is None else legacy)

    def test_01_current_inverse_reaches_exact_accepted_before_peace_bytes(self):
        projected = assert_historical_annex_source(self.current, self.legacy)
        self.assertEqual(hashlib.sha256(projected).hexdigest(), BASE_SHA)
        self.assertEqual(hashlib.sha256(self.legacy).hexdigest(), LEGACY_SHA256)
        self.assertEqual(self.current.count(GUARD), 2)
        for anchor in ANCHORS:
            self.assertEqual(projected.count(anchor), 1)
            projected = projected.replace(anchor, anchor + GUARD, 1)
        self.assertEqual(projected, self.current)
        self.assertEqual(self.current.startswith(b'\xef\xbb\xbf'), self.legacy.startswith(b'\xef\xbb\xbf'))
        self.assertEqual(b'\r\n' in self.current, b'\r\n' in self.legacy)

    def test_02_missing_partial_duplicate_and_moved_peace_spans_reject(self):
        mutations = (
            self.current.replace(GUARD, b''),
            self.current.replace(GUARD, b'', 1),
            self.current + GUARD,
            self.current.replace(ANCHORS[0] + GUARD, GUARD + ANCHORS[0], 1),
            self.current.replace(GUARD, GUARD[:-1], 1),
            self.current.replace(GUARD, GUARD.replace(b'@FROM', b'@ROOT', 1), 1),
        )
        for index, candidate in enumerate(mutations):
            with self.subTest(index=index):
                self.assertNotEqual(candidate, self.current)
                self.reject(candidate)

    def test_03_foreign_bytes_embargo_predicates_BOM_and_EOL_reject(self):
        replacements = (
            (b'transfer_troops = no', b'transfer_troops = yes'),
            (b'limit = { has_dynamic_modifier = embargo_dynamic_modifier }',
             b'limit = { always = yes }'),
            (b'clear_variable = embargo_modifier_value',
             b'clear_variable = unrelated_value'),
        )
        for before, after in replacements:
            self.assertIn(before, self.current)
            with self.subTest(before=before):
                self.reject(self.current.replace(before, after, 1))
        mutations = (
            b'# foreign prefix\n' + self.current,
            self.current + b'\n# foreign suffix\n',
            self.current[:-1],
            b'\xef\xbb\xbf' + self.current,
            self.current.replace(b'\n', b'\r\n'),
        )
        for index, candidate in enumerate(mutations):
            with self.subTest(index=index):
                self.assertNotEqual(candidate, self.current)
                self.reject(candidate)

    def test_04_forged_legacy_baseline_rejects_without_accepting_current_hash(self):
        for candidate in (self.legacy + b'# foreign\n', self.legacy[:-1],
                          b'\xef\xbb\xbf' + self.legacy,
                          self.legacy.replace(b'\n', b'\r\n')):
            with self.subTest(size=len(candidate)):
                self.reject(self.current, legacy=candidate)
        # The old no-peace view is deliberately not accepted as current gameplay.
        self.reject(self.legacy)

    def test_05_behavior_still_parses_raw_current_source(self):
        source = inspect.getsource(main)
        self.assertIn('assert_historical_annex_source(raw,before)', source)
        self.assertIn("actions=parser.one(parser.ast(raw),'on_actions')", source)
        self.assertNotIn('parser.ast(preservation)', source)
        self.assertNotIn('raw=assert_historical_annex_source', source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
