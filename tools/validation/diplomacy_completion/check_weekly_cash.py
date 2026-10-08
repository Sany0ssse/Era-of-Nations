"""Execute the current weekly debt/cash slice, with real remaining debt caps."""
from pathlib import Path
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    'eon_weekly_ast', ROOT / 'tools/validation/diplomacy_package_03/_support.py')
parser = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = parser
spec.loader.exec_module(parser)


class WeeklyModel(parser.Model):
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
                target[name] = min(self.value(parser.one(value, 'max'), stack),
                                   max(self.value(parser.one(value, 'min'), stack), target.get(name, 0)))
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
                owner.variables.update(treasury=500, treasury_rate=rate, debt=debt)
                if automatic:
                    owner.flags.add('automatically_pay_off_debt_enabled')
                # An earlier effect must not leak a previous temporary deduction.
                model.temp['treasury_rate_debt_payment'] = 0 if automatic and rate == 100 and debt == 1 else 17
                model.effect(nodes, [1])
                payment = min(debt, max(rate, 0) * .25) if automatic else 0
                assert abs(owner.variables['treasury'] - (500 + rate - payment)) < 1e-9, (rate, debt, automatic, owner.variables)
                expected_debt = debt - payment
                if automatic and rate > 0 and debt > 0 and expected_debt < .001:
                    expected_debt = 0
                assert abs(owner.variables['debt'] - expected_debt) < 1e-9
                assert model.temp['treasury_rate_debt_payment'] == payment
                cases += 1
    print(json.dumps({'checks_passed': True, 'weekly_cash_cases': cases,
                      'native_weekly_hook_order_proven': False,
                      'proof_scope': 'actual repayment and cash mutation AST; budget input and native ordering supplied'}, indent=2))


if __name__ == '__main__':
    main()
