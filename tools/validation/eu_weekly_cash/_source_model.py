"""Bounded current-source EU rates -> display/cash -> weekly treasury AST.

The fixtures declare annual allocations and other weekly rates. They do not
simulate budget adoption, engine scheduling, idea callbacks or a campaign.
"""
from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    'eu_weekly_membership', ROOT / 'tools/validation/eu_membership/test_lifecycle.py')
membership = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = membership
spec.loader.exec_module(membership)
ast, one = membership.ast, membership.one
MONEY = 'common/scripted_effects/00_money_system.txt'


def read(path):
    return (ROOT / path).read_bytes().decode('utf-8-sig')


def added_rate(node, rate, operand):
    return node[0] == 'add_to_variable' and node[2] == [(rate, '=', operand)]


def direct_rate_block(source, effect, rate, operand):
    body = one(ast(source), effect)
    found = [node for node in body if node[0] == 'if' and
             any(added_rate(child, rate, operand) for child in node[2])]
    assert len(found) == 1, (effect, rate, operand)
    return [found[0]]


def contribution_conversion():
    body = one(ast(read('common/scripted_effects/00_eu_scripted_effects.txt')),
               'update_EU_budget_call_rate')
    loops = [v for k, op, v in body if k == 'for_each_scope_loop']
    found = []
    for loop in loops:
        for i, node in enumerate(loop):
            if node == ('set_variable', '=', [('THIS.EU_budget_contribution_weekly', '=',
                                               'THIS.EU_budget_contribution')]):
                found.append(loop[i:i + 2])
    assert len(found) == 1
    return found[0]


def display_and_cash_nodes():
    body = one(ast(read(MONEY)), 'update_display')
    def assignment(node, key, variable):
        return node[0] == key and isinstance(node[2], list) and node[2][0][0] == variable
    def segment(variable):
        start = next(i for i, n in enumerate(body) if assignment(n, 'set_variable', variable))
        end = next(i for i in range(start, len(body)) if body[i][0] == 'clamp_variable'
                   and one(body[i][2], 'var') == variable)
        return body[start:end + 1]
    income, expense = segment('display_income'), segment('display_expense')
    # Only the unrelated resource/tax diagnostic ratio is outside this scope.
    excluded = [n for n in income if n[0] in ('set_variable', 'divide_variable')
                and n[2][0][0] == 'resource_to_tax_income']
    assert [n[0] for n in excluded] == ['set_variable', 'divide_variable']
    income = [n for n in income if n not in excluded]
    start = next(i for i, n in enumerate(body) if assignment(n, 'set_variable', 'treasury_rate'))
    cash = body[start:start + 4]
    assert [n[2][0][0] for n in cash] == ['treasury_rate', 'treasury_rate',
                                        'eon_treasury_cash_rate', 'eon_treasury_cash_rate']
    return expense + income + cash


def weekly_settlement():
    raw = read('common/on_actions/01_on_actions.txt')
    start = raw.index('# Pay down debt automatically this weekly tick')
    end = raw.index('#Automated taking debt', start)
    return ast(raw[start:end])


class CashModel(membership.Model):
    """Execute the actual financial snippets with explicit numeric operands."""
    def __init__(self, money=None):
        super().__init__()
        self.members()
        self.triggers.update({k: v for k, op, v in ast(read(
            'common/scripted_triggers/eon_eu_financial_triggers.txt'))})
        self.effects.update({k: v for k, op, v in ast(read(
            'common/scripted_effects/eon_investment_income_effects.txt'))})
        money = read(MONEY) if money is None else money
        self.income = direct_rate_block(money, 'calculate_additional_income_rate',
                                       'additional_income_rate', 'EU_subsidies')
        self.expense = direct_rate_block(money, 'calculate_additional_expense_rate',
                                        'additional_expenses_rate', 'EU_budget_contribution_weekly')
        self.other_income = direct_rate_block(money, 'calculate_additional_income_rate',
                                             'additional_income_rate', 'additional_income_blood_diamond_trade')
        # Preserve real refresh resets; skip unrelated national calculations.
        self.income_reset = one(ast(money), 'calculate_additional_income_rate')[:1]
        self.expense_reset = one(ast(money), 'calculate_additional_expense_rate')[:1]

    def value(self, token, stack):
        if not isinstance(token, list):
            return super().value(token, stack)
        result = 0
        for key, op, value in token:
            assert op == '=' and key in ('value', 'add', 'subtract', 'multiply', 'divide'), token
            rhs = self.value(value, stack)
            if key == 'value': result = rhs
            elif key == 'add': result += rhs
            elif key == 'subtract': result -= rhs
            elif key == 'multiply': result *= rhs
            else:
                assert rhs != 0
                result /= rhs
        return result

    def effect(self, nodes, stack):
        i = 0
        while i < len(nodes):
            key, op, value = nodes[i]; i += 1
            if key == 'if':
                batch = [(key, op, value)]
                while i < len(nodes) and nodes[i][0] in ('else', 'else_if'):
                    batch.append(nodes[i]); i += 1
                super().effect(batch, stack)
            elif key in ('set_variable', 'add_to_variable', 'subtract_from_variable',
                         'multiply_variable', 'divide_variable', 'set_temp_variable',
                         'add_to_temp_variable', 'subtract_from_temp_variable',
                         'multiply_temp_variable', 'divide_temp_variable'):
                assert len(value) == 1 and value[0][1] == '='
                name, _, token = value[0]; rhs = self.value(token, stack)
                if 'temp' in key: target, name = self.temp, name
                else:
                    obj, name = self.slot(name, stack); target = obj.variables
                before = target.get(name, 0)
                if key.startswith('set_'): result = rhs
                elif key.startswith('add_'): result = before + rhs
                elif key.startswith('subtract_'): result = before - rhs
                elif key.startswith('multiply_'): result = before * rhs
                else:
                    assert rhs != 0
                    result = before / rhs
                target[name] = result
            elif key == 'clamp_variable':
                obj, name = self.slot(one(value, 'var'), stack)
                lower = next((v for k, op, v in value if k == 'min'), '-1e100')
                upper = next((v for k, op, v in value if k == 'max'), '1e100')
                obj.variables[name] = min(self.value(upper, stack),
                    max(self.value(lower, stack), obj.variables.get(name, 0)))
            else:
                super().effect([(key, op, value)], stack)

    def refresh_cash_rates(self, who=2):
        nation = self.nations[who]
        self.sender = who
        nodes = self.income_reset + self.expense_reset + self.income + self.expense + self.other_income
        self.effect(nodes + display_and_cash_nodes(), [nation])

    def settle_week(self, who=2):
        self.sender = who
        self.effect(weekly_settlement(), [self.nations[who]])


def seed_rates(model, grants=(52, 104, 156, 208), contribution=104, who=2):
    nation = model.nations[who]
    nation.variables.update(treasury=500, debt=0, tax_gain=10, bureaucracy_gain=4,
                           energy_selling_income=0, energy_buying_expenses=0)
    for name, value in zip(('EU_natural_subsidies', 'EU_growth_subsidies',
                            'EU_admin_subsidies', 'EU_global_exp_subsidies'), grants):
        nation.variables[name] = value
    nation.variables['EU_budget_contribution'] = contribution
    model.effect(contribution_conversion(), [nation])
    return nation
