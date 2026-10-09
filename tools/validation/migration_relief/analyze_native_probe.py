"""Validate a complete native migration trace against its frozen source bytes."""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import re


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze(manifest_path, game_log, error_log):
    for path in (manifest_path, game_log, error_log):
        assert path.is_file(), 'Require an existing receipt/log: ' + str(path)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    assert manifest['kind'] == 'native_migration_relief' and manifest['schema'] == 1
    marker = manifest['marker']
    expected = manifest['assertions']
    assert len(expected) == len(set(expected)), 'Manifest assertions must be unique'
    assert set(manifest['expectations']) == set(expected), 'Every assertion requires an explicit expected result'
    text = game_log.read_text(encoding='utf-8-sig', errors='replace')
    problems = []
    pattern = re.escape(marker)
    startup = re.findall(pattern + r' STARTUP(?:\s|$)', text)
    beginnings = re.findall(pattern + r' RUN_BEGIN(?:\s|$)', text)
    endings = re.findall(pattern + r' RUN_END passes=([-0-9.]+) fails=([-0-9.]+)', text)
    if len(startup) != 1: problems.append({'startup_count': len(startup), 'expected': 1})
    if len(beginnings) != 1: problems.append({'run_begin_count': len(beginnings), 'expected': 1})
    if len(endings) != 1: problems.append({'run_end_count': len(endings), 'expected': 1})
    aborted = re.findall(pattern + r' ABORT([^\r\n]*)', text)
    if aborted: problems.append({'aborted': aborted})
    records = re.findall(pattern + r' (BEGIN|PASS|FAIL|END) ([A-Za-z0-9_]+)', text)
    names = {label for status, label in records}
    if names != set(expected):
        problems.append({'missing_assertions': sorted(set(expected) - names),
                         'unexpected_assertions': sorted(names - set(expected))})
    counts = Counter(records)
    failed = []
    for label in expected:
        observed = [status for status, name in records if name == label]
        if observed not in (['BEGIN', 'PASS', 'END'], ['BEGIN', 'FAIL', 'END']):
            problems.append({'assertion': label, 'invalid_record_order_or_count': observed})
        if counts[('FAIL', label)]: failed.append(label)
    # Assertion order also binds setup→primitive gate→core transitions. A pasted
    # result from another run cannot compensate for missing/interleaved records.
    actual_order = [label for status, label in records if status == 'BEGIN']
    if actual_order != expected: problems.append({'assertion_order_mismatch': actual_order})
    normalized = [('RESULT' if status in ('PASS', 'FAIL') else status, label) for status, label in records]
    triplets = [(status, label) for label in expected for status in ('BEGIN', 'RESULT', 'END')]
    if normalized != triplets: problems.append({'interleaved_or_incomplete_assertion_triplets': True})
    pass_count = sum(status == 'PASS' for status, name in records)
    fail_count = sum(status == 'FAIL' for status, name in records)
    if len(endings) == 1:
        claimed = tuple(float(value) for value in endings[0])
        if claimed != (pass_count, fail_count):
            problems.append({'end_counter_mismatch': claimed, 'observed': [pass_count, fail_count]})
    if failed: problems.append({'failed_assertions': failed})
    if len(beginnings) == len(endings) == 1:
        begin_at = text.index(marker + ' RUN_BEGIN')
        end_at = text.index(marker + ' RUN_END')
        if end_at <= begin_at: problems.append({'end_before_begin': True})
        for match in re.finditer(pattern + r' (BEGIN|PASS|FAIL|END) ([A-Za-z0-9_]+)', text):
            if not begin_at < match.start() < end_at:
                problems.append({'record_outside_run': match.group(0)})

    source = Path(manifest['source_root'])
    private = Path(manifest['fixture_root'])
    docs = Path(manifest['documentation_root'])
    for field, directory in (('source_sha256', source), ('fixture_sha256', source),
                             ('documentation_sha256', docs)):
        for rel, digest in manifest[field].items():
            path = directory / rel
            if not path.is_file(): problems.append({'missing_bound_file': str(path), 'kind': field})
            elif sha(path) != digest: problems.append({'changed_bound_file': str(path), 'kind': field})
    # The installed frozen fixture and the builder receipt must both match.
    for rel, digest in manifest['fixture_sha256'].items():
        path = private / rel
        if not path.is_file() or sha(path) != digest:
            problems.append({'changed_private_fixture': str(path)})
    errors = error_log.read_text(encoding='utf-8-sig', errors='replace')
    related = [line for line in errors.splitlines() if re.search(
        r'eon_native_migration|EON_MIGRATION_NATIVE|eon_migration|eon_refugee|eon_humanitarian|'
        r'MDC_migration|migration_agreement|eon_labor|00_migrants_on_actions|'
        r'00_state_population_monthly_on_actions', line, re.I)]
    if related: problems.append({'related_native_script_errors': related[:50], 'count': len(related)})
    observations = re.findall(pattern + r' OBS ([^\r\n]*)', text)
    required_observations = manifest.get('required_observations', [])
    diagnostic_counts, diagnostic_positions = {}, []
    for name in required_observations:
        matches = list(re.finditer(pattern + r' OBS ' + re.escape(name) + r'(?:\s|$)', text))
        diagnostic_counts[name] = len(matches)
        if len(matches) != 1:
            problems.append({'required_observation': name, 'count': len(matches), 'expected': 1})
        else:
            diagnostic_positions.append(matches[0].start())
    if len(diagnostic_positions) == len(required_observations) and diagnostic_positions != sorted(diagnostic_positions):
        problems.append({'required_observations_out_of_order': required_observations})
    return {
        'passed': not problems, 'assertions_expected': len(expected),
        'assertions_passed': pass_count, 'assertions_failed': fail_count,
        'failed_assertions': failed, 'problems': problems, 'observations': observations,
        'required_observation_counts': diagnostic_counts,
        'marker': marker, 'countries': manifest['countries'],
        'manifest_sha256': sha(manifest_path), 'game_log_sha256': sha(game_log),
        'error_log_sha256': sha(error_log), 'related_script_errors': len(related),
        'source_sha256': manifest['source_sha256'], 'limits': manifest['limits'],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--game-log', type=Path, required=True)
    parser.add_argument('--error-log', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Preserve previous native results'
    result = analyze(args.manifest, args.game_log, args.error_log)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('passed', 'assertions_expected', 'assertions_passed',
                                                 'assertions_failed', 'failed_assertions', 'problems')}))
    raise SystemExit(0 if result['passed'] else 1)
