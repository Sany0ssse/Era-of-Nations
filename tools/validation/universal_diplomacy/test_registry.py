"""Current-source legacy pair regressions with native24 flag selector semantics.

Raw old-save receipts are supplied as fixtures. These tests execute the actual
script AST; they do not load a native .hoi4 save or prove campaign behavior.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
ADAPTER = ROOT / 'tools/validation/diplomacy_package_26/test_relations.py'
spec = importlib.util.spec_from_file_location('registry_relations_adapter', ADAPTER)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
P = m.P
PEERS = ('GER', 'GRE', 'HEZ', 'IRQ', 'ISR', 'KUR', 'KUW', 'NKO', 'PER', 'SAU', 'TUR', 'USA')
NATIONAL_PATHS = ('events/Iraq.txt', 'events/Iran.txt', 'common/decisions/Iran.txt',
    'common/scripted_effects/eon_per_usa_normalization_effects.txt', 'history/countries/PER - Iran.txt',
    *('common/national_focus/' + name + '_Focus_Tree.txt' for name in ('Botswana', 'Iraq', 'Iran', 'Greece', 'Germany')))
for country in ('BRA', 'BOT', 'NEP'):
    m.IDS.setdefault(country, len(m.IDS) + 1)


def frame(actor, peer):
    return m.ctx(actor, peer) | {'prev': [peer]}


def pair(state, name, actor, peer):
    return m.condition([(P + name, '=', 'yes')], state, frame(actor, peer))


def write_raw(state, actor, peer, known=True, active=True):
    commands = []
    if known: commands.append(('set_country_flag', '=', P + 'legacy_known@' + peer))
    if active: commands.append(('set_country_flag', '=', P + 'legacy_no_ties@' + peer))
    m.execute(commands, state, m.ctx(actor, peer))


def migrate(state, actor, peer):
    m.execute(m.EFFECTS[P + 'legacy_migrate_pair'], state, frame(actor, peer))


class RegistryTests(unittest.TestCase):
    def test_native24_literal_flags_differ_from_variable_country_suffixes(self):
        state = m.state()
        context = frame('GER', 'USA')
        m.execute(m.parse('set_country_flag = raw@USA set_country_flag = proper@PREV set_variable = { sample@USA = 7 }'), state, context)
        self.assertTrue(m.hasflag(state, context, 'raw@USA'))
        self.assertFalse(m.hasflag(state, context, 'raw@PREV'))
        self.assertFalse(m.hasflag(state, context, 'proper@USA'))
        self.assertTrue(m.hasflag(state, context, 'proper@PREV'))
        self.assertEqual(m.value(state, context, 'sample@USA'), 7)
        self.assertEqual(m.value(state, context, 'sample@PREV'), 7)
        m.execute(m.parse('clr_country_flag = proper@USA'), state, context)
        self.assertTrue(m.hasflag(state, context, 'proper@PREV'))
        m.execute(m.parse('clr_country_flag = proper@PREV'), state, context)
        self.assertFalse(m.hasflag(state, context, 'proper@PREV'))
        self.assertFalse(m.hasflag(state, frame('GER', 'BRA'), 'raw@PREV'))

    def test_old_raw_break_is_exact_before_tick_and_migrates_once(self):
        for actor in ('GER', 'BRA', 'BOT', 'NEP'):
            for peer in PEERS:
                if peer == actor: continue
                with self.subTest(actor=actor, peer=peer):
                    state = m.state()
                    state['global_flags'].clear()
                    write_raw(state, actor, peer)
                    state['countries'][actor]['opinion_modifiers'].add((peer, 'no_diplomatic_ties'))
                    before = deepcopy(state)
                    self.assertTrue(pair(state, 'legacy_pair_active', actor, peer))
                    self.assertFalse(pair(state, 'legacy_pair_active', actor, 'F'))
                    self.assertFalse(pair(state, 'legacy_pair_active', peer, actor))
                    self.assertEqual(state, before, 'queries are pure')
                    self.assertFalse(pair(state, 'relations_state_available', actor, peer))
                    migrate(state, actor, peer)
                    self.assertTrue(m.flag(state, 'legacy_known', actor, peer))
                    self.assertTrue(m.flag(state, 'legacy_no_ties', actor, peer))
                    self.assertFalse(m.hasflag(state, frame(actor, peer), P + 'legacy_known@' + peer))
                    self.assertFalse(m.hasflag(state, frame(actor, peer), P + 'legacy_no_ties@' + peer))
                    expected = deepcopy(before)
                    flags = expected['countries'][actor]['flags']
                    flags.difference_update({P + 'legacy_known@literal:' + peer, P + 'legacy_no_ties@literal:' + peer})
                    flags.update({P + 'legacy_known@' + peer, P + 'legacy_no_ties@' + peer})
                    self.assertEqual(state, expected, 'only these two directed receipt keys change')
                    migrate(state, actor, peer)
                    self.assertEqual(state, expected)

    def test_raw_restored_and_orphan_active_receipts(self):
        for known, active in ((True, False), (False, True)):
            state = m.state()
            state['global_flags'].clear()
            write_raw(state, 'BRA', 'SAU', known, active)
            self.assertTrue(pair(state, 'legacy_pair_known', 'BRA', 'SAU'))
            self.assertEqual(pair(state, 'legacy_pair_active', 'BRA', 'SAU'), active)
            migrate(state, 'BRA', 'SAU')
            self.assertTrue(m.flag(state, 'legacy_known', 'BRA', 'SAU'))
            self.assertEqual(m.flag(state, 'legacy_no_ties', 'BRA', 'SAU'), active)
            self.assertEqual(pair(state, 'relations_state_available', 'BRA', 'SAU'), not active)

    def test_proper_known_receipt_is_authoritative_over_stale_raw_state(self):
        for proper_active in (False, True):
            state = m.state()
            state['global_flags'].clear()
            state['countries']['GER']['flags'].add(P + 'legacy_known@SAU')
            if proper_active: state['countries']['GER']['flags'].add(P + 'legacy_no_ties@SAU')
            write_raw(state, 'GER', 'SAU', True, not proper_active)
            before = deepcopy(state)
            self.assertEqual(pair(state, 'legacy_pair_active', 'GER', 'SAU'), proper_active)
            migrate(state, 'GER', 'SAU')
            expected = deepcopy(before)
            expected['countries']['GER']['flags'].difference_update({P + 'legacy_known@literal:SAU', P + 'legacy_no_ties@literal:SAU'})
            self.assertEqual(state, expected)
            self.assertEqual(pair(state, 'legacy_pair_active', 'GER', 'SAU'), proper_active)
        # An incomplete proper break is retained; migration never clears it.
        state = m.state()
        state['countries']['GER']['flags'].add(P + 'legacy_no_ties@SAU')
        write_raw(state, 'GER', 'SAU', True, False)
        migrate(state, 'GER', 'SAU')
        self.assertTrue(pair(state, 'legacy_pair_active', 'GER', 'SAU'))

    def test_modern_records_are_preserved_and_broken_pair_stays_closed(self):
        for modern, raw_active in (('established', True), ('broken', False)):
            state = m.state()
            owner = state['countries']['BRA']
            owner['flags'].add(P + modern + '@SAU')
            owner['variables'][P + 'relation_record@SAU'] = 1 if modern == 'established' else 2
            write_raw(state, 'BRA', 'SAU', True, raw_active)
            variables = deepcopy(owner['variables'])
            arrays = deepcopy(owner['arrays'])
            migrate(state, 'BRA', 'SAU')
            self.assertTrue(m.flag(state, modern, 'BRA', 'SAU'))
            self.assertEqual(owner['variables'], variables)
            self.assertEqual(owner['arrays'], arrays)
            self.assertFalse(pair(state, 'relations_state_available', 'BRA', 'SAU'))
            # Missing proper_known is deliberately not a new authority rule:
            # a raw national break still blocks an established receipt.
            self.assertEqual(pair(state, 'legacy_pair_active', 'BRA', 'SAU'), raw_active)

    def test_bounded_country_pass_uses_twelve_unique_peers_then_is_inert(self):
        state = m.state()
        state['global_flags'].clear()
        for index, peer in enumerate(PEERS): write_raw(state, 'BRA', peer, True, index % 2 == 0)
        reverse = deepcopy(state['countries']['SAU'])
        m.execute(m.EFFECTS[P + 'legacy_migrate_country'], state, m.ctx('BRA', 'SAU'))
        self.assertIn(P + 'legacy_literal_compat_done', state['countries']['BRA']['flags'])
        for index, peer in enumerate(PEERS):
            self.assertTrue(m.flag(state, 'legacy_known', 'BRA', peer))
            self.assertEqual(m.flag(state, 'legacy_no_ties', 'BRA', peer), index % 2 == 0)
        self.assertEqual(state['global_flags'], set(), 'compatibility does not certify fresh history')
        self.assertEqual(state['countries']['SAU'], reverse)
        before = deepcopy(state)
        m.execute(m.EFFECTS[P + 'legacy_migrate_country'], state, m.ctx('BRA', 'SAU'))
        self.assertEqual(state, before)
        body = m.one(m.EFFECTS[P + 'legacy_migrate_country'], 'if')
        country_scopes = [name for name, op, data in body if name in PEERS]
        self.assertEqual(country_scopes, list(PEERS))
        self.assertNotRegex(str(body), r'every_(?:possible_)?country')
        self.assertEqual(m.EFFECTS[P + 'daily_update'][0], (P + 'legacy_migrate_country', '=', 'yes'))

    def test_national_history_regression_rejects_original_literal_writer(self):
        state = m.state()
        # This is the original two-command island, with an actual country tag.
        old = m.parse('set_country_flag = eon_diplomatic_relations_legacy_known@USA set_country_flag = eon_diplomatic_relations_legacy_no_ties@USA')
        m.execute(old, state, m.ctx('PER', 'USA'))
        self.assertFalse(m.flag(state, 'legacy_known', 'PER', 'USA'))
        self.assertFalse(m.flag(state, 'legacy_no_ties', 'PER', 'USA'))
        fixed = m.state()
        m.legacy_no_ties(fixed, 'PER', 'USA')
        self.assertTrue(m.flag(fixed, 'legacy_known', 'PER', 'USA'))
        self.assertTrue(m.flag(fixed, 'legacy_no_ties', 'PER', 'USA'))
        self.assertFalse(m.flag(fixed, 'legacy_no_ties', 'PER', 'BRA'))

    def test_national_sources_have_no_remaining_literal_flag_mutations(self):
        forbidden = re.compile(r'\b(?:set|clr)_country_flag\s*=\s*' + P + r'legacy_(?:known|no_ties)@[A-Z]{3}\b')
        for path in NATIONAL_PATHS:
            self.assertIsNone(forbidden.search((ROOT / path).read_text(encoding='utf-8-sig')), path)

    def test_all_twenty_eight_wrappers_execute_actual_country_pairs(self):
        pattern = re.compile(r'\b([A-Z]{3})\s*=\s*\{\s*PREV\s*=\s*\{\s*'
            r'set_country_flag\s*=\s*' + P + r'legacy_known@PREV\s*'
            r'(set|clr)_country_flag\s*=\s*' + P + r'legacy_no_ties@PREV\s*\}\s*\}')
        found = 0
        for path in NATIONAL_PATHS:
            for match in pattern.finditer((ROOT / path).read_text(encoding='utf-8-sig')):
                found += 1
                peer, command = match.groups()
                for actor in ('BRA', 'NEP'):
                    state = m.state()
                    # Removing a restriction must clear an actual populated key.
                    state['countries'][actor]['flags'].add(P + 'legacy_no_ties@' + peer)
                    expected = deepcopy(state)
                    flags = expected['countries'][actor]['flags']
                    flags.add(P + 'legacy_known@' + peer)
                    if command == 'clr': flags.discard(P + 'legacy_no_ties@' + peer)
                    m.execute(m.parse(match[0]), state, m.ctx(actor, 'F'))
                    self.assertEqual(state, expected, (path, actor, peer))
                    mutant = m.state()
                    old = 'set_country_flag = ' + P + 'legacy_known@' + peer + ' ' + command + '_country_flag = ' + P + 'legacy_no_ties@' + peer
                    m.execute(m.parse(old), mutant, m.ctx(actor, 'F'))
                    self.assertFalse(m.flag(mutant, 'legacy_known', actor, peer), 'original literal writer must fail actual pair assertion')
        self.assertEqual(found, 28)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RegistryTests))
    print(json.dumps({'all_passed': result.wasSuccessful(), 'tests': result.testsRun,
        'literal_peer_tags': list(PEERS), 'native_runtime': False, 'native_save_load': False,
        'proof_scope': 'actual source AST and supplied raw receipts; flag-selector semantics bound to native24',
        'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in [*m.FILES[:2], ADAPTER.relative_to(ROOT).as_posix()]}}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
