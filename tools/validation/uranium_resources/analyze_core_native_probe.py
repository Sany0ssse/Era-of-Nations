"""Validate source-bound uranium native evidence; synthetic logs are not proof."""
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import json
import math
import re

from build_core_native_probe import NS, canonical
from build_native_probe import load_parser, sha


def parse_log(text, manifest):
    marker = re.escape(manifest['marker'])
    assert len(re.findall(marker+r' STARTUP source_bound_core', text)) == 1
    passed = re.findall(marker+r' PASS ([A-Za-z0-9_]+)', text)
    failed = re.findall(marker+r' FAIL ([A-Za-z0-9_]+)', text)
    assert Counter(passed+failed) == Counter(manifest['assertions']), 'Missing/duplicate/unexpected assertions'
    assert all(count == 1 for count in Counter(passed+failed).values())
    summaries = re.findall(marker+r' END passes=([0-9.]+) fails=([0-9.]+)', text)
    assert len(summaries) == 1 and list(map(float, summaries[0])) == [len(passed), len(failed)]
    assert not re.search(marker+r' (ABORT|DUPLICATE_EVENT)', text)
    observed = {}
    for index, line in enumerate(text.splitlines(), 1):
        match = re.search(marker+r' OBS ([A-Za-z0-9_]+) ROOT=([^ ]+) THIS=([^ ]+) (.*)', line)
        if not match: continue
        label, root, actor, tail = match.groups()
        assert label in manifest['observation_labels'] and label not in observed
        assert root == manifest['expected_root'] and actor == manifest['expected_actor']
        dates = re.findall(r'\[(\d{4}\.\d{2}\.\d{2}\.\d{2})\]', line)
        assert dates, 'Missing native timestamp'
        year, month, day, hour = map(int, dates[-1].split('.'))
        assert 0 <= hour <= 24
        instant = datetime(year, month, day)+timedelta(hours=hour)
        pairs = re.findall(r'([a-z_]+)=(-?\d+(?:\.\d+)?)', tail)
        assert Counter(key for key, value in pairs) == Counter(list(manifest['observation_fields'])), 'Malformed/duplicate native numeric fields'
        values = {key: float(value) for key, value in pairs}
        assert all(math.isfinite(value) for value in values.values())
        observed[label] = {'line_index': index, 'native_date': dates[-1], 'instant': instant, **values}
    assert set(observed) == set(manifest['observation_labels'])
    ordered = [observed[label] for label in manifest['observation_labels']]
    assert all(a['line_index'] < b['line_index'] and a['instant'] <= b['instant'] for a, b in zip(ordered, ordered[1:]))
    elapsed = (ordered[-1]['instant']-ordered[0]['instant']).total_seconds()/3600
    assert elapsed >= manifest['minimum_total_native_hours'], ('Insufficient native clock', elapsed)

    def equal(actual, expected):
        assert math.isclose(actual, expected, abs_tol=0.02, rel_tol=1e-6), (actual, expected)

    # Counter PASS text alone is insufficient: enforce independent material
    # observations from the production variables recorded in this process.
    raw = observed['raw_to_fuel']
    equal(raw['raw'], 0); equal(raw['fuel'], 1000); equal(raw['tails'], 8000)
    equal(raw['feed'], 9000); equal(raw['last_fuel'], 1000)
    before, after = observed['finite_deposit_before'], observed['finite_deposit_after']
    equal(before['state_reserve'], 10000); equal(after['state_reserve'], 0)
    equal(after['extracted'], 10000)
    assert 0 < after['delivered'] <= 10000.02
    equal(after['delivered'], after['raw']+after['fuel']+after['tails'])
    equal(after['feed'], after['last_fuel']*9)
    capture_before, capture_after = observed['captured_deposit_before'], observed['captured_deposit_after']
    equal(capture_before['state_reserve']-capture_after['state_reserve'], capture_after['extracted'])
    assert capture_after['extracted'] > 0 and capture_after['delivered'] > 0
    equal(capture_after['delivered'], capture_after['raw']+capture_after['fuel']+capture_after['tails'])
    fractional = observed['fractional_resource_observation']
    fraction_delta = fractional['fraction_after']-fractional['fraction_before']
    assert fraction_delta >= 0, 'Negative native resource addition'
    for item in observed.values(): item.pop('instant')
    return {'passed': passed, 'failed': failed, 'observations': observed,
            'elapsed_native_hours': elapsed, 'native_fractional_resource_delta': fraction_delta,
            'native_fractional_resource_0_1_supported': math.isclose(fraction_delta, 0.1, abs_tol=0.005)}


def verify_bindings(source, fixture, manifest):
    parser = load_parser()
    aliases = parser.ast((fixture/'mod'/'common/scripted_effects'/f'{NS}_effects.txt').read_bytes())
    for binding in manifest['callback_bindings']:
        nodes = parser.ast((source/binding['source_path']).read_bytes())
        for part in binding['selector']: nodes = parser.one(nodes, part)
        assert canonical(nodes) == binding['source_ast_sha256']
        assert canonical(parser.one(aliases, binding['alias'])) == binding['source_ast_sha256']
    original = parser.ast((source/'common/decisions/eon_uranium_decisions.txt').read_bytes())
    original = parser.one(parser.one(original, 'eon_uranium_category'), 'eon_uranium_expand_mine')
    assert canonical(original) == manifest['private_mine_decision_source_ast_sha256']
    actual = parser.ast((fixture/'mod'/'common/decisions'/f'{NS}_decisions.txt').read_bytes())
    actual = parser.one(parser.one(actual, NS+'_category'), NS+'_mine')
    expected_changes = {'days_remove': '1', 'ai_will_do': parser.ast('factor = 0'),
                        'complete_effect': parser.ast(NS+'_mine_begin_wrapper = yes'),
                        'remove_effect': parser.ast(NS+'_mine_complete_wrapper = yes')}
    assert actual == [(key, op, expected_changes.get(key, value)) for key, op, value in original]


def analyze(manifest_path, launch_path, game_log):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    launch = json.loads(launch_path.read_text(encoding='utf-8-sig'))
    assert manifest['schema'] == 1 and manifest['kind'] == 'native_source_bound_uranium_core'
    assert not manifest['preparation_only'], 'Preparation-only manifest cannot establish native acceptance'
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
        assert sha(source/rel) == digest, ('Changed production source', rel)
    for rel, digest in manifest['fixture_sha256'].items():
        assert sha(fixture/'mod'/rel) == sha(source/rel) == digest
        assert launch['embedded_source_sha256'].get(rel) == digest
        assert not (source/rel).read_bytes().startswith(b'\xef\xbb\xbf'), ('Unexpected native script BOM', rel)
    verify_bindings(source, fixture, manifest)
    error_log = user_dir/'logs/error.log'
    selected = [line for line in error_log.read_text(encoding='utf-8-sig', errors='replace').splitlines()
                if re.search(r'uranium|eon_private_uranium_core|unknown resource|invalid resource|set_state_owner_to|set_state_controller_to|energy_building_enrichment_facilities', line, re.I)]
    parsed = parse_log(game_log.read_text(encoding='utf-8-sig', errors='replace'), manifest)
    accepted = not parsed['failed'] and not selected
    return {'native_source_bound_uranium_core_passed': accepted, **parsed,
            'native_assertions_passed': len(parsed['passed']), 'native_assertions_failed': len(parsed['failed']),
            'selected_errors': selected, 'manifest_sha256': sha(manifest_path), 'launch_receipt_sha256': sha(launch_path),
            'game_log_sha256': sha(game_log), 'error_log_sha256': sha(error_log), 'analyzer_sha256': sha(Path(__file__)),
            'actual_human_gui_clicks_verified': False, 'save_load_verified': False, 'multiplayer_verified': False,
            'full_enrichment_project_calendar_verified': False, 'limits': manifest['limits']}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--manifest', type=Path, required=True)
    cli.add_argument('--launch-receipt', type=Path, required=True)
    cli.add_argument('--game-log', type=Path, required=True)
    args = cli.parse_args()
    result = analyze(args.manifest, args.launch_receipt, args.game_log)
    print(json.dumps(result, indent=2))
    if not result['native_source_bound_uranium_core_passed']: raise SystemExit(1)


if __name__ == '__main__': main()
