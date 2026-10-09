"""Missile catalog and actual source predicate regressions.

These tests read the game source. They do not emulate native air-wing loading,
missile missions, project progress or a playable HOI4 campaign.
"""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '2b6a26e76c80f7923d11ebc2c0694e882253fb32'
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|[=<>!]+|[^\s{}=<>!#"]+')
MISSILE_TECH_FILES = (
    'ballistic_missiles.txt', 'cruise_missiles.txt',
    'missile_defense.txt', 'non_got_missiles.txt',
)


def ast(text):
    tokens = [m[0].strip('"') for m in TOKEN.finditer(text.lstrip('\ufeff'))
              if not m[0].startswith('#')]
    index = 0

    def block():
        nonlocal index
        nodes = []
        while index < len(tokens) and tokens[index] != '}':
            key = tokens[index]
            index += 1
            if index == len(tokens) or tokens[index] not in ('=', '<', '>', '<=', '>=', '!=', '=='):
                nodes.append(('__item__', '=', key))
                continue
            op = tokens[index]
            index += 1
            if tokens[index] == '{':
                index += 1
                value = block()
                assert tokens[index] == '}'
                index += 1
            else:
                value = tokens[index]
                index += 1
            nodes.append((key, op, value))
        return nodes

    nodes = block()
    assert index == len(tokens)
    return nodes


def get(nodes, key, default=None):
    values = [value for name, _, value in nodes if name == key]
    assert len(values) <= 1, (key, len(values))
    return values[0] if values else default


def load(path):
    return ast((ROOT / path).read_text(encoding='utf-8-sig'))


def predicate(nodes, techs=frozenset(), dlcs=frozenset(), projects=frozenset()):
    """Execute only the documented eligibility grammar used by this catalog."""
    answers = []
    for key, op, value in nodes:
        assert op == '='
        if key in ('ROOT', 'FROM', 'AND'):
            result = predicate(value, techs, dlcs, projects)
        elif key == 'OR':
            result = any(predicate([node], techs, dlcs, projects) for node in value)
        elif key == 'NOT':
            result = not predicate(value, techs, dlcs, projects)
        elif key == 'has_tech':
            result = value in techs
        elif key == 'has_dlc':
            result = value in dlcs
        elif key == 'is_special_project_completed':
            result = value.removeprefix('sp:') in projects
        elif key == 'always':
            result = value == 'yes'
        else:
            raise AssertionError(f'Unmodelled predicate: {key}')
        answers.append(result)
    return all(answers)


class MissileResearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.equipment = {}
        for path in sorted((ROOT / 'common/units/equipment').glob('*.txt')):
            nodes = ast(path.read_text(encoding='utf-8-sig'))
            cls.equipment.update({key: value for key, _, value in get(nodes, 'equipments', [])})
        cls.tech = {}
        for path in sorted((ROOT / 'common/technologies').glob('*.txt')):
            nodes = ast(path.read_text(encoding='utf-8-sig'))
            cls.tech.update({key: value for key, _, value in get(nodes, 'technologies', [])
                             if isinstance(value, list)})
        cls.missile_tech = {}
        for name in MISSILE_TECH_FILES:
            cls.missile_tech.update({key: value for key, _, value in get(
                load(f'common/technologies/{name}'), 'technologies', [])
                                    if isinstance(value, list)})
        cls.projects = {key: value for key, _, value in load(
            'common/special_projects/projects/missile_projects.txt')}

    def test_all_missile_equipment_unlocks_resolve(self):
        missing = [(tech, item) for tech, nodes in self.missile_tech.items()
                   for key, _, items in nodes if key == 'enable_equipments'
                   for _, _, item in items if item not in self.equipment]
        self.assertEqual(missing, [])

    def test_restored_early_models_have_existing_english_and_russian_names(self):
        for language in ('english', 'russian'):
            texts = '\n'.join(path.read_text(encoding='utf-8-sig') for path in
                              (ROOT / f'localisation/{language}').glob('*.yml'))
            for key in ('guided_missile_equipment_0', 'anti_ship_missile_equipment_0'):
                with self.subTest(language=language, key=key):
                    self.assertRegex(texts, rf'(?m)^\s*{key}:\d*\s*".+"')

    def test_restored_models_preserve_existing_script_enum_numeric_positions(self):
        original = subprocess.run(['git', 'show', BASELINE+':common/script_enums.txt'],
                                  cwd=ROOT, capture_output=True, check=True).stdout.decode('utf-8-sig')
        old = [value for _, _, value in get(ast(original), 'script_enum_equipment_bonus_type')]
        new = [value for _, _, value in get(load('common/script_enums.txt'), 'script_enum_equipment_bonus_type')]
        # The added aliases must be the only new values and must not shift the
        # numeric positions that older saves or scripted variables may retain.
        self.assertEqual(len(old), 639)
        self.assertEqual(new[:len(old)], old)
        self.assertEqual(new[len(old):], ['guided_missile_equipment_0', 'anti_ship_missile_equipment_0'])

    def test_all_missile_research_paths_resolve(self):
        missing = [(tech, get(path, 'leads_to_tech'))
                   for tech, nodes in self.missile_tech.items()
                   for key, _, path in nodes if key == 'path'
                   if get(path, 'leads_to_tech') not in self.tech]
        self.assertEqual(missing, [])

    def test_researched_glcm_can_be_produced_in_both_dlc_branches(self):
        for level in range(1, 9):
            model = self.equipment[f'guided_missile_equipment_{level}']
            guard = get(model, 'can_be_produced', [])
            for suffix, dlcs in (('', {'Gotterdammerung'}), ('_non_got', set())):
                tech = f'GLCM{level}{suffix}'
                with self.subTest(level=level, branch=suffix or 'GoT'):
                    self.assertTrue(predicate(guard, {tech}, dlcs))
                    self.assertIn(f'guided_missile_equipment_{level}',
                                  [value for _, _, value in get(self.tech[tech], 'enable_equipments')])
                    self.assertFalse(predicate(guard, {f'GLCM{max(0, level-1)}{suffix}'}, dlcs))
                    self.assertFalse(predicate(guard, set(), dlcs))

    def test_foundation_unlock_does_not_bypass_model_production_research(self):
        for stem, tech in (('guided_missile', 'GLCM'), ('anti_ship_missile', 'ASM'),
                           ('ballistic_missile', 'IRBM'), ('sam_missile', 'SAM')):
            for level in range(1, 9):
                with self.subTest(family=stem, level=level):
                    guard = get(self.equipment[f'{stem}_equipment_{level}'], 'can_be_produced', [])
                    prerequisite = f'{tech}{level-1 if stem == "sam_missile" else level}'
                    self.assertTrue(predicate(guard, {prerequisite}, {'Gotterdammerung'}))
                    self.assertFalse(predicate(guard, {tech}, {'Gotterdammerung'}))

    def test_early_referenced_models_are_buildable_single_use_and_weaker(self):
        for stem, tech in (('guided_missile', 'GLCM'), ('anti_ship_missile', 'GLCM')):
            with self.subTest(family=stem):
                first = self.equipment[f'{stem}_equipment_0']
                later = self.equipment[f'{stem}_equipment_1']
                self.assertEqual(get(first, 'archetype'), f'{stem}_equipment')
                self.assertEqual(get(first, 'is_buildable'), 'yes')
                self.assertEqual(get(first, 'one_use_only'), 'yes')
                self.assertLess(float(get(first, 'air_range')), float(get(later, 'air_range')))
                self.assertLess(float(get(first, 'build_cost_ic')), float(get(later, 'build_cost_ic')))
                self.assertGreater(float(get(first, 'air_range')), 0)
                self.assertTrue(predicate(get(first, 'can_be_produced'), {tech}, {'Gotterdammerung'}))
                self.assertFalse(predicate(get(first, 'can_be_produced'), set(), {'Gotterdammerung'}))
        first = self.equipment['guided_missile_equipment_0']
        self.assertTrue(predicate(get(first, 'can_be_produced'), {'GLCM_non_got'}, set()))

    def test_hypersonic_project_matches_missile_dlc_without_aircraft_dlc(self):
        allowed = get(self.projects['sp_hypersonic_missile'], 'allowed')
        self.assertTrue(predicate(allowed, dlcs={'Gotterdammerung'}))
        self.assertFalse(predicate(allowed, dlcs={'By Blood Alone'}))
        for name in ('HSCM', 'HSCM1', 'HSCM2'):
            allowed = get(self.tech[name], 'allow')
            required = {'sp_missile_project'}
            if name == 'HSCM':
                self.assertFalse(predicate(allowed, projects=required))
                required.add('sp_hypersonic_missile')
            self.assertTrue(predicate(allowed, projects=required))

    def test_every_researchable_model_has_a_buildable_resolving_equipment(self):
        enums = {value for _, _, value in get(load('common/script_enums.txt'),
                                              'script_enum_equipment_bonus_type')}
        families = (('ICBM', 'nuclear_missile', 8, 1),
                    ('IRBM', 'ballistic_missile', 8, 1),
                    ('NIRBM', 'nuclear_ballistic_missile', 7, 1),
                    ('GLCM', 'guided_missile', 8, 1),
                    ('ASM', 'anti_ship_missile', 8, 1),
                    ('SAM', 'sam_missile', 7, 0),
                    ('HSCM', 'hypersonic_missile', 2, 1))
        for tech_stem, model_stem, last, first in families:
            for level in range(first, last + 1):
                model_level = level + 1 if tech_stem == 'SAM' else level
                name = f'{tech_stem}{level}'
                ident = f'{model_stem}_equipment_{model_level}'
                with self.subTest(tech=name, equipment=ident):
                    self.assertIn(ident, [value for _, _, value in
                                        get(self.tech[name], 'enable_equipments')])
                    model = self.equipment[ident]
                    self.assertIn(ident, enums)
                    self.assertEqual(get(model, 'is_buildable'), 'yes')
                    self.assertEqual(get(model, 'one_use_only'), 'yes')
                    archetype = get(model, 'archetype')
                    self.assertIn(archetype, self.equipment)
                    parent = get(model, 'parent')
                    if parent:
                        self.assertIn(parent, self.equipment)
                        self.assertEqual(get(self.equipment[parent], 'archetype'), archetype)
                    self.assertGreater(float(get(model, 'air_range')), 0)
                    self.assertGreater(float(get(model, 'build_cost_ic',
                                                 get(self.equipment[archetype], 'build_cost_ic'))), 0)
                    self.assertTrue(get(self.equipment[archetype], 'allow_mission_type'))
        self.assertIn('guided_missile_equipment_0', enums)
        self.assertIn('anti_ship_missile_equipment_0', enums)

    def test_nuclear_and_conventional_project_research_gates_remain_distinct(self):
        for tech_stem, last in (('ICBM', 8), ('NIRBM', 7)):
            for level in range(1, last + 1):
                name = f'{tech_stem}{level}'
                with self.subTest(tech=name):
                    allowed = get(self.tech[name], 'allow')
                    self.assertTrue(predicate(allowed, projects={'sp_nuclear_warhead_program'}))
                    self.assertFalse(predicate(allowed, projects={'sp_missile_project'}))
        for level in range(1, 9):
            with self.subTest(tech=f'IRBM{level}'):
                allowed = get(self.tech[f'IRBM{level}'], 'allow')
                self.assertTrue(predicate(allowed, projects={'sp_missile_project'}))
                self.assertFalse(predicate(allowed, projects={'sp_nuclear_warhead_program'}))

    def test_silo_research_callbacks_resolve_hidden_unlocks_and_sub_units(self):
        for name in ('ICBM', 'IRBM', 'GLCM', 'GLCM_non_got', 'TEL_launched_missiles',
                     'TEL_launched_missiles_non_got'):
            self.assertEqual(get(get(self.tech[name], 'on_research_complete'),
                                 'add_missile_building_level'), 'yes')
        for level in range(1, 11):
            unlock = get(self.tech[f'hid_tech_missile_{level}'], 'enable_building')
            self.assertEqual(get(unlock, 'building'), 'rocket_site')
            self.assertEqual(int(get(unlock, 'level')), level)
        units = get(load('common/units/MD_air_units.txt'), 'sub_units')
        for name in ('guided_missile', 'anti_ship_missile', 'hypersonic_missile',
                     'ballistic_missile', 'nuclear_ballistic_missile', 'nuclear_missile', 'sam_missile'):
            unit = get(units, name)
            for needed, _, _ in get(unit, 'need'):
                self.assertIn(needed, self.equipment)


if __name__ == '__main__':
    unittest.main(verbosity=2)
