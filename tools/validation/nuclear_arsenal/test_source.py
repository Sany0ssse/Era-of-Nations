"""Execute current arsenal script AST with explicit native inventory oracles.

This is a source behavior check, not a native missile deployment or raid test.
Unknown visited statements fail. Economics recomputation is a recorded boundary;
no fixture invents a treasury debit for the arsenal refresh.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import importlib.util
import io
import json
import math
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    'arsenal_ast_support', ROOT/'tools/validation/diplomacy_package_03/_support.py')
p = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = p
spec.loader.exec_module(p)

EFFECTS = 'common/scripted_effects/eon_nuclear_arsenal_effects.txt'
TRIGGERS = 'common/scripted_triggers/eon_nuclear_arsenal_triggers.txt'
DECISIONS = 'common/decisions/eon_nuclear_arsenal_decisions.txt'
CATEGORY = 'common/decisions/categories/eon_nuclear_arsenal_categories.txt'
SOURCE_OVERRIDES = {}


class Model:
    def __init__(self, reserve=0, deployed=0, ballistic_reserve=0, ballistic_deployed=0, *, prototype_enabled=False):
        self.effects = {k: v for k, op, v in p.ast(SOURCE_OVERRIDES.get(EFFECTS, (ROOT/EFFECTS).read_bytes()))}
        self.triggers = {k: v for k, op, v in p.ast(SOURCE_OVERRIDES.get(TRIGGERS, (ROOT/TRIGGERS).read_bytes()))}
        if prototype_enabled:
            # Explicit test-only enablement preserves the prototype regression
            # suite; production remains disabled because native counts failed.
            assert self.triggers['eon_nuclear_arsenal_enabled'] == [('always', '=', 'no')]
            self.triggers['eon_nuclear_arsenal_enabled'] = [('always', '=', 'yes')]
        self.variables = {'treasury': 10, 'var_reactor_material_stockpile': 12000,
                          'var_nuclear_material_stockpile': 22}
        self.flags, self.days, self.boundaries = {}, 0, []
        self.native = {'num_equipment@nuclear_missile_equipment': reserve,
                       'num_equipment@nuclear_ballistic_missile_equipment': ballistic_reserve,
                       'num_deployed_planes_with_type@nuclear_missile_equipment': deployed,
                       'num_deployed_planes_with_type@nuclear_ballistic_missile_equipment': ballistic_deployed}

    def val(self, token):
        try: return float(token)
        except ValueError: pass
        if token.startswith(('num_equipment@', 'num_deployed_planes_with_type@')):
            assert token in self.native, ('Missing native fixture input', token)
            return self.native[token]
        return self.variables.get(token, 0)

    def flag(self, name):
        if name not in self.flags: return False
        entry = self.flags[name]
        if entry is None: return True  # Native scalar set_country_flag.
        expiry, value = entry
        return value != 0 and expiry > self.days

    def trigger(self, nodes):
        results = []
        for key, op, value in nodes:
            if key == 'AND': result = self.trigger(value)
            elif key == 'OR': result = any(self.trigger([node]) for node in value)
            elif key == 'NOT': result = not self.trigger(value)
            elif key == 'always': result = value == 'yes'
            elif key == 'exists': result = value == 'yes'
            elif key == 'is_ai': result = value == 'no'
            elif key == 'has_country_flag': result = self.flag(value)
            elif key == 'has_variable': result = value in self.variables
            elif key == 'check_variable':
                assert len(value) == 1
                name, cmp, right = value[0]
                result = p.compare(self.val(name), cmp, self.val(right))
            elif key in ('custom_trigger_tooltip', 'custom_override_tooltip'):
                result = self.trigger([node for node in value if node[0] != 'tooltip'])
            elif key in self.triggers: result = self.trigger(self.triggers[key]) == (value == 'yes')
            else: raise AssertionError(('Unknown visited trigger', key))
            results.append(result)
        return all(results)

    def effect(self, nodes):
        branch = None
        for key, op, value in nodes:
            if key == 'if':
                branch = self.trigger(p.one(value, 'limit'))
                if branch: self.effect([node for node in value if node[0] != 'limit'])
            elif key == 'else_if':
                if not branch and self.trigger(p.one(value, 'limit')):
                    self.effect([node for node in value if node[0] != 'limit'])
                    branch = True
            elif key == 'else':
                assert branch is not None
                if not branch: self.effect(value)
                branch = None
            elif key in ('set_variable', 'add_to_variable', 'subtract_from_variable', 'multiply_variable'):
                assert len(value) == 1
                name, cmp, right = value[0]
                current, operand = self.val(name), self.val(right)
                self.variables[name] = {'set_variable': lambda: operand,
                                        'add_to_variable': lambda: current+operand,
                                        'subtract_from_variable': lambda: current-operand,
                                        'multiply_variable': lambda: current*operand}[key]()
            elif key == 'clamp_variable':
                name = p.one(value, 'var')
                self.variables[name] = min(self.val(p.maybe(value, 'max', '1e100')),
                    max(self.val(p.maybe(value, 'min', '-1e100')), self.val(name)))
            elif key == 'set_country_flag':
                if isinstance(value, list):
                    # Native81 independently observes that a timed block with
                    # no explicit value has value0 and fails has_country_flag;
                    # an explicit value1 is visible immediately in THIS/ROOT.
                    self.flags[p.one(value, 'flag')] = (self.days + self.val(p.one(value, 'days')),
                                                       self.val(p.maybe(value, 'value', '0')))
                else: self.flags[value] = None
            elif key == 'clr_country_flag': self.flags.pop(value, None)
            elif key == 'custom_effect_tooltip': pass
            elif key == 'hidden_effect': self.effect(value)
            elif key == 'ingame_update_setup': self.boundaries.append(key)
            elif key in self.effects: self.effect(self.effects[key])
            else: raise AssertionError(('Unknown visited effect', key))

    def call(self, name): self.effect(self.effects[name])

    def ready(self): return self.trigger(self.triggers['eon_nuclear_arsenal_ready'])

    def next_week(self):
        self.days += 7
        self.call('eon_nuclear_arsenal_weekly')


class PrototypeModel(Model):
    def __init__(self, *args, **kwargs):
        assert 'prototype_enabled' not in kwargs
        super().__init__(*args, prototype_enabled=True, **kwargs)


class ArsenalTests(unittest.TestCase):
    def assertClose(self, actual, expected): self.assertTrue(math.isclose(actual, expected, abs_tol=1e-10), (actual, expected))

    def test_no_arsenal_has_no_minimum_bill(self):
        m = PrototypeModel(); m.call('eon_nuclear_arsenal_refresh')
        self.assertEqual(m.variables['eon_nuclear_arsenal_total'], 0)
        self.assertEqual(m.variables['eon_nuclear_arsenal_weekly_cost'], 0)
        self.assertTrue(m.ready())

    def test_reserve_and_deployed_native_inventory_are_separate(self):
        m = PrototypeModel(reserve=10, deployed=4, ballistic_reserve=6, ballistic_deployed=2)
        m.call('eon_nuclear_arsenal_refresh')
        self.assertEqual(m.variables['eon_nuclear_arsenal_reserve'], 16)
        self.assertEqual(m.variables['eon_nuclear_arsenal_deployed'], 6)
        self.assertEqual(m.variables['eon_nuclear_arsenal_total'], 22)
        self.assertClose(m.variables['eon_nuclear_arsenal_weekly_cost'], 0.00268)

    def test_more_weapons_increase_bill_and_deployment_is_not_free(self):
        reserve, deployed, large = PrototypeModel(reserve=10), PrototypeModel(deployed=10), PrototypeModel(reserve=100)
        for m in (reserve, deployed, large): m.call('eon_nuclear_arsenal_refresh')
        self.assertClose(reserve.variables['eon_nuclear_arsenal_weekly_cost'], 0.0022)
        self.assertClose(deployed.variables['eon_nuclear_arsenal_weekly_cost'], 0.0026)
        self.assertClose(large.variables['eon_nuclear_arsenal_weekly_cost'], 0.004)

    def test_refresh_cannot_debit_money_consume_uranium_or_extend_recovery(self):
        m = PrototypeModel(reserve=100); m.call('eon_nuclear_arsenal_refresh')
        before = deepcopy(m.variables)
        for _ in range(25): m.call('eon_nuclear_arsenal_refresh')
        self.assertEqual(m.variables, before)
        self.assertEqual(m.variables['treasury'], 10)
        self.assertEqual(m.variables['var_reactor_material_stockpile'], 12000)
        self.assertEqual(m.variables['var_nuclear_material_stockpile'], 22)

    def test_existing_stockpile_defaults_to_full_ready_maintenance(self):
        m = PrototypeModel(reserve=28); m.call('eon_nuclear_arsenal_refresh')
        self.assertTrue(m.ready())
        self.assertFalse(m.flag('eon_nuclear_arsenal_safety_mode'))
        self.assertClose(m.variables['eon_nuclear_arsenal_weekly_cost'], 0.00256)

    def test_safety_mode_costs_35_percent_and_disables_nuclear_launch(self):
        m = PrototypeModel(reserve=100); m.call('eon_nuclear_arsenal_set_safety')
        self.assertTrue(m.flag('eon_nuclear_arsenal_safety_mode'))
        self.assertFalse(m.ready())
        self.assertClose(m.variables['eon_nuclear_arsenal_weekly_cost'], 0.0014)
        before = deepcopy(m.variables)
        m.call('eon_nuclear_arsenal_set_safety')
        self.assertEqual(m.variables, before)

    def test_safety_mode_remains_unready_without_weapons(self):
        m = PrototypeModel(reserve=1); m.call('eon_nuclear_arsenal_set_safety')
        m.native['num_equipment@nuclear_missile_equipment'] = 0
        m.next_week()
        self.assertFalse(m.ready())
        self.assertEqual(m.variables['eon_nuclear_arsenal_weekly_cost'], 0)

    def test_resumption_requires_four_genuine_weekly_pulses(self):
        m = PrototypeModel(reserve=100); m.call('eon_nuclear_arsenal_set_safety')
        m.call('eon_nuclear_arsenal_resume_full')
        self.assertEqual(m.variables['eon_nuclear_arsenal_recovery_remaining'], 4)
        self.assertClose(m.variables['eon_nuclear_arsenal_weekly_cost'], 0.004)
        for remaining in (3, 2, 1):
            m.next_week()
            self.assertEqual(m.variables['eon_nuclear_arsenal_recovery_remaining'], remaining)
            self.assertFalse(m.ready())
            for _ in range(12): m.call('eon_nuclear_arsenal_refresh')
            m.call('eon_nuclear_arsenal_resume_full')
            self.assertEqual(m.variables['eon_nuclear_arsenal_recovery_remaining'], remaining)
        m.next_week(); self.assertTrue(m.ready())
        self.assertEqual(m.variables['eon_nuclear_arsenal_recovery_remaining'], 0)

    def test_same_week_duplicate_cannot_accelerate_recovery(self):
        m = PrototypeModel(reserve=2); m.call('eon_nuclear_arsenal_set_safety')
        m.call('eon_nuclear_arsenal_resume_full'); m.next_week()
        for _ in range(10): m.call('eon_nuclear_arsenal_weekly')
        self.assertEqual(m.variables['eon_nuclear_arsenal_recovery_remaining'], 3)
        m.days += 5; m.call('eon_nuclear_arsenal_weekly')
        self.assertEqual(m.variables['eon_nuclear_arsenal_recovery_remaining'], 3)

    def test_native_timed_block_requires_explicit_nonzero_value(self):
        m = PrototypeModel()
        m.effect(p.ast('set_country_flag = { flag = private_no_value days = 6 }'))
        self.assertFalse(m.flag('private_no_value'))
        m.effect(p.ast('set_country_flag = { flag = private_value_one days = 6 value = 1 }'))
        self.assertTrue(m.flag('private_value_one'))
        m.days += 7
        self.assertFalse(m.flag('private_value_one'))

    def test_return_to_safety_cancels_recovery_and_full_restart_is_four(self):
        m = PrototypeModel(reserve=2); m.call('eon_nuclear_arsenal_set_safety')
        m.call('eon_nuclear_arsenal_resume_full'); m.next_week()
        m.call('eon_nuclear_arsenal_set_safety')
        self.assertEqual(m.variables['eon_nuclear_arsenal_recovery_remaining'], 0)
        m.call('eon_nuclear_arsenal_resume_full')
        self.assertEqual(m.variables['eon_nuclear_arsenal_recovery_remaining'], 4)

    def test_weekly_refresh_removes_cost_after_inventory_is_spent(self):
        m = PrototypeModel(reserve=1); m.call('eon_nuclear_arsenal_refresh')
        m.native['num_equipment@nuclear_missile_equipment'] = 0
        m.next_week()
        self.assertEqual(m.variables['eon_nuclear_arsenal_total'], 0)
        self.assertEqual(m.variables['eon_nuclear_arsenal_weekly_cost'], 0)

    def test_negative_counter_fixture_cannot_create_income(self):
        m = PrototypeModel(reserve=-3, deployed=-2); m.call('eon_nuclear_arsenal_refresh')
        self.assertEqual(m.variables['eon_nuclear_arsenal_total'], 0)
        self.assertEqual(m.variables['eon_nuclear_arsenal_weekly_cost'], 0)

    def test_decisions_execute_guarded_source_actions(self):
        category = p.one(p.ast((ROOT/DECISIONS).read_bytes()), 'eon_nuclear_arsenal_category')
        m = PrototypeModel(reserve=5); m.call('eon_nuclear_arsenal_refresh')
        safety = p.one(category, 'eon_nuclear_arsenal_safety')
        resume = p.one(category, 'eon_nuclear_arsenal_full')
        self.assertTrue(m.trigger(p.one(safety, 'visible')))
        self.assertFalse(m.trigger(p.one(resume, 'visible')))
        m.effect(p.one(safety, 'complete_effect'))
        self.assertFalse(m.ready())
        self.assertTrue(m.trigger(p.one(resume, 'visible')))
        m.effect(p.one(resume, 'complete_effect'))
        self.assertEqual(m.variables['eon_nuclear_arsenal_recovery_remaining'], 4)
        self.assertEqual(m.boundaries, ['ingame_update_setup', 'ingame_update_setup'])

    def test_player_locale_keys_exist_with_bom(self):
        keys = {'eon_nuclear_arsenal_category', 'eon_nuclear_arsenal_category_desc',
                'eon_nuclear_arsenal_status', 'eon_nuclear_arsenal_status_desc',
                'eon_nuclear_arsenal_safety', 'eon_nuclear_arsenal_safety_desc',
                'eon_nuclear_arsenal_full', 'eon_nuclear_arsenal_full_desc',
                'eon_nuclear_arsenal_launch_ready_tt', 'eon_nuclear_arsenal_safety_tt',
                'eon_nuclear_arsenal_full_tt', 'eon_nuclear_arsenal_mode_safety',
                'eon_nuclear_arsenal_mode_recovery', 'eon_nuclear_arsenal_mode_full'}
        for lang in ('english', 'russian'):
            raw = (ROOT/f'localisation/{lang}/eon_nuclear_arsenal_l_{lang}.yml').read_bytes()
            self.assertTrue(raw.startswith(b'\xef\xbb\xbf'))
            text = raw.decode('utf-8-sig')
            for key in keys: self.assertIn(' '+key+':0 "', text)

    def test_raid_gate_has_localized_reason_instead_of_internal_flags(self):
        trigger = p.one(p.ast((ROOT/TRIGGERS).read_bytes()), 'eon_nuclear_arsenal_ready')
        tooltip = p.one(trigger, 'custom_override_tooltip')
        self.assertEqual(p.one(tooltip, 'tooltip'), 'eon_nuclear_arsenal_launch_ready_tt')

    def test_decision_helper_effects_are_hidden_behind_readable_tooltips(self):
        category = p.one(p.ast((ROOT/DECISIONS).read_bytes()), 'eon_nuclear_arsenal_category')
        for name in ('eon_nuclear_arsenal_status', 'eon_nuclear_arsenal_safety', 'eon_nuclear_arsenal_full'):
            effects = p.one(p.one(category, name), 'complete_effect')
            self.assertEqual({key for key, op, value in effects}, {'hidden_effect', 'custom_effect_tooltip'})
            self.assertEqual(len(p.one(effects, 'hidden_effect')), 1)


class DisabledArsenalTests(unittest.TestCase):
    def seeded(self, safety=True):
        m = Model(reserve=8, deployed=5, ballistic_reserve=2, ballistic_deployed=7)
        m.variables.update(eon_nuclear_arsenal_weekly_cost=999,
                           eon_nuclear_arsenal_recovery_remaining=4,
                           eon_nuclear_arsenal_total=22,
                           eon_nuclear_arsenal_reserve=10,
                           eon_nuclear_arsenal_deployed=12,
                           eon_nuclear_arsenal_deployed_premium=88)
        if safety: m.flags['eon_nuclear_arsenal_safety_mode'] = None
        return m

    def test_actual_source_gate_is_disabled_and_category_hidden(self):
        m = self.seeded()
        self.assertEqual(m.triggers['eon_nuclear_arsenal_enabled'], [('always', '=', 'no')])
        self.assertFalse(m.trigger([('eon_nuclear_arsenal_enabled', '=', 'yes')]))
        category = p.one(p.ast(SOURCE_OVERRIDES.get(CATEGORY, (ROOT/CATEGORY).read_bytes())), 'eon_nuclear_arsenal_category')
        self.assertFalse(m.trigger(p.one(category, 'allowed')))
        self.assertFalse(m.trigger(p.one(category, 'visible')))

    def test_stale_cost_clears_without_accessing_native_inventory(self):
        m = self.seeded(); m.native.clear()
        before, flags = deepcopy(m.variables), deepcopy(m.flags)
        before['eon_nuclear_arsenal_weekly_cost'] = 0
        for _ in range(25): m.call('eon_nuclear_arsenal_refresh')
        self.assertEqual(m.variables, before)
        self.assertEqual(m.flags, flags)
        self.assertEqual(m.boundaries, [])

    def test_weekly_and_duplicates_cannot_progress_or_write_flags(self):
        m = self.seeded(); before, flags = deepcopy(m.variables), deepcopy(m.flags)
        before['eon_nuclear_arsenal_weekly_cost'] = 0
        for _ in range(4):
            m.next_week()
            for _ in range(10): m.call('eon_nuclear_arsenal_weekly')
        self.assertEqual(m.variables, before)
        self.assertEqual(m.flags, flags)
        self.assertTrue(m.ready())
        self.assertEqual(m.boundaries, [])

    def test_safety_and_resume_are_noops_for_both_old_mode_states(self):
        for safety in (False, True):
            for effect in ('eon_nuclear_arsenal_set_safety', 'eon_nuclear_arsenal_resume_full'):
                m = self.seeded(safety); m.native.clear()
                before, flags = deepcopy(m.variables), deepcopy(m.flags)
                for _ in range(3): m.call(effect)
                self.assertEqual(m.variables, before)
                self.assertEqual(m.flags, flags)
                self.assertEqual(m.boundaries, [])

    def test_ready_ignores_all_stale_safety_and_recovery_values(self):
        for safety in (False, True):
            for remaining in (-1, 0, 1, 4, 999):
                m = self.seeded(safety)
                m.variables['eon_nuclear_arsenal_recovery_remaining'] = remaining
                self.assertTrue(m.ready())

    def test_all_stale_decisions_are_unavailable_and_helpers_are_guarded(self):
        category = p.one(p.ast(SOURCE_OVERRIDES.get(DECISIONS, (ROOT/DECISIONS).read_bytes())), 'eon_nuclear_arsenal_category')
        for name in ('eon_nuclear_arsenal_status', 'eon_nuclear_arsenal_safety', 'eon_nuclear_arsenal_full'):
            for safety in (False, True):
                m = self.seeded(safety); decision = p.one(category, name)
                self.assertFalse(m.trigger(p.one(decision, 'available')))
                self.assertFalse(m.trigger(p.one(decision, 'visible')))
                before, flags = deepcopy(m.variables), deepcopy(m.flags)
                if name == 'eon_nuclear_arsenal_status': before['eon_nuclear_arsenal_weekly_cost'] = 0
                m.effect(p.one(decision, 'complete_effect'))
                self.assertEqual(m.variables, before)
                self.assertEqual(m.flags, flags)
                self.assertEqual(m.boundaries, [])


def disabled_negative_controls():
    mutations = [
        ('gate_enabled_in_production', TRIGGERS, 'eon_nuclear_arsenal_enabled = { always = no }', 'eon_nuclear_arsenal_enabled = { always = yes }'),
        ('stale_ready_flags_still_block', TRIGGERS, 'NOT = { eon_nuclear_arsenal_enabled = yes }', 'always = no'),
        ('stale_cost_reset_missing', EFFECTS, ' set_variable = { eon_nuclear_arsenal_weekly_cost = 0 }\n', ''),
        ('refresh_runs_while_disabled', EFFECTS, 'limit = { eon_nuclear_arsenal_enabled = yes }', 'limit = { always = yes }'),
        ('disabled_refresh_debits_treasury', EFFECTS, ' set_variable = { eon_nuclear_arsenal_weekly_cost = 0 }\n', ' subtract_from_variable = { treasury = 1 }\n set_variable = { eon_nuclear_arsenal_weekly_cost = 0 }\n'),
        ('disabled_refresh_burns_fuel', EFFECTS, ' set_variable = { eon_nuclear_arsenal_weekly_cost = 0 }\n', ' subtract_from_variable = { var_reactor_material_stockpile = 1 }\n set_variable = { eon_nuclear_arsenal_weekly_cost = 0 }\n'),
        ('disabled_category_is_exposed', CATEGORY, 'allowed = { eon_nuclear_arsenal_enabled = yes }', 'allowed = { always = yes }'),
        ('cached_category_visible', CATEGORY, '  eon_nuclear_arsenal_enabled = yes\n', '  always = yes\n'),
        ('cached_status_decision_visible', DECISIONS, 'visible = { eon_nuclear_arsenal_enabled = yes is_ai = no }', 'visible = { is_ai = no }'),
        ('cached_safety_decision_visible', DECISIONS, '   eon_nuclear_arsenal_enabled = yes\n', '   always = yes\n'),
        ('cached_resume_decision_visible', DECISIONS, 'visible = { eon_nuclear_arsenal_enabled = yes is_ai = no has_country_flag = eon_nuclear_arsenal_safety_mode }', 'visible = { is_ai = no has_country_flag = eon_nuclear_arsenal_safety_mode }'),
        ('stale_decisions_available', DECISIONS, 'available = { eon_nuclear_arsenal_enabled = yes }', 'available = { always = yes }'),
    ]
    rejected = []
    for name, rel, needle, replacement in mutations:
        original = (ROOT/rel).read_bytes().decode('utf-8-sig')
        assert needle in original
        SOURCE_OVERRIDES[rel] = original.replace(needle, replacement, 1)
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(DisabledArsenalTests))
        assert not result.wasSuccessful(), ('Surviving default-off mutation', name)
        rejected.append(name); SOURCE_OVERRIDES.clear()
    return rejected


def negative_controls():
    original = (ROOT/EFFECTS).read_bytes().decode('utf-8-sig')
    mutations = {
        'stockpile_is_mistaken_for_deployment': (
            'num_deployed_planes_with_type@nuclear_missile_equipment',
            'num_equipment@nuclear_missile_equipment'),
        'ballistic_reserves_omitted': (
            'add_to_variable = { eon_nuclear_arsenal_reserve = num_equipment@nuclear_ballistic_missile_equipment }',
            'add_to_variable = { eon_nuclear_arsenal_reserve = 0 }'),
        'tenfold_weapon_price': (
            'multiply_variable = { eon_nuclear_arsenal_weekly_cost = 0.00002 }',
            'multiply_variable = { eon_nuclear_arsenal_weekly_cost = 0.0002 }'),
        'free_safety_storage': (
            'multiply_variable = { eon_nuclear_arsenal_weekly_cost = 0.35 }',
            'multiply_variable = { eon_nuclear_arsenal_weekly_cost = 0 }'),
        'resume_is_immediately_ready': (
            'set_variable = { eon_nuclear_arsenal_recovery_remaining = 4 }',
            'set_variable = { eon_nuclear_arsenal_recovery_remaining = 0 }'),
        'two_recovery_steps_each_week': (
            'subtract_from_variable = { eon_nuclear_arsenal_recovery_remaining = 1 }',
            'subtract_from_variable = { eon_nuclear_arsenal_recovery_remaining = 2 }'),
        'same_week_guard_expires_immediately': (
            'flag = eon_nuclear_arsenal_weekly_processed days = 6',
            'flag = eon_nuclear_arsenal_weekly_processed days = 0'),
        'timed_guard_missing_native_value': (
            'flag = eon_nuclear_arsenal_weekly_processed days = 6 value = 1',
            'flag = eon_nuclear_arsenal_weekly_processed days = 6'),
        'refresh_also_debits_money': (
            'set_variable = { eon_nuclear_arsenal_weekly_cost = 0 }',
            'subtract_from_variable = { treasury = 1 } set_variable = { eon_nuclear_arsenal_weekly_cost = 0 }'),
        'refresh_burns_reactor_fuel': (
            'set_variable = { eon_nuclear_arsenal_weekly_cost = 0 }',
            'subtract_from_variable = { var_reactor_material_stockpile = 1 } set_variable = { eon_nuclear_arsenal_weekly_cost = 0 }'),
    }
    rejected = []
    for name, (needle, replacement) in mutations.items():
        assert original.count(needle) == 1, (name, 'Mutation must be narrow')
        SOURCE_OVERRIDES[EFFECTS] = original.replace(needle, replacement)
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ArsenalTests)
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        assert not result.wasSuccessful(), ('Surviving source mutation', name)
        rejected.append(name)
    SOURCE_OVERRIDES.clear()
    return rejected


if __name__ == '__main__':
    suite = unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromTestCase(ArsenalTests),
        unittest.defaultTestLoader.loadTestsFromTestCase(DisabledArsenalTests)])
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)
    rejected = negative_controls() if result.wasSuccessful() else []
    disabled_rejected = disabled_negative_controls() if result.wasSuccessful() else []
    hashes = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
              for name in (EFFECTS, TRIGGERS, DECISIONS, CATEGORY) if (ROOT/name).exists()}
    print(json.dumps({'actual_source_tests': result.testsRun,
                      'checks_passed': result.wasSuccessful(),
                      'source_mutations_rejected': rejected,
                      'default_off_source_mutations_rejected': disabled_rejected,
                      'prototype_gate_enabled_only_in_test_model': True,
                      'source_sha256': hashes,
                      'native_game_behavior_tested': False}, indent=2))
    raise SystemExit(not result.wasSuccessful())
