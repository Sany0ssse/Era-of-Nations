"""Execute existing protest growth source with bounded synthetic country facts.

Both passive RNG outcomes are supplied explicitly. The monthly event draw is a
recorded boundary: native events, rendered UI and a campaign are not simulated.
Removing or moving the final clamp must fail the same behavioural invariant.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = 'common/scripted_effects/00_protests_effects.txt'
LOCALES = {
    'english': 'localisation/english/MDC_politics_content_l_english.yml',
    'russian': 'localisation/russian/MD_politics_content_l_russian.yml',
}
spec = importlib.util.spec_from_file_location(
    'protest_source_parser', ROOT / 'tools/validation/diplomacy_package_26/test_relations.py'
)
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)
parse = parser.parse


def one(nodes, key):
    found = [data for name, operator, data in nodes if name == key]
    assert len(found) == 1, (key, len(found))
    return found[0]


def source():
    return dict((name, body) for name, operator, body in parse(
        (ROOT / SOURCE).read_text(encoding='utf-8-sig')
    ))


class Growth:
    """Strict reachable helper interpreter; unknown commands fail closed."""

    def __init__(self, definitions, strength=0, radicalisation=0, decay=False):
        self.definitions = definitions
        self.variables = {'protest_strength': strength, 'protest_radicalisation': radicalisation}
        self.temps = {}
        self.facts = {'has_fuel': 100, 'has_stability': .65, 'has_war_support': .5,
                      'has_offensive_war': False, 'has_negative_economy_vibe': False}
        self.ideas, self.modifiers = set(), set()
        self.volunteers = False
        self.decay = decay
        self.rolls = []

    @staticmethod
    def key(token):
        return token.removeprefix('THIS.')

    def value(self, token):
        try:
            return float(token)
        except ValueError:
            pass
        if token.startswith('THIS.'):
            return self.variables.get(self.key(token), 0)
        return self.temps.get(token, self.variables.get(token, 0))

    @staticmethod
    def compare(left, operator, right):
        return {'=': left == right, '>': left > right, '<': left < right,
                '>=': left >= right, '<=': left <= right, '!=': left != right}[operator]

    def condition(self, nodes):
        outcomes = []
        for name, operator, data in nodes:
            if name == 'check_variable':
                assert len(data) == 1
                field, comparison, wanted = data[0]
                ready = self.compare(self.value(field), comparison, self.value(wanted))
            elif name == 'NOT':
                ready = not self.condition(data)
            elif name == 'OR':
                ready = any(self.condition([node]) for node in data)
            elif name == 'has_variable':
                ready = self.key(data) in self.variables
            elif name == 'has_idea':
                ready = data in self.ideas
            elif name == 'has_dynamic_modifier':
                ready = one(data, 'modifier') in self.modifiers
            elif name == 'any_other_country':
                # Explicit external witness; do not invent country/volunteer AI.
                assert data == [('has_volunteers_amount_from', '=',
                                 [('tag', '=', 'PREV'), ('count', '>', '0')])]
                ready = self.volunteers
            elif name in self.facts:
                if data in ('yes', 'no'):
                    ready = self.facts[name] == (data == 'yes')
                else:
                    ready = self.compare(self.facts[name], operator, float(data))
            else:
                raise AssertionError(('Unknown protest condition', name))
            outcomes.append(ready)
        return all(outcomes)

    def execute(self, nodes):
        for name, operator, data in nodes:
            assert operator == '='
            if name == 'if':
                if self.condition(one(data, 'limit')):
                    self.execute([node for node in data if node[0] != 'limit'])
            elif name == 'random':
                assert float(one(data, 'chance')) in (10, 50)
                if self.decay:
                    self.execute([node for node in data if node[0] != 'chance'])
            elif name in ('clamp_variable', 'clamp_temp_variable'):
                fields = dict((field, value) for field, op, value in data)
                target = self.temps if name == 'clamp_temp_variable' else self.variables
                field = self.key(fields['var'])
                target[field] = max(float(fields.get('min', '-inf')),
                                    min(float(fields.get('max', 'inf')), target[field]))
            elif name == 'round_temp_variable':
                # Test inputs avoid fractional ties; native rounding is unclaimed.
                self.temps[data] = round(self.temps[data])
            elif name in ('set_variable', 'add_to_variable', 'set_temp_variable',
                          'add_to_temp_variable', 'subtract_from_temp_variable',
                          'multiply_temp_variable'):
                assert len(data) == 1
                field, op, wanted = data[0]
                assert op == '='
                target = self.temps if 'temp' in name else self.variables
                amount = self.value(wanted)
                field = self.key(field)
                previous = target.get(field, 0)
                if name.startswith('set_'):
                    target[field] = amount
                elif name.startswith('add_'):
                    target[field] = previous + amount
                elif name.startswith('subtract_'):
                    target[field] = previous - amount
                else:
                    target[field] = previous * amount
            elif name == 'roll_protest_chance':
                assert data == 'yes'
                choices = one(self.definitions[name], 'random_list')
                assert len(choices) == 2 and choices[0][0] == '500'
                assert choices[1][0] == 'var:protest_strength'
                self.rolls.append(self.value('protest_strength'))
            elif name in self.definitions:
                assert data == 'yes'
                self.execute(self.definitions[name])
            else:
                raise AssertionError(('Unknown protest effect', name))

    def tick(self):
        self.execute(self.definitions['apply_protest_effects'])
        return self


class ProtestChecks(unittest.TestCase):
    def test_monthly_bounds_before_event_draw(self):
        for strength in (-8, 0, 35, 36, 98, 100, 120):
            for decay in (False, True):
                with self.subTest(strength=strength, decay=decay):
                    x = Growth(source(), strength, radicalisation=9, decay=decay)
                    x.variables.update(energy_balance=-1, expected_welfare_spending=10)
                    x.facts['has_fuel'] = 0
                    x.tick()
                    self.assertGreaterEqual(x.variables['protest_strength'], 0)
                    self.assertLessEqual(x.variables['protest_strength'], 100)
                    self.assertTrue(all(35 < weight <= 100 for weight in x.rolls))

    def test_remove_or_move_clamp_mutants_fail_same_bound(self):
        definitions = source()
        body = definitions['apply_protest_effects']
        index = next(i for i, node in enumerate(body) if node[0] == 'clamp_variable')
        for location in (None, 0):
            mutated = deepcopy(definitions)
            removed = mutated['apply_protest_effects'].pop(index)
            if location is not None:
                mutated['apply_protest_effects'].insert(location, removed)
            for decay in (False, True):
                x = Growth(mutated, strength=100, decay=decay)
                x.variables['expected_welfare_spending'] = 8
                x.tick()
                self.assertGreater(x.variables['protest_strength'], 100)
                self.assertGreater(x.rolls[-1], 100)

    def test_fuel_shortage_changes_strength_not_radicalisation(self):
        for decay in (False, True):
            stocked = Growth(source(), strength=10, radicalisation=4, decay=decay).tick()
            empty = Growth(source(), strength=10, radicalisation=4, decay=decay)
            empty.facts['has_fuel'] = 0
            empty.tick()
            self.assertEqual(empty.variables['protest_strength'], stocked.variables['protest_strength'] + 1)
            self.assertEqual(empty.variables['protest_radicalisation'], stocked.variables['protest_radicalisation'])
            empty = Growth(source(), strength=10)
            empty.facts['has_fuel'] = 0
            empty.variables['modifier@protests_drift_modifier'] = 1
            self.assertEqual(empty.tick().variables['protest_strength'], 12)

    def test_existing_threshold_and_all_growth_reasons(self):
        self.assertEqual(Growth(source(), strength=35).tick().rolls, [])
        self.assertEqual(Growth(source(), strength=36).tick().rolls, [36])
        x = Growth(source())
        x.variables.update(energy_balance=-1, expected_welfare_spending=2,
                           expected_minimal_salary=2, expected_health_spending=2,
                           expected_edu_spending=2, expected_police_spending=2,
                           expected_adm_spending=2, expected_military_sp=2)
        x.facts.update(has_fuel=0, has_stability=.1, has_war_support=.1,
                       has_offensive_war=True, has_negative_economy_vibe=True)
        x.ideas.update(('War_with_nukestate_idea', 'AB_partial_mobilization'))
        x.modifiers.add('high_unemployment_modifier')
        x.volunteers = True
        # Seven synthetic budget shortfalls of2 and eight separate source reasons.
        self.assertEqual(x.tick().variables['protest_strength'], 22)

    def test_fuel_localisation_matches_source(self):
        for language, relative in LOCALES.items():
            data = (ROOT / relative).read_bytes()
            self.assertTrue(data.startswith(b'\xef\xbb\xbf'))
            self.assertNotIn(b'\r', data)
            text = data.decode('utf-8-sig')
            line = re.findall(r'^\s*no_fuel_protests_TT:.*$', text, re.M)
            self.assertEqual(len(line), 1)
            self.assertIn('+1', line[0])
            self.assertNotIn('radicalisation', line[0].lower())
            self.assertNotIn('радикализац', line[0].lower())


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ProtestChecks)
    )
    print(json.dumps({'all_passed': result.wasSuccessful(), 'tests': result.testsRun,
                      'native_runtime': False, 'random_event_delivery': False,
                      'source_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                                        for p in (SOURCE, *LOCALES.values())}}, indent=2))
    raise SystemExit(not result.wasSuccessful())
