"""Current-source six selectors. Model dispatch is not native war/timer proof."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import sys
import unittest

HERE = Path(__file__).resolve().parent
from test_transport import Transport, KINDS, ast, one, ROOT
from reserved_selector_compat import restore_reserved_selectors, BEFORE_SHA, AFTER_SHA, CATALOG_SHA
catalog_raw = (HERE / 'canonical_reserved_selectors.json').read_bytes()
assert hashlib.sha256(catalog_raw).hexdigest() == CATALOG_SHA, 'Reviewed catalog bytes changed'
MANIFEST = json.loads(catalog_raw)
ACTION = MANIFEST['source_path']
TRIGGER = 'common/scripted_triggers/eon_peace_settlement_triggers.txt'
TRIGGER_SHA = '5f0171c324095f53294008e11fd396b34a4b5e46d63ec58d2c84f3c4a8222f90'
# Candidate means the actual current checkout, never a candidate fixture.
RAW = {'before': (HERE / 'fixtures/peace_actions_before_reserved_selectable.txt').read_bytes(),
       'candidate': (ROOT / ACTION).read_bytes()}
ACTIONS = {name: dict((k, v) for k, _, v in one(ast(raw), 'scripted_diplomatic_actions')) for name, raw in RAW.items()}

def inverse(raw):
    for fields in MANIFEST['fields'].values():
        after = fields['after'].encode(); before = fields['before'].encode()
        assert raw.count(after) == 1, 'Missing/duplicate reviewed selector island'
        raw = raw.replace(after, before, 1)
    return raw

def model(kind, candidate=True, sender_ai=False, recipient_ai=True, root=1, current=2):
    m = Transport()
    m.actions.update(deepcopy(ACTIONS['candidate' if candidate else 'before']))
    m.root, m.from_ = root, current
    for country in m.countries.values():
        country.enemies.clear(); country.defensive.clear(); country.offensive.clear()
    m.countries[root].enemies.add(current); m.countries[current].enemies.add(root)
    m.countries[root].defensive.add(current); m.countries[current].offensive.add(root)
    m.countries[root].ai, m.countries[current].ai = sender_ai, recipient_ai
    m.countries[root].variables.update(eon_peace_draft_target=current, eon_peace_draft_kind=kind)
    return m

def gate(m, action, key): return m.truth(one(m.actions[action], key), current=m.from_)
def run(m, action, key): m.effect(one(m.actions[action], key), current=m.from_)
def sent(kind, action, candidate=True, root=1, current=2):
    m = model(kind, candidate, root=root, current=current)
    assert gate(m, action, 'can_be_sent')
    run(m, action, 'on_sent_effect')
    return m

class ReservedSelectors(unittest.TestCase):
    def test_six_field_whole_byte_inverse_encoding_and_current_trigger_hash(self):
        self.assertEqual(hashlib.sha256(RAW['before']).hexdigest(), MANIFEST['before_sha256'])
        self.assertEqual(hashlib.sha256(RAW['candidate']).hexdigest(), MANIFEST['after_sha256'])
        self.assertEqual(inverse(RAW['candidate']), RAW['before'])
        self.assertEqual(hashlib.sha256((ROOT / TRIGGER).read_bytes()).hexdigest(), TRIGGER_SHA)
        for check in (lambda b: b.startswith(b'\xef\xbb\xbf'), lambda b: b'\r\n' in b, lambda b: b'\n' in b.replace(b'\r\n', b''), lambda b: b.endswith(b'\n')):
            self.assertEqual(check(RAW['before']), check(RAW['candidate']))

    def test_all_other_fields_and_original_ai_subject_pair_islands_exact(self):
        self.assertEqual(ACTIONS['before'].keys(), ACTIONS['candidate'].keys())
        for kind, action, ordinal, cost in KINDS:
            old, new = ACTIONS['before'][action], ACTIONS['candidate'][action]
            self.assertEqual([n for n in old if n[0] != 'selectable'], [n for n in new if n[0] != 'selectable'])
            choices = one(one(new, 'selectable'), 'OR')
            self.assertEqual(choices[0], ('AND', '=', one(old, 'selectable')))
            self.assertEqual(choices[1][2], [('is_ai', '=', 'yes'), ('has_country_flag', '=', 'eon_peace_reserved_' + kind + '@ROOT'),
                                            ('ROOT', '=', [('has_country_flag', '=', 'eon_peace_reserved_' + kind + '@PREV')])])

    def test_valid_reserved_response_old_blocked_candidate_open_but_send_closed(self):
        for kind, action, ordinal, cost in KINDS:
            old, new = sent(ordinal, action, False), sent(ordinal, action, True)
            with self.subTest(kind=kind):
                self.assertFalse(gate(old, action, 'selectable'))
                self.assertTrue(gate(new, action, 'selectable'))
                self.assertTrue(gate(new, action, 'can_be_accepted'))
                for _, other, _, _ in KINDS:
                    self.assertFalse(gate(new, other, 'can_be_sent'))
                    if other != action: self.assertFalse(gate(new, other, 'selectable'))

    def test_expired_or_removed_timed_pending_stays_selectable_but_complete_rejects(self):
        for kind, action, ordinal, cost in KINDS:
            for expiry in ('expired', 'removed'):
                m = sent(ordinal, action)
                if expiry == 'expired': m.day = 31
                else:
                    for owner, peer in ((1, 2), (2, 1)):
                        m.countries[owner].flags.pop('eon_peace_pending_' + kind + '@' + str(peer))
                before = deepcopy(m.countries)
                with self.subTest(kind=kind, expiry=expiry):
                    self.assertTrue(gate(m, action, 'selectable'))
                    self.assertFalse(gate(m, action, 'can_be_accepted'))
                    self.assertFalse(any(gate(m, a, 'can_be_sent') for _, a, _, _ in KINDS))
                    self.assertEqual(m.countries, before, 'A query must never release the untimed reservation')
                    run(m, action, 'complete_effect')
                    self.assertEqual(m.calls, [('eon_peace_reject_' + kind, 2, 1)])

    def test_root_sender_human_or_ai_does_not_change_reserved_identity(self):
        for kind, action, ordinal, cost in KINDS:
            for sender_ai in (False, True):
                m = sent(ordinal, action); m.countries[1].ai = sender_ai
                self.assertTrue(gate(m, action, 'selectable'))
                self.assertFalse(gate(m, action, 'can_be_sent'))
                self.assertTrue(gate(m, action, 'can_be_accepted'))
                # AI initiation restrictions for other kinds are deliberately unchanged.

    def test_human_recipient_before_pending_and_expired_behavior_unchanged(self):
        for kind, action, ordinal, cost in KINDS:
            old, new = model(ordinal, False, recipient_ai=False), model(ordinal, True, recipient_ai=False)
            for phase in ('before', 'pending', 'expired'):
                if phase == 'pending': run(old, action, 'on_sent_effect'); run(new, action, 'on_sent_effect')
                if phase == 'expired': old.day = new.day = 31
                with self.subTest(kind=kind, phase=phase):
                    for field in ('visible', 'selectable', 'can_be_sent', 'can_be_accepted'):
                        self.assertEqual(gate(old, action, field), gate(new, action, field))

    def test_one_sided_zero_wrong_kind_and_third_pair_reserved_branches_closed(self):
        for kind, action, ordinal, cost in KINDS:
            for mutation in ('sender_missing', 'recipient_missing', 'sender_zero', 'recipient_zero', 'third_sender', 'third_receiver'):
                m = sent(ordinal, action)
                if mutation.endswith('missing'):
                    owner, peer = (1, 2) if mutation.startswith('sender') else (2, 1)
                    m.countries[owner].flags.pop('eon_peace_reserved_' + kind + '@' + str(peer))
                if mutation.endswith('zero'):
                    owner, peer = (1, 2) if mutation.startswith('sender') else (2, 1)
                    m.countries[owner].flag_values['eon_peace_reserved_' + kind + '@' + str(peer)] = 0
                if mutation == 'third_sender': m.root = 3
                if mutation == 'third_receiver': m.from_ = 3
                with self.subTest(kind=kind, mutation=mutation):
                    self.assertFalse(gate(m, action, 'selectable'))
                    self.assertFalse(gate(m, action, 'can_be_accepted'))
            m = sent(ordinal, action)
            for other_kind, other_action, _, _ in KINDS:
                if other_kind != kind: self.assertFalse(gate(m, other_action, 'selectable'))

    def test_arbitrary_root_scope_and_symmetric_reverse_cannot_send_again(self):
        for kind, action, ordinal, cost in KINDS:
            for root, current in ((1, 2), (3, 4)):
                m = sent(ordinal, action, root=root, current=current)
                self.assertTrue(gate(m, action, 'selectable'))
                self.assertFalse(gate(m, action, 'can_be_sent'))
                m.countries[root].ai = True
                m.root, m.from_ = current, root
                self.assertTrue(gate(m, action, 'selectable'), 'Per-kind reciprocal reservation is symmetric, not direction metadata')
                self.assertFalse(gate(m, action, 'can_be_sent'))

    def test_invalid_rights_rule_or_cash_do_not_enable_acceptance_or_execute(self):
        for kind, action, ordinal, cost in KINDS:
            for mutation in ('subject', 'capitulated', 'disabled', 'cash'):
                if mutation == 'cash' and cost == 0: continue
                m = sent(ordinal, action)
                if mutation == 'subject': m.countries[1].subject = True
                if mutation == 'capitulated': m.countries[2].capitulated = True
                if mutation == 'disabled': m.rules['peace_deal_AI'] = 'DISABLED'
                if mutation == 'cash': m.countries[1].variables['treasury'] = cost - .001
                with self.subTest(kind=kind, mutation=mutation):
                    self.assertTrue(gate(m, action, 'selectable'))
                    self.assertFalse(gate(m, action, 'can_be_accepted'))
                    run(m, action, 'complete_effect')
                    self.assertEqual(m.calls, [('eon_peace_reject_' + kind, 2, 1)])

    def test_repeat_on_sent_no_replacement_and_accepted_dispatch_exact(self):
        for kind, action, ordinal, cost in KINDS:
            m = sent(ordinal, action); before = deepcopy(m.countries)
            run(m, action, 'on_sent_effect')
            self.assertEqual(m.countries, before)
            self.assertEqual(m.calls, [])
            run(m, action, 'complete_effect')
            self.assertEqual(m.calls, [('eon_peace_execute_' + kind, 2, 1)])
            # Model execution helpers are dispatch boundaries, not native world/cleanup emulation.

    def test_inverse_missing_duplicate_external_and_scope_mutants_fail(self):
        raw = RAW['candidate']
        for info in MANIFEST['fields'].values():
            span = info['after'].encode()
            for mutant in (raw.replace(span, b'', 1), raw + span, raw.replace(span, span.replace(b'@PREV', b'@ROOT'), 1)):
                with self.assertRaises(AssertionError): inverse(mutant)
        for mutant in (b'# outside\n' + raw, raw + b'# outside\n', raw.replace(b'cost = 0', b'cost = 1', 1)):
            self.assertNotEqual(inverse(mutant), RAW['before'])
            with self.assertRaises(AssertionError): restore_reserved_selectors(mutant)
        self.assertEqual(restore_reserved_selectors(RAW['candidate']), RAW['before'])
        self.assertEqual(restore_reserved_selectors(RAW['before']), RAW['before'])
        # The compatibility helper also closes partial/missing/duplicate selector
        # bytes and a mutation of the previously proven core-pressure island.
        mutants = [raw.replace(b'eon_peace_sender_core_pressure_in_pair = yes',
                               b'eon_peace_recipient_core_pressure_in_pair = yes', 1)]
        for fields in MANIFEST['fields'].values():
            after, before = fields['after'].encode(), fields['before'].encode()
            mutants += [raw.replace(after, before, 1), raw + after, raw.replace(after, b'', 1),
                        raw.replace(after, after.replace(b'@PREV', b'@ROOT'), 1)]
        for mutant in mutants:
            self.assertNotEqual(mutant, raw)
            with self.assertRaises(AssertionError): restore_reserved_selectors(mutant)

if __name__ == '__main__': unittest.main(verbosity=2)
