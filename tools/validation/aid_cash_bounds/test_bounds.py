"""Current aid AST treasury guards and exact historical byte islands; no game."""
from pathlib import Path
from copy import deepcopy
import importlib.util
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
path = ROOT / 'tools/validation/aid_flag_scope/_model.py'
spec = importlib.util.spec_from_file_location('aid_cash_scope_model', path)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from byte_compat import before_aid_cash_bounds, JOURNAL
raw = (ROOT / JOURNAL['path']).read_bytes()
old = before_aid_cash_bounds(JOURNAL['path'], raw)
current = {k: v for k, o, v in m.ast(raw.decode('utf-8-sig'))}
previous = {k: v for k, o, v in m.ast(old.decode('utf-8-sig'))}
original_trigger = m.trigger

def trigger(nodes, state, frame, definitions):
    for node in nodes:
        key, op, body = node
        if key == 'add_to_temp_variable':
            name, operator, source = body[0]
            assert operator == '='
            state['temp'][name] = m.value(state, frame, name) + m.value(state, frame, source)
        elif not original_trigger([node], state, frame, definitions):
            return False
    return True
m.trigger = trigger

def draft(wallet):
    state, donor, recipient, other = m.fixture()
    state['countries'][donor]['vars']['treasury'] = wallet
    state['countries'][donor]['flags'].update(('eon_aid_reserved', 'eon_aid_draft_owner'))
    state['countries'][recipient]['flags'].update(('eon_aid_reserved', 'eon_aid_draft_recipient'))
    state['countries'][donor]['vars'].update(eon_aid_partner=recipient, eon_aid_amount=0, eon_aid_escrow=0)
    state['countries'][recipient]['vars'].update(eon_aid_partner=donor, eon_aid_amount=0)
    state['temp']['eon_aid_proposed_amount'] = 5
    return state, m.context(donor, donor, from_=recipient)

checks = 0
for wallet, allowed in ((4.99, False), (5, True), (1000000, True), (1000000.01, False), (1000035, False)):
    state, frame = draft(wallet)
    assert m.trigger(current['eon_aid_draft_send_ready'], deepcopy(state), frame, current) == allowed
    if wallet > 1000000:
        assert m.trigger(previous['eon_aid_draft_send_ready'], deepcopy(state), frame, previous)
    checks += 1

for wallet, amount, allowed in ((-1000000, 5, True), (-1000000.01, 5, False),
                               (-1000035, 5, False), (999995, 5, True), (999995.01, 5, False),
                               (999985, 15, True), (999965, 35, True)):
    state, donor, recipient, other = m.fixture()
    state['countries'][recipient]['vars'].update(treasury=wallet, eon_aid_amount=amount)
    frame = m.context(recipient, recipient, from_=donor)
    assert m.trigger(current['eon_aid_recipient_capacity_available'], deepcopy(state), frame, current) == allowed
    if wallet < -1000000:
        assert m.trigger(previous['eon_aid_recipient_capacity_available'], deepcopy(state), frame, previous)
    checks += 1

# Both new lines are necessary: removing either must reproduce its bad boundary.
for edit in JOURNAL['edits']:
    altered = raw.replace(bytes.fromhex(edit['after']), bytes.fromhex(edit['before']), 1)
    try: before_aid_cash_bounds(JOURNAL['path'], altered)
    except AssertionError: pass
    else: raise AssertionError('Adapter accepted an incomplete guard patch')
    checks += 1
assert b'\r' not in raw and not raw.startswith(b'\xef\xbb\xbf')
print(json.dumps({'checks': checks, 'new_guard_lines': 2,
 'source_sha256': hashlib.sha256(raw).hexdigest(), 'historical_view_sha256': hashlib.sha256(old).hexdigest(),
 'proof_scope': 'current AST gates and narrowly digest-bound byte projection; native campaign unverified'}, indent=2))
