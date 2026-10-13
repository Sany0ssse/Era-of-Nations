"""Validate ordered native EU lifecycle assertions against frozen source bytes."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta
import argparse
import hashlib
import json
import re

NEW_ERRORS = re.compile(r'eon_native_eu|EON_EU_NATIVE|eon_eu_(membership|institutions|voting)|eon_eu_|eon_edu_|Token\s+(?:EU_exit_three_month|EU_exit|EU_voting_mission_focus_EUXXX_QMV_result_timer|EU_voting_mission_focus_EUXXX_QMV_result|EU_parliament_focus_EUXXX_approve_timer|EU_parliament_focus_EUXXX_approve)\b', re.I)
LEGACY_ERRORS = re.compile(
    r'00_eu_scripted_effects|99_EU_voting_scripted_effects|99_EU_scripted_triggers|'
    r'01_european_union_guis|AA_Organizations|EU_ideas\.txt|EU_Council_ideas|'
    r'00_EU_on_actions|EUupdate|EUvote|00_money_system|'
    r'EU_voting_decisions\.txt|EU_events\.txt|01_on_actions\.txt|'
    r'international_systems_scripted_gui\.txt|99_EU_voting_scripted_triggers\.txt|'
    r'EU_POTEF_decisions\.txt|Belarus\.txt|Hungary\.txt|'
    r'00_game_rule_triggers\.txt|00_game_rules\.txt|00_game_rules_on_actions\.txt|'
    r'EU_update_AI_focus_|'
    r'Error: unexpected token in file: "memfile" near line: 1 \( прав \)|'
    r"Invalid effect '(?:прав|Союза_voting_modifier)' in memfile line : 1|"
    r'Unknown effect-type: (?:прав|Союза_voting_modifier), near line: 1', re.I)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def error_key(line):
    # Engine timestamps and error-log destinations differ between launches;
    # source filenames, line numbers and messages remain part of the receipt.
    return re.sub(r'^\[[0-9:. ]+\]\s*', '', line.strip())


def game_timestamp(line):
    """Read the engine's game date, never the wall-clock logger timestamp."""
    match = re.search(r'\[(\d{4})\.(\d{2})\.(\d{2})\.(\d{2})\]', line)
    if not match:
        return None
    try:
        year, month, day, hour = (int(value) for value in match.groups())
        if hour == 24:
            return datetime(year, month, day) + timedelta(days=1)
        return datetime(year, month, day, hour)
    except (ValueError, OverflowError):
        return None


def faction_diagnostic_result(contract, observation_lines):
    """Characterize native goal storage separately from lifecycle assertions.

    Unsupported storage is an explicit negative diagnostic result, never a
    synthetic PASS. Failed mutation/time controls cannot establish support.
    """
    if not contract:
        return None
    assert contract['schema'] == 1
    labels = set()
    for field in ('required_native_preconditions', 'structure_positive_labels',
                  'structure_negative_labels', 'clock_advance_labels',
                  'marker_positive_labels', 'marker_negative_labels',
                  'control_positive_labels', 'control_negative_labels'):
        labels.update(contract.get(field, []))
    labels.add(contract['no_dlc_label'])
    values = {}
    for label in sorted(labels):
        lines = observation_lines.get(label, [])
        match = re.fullmatch(r'value=([01])', lines[0][1]) if len(lines) == 1 else None
        values[label] = int(match[1]) if match else None
    malformed = [label for label, value in values.items() if value is None]
    required_true = (contract['required_native_preconditions'] + contract.get('structure_positive_labels', []) +
                     contract['clock_advance_labels'])
    required_false = contract.get('structure_negative_labels', [])
    failed_controls = [label for label in required_true if values[label] != 1] + [label for label in required_false if values[label] != 0]
    clocks = []
    for start_label, end_label in zip(contract['clock_labels'], contract['clock_labels'][1:]):
        start_lines, end_lines = observation_lines.get(start_label, []), observation_lines.get(end_label, [])
        start = game_timestamp(start_lines[0][0]) if len(start_lines) == 1 else None
        finish = game_timestamp(end_lines[0][0]) if len(end_lines) == 1 else None
        elapsed = (finish - start).total_seconds() / 3600 if start and finish else None
        clocks.append({'start_observation': start_label, 'end_observation': end_label,
                       'elapsed_hours': elapsed, 'requested_hours': contract['required_delay_hours']})
        if elapsed is None or elapsed < 1:
            failed_controls.append(start_label + '->' + end_label)
    # The short natural timer is an independent native witness, never cleared
    # by the diagnostic. Only initial/final state are required, not offset ticks.
    natural_timer = dict.fromkeys(contract.get('natural_flag_positive_labels', []), 1)
    natural_timer.update(dict.fromkeys(contract.get('natural_flag_negative_labels', []), 0))
    for label, expected in natural_timer.items():
        lines = observation_lines.get(label, [])
        match = re.fullmatch(r'value=([01])', lines[0][1]) if len(lines) == 1 else None
        value = int(match[1]) if match else None
        values[label] = value
        if value != expected:
            failed_controls.append(label)
    marker_positive = all(values[label] == 1 for label in contract['marker_positive_labels'])
    marker_negative = all(values[label] == 0 for label in contract['marker_negative_labels'])
    control_positive = all(values[label] == 1 for label in contract['control_positive_labels'])
    control_negative = all(values[label] == 0 for label in contract['control_negative_labels'])
    controls_valid = not malformed and not failed_controls
    supported = controls_valid and marker_positive and marker_negative and control_positive and control_negative
    if not controls_valid:
        status = 'invalid_native_controls'
    elif supported:
        status = 'native_goal_identity_supported'
    elif (all(values[label] == 0 for label in contract['marker_positive_labels']) and marker_negative and
          all(values[label] == 0 for label in contract['control_positive_labels']) and control_negative):
        status = 'native_goal_storage_unsupported'
    elif all(values[label] == 0 for label in contract['marker_positive_labels']) and marker_negative and control_positive and control_negative:
        status = 'hidden_identity_goal_unsupported'
    else:
        status = 'native_goal_identity_inconsistent'
    return {'diagnostic_only': True, 'supported': supported, 'status': status,
            'controls_valid': controls_valid, 'failed_controls': failed_controls,
            'malformed_atomic_observations': malformed, 'native_atomic_values': values,
            'elapsed_game_time': clocks, 'has_ncns_dlc': values[contract['no_dlc_label']],
            'core_assertions_are_not_diagnostic_acceptance': True,
            'goal_id': contract['goal_id'], 'visible_control_goal_id': contract['visible_control_goal_id'],
            'limits': contract['limits']}
def edu_callback_result(contract, text, marker, observation_lines):
    """Require production callback actors/hooks within the actual EDU trace.

    Hook text outside this window or a later faction diagnostic cannot satisfy
    formation/departure acceptance. Country tokens are compared verbatim.
    """
    if not contract:
        return None
    failures = []
    endpoints = []
    for field in ('start_observation', 'end_observation', 'required_creation_actor_observation'):
        label = contract[field]
        lines = observation_lines.get(label, [])
        matches = list(re.finditer(re.escape(marker + ' OBS ' + label) + r'(?:\s|$)', text))
        if len(lines) != 1 or len(matches) != 1:
            failures.append({'missing_or_duplicate_edu_observation': label})
        endpoints.append(matches[0].start() if len(matches) == 1 else None)
    if any(value is None for value in endpoints) or not endpoints[0] < endpoints[2] < endpoints[1]:
        failures.append({'edu_callback_window_invalid': True})
        return {'passed': False, 'failures': failures}
    window = text[endpoints[0]:endpoints[1]]
    actor_rows = observation_lines[contract['required_creation_actor_observation']]
    actor_values = dict(re.findall(r'\b(actor|scope|sender)=([^\s]+)', actor_rows[0][1]))
    start_values = dict(re.findall(r'\b(actor|founder)=([^\s]+)', observation_lines[contract['start_observation']][0][1]))
    if not {'actor', 'scope'} <= set(actor_values) or actor_values.get('actor') != actor_values.get('scope') or actor_values.get('actor') in (None, '0', '0.0') or start_values.get('founder') != actor_values.get('actor') or start_values.get('actor') != start_values.get('founder'):
        failures.append({'invalid_edu_creation_actor_observation': actor_values})
    logs = {}
    for label in [contract['actual_creation_callback_log'], *contract['required_hook_logs']]:
        rows = [line for line in window.splitlines() if label + ' ' in line]
        logs[label] = rows
        if not rows:
            failures.append({'missing_actual_edu_callback_log': label})
        for line in rows:
            values = dict(re.findall(r'\b(actor|scope|sender)=([^\s]+)', line))
            if not values.get('actor') or values.get('actor') != values.get('scope'):
                failures.append({'edu_callback_actor_scope_mismatch': line})
    creation_rows = logs[contract['actual_creation_callback_log']]
    if creation_rows:
        values = dict(re.findall(r'\b(actor|scope|sender)=([^\s]+)', creation_rows[0]))
        # Non-targeted activation may reset FROM. Source intentionally ignores
        # it; preserve raw sender observations without inventing a pair gate.
        if any(values.get(key) != actor_values.get(key) for key in ('actor', 'scope')):
            failures.append({'edu_creation_callback_does_not_match_return_context': {'callback': values, 'return': actor_values}})
        if window.index(contract['actual_creation_callback_log']) >= endpoints[2] - endpoints[0]:
            failures.append({'edu_creation_callback_after_return': True})
    # New plain trace is explicitly bound by the v14 contract. Old v13
    # receipts retain their exact bracketed expectation and stay failures.
    commit_label = contract.get('authorized_formed_commit_log', '[EON EDU] FORMED_COMMIT')
    commits = logs.get(commit_label, [])
    expected_commits = contract['expected_authorized_formed_commits']
    if len(commits) != expected_commits:
        failures.append({'edu_authorized_commit_count': len(commits), 'expected': expected_commits})
    for line in commits:
        values = dict(re.findall(r'\b(actor|scope)=([^\s]+)', line))
        if values.get('actor') != actor_values.get('actor'):
            failures.append({'unexpected_edu_formed_commit_actor': line})
    return {'passed': not failures, 'failures': failures, 'creation_context': actor_values,
            'creation_callback_contexts': [dict(re.findall(r'\b(actor|scope|sender)=([^\s]+)', row)) for row in creation_rows],
            'hook_counts': {label: len(rows) for label, rows in logs.items()},
            'expected_authorized_formed_commits': expected_commits}


def extension_callback_result(contract, text, marker, observation_lines):
    """Require an actual native response delta, retaining raw no-op evidence.

    The optional second stage is a declared interface-removal calibration,
    followed by the same native activation API under current real gates. It
    never executes a copied complete_effect or a production handler fallback.
    """
    from decimal import Decimal, InvalidOperation
    if not contract:
        return None
    assert contract['schema'] == 1 and contract['actions']
    failures, receipts = [], []
    counts = ('answer', 'electorate', 'yes', 'no', 'abstain', 'approvals',
              'rejections', 'abstentions', 'queue', 'notice', 'project')
    delta_fields = ('answer', 'yes', 'no', 'abstain', 'approvals', 'rejections', 'abstentions')

    def row(label, kind='OBS', required=True):
        matches = list(re.finditer(re.escape(marker + ' ' + kind + ' ' + label) + r'(?:\s|$)([^\r\n]*)', text))
        if len(matches) != 1:
            if required or matches:
                failures.append({'extension_missing_or_duplicate_' + kind.lower(): label, 'count': len(matches)})
            return None, None
        payload = matches[0][1].strip()
        return dict(re.findall(r'\b([a-z_]+)=([^\s]+)', payload)), matches[0].start()

    def values(label):
        parsed, position = row(label)
        if parsed is None:
            return None, position
        # Bind both independently parsed witness forms; callers cannot submit
        # a receipt dictionary that disagrees with the actual engine text.
        rows = observation_lines.get(label, [])
        if len(rows) != 1 or dict(re.findall(r'\b([a-z_]+)=([^\s]+)', rows[0][1])) != parsed:
            failures.append({'extension_context_receipt_mismatch': label})
        try:
            for key in counts:
                value = Decimal(parsed[key])
                if not value.is_finite() or value != value.to_integral_value() or value < 0:
                    raise ValueError(key)
                parsed[key] = int(value)
        except (KeyError, ValueError, InvalidOperation):
            failures.append({'extension_invalid_counter_context': label})
            return None, position
        return parsed, position

    for action in contract['actions']:
        prior = len(failures)
        before, begin_at = values(action['before_observation'])
        raw, raw_at = values(action['raw_after_observation'])
        final, final_at = values(action['after_observation'])
        requested, request_at = row(action['requested_trace'], 'TRACE')
        calibration, calibration_at = row(action['calibration_before_observation'], required=False)
        remove, remove_at = row(action['remove_requested_trace'], 'TRACE', required=False)
        retry, retry_at = row(action['calibration_requested_trace'], 'TRACE', required=False)
        removal, removal_at = row(action['active_after_remove_observation'], required=False)
        stages = [item for item in (before, raw, final, requested) if item]
        if len(stages) != 4:
            receipts.append({'decision': action['decision'], 'passed': False})
            continue
        expected_actor, expected_target = before.get('expected_actor'), before.get('target')
        if expected_actor in (None, '0', '0.0') or expected_target in (None, '0', '0.0') or expected_actor == expected_target:
            failures.append({'extension_invalid_expected_country_tokens': action['before_observation']})
        for item in stages + [item for item in (calibration, remove, retry) if item]:
            if any(item.get(key) != expected for key, expected in
                   (('actor', expected_actor), ('scope', expected_actor), ('expected_actor', expected_actor),
                    ('target', expected_target), ('sender', expected_target))):
                failures.append({'extension_native_actor_target_context_mismatch': action['decision'], 'context': item})
        if not begin_at < request_at < raw_at < final_at:
            failures.append({'extension_raw_activation_order_invalid': action['decision']})
        for item in (before, raw, final):
            if item['queue'] != 0 or item['electorate'] <= 0 or item['notice'] <= 0 or item['project'] <= 0:
                failures.append({'extension_not_current_unqueued_context': action['decision']})
            if any(item[field] != before[field] for field in ('electorate', 'notice', 'project')):
                failures.append({'extension_serial_or_electorate_changed_during_activation': action['decision']})
        wanted = dict.fromkeys(delta_fields, 0)
        wanted['answer'] = wanted[action['increment_array']] = wanted[action['increment_counter']] = 1
        raw_delta = {field: raw[field] - before[field] for field in delta_fields}
        final_delta = {field: final[field] - before[field] for field in delta_fields}
        calibration_present = any(item is not None for item in (calibration, remove, retry, removal))
        committed_stage = None
        if raw_delta == wanted:
            committed_stage = 'initial_native_activation'
            if final_delta != wanted or calibration_present:
                failures.append({'extension_duplicate_or_changed_response_after_raw_commit': action['decision']})
        elif all(value == 0 for value in raw_delta.values()):
            committed_stage = 'declared_selected_decision_removal_calibration'
            if not all(item is not None for item in (calibration, remove, retry, removal)):
                failures.append({'extension_raw_noop_without_complete_native_calibration': action['decision']})
            else:
                calibrated, _ = values(action['calibration_before_observation'])
                if calibrated is None or any(calibrated[field] != raw[field] for field in counts):
                    failures.append({'extension_calibration_before_differs_from_raw_noop': action['decision']})
                if removal.get('value') != '0' or not raw_at < calibration_at < remove_at < removal_at < retry_at < final_at:
                    failures.append({'extension_native_removal_or_calibration_order_invalid': action['decision']})
            if final_delta != wanted:
                failures.append({'extension_calibrated_native_callback_delta_not_one': action['decision'], 'delta': final_delta})
        else:
            failures.append({'extension_raw_native_callback_delta_not_zero_or_one': action['decision'], 'delta': raw_delta})
        receipts.append({'decision': action['decision'], 'actor_tag': action['actor_tag'],
                         'target_tag': action['target_tag'], 'passed': len(failures) == prior,
                         'raw_activation_noop': all(value == 0 for value in raw_delta.values()),
                         'committed_stage': committed_stage, 'raw_delta': raw_delta, 'final_delta': final_delta})
    return {'passed': not failures, 'failures': failures, 'actions': receipts,
            'raw_native_noops': sum(item.get('raw_activation_noop', False) for item in receipts),
            'claims_excluded': ['GUI click', 'Native action result inferred from preexisting AI response', 'Copied handler fallback']}


def runtime_provenance_problems(manifest, source, private):
    """Verify original sidecars and active AI-only files as distinct evidence."""
    from runtime_override_support import (override_actions, validate_override_bytes,
                                          validate_override_maps)
    failures = []
    try:
        version = manifest['fixture_version']
        assert type(version) is int and version in (15, 16, 17, 18)
        assert manifest['marker'] == f'EON_EU_NATIVE_V{version}'
        actions = override_actions(version)
        if version == 15:
            from runtime_support import SOURCE_METHOD, GOLDEN114
        else:
            from extension_source_runtime_support import SOURCE_METHOD
            from runtime_support import GOLDEN114
        assert manifest['extension_runtime_method'] == SOURCE_METHOD
        assert manifest['negative_native109_history_preserved'] is True
        assert 'extension_callback_contract' not in manifest, 'Do not rewrite old API acceptance'
        contract = manifest['source_handler_runtime_contract']
        assert contract['schema'] == 1 and contract['method'] == SOURCE_METHOD and len(contract['actions']) == 30
        if version >= 16:
            assert contract['positive_dispatch'] == 'source-only; independent of raw API outcome'
            assert manifest['raw_api_diagnostic_contract']['diagnostic_only'] is True
        baseline = manifest['baseline114_contract']
        assert len(baseline['assertions']) == 114
        assert hashlib.sha256(json.dumps(baseline, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == manifest['baseline114_sha256'] == GOLDEN114
        assert all(label in manifest['assertions'] and manifest['expectations'][label] == baseline['expectations'][label] for label in baseline['assertions'])
        assert all(clock in manifest['required_elapsed_game_time'] for clock in baseline['required_elapsed_game_time'])
        if version >= 16:
            from edu_runtime_support import SOURCE_METHOD as EDU_METHOD, GOLDEN41
            if version>=17:
                from edu_confirmation_runtime_support import METHOD, MIGRATION, migrated_expectations
                assert manifest['edu_runtime_method']==METHOD
                assert manifest['baseline41_migration_map']==MIGRATION
            else:
                assert manifest['edu_runtime_method'] == EDU_METHOD
            edu_contract = manifest['edu_source_handler_runtime_contract']
            assert edu_contract['schema'] == 1 and edu_contract['method'] == EDU_METHOD
            assert edu_contract['positive_dispatch'] == 'source-only; independent of raw API outcome'
            assert len(edu_contract['actions']) == 15
            assert manifest['edu_raw_api_diagnostic_contract']['diagnostic_only'] is True
            original_edu = manifest['baseline41_contract']
            assert len(original_edu['assertions']) == 41
            assert hashlib.sha256(json.dumps(original_edu, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == manifest['baseline41_sha256'] == GOLDEN41
            if version>=17:
                expected_updates=migrated_expectations(original_edu['expectations'],'eon_native_eu_probe')
                for label in original_edu['assertions']:
                    if label in MIGRATION:
                        assert label not in manifest['assertions']
                        assert manifest['expectations'][MIGRATION[label]]==expected_updates[label]
                    else:
                        assert label in manifest['assertions'] and manifest['expectations'][label]==original_edu['expectations'][label]
                migrated=[MIGRATION.get(label,label) for label in original_edu['assertions']]
                assert [label for label in manifest['assertions'] if label in migrated]==migrated
                confirmation=manifest['edu_confirmation_contract']
                assert confirmation['schema']==1 and confirmation['method']==METHOD and confirmation['migration_map']==MIGRATION
                assert confirmation['expected_authorized_confirmations']==2
                assert confirmation['creation_stamps']==[a['stamp'] for a in edu_contract['actions'] if a['decision']=='EU_create_EDU' and a['gate_mode']=='positive']
                if version==18:
                    from fixture_isolation_runtime_support import REMOVE_LABEL,LEGACY_REMOVE,removal_contract,removal_expectation,cleanup_contract,validate_removal_fixture,validate_cleanup_fixture
                    isolation=manifest['edu_removal_isolation_contract']
                    assert isolation==removal_contract()
                    assert manifest['expectations'][REMOVE_LABEL]==removal_expectation('eon_native_eu_probe')
                    assert manifest['assertions'].index(REMOVE_LABEL)<manifest['assertions'].index(LEGACY_REMOVE)
                    cleanup=manifest['extension_cleanup_dispatch_contract']
                    assert cleanup==cleanup_contract()
                    fixture_module={'fixture_text':{'events/eon_native_eu_probe.txt':(private/'events/eon_native_eu_probe.txt').read_text('utf-8')},
                                    'expectations':manifest['expectations'],'edu_removal_isolation_contract':isolation,
                                    'extension_cleanup_dispatch_contract':cleanup}
                    validate_removal_fixture(fixture_module,'eon_native_eu_probe',manifest['marker'])
                    validate_cleanup_fixture(fixture_module,'eon_native_eu_probe',manifest['marker'])
            else:
                assert all(label in manifest['assertions'] and manifest['expectations'][label] == original_edu['expectations'][label] for label in original_edu['assertions'])
            assert all(clock in manifest['required_elapsed_game_time'] for clock in original_edu['required_elapsed_game_time'])
            assert [label for label in manifest['required_observations'] if label in original_edu['required_observations']] == original_edu['required_observations']
        validate_override_maps(manifest['runtime_overrides'], manifest['source_sha256'], manifest['effective_source_sha256'],
                               manifest['provenance_sha256'], manifest['fixture_sha256'], fixture_version=version)
        assert len(manifest['fixture_sha256']) == {15:7, 16:9,17:9,18:9}[version], 'Require exact version-specific fixture inventory'
        provenance = Path(manifest['provenance_root'])
        assert provenance.resolve() != source.resolve(), 'Run evidence needs independent immutable originals'
        for rel, ids in actions.items():
            original = (provenance / rel).read_bytes()
            active = (source / rel).read_bytes()
            receipt = validate_override_bytes(rel, original, active, ids, fixture_version=version)
            assert receipt == manifest['runtime_overrides'][rel]
            assert (private / rel).read_bytes() == active
    except (AssertionError, KeyError, OSError, ValueError, TypeError) as error:
        failures.append({'invalid_source_handler_provenance_contract': str(error)})
    return failures


def analyze(manifest_path, game_log, error_log, baseline_error_log=None):
    for path in (manifest_path, game_log, error_log):
        assert path.is_file(), 'Require an existing receipt/log: ' + str(path)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    assert manifest['kind'] == 'native_eu_lifecycle' and manifest['schema'] == 1
    marker, expected = manifest['marker'], manifest['assertions']
    assert len(expected) == len(set(expected)), 'Manifest assertions must be unique'
    assert set(manifest['expectations']) == set(expected), 'Every assertion needs an explicit expected result'
    text = game_log.read_text(encoding='utf-8-sig', errors='replace')
    pattern, problems = re.escape(marker), []
    startup = re.findall(pattern + r' STARTUP(?:\s|$)', text)
    beginnings = re.findall(pattern + r' RUN_BEGIN(?:\s|$)', text)
    endings = re.findall(pattern + r' RUN_END passes=([-0-9.]+) fails=([-0-9.]+)', text)
    for name, values in (('startup', startup), ('run_begin', beginnings), ('run_end', endings)):
        if len(values) != 1:
            problems.append({name + '_count': len(values), 'expected': 1})
    if manifest.get('fixture_version', 0) >= 13:
        expected_startup = marker + ' STARTUP fixture_version=' + str(manifest['fixture_version'])
        if len(re.findall(re.escape(expected_startup) + r'(?:\s|$)', text)) != 1:
            problems.append({'missing_exact_fixture_version_startup': expected_startup})
        # V1 is a prefix of V13. Match the old complete token, not startswith.
        if re.search(r'(?<![A-Za-z0-9_])EON_EU_NATIVE_V1(?:\s|$)', text):
            problems.append({'mixed_old_v1_probe_records': True})
    aborted = re.findall(pattern + r' ABORT([^\r\n]*)', text)
    if aborted:
        problems.append({'aborted': aborted})
    records = re.findall(pattern + r' (BEGIN|PASS|FAIL|END) ([A-Za-z0-9_]+)', text)
    names, counts = {label for status, label in records}, Counter(records)
    if names != set(expected):
        problems.append({'missing_assertions': sorted(set(expected) - names),
                         'unexpected_assertions': sorted(names - set(expected))})
    failed = []
    for label in expected:
        observed = [status for status, name in records if name == label]
        if observed not in (['BEGIN', 'PASS', 'END'], ['BEGIN', 'FAIL', 'END']):
            problems.append({'assertion': label, 'invalid_record_order_or_count': observed})
        if counts[('FAIL', label)]:
            failed.append(label)
    actual_order = [label for status, label in records if status == 'BEGIN']
    if actual_order != expected:
        problems.append({'assertion_order_mismatch': actual_order})
    normalized = [('RESULT' if status in ('PASS', 'FAIL') else status, label) for status, label in records]
    triplets = [(status, label) for label in expected for status in ('BEGIN', 'RESULT', 'END')]
    if normalized != triplets:
        problems.append({'interleaved_or_incomplete_assertion_triplets': True})
    pass_count, fail_count = sum(status == 'PASS' for status, name in records), sum(status == 'FAIL' for status, name in records)
    if len(endings) == 1 and tuple(float(value) for value in endings[0]) != (pass_count, fail_count):
        problems.append({'end_counter_mismatch': endings[0], 'observed': [pass_count, fail_count]})
    if failed:
        problems.append({'failed_assertions': failed})
    if len(beginnings) == len(endings) == 1:
        begin_at, end_at = text.index(marker + ' RUN_BEGIN'), text.index(marker + ' RUN_END')
        if end_at <= begin_at:
            problems.append({'end_before_begin': True})
        for match in re.finditer(pattern + r' (BEGIN|PASS|FAIL|END) ([A-Za-z0-9_]+)', text):
            if not begin_at < match.start() < end_at:
                problems.append({'record_outside_run': match.group(0)})

    source, private, docs = (Path(manifest[field]) for field in ('source_root', 'fixture_root', 'documentation_root'))
    runtime_mode = manifest.get('fixture_version', 0) >= 15
    if runtime_mode:
        problems.extend(runtime_provenance_problems(manifest, source, private))
    provenance = Path(manifest.get('provenance_root', str(source)))
    for field, directory in (('source_sha256', source), ('fixture_sha256', source), ('documentation_sha256', docs)):
        assert manifest[field], 'Hash binding must not be empty: ' + field
        for rel, digest in manifest[field].items():
            path = (provenance if runtime_mode and field == 'source_sha256' and rel in manifest.get('runtime_overrides', {}) else directory) / rel
            if not path.is_file():
                problems.append({'missing_bound_file': str(path), 'kind': field})
            elif sha(path) != digest:
                problems.append({'changed_bound_file': str(path), 'kind': field})
    if runtime_mode:
        for rel, digest in manifest.get('effective_source_sha256', {}).items():
            path = source / rel
            if not path.is_file() or sha(path) != digest:
                problems.append({'changed_effective_source_file': str(path)})
    for rel, digest in manifest['fixture_sha256'].items():
        path = private / rel
        if not path.is_file() or sha(path) != digest:
            problems.append({'changed_private_fixture': str(path)})

    errors = error_log.read_text(encoding='utf-8-sig', errors='replace')
    related = [line for line in errors.splitlines() if NEW_ERRORS.search(line) or LEGACY_ERRORS.search(line)]
    baseline, preexisting, new_related = Counter(), [], []
    if baseline_error_log is not None:
        assert baseline_error_log.is_file(), 'Require existing baseline error log'
        baseline = Counter(error_key(line) for line in baseline_error_log.read_text(encoding='utf-8-sig', errors='replace').splitlines()
                           if LEGACY_ERRORS.search(line) and not NEW_ERRORS.search(line))
    # New eon_eu compile/runtime errors are always fatal. Legacy errors may only
    # be excluded by exact message+source-line multiplicity from an explicit log.
    for line in related:
        key = error_key(line)
        if not NEW_ERRORS.search(line) and baseline[key] > 0:
            preexisting.append(line)
            baseline[key] -= 1
        else:
            new_related.append(line)
    if new_related:
        problems.append({'related_native_script_errors': new_related[:60], 'count': len(new_related)})
    observations = re.findall(pattern + r' OBS ([^\r\n]*)', text)
    diagnostic_counts, positions = {}, []
    for name in manifest.get('required_observations', []):
        matches = list(re.finditer(pattern + r' OBS ' + re.escape(name) + r'(?:\s|$)', text))
        diagnostic_counts[name] = len(matches)
        if len(matches) != 1:
            problems.append({'required_observation': name, 'count': len(matches), 'expected': 1})
        else:
            positions.append(matches[0].start())
    if positions != sorted(positions):
        problems.append({'required_observations_out_of_order': True})
    observation_lines = {}
    for line in text.splitlines():
        match = re.search(pattern + r' OBS ([A-Za-z0-9_]+)(?:\s+(.*))?$', line)
        if match:
            observation_lines.setdefault(match[1], []).append((line, match[2] or ''))
    extension_evidence = extension_callback_result(manifest.get('extension_callback_contract'), text, marker, observation_lines)
    if extension_evidence and not extension_evidence['passed']:
        problems.append({'extension_native_callback_contract_failed': extension_evidence})
    source_handler_evidence = None
    raw_api_evidence = None
    if runtime_mode:
        if manifest['fixture_version'] >= 16:
            from extension_source_runtime_support import source_handler_callback_result, raw_api_diagnostic_result
            raw_api_evidence = raw_api_diagnostic_result(manifest.get('raw_api_diagnostic_contract'), text, marker, observation_lines)
            if not raw_api_evidence or not raw_api_evidence['controls_valid']:
                problems.append({'invalid_raw_api_diagnostic_controls': raw_api_evidence})
        else:
            from runtime_support import source_handler_callback_result
        source_handler_evidence = source_handler_callback_result(manifest.get('source_handler_runtime_contract'), text, marker, observation_lines)
        if not source_handler_evidence or not source_handler_evidence['passed']:
            problems.append({'source_handler_runtime_contract_failed': source_handler_evidence})
    if manifest.get('fixture_version') in (17,18):
        from edu_confirmation_runtime_support import edu_confirmation_result
        edu_evidence=edu_confirmation_result(manifest.get('edu_confirmation_contract'),text,marker,observation_lines)
    else:
        edu_evidence = edu_callback_result(manifest.get('edu_native_callback_contract'), text, marker, observation_lines)
    if edu_evidence and not edu_evidence['passed']:
        problems.append({'edu_native_callback_contract_failed': edu_evidence})
    edu_source_evidence = None
    edu_raw_evidence = None
    removal_isolation_evidence=cleanup_dispatch_evidence=None
    if manifest.get('fixture_version')==18:
        from fixture_isolation_runtime_support import edu_removal_isolation_result,extension_cleanup_dispatch_result
        removal_isolation_evidence=edu_removal_isolation_result(manifest.get('edu_removal_isolation_contract'),text,marker)
        cleanup_dispatch_evidence=extension_cleanup_dispatch_result(manifest.get('extension_cleanup_dispatch_contract'),text,marker)
        for name,result in (('isolated_raw_removal',removal_isolation_evidence),('conditional_cleanup_dispatch',cleanup_dispatch_evidence)):
            if not result['passed']:problems.append({name+'_contract_failed':result})
    if manifest.get('fixture_version') in (16,17,18):
        from edu_runtime_support import edu_source_handler_callback_result, edu_raw_api_diagnostic_result
        edu_source_evidence = edu_source_handler_callback_result(manifest.get('edu_source_handler_runtime_contract'), text, marker, observation_lines)
        if not edu_source_evidence or not edu_source_evidence['passed']:
            problems.append({'edu_source_handler_runtime_contract_failed': edu_source_evidence})
        edu_raw_evidence = edu_raw_api_diagnostic_result(manifest.get('edu_raw_api_diagnostic_contract'), text, marker, observation_lines)
        if not edu_raw_evidence or not edu_raw_evidence['controls_valid']:
            problems.append({'invalid_edu_raw_api_diagnostic_controls': edu_raw_evidence})
        # The extracted constructor and actual confirmation/historical hook
        # evidence must describe the same country instance.
        if edu_source_evidence and edu_source_evidence['passed'] and edu_evidence and edu_evidence['passed']:
            first_stamp = manifest['edu_source_handler_runtime_contract']['actions'][0]['stamp']
            rows = re.findall(pattern + r' TRACE ' + re.escape(first_stamp + '_BEFORE_SOURCE_HANDLER') + r'(?:[ \t]|$)([^\r\n]*)', text, re.M)
            values = dict(re.findall(r'\b([a-z_]+)=([^\s]+)', rows[0])) if len(rows) == 1 else {}
            if values.get('actor') != edu_evidence['creation_context'].get('actor'):
                key=('edu_source_creation_actor_differs_from_confirmation' if manifest['fixture_version']>=17 else
                     'edu_source_creation_actor_differs_from_native_hook')
                problems.append({key:values.get('actor')})
        if len(beginnings) == len(endings) == 1:
            prefixes = tuple(action['stamp'] + '_' for key in ('source_handler_runtime_contract', 'edu_source_handler_runtime_contract')
                             for action in manifest[key]['actions']) + ('EXTENSION_RAW_NEGATIVE_', 'EDU_RAW_NEGATIVE_')
            for match in re.finditer(pattern + r' TRACE ([A-Za-z0-9_]+)', text):
                if match[1].startswith(prefixes) and not begin_at < match.start() < end_at:
                    problems.append({'source_runtime_trace_outside_run': match[1]})
    elapsed_game_time = []
    for contract in manifest.get('required_elapsed_game_time', []):
        start_label, end_label = contract['start_observation'], contract['end_observation']
        minimum = contract['minimum_hours']
        assert minimum > 0, 'Elapsed-time evidence must require positive advancement'
        assert start_label in manifest['required_observations'] and end_label in manifest['required_observations']
        start_lines, end_lines = observation_lines.get(start_label, []), observation_lines.get(end_label, [])
        start = game_timestamp(start_lines[0][0]) if len(start_lines) == 1 else None
        finish = game_timestamp(end_lines[0][0]) if len(end_lines) == 1 else None
        hours = (finish - start).total_seconds() / 3600 if start and finish else None
        receipt = {'start_observation': start_label, 'end_observation': end_label,
                   'start_game_date': start.isoformat() if start else None,
                   'end_game_date': finish.isoformat() if finish else None,
                   'elapsed_hours': hours, 'minimum_hours': minimum}
        elapsed_game_time.append(receipt)
        if hours is None or hours < minimum:
            problems.append({'missing_or_insufficient_actual_game_time': receipt})
    named_factions = []
    for contract in manifest.get('required_named_factions', []):
        label = contract['observation']
        assert label in manifest['required_observations']
        lines = observation_lines.get(label, [])
        values = dict(re.findall(r'(?:^|\s)([a-z]+)=(.*?)(?=\s[a-z]+=|$)', lines[0][1])) if len(lines) == 1 else {}
        observed = {member: values.get(member) for member in contract['members']}
        named_factions.append({'observation': label, 'members': observed, 'allowed_names': contract['allowed_names']})
        if not all(name in contract['allowed_names'] for name in observed.values()):
            problems.append({'required_nato_name_not_observed': named_factions[-1]})
    return {
        'passed': not problems, 'assertions_expected': len(expected), 'assertions_passed': pass_count,
        'assertions_failed': fail_count, 'failed_assertions': failed, 'problems': problems,
        'observations': observations, 'required_observation_counts': diagnostic_counts,
        'elapsed_game_time': elapsed_game_time, 'named_factions': named_factions,
        'diagnostic_result': faction_diagnostic_result(manifest.get('faction_identity_diagnostic'), observation_lines),
        'edu_callback_evidence': edu_evidence,
        'extension_callback_evidence': extension_evidence,
        'source_handler_runtime_evidence': source_handler_evidence,
        'raw_api_diagnostic_evidence': raw_api_evidence,
        'edu_source_handler_runtime_evidence': edu_source_evidence,
        'edu_removal_isolation_evidence': removal_isolation_evidence,
        'extension_cleanup_dispatch_evidence': cleanup_dispatch_evidence,
        'edu_raw_api_diagnostic_evidence': edu_raw_evidence,
        'marker': marker, 'countries': manifest['countries'], 'manifest_sha256': sha(manifest_path),
        'analyzer_sha256': sha(Path(__file__)),
        'game_log_sha256': sha(game_log), 'error_log_sha256': sha(error_log),
        'baseline_error_log_sha256': sha(baseline_error_log) if baseline_error_log else None,
        'related_script_errors': len(new_related), 'preexisting_related_script_errors': preexisting,
        'source_sha256': manifest['source_sha256'], 'limits': manifest['limits'],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--game-log', type=Path, required=True)
    parser.add_argument('--error-log', type=Path, required=True)
    parser.add_argument('--baseline-error-log', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Preserve previous native results'
    result = analyze(args.manifest, args.game_log, args.error_log, args.baseline_error_log)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('passed', 'assertions_expected', 'assertions_passed',
                                                 'assertions_failed', 'failed_assertions', 'problems')}))
    raise SystemExit(0 if result['passed'] else 1)
