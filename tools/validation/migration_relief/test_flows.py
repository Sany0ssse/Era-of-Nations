"""Execute actual migration helper AST with bounded native primitives.

This intentionally models STATE population and country counters separately.
Unsupported source statements fail closed; this is not native HOI4 acceptance.
"""
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
import math
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/validation/diplomacy_package_02'))
from _treaty_support import ast, one, compare


@dataclass
class Country:
    ident: int
    exists: bool = True
    at_war: bool = False
    variables: dict = field(default_factory=dict)
    arrays: dict = field(default_factory=dict)
    flags: set = field(default_factory=set)
    modifiers: set = field(default_factory=set)
    ideas: set = field(default_factory=set)
    neighbors: set = field(default_factory=set)
    wars: set = field(default_factory=set)
    faction: str | None = None
    kind: str = 'country'
    scope_token: float | None = None

    @property
    def pointer(self):
        # Native THIS.id is an opaque fractional scope token, not the fixture
        # identifier or an array index. Preserve every fractional component.
        return self.scope_token if self.scope_token is not None else 10789 + self.ident + .02446 * self.ident


@dataclass
class State:
    ident: int
    population: float
    owner: int
    controller: int
    cores: set = field(default_factory=set)
    variables: dict = field(default_factory=dict)
    arrays: dict = field(default_factory=dict)
    flags: set = field(default_factory=set)
    neighbors: set = field(default_factory=set)
    kind: str = 'state'


def rounded(value):
    return math.floor(value + .5) if value >= 0 else math.ceil(value - .5)


class Model:
    def __init__(self, countries=None, states=None, root=1):
        self.countries = countries or {ident: Country(ident) for ident in range(1, 5)}
        self.states = states or {
            101: State(101, 100000, 1, 1, {1}),
            102: State(102, 100000, 2, 2, {2}),
            103: State(103, 100000, 3, 3, {3}),
            104: State(104, 100000, 4, 4, {4}),
        }
        self.root = self.countries[root]
        self.global_vars = {'eon_migration_array_size': 0}
        self.global_arrays = {}
        self.global_flags, self.flag_days, self.temp = set(), {}, {}
        self.trace, self.manpower_calls = [], []
        self.random_branch = 0
        self.effects = {key: value for key, op, value in ast((ROOT / 'common/scripted_effects/eon_migration_relief_effects.txt').read_text(encoding='utf-8-sig'))}
        self.triggers = {key: value for key, op, value in ast((ROOT / 'common/scripted_triggers/eon_migration_relief_triggers.txt').read_text(encoding='utf-8-sig'))}
        for country in self.countries.values():
            country.variables.update(population_total_m=1, gdp_per_capita=10,
                                     total_unemployed_percentage_display=.1,
                                     eon_migration_peace_months=3,
                                     eon_migration_home_control_ratio=1)
        for country in self.countries.values():
            self.run('eon_migration_initialize_country', country.ident)

    def scope(self, token, stack):
        if token == 'ROOT': return self.root
        if token == 'THIS': return stack[-1]
        if token == 'PREV': return stack[-2] if len(stack) > 1 else None
        if token in ('owner', 'controller'):
            return self.countries.get(getattr(stack[-1], token)) if isinstance(stack[-1], State) else None
        if token.startswith('var:'):
            number = self.value(token[4:], stack)
            if token.endswith('_state'):
                return self.states.get(number) if number == int(number) else None
            return next((country for country in self.countries.values() if country.pointer == number), None)
        raise AssertionError(('Unsupported scope', token))

    def variable(self, name, stack, temporary=False):
        if name.startswith('var:'): name = name[4:]
        array_index = None
        if '^' in name:
            name, index = name.split('^', 1)
            array_index = int(self.value(index, stack))
        if name.startswith('global.'):
            return self.global_arrays if array_index is not None else self.global_vars, name[7:], array_index
        owner = stack[-1]
        if '.' in name:
            scope, name = name.split('.', 1)
            owner = self.scope(scope, stack)
        assert owner is not None, ('Invalid variable owner', name)
        if array_index is not None:
            return owner.arrays, name, array_index
        return self.temp if temporary else owner.variables, name, None

    def value(self, token, stack):
        if isinstance(token, list):
            raise AssertionError(('Unexpected expression', token))
        if token.startswith('var:'): token = token[4:]
        try: return float(token)
        except ValueError: pass
        if token in ('ROOT', 'THIS', 'PREV', 'owner', 'controller'):
            current = self.scope(token, stack)
            return 0 if current is None else current.pointer if isinstance(current, Country) else current.ident
        if token == 'state_population':
            assert isinstance(stack[-1], State)
            return stack[-1].population
        if token == 'state_population_k':
            assert isinstance(stack[-1], State)
            return stack[-1].population / 1000
        if token.endswith('.id'):
            current = self.scope(token[:-3], stack)
            return 0 if current is None else current.pointer if isinstance(current, Country) else current.ident
        if token in self.temp:
            return self.temp[token]
        values, key, index = self.variable(token, stack)
        if index is None: return values.get(key, 0)
        entries = values.get(key, [])
        return entries[index] if 0 <= index < len(entries) else 0

    def assign(self, name, value, stack, temporary=False):
        values, key, index = self.variable(name, stack, temporary)
        if index is None:
            values[key] = value
        else:
            entries = values.setdefault(key, [])
            assert 0 <= index < len(entries), ('Out of bounds ledger write', key, index, len(entries))
            entries[index] = value

    def flag(self, token, stack):
        if '@' not in token: return token
        name, target = token.split('@', 1)
        scope = self.scope(target, stack)
        return name + '@' + str(0 if scope is None else scope.ident)

    def check(self, nodes, stack):
        if any(key == 'var' for key, op, value in nodes):
            left, right = one(nodes, 'var'), one(nodes, 'value')
            mode = next((value for key, op, value in nodes if key == 'compare'), 'equals')
            op = {'equals': '=', 'not_equals': '!=', 'greater_than': '>',
                  'greater_than_or_equals': '>=', 'less_than': '<', 'less_than_or_equals': '<='}[mode]
        else:
            assert len(nodes) == 1
            left, op, right = nodes[0]
        return compare(self.value(left, stack), op, self.value(right, stack))

    @staticmethod
    def branches(nodes, index, value):
        result = [('if', value)]
        while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
            result.append((nodes[index][0], nodes[index][2]))
            index += 1
        return result, index

    def trigger(self, nodes, stack):
        index = 0
        while index < len(nodes):
            key, op, value = nodes[index]
            index += 1
            current = stack[-1]
            if key in self.triggers:
                passed = self.trigger(self.triggers[key], stack) == (value == 'yes')
            elif key in ('ROOT', 'THIS', 'PREV', 'owner', 'controller') or key.startswith('var:'):
                target = self.scope(key, stack)
                passed = target is not None and self.trigger(value, stack + [target])
            elif key in ('AND', 'hidden_trigger', 'custom_trigger_tooltip'):
                passed = self.trigger(value, stack)
            elif key == 'OR': passed = any(self.trigger([node], stack) for node in value)
            elif key == 'NOT': passed = not self.trigger(value, stack)
            elif key == 'if':
                branches, index = self.branches(nodes, index, value)
                passed = True
                for kind, branch in branches:
                    if kind == 'else' or self.trigger(one(branch, 'limit'), stack):
                        passed = self.trigger([node for node in branch if node[0] != 'limit'], stack)
                        break
            elif key in ('set_temp_variable', 'subtract_from_temp_variable', 'multiply_temp_variable', 'add_to_temp_variable'):
                self.effect([(key, op, value)], stack)
                passed = True
            elif key == 'check_variable': passed = self.check(value, stack)
            elif key == 'exists': passed = isinstance(current, Country) and current.exists == (value == 'yes')
            elif key == 'has_war': passed = current.at_war == (value == 'yes')
            elif key == 'has_idea': passed = value in current.ideas
            elif key in ('has_country_flag', 'has_state_flag'): passed = self.flag(value, stack) in current.flags
            elif key == 'has_global_flag': passed = value in self.global_flags
            elif key == 'has_dynamic_modifier': passed = one(value, 'modifier') in current.modifiers
            elif key == 'tag': passed = current.ident == self.scope(value, stack).ident
            elif key == 'state_population': passed = compare(current.population, op, self.value(value, stack))
            elif key in ('is_owned_by', 'is_controlled_by', 'is_core_of'):
                target = self.scope(value, stack)
                if target is None: passed = False
                elif key == 'is_core_of': passed = target.ident in current.cores
                else: passed = getattr(current, 'owner' if key == 'is_owned_by' else 'controller') == target.ident
            elif key in ('any_owned_state', 'any_neighbor_state'):
                selected = [state for state in self.states.values() if state.owner == current.ident] if key == 'any_owned_state' else [self.states[ident] for ident in current.neighbors]
                passed = any(self.trigger(value, stack + [state]) for state in selected)
            elif key == 'is_neighbor_of': passed = self.scope(value, stack).ident in current.neighbors
            elif key == 'is_in_faction_with':
                other = self.scope(value, stack)
                passed = current.faction is not None and current.faction == other.faction
            elif key == 'has_war_with': passed = self.scope(value, stack).ident in current.wars
            elif key == 'always': passed = value == 'yes'
            else: raise AssertionError(('Unmodeled trigger', key, op, value))
            if not passed: return False
        return True

    def effect(self, nodes, stack):
        index = 0
        while index < len(nodes):
            key, op, value = nodes[index]
            index += 1
            current = stack[-1]
            if key in self.effects:
                assert value == 'yes'
                self.trace.append((current.kind, current.ident, key))
                self.effect(self.effects[key], stack)
            elif key in ('ROOT', 'THIS', 'PREV', 'owner', 'controller') or key.startswith('var:'):
                target = self.scope(key, stack)
                if target is not None: self.effect(value, stack + [target])
            elif key == 'if':
                branches, index = self.branches(nodes, index, value)
                for kind, branch in branches:
                    if kind == 'else' or self.trigger(one(branch, 'limit'), stack):
                        self.effect([node for node in branch if node[0] != 'limit'], stack)
                        break
            elif key in ('set_variable', 'set_temp_variable', 'add_to_variable', 'add_to_temp_variable',
                         'subtract_from_variable', 'subtract_from_temp_variable', 'multiply_variable',
                         'multiply_temp_variable', 'divide_variable', 'divide_temp_variable'):
                assert len(value) == 1
                name, operator, amount = value[0]
                number = self.value(amount, stack)
                if key.startswith('set_'): result = number
                else:
                    old = self.value(name, stack)
                    if key.startswith('add_'): result = old + number
                    elif key.startswith('subtract_'): result = old - number
                    elif key.startswith('multiply_'): result = old * number
                    elif key.startswith('divide_'):
                        assert number != 0, ('Division by zero', name)
                        result = old / number
                    else: raise AssertionError(key)
                self.assign(name, result, stack, 'temp_variable' in key)
            elif key in ('clamp_variable', 'clamp_temp_variable'):
                name = one(value, 'var')
                low = next((self.value(v, stack) for k, op, v in value if k == 'min'), -math.inf)
                high = next((self.value(v, stack) for k, op, v in value if k == 'max'), math.inf)
                assert low <= high, ('Invalid clamp interval', name, low, high)
                self.assign(name, max(low, min(high, self.value(name, stack))), stack, 'temp_variable' in key)
            elif key in ('round_variable', 'round_temp_variable'):
                self.assign(value, rounded(self.value(value, stack)), stack, 'temp_variable' in key)
            elif key == 'clear_variable':
                values, name, array_index = self.variable(value, stack)
                assert array_index is None
                values.pop(name, None)
            elif key == 'resize_array':
                name = one(value, 'array')
                size = int(self.value(one(value, 'size'), stack))
                initial = self.value(one(value, 'value'), stack)
                assert size >= 0
                arrays = self.global_arrays if name.startswith('global.') else current.arrays
                name = name.removeprefix('global.')
                entries = arrays.setdefault(name, [])
                arrays[name] = entries[:size] + [initial] * max(0, size - len(entries))
            elif key == 'add_to_array':
                name = one(value, 'array')
                arrays = self.global_arrays if name.startswith('global.') else current.arrays
                arrays.setdefault(name.removeprefix('global.'), []).append(self.value(one(value, 'value'), stack))
            elif key == 'for_each_loop':
                name = one(value, 'array')
                arrays = self.global_arrays if name.startswith('global.') else current.arrays
                array = arrays.get(name.removeprefix('global.'), [])
                index_name, value_name = one(value, 'index'), one(value, 'value')
                for entry_index, entry_value in enumerate(list(array)):
                    self.temp[index_name], self.temp[value_name] = entry_index, entry_value
                    self.effect([node for node in value if node[0] not in ('array', 'index', 'value')], stack)
            elif key == 'random_list':
                # Deterministically select a native weighted branch; fallback
                # target selection remains actual production source control flow.
                choices = [branch for weight, op, branch in value if float(weight) > 0]
                assert choices
                self.effect(choices[self.random_branch % len(choices)], stack)
            elif key in ('every_controlled_state', 'every_owned_state', 'every_state', 'every_country', 'random_country', 'random_owned_controlled_state', 'every_core_state'):
                if key.endswith('country'):
                    selected = [nation for nation in self.countries.values() if nation.exists]
                elif key == 'every_controlled_state': selected = [state for state in self.states.values() if state.controller == current.ident]
                elif key == 'every_owned_state': selected = [state for state in self.states.values() if state.owner == current.ident]
                elif key == 'random_owned_controlled_state': selected = [state for state in self.states.values() if state.owner == current.ident and state.controller == current.ident]
                elif key == 'every_core_state': selected = [state for state in self.states.values() if current.ident in state.cores]
                else: selected = list(self.states.values())
                limit = next((v for k, op, v in value if k == 'limit'), [])
                selected = [target for target in sorted(selected, key=lambda target: target.ident) if self.trigger(limit, stack + [target])]
                if key.startswith('random_'): selected = selected[:1]
                for target in selected:
                    self.effect([node for node in value if node[0] != 'limit'], stack + [target])
            elif key in ('set_country_flag', 'set_state_flag', 'set_global_flag'):
                flag = one(value, 'flag') if isinstance(value, list) else value
                days = next((float(v) for k, op, v in value if k == 'days'), None) if isinstance(value, list) else None
                flags = self.global_flags if key == 'set_global_flag' else current.flags
                flags.add(flag)
                if days is not None: self.flag_days[(key, current.ident, flag)] = days
            elif key in ('clr_country_flag', 'clr_state_flag', 'clr_global_flag'):
                flags = self.global_flags if key == 'clr_global_flag' else current.flags
                flags.discard(self.flag(value, stack))
            elif key == 'add_dynamic_modifier': current.modifiers.add(one(value, 'modifier'))
            elif key == 'add_manpower':
                assert isinstance(current, State), 'Migration changed COUNTRY manpower'
                amount = self.value(value, stack)
                self.manpower_calls.append((current.kind, current.ident, amount))
                current.population += amount
                assert current.population >= 0
            else: raise AssertionError(('Unmodeled effect', key, op, value))

    def run(self, effect, actor=1):
        scope = self.states[actor] if actor in self.states else self.countries[actor]
        self.effect([(effect, '=', 'yes')], [scope])

    def ledger(self, state, origin, stock, fresh=0, age=4, integrated=0, longterm=0):
        self.run('eon_migration_prepare_state_ledger', state)
        actor = self.states[state]
        for name, value in (('eon_refugee_stock', stock), ('eon_refugee_fresh', fresh),
                            ('eon_refugee_age', age), ('eon_refugee_integrated', integrated),
                            ('eon_refugee_longterm', longterm)):
            actor.arrays[name][self.origin_slot(origin)] = value
        self.run('eon_migration_recount_state', state)

    def offer_flow(self, source=101, target=102, origin=1, target_country=2, amount=1000, kind=1):
        self.global_vars.update(eon_migration_source_state=source, eon_migration_target_state=target,
                                eon_migration_origin_country=self.countries[origin].pointer,
                                eon_migration_origin_slot=self.origin_slot(origin),
                                eon_migration_target_country=self.countries[target_country].pointer,
                                eon_migration_amount=amount, eon_migration_kind=kind)

    def origin_slot(self, ident):
        return int(self.countries[ident].variables.get('eon_migration_origin_slot', 0))

    def snapshot(self):
        return deepcopy((self.countries, self.states))


class ActualFlowCores(unittest.TestCase):
    def assert_conserved(self, model, before, amount, source, target):
        self.assertEqual(sum(state.population for state in model.states.values()), sum(before.values()))
        self.assertEqual(model.states[source].population, before[source] - amount)
        self.assertEqual(model.states[target].population, before[target] + amount)
        self.assertEqual(model.manpower_calls[-2:], [('state', source, -amount), ('state', target, amount)])

    def assert_consumed(self, model):
        for name in ('eon_migration_amount', 'eon_migration_debit', 'eon_migration_target_state', 'eon_migration_kind'):
            self.assertNotIn(name, model.global_vars)

    def test_registry_keeps_fractional_tokens_separate_from_integer_slots(self):
        model = Model()
        country = model.countries[1]
        self.assertEqual(model.origin_slot(1), 1)
        self.assertNotEqual(country.pointer, int(country.pointer))
        self.assertEqual(model.global_arrays['eon_migration_origins'][1], country.pointer)
        self.assertEqual(model.global_vars['eon_migration_array_size'], 5)
        registry = deepcopy(model.global_arrays)
        model.run('eon_migration_initialize_country', 1)
        model.run('eon_migration_initialize_country', 1)
        self.assertEqual(model.global_arrays, registry)
        self.assertEqual(model.origin_slot(1), 1)
        model.global_vars['eon_migration_origin_country'] = country.pointer
        self.assertIs(model.scope('var:global.eon_migration_origin_country', [model.root]), country)
        model.global_vars['eon_migration_origin_country'] = int(country.pointer)
        self.assertIsNone(model.scope('var:global.eon_migration_origin_country', [model.root]))

    def test_civil_war_copied_slot_allocates_new_append_only_entry_without_cohort_copy(self):
        model = Model()
        model.ledger(102, 1, 500, age=4)
        registry = deepcopy(model.global_arrays['eon_migration_origins'])
        original = model.countries[1]
        successor = Country(5, variables=deepcopy(original.variables), flags=deepcopy(original.flags),
                            scope_token=original.pointer + .005)
        model.countries[5] = successor
        model.run('eon_migration_initialize_country', 5)
        self.assertEqual(model.origin_slot(1), 1)
        self.assertEqual(model.origin_slot(5), 5)
        self.assertEqual(model.global_arrays['eon_migration_origins'][:5], registry)
        self.assertEqual(model.global_arrays['eon_migration_origins'][5], successor.pointer)
        model.run('eon_migration_prepare_state_ledger', 102)
        self.assertEqual(model.states[102].arrays['eon_refugee_stock'], [0, 500, 0, 0, 0, 0])
        model.run('eon_migration_initialize_country', 5)
        self.assertEqual(model.global_vars['eon_migration_array_size'], 6)

    def test_existing_origin_recovers_overwritten_slot_without_stranding_old_cohorts(self):
        model = Model()
        model.ledger(102, 1, 500, age=4)
        registry = deepcopy(model.global_arrays)
        model.countries[1].variables['eon_migration_origin_slot'] = model.origin_slot(2)
        model.run('eon_migration_initialize_country', 1)
        self.assertEqual(model.origin_slot(1), 1)
        self.assertEqual(model.origin_slot(2), 2)
        self.assertEqual(model.global_arrays, registry)
        self.assertEqual(model.global_vars['eon_migration_array_size'], 5)
        model.run('eon_migration_process_refugee_cohorts', 102)
        self.assertEqual(model.states[102].arrays['eon_refugee_stock'][1], 490)
        self.assertEqual(model.countries[2].variables['eon_refugee_month_returned'], 10)

    def test_new_origin_without_inherited_registration_preserves_legitimate_fund(self):
        model = Model()
        # Ordinary first registration has neither inherited registration signal.
        # A preexisting legitimate balance/receipt is therefore not erased.
        newcomer = Country(5, variables={'eon_refugee_relief_fund': .1,
                                       'eon_refugee_weekly_fund_paid': .01},
                           flags={'eon_refugee_fund_week_consumed'})
        model.countries[5] = newcomer
        model.run('eon_migration_initialize_country', 5)
        self.assertEqual(model.origin_slot(5), 5)
        self.assertEqual(newcomer.variables['eon_refugee_relief_fund'], .1)
        self.assertEqual(newcomer.variables['eon_refugee_weekly_fund_paid'], .01)
        self.assertIn('eon_refugee_fund_week_consumed', newcomer.flags)

    def test_canonical_origin_recovery_preserves_actual_fund_receipt_and_lock(self):
        for overwritten_slot in (0, 2):
            with self.subTest(overwritten_slot=overwritten_slot):
                model = Model()
                model.ledger(102, 1, 500, age=4)
                original = model.countries[1]
                original.variables.update(eon_refugee_relief_fund=.1,
                                          eon_refugee_weekly_fund_paid=.01,
                                          eon_migration_origin_slot=overwritten_slot)
                original.flags.add('eon_refugee_fund_week_consumed')
                registry, states = deepcopy(model.global_arrays), deepcopy(model.states)
                model.run('eon_migration_initialize_country', 1)
                self.assertEqual(model.origin_slot(1), 1)
                self.assertEqual(model.global_vars['eon_migration_array_size'], 5)
                self.assertEqual(model.global_arrays, registry)
                self.assertEqual(model.states, states)
                self.assertEqual(original.variables['eon_refugee_relief_fund'], .1)
                self.assertEqual(original.variables['eon_refugee_weekly_fund_paid'], .01)
                self.assertIn('eon_refugee_fund_week_consumed', original.flags)

    def test_genuinely_new_copied_origin_clears_only_its_restricted_finance(self):
        # Exercise both sides of the production OR, including the cases where
        # native copy_tag may copy variables but omit country flags or vice versa.
        for inherited_flag, inherited_slot in ((True, 1), (True, 0), (False, 1)):
            with self.subTest(initialized=inherited_flag, slot=inherited_slot):
                model = Model()
                model.ledger(102, 1, 500, age=4)
                original = model.countries[1]
                original.variables.update(eon_refugee_relief_fund=.1,
                                          eon_refugee_weekly_fund_paid=.01,
                                          treasury=9.9)
                original.flags.add('eon_refugee_fund_week_consumed')
                successor = Country(5, variables=deepcopy(original.variables),
                                    flags=deepcopy(original.flags),
                                    scope_token=original.pointer + .005)
                successor.variables['eon_migration_origin_slot'] = inherited_slot
                if not inherited_flag:
                    successor.flags.discard('eon_migration_relief_initialized')
                model.countries[5] = successor
                source, states = deepcopy(original), deepcopy(model.states)
                old_map = deepcopy(model.global_arrays['eon_migration_origins'])
                model.run('eon_migration_initialize_country', 5)
                self.assertEqual(original, source)
                self.assertEqual(model.states, states)
                self.assertEqual(model.origin_slot(5), 5)
                self.assertEqual(model.global_vars['eon_migration_array_size'], 6)
                self.assertEqual(model.global_arrays['eon_migration_origins'][:5], old_map)
                self.assertEqual(model.global_arrays['eon_migration_origins'][5], successor.pointer)
                self.assertEqual(successor.variables.get('eon_refugee_relief_fund', 0), 0)
                self.assertEqual(successor.variables.get('eon_refugee_weekly_fund_paid', 0), 0)
                self.assertNotIn('eon_refugee_fund_week_consumed', successor.flags)
                self.assertEqual(sum(country.variables.get('eon_refugee_relief_fund', 0)
                                     for country in model.countries.values()), .1)
                registered = deepcopy((successor, model.global_arrays, model.global_vars))
                model.run('eon_migration_initialize_country', 5)
                model.run('eon_migration_register_country', 5)
                self.assertEqual((successor, model.global_arrays, model.global_vars), registered)

    def test_registered_new_origin_retains_new_credit_and_weekly_receipt(self):
        model = Model()
        original = model.countries[1]
        successor = Country(5, variables=deepcopy(original.variables),
                            flags=deepcopy(original.flags), scope_token=original.pointer + .005)
        model.countries[5] = successor
        model.run('eon_migration_initialize_country', 5)
        # Seed a real credit after registration; the aid interpreter separately
        # verifies donor debit/consent. Registration must not erase new money.
        successor.variables.update(eon_refugee_relief_fund=.2,
                                   eon_refugee_weekly_fund_paid=.015)
        successor.flags.add('eon_refugee_fund_week_consumed')
        registered = deepcopy((successor, model.global_arrays, model.global_vars))
        model.run('eon_migration_initialize_country', 5)
        model.run('eon_migration_register_country', 5)
        self.assertEqual((successor, model.global_arrays, model.global_vars), registered)

    def test_monthly_phases_resolve_full_origin_token_then_voluntary_return_conserves(self):
        model = Model()
        model.ledger(102, 1, 10000, fresh=1000, age=2)
        before = {ident: state.population for ident, state in model.states.items()}
        phases = [node for node in model.effects['eon_migration_monthly_world_update'] if node[0] == 'every_state']
        model.effect(phases, [model.root])
        self.assert_conserved(model, before, 200, 102, 101)
        self.assertEqual(model.states[102].arrays['eon_refugee_stock'][1], 9800)
        self.assertEqual(model.states[102].arrays['eon_refugee_fresh'][1], 0)
        self.assertEqual(model.states[102].arrays['eon_refugee_age'][1], 3)
        self.assertEqual(model.countries[2].variables['eon_refugee_month_returned'], 200)
        self.assertEqual(model.global_vars['eon_migration_origin_country'], model.countries[1].pointer)
        self.assertEqual(model.global_arrays['eon_migration_origins'][1], model.countries[1].pointer)

    def test_dead_origin_registry_entry_and_cohort_survive_without_population_transfer(self):
        model = Model()
        model.ledger(102, 1, 10000, age=4)
        model.countries[1].exists = False
        registry = deepcopy(model.global_arrays)
        before = {ident: state.population for ident, state in model.states.items()}
        model.run('eon_migration_process_refugee_cohorts', 102)
        self.assertEqual({ident: state.population for ident, state in model.states.items()}, before)
        self.assertEqual(model.states[102].arrays['eon_refugee_stock'][1], 10000)
        self.assertEqual(model.global_arrays, registry)
        self.assertEqual(model.manpower_calls, [])

    def test_new_refugee_exact_debit_credit_cohort_fresh_and_age(self):
        model = Model()
        before = {ident: state.population for ident, state in model.states.items()}
        model.offer_flow()
        model.run('eon_migration_move_population')
        self.assert_conserved(model, before, 1000, 101, 102)
        target = model.states[102]
        self.assertEqual(target.arrays['eon_refugee_stock'][1], 1000)
        self.assertEqual(target.arrays['eon_refugee_fresh'][1], 1000)
        self.assertEqual(target.arrays['eon_refugee_age'][1], 0)
        self.assertEqual(target.arrays['eon_refugee_integrated'][1], 0)
        self.assertEqual(model.countries[1].variables['eon_migration_month_out'], 1000)
        self.assertEqual(model.countries[2].variables['eon_refugee_month_arrived'], 1000)
        self.assert_consumed(model)
        once = model.snapshot()
        model.run('eon_migration_move_population')
        self.assertEqual(model.snapshot(), once)

    def test_arrival_dilutes_existing_age_preserves_other_origins_and_grows_array(self):
        model = Model()
        model.ledger(102, 1, 2000, age=9, integrated=1200)
        model.ledger(102, 3, 3000, age=6, integrated=2000)
        model.global_vars['eon_migration_array_size'] = 8
        model.offer_flow(amount=50)
        model.run('eon_migration_move_population')
        target = model.states[102]
        self.assertEqual(target.arrays['eon_refugee_stock'][1], 2050)
        self.assertAlmostEqual(target.arrays['eon_refugee_age'][1], 2000 * 9 / 2050)
        self.assertEqual(target.arrays['eon_refugee_integrated'][1], 1200)
        self.assertEqual(target.arrays['eon_refugee_stock'][3], 3000)
        self.assertEqual(target.arrays['eon_refugee_age'][3], 6)
        self.assertEqual(len(target.arrays['eon_refugee_stock']), 8)

    def test_large_new_arrival_cannot_inherit_old_cohort_settlement_age(self):
        model = Model()
        model.ledger(102, 1, 100, age=60, integrated=80, longterm=50)
        model.offer_flow(amount=9900)
        model.run('eon_migration_move_population')
        cohort = model.states[102].arrays
        self.assertAlmostEqual(cohort['eon_refugee_age'][1], .6)
        self.assertEqual(cohort['eon_refugee_longterm'][1], 50)
        self.assertEqual(cohort['eon_refugee_integrated'][1], 80)
        self.assertEqual(cohort['eon_refugee_fresh'][1], 9900)
        once = model.snapshot()
        model.run('eon_migration_process_refugee_cohorts', 102)
        self.assertEqual(model.snapshot(), once)

    def test_return_debits_source_cohort_and_does_not_create_refugees_at_home(self):
        model = Model()
        model.ledger(102, 1, 2000, fresh=100, age=6, integrated=1900)
        before = {ident: state.population for ident, state in model.states.items()}
        model.offer_flow(source=102, target=101, origin=1, target_country=1, amount=500, kind=2)
        model.run('eon_migration_move_population', 102)
        self.assert_conserved(model, before, 500, 102, 101)
        self.assertEqual(model.states[102].arrays['eon_refugee_stock'][1], 1500)
        self.assertEqual(model.states[102].arrays['eon_refugee_integrated'][1], 1400)
        self.assertEqual(model.states[102].arrays['eon_refugee_fresh'][1], 100)
        self.assertEqual(model.states[101].arrays.get('eon_refugee_stock', []), [])
        self.assertEqual(model.countries[2].variables['eon_refugee_month_returned'], 500)
        self.assert_consumed(model)

    def test_returns_and_onward_exclude_fresh_and_longterm_at_exact_boundary(self):
        for kind, target, target_country in ((2, 101, 1), (3, 103, 3)):
            for amount in (1200, 1201):
                with self.subTest(kind=kind, amount=amount):
                    model = Model()
                    model.ledger(102, 1, 2000, fresh=100, age=60, integrated=1800, longterm=700)
                    model.offer_flow(source=102, target=target, origin=1,
                                     target_country=target_country, amount=amount, kind=kind)
                    before = model.snapshot()
                    population = {ident: state.population for ident, state in model.states.items()}
                    model.run('eon_migration_move_population', 102)
                    if amount == 1201:
                        self.assertEqual(model.snapshot(), before)
                        self.assertEqual(model.manpower_calls, [])
                    else:
                        self.assert_conserved(model, population, amount, 102, target)
                        cohort = model.states[102].arrays
                        self.assertEqual(cohort['eon_refugee_stock'][1], 800)
                        self.assertEqual(cohort['eon_refugee_fresh'][1], 100)
                        self.assertEqual(cohort['eon_refugee_longterm'][1], 700)
                        self.assertEqual(cohort['eon_refugee_integrated'][1], 700)
                        if kind == 3:
                            received = model.states[target].arrays
                            self.assertEqual(received['eon_refugee_stock'][1], 1200)
                            self.assertEqual(received['eon_refugee_longterm'][1], 0)
                            self.assertEqual(received['eon_refugee_integrated'][1], 0)
                    self.assert_consumed(model)

    def test_onward_debits_same_origin_and_only_target_receives_fresh_cohort(self):
        model = Model()
        model.ledger(102, 1, 2000, fresh=100, age=6, integrated=1700)
        before = {ident: state.population for ident, state in model.states.items()}
        model.offer_flow(source=102, target=103, origin=1, target_country=3, amount=500, kind=3)
        model.run('eon_migration_move_population', 102)
        self.assert_conserved(model, before, 500, 102, 103)
        self.assertEqual(model.states[102].arrays['eon_refugee_stock'][1], 1500)
        self.assertEqual(model.states[103].arrays['eon_refugee_stock'][1], 500)
        self.assertEqual(model.states[103].arrays['eon_refugee_fresh'][1], 500)
        self.assertEqual(model.states[103].arrays['eon_refugee_age'][1], 0)
        self.assertEqual(sum(state.arrays.get('eon_refugee_stock', [0, 0])[1] for state in model.states.values()), 2000)
        self.assert_consumed(model)

    def test_workers_have_separate_receipt_no_refugee_copy(self):
        model = Model()
        before = {ident: state.population for ident, state in model.states.items()}
        model.offer_flow(amount=250, kind=4)
        model.run('eon_migration_move_population')
        self.assert_conserved(model, before, 250, 101, 102)
        self.assertEqual(model.states[102].arrays['eon_labor_stock'][1], 250)
        self.assertEqual(sum(model.states[102].arrays['eon_refugee_stock']), 0)
        self.assertEqual(model.countries[2].variables['eon_labor_month_arrived'], 250)
        self.assertNotIn('eon_refugee_month_arrived', model.countries[2].variables)

    def test_actual_refugee_departures_partial_full_closed_and_no_host_routes(self):
        for route in ('partial_capacity', 'full_capacity', 'closed_admission', 'no_available_route'):
            for branch in (0, 1):
                with self.subTest(route=route, branch=branch):
                    model = Model()
                    model.random_branch = branch
                    model.states[101].population = 2000000
                    model.states[101].variables['damaged_building_level@infrastructure'] = .5
                    model.countries[1].at_war = True
                    # Only country2 is willing; no fixed national role assignment.
                    for nation in model.countries.values():
                        nation.flags.add('eon_migration_relief_initialized')
                        nation.variables['eon_refugee_policy'] = 0
                    model.countries[2].variables['eon_refugee_policy'] = 1
                    model.countries[2].neighbors.add(1)
                    existing_stock = 20000 if route == 'full_capacity' else 19000
                    model.ledger(102, 3, existing_stock)
                    if route == 'closed_admission': model.countries[2].variables['eon_refugee_policy'] = 0
                    elif route == 'no_available_route': model.countries[2].neighbors.clear()
                    model.run('eon_migration_refresh_country', 2)
                    before = {ident: state.population for ident, state in model.states.items()}
                    model.run('eon_migration_refugee_departures', 1)
                    moved = 1000 if route == 'partial_capacity' else 0
                    self.assertEqual(model.states[101].population, before[101] - moved)
                    self.assertEqual(model.states[102].population, before[102] + moved)
                    self.assertEqual(sum(state.population for state in model.states.values()), sum(before.values()))
                    self.assertEqual(model.states[102].arrays['eon_refugee_stock'][1], moved)
                    self.assertEqual(model.states[102].arrays['eon_refugee_stock'][3], existing_stock)
                    self.assertEqual(model.countries[1].variables['eon_refugee_month_unplaced'], 20000 - moved)
                    self.assertEqual(model.countries[2].variables.get('eon_refugee_month_arrived', 0), moved)
                    self.assertEqual(model.temp['eon_migration_moved_people'], moved)

    def test_failed_native_flow_receipt_reports_zero_and_stale_receipt_cannot_leak(self):
        model = Model()
        model.temp['eon_migration_moved_people'] = 999
        model.offer_flow(kind=5)
        before = model.snapshot()
        model.run('eon_migration_move_population')
        self.assertEqual(model.temp['eon_migration_moved_people'], 0)
        self.assertEqual(model.snapshot(), before)
        model.offer_flow(amount=500)
        model.run('eon_migration_move_population')
        self.assertEqual(model.temp['eon_migration_moved_people'], 500)
        model.run('eon_migration_move_population')
        self.assertEqual(model.temp['eon_migration_moved_people'], 0)

    def test_actual_labor_departures_requires_reciprocal_treaty_peace_and_vacancies(self):
        for blocked in (None, 'closed_exporter', 'closed_importer', 'war_exporter', 'war_importer',
                        'missing_reciprocal_flag', 'no_vacancies'):
            with self.subTest(blocked=blocked):
                model = Model()
                model.countries[2].variables['migrants_cut'] = -.05
                model.countries[1].variables['average_worker_fulfillment'] = .5
                model.countries[2].flags.add('migration_agreement_migrants_cut@1')
                model.countries[1].flags.add('migration_agreement_migrants_add@2')
                if blocked == 'closed_exporter': model.countries[2].ideas.add('closed_borders')
                elif blocked == 'closed_importer': model.countries[1].ideas.add('closed_borders')
                elif blocked == 'war_exporter': model.countries[2].at_war = True
                elif blocked == 'war_importer': model.countries[1].at_war = True
                elif blocked == 'missing_reciprocal_flag': model.countries[2].flags.clear()
                elif blocked == 'no_vacancies': model.countries[1].variables['average_worker_fulfillment'] = 1
                before = model.snapshot()
                population = {ident: state.population for ident, state in model.states.items()}
                model.run('eon_migration_labor_departures', 2)
                if blocked:
                    self.assertEqual(model.snapshot(), before)
                    self.assertEqual(model.manpower_calls, [])
                else:
                    self.assert_conserved(model, population, 5, 102, 101)
                    self.assertEqual(model.countries[1].variables['eon_labor_month_arrived'], 5)
                    self.assertEqual(model.states[101].arrays['eon_labor_stock'][2], 5)
                    self.assertEqual(sum(model.states[101].arrays['eon_refugee_stock']), 0)

    def test_invalid_flows_are_atomic_no_population_or_cohort_mutation(self):
        invalids = ('same_state', 'wrong_target_country', 'wrong_target_owner', 'wrong_target_controller',
                    'target_not_core', 'dead_target', 'missing_target', 'missing_source', 'missing_amount',
                    'zero_amount', 'negative_amount', 'source_exhausted', 'invalid_kind', 'missing_kind',
                    'missing_origin', 'truncated_origin_token', 'return_not_home', 'new_refugee_wrong_origin', 'stock_short', 'fresh_only')
        for invalid in invalids:
            with self.subTest(invalid=invalid):
                model = Model()
                model.ledger(102, 1, 500, fresh=100, age=4)
                model.offer_flow()
                if invalid == 'same_state': model.global_vars['eon_migration_target_state'] = 101
                elif invalid == 'wrong_target_country': model.global_vars['eon_migration_target_country'] = model.countries[3].pointer
                elif invalid == 'wrong_target_owner': model.states[102].owner = 3
                elif invalid == 'wrong_target_controller': model.states[102].controller = 3
                elif invalid == 'target_not_core': model.states[102].cores.clear()
                elif invalid == 'dead_target': model.countries[2].exists = False
                elif invalid == 'missing_target': model.global_vars.pop('eon_migration_target_state')
                elif invalid == 'missing_source': model.global_vars.pop('eon_migration_source_state')
                elif invalid == 'missing_amount': model.global_vars.pop('eon_migration_amount')
                elif invalid == 'zero_amount': model.global_vars['eon_migration_amount'] = 0
                elif invalid == 'negative_amount': model.global_vars['eon_migration_amount'] = -50
                elif invalid == 'source_exhausted': model.global_vars['eon_migration_amount'] = 100000
                elif invalid == 'invalid_kind': model.global_vars['eon_migration_kind'] = 5
                elif invalid == 'missing_kind': model.global_vars.pop('eon_migration_kind')
                elif invalid == 'missing_origin': model.global_vars.pop('eon_migration_origin_country')
                elif invalid == 'truncated_origin_token': model.global_vars['eon_migration_origin_country'] = int(model.countries[1].pointer)
                elif invalid == 'return_not_home': model.global_vars['eon_migration_kind'] = 2
                elif invalid == 'new_refugee_wrong_origin': model.global_vars['eon_migration_origin_country'] = model.countries[3].pointer
                elif invalid == 'stock_short': model.offer_flow(source=102, target=101, target_country=1, amount=501, kind=2)
                elif invalid == 'fresh_only': model.offer_flow(source=102, target=101, target_country=1, amount=401, kind=2)
                before = model.snapshot()
                model.run('eon_migration_move_population')
                self.assertEqual(model.snapshot(), before)
                self.assertEqual(model.manpower_calls, [])
                self.assert_consumed(model)

    def test_state_control_change_reassigns_totals_without_copying_cohorts(self):
        model = Model()
        model.ledger(102, 1, 3000, integrated=1000)
        model.run('eon_migration_refresh_country', 2)
        ledger = deepcopy(model.states[102].arrays)
        model.states[102].owner = model.states[102].controller = 3
        model.run('eon_migration_refresh_country', 2)
        model.run('eon_migration_refresh_country', 3)
        self.assertEqual(model.countries[2].variables['eon_refugees_hosted'], 0)
        self.assertEqual(model.countries[3].variables['eon_refugees_hosted'], 3000)
        self.assertEqual(model.states[102].arrays, ledger)

    def test_recount_does_not_overwrite_outer_origin_loop_index(self):
        model = Model()
        model.ledger(102, 1, 10000, age=4, integrated=0)
        model.ledger(102, 3, 0, age=0, integrated=0)
        model.countries[2].variables['gdp_per_capita'] = 20
        model.run('eon_migration_process_refugee_cohorts', 102)
        # Return = 10000*.02*.5; integration applies to the remaining origin 1 cohort.
        self.assertEqual(model.states[102].arrays['eon_refugee_stock'][1], 9900)
        self.assertEqual(model.states[102].arrays['eon_refugee_integrated'][1], 792)
        self.assertEqual(model.states[102].arrays['eon_refugee_integrated'][3], 0)

    def test_safe_return_requires_peace_time_control_and_low_damage(self):
        for invalid in ('war', 'dead_origin', 'too_soon', 'lost_control', 'damaged_home'):
            with self.subTest(invalid=invalid):
                model = Model()
                model.ledger(102, 1, 10000, age=4)
                if invalid == 'war': model.countries[1].at_war = True
                elif invalid == 'dead_origin': model.countries[1].exists = False
                elif invalid == 'too_soon': model.countries[1].variables['eon_migration_peace_months'] = 2
                elif invalid == 'lost_control': model.countries[1].variables['eon_migration_home_control_ratio'] = .25
                elif invalid == 'damaged_home': model.states[101].variables['damaged_building_level@infrastructure'] = .25
                model.run('eon_migration_process_refugee_cohorts', 102)
                self.assertEqual(model.manpower_calls, [])
                self.assertEqual(model.states[102].arrays['eon_refugee_stock'][1], 10000)

    def test_fresh_arrivals_cannot_be_returned_or_integrated_in_same_month(self):
        model = Model()
        model.ledger(102, 1, 10000, fresh=10000, age=5)
        model.run('eon_migration_process_refugee_cohorts', 102)
        self.assertEqual(model.manpower_calls, [])
        self.assertEqual(model.states[102].arrays['eon_refugee_integrated'][1], 0)

    def test_longterm_only_cohort_cannot_return_or_relocate(self):
        model = Model()
        model.ledger(102, 1, 10000, fresh=1000, age=60, integrated=9000, longterm=9000)
        model.countries[2].variables['eon_refugee_policy'] = 0
        model.countries[3].neighbors.add(2)
        model.countries[3].variables['eon_refugee_policy'] = 2
        model.countries[3].flags.add('eon_migration_relief_initialized')
        model.run('eon_migration_refresh_country', 3)
        before = model.snapshot()
        model.run('eon_migration_process_refugee_cohorts', 102)
        self.assertEqual(model.manpower_calls, [])
        self.assertEqual(model.snapshot(), before)

    def test_longterm_calibration_excludes_fresh_and_counts_as_integrated(self):
        model = Model()
        model.countries[1].at_war = True  # No voluntary return while home is unsafe.
        model.ledger(102, 1, 10000, fresh=1000, age=60, integrated=2000, longterm=1000)
        model.run('eon_migration_process_refugee_cohorts', 102)
        cohort = model.states[102].arrays
        self.assertEqual(cohort['eon_refugee_stock'][1], 10000)
        self.assertEqual(cohort['eon_refugee_fresh'][1], 1000)
        self.assertEqual(cohort['eon_refugee_longterm'][1], 1160)  # (10000-1000-1000)*2%.
        self.assertEqual(cohort['eon_refugee_integrated'][1], 2560)  # (10000-2000-1000)*8%.
        self.assertLessEqual(cohort['eon_refugee_longterm'][1], cohort['eon_refugee_integrated'][1])
        self.assertLessEqual(cohort['eon_refugee_integrated'][1], 9000)
        self.assertEqual(model.states[102].variables['eon_refugees_longterm_total'], 1160)
        self.assertEqual(model.manpower_calls, [])

    def test_closed_borders_block_longterm_calibration_without_removing_residents(self):
        model = Model()
        model.countries[1].at_war = True
        model.countries[2].ideas.add('closed_borders')
        model.ledger(102, 1, 10000, age=60, integrated=2000, longterm=1000)
        model.run('eon_migration_process_refugee_cohorts', 102)
        self.assertEqual(model.states[102].arrays['eon_refugee_stock'][1], 10000)
        self.assertEqual(model.states[102].arrays['eon_refugee_longterm'][1], 1000)
        self.assertEqual(model.manpower_calls, [])

    def test_weekly_fund_consumption_exact_once_and_partial_shortfall(self):
        for fund in (0, .0002, .1):
            with self.subTest(fund=fund):
                model = Model()
                model.ledger(102, 1, 10000)
                model.countries[2].variables['eon_refugee_relief_fund'] = fund
                model.run('eon_migration_relief_weekly', 2)
                cost = model.countries[2].variables['eon_refugee_weekly_cost']
                paid = min(fund, cost)
                self.assertAlmostEqual(model.countries[2].variables['eon_refugee_weekly_fund_paid'], paid)
                self.assertAlmostEqual(model.countries[2].variables['eon_refugee_relief_fund'], fund - paid)
                self.assertAlmostEqual(model.countries[2].variables['eon_refugee_weekly_net_cost'], cost - paid)
                once = model.snapshot()
                model.run('eon_migration_relief_weekly', 2)
                self.assertEqual(model.snapshot(), once)
                self.assertEqual(model.flag_days[('set_country_flag', 2, 'eon_refugee_fund_week_consumed')], 6)
                model.countries[2].flags.discard('eon_refugee_fund_week_consumed')
                model.run('eon_migration_relief_weekly', 2)
                self.assertGreaterEqual(model.countries[2].variables['eon_refugee_relief_fund'], 0)

    def test_zero_population_ratio_costs_and_display_remain_finite(self):
        model = Model()
        model.countries[2].variables['population_total_m'] = 0
        model.countries[2].variables.update(eon_migration_month_in=0, eon_migration_month_out=0)
        model.run('eon_migration_refresh_country', 2)
        model.run('eon_migration_display_rates', 2)
        values = model.countries[2].variables
        self.assertEqual(values['eon_refugee_capacity'], 1000)
        self.assertEqual(values['eon_refugee_service_pressure'], 0)
        self.assertEqual(values['net_immigration_rate'], 0)
        self.assertTrue(all(math.isfinite(value) for value in values.values()))

    def test_weekly_cost_tapers_with_integration_and_excludes_longterm(self):
        for integrated, longterm, effective in ((0, 0, 10000), (6000, 2000, 5000), (10000, 10000, 0)):
            with self.subTest(integrated=integrated, longterm=longterm):
                model = Model()
                model.ledger(102, 1, 10000, integrated=integrated, longterm=longterm)
                model.run('eon_migration_refresh_country', 2)
                country = model.countries[2].variables
                self.assertEqual(country['eon_refugees_hosted'], 10000)
                self.assertEqual(country['eon_refugees_integrated'], integrated)
                self.assertEqual(country['eon_refugees_longterm'], longterm)
                self.assertAlmostEqual(country['eon_refugee_weekly_cost'], effective * .05 / 1000000 * 1.5)
                self.assertAlmostEqual(country['eon_refugee_workforce_delay_m'], (10000 - integrated) * .6 / 1000000)

    def test_domestic_relief_is_controlled_damaged_home_need_and_spends_fund(self):
        model = Model()
        model.countries[2].at_war = True
        model.ledger(102, 1, 10000, integrated=10000, longterm=10000)
        model.states[102].arrays['eon_labor_stock'][1] = 500
        model.run('eon_migration_recount_state', 102)
        model.states[102].variables['damaged_building_level@infrastructure'] = .26
        for ident, owner, controller, cores in ((105, 2, 3, {2}), (106, 2, 2, {3}), (107, 3, 2, {2})):
            model.states[ident] = State(ident, 100000, owner, controller, cores,
                                      variables={'damaged_building_level@infrastructure': .9})
        model.countries[2].variables['eon_refugee_relief_fund'] = .01
        before = {ident: state.population for ident, state in model.states.items()}
        ledger = deepcopy(model.states[102].arrays)
        model.run('eon_migration_relief_weekly', 2)
        country = model.countries[2].variables
        self.assertEqual(country['eon_civilian_relief_need'], 895)  # 1% of nonlocal-excluded home population.
        self.assertAlmostEqual(country['eon_refugee_weekly_cost'], 895 * .05 / 1000000 * 1.5)
        self.assertEqual(country['eon_refugee_weekly_net_cost'], 0)
        self.assertAlmostEqual(country['eon_refugee_relief_fund'], .01 - country['eon_refugee_weekly_cost'])
        self.assertEqual({ident: state.population for ident, state in model.states.items()}, before)
        self.assertEqual(model.states[102].arrays, ledger)
        self.assertEqual(model.manpower_calls, [])
        model.countries[2].at_war = False
        model.run('eon_migration_refresh_country', 2)
        self.assertEqual(country['eon_civilian_relief_need'], 0)
        self.assertEqual(country['eon_refugee_weekly_cost'], 0)

    def test_source_monthly_phase_order_and_global_fresh_clear(self):
        source = Model().effects['eon_migration_monthly_world_update']
        state_phases = [(index, value) for index, (key, op, value) in enumerate(source) if key == 'every_state']
        self.assertEqual(len(state_phases), 2)
        first = state_phases[0][1]
        loop = one(first, 'for_each_loop')
        self.assertEqual(one(loop, 'array'), 'eon_refugee_stock')
        self.assertIn(('set_variable', '=', [('eon_refugee_fresh^eon_origin_index', '=', '0')]), loop)
        self.assertIn(('eon_migration_process_refugee_cohorts', '=', 'yes'), state_phases[1][1])
        country_phases = [(index, value) for index, (key, op, value) in enumerate(source) if key == 'every_country']
        refugee_arrivals = next(index for index, nodes in country_phases if ('eon_migration_refugee_departures', '=', 'yes') in nodes)
        labor_arrivals = next(index for index, nodes in country_phases if ('eon_migration_labor_departures', '=', 'yes') in nodes)
        self.assertLess(state_phases[0][0], state_phases[1][0])
        self.assertLess(state_phases[1][0], refugee_arrivals)
        self.assertLess(refugee_arrivals, labor_arrivals)
        self.assertEqual(source[-1], ('eon_migration_clear_flow_scratch', '=', 'yes'))
        model = Model()
        model.ledger(102, 1, 200, fresh=200, age=0)
        model.ledger(103, 1, 300, fresh=300, age=0)
        model.effect([source[state_phases[0][0]]], [model.root])
        for state in (102, 103):
            self.assertEqual(model.states[state].arrays['eon_refugee_fresh'][1], 0)
            self.assertEqual(model.states[state].arrays['eon_refugee_age'][1], 1)

    def test_source_monthly_27_day_world_lock_and_scratch_clear(self):
        model = Model()
        pulse = model.effects['eon_migration_monthly_pulse']
        condition = one(one(pulse, 'if'), 'limit')
        self.assertIn(('NOT', '=', [('has_global_flag', '=', 'eon_migration_month_consumed')]), condition)
        lock = one(one(pulse, 'if'), 'set_global_flag')
        self.assertEqual(one(lock, 'days'), '27')
        self.assertIn(('eon_migration_monthly_world_update', '=', 'yes'), one(pulse, 'if'))
        clear = model.effects['eon_migration_clear_flow_scratch']
        expected = {'amount', 'debit', 'source_state', 'target_state', 'origin_country', 'origin_slot', 'target_country', 'previous_host', 'return_gdpc', 'kind'}
        self.assertEqual({value.removeprefix('global.eon_migration_') for key, op, value in clear}, expected)
        for suffix in expected: model.global_vars['eon_migration_' + suffix] = 77
        model.run('eon_migration_clear_flow_scratch')
        self.assertEqual(model.global_vars, {'eon_migration_array_size': 5})

    def test_source_only_state_add_manpower_and_no_deferred_population_effects(self):
        model = Model()
        def walk(nodes, scopes=()):
            for key, op, value in nodes:
                if key == 'add_manpower':
                    self.assertIn(scopes[-1], ('var:global.eon_migration_source_state', 'var:global.eon_migration_target_state'))
                if key in ('country_event', 'news_event', 'hidden_effect'): raise AssertionError(('Deferred population operation', key))
                if isinstance(value, list):
                    walk(value, scopes + (key,) if key.startswith('var:') else scopes)
        walk(model.effects['eon_migration_move_population'])
        # Recount's private iterator must not overwrite process_refugee_cohorts.
        for key, op, value in model.effects['eon_migration_recount_state']:
            if key == 'for_each_loop': self.assertNotEqual(one(value, 'index'), 'eon_origin_index')


if __name__ == '__main__':
    unittest.main(verbosity=2)
