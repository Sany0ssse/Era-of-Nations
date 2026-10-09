#!/usr/bin/env python3
"""Check actual AI division sources against declared units; no campaign simulation."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCES = (
    Path("common/ai_templates/MD_generic.txt"),
    Path("common/scripted_effects/00_AI_templates.txt"),
)
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|\#[^\n]*|[{}]|!=|<=|>=|[=<>]|[^\s{}=<>!#]+')
REGIMENTAL_MINIMUM = 3  # Native 1.19 gate, retained by the mod's explicit define.


@dataclass(frozen=True)
class Node:
    key: str
    operator: str | None
    value: str | list["Node"] | None
    line: int


def parse(text: str) -> list[Node]:
    """Keep repeated battalion keys, quoted values and source locations intact."""
    tokens = [(match.group(), text.count("\n", 0, match.start()) + 1)
              for match in TOKEN.finditer(text)
              if not match.group().startswith("#")]

    def block(index: int, nested: bool = False) -> tuple[list[Node], int]:
        nodes = []
        while index < len(tokens):
            key, line = tokens[index]
            if key == "}":
                if not nested:
                    raise ValueError(f"Unexpected closing brace on line {line}")
                return nodes, index + 1
            if key in {"{", "=", ">", "<", ">=", "<=", "!="}:
                raise ValueError(f"Unexpected token {key} on line {line}")
            index += 1
            operator = None
            value = None
            if index < len(tokens) and tokens[index][0] in {"=", ">", "<", ">=", "<=", "!="}:
                operator = tokens[index][0]
                index += 1
                if index >= len(tokens):
                    raise ValueError(f"Missing value on line {line}")
                if tokens[index][0] == "{":
                    value, index = block(index + 1, True)
                else:
                    value = tokens[index][0]
                    if value in {"}", "=", ">", "<", ">=", "<=", "!="}:
                        raise ValueError(f"Missing value on line {line}")
                    index += 1
            nodes.append(Node(key, operator, value, line))
        if nested:
            raise ValueError("Unclosed script block")
        return nodes, index

    return block(0)[0]


def scalar(block: list[Node], key: str) -> str | None:
    matches = [node.value for node in block if node.key == key]
    return matches[0] if len(matches) == 1 and isinstance(matches[0], str) else None


def declared_units(root: Path) -> dict[str, list[Node]]:
    units = {}
    for path in sorted((root / "common/units").glob("*.txt")):
        for node in parse(path.read_text(encoding="utf-8-sig")):
            if node.key != "sub_units" or not isinstance(node.value, list):
                continue
            for unit in node.value:
                if isinstance(unit.value, list):
                    if unit.key in units:
                        raise ValueError(f"Duplicate unit definition: {unit.key}")
                    units[unit.key] = unit.value
    return units


def inspect_source(text: str, units: dict[str, list[Node]], source: Path) -> tuple[list[str], int, int]:
    errors = []
    templates = 0
    references = 0

    def walk(nodes: list[Node], hq_role: bool = False) -> None:
        nonlocal templates, references
        hq_role = hq_role or scalar(nodes, "role") == "hq_role"
        line_nodes = next((part.value for part in nodes if part.key == "regiments"
                           and isinstance(part.value, list)), [])
        columns = {}
        group_counts = Counter()
        for entry in line_nodes:
            if entry.key not in units:
                continue
            group = scalar(units[entry.key], "group")
            if isinstance(entry.value, str) and entry.value.isdigit():
                group_counts[group] += int(entry.value)
            elif isinstance(entry.value, list):
                x = scalar(entry.value, "x")
                if x is not None:
                    columns.setdefault(x, []).append(group)
        for node in nodes:
            if not isinstance(node.value, list):
                continue
            if node.key in {"target_template", "division_template"}:
                templates += 1
            if node.key in {"regiments", "support", "regimental_support"}:
                positions = set()
                for entry in node.value:
                    references += 1
                    location = f"{source.as_posix()}:{entry.line}"
                    if entry.key not in units:
                        errors.append(f"{location}: undeclared unit {entry.key}")
                        continue
                    unit = units[entry.key]
                    group = scalar(unit, "group")
                    is_hq_unit = (hq_role and scalar(unit, "allow_in_army_hq") == "yes"
                                  and scalar(unit, "allow_in_non_army_hq") == "no")
                    if node.key == "regiments" and not is_hq_unit:
                        if group == "support" or scalar(unit, "regimental") == "no":
                            errors.append(f"{location}: support-only unit {entry.key} in line regiments")
                    if node.key == "support" and group != "support":
                        errors.append(f"{location}: line unit {entry.key} in support companies")
                    if node.key == "support" and scalar(unit, "divisional") == "no":
                        errors.append(f"{location}: regimental-only unit {entry.key} in division support")
                    allowed_groups = set()
                    if node.key == "regimental_support":
                        if group != "support" or scalar(unit, "regimental") == "no":
                            errors.append(f"{location}: {entry.key} cannot occupy regimental support")
                        allowed_groups = {part.key for field in unit
                                          if field.key == "allowed_battalion_groups" and isinstance(field.value, list)
                                          for part in field.value}
                        if not allowed_groups:
                            errors.append(f"{location}: {entry.key} has no compatible battalion groups")
                    if isinstance(entry.value, str):
                        if not entry.value.isdigit() or int(entry.value) < 1:
                            errors.append(f"{location}: invalid AI battalion count {entry.value}")
                        elif node.key == "regimental_support":
                            # Counts give a necessary capacity check. Actual AI placement is
                            # an engine operation and needs the separate native save probe.
                            compatible = sum(group_counts[group] for group in allowed_groups)
                            if compatible < REGIMENTAL_MINIMUM * int(entry.value):
                                errors.append(f"{location}: not enough compatible line battalions for {entry.key}")
                    elif isinstance(entry.value, list):
                        x, y = scalar(entry.value, "x"), scalar(entry.value, "y")
                        if x is None or y is None or not x.isdigit() or not y.isdigit():
                            errors.append(f"{location}: incomplete or invalid template coordinates")
                        elif (x, y) in positions:
                            errors.append(f"{location}: occupied {node.key} slot ({x}, {y})")
                        else:
                            positions.add((x, y))
                            if node.key == "regimental_support":
                                line_groups = columns.get(x, [])
                                if int(x) >= 4 or y != "0":
                                    errors.append(f"{location}: regimental support lies outside the mod's four single-row slots")
                                if len(line_groups) < REGIMENTAL_MINIMUM:
                                    errors.append(f"{location}: regimental support needs three line battalions in column {x}")
                                if any(line_group not in allowed_groups for line_group in line_groups):
                                    errors.append(f"{location}: incompatible regiment group for {entry.key}")
                    else:
                        errors.append(f"{location}: missing unit count or coordinates")
            walk(node.value, hq_role)

    walk(parse(text))
    return errors, templates, references


def check_mutants(units: dict[str, list[Node]]) -> int:
    """Prove the reader rejects missing IDs and misplaced/overlapping units."""
    bad = [
        'division_template = { regiments = { SP_AA_Battery = { x = 0 y = 0 } } }',
        'target_template = { support = { SP_AA_battery = 1 } }',
        'target_template = { support = { armor_Bat = 1 } }',
        'target_template = { regiments = { L_Inf_Bat = 0 } }',
        'division_template = { regiments = { L_Inf_Bat = { x = 0 y = 0 } Arty_Bat = { x = 0 y = 0 } } }',
        'division_template = { regiments = { L_Inf_Bat = { x = 0 } } }',
        'ordinary = { target_template = { regiments = { HQ_Mot_Inf_Bat = 1 } } }',
    ]
    if "eon_regimental_light_artillery" in units:
        eligible_line = ('L_Inf_Bat = { x = 0 y = 0 } L_Inf_Bat = { x = 0 y = 1 } '
                         'L_Inf_Bat = { x = 0 y = 2 }')
        bad.extend([
            'target_template = { support = { eon_regimental_light_artillery = 1 } }',
            'target_template = { regiments = { L_Inf_Bat = 2 } '
            'regimental_support = { eon_regimental_light_artillery = 1 } }',
            'target_template = { regiments = { armor_Bat = 3 } '
            'regimental_support = { eon_regimental_light_artillery = 1 } }',
            'division_template = { regiments = { L_Inf_Bat = { x = 0 y = 0 } '
            'L_Inf_Bat = { x = 0 y = 1 } } regimental_support = { '
            'eon_regimental_light_artillery = { x = 0 y = 0 } } }',
            'division_template = { regiments = { ' + eligible_line + ' } '
            'regimental_support = { eon_regimental_light_artillery = { x = 0 y = 1 } } }',
            'division_template = { regiments = { ' + eligible_line + ' } '
            'regimental_support = { Arty_Battery = { x = 0 y = 0 } } }',
        ])
        good_regimental = ('division_template = { regiments = { ' + eligible_line + ' } '
                           'regimental_support = { eon_regimental_light_artillery = { x = 0 y = 0 } } }')
        if inspect_source(good_regimental, units, Path("eligible-regimental-control"))[0]:
            raise AssertionError("Reader rejected a compatible three-battalion regiment")
    for index, text in enumerate(bad, 1):
        errors, _, _ = inspect_source(text, units, Path(f"mutant-{index}"))
        if not errors:
            raise AssertionError(f"Reader accepted invalid mutant {index}")
    good = ('hq_generic = { role = hq_role target_template = { '
            'regiments = { HQ_Mot_Inf_Bat = 2 } support = { hq_engineer = 1 } } }')
    if inspect_source(good, units, Path("hq-control"))[0]:
        raise AssertionError("Reader rejected the explicit army-HQ exception")
    # Comments and duplicate battalion keys must not erase or invent references.
    parsed = parse('# SP_AA_battery = { }\ndivision_template = { name = "#quoted" '
                   'regiments = { L_Inf_Bat = { x = 0 y = 0 } L_Inf_Bat = { x = 0 y = 1 } } }')
    if scalar(parsed[0].value, "name") != '"#quoted"':
        raise AssertionError("Quoted hash parsed as a comment")
    errors, _, references = inspect_source('# bad = {}\n' +
        'division_template = { regiments = { L_Inf_Bat = { x = 0 y = 0 } L_Inf_Bat = { x = 0 y = 1 } } }',
        units, Path("duplicate-key-control"))
    if errors or references != 2:
        raise AssertionError("Reader dropped repeated battalion entries")
    return len(bad)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    units = declared_units(args.root)
    rejected = check_mutants(units)
    errors = []
    templates = references = 0
    for source in SOURCES:
        found, count, refs = inspect_source((args.root / source).read_text(encoding="utf-8-sig"), units, source)
        errors.extend(found)
        templates += count
        references += refs
    for error in errors:
        print(f"FAIL {error}")
    print(f"{'FAIL' if errors else 'PASS'}: {templates} actual AI templates, {references} unit references, "
          f"{len(units)} declared units; {rejected} invalid mutants rejected, HQ exception preserved")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
