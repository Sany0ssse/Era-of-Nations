"""Execute current humanitarian AST and actual treasury helper, not HOI4 runtime.

Uses the retained bounded executor definitions without running historical suites.
Native reply consent and timer expiration are explicit inputs to these scenarios.
Migration initialization is an asserted no-op for preregistered canonical fixtures;
the registry and copied-balance cleanup AST are not executed by this model.
"""
from pathlib import Path
from copy import deepcopy
from collections import Counter
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/validation/diplomacy_package_01'))
executor = ROOT / 'tools/validation/diplomacy_package_01/test_energy.py'
text = executor.read_text(encoding='utf-8-sig')
boundary = '\ndef state():'
assert text.count(boundary) == 1
m = {'__file__': str(executor), '__name__': 'humanitarian_current_ast_executor'}
exec(compile(text.split(boundary)[0], str(executor), 'exec'), m)
ast, one, context, switch = (m[name] for name in ('ast', 'one', 'context', 'switch'))
base_trigger, base_execute = m['trigger'], m['execute']
paths = [
 'common/scripted_triggers/eon_humanitarian_aid_triggers.txt',
 'common/scripted_effects/eon_humanitarian_aid_effects.txt',
 'common/scripted_diplomatic_actions/eon_humanitarian_aid_actions.txt',
 'common/on_actions/eon_humanitarian_aid_on_actions.txt',
 'events/eon_humanitarian_aid_events.txt',
 'common/scripted_effects/00_budget_effects.txt',
]
read = lambda path: (ROOT / path).read_text(encoding='utf-8-sig')
m['capacity_triggers'] = {key: body for key, op, body in ast(read(paths[0]))}
m['effects'] = {key: body for key, op, body in ast(read(paths[1]))}
m['effects']['modify_treasury_effect'] = one(ast(read(paths[-1])), 'modify_treasury_effect')
actions = one(ast(read(paths[2])), 'scripted_diplomatic_actions')
offer = one(actions, 'eon_offer_humanitarian_aid')
withdraw = one(actions, 'eon_withdraw_humanitarian_aid')
hooks = one(ast(read(paths[3])), 'on_actions')
groups = Counter()
registration_source = 'common/scripted_effects/eon_migration_relief_effects.txt'

def trigger(nodes, result, frame):
    index = 0
    while index < len(nodes):
        key, op, body = nodes[index]; index += 1
        grouped = [(key, op, body)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        country = result['countries'][frame['scope']]
        if key == 'is_subject': passed = country['subject'] == (body == 'yes')
        elif key == 'has_war': passed = bool(country['wars']) == (body == 'yes')
        elif key == 'has_country_leader': passed = country.get('leader', 'Ordinary') == one(body, 'name')
        else: passed = base_trigger(grouped, result, frame)
        if not passed: return False
    return True

def execute(nodes, result, frame):
    index = 0
    while index < len(nodes):
        key, op, body = nodes[index]; index += 1
        grouped = [(key, op, body)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        if key == 'eon_migration_initialize_country':
            # This adapter covers only an already registered, initialized token.
            # Real registration/recovery/copy_tag cleanup belongs to flow tests
            # and native probes; never silently simulate those branches here.
            assert op == '=' and body == 'yes'
            country = result['countries'][frame['scope']]
            slot = country['variables'].get('eon_migration_origin_slot', 0)
            origins = result['preregistered_origins']
            assert isinstance(slot, int) and 0 < slot < len(origins), 'Fixture is not preregistered'
            assert origins[slot] == frame['scope'], 'Fixture origin slot is not canonical'
            assert 'eon_migration_relief_initialized' in country['flags'], 'Fixture is not initialized'
            result['initialization_calls'].append(frame['scope'])
            result['effect_trace'].append(('preregistered_initialization', frame['scope']))
        elif key == 'every_country':
            limits = [v for k, o, v in body if k == 'limit']
            for actor, country in result['countries'].items():
                inner = switch(frame, actor)
                if country['exists'] and (not limits or trigger(limits[0], result, inner)):
                    execute([node for node in body if node[0] != 'limit'], result, inner)
        else:
            if key == 'modify_treasury_effect':
                assert 'eon_humanitarian_aid_pending' not in result['countries'][frame['scope']]['flags'], 'Record was not consumed before debit'
                result['debits'].append(frame['scope'])
                result['effect_trace'].append(('debit', frame['scope']))
            if key == 'set_variable' and isinstance(body, list) and body[0][0] == 'eon_humanitarian_aid_partner':
                result['effect_trace'].append(('offer_record', frame['scope']))
            if key == 'add_to_variable' and isinstance(body, list) and body[0][0] == 'eon_refugee_relief_fund':
                result['effect_trace'].append(('fund_credit', frame['scope']))
            if key == 'set_country_flag' and isinstance(body, list):
                result['timers'].append((frame['scope'], one(body, 'flag'), float(one(body, 'days'))))
            base_execute(grouped, result, frame)

m['trigger'], m['execute'] = trigger, execute

def state(treasury=1, fund=0, hosted=10000, war=False):
    result = {'countries': {}, 'temp': {}, 'events': [], 'recalculations': [], 'ui_updates': 0,
              'debits': [], 'timers': [], 'initialization_calls': [], 'effect_trace': [],
              'preregistered_origins': [0, 101, 202, 303, 404]}
    for slot, identity in enumerate((101, 202, 303, 404), 1):
        result['countries'][identity] = {'variables': {'treasury': treasury, 'eon_refugee_relief_fund': 0,
          'eon_refugees_hosted': hosted, 'gdp_total': 20, 'num_of_civilian_factories': 5,
          'eon_migration_origin_slot': slot, 'eon_refugee_policy': 1},
          'arrays': {'influence_array': [101]}, 'flags': {'eon_migration_relief_initialized'}, 'wars': set(),
          'exists': True, 'ai': False, 'subject': False}
    result['countries'][101]['variables'].update(gdp_total=100, num_of_civilian_factories=50)
    result['countries'][202]['variables']['eon_refugee_relief_fund'] = fund
    if war: result['countries'][202]['wars'].add(404)
    return result

def vars_(result, actor=101): return result['countries'][actor]['variables']
def flags(result, actor=101): return result['countries'][actor]['flags']
def frame(donor=101, recipient=202): return context(donor, scope=recipient)
def run(result, body, donor=101, recipient=202):
    result['temp'] = {}; execute(body, result, frame(donor, recipient))
def ready(result, donor=101, recipient=202):
    result['temp'] = {}; return trigger(one(offer, 'can_be_sent'), result, frame(donor, recipient))
def send(result, donor=101, recipient=202): run(result, one(offer, 'on_sent_effect'), donor, recipient)
def reply(result, accepted=True, donor=101, recipient=202):
    run(result, one(offer, 'complete_effect' if accepted else 'reject_effect'), donor, recipient)
def daily(result, donor=101):
    result['temp'] = {}; execute(one(one(hooks, 'on_daily'), 'effect'), result, context(donor))
def balance(result):
    return sum(c['variables'].get('treasury', 0) + c['variables'].get('eon_refugee_relief_fund', 0)
               for c in result['countries'].values())
def cash_snapshot(result):
    return [(actor, vars_(result, actor).get('treasury', 0), vars_(result, actor).get('eon_refugee_relief_fund', 0))
            for actor in result['countries']]

# Inspect current integration order without executing the migration registry.
# A copied balance must be retired before the ready check and first backed grant;
# the complete cleanup behavior is outside these canonical-fixture scenarios.
send_body = m['effects']['eon_humanitarian_aid_send_offer']
assert send_body[0] == ('eon_migration_initialize_country', '=', 'yes')
assert one(one(send_body, 'if'), 'limit') == [('eon_humanitarian_aid_offer_ready', '=', 'yes')]
initialize_body = one(ast(read(registration_source)), 'eon_migration_initialize_country')
assert initialize_body[0] == ('eon_migration_register_country', '=', 'yes')
assert 'eon_migration_initialize_country' not in m['effects']
groups['registration_before_offer_source_boundary'] += 1

result = state(fund=.25); before = cash_snapshot(result)
send(result)
assert result['initialization_calls'] == [202]
assert result['effect_trace'] == [('preregistered_initialization', 202), ('offer_record', 101)]
assert cash_snapshot(result) == before and not result['debits']
reply(result)
assert result['effect_trace'] == [('preregistered_initialization', 202), ('offer_record', 101),
                                  ('debit', 101), ('fund_credit', 202)]
assert abs(vars_(result, 202)['eon_refugee_relief_fund'] - .35) < 1e-8
groups['preregistered_recipient_hook_order_no_prepayment'] += 1

for invalid in ('uninitialized', 'wrong_token', 'invalid_slot'):
    result = state()
    if invalid == 'uninitialized': flags(result, 202).discard('eon_migration_relief_initialized')
    elif invalid == 'wrong_token': result['preregistered_origins'][2] = 303
    else: vars_(result, 202)['eon_migration_origin_slot'] = 0
    before = deepcopy(result['countries'])
    try:
        send(result)
    except AssertionError:
        pass
    else:
        raise AssertionError('The no-op adapter accepted a noncanonical fixture')
    assert result['countries'] == before and not result['initialization_calls']
    groups['registration_noop_rejects_outside_fixture_contract'] += 1

for hosted, war in ((10000, False), (0, True), (0, False)):
    result = state(hosted=hosted, war=war); before = cash_snapshot(result)
    assert ready(result) == (hosted > 0 or war)
    send(result); assert cash_snapshot(result) == before
    reply(result)
    if hosted or war:
        assert abs(vars_(result)['treasury'] - .9) < 1e-8
        assert abs(vars_(result, 202)['eon_refugee_relief_fund'] - .1) < 1e-8
        assert vars_(result, 202)['treasury'] == 1
        assert len(result['debits']) == 1
        assert 'eon_humanitarian_aid_cooldown@202' in flags(result)
        assert (101, 'eon_humanitarian_aid_live', 30) in result['timers']
        assert (101, 'eon_humanitarian_aid_cooldown@PREV', 180) in result['timers']
    else: assert cash_snapshot(result) == before
    assert abs(balance(result) - 4) < 1e-8
    after = cash_snapshot(result); reply(result); reply(result, False)
    assert cash_snapshot(result) == after
    groups['need_consent_conservation_and_replay'] += 1

for amount, fund, allowed in ((.099, 0, False), (.1, 0, True), (1000000, 9.9, True),
                             (1000000.1, 0, False), (1, 9.90001, False), (1, -1, False)):
    result = state(treasury=amount, fund=fund)
    assert ready(result) == allowed
    before = balance(result); send(result); reply(result)
    assert abs(balance(result) - before) < 1e-7
    assert bool(result['debits']) == allowed
    groups['cash_and_restricted_fund_boundaries'] += 1

for change in ('cash_spent', 'fund_filled', 'negative_fund', 'no_need', 'bilateral_war', 'donor_subject', 'donor_dead', 'recipient_dead'):
    result = state(); send(result)
    if change == 'cash_spent': vars_(result)['treasury'] = .09
    elif change == 'fund_filled': vars_(result, 202)['eon_refugee_relief_fund'] = 10
    elif change == 'negative_fund': vars_(result, 202)['eon_refugee_relief_fund'] = -1
    elif change == 'no_need': vars_(result, 202)['eon_refugees_hosted'] = 0
    elif change == 'bilateral_war': result['countries'][202]['wars'].add(101)
    elif change == 'donor_subject': result['countries'][101]['subject'] = True
    elif change == 'donor_dead': result['countries'][101]['exists'] = False
    elif change == 'recipient_dead': result['countries'][202]['exists'] = False
    before = cash_snapshot(result); reply(result)
    assert cash_snapshot(result) == before and not result['debits']
    assert 'eon_humanitarian_aid_pending' not in flags(result)
    groups['fresh_conditions_at_native_consent'] += 1

for accepted in (False, True):
    result = state(); send(result); before = cash_snapshot(result)
    run(result, one(withdraw, 'complete_effect'))
    assert 'eon_humanitarian_aid_cancelled' in flags(result)
    assert not ready(result, recipient=303)
    reply(result, accepted)
    assert cash_snapshot(result) == before and not result['debits']
    assert ready(result, recipient=303)
    groups['withdraw_then_consume_original_reply'] += 1

for callback in (True, False):
    result = state(); send(result)
    reply(result, callback, recipient=303)
    assert vars_(result)['eon_humanitarian_aid_partner'] == 202
    before = cash_snapshot(result); send(result, recipient=303)
    assert vars_(result)['eon_humanitarian_aid_partner'] == 202
    assert cash_snapshot(result) == before
    groups['mismatched_reply_and_send_cannot_overwrite'] += 1

for change in ('expiry', 'recipient_dead', 'missing_partner', 'unknown_partner'):
    result = state(); send(result)
    if change == 'expiry': flags(result).discard('eon_humanitarian_aid_live')
    elif change == 'recipient_dead': result['countries'][202]['exists'] = False
    elif change == 'missing_partner': vars_(result).pop('eon_humanitarian_aid_partner')
    else: vars_(result)['eon_humanitarian_aid_partner'] = 999
    before = cash_snapshot(result); daily(result); reply(result)
    assert cash_snapshot(result) == before and not result['debits']
    assert 'eon_humanitarian_aid_pending' not in flags(result)
    if change in ('expiry', 'recipient_dead'):
        assert 'eon_humanitarian_aid_retired_pair@202' in flags(result)
        result['countries'][202]['exists'] = True
        assert not ready(result) and ready(result, recipient=303)
        send(result, recipient=303); reply(result) # Old 202 reply cannot affect 303.
        assert vars_(result)['eon_humanitarian_aid_partner'] == 303
    else:
        assert 'eon_humanitarian_aid_quarantined' in flags(result)
        assert not ready(result, recipient=303)
    groups['forced_cleanup_tombstone_no_refund'] += 1

for hook, actor, from_, extinct in (('on_annex', 303, 202, 202), ('on_subject_annexed', 202, 303, 202),
                                   ('on_annex', 303, 101, 101), ('on_subject_annexed', 101, 303, 101)):
    result = state(); send(result); before = cash_snapshot(result)
    result['temp'] = {}; execute(one(one(hooks, hook), 'effect'), result, context(actor, from_))
    assert cash_snapshot(result) == before and not result['debits']
    assert 'eon_humanitarian_aid_pending' not in flags(result)
    reply(result); assert cash_snapshot(result) == before
    groups['annex_and_subject_integration_without_asset_transfer'] += 1

result = state(); send(result); reply(result, False)
assert ready(result)
groups['decline_without_success_cooldown'] += 1
result = state(); send(result); reply(result)
assert not ready(result) and ready(result, recipient=303)
flags(result).discard('eon_humanitarian_aid_cooldown@202')
assert ready(result)
groups['success_cooldown_exact_partner'] += 1

for stray in ('live', 'cancelled', 'partner'):
    result = state()
    if stray == 'partner': vars_(result)['eon_humanitarian_aid_partner'] = 202
    else: flags(result).add('eon_humanitarian_aid_' + stray)
    before = cash_snapshot(result); daily(result)
    assert cash_snapshot(result) == before
    assert 'eon_humanitarian_aid_quarantined' in flags(result)
    assert not ready(result, recipient=303)
    groups['unowned_stray_record_closes_only_donor_channel'] += 1

result = state(hosted=0, war=True); send(result); reply(result)
result['countries'][202]['wars'].clear()
before = cash_snapshot(result); daily(result, donor=202)
assert cash_snapshot(result) == before and vars_(result, 202)['eon_refugee_relief_fund'] == .1
groups['prepared_relief_balance_survives_end_of_need'] += 1

result = state(fund=9.85); send(result); send(result, donor=303)
before = balance(result); reply(result); reply(result, donor=303)
assert len(result['debits']) == 1
assert abs(vars_(result, 202)['eon_refugee_relief_fund'] - 9.95) < 1e-8
assert abs(balance(result) - before) < 1e-8
assert 'eon_humanitarian_aid_pending' not in flags(result, 303)
groups['concurrent_donors_recheck_shared_fund_capacity'] += 1

result = state()
vars_(result).update(eon_aid_escrow=35, eon_aid_partner=404, pending_assume_debt_offer=404)
flags(result).add('eon_aid_reserved')
existing = {key: vars_(result)[key] for key in ('eon_aid_escrow', 'eon_aid_partner', 'pending_assume_debt_offer')}
send(result); reply(result)
assert all(vars_(result)[key] == value for key, value in existing.items())
assert 'eon_aid_reserved' in flags(result)
groups['existing_economic_aid_and_debt_records_preserved'] += 1

# Outcome events must remain inert. There is precisely one debit and fund credit
# site in the owned source, and no general recipient treasury or debt credit.
effect_text = read(paths[1])
assert effect_text.count('modify_treasury_effect = yes') == 1
assert effect_text.count('add_to_variable = { eon_refugee_relief_fund = 0.1 }') == 1
for forbidden in ('modify_debt_effect', 'add_political_power', 'change_influence_percentage',
                  'set_demilitarized_zone', 'give_military_access', 'refund', 'eon_aid_escrow'):
    assert forbidden not in effect_text
for key, op, body in ast(read(paths[4])):
    if key == 'country_event':
        assert one(body, 'option') == [('name', '=', 'eon_humanitarian_aid.ack')]
        assert not any(k in ('immediate', 'trigger') for k, o, v in body)
assert one(offer, 'cost') == '0' and one(offer, 'requires_acceptance') == 'yes'
assert one(withdraw, 'cost') == '0'
groups['inert_notices_and_no_second_accounting_channel'] += 1

en = ROOT / 'localisation/english/eon_humanitarian_aid_l_english.yml'
ru = ROOT / 'localisation/russian/eon_humanitarian_aid_l_russian.yml'
def keys(path):
    return [line.strip().split(':', 1)[0] for line in path.read_text(encoding='utf-8-sig').splitlines()[1:] if line.strip()]
assert keys(en) == keys(ru) and len(keys(en)) == len(set(keys(en)))
for path in (en, ru): assert path.read_bytes().startswith(b'\xef\xbb\xbf')
groups['localisation_key_parity_and_bom'] += 1
print(json.dumps({'scenarios': sum(groups.values()), 'groups': dict(groups),
 'proof_scope': 'ordered current humanitarian AST and treasury helper; preregistered initialization no-op; engine UI and campaign unverified',
 'migration_registration_ast_executed': False,
 'copied_unbacked_fund_cleanup_executed': False,
 'preregistered_initializer_noop_asserted': True,
 'registration_source_order_inspected': True,
 'hashes': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths + [registration_source, str(en.relative_to(ROOT)), str(ru.relative_to(ROOT))]}}, indent=2))
