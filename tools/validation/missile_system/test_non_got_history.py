"""Verify deterministic history projection and bounded native entry point."""
import copy
import unittest

from generate_non_got_history import (
    ACTION, DESTINATION, EFFECT, FLAG, ROOT, action_text, records, render,
)
from test_research import ast, get


class NonGotHistory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = records()
        cls.effects = ast((ROOT / DESTINATION).read_text(encoding='utf-8-sig'))

    def test_generated_effect_and_startup_equal_current_source_projection(self):
        self.assertEqual((ROOT / DESTINATION).read_text(encoding='utf-8-sig'), render(self.rows))
        self.assertEqual((ROOT / ACTION).read_text(encoding='utf-8-sig'), action_text())
        self.assertNotIn(b'\xef\xbb\xbf', (ROOT / DESTINATION).read_bytes())
        self.assertNotIn(b'\xef\xbb\xbf', (ROOT / ACTION).read_bytes())

    def test_effect_is_bounded_to_no_got_initial_scenario_and_exactly_once(self):
        gated = get(get(self.effects, EFFECT), 'if')
        self.assertEqual(get(gated, 'limit'), [
            ('NOT', '=', [('has_dlc', '=', 'Gotterdammerung')]), ('date', '<', '2000.1.2'),
        ])
        countries = [nodes for key, _, nodes in gated if key == 'if']
        self.assertEqual(len(countries), len(self.rows))
        for row, country in zip(self.rows, countries):
            self.assertEqual(get(country, 'limit'), [('tag', '=', row['tag'])])
            init = get(country, 'if')
            self.assertEqual(get(init, 'limit'), [
                ('exists', '=', 'yes'), ('NOT', '=', [('has_country_flag', '=', FLAG)]),
            ])
            self.assertEqual(get(init, 'set_country_flag'), FLAG)
            self.assertEqual(get(init, 'complete_special_project'), 'sp:sp_missile_project_non_got')
            actual = get(init, 'set_technology')
            self.assertEqual({key for key, _, value in actual if value == '1'}, set(row['techs'] + row['hidden']))
            if row['launchers'] is not None:
                self.assertEqual(get(get(init, 'set_variable'), 'num_launchers_set'), str(row['launchers']))
            else:
                self.assertIsNone(get(init, 'set_variable'))

    def test_startup_enters_country_scope_before_country_helper(self):
        actions = ast(action_text())
        effect = get(get(get(actions, 'on_actions'), 'on_startup'), 'effect')
        self.assertEqual(effect, [('every_country', '=', [(EFFECT, '=', 'yes')])])

    def test_representative_country_levels_match_initial_history(self):
        rows = {row['tag']: row for row in self.rows}
        self.assertEqual(len(rows), 28)
        self.assertEqual(sum('GLCM_non_got' in row['techs'] for row in self.rows), 24)
        for tag, final in (('USA', 4), ('GER', 4), ('BRA', 2), ('NKO', 3), ('RAJ', 1)):
            with self.subTest(tag=tag):
                glcm = {key for key in rows[tag]['techs'] if key.startswith('GLCM')}
                self.assertEqual(glcm, {'GLCM_non_got'} | {f'GLCM{level}_non_got' for level in range(1, final+1)})
        self.assertIn('SAM0_non_got', rows['UKR']['techs'])
        self.assertNotIn('GLCM_non_got', rows['UKR']['techs'])
        self.assertEqual(rows['UKR']['hidden'], [])

    def test_no_future_nuclear_missile_stockpile_or_additive_launcher_grants(self):
        text = render(self.rows)
        for forbidden in ('ICBM', 'NIRBM', 'ballistic_missile', 'add_to_variable',
                          'add_building_construction', 'add_equipment', 'add_to_stockpile',
                          'sp_nuclear_warhead_program', '2005', '2015', 'HSCM'):
            self.assertNotIn(forbidden, text)
        self.assertNotIn('add_missile_building_level', text)

    def test_source_changed_grant_breaks_generated_binding(self):
        altered = copy.deepcopy(self.rows)
        altered[0]['techs'].append('GLCM8_non_got')
        self.assertNotEqual(render(altered), render(self.rows))
        altered = copy.deepcopy(self.rows)
        altered[0]['sha256'] = '0' * 64
        self.assertNotEqual(render(altered), render(self.rows))


if __name__ == '__main__':
    unittest.main(verbosity=2)
