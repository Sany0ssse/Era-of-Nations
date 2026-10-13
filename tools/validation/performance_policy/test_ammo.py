"""Execute actual periodic ammo hook ASTs with stateful command doubles.

This proves hook eligibility, scope, ordering and reduced repeated searches.
It does not model the native fleet/land/air consumption calculator or FPS.
The fixture is the exact source before this bounded optimization.
"""
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
import itertools
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/validation/diplomacy_package_03"))
from _support import ast, one

SOURCE = ROOT / "common/on_actions/00_ammo_on_actions.txt"
FIXTURE = Path(__file__).resolve().parent / "fixtures/ammo_on_actions_baseline.txt"


def hooks(source, kind):
    return [value for key, _, value in one(ast(source), "on_actions") if key == kind]


def desired_source_ast(baseline):
    """The sole authorized source transformation, preserving every other node."""
    result = deepcopy(ast(baseline))
    body = one(result, "on_actions")
    daily = [i for i, (key, _, _) in enumerate(body) if key == "on_daily"]
    assert len(daily) == 3
    consume = one(one(body[daily[1]][2], "effect"), "if")
    recalc = deepcopy(one(one(body[daily[2]][2], "effect"), "if"))
    eligibility = one(consume, "limit")
    outer_recalc = one(recalc, "limit")
    assert one(outer_recalc, "OR") == one(eligibility, "OR")
    recalc[:] = [(key, op, value) for key, op, value in recalc if key != "limit"]
    recalc.insert(0, ("limit", "=", [("has_game_rule", "=", one(outer_recalc, "has_game_rule"))]))
    consume.append(("if", "=", recalc))
    del body[daily[2]]
    return result


@dataclass
class State:
    stock: float
    production: float
    consumption: float
    cap: float
    battle_consumption: float
    rating: float
    stock_days: float = 0
    summary: float = 0
    topbar: float = 0
    trace: list = field(default_factory=list)


class HookRuntime:
    def __init__(self, state, actor="POL", root="CHI", countries=("POL", "GER", "UKR", "CHI"),
                 war=False, volunteer_pairs=(), potato="no"):
        self.state, self.actor, self.root = state, actor, root
        self.countries, self.war = countries, war
        self.volunteer_pairs, self.potato = set(volunteer_pairs), potato
        self.searches = 0
        self.candidates = 0

    def trigger(self, rows, scope=None, previous=None, mode="AND"):
        scope = scope or self.actor
        values = (self.trigger_node(k, op, v, scope, previous) for k, op, v in rows)
        return any(values) if mode == "OR" else not any(values) if mode == "NOT" else all(values)

    def trigger_node(self, key, op, value, scope, previous):
        assert op == "=", (key, op)
        if key in {"AND", "OR", "NOT"}:
            return self.trigger(value, scope, previous, key)
        if key == "has_war":
            assert scope == self.actor
            return self.war == (value == "yes")
        if key == "has_game_rule":
            assert one(value, "rule") == "ammo_potato_mod"
            return self.potato == one(value, "option")
        if key == "any_other_country":
            self.searches += 1
            for candidate in self.countries:
                if candidate == scope:
                    continue
                self.candidates += 1
                if self.trigger(value, candidate, scope):
                    return True
            return False
        if key == "has_volunteers_amount_from":
            count = [row for row in value if row[0] == "count"]
            assert count == [("count", ">", "0")]
            ref = one(value, "tag")
            sender = {"THIS": scope, "PREV": previous, "ROOT": self.root}.get(ref, ref)
            return (sender, scope) in self.volunteer_pairs
        raise AssertionError((key, op, value))

    def effects(self, rows):
        for key, op, value in rows:
            assert op == "=", (key, op)
            if key == "if":
                if self.trigger(one(value, "limit")):
                    self.effects([row for row in value if row[0] != "limit"])
            elif key == "effect":
                self.effects(value)
            else:
                assert value == "yes", (key, value)
                self.command(key)

    def command(self, key):
        """Commands are unchanged; doubles expose order-sensitive boundaries."""
        s = self.state
        s.trace.append((key, s.stock, s.consumption, s.rating))
        if key == "add_produced_ammo":
            s.stock = min(s.cap, max(0, s.stock + s.production))
            s.topbar = s.stock / s.cap * 100
        elif key == "add_consumed_ammo":
            s.stock = min(s.cap, max(0, s.stock - s.consumption))
            s.topbar = s.stock / s.cap * 100
        elif key == "count_ammo_stock_days":
            s.stock_days = -s.stock / s.rating if s.rating < 0 else (s.cap - s.stock) / s.rating if s.rating > 0 and s.stock < s.cap else 0
        elif key == "count_current_consumption":
            s.consumption = s.battle_consumption
        elif key == "count_consumption_rating":
            s.rating = s.production - s.consumption
        elif key == "count_summarry_ammunition_effect":
            s.summary = max(-0.5, s.rating * 0.00001) if s.rating < 0 and s.stock == 0 else 0
        else:
            raise AssertionError(key)

    def tick(self, source):
        for hook in hooks(source, "on_daily"):
            self.effects(one(hook, "effect"))


class AmmoPeriodicRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before, cls.after = FIXTURE.read_bytes(), SOURCE.read_bytes()

    def initial(self, stock=50, old=7, new=98):
        return State(stock, 11, old, 100, new, 11-old)

    def compare(self, source=None):
        actual = source if source is not None else self.after
        for war, volunteer, potato, stock, old, new in itertools.product(
                (False, True), (False, True), ("no", "yes", "other"), (0, 50, 100), (0, 7, 120), (0, 98)):
            pairs = {("POL", "UKR")} if volunteer else set()
            a = HookRuntime(self.initial(stock, old, new), war=war, volunteer_pairs=pairs, potato=potato)
            b = HookRuntime(self.initial(stock, old, new), war=war, volunteer_pairs=pairs, potato=potato)
            a.tick(self.before); b.tick(actual)
            if a.state != b.state:
                raise AssertionError((war, volunteer, potato, stock, old, new, a.state, b.state))
        return 216

    def test_only_owned_daily_scan_is_merged(self):
        self.assertEqual(ast(self.after), desired_source_ast(self.before))

    def test_one_foreign_search_at_peace_even_without_volunteers(self):
        for potato in ("no", "yes", "other"):
            runtime = HookRuntime(self.initial(), potato=potato)
            runtime.tick(self.after)
            self.assertEqual(runtime.searches, 1)
            self.assertEqual(runtime.candidates, 3)
        baseline = HookRuntime(self.initial(), potato="no")
        baseline.tick(self.before)
        self.assertEqual(baseline.searches, 2, "The original duplicate must remain reproducible")

    def test_stateful_differential_matrix_preserves_trace_and_cashless_values(self):
        self.assertEqual(self.compare(), 216)

    def test_old_consumption_and_rate_are_used_before_recalculation(self):
        runtime = HookRuntime(self.initial(), war=True)
        runtime.tick(self.after)
        self.assertEqual([row[0] for row in runtime.state.trace], [
            "add_produced_ammo", "add_consumed_ammo", "count_ammo_stock_days",
            "count_current_consumption", "count_consumption_rating", "count_summarry_ammunition_effect"])
        self.assertEqual(runtime.state.stock, 54)
        self.assertEqual(runtime.state.stock_days, 11.5)
        self.assertEqual(runtime.state.consumption, 98)

    def test_volunteer_sender_is_previous_actor_not_callback_root(self):
        a = HookRuntime(self.initial(), root="CHI", volunteer_pairs={("POL", "UKR")})
        a.tick(self.after)
        self.assertIn("add_consumed_ammo", [row[0] for row in a.state.trace])
        b = HookRuntime(self.initial(), root="CHI", volunteer_pairs={("CHI", "UKR")})
        b.tick(self.after)
        self.assertEqual([row[0] for row in b.state.trace], ["add_produced_ammo"])

    def test_multiday_representative_countries_use_current_participation(self):
        countries = ("POL", "GER", "UKR", "USA", "CHI", "ALB", "BEL")
        schedule = ((False, False, "no"), (False, True, "no"), (True, False, "no"),
                    (False, False, "no"), (False, True, "yes"), (True, False, "yes"),
                    (False, True, "no"), (False, False, "no"))
        for actor in countries[:-1]:
            before_state, after_state = self.initial(), self.initial()
            target = "UKR" if actor != "UKR" else "POL"
            for day, (war, volunteer, potato) in enumerate(schedule):
                pairs = {(actor, target)} if volunteer else set()
                a = HookRuntime(before_state, actor=actor, root="BEL", countries=countries,
                                war=war, volunteer_pairs=pairs, potato=potato)
                b = HookRuntime(after_state, actor=actor, root="BEL", countries=countries,
                                war=war, volunteer_pairs=pairs, potato=potato)
                a.tick(self.before); b.tick(self.after)
                self.assertEqual(a.state, b.state, (actor, day))
                self.assertLessEqual(b.searches, 1, (actor, day))

    def test_potato_rule_and_all_monthly_hooks_are_preserved(self):
        self.assertEqual(hooks(self.after, "on_monthly"), hooks(self.before, "on_monthly"))
        for potato in ("yes", "other"):
            runtime = HookRuntime(self.initial(), war=True, potato=potato)
            runtime.tick(self.after)
            self.assertEqual([row[0] for row in runtime.state.trace], ["add_produced_ammo", "add_consumed_ammo", "count_ammo_stock_days"])

    def test_negative_controls_detect_order_scope_rule_and_production_regressions(self):
        prefix, marker, suffix = self.after.rpartition(b"count_ammo_stock_days = yes")
        self.assertTrue(marker)
        mutations = (
            self.after.replace(b"tag = PREV", b"tag = ROOT"),
            self.after.replace(b"option = no", b"option = yes", 1),
            self.after.replace(b"add_produced_ammo = yes", b"add_consumed_ammo = yes", 1),
            prefix + b"count_current_consumption = yes" + suffix,
        )
        for index, mutated in enumerate(mutations):
            with self.subTest(mutation=index):
                self.assertNotEqual(ast(mutated), desired_source_ast(self.before))
                with self.assertRaises(AssertionError):
                    self.compare(mutated)

    def test_bom_eol_and_produced_hook_bytes_preserved(self):
        self.assertEqual(self.after.startswith(b"\xef\xbb\xbf"), self.before.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(self.after.count(b"\r\n"), 0)
        marker = b"    on_daily = {\n        effect = { add_produced_ammo = yes }\n    }"
        self.assertIn(marker, self.before)
        self.assertIn(marker, self.after)


if __name__ == "__main__":
    unittest.main()
