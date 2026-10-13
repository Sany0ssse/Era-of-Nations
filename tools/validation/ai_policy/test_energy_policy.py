"""Execute actual energy-policy AI weights and draft preparation AST.

Native selection, GUI scheduling, callbacks and a campaign are not simulated.
Supplied country facts and nearest rounding are explicit boundary inputs;
unknown visited script nodes fail instead of silently becoming true.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import sys
import unittest

from energy_byte_compat import CATALOG, negative_controls, restore_energy_ai

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/validation/diplomacy_package_03'))
from _support import ast, one, compare

GUI = 'common/scripted_guis/01_energy_gui.txt'
ACTION = 'common/scripted_diplomatic_actions/MDDC_energy_contract_scripted_diplomatic_actions.txt'
HOOK = 'common/on_actions/00_ai_gui_on_actions.txt'
POLICY_TRIGGER = 'common/scripted_triggers/eon_energy_ai_policy_triggers.txt'
POLICIES = ('heavy_power_restrictions', 'some_power_restrictions', 'no_power_rules',
            'some_additional_consumption', 'heavy_additional_consumption')


def load(path):
    return ast((ROOT / path).read_bytes())


class Model:
    def __init__(self, ratio=1.0, ideas=(), opinion=80, war=False, base_coefficient=1.0, export_demand=0.0, global_use=0.0):
        self.countries = {
            1: {'variables': {'energy_balance_value_display': ratio}, 'ideas': set(ideas),
                'flags': set(), 'arrays': {}, 'opinion': opinion, 'war': war,
                'ai': True, 'original_tag': 'GEN', 'base_coefficient': base_coefficient},
            2: {'variables': {}, 'ideas': set(), 'flags': set(), 'arrays': {},
                'opinion': opinion, 'war': war, 'ai': True, 'original_tag': 'GEN'},
        }
        self.root, self.temp, self.external = 1, {}, []
        self.global_use = global_use
        source_ideas = one(one(load('common/ideas/AA_Energy.txt'), 'ideas'), 'hidden_ideas')
        self.deltas = {name + '_spirit': float(one(one(one(source_ideas, name + '_spirit'), 'modifier'), 'energy_use_multiplier'))
                       for name in POLICIES if name != 'no_power_rules'}
        self.refresh_supply(ratio=ratio, exports=export_demand)
        gui = one(one(load(GUI), 'scripted_gui'), 'energy_scripted_gui')
        self.weights = one(gui, 'ai_weights')
        self.gui_effects = one(gui, 'effects')
        self.actions = one(load(ACTION), 'scripted_diplomatic_actions')

    def refresh_supply(self, supply=None, ratio=None, exports=0.0):
        current = self.countries[1]
        coefficient = current['base_coefficient'] + self.global_use + sum(self.deltas[idea] for idea in current['ideas'])
        demand = max(.001, coefficient)
        if supply is None: supply = ratio * (demand + exports)
        current['variables'].update({
            'eon_energy_delivery_demand': demand,
            'energy_consumption': demand + exports,
            'energy_sum': supply,
            'energy_balance_value_display': supply / (demand + exports),
        })

    def country(self, token, stack):
        if token == 'ROOT': return self.root
        if token == 'THIS': return stack[-1]
        if token == 'PREV': return stack[-2]
        if token == 'PREV.PREV': return stack[-3]
        if token.startswith('var:'): return int(self.value(token[4:], stack))
        raise AssertionError(('Unknown country', token))

    def flag(self, token, stack):
        if '@' not in token: return token
        name, scope = token.split('@', 1)
        return name + '@' + str(self.country(scope, stack))

    def value(self, token, stack):
        try: return float(token)
        except ValueError: pass
        if token in ('ROOT', 'THIS', 'PREV'): return self.country(token, stack)
        if token == 'opinion@ROOT': return self.countries[stack[-1]]['opinion']
        if token == 'modifier@energy_use_multiplier':
            current = self.countries[stack[-1]]
            return current['base_coefficient'] - 1 + sum(self.deltas[idea] for idea in current['ideas'])
        if token == 'global.ai_energy_use_modifier': return self.global_use
        if token.startswith('PREV.'):
            return self.countries[self.country('PREV', stack)]['variables'].get(token[5:], 0)
        if '^' in token:
            array, index = token.split('^', 1)
            return self.countries[stack[-1]]['arrays'][array][int(self.value(index, stack))]
        return self.temp.get(token, self.countries[stack[-1]]['variables'].get(token, 0))

    def trigger(self, nodes, stack):
        result = []
        for key, op, val in nodes:
            current = self.countries[stack[-1]]
            if key == 'AND': passed = self.trigger(val, stack)
            elif key == 'OR': passed = any(self.trigger([node], stack) for node in val)
            elif key == 'NOT': passed = not self.trigger(val, stack)
            elif key in ('ROOT', 'THIS', 'PREV'):
                passed = self.trigger(val, stack + [self.country(key, stack)])
            elif key == 'has_idea': passed = val in current['ideas']
            elif key == 'has_country_flag': passed = self.flag(val, stack) in current['flags']
            elif key == 'has_dynamic_modifier': passed = one(val, 'modifier') in current.get('modifiers', set())
            elif key == 'has_war_with': passed = current['war']
            elif key == 'has_opinion':
                _, operator, bound = next(node for node in val if node[0] == 'value')
                passed = compare(current['opinion'], operator, self.value(bound, stack))
            elif key == 'original_tag': passed = current['original_tag'] == val
            elif key == 'is_ai': passed = current['ai'] == (val == 'yes')
            elif key == 'check_variable':
                name, operator, bound = val[0]
                passed = compare(self.value(name, stack), operator, self.value(bound, stack))
            elif key in ('set_temp_variable', 'multiply_temp_variable', 'add_to_temp_variable',
                         'subtract_from_temp_variable', 'divide_temp_variable', 'clamp_temp_variable'):
                self.effect([(key, op, val)], stack); passed = True
            elif key == 'eon_energy_ai_can_raise_demand':
                passed = self.trigger(one(load(POLICY_TRIGGER), key), stack) == (val == 'yes')
            elif key == 'has_active_mission': passed = False
            elif key == 'always': passed = val == 'yes'
            elif key in ('any_country', 'any_other_country'):
                passed = any(self.trigger(val, stack + [ident]) for ident in sorted(self.countries)
                             if key == 'any_country' or ident != stack[-1])
            else: raise AssertionError(('Unknown trigger', key, op, val))
            result.append(passed)
        return all(result)

    def effect(self, nodes, stack):
        index = 0
        while index < len(nodes):
            key, op, val = nodes[index]; index += 1
            current = self.countries[stack[-1]]
            if key == 'if':
                branches = [('if', val)]
                while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                    branches.append((nodes[index][0], nodes[index][2])); index += 1
                for kind, branch in branches:
                    if kind == 'else' or self.trigger(one(branch, 'limit'), stack):
                        self.effect([node for node in branch if node[0] != 'limit'], stack); break
            elif key in ('ROOT', 'PREV', 'THIS'):
                self.effect(val, stack + [self.country(key, stack)])
            elif key == 'random_country':
                # Deterministic test adapter: actual native random choice remains unvalidated.
                candidates = [ident for ident in sorted(self.countries)
                              if self.trigger(one(val, 'limit'), stack + [ident])]
                if candidates:
                    self.effect([node for node in val if node[0] != 'limit'], stack + [candidates[0]])
            elif key == 'for_each_loop':
                array, name, row = one(val, 'array'), one(val, 'value'), one(val, 'index')
                for i, value in enumerate(current['arrays'][array]):
                    self.temp[name], self.temp[row] = value, i
                    self.effect([node for node in val if node[0] not in ('array', 'value', 'index', 'break')], stack)
                    if any(k == 'break' and self.temp.get(v, 0) for k, _, v in val): break
            elif key == 'while_loop_effect':
                count = 0
                while self.trigger(one(val, 'limit'), stack):
                    count += 1; assert count < 1000, 'Unbounded test loop'
                    self.effect([node for node in val if node[0] != 'limit'], stack)
            elif key in ('set_variable', 'set_temp_variable', 'multiply_variable', 'multiply_temp_variable',
                         'add_to_variable', 'add_to_temp_variable', 'subtract_from_variable', 'subtract_from_temp_variable',
                         'divide_variable', 'divide_temp_variable'):
                name, _, amount = val[0]
                dest = self.temp if 'temp' in key else current['variables']
                number = self.value(amount, stack)
                if key.startswith('set_'): dest[name] = number
                elif key.startswith('multiply_'): dest[name] = dest.get(name, 0) * number
                elif key.startswith('divide_'): dest[name] = dest.get(name, 0) / number
                elif key.startswith('subtract_'): dest[name] = dest.get(name, 0) - number
                else: dest[name] = dest.get(name, 0) + number
            elif key in ('round_variable', 'round_temp_variable'):
                dest = self.temp if 'temp' in key else current['variables']
                dest[val] = int(dest[val] + .5)
            elif key in ('clamp_variable', 'clamp_temp_variable'):
                dest = self.temp if 'temp' in key else current['variables']
                name = one(val, 'var')
                for bound, _, limit in val:
                    if bound == 'min': dest[name] = max(dest.get(name, 0), self.value(limit, stack))
                    if bound == 'max': dest[name] = min(dest.get(name, 0), self.value(limit, stack))
            elif key in ('set_country_flag', 'clr_country_flag'):
                if key == 'set_country_flag': current['flags'].add(self.flag(val, stack))
                else: current['flags'].discard(self.flag(val, stack))
            elif key == 'clear_variable': current['variables'].pop(val, None)
            elif key == 'add_ideas': current['ideas'].add(val)
            elif key == 'remove_ideas':
                current['ideas'].difference_update(item for _, _, item in val)
            elif key in ('log', 'ingame_update_setup'):
                self.external.append(key)  # The real update runs in HOI4 only.
            elif key == 'eon_nuclear_fuel_ai_prepare_offer':
                self.external.append(key)  # Separate owned backend, not interpreted here.
            else: raise AssertionError(('Unknown effect', key, op, val))

    def score(self, nodes, stack):
        total = 1.0
        for key, _, value in nodes:
            if key == 'base': total = float(value)
            elif key == 'factor': total *= self.value(value, stack)
            elif key == 'modifier':
                conditions = [node for node in value if node[0] not in ('add', 'factor')]
                if self.trigger(conditions, stack):
                    for kind, _, amount in value:
                        if kind == 'add': total += self.value(amount, stack)
                        elif kind == 'factor': total *= self.value(amount, stack)
            else: raise AssertionError(('Unknown score statement', key))
        return total

    def scores(self):
        return {name: self.score(one(one(self.weights, name + '_button_click'), 'ai_will_do'), [1])
                for name in POLICIES}

    def draft(self):
        hooks = one(one(load(HOOK), 'on_actions'), 'on_daily')
        effect = one(hooks, 'effect')
        weekly = [val for key, _, val in effect if key == 'if'
                  and ('has_global_flag', '=', 'normal_week') in one(val, 'limit')]
        assert len(weekly) == 1
        energy = [val for key, _, val in weekly[0] if key == 'if'
                  and ('has_country_flag', '=', 'energy_main') in one(val, 'limit')]
        assert len(energy) == 1
        self.effect([('if', '=', energy[0])], [1])


class EnergyPolicy(unittest.TestCase):
    def test_severe_shortage_stops_encouraging_consumption(self):
        scores = Model(.60, ['some_additional_consumption_spirit']).scores()
        self.assertGreater(scores['heavy_power_restrictions'], 0)
        self.assertEqual(scores['some_additional_consumption'], 0)
        self.assertEqual(scores['heavy_additional_consumption'], 0)

    def test_moderate_restriction_recovery_is_reachable(self):
        scores = Model(1.25, ['heavy_power_restrictions_spirit']).scores()
        self.assertGreater(scores['some_power_restrictions'], 0)

    def test_deficit_with_rationing_does_not_drop_all_restrictions(self):
        self.assertEqual(Model(.80, ['some_power_restrictions_spirit']).scores()['no_power_rules'], 0)

    def test_lower_consumption_is_reachable_after_surplus_disappears(self):
        scores = Model(.98, ['some_additional_consumption_spirit']).scores()
        self.assertGreater(scores['no_power_rules'], 0)

    def test_current_policy_is_not_selected_again_and_no_country_forced_surplus(self):
        for name in POLICIES:
            ideas = [] if name == 'no_power_rules' else [name + '_spirit']
            model = Model(1.0, ideas); model.countries[1]['original_tag'] = 'USA'
            scores = model.scores()
            self.assertEqual(scores[name], 0, name)
            self.assertEqual(scores['some_additional_consumption'], 0)
            self.assertEqual(scores['heavy_additional_consumption'], 0)

    def test_peaceful_friendly_framework_is_not_cancelled_without_reason(self):
        model = Model(opinion=100)
        self.assertEqual(model.score(one(one(model.actions, 'cancel_energy_agreement'), 'ai_desire'), [2]), 0)

    def test_war_or_hostility_can_cancel_framework_with_nonnegative_weight(self):
        for opinion, war in ((100, True), (-100, False), (-200, False)):
            model = Model(opinion=opinion, war=war)
            self.assertGreater(model.score(one(one(model.actions, 'cancel_energy_agreement'), 'ai_desire'), [2]), 0)

    def draft_model(self, own_balance=0, other_balance=0):
        model = Model()
        model.countries[1]['flags'] = {'energy_main', 'energy_agreement@2'}
        model.countries[2]['flags'] = {'energy_agreement@1'}
        model.countries[1]['variables']['energy_balance'] = own_balance
        model.countries[2]['variables']['energy_balance'] = other_balance
        model.countries[1]['arrays'] = {'energy_contractors': [], 'energy_contracts_ammount': [], 'energy_contracts_price': []}
        model.countries[2]['arrays'] = deepcopy(model.countries[1]['arrays'])
        return model

    def test_crisis_stops_an_expense_import_and_keeps_revenue_export(self):
        model = self.draft_model()
        model.countries[1]['modifiers'] = {'very_high_interest_country_modifiers'}
        model.countries[1]['arrays'] = {'energy_contractors': [2, 3], 'energy_contracts_ammount': [-8, 4], 'energy_contracts_price': [.05, .05]}
        model.draft()
        self.assertEqual(model.countries[1]['variables']['energy_selling_selected_TAG'], 3)
        self.assertEqual(model.countries[1]['variables']['temp_energy_ammount'], 0)

    def test_import_draft_does_not_exceed_fractional_supplier_capacity(self):
        for capacity in (.3, 1.3, 17.3, 17.6, 32.0):
            model = self.draft_model(-100, capacity)
            model.draft()
            amount = model.countries[1]['variables']['temp_energy_ammount']
            self.assertEqual(amount, int(capacity))
            self.assertGreaterEqual(amount, 0)

    def test_export_draft_does_not_round_up_beyond_fractional_surplus(self):
        for capacity in (.3, 1.3, 17.3, 17.6, 32.0):
            model = self.draft_model(capacity, -100)
            model.draft()
            amount = model.countries[1]['variables']['temp_energy_ammount']
            self.assertEqual(amount, -int(capacity))

    def test_inflight_terms_are_not_replaced_by_weekly_draft_preparation(self):
        model = self.draft_model(-100, 40)
        model.countries[1]['flags'].add('question_about_contract')
        model.countries[1]['variables'].update({'energy_selling_selected_TAG': 7, 'temp_energy_ammount': 16, 'temp_energy_price': .04})
        before = deepcopy(model.countries[1]['variables'])
        model.draft()
        self.assertEqual(model.countries[1]['variables'], before)

    def test_crisis_cancellation_is_not_overwritten_by_new_paid_import(self):
        model = self.draft_model(-25, 40)
        model.countries[1]['modifiers'] = {'very_high_interest_country_modifiers'}
        model.countries[1]['arrays'] = {'energy_contractors': [2], 'energy_contracts_ammount': [8], 'energy_contracts_price': [.05]}
        model.draft()
        self.assertEqual(model.countries[1]['variables']['temp_energy_ammount'], 0)

    def test_busy_supplier_is_not_selected_for_a_new_request(self):
        model = self.draft_model(-25, 40)
        model.countries[2]['flags'].add('question_about_contract')
        model.countries[1]['variables'].update({'energy_selling_selected_TAG': 7, 'temp_energy_ammount': 16, 'temp_energy_price': .04})
        model.draft()
        self.assertEqual(model.countries[1]['variables'].get('energy_selling_selected_TAG', 0), 0)
        self.assertEqual(model.countries[1]['variables'].get('temp_energy_ammount', 0), 0)

    def test_policy_hysteresis_does_not_cycle_in_unchanged_power_supply(self):
        # Synthetic domestic-only system with no other consumption modifiers,
        # calibrated from actual idea energy_use_multiplier fields.
        source_ideas = one(one(load('common/ideas/AA_Energy.txt'), 'ideas'), 'hidden_ideas')
        deltas = {name + '_spirit': float(one(one(one(source_ideas, name + '_spirit'), 'modifier'), 'energy_use_multiplier'))
                  for name in POLICIES if name != 'no_power_rules'}
        for supply in (.4, .7, .8, .94, 1.0, 1.14, 1.26, 1.4, 1.7):
            for initial in (None, *deltas):
                model = Model(ideas=[] if initial is None else [initial])
                seen = []
                for _ in range(12):
                    state = tuple(sorted(model.countries[1]['ideas']))
                    ratio = supply / (1 + sum(deltas[idea] for idea in state))
                    model.refresh_supply(supply=supply)
                    scores = model.scores()
                    eligible = [name for name in POLICIES if scores[name] > 0]
                    if not eligible: break
                    self.assertNotIn(state, seen, (supply, initial, seen, scores))
                    seen.append(state)
                    selected = max(eligible, key=lambda name: scores[name])
                    model.effect(one(model.gui_effects, selected + '_button_click'), [1])
                else: self.fail(('No stable policy in twelve synthetic checks', supply, initial))

    def test_very_easy_difficulty_does_not_cycle_between_rationing_and_normal(self):
        # This is the real -0.50 difficulty idea, not an assumed unit base.
        source_ideas = one(one(load('common/ideas/AA_Energy.txt'), 'ideas'), 'hidden_ideas')
        difficulty = float(one(one(one(source_ideas, 'ai_energy_very_easy_difficulty'), 'modifier'), 'energy_use_multiplier'))
        deltas = {name + '_spirit': float(one(one(one(source_ideas, name + '_spirit'), 'modifier'), 'energy_use_multiplier'))
                  for name in POLICIES if name != 'no_power_rules'}
        model = Model(base_coefficient=1 + difficulty)
        seen = []
        for _ in range(12):
            state = tuple(sorted(model.countries[1]['ideas']))
            model.refresh_supply(supply=.47)
            eligible = {name: score for name, score in model.scores().items() if score > 0}
            if not eligible: break
            self.assertNotIn(state, seen, (state, seen, eligible))
            seen.append(state)
            selected = max(eligible, key=eligible.get)
            model.effect(one(model.gui_effects, selected + '_button_click'), [1])
        else: self.fail('Difficulty fixture never reached a stable policy')

    def test_demand_projection_keeps_actual_export_obligations_unscaled(self):
        model = Model(1.17, ['some_power_restrictions_spirit'], base_coefficient=.5, export_demand=4)
        self.assertGreater(model.scores()['no_power_rules'], 0)
        self.assertAlmostEqual(model.temp['eon_energy_ai_target_demand'], 4.5)

    def test_policies_stabilize_with_difficulty_global_modifiers_and_exports(self):
        source_ideas = one(one(load('common/ideas/AA_Energy.txt'), 'ideas'), 'hidden_ideas')
        difficulties = [1.0] + [1 + float(one(one(one(source_ideas, 'ai_energy_' + level + '_difficulty'), 'modifier'), 'energy_use_multiplier'))
                               for level in ('very_easy', 'easy', 'hard', 'very_hard')]
        for base in difficulties:
            for global_use in (-.25, 0.0, .25):
                for exports in (0.0, 2.0):
                    for initial in (None, *self.deltas_for_tests(source_ideas)):
                        for initial_ratio in (.60, .80, .94, 1.01, 1.26, 1.40):
                            model = Model(initial_ratio, [] if initial is None else [initial],
                                          base_coefficient=base, export_demand=exports, global_use=global_use)
                            supply = model.countries[1]['variables']['energy_sum']
                            seen = []
                            for _ in range(12):
                                state = tuple(sorted(model.countries[1]['ideas']))
                                model.refresh_supply(supply=supply, exports=exports)
                                scores = {name: score for name, score in model.scores().items() if score > 0}
                                if not scores: break
                                self.assertNotIn(state, seen, (base, global_use, exports, initial_ratio, seen, scores))
                                seen.append(state)
                                model.effect(one(model.gui_effects, max(scores, key=scores.get) + '_button_click'), [1])
                            else: self.fail(('Unstable policy', base, global_use, exports, initial_ratio))

    @staticmethod
    def deltas_for_tests(source_ideas):
        return {name + '_spirit': float(one(one(one(source_ideas, name + '_spirit'), 'modifier'), 'energy_use_multiplier'))
                for name in POLICIES if name != 'no_power_rules'}


class EnergySourceOwnership(unittest.TestCase):
    def test_exact_owned_islands_restore_all_other_source_bytes(self):
        for path, patch in CATALOG.items():
            raw = (ROOT / path).read_bytes()
            projected = restore_energy_ai(path, raw)
            self.assertEqual(hashlib.sha256(projected).hexdigest(), patch['before_file_sha256'], path)
            self.assertEqual(raw.startswith(b'\xef\xbb\xbf'), projected.startswith(b'\xef\xbb\xbf'), path)
            self.assertEqual(raw.count(b'\r\n'), projected.count(b'\r\n'), path)

    def test_changed_missing_duplicate_and_unrelated_mutations_are_not_allowed(self):
        self.assertEqual(sum(len(negative_controls(path, (ROOT / path).read_bytes())) for path in CATALOG), 12)

    def test_shared_projection_has_no_persistent_gameplay_side_effects(self):
        permitted = {'set_temp_variable', 'add_to_temp_variable', 'subtract_from_temp_variable',
                     'multiply_temp_variable', 'divide_temp_variable', 'clamp_temp_variable', 'check_variable'}
        nodes = one(load(POLICY_TRIGGER), 'eon_energy_ai_can_raise_demand')
        self.assertTrue(all(key in permitted for key, _, _ in nodes))
        self.assertEqual(len([key for key, _, _ in nodes if key == 'check_variable']), 2)


if __name__ == '__main__':
    unittest.main()
