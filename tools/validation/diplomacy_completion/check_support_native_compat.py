"""Prove narrow support syntax repairs preserve every other parsed statement."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = 'c1420b108dee2d129018951c9ba73c1f6bfc4360'
spec = importlib.util.spec_from_file_location(
    'eon_compat_ast', ROOT / 'tools/validation/diplomacy_package_03/_support.py')
parser = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = parser
spec.loader.exec_module(parser)
OPERATORS = {'equals': '=', 'not_equals': '!=', 'less_than': '<',
             'less_than_or_equals': '<=', 'greater_than': '>',
             'greater_than_or_equals': '>='}
NAMES = ('advisers', 'aid', 'ammo', 'services', 'foreign_cash', 'defensive_alliance',
         'consultation', 'defence_formation', 'foreign_equipment')
PATHS = [f'common/scripted_triggers/eon_{name}_triggers.txt' for name in NAMES]
PATHS += [f'common/scripted_effects/eon_{name}_effects.txt'
          for name in ('consultation', 'advisers', 'services')]
PATHS.append('events/00_Influence_events.txt')


def normalize(nodes):
    result = []
    for key, op, value in nodes:
        if key == 'check_variable' and isinstance(value, list) and any(k == 'var' for k, _, _ in value):
            fields = {k: v for k, _, v in value}
            value = [(fields['var'], OPERATORS[fields.get('compare', 'equals')], fields['value'])]
            if value[0][0] == 'global.threat':
                key, op, value = 'threat', value[0][1], value[0][2]
        if key in ('has_government', 'has_war_with', 'tag') and isinstance(value, str) and value.startswith('var:eon_'):
            value = value[4:]
        if isinstance(value, list):
            value = normalize(value)
        result.append((key, op, value))
    return result


def walk(nodes):
    for node in nodes:
        yield node
        if isinstance(node[2], list):
            yield from walk(node[2])


def main():
    checks, hashes, conversions = 0, {}, 0
    for relative in PATHS:
        before = subprocess.check_output(['git', 'show', BASELINE + ':' + relative], cwd=ROOT)
        after = (ROOT / relative).read_bytes()
        old, current = parser.ast(before), parser.ast(after)
        assert normalize(current) == normalize(old), ('Other behavior changed', relative)
        assert before.startswith(b'\xef\xbb\xbf') == after.startswith(b'\xef\xbb\xbf')
        assert before.count(b'\r\n') == after.count(b'\r\n'), ('Changed existing CRLF', relative)
        assert before.count(b'\n') == after.count(b'\n'), ('Changed existing line count', relative)
        hashes[relative] = hashlib.sha256(after).hexdigest()
        for key, op, value in walk(current):
            if key != 'check_variable' or not isinstance(value, list) or not any(k == 'var' for k, _, _ in value):
                continue
            fields = {k: v for k, _, v in value}
            mode = fields.get('compare', 'equals')
            operator = OPERATORS[mode]
            assert mode in ('greater_than_or_equals', 'less_than_or_equals')
            threshold = fields['value']
            try:
                actual_thresholds = [float(threshold)]
            except ValueError:
                actual_thresholds = [-1000000, 0, .001, 5, 1000000]
            for threshold in actual_thresholds:
                for left in (threshold - .001, threshold, threshold + .001):
                    expected = left >= threshold if mode == 'greater_than_or_equals' else left <= threshold
                    assert parser.compare(left, operator, threshold) == expected
                    checks += 1
            conversions += 1
    # Resolve a provider by identity, not by comparing an ideology to a variable name.
    advisers = parser.ast((ROOT / 'common/scripted_triggers/eon_advisers_triggers.txt').read_bytes())
    services = parser.ast((ROOT / 'common/scripted_triggers/eon_services_triggers.txt').read_bytes())
    for nodes, provider in ((advisers, 'eon_advisers_policy_provider'), (services, 'eon_services_policy_provider')):
        assert ('has_government', '=', 'var:' + provider) in list(walk(nodes))
        actual = [n for n in walk(nodes) if n[0] == 'has_government' and n[2] == 'var:' + provider]
        assert len(actual) == 1
        for recipient, donor in (('democratic', 'democratic'), ('democratic', 'communism')):
            model = parser.Model(current=1)
            model.countries[1].government = recipient
            model.countries[2].government = donor
            model.countries[1].variables[provider] = 2
            assert model.trigger(actual, [1]) == (recipient == donor)
            checks += 1
    print(json.dumps({'checks_passed': True, 'files_checked': len(hashes),
                      'inclusive_comparisons_checked': conversions,
                      'boundary_and_identity_cases': checks,
                      'baseline_commit': BASELINE,
                      'source_sha256': hashes,
                      'native_runtime_proven': False,
                      'proof_scope': 'full parsed statement equivalence and exact comparison boundaries; native load still required'}, indent=2))


if __name__ == '__main__':
    main()
