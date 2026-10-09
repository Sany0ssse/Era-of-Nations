"""Accept a recorded native uranium prototype only with matching launch evidence."""
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import hashlib
import json
import re


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_log(text, manifest):
    marker = re.escape(manifest['marker'])
    startup = re.findall(marker+r' STARTUP native_resource_trade_prototype', text)
    passed = re.findall(marker+r' PASS ([A-Za-z0-9_]+)', text)
    failed = re.findall(marker+r' FAIL ([A-Za-z0-9_]+)', text)
    actual, expected = Counter(passed+failed), Counter(manifest['assertions'])
    assert len(startup) == 1, 'Missing/duplicate startup marker'
    assert actual == expected, ('Missing/duplicate/unexpected assertions', actual, expected)
    assert all(count == 1 for count in actual.values())
    summary = re.findall(marker+r' END passes=([0-9.]+) fails=([0-9.]+)', text)
    assert len(summary) == 1 and list(map(float, summary[0])) == [len(passed), len(failed)]
    assert not re.search(marker+r' (ABORT|DUPLICATE_EVENT)', text), 'Aborted/duplicate native callback'
    observations = {}
    for line_index, line in enumerate(text.splitlines(), 1):
        match = re.search(marker+r' OBS ([A-Za-z0-9_]+) ROOT=([^ ]+) THIS=([^ ]+) (.*)', line)
        if not match:
            continue
        label, root, this, fields = match.groups()
        assert label in manifest['observation_labels'] and label not in observations
        actor = manifest['expected_observation_actors'][label]
        # ROOT remains the event owner USA inside a nested CAN observation.
        assert root == 'USA' and this == actor, ('Wrong native scope', label, root, this)
        stamp = re.findall(r'\[(\d{4}\.\d{2}\.\d{2}\.\d{2})\]', line)
        assert stamp, ('Missing native date', label)
        year, month, day, hour = map(int, stamp[-1].split('.'))
        assert 0 <= hour <= 24
        instant = datetime(year, month, day)+timedelta(hours=hour)
        values = dict(re.findall(r'(balance|produced|imported|exported|consumed)=(-?\d+(?:\.\d+)?)', fields))
        assert set(values) == {'balance', 'produced', 'imported', 'exported', 'consumed'}
        observations[label] = {'line_index': line_index, 'native_date': stamp[-1],
                               'instant': instant, 'actor': actor,
                               **{key: float(value) for key, value in values.items()}}
    assert set(observations) == set(manifest['observation_labels'])
    ordered = [observations[label] for label in manifest['observation_labels']]
    assert all(a['line_index'] < b['line_index'] and a['instant'] <= b['instant'] for a, b in zip(ordered, ordered[1:]))
    elapsed = (ordered[-1]['instant']-ordered[0]['instant']).total_seconds()/3600
    assert elapsed >= manifest['minimum_total_native_hours'], ('Insufficient native waiting', elapsed)
    before, first = observations['usa_before_import'], observations['usa_after_import_8']
    producer_before = observations['can_baseline']
    producer_after = observations['can_after_resource_added']
    assert producer_after['produced'] > producer_before['produced'], 'Canadian extraction did not rise'
    assert producer_after['exported'] > 0, 'No Canadian uranium made available for export'
    assert first['imported']-before['imported'] >= 8, 'Imported amount8 not delivered'
    assert first['balance']-before['balance'] >= 8, 'Import did not increase domestic balance'
    for value in observations.values():
        value.pop('instant')
    return {'passed': passed, 'failed': failed, 'observations': observations,
            'elapsed_native_hours': elapsed,
            'repeated_import_8_delta': observations['usa_after_repeat_import_8']['imported']-first['imported'],
            'expanded_import_16_delta': observations['usa_after_import_16']['imported']-observations['usa_after_repeat_import_8']['imported'],
            'native_consumed_after_scripted_import': first['consumed']}


def analyze(manifest_path, launch_path, game_log):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    launch = json.loads(launch_path.read_text(encoding='utf-8-sig'))
    assert manifest['schema'] == 1 and not manifest['preparation_only']
    source, fixture = Path(manifest['source_root']), Path(manifest['fixture_root'])
    assert launch['schema'] == 1 and isinstance(launch['pid'], int) and launch['pid'] > 0
    assert Path(launch['source_root']).resolve() == source.resolve()
    assert launch['manifest_sha256'] == sha(manifest_path)
    assert launch['embedded_fixture'] and Path(launch['embedded_root']).resolve() == source.resolve()
    assert launch['enabled_mods'] == manifest['expected_enabled_mods']
    assert Path(launch['game_log']).resolve() == game_log.resolve()
    user_dir = Path(launch['user_dir'])
    assert game_log.resolve() == (user_dir/'logs/game.log').resolve()
    export = manifest['source_export_binding']
    assert export and sha(Path(export['path'])) == export['sha256'] == launch['source_export_receipt_sha256']
    start = json.loads(Path(launch['start_receipt']).read_text(encoding='utf-8-sig'))
    assert start['pid'] == launch['pid'] and start['exe'] == launch['exe']
    assert '-start_tag='+manifest['expected_native_start_tag'] in start['arguments']
    assert start['process_start_utc'] == launch['process_start_utc']
    started = datetime.fromisoformat(start['process_start_utc'].replace('Z', '+00:00'))
    assert game_log.stat().st_ctime >= started.timestamp()-3 and game_log.stat().st_mtime >= started.timestamp()
    assert sha(Path(launch['exe'])) == launch['exe_sha256'].lower()
    assert json.loads((user_dir/'dlc_load.json').read_text(encoding='utf-8-sig'))['enabled_mods'] == launch['enabled_mods']
    descriptor = (user_dir/'mod/era_of_nations.mod').read_text(encoding='utf-8-sig')
    names = re.findall(r'^\s*name\s*=\s*"([^"]+)"', descriptor, re.M)
    paths = re.findall(r'^\s*path\s*=\s*"([^"]+)"', descriptor, re.M)
    assert len(names) == len(paths) == 1 and Path(paths[0]).resolve() == source.resolve()
    system = (user_dir/'logs/system.log').read_text(encoding='utf-8-sig', errors='replace')
    assert re.findall(r'Active Mod Count: (\d+)', system) == ['1']
    assert Counter(re.findall(r'Active Mod: ([^\r\n]+)', system)) == Counter(names)
    for rel, digest in manifest['source_sha256'].items():
        assert sha(source/rel) == digest, ('Changed source dependency', rel)
    for rel, digest in manifest['fixture_sha256'].items():
        assert sha(fixture/'mod'/rel) == sha(source/rel) == digest, ('Changed embedded fixture', rel)
    assert all(launch['embedded_source_sha256'].get(rel) == digest
               for rel, digest in manifest['fixture_sha256'].items())
    docs = Path(manifest['installed_documentation_root'])
    for rel, digest in manifest['installed_documentation_sha256'].items():
        assert sha(docs/rel) == digest
    error_log = user_dir/'logs/error.log'
    errors = error_log.read_text(encoding='utf-8-sig', errors='replace')
    selected = [line for line in errors.splitlines() if re.search(
        r'uranium|eon_private_uranium_probe|unknown resource|invalid resource|create_import', line, re.I)]
    parsed = parse_log(game_log.read_text(encoding='utf-8-sig', errors='replace'), manifest)
    accepted = not parsed['failed'] and not selected
    return {'native_resource_trade_prototype_passed': accepted,
            'native_assertions_passed': len(parsed['passed']), 'native_assertions_failed': len(parsed['failed']),
            **parsed, 'selected_errors': selected, 'manifest_sha256': sha(manifest_path),
            'launch_receipt_sha256': sha(launch_path), 'game_log_sha256': sha(game_log),
            'error_log_sha256': sha(error_log), 'analyzer_sha256': sha(Path(__file__)),
            'final_physical_uranium_model_tested': False,
            'actual_human_gui_clicks_verified': False, 'save_load_verified': False,
            'native_ai_purchasing_verified': False, 'multiplayer_verified': False,
            'limits': manifest['limits']}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--manifest', type=Path, required=True)
    cli.add_argument('--launch-receipt', type=Path, required=True)
    cli.add_argument('--game-log', type=Path, required=True)
    args = cli.parse_args()
    result = analyze(args.manifest, args.launch_receipt, args.game_log)
    print(json.dumps(result, indent=2))
    if not result['native_resource_trade_prototype_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
