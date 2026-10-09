"""Accept staged enrichment only with native waits, checkpoints and source bindings."""
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import importlib.util
import json
import math
import re

from build_native_probe import load_parser, sha
from build_core_native_probe import canonical
from build_enrichment_checkpoint_native_probe import NS


def parse_log(text, manifest):
    marker = re.escape(manifest['marker'])
    assert len(re.findall(marker+r' STARTUP staged_enrichment', text)) == 1
    passed = re.findall(marker+r' PASS ([A-Za-z0-9_]+)', text)
    failed = re.findall(marker+r' FAIL ([A-Za-z0-9_]+)', text)
    assert Counter(passed+failed) == Counter(manifest['assertions'])
    assert all(count == 1 for count in Counter(passed+failed).values())
    summary = re.findall(marker+r' END passes=([0-9.]+) fails=([0-9.]+)', text)
    assert len(summary) == 1 and list(map(float, summary[0])) == [len(passed), len(failed)]
    assert not re.search(marker+r' (ABORT|DUPLICATE_EVENT)', text)
    checkpoints = re.findall(marker+r' CHECKPOINT (BEFORE|AFTER) ([A-Za-z0-9_]+) ROOT=([^ ]+) THIS=([^\s]+)', text)
    expected = [(position, name, 'GER', 'GER') for name in manifest['checkpoints'] for position in ('BEFORE', 'AFTER')]
    assert checkpoints == expected, 'Missing, duplicate, unordered or wrong-frame checkpoint'
    observations = {}
    for index, line in enumerate(text.splitlines(), 1):
        match = re.search(marker+r' OBS ([A-Za-z0-9_]+) ROOT=([^ ]+) THIS=([^ ]+) (.*)', line)
        if not match: continue
        label, root, actor, fields = match.groups()
        assert label in manifest['observation_labels'] and label not in observations
        assert root == actor == 'GER'
        dates = re.findall(r'\[(\d{4}\.\d{2}\.\d{2}\.\d{2})\]', line)
        assert dates
        year, month, day, hour = map(int, dates[-1].split('.'))
        assert 0 <= hour <= 24
        instant = datetime(year, month, day)+timedelta(hours=hour)
        pairs = re.findall(r'([a-z_]+)=(-?\d+(?:\.\d+)?)', fields)
        assert Counter(key for key, value in pairs) == Counter(list(manifest['observation_fields']))
        values = {key: float(value) for key, value in pairs}
        assert all(math.isfinite(value) for value in values.values())
        observations[label] = {'line_index': index, 'native_date': dates[-1], 'instant': instant, **values}
    assert set(observations) == set(manifest['observation_labels'])
    ordered = [observations[label] for label in manifest['observation_labels']]
    assert all(a['line_index'] < b['line_index'] and a['instant'] <= b['instant'] for a, b in zip(ordered, ordered[1:]))
    elapsed = (ordered[-1]['instant']-ordered[0]['instant']).total_seconds()/3600
    assert elapsed >= manifest['minimum_total_native_hours']
    for prefix in ('triple', 'single'):
        assert observations[prefix+'_after_native_wait']['instant'] > observations['after_'+prefix+'_call']['instant'], 'No actual native activation wait'
    details = {}
    if manifest.get('enrichment_evidence_version', 1) == 1:
        expected_money = {'before_triple': (100, 0, 0, 0), 'after_triple_call': (25, 0, 3, 75),
                          'triple_after_native_wait': (25, 0, 3, 75), 'after_timeout': (25, 3, 0, 0),
                          'after_single_call': (75, 3, 1, 25), 'single_after_native_wait': (75, 3, 1, 25),
                          'after_cancel': (100, 3, 0, 0), 'final': (100, 3, 0, 0)}
        for label, expected_values in expected_money.items():
            actual = observations[label]
            assert all(math.isclose(actual[key], value, abs_tol=0.02, rel_tol=1e-6)
                       for key, value in zip(('treasury', 'facilities', 'count', 'escrow'), expected_values)), (label, actual, expected_values)
    else:
        assert manifest['enrichment_evidence_version'] == 2
        near = lambda a, b: math.isclose(a, b, abs_tol=0.02, rel_tol=1e-6)
        expected_projects = [(0, 0, 0, 0), (0, 3, 75, 1), (0, 3, 75, 1), (3, 0, 0, 0),
                             (3, 1, 25, 1), (3, 1, 25, 1), (3, 0, 0, 0), (3, 0, 0, 0)]
        for value, expected_values in zip(ordered, expected_projects):
            assert all(near(value[key], expected) for key, expected in zip(('facilities', 'count', 'escrow', 'paid'), expected_values))
            assert all(value[key] in (0, 1) for key in ('paid', 'active', 'allowed_no_active', 'allowed_yes_active'))
        actual_deltas = {'triple_charge': observations['before_triple']['treasury']-observations['after_triple_call']['treasury'],
                         'timeout_charge': observations['after_timeout']['treasury']-observations['triple_after_native_wait']['treasury'],
                         'single_charge': 100-observations['after_single_call']['treasury'],
                         'cancel_refund': observations['after_cancel']['treasury']-observations['single_after_native_wait']['treasury']}
        expected_deltas = {'triple_charge': 75, 'timeout_charge': 0, 'single_charge': 25, 'cancel_refund': 25}
        for key, expected in expected_deltas.items(): assert near(actual_deltas[key], expected), (key, actual_deltas[key], expected)
        for label, expected in (('after_triple_call', 75), ('after_timeout', 0), ('after_single_call', 25), ('after_cancel', 25)):
            assert near(observations[label]['money_delta'], expected), ('Incorrect callback-local delta', label)
        for prefix in ('triple', 'single'):
            label = prefix+'_native_mission_active_after_wait'
            if label in passed: assert observations[prefix+'_after_native_wait']['active'] == 1
            if label in failed: assert observations[prefix+'_after_native_wait']['active'] == 0
        yes_active = observations['triple_after_native_wait']['allowed_yes_active']
        if 'private_allowed_yes_native_mission_registered' in passed: assert yes_active == 1
        if 'private_allowed_yes_native_mission_registered' in failed: assert yes_active == 0
        details = {'callback_local_treasury_deltas': actual_deltas,
                   'native_enrichment_mission_activation_observed': all(observations[prefix+'_after_native_wait']['active'] == 1 for prefix in ('triple', 'single')),
                   'private_loadtime_mission_controls': {'allowed_no_active': observations['triple_after_native_wait']['allowed_no_active'], 'allowed_yes_active': yes_active},
                   'unrelated_inter_event_treasury_changes': {'triple_wait': observations['triple_after_native_wait']['treasury']-observations['after_triple_call']['treasury'],
                                                             'single_wait': observations['single_after_native_wait']['treasury']-observations['after_single_call']['treasury'],
                                                             'final_wait': observations['final']['treasury']-observations['after_cancel']['treasury']}}
    for value in observations.values(): value.pop('instant')
    return {'passed': passed, 'failed': failed, 'observations': observations, 'elapsed_native_hours': elapsed,
            'all_source_checkpoint_pairs_seen': True, **details}


def verify_bindings(source, fixture, manifest):
    parser = load_parser()
    aliases = parser.ast((fixture/'mod'/'common/scripted_effects'/f'{NS}_effects.txt').read_bytes())
    assert len(manifest['callback_bindings']) == 4
    for binding in manifest['callback_bindings']:
        nodes = parser.ast((source/binding['source_path']).read_bytes())
        for part in binding['selector']: nodes = parser.one(nodes, part)
        assert canonical(nodes) == binding['source_ast_sha256']
        assert canonical(parser.one(aliases, binding['alias'])) == binding['source_ast_sha256']
    if manifest.get('enrichment_evidence_version', 1) == 2:
        original = parser.one(parser.one(parser.ast((source/'common/decisions/generic.txt').read_bytes()), 'GENERIC_economic_category'), 'energy_building_enrichment_facilities')
        assert canonical(original) == manifest['loadtime_control_source_ast_sha256']
        controls = parser.one(parser.ast((fixture/'mod/common/decisions'/f'{NS}_loadtime_controls.txt').read_bytes()), 'GENERIC_economic_category')
        assert len(controls) == 2
        for allowed in ('no', 'yes'):
            expected = [(key, op, parser.ast('always = '+allowed) if key == 'allowed' else value) for key, op, value in original]
            expected += parser.ast('activation = { always = no } ai_will_do = { factor = 0 }')
            assert parser.one(controls, NS+'_allowed_'+allowed) == expected


def analyze(manifest_path, launch_path, game_log):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    assert manifest['kind'] == 'native_staged_uranium_enrichment'
    verify_bindings(Path(manifest['source_root']), Path(manifest['fixture_root']), manifest)
    path = Path(__file__).with_name('analyze_native_probe.py')
    spec = importlib.util.spec_from_file_location('uranium_enrichment_receipt_verifier', path)
    evidence = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evidence)
    evidence.parse_log = parse_log
    result = evidence.analyze(manifest_path, launch_path, game_log)
    result['native_staged_enrichment_verified'] = result.pop('native_resource_trade_prototype_passed')
    result['receipt_verifier_sha256'] = sha(path)
    result['analyzer_sha256'] = sha(Path(__file__))
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--manifest', type=Path, required=True)
    cli.add_argument('--launch-receipt', type=Path, required=True)
    cli.add_argument('--game-log', type=Path, required=True)
    args = cli.parse_args()
    result = analyze(args.manifest, args.launch_receipt, args.game_log)
    print(json.dumps(result, indent=2))
    if not result['native_staged_enrichment_verified']: raise SystemExit(1)


if __name__ == '__main__': main()
