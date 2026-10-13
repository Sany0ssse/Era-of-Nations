"""Actual energy reply selector + exact historical byte guards; not a native AI simulator.

Default reads the authoritative local game source. --mod-root/--action-source are
explicit private staging inputs; no installed bytes, callbacks or AI scores are
substituted. Strict model definitions omit unrelated old commercial test loops.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path
import argparse
import ast as python_ast
import hashlib
import io
import os
import sys
import unittest
from energy_byte_compat import CATALOG, SELECTOR_CATALOG, restore_energy_ai, restore_energy_selector, negative_controls

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--mod-root', type=Path)
parser.add_argument('--action-source', type=Path)
inputs, remaining = parser.parse_known_args()
sys.argv = [sys.argv[0]] + remaining
ROOT = (inputs.mod_root or Path(__file__).resolve().parents[3]).resolve()
ACTION = 'common/scripted_diplomatic_actions/MDDC_energy_contract_scripted_diplomatic_actions.txt'
ACTION_SOURCE = (inputs.action_source or ROOT / ACTION).resolve()
sys.path.insert(0, str(ROOT / 'tools/validation/diplomacy_package_01'))
manifest = SELECTOR_CATALOG[ACTION]
sha = lambda raw: hashlib.sha256(raw).hexdigest()
candidate = ACTION_SOURCE.read_bytes()
# The exact pre-change input is allowed to load only to reproduce the single
# regression RED; full-source/current-selector tests still require new bytes.
baseline = candidate if sha(candidate) == manifest['before_file_sha256'] else restore_energy_selector(ACTION, candidate)
def restore_energy_ai_original_baseline(raw):
    patch = CATALOG[ACTION]
    before, after = patch['before'].encode(), patch['after'].encode()
    assert raw.count(after) == 1
    restored = raw.replace(after, before, 1)
    assert sha(restored) == patch['before_file_sha256']
    return restored

def load_model_definitions(path, base=None):
    parsed = python_ast.parse(path.read_text(encoding='utf-8'), str(path))
    body = []
    boundary = False
    replaced = 0
    for node in parsed.body:
        if isinstance(node, python_ast.Assign) and any((isinstance(t, python_ast.Name) and t.id == 'cases' for t in node.targets)):
            boundary = True
            break
        if base is not None and isinstance(node, python_ast.With):
            expected = python_ast.parse("with redirect_stdout(io.StringIO()):\n    base = runpy.run_path(str(Path(__file__).with_name('test_energy.py')))\n").body[0]
            assert python_ast.dump(node) == python_ast.dump(expected)
            replaced += 1
            continue
        body.append(node)
    assert boundary and replaced == (1 if base is not None else 0)
    env = {'__file__': str(path), '__name__': 'private_energy_strict_model'}
    if base is not None:
        env['base'] = base
    with redirect_stdout(io.StringIO()):
        exec(compile(python_ast.Module(body=body, type_ignores=[]), str(path), 'exec'), env)
    return env

def action(raw):
    return one(one(ast(raw.decode('utf-8-sig')), 'scripted_diplomatic_actions'), 'energy_contract_agreement')

def select(nodes, state, sender='A', recipient='B'):
    return model['trigger'](one(nodes, 'selectable'), state, model['native'](sender, recipient))

def ready(nodes, state, field='can_be_sent', sender='A', recipient='B'):
    return model['trigger'](one(nodes, field), state, model['native'](sender, recipient))

def world(sender='A', recipient='B', sender_ai=True, recipient_ai=True):
    state = model['state']()
    state['countries'][sender]['ai'] = sender_ai
    state['countries'][recipient]['ai'] = recipient_ai
    return state

def pending(sender='A', recipient='B', sender_ai=True, recipient_ai=True):
    state = world(sender, recipient, sender_ai, recipient_ai)
    assert model['send'](state, sender, recipient)
    return state

def execute(nodes, state, field, sender='A', recipient='B'):
    model['execute'](one(nodes, field), state, model['native'](sender, recipient))

commercial = load_model_definitions(ROOT / 'tools/validation/diplomacy_package_01/test_energy.py')
model = load_model_definitions(ROOT / 'tools/validation/diplomacy_package_01/test_framework.py', commercial)
ast, one = model['ast'], model['one']
old, new = action(baseline), action(candidate)

class EnergySelector(unittest.TestCase):

    def test_pending_recipient_ai_is_selectable_regression(self):
        variant = os.environ.get('ENERGY_SOURCE_VARIANT', 'candidate')
        self.assertIn(variant, ('baseline', 'candidate'))
        source = old if variant == 'baseline' else new
        state = pending()
        self.assertTrue(select(source, state))
        self.assertFalse(ready(source, state))
        self.assertTrue(ready(source, state, 'can_be_accepted'))

    def test_original_human_ui_and_human_sender_to_ai(self):
        for sender_ai in (False, True):
            for recipient_ai in (False, True):
                state = world(sender_ai=sender_ai, recipient_ai=recipient_ai)
                self.assertEqual(select(old, state), select(new, state))
                self.assertTrue(select(new, state))
                state = pending(sender_ai=sender_ai, recipient_ai=recipient_ai)
                self.assertFalse(select(old, state))
                self.assertEqual(select(new, state), recipient_ai)
                self.assertFalse(ready(new, state))

    def test_pair_identity_and_arbitrary_sender_roots(self):
        for sender, recipient in (('A', 'B'), ('B', 'A'), ('C', 'D'), ('D', 'C')):
            state = pending(sender, recipient, sender_ai=False)
            self.assertTrue(select(new, state, sender, recipient))
            self.assertFalse(ready(new, state, sender=sender, recipient=recipient))
            outside = next((c for c in state['countries'] if c not in (sender, recipient)))
            for actual_sender, actual_recipient in ((sender, outside), (outside, recipient), (recipient, sender)):
                state['countries'][actual_recipient]['ai'] = True
                self.assertFalse(select(new, state, actual_sender, actual_recipient))
            for country, variable, wrong in ((sender, 'pending_energy_offer_country', 0), (recipient, 'eon_energy_framework_pending_sender', 0), (sender, 'pending_energy_offer_country', outside), (recipient, 'eon_energy_framework_pending_sender', outside)):
                modified = deepcopy(state)
                modified['countries'][country]['variables'][variable] = wrong
                self.assertFalse(select(new, modified, sender, recipient))

    def test_stale_terms_cannot_force_agreement_but_can_drain(self):
        for change in ('recipient vanished', 'sender vanished', 'war', 'not adjacent', 'opinion', 'recipient signed', 'sender signed', 'recipient withdrawn', 'sender withdrawn'):
            state = pending()
            a, b = (state['countries']['A'], state['countries']['B'])
            if change == 'recipient vanished':
                b['exists'] = False
            elif change == 'sender vanished':
                a['exists'] = False
            elif change == 'war':
                b['wars'].add('A')
            elif change == 'not adjacent':
                b['neighbors'].discard('A')
            elif change == 'opinion':
                b['opinions']['A'] = 10
            elif change == 'recipient signed':
                b['flags'].add('energy_agreement@A')
            elif change == 'sender signed':
                a['flags'].add('energy_agreement@B')
            elif change == 'recipient withdrawn':
                b['flags'].add('eon_energy_framework_withdrawn')
            elif change == 'sender withdrawn':
                a['flags'].add('eon_energy_framework_withdrawn')
            self.assertTrue(select(new, state), change)
            self.assertFalse(ready(new, state, 'can_be_accepted'), change)
            original = deepcopy(state)
            protected_flags = [c['flags'] - {'eon_energy_framework_withdrawn'} for c in (a, b)]
            execute(new, state, 'complete_effect')
            execute(old, original, 'complete_effect')
            self.assertEqual(state, original, change)
            self.assertFalse(model['reserved'](state, 'A'))
            self.assertFalse(model['reserved'](state, 'B'))
            self.assertEqual(protected_flags, [state['countries'][c]['flags'] for c in ('A', 'B')])
            self.assertFalse(state.get('external_calls'))

    def test_actual_complete_reject_and_wrong_callbacks_equivalent(self):
        for callback in ('complete_effect', 'reject_effect'):
            for sender, recipient in (('A', 'B'), ('B', 'A'), ('C', 'D'), ('D', 'C')):
                state = pending(sender, recipient)
                original = deepcopy(state)
                execute(new, state, callback, sender, recipient)
                execute(old, original, callback, sender, recipient)
                self.assertEqual(state, original)
                self.assertEqual(model['agreed'](state, sender, recipient), callback == 'complete_effect')
                self.assertFalse(model['reserved'](state, sender))
                self.assertFalse(model['reserved'](state, recipient))
                before = deepcopy(state)
                execute(new, state, callback, sender, recipient)
                self.assertEqual(state, before)
                state = pending('A', 'C')
                before = deepcopy(state)
                execute(new, state, callback, 'A', 'B')
                self.assertEqual(state, before)

    def test_withdrawal_original_reservation_and_cancel_exact(self):
        for callback in ('complete_effect', 'reject_effect'):
            state = pending()
            model['execute'](one(model['cancel'], 'complete_effect'), state, model['native']())
            self.assertTrue(select(new, state))
            self.assertFalse(ready(new, state))
            self.assertFalse(ready(new, state, 'can_be_accepted'))
            self.assertTrue(model['reserved'](state, 'A'))
            self.assertTrue(model['reserved'](state, 'B'))
            original = deepcopy(state)
            execute(new, state, callback)
            execute(old, original, callback)
            self.assertEqual(state, original)
            self.assertFalse(model['reserved'](state, 'A'))
            self.assertFalse(model['reserved'](state, 'B'))
            self.assertFalse(model['agreed'](state))
        self.assertEqual(one(ast(candidate.decode()), 'scripted_diplomatic_actions')[1], one(ast(baseline.decode()), 'scripted_diplomatic_actions')[1])

def canonical(raw):
    inverse = restore_energy_selector(ACTION, raw)
    if sha(inverse) != manifest['before_file_sha256']:
        raise AssertionError('Foreign bytes outside exact selector')
    return inverse

class ByteGuards(unittest.TestCase):

    def test_exact_full_source_inverse_then_original_cancel_inverse(self):
        self.assertEqual(sha(candidate), manifest['after_file_sha256'])
        self.assertEqual(sha(canonical(candidate)), manifest['before_file_sha256'])
        self.assertEqual(restore_energy_ai(ACTION, candidate), restore_energy_ai_original_baseline(baseline))
        self.assertEqual(sha(restore_energy_ai(ACTION, candidate)), manifest['historical_cancel_inverse_file_sha256'])
        self.assertEqual(CATALOG[ACTION]['before_file_sha256'], manifest['historical_cancel_inverse_file_sha256'])
        self.assertEqual([n for n in new if n[0] != 'selectable'], [n for n in old if n[0] != 'selectable'])
        self.assertEqual(one(one(new, 'selectable'), 'OR'), [('AND', '=', one(old, 'selectable')), ('AND', '=', [('is_ai', '=', 'yes'), ('eon_energy_framework_response_current', '=', 'yes')])])
        self.assertEqual(candidate.startswith(bytes.fromhex('efbbbf')), baseline.startswith(bytes.fromhex('efbbbf')))
        self.assertEqual(bytes.fromhex('0d0a') in candidate, bytes.fromhex('0d0a') in baseline)
        self.assertEqual(ACTION_SOURCE.read_bytes(), candidate)

    def test_cost_callbacks_acceptance_desire_exact(self):
        for field in ('on_sent_effect', 'complete_effect', 'reject_effect', 'can_be_sent', 'can_be_accepted', 'ai_desire', 'ai_acceptance', 'cost', 'requires_acceptance'):
            self.assertEqual(one(new, field), one(old, field), field)
        self.assertIn(('modifier', '=', [('factor', '=', '0'), ('ROOT', '=', [('NOT', '=', [('check_variable', '=', [('pending_energy_offer_country', '=', '0')])])])]), one(new, 'ai_desire'))

    def test_hostile_selector_and_foreign_bytes_rejected(self):
        before, after = (manifest['before'].encode(), manifest['after'].encode())
        mutants = [candidate.replace(after, before, 1), candidate.replace(after, b'', 1), candidate.replace(after, after + after, 1), candidate.replace(b'is_ai = yes', b'ROOT = { is_ai = yes }', 1), candidate.replace(b'eon_energy_framework_response_current = yes', b'eon_energy_framework_terms_available = yes', 1), candidate.replace(b'cost = 75', b'cost = 74', 1), candidate.replace(b'factor = 10', b'factor = 11', 1), candidate.replace(b'on_sent_effect = {', b'on_sent_effect = { set_variable = { foreign = 1 }', 1), b'# foreign mutation\n' + candidate]
        for mutant in mutants:
            self.assertNotEqual(mutant, candidate)
            with self.assertRaises(AssertionError):
                canonical(mutant)
            try:
                projected = restore_energy_ai(ACTION, mutant)
            except AssertionError:
                pass
            else:
                self.assertNotEqual(sha(projected), manifest['historical_cancel_inverse_file_sha256'])
        self.assertEqual(len(negative_controls(ACTION, candidate)), 4)
        unchanged = b'any foreign path bytes'
        self.assertEqual(restore_energy_selector('common/unowned.txt', unchanged), unchanged)

    def test_frozen_catalog_tampering_rejected(self):
        patch = SELECTOR_CATALOG[ACTION]
        for key in ('before', 'after', 'before_island_sha256', 'after_island_sha256'):
            previous = patch[key]
            try:
                patch[key] += '# changed canonical bytes'
                with self.assertRaises(AssertionError):
                    restore_energy_selector(ACTION, candidate)
            finally:
                patch[key] = previous

if __name__ == '__main__': unittest.main()
