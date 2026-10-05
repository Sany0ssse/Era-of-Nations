"""Fail-closed interpreter for treaty source, with one shared temporary environment.

This models source control flow and pair bookkeeping, not the HOI4 engine.
The existing influence macro is witnessed with its actual call parameters.
"""
from dataclasses import dataclass, field
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|[=<>!]+|[^\s{}=<>!#"]+')


def ast(text):
    tokens = [m[0].strip('"') for m in TOKEN.finditer(text.lstrip('\ufeff'))
              if not m[0].startswith('#')]
    index = 0

    def parse():
        nonlocal index
        result = []
        while index < len(tokens) and tokens[index] != '}':
            key = tokens[index]
            index += 1
            if index >= len(tokens) or tokens[index] not in ('=', '<', '>', '<=', '>=', '!=', '=='):
                result.append(('__item__', '=', key))
                continue
            op = tokens[index]
            index += 1
            if tokens[index] == '{':
                index += 1
                value = parse()
                assert tokens[index] == '}'
                index += 1
            else:
                value = tokens[index]
                index += 1
            result.append((key, op, value))
        return result

    result = parse()
    assert index == len(tokens), 'Unbalanced source'
    return result


def one(nodes, key):
    matches = [value for name, op, value in nodes if name == key]
    assert len(matches) == 1, (key, len(matches))
    return matches[0]


def compare(left, op, right):
    return {'=': left == right, '==': left == right, '!=': left != right,
            '<': left < right, '>': left > right, '<=': left <= right,
            '>=': left >= right}[op]


@dataclass
class Country:
    ident: int
    variables: dict = field(default_factory=dict)
    flags: set = field(default_factory=set)
    arrays: dict = field(default_factory=dict)
    opinions: dict = field(default_factory=dict)
    modifiers: set = field(default_factory=set)
    wars: set = field(default_factory=set)
    allies: set = field(default_factory=set)
    in_faction: bool = False
    exists: bool = True
    original_tag: str = 'GEN'
    leader: str = 'Generic leader'
    projects: list = field(default_factory=list)


class Interpreter:
    def __init__(self, countries, sender=1, receiver=2, remove_all=False):
        self.countries = countries
        self.sender, self.receiver = sender, receiver
        self.temp = {}
        self.remove_all = remove_all
        self.external_calls = []
        self.opinion_calls = []
        self.effects = dict((k, v) for k, op, v in ast((ROOT / 'common/scripted_effects/eon_investment_treaty_effects.txt').read_text(encoding='utf-8-sig')))
        self.triggers = dict((k, v) for k, op, v in ast((ROOT / 'common/scripted_triggers/eon_investment_treaty_triggers.txt').read_text(encoding='utf-8-sig')))
        eri_source = ast((ROOT / 'common/scripted_triggers/99_ERI_scripted_triggers.txt').read_text(encoding='utf-8-sig'))
        self.triggers['ERI_is_not_transitional_government'] = one(eri_source, 'ERI_is_not_transitional_government')

    def country(self, token, stack):
        if token == 'ROOT': return self.countries[self.sender]
        if token == 'THIS': return stack[-1]
        if token == 'PREV': return stack[-2]
        if token.startswith('var:'):
            return self.countries[int(self.value(token[4:], stack))]
        return self.countries[int(token)]

    def value(self, token, stack):
        if token.startswith('var:'): token = token[4:]
        try: return float(token)
        except ValueError: pass
        if token in ('ROOT', 'THIS', 'PREV'): return self.country(token, stack).ident
        if '.' in token:
            owner, key = token.split('.', 1)
            country = self.country(owner, stack)
        else: country, key = stack[-1], token
        if key == 'id': return country.ident
        return self.temp.get(key, country.variables.get(key, 0))

    def flag(self, token, stack):
        if '@' not in token: return token
        name, target = token.split('@', 1)
        return name + '@' + str(self.country(target, stack).ident)

    def check(self, nodes, stack):
        if any(k == 'var' for k, op, v in nodes):
            key, number = one(nodes, 'var'), one(nodes, 'value')
            mode = next((v for k, op, v in nodes if k == 'compare'), 'equals')
            op = {'equals': '=', 'not_equals': '!=', 'greater_than': '>',
                  'greater_than_or_equals': '>=', 'less_than': '<',
                  'less_than_or_equals': '<='}[mode]
        else:
            assert len(nodes) == 1
            key, op, number = nodes[0]
        return compare(self.value(key, stack), op, self.value(number, stack))

    def trigger(self, nodes, stack=None):
        if stack is None: stack = [self.countries[self.receiver]]
        for key, op, value in nodes:
            country = stack[-1]
            if key == 'tooltip': continue
            if key in self.triggers:
                passed = self.trigger(self.triggers[key], stack) == (value == 'yes')
            elif key in ('ROOT', 'THIS', 'PREV') or key.startswith('var:'):
                passed = self.trigger(value, stack + [self.country(key, stack)])
            elif key in ('AND', 'custom_trigger_tooltip', 'hidden_trigger'):
                passed = self.trigger(value, stack)
            elif key == 'NOT': passed = not self.trigger(value, stack)
            elif key == 'OR': passed = any(self.trigger([node], stack) for node in value)
            elif key == 'if':
                passed = not self.trigger(one(value, 'limit'), stack) or self.trigger([n for n in value if n[0] != 'limit'], stack)
            elif key == 'always': passed = value == 'yes'
            elif key == 'exists': passed = country.exists == (value == 'yes')
            elif key == 'original_tag': passed = country.original_tag == value
            elif key == 'has_country_leader': passed = country.leader == one(value, 'name')
            elif key == 'has_country_flag': passed = self.flag(value, stack) in country.flags
            elif key == 'has_war_with': passed = self.country(value, stack).ident in country.wars
            elif key == 'has_opinion':
                target = self.country(one(value, 'target'), stack).ident
                item = next(n for n in value if n[0] == 'value')
                passed = compare(country.opinions.get(target, 0), item[1], self.value(item[2], stack))
            elif key == 'is_in_faction': passed = country.in_faction == (value == 'yes')
            elif key == 'any_allied_country': passed = any(self.trigger(value, stack + [self.countries[n]]) for n in country.allies)
            elif key == 'check_variable': passed = self.check(value, stack)
            elif key == 'is_in_array':
                passed = int(self.value(one(value, 'value'), stack)) in country.arrays.get(one(value, 'array'), [])
            else: raise ValueError('Unmodeled trigger: ' + key)
            if not passed: return False
        return True

    def effect(self, nodes, stack=None):
        if stack is None:
            self.temp = {}
            stack = [self.countries[self.receiver]]
        for key, op, value in nodes:
            country = stack[-1]
            if key in ('log', 'custom_effect_tooltip'): continue
            if key in self.effects:
                assert value == 'yes'
                self.effect(self.effects[key], stack)
            elif key in ('ROOT', 'THIS', 'PREV') or key.startswith('var:'):
                self.effect(value, stack + [self.country(key, stack)])
            elif key == 'if':
                if self.trigger(one(value, 'limit'), stack): self.effect([n for n in value if n[0] != 'limit'], stack)
            elif key == 'while_loop_effect':
                count = 0
                while self.trigger(one(value, 'limit'), stack):
                    self.effect([n for n in value if n[0] not in ('limit', 'break')], stack)
                    count += 1
                    assert count < 1000, 'Nonterminating cleanup'
            elif key in ('set_variable', 'set_temp_variable'):
                assert len(value) == 1
                name, operator, number = value[0]
                (self.temp if key == 'set_temp_variable' else country.variables)[name] = self.value(number, stack)
            elif key == 'clear_variable': country.variables.pop(value, None)
            elif key == 'set_country_flag': country.flags.add(self.flag(value, stack))
            elif key == 'clr_country_flag': country.flags.discard(self.flag(value, stack))
            elif key in ('add_opinion_modifier', 'reverse_add_opinion_modifier', 'remove_opinion_modifier'):
                other = self.country(one(value, 'target'), stack)
                modifier = one(value, 'modifier')
                self.opinion_calls.append((country.ident, key, other.ident, modifier))
                if key == 'reverse_add_opinion_modifier': other.modifiers.add((country.ident, modifier))
                elif key == 'add_opinion_modifier': country.modifiers.add((other.ident, modifier))
                else: country.modifiers.discard((other.ident, modifier))
            elif key in ('remove_from_array', 'add_to_array'):
                array = country.arrays.setdefault(one(value, 'array'), [])
                member = int(self.value(one(value, 'value'), stack))
                if key == 'add_to_array': array.append(member)
                elif self.remove_all: array[:] = [n for n in array if n != member]
                elif member in array: array.remove(member)
            elif key == 'change_influence_percentage':
                assert value == 'yes'
                self.external_calls.append((country.ident, key, {name: self.temp.get(name) for name in ('percent_change', 'tag_index', 'influence_target')}))
            else: raise ValueError('Unmodeled effect: ' + key)


def countries():
    result = {n: Country(n, opinions={other: 30 for other in (1, 2, 3, 4)},
                         arrays={'permanent_investment_targets': []},
                         projects=['existing-building', 'pending-project']) for n in (1, 2, 3, 4)}
    return result
