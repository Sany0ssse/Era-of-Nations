"""Bind a native no-GoT history observation to the frozen source and process."""
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import json
import math
import re

from build_non_got_history_native_probe import sha


def parse_log(text, manifest):
    marker = re.escape(manifest['marker'])
    assert len(re.findall(marker+r' STARTUP native_no_got_missile_history', text)) == 1
    passed = re.findall(marker+r' PASS ([A-Za-z0-9_]+)', text)
    failed = re.findall(marker+r' FAIL ([A-Za-z0-9_]+)', text)
    assert Counter(passed + failed) == Counter(manifest['assertions']), 'Missing, duplicate or unexpected native assertions'
    assert all(count == 1 for count in Counter(passed + failed).values())
    summary = re.findall(marker+r' END passes=([0-9.]+) fails=([0-9.]+)', text)
    assert len(summary) == 1 and list(map(float, summary[0])) == [len(passed), len(failed)]
    assert not re.search(marker+r' (ABORT|DUPLICATE_EVENT)', text)
    expected = {tag.lower() + '_initial': tag for tag in manifest['observed_countries']}
    expected['observer_later'] = manifest['expected_native_start_tag']
    observations = {}
    for index, line in enumerate(text.splitlines(), 1):
        match = re.search(marker+r' OBS ([a-z_]+) ROOT=([^ ]+) THIS=([^ ]+) launchers=(-?\d+(?:\.\d+)?)', line)
        if not match:
            continue
        label, root, actor, value = match.groups()
        assert label in expected and label not in observations
        assert root == manifest['expected_native_start_tag'] and actor == expected[label]
        dates = re.findall(r'\[(\d{4}\.\d{2}\.\d{2}\.\d{2})\]', line)
        assert dates
        year, month, day, hour = map(int, dates[-1].split('.'))
        assert 0 <= hour <= 24
        instant = datetime(year, month, day) + timedelta(hours=hour)
        launchers = float(value)
        assert math.isfinite(launchers)
        observations[label] = dict(line_index=index, native_date=dates[-1], instant=instant, launchers=launchers)
    assert set(observations) == set(expected)
    later = observations['observer_later']
    elapsed = {}
    for tag in manifest['observed_countries']:
        first = observations[tag.lower() + '_initial']
        assert first['instant'] < datetime(2000, 1, 2)
        assert first['line_index'] < later['line_index']
        elapsed[tag] = (later['instant'] - first['instant']).total_seconds() / 3600
        assert elapsed[tag] >= manifest['minimum_total_native_hours']
        source_counter = manifest['history_rows'][tag]['launchers']
        if source_counter is not None:
            assert first['launchers'] == source_counter, (tag, first['launchers'], source_counter)
    for row in observations.values():
        row.pop('instant')
    return dict(passed=passed, failed=failed, observations=observations, elapsed_native_hours=elapsed)


def analyze(manifest_path, launch_path, game_log):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    launch = json.loads(launch_path.read_text(encoding='utf-8-sig'))
    assert manifest['schema'] == 1 and manifest['kind'] == 'native_no_got_missile_history'
    assert not manifest['preparation_only']
    source, fixture = Path(manifest['source_root']), Path(manifest['fixture_root'])
    assert launch['schema'] == 1 and isinstance(launch['pid'], int) and launch['pid'] > 0
    assert Path(launch['source_root']).resolve() == source.resolve()
    assert launch['manifest_sha256'] == sha(manifest_path)
    assert launch['embedded_fixture'] and Path(launch['embedded_root']).resolve() == source.resolve()
    assert launch['enabled_mods'] == manifest['expected_enabled_mods']
    user_dir = Path(launch['user_dir'])
    assert Path(launch['game_log']).resolve() == game_log.resolve() == (user_dir / 'logs/game.log').resolve()
    export = manifest['source_export_binding']
    assert export and sha(Path(export['path'])) == export['sha256'] == launch['source_export_receipt_sha256'].lower()
    start = json.loads(Path(launch['start_receipt']).read_text(encoding='utf-8-sig'))
    assert start['pid'] == launch['pid'] and start['exe'] == launch['exe']
    assert '-start_tag=' + manifest['expected_native_start_tag'] in start['arguments']
    assert start['process_start_utc'] == launch['process_start_utc']
    began = datetime.fromisoformat(start['process_start_utc'].replace('Z', '+00:00'))
    assert game_log.stat().st_ctime >= began.timestamp() - 3 and game_log.stat().st_mtime >= began.timestamp()
    assert sha(Path(launch['exe'])) == launch['exe_sha256'].lower()
    private_dlc = json.loads((user_dir / 'dlc_load.json').read_text(encoding='utf-8-sig'))
    assert private_dlc['enabled_mods'] == launch['enabled_mods']
    assert 'dlc/dlc043_gotterdammerung/dlc043.dlc' in private_dlc['disabled_dlcs']
    descriptor = (user_dir / 'mod/era_of_nations.mod').read_text(encoding='utf-8-sig')
    names = re.findall(r'^\s*name\s*=\s*"([^"]+)"', descriptor, re.M)
    paths = re.findall(r'^\s*path\s*=\s*"([^"]+)"', descriptor, re.M)
    assert len(names) == len(paths) == 1 and Path(paths[0]).resolve() == source.resolve()
    system = (user_dir / 'logs/system.log').read_text(encoding='utf-8-sig', errors='replace')
    assert re.findall(r'Active Mod Count: (\d+)', system) == ['1']
    assert Counter(re.findall(r'Active Mod: ([^\r\n]+)', system)) == Counter(names)
    for rel, digest in manifest['source_sha256'].items():
        assert sha(source / rel) == digest, ('Changed production source', rel)
    for rel, digest in manifest['fixture_sha256'].items():
        assert sha(fixture / 'mod' / rel) == sha(source / rel) == digest
        assert launch['embedded_source_sha256'].get(rel) == digest
    error_log = user_dir / 'logs/error.log'
    selected = [line for line in error_log.read_text(encoding='utf-8-sig', errors='replace').splitlines()
                if re.search(r'eon_private_non_got_missile_probe|eon_missile_non_got_history|non_got_missiles\.txt|'
                             r'MD_guided_missiles\.txt|script_enums\.txt|missile_projects\.txt|'
                             r'guided_missile_equipment_0|Invalid equipment type|Invalid air wing', line, re.I)]
    parsed = parse_log(game_log.read_text(encoding='utf-8-sig', errors='replace'), manifest)
    return dict(native_non_got_history_probe_passed=not parsed['failed'] and not selected,
                **parsed, native_assertions_passed=len(parsed['passed']), native_assertions_failed=len(parsed['failed']),
                selected_errors=selected, manifest_sha256=sha(manifest_path), launch_receipt_sha256=sha(launch_path),
                game_log_sha256=sha(game_log), error_log_sha256=sha(error_log), analyzer_sha256=sha(Path(__file__)),
                actual_production_ui_verified=False, actual_factory_output_verified=False,
                actual_human_gui_clicks_verified=False, actual_raid_launch_verified=False,
                save_load_verified=False, multiplayer_verified=False, limits=manifest['limits'])


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--manifest', type=Path, required=True)
    cli.add_argument('--launch-receipt', type=Path, required=True)
    cli.add_argument('--game-log', type=Path, required=True)
    args = cli.parse_args()
    result = analyze(args.manifest, args.launch_receipt, args.game_log)
    print(json.dumps(result, indent=2))
    if not result['native_non_got_history_probe_passed']:
        raise SystemExit(1)
