"""Current source vs fixed historical AST: direct pair pressure regressions.

No AI-choice, native dispatch or complete campaign claim from this model.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
from test_transport import Transport, KINDS, ast, one, ROOT
from reserved_selector_compat import restore_reserved_selectors

ACTION = "common/scripted_diplomatic_actions/eon_peace_settlement_actions.txt"
TRIGGER = "common/scripted_triggers/eon_peace_settlement_triggers.txt"
RECIPIENT = "eon_peace_recipient_core_pressure_in_pair"
SENDER = "eon_peace_sender_core_pressure_in_pair"



def restore_trigger_islands(current):
    info = json.loads((HERE / "canonical_ai_pair_context.json").read_text("utf-8"))
    helpers = (HERE / "fixtures/ai_pair_context/pair-helpers.txt").read_bytes()
    assert current.count(helpers) == 1 and current.endswith(helpers)
    text = current[:-len(helpers)].decode("utf-8")
    guards = info["subject_ready_guards"]
    for key in ("new_recipient", "new_sender"):
        assert text.count(guards[key]) == 1, ("Missing/duplicate owned subject guard", key)
        text = text.replace(guards[key], guards["old"])
    return text.encode("utf-8")

class PairTransport(Transport):
    def __init__(self, candidate=False, rules=None):
        super().__init__(rules=rules)
        self.temps = {}
        source_root = ROOT if candidate else HERE / "fixtures/ai_pair_context"
        self.actions.update(dict((k, v) for k, _, v in one(ast((source_root / ACTION).read_bytes()), "scripted_diplomatic_actions")))
        self.helpers = dict((k, v) for k, _, v in ast((source_root / TRIGGER).read_bytes()))
        for c in self.countries.values():
            c.variables.update(surrender_progress=0, stability=1, war_support=1, war_months=0)

    def scalar(self, token, current=2, prev=None):
        if token.startswith("var:"): return self.temps[token[4:]]
        try: return float(token)
        except ValueError: pass
        if "." in token:
            prefix, variable = token.split(".", 1)
            current = self.target(prefix, current, prev)
        else: variable = token
        return self.temps.get(variable, self.countries[current].variables.get(variable, 0))

    def math(self, rows, current=2, prev=None):
        for key, _, value in rows:
            if key == "if":
                if self.truth(one(value, "limit"), current, prev):
                    self.math([r for r in value if r[0] != "limit"], current, prev)
            elif key in ("set_temp_variable", "subtract_from_temp_variable", "multiply_temp_variable"):
                name, _, token = value[0]; number = self.scalar(token, current, prev)
                self.temps[name] = number if key == "set_temp_variable" else self.temps.get(name, 0) - number if key == "subtract_from_temp_variable" else self.temps.get(name, 0) * number
            else: raise AssertionError(("Unsupported math", key, value))

    def conference_pressure(self):
        # Execute only actual surrender component, not omitted legacy components.
        rows = one(one(self.actions["eon_offer_peace_conference"], "ai_acceptance"), "surrender_progress_loc")
        total = float(one(rows, "base"))
        for key, _, modifier in rows:
            if key != "modifier": continue
            conditions = [r for r in modifier if r[0] not in ("set_temp_variable", "subtract_from_temp_variable", "multiply_temp_variable", "if", "add")]
            # The second preexisting exhaustion component is intentionally excluded
            # when neither country's fixture contains war_exhaustion_value.
            if any(k == "has_variable" for k, _, _ in conditions):
                if "war_exhaustion_value" not in self.countries[2].variables: continue
                raise AssertionError("Exhaustion path outside this narrow probe")
            self.assert_empty_conditions(conditions)
            self.math([r for r in modifier if r[0] != "add"])
            total += self.scalar(one(modifier, "add"))
        return total

    @staticmethod
    def assert_empty_conditions(rows):
        assert rows == [], ("Unsupported pressure conditions", rows)


def both(sender_loss=0, recipient_loss=0, sender_control=1, recipient_control=2,
         sender_core=True, recipient_core=True, rule="ENABLED"):
    models = []
    for candidate in (False, True):
        m = PairTransport(candidate, rules={"peace_deal_AI": rule})
        m.countries[1].variables["surrender_progress"] = sender_loss
        m.countries[2].variables["surrender_progress"] = recipient_loss
        m.states = {"sender_core": {"owner": 1, "controller": sender_control, "cores": {1} if sender_core else set()},
                    "recipient_core": {"owner": 2, "controller": recipient_control, "cores": {2} if recipient_core else set()}}
        models.append(m)
    return models


class PairPressure(unittest.TestCase):
    def test_01_source_baseline_unrelated_sender_collapse_scores_offer(self):
        a, b = both(sender_loss=.5, sender_control=3)
        for action in ("eon_offer_peace_statusquo", "eon_offer_armistice_90"):
            self.assertEqual(a.ai_score(action, "ai_desire"), 10)
            self.assertEqual(b.ai_score(action, "ai_desire"), -50)

    def test_02_all_six_acceptance_pressure_ignores_third_party_only_collapse(self):
        a, b = both(recipient_loss=.7, recipient_control=3)
        for _, action, _, _ in KINDS:
            if action == "eon_offer_peace_conference":
                self.assertEqual(a.conference_pressure(), 70)
                self.assertEqual(b.conference_pressure(), 0)
            else:
                before = a.ai_score(action, "ai_acceptance")
                after = b.ai_score(action, "ai_acceptance")
                self.assertEqual(before - after, 120)
        a, b = both(sender_loss=.7, sender_control=3)
        for _, action, _, _ in KINDS:
            if action == "eon_offer_peace_conference":
                self.assertEqual(a.conference_pressure(), -70)
                self.assertEqual(b.conference_pressure(), 0)
            else:
                self.assertEqual(b.ai_score(action, "ai_acceptance") - a.ai_score(action, "ai_acceptance"), 160)

    def test_03_genuine_pair_core_pressure_preserves_existing_thresholds(self):
        for sender_loss in (0, .2, .35, .36, .65, .66, .9):
            for recipient_loss in (0, .2, .35, .36, .65, .66, .9):
                a, b = both(sender_loss, recipient_loss, sender_control=2, recipient_control=1)
                for action in ("eon_offer_peace_statusquo", "eon_offer_armistice_90"):
                    self.assertEqual(a.ai_score(action, "ai_desire"), b.ai_score(action, "ai_desire"))
                for _, action, _, _ in KINDS:
                    if action == "eon_offer_peace_conference": self.assertEqual(a.conference_pressure(), b.conference_pressure())
                    else: self.assertEqual(a.ai_score(action, "ai_acceptance"), b.ai_score(action, "ai_acceptance"))

    def test_04_foreign_owned_noncore_and_third_controller_are_not_pair_pressure(self):
        _, m = both(.7, .7, sender_control=3, recipient_control=3)
        self.assertFalse(m.truth(m.helpers[SENDER])); self.assertFalse(m.truth(m.helpers[RECIPIENT]))
        m.states["sender_core"]["controller"] = 2; m.states["recipient_core"]["controller"] = 1
        self.assertTrue(m.truth(m.helpers[SENDER])); self.assertTrue(m.truth(m.helpers[RECIPIENT]))
        m.states["sender_core"]["cores"].clear(); m.states["recipient_core"]["cores"].clear()
        self.assertFalse(m.truth(m.helpers[SENDER])); self.assertFalse(m.truth(m.helpers[RECIPIENT]))
        m.states["sender_core"].update(owner=3, cores={1}); m.states["recipient_core"].update(owner=3, cores={2})
        self.assertFalse(m.truth(m.helpers[SENDER])); self.assertFalse(m.truth(m.helpers[RECIPIENT]))

    def test_05_game_rules_and_global_fatigue_stay_identical(self):
        for rule in ("ENABLED", "RESTRICTED", "ENCOURAGED", "DISABLED"):
            a, b = both(sender_loss=.7, recipient_loss=.7, sender_control=2, recipient_control=1, rule=rule)
            for m in (a, b):
                m.countries[1].variables.update(stability=.1, war_support=.1, war_months=15)
                m.countries[2].variables.update(stability=.1, war_support=.1, war_months=15)
            for action in ("eon_offer_peace_statusquo", "eon_offer_armistice_90"):
                self.assertEqual(a.ai_score(action, "ai_desire"), b.ai_score(action, "ai_desire"))
            for _, action, _, _ in KINDS:
                if action != "eon_offer_peace_conference": self.assertEqual(a.ai_score(action, "ai_acceptance"), b.ai_score(action, "ai_acceptance"))

    def test_06_all_non_ai_action_fields_and_original_triggers_are_unchanged(self):
        a, b = both()
        projected = dict((k, v) for k, _, v in one(ast(restore_reserved_selectors((ROOT / ACTION).read_bytes())), "scripted_diplomatic_actions"))
        for _, action, _, _ in KINDS:
            for key, op, value in a.actions[action]:
                if key not in ("ai_desire", "ai_acceptance"):
                    self.assertEqual(value, one(projected[action], key), (action, key))
        restored = dict((k, v) for k, _, v in ast(restore_trigger_islands((ROOT / TRIGGER).read_bytes())))
        for key, value in a.helpers.items(): self.assertEqual(value, restored[key], key)
        self.assertEqual(set(b.helpers) - set(a.helpers), {RECIPIENT, SENDER})

    def test_07_exact_owned_inverse_and_external_or_scope_negative_controls(self):
        info = json.loads((HERE / "canonical_ai_pair_context.json").read_text("utf-8"))
        raw = restore_reserved_selectors((ROOT / ACTION).read_bytes()); baseline = (HERE / "fixtures/ai_pair_context" / ACTION).read_bytes()
        def restore(raw):
            txt = raw.decode("utf-8")
            for p in reversed(info["patches"]):
                assert txt.count(p["new"]) == p["count"]
                txt = txt.replace(p["new"], p["old"])
            return txt.encode("utf-8")
        self.assertEqual(restore(raw), baseline)
        self.assertNotEqual(restore(raw + b"\n# foreign\n"), baseline)
        first = info["patches"][0]
        for mutated in (raw.replace(first["new"].encode(), first["old"].encode(), 1), raw + first["new"].encode()):
            with self.assertRaises(AssertionError): restore(mutated)
        _, m = both(.7, 0, sender_control=2)
        wrong = deepcopy(m.helpers[SENDER])
        def mutate(rows):
            for i, (key, op, val) in enumerate(rows):
                if key == "is_controlled_by": rows[i] = (key, op, "ROOT"); return True
                if isinstance(val, list) and mutate(val): return True
            return False
        self.assertTrue(mutate(wrong)); self.assertTrue(m.truth(m.helpers[SENDER])); self.assertFalse(m.truth(wrong))

    def test_08_arbitrary_swapped_roots_and_no_pair_war_fail_closed(self):
        for sender, recipient in ((1, 2), (2, 1), (3, 4), (4, 3)):
            m = PairTransport(candidate=True)
            m.root = sender; m.from_ = recipient
            m.countries[sender].enemies = {recipient}
            m.countries[recipient].enemies = {sender}
            m.states = {"a": {"owner": sender, "cores": {sender}, "controller": recipient},
                        "b": {"owner": recipient, "cores": {recipient}, "controller": sender}}
            self.assertTrue(m.truth(m.helpers[SENDER], current=recipient))
            self.assertTrue(m.truth(m.helpers[RECIPIENT], current=recipient))
            m.countries[sender].enemies.clear(); m.countries[recipient].enemies.clear()
            self.assertFalse(m.truth(m.helpers[SENDER], current=recipient))
            self.assertFalse(m.truth(m.helpers[RECIPIENT], current=recipient))


    def test_09_current_source_exact_islands_and_fixed_baseline_hashes(self):
        info = json.loads((HERE / "canonical_ai_pair_context.json").read_text("utf-8"))
        helpers = (HERE / "fixtures/ai_pair_context/pair-helpers.txt").read_bytes()
        for relative, hashes in info["files"].items():
            baseline = (HERE / "fixtures/ai_pair_context" / relative).read_bytes()
            current = (ROOT / relative).read_bytes()
            if relative == ACTION: current = restore_reserved_selectors(current)
            self.assertEqual(hashlib.sha256(baseline).hexdigest(), hashes["before_sha256"])
            self.assertEqual(hashlib.sha256(current).hexdigest(), hashes["candidate_sha256"])
            if relative == ACTION:
                restored = current.decode("utf-8")
                for p in reversed(info["patches"]):
                    self.assertEqual(restored.count(p["new"]), p["count"])
                    restored = restored.replace(p["new"], p["old"])
                self.assertEqual(restored.encode("utf-8"), baseline)
            else:
                self.assertEqual(hashlib.sha256(helpers).hexdigest(), hashes["append_sha256"])
                self.assertEqual(current.count(helpers), 1)
                self.assertTrue(current.endswith(helpers))
                self.assertEqual(restore_trigger_islands(current), baseline)
                for bad in (current[:-len(helpers)], current + helpers, current + b"# foreign suffix\n",
                            b"# foreign prefix\n" + current, current.replace(b"is_controlled_by = PREV.PREV", b"is_controlled_by = ROOT")):
                    self.assertNotEqual(hashlib.sha256(bad).hexdigest(), hashes["candidate_sha256"])

    def test_10_closed_state_query_rejects_wrong_or_unknown_scopes(self):
        m = PairTransport(candidate=True)
        m.states = {"s": {"owner": 1, "controller": 2, "cores": {1}}}
        for script, current in (("is_core_of = ROOT", 2), ("is_controlled_by = missing_country", "s"),
                                ("any_owned_state = yes", 2), ("is_core_of > ROOT", "s")):
            with self.assertRaises(AssertionError): m.truth(ast(script), current=current)
        with self.assertRaises(AssertionError): m.truth(ast("is_core_of = PREV.PREV"), current="s", prev=(1,))


if __name__ == "__main__": unittest.main(verbosity=2)
