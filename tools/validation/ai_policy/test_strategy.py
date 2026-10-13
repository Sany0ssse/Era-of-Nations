"""Execute actual AI strategy guard ASTs; this is not native AI-choice proof.

The model is deliberately closed to scopes, flag checks and target quantifiers
used by the guards tested here. Unknown keys fail instead of defaulting to true.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/validation/peace_settlement"))
from test_legacy_safety import parse, one


def blocks(rows, key):
    out = []
    for k, op, value in rows:
        if k == key:
            out.append(value)
        if isinstance(value, list):
            out.extend(blocks(value, key))
    return out


class Guards:
    def __init__(self, tag="POL", root="GER", countries=("POL", "GER", "BEL")):
        self.tag, self.root = tag, root
        self.countries = set(countries)
        self.flags = {c: set() for c in countries}
        self.wargoals, self.justifying = set(), set()
        self.units_enabled = True
        self.scientist_specializations = set()
        self.political_power = 300

    def reference(self, name, scope, previous):
        return {"THIS": scope, "PREV": previous, "ROOT": self.root}.get(name, name)

    def rows(self, rows, scope=None, previous=None, mode="AND"):
        scope = scope or self.tag
        values = [self.node(k, op, value, scope, previous) for k, op, value in rows]
        if mode == "OR":
            return any(values)
        if mode == "NOT":
            return not any(values)
        return all(values)

    def node(self, key, op, value, scope, previous):
        if key == "has_political_power":
            assert op == ">", op
            return self.political_power > float(value)
        assert op == "=", (key, op)
        if key in ("AND", "OR", "NOT"):
            return self.rows(value, scope, previous, key)
        if key == "any_other_country":
            return any(self.rows(value, c, scope) for c in self.countries if c != scope)
        if key in ("is_justifying_wargoal_against", "has_wargoal_against"):
            pairs = self.justifying if key.startswith("is_") else self.wargoals
            return (scope, self.reference(value, scope, previous)) in pairs
        if key == "has_country_flag":
            return value in self.flags[scope]
        if key in ("tag", "original_tag"):
            return scope == value
        if key == "ai_for_units_is_not_disabled":
            return self.units_enabled == (value == "yes")
        if key == "can_assign_supportive_scientist_to_faction":
            return value in self.scientist_specializations
        raise AssertionError((key, op, value))


def effect_guards():
    source = ROOT / "common/scripted_effects/00_ai_strategy_scripted_effects.txt"
    effect = one(parse(source.read_text(encoding="utf-8-sig")), "ai_update_build_units")
    branches = [value for key, op, value in effect if key == "if"]
    start = one(branches[0], "limit")
    clear = one(branches[1], "limit")
    start_foreign = blocks(start, "any_other_country")
    assert len(start_foreign) == 1
    # Find the outermost removal predicate containing the foreign-country check.
    clear_foreign = [(k, op, v) for k, op, v in clear
                     if k in ("NOT", "any_other_country")
                     and (k == "any_other_country" or blocks(v, "any_other_country"))]
    assert len(clear_foreign) == 1
    return start_foreign[0], clear_foreign


class StrategyRegression(unittest.TestCase):
    def test_incoming_wargoal_uses_current_country_not_root_aggressor(self):
        start, clear = effect_guards()
        model = Guards(tag="POL", root="GER")
        model.wargoals.add(("GER", "POL"))
        self.assertTrue(model.rows([( "any_other_country", "=", start)]))
        self.assertFalse(model.rows(clear))

    def test_justification_uses_previous_target_scope_in_nested_callback(self):
        start, clear = effect_guards()
        model = Guards(tag="UKR", root="CHI", countries=("UKR", "SOV", "BEL", "CHI"))
        model.justifying.add(("SOV", "UKR"))
        self.assertTrue(model.rows([( "any_other_country", "=", start)]))
        self.assertFalse(model.rows(clear))

    def test_neutral_bystander_cannot_erase_one_real_threat(self):
        _, clear = effect_guards()
        model = Guards()
        model.wargoals.add(("GER", "POL"))
        # BEL neither has nor justifies a wargoal. It must not satisfy removal.
        self.assertFalse(model.rows(clear))

    def test_no_foreign_threat_allows_removal_including_no_other_country(self):
        _, clear = effect_guards()
        self.assertTrue(Guards().rows(clear))
        alone = Guards(countries=("POL",))
        self.assertTrue(alone.rows(clear))

    def test_unrelated_wargoal_does_not_raise_threat_for_current_country(self):
        start, clear = effect_guards()
        model = Guards()
        model.wargoals.add(("GER", "BEL"))
        self.assertFalse(model.rows([( "any_other_country", "=", start)]))
        self.assertTrue(model.rows(clear))

    def test_major_factory_allowed_filter_reaches_each_supported_tag(self):
        p = ROOT / "common/ai_strategy/MD_econ_ai.txt"
        rule = one(parse(p.read_text(encoding="utf-8-sig")), "AI_major_military_factories")
        guard = one(rule, "allowed")
        supported = ("CHI", "BRA", "SAF", "RAJ", "GER", "FRA", "ITA", "CAN", "USA", "JAP")
        for tag in supported:
            with self.subTest(tag=tag):
                self.assertTrue(Guards(tag=tag).rows(guard))
        for tag in ("POL", "UKR", "ALB", "BOT", "SOV"):
            with self.subTest(excluded=tag):
                self.assertFalse(Guards(tag=tag).rows(guard))
        disabled = Guards(tag="GER")
        disabled.units_enabled = False
        self.assertFalse(disabled.rows(guard))

    def test_sadc_filter_reaches_members_and_preserves_exclusions(self):
        p = ROOT / "common/ai_strategy/BOT.txt"
        guard = one(one(parse(p.read_text(encoding="utf-8-sig")), "SADC_cooperation"), "allowed")
        supported = ("AGL", "BOT", "DRC", "LES", "MAD", "MLC", "MLW", "MOZ", "MRT",
                     "NAM", "RCD", "SAF", "SEY", "SWA", "TNZ", "UNI", "ZAM", "ZIM")
        for tag in supported:
            with self.subTest(tag=tag):
                self.assertTrue(Guards(tag=tag).rows(guard))
        for tag in ("POL", "GER", "UKR", "USA", "CHI", "ALB"):
            with self.subTest(excluded=tag):
                self.assertFalse(Guards(tag=tag).rows(guard))

    def test_supportive_scientist_includes_air_and_requires_pp_reserve(self):
        p = ROOT / "common/ai_strategy/default.txt"
        guard = one(one(parse(p.read_text(encoding="utf-8-sig")),
                        "default_assign_supportive_scientist"), "enable")
        for specialization in ("specialization_land", "specialization_nuclear",
                               "specialization_naval", "specialization_air"):
            with self.subTest(specialization=specialization):
                model = Guards()
                model.scientist_specializations = {specialization}
                self.assertTrue(model.rows(guard))
                model.political_power = 250
                self.assertFalse(model.rows(guard))
        self.assertFalse(Guards().rows(guard))


if __name__ == "__main__":
    unittest.main(verbosity=2)
