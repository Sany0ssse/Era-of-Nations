"""Execute the two actual EU money gate limits; this is not weekly cash proof."""
from pathlib import Path
import importlib.util
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    'eu_membership_finance_fixture', ROOT / 'tools/validation/eu_membership/test_lifecycle.py')
MEMBERSHIP = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MEMBERSHIP
SPEC.loader.exec_module(MEMBERSHIP)
Model, ast, one = MEMBERSHIP.Model, MEMBERSHIP.ast, MEMBERSHIP.one


def money_gate(nodes, expected_value):
    """Find the real enclosing if, by its direct money-rate addition."""
    for key, op, value in nodes:
        if not isinstance(value, list):
            continue
        if key == 'if' and any(
            child_key == 'add_to_variable' and any(
                right == expected_value for left, operator, right in child_value)
            for child_key, child_operator, child_value in value
            if isinstance(child_value, list)
        ):
            return one(value, 'limit')
        result = money_gate(value, expected_value)
        if result is not None:
            return result
    return None


class FinanceGates(unittest.TestCase):
    def setUp(self):
        self.m = Model()
        self.m.members()
        self.country = self.m.nations[2]
        self.country.variables.update(
            EU_budget_contribution=104, EU_budget_contribution_weekly=2,
            EU_subsidies=7, EU_budget_call_rate=1)
        source = ast((ROOT / 'common/scripted_effects/00_money_system.txt').read_text(encoding='utf-8-sig'))
        self.expense = money_gate(source, 'EU_budget_contribution_weekly')
        self.income = money_gate(source, 'EU_subsidies')
        self.assertIsNotNone(self.expense)
        self.assertIsNotNone(self.income)
        financial = ROOT / 'common/scripted_triggers/eon_eu_financial_triggers.txt'
        if financial.exists():
            self.m.triggers.update({k: value for k, operator, value in ast(financial.read_text(encoding='utf-8-sig'))})

    def eligible(self, gate):
        return self.m.trigger(gate, [self.country])

    def assert_no_flows(self):
        self.assertFalse(self.eligible(self.expense))
        self.assertFalse(self.eligible(self.income))

    def test_active_registered_member_participates(self):
        self.assertTrue(self.eligible(self.expense))
        self.assertTrue(self.eligible(self.income))

    def test_subject_with_stale_registry_is_ineligible_before_refresh(self):
        self.country.subjects = True
        self.assertIn(2, self.m.global_owner.arrays['EU_member'])
        self.assert_no_flows()

    def test_subject_after_refresh_keeps_legal_marker_and_caches_without_flows(self):
        self.country.subjects = True
        self.m.call('eon_eu_refresh_membership', 2)
        self.assertNotIn(2, self.m.global_owner.arrays['EU_member'])
        self.assertIn('EU_member', self.country.ideas)
        self.assertEqual(self.country.variables['EU_budget_contribution_weekly'], 2)
        self.assertEqual(self.country.variables['EU_subsidies'], 7)
        self.assertEqual(self.country.variables['EU_budget_call_rate'], 1)
        self.assert_no_flows()

    def test_sovereignty_restoration_and_registry_refresh_resumes_eligibility(self):
        self.country.subjects = True
        self.m.call('eon_eu_refresh_membership', 2)
        self.country.subjects = False
        self.assert_no_flows()  # The current canonical registry must also be restored.
        self.m.call('eon_eu_refresh_membership', 2)
        self.assertTrue(self.eligible(self.expense))
        self.assertTrue(self.eligible(self.income))
        self.assertEqual(self.country.variables['EU_budget_call_rate'], 1)

    def test_former_member_with_stale_registry_and_values_has_no_flows(self):
        self.country.ideas.remove('EU_member')
        self.assertIn(2, self.m.global_owner.arrays['EU_member'])
        self.assert_no_flows()

    def test_dormant_union_with_stale_idea_registry_and_values_has_no_flows(self):
        self.m.global_owner.flags.add('eon_eu_dormant')
        self.assert_no_flows()

    def test_rule_disabled_or_federated_union_has_no_flows(self):
        for flag in ('GAME_RULE_eu_disabled', 'usoe_formed'):
            with self.subTest(flag=flag):
                self.m.global_owner.flags.add(flag)
                self.assert_no_flows()
                self.m.global_owner.flags.remove(flag)

    def test_council_voting_suspension_does_not_suspend_budget_participation(self):
        self.country.ideas.add('EUU_voting_rights_suspended')
        self.assertTrue(self.eligible(self.expense))
        self.assertTrue(self.eligible(self.income))

    def test_subsidy_suspension_blocks_income_only(self):
        self.country.ideas.add('EUU_subsidies_suspended')
        self.assertTrue(self.eligible(self.expense))
        self.assertFalse(self.eligible(self.income))

    def test_live_legal_member_absent_from_registry_has_no_flows(self):
        self.m.global_owner.arrays['EU_member'].remove(2)
        self.assertTrue(self.m.test('eon_eu_is_active_member', 2))
        self.assert_no_flows()


class BudgetBookkeepingModel(Model):
    """Execute actual budget cache arithmetic, not legacy distribution or treasury."""
    def __init__(self):
        super().__init__()
        source = ast((ROOT / 'common/scripted_effects/00_eu_scripted_effects.txt').read_text(encoding='utf-8-sig'))
        self.effects = {name: one(source, name) for name in ('EU_budget_total_gain', 'update_EU_expenditure',
            'distribute_EU_budget', 'distribute_EU_admin_exp')}
        triggers = ast((ROOT / 'common/scripted_triggers/99_EU_scripted_triggers.txt').read_text(encoding='utf-8-sig'))
        self.triggers['is_leader_of_EU_foreign_policy'] = one(triggers, 'is_leader_of_EU_foreign_policy')
        self.divisions = []

    def effect(self, nodes, stack):
        i = 0
        while i < len(nodes):
            key, op, value = nodes[i]; i += 1
            if key in self.effects:
                self.effect(self.effects[key], stack)
            elif key == 'if':
                branches = [('if', value)]
                while i < len(nodes) and nodes[i][0] in ('else', 'else_if'):
                    branches.append((nodes[i][0], nodes[i][2])); i += 1
                for kind, body in branches:
                    if kind == 'else' or self.trigger(one(body, 'limit'), stack):
                        self.effect([node for node in body if node[0] != 'limit'], stack)
                        break
            elif key == 'for_each_scope_loop':
                owner, name = self.slot(one(value, 'array'), stack)
                for ident in owner.arrays.get(name, []):
                    self.effect([node for node in value if node[0] != 'array'], stack + [self.nations[ident]])
            elif key in ('set_variable', 'add_to_variable', 'subtract_from_variable', 'multiply_variable', 'divide_variable'):
                name, operator, operand = value[0]
                owner, slot = self.slot(name, stack)
                number = self.value(operand, stack)
                previous = owner.variables.get(slot, 0)
                if key == 'set_variable': result = number
                elif key == 'add_to_variable': result = previous + number
                elif key == 'subtract_from_variable': result = previous - number
                elif key == 'multiply_variable': result = previous * number
                else:
                    self.divisions.append((stack[-1].ident, name, number))
                    assert number != 0, ('unguarded budget division', name, operand)
                    result = previous / number
                owner.variables[slot] = result
            elif key in ('set_temp_variable', 'multiply_temp_variable'):
                name, operator, operand = value[0]
                number = self.value(operand, stack)
                self.temp[name] = number if key == 'set_temp_variable' else self.temp.get(name, 0) * number
            elif key in ('distribute_EU_growth_exp', 'distribute_EU_natural_exp'):
                self.receipts.append((key, stack[-1].ident))  # Explicit external physical-allocation boundary.
            elif key == 'effect_tooltip':
                pass  # Native previews are not a second execution of bookkeeping.
            elif key == 'custom_effect_tooltip':
                pass
            elif key == 'update_eu_dirty_variable':
                self.receipts.append((key, stack[-1].ident))
            else:
                raise AssertionError(('unmodeled budget bookkeeping operation', key))


class BudgetBookkeeping(unittest.TestCase):
    def setUp(self):
        self.m = BudgetBookkeepingModel()
        self.m.global_owner.arrays['EU_member'] = [1, 2]
        self.m.nations[1].variables.update(EU_growth_subsidies=10, EU_natural_subsidies=20,
            EU_global_exp_subsidies=3, EU_admin_subsidies=7, EU_budget_contribution=15)
        self.m.nations[2].variables.update(EU_growth_subsidies=2, EU_natural_subsidies=3,
            EU_global_exp_subsidies=0, EU_admin_subsidies=5, EU_budget_contribution=8)

    def bookkeeping(self, expenditure):
        self.m.global_owner.variables['EU_total_exp'] = expenditure
        self.m.effect(self.m.effects['EU_budget_total_gain'], [self.m.nations[3]])
        self.assertEqual(self.m.nations[1].variables['EU_budget_total_gain'], 40)
        self.assertEqual(self.m.nations[1].variables['EU_budget_net'], 25)
        self.assertEqual(self.m.nations[2].variables['EU_budget_total_gain'], 10)
        self.assertEqual(self.m.nations[2].variables['EU_budget_net'], 2)
        self.assertEqual(self.m.global_owner.variables['EU_total_exp'], expenditure)
        self.assertNotIn('EU_budget_total_gain', self.m.nations[3].variables)

    def test_positive_budget_caches_ratio_and_net_once_for_members_only(self):
        self.bookkeeping(100)
        self.assertAlmostEqual(self.m.nations[1].variables['EU_budget_ratio_gain'], .4)
        self.assertAlmostEqual(self.m.nations[2].variables['EU_budget_ratio_gain'], .1)
        self.assertEqual(len(self.m.divisions), 2)

    def test_zero_budget_has_zero_ratio_without_dividing_by_zero(self):
        self.m.nations[1].variables['EU_budget_ratio_gain'] = .9
        self.bookkeeping(0)
        self.assertEqual(self.m.nations[1].variables['EU_budget_ratio_gain'], 0)
        self.assertEqual(self.m.nations[2].variables['EU_budget_ratio_gain'], 0)
        self.assertEqual(self.m.divisions, [])

    def test_nonpositive_corrupt_budget_does_not_publish_negative_ratio(self):
        self.bookkeeping(-10)
        self.assertEqual(self.m.nations[1].variables['EU_budget_ratio_gain'], 0)
        self.assertEqual(self.m.nations[2].variables['EU_budget_ratio_gain'], 0)
        self.assertEqual(self.m.divisions, [])

    def test_update_expenditure_preserves_policy_ratios_and_scales_four_totals(self):
        variables = self.m.global_owner.variables
        ratios = {'growth': .5, 'natural': .3, 'global': .1, 'admin': .1}
        variables['EU_total_exp'] = 20
        for name, ratio in ratios.items(): variables[f'EU_{name}_exp_ratio'] = ratio
        self.m.effect(self.m.effects['update_EU_expenditure'], [self.m.nations[3]])
        for name, ratio in ratios.items():
            self.assertEqual(variables[f'EU_{name}_exp_ratio'], ratio)
            self.assertEqual(variables[f'EU_{name}_exp_total'], ratio * 20)


class RoleBudgetCaches(unittest.TestCase):
    def setUp(self):
        self.m = BudgetBookkeepingModel()
        self.m.global_owner.arrays['EU_member'] = [1, 2]
        self.m.global_owner.variables.update(EU_total_exp=100, EU_admin_exp_total=10, EU_global_exp_total=12)
        for ident in (1, 2):
            self.m.nations[ident].ideas.add('EU_member')
            self.m.nations[ident].variables.update(EU_admin_subsidies=17, EU_global_exp_subsidies=19)

    def distribute(self):
        self.m.effect(self.m.effects['distribute_EU_budget'], [self.m.nations[3]])

    def test_replacement_clears_former_active_holder_before_assigning_current(self):
        self.m.nations[2].ideas.update(('EU_commission_president', 'EU_foreign_minister'))
        self.distribute()
        self.assertEqual(self.m.nations[1].variables['EU_admin_subsidies'], 0)
        self.assertEqual(self.m.nations[1].variables['EU_global_exp_subsidies'], 0)
        self.assertEqual(self.m.nations[2].variables['EU_admin_subsidies'], 10)
        self.assertEqual(self.m.nations[2].variables['EU_global_exp_subsidies'], 12)

    def test_two_distinct_administrative_holders_receive_half_each(self):
        self.m.nations[1].ideas.add('EU_commission_president')
        self.m.nations[2].ideas.add('frontex_ExDir')
        self.distribute()
        self.assertEqual(self.m.nations[1].variables['EU_admin_subsidies'], 5)
        self.assertEqual(self.m.nations[2].variables['EU_admin_subsidies'], 5)

    def test_two_administrative_offices_same_country_preserve_both_shares(self):
        self.m.nations[1].ideas.update(('EU_commission_president', 'frontex_ExDir'))
        self.distribute()
        self.assertEqual(self.m.nations[1].variables['EU_admin_subsidies'], 10)
        self.assertEqual(self.m.nations[2].variables['EU_admin_subsidies'], 0)

    def test_absent_offices_clear_previous_role_caches(self):
        self.distribute()
        for ident in (1, 2):
            self.assertEqual(self.m.nations[ident].variables['EU_admin_subsidies'], 0)
            self.assertEqual(self.m.nations[ident].variables['EU_global_exp_subsidies'], 0)

    def test_parliament_foreign_policy_fallback_uses_actual_legacy_trigger(self):
        self.m.nations[2].ideas.add('EU_parliament_president')
        self.distribute()
        self.assertEqual(self.m.nations[1].variables['EU_global_exp_subsidies'], 0)
        self.assertEqual(self.m.nations[2].variables['EU_global_exp_subsidies'], 12)

    def test_all_four_relevant_office_callbacks_mark_budget_changed(self):
        ideas = one(one(ast((ROOT / 'common/ideas/EU_ideas.txt').read_text(encoding='utf-8-sig')), 'ideas'), 'country')
        for role in ('EU_commission_president', 'EU_foreign_minister', 'frontex_ExDir', 'EU_parliament_president'):
            for callback in ('on_add', 'on_remove'):
                with self.subTest(role=role, callback=callback):
                    self.assertIn(('set_global_flag', '=', 'eon_eu_budget_changed'), one(one(ideas, role), callback))


if __name__ == '__main__':
    unittest.main(verbosity=2)
