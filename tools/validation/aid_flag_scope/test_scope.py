"""Exact aid selector repair: current AST, historical RED, and bounded mutants.

Run without options for current acceptance. --red observes the unchanged source
before the fix; --json emits the current receipt to stdout. No game writes.
"""
from copy import deepcopy
from pathlib import Path
import argparse
import hashlib
import json
import sys
import _model as m

ROOT = Path(__file__).resolve().parents[3]
SOURCE = 'common/scripted_triggers/eon_aid_triggers.txt'
DEPENDENCIES = [SOURCE, 'common/scripted_effects/eon_aid_effects.txt',
                'common/scripted_effects/eon_support_effects.txt']
BASELINE_SHA = '066696fa744e4c0651c19685aaa90b9d937a5af8afaa16a0fb7ddea35e2ee7ec'
OLD_LEGACY = '''\t\tNOT = {
\t\t\tOR = {
\t\t\t\thas_country_flag = sending_small_billion_@eon_aid_policy_donor
\t\t\t\thas_country_flag = sending_medium_billion_@eon_aid_policy_donor
\t\t\t\thas_country_flag = sending_high_billion_@eon_aid_policy_donor
\t\t\t\thas_country_flag = eon_aid_legacy_quarantined@eon_aid_policy_donor
\t\t\t}
\t\t}
'''.encode()
NEW_LEGACY = '''\t\tvar:eon_aid_policy_donor = {
\t\t\tPREV = {
\t\t\t\tNOT = {
\t\t\t\t\tOR = {
\t\t\t\t\t\thas_country_flag = sending_small_billion_@PREV
\t\t\t\t\t\thas_country_flag = sending_medium_billion_@PREV
\t\t\t\t\t\thas_country_flag = sending_high_billion_@PREV
\t\t\t\t\t\thas_country_flag = eon_aid_legacy_quarantined@PREV
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t}
'''.encode()
OLD_RETIRED = b'\t\tNOT = { has_country_flag = eon_aid_retired_pair@eon_aid_policy_donor }\n'
NEW_RETIRED = '''\t\tvar:eon_aid_policy_donor = {
\t\t\tPREV = { NOT = { has_country_flag = eon_aid_retired_pair@PREV } }
\t\t}
'''.encode()
PREFIXES = ('sending_small_billion_', 'sending_medium_billion_', 'sending_high_billion_',
            'eon_aid_legacy_quarantined', 'eon_aid_retired_pair')


def definitions(raw):
    return {key: body for key, operator, body in m.ast(raw.decode('utf-8-sig'))}


def walk(nodes):
    for node in nodes:
        yield node
        if isinstance(node[2], list):
            yield from walk(node[2])


def identity_case(source, prefix, location='recipient', peer='exact', gui=False):
    state, donor, recipient, other = m.fixture()
    owner = donor if location == 'donor' else recipient
    country = other if peer == 'other' else recipient if location == 'donor' else donor
    # Seed through native29-calibrated real scope suffix, never scalar aliases.
    writer_frame = m.context(donor, owner, from_=country)
    m.write_flags([('set_country_flag', '=', prefix + '@FROM')], state, writer_frame)
    name = 'eon_aid_gui_ready' if gui else 'eon_aid_retired_pair_available' if prefix == PREFIXES[-1] else 'eon_aid_legacy_pair_available'
    return m.evaluate(source, name, state, m.context(donor, recipient))


def red_failures(source):
    return [prefix for prefix in PREFIXES if identity_case(source, prefix)]


def draft_fixture():
    state, donor, recipient, other = m.fixture()
    state['temp']['eon_aid_proposed_amount'] = 5
    state['countries'][donor]['flags'].update(('eon_aid_reserved', 'eon_aid_draft_owner'))
    state['countries'][recipient]['flags'].update(('eon_aid_reserved', 'eon_aid_draft_recipient'))
    for actor, peer in ((donor, recipient), (recipient, donor)):
        state['countries'][actor]['vars'].update(eon_aid_partner=peer, eon_aid_amount=0, eon_aid_escrow=0)
    return state, donor, recipient, other


def validate(raw):
    source = definitions(raw)
    assert raw.count(NEW_LEGACY) == raw.count(NEW_RETIRED) == 1, 'Only two explicit source islands are allowed'
    inverse = raw.replace(NEW_LEGACY, OLD_LEGACY, 1).replace(NEW_RETIRED, OLD_RETIRED, 1)
    assert hashlib.sha256(inverse).hexdigest() == BASELINE_SHA, 'Unowned source bytes changed'
    assert not raw.startswith(b'\xef\xbb\xbf') and b'\r' not in raw, 'Preserve original no-BOM/LF'
    assert b'@eon_aid_policy_donor' not in raw
    old = definitions(inverse)
    historical = red_failures(old)
    assert historical == list(PREFIXES), historical
    checks = []

    def record(label, actual, wanted):
        assert actual == wanted, (label, actual, wanted)
        checks.append(label)

    state, donor, recipient, other = m.fixture()
    frame = m.context(donor, recipient)
    for name in ('eon_aid_national_policy_allowed', 'eon_aid_legacy_pair_available',
                 'eon_aid_retired_pair_available', 'eon_aid_gui_ready'):
        record('baseline_' + name, m.evaluate(source, name, state, frame), True)
    for prefix in PREFIXES:
        record(prefix + '_exact_pair', identity_case(source, prefix), False)
        record(prefix + '_other_pair', identity_case(source, prefix, peer='other'), True)
        record(prefix + '_gui_exact', identity_case(source, prefix, gui=True), False)
        record(prefix + '_gui_other', identity_case(source, prefix, peer='other', gui=True), True)
    record('donor_side_retired_exact', identity_case(source, PREFIXES[-1], location='donor'), False)
    record('donor_side_retired_other', identity_case(source, PREFIXES[-1], location='donor', peer='other'), True)
    for mode in ('unknown', 'absent'):
        varied = deepcopy(state)
        selected = 999 if mode == 'unknown' else donor
        varied['temp']['eon_aid_policy_donor'] = selected
        if mode == 'absent':
            varied['countries'][donor]['exists'] = False
        record(mode + '_national', m.evaluate(source, 'eon_aid_national_policy_allowed', varied, frame), False)
        record(mode + '_gui', m.evaluate(source, 'eon_aid_gui_ready', varied,
                                       m.context(selected, recipient)), False)
    # Preserve genuine national, war, budget, capacity, and reservation guards.
    for label, change in (
        ('recipient_war', lambda s: s['countries'][recipient]['wars'].add(donor)),
        ('donor_war', lambda s: s['countries'][donor]['wars'].add(recipient)),
        ('donor_cash_below5', lambda s: s['countries'][donor]['vars'].update(treasury=4.999)),
        ('missing_influence', lambda s: s['countries'][recipient]['arrays'].update(influence_array=[])),
        ('equal_civilian_capacity', lambda s: s['countries'][recipient]['vars'].update(num_of_civilian_factories=50)),
        ('insufficient_gdp_capacity', lambda s: s['countries'][recipient]['vars'].update(gdp_total=200)),
        ('recipient_reserved', lambda s: s['countries'][recipient]['flags'].add('eon_aid_reserved')),
        ('donor_reserved', lambda s: s['countries'][donor]['flags'].add('eon_aid_reserved')),
        ('national_eri_transitional', lambda s: (s['countries'][donor].update(tag='ERI', leader='Eritrean Transitional Government'), s['countries'][donor]['flags'].add('ETH_transitional_government_FLAG'))),
    ):
        varied = deepcopy(state)
        change(varied)
        record(label, m.evaluate(source, 'eon_aid_gui_ready', varied, frame), False)
    varied = deepcopy(state)
    varied['countries'][donor]['vars']['treasury'] = 5
    record('cash_exact5', m.evaluate(source, 'eon_aid_gui_ready', varied, frame), True)
    varied = deepcopy(state)
    varied['temp']['eon_aid_policy_donor'] = recipient
    record('self_national', m.evaluate(source, 'eon_aid_national_policy_allowed', varied, frame), False)
    draft, donor, recipient, other = draft_fixture()
    draft_frame = m.context(donor, donor, from_=recipient)
    record('actual_draft_gate_baseline', m.evaluate(source, 'eon_aid_draft_send_ready', draft, draft_frame), True)
    for prefix in PREFIXES:
        for peer, wanted in ((donor, False), (other, True)):
            varied = deepcopy(draft)
            m.write_flags([('set_country_flag', '=', prefix + '@FROM')], varied,
                          m.context(recipient, recipient, from_=peer))
            record(prefix + '_actual_draft_' + str(peer),
                   m.evaluate(source, 'eon_aid_draft_send_ready', varied, draft_frame), wanted)
    varied = deepcopy(state)
    # Literal scalar-name flags are wrong keys; they must not impersonate a
    # proper existing pair record or block every subsequent donor.
    varied['countries'][recipient]['flags'].update(prefix + '@eon_aid_policy_donor' for prefix in PREFIXES)
    record('literal_alias_flags_do_not_block_real_pair',
           m.evaluate(source, 'eon_aid_gui_ready', varied, frame), True)
    # Actual source quarantine writer (recipient ROOT, donor FROM), not a copied rule.
    aid = definitions((ROOT / DEPENDENCIES[1]).read_bytes())
    writers = [node for node in walk(aid['eon_aid_cancel_legacy_offer'])
               if node[0] == 'set_country_flag' and node[2] == 'eon_aid_legacy_quarantined@FROM']
    assert len(writers) == 1
    varied = deepcopy(state)
    m.write_flags(writers, varied, m.context(recipient, recipient, from_=donor))
    record('actual_quarantine_writer_exact', m.evaluate(source, 'eon_aid_legacy_pair_available', varied, frame), False)
    # Actual cleanup writer island: recipient -> stored donor -> PREV recipient.
    support = definitions((ROOT / DEPENDENCIES[2]).read_bytes())
    branches = [body for key, operator, body in support['eon_support_daily_cleanup'] if key == 'if']
    retirement = [node for branch in branches for node in branch
                  if node[0] == 'var:eon_aid_partner']
    assert len(retirement) == 1
    varied = deepcopy(state)
    varied['countries'][recipient]['vars']['eon_aid_partner'] = donor
    m.write_flags(retirement, varied, frame)
    record('actual_cleanup_retired_writer_exact', m.evaluate(source, 'eon_aid_retired_pair_available', varied, frame), False)
    # Each of five bounded scalar-read regressions must fail a targeted gate.
    rejected = []
    for prefix in PREFIXES:
        target = ('has_country_flag = ' + prefix + '@PREV').encode()
        needle = ('has_country_flag = ' + prefix + '@eon_aid_policy_donor').encode()
        assert raw.count(target) == (2 if prefix == PREFIXES[-1] else 1)
        mutant = definitions(raw.replace(target, needle, 1))
        assert identity_case(mutant, prefix), ('Scalar mutant undetected', prefix)
        rejected.append(prefix)
    # Removal of the unchanged reciprocal donor guard must also be detected.
    donor_guard = b'\t\tvar:eon_aid_policy_donor = { NOT = { has_country_flag = eon_aid_retired_pair@PREV } }\n'
    assert raw.count(donor_guard) == 1
    removed = definitions(raw.replace(donor_guard, b'', 1))
    assert identity_case(removed, PREFIXES[-1], location='donor'), 'Dropped donor guard mutant undetected'
    rejected.append('removed_existing_donor_retired_guard')
    # Each new outer donor -> PREV recipient roundtrip is essential: a direct
    # donor check reads another owner's flags and misses the recipient record.
    wrong_legacy = NEW_LEGACY.replace(b'\t\t\tPREV = {\n', b'', 1).replace(b'\t\t\t}\n\t\t}\n', b'\t\t}\n', 1)
    wrong_owner = definitions(raw.replace(NEW_LEGACY, wrong_legacy, 1))
    assert identity_case(wrong_owner, PREFIXES[0]), 'Wrong-owner mutant undetected'
    rejected.append('removed_recipient_roundtrip')
    # Country-variable aliases remain valid; only keyed FLAG suffixes are literal.
    record('temp_country_alias_roundtrip', m.value(state, frame, 'var:eon_aid_policy_donor'), donor)
    record('scalar_flag_remains_literal', m.flag(state, frame, PREFIXES[0] + '@eon_aid_policy_donor'), PREFIXES[0] + '@eon_aid_policy_donor')
    hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
              for path in DEPENDENCIES + ['tools/validation/aid_flag_scope/_model.py',
                                          'tools/validation/aid_flag_scope/test_scope.py']}
    return {'checks_passed': len(checks), 'historical_five_read_failures': historical,
            'bounded_mutants_rejected': rejected, 'source_sha256': hashes,
            'source_islands': 2, 'native_gameplay_proven': False,
            'limits': ['Current source gate execution only; no popup/refund/campaign claims',
                       'Native29 selector primitive informs adapter; native40 actual gates pending']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--red', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    raw = (ROOT / SOURCE).read_bytes()
    if args.red:
        result = {'source_sha256': hashlib.sha256(raw).hexdigest(),
                  'incorrectly_available_exact_pairs': red_failures(definitions(raw)),
                  'native_gameplay_proven': False}
        print(json.dumps(result, indent=2))
        assert result['incorrectly_available_exact_pairs'] == list(PREFIXES)
        sys.exit(1)  # Intentionally RED: every expected exact-pair restriction fails.
    result = validate(raw)
    print(json.dumps(result, indent=2) if args.json else
          f"Aid flag scope: {result['checks_passed']} gates/controls PASS; five old defects and seven bounded mutants reproduced.")
