"""Portable Git-source checks; no game installation or private artifacts needed."""
from pathlib import Path
import os
import json
import re
import unittest
import audit
from byte_compat import FRAMEWORK, canonical_framework_view

if os.environ.get('EON_AI_PLAYER_MOD_ROOT'):
    audit.ROOT = Path(os.environ['EON_AI_PLAYER_MOD_ROOT']).resolve()
SOURCE_PATH = Path(os.environ.get('EON_AI_PLAYER_SOURCE_PATH', str(audit.ROOT / audit.SOURCE)))
B = json.loads((Path(__file__).resolve().parent / 'bindings.json').read_text(encoding='utf-8'))

def root_value(nodes, exists, ai):
    values = {'exists': exists, 'is_ai': ai}
    return all(values[n['key']] == (n['value'] == 'yes') for n in nodes)

class PlayerDecisionFilterChecks(unittest.TestCase):
    def test_exact_before_or_after_and_full_inverse(self):
        raw = SOURCE_PATH.read_bytes()
        digest = audit.sha(raw)
        self.assertIn(digest, (B['before_sha256'], B['after_sha256']))
        after = digest == B['after_sha256']
        text = raw.decode('utf-8-sig')
        ds = audit.decisions(text)
        restored = raw
        for p in reversed(B['patches']):
            start, end = (p['after_start'], p['after_end']) if after else (p['before_start'], p['before_end'])
            old, new = bytes.fromhex(p['before_hex']), bytes.fromhex(p['after_hex'])
            self.assertEqual(raw[start:end], new if after else old)
            if after:
                restored = restored[:start] + old + restored[end:]
            fs = audit.fields(ds[p['id']]['value'])
            expected = [('exists', '=', 'yes')]
            if after:
                expected += [('is_ai', '=', 'no')]
            nodes = fs['target_root_trigger']['value']
            self.assertEqual([(x['key'], x['op'], x['value']) for x in nodes], expected)
            self.assertEqual([(x['key'], x['op'], x['value']) for x in fs['ai_will_do']['value']],
                             [('factor', '=', '0')])
            for exists in (False, True):
                self.assertEqual(root_value(nodes, exists, False), exists)
                self.assertEqual(root_value(nodes, exists, True), exists and not after)
        self.assertEqual(audit.sha(restored), B['before_sha256'])
        self.assertEqual(restored.count(b'\r\n'), raw.count(b'\r\n'))
        self.assertEqual(restored.startswith(b'\xef\xbb\xbf'), raw.startswith(b'\xef\xbb\xbf'))

    def test_pure_closure_direct_ui_and_bound_sources(self):
        for rel, digest in B['input_sha256'].items():
            raw = (audit.ROOT / rel).read_bytes()
            if rel == FRAMEWORK:
                raw = canonical_framework_view(raw)
            self.assertEqual(audit.sha(raw), digest, rel)
        proof = audit.audit_source(SOURCE_PATH.read_text(encoding='utf-8-sig'))
        for p in B['patches']:
            self.assertEqual(proof[p['id']]['direct_ui_id'], p['direct_ui_id'])
            self.assertEqual(proof[p['id']]['closure'], p['closure'])
        registry = audit.trigger_registry()
        for body in ('set_temp_variable = { x = 1 }', 'set_variable = { x = 1 }',
                     'random_country = { always = yes }', 'clear_array = x',
                     'unknown_operation = yes'):
            with self.assertRaises(ValueError):
                audit.pure(audit.parse(body), registry)

    def test_framework_source_view_rejects_unrelated_edits(self):
        raw = (audit.ROOT / FRAMEWORK).read_bytes()
        self.assertEqual(audit.sha(canonical_framework_view(raw)), B["input_sha256"][FRAMEWORK])
        for mutant in (b" " + raw, raw + b"# unrelated drift", raw.replace(b"factor = 10", b"factor = 11", 1)):
            self.assertNotEqual(mutant, raw)
            with self.assertRaises(ValueError):
                canonical_framework_view(mutant)

    def test_other_weights_and_no_explicit_decision_activation(self):
        zero = nonzero = 0
        for rel in (audit.SOURCE, audit.INPUTS[-2], audit.INPUTS[-1]):
            path = SOURCE_PATH if rel == audit.SOURCE else audit.ROOT / rel
            category = audit.parse(path.read_text(encoding='utf-8-sig'))[0]
            for decision in category['value']:
                fs = audit.fields(decision['value'])
                if 'ai_will_do' not in fs:
                    continue
                if [(x['key'], x['op'], x['value']) for x in fs['ai_will_do']['value']] == [('factor', '=', '0')]:
                    zero += 1
                else:
                    nonzero += 1
        self.assertEqual((zero, nonzero), (37, 22))
        # Scan only repository game folders; never .local or linked test mounts.
        operation = re.compile(r'\b(?:activate_targeted_decision|activate_decision|has_decision|remove_decision)\s*=')
        for directory in ('common', 'events'):
            for path in (audit.ROOT / directory).rglob('*.txt'):
                text = path.read_text(encoding='utf-8-sig')
                if operation.search(text):
                    self.assertFalse(any(re.search(r'\b' + re.escape(id) + r'\b', text) for id in audit.IDS), str(path))

if __name__ == '__main__':
    unittest.main()
