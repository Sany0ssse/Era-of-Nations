"""Source-only private override controls; never mutate production or launch."""
from copy import deepcopy
from pathlib import Path
import hashlib
import unittest

from runtime_override_support import (ROOT, RUNTIME_OVERRIDE_ACTIONS,
                                      validate_override_bytes, validate_override_maps)
from extension_support import ast, render
from runtime_support import ai_weight_overlay


class RuntimeOverrideContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = {path: (ROOT / path).read_bytes() for path in RUNTIME_OVERRIDE_ACTIONS}
        cls.overlay = {}
        for path, ids in RUNTIME_OVERRIDE_ACTIONS.items():
            nodes = deepcopy(ast(cls.original[path].decode('utf-8-sig')))
            for _, _, category in nodes:
                if not isinstance(category, list): continue
                for ident, _, action in category:
                    if ident in ids:
                        pos = next(i for i, row in enumerate(action) if row[0] == 'ai_will_do')
                        action[pos] = ('ai_will_do', '=', [('factor', '=', '0')])
            cls.overlay[path] = ai_weight_overlay(cls.original[path].decode('utf-8'), ids).encode('utf-8')

    def records(self):
        return {path: validate_override_bytes(path, self.original[path], self.overlay[path], ids)
                for path, ids in RUNTIME_OVERRIDE_ACTIONS.items()}

    def maps(self):
        records = self.records()
        before = {path: row['source_sha256'] for path, row in records.items()}
        before['common/scripted_effects/eon_eu_voting_effects.txt'] = '3' * 64
        after = dict(before)
        fixtures = {path: row['runtime_override_sha256'] for path, row in records.items()}
        after.update(fixtures)
        provenance = {path: row['source_sha256'] for path, row in records.items()}
        return records, before, after, provenance, fixtures

    def action(self, nodes, ident):
        matches = [row for _, _, category in nodes if isinstance(category, list)
                   for row in category if row[0] == ident]
        self.assertEqual(len(matches), 1)
        return matches[0][2]

    def test_exact_two_actual_source_files_and_eight_ai_holds_are_accepted(self):
        records = self.records()
        self.assertEqual(len(records), 2)
        self.assertEqual(sum(len(row['selected_ai_action_ids']) for row in records.values()), 8)
        for path, row in records.items():
            self.assertEqual(row['source_sha256'], hashlib.sha256(self.original[path]).hexdigest())
            self.assertEqual(row['runtime_override_sha256'], hashlib.sha256(self.overlay[path]).hexdigest())
        self.assertTrue(validate_override_maps(*self.maps()))

    def test_handler_price_target_and_visibility_mutants_fail_whole_ast_boundary(self):
        path = 'common/decisions/eon_eu_withdrawal_extension_decisions.txt'
        for field, replacement in (
            ('complete_effect', [('add_political_power', '=', '1')]),
            ('cost', '1'), ('target_trigger', [('always', '=', 'yes')]),
            ('visible', [('always', '=', 'yes')])):
            nodes = deepcopy(ast(self.overlay[path].decode('utf-8')))
            action = self.action(nodes, 'eon_eu_extension_approve')
            pos = next(i for i, row in enumerate(action) if row[0] == field)
            action[pos] = (field, '=', replacement)
            with self.subTest(field=field):
                with self.assertRaisesRegex(AssertionError, 'outside the exact eight AI holds'):
                    validate_override_bytes(path, self.original[path], render(nodes).encode(), RUNTIME_OVERRIDE_ACTIONS[path])

    def test_category_gate_and_added_decision_are_not_ai_only_changes(self):
        path = 'common/decisions/eon_eu_membership_decisions.txt'
        for kind in ('category', 'extra'):
            nodes = deepcopy(ast(self.overlay[path].decode('utf-8')))
            category = next(body for _, _, body in nodes if isinstance(body, list))
            if kind == 'category':
                positions = [i for i, row in enumerate(category) if row[0] == 'allowed']
                if positions: category[positions[0]] = ('allowed', '=', [('always', '=', 'no')])
                else: category.append(('allowed', '=', [('always', '=', 'no')]))
            else:
                category.append(('unrelated_new_decision', '=', [('cost', '=', '0')]))
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(AssertionError, 'outside the exact eight AI holds'):
                    validate_override_bytes(path, self.original[path], render(nodes).encode(), RUNTIME_OVERRIDE_ACTIONS[path])

    def test_ninth_unselected_ai_weight_change_is_rejected(self):
        path = 'common/decisions/eon_eu_membership_decisions.txt'
        nodes = deepcopy(ast(self.overlay[path].decode('utf-8')))
        changed = False
        for _, _, category in nodes:
            if not isinstance(category, list): continue
            for ident, _, action in category:
                if ident in RUNTIME_OVERRIDE_ACTIONS[path] or not isinstance(action, list): continue
                ai = [i for i, row in enumerate(action) if row[0] == 'ai_will_do']
                if ai:
                    action[ai[0]] = ('ai_will_do', '=', [('factor', '=', '99')])
                    changed = True; break
            if changed: break
        self.assertTrue(changed)
        with self.assertRaisesRegex(AssertionError, 'outside the exact eight AI holds'):
            validate_override_bytes(path, self.original[path], render(nodes).encode(), RUNTIME_OVERRIDE_ACTIONS[path])

    def test_seven_duplicate_or_unknown_selected_actions_are_rejected(self):
        path = next(iter(RUNTIME_OVERRIDE_ACTIONS)); ids = list(RUNTIME_OVERRIDE_ACTIONS[path])
        for bad in (ids[:-1], ids + [ids[0]], ids + ['unknown_ai_action']):
            with self.subTest(ids=bad):
                with self.assertRaises(AssertionError):
                    validate_override_bytes(path, self.original[path], self.overlay[path], bad)

    def test_unknown_filepath_duplicate_source_id_or_missing_ai_block_is_rejected(self):
        path = next(iter(RUNTIME_OVERRIDE_ACTIONS)); ids = RUNTIME_OVERRIDE_ACTIONS[path]
        with self.assertRaisesRegex(AssertionError, 'Unknown private override path'):
            validate_override_bytes('../outside.txt', self.original[path], self.overlay[path], ids)
        for kind in ('duplicate', 'missing_ai'):
            source = deepcopy(ast(self.original[path].decode('utf-8-sig')))
            action = self.action(source, ids[0])
            if kind == 'missing_ai': action[:] = [row for row in action if row[0] != 'ai_will_do']
            else:
                category = next(body for _, _, body in source if isinstance(body, list) and any(row[0] == ids[0] for row in body))
                category.append((ids[0], '=', deepcopy(action)))
            with self.subTest(kind=kind):
                with self.assertRaises(AssertionError):
                    validate_override_bytes(path, render(source).encode(), self.overlay[path], ids)

    def test_literal_override_rejects_bom_and_invalid_utf8_without_normalizing(self):
        path = next(iter(RUNTIME_OVERRIDE_ACTIONS)); ids = RUNTIME_OVERRIDE_ACTIONS[path]
        for bad in (b'\xef\xbb\xbf' + self.overlay[path], self.overlay[path] + b'\xef\xbb\xbf'):
            with self.assertRaisesRegex(AssertionError, 'U\+FEFF'):
                validate_override_bytes(path, self.original[path], bad, ids)
        with self.assertRaises(UnicodeDecodeError):
            validate_override_bytes(path, self.original[path], self.overlay[path] + b'\xff', ids)

    def test_comments_and_line_endings_outside_ai_bodies_are_exact(self):
        path = next(iter(RUNTIME_OVERRIDE_ACTIONS)); ids = RUNTIME_OVERRIDE_ACTIONS[path]
        for bad in (b'# extra comment\n' + self.overlay[path], self.overlay[path].replace(b'\r\n',b'\n')):
            if bad == self.overlay[path]: bad += b'\n'
            with self.assertRaisesRegex(AssertionError, 'bytes outside'):
                validate_override_bytes(path, self.original[path], bad, ids)

    def test_effective_map_cannot_replace_other_source_or_drop_key(self):
        for kind in ('other', 'omit'):
            records, before, after, provenance, fixture = self.maps()
            if kind == 'other': after['common/scripted_effects/eon_eu_voting_effects.txt'] = '4' * 64
            else: after.pop('common/scripted_effects/eon_eu_voting_effects.txt')
            with self.subTest(kind=kind):
                with self.assertRaises(AssertionError): validate_override_maps(records, before, after, provenance, fixture)

    def test_provenance_runtime_interchange_and_fixture_hash_drift_are_rejected(self):
        for kind in ('before', 'provenance', 'fixture', 'metadata', 'path'):
            records, before, after, provenance, fixture = self.maps(); path = next(iter(records))
            if kind == 'before': before[path] = after[path]
            elif kind == 'provenance': provenance[path] = after[path]
            elif kind == 'fixture': fixture[path] = '4' * 64
            elif kind == 'path': records[path]['path'] = '../different.txt'
            else: records[path]['undeclared_extra'] = 'not_allowed'
            with self.subTest(kind=kind):
                with self.assertRaises(AssertionError): validate_override_maps(records, before, after, provenance, fixture)


if __name__ == '__main__': unittest.main(verbosity=2)
