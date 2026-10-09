#!/usr/bin/env python3
"""Evaluate real AI enable/upgrade conditions at the repaired factory boundaries."""

from __future__ import annotations

import operator
import unittest
from dataclasses import dataclass, field

from test_ai_templates import Node, ROOT, parse, scalar


def block(nodes: list[Node], key: str) -> list[Node]:
    matches = [node.value for node in nodes if node.key == key]
    if len(matches) != 1 or not isinstance(matches[0], list):
        raise AssertionError(f"Expected one {key} block")
    return matches[0]


@dataclass
class Country:
    military: int
    naval: int = 1
    tag: str = "GER"
    ideas: set[str] = field(default_factory=set)


OPERATORS = {"=": operator.eq, "<": operator.lt, ">": operator.gt,
             "<=": operator.le, ">=": operator.ge, "!=": operator.ne}


def condition(nodes: list[Node], country: Country) -> bool:
    values = []
    for node in nodes:
        if node.key in {"AND", "OR", "NOT"}:
            if node.key == "OR":
                values.append(any(condition([part], country) for part in node.value))
            elif node.key == "NOT":
                values.append(not condition(node.value, country))
            else:
                values.append(condition(node.value, country))
        elif node.key in {"num_of_military_factories", "num_of_naval_factories"}:
            number = country.military if node.key == "num_of_military_factories" else country.naval
            values.append(OPERATORS[node.operator](number, int(node.value)))
        elif node.key in {"tag", "original_tag"}:
            values.append(OPERATORS[node.operator](country.tag, node.value))
        elif node.key == "has_idea":
            values.append(node.value in country.ideas)
        else:
            raise AssertionError(f"Unsupported condition: {node.key}")
    return all(values)


def priority(nodes: list[Node], country: Country) -> float:
    value = float(scalar(nodes, "factor"))
    for node in nodes:
        if node.key == "modifier":
            tests = [part for part in node.value if part.key != "factor"]
            if condition(tests, country):
                value *= float(scalar(node.value, "factor"))
        elif node.key != "factor":
            raise AssertionError(f"Unsupported priority field: {node.key}")
    return value


class AIFactoryBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        source = parse((ROOT / "common/ai_templates/MD_generic.txt").read_text(encoding="utf-8-sig"))
        marines = block(source, "marines_generic")
        cls.light = block(marines, "light_marine_brigades")
        cls.motorized = block(marines, "mot_marines_brigades")
        ifv = block(source, "IFV_generic")
        cls.generic_ifv = block(ifv, "ifv_infantry_generic")
        cls.division_ifv = block(ifv, "ifv_infantry_divisions")

    def test_light_marines_include_fifth_factory(self) -> None:
        for factories in (4, 5, 6, 7, 8, 9, 10):
            with self.subTest(factories=factories):
                country = Country(factories)
                expected = factories <= 5
                self.assertEqual(condition(block(self.light, "enable"), country), expected)
                self.assertEqual(priority(block(self.light, "upgrade_prio"), country) > 0, expected)

    def test_motorized_marines_cover_six_through_nine(self) -> None:
        for factories in (4, 5, 6, 7, 8, 9, 10):
            with self.subTest(factories=factories):
                country = Country(factories)
                expected = 6 <= factories <= 9
                self.assertEqual(condition(block(self.motorized, "enable"), country), expected)
                self.assertEqual(priority(block(self.motorized, "upgrade_prio"), country) > 0, expected)

    def test_marines_preserve_dockyard_requirement(self) -> None:
        for factories in (4, 5, 6, 7, 8, 9, 10):
            country = Country(factories, naval=0)
            for template in (self.light, self.motorized):
                self.assertFalse(condition(block(template, "enable"), country))
                self.assertEqual(priority(block(template, "upgrade_prio"), country), 0)

    def test_ifv_has_working_target_at_fifteen_sixteen_seventeen(self) -> None:
        for factories in (15, 16, 17):
            country = Country(factories)
            generic = condition(block(self.generic_ifv, "enable"), country)
            division = condition(block(self.division_ifv, "enable"), country)
            self.assertEqual(generic, factories <= 16)
            self.assertEqual(division, factories >= 17)
            self.assertEqual(priority(block(self.generic_ifv, "upgrade_prio"), country) > 0, factories <= 16)
            self.assertTrue((generic and priority(block(self.generic_ifv, "upgrade_prio"), country) > 0)
                            or (division and priority(block(self.division_ifv, "upgrade_prio"), country) > 0))

    def test_ifv_retains_country_weights_and_rank_suppression(self) -> None:
        for tag, multiplier in (("GER", 1), ("USA", 5), ("CHI", 5), ("SOV", 7)):
            self.assertEqual(priority(block(self.division_ifv, "upgrade_prio"), Country(17, tag=tag)), multiplier)
        for idea in ("minor_power", "non_power"):
            for factories in (15, 16, 17):
                country = Country(factories, ideas={idea})
                self.assertEqual(priority(block(self.division_ifv, "upgrade_prio"), country), 0)
                self.assertEqual(priority(block(self.generic_ifv, "upgrade_prio"), country) > 0, factories <= 16)


if __name__ == "__main__":
    unittest.main(verbosity=2)
