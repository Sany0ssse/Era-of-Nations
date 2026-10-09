"""Classify paired native oil/uranium rights counters with strict run receipts."""
from pathlib import Path
import argparse
import importlib.util
import json
import math
import re

from build_native_probe import sha


def parse_log(text, manifest):
    # The family has the same strict event/observation grammar as the ordinary
    # rights verifier. Reuse its structural parser without its positive-delivery
    # assumption: this diagnostic must retain valid recorded zero observations.
    marker = re.escape(manifest['marker'])
    from collections import Counter
    from datetime import datetime, timedelta
    assert len(re.findall(marker+r' STARTUP coastal_resource_rights', text)) == 1
    passed = re.findall(marker+r' PASS ([A-Za-z0-9_]+)', text)
    failed = re.findall(marker+r' FAIL ([A-Za-z0-9_]+)', text)
    assert Counter(passed+failed) == Counter(manifest['assertions'])
    assert all(n == 1 for n in Counter(passed+failed).values())
    end = re.findall(marker+r' END passes=([0-9.]+) fails=([0-9.]+)', text)
    assert len(end) == 1 and list(map(float, end[0])) == [len(passed), len(failed)]
    assert not re.search(marker+r' (ABORT|DUPLICATE_EVENT)', text)
    observations = {}
    for index, line in enumerate(text.splitlines(), 1):
        found = re.search(marker+r' OBS ([A-Za-z0-9_]+) ROOT=([^ ]+) THIS=([^ ]+) (.*)', line)
        if not found: continue
        label, root, actor, raw = found.groups()
        assert label in manifest['observation_labels'] and label not in observations
        assert root == manifest['expected_observation_roots'][label]
        assert actor == manifest['expected_observation_actors'][label]
        dates = re.findall(r'\[(\d{4}\.\d{2}\.\d{2}\.\d{2})\]', line)
        assert dates
        year, month, day, hour = map(int, dates[-1].split('.'))
        assert 0 <= hour <= 24
        pairs = re.findall(r'([a-z_]+)=(-?\d+(?:\.\d+)?)', raw)
        assert Counter(k for k, v in pairs) == Counter(list(manifest['observation_fields']))
        values = {k: float(v) for k, v in pairs}
        assert all(math.isfinite(v) for v in values.values())
        observations[label] = {'line': index, 'native_date': dates[-1], 'instant': datetime(year, month, day)+timedelta(hours=hour), **values}
    assert set(observations) == set(manifest['observation_labels'])
    ordered = [observations[label] for label in manifest['observation_labels']]
    assert all(a['line'] < b['line'] and a['instant'] <= b['instant'] for a, b in zip(ordered, ordered[1:]))
    elapsed = (ordered[-1]['instant']-ordered[0]['instant']).total_seconds()/3600
    assert elapsed >= manifest['minimum_total_native_hours']
    before, after = observations['receiver_before'], observations['receiver_after']
    deltas = {resource: {counter: after[resource+'_'+counter]-before[resource+'_'+counter]
                         for counter in ('balance', 'produced', 'imported', 'exported', 'consumed')}
              for resource in ('uranium', 'oil')}
    positive = {resource: deltas[resource]['produced'] > 0 or deltas[resource]['imported'] > 0 for resource in deltas}
    expected = max(0, observations['receiver_before_settlement']['uranium_balance'])*100
    actual = observations['receiver_after_settlement']['raw']
    matched = math.isclose(actual, expected, abs_tol=.02, rel_tol=1e-6)
    for value in observations.values(): value.pop('instant')
    return {'passed': passed, 'failed': failed, 'observations': observations, 'elapsed_native_hours': elapsed,
            'native_paired_resource_counter_deltas': deltas, 'native_counter_positive': positive,
            'paired_control_classification': 'both_native_counters_increase' if all(positive.values()) else
                'uranium_counter_absent_oil_positive' if positive['oil'] and not positive['uranium'] else
                'both_native_counters_absent' if not any(positive.values()) else 'oil_control_absent_uranium_positive',
            'expected_native_material_delivery_kg': expected, 'actual_public_material_credit_kg': actual,
            'public_material_credit_matches_native_balance': matched,
            'native_uranium_positive_delivery_observed': after['uranium_balance'] > 0,
            'legal_rights_inferred_as_delivery': False}


def analyze(manifest_path, launch_path, game_log):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    assert manifest['kind'] == 'native_uranium_rights_connectivity_control'
    path = Path(__file__).with_name('analyze_native_probe.py')
    spec = importlib.util.spec_from_file_location('uranium_connectivity_receipt_verifier', path)
    evidence = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evidence)
    evidence.parse_log = parse_log
    result = evidence.analyze(manifest_path, launch_path, game_log)
    result['native_rights_connectivity_control_recorded'] = result.pop('native_resource_trade_prototype_passed')
    result['native_uranium_rights_delivery_verified'] = (result['native_rights_connectivity_control_recorded'] and
        result['native_counter_positive']['uranium'] and result['native_uranium_positive_delivery_observed'] and
        result['public_material_credit_matches_native_balance'])
    result['receipt_verifier_sha256'], result['analyzer_sha256'] = sha(path), sha(Path(__file__))
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--manifest', type=Path, required=True)
    cli.add_argument('--launch-receipt', type=Path, required=True)
    cli.add_argument('--game-log', type=Path, required=True)
    args = cli.parse_args()
    result = analyze(args.manifest, args.launch_receipt, args.game_log)
    print(json.dumps(result, indent=2))
    if not result['native_rights_connectivity_control_recorded']: raise SystemExit(1)


if __name__ == '__main__': main()
