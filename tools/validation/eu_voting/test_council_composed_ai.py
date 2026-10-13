"""Composed Council/frontend AST and actual parent literal AI dispatcher.

Legacy agenda-specific political weight calculation remains an opaque input;
the exact selected production helper is recorded and its declared sign is
returned. Round creation, authority, vote gates and recount are actual AST.
"""
from copy import deepcopy
from pathlib import Path
import json, re, unittest
from test_council_frontend import FrontModel, P, ROOT, HERE, ast, one, AGENDA_IDS

LEGACY = {k: v for k, _, v in ast((ROOT / 'common/scripted_effects/99_EU_voting_scripted_effects.txt').read_text('utf-8-sig')) if re.fullmatch(r'EU_update_AI_focus_EU\d+_voting_modifier', k)}

class ComposedDispatch(FrontModel):
    def __init__(self, weight=1, agenda=101):
        super().__init__()
        self.calls, self.weight = [], weight
        self.temp['v'] = agenda
        self.click(P)  # Actual guarded proposal stamps canonical round/window.
        for i in (2, 3): self.countries[i].ai = True

    def effect(self, nodes, stack):
        if len(nodes) == 1 and nodes[0][0] in LEGACY:
            self.calls.append((stack[-1].ident, nodes[0][0]))
            self.temp['EU_AI_focus_modifier_yes_vote'] = self.weight
            return
        return super().effect(nodes, stack)

class ComposedAiRegressions(unittest.TestCase):
    def test_every_supported_numeric_agenda_selects_exact_existing_policy_once(self):
        model = ComposedDispatch()
        numbers = AGENDA_IDS
        self.assertEqual(len(set(numbers)), 47)
        for number in numbers:
            with self.subTest(number=number):
                model.calls.clear()
                model.global_vars['current_active_vote_disp'] = number
                model.required('eon_eu_set_current_agenda_ai_weights')
                expected = f'EU_update_AI_focus_EU{number}_voting_modifier'
                self.assertIn(expected, LEGACY)
                self.assertEqual(model.calls, [(model.root.ident, expected)])

    def test_unknown_numeric_agenda_clears_stale_weight(self):
        for agenda in (0, 999, -1):
            model = ComposedDispatch(); model.temp['EU_AI_focus_modifier_yes_vote'] = 500
            model.global_vars['current_active_vote_disp'] = agenda
            model.required('eon_eu_set_current_agenda_ai_weights')
            self.assertEqual(model.calls, [])
            self.assertEqual(model.temp['EU_AI_focus_modifier_yes_vote'], 0)

    def test_actual_valid_round_positive_pulse_votes_and_skips_humans(self):
        model = ComposedDispatch(1)
        model.required('eon_eu_council_ai_pulse')
        self.assertEqual(model.calls, [(2, 'EU_update_AI_focus_EU101_voting_modifier'), (3, 'EU_update_AI_focus_EU101_voting_modifier')])
        self.assertEqual(model.global_vars['EU_active_vote_yes'], 2)
        self.assertEqual(model.global_vars['EU_active_vote_no'], 0)

    def test_actual_valid_round_negative_policy_votes_no(self):
        model = ComposedDispatch(-1, agenda=401)
        model.required('eon_eu_council_ai_pulse')
        self.assertEqual([key for _, key in model.calls], ['EU_update_AI_focus_EU401_voting_modifier'] * 2)
        self.assertEqual(model.global_vars['EU_active_vote_yes'], 0)
        self.assertEqual(model.global_vars['EU_active_vote_no'], 2)

    def test_repeated_actual_pulse_has_one_ballot_per_actor(self):
        model = ComposedDispatch(); model.required('eon_eu_council_ai_pulse')
        before = deepcopy(model.global_arrays)
        model.required('eon_eu_council_ai_pulse')
        self.assertEqual(model.global_arrays, before)
        self.assertEqual(model.global_vars['EU_active_vote_yes'], 2)
        self.assertEqual(len(model.calls), 2)

    def test_suspended_ai_and_outsider_never_receive_policy_call(self):
        model = ComposedDispatch(); model.countries[3].ideas.add('EUU_voting_rights_suspended')
        model.countries[7].ai = True
        model.required('eon_eu_council_ai_pulse')
        self.assertEqual([actor for actor, _ in model.calls], [2])

    def test_swapped_literal_policy_mutant_is_detected(self):
        model = ComposedDispatch()
        branch = next(v for k, _, v in model.effects['eon_eu_set_current_agenda_ai_weights'] if k == 'if')
        self.assertEqual(branch[-1][0], 'EU_update_AI_focus_EU101_voting_modifier')
        branch[-1] = ('EU_update_AI_focus_EU102_voting_modifier', '=', 'yes')
        model.required('eon_eu_set_current_agenda_ai_weights')
        self.assertNotEqual(model.calls, [(model.root.ident, 'EU_update_AI_focus_EU101_voting_modifier')])

    def test_expired_or_changed_round_never_routes_ai_policy_or_casts(self):
        for mode in ('expired', 'changed'):
            model = ComposedDispatch()
            if mode == 'expired': model.global_flags.discard('eon_eu_council_vote_deadline')
            else: model.global_vars.update(current_active_vote_disp=401, EUXXX_council_agenda=401)
            before = deepcopy(model.global_arrays)
            model.required('eon_eu_council_ai_pulse')
            self.assertEqual(model.calls, [])
            self.assertEqual(model.global_arrays, before)

if __name__ == '__main__': unittest.main(verbosity=2)
