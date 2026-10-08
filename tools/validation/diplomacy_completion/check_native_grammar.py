"""Reject syntax disproven by HOI4 1.19.3 startup; not a native compiler."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    'eon_source_ast', ROOT / 'tools/validation/diplomacy_package_03/_support.py')
parser = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = parser
spec.loader.exec_module(parser)

COMPARISONS = {'equals', 'not_equals', 'less_than', 'less_than_or_equals',
               'greater_than', 'greater_than_or_equals'}


def walk(nodes):
    for key, operator, value in nodes:
        yield key, operator, value
        if isinstance(value, list):
            yield from walk(value)


def inspect(nodes):
    errors = []
    for key, operator, value in walk(nodes):
        if operator in ('>=', '<='):
            errors.append(f'Unsupported inclusive shorthand: {key} {operator}')
        if key == 'has_opinion_modifier' and isinstance(value, list):
            errors.append('has_opinion_modifier requires a scalar modifier ID')
        if key in ('has_government', 'has_war_with', 'tag') and isinstance(value, str) and value.startswith('eon_'):
            errors.append('Country variable in ' + key + ' needs var: prefix')
        if key == 'check_variable' and isinstance(value, list):
            fields = {k: v for k, op, v in value}
            if 'var' in fields:
                if len(fields) != len(value) or any(op != '=' or not isinstance(v, str) for k, op, v in value):
                    errors.append('Explicit check_variable fields must be unique scalar assignments')
                if set(fields) - {'var', 'value', 'compare', 'tooltip'}:
                    errors.append('Unknown explicit check_variable field')
                if 'value' not in fields or fields.get('compare', 'equals') not in COMPARISONS:
                    errors.append('Invalid explicit check_variable comparison')
            elif len(value) != 1 or value[0][1] not in ('=', '<', '>'):
                errors.append('Invalid short check_variable comparison')
    return errors


def main():
    errors, hashes = [], {}
    paths = []
    for folder in ('common/scripted_triggers', 'common/scripted_effects',
                   'common/scripted_localisation', 'common/scripted_diplomatic_actions',
                   'common/decisions', 'common/on_actions', 'events'):
        for path in sorted((ROOT / folder).glob('eon_*.txt')):
            paths.append(path)
    paths.append(ROOT / 'events/00_Influence_events.txt')
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        raw = path.read_bytes()
        hashes[relative] = hashlib.sha256(raw).hexdigest()
        for error in inspect(parser.ast(raw)):
            errors.append({'file': relative, 'error': error})
    groups = {}
    for path in sorted((ROOT / 'common/factions/rules/groups').glob('*.txt')):
        for key, op, value in parser.ast(path.read_bytes()):
            if isinstance(value, list):
                for name, op, item in parser.maybe(value, 'rules', []):
                    assert name == '__item__', ('Unexpected rule group item', path, name)
                    groups.setdefault(item, []).append(key)
    template = parser.one(parser.ast((ROOT / 'common/factions/templates/eon_defensive_alliance.txt').read_bytes()),
                          'eon_defensive_alliance_template')
    rules = parser.one(template, 'default_rules')
    for key, op, rule in rules:
        if len(groups.get(rule, [])) != 1:
            errors.append({'file': 'common/factions/templates/eon_defensive_alliance.txt',
                           'error': 'Default rule needs exactly one native rule group: ' + rule})
    # Known bad source must fail this guard, including direct numeric shorthand.
    assert inspect(parser.ast('x = { check_variable = { treasury >= 5 } }'))
    assert inspect(parser.ast('x = { has_political_power >= 10 }'))
    assert inspect(parser.ast('x = { has_opinion_modifier = { target = PREV modifier = no_diplomatic_ties } }'))
    assert inspect(parser.ast('x = { check_variable = { var < treasury value = 5 } }'))
    assert inspect(parser.ast('x = { check_variable = { var = treasury value = 5 value = 6 } }'))
    assert inspect(parser.ast('x = { check_variable = { var = { treasury = 1 } value = 5 } }'))
    assert not inspect(parser.ast('x = { check_variable = { var = treasury value = 5 compare = greater_than_or_equals } }'))
    print(json.dumps({'checks_passed': not errors, 'files_checked': len(hashes),
                      'errors': errors, 'source_sha256': hashes,
                      'native_compilation_proven': False,
                      'proof_scope': 'documented grammar and known native startup failures only'}, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
