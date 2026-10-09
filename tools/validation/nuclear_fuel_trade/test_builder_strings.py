"""Preserve actual native nested strings when constructing private AI controls."""
from pathlib import Path
import importlib.util
import json
import re
import unittest

from build_native_probe import emit_native_ast
import build_native_probe as builder

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('fuel_builder_string_native_parser',
    ROOT / 'tools/validation/diplomacy_package_03/_support.py')
p = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = p
spec.loader.exec_module(p)


def walk(nodes):
    for key, op, value in nodes:
        yield key, op, value
        if isinstance(value, list):
            yield from walk(value)


def old_json_escape_emit(nodes):
    """The prior implementation, retained only as a rejected regression mutant."""
    rows = []
    for key, op, value in nodes:
        if key == '__item__':
            rows.append(str(value))
        elif isinstance(value, list):
            rows.append(key + ' ' + op + ' { ' + old_json_escape_emit(value) + ' }')
        else:
            scalar = str(value)
            if key == 'log' or not scalar or re.search(r'\s', scalar):
                scalar = json.dumps(scalar, ensure_ascii=False)
            rows.append(key + ' ' + op + ' ' + scalar)
    return '\n'.join(rows)


class NativeBuilderStrings(unittest.TestCase):
    def test_original_unit_hooks_are_excluded_from_all_private_controls(self):
        protected=('common/on_actions/00_partisans.txt',
                   'common/on_actions/99_EGY_on_actions.txt',
                   'common/on_actions/99_PER_on_actions.txt')
        hooks=[]
        for rel in protected:
            nodes=p.one(p.ast((ROOT/rel).read_bytes()),'on_actions')
            for hook,op,value in nodes:
                if isinstance(value,list) and hook.startswith(('on_weekly','on_monthly')) and any(key=='effect' for key,op,body in value):
                    hooks.append((rel,hook))
                    self.assertFalse(builder.should_control_on_action(rel,hook))
        self.assertTrue(hooks,'Exercise real native hook registrations, not invented file names')
        self.assertTrue(builder.should_control_on_action('common/on_actions/01_on_actions.txt','on_weekly'))
        self.assertTrue(builder.should_control_on_action('common/on_actions/00_ai_gui_on_actions.txt','on_daily'))
        saved=builder.UNTOUCHED_UNIT_ON_ACTIONS
        try:
            builder.UNTOUCHED_UNIT_ON_ACTIONS=set()
            self.assertTrue(all(builder.should_control_on_action(rel,hook) for rel,hook in hooks),'The independent protected paths reject an exclusion-removal mutant')
        finally:builder.UNTOUCHED_UNIT_ON_ACTIONS=saved

    def test_three_original_unit_payloads_survive_repeated_guard_emission(self):
        for rel in ('common/on_actions/00_partisans.txt',
                    'common/on_actions/99_EGY_on_actions.txt',
                    'common/on_actions/99_PER_on_actions.txt'):
            with self.subTest(rel=rel):
                original = p.ast((ROOT / rel).read_bytes())
                divisions = [value for key, op, value in walk(original) if key == 'division']
                self.assertTrue(divisions)
                self.assertTrue(any(r'\"' in text for text in divisions))
                emitted = original
                for _ in range(8):
                    emitted = p.ast(emit_native_ast(emitted).encode('utf-8'))
                    self.assertEqual(emitted, original)
                self.assertEqual([value for key, op, value in walk(emitted) if key == 'division'], divisions)
                self.assertNotEqual(p.ast(old_json_escape_emit(original)), original)

    def test_native_log_quotes_and_windows_escapes_remain_lexical(self):
        source = r'''log = "EON message \"quoted\" path=C:\\Game\\mod"'''
        original = p.ast(source)
        emitted = emit_native_ast(original)
        self.assertEqual(p.ast(emitted), original)
        self.assertEqual(emitted, source)
        self.assertNotEqual(p.ast(old_json_escape_emit(original)), original)

    def test_private_guard_preserves_nested_unit_body_and_log(self):
        source = r'''effect = { log = "BEGIN \"division\"" create_unit = { division = "name = \"Test unit\" division_template = \"Special forces\" start_experience_factor = 0.6" owner = PREV count = 1 } }'''
        original = p.one(p.ast(source), 'effect')
        guard = p.ast('if = { limit = { NOT = { has_global_flag = eon_private_fuel_probe_active } } }')
        p.one(guard, 'if').extend(original)
        rebuilt = p.ast(emit_native_ast(guard))
        self.assertEqual(rebuilt, guard)
        self.assertEqual([value for key, op, value in walk(rebuilt) if key == 'division'],
                         [value for key, op, value in walk(original) if key == 'division'])


if __name__ == '__main__':
    unittest.main()
