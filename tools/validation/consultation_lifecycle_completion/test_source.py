"""Ten bounded source deltas, strict semantics and negative byte controls."""
from pathlib import Path
import importlib.util
import sys
import unittest

import _support as s
import _source_guard as g

ALLOWED = {
    s.FILES[0]: {'eon_consultation_clear_pending', 'eon_consultation_resolve_invalid_request',
                 'eon_consultation_withdraw_request', 'eon_consultation_daily_cleanup'},
    s.FILES[1]: {'eon_consultation_base_pair_available', 'eon_consultation_draft_current',
                 'eon_consultation_draft_send_ready', 'eon_consultation_response_pair_current',
                 'eon_consultation_response_valid', 'eon_consultation_withdraw_available'},
}


class SourceBoundaries(unittest.TestCase):
    def test_exact_ten_islands_and_all_outside_bytes(self):
        journal = g.load_journal()
        self.assertEqual(set(journal['files']), set(ALLOWED))
        for rel, names in ALLOWED.items():
            with self.subTest(path=rel):
                entry = journal['files'][rel]
                self.assertEqual({i['name'] for i in entry['islands']}, names)
                self.assertEqual(len(entry['islands']), len(names))
                restored = g.restore_before(rel)
                self.assertEqual(g.sha(restored), entry['before_sha256'])
                self.assertEqual(g.sha((s.ROOT / rel).read_bytes()), entry['after_sha256'])

    def test_each_island_and_unrelated_bytes_reject_mutation(self):
        for rel, entry in g.load_journal()['files'].items():
            raw = (s.ROOT / rel).read_bytes()
            mutations = [raw + b'\n', b'\xef\xbb\xbf' + raw, raw.replace(b'\n', b'\r\n'),
                         raw.replace(b'# ', b'# changed ', 1)]
            for island in entry['islands']:
                token = island['after'].encode()
                mutations.extend((raw.replace(token, island['before'].encode()),
                                  raw.replace(token, token.replace(b' = ', b' =  ', 1)),
                                  raw + token))
            for index, mutation in enumerate(mutations):
                with self.subTest(path=rel, mutant=index):
                    self.assertNotEqual(raw, mutation)
                    with self.assertRaises(AssertionError):
                        g.restore_before(rel, mutation)

    def test_parsed_source_known_grammar_and_exact_reference_resolution(self):
        spec = importlib.util.spec_from_file_location('consultation_core_grammar',
            s.ROOT / 'tools/validation/diplomacy_completion/check_native_grammar.py')
        grammar = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(grammar)
        all_definitions = set()
        trees = []
        for rel in s.FILES:
            tree = grammar.parser.ast((s.ROOT / rel).read_bytes())
            self.assertFalse(grammar.inspect(tree), rel)
            names = [key for key, op, value in tree]
            self.assertEqual(len(names), len(set(names)))
            all_definitions.update(names); trees.append(tree)
        for tree in trees:
            for name, op, value in grammar.walk(tree):
                if name.startswith('eon_consultation_') and isinstance(value, str) and value in ('yes', 'no'):
                    self.assertIn(name, all_definitions)

    def test_existing_ui_adapter_has_native_scalar_flag_boundary(self):
        spec = importlib.util.spec_from_file_location('consultation_root_ui_adapter',
            s.ROOT / 'tools/validation/diplomacy_channel_ui/_support.py')
        ui = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ui)
        state = ui.state(); context = ui.ctx('A', 'B')
        state['global']['temps']['probe_country'] = ui.IDS['B']
        proper = ui.flag_key(state, context, 'probe@FROM')
        self.assertNotEqual(proper, ui.flag_key(state, context, 'probe@probe_country'))
        self.assertEqual(ui.key(state, context, 'probe@probe_country'), proper)
        self.assertEqual(ui.flag_key(state, context, 'probe@USA'), 'probe@literal:USA')
        state['countries']['A']['flags'].add(proper)
        self.assertTrue(ui.condition(ui.parse('has_country_flag = probe@FROM'), state, context))
        self.assertFalse(ui.condition(ui.parse('has_country_flag = probe@probe_country'), state, context))
        ui.execute(ui.parse('clr_country_flag = probe@probe_country'), state, context)
        self.assertIn(proper, state['countries']['A']['flags'])


if __name__ == '__main__':
    unittest.main()
