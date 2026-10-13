"""Actual current-source response lifecycle; never native AI selection proof."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools/validation/ai_policy'))
from test_alliance_initiative import fixture
from _support import ast, one

REL = 'common/scripted_diplomatic_actions/eon_defensive_alliance_action.txt'
CATALOG = json.loads((HERE / 'canonical_alliance_selectable.json').read_text(encoding='utf-8'))
BEFORE = (HERE / 'fixtures/alliance_action_before_selectable.txt').read_bytes()
assert hashlib.sha256(BEFORE).hexdigest() == 'cf0e6b7920676d1896cfc192d9ad9c1869fd5ab6884863498aa7bdd613ec713d'
assert CATALOG['before_sha256'] == hashlib.sha256(BEFORE).hexdigest()
assert CATALOG['after_sha256'] == '64383ca1c9c8af0e5794479730c054bc171eb31664254467447b32f848581b88'

def current_bytes():
    return (ROOT / REL).read_bytes()

def action(raw):
    return one(one(ast(raw), 'scripted_diplomatic_actions'), 'eon_propose_defensive_alliance')

def reviewed_inverse(raw):
    after = CATALOG['field_after'].encode('utf-8')
    before = CATALOG['field_before'].encode('utf-8')
    assert raw.count(after) == 1, 'Missing or duplicated canonical selectable island'
    return raw.replace(after, before, 1)

def model(sender_ai=True, recipient_ai=True, root=1, current=2, baseline=False):
    m = fixture()
    m.action = action(BEFORE if baseline else current_bytes())
    m.root, m.current = root, current
    for country in m.countries.values():
        country.neighbors.clear(); country.wargoals.clear(); country.justifications.clear(); country.opinions.clear()
    m.countries[root].ai, m.countries[current].ai = sender_ai, recipient_ai
    m.countries[root].neighbors.add(current)
    m.countries[current].neighbors.add(root)
    m.countries[root].opinions[current] = m.countries[current].opinions[root] = 150
    next(peer for ident, peer in m.countries.items() if ident not in (root, current)).wargoals.add(root)
    return m

def send(m):
    m.action_effect('on_sent_effect')

class AllianceResponses(unittest.TestCase):
    def test_current_whole_file_inverse_and_original_branch_exact(self):
        raw = current_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), CATALOG['after_sha256'])
        self.assertEqual(reviewed_inverse(raw), BEFORE)
        old, new = action(BEFORE), action(raw)
        self.assertEqual([n for n in old if n[0] != 'selectable'], [n for n in new if n[0] != 'selectable'])
        choices = one(one(new, 'selectable'), 'OR')
        self.assertEqual(choices[0], ('AND', '=', one(old, 'selectable')))
        self.assertEqual(choices[1][2], [('is_ai', '=', 'yes'), ('eon_defensive_alliance_offer_response_current', '=', 'yes')])
        self.assertEqual(raw.startswith(b'\xef\xbb\xbf'), BEFORE.startswith(b'\xef\xbb\xbf'))
        self.assertEqual(b'\r\n' in raw, b'\r\n' in BEFORE)
        self.assertEqual(b'\n' in raw.replace(b'\r\n', b''), b'\n' in BEFORE.replace(b'\r\n', b''))

    def test_inverse_rejects_missing_duplicate_and_external_mutants(self):
        raw = current_bytes(); span = CATALOG['field_after'].encode('utf-8')
        for mutant in (raw.replace(span, b'', 1), raw + span):
            with self.assertRaises(AssertionError): reviewed_inverse(mutant)
        for mutant in (raw.replace(b'cost = 0', b'cost = 1'), b'# external\n' + raw, raw + b'# external\n'):
            self.assertNotEqual(reviewed_inverse(mutant), BEFORE)

    def test_ai_current_response_selectable_but_new_send_and_desire_closed(self):
        m = model()
        self.assertTrue(m.ready())
        self.assertEqual(m.proposal_score(), 50)
        send(m)
        self.assertTrue(m.trigger(one(m.action, 'selectable')))
        self.assertFalse(m.trigger(one(m.action, 'can_be_sent')))
        self.assertFalse(m.ready())
        self.assertEqual(m.proposal_score(), 0)
        self.assertTrue(m.trigger(one(m.action, 'can_be_accepted')))
        self.assertFalse(m.factions)

    def test_human_sender_ai_recipient_retains_consensual_response(self):
        m = model(sender_ai=False)
        self.assertTrue(m.ready())
        send(m)
        self.assertTrue(m.trigger(one(m.action, 'selectable')))
        self.assertFalse(m.trigger(one(m.action, 'can_be_sent')))
        self.assertEqual(m.proposal_score(), 0)
        self.assertTrue(m.trigger(one(m.action, 'can_be_accepted')))
        self.assertEqual(m.factions, {})

    def test_human_recipient_behavior_exact_before_and_after_pending(self):
        for sender_ai in (False, True):
            old, new = model(sender_ai=sender_ai, recipient_ai=False, baseline=True), model(sender_ai=sender_ai, recipient_ai=False)
            for phase in ('before', 'pending'):
                if phase == 'pending': send(old); send(new)
                for field in ('selectable', 'can_be_sent', 'can_be_accepted'):
                    self.assertEqual(old.trigger(one(old.action, field)), new.trigger(one(new.action, field)))
            self.assertFalse(new.trigger(one(new.action, 'selectable')))

    def test_other_real_root_ids_have_the_same_reciprocal_scope(self):
        for root, current in ((1, 2), (3, 4)):
            m = model(root=root, current=current)
            send(m)
            with self.subTest(root=root, current=current):
                self.assertTrue(m.trigger(one(m.action, 'selectable')))
                self.assertFalse(m.trigger(one(m.action, 'can_be_sent')))
                self.assertTrue(m.trigger(one(m.action, 'can_be_accepted')))
                self.assertEqual(m.countries[current].variables['eon_defensive_alliance_pending_sender'], root)
                self.assertEqual(m.countries[root].variables['eon_defensive_alliance_pending_recipient'], current)

    def test_reverse_third_stale_and_one_sided_reservations_closed(self):
        for mutation in ('reverse', 'third_sender', 'third_receiver', 'one_sided_sender', 'one_sided_receiver', 'stale_zero'):
            m = model(); send(m)
            if mutation == 'reverse': m.root, m.current = 2, 1
            if mutation == 'third_sender': m.root = 3
            if mutation == 'third_receiver': m.current = 3
            if mutation == 'one_sided_sender': m.countries[1].variables['eon_defensive_alliance_pending_recipient'] = 3
            if mutation == 'one_sided_receiver': m.countries[2].variables['eon_defensive_alliance_pending_sender'] = 3
            if mutation == 'stale_zero': m.countries[2].variables['eon_defensive_alliance_pending_sender'] = 0
            with self.subTest(mutation=mutation):
                for field in ('selectable', 'can_be_sent', 'can_be_accepted'):
                    self.assertFalse(m.trigger(one(m.action, field)))

    def test_changed_rights_do_not_manufacture_acceptance_or_execution(self):
        for mutation in ('national_sender', 'national_receiver', 'subject', 'war'):
            m = model(); send(m)
            if mutation == 'national_sender': m.countries[1].rules['can_create_factions'] = False
            if mutation == 'national_receiver': m.countries[2].rules['can_join_factions'] = False
            if mutation == 'subject': m.countries[2].subject = True
            if mutation == 'war': m.countries[1].wars.add(2); m.countries[2].wars.add(1)
            self.assertTrue(m.trigger(one(m.action, 'selectable')))
            self.assertFalse(m.trigger(one(m.action, 'can_be_sent')))
            self.assertFalse(m.trigger(one(m.action, 'can_be_accepted')))
            m.action_effect('complete_effect')
            self.assertEqual(m.factions, {})
            self.assertEqual(m.native_calls, [])

    def test_repeated_source_send_keeps_existing_reservation(self):
        m = model(); send(m)
        before = deepcopy((m.countries, m.factions, m.native_calls))
        send(m)
        self.assertEqual((m.countries, m.factions, m.native_calls), before)
        # Native callback attempts still need a separate duplicate census.

    def test_original_accept_reject_terminal_and_replay_guards_remain(self):
        for response in ('complete_effect', 'reject_effect'):
            m = model(); send(m); m.action_effect(response)
            self.assertEqual(m.countries[1].variables.get('eon_defensive_alliance_pending_recipient', 0), 0)
            self.assertEqual(m.countries[2].variables.get('eon_defensive_alliance_pending_sender', 0), 0)
            if response == 'complete_effect':
                self.assertIsNotNone(m.countries[1].faction)
                self.assertEqual(m.countries[1].faction, m.countries[2].faction)
            else: self.assertEqual(m.factions, {})
            before = deepcopy((m.countries, m.factions, m.native_calls))
            m.action_effect(response)
            self.assertEqual((m.countries, m.factions, m.native_calls), before)

if __name__ == '__main__': unittest.main(verbosity=2)
