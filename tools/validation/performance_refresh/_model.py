"""Actual-source state aggregation model; explicit unchanged GDP/finance boundaries.
Unknown visited commands/triggers fail closed. This is not the native engine.
"""
from pathlib import Path
import copy, random, sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/validation/diplomacy_package_03"))
from _support import ast, one, compare

class Refresh:
    def __init__(self, helpers, states, country=1, root=9, fixture=None):
        self.helpers, self.states, self.country, self.root = helpers, copy.deepcopy(states), country, root
        self.variables = {country: copy.deepcopy(fixture or {})}
        self.variables.setdefault(root, {'wrong_root_sentinel': 999})
        self.temp, self.dynamic = {}, set()
        self.current, self.previous = country, None
        self.visits, self.queries, self.boundaries, self.delegates = [], [], [], []
        self.global_vars = {'average_world_productivity': 1000}
        self.modifiers = {
            country: {'consumer_goods_expected_value': .2, 'consumer_goods_factor': .1,
                      'productivity_growth_modifier': .08, 'country_productivity_growth_modifier': .1},
            root: {},
        }
        self.resources = dict.fromkeys(('oil', 'steel', 'chromium', 'rubber', 'aluminium', 'tungsten'), 3)
        for st, facts in self.states.items():
            self.variables[st] = copy.deepcopy(facts.get('vars', {}))
            self.modifiers[st] = copy.deepcopy(facts.get('modifiers', {}))
        self.native = {
            'calculate_gdp', 'eon_energy_delivery_daily_tick',
            'inflation_laws_update', 'calculate_visegrad_gdp', 'calculate_int_investments_rate',
            'calculate_resource_sale_rate', 'calculate_tax_gain', 'calculate_additional_income_rate',
            'expense_modifier_calculations', 'update_military_rate', 'update_bureaucracy_rate',
            'update_police_rate', 'update_education_rate', 'update_health_rate', 'update_social_rate',
            'calculate_interest_rate', 'calculate_additional_expense_rate', 'calculate_inflation_rate',
            'update_economic_cycle_cost', 'update_cyber_cost',
            'update_employment_productivity_output_dynamic_modifier', 'calculate_productivity_population_buff',
            'calculate_migration_mechanic_values', 'calculate_ai_taxes_desire', 'update_display',
            'update_money_dirty_variable', 'update_energy_dirty_variable',
        }

    def resolve(self, token):
        if token.startswith('PREV.'):
            assert self.previous is not None, 'Missing PREV'
            return self.previous, token[5:]
        if token.startswith('THIS.'): return self.current, token[5:]
        if token.startswith('ROOT.'): return self.root, token[5:]
        return self.current, token

    def value(self, token):
        if isinstance(token, list):
            result = None
            for k, op, v in token:
                assert op == '='
                if k == 'value': result = self.value(v)
                elif k == 'add': result += self.value(v)
                elif k == 'multiply': result *= self.value(v)
                elif k == 'clamp':
                    for ck, cop, cv in v:
                        assert cop == '=' and ck in ('min', 'max')
                        result = max(result, self.value(cv)) if ck == 'min' else min(result, self.value(cv))
                else: raise AssertionError(('Unknown expression', k))
            assert result is not None
            return result
        try: return float(token)
        except (ValueError, TypeError): pass
        if token == 'THIS.id': return self.current
        if token.startswith('global.'): return self.global_vars.get(token[7:], 0)
        scope, token = self.resolve(token)
        if token.startswith('modifier@'): return self.modifiers[scope].get(token[9:], 0)
        if token.startswith('resource_produced@'):
            assert scope == self.country
            self.queries.append((scope, token))
            return self.resources.get(token[18:], 0)
        if token.startswith(('building_level@', 'damaged_building_level@', 'buildling_level@')):
            assert scope in self.states, ('Country building query', scope, token)
            self.queries.append((scope, token))
            kind, name = token.split('@', 1)
            # Preserve inherited misspelling; exact native result is an explicit input.
            if kind == 'buildling_level': return self.states[scope].get('typo_anti_air_value', 0)
            return self.states[scope].get('damage' if kind == 'damaged_building_level' else 'buildings', {}).get(name, 0)
        if token == 'state_population_k':
            assert scope in self.states
            return self.states[scope].get('population', 0)
        return self.temp.get((scope, token), self.variables[scope].get(token, 0))

    def condition(self, nodes):
        for k, op, v in nodes:
            if k in ('AND', 'OR', 'NOT'):
                parts = [self.condition([n]) for n in v]
                ok = all(parts) if k == 'AND' else any(parts) if k == 'OR' else not all(parts)
            elif k == 'check_variable':
                assert len(v) == 1
                vk, vo, vv = v[0]
                ok = compare(self.value(vk), vo, self.value(vv))
            elif k == 'always': ok = v == 'yes'
            elif k == 'has_dynamic_modifier': ok = (self.current, one(v, 'modifier')) in self.dynamic
            elif k == 'has_railway_level':
                assert int(self.value(one(v, 'state'))) == self.current
                ok = self.states[self.current].get('railway', 0) >= int(one(v, 'level'))
            elif k == 'any_province_building_level':
                building = one(v, 'building')
                nk, no, nv = next(n for n in v if n[0] == 'level')
                ok = any(compare(level, no, float(nv)) for level in self.states[self.current].get('province_buildings', {}).get(building, []))
            elif k == 'has_state_flag': ok = v in self.states[self.current].get('flags', set())
            elif k == 'is_coastal': ok = self.states[self.current].get('coastal', False) == (v == 'yes')
            elif k == 'is_ai': ok = self.variables[self.current].get('fixture_ai', False) == (v == 'yes')
            elif k == 'is_debug': ok = False
            elif k == 'any_owned_state': ok = bool(self.states) and self.condition(v)
            elif k == 'capital_scope': ok = True # explicit valid-capital fixture, so repair stays unreachable
            else: raise AssertionError(('Unknown visited trigger', k, op, v))
            if not ok: return False
        return True

    def variable(self, kind, nodes):
        if any(k == 'var' for k, op, v in nodes):
            target, amount = one(nodes, 'var'), one(nodes, 'value')
        else:
            assert len(nodes) == 1
            target, op, amount = nodes[0]
            assert op == '='
        scope, key = self.resolve(target)
        temp = 'temp' in kind
        target_dict = self.temp if temp else self.variables[scope]
        target_key = (scope, key) if temp else key
        val = self.value(amount)
        before = target_dict.get(target_key, 0)
        if kind.startswith('set_'): target_dict[target_key] = val
        elif kind.startswith('add_'): target_dict[target_key] = before + val
        elif kind.startswith('multiply_'): target_dict[target_key] = before * val
        elif kind.startswith('divide_'):
            assert val != 0, ('Unmodeled zero division', kind, target)
            target_dict[target_key] = before / val
        else: raise AssertionError(('Unknown variable operation', kind))

    def execute(self, nodes):
        branch = None
        for k, op, v in nodes:
            if k in ('if', 'else_if', 'else'):
                if k == 'if': branch = False
                else: assert branch is not None
                if not branch and (k == 'else' or self.condition(one(v, 'limit'))):
                    branch = True
                    self.execute([n for n in v if n[0] != 'limit'])
                continue
            branch = None
            if k == 'hidden_effect': self.execute(v)
            elif k == 'every_controlled_state':
                old = self.current, self.previous
                assert self.current == self.country
                for st in self.states:
                    if not self.states[st].get('controlled', True): continue
                    self.current, self.previous = st, old[0]
                    self.visits.append(st)
                    self.execute(v)
                self.current, self.previous = old
            elif k == 'add_dynamic_modifier': self.dynamic.add((self.current, one(v, 'modifier')))
            elif k in ('set_variable', 'add_to_variable', 'multiply_variable', 'divide_variable', 'set_temp_variable', 'add_to_temp_variable', 'multiply_temp_variable', 'divide_temp_variable'):
                self.variable(k, v)
            elif k in ('clamp_variable', 'clamp_temp_variable'):
                scope, key = self.resolve(one(v, 'var'))
                td = self.temp if k == 'clamp_temp_variable' else self.variables[scope]
                tk = (scope, key) if k == 'clamp_temp_variable' else key
                for ck, cop, cv in v:
                    if ck == 'var': continue
                    assert ck in ('min', 'max') and cop == '='
                    val = self.value(cv)
                    td[tk] = max(td.get(tk, 0), val) if ck == 'min' else min(td.get(tk, 0), val)
            elif k in self.native:
                assert v == 'yes'
                self.delegates.append((k, self.current, self.root))
                # Only a boundary record; no GDP/economy formula is fabricated here.
                self.boundaries.append((k, copy.deepcopy(self.variables), copy.deepcopy(self.dynamic)))
            elif k in self.helpers:
                assert v == 'yes'
                self.execute(self.helpers[k])
            else: raise AssertionError(('Unknown visited effect', k, op, v))

    def call(self, key): self.execute(self.helpers[key])

    def visible(self): return self.variables, self.temp, self.dynamic, self.boundaries, self.delegates

def fixture(seed=0, count=4):
    rng = random.Random(seed)
    names = ('industrial_complex', 'arms_factory', 'dockyard', 'offices', 'rubber_refinery', 'agriculture_district',
             'nuclear_reactor', 'synthetic_refinery', 'fossil_powerplant', 'rocket_site', 'anti_air_building',
             'radar_station', 'air_base', 'fuel_silo', 'nuclear_facility', 'air_facility', 'land_facility', 'naval_facility')
    states = {}
    for st in range(100, 100 + count):
        buildings = {name: rng.randrange(8) for name in names}
        states[st] = {
            'buildings': buildings, 'damage': {name: rng.randrange(buildings[name] + 1) for name in names},
            'population': rng.randrange(1000, 20000), 'controlled': rng.choice((True, True, False)),
            'railway': rng.randrange(7), 'coastal': rng.choice((True, False)),
            'province_buildings': {'naval_base': [rng.randrange(7), rng.randrange(7)], 'supply_node': [rng.randrange(2)]},
            'flags': {'has_river'} if seed % 2 else {'encourage_productivity_in_state'},
            'modifiers': {'state_productivity_growth_modifier': -.1, 'state_renewable_energy_generation_modifier': .2},
            'vars': {'productivity_state_var': rng.randrange(100, 2500), 'hydroelectric_energy_production_var': .5,
                     'geothermal_energy_production_var': .1, 'hydroelectric_energy_storage_var': 100,
                     'number_of_battery_parks_state_var': 2, 'renewable_energy_random_var': .7,
                     'min_renewable_energy_var': .4, 'max_renewable_energy_var': 1.4},
        }
    return states
