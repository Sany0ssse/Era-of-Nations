"""Actual trigger AST, separate from frozen pair scoring/native proposal."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import unittest

HERE = Path(__file__).resolve().parent
from test_transport import Transport, KINDS, ast, one, ROOT
from test_ai_pair_context import restore_trigger_islands

REL = "common/scripted_triggers/eon_peace_settlement_triggers.txt"


def model(parent, selected=False, candidate=True):
    m = Transport()
    source_root = ROOT if candidate else HERE / "fixtures/ai_pair_context"
    m.helpers = {k: v for k, _, v in ast((source_root / REL).read_bytes())}
    other = 2 if parent == 1 else 1
    m.countries[parent].subjects.add(3)
    m.countries[parent].enemies.add(4)
    m.countries[3].subject = True
    m.countries[3].enemies = {4, other} if selected else {4}
    m.countries[4].enemies = {parent, 3}
    m.countries[3].co_belligerents = {parent}
    return m


class SubjectGate(unittest.TestCase):
    def test_unrelated_subject_front_baseline_blocks_and_candidate_allows_fixed_terms(self):
        for parent in (1, 2):
            old = model(parent, candidate=False)
            new = model(parent, candidate=True)
            self.assertFalse(old.truth(old.helpers["eon_peace_settlement_ready"]))
            self.assertTrue(new.truth(new.helpers["eon_peace_settlement_ready"]))
            for suffix, action, kind, cost in KINDS:
                old.draft(kind); new.draft(kind)
                self.assertFalse(old.gate(action, "can_be_sent"))
                self.assertEqual(new.gate(action, "can_be_sent"), suffix != "conference")

    def test_selected_subject_front_still_excludes_parent_on_either_offer_side(self):
        for parent in (1, 2):
            m = model(parent, selected=True)
            self.assertFalse(m.truth(m.helpers["eon_peace_settlement_ready"]))
            for _, action, kind, _ in KINDS:
                m.draft(kind)
                self.assertFalse(m.gate(action, "can_be_sent"))

    def test_subject_entering_selected_front_after_send_invalidates_response(self):
        for parent in (1, 2):
            m = model(parent)
            m.draft(1); m.run("eon_offer_peace_statusquo", "on_sent_effect")
            self.assertTrue(m.gate("eon_offer_peace_statusquo", "can_be_accepted"))
            m.countries[3].enemies.add(2 if parent == 1 else 1)
            self.assertFalse(m.gate("eon_offer_peace_statusquo", "can_be_accepted"))
            m.run("eon_offer_peace_statusquo", "complete_effect")
            self.assertEqual(m.calls, [("eon_peace_reject_statusquo", 2, 1)])

    def test_unrelated_front_does_not_erase_conference_or_money_national_guards(self):
        for parent in (1, 2):
            for mutate in (lambda m: setattr(m.countries[1], "subject", True),
                           lambda m: setattr(m.countries[2], "capitulated", True),
                           lambda m: setattr(m.countries[1], "conference", True),
                           lambda m: setattr(m.countries[2], "civil_war_target", 1)):
                m = model(parent); mutate(m); m.draft(1)
                self.assertFalse(m.gate("eon_offer_peace_statusquo", "can_be_sent"))
            m = model(parent); m.draft(4); m.countries[1].variables["treasury"] = 4.999
            self.assertFalse(m.gate("eon_offer_peace_payment_5", "can_be_sent"))

    def test_only_two_confirmed_guard_islands_change(self):
        spec = json.loads((HERE / "canonical_ai_pair_context.json").read_text("utf-8"))
        before = (HERE / "fixtures/ai_pair_context" / REL).read_bytes()
        current = (ROOT / REL).read_bytes()
        self.assertEqual(restore_trigger_islands(current), before)
        old = dict((k, v) for k, _, v in ast(before))
        new = dict((k, v) for k, _, v in ast(current))
        self.assertEqual({k for k in old if old[k] != new[k]}, {"eon_peace_settlement_ready"})
        for key in ("new_recipient", "new_sender"):
            island = spec["subject_ready_guards"][key].encode()
            for bad in (current.replace(island, spec["subject_ready_guards"]["old"].encode(), 1), current + island):
                with self.assertRaises(AssertionError): restore_trigger_islands(bad)
        self.assertNotEqual(restore_trigger_islands(b"# foreign prefix\n" + current), before)

    def test_second_depth_scope_cannot_silently_be_replaced_by_parent(self):
        m = model(1, selected=True)
        wrong = deepcopy(m.helpers["eon_peace_settlement_ready"])
        def mutate(rows):
            for i, (k, op, v) in enumerate(rows):
                if k == "has_war_with" and v == "PREV.PREV": rows[i] = (k, op, "PREV"); return True
                if isinstance(v, list) and mutate(v): return True
            return False
        self.assertTrue(mutate(wrong))
        self.assertFalse(m.truth(m.helpers["eon_peace_settlement_ready"]))
        self.assertTrue(m.truth(wrong), "Wrong parent target would admit its selected-war subject")


if __name__ == "__main__": unittest.main(verbosity=2)
