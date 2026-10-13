"""Test explicit AI ownership in the current adapter; not native scheduling."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest

import test_relations as m


class AIOwnershipPrimitiveTests(unittest.TestCase):
    def test_boolean_ownership_and_missing_human_fixture(self):
        for present, current in ((False, False), (True, False), (True, True)):
            result = m.state()
            if present:
                result['countries']['A']['is_ai'] = current
            before = deepcopy(result)
            for expected in ('yes', 'no'):
                self.assertEqual(m.condition([('is_ai', '=', expected)], result, m.ctx()),
                                 current == (expected == 'yes'))
            self.assertEqual(result, before)

    def test_this_root_from_and_prev_read_actual_country(self):
        result = m.state()
        for country, current in (('A', False), ('B', True), ('C', False)):
            result['countries'][country]['is_ai'] = current
        context = {'scope': 'A', 'prev': ['B'], 'root': 'B', 'from': 'C'}
        for scope, wanted in (('THIS', 'no'), ('ROOT', 'yes'), ('FROM', 'no'), ('PREV', 'yes')):
            self.assertTrue(m.condition([(scope, '=', [('is_ai', '=', wanted)])], result, context))
            self.assertFalse(m.condition([(scope, '=', [('is_ai', '=', 'no' if wanted == 'yes' else 'yes')])], result, context))

    def test_invalid_ownership_or_trigger_remains_fail_closed(self):
        for operator, value in (('>', 'yes'), ('=', 'maybe'), ('=', [])):
            with self.subTest(operator=operator, value=value), self.assertRaises(AssertionError):
                m.condition([('is_ai', operator, value)], m.state(), m.ctx())
        result = m.state()
        result['countries']['A']['is_ai'] = 'false'
        with self.assertRaises(AssertionError):
            m.condition([('is_ai', '=', 'no')], result, m.ctx())
        with self.assertRaises(AssertionError):
            m.condition([('unsupported_native_trigger', '=', 'yes')], m.state(), m.ctx())

    def test_nine_actual_root_filters_keep_humans_and_exclude_ai(self):
        names = ('status', 'propose', 'propose_head', 'withdraw', 'recall',
                 'persona_non_grata', 'close', 'close_host', 'break')
        for name in names:
            body = m.DECISIONS[m.P + name]
            self.assertEqual(m.one(body, 'ai_will_do'), [('factor', '=', '0')])
            root = m.one(body, 'target_root_trigger')
            self.assertEqual(root, [('exists', '=', 'yes'), ('is_ai', '=', 'no')])
            for exists, current in ((True, False), (True, True), (False, False), (False, True)):
                with self.subTest(action=name, exists=exists, is_ai=current):
                    result = m.state()
                    result['countries']['A'].update(exists=exists, is_ai=current)
                    before = deepcopy(result)
                    self.assertEqual(m.condition(root, result, m.ctx()), exists and not current)
                    self.assertEqual(result, before)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AIOwnershipPrimitiveTests)
    result = unittest.TextTestRunner(stream=sys.stderr).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    paths = (Path(m.__file__), m.ROOT / m.FILES[2], Path(__file__))
    print(json.dumps({'all_passed': True, 'tests': result.testsRun,
                      'protected_dependencies_sha256': {path.relative_to(m.ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
                      'native_AI_scheduling_proven': False,
                      'proof_scope': 'actual current adapter AI ownership primitive, exact nine actor filters, scope and fail-closed boundaries'}, indent=2))
