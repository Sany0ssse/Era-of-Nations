"""Guard the production weekly cash integration; engine receipts verify outcomes."""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('missile_parser', ROOT/'tools/validation/diplomacy_package_03/_support.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

class BudgetIntegration(unittest.TestCase):
    def test_refresh_rate_has_one_component(self):
        source = p.ast((ROOT/'common/scripted_effects/00_money_system.txt').read_bytes())
        body = p.one(source, 'calculate_additional_expense_rate')
        self.assertEqual(body[:3], [
            ('set_variable', '=', [('additional_expenses_rate', '=', '0')]),
            ('eon_nuclear_arsenal_refresh', '=', 'yes'),
            ('add_to_variable', '=', [('additional_expenses_rate', '=', 'eon_nuclear_arsenal_weekly_cost')]),
        ])
        self.assertEqual(sum(k == 'eon_nuclear_arsenal_refresh' for k, _, _ in body), 1)

    def test_progress_precedes_recalculation_and_single_payment(self):
        source = p.ast((ROOT/'common/on_actions/01_on_actions.txt').read_bytes())
        body = p.one(p.one(p.one(source, 'on_actions'), 'on_weekly'), 'effect')
        keys = [k for k, _, _ in body]
        self.assertEqual(keys.count('eon_nuclear_arsenal_weekly'), 1)
        self.assertLess(keys.index('eon_nuclear_arsenal_weekly'), keys.index('ingame_update_setup'))
        payments = [v for k, _, v in body if k == 'add_to_variable' and isinstance(v, list) and any(a == 'treasury' for a, _, _ in v)]
        self.assertEqual(payments, [[('treasury', '=', 'treasury_rate_gain')]])

if __name__ == '__main__': unittest.main(verbosity=2)
