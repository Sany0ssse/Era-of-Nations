#!/usr/bin/env python3
"""Validate actual regimental support sources; this is not a combat or GUI test."""

from __future__ import annotations

import argparse
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import re

from test_ai_templates import Node, ROOT, declared_units, parse, scalar


IDS = ("eon_regimental_light_artillery", "eon_regimental_motorized_artillery")
GROUPS = (("infantry",), ("mobile", "armor"))


def block(nodes: list[Node], key: str) -> list[Node]:
    matches = [node.value for node in nodes if node.key == key]
    if len(matches) != 1 or not isinstance(matches[0], list):
        raise AssertionError(f"Missing or duplicate block {key}")
    return matches[0]


def number(nodes: list[Node], key: str) -> Decimal:
    value = scalar(nodes, key)
    if value is None:
        raise AssertionError(f"Missing or repeated numeric field {key}")
    return Decimal(value)


def validate_unit(unit: list[Node], baseline: list[Node], motorized: bool) -> None:
    # Native support semantics are explicit; line/divisional placement must not
    # silently become another way to duplicate this attachment.
    assert scalar(unit, "group") == "support"
    assert scalar(unit, "regimental") == "yes"
    assert scalar(unit, "divisional") == "no"
    assert scalar(unit, "active") == "yes"
    assert scalar(unit, "affects_speed") == "no"
    assert number(unit, "combat_width") == 0
    assert tuple(node.key for node in block(unit, "allowed_battalion_groups")) == GROUPS[int(motorized)]
    assert {"artillery", "support"} == {node.key for node in block(unit, "type")}
    categories = {node.key for node in block(unit, "categories")}
    assert {"category_support_battalions", "category_regimental_support_battalions",
            "category_army", "category_artillery"} <= categories
    assert scalar(unit, "sprite") == scalar(baseline, "sprite")

    needs = {node.key: Decimal(node.value) for node in block(unit, "need")}
    assert needs["artillery_equipment"] == number(block(baseline, "need"), "artillery_equipment") / 2
    assert needs["command_control_equipment"] > 0
    assert all(value > 0 for value in needs.values())
    assert set(needs) == {node.key for node in block(unit, "essential")}
    assert number(unit, "manpower") == number(baseline, "manpower") / 2
    for stat in ("max_strength", "max_organisation"):
        assert number(unit, stat) == number(baseline, stat) / 2
    assert number(unit, "supply_consumption") >= number(baseline, "supply_consumption") / 2 > 0
    for stat in ("soft_attack", "hard_attack", "defense", "breakthrough"):
        assert 1 + number(unit, stat) == (1 + number(baseline, stat)) / 2
    assert not any(node.key in {"battalion_mult", "battalion_add", "supply_consumption_factor",
                               "fuel_consumption_factor"} for node in unit)
    if motorized:
        assert needs["util_vehicle_equipment"] == 5
        assert scalar(unit, "transport") == "util_vehicle_equipment"
        assert number(unit, "own_equipment_fuel_consumption_mult") > 0
        assert scalar(unit, "can_be_parachuted") == "no"
    else:
        assert set(needs) == {"artillery_equipment", "command_control_equipment"}
        assert number(unit, "supply_consumption") == number(baseline, "supply_consumption") / 2


def change(unit: list[Node], key: str, value: str | list[Node]) -> list[Node]:
    assert sum(node.key == key for node in unit) == 1
    return [replace(node, value=value) if node.key == key else node for node in unit]


def validate_category_registry(units: dict[str, list[Node]], categories: set[str]) -> None:
    # The mod overrides the vanilla registry. A vanilla-known name still needs
    # an explicit mod declaration, or native loading reports an invalid tag.
    for name in IDS:
        requested = {node.key for node in block(units[name], "categories")}
        missing = requested - categories
        assert not missing, f"{name}: undeclared subunit categories {sorted(missing)}"


def mutation_checks(units: dict[str, list[Node]]) -> int:
    source = units[IDS[1]]
    mutants = [change(source, key, value) for key, value in (
        ("group", "armor"), ("regimental", "no"), ("divisional", "yes"),
        ("active", "no"), ("combat_width", "1"), ("manpower", "0"),
        ("max_strength", "0"), ("soft_attack", "0"), ("supply_consumption", "0"),
        ("own_equipment_fuel_consumption_mult", "0"), ("can_be_parachuted", "yes"),
    )]
    needs = block(source, "need")
    mutants.append(change(source, "need", change(needs, "artillery_equipment", "0")))
    mutants.append(change(source, "allowed_battalion_groups", [Node("infantry", None, None, 0)]))
    mutants.append(change(source, "essential", [Node("artillery_equipment", None, None, 0)]))
    for index, unit in enumerate(mutants, 1):
        try:
            validate_unit(unit, units["Arty_Battery"], True)
        except (AssertionError, KeyError):
            continue
        raise AssertionError(f"Validator accepted regimental support mutant {index}")
    return len(mutants)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--engine-root", type=Path,
                        default=Path(r"D:\SteamLibrary\steamapps\common\Hearts of Iron IV"))
    args = parser.parse_args()
    units = declared_units(args.root)
    registry = block(parse((args.root / "common/unit_tags/00_categories.txt").read_text(encoding="utf-8-sig")), "sub_unit_categories")
    categories = {node.key for node in registry}
    assert len(categories) == len(registry), "Duplicate subunit category declaration"
    validate_category_registry(units, categories)
    try:
        validate_category_registry(units, categories - {"category_regimental_support_battalions"})
    except AssertionError:
        pass
    else:
        raise AssertionError("Validator accepted a missing regimental support category")
    for index, name in enumerate(IDS):
        validate_unit(units[name], units["Arty_Battery"], bool(index))
    rejected = mutation_checks(units) + 1

    # Check declared, paid-for equipment, rather than trusting equipment labels.
    equipments = {}
    for path in (args.root / "common/units/equipment").glob("*.txt"):
        for container in parse(path.read_text(encoding="utf-8-sig")):
            if container.key == "equipments" and isinstance(container.value, list):
                equipments.update({node.key: node.value for node in container.value
                                   if isinstance(node.value, list)})
    for name in IDS:
        for need in block(units[name], "need"):
            assert need.key in equipments, f"Undeclared required equipment {need.key}"
            assert number(equipments[need.key], "build_cost_ic") > 0
    assert number(equipments["util_vehicle_equipment"], "fuel_consumption") > 0

    # Every live direct towed-artillery upgrade in both DLC paths applies to
    # the new units, at half the old battery's calibrated direct bonus.
    upgrades = 0
    for filename, prefix in (("artillery.txt", ""), ("NSB_artillery.txt", "nsb_")):
        technologies = block(parse((args.root / "common/technologies" / filename).read_text(encoding="utf-8-sig")), "technologies")
        for level in range(1, 6):
            tech = block(technologies, f"{prefix}Arty_upgrade_{level}")
            old = block(tech, "Arty_Battery")
            for name in IDS:
                new = block(tech, name)
                assert {node.key for node in new} == {node.key for node in old}
                for node in old:
                    assert number(new, node.key) == Decimal(node.value) / 2
            upgrades += 1

    # Both languages must be actual readable labels with the game encoding.
    for language in ("english", "russian"):
        path = args.root / f"localisation/{language}/eon_regimental_support_l_{language}.yml"
        data = path.read_bytes()
        assert data.startswith(b"\xef\xbb\xbf")
        assert data.count(b"\n") == data.count(b"\r\n")
        text = data.decode("utf-8-sig")
        assert text.startswith(f"l_{language}:\r\n")
        for name in IDS:
            for key in (name, name + "_desc"):
                assert re.search(r'^ ' + re.escape(key) + r':0 "[^"\r\n]+"\r?$', text, re.M), key

    # These are source declarations only. Scripting a template can bypass UI
    # checks; reading these declarations does not prove interactive placement.
    defines = (args.root / "common/defines/MD_defines.lua").read_text(encoding="utf-8-sig")
    assert re.search(r"NDefines\.NMilitary\.MAX_DIVISION_BRIGADE_WIDTH\s*=\s*4\b", defines)
    assert re.search(r"NDefines\.NMilitary\.MAX_REGIMENTAL_SUPPORT_WIDTH\s*=\s*4\b", defines)
    assert "REGIMENTAL_SUPPORT_REQUIRED_BATTALIONS" not in defines
    installed = args.engine_root / "common/defines/00_defines.lua"
    native_note = "installed default unavailable"
    if installed.is_file():
        native = installed.read_text(encoding="utf-8-sig")
        assert re.search(r"REGIMENTAL_SUPPORT_REQUIRED_BATTALIONS\s*=\s*\{\s*3\s*\}", native)
        native_note = "installed native minimum of 3 declared; GUI not tested"
    print(f"PASS: 2 paid regimental units with declared category IDs, 10 complete upgrade paths, 2 BOM/CRLF languages, "
          f"{rejected} invalid mutants rejected; {native_note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
