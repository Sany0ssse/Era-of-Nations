"""Source contracts for an OBS-only private no-DLC faction-marker diagnostic."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/validation/diplomacy_package_02'))
from _treaty_support import ast, one
from faction_identity_diagnostic import build_diagnostic


def walk(nodes):
    for key, op, value in nodes:
        yield key, op, value
        if isinstance(value, list):
            yield from walk(value)


class DiagnosticContracts(unittest.TestCase):
    def setUp(self):
        self.d = build_diagnostic('eon_private_identity_test', 'EON_PRIVATE_ID')
        self.goal = self.d['contract']['goal_id']
        self.control = self.d['contract']['visible_control_goal_id']

    def events(self):
        text = next(text for path, text in self.d['fixture_text'].items() if path.startswith('events/'))
        return {one(body, 'id'): body for key, op, body in ast(text) if key == 'country_event'}

    def test_exact_unique_private_event_range_and_entry(self):
        self.assertEqual(set(self.events()), {f'eon_private_identity_test.{n}' for n in range(1000, 1005)})
        self.assertEqual(self.d['entry_event_id'], 1000)
        self.assertEqual(self.d['terminal_event_id'], 1004)
        self.assertIn('id = eon_private_identity_test.1000 hours = 2', self.d['entry_effect'])

    def test_every_event_hidden_triggered_only(self):
        for event in self.events().values():
            self.assertEqual(one(event, 'hidden'), 'yes')
            self.assertEqual(one(event, 'is_triggered_only'), 'yes')

    def test_goals_are_never_completing_zero_ai_and_distinct_visibility(self):
        text = next(text for path, text in self.d['fixture_text'].items() if '/goals/' in path)
        goals = ast(text)
        self.assertEqual({key for key, op, value in goals}, {self.goal, self.control})
        for ident, visibility in ((self.goal, 'no'), (self.control, 'yes')):
            body = one(goals, ident)
            self.assertEqual(one(body, 'category'), 'medium_term')
            self.assertEqual(one(one(body, 'visible'), 'always'), visibility)
            self.assertEqual(one(one(body, 'available'), 'always'), 'yes')
            self.assertEqual(one(one(body, 'completed'), 'always'), 'no')
            self.assertEqual(one(one(body, 'cancel'), 'always'), 'no')
            self.assertEqual(one(one(body, 'ai_will_do'), 'factor'), '0')

    def test_observations_unique_and_no_unsupported_automatic_pass(self):
        self.assertTrue(self.d['diagnostic_only'])
        self.assertEqual(len(self.d['observations']), len(set(self.d['observations'])))
        self.assertGreater(len(self.d['observations']), 30)
        for text in self.d['fixture_text'].values():
            self.assertNotIn('EON_PRIVATE_ID PASS ', text)
            self.assertNotIn('EON_PRIVATE_ID FAIL ', text)
            self.assertNotIn('eon_native_eu_probe_passes', text)
            self.assertNotIn('eon_native_eu_probe_fails', text)

    def test_four_future_events_use_twelve_hour_delays(self):
        event_calls = [value for body in self.events().values() for key, op, value in walk(one(body, 'immediate')) if key == 'country_event']
        self.assertEqual(len(event_calls), 4)
        self.assertTrue(all(one(value, 'hours') == '12' for value in event_calls))

    def test_positive_one_day_witness_not_manually_cleared(self):
        nodes = [node for body in self.events().values() for node in walk(one(body, 'immediate'))]
        flags = [value for key, op, value in nodes if key == 'set_global_flag']
        self.assertEqual(len(flags), 1)
        self.assertEqual(one(flags[0], 'days'), '1')
        self.assertEqual(one(flags[0], 'value'), '1')
        self.assertFalse(any(key == 'clr_global_flag' for key, op, value in nodes))

    def test_date_capture_and_each_phase_advancement_are_explicit(self):
        text = next(text for path, text in self.d['fixture_text'].items() if path.startswith('events/'))
        self.assertIn('eon_private_edu_diag_start_date = global.date', text)
        self.assertIn('value = global.eon_private_edu_diag_previous_date compare = greater_than', text)
        self.assertEqual(text.count('eon_private_edu_diag_previous_date = global.date'), 5)

    def test_native_mutations_have_actual_membership_guards(self):
        events = self.events()
        for number, effect in ((1000, 'add_faction_goal'), (1001, 'set_faction_leader'),
                               (1002, 'dismantle_faction'), (1003, 'create_faction_from_template')):
            body = one(events[f'eon_private_identity_test.{number}'], 'immediate')
            found = [value for key, op, value in walk(body) if key == 'if' and effect in {k for k, o, v in walk(value)}]
            self.assertTrue(found)
            self.assertTrue(any('is_in_faction' in {k for k, o, v in walk(one(value, 'limit'))} for value in found))

    def test_localization_bom_ids_and_fixture_paths_are_private(self):
        paths = self.d['fixture_text']
        self.assertEqual(len(paths), 4)
        for language in ('english', 'russian'):
            text = next(text for path, text in paths.items() if path.startswith(f'localisation/{language}/'))
            self.assertTrue(text.startswith('\ufeffl_' + language + ':'))
            for ident in (self.goal, self.control):
                self.assertIn(f' {ident}_name:', text)
                self.assertIn(f' {ident}_desc:', text)
        self.assertTrue(all('eon_private_identity_test_faction_identity_diagnostic' in path for path in paths))
        self.assertTrue(all(ident.startswith('eon_private_identity_test_') for ident in (self.goal, self.control)))

    def test_terminal_is_only_emitted_after_last_diagnostic_event(self):
        d = build_diagnostic('eon_private_identity_test', 'EON_PRIVATE_ID', terminal_effect='log = "CORE TERMINAL"')
        text = next(text for path, text in d['fixture_text'].items() if path.startswith('events/'))
        events = [value for key, op, value in ast(text) if key == 'country_event']
        for event in events[:-1]:
            self.assertNotIn('CORE TERMINAL', str(event))
        self.assertIn('CORE TERMINAL', str(events[-1]))

    def test_diagnostic_verdict_requires_effect_outcomes_not_only_preconditions(self):
        contract = self.d['contract']
        positive, negative = contract['structure_positive_labels'], contract['structure_negative_labels']
        self.assertIn('EDU_GOAL_DIAG_AFTER_TRANSFER_POL_LEADER', positive)
        self.assertIn('EDU_GOAL_DIAG_AFTER_TRANSFER_USA_LEADER', negative)
        self.assertIn('EDU_GOAL_DIAG_AFTER_DISMANTLE_USA_IN_FACTION', negative)
        self.assertIn('EDU_GOAL_DIAG_AFTER_DISMANTLE_WAIT_POL_IN_FACTION', negative)
        self.assertIn('EDU_GOAL_DIAG_AFTER_RECREATE_SHARED_FACTION', positive)
        self.assertIn('EDU_GOAL_DIAG_FINAL_USA_LEADER', positive)
        labels = positive + negative + contract['natural_flag_positive_labels'] + contract['natural_flag_negative_labels']
        self.assertTrue(set(labels).issubset(self.d['observations']))
        self.assertFalse(set(positive).intersection(negative))

    def test_namespace_marker_and_terminal_reject_injection(self):
        for namespace, marker in (('bad"namespace', 'OK'), ('OK', 'bad"marker'), ('OK', 'bad\nmarker')):
            with self.assertRaises(ValueError):
                build_diagnostic(namespace, marker)


if __name__ == '__main__':
    unittest.main()
