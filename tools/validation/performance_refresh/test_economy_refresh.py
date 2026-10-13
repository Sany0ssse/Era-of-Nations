"""Portable current-source regression; before fixtures are exact helper islands.
No .local, Git history, rebuild, native launch, or full historical money source.
"""
from pathlib import Path
import copy, hashlib, sys, unittest
ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools/validation/diplomacy_package_03"))
from _support import ast, one
from _model import Refresh, fixture

def body_span(text, key):
    needle = key + ' = {'
    assert text.count(needle) == 1, (key, text.count(needle))
    start = text.index(needle) + len(needle)
    depth, quoted, comment, escaped = 1, False, False, False
    for end in range(start, len(text)):
        c = text[end]
        if comment:
            if c == '\n': comment = False
            continue
        if quoted:
            if escaped: escaped = False
            elif c == '\\': escaped = True
            elif c == '"': quoted = False
            continue
        if c == '#': comment = True
        elif c == '"': quoted = True
        elif c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0: return start, end
    raise AssertionError(('Unclosed body', key))

def raw_body(text, key):
    a, b = body_span(text, key)
    return text[a:b]

def expand(nodes, helpers):
    result = []
    for key, op, value in nodes:
        if key in helpers:
            assert op == '=' and value == 'yes', (key, op, value)
            result.extend(expand(helpers[key], helpers))
        elif isinstance(value, list): result.append((key, op, expand(value, helpers)))
        else: result.append((key, op, value))
    return result

def sources(which):
    if which == "baseline":
        raw = (HERE / "fixtures/baseline_state_refresh.txt").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == '47fd8b2686ebd67705f4a2664404ed55d9df6a8387a6e2d8d9b20b3df8087717', "Before fixture drift"
        return dict((k, v) for k, op, v in ast(raw) if isinstance(v, list))
    result = {}
    for rel in ('common/scripted_effects/00_money_system.txt', 'common/scripted_effects/00_damaged_buildings_count.txt', 'common/scripted_effects/eon_economy_state_refresh_effects.txt', 'common/scripted_effects/!_energy_effects.txt'):
        result.update({k: v for k, op, v in ast((ROOT / rel).read_bytes()) if isinstance(v, list)})
    return result

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old, cls.new = sources('baseline'), sources('candidate')

    def pair(self, states, variables=None, root=9):
        old = Refresh(self.old, states, fixture=variables, root=root)
        new = Refresh(self.new, states, fixture=variables, root=root)
        old.call('calculate_damaged_buildings_count'); old.call('update_state_variables')
        new.call('eon_economy_refresh_state_and_damage')
        return old, new

    def test_old_actual_two_state_walks_exposes_redundant_work(self):
        old, new = self.pair(fixture(3, 8))
        count = sum(s.get('controlled', True) for s in old.states.values())
        self.assertEqual(len(old.visits), 2 * count)
        with self.assertRaises(AssertionError): self.assertEqual(len(old.visits), count) # retained RED witness
        self.assertEqual(len(new.visits), count)
        self.assertEqual(old.visible(), new.visible())

    def test_300_differential_worlds_preserve_state_temp_and_delegate_inputs(self):
        for seed in range(300):
            old, new = self.pair(fixture(seed, seed % 20), {'num_of_synthetic_refinery': seed % 11})
            self.assertEqual(old.visible(), new.visible(), seed)
            self.assertEqual(sorted(old.queries), sorted(new.queries), seed)
            self.assertEqual(len(new.visits) * 2, len(old.visits), seed)

    def test_both_public_entrypoints_expand_to_original_exact_AST(self):
        helpers = {k: v for k, v in self.new.items() if k.startswith('eon_economy_')}
        for key in ('calculate_damaged_buildings_count', 'update_state_variables'):
            self.assertEqual(expand(self.new[key], helpers), self.old[key])

    def test_repeated_call_inherited_accumulators_not_silently_fixed(self):
        old, new = self.pair(fixture(8), {'num_of_synthetic_refinery': 7, 'total_number_of_controlled_states': 13})
        for _ in range(3):
            old.call('calculate_damaged_buildings_count'); old.call('update_state_variables')
            new.call('eon_economy_refresh_state_and_damage')
            self.assertEqual(old.visible(), new.visible())

    def test_negative_and_zero_growth_empty_country_and_unrelated_ROOT(self):
        for count in (0, 1, 5):
            for growth in (-.2, 0, .2):
                old = Refresh(self.old, fixture(10, count)); new = Refresh(self.new, fixture(10, count))
                old.modifiers[1]['productivity_growth_modifier'] = growth
                new.modifiers[1]['productivity_growth_modifier'] = growth
                old.call('calculate_damaged_buildings_count'); old.call('update_state_variables')
                new.call('eon_economy_refresh_state_and_damage')
                self.assertEqual(old.visible(), new.visible())
                self.assertEqual(new.variables[9], {'wrong_root_sentinel': 999})

    def test_daily_fuel_zero_tax_and_building_change_weekly_call_boundary(self):
        old = Refresh(self.old, fixture(12), fixture={'fuel_k': 0, 'no_fuel_penalties_var': -.5, 'tax_law_fixture': .1})
        new = Refresh(self.new, fixture(12), fixture={'fuel_k': 0, 'no_fuel_penalties_var': -.5, 'tax_law_fixture': .1})
        for model in (old, new): model.states[100]['controlled'] = True
        initial_civs = sum(st['buildings']['industrial_complex'] for st in old.states.values() if st['controlled'])
        for day in range(3):
            # Actual external facts change while the fuel penalty remains identical.
            for model in (old, new):
                model.variables[1]['tax_law_fixture'] += .05
                model.states[100]['buildings']['industrial_complex'] += 2
                model.states[100]['damage']['industrial_complex'] += 1
                model.call('energy_on_daily')
            self.assertEqual(old.visible(), new.visible())
        self.assertEqual(sum(k == 'calculate_tax_gain' for k, _, _ in new.delegates), 3)
        self.assertEqual(new.variables[1]['industrial_complex_total'], initial_civs + 6)
        last_tax = [snap for name, snap, dyn in new.boundaries if name == 'calculate_tax_gain'][-1]
        self.assertAlmostEqual(last_tax[1]['tax_law_fixture'], .25)
        for model in (old, new): model.call('ingame_update_setup') # unchanged weekly entry
        self.assertEqual(old.visible(), new.visible())
        self.assertEqual(sum(k == 'calculate_tax_gain' for k, _, _ in new.delegates), 4)

    def test_fresh_control_population_and_damage_not_cached_between_calls(self):
        states = fixture(8, 4)
        states[100]['controlled'] = True
        states[101]['controlled'] = False
        old, new = self.pair(states)
        for model in (old, new):
            model.states[100]['controlled'] = False
            model.states[101]['controlled'] = True
            model.states[101]['population'] += 10000
            model.states[101]['damage']['industrial_complex'] += 3
            model.states[101]['vars']['hydroelectric_energy_storage_var'] += 20
            # State variable facts are independent from state-owned source metadata.
            model.variables[101]['hydroelectric_energy_storage_var'] += 20
        old.call('calculate_damaged_buildings_count'); old.call('update_state_variables')
        new.call('eon_economy_refresh_state_and_damage')
        self.assertEqual(old.visible(), new.visible())
        controlled = [st for st in new.states.values() if st['controlled']]
        self.assertEqual(new.variables[1]['num_of_damaged_civs'], sum(st['damage']['industrial_complex'] for st in controlled))
        self.assertEqual(new.variables[1]['population_total'], sum(st['population'] * .01 for st in controlled))

    def test_naive_unchanged_fuel_guard_loses_real_fresh_inputs(self):
        # This private hostile source is never proposed for installation.
        raw = (ROOT / 'common/scripted_effects/!_energy_effects.txt').read_text(encoding='utf-8-sig')
        daily = raw_body(raw, 'energy_on_daily')
        daily = daily.replace('\tset_variable = { no_fuel_penalties_var = 0 }', '\tset_temp_variable = { old_penalty = no_fuel_penalties_var }\n\tset_variable = { no_fuel_penalties_var = 0 }', 1)
        daily = daily.replace('\t\tingame_update_setup = yes', '\t\tif = { limit = { NOT = { check_variable = { old_penalty = no_fuel_penalties_var } } } ingame_update_setup = yes }', 1)
        bad_helpers = copy.deepcopy(self.old)
        bad_helpers['energy_on_daily'] = ast(daily)
        good = Refresh(self.old, fixture(11), fixture={'fuel_k': 0, 'no_fuel_penalties_var': -.5, 'tax_law_fixture': .3})
        bad = Refresh(bad_helpers, fixture(11), fixture={'fuel_k': 0, 'no_fuel_penalties_var': -.5, 'tax_law_fixture': .3})
        good.call('energy_on_daily'); bad.call('energy_on_daily')
        self.assertGreater(len(good.visits), 0)
        self.assertEqual(len(bad.visits), 0)
        self.assertEqual(sum(k == 'calculate_tax_gain' for k, _, _ in good.delegates), 1)
        self.assertEqual(sum(k == 'calculate_tax_gain' for k, _, _ in bad.delegates), 0)
        self.assertNotEqual(good.visible(), bad.visible())

    def test_fuel_zero_to_positive_preserves_existing_recovery_and_storage_path(self):
        old = Refresh(self.old, fixture(16), fixture={'fuel_k': 0, 'no_fuel_penalties_var': 0, 'max_stored_energy': 0})
        new = Refresh(self.new, fixture(16), fixture={'fuel_k': 0, 'no_fuel_penalties_var': 0, 'max_stored_energy': 0})
        for model in (old, new):
            # Avoid ROOT-based inherited storage branch; explicit unrelated ROOT has no storage.
            model.call('energy_on_daily')
            model.variables[1]['fuel_k'] = 10
            model.call('energy_on_daily')
        self.assertEqual(old.visible(), new.visible())
        self.assertEqual(new.variables[1]['no_fuel_penalties_var'], 0)
        self.assertEqual(sum(k == 'calculate_tax_gain' for k, _, _ in new.delegates), 1)

    def test_unknown_effect_trigger_and_bad_PREV_fail_closed(self):
        model = Refresh(self.new, fixture())
        for text in ('not_native_command = yes', 'if = { limit = { not_native_trigger = yes } set_variable = { x = 1 } }'):
            with self.assertRaises(AssertionError): model.execute(ast(text))
        with self.assertRaises(AssertionError): model.execute(ast('set_variable = { PREV.x = 1 }'))

    def test_hostile_damage_mutations_are_detected(self):
        for src, dst in (('PREV.num_of_damaged_civs', 'ROOT.num_of_damaged_civs'),
                         ('damaged_building_level@industrial_complex', 'building_level@industrial_complex')):
            new = copy.deepcopy(self.new)
            raw = (ROOT / 'common/scripted_effects/eon_economy_state_refresh_effects.txt').read_text(encoding='utf-8-sig')
            self.assertIn(src, raw)
            raw = raw.replace(src, dst, 1)
            new.update({k: v for k, op, v in ast(raw)})
            good, _ = self.pair(fixture(17))
            bad = Refresh(new, fixture(17))
            bad.call('eon_economy_refresh_state_and_damage')
            self.assertNotEqual(good.visible(), bad.visible())


    def test_current_budget_and_daily_control_flow_retains_all_original_calls(self):
        current = list(self.new["ingame_update_setup"])
        assert current[0] == ("eon_economy_refresh_state_and_damage", "=", "yes")
        restored = [("calculate_damaged_buildings_count", "=", "yes"), ("update_state_variables", "=", "yes")] + current[1:]
        self.assertEqual(restored, self.old["ingame_update_setup"])
        self.assertEqual(self.new["energy_on_daily"], self.old["energy_on_daily"])


    def test_current_combined_body_is_only_exact_original_islands_commuted(self):
        damage = one(self.old["calculate_damaged_buildings_count"], "hidden_effect")
        state = self.old["update_state_variables"]
        di = next(i for i,n in enumerate(damage) if n[0] == "every_controlled_state")
        si = next(i for i,n in enumerate(state) if n[0] == "hidden_effect")
        hidden = state[si][2]
        li = next(i for i,n in enumerate(hidden) if n[0] == "every_controlled_state")
        expected = [("hidden_effect", "=", damage[:di])] + state[:si]
        expected += [("hidden_effect", "=", hidden[:li] + [("every_controlled_state", "=", damage[di][2] + hidden[li][2])] + damage[di+1:])]
        expected += state[si+1:]
        self.assertEqual(self.new["eon_economy_refresh_state_and_damage"], expected)


if __name__ == "__main__": unittest.main(verbosity=2)
