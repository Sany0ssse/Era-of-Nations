"""Verify native state activation diagnosis and target callback scope receipts."""
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
from build_state_activation_native_probe import NS


def parse_log(text, manifest):
    marker = re.escape(manifest['marker'])
    assert len(re.findall(marker+r' STARTUP native_state_activation', text)) == 1
    passed = re.findall(marker+r' PASS ([A-Za-z0-9_]+)', text)
    failed = re.findall(marker+r' FAIL ([A-Za-z0-9_]+)', text)
    seen = Counter(passed+failed)
    assert all(n == 1 for n in seen.values()) and set(seen) <= set(manifest['assertions'])
    required = set(manifest['assertions'])-set(manifest['optional_callback_assertions'])
    assert required <= set(seen)
    end = re.findall(marker+r' END passes=([0-9.]+) fails=([0-9.]+)', text)
    assert len(end) == 1 and list(map(float, end[0])) == [len(passed), len(failed)]
    assert not re.search(marker+r' (ABORT|DUPLICATE_EVENT)', text)
    # Callback flags and END counters cannot conceal an invocation before
    # initialization. New probes trace native callbacks; legacy probes must
    # also place all callback assertions after their initial observation.
    startup_at = re.search(marker+r' STARTUP native_state_activation',text).start()
    initial_at = re.search(marker+r' OBS before_ordinary_activation ',text)
    assert initial_at, 'Missing initial callback boundary'
    for callback in re.finditer(marker+r' (?:PASS|FAIL) ((?:ordinary_complete_native|ordinary_remove_native|ordinary_source_|timed_native_FROM|timed_source_)[A-Za-z0-9_]*)',text):
        assert callback.start() > initial_at.start() > startup_at, 'Native callback ran before initialized state fixture'
    observations = {}
    for index, line in enumerate(text.splitlines(), 1):
        found = re.search(marker+r' OBS ([A-Za-z0-9_]+) ROOT=([^ ]+) THIS=([^ ]+) (.*)', line)
        if not found: continue
        label, root, actor, raw = found.groups()
        assert label in manifest['observation_labels'] and label not in observations and root == actor == 'GER'
        dates = re.findall(r'\[(\d{4}\.\d{2}\.\d{2}\.\d{2})\]', line)
        assert dates
        year, month, day, hour = map(int, dates[-1].split('.'))
        assert 0 <= hour <= 24
        pairs = re.findall(r'([a-z_]+)=(-?\d+(?:\.\d+)?)', raw)
        assert Counter(k for k, v in pairs) == Counter(list(manifest['observation_fields']))
        values = {k: float(v) for k, v in pairs}
        assert all(math.isfinite(v) for v in values.values())
        for key in ('ordinary_complete', 'ordinary_remove', 'timed_callback'): assert values[key] in (0, 1)
        observations[label] = {'line': index, 'native_date': dates[-1], 'instant': datetime(year, month, day)+timedelta(hours=hour), **values}
    assert set(observations) == set(manifest['observation_labels'])
    ordered = [observations[label] for label in manifest['observation_labels']]
    assert all(a['line'] < b['line'] and a['instant'] < b['instant'] for a, b in zip(ordered, ordered[1:]))
    elapsed = (ordered[-1]['instant']-ordered[0]['instant']).total_seconds()/3600
    assert elapsed >= manifest['minimum_total_native_hours']
    final = observations['after_native_timeout_wait']
    initial = observations['before_ordinary_activation']
    assert initial['ordinary_complete'] == initial['ordinary_remove'] == initial['timed_callback'] == 0, 'Callback already fired before arming'
    for key, assertion in (('ordinary_complete', 'ordinary_complete_native_FROM_state44'), ('ordinary_remove', 'ordinary_remove_native_FROM_state44')):
        assert (assertion in seen) == bool(final[key]), ('Callback observation/statement mismatch', key)
    timed_assertions = [label for label in manifest['optional_callback_assertions'] if label.startswith('timed_')]
    assert all((label in seen) == bool(final['timed_callback']) for label in timed_assertions)
    if 'timed_native_callback_fired' in passed: assert final['timed_callback'] == 1
    if 'timed_native_callback_fired' in failed: assert final['timed_callback'] == 0
    if final['timed_callback']: assert math.isclose(final['capacity'], 7.5, abs_tol=.01)
    if manifest.get('state_evidence_version',1) >= 2:
        assert manifest['state_evidence_version'] in (2,3,4,5)
        arm_o = re.search(marker+r' ARMED ordinary_native_AI_selection',text)
        arm_t = re.search(marker+r' ARMED timed_native_FROM_control',text)
        assert arm_o and arm_t and initial_at.start() < arm_o.start() < arm_t.start()
        callback_positions = {}
        for hit in re.finditer(marker+r' CALLBACK (ordinary_begin|ordinary_remove|timed_timeout)',text):
            assert hit[1] not in callback_positions
            callback_positions[hit[1]] = hit.start()
        for callback,key,arm in (('ordinary_begin','ordinary_complete',arm_o),('ordinary_remove','ordinary_remove',arm_o),('timed_timeout','timed_callback',arm_t)):
            assert (callback in callback_positions) == bool(final[key])
            if final[key]: assert callback_positions[callback] > arm.start(), 'Native callback preceded its stage arm'
        if final['timed_callback']:
            final_at=re.search(marker+r' OBS after_native_timeout_wait ',text).start()
            assert callback_positions['timed_timeout'] < final_at, 'Timed callback ran after its final observation'
        if manifest['state_evidence_version'] in (4,5):
            assert manifest['timed_native_timeout_observation_delay_hours'] == 64
            assert manifest['minimum_timed_timeout_observation_hours'] == 60
            waited=(final['instant']-observations['after_ordinary_activation_wait']['instant']).total_seconds()/3600
            assert waited >= 60, 'Timed callback observation was premature'
        if final['ordinary_complete'] and final['ordinary_remove']:
            assert callback_positions['ordinary_begin'] < callback_positions['ordinary_remove'] < arm_t.start()
        if manifest.get('state_evidence_version',1) >= 3 and final['ordinary_complete']:
            line=text[:callback_positions['ordinary_begin']].splitlines()[-1]
            stamp=re.findall(r'\[(\d{4}\.\d{2}\.\d{2}\.\d{2})\]',line)[-1]
            year,month,day,hour=map(int,stamp.split('.'))
            began=datetime(year,month,day)+timedelta(hours=hour)
            waited=(observations['after_ordinary_activation_wait']['instant']-began).total_seconds()/3600
            assert waited >= 30,'Ordinary native wait was scheduled before actual AI selection'
        for key in ('ordinary_complete','ordinary_remove'): assert observations['after_ordinary_activation_wait'][key] == final[key]
        assert observations['after_ordinary_activation_wait']['timed_callback'] == 0
        if final['ordinary_complete']:
            assert 'ordinary_source_begin_deducts_exactly025' in seen
        if final['ordinary_remove']:
            assert {'ordinary_source_remove_has_no_second_charge','ordinary_source_remove_geometric_expansion'} <= set(seen)
    for value in observations.values(): value.pop('instant')
    return {'passed': passed, 'failed': failed, 'observations': observations, 'elapsed_native_hours': elapsed,
            'ordinary_activate_targeted_decision_called_complete_effect': bool(final['ordinary_complete']) if manifest.get('state_evidence_version',1) == 1 else False,
            'ordinary_activate_targeted_decision_called_remove_effect': bool(final['ordinary_remove']) if manifest.get('state_evidence_version',1) == 1 else False,
            'native_AI_selected_ordinary_source_callbacks_verified': manifest.get('state_evidence_version',1) >= 2 and bool(final['ordinary_complete']) and bool(final['ordinary_remove']) and all(label in passed for label in ('ordinary_complete_native_FROM_state44','ordinary_source_begin_deducts_exactly025','ordinary_remove_native_FROM_state44','ordinary_source_remove_has_no_second_charge','ordinary_source_remove_geometric_expansion')),
            'native_targeted_mission_source_callbacks_verified': bool(final['timed_callback']) and set(timed_assertions) <= set(passed),
            'ordinary_player_decision_click_verified': False}


def verify_bindings(source, fixture, manifest):
    parser = load_parser()
    aliases = parser.ast((fixture/'mod/common/scripted_effects'/f'{NS}_effects.txt').read_bytes())
    assert len(manifest['callback_bindings']) == 2
    for binding in manifest['callback_bindings']:
        body = parser.ast((source/binding['source_path']).read_bytes())
        for part in binding['selector']: body = parser.one(body, part)
        assert canonical(body) == canonical(parser.one(aliases, binding['alias'])) == binding['source_ast_sha256']
    original = parser.one(parser.one(parser.ast((source/'common/decisions/eon_uranium_decisions.txt').read_bytes()), 'eon_uranium_category'), 'eon_uranium_expand_mine')
    assert canonical(original) == manifest['private_ordinary_source_ast_sha256']
    if manifest.get('state_evidence_version',1) == 5:
        binding=manifest['state_target_selector_binding']
        assert binding['source_path'] == 'common/decisions/eon_uranium_decisions.txt'
        assert binding['selector'] == ['eon_uranium_category','eon_uranium_expand_mine','state_target']
        selector=parser.one(original,'state_target')
        assert selector == binding['value'] == 'any_owned_state'
        assert canonical(selector) == binding['source_ast_sha256']
        decisions=parser.one(parser.ast((fixture/'mod/common/decisions'/f'{NS}_decisions.txt').read_bytes()),NS+'_category')
        ordinary=parser.one(decisions,NS+'_ordinary')
        timed=parser.one(decisions,NS+'_timed')
        assert parser.one(ordinary,'state_target') == parser.one(timed,'state_target') == selector
        assert canonical(ordinary) == manifest['private_ordinary_fixture_ast_sha256']
        assert canonical(timed) == manifest['private_timed_fixture_ast_sha256']
        # All copied ordinary metadata except the declared private clock,
        # gating, priority and source callback wrappers stays source-bound.
        altered={'days_remove','ai_will_do','target_root_trigger','target_trigger','complete_effect','remove_effect'}
        assert canonical([entry for entry in ordinary if entry[0] not in altered]) == canonical([entry for entry in original if entry[0] not in altered])


def analyze(manifest_path, launch_path, game_log):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    assert manifest['kind'] == 'native_uranium_state_activation_control'
    verify_bindings(Path(manifest['source_root']), Path(manifest['fixture_root']), manifest)
    path = Path(__file__).with_name('analyze_native_probe.py')
    spec = importlib.util.spec_from_file_location('uranium_state_activation_receipt_verifier', path)
    evidence = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evidence)
    evidence.parse_log = parse_log
    result = evidence.analyze(manifest_path, launch_path, game_log)
    result['native_state_activation_control_recorded'] = result.pop('native_resource_trade_prototype_passed')
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
    if not result['native_state_activation_control_recorded']: raise SystemExit(1)


if __name__ == '__main__': main()
