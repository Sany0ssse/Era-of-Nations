"""Execute current budget/cash AST without charging energy forecasts twice."""
from pathlib import Path
import importlib.util
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    'eon_weekly_ast', ROOT / 'tools/validation/diplomacy_package_03/_support.py')
parser = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = parser
spec.loader.exec_module(parser)


class WeeklyModel(parser.Model):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.effects.update({k: v for k, _, v in parser.ast(
            (ROOT / 'common/scripted_effects/eon_investment_income_effects.txt').read_bytes())})

    def trigger(self, nodes, stack=None):
        if stack is None:
            stack = [self.current]
        values = []
        for node in nodes:
            if node[0] == 'has_active_mission':
                assert node[2] == 'cheap_loan_from_the_imf_mission'
                values.append(node[2] in getattr(self.countries[stack[-1]], 'active_missions', set()))
            else:
                values.append(super().trigger([node], stack))
        return all(values)

    def effect(self, nodes, stack=None):
        if stack is None:
            self.temp, stack = {}, [self.current]
        for key, op, value in nodes:
            if key in ('add_to_variable', 'subtract_from_variable', 'add_to_temp_variable',
                       'subtract_from_temp_variable', 'multiply_temp_variable'):
                assert len(value) == 1 and value[0][1] == '='
                name, _, amount = value[0]
                target = self.temp if 'temp' in key else self.countries[stack[-1]].variables
                operand, current = self.value(amount, stack), target.get(name, 0)
                target[name] = (current * operand if key.startswith('multiply') else
                                current - operand if key.startswith('subtract') else current + operand)
            elif key == 'clamp_variable':
                name = parser.one(value, 'var')
                target = self.countries[stack[-1]].variables
                lower = parser.maybe(value, 'min', '-1000000000000')
                target[name] = min(self.value(parser.one(value, 'max'), stack),
                                   max(self.value(lower, stack), target.get(name, 0)))
            else:
                super().effect([(key, op, value)], stack)


def main():
    raw = (ROOT / 'common/on_actions/01_on_actions.txt').read_bytes()
    # These markers enclose only the actual debt repayment and treasury mutation.
    start = raw.index(b'# Pay down debt automatically this weekly tick')
    end = raw.index(b'#Automated taking debt', start)
    nodes = parser.ast(raw[start:end])
    cases = 0
    for rate in (100, -100, 0, .001, 4):
        for debt in (1, 0, .0005, 25, 500):
            for automatic in (True, False):
                model = WeeklyModel(current=1)
                owner = model.countries[1]
                owner.variables.update(treasury=500, treasury_rate=rate,
                                       eon_treasury_cash_rate=rate, debt=debt)
                if automatic:
                    owner.flags.add('automatically_pay_off_debt_enabled')
                # An earlier effect must not leak a previous temporary deduction.
                model.temp['treasury_rate_debt_payment'] = 0 if automatic and rate == 100 and debt == 1 else 17
                model.effect(nodes, [1])
                payment = min(debt, max(rate, 0) * .25) if automatic else 0
                assert abs(owner.variables['treasury'] - (500 + rate - payment)) < 1e-9, (rate, debt, automatic, owner.variables)
                expected_debt = debt - payment
                assert abs(owner.variables['debt'] - expected_debt) < 1e-9
                assert model.temp['treasury_rate_debt_payment'] == payment
                cases += 1
    # Select intact contiguous statement ranges in the real update_display AST.
    # Budget arrays, diagnostic ratios and regional political updates are outside
    # this cash integration's scope; none of their operands are hand-recreated.
    display = parser.one(parser.ast((ROOT / 'common/scripted_effects/00_money_system.txt').read_bytes()), 'update_display')
    def assignment(node, key, variable):
        return node[0] == key and isinstance(node[2], list) and node[2][0][0] == variable
    def segment(variable):
        first = next(i for i, n in enumerate(display) if assignment(n, 'set_variable', variable))
        last = next(i for i in range(first, len(display))
                    if display[i][0] == 'clamp_variable' and parser.one(display[i][2], 'var') == variable)
        return display[first:last + 1]
    expense_nodes = segment('display_expense')
    income_nodes = segment('display_income')
    # The only excluded income statements maintain an unrelated display ratio.
    excluded = [n for n in income_nodes if n[0] in ('set_variable', 'divide_variable')
                and n[2][0][0] == 'resource_to_tax_income']
    assert [n[0] for n in excluded] == ['set_variable', 'divide_variable']
    income_nodes = [n for n in income_nodes if n not in excluded]
    cash_start = next(i for i, n in enumerate(display) if assignment(n, 'set_variable', 'treasury_rate'))
    cash_nodes = display[cash_start:cash_start + 4]
    assert [n[2][0][0] for n in cash_nodes] == [
        'treasury_rate', 'treasury_rate', 'eon_treasury_cash_rate', 'eon_treasury_cash_rate']
    integration_cases = 0
    for nonenergy_income, nonenergy_expense in ((100, 40), (4, 8), (1000010, 10), (10, 1000010), (1000010, 1000010)):
        for energy_income, energy_expense in ((0, 0), (50, 20), (1000010, 0), (0, 1000010)):
            for automatic in (True, False):
                model = WeeklyModel(current=1)
                owner = model.countries[1]
                owner.variables.update(
                    treasury=500, debt=1, tax_gain=nonenergy_income,
                    additional_income_rate=energy_income,
                    energy_selling_income=energy_income,
                    bureaucracy_gain=nonenergy_expense,
                    additional_expenses_rate=energy_expense,
                    energy_buying_expenses=energy_expense,
                )
                if automatic:
                    owner.flags.add('automatically_pay_off_debt_enabled')
                model.effect(expense_nodes + income_nodes + cash_nodes, [1])
                cash_rate = min(nonenergy_income, 1000000) - min(nonenergy_expense, 1000000)
                forecast = min(nonenergy_income + energy_income, 1000000) - min(nonenergy_expense + energy_expense, 1000000)
                assert owner.variables['eon_treasury_cash_rate'] == cash_rate
                assert owner.variables['treasury_rate'] == forecast
                model.effect(nodes, [1])
                payment = min(1, max(cash_rate, 0) * .25) if automatic else 0
                expected_cash = min(1000000, max(-1000000, 500 + cash_rate - payment))
                assert owner.variables['treasury'] == expected_cash
                debt_after_first = 1 - payment
                assert owner.variables['debt'] == debt_after_first
                # A second week must not carry the earlier temporary payment.
                model.effect(expense_nodes + income_nodes + cash_nodes + nodes, [1])
                second_payment = min(debt_after_first, max(cash_rate, 0) * .25) if automatic else 0
                assert owner.variables['treasury'] == min(1000000, max(-1000000, expected_cash + cash_rate - second_payment))
                assert owner.variables['debt'] == debt_after_first - second_payment
                integration_cases += 1
    pause_cases = 0
    for cheap_loan in (False, True):
        for suspended in (False, True):
            for reinvesting in (False, True):
                model = WeeklyModel(current=1)
                owner = model.countries[1]
                owner.variables.update(tax_gain=100, bureaucracy_gain=20, debt_rate=10,
                                       additional_expenses_rate=30, energy_buying_expenses=30,
                                       additional_income_rate=40, energy_selling_income=40,
                                       int_investments_rate=50)
                owner.active_missions = {'cheap_loan_from_the_imf_mission'} if cheap_loan else set()
                if suspended:
                    owner.flags.add('paused_debt_repayment')
                if reinvesting:
                    owner.flags.add('int_reinvestment_flag')
                model.effect(expense_nodes + income_nodes + cash_nodes, [1])
                expense = 20 + (0 if cheap_loan or suspended else 10)
                income = 100 + (0 if reinvesting else 50)
                assert owner.variables['eon_cash_expense_rate'] == expense
                assert owner.variables['eon_cash_income_rate'] == income
                assert owner.variables['eon_treasury_cash_rate'] == income - expense
                pause_cases += 1
    retained_income_cases = 0
    for portfolio in (500, 999999.99, 1000000):
        for dividend in (0, .00001, 50):
            for treasury in (0, 999999.99, 1000000):
                for existing_claim in (0, 5):
                    model = WeeklyModel(current=1)
                    owner = model.countries[1]
                    owner.variables.update(int_investments=portfolio,
                                           int_investments_rate=dividend,
                                           treasury=treasury,
                                           eon_investment_unclaimed_income=existing_claim,
                                           bureaucracy_gain=20)
                    owner.flags.add('int_reinvestment_flag')
                    before = portfolio + treasury + existing_claim
                    model.effect(expense_nodes + income_nodes + cash_nodes, [1])
                    model.effect([('eon_investment_reinvest_weekly', '=', 'yes')] + nodes, [1])
                    after = sum(owner.variables[x] for x in (
                        'int_investments', 'treasury', 'eon_investment_unclaimed_income'))
                    assert abs(after - (before + dividend - 20)) < 1e-8
                    expected_portfolio = min(1000000, portfolio + dividend)
                    assert abs(owner.variables['int_investments'] - expected_portfolio) < 1e-8
                    saved = dict(owner.variables)
                    model.effect([('eon_investment_claim_income', '=', 'yes')], [1])
                    assert owner.variables == saved, 'Repeated collection credited twice'
                    retained_income_cases += 1
    category = parser.one(parser.ast((ROOT / 'common/decisions/categories/eon_investment_income_categories.txt').read_bytes()), 'eon_investment_income_category')
    panel = parser.one(parser.ast((ROOT / 'common/decisions/eon_investment_income_decisions.txt').read_bytes()), 'eon_investment_income_category')
    collect = parser.one(panel, 'eon_investment_income_collect')
    manual_income_ui_cases = 0
    for exists in (False, True):
        for claim in (0, .00001, 5):
            for treasury in (-1000000, 0, 999999.99, 1000000):
                model = WeeklyModel(current=1)
                owner = model.countries[1]
                owner.exists = exists
                owner.variables.update(treasury=treasury, eon_investment_unclaimed_income=claim)
                for ident in (2, 3, 4):
                    model.countries[ident].variables.update(treasury=700 + ident,
                        eon_investment_unclaimed_income=100 + ident)
                other_balances = {ident: dict(model.countries[ident].variables) for ident in (2, 3, 4)}
                assert model.trigger(parser.one(category, 'visible'), [1]) == (claim > 0)
                assert model.trigger(parser.one(collect, 'visible'), [1]) == (claim > 0)
                assert model.trigger(parser.one(collect, 'available'), [1]) == (claim > 0 and treasury < 1000000)
                model.effect(parser.one(collect, 'complete_effect'), [1])
                payment = min(claim, max(1000000 - treasury, 0)) if exists else 0
                assert abs(owner.variables['treasury'] - treasury - payment) < 1e-8
                assert abs(owner.variables['eon_investment_unclaimed_income'] - claim + payment) < 1e-8
                assert other_balances == {ident: dict(model.countries[ident].variables) for ident in (2, 3, 4)}
                saved = dict(owner.variables)
                model.effect(parser.one(collect, 'complete_effect'), [1])
                assert owner.variables == saved
                manual_income_ui_cases += 1
    source_paths = (
        'common/on_actions/01_on_actions.txt',
        'common/scripted_effects/00_money_system.txt',
        'common/scripted_effects/eon_investment_income_effects.txt',
        'common/decisions/categories/eon_investment_income_categories.txt',
        'common/decisions/eon_investment_income_decisions.txt',
    )
    print(json.dumps({'checks_passed': True, 'weekly_cash_cases': cases,
                      'energy_budget_cash_integration_cases': integration_cases,
                      'debt_pause_and_reinvestment_cases': pause_cases,
                      'retained_investment_income_cases': retained_income_cases,
                      'manual_income_ui_cases': manual_income_ui_cases,
                      'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source_paths},
                      'native_ui_proven': False,
                      'native_weekly_hook_order_proven': False,
                      'proof_scope': 'actual budget forecast exclusion, repayment and cash mutation AST; regional updates and native ordering outside scope'}, indent=2))


if __name__ == '__main__':
    main()
