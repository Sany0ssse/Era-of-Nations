#!/usr/bin/env python3
"""Exercise the actual tutorial hooks and replay flow in a small script reader.

This checks scope, ordering and one-time delivery. It does not render game UI or
prove multiplayer acceptance; the native game remains the authority for those.
"""

from __future__ import annotations

import copy
import re
import unittest
from dataclasses import dataclass, field

from test_ai_templates import Node, ROOT, parse, scalar


FLAG = "eon_division_design_tutorial_seen"
FIRST = "eon_division_design_tutorial.1"


def block(nodes: list[Node], key: str) -> list[Node]:
    matches = [node.value for node in nodes if node.key == key]
    if len(matches) != 1 or not isinstance(matches[0], list):
        raise AssertionError(f"Expected one {key} block")
    return matches[0]


def source(path: str) -> list[Node]:
    return parse((ROOT / path).read_text(encoding="utf-8-sig"))


@dataclass
class Country:
    tag: str
    human: bool
    exists: bool = True
    flags: set[str] = field(default_factory=set)
    events: list[str] = field(default_factory=list)


def allowed(nodes: list[Node], country: Country) -> bool:
    checks = []
    for node in nodes:
        if node.key == "is_ai":
            checks.append((not country.human) == (node.value == "yes"))
        elif node.key == "exists":
            checks.append(country.exists == (node.value == "yes"))
        elif node.key == "always":
            checks.append(node.value == "yes")
        elif node.key == "has_country_flag":
            checks.append(node.value in country.flags)
        elif node.key == "NOT" and isinstance(node.value, list):
            checks.append(not allowed(node.value, country))
        else:
            raise AssertionError(f"Unsupported trigger: {node.key}")
    return all(checks)


def execute(nodes: list[Node], country: Country | None, countries: list[Country]) -> None:
    for node in nodes:
        if node.key == "every_country":
            limit = block(node.value, "limit")
            effects = [part for part in node.value if part.key != "limit"]
            for target in countries:
                if allowed(limit, target):
                    execute(effects, target, countries)
        elif node.key == "if":
            if allowed(block(node.value, "limit"), country):
                execute([part for part in node.value if part.key != "limit"], country, countries)
        elif node.key == "set_country_flag":
            country.flags.add(node.value)
        elif node.key == "country_event":
            event = scalar(node.value, "id")
            if FLAG not in country.flags:
                raise AssertionError("Tutorial queued before the persistent seen flag")
            if not country.human:
                raise AssertionError("Tutorial delivered to AI")
            country.events.append(event)
        else:
            # Fails closed if an informational flow acquires an untested effect.
            raise AssertionError(f"Unsupported tutorial effect: {node.key}")


class TutorialLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.hooks = block(source("common/on_actions/eon_division_design_tutorial_on_actions.txt"), "on_actions")
        cls.startup = block(block(cls.hooks, "on_startup"), "effect")
        cls.daily = block(block(cls.hooks, "on_daily"), "effect")
        cls.category = block(source("common/decisions/categories/eon_division_design_tutorial_categories.txt"),
                             "eon_division_design_help_category")
        cls.decision = block(block(source("common/decisions/eon_division_design_tutorial_decisions.txt"),
                                  "eon_division_design_help_category"), "eon_division_design_reopen_guide")
        cls.pages = [node.value for node in source("events/eon_division_design_tutorial.txt")
                     if node.key == "country_event"]

    def test_startup_delivers_to_each_existing_human_once(self) -> None:
        countries = [Country("USA", True), Country("SWI", True),
                     Country("FRA", False), Country("ZZZ", True, False)]
        execute(self.startup, None, countries)
        self.assertEqual([country.events for country in countries], [[FIRST], [FIRST], [], []])
        execute(self.startup, None, countries)
        for country in countries:
            execute(self.daily, country, countries)
        self.assertEqual([country.events for country in countries], [[FIRST], [FIRST], [], []])

    def test_daily_covers_old_save_and_later_human_control(self) -> None:
        old_save = Country("GER", True)
        late_join = Country("RAJ", False)
        execute(self.daily, old_save, [old_save, late_join])
        execute(self.daily, late_join, [old_save, late_join])
        self.assertEqual(old_save.events, [FIRST])
        self.assertEqual(late_join.events, [])
        late_join.human = True
        execute(self.daily, late_join, [old_save, late_join])
        execute(self.daily, late_join, [old_save, late_join])
        self.assertEqual(late_join.events, [FIRST])

    def test_seen_country_does_not_repeat_after_state_reload(self) -> None:
        country = Country("FRA", True)
        execute(self.daily, country, [country])
        loaded = Country(country.tag, country.human, flags=set(country.flags))
        execute(self.startup, None, [loaded])
        execute(self.daily, loaded, [loaded])
        self.assertEqual(loaded.events, [])
        self.assertIn(FLAG, loaded.flags)

    def test_seen_is_consumed_before_immediate_event(self) -> None:
        for actual in (self.startup, self.daily):
            mutated = copy.deepcopy(actual)
            scope = mutated[0].value
            flag = next(index for index, node in enumerate(scope) if node.key == "set_country_flag")
            event = next(index for index, node in enumerate(scope) if node.key == "country_event")
            scope[flag], scope[event] = scope[event], scope[flag]
            country = Country("USA", True)
            with self.assertRaisesRegex(AssertionError, "queued before"):
                execute(mutated, country, [country])

    def test_replay_is_free_and_rechecks_human_control(self) -> None:
        self.assertEqual(scalar(self.decision, "cost"), "0")
        self.assertEqual(scalar(block(self.decision, "ai_will_do"), "factor"), "0")
        for human in (True, False):
            country = Country("UKR", human, flags={FLAG})
            self.assertEqual(allowed(block(self.category, "visible"), country), human)
            self.assertEqual(allowed(block(self.decision, "visible"), country), human)
            self.assertEqual(allowed(block(self.decision, "available"), country), human)
            execute(block(self.decision, "complete_effect"), country, [country])
            self.assertEqual(country.events, [FIRST] if human else [])
            self.assertEqual(country.flags, {FLAG})

    def test_pages_are_human_only_with_safe_close_and_valid_links(self) -> None:
        page_ids = {scalar(page, "id") for page in self.pages}
        self.assertEqual(page_ids, {FIRST, "eon_division_design_tutorial.2", "eon_division_design_tutorial.3"})
        for page in self.pages:
            self.assertEqual(scalar(page, "is_triggered_only"), "yes")
            self.assertTrue(allowed(block(page, "trigger"), Country("GER", True)))
            self.assertFalse(allowed(block(page, "trigger"), Country("GER", False)))
            options = [node.value for node in page if node.key == "option"]
            self.assertEqual(scalar(options[0], "name"), "eon_division_design_tutorial.close")
            self.assertEqual(scalar(block(options[0], "ai_chance"), "factor"), "1")
            self.assertEqual({node.key for node in options[0]}, {"name", "ai_chance"})
            for option in options[1:]:
                self.assertEqual({node.key for node in option}, {"name", "ai_chance", "country_event"})
                self.assertEqual(scalar(block(option, "ai_chance"), "factor"), "0")
                self.assertIn(scalar(block(option, "country_event"), "id"), page_ids)

    def test_all_page_and_decision_labels_exist_in_both_localisations(self) -> None:
        keys = {"eon_division_design_help_category", "eon_division_design_help_category_desc",
                "eon_division_design_reopen_guide", "eon_division_design_reopen_guide_desc"}
        for page in self.pages:
            keys.update(scalar(page, field) for field in ("title", "desc"))
            keys.update(scalar(node.value, "name") for node in page if node.key == "option")
        for language in ("english", "russian"):
            path = ROOT / f"localisation/{language}/eon_division_design_tutorial_l_{language}.yml"
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), str(path))
            text = raw.decode("utf-8-sig")
            self.assertTrue(text.startswith(f"l_{language}:"))
            present = re.findall(r"^ ([\w.]+):", text, re.M)
            self.assertEqual(len(present), len(set(present)))
            self.assertFalse(keys - set(present), f"{language}: {keys - set(present)}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
