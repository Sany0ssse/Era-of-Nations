"""Bind actual native missile counter logs to the private source and process."""
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import json
import math
import re

from build_native_probe import sha


def parse_log(text, manifest):
    marker = re.escape(manifest['marker'])
    assert len(re.findall(marker+r' STARTUP native_missile_inventory_deployment', text)) == 1
    passed = re.findall(marker+r' PASS ([A-Za-z0-9_]+)', text)
    failed = re.findall(marker+r' FAIL ([A-Za-z0-9_]+)', text)
    assert Counter(passed+failed) == Counter(manifest['assertions']), 'Missing/duplicate/unexpected assertions'
    assert all(count == 1 for count in Counter(passed+failed).values())
    summary = re.findall(marker+r' END passes=([0-9.]+) fails=([0-9.]+)', text)
    assert len(summary) == 1 and list(map(float, summary[0])) == [len(passed), len(failed)]
    assert not re.search(marker+r' (ABORT|DUPLICATE_EVENT)', text)

    def native_record(index, line):
        dates = re.findall(r'\[(\d{4}\.\d{2}\.\d{2}\.\d{2})\]', line)
        assert dates, 'Missing native date'
        year, month, day, hour = map(int, dates[-1].split('.'))
        assert 0 <= hour <= 24
        try:
            instant = datetime(year, month, day)+timedelta(hours=hour)
        except ValueError as error:
            raise AssertionError('Invalid native date') from error
        return {'line_index': index, 'native_date': dates[-1], 'instant': instant}

    assertion_records, startup_records, summary_records = {}, [], []
    for index, line in enumerate(text.splitlines(), 1):
        result = re.search(marker+r' (PASS|FAIL) ([A-Za-z0-9_]+)', line)
        if result:
            verdict, label = result.groups()
            assertion_records[label] = {**native_record(index, line), 'verdict': verdict}
        if re.search(marker+r' STARTUP native_missile_inventory_deployment', line):
            startup_records.append(native_record(index, line))
        if re.search(marker+r' END passes=([0-9.]+) fails=([0-9.]+)', line):
            summary_records.append(native_record(index, line))
    assert len(startup_records) == len(summary_records) == 1
    startup, ending = startup_records[0], summary_records[0]
    observed = {}
    for index, line in enumerate(text.splitlines(), 1):
        match = re.search(marker+r' OBS ([A-Za-z0-9_]+) ROOT=([^ ]+) THIS=([^ ]+) (.*)', line)
        if not match:
            continue
        label, root, actor, tail = match.groups()
        assert label in manifest['observation_labels'] and label not in observed
        assert root == actor == manifest['expected_observation_actors'][label]
        matches = [re.fullmatch(r'([a-z_]+)=(-?\d+(?:\.\d+)?)', token) for token in tail.split()]
        assert all(matches), 'Malformed observation field'
        pairs = [match.groups() for match in matches]
        assert Counter(key for key, value in pairs) == Counter(list(manifest['observation_fields']))
        values = {key: float(value) for key, value in pairs}
        assert all(math.isfinite(value) and value >= 0 for value in values.values()), 'Invalid inventory counter'
        observed[label] = {**native_record(index, line), **values}
    assert set(observed) == set(manifest['observation_labels'])
    records = sorted([startup, ending, *assertion_records.values(), *observed.values()], key=lambda row: row['line_index'])
    assert records[0] is startup and records[-1] is ending, 'Evidence outside startup/summary frame'
    assert all(a['instant'] <= b['instant'] for a, b in zip(records, records[1:])), 'Native dates went backwards'
    semantics = {}
    for tag in ('ger', 'fra', 'raj'):
        phases = [observed[tag+'_'+phase] for phase in ('baseline', 'reserve_added', 'loaded', 'after_day')]
        assert all(manifest['expected_observation_actors'][tag+'_'+phase] == tag.upper()
                   for phase in ('baseline', 'reserve_added', 'loaded', 'after_day'))
        assert all(a['line_index'] < b['line_index'] and a['instant'] <= b['instant'] for a, b in zip(phases, phases[1:]))
        elapsed = (phases[-1]['instant']-phases[0]['instant']).total_seconds()/3600
        assert elapsed >= manifest['minimum_total_native_hours']
        baseline, reserve, loaded, after = phases
        assert baseline['instant'] == reserve['instant'] == loaded['instant'], 'Immediate probe phases changed native date'

        def correlate(suffix, phase, lower, upper, expected=None):
            label = tag+'_'+suffix
            if label not in manifest['assertions']:
                return
            record = assertion_records[label]
            assert lower['line_index'] < record['line_index'] < upper['line_index'], (label, 'Wrong assertion phase')
            assert record['instant'] == phase['instant'], (label, 'Wrong assertion native date')
            if expected is not None:
                assert (record['verdict'] == 'PASS') == expected, (label, 'Verdict contradicts observation')

        # These checks use the same native getters immediately surrounding OBS
        # in the bound builder. Do not infer support for any unasserted getter.
        for suffix in ('frame_initial', 'history_registered', 'missile_base_techs_enabled'):
            correlate(suffix, baseline, startup, baseline, True if suffix == 'frame_initial' else None)
        correlate('initial_deployed_total_twelve_experiment', baseline, baseline, reserve,
                  baseline['all_deployed_planes'] == 12)
        correlate('control_fighter_deployed', baseline, baseline, reserve,
                  baseline['control_fighter_deployed_archetype'] > 0)
        for field, added in (('nuclear_reserve', 3), ('short_nuclear_reserve', 5), ('guided_reserve', 7), ('ballistic_reserve', 11)):
            correlate('reserve_added_'+field, reserve, reserve, loaded,
                      math.isclose(reserve[field]-baseline[field], added, abs_tol=.02))
        for suffix in ('owned_controlled_capital', 'rocket_site_ready'):
            correlate(suffix, loaded, reserve, loaded)
        correlate('frame_after_day', after, loaded, after, True)
        for suffix, field, minimum in (
            ('deployed_total_at_least_twelve_experiment', 'all_deployed_planes', 11),
            ('control_fighter_still_deployed', 'control_fighter_deployed_archetype', 0),
            ('deployed_nuclear_enum_positive', 'nuclear_deployed_enum', 0),
            ('deployed_ballistic_enum_positive', 'ballistic_deployed_enum', 0),
        ):
            correlate(suffix, after, after, ending, after[field] > minimum)
        semantics[tag] = {'elapsed_native_hours': elapsed,
                         'deployment_method': manifest.get('deployment_method', 'runtime_load_oob'),
                         'starting_deployed_counters': {field: baseline[field] for field in manifest['observation_fields'] if 'deployed' in field},
                         'nuclear_num_equipment_loaded_delta': loaded['nuclear_reserve']-reserve['nuclear_reserve'],
                         'short_nuclear_num_equipment_loaded_delta': loaded['short_nuclear_reserve']-reserve['short_nuclear_reserve'],
                         'deployed_counter_deltas': {field: after[field]-baseline[field] for field in manifest['observation_fields'] if 'deployed' in field}}
    for value in observed.values():
        value.pop('instant')
    return {'passed': passed, 'failed': failed, 'observations': observed, 'native_counter_semantics': semantics}


def analyze(manifest_path, launch_path, game_log):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    launch = json.loads(launch_path.read_text(encoding='utf-8-sig'))
    assert manifest['schema'] == 1 and manifest['kind'] == 'native_missile_inventory_deployment'
    assert not manifest['preparation_only']
    source, fixture = Path(manifest['source_root']), Path(manifest['fixture_root'])
    assert launch['schema'] == 1 and isinstance(launch['pid'], int) and launch['pid'] > 0
    assert Path(launch['source_root']).resolve() == source.resolve()
    assert launch['manifest_sha256'] == sha(manifest_path)
    assert launch['embedded_fixture'] and Path(launch['embedded_root']).resolve() == source.resolve()
    assert launch['enabled_mods'] == manifest['expected_enabled_mods']
    user_dir = Path(launch['user_dir'])
    assert Path(launch['game_log']).resolve() == game_log.resolve() == (user_dir/'logs/game.log').resolve()
    export = manifest['source_export_binding']
    assert export and sha(Path(export['path'])) == export['sha256'] == launch['source_export_receipt_sha256'].lower()
    start = json.loads(Path(launch['start_receipt']).read_text(encoding='utf-8-sig'))
    assert start['pid'] == launch['pid'] and start['exe'] == launch['exe']
    assert '-start_tag='+manifest['expected_native_start_tag'] in start['arguments']
    assert start['process_start_utc'] == launch['process_start_utc']
    began = datetime.fromisoformat(start['process_start_utc'].replace('Z', '+00:00'))
    assert game_log.stat().st_ctime >= began.timestamp()-3 and game_log.stat().st_mtime >= began.timestamp()
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
        assert sha(source/rel) == digest, ('Changed production source', rel)
    for rel, digest in manifest['fixture_sha256'].items():
        assert sha(fixture/'mod'/rel) == sha(source/rel) == digest
        assert launch['embedded_source_sha256'].get(rel) == digest
    error_log = user_dir/'logs/error.log'
    selected = [line for line in error_log.read_text(encoding='utf-8-sig', errors='replace').splitlines()
                if re.search(r'eon_private_missile_probe|00_raids_triggers\.txt|eon_tactical_nuclear_missile_raid\.txt|eon_nuclear_arsenal_ready|Invalid equipment type|Invalid air wing|nuclear_ballistic_missile_equipment_1', line, re.I)]
    parsed = parse_log(game_log.read_text(encoding='utf-8-sig', errors='replace'), manifest)
    accepted = not parsed['failed'] and not selected
    return {'native_missile_counter_probe_passed': accepted, **parsed, 'native_assertions_passed': len(parsed['passed']),
            'native_assertions_failed': len(parsed['failed']), 'selected_errors': selected,
            'manifest_sha256': sha(manifest_path), 'launch_receipt_sha256': sha(launch_path),
            'game_log_sha256': sha(game_log), 'error_log_sha256': sha(error_log), 'analyzer_sha256': sha(Path(__file__)),
            'actual_human_gui_clicks_verified': False, 'actual_raid_launch_verified': False,
            'automatic_one_use_only_consumption_verified': False, 'save_load_verified': False,
            'multiplayer_verified': False, 'limits': manifest['limits']}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--manifest', type=Path, required=True)
    cli.add_argument('--launch-receipt', type=Path, required=True)
    cli.add_argument('--game-log', type=Path, required=True)
    args = cli.parse_args()
    result = analyze(args.manifest, args.launch_receipt, args.game_log)
    print(json.dumps(result, indent=2))
    if not result['native_missile_counter_probe_passed']:
        raise SystemExit(1)
