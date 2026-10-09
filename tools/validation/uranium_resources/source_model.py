"""Execute the actual uranium AST with explicit native fixture inputs.

This interpreter does not emulate HOI4 trade delivery, calendar expiry or its
economic engine. Native input values, state resource multipliers, delivery shares
and control are explicit fixture oracles. Every visited unknown statement fails.
"""
from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import importlib.util
import math
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('uranium_actual_ast', ROOT/'tools/validation/diplomacy_package_03/_support.py')
p = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = p
spec.loader.exec_module(p)


@dataclass
class Entity:
    kind: str
    ident: int
    tag: str = ''
    exists: bool = True
    ai: bool = False
    owner: str = ''
    controller: str = ''
    variables: dict = field(default_factory=dict)
    flags: set = field(default_factory=set)
    arrays: dict = field(default_factory=dict)
    techs: set = field(default_factory=set)
    missions: set = field(default_factory=set)
    wars: set = field(default_factory=set)
    embargoing: set = field(default_factory=set)
    resource_rights: dict = field(default_factory=dict)
    native: dict = field(default_factory=lambda: {
        'resource@uranium': 0, 'resource_imported@uranium': 0,
        'resource_exported@uranium': 0, 'resource_produced@uranium': 0,
        'resource_consumed@uranium': 0,
        'modifier@nuclear_reactor_fuel_production': 0,
        'industrial_complex_total': 0,
        'num_of_civilian_factories_available_for_projects': 0,
        'building_level@nuclear_reactor': 0,
        'days_mission_timeout@energy_building_enrichment_facilities': 0,
    })
    # Explicit oracle describing how native output changes affect the controller.
    resource_multiplier: float = 1
    retained_delivered_share: float = 1


class Source:
    def __init__(self):
        self.raw, self.sha256, self.effects, self.triggers = {}, {}, {}, {}
        for kind, destination in (('effects', self.effects), ('triggers', self.triggers)):
            rel = 'common/scripted_'+kind+'/eon_uranium_'+kind+'.txt'
            raw = (ROOT/rel).read_bytes()
            self.raw[rel] = raw
            self.sha256[rel] = hashlib.sha256(raw).hexdigest()
            for key, operator, value in p.ast(raw):
                assert operator == '=' and isinstance(value, list)
                assert key not in destination
                destination[key] = value
        for rel, helper in (
            ('common/scripted_effects/!_energy_effects.txt', 'build_enrichment_facilities_effect'),
            ('common/scripted_effects/!_energy_effects.txt', 'change_reactor_grade_material_effect'),
            ('common/scripted_effects/00_budget_effects.txt', 'modify_treasury_effect'),
            ('common/scripted_effects/00_missiles_scripted_effects.txt', 'nuclear_reactor_fuel_consumption'),
            ('common/scripted_effects/00_missiles_scripted_effects.txt', 'setup_starting_reactor_stockpile'),
            ('common/scripted_effects/eon_nuclear_fuel_trade_effects.txt', 'eon_nuclear_fuel_trade_release_refunds'),
        ):
            self.effects[helper] = self.hook(rel, [helper])
        self.resources = self.hook('common/resources/00_resources.txt', ['resources'])

    def hook(self, rel, selector):
        if rel not in self.raw:
            raw = (ROOT/rel).read_bytes()
            self.raw[rel] = raw
            self.sha256[rel] = hashlib.sha256(raw).hexdigest()
        nodes = p.ast(self.raw[rel])
        for key in selector:
            nodes = p.one(nodes, key)
        return nodes


class Model:
    def __init__(self, source, from_state=False):
        self.source = source
        self.entities = {
            'GLOBAL': Entity('global', 0),
            'AAA': Entity('country', 1, 'AAA'),
            'BBB': Entity('country', 2, 'BBB'),
            '101': Entity('state', 101, owner='AAA', controller='AAA'),
        }
        self.current = self.root = 'AAA'
        self.from_ = '101' if from_state else 'BBB'
        self.temp, self.native_calls, self.expiry_rules = {}, [], []
        self.meta_expansions = []
        self.visited_effects, self.visited_triggers = set(), set()
        # Geology is supplied explicitly, and tested separately on its actual AST.
        self.entities['GLOBAL'].flags.add('eon_uranium_geology_initialized')
        for country in ('AAA', 'BBB'):
            self.entities[country].techs.add('nuclear_technology')
            # Ordinary fixtures supply modern kg stocks explicitly. Legacy
            # migration cases remove this flag before executing initialization.
            self.entities[country].flags.add('eon_uranium_reactor_stock_in_kg')
        # These existing whole-economy helpers are explicit boundaries; no test
        # below claims to execute their internal GDP, trade or event machinery.
        self.boundaries = {'ingame_update_setup', 'eon_nuclear_fuel_trade_daily_cleanup',
                           'calculate_energy_use', 'update_energy_dirty_variable'}
        source.hook('common/scripted_effects/eon_nuclear_fuel_trade_effects.txt',
                    ['eon_nuclear_fuel_trade_daily_cleanup'])
        source.hook('common/scripted_effects/00_money_system.txt', ['ingame_update_setup'])
        source.hook('common/scripted_effects/!_energy_effects.txt', ['calculate_energy_use'])
        source.hook('common/scripted_effects/00_money_system.txt', ['update_energy_dirty_variable'])

    def scope(self, name, stack):
        if name == 'ROOT': return self.root
        if name == 'THIS': return stack[-1]
        if name == 'FROM': return self.from_
        if name == 'PREV':
            assert len(stack) >= 2, 'PREV without an ancestor'
            return stack[-2]
        if name.startswith('var:'):
            ident = int(self.value(name[4:], stack))
            found = [key for key, entity in self.entities.items() if entity.ident == ident]
            assert len(found) == 1, ('Ambiguous numeric scope', name)
            return found[0]
        assert name in self.entities, ('Unknown scope', name)
        return name

    def owner_key(self, token, stack):
        parts, scope, previous = token.split('.'), stack[-1], len(stack)-1
        while len(parts) > 1:
            name = parts.pop(0)
            if name == 'global': scope = 'GLOBAL'
            elif name == 'PREV':
                previous -= 1
                assert previous >= 0, 'Dotted PREV without an ancestor'
                scope = stack[previous]
            elif name in ('ROOT', 'THIS', 'FROM'): scope = self.scope(name, stack)
            else:
                assert name in self.entities, ('Unknown dotted scope', name)
                scope = name
        return scope, parts[0]

    def value(self, token, stack):
        assert isinstance(token, str), ('Non-scalar value', token)
        try: return float(token)
        except ValueError: pass
        if token in ('ROOT', 'THIS', 'FROM', 'PREV'):
            return self.entities[self.scope(token, stack)].ident
        scope, key = self.owner_key(token.removeprefix('var:'), stack)
        entity = self.entities[scope]
        if key == 'id': return entity.ident
        if key.startswith(('resource@', 'resource_imported@', 'resource_exported@',
                           'resource_produced@', 'resource_consumed@', 'modifier@', 'building_level@', 'days_mission_timeout@')) or key in (
                               'industrial_complex_total', 'num_of_civilian_factories_available_for_projects'):
            assert key in entity.native, ('Missing native fixture input', scope, key)
            return entity.native[key]
        # Execution temporary variables are shared by unqualified statements.
        # A native scoped lookup (PREV.x/ROOT.x/state.x/global.x) reads that
        # entity's persistent variable, never a same-name execution temporary.
        if '.' not in token.removeprefix('var:'):
            return self.temp.get(key, entity.variables.get(key, 0))
        return entity.variables.get(key, 0)

    def var(self, token, stack, temporary=False):
        scope, key = self.owner_key(token, stack)
        assert not temporary or scope == stack[-1], 'Scoped temporary mutation needs an explicit model'
        return (self.temp if temporary else self.entities[scope].variables), key

    def flag_key(self, key, stack):
        if '@' not in key: return key
        name, reference = key.split('@', 1)
        return name+'@'+str(self.entities[self.scope(reference, stack)].ident)

    def variable_check(self, nodes, stack):
        if any(key == 'var' for key, op, value in nodes):
            key, amount = p.one(nodes, 'var'), p.one(nodes, 'value')
            operator = {'equals': '=', 'not_equals': '!=', 'less_than': '<',
                        'less_than_or_equals': '<=', 'greater_than': '>',
                        'greater_than_or_equals': '>='}[p.maybe(nodes, 'compare', 'equals')]
        else:
            assert len(nodes) == 1
            key, operator, amount = nodes[0]
        return p.compare(self.value(key, stack), operator, self.value(amount, stack))

    def trigger(self, nodes, stack=None):
        stack = [self.current] if stack is None else stack
        index = 0
        while index < len(nodes):
            key, operator, value = nodes[index]
            index += 1
            entity = self.entities[stack[-1]]
            if key in self.source.triggers:
                self.visited_triggers.add(key)
                passed = self.trigger(self.source.triggers[key], stack) == (value == 'yes')
            elif key in ('ROOT', 'THIS', 'FROM', 'PREV') or key in self.entities or key.startswith('var:'):
                passed = self.trigger(value, stack+[self.scope(key, stack)])
            elif key in ('AND', 'hidden_trigger', 'custom_trigger_tooltip'):
                passed = self.trigger(value, stack)
            elif key == 'tooltip': continue
            elif key == 'NOT': passed = not self.trigger(value, stack)
            elif key == 'OR': passed = any(self.trigger([node], stack) for node in value)
            elif key == 'if':
                branches = [value]
                while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                    branches.append(nodes[index][2])
                    index += 1
                passed = True
                for branch in branches:
                    if self.trigger(p.maybe(branch, 'limit', []), stack):
                        passed = self.trigger([node for node in branch if node[0] != 'limit'], stack)
                        break
            elif key in ('set_temp_variable', 'add_to_temp_variable', 'subtract_from_temp_variable',
                         'multiply_temp_variable', 'divide_temp_variable', 'round_temp_variable', 'clamp_temp_variable'):
                self.effect([(key, operator, value)], stack)
                passed = True
            elif key == 'always': passed = value == 'yes'
            elif key == 'check_variable': passed = self.variable_check(value, stack)
            elif key == 'has_variable':
                scope, variable = self.owner_key(value, stack)
                passed = variable in self.entities[scope].variables
            elif key == 'has_country_flag' or key == 'has_state_flag':
                passed = self.flag_key(value, stack) in entity.flags
            elif key == 'has_global_flag': passed = value in self.entities['GLOBAL'].flags
            elif key == 'has_tech': passed = value in entity.techs
            elif key == 'has_active_mission': passed = value in entity.missions
            elif key == 'is_ai': passed = entity.ai == (value == 'yes')
            elif key == 'exists': passed = entity.exists == (value == 'yes')
            elif key == 'tag': passed = stack[-1] == self.scope(value, stack)
            elif key == 'is_owned_by': passed = entity.owner == self.scope(value, stack)
            elif key == 'is_controlled_by': passed = entity.controller == self.scope(value, stack)
            elif key == 'has_war_with': passed = self.scope(value, stack) in entity.wars
            elif key == 'is_embargoing': passed = self.scope(value, stack) in entity.embargoing
            elif key == 'is_embargoed_by': passed = stack[-1] in self.entities[self.scope(value, stack)].embargoing
            elif key == 'has_resources_rights':
                assert isinstance(value, list)
                if entity.kind == 'state':
                    state_key, recipient = stack[-1], self.scope(p.one(value, 'receiver'), stack)
                else:
                    state_key, recipient = self.scope(p.one(value, 'state'), stack), stack[-1]
                resources = p.maybe(value, 'resources', [('__item__', '=', 'uranium')])
                requested = {entry for name, op, entry in resources if name == '__item__'}
                assert requested == {'uranium'}, ('Unknown resource-rights fixture', requested)
                # Installed native documentation: this predicate is false when
                # the state has no resource, even if a rights identity remains.
                passed = (self.entities[state_key].native['resource@uranium'] > 0 and
                          requested <= self.entities[recipient].resource_rights.get(state_key, set()))
            elif key == 'is_in_array':
                if any(k == 'array' for k, op, v in value):
                    array, item = p.one(value, 'array'), p.one(value, 'value')
                else:
                    assert len(value) == 1
                    array, op, item = value[0]
                    assert op == '='
                scope, array = self.owner_key(array, stack)
                passed = self.value(item, stack) in self.entities[scope].arrays.get(array, [])
            else: raise AssertionError(('Unknown visited trigger', key, operator, value))
            if not passed: return False
        return True

    def effect(self, nodes, stack=None):
        if stack is None:
            self.temp = {}
            stack = [self.current]
        index = 0
        while index < len(nodes):
            key, operator, value = nodes[index]
            index += 1
            entity = self.entities[stack[-1]]
            if key in self.source.effects:
                assert value == 'yes'
                self.visited_effects.add(key)
                self.effect(self.source.effects[key], stack)
            elif key in self.boundaries:
                assert value == 'yes'
                self.native_calls.append({'boundary': key, 'scope': stack[-1]})
            elif key in ('ROOT', 'THIS', 'FROM', 'PREV') or key in self.entities or key.startswith('var:'):
                self.effect(value, stack+[self.scope(key, stack)])
            elif key == 'if':
                branches = [value]
                while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                    branches.append(nodes[index][2])
                    index += 1
                for branch in branches:
                    if self.trigger(p.maybe(branch, 'limit', []), stack):
                        self.effect([node for node in branch if node[0] != 'limit'], stack)
                        break
            elif key == 'effect_tooltip':
                # Installed effects documentation: show only the effects'
                # tooltip. Its enclosed effects do not change gameplay state.
                self.native_calls.append({'effect_tooltip': True, 'scope': stack[-1]})
            elif key == 'hidden_effect':
                self.effect(value, stack)
            elif key == 'add_opinion_modifier':
                assert entity.kind == 'country'
                assert {name for name, op, entry in value} == {'target', 'modifier'}
                target = self.scope(p.one(value, 'target'), stack)
                assert self.entities[target].kind == 'country'
                # Record the exact callback boundary; opinion state is native.
                self.native_calls.append({'add_opinion_modifier': p.one(value, 'modifier'),
                                          'scope': stack[-1], 'target': target})
            elif key == 'country_event':
                assert entity.kind == 'country'
                assert {name for name, op, entry in value} == {'id', 'days'}
                days = self.value(p.one(value, 'days'), stack)
                assert math.isfinite(days) and days >= 0
                # Queue request only: no native event dispatch is emulated.
                self.native_calls.append({'country_event': p.one(value, 'id'),
                                          'scope': stack[-1], 'days': days})
            elif key in ('log', 'custom_effect_tooltip'): continue
            elif key == 'meta_effect':
                template = p.one(value, 'text')
                template = p.ast(template) if isinstance(template, str) else template
                bindings = {}
                for name, op, expression in value:
                    if name == 'text': continue
                    if name == 'debug':
                        assert op == '=' and expression in ('yes', 'no')
                        continue
                    assert op == '=' and isinstance(expression, str)
                    match = re.fullmatch(r'\[\?([A-Za-z_][A-Za-z0-9_.@:]*)\|0\]', expression)
                    tag = re.fullmatch(r'\[(THIS|ROOT|FROM|PREV)\.GetTag\]', expression)
                    if match:
                        replacement = format(self.value(match[1], stack), '.0f')
                    elif tag:
                        country = self.entities[self.scope(tag[1], stack)]
                        assert country.kind == 'country' and re.fullmatch(r'[A-Z]{3}', country.tag)
                        replacement = country.tag
                    elif re.fullmatch(r'[A-Z]{3}|-?[0-9]+', expression):
                        replacement = expression
                    else:
                        raise AssertionError(('Unknown meta-effect fixture formatter', expression))
                    bindings['['+name+']'] = replacement
                def substitute(nodes):
                    result = []
                    for name, op, entry in nodes:
                        name = bindings.get(name, name)
                        assert not re.search(r'\[[A-Z_]+\]', name), 'Unbound meta-effect scope argument'
                        entry = substitute(entry) if isinstance(entry, list) else bindings.get(entry, entry)
                        assert isinstance(entry, list) or not re.search(r'\[[A-Z_]+\]', entry), 'Unbound meta-effect argument'
                        result.append((name, op, entry))
                    return result
                expanded = substitute(template)
                self.meta_expansions.append({'scope': stack[-1], 'ast': expanded})
                self.effect(expanded, stack)
            elif key == 'hidden_effect': self.effect(value, stack)
            elif key in ('every_controlled_state', 'every_state'):
                targets = [name for name, item in self.entities.items()
                           if item.kind == 'state' and (key == 'every_state' or item.controller == stack[-1])]
                for name in targets:
                    if self.trigger(p.maybe(value, 'limit', []), stack+[name]):
                        self.effect([node for node in value if node[0] != 'limit'], stack+[name])
            elif key == 'random_country':
                targets = [name for name, item in self.entities.items()
                           if item.kind == 'country' and self.trigger(p.maybe(value, 'limit', []), stack+[name])]
                if targets:
                    # Selection is an explicit deterministic fixture oracle.
                    self.effect([node for node in value if node[0] != 'limit'], stack+[targets[0]])
            elif key == 'every_country':
                for name, item in self.entities.items():
                    if item.kind == 'country' and self.trigger(p.maybe(value, 'limit', []), stack+[name]):
                        self.effect([node for node in value if node[0] != 'limit'], stack+[name])
            elif key in ('set_variable', 'set_temp_variable', 'add_to_variable', 'add_to_temp_variable',
                         'subtract_from_variable', 'subtract_from_temp_variable', 'multiply_variable',
                         'multiply_temp_variable', 'divide_variable', 'divide_temp_variable'):
                if any(k == 'var' for k, op, v in value):
                    variable, amount = p.one(value, 'var'), p.one(value, 'value')
                else:
                    assert len(value) == 1
                    variable, op, amount = value[0]
                    assert op == '='
                temporary = '_temp_variable' in key
                store, variable = self.var(variable, stack, temporary)
                amount = self.value(amount, stack)
                old = store.get(variable, 0)
                if key.startswith('set_'): store[variable] = amount
                elif key.startswith('add_'): store[variable] = old+amount
                elif key.startswith('subtract_'): store[variable] = old-amount
                elif key.startswith('multiply_'): store[variable] = old*amount
                elif key.startswith('divide_'):
                    assert amount != 0, 'Source division by zero'
                    store[variable] = old/amount
            elif key in ('clear_variable', 'clear_temp_variable'):
                store, variable = self.var(value, stack, key == 'clear_temp_variable')
                store.pop(variable, None)
            elif key in ('clamp_variable', 'clamp_temp_variable'):
                store, variable = self.var(p.one(value, 'var'), stack, key == 'clamp_temp_variable')
                old = store.get(variable, 0)
                if any(k == 'min' for k, op, v in value): old = max(old, self.value(p.one(value, 'min'), stack))
                if any(k == 'max' for k, op, v in value): old = min(old, self.value(p.one(value, 'max'), stack))
                store[variable] = old
            elif key in ('round_variable', 'round_temp_variable'):
                store, variable = self.var(value, stack, key == 'round_temp_variable')
                old = store.get(variable, 0)
                store[variable] = math.floor(old+0.5) if old >= 0 else math.ceil(old-0.5)
            elif key in ('set_country_flag', 'set_state_flag', 'set_global_flag'):
                flag = p.one(value, 'flag') if isinstance(value, list) else value
                if isinstance(value, list) and any(k == 'days' for k, op, v in value):
                    self.expiry_rules.append((stack[-1], flag, self.value(p.one(value, 'days'), stack)))
                target = self.entities['GLOBAL'] if key == 'set_global_flag' else entity
                target.flags.add(self.flag_key(flag, stack))
            elif key in ('clr_country_flag', 'clr_state_flag', 'clr_global_flag'):
                target = self.entities['GLOBAL'] if key == 'clr_global_flag' else entity
                target.flags.discard(self.flag_key(value, stack))
            elif key == 'add_to_array':
                assert len(value) == 1
                array, op, item = value[0]
                assert op == '='
                scope, array = self.owner_key(array, stack)
                self.entities[scope].arrays.setdefault(array, []).append(self.value(item, stack))
            elif key == 'activate_mission':
                entity.missions.add(value)
                self.native_calls.append({'mission': value, 'scope': stack[-1]})
            elif key == 'remove_mission':
                assert entity.kind == 'country'
                entity.missions.discard(value)
                # Documented primitive removal, without timeout/complete
                # callbacks. Activation/expiry and elapsed time are not modeled.
                entity.native['days_mission_timeout@'+value] = 0
                self.native_calls.append({'remove_mission':value,'scope':stack[-1]})
            elif key == 'add_days_mission_timeout':
                mission = p.one(value, 'mission')
                days = self.value(p.one(value, 'days'), stack)
                assert isinstance(mission, str) and math.isfinite(days)
                # Record the actual calendar request. Only the native game can
                # establish registration, remaining days and timed completion.
                self.native_calls.append({'add_days_mission_timeout': mission,
                                          'days': days, 'scope': stack[-1]})
            elif key == 'add_resource':
                assert entity.kind == 'state'
                resource, amount = p.one(value, 'type'), self.value(p.one(value, 'amount'), stack)
                assert resource == 'uranium', ('Unknown native resource fixture', resource)
                assert float(amount).is_integer(), ('Fractional add/remove would be truncated by the recorded native engine', amount)
                effective_delta = amount*entity.resource_multiplier
                entity.native['resource@uranium'] += effective_delta
                # A controlled explicit oracle, not a native engine simulation.
                controller = self.entities[entity.controller]
                controller.native['resource@uranium'] += effective_delta*entity.retained_delivered_share
                controller.native['resource_produced@uranium'] += effective_delta
                self.native_calls.append({'add_resource': resource, 'amount': amount, 'state': stack[-1]})
            elif key == 'create_import':
                resource = p.one(value, 'resource')
                keys = [name for name, op, entry in value if name in ('amount', 'factories')]
                assert len(keys) == 1, 'Native import must bind exactly one amount/factory input'
                argument = keys[0]
                quantity = self.value(p.one(value, argument), stack)
                assert math.isfinite(quantity) and quantity > 0
                call = {'create_import': resource, argument: quantity,
                        'importer': stack[-1], 'exporter': self.scope(p.one(value, 'exporter'), stack)}
                if argument == 'factories':
                    assert quantity == math.floor(quantity), 'Native factories must be whole'
                    cic = float(p.one(p.one(self.source.resources, resource), 'cic'))
                    assert cic > 0
                    call['requested_native_capacity'] = quantity/cic
                # This is a request/quote boundary only. No native delivered
                # balance, importer inventory or exporter allocation is changed.
                self.native_calls.append(call)
            else: raise AssertionError(('Unknown visited effect', key, operator, value))

    def call(self, helper):
        assert helper in self.source.effects
        self.effect([(helper, '=', 'yes')])

    def country(self, tag='AAA'): return self.entities[tag]
    def state(self, ident='101'): return self.entities[ident]
