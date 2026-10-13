"""Current-source EU cash regressions; no native or campaign acceptance."""
import copy
import unittest
from _source_model import CashModel, ROOT, MONEY, ast, one, read, seed_rates


class EUWeeklyCash(unittest.TestCase):
    def setUp(self):
        self.m = CashModel()
        self.c = seed_rates(self.m)

    def test_four_annual_grants_are_paid_as_one_week_of_cash(self):
        self.m.refresh_cash_rates()
        self.assertAlmostEqual(self.c.variables['additional_income_rate'], 10)
        self.assertAlmostEqual(self.c.variables['additional_expenses_rate'], 2)
        self.assertEqual(self.c.variables['treasury'], 500)
        self.m.settle_week()
        self.assertAlmostEqual(self.c.variables['treasury'], 514)

    def test_52_weeks_pay_the_nominal_annual_grants_and_contribution(self):
        for grants in ((52, 104, 156, 208), (0, 0, 0, 0), (0.13, 4.5, 2.7, 52.123)):
            with self.subTest(grants=grants):
                m = CashModel(); c = seed_rates(m, grants=grants, contribution=13)
                for _ in range(52): m.refresh_cash_rates(); m.settle_week()
                self.assertAlmostEqual(c.variables['treasury'] - 500,
                                       52 * (10 - 4) + sum(grants) - 13, places=8)

    def test_old_multiplier_is_detected_as_a_1_2_percent_shortfall(self):
        raw = read(MONEY)
        current = '\t\t}\n\t\tdivide_variable = { EU_subsidies = 52 }\n\t\tadd_to_variable = { additional_income_rate = EU_subsidies }'
        old = '\t\t\t\tmultiply = 0.019\n\t\t\t}\n\t\t}\n\t\tadd_to_variable = { additional_income_rate = EU_subsidies }'
        self.assertEqual(raw.count(current), 1)
        # Recreate only the inherited arithmetic for this negative control.
        mutant = raw.replace('\t\t\t}\n' + current, old, 1)
        m = CashModel(mutant); c = seed_rates(m)
        m.refresh_cash_rates()
        self.assertAlmostEqual(c.variables['additional_income_rate'] * 52, 520 * .988)
        self.assertNotAlmostEqual(c.variables['additional_income_rate'] * 52, 520)

    def test_council_suspension_does_not_suspend_financial_participation(self):
        self.c.ideas.add('EUU_voting_rights_suspended')
        self.m.refresh_cash_rates(); self.m.settle_week()
        self.assertAlmostEqual(self.c.variables['treasury'], 514)

    def test_subsidy_suspension_still_charges_contribution(self):
        self.c.ideas.add('EUU_subsidies_suspended')
        self.m.refresh_cash_rates(); self.m.settle_week()
        self.assertAlmostEqual(self.c.variables['treasury'], 504)

    def test_nonmember_with_stale_registry_and_rates_receives_no_eu_cash(self):
        self.c.ideas.discard('EU_member')
        self.m.refresh_cash_rates(); self.m.settle_week()
        self.assertAlmostEqual(self.c.variables['treasury'], 506)
        self.assertEqual(self.c.variables['additional_income_rate'], 0)
        self.assertEqual(self.c.variables['additional_expenses_rate'], 0)

    def test_subject_or_dormant_union_with_stale_caches_has_no_eu_cash(self):
        for dormant in (False, True):
            with self.subTest(dormant=dormant):
                m = CashModel(); c = seed_rates(m)
                if dormant: m.global_owner.flags.add('eon_eu_dormant')
                else: c.subjects = True
                m.refresh_cash_rates(); m.settle_week()
                self.assertAlmostEqual(c.variables['treasury'], 506)

    def test_actual_access_cleanup_and_departure_marker_stop_both_flows(self):
        self.m.call('eon_eu_clear_country_access', 2)
        self.m.idea_remove(self.c, [self.c])
        self.m.refresh_cash_rates(); self.m.settle_week()
        self.assertNotIn(2, self.m.global_owner.arrays['EU_member'])
        self.assertEqual(self.c.variables['treasury'], 506)
        self.assertEqual(self.c.variables['EU_budget_contribution_weekly'], 0)

    def test_repeated_refresh_changes_rates_without_transferring_cash_or_debt(self):
        self.c.variables.update(debt=19, additional_income_rate=999, additional_expenses_rate=999)
        other = copy.deepcopy(self.m.nations[1].variables)
        for _ in range(5): self.m.refresh_cash_rates()
        self.assertEqual((self.c.variables['treasury'], self.c.variables['debt']), (500, 19))
        self.assertAlmostEqual(self.c.variables['additional_income_rate'], 10)
        self.assertAlmostEqual(self.c.variables['additional_expenses_rate'], 2)
        self.assertEqual(self.m.nations[1].variables, other)

    def test_existing_other_income_and_energy_forecast_cash_exclusion_survive(self):
        self.c.ideas.add('blood_diamond_trade')
        self.m.refresh_cash_rates()
        self.assertAlmostEqual(self.c.variables['additional_income_rate'], 10.04)
        # Declared existing energy forecast is accounted separately; execute
        # the real display/cash nodes to prove no second cash settlement.
        self.c.variables['additional_income_rate'] += 3
        self.c.variables['additional_expenses_rate'] += 2
        self.c.variables.update(energy_selling_income=3, energy_buying_expenses=2)
        from _source_model import display_and_cash_nodes
        self.m.effect(display_and_cash_nodes(), [self.c])
        self.assertAlmostEqual(self.c.variables['treasury_rate'], 15.04)
        self.assertAlmostEqual(self.c.variables['eon_treasury_cash_rate'], 14.04)
        self.m.settle_week()
        self.assertAlmostEqual(self.c.variables['treasury'], 514.04)

    def test_actual_weekly_cash_pays_only_remaining_debt_and_does_not_repeat(self):
        self.c.variables['debt'] = 1
        self.c.flags.add('automatically_pay_off_debt_enabled')
        self.m.refresh_cash_rates(); self.m.settle_week()
        self.assertAlmostEqual(self.c.variables['treasury'], 513)
        self.assertEqual(self.c.variables['debt'], 0)
        self.assertNotIn('automatically_pay_off_debt_enabled', self.c.flags)
        self.m.refresh_cash_rates(); self.m.settle_week()
        self.assertAlmostEqual(self.c.variables['treasury'], 527)


if __name__ == '__main__':
    unittest.main(verbosity=2)
