"""Inspect actual final rights shipments in both native settlement orders."""
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import importlib.util
import json
import math
import re


def parse_log(text, manifest):
    marker = re.escape(manifest['marker'])
    assert len(re.findall(marker+r' STARTUP final_resource_rights', text)) == 1
    passed = re.findall(marker+r' PASS ([A-Za-z0-9_]+)', text)
    failed = re.findall(marker+r' FAIL ([A-Za-z0-9_]+)', text)
    assert Counter(passed+failed) == Counter(manifest['assertions'])
    assert all(count == 1 for count in Counter(passed+failed).values())
    summary = re.findall(marker+r' END passes=([0-9.]+) fails=([0-9.]+)', text)
    assert len(summary) == 1 and list(map(float, summary[0])) == [len(passed), len(failed)]
    assert not re.search(marker+r' (ABORT|DUPLICATE_EVENT)', text)
    observations = {}
    for index, line in enumerate(text.splitlines(), 1):
        match = re.search(marker+r' OBS ([A-Za-z0-9_]+) ROOT=([^ ]+) THIS=([^ ]+) (.*)', line)
        if not match: continue
        label, root, actor, fields = match.groups()
        assert label in manifest['observation_labels'] and label not in observations
        assert manifest['expected_observation_frames'][label] == {'root': root, 'actor': actor}
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
    order_checks = {}
    for order in ('owner_first', 'recipient_first'):
        before = observations[order+'_before_'+('owner' if order == 'owner_first' else 'recipient')+'_settlement']
        recipient = observations[order+'_after_recipient_settlement']
        owner = observations[order+'_after_owner_settlement']
        same_hour = before['instant'] == recipient['instant'] == owner['instant']
        expected = before['recipient_delivery_before']
        final_reserve = before['final_reserve_before']
        recipient_credit = math.isclose(recipient['raw'], expected, abs_tol=0.02, rel_tol=1e-6) and expected > 0
        physical = all(value['state_reserve'] == value['state_flow'] == 0 and
                       math.isclose(value['state_extracted'], final_reserve, abs_tol=0.02, rel_tol=1e-6)
                       for value in (recipient, owner)) and final_reserve > 0
        rights_snapshot = recipient['state_recipient'] > 0 and owner['state_recipient'] == recipient['state_recipient']
        delivery_ceiling = final_reserve+(owner['imported']+recipient['imported'])*100
        no_extra_mass = owner['raw']+recipient['raw'] <= delivery_ceiling+0.02
        order_checks[order] = {'same_native_hour': same_hour, 'expected_recipient_credit_kg': expected,
                              'actual_recipient_credit_kg': recipient['raw'], 'recipient_credit_preserved': recipient_credit,
                              'single_final_extraction_verified': physical, 'recipient_snapshot_preserved': rights_snapshot,
                              'credited_mass_within_extraction_and_imports': no_extra_mass,
                              'accepted': same_hour and recipient_credit and physical and rights_snapshot and no_extra_mass}
    for value in observations.values(): value.pop('instant')
    return {'passed': passed, 'failed': failed, 'observations': observations, 'elapsed_native_hours': elapsed,
            'final_rights_order_checks': order_checks,
            'both_native_final_rights_orders_passed': all(value['accepted'] for value in order_checks.values())}


def analyze(manifest_path, launch_path, game_log):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    assert manifest['kind'] == 'native_final_uranium_resource_rights'
    path = Path(__file__).with_name('analyze_native_probe.py')
    spec = importlib.util.spec_from_file_location('uranium_final_rights_receipt_verifier', path)
    evidence = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evidence)
    evidence.parse_log = parse_log
    result = evidence.analyze(manifest_path, launch_path, game_log)
    receipt_pass = result.pop('native_resource_trade_prototype_passed')
    result['native_final_rights_cache_orders_verified'] = receipt_pass and result['both_native_final_rights_orders_passed']
    result['receipt_verifier_sha256'] = evidence.sha(path)
    result['analyzer_sha256'] = evidence.sha(Path(__file__))
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--manifest', type=Path, required=True)
    cli.add_argument('--launch-receipt', type=Path, required=True)
    cli.add_argument('--game-log', type=Path, required=True)
    args = cli.parse_args()
    result = analyze(args.manifest, args.launch_receipt, args.game_log)
    print(json.dumps(result, indent=2))
    if not result['native_final_rights_cache_orders_verified']: raise SystemExit(1)


if __name__ == '__main__': main()
