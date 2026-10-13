"""Reject broadened historical masks and preserve all other finance bytes."""
import hashlib
import importlib.util
import unittest
from _source_model import ROOT, MONEY, ast, one, read, direct_rate_block
from byte_compat import CURRENT, ORIGINAL, restore_weekly_subsidy


class HistoricalProjection(unittest.TestCase):
    def setUp(self):
        self.raw = (ROOT / MONEY).read_bytes()

    def test_exact_current_projection_reverses_only_calculation_and_preserves_format(self):
        restored = restore_weekly_subsidy(MONEY, self.raw)
        self.assertEqual(self.raw, restored.replace(ORIGINAL.encode(), CURRENT.encode(), 1))
        self.assertEqual(self.raw.count(b'\n'), restored.count(b'\n'))
        self.assertEqual(self.raw.count(b'\r\n'), restored.count(b'\r\n'))
        self.assertEqual(self.raw.startswith(b'\xef\xbb\xbf'), restored.startswith(b'\xef\xbb\xbf'))
        self.assertEqual(restore_weekly_subsidy(MONEY, read(MONEY)), restored.decode('utf-8-sig'))

    def test_old_or_missing_calculation_is_rejected(self):
        for replacement in ('', ORIGINAL):
            with self.subTest(replacement=replacement):
                with self.assertRaises(AssertionError):
                    restore_weekly_subsidy(MONEY, read(MONEY).replace(CURRENT, replacement, 1))

    def test_duplicate_current_calculation_is_rejected(self):
        with self.assertRaises(AssertionError):
            restore_weekly_subsidy(MONEY, read(MONEY) + CURRENT)

    def test_changed_divisor_grant_or_order_is_rejected(self):
        divide = '\t\tdivide_variable = { EU_subsidies = 52 }\n'
        for replacement in (CURRENT.replace('= 52 }', '= 53 }'),
                            CURRENT.replace('THIS.EU_admin_subsidies', 'THIS.EU_growth_subsidies'),
                            divide + CURRENT.replace(divide, ''),
                            CURRENT.replace('\t\t\t}\n', '\t\t\t\tmultiply = 0.019\n\t\t\t}\n')):
            with self.subTest(replacement=replacement):
                mutant = read(MONEY).replace(CURRENT, replacement, 1)
                with self.assertRaises(AssertionError): restore_weekly_subsidy(MONEY, mutant)

    def test_adjacent_and_unrelated_mutations_remain_visible_after_projection(self):
        restored = restore_weekly_subsidy(MONEY, read(MONEY))
        for suffix in ('# adjacent unrelated bytes\n', '\t\tadd_to_variable = { treasury = 1 }\n'):
            mutant = read(MONEY).replace(CURRENT, CURRENT + suffix, 1)
            changed = restore_weekly_subsidy(MONEY, mutant)
            self.assertIn(suffix, changed)
            self.assertNotEqual(hashlib.sha256(changed.encode()).digest(), hashlib.sha256(restored.encode()).digest())
        marker = '\t# Cartel Mechanic Costs\n'
        self.assertEqual(read(MONEY).count(marker), 1)
        mutant = read(MONEY).replace(marker, marker + '# foreign suffix mutation\n', 1)
        self.assertIn('# foreign suffix mutation', restore_weekly_subsidy(MONEY, mutant))

    def test_foreign_source_path_is_untouched(self):
        self.assertEqual(restore_weekly_subsidy('foreign.txt', self.raw), self.raw)

    def test_all_seven_existing_migration_islands_and_negative_controls_remain_exact(self):
        spec = importlib.util.spec_from_file_location('migration_money_islands',
            ROOT / 'tools/validation/migration_relief/byte_compat.py')
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
        self.assertEqual(len(migration.CATALOG['islands']), 7)
        # The accepted later arsenal insertion is checked/restored first, in
        # exactly the same order as the existing package25 historical guard.
        arsenal_spec = importlib.util.spec_from_file_location('accepted_arsenal_islands',
            ROOT / 'tools/validation/missile_system/byte_compat.py')
        arsenal = importlib.util.module_from_spec(arsenal_spec); arsenal_spec.loader.exec_module(arsenal)
        current = arsenal.restore_arsenal_budget(MONEY, read(MONEY))
        for item in migration.CATALOG['islands']:
            self.assertEqual(current.count(item['current']), 1)
            self.assertEqual(hashlib.sha256(item['current'].encode()).hexdigest(), item['current_sha256'])
        self.assertEqual(len(migration.negative_controls(current)), 14)
        self.assertEqual(restore_weekly_subsidy(MONEY, migration.restore_migration_money(MONEY, current)),
                         migration.restore_migration_money(MONEY, restore_weekly_subsidy(MONEY, current)))

    def test_actual_source_applies_division_after_four_grants_before_rate_addition(self):
        block = direct_rate_block(read(MONEY), 'calculate_additional_income_rate',
                                  'additional_income_rate', 'EU_subsidies')[0][2]
        self.assertEqual([k for k, op, v in block], ['limit', 'set_variable', 'divide_variable', 'add_to_variable'])
        expression = one(one(block, 'set_variable'), 'EU_subsidies')
        self.assertEqual([k for k, op, v in expression], ['value', 'add', 'add', 'add'])
        self.assertEqual(one(block, 'divide_variable'), [('EU_subsidies', '=', '52')])


if __name__ == '__main__':
    unittest.main(verbosity=2)
