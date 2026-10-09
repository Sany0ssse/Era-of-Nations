"""Narrow source integration checks; these do not replace a native campaign."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'tools/validation/diplomacy_package_02'))
from _treaty_support import ast

def source(relative):
    return (ROOT/relative).read_text(encoding='utf-8-sig')

class Integration(unittest.TestCase):
    def test_weekly_relief_precedes_economy_and_monthly_has_single_owner(self):
        weekly = source('common/on_actions/01_on_actions.txt')
        self.assertLess(weekly.index('eon_migration_relief_weekly = yes'), weekly.index('ingame_update_setup = yes'))
        retired = source('common/on_actions/00_migrants_on_actions.txt')
        self.assertEqual(retired.count('eon_migration_monthly_pulse = yes'), 1)
        self.assertNotIn('add_manpower', retired)
        self.assertNotIn('migrants_add', retired)

    def test_economy_has_no_second_people_or_private_remittance_credit(self):
        money = source('common/scripted_effects/00_money_system.txt')
        self.assertEqual(money.count('set_variable = { migrant_workforce_add = 0 }'), 1)
        self.assertTrue('subtract_from_temp_variable = { workforce_total = eon_refugee_workforce_delay_m }' in money)
        self.assertIn('set_variable = { adding_migrants_income = 0 }', money)
        self.assertNotIn('set_variable = { adding_migrants_income = migrants_cut }', money)
        self.assertTrue('add_to_variable = { additional_expenses_rate = eon_refugee_weekly_net_cost }' in money)
        self.assertTrue('add_to_variable = { additional_expenses_rate = eon_refugee_capacity_weekly_cost }' in money)
        dynamic = dict((key,value) for key,_,value in ast(source('common/dynamic_modifiers/0_dynamic_modifiers.txt')))
        migration = dynamic['migration_rate_impact_effect']
        self.assertFalse(any(key == 'monthly_population' for key,_,_ in migration))
        self.assertTrue(any(key == 'custom_modifier_tooltip' and value == 'eon_migration_population_flow_tt' for key,_,value in migration))

    def test_population_growth_constant_and_nested_capital_scope(self):
        growth = re.search(r'POPULATION_YEARLY_GROWTH_BASE\s*=\s*([0-9.]+)', source('common/defines/MD_defines.lua')).group(1)
        state_growth = re.search(r'base_growth\s*=\s*([0-9.]+)', source('common/on_actions/00_state_population_monthly_on_actions.txt')).group(1)
        self.assertEqual(float(growth), float(state_growth))
        money = source('common/scripted_effects/00_money_system.txt')
        self.assertIn('random_owned_state = { PREV = { set_capital = { state = PREV } } }', money)
        self.assertNotIn('random_owned_state = { ROOT = { set_capital = { state = PREV } } }', money)

    def test_localisation_covers_every_new_ui_key_and_keeps_person_units(self):
        locale = {}
        for language in ('english','russian'):
            path = ROOT/'localisation'/language/'replace'/f'eon_migration_relief_l_{language}.yml'
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b'\xef\xbb\xbf'))
            self.assertNotIn(b'\n', raw.replace(b'\r\n', b''))
            pairs = re.findall(r'^ ([A-Za-z0-9_.]+):0 "(.*)"$', raw.decode('utf-8-sig'), re.M)
            # CRLF matching retains one carriage return after the closing quote.
            if not pairs:
                pairs = re.findall(r'^ ([A-Za-z0-9_.]+):0 "(.*)"\r?$', raw.decode('utf-8-sig'), re.M)
            self.assertEqual(len(pairs), len(set(k for k,_ in pairs)))
            locale[language] = dict(pairs)
            self.assertGreater(len(pairs), 15)
            for value in locale[language].values():
                self.assertNotIn('neighbour_war_refugees_display|%', value)
                self.assertNotIn('personal_war_refugees_display|%', value)
        self.assertEqual(locale['english'].keys(), locale['russian'].keys())
        definitions = ast(source('common/decisions/eon_migration_relief_decisions.txt'))
        for category,_,decisions in definitions:
            self.assertIn(category, locale['english'])
            for key,_,_ in decisions:
                self.assertIn(key, locale['english'])
                self.assertIn(key+'_desc', locale['english'])
        for key in ('eon_refugee_reception_modifier','eon_refugee_reception_modifier_tt','eon_migration_population_flow_tt', 'MAXIMUM_MIGRATION_RATE_TT_DELAYED', 'NET_MIGRATION_RATE_TT_DELAYED'):
            self.assertIn(key, locale['english'])

    def test_existing_national_border_prohibition_is_not_bypassed(self):
        triggers = dict((key,value) for key,_,value in ast(source('common/scripted_triggers/eon_migration_relief_triggers.txt')))
        self.assertIn(('NOT','=',[('has_idea','=','closed_borders')]), triggers['eon_migration_host_available'])
        decisions = source('common/decisions/eon_migration_relief_decisions.txt')
        self.assertEqual(decisions.count('available = { NOT = { has_idea = closed_borders } }'),2)

if __name__ == '__main__':
    unittest.main(verbosity=2)
