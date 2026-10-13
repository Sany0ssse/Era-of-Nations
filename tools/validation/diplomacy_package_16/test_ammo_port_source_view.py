"""Hostile controls for the exact historical ammo-source byte view."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import subprocess
import unittest

from ammo_port_source_view import (
    ROOT, SOURCE, PROOF, HISTORICAL_SHA256, APPROVED_SOURCE_SHA256,
    historical_ammo_mechanics_bytes,
)

BASELINE = '0e70f281145041d9e707089623ef5ecb610b744f'


class ExactAmmoPortSourceView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actual = (ROOT / SOURCE).read_bytes()
        cls.original = (PROOF / 'fixtures/ammo_port_mechanics_baseline.txt').read_bytes()
        cls.catalog = json.loads((PROOF / 'canonical_ammo_ports.json').read_text('utf-8'))
        cls.before = cls.catalog['before_span'].encode('utf-8')
        cls.after = cls.catalog['candidate_span'].encode('utf-8')

    def reject(self, actual, **kwargs):
        with self.assertRaises(AssertionError):
            historical_ammo_mechanics_bytes(actual, **kwargs)

    def test_01_current_inverse_equals_whole_git_baseline(self):
        git_original = subprocess.check_output(['git', 'show', BASELINE + ':' + SOURCE], cwd=ROOT)
        self.assertEqual(git_original, self.original)
        self.assertEqual(hashlib.sha256(self.actual).hexdigest(), APPROVED_SOURCE_SHA256)
        self.assertEqual(historical_ammo_mechanics_bytes(self.actual), git_original)
        self.assertEqual(hashlib.sha256(git_original).hexdigest(), HISTORICAL_SHA256)

    def test_02_original_view_is_unchanged_and_source_format_preserved(self):
        self.assertEqual(historical_ammo_mechanics_bytes(self.original), self.original)
        self.assertEqual(self.actual.startswith(b'\xef\xbb\xbf'), self.original.startswith(b'\xef\xbb\xbf'))
        self.assertEqual(b'\r\n' in self.actual, b'\r\n' in self.original)
        self.assertEqual(self.actual.endswith(b'\n'), self.original.endswith(b'\n'))

    def test_03_missing_duplicate_and_old_plus_new_spans_rejected(self):
        variants = (
            self.actual.replace(self.after, b'', 1),
            self.actual + b'\n' + self.after,
            self.actual.replace(self.after, self.after + b'\n' + self.after, 1),
            self.actual + b'\n' + self.before,
        )
        for index, actual in enumerate(variants):
            with self.subTest(index=index): self.reject(actual)

    def test_04_unowned_prefix_suffix_capacity_guard_and_combat_bytes_rejected(self):
        replacements = (
            (b'@base_max_ammo_limit = 10000', b'@base_max_ammo_limit = 10001'),
            (b'set_temp_variable = { i = 0 }', b'set_temp_variable = { i = 1 }'),
            (b'number_of_ships_in_combat = i', b'number_of_ships_in_combat = 0'),
            (b'naval_base > 0', b'naval_base > 1'),
        )
        for before, after in replacements:
            self.assertIn(before, self.actual)
            with self.subTest(before=before): self.reject(self.actual.replace(before, after, 1))
        for actual in (b'# prefix\n' + self.actual, self.actual + b'# suffix\n', self.actual[:-1]):
            with self.subTest(size=len(actual)): self.reject(actual)

    def test_05_algorithm_format_BOM_and_EOL_changes_rejected(self):
        replacements = (
            (b'eon_ammo_port_loop_break = 0', b'eon_ammo_port_loop_break = 1'),
            (b'max = 100', b'max = 101'),
            (b'state = PREV', b'state = ROOT'),
            (b'set_temp_variable = { i = 1 }', b'set_temp_variable = { i =  1 }'),
        )
        for before, after in replacements:
            self.assertIn(before, self.after)
            damaged = self.after.replace(before, after, 1)
            with self.subTest(before=before): self.reject(self.actual.replace(self.after, damaged, 1))
        for actual in (b'\xef\xbb\xbf' + self.actual, self.actual.replace(b'\n', b'\r\n')):
            with self.subTest(size=len(actual)): self.reject(actual)

    def test_06_catalog_field_and_matching_forged_span_changes_rejected(self):
        for field in ('source', 'baseline_sha256', 'candidate_sha256', 'candidate_span_sha256'):
            catalog = deepcopy(self.catalog); catalog[field] += '_changed'
            with self.subTest(field=field): self.reject(self.actual, catalog=catalog)
        for field in ('before_span', 'candidate_span'):
            catalog = deepcopy(self.catalog); del catalog[field]
            with self.subTest(missing=field): self.reject(self.actual, catalog=catalog)
        catalog = deepcopy(self.catalog)
        catalog['before_span'] = catalog['before_span'].replace('size  > i', 'size > i')
        self.reject(self.actual, catalog=catalog)
        catalog = deepcopy(self.catalog)
        catalog['candidate_span'] = catalog['candidate_span'].replace('max = 100', 'max = 101')
        forged = self.actual.replace(self.after, catalog['candidate_span'].encode('utf-8'), 1)
        self.reject(forged, catalog=catalog)

    def test_07_frozen_fixture_changes_rejected_even_with_matching_catalog(self):
        for original in (self.original + b'# unowned\n', self.original[:-1],
                         b'\xef\xbb\xbf' + self.original, self.original.replace(b'\n', b'\r\n')):
            with self.subTest(size=len(original)): self.reject(self.actual, original=original)
        original = self.original.replace(self.before, self.before.replace(b'100', b'101'), 1)
        catalog = deepcopy(self.catalog); catalog['before_span'] = self.before.replace(b'100', b'101').decode('utf-8')
        catalog['baseline_sha256'] = hashlib.sha256(original).hexdigest()
        self.reject(self.actual, catalog=catalog, original=original)

    def test_08_actual_guard_uses_inverse_and_whole_original_equality(self):
        source = (ROOT / 'tools/validation/diplomacy_package_16/test_source.py').read_bytes()
        old_guard = b'    assert native_capacity_bytes == baseline_bytes(native_capacity_path)\n'
        current_guard = b'    assert historical_ammo_mechanics_bytes(native_capacity_bytes) == baseline_bytes(native_capacity_path)\n'
        self.assertEqual(source.count(old_guard), 0)
        self.assertEqual(source.count(current_guard), 1)
        namespace = {'native_capacity_bytes': self.actual, 'native_capacity_path': SOURCE,
                     'historical_ammo_mechanics_bytes': historical_ammo_mechanics_bytes,
                     'baseline_bytes': lambda path: self.original if path == SOURCE else None}
        exec(compile(current_guard.decode().strip(), '<actual-package16-guard>', 'exec'), namespace)
        namespace['native_capacity_bytes'] = self.actual + b'# unowned\n'
        with self.assertRaises(AssertionError):
            exec(compile(current_guard.decode().strip(), '<actual-package16-guard>', 'exec'), namespace)


if __name__ == '__main__': unittest.main(verbosity=2)
