"""Current actual-AST checks and known-bad source replay; emits one JSON object."""
from pathlib import Path
import hashlib
import io
import json
import sys
import unittest

import _support as s
import _source_guard as g
from test_lifecycle import ConsultationLifecycle
from test_source import SourceBoundaries

ORIGINAL_METHODS = (
    'test_native_flag_literal_scalar_and_scope_are_distinct',
    'test_retired_gate_checks_each_actual_direction_and_ignores_wrong_pair',
    'test_draft_expiry_keeps_original_reservation_until_cancel_or_stale_send',
    'test_expired_request_consumes_original_reply_without_agreement_or_extra_pp',
    'test_expiry_markers_fail_closed_even_if_time_windows_restored',
    'test_wrong_peer_or_topic_cannot_consume_reserved_expired_modal',
    'test_withdraw_and_expired_reason_are_distinct_and_repeat_callbacks_inert',
    'test_dead_corrupt_and_annex_records_keep_exact_pair_retirement',
    'test_active_close_war_and_time_expiry_preserve_separate_contracts',
)


class CountResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = 0
        self.subcases = 0

    def startTest(self, test):
        super().startTest(test)
        self.subcases = 0

    def addSubTest(self, test, subtest, error):
        self.cases += 1
        self.subcases += 1
        super().addSubTest(test, subtest, error)

    def stopTest(self, test):
        if not self.subcases:
            self.cases += 1
        super().stopTest(test)


def evaluate(base, overrides=None, methods=None):
    case = type('SourceCase', (base,), {'overrides': overrides})
    suite = (unittest.TestSuite(case(name) for name in methods) if methods
             else unittest.defaultTestLoader.loadTestsFromTestCase(case))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, resultclass=CountResult).run(suite)
    return {'checks_passed': result.wasSuccessful(), 'methods': result.testsRun,
            'cases': result.cases, 'failures': len(result.failures), 'errors': len(result.errors)}, stream.getvalue()


def mutant(relative, helper, old, new):
    entry = g.load_journal()['files'][relative]
    island = next(item for item in entry['islands'] if item['name'] == helper)
    before = island['after']
    assert before.count(old) == 1, (helper, old, before.count(old))
    after = before.replace(old, new)
    raw = (s.ROOT / relative).read_bytes()
    assert raw.count(before.encode()) == 1
    return {relative: raw.replace(before.encode(), after.encode())}


def main():
    reports, diagnostics = {}, []
    for name, cls in (('lifecycle', ConsultationLifecycle), ('source', SourceBoundaries)):
        reports[name], message = evaluate(cls)
        if not reports[name]['checks_passed']:
            diagnostics.append(message)

    old, message = evaluate(ConsultationLifecycle, g.baseline_sources(), ORIGINAL_METHODS)
    red = {'old_source_rejected': not old['checks_passed'], **old,
           'baseline_sha256': {path: item['before_sha256'] for path, item in g.load_journal()['files'].items()}}
    assert red['old_source_rejected'] and red['failures'] == 13 and red['errors'] == 0, ('Unexpected old-source reproduction', red, message)
    red['checks_passed'] = True

    effects, triggers = s.FILES
    rows = []
    # Restore the two exact old causal branches independently.
    for relative, helper, method in (
        (effects, 'eon_consultation_daily_cleanup', ORIGINAL_METHODS[2]),
        (triggers, 'eon_consultation_base_pair_available', ORIGINAL_METHODS[1]),
    ):
        island = next(i for i in g.load_journal()['files'][relative]['islands'] if i['name'] == helper)
        rows.append((helper + '_old', {relative: (s.ROOT / relative).read_bytes().replace(island['after'].encode(), island['before'].encode())}, method))
    rows += [
        ('expired_clear_missing', mutant(effects, 'eon_consultation_clear_pending', '\tclr_country_flag = eon_consultation_expired\n', ''), ORIGINAL_METHODS[3]),
        ('expired_notice_wrong', mutant(effects, 'eon_consultation_resolve_invalid_request', 'country_event = eon_consultation.26', 'country_event = eon_consultation.24'), ORIGINAL_METHODS[3]),
        ('invalid_pair_guard_missing', mutant(effects, 'eon_consultation_resolve_invalid_request', 'limit = { eon_consultation_response_pair_current = yes }', 'limit = { always = yes }'), ORIGINAL_METHODS[5]),
        ('expiry_not_bilateral', mutant(effects, 'eon_consultation_daily_cleanup', '\t\t\tvar:eon_consultation_partner = { set_country_flag = eon_consultation_expired }\n', ''), ORIGINAL_METHODS[3]),
        ('expired_force_withdraw', mutant(effects, 'eon_consultation_withdraw_request', '\n\t\t\tNOT = { has_country_flag = eon_consultation_expired }\n', '\n'), 'test_force_withdraw_expired_and_end_pending_do_not_release_original'),
    ]
    # Force-withdraw must lose both its independent execution guards to regress.
    entry = rows[-1][1][effects]
    rows[-1][1][effects] = entry.replace(b'\t\t\t\tNOT = { has_country_flag = eon_consultation_expired }\n', b'')
    for helper in ('eon_consultation_draft_send_ready', 'eon_consultation_response_valid', 'eon_consultation_withdraw_available'):
        for indent, side in (('\t', 'owner'), ('\t\t', 'peer')):
            rows.append((helper + '_' + side + '_expired_guard_missing',
                mutant(triggers, helper, '\n' + indent + 'NOT = { has_country_flag = eon_consultation_expired }\n', '\n'), ORIGINAL_METHODS[4]))
    mutant_reports = []
    for name, source, method in rows:
        report, message = evaluate(ConsultationLifecycle, source, (method,))
        assert not report['checks_passed'] and not report['errors'], ('Mutant was not rejected by its behavioral oracle', name, report, message)
        mutant_reports.append({'name': name, 'rejected': True, 'failures': report['failures']})

    paths = [*s.FILES, 'common/scripted_diplomatic_actions/eon_consultation_actions.txt',
             'events/eon_consultation_events.txt', 'common/on_actions/eon_consultation_on_actions.txt',
             'tools/validation/diplomacy_channel_ui/_support.py',
             'tools/validation/diplomacy_package_07/test_consultations.py',
             'tools/validation/diplomacy_package_01/test_energy.py']
    sources = {path: g.sha((s.ROOT / path).read_bytes()) for path in paths}
    output = {'checks_passed': all(item['checks_passed'] for item in reports.values()),
              'cases': sum(item['cases'] for item in reports.values()), 'checks': reports,
              'red': red, 'mutants': mutant_reports, 'sources': sources,
              'source_islands': 10, 'native_acceptance_proven': False,
              'proof_scope': 'Current source AST, calibrated FLAG/shared-temp primitives and exact byte boundaries; explicit fixture expiry, backend option execution. Native delivery, clock, AI, GUI, saves and multiplayer are not simulated.'}
    for message in diagnostics:
        print(message, file=sys.stderr)
    print(json.dumps(output, ensure_ascii=False))
    return 0 if output['checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
