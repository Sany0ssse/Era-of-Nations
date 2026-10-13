"""Bounded execution of actual EU vote AST; native acceptance is separate."""
from pathlib import Path
from copy import deepcopy
import os
import sys
import unittest

ROOT = Path(os.environ.get('EON_WORKSPACE_ROOT', Path(__file__).resolve().parents[3])).resolve()
SOURCE = ROOT

def source_path(name, source=None):
    selected = SOURCE if source is None else source
    path = selected / name
    return path if path.exists() else ROOT / name
sys.path.insert(0, str(ROOT / 'tools/validation/migration_relief'))
from test_flows import Model, Country, State, ast, one


class VoteModel(Model):
    def __init__(self, count=10, source=None):
        self.source = SOURCE if source is None else source
        countries = {i: Country(i) for i in range(1, count + 2)}
        states = {100 + i: State(100 + i, 100000, i, i, {i}) for i in countries}
        super().__init__(countries, states)
        for filename in ('common/scripted_effects/eon_eu_voting_effects.txt', 'common/scripted_effects/eon_eu_handoff_effects.txt'):
            path = source_path(filename, self.source)
            if path.exists():
                self.effects.update({k: v for k, op, v in ast(path.read_text(encoding='utf-8-sig'))})
        self.effects['update_eu_dirty_variable'] = one(ast((ROOT / 'common/scripted_effects/00_eu_scripted_effects.txt').read_text(encoding='utf-8-sig')), 'update_eu_dirty_variable')
        self.triggers.update({k: v for k, op, v in ast((ROOT / 'common/scripted_triggers/99_EU_voting_scripted_triggers.txt').read_text(encoding='utf-8-sig'))})
        for filename in ('common/scripted_triggers/eon_eu_membership_triggers.txt', 'common/scripted_triggers/eon_eu_voting_triggers.txt', 'common/scripted_triggers/eon_eu_handoff_triggers.txt'):
            path = source_path(filename, self.source)
            if path.exists():
                self.triggers.update({k: v for k, op, v in ast(path.read_text(encoding='utf-8-sig'))})
        self.global_arrays['EU_member'] = [countries[i].pointer for i in range(1, count + 1)]
        # Declared valid open round: threshold regressions exercise actual ballot guards.
        self.global_vars.update(EU_member_count=count, current_active_vote_disp=401,
                                EUXXX_council_agenda=401, eon_eu_council_round_agenda=401,
                                eon_eu_council_vote_instance=1)
        self.global_flags.update(('eon_eu_council_vote_clock_started', 'eon_eu_council_vote_deadline'))
        for i in range(1, count + 1):
            countries[i].ideas.add('EU_member')
        self.count = count

    def trigger(self, nodes, stack):
        index = 0
        while index < len(nodes):
            key, op, value = nodes[index]
            index += 1
            if key == 'tooltip': continue
            if key == 'if':
                branches, index = self.branches(nodes, index, value)
                passed = True
                for kind, branch in branches:
                    if kind == 'else' or self.trigger(one(branch, 'limit'), stack):
                        passed = self.trigger([n for n in branch if n[0] != 'limit'], stack)
                        break
                if not passed: return False
            elif key == 'divide_temp_variable':
                self.effect([(key, op, value)], stack)
            elif key == 'is_in_array':
                name = one(value, 'array') if any(k == 'array' for k, _, _ in value) else value[0][0]
                item = one(value, 'value') if any(k == 'array' for k, _, _ in value) else value[0][2]
                arrays = self.global_arrays if name.startswith('global.') else stack[-1].arrays
                if self.value(item, stack) not in arrays.get(name.removeprefix('global.'), []): return False
            elif key == 'is_subject':
                if getattr(stack[-1], 'subject', False) != (value == 'yes'): return False
            elif key == 'num_of_owned_states':
                from test_flows import compare
                owned = sum(s.owner == stack[-1].ident for s in self.states.values())
                if not compare(owned, op, self.value(value, stack)): return False
            elif not super().trigger([(key, op, value)], stack): return False
        return True

    def effect(self, nodes, stack):
        index = 0
        while index < len(nodes):
            key, op, value = nodes[index]
            index += 1
            if key == 'hidden_effect':
                self.effect(value, stack)
            elif key == 'for_each_scope_loop':
                name = one(value, 'array')
                arrays = self.global_arrays if name.startswith('global.') else stack[-1].arrays
                for pointer in list(arrays.get(name.removeprefix('global.'), [])):
                    target = next((c for c in self.countries.values() if c.pointer == pointer), None)
                    if target is not None:
                        super().effect([n for n in value if n[0] != 'array'], stack + [target])
            elif key in ('remove_from_array', 'clear_array'):
                name = value if key == 'clear_array' else one(value, 'array')
                arrays = self.global_arrays if name.startswith('global.') else stack[-1].arrays
                if key == 'clear_array': arrays[name.removeprefix('global.')] = []
                else:
                    item = self.value(one(value, 'value'), stack)
                    arrays[name.removeprefix('global.')] = [x for x in arrays.get(name.removeprefix('global.'), []) if x != item]
            elif key == 'add_to_array' and not any(k == 'array' for k, _, _ in value):
                name, _, item = value[0]
                super().effect([(key, op, [('array', '=', name), ('value', '=', item)])], stack)
            else:
                # Keep a complete adjacent if/else chain for the real dispatcher.
                group = [(key, op, value)]
                if key == 'if':
                    while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                        group.append(nodes[index])
                        index += 1
                super().effect(group, stack)

    def required(self, name):
        if name not in self.effects: raise AssertionError('Missing production helper: ' + name)
        self.run(name, self.root.ident)

    def ballot(self, yes, no=()):
        self.global_arrays['EU_active_vote_supporters'] = [self.countries[i].pointer for i in yes]
        self.global_arrays['EU_active_vote_rejecters'] = [self.countries[i].pointer for i in no]
        self.required('eon_eu_recount_council_vote')

    def passed(self):
        return self.trigger(self.triggers['EU_voting_decision_result_trigger'], [self.root])


class VoteRegressions(unittest.TestCase):
    def test_abstention_does_not_reduce_member_denominator(self):
        model = VoteModel(10)
        model.global_vars.update(EU_active_vote_yes=1, EU_active_vote_no=0, EU_pop_ratio_yes=.7,
                                eon_eu_voters=10, eon_eu_yes_fraction=.1, eon_eu_opposing_members=9)
        self.assertFalse(model.passed())

    def test_exact_55_percent_states_and_65_percent_population_pass(self):
        model = VoteModel(20)
        model.global_vars.update(EU_active_vote_yes=11, EU_active_vote_no=9, EU_pop_ratio_yes=.65,
                                eon_eu_voters=20, eon_eu_yes_fraction=.55, eon_eu_opposing_members=9)
        self.assertTrue(model.passed())

    def test_one_ballot_per_country_even_if_legacy_array_contains_duplicates(self):
        model = VoteModel(10)
        model.ballot([1, 1, 1], [2])
        self.assertEqual(model.global_vars['EU_active_vote_yes'], 1)
        self.assertEqual(model.global_vars['EU_active_vote_no'], 1)

    def test_nonmember_ballot_and_population_are_excluded(self):
        model = VoteModel(10)
        model.states[111].population = 9000000
        model.ballot([1, 11], [2])
        self.assertEqual(model.global_vars['EU_active_vote_yes'], 1)
        self.assertAlmostEqual(model.global_vars['EU_pop_ratio_yes'], .1)

    def test_extinct_and_suspended_members_lose_ballot_and_denominator(self):
        model = VoteModel(10)
        model.countries[1].exists = False
        model.countries[2].ideas.add('EUU_voting_rights_suspended')
        model.ballot([1, 2, 3], [4])
        self.assertEqual(model.global_vars['EU_active_vote_yes'], 1)
        self.assertEqual(model.global_vars['eon_eu_voters'], 8)
        self.assertAlmostEqual(model.global_vars['EU_pop_ratio_yes'], .125)

    def test_repeated_support_is_idempotent_and_switching_replaces_ballot(self):
        model = VoteModel(10)
        model.required('eon_eu_support_council_vote')
        model.required('eon_eu_support_council_vote')
        self.assertEqual(model.global_vars['EU_active_vote_yes'], 1)
        model.required('eon_eu_reject_council_vote')
        model.required('eon_eu_reject_council_vote')
        self.assertEqual(model.global_vars['EU_active_vote_yes'], 0)
        self.assertEqual(model.global_vars['EU_active_vote_no'], 1)

    def test_outsider_cannot_use_vote_callback(self):
        model = VoteModel(10)
        model.root = model.countries[11]
        model.required('eon_eu_support_council_vote')
        self.assertEqual(model.global_vars.get('EU_active_vote_yes', 0), 0)

    def test_no_current_agenda_prevents_vote_callback(self):
        model = VoteModel(10)
        model.global_vars['current_active_vote_disp'] = 0
        model.required('eon_eu_support_council_vote')
        self.assertEqual(model.global_vars.get('EU_active_vote_yes', 0), 0)

    def test_all_abstentions_fail_without_division_by_zero(self):
        model = VoteModel(10)
        model.ballot([])
        self.assertFalse(model.passed())

    def test_empty_union_fails_without_division_by_zero(self):
        model = VoteModel(0)
        model.ballot([])
        self.assertFalse(model.passed())

    def test_blocking_minority_requires_four_members(self):
        model = VoteModel(10)
        for i in range(1, 8): model.states[100 + i].population = 10000
        for i in range(8, 11): model.states[100 + i].population = 1000000
        model.ballot(range(1, 8), range(8, 11))
        self.assertTrue(model.passed())
        model.ballot(range(1, 7), range(7, 11))
        self.assertFalse(model.passed())

    def test_population_weight_uses_residents_not_recruitable_manpower(self):
        model = VoteModel(10)
        model.countries[1].variables['max_manpower_k'] = 999999
        model.ballot([1])
        self.assertAlmostEqual(model.global_vars['EU_pop_ratio_yes'], .1)

    def test_treaty_reform_cannot_pass_with_ordinary_qmv(self):
        model = VoteModel(10)
        model.global_vars.update(current_active_vote_disp=104, EUXXX_council_agenda=104,
                                eon_eu_council_round_agenda=104)
        model.ballot(range(1, 9), [9, 10])
        self.assertFalse(model.passed())

    def test_explicit_abstention_does_not_veto_unanimity(self):
        model = VoteModel(10)
        model.global_vars.update(current_active_vote_disp=104, EUXXX_council_agenda=104,
                                eon_eu_council_round_agenda=104)
        model.global_arrays['eon_eu_council_abstainers'] = [model.countries[i].pointer for i in range(2, 11)]
        model.ballot([1])
        self.assertTrue(model.passed())

    def test_unanswered_member_does_not_silently_ratify_treaty(self):
        model = VoteModel(10)
        model.global_vars.update(current_active_vote_disp=104, EUXXX_council_agenda=104,
                                eon_eu_council_round_agenda=104)
        model.ballot(range(1, 10))
        self.assertFalse(model.passed())

    def test_removed_member_ballot_is_purged_before_later_reentry(self):
        model = VoteModel(10)
        model.ballot([1, 2])
        model.countries[2].ideas.remove('EU_member')
        model.required('eon_eu_recount_council_vote')
        model.countries[2].ideas.add('EU_member')
        model.required('eon_eu_recount_council_vote')
        self.assertEqual(model.global_vars['EU_active_vote_yes'], 1)


if __name__ == '__main__': unittest.main(verbosity=2)
