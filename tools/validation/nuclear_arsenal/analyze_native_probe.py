"""Validate frozen native upkeep evidence; never launch or mutate the game."""
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import hashlib
import json
import math
import re

from build_native_probe import (sha, expense_reference, weekly_instrumentation,
                                restore_weekly_instrumentation, MONEY_REL, WEEKLY_REL, NS)


def parse_log_v3(text, manifest):
    assert manifest['fixture_version'] == 3, 'Fresh V3 evidence is required; older failed fixtures remain separate'
    assert manifest['monetary_comparison_scale'] == 1000000
    assert manifest['budget_baseline_refreshes'] == 3
    marker = re.escape(manifest['marker'])
    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines) if re.search(marker+r' STARTUP native_nuclear_arsenal_upkeep', line)]
    assert len(starts) == 1, 'Missing/duplicate native startup'
    passed = re.findall(marker+r' PASS ([A-Za-z0-9_]+)', text)
    failed = re.findall(marker+r' FAIL ([A-Za-z0-9_]+)', text)
    assert Counter(passed+failed) == Counter(manifest['assertions']), 'Missing/duplicate/unexpected assertions'
    assert all(count == 1 for count in Counter(passed+failed).values())
    endings = [(index, re.search(marker+r' END passes=([0-9.]+) fails=([0-9.]+)', line))
               for index, line in enumerate(lines) if re.search(marker+r' END ', line)]
    assert len(endings) == 1 and endings[0][1], 'Missing/duplicate native end'
    end_line, end = endings[0]
    assert list(map(float, end.groups())) == [len(passed), len(failed)]
    assert not re.search(marker+r' (ABORT|DUPLICATE_EVENT)', text)
    observed = {}
    for index, line in enumerate(lines):
        match = re.search(marker+r' OBS ([A-Za-z0-9_]+) ROOT=([^ ]+) THIS=([^ ]+) (.*)', line)
        if not match: continue
        label, root, actor, fields = match.groups()
        assert label in manifest['observation_labels'] and label not in observed
        assert root == actor == manifest['expected_observation_actors'][label], ('Wrong country frame', label, root, actor)
        assert starts[0] < index < end_line, 'Snapshot outside native run'
        dates = re.findall(r'\[(\d{4}\.\d{2}\.\d{2}\.\d{2})\]', line)
        assert dates
        year, month, day, hour = map(int, dates[-1].split('.'))
        assert 0 <= hour <= 24
        instant = datetime(year, month, day)+timedelta(hours=hour)
        pairs = re.findall(r'([a-z_]+)=(-?\d+(?:\.\d+)?)', fields)
        assert Counter(key for key, value in pairs) == Counter(manifest['observation_fields'])
        values = {key: float(value) for key, value in pairs}
        assert all(math.isfinite(value) for value in values.values())
        observed[label] = dict(line_index=index+1, native_date=dates[-1], instant=instant, **values)
    assert set(observed) == set(manifest['observation_labels'])
    tolerance = manifest['numeric_tolerance']
    assert 0 < tolerance <= 0.000011, 'Overly permissive monetary tolerance'
    near = lambda a, b: math.isclose(a, b, abs_tol=tolerance, rel_tol=1e-7)
    prices = manifest['game_prices']
    assert prices == dict(fixed=0.002, weapon=0.00002, deployed_premium=0.00004, safety_share=0.35)
    intervals = {}
    for tag in manifest['observed_countries']:
        prefix = tag.lower()+'_'
        phases = [observed[prefix+phase] for phase in ('full_before', 'safety', 'resume', 'week_1', 'week_2', 'week_3', 'week_4')]
        assert all(a['line_index'] < b['line_index'] and a['instant'] <= b['instant'] for a, b in zip(phases, phases[1:]))
        full, safety, resume, *weeks = phases
        assert full['step'] == safety['step'] == resume['step'] == 0
        assert full['ready'] == 1 and full['safety'] == full['remaining'] == 0
        assert safety['ready'] == 0 and safety['safety'] == 1 and safety['remaining'] == 0
        assert resume['ready'] == resume['safety'] == 0 and resume['remaining'] == 4
        assert full['total'] > 0 and full['total'] == safety['total'] == resume['total']
        assert full['reserve'] == safety['reserve'] == resume['reserve']
        assert full['deployed'] == safety['deployed'] == resume['deployed']
        assert near(full['cost'], full['full_cost']) and near(full['expense'], full['full_expense'])
        assert near(safety['cost'], full['cost']*prices['safety_share']), 'Safety upkeep cost wrong'
        assert near(full['expense']-safety['expense'], full['cost']-safety['cost']), 'Arsenal budget charged twice or not replaced'
        assert near(resume['cost'], full['cost']) and near(resume['expense'], full['expense'])
        assert near(full['treasury'], full['treasury_before']), 'Arsenal refresh debited treasury'
        assert near(safety['treasury'], full['treasury']) and near(resume['treasury'], full['treasury']), 'Mode switch directly debited treasury'
        for step, row in enumerate(weeks, 1):
            assert row['step'] == step and row['remaining'] == 4-step
            assert row['safety'] == 0 and row['ready'] == int(step == 4)
        assert weeks[0]['instant'] > resume['instant'], 'First recovery pulse fabricated in same setup frame'
        intervals[tag] = [(right['instant']-left['instant']).total_seconds()/3600 for left, right in zip(weeks, weeks[1:])]
        assert intervals[tag] == [manifest['weekly_interval_hours']]*3 == [168]*3, 'Four pulses are not separate real weeks'
        for row in phases:
            assert row['total'] == row['reserve']+row['deployed']
            assert row['reserve'] >= 0 and row['deployed'] >= 0
            ordinary = 0 if row['total'] == 0 else prices['fixed']+prices['weapon']*row['total']+prices['deployed_premium']*row['deployed']
            expected_cost = ordinary*(prices['safety_share'] if row['safety'] else 1)
            assert near(row['cost'], expected_cost), ('Native cost does not match bound game calibration', tag, row)
    for row in observed.values(): row.pop('instant')
    return dict(passed=passed, failed=failed, observations=observed,
                weekly_interval_native_hours=intervals, four_real_weekly_pulses_seen=True,
                budget_component_replaced_once=True)


def parse_log_v4(text, manifest):
    assert manifest['fixture_version'] == 4
    assert manifest['monetary_comparison_scale'] == 1000000
    assert manifest['budget_reference_mode'] == 'same_input_exact_hook_inverse'
    assert manifest['weekly_trace_stages'] == ['production_before', 'production_after', 'production_budget', 'production_cash']
    assert manifest['weekly_latch_contract'] == {'flag': 'eon_nuclear_arsenal_weekly_processed', 'days': 6, 'value': 1}
    marker = re.escape(manifest['marker'])
    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines) if re.search(marker+r' STARTUP native_nuclear_arsenal_upkeep', line)]
    assert len(starts) == 1, 'Missing/duplicate native startup'
    passed = re.findall(marker+r' PASS ([A-Za-z0-9_]+)', text)
    failed = re.findall(marker+r' FAIL ([A-Za-z0-9_]+)', text)
    assert Counter(passed+failed) == Counter(manifest['assertions']), 'Missing/duplicate/unexpected assertions'
    assert all(count == 1 for count in Counter(passed+failed).values())
    endings = [(index, re.search(marker+r' END passes=([0-9.]+) fails=([0-9.]+)', line))
               for index, line in enumerate(lines) if re.search(marker+r' END ', line)]
    assert len(endings) == 1 and endings[0][1], 'Missing/duplicate native end'
    end_line, end = endings[0]
    assert list(map(float, end.groups())) == [len(passed), len(failed)]
    assert not re.search(marker+r' (ABORT|DUPLICATE_EVENT)', text)

    def native_stamp(index, line):
        dates = re.findall(r'\[(\d{4}\.\d{2}\.\d{2}\.\d{2})\]', line)
        assert dates, 'Missing native date'
        year, month, day, hour = map(int, dates[-1].split('.'))
        assert 0 <= hour <= 24
        try:
            instant = datetime(year, month, day)+timedelta(hours=hour)
        except ValueError as error:
            raise AssertionError('Invalid native date') from error
        return dict(line_index=index+1, native_date=dates[-1], instant=instant)

    assert re.search(marker+r' STARTUP native_nuclear_arsenal_upkeep\s*$', lines[starts[0]])
    assert re.search(marker+r' END passes=([0-9]+(?:\.[0-9]+)?) fails=([0-9]+(?:\.[0-9]+)?)\s*$', lines[end_line])
    startup, ending = native_stamp(starts[0], lines[starts[0]]), native_stamp(end_line, lines[end_line])
    assertion_records = {}
    for index, line in enumerate(lines):
        result = re.search(marker+r' (PASS|FAIL) ([A-Za-z0-9_]+)\s*$', line)
        if result:
            verdict, label = result.groups()
            assert starts[0] < index < end_line, 'Assertion outside native run'
            assertion_records[label] = dict(verdict=verdict, **native_stamp(index, line))
    assert set(assertion_records) == set(manifest['assertions']), 'Malformed assertion record'

    def record(index, line, fields):
        matches = [re.fullmatch(r'([a-z_]+)=(-?\d+(?:\.\d+)?)', token) for token in fields.split()]
        assert all(matches), 'Malformed numeric record field'
        pairs = [match.groups() for match in matches]
        assert len(pairs) == len({key for key, value in pairs}), 'Duplicate numeric record field'
        values = {key: float(value) for key, value in pairs}
        assert all(math.isfinite(value) for value in values.values())
        assert starts[0] < index < end_line, 'Snapshot outside native run'
        return dict(**native_stamp(index, line), **values)

    observed, traces = {}, []
    for index, line in enumerate(lines):
        match = re.search(marker+r' OBS ([A-Za-z0-9_]+) ROOT=([^ ]+) THIS=([^ ]+) (.*)', line)
        if match:
            label, root, actor, fields = match.groups()
            assert label in manifest['observation_labels'] and label not in observed
            assert root == actor == manifest['expected_observation_actors'][label], ('Wrong country frame', label, root, actor)
            row = record(index, line, fields)
            assert set(row)-{'line_index', 'native_date', 'instant'} == set(manifest['observation_fields'])
            observed[label] = row
        match = re.search(marker+r' TRACE ([A-Za-z0-9_]+) ROOT=([^ ]+) THIS=([^ ]+) (.*)', line)
        if match:
            stage, root, actor, fields = match.groups()
            assert stage in manifest['weekly_trace_stages']
            assert root == actor and actor in manifest['observed_countries']
            row = record(index, line, fields)
            assert set(row)-{'line_index', 'native_date', 'instant'} == {'weeks', 'remaining', 'cost', 'expense', 'treasury', 'active', 'latch'}
            assert row['active'] == 1 and row['latch'] in (0, 1)
            traces.append(dict(stage=stage, actor=actor, **row))
    assert set(observed) == set(manifest['observation_labels'])
    assert len(traces) == len(manifest['observed_countries'])*4*4, 'Missing/extra upstream weekly trace'
    records = sorted([startup, ending, *assertion_records.values(), *observed.values(), *traces],
                     key=lambda row: row['line_index'])
    assert all(a['instant'] <= b['instant'] for a, b in zip(records, records[1:])), 'Native record dates went backwards'
    tolerance = manifest['numeric_tolerance']
    assert 0 < tolerance <= 0.000011, 'Overly permissive monetary tolerance'
    near = lambda a, b: math.isclose(a, b, abs_tol=tolerance, rel_tol=0)
    prices = manifest['game_prices']
    assert prices == dict(fixed=0.002, weapon=0.00002, deployed_premium=0.00004, safety_share=0.35)
    intervals, contextualized = {}, []

    def phase_assertions(tag, phase, row, lower):
        if phase == 'full_before':
            suffixes = ['initial_frame', 'refresh_free', 'arsenal_positive', 'default_full_ready']
        elif phase == 'safety':
            suffixes = ['safety_blocks', 'safety_cost']
        elif phase == 'resume':
            suffixes = ['refresh_does_not_recover']
        else:
            suffixes = [phase+'_'+suffix for suffix in ('frame', 'remaining', 'readiness', 'duplicate_blocked')]
        suffixes += [phase+'_'+suffix for suffix in ('rate_repeatable', 'budget_once', 'income_preserved')]
        for suffix in suffixes:
            label = tag.lower()+'_'+suffix
            assert label in assertion_records, ('Missing phase assertion', label)
            assertion = assertion_records[label]
            assert lower['line_index'] < assertion['line_index'] < row['line_index'], ('Wrong assertion phase', label)
            assert assertion['instant'] == row['instant'], ('Wrong assertion native date', label)
            contextualized.append(label)

    for tag in manifest['observed_countries']:
        prefix = tag.lower()+'_'
        phases = [observed[prefix+phase] for phase in ('full_before', 'safety', 'resume', 'week_1', 'week_2', 'week_3', 'week_4')]
        assert all(a['line_index'] < b['line_index'] and a['instant'] <= b['instant'] for a, b in zip(phases, phases[1:]))
        full, safety, resume, *weeks = phases
        assert full['instant'] == safety['instant'] == resume['instant'], 'Immediate setup phases changed native date'
        phase_assertions(tag, 'full_before', full, startup)
        phase_assertions(tag, 'safety', safety, full)
        phase_assertions(tag, 'resume', resume, safety)
        assert full['step'] == safety['step'] == resume['step'] == 0
        assert full['ready'] == 1 and full['safety'] == full['remaining'] == 0
        assert safety['ready'] == 0 and safety['safety'] == 1 and safety['remaining'] == 0
        assert resume['ready'] == resume['safety'] == 0 and resume['remaining'] == 4
        assert full['total'] > 0 and full['total'] == safety['total'] == resume['total']
        assert full['reserve'] == safety['reserve'] == resume['reserve']
        assert full['deployed'] == safety['deployed'] == resume['deployed']
        assert near(full['cost'], full['full_cost']) and near(full['expense'], full['full_expense'])
        assert near(safety['cost'], full['cost']*prices['safety_share']), 'Safety upkeep cost wrong'
        assert near(resume['cost'], full['cost'])
        assert near(full['treasury'], full['treasury_before']), 'Arsenal refresh debited treasury'
        assert near(safety['treasury'], full['treasury']) and near(resume['treasury'], full['treasury']), 'Mode switch directly debited treasury'
        for row in phases:
            assert row['total'] == row['reserve']+row['deployed']
            assert row['reserve'] >= 0 and row['deployed'] >= 0
            ordinary = 0 if row['total'] == 0 else prices['fixed']+prices['weapon']*row['total']+prices['deployed_premium']*row['deployed']
            assert near(row['cost'], ordinary*(prices['safety_share'] if row['safety'] else 1)), 'Native cost differs from bound game calibration'
            assert near(row['rate_before'], row['rate_after']) and near(row['expense'], row['rate_after']), 'Same-input rate is not repeatable'
            assert near(row['expense']-row['base_expense'], row['cost']), 'Arsenal component added twice or omitted'
            assert near(row['income'], row['income_before']), 'Private observer changed energy income accumulator'
        for step, row in enumerate(weeks, 1):
            assert row['step'] == step and row['remaining'] == 4-step
            assert row['safety'] == 0 and row['ready'] == int(step == 4)
            assert row['latch'] == 1, 'Native same-pulse guard is not visible after duplicate'
            cycle = [entry for entry in traces if entry['actor'] == tag and entry['instant'] == row['instant']]
            assert [entry['stage'] for entry in cycle] == manifest['weekly_trace_stages'], 'Wrong upstream weekly execution order'
            assert all(entry['line_index'] < row['line_index'] for entry in cycle), 'Observer ran before ordinary upstream weekly budget/cash'
            assert all(entry['weeks'] == step-1 for entry in cycle)
            assert cycle[0]['remaining'] == 5-step and cycle[0]['latch'] == 0
            assert all(entry['remaining'] == 4-step and entry['latch'] == 1 for entry in cycle[1:])
            phase_assertions(tag, f'week_{step}', row, cycle[-1])
            # Later ordinary weekly handlers may settle investment income/debt
            # or refresh GDP. Their total must not be mistaken for a fixed
            # arsenal-only invoice. The same-input reference above proves the
            # exact component at each snapshot; these rows establish ordering.
        assert weeks[0]['instant'] > resume['instant'], 'First recovery pulse fabricated in setup frame'
        intervals[tag] = [(right['instant']-left['instant']).total_seconds()/3600 for left, right in zip(weeks, weeks[1:])]
        assert intervals[tag] == [manifest['weekly_interval_hours']]*3 == [168]*3, 'Four pulses are not separate real weeks'
    assert Counter(contextualized) == Counter(manifest['assertions']), 'Unbound assertion context'
    for row in list(observed.values())+traces: row.pop('instant')
    return dict(passed=passed, failed=failed, observations=observed, weekly_traces=traces,
                weekly_interval_native_hours=intervals, four_real_weekly_pulses_seen=True,
                budget_component_replaced_once=True, budget_reference_mode=manifest['budget_reference_mode'],
                upstream_weekly_order_verified=True)


def parse_log(text, manifest):
    if manifest['fixture_version'] == 3: return parse_log_v3(text, manifest)
    if manifest['fixture_version'] == 4: return parse_log_v4(text, manifest)
    raise AssertionError('Fresh V3 or V4 evidence required; older failed fixtures remain separate')


def analyze(manifest_path, launch_path, game_log):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    launch = json.loads(launch_path.read_text(encoding='utf-8-sig'))
    assert manifest['schema'] == 1 and manifest['kind'] == 'native_nuclear_arsenal_upkeep'
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
        if manifest['fixture_version'] == 4 and rel == WEEKLY_REL:
            restored = restore_weekly_instrumentation((source/rel).read_bytes(), manifest['private_weekly_replacements'])
            assert hashlib.sha256(restored).hexdigest() == digest, ('Changed production source outside private logs', rel)
            instrumented, changes = weekly_instrumentation(restored)
            assert changes == manifest['private_weekly_replacements'] and instrumented == (source/rel).read_bytes()
        else:
            assert sha(source/rel) == digest, ('Changed production source', rel)
    if manifest['fixture_version'] == 4:
        reference = expense_reference((source/MONEY_REL).read_bytes())
        assert hashlib.sha256(reference.encode('utf-8')).hexdigest() == manifest['expense_reference_body_sha256']
        assert (source/f'common/scripted_effects/{NS}_expense_reference.txt').read_bytes() == (f'{NS}_expense_reference = {{'+reference+'}\n').encode('utf-8')
    for rel, digest in manifest['fixture_sha256'].items():
        assert sha(fixture/'mod'/rel) == sha(source/rel) == digest
        assert launch['embedded_source_sha256'].get(rel) == digest
    docs = Path(manifest['installed_documentation_root'])
    for rel, digest in manifest['installed_documentation_sha256'].items():
        assert sha(docs/rel) == digest, ('Changed native documentation', rel)
    error_log = user_dir/'logs/error.log'
    selected = [line for line in error_log.read_text(encoding='utf-8-sig', errors='replace').splitlines()
                if re.search(r'eon_private_upkeep|eon_nuclear_arsenal|Invalid equipment type|Invalid air wing', line, re.I)]
    parsed = parse_log(game_log.read_text(encoding='utf-8-sig', errors='replace'), manifest)
    return dict(native_nuclear_arsenal_upkeep_probe_passed=not parsed['failed'] and not selected,
                **parsed, native_assertions_passed=len(parsed['passed']), native_assertions_failed=len(parsed['failed']),
                selected_errors=selected, manifest_sha256=sha(manifest_path), launch_receipt_sha256=sha(launch_path),
                game_log_sha256=sha(game_log), error_log_sha256=sha(error_log), analyzer_sha256=sha(Path(__file__)),
                actual_human_gui_clicks_verified=False, actual_raid_launch_verified=False,
                native_inventory_counter_semantics_verified=False, save_load_verified=False,
                multiplayer_verified=False, limits=manifest['limits'])


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--manifest', type=Path, required=True)
    cli.add_argument('--launch-receipt', type=Path, required=True)
    cli.add_argument('--game-log', type=Path, required=True)
    args = cli.parse_args()
    result = analyze(args.manifest, args.launch_receipt, args.game_log)
    print(json.dumps(result, indent=2))
    if not result['native_nuclear_arsenal_upkeep_probe_passed']: raise SystemExit(1)
