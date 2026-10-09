"""Narrow actual-AST cash/default-claim accounting; economy refresh is opaque.

No independent payment algorithm is supplied. Native ingame_update_setup is
counted, never replaced with claims about whole-economy or GUI behavior.
"""
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('eon_default_parser', ROOT / 'tools/validation/aid_flag_scope/_model.py')
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)
one = parser.one


def ast(text):
    # Budget/decision files also contain native lists of bare items; retain
    # those items without treating them as executable payment predicates.
    tokens = [match[0].strip('"') for match in parser.TOKEN.finditer(text.lstrip('\ufeff'))
              if not match[0].startswith('#')]
    position = 0

    def parse():
        nonlocal position
        nodes = []
        while position < len(tokens) and tokens[position] != '}':
            key = tokens[position]
            position += 1
            if position >= len(tokens) or tokens[position] not in ('=', '<', '>', '<=', '>=', '!=', '=='):
                nodes.append(('__item__', '=', key))
                continue
            operator = tokens[position]
            position += 1
            if tokens[position] == '{':
                position += 1
                body = parse()
                assert tokens[position] == '}'
                position += 1
            else:
                body = tokens[position]
                position += 1
            nodes.append((key, operator, body))
        return nodes

    result = parse()
    assert position == len(tokens)
    return result


class Model:
    def __init__(self, effects, triggers, cash, claim, aggregate=73, interest=4,
                 gdp=100, active=True, exists=True, precision=None, overdue=False, ai=False):
        self.effects, self.triggers = effects, triggers
        self.variables = {'treasury': cash, 'debt_default_left': claim, 'debt': aggregate,
                          'interest_rate': interest, 'gdp_total': gdp,
                          'debt_default_total': 999, 'debt_bailout': 123,
                          'old_gdp': gdp, 'int_investments': 13}
        self.temp = {'eon_debt_default_requested_payment': 99999, 'eon_debt_default_payment': 777}
        self.active, self.exists = active, exists
        self.precision, self.updates = precision, 0
        self.flags = {'eon_debt_default_overdue'} if overdue else set()
        self.booms = 0
        self.ai = ai
        self.native_outcomes = []
        # Decision callbacks can remain queued while another repayment closes
        # the old record. Presence is modeled; native tests own the real timer.
        self.decisions = set()
        # Political intervention scopes are deliberately not simulated: these
        # sovereign fixtures have zero influence entries, and their preserved
        # AST is checked separately. Native tests cover real callback execution.

    def value(self, key):
        try:
            return float(key)
        except (TypeError, ValueError):
            return self.temp.get(key, self.variables.get(key, 0))

    def assign(self, owner, key, value):
        assert '.' not in key and '^' not in key, ('Unexpected qualified state', key)
        if self.precision is not None:
            quantum = Decimal(1).scaleb(-self.precision)
            value = float(Decimal(str(value)).quantize(quantum, rounding=ROUND_DOWN))
        owner[key] = value

    def trigger(self, nodes):
        for key, operator, body in nodes:
            if key in self.triggers:
                passed = self.trigger(self.triggers[key]) == (body == 'yes')
            elif key == 'exists':
                passed = self.exists == (body == 'yes')
            elif key == 'has_active_mission':
                assert body == 'debt_default_main_mission'
                passed = self.active
            elif key == 'has_decision':
                passed = body in self.decisions
            elif key in ('set_temp_variable', 'multiply_temp_variable',
                         'add_to_temp_variable', 'subtract_from_temp_variable',
                         'clamp_temp_variable'):
                # These math primitives are documented native triggers too.
                self.effect([(key, operator, body)])
                passed = True
            elif key == 'has_country_flag':
                passed = body in self.flags
            elif key == 'has_variable':
                passed = body in self.variables
            elif key == 'is_subject':
                passed = body == 'no'
            elif key == 'is_ai':
                passed = self.ai == (body == 'yes')
            elif key == 'has_dynamic_modifier':
                assert one(body, 'modifier') == 'cartel_penalties'
                passed = False  # These accounting fixtures have no cartels.
            elif key == 'if':
                limit = one(body, 'limit')
                passed = (not self.trigger(limit) or
                          self.trigger([node for node in body if node[0] != 'limit']))
            elif key == 'check_variable':
                if any(k == 'var' for k, o, v in body):
                    left, right = one(body, 'var'), one(body, 'value')
                    names = {'less_than_or_equals': '<=', 'greater_than_or_equals': '>=',
                             'less_than': '<', 'greater_than': '>', 'equals': '='}
                    comparisons = [v for k, o, v in body if k == 'compare']
                    comparison = names[comparisons[0]] if comparisons else '='
                else:
                    assert len(body) == 1
                    left, comparison, right = body[0]
                passed = parser.compare(self.value(left), comparison, self.value(right))
            elif key in ('AND', 'custom_trigger_tooltip'):
                passed = self.trigger([node for node in body if node[0] != 'tooltip'])
            elif key == 'NOT':
                passed = not self.trigger(body)
            elif key == 'OR':
                passed = any(self.trigger([node]) for node in body)
            else:
                raise AssertionError(('Unknown default trigger', key, operator, body))
            if not passed:
                return False
        return True

    def effect(self, nodes):
        preceding_if = None
        for key, operator, body in nodes:
            if key == 'else':
                assert preceding_if is not None, 'Unpaired else reached'
                if not preceding_if:
                    self.effect(body)
                preceding_if = None
                continue
            preceding_if = None
            if key in self.effects:
                self.effect(self.effects[key])
            elif key == 'if':
                limits = [v for k, o, v in body if k == 'limit']
                assert len(limits) == 1
                preceding_if = self.trigger(limits[0])
                if preceding_if:
                    self.effect([node for node in body if node[0] != 'limit'])
            elif key in ('set_temp_variable', 'set_variable', 'multiply_temp_variable',
                         'multiply_variable', 'subtract_from_variable', 'add_to_variable',
                         'add_to_temp_variable', 'subtract_from_temp_variable'):
                assert len(body) == 1 and body[0][1] == '='
                variable, _, source = body[0]
                owner = self.temp if key in ('set_temp_variable', 'multiply_temp_variable',
                                            'add_to_temp_variable', 'subtract_from_temp_variable') else self.variables
                operand = self.value(source)
                if key in ('subtract_from_variable', 'add_to_variable',
                           'subtract_from_temp_variable', 'add_to_temp_variable'):
                    operand = owner.get(variable, 0) + operand * (-1 if key.startswith('subtract_') else 1)
                elif key in ('multiply_variable', 'multiply_temp_variable'):
                    operand *= owner.get(variable, 0)
                self.assign(owner, variable, operand)
            elif key in ('clamp_variable', 'clamp_temp_variable'):
                owner = self.temp if key == 'clamp_temp_variable' else self.variables
                variable = one(body, 'var')
                lower = [v for k, o, v in body if k == 'min']
                upper = [v for k, o, v in body if k == 'max']
                result = owner.get(variable, 0)
                if lower:
                    result = max(result, self.value(lower[0]))
                if upper:
                    result = min(result, self.value(upper[0]))
                self.assign(owner, variable, result)
            elif key == 'ingame_update_setup':
                assert body == 'yes'
                self.updates += 1
            elif key == 'custom_effect_tooltip':
                pass  # UI interpolation is a native boundary.
            elif key == 'clear_variable':
                self.variables.pop(body, None)
            elif key == 'set_country_flag':
                assert isinstance(body, str)
                self.flags.add(body)
            elif key == 'clr_country_flag':
                self.flags.discard(body)
            elif key == 'add_timed_idea':
                assert one(body, 'idea') == 'debt_default_ecomomic_boom'
                assert one(body, 'days') == '360'
                self.booms += 1
            elif key == 'round_variable':
                self.assign(self.variables, body, round(self.value(body)))
            elif key == 'activate_mission':
                assert body == 'debt_default_main_mission'
                self.active = True
            elif key == 'depression':
                assert body == 'yes'
                self.native_outcomes.append('depression')  # Native economic boundary.
            elif key == 'every_subject_country':
                # Fixtures explicitly have no subjects; no target is traversed.
                self.native_outcomes.append('empty_subject_iteration')
            elif key == 'create_wargoal':
                self.native_outcomes.append('create_wargoal')  # RED observer only.
            elif key == 'FROM':
                assert all(k == 'add_autonomy_score' for k,o,v in body)
                self.native_outcomes.append('foreign_autonomy')  # RED observer only.
            elif key == 'log':
                pass
            else:
                raise AssertionError(('Unknown default effect', key, operator, body))


def read(path):
    return ROOT.joinpath(path).read_text(encoding='utf-8-sig')


def definitions(path):
    return {key: body for key, operator, body in ast(read(path))}
