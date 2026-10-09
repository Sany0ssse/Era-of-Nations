#!/usr/bin/env python3
"""Check infantry technology subunit unlocks against the actual mod database."""

from __future__ import annotations

import unittest

from test_ai_templates import ROOT, declared_units, parse, scalar


def unlock_references(nodes):
    for node in nodes:
        if isinstance(node.value, list):
            if node.key == "enable_subunits":
                yield from node.value
            yield from unlock_references(node.value)


class InfantryUnlockReferences(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.units = declared_units(ROOT)
        cls.tech = parse((ROOT / "common/technologies/infantry.txt").read_text(encoding="utf-8-sig"))
        cls.unlocks = list(unlock_references(cls.tech))

    def test_each_actual_unlock_has_a_declared_subunit(self):
        self.assertTrue(self.unlocks, "No actual unlocks were read")
        missing = [f"{node.key} on line {node.line}" for node in self.unlocks if node.key not in self.units]
        self.assertFalse(missing, "Undeclared enable_subunits: " + ", ".join(missing))

    def test_existing_special_forces_id_remains_active_and_unlockable(self):
        self.assertIn("Special_Forces", self.units)
        self.assertEqual(scalar(self.units["Special_Forces"], "active"), "yes")
        self.assertIn("Special_Forces", {node.key for node in self.unlocks})


if __name__ == "__main__":
    unittest.main(verbosity=2)
