"""Execute the real equipment-purchase budget branch repeatedly in one scope.

This targets the native82 counterexample: the temporary basket previously
survived nested effect calls, then was multiplied again. All price inputs stay
explicit and unchanged. This is AST regression, not a native market campaign.
"""
from copy import deepcopy
import json
import math

from test_launch import one, read


def walk(nodes):
    for node in nodes:
        yield node
        if isinstance(node[2], list): yield from walk(node[2])


def market_branch():
    effect = one(read('common/scripted_effects/00_money_system.txt'), 'calculate_additional_expense_rate')
    candidates = [node for node in effect if node[0] == 'if' and
                  ('market_purchase_factories', '>', '0') in list(walk(one(node[2], 'limit')))]
    assert len(candidates) == 1
    return candidates[0]


class Model:
    def __init__(self, inputs, old_temp=0):
        self.inputs = inputs
        self.temp = {'market_purchase_factories_cost': old_temp}
        self.variables = {'additional_expenses_rate': 0}

    def value(self, value):
        if isinstance(value, list):
            result = None
            for key, operator, amount in value:
                assert operator == '='
                operand = self.value(amount)
                if key == 'value': result = operand
                elif key == 'add': result += operand
                elif key == 'multiply': result *= operand
                else: raise AssertionError(('Unknown market expression', key))
            assert result is not None
            return result
        if value in self.temp: return self.temp[value]
        if value in self.variables: return self.variables[value]
        if value in self.inputs: return self.inputs[value]
        return float(value)

    def execute(self, nodes):
        for key, operator, body in nodes:
            if key == 'if':
                limit = one(body, 'limit'); assert len(limit) == 1
                var, comparison, expected = one(limit, 'check_variable')[0]
                assert comparison == '>'
                if self.value(var) > self.value(expected):
                    self.execute([node for node in body if node[0] != 'limit'])
            elif key in ('set_temp_variable', 'add_to_temp_variable', 'multiply_temp_variable', 'set_variable', 'add_to_variable'):
                assert len(body) == 1
                var, comparator, amount = body[0]; assert comparator == '='
                target = self.variables if key in ('set_variable', 'add_to_variable') else self.temp
                quantity = self.value(amount)
                if key.startswith('add'): quantity += target.get(var, 0)
                elif key.startswith('multiply'): quantity *= target[var]
                target[var] = quantity
            else: raise AssertionError(('Unknown market effect', key))


def input_fixture(branch, count, modifier, base_cost):
    names = {value for key, operator, value in walk([branch]) if isinstance(value, str)}
    inputs = {name: 0 for name in names if name.startswith(('amount_', 'global.'))}
    inputs.update({'market_purchase_factories': count, 'global.base_unit_cost': base_cost,
                   'modifier@international_market_purchase_modifier': modifier})
    multiplier_names = sorted(name for name in inputs if name.endswith('_cost_mult'))
    amount_names = sorted(name for name in inputs if name.startswith('amount_'))
    for index, name in enumerate(multiplier_names): inputs[name] = (index+1)*0.13
    for index, name in enumerate(amount_names): inputs[name] = (index % 5)+1
    return inputs


def assert_repeatable(branch, count, modifier, base_cost, old_temp):
    model = Model(input_fixture(branch, count, modifier, base_cost), old_temp)
    results = []
    for _ in range(6):
        model.variables['additional_expenses_rate'] = 0
        model.execute([branch])
        results.append(model.variables['additional_expenses_rate'])
        if count > 0:
            assert math.isclose(model.variables['market_purchase_factories_cost_track'], results[-1], abs_tol=1e-10)
            assert math.isclose(model.temp['market_purchase_factories_cost'], results[-1], abs_tol=1e-10)
    assert all(math.isclose(value, results[0], abs_tol=1e-10) for value in results), results
    if count == 0: assert results == [0]*6 and model.temp['market_purchase_factories_cost'] == old_temp
    return results[0]


def run():
    branch = market_branch()
    body = branch[2]
    # Reset before the first basket addition; neither basket prices nor the
    # country multiplier/final2 are changed by this fix.
    reset = ('set_temp_variable', '=', [('market_purchase_factories_cost', '=', '0')])
    assert body[1] == reset
    assert sum(node == reset for node in body) == 1
    additions = [node for node in body if node[0] == 'add_to_temp_variable' and
                 one(node[2], 'market_purchase_factories_cost')]
    assert len(additions) == 28
    cases = 0
    for count in (0, 1, 7):
        for modifier in (-0.5, 0, 0.35, 1):
            for base_cost in (0.03, 1.7):
                expected = assert_repeatable(branch, count, modifier, base_cost, 0)
                for poisoned in (1, 37.26, 999):
                    actual = assert_repeatable(branch, count, modifier, base_cost, poisoned)
                    assert math.isclose(actual, expected, abs_tol=1e-10)
                    cases += 1
    # Removing exactly the reset recreates the native repeated-call failure.
    old = deepcopy(branch)
    old[2].remove(reset)
    try: assert_repeatable(old, 1, 0.35, 1.7, 0)
    except AssertionError: rejected = True
    else: raise AssertionError('Missing-reset mutant survived')
    # The observed82 RAJ increments follow the same carry-forward factor2.7.
    before, base, after, arsenal = 37.26158, 107.21430, 296.09612, 0.00256
    first = base-(before-arsenal)
    second = (after-arsenal)-base
    assert math.isclose(second, first*2.7, abs_tol=0.000011, rel_tol=0)
    print(json.dumps({'market_budget_same_context_cases': cases,
                      'repeated_calls_per_case': 6, 'basket_components_preserved': len(additions),
                      'missing_reset_mutant_rejected': rejected,
                      'native82_failed_receipt_preserved': True,
                      'native82_ratio_matches_old_scratch_carry': True,
                      'native_fixed_budget_behavior_verified': False}, indent=2))


if __name__ == '__main__': run()
