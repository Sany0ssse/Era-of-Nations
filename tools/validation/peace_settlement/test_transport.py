"""Actual-source peace transport model; native war/GUI behavior remains untested.

Breaks covered: defender access gates, side/target swaps, unauthorized coalition
peace, mutable sent terms, stale responses and reservation reuse before closure.
Native execution helpers are a boundary: this model does not emulate their
world effects or claim game-engine acceptance.
"""
from dataclasses import dataclass, field
from pathlib import Path
import copy
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/validation/diplomacy_package_03"))
from _support import ast, one

KINDS = (
    ("statusquo", "eon_offer_peace_statusquo", 1, 0),
    ("armistice_90", "eon_offer_armistice_90", 2, 0),
    ("armistice_180", "eon_offer_armistice_180", 3, 0),
    ("payment_5", "eon_offer_peace_payment_5", 4, 5),
    ("payment_10", "eon_offer_peace_payment_10", 5, 10),
    ("conference", "eon_offer_peace_conference", 6, 0),
)


@dataclass
class Country:
    exists: bool = True
    ai: bool = False
    subject: bool = False
    capitulated: bool = False
    conference: bool = False
    civil_war: bool = False
    civil_war_target: int | None = None
    faction: int | None = None
    enemies: set = field(default_factory=set)
    offensive: set = field(default_factory=set)
    defensive: set = field(default_factory=set)
    subjects: set = field(default_factory=set)
    co_belligerents: set = field(default_factory=set)
    variables: dict = field(default_factory=lambda: {"treasury": 100})
    # None denotes untimed reservation, integer denotes expiration day.
    flags: dict = field(default_factory=dict)
    # Native R6 differentiates numeric zero block flags from positive flags.
    # Manual declared fixtures without metadata represent already-active flags.
    flag_values: dict = field(default_factory=dict)


class Transport:
    def __init__(self, rules=None):
        self.countries = {n: Country() for n in range(1, 5)}
        # Explicit observed state facts only: no implied country-wide occupation.
        self.states = {}
        self.countries[1].enemies = {2}
        self.countries[2].enemies = {1}
        self.countries[1].defensive = {2}
        self.countries[2].offensive = {1}
        self.root = 1
        self.from_ = 2
        self.day = 0
        self.rules = rules or {"peace_deal_AI": "ENABLED"}
        self.calls = []
        self.events = []
        self.helpers = {}
        self.actions = {}
        for rel in ("common/scripted_triggers/eon_peace_settlement_triggers.txt",):
            p = ROOT / rel
            if p.exists():
                rows = ast(p.read_bytes())
                names = [k for k, op, v in rows]
                assert len(names) == len(set(names)), ("Duplicate peace trigger IDs", rel)
                assert not set(names).intersection(self.helpers), ("Duplicate peace trigger definitions", rel)
                self.helpers.update({k: v for k, op, v in rows})
        for rel in ("common/scripted_diplomatic_actions/peace_deal.txt",
                    "common/scripted_diplomatic_actions/eon_peace_settlement_actions.txt"):
            p = ROOT / rel
            if p.exists():
                rows = one(ast(p.read_bytes()), "scripted_diplomatic_actions")
                names = [k for k, op, v in rows]
                assert len(names) == len(set(names)), ("Duplicate peace action IDs", rel)
                assert not set(names).intersection(self.actions), ("Duplicate action definitions across files", rel)
                self.actions.update({k: v for k, op, v in rows})

    def target(self, value, current, prev):
        if value.startswith("PREV"):
            chain = () if prev is None else prev if isinstance(prev, tuple) else (prev,)
            depth = value.split(".").count("PREV")
            assert len(chain) >= depth, ("Missing model scope predecessor", value, current, prev)
            return chain[depth - 1]
        return {"ROOT": self.root, "FROM": self.from_, "THIS": current, "PREV": prev}.get(value, value)

    @staticmethod
    def push(current, prev):
        return (current,) + (() if prev is None else prev if isinstance(prev, tuple) else (prev,))

    def flag(self, name, current, prev):
        base, sep, target = name.partition("@")
        return base + ("@" + str(self.target(target, current, prev)) if sep else "")

    def active_flag(self, name, current, prev):
        name = self.flag(name, current, prev)
        country = self.countries[current]
        flags = country.flags
        return (name in flags and country.flag_values.get(name, 1) != 0
                and (flags[name] is None or flags[name] > self.day))

    def value(self, name, current, prev):
        if name in ("ROOT", "THIS", "PREV"):
            return self.target(name, current, prev)
        try:
            return float(name)
        except (ValueError, TypeError):
            if name.startswith("ROOT."):
                return self.countries[self.root].variables.get(name[5:], 0)
            return self.countries[current].variables.get(name, 0)

    def truth(self, nodes, current=2, prev=None):
        def row(key, op, value):
            if key == "any_owned_state":
                assert current in self.countries and isinstance(value, list), ("Invalid owned-state query scope", current, value)
                return any(state["owner"] == current and self.truth(value, state_id, self.push(current, prev))
                           for state_id, state in self.states.items())
            if key in ("is_core_of", "is_controlled_by", "is_owned_by"):
                assert current in self.states and isinstance(value, str) and op == "=", ("Invalid state predicate scope", key, current, value)
                state = self.states[current]
                target = self.target(value, current, prev)
                assert target in self.countries, ("Unknown country target in state predicate", value, target)
                assert set(state) == {"owner", "controller", "cores"} and isinstance(state["cores"], set), ("Malformed modeled state", state)
                if key == "is_core_of": return target in state["cores"]
                return target == state["controller" if key == "is_controlled_by" else "owner"]
            country = self.countries[current]
            if key in ("ROOT", "THIS", "PREV") and isinstance(value, list):
                return self.truth(value, self.target(key, current, prev), self.push(current, prev))
            if key in ("AND", "hidden_trigger", "custom_trigger_tooltip", "limit"):
                return self.truth(value, current, prev)
            if key == "OR":
                return any(row(*n) for n in value)
            if key == "NOT":
                return not any(row(*n) for n in value)
            if key == "tooltip":
                return True
            if key == "always":
                return value == "yes"
            if key in self.helpers:
                return self.truth(self.helpers[key], current, prev) == (value == "yes")
            if key == "peace_deal_available":
                # Characterization input: early war violates the old long-war gate.
                return value == "no"
            if key == "is_in_peace_conference":
                # R4 no assignment was not a negation; use NOT around yes.
                # This fixture caveat is independently checked by native R5.
                return country.conference
            attributes = {"exists": "exists", "is_ai": "ai", "is_subject": "subject",
                          "has_capitulated": "capitulated", "has_civil_war": "civil_war"}
            if key in attributes:
                return getattr(country, attributes[key]) == (value == "yes")
            if key == "tag":
                return current == self.target(value, current, prev)
            if key == "civilwar_target":
                return country.civil_war_target == self.target(value, current, prev)
            if key in ("has_war_with", "has_offensive_war_with", "has_defensive_war_with", "has_war_together_with"):
                names = {"has_war_with": "enemies", "has_offensive_war_with": "offensive",
                         "has_defensive_war_with": "defensive", "has_war_together_with": "co_belligerents"}
                return self.target(value, current, prev) in getattr(country, names[key])
            if key in ("any_country", "any_enemy_country", "any_subject_country"):
                targets = {"any_country": self.countries.keys(), "any_enemy_country": country.enemies,
                           "any_subject_country": country.subjects}[key]
                return any(self.truth(value, n, self.push(current, prev)) for n in targets)
            if key == "is_in_faction":
                return (country.faction is not None) == (value == "yes")
            if key == "is_faction_leader":
                return value == "no"
            if key == "has_idea":
                return False
            if key == "has_country_flag":
                return self.active_flag(value, current, prev)
            if key == "has_game_rule":
                return self.rules.get(one(value, "rule")) == one(value, "option")
            if key == "check_variable":
                for variable, comparison, expected in value:
                    left = self.value(variable, current, prev)
                    right = self.value(expected, current, prev)
                    if not {"=": left == right, ">=": left >= right, ">": left > right,
                            "<": left < right, "<=": left <= right, "!=": left != right}[comparison]:
                        return False
                return True
            if key in ("surrender_progress", "has_stability", "has_war_support"):
                variable = {"has_stability": "stability", "has_war_support": "war_support"}.get(key, key)
                left, right = country.variables.get(variable, 0), float(value)
                return {"=": left == right, ">": left > right, "<": left < right}[op]
            if key == "war_length_with":
                months, comparison, expected = next(n for n in value if n[0] == "months")
                left, right = country.variables.get("war_months", 0), float(expected)
                return {">": left > right, "<": left < right, "=": left == right}[comparison]
            raise AssertionError(("Unsupported visited trigger", key, op, value))
        return all(row(*n) for n in nodes)

    def effect(self, nodes, current=2, prev=None):
        previous_if = None
        for key, op, value in nodes:
            if key == "if":
                previous_if = self.truth(one(value, "limit"), current, prev)
                if previous_if:
                    self.effect([n for n in value if n[0] != "limit"], current, prev)
            elif key == "else":
                assert previous_if is not None, "Orphan else in actual transport"
                if not previous_if:
                    self.effect(value, current, prev)
            elif key in ("ROOT", "PREV", "FROM"):
                self.effect(value, self.target(key, current, prev), self.push(current, prev))
            elif key == "set_variable":
                for name, comparison, expected in value:
                    self.countries[current].variables[name] = self.value(expected, current, prev)
            elif key == "country_event":
                self.events.append((current, one(value, "id")))
            elif key == "set_country_flag":
                if isinstance(value, list):
                    name = one(value, "flag")
                    days = next((float(v) for k, op, v in value if k == "days"), None)
                    expiry = None if days is None else self.day + days
                    numeric = next((float(v) for k, op, v in value if k == "value"), 0)
                else:
                    name, expiry, numeric = value, None, 1
                resolved = self.flag(name, current, prev)
                self.countries[current].flags[resolved] = expiry
                self.countries[current].flag_values[resolved] = numeric
            elif key == "clr_country_flag":
                resolved = self.flag(value, current, prev)
                self.countries[current].flags.pop(resolved, None)
                self.countries[current].flag_values.pop(resolved, None)
            elif key.startswith("eon_peace_execute_") or key.startswith("eon_peace_reject_"):
                # Validated boundary dispatch; implementation belongs to root tests.
                self.calls.append((key, current, self.root))
            elif key == "trigger_peace_deal":
                self.calls.append(("legacy_native_conference", current, self.root))
            elif key == "log":
                pass
            else:
                raise AssertionError(("Unsupported visited effect", key, op, value))

    def gate(self, action, key):
        assert action in self.actions, ("Missing negotiated peace action", action)
        return self.truth(one(self.actions[action], key))

    def run(self, action, key):
        assert action in self.actions, ("Missing negotiated peace action", action)
        self.effect(one(self.actions[action], key))

    def draft(self, kind):
        self.countries[1].variables.update(eon_peace_draft_target=2, eon_peace_draft_kind=kind)

    def ai_score(self, action, part):
        def score(nodes):
            result = float(one(nodes, "base"))
            for key, op, value in nodes:
                if key != "modifier":
                    continue
                conditions = [n for n in value if n[0] not in ("add", "factor")]
                if self.truth(conditions):
                    for key, op, value in value:
                        if key == "add": result += float(value)
                        if key == "factor": result *= float(value)
            return result
        nodes = one(self.actions[action], part)
        if any(k == "base" for k, op, v in nodes):
            return score(nodes)
        return sum(score(v) for k, op, v in nodes)


class PeaceTransportTests(unittest.TestCase):
    def test_early_defender_faction_minor_can_open_draft(self):
        model = Transport()
        model.countries[1].faction = 7
        model.countries[2].faction = 8
        action = "propose_ceasefire_defensive"
        self.assertTrue(model.gate(action, "visible"))
        self.assertTrue(model.gate(action, "selectable"), "An early defending faction minor must be able to discuss peace")
        self.assertEqual(one(model.actions[action], "requires_acceptance"), "no")
        model.run(action, "complete_effect")
        self.assertEqual(model.events, [(1, "eon_peace_settlement.1")])
        self.assertEqual(model.countries[1].variables["eon_peace_draft_target"], 2)
        self.assertEqual(model.countries[1].variables["eon_peace_draft_kind"], 1)
        self.assertEqual(model.calls, [])

    def test_opening_draft_does_not_mutate_sent_terms(self):
        model = Transport()
        model.countries[1].flags["eon_peace_reserved_payment_10@2"] = None
        model.countries[2].flags["eon_peace_pending_payment_10@1"] = 30
        before = copy.deepcopy([model.countries[1].flags, model.countries[2].flags])
        model.run("propose_ceasefire_defensive", "complete_effect")
        self.assertEqual([model.countries[1].flags, model.countries[2].flags], before)
        self.assertEqual(model.calls, [])

    def test_attacker_can_open_same_draft_without_world_effect(self):
        model = Transport()
        model.countries[1].offensive, model.countries[1].defensive = {2}, set()
        model.countries[2].offensive, model.countries[2].defensive = set(), {1}
        self.assertTrue(model.gate("propose_ceasefire", "selectable"))
        model.run("propose_ceasefire", "complete_effect")
        self.assertEqual(model.events, [(1, "eon_peace_settlement.1")])
        self.assertEqual(model.calls, [])

    def test_draft_selection_exposes_only_one_immutable_offer(self):
        model = Transport()
        self.assertTrue(set(a for suffix, a, k, cost in KINDS) <= model.actions.keys(), "Negotiated offers are missing")
        for suffix, action, kind, cost in KINDS:
            model.draft(kind)
            visible = [a for s, a, k, c in KINDS if model.gate(a, "visible")]
            self.assertEqual(visible, [action])
        model.countries[1].variables["eon_peace_draft_target"] = 3
        self.assertFalse(any(model.gate(a, "visible") for s, a, k, c in KINDS))

    def test_each_offer_requires_paired_pending_and_reservation(self):
        model = Transport()
        for suffix, action, kind, cost in KINDS:
            with self.subTest(action=action):
                model = Transport()
                model.draft(kind)
                self.assertTrue(model.gate(action, "can_be_sent"))
                self.assertFalse(model.gate(action, "can_be_accepted"))
                model.run(action, "on_sent_effect")
                self.assertTrue(model.gate(action, "can_be_accepted"))
                self.assertEqual(model.countries[1].flags["eon_peace_reserved_" + suffix + "@2"], None)
                self.assertEqual(model.countries[2].flags["eon_peace_pending_" + suffix + "@1"], 30)
                self.assertFalse(any(model.gate(a, "can_be_sent") for s, a, k, c in KINDS))
                for other_suffix, other_action, other_kind, other_cost in KINDS:
                    model.draft(other_kind)
                    self.assertFalse(model.gate(other_action, "can_be_sent"), "A pending offer reserves the pair across all new draft kinds")
                model.countries[1].variables["eon_peace_draft_kind"] = 99
                self.assertTrue(model.gate(action, "can_be_accepted"), "Sent terms may not follow mutable draft variables")
                for missing_side, marker in [(1, "pending"), (2, "pending"), (1, "reserved"), (2, "reserved")]:
                    altered = copy.deepcopy(model)
                    target = 2 if missing_side == 1 else 1
                    del altered.countries[missing_side].flags[f"eon_peace_{marker}_{suffix}@{target}"]
                    self.assertFalse(altered.gate(action, "can_be_accepted"))
                    altered.run(action, "complete_effect")
                    self.assertEqual(altered.calls, [("eon_peace_reject_" + suffix, 2, 1)])

    def test_expired_offer_reservation_blocks_reuse_until_terminal_callback(self):
        model = Transport()
        model.draft(1)
        model.run("eon_offer_peace_statusquo", "on_sent_effect")
        model.day = 31
        self.assertFalse(model.gate("eon_offer_peace_statusquo", "can_be_accepted"))
        self.assertFalse(model.gate("eon_offer_peace_statusquo", "can_be_sent"))
        model.run("eon_offer_peace_statusquo", "complete_effect")
        self.assertEqual(model.calls, [("eon_peace_reject_statusquo", 2, 1)])
        model.calls.clear()
        model.run("eon_offer_peace_statusquo", "reject_effect")
        self.assertEqual(model.calls, [("eon_peace_reject_statusquo", 2, 1)])

    def test_stale_war_capitulation_subject_coalition_and_cash_reject(self):
        changes = [
            ("peace", lambda m: m.countries[2].enemies.clear()),
            ("capitulated sender", lambda m: setattr(m.countries[1], "capitulated", True)),
            ("conference receiver", lambda m: setattr(m.countries[2], "conference", True)),
            ("sender subject", lambda m: setattr(m.countries[1], "subject", True)),
            ("participating subject", lambda m: (m.countries[1].subjects.add(3), m.countries[3].co_belligerents.add(1), m.countries[3].enemies.add(2), m.countries[2].enemies.add(3))),
            ("sender cash spent", lambda m: m.countries[1].variables.update(treasury=4.999)),
        ]
        for label, change in changes:
            with self.subTest(label=label):
                model = Transport()
                model.draft(4)
                model.run("eon_offer_peace_payment_5", "on_sent_effect")
                change(model)
                self.assertFalse(model.gate("eon_offer_peace_payment_5", "can_be_accepted"))
                model.run("eon_offer_peace_payment_5", "complete_effect")
                self.assertEqual(model.calls, [("eon_peace_reject_payment_5", 2, 1)])

    def test_nonparticipating_faction_and_subject_do_not_block_contact(self):
        model = Transport()
        model.countries[1].faction = 7
        model.countries[1].subjects.add(3)
        self.assertTrue(model.gate("propose_ceasefire_defensive", "can_be_sent"))
        model.draft(1)
        self.assertTrue(model.gate("eon_offer_peace_statusquo", "can_be_sent"))

    def test_payment_exact_boundary_checks_sender_not_receiver(self):
        for amount, action, kind in [(5, "eon_offer_peace_payment_5", 4), (10, "eon_offer_peace_payment_10", 5)]:
            model = Transport()
            model.draft(kind)
            model.countries[1].variables["treasury"] = amount
            model.countries[2].variables["treasury"] = 0
            self.assertTrue(model.gate(action, "can_be_sent"))
            model.countries[1].variables["treasury"] = amount - 0.001
            self.assertFalse(model.gate(action, "can_be_sent"))

    def test_disabled_ai_cannot_accept_but_human_can(self):
        model = Transport({"peace_deal_AI": "DISABLED"})
        model.draft(1)
        model.run("eon_offer_peace_statusquo", "on_sent_effect")
        self.assertTrue(model.gate("eon_offer_peace_statusquo", "can_be_accepted"))
        model.countries[2].ai = True
        self.assertFalse(model.gate("eon_offer_peace_statusquo", "can_be_accepted"))
        model.run("eon_offer_peace_statusquo", "complete_effect")
        self.assertEqual(model.calls, [("eon_peace_reject_statusquo", 2, 1)])

    def test_unreserved_duplicate_complete_does_not_dispatch_execution(self):
        model = Transport()
        model.draft(1)
        model.run("eon_offer_peace_statusquo", "complete_effect")
        model.run("eon_offer_peace_statusquo", "complete_effect")
        self.assertEqual(model.calls, [("eon_peace_reject_statusquo", 2, 1), ("eon_peace_reject_statusquo", 2, 1)])

    def test_ai_reaches_statusquo_and_short_armistice_without_human_draft(self):
        model = Transport()
        model.countries[1].ai = True
        model.states = {"sender_core": {"owner": 1, "controller": 2, "cores": {1}}}
        model.countries[1].variables.update(surrender_progress=0.7, stability=0.2, war_support=0.2, war_months=14)
        for action in ("eon_offer_peace_statusquo", "eon_offer_armistice_90"):
            with self.subTest(action=action):
                self.assertTrue(model.gate(action, "allowed"))
                self.assertTrue(model.gate(action, "visible"))
                self.assertTrue(model.gate(action, "can_be_sent"))
                self.assertGreater(model.ai_score(action, "ai_desire"), 0)
        for action in ("eon_offer_armistice_180", "eon_offer_peace_payment_5", "eon_offer_peace_payment_10", "eon_offer_peace_conference"):
            self.assertFalse(model.gate(action, "can_be_sent"), "AI must not blindly offer payments or a conference")
        model.rules["peace_deal_AI"] = "DISABLED"
        for action in ("eon_offer_peace_statusquo", "eon_offer_armistice_90"):
            self.assertEqual(model.ai_score(action, "ai_desire"), 0)
            self.assertFalse(model.gate(action, "can_be_sent"))

    def test_ai_acceptance_distinguishes_loss_pressure_from_winning(self):
        model = Transport()
        model.states = {"sender_core": {"owner": 1, "controller": 2, "cores": {1}},
                        "recipient_core": {"owner": 2, "controller": 1, "cores": {2}}}
        model.countries[2].variables.update(surrender_progress=0.7, stability=0.2, war_support=0.2, war_months=14)
        self.assertGreater(model.ai_score("eon_offer_peace_statusquo", "ai_acceptance"), 0)
        model.countries[2].variables.update(surrender_progress=0.01, stability=0.8, war_support=0.8)
        model.countries[1].variables.update(surrender_progress=0.7)
        self.assertLess(model.ai_score("eon_offer_peace_statusquo", "ai_acceptance"), 0)

    def test_stale_terminal_acceptance_dispatches_cleanup(self):
        model = Transport()
        model.draft(1)
        model.run("eon_offer_peace_statusquo", "on_sent_effect")
        model.countries[2].enemies.clear()
        model.run("eon_offer_peace_statusquo", "complete_effect")
        self.assertEqual(model.calls, [("eon_peace_reject_statusquo", 2, 1)])

    def test_fixed_terms_do_not_bind_other_wars_but_conference_excludes_them(self):
        for configure in (lambda m: m.countries[1].enemies.add(3),
                          lambda m: m.countries[3].co_belligerents.add(1)):
            model = Transport()
            configure(model)
            for suffix, action, kind, cost in KINDS:
                model.draft(kind)
                self.assertEqual(model.gate(action, "can_be_sent"), suffix != "conference")

    def test_foreign_war_peace_is_not_blocked_by_unrelated_civil_war(self):
        model = Transport()
        model.countries[1].civil_war = True
        model.countries[1].civil_war_target = 3
        model.countries[1].enemies.add(3)
        model.draft(1)
        self.assertTrue(model.gate("eon_offer_peace_statusquo", "can_be_sent"))
        model.countries[1].civil_war_target = 2
        self.assertFalse(model.gate("eon_offer_peace_statusquo", "can_be_sent"))
        model.countries[1].civil_war_target = None
        model.countries[2].civil_war_target = 1
        self.assertFalse(model.gate("eon_offer_peace_statusquo", "can_be_sent"))

    def test_actual_war_relation_hook_invalidates_only_new_pair_approvals(self):
        model = Transport()
        for suffix, action, kind, cost in KINDS:
            for a, b in ((1, 2), (2, 1), (1, 3), (3, 1)):
                model.countries[a].flags[f"eon_peace_pending_{suffix}@{b}"] = 30
                model.countries[a].flags[f"eon_peace_reserved_{suffix}@{b}"] = None
        before = copy.deepcopy([c.flags for c in model.countries.values()])
        path = ROOT / "common/on_actions/eon_peace_settlement_on_actions.txt"
        self.assertTrue(path.exists(), "Pair-specific war relation invalidation is missing")
        hook = one(one(ast(path.read_bytes()), "on_actions"), "on_war_relation_added")
        model.effect(one(hook, "effect"), current=1)
        for suffix, action, kind, cost in KINDS:
            self.assertNotIn(f"eon_peace_pending_{suffix}@2", model.countries[1].flags)
            self.assertNotIn(f"eon_peace_pending_{suffix}@1", model.countries[2].flags)
            self.assertIn(f"eon_peace_reserved_{suffix}@2", model.countries[1].flags)
            self.assertIn(f"eon_peace_reserved_{suffix}@1", model.countries[2].flags)
            self.assertEqual(model.countries[1].flags[f"eon_peace_pending_{suffix}@3"], 30)
            self.assertEqual(model.countries[3].flags[f"eon_peace_pending_{suffix}@1"], 30)
        self.assertEqual(model.countries[3].flags, before[2])

    def test_nonparticipating_subject_is_excluded_only_from_conference(self):
        for overlord in (1, 2):
            model = Transport()
            model.countries[overlord].subjects.add(3)
            model.draft(1)
            self.assertTrue(model.gate("eon_offer_peace_statusquo", "can_be_sent"))
            model.draft(6)
            self.assertFalse(model.gate("eon_offer_peace_conference", "can_be_sent"), "LIMITED conference includes potential subjects even if they did not join this war")

    def test_native_timed_flag_block_needs_explicit_active_value(self):
        # Native R6: default block = 0, explicit value=1 = active, scalar = active.
        # ROOT/PREV dynamic suffixes were independently verified; literal tags were not.
        for name, setter, active in (
            ("r6_default", "set_country_flag = { flag = r6_default days = 30 }", False),
            ("r6_zero", "set_country_flag = { flag = r6_zero days = 30 value = 0 }", False),
            ("r6_explicit", "set_country_flag = { flag = r6_explicit days = 30 value = 1 }", True),
            ("r6_scalar", "set_country_flag = r6_scalar", True),
        ):
            with self.subTest(name=name):
                model = Transport()
                model.effect(ast(setter))
                self.assertEqual(model.truth(ast("has_country_flag = " + name)), active)
                if "days" in setter:
                    model.day = 30
                    self.assertFalse(model.truth(ast("has_country_flag = " + name)), "A positive timed flag still expires")

    def test_every_sent_pending_marker_has_explicit_active_value(self):
        model = Transport()
        def walk(nodes):
            for key, op, value in nodes:
                yield key, op, value
                if isinstance(value, list):
                    yield from walk(value)
        for suffix, action, kind, cost in KINDS:
            with self.subTest(action=action):
                blocks = [value for key, op, value in walk(one(model.actions[action], "on_sent_effect"))
                          if key == "set_country_flag" and isinstance(value, list)
                          and one(value, "flag").startswith("eon_peace_pending_")]
                self.assertEqual(len(blocks), 2, "Each side must receive its own immutable pending marker")
                for block in blocks:
                    self.assertEqual(one(block, "value"), "1", "Timed pending block defaults to native numeric zero")

    def test_native_conference_predicate_does_not_use_no_as_negation(self):
        # R4 observed that the no assignment did not negate this native query.
        # R5 independently verifies yes/no/NOT yes; this fixture models the caveat.
        model = Transport()
        for current in (1, 2):
            for conference in (False, True):
                with self.subTest(current=current, conference=conference):
                    model.countries[current].conference = conference
                    self.assertEqual(model.truth(ast("is_in_peace_conference = yes"), current=current), conference)
                    self.assertEqual(model.truth(ast("is_in_peace_conference = no"), current=current), conference)
                    self.assertEqual(model.truth(ast("NOT = { is_in_peace_conference = yes }"), current=current), not conference)

    def test_settlement_readiness_negates_positive_conference_query_on_both_sides(self):
        model = Transport()
        ready = model.helpers["eon_peace_settlement_ready"]
        def walk(nodes):
            for key, op, value in nodes:
                yield key, op, value
                if isinstance(value, list):
                    yield from walk(value)
        self.assertFalse(any(key == "is_in_peace_conference" and value == "no"
                             for key, op, value in walk(ready)),
                         "Use explicit NOT around the positive native conference query")
        self.assertTrue(model.truth(ready))
        for current in (1, 2):
            with self.subTest(current=current):
                model.countries[current].conference = True
                self.assertFalse(model.truth(ready), "A conference participant cannot accept a new settlement")
                model.countries[current].conference = False
                self.assertTrue(model.truth(ready), "Outside conferences the same two countries remain eligible")

    def test_new_ai_actions_use_documented_stability_trigger(self):
        # HOI4 1.19 native r3 rejected bare stability predicates. Dynamic
        # ROOT.stability values in legacy calculations are valid and unowned.
        path = ROOT / "common/scripted_diplomatic_actions/eon_peace_settlement_actions.txt"
        def walk(nodes):
            for key, op, value in nodes:
                yield key, op, value
                if isinstance(value, list):
                    yield from walk(value)
        predicates = [(key, op, value) for key, op, value in walk(ast(path.read_bytes()))
                      if key == "stability" and op in ("=", "<", ">")]
        self.assertEqual(predicates, [], "Native stability predicate is has_stability; bare stability is rejected")

    def test_documented_stability_predicate_uses_country_fact_and_exact_boundary(self):
        model = Transport()
        for current in (1, 2):
            for actual in (0.349, 0.35, 0.351):
                with self.subTest(current=current, actual=actual):
                    model.countries[current].variables["stability"] = actual
                    self.assertEqual(model.truth(ast("has_stability < 0.35"), current=current), actual < 0.35)
                    self.assertEqual(model.truth(ast("has_stability > 0.35"), current=current), actual > 0.35)
                    self.assertEqual(model.truth(ast("has_stability = 0.35"), current=current), actual == 0.35)

    def test_undocumented_bare_stability_predicate_fails_closed(self):
        model = Transport()
        model.countries[2].variables["stability"] = 0.1
        with self.assertRaisesRegex(AssertionError, "Unsupported visited trigger"):
            model.truth(ast("stability < 0.35"))

    def test_negated_scripted_trigger_keeps_no_semantics(self):
        model = Transport()
        self.assertFalse(model.truth(ast("eon_peace_contact_ready = no")))
        model.countries[2].enemies.clear()
        self.assertTrue(model.truth(ast("eon_peace_contact_ready = no")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
