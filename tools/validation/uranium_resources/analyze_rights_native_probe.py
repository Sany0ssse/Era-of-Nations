"""Inspect uranium rights classification and material credit with strict receipts."""
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
    assert len(re.findall(marker+r' STARTUP native_resource_rights', text)) == 1
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
        assert root == manifest['expected_observation_roots'][label] and actor == manifest['expected_observation_actors'][label]
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
    before, after = observations['nep_before_rights'], observations['nep_after_rights']
    assert after['balance'] > 0 and after['balance'] > before['balance'], 'Rights did not increase recipient native delivery'
    classifier = {key+'_delta': after[key]-before[key] for key in ('balance', 'produced', 'imported', 'exported')}
    expected = observations['nep_before_material_settlement']['balance']*100
    actual = observations['nep_after_material_settlement']['raw']
    for value in observations.values(): value.pop('instant')
    return {'passed': passed, 'failed': failed, 'observations': observations, 'elapsed_native_hours': elapsed,
            'native_receiver_counter_changes': classifier, 'expected_native_rights_delivery_kg': expected,
            'actual_rights_material_credit_kg': actual,
            'native_material_credit_matches_rights_balance': math.isclose(actual, expected, abs_tol=0.02, rel_tol=1e-6)}


def analyze(manifest_path, launch_path, game_log):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    assert manifest['kind'] == 'native_uranium_resource_rights'
    # Reuse the existing strict process/launcher/export/hash verifier in an
    # isolated module instance; only its log parser is replaced for this family.
    path = Path(__file__).with_name('analyze_native_probe.py')
    spec = importlib.util.spec_from_file_location('uranium_rights_receipt_verifier', path)
    evidence = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evidence)
    evidence.parse_log = parse_log
    result = evidence.analyze(manifest_path, launch_path, game_log)
    result['native_uranium_rights_support_verified'] = result.pop('native_resource_trade_prototype_passed')
    result['native_source_rights_material_credit_verified'] = (
        result['native_uranium_rights_support_verified'] and result['native_material_credit_matches_rights_balance'])
    result['receipt_verifier_sha256'] = evidence.sha(path)
    result['analyzer_sha256'] = evidence.sha(Path(__file__))
    result['final_deposit_two_country_cache_verified'] = False
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--manifest', type=Path, required=True)
    cli.add_argument('--launch-receipt', type=Path, required=True)
    cli.add_argument('--game-log', type=Path, required=True)
    args = cli.parse_args()
    result = analyze(args.manifest, args.launch_receipt, args.game_log)
    print(json.dumps(result, indent=2))
    if not result['native_source_rights_material_credit_verified']: raise SystemExit(1)


if __name__ == '__main__': main()
