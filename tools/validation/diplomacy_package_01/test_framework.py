"""Execute actual native energy-framework callbacks with the commercial model.

ROOT is the sender and current country is the receiver. Country-event FROM uses
the original effect ROOT; temporary variables are shared across country scopes.
Native UI delivery, AI and influence calculations require engine verification.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from itertools import product
from pathlib import Path
import hashlib
import io
import json
import runpy

from _support import ROOT, baseline

with redirect_stdout(io.StringIO()):
    base = runpy.run_path(str(Path(__file__).with_name('test_energy.py')))

ast, one = base['ast'], base['one']
env = base['execute'].__globals__
old_trigger, old_execute = env['trigger'], env['execute']
effects = env['effects']
triggers = dict((k, v) for k, op, v in ast(
    (ROOT / 'common/scripted_triggers/eon_energy_framework_triggers.txt').read_text(encoding='utf-8-sig')
))
actions = one(ast((ROOT / 'common/scripted_diplomatic_actions/MDDC_energy_contract_scripted_diplomatic_actions.txt').read_text(encoding='utf-8-sig')), 'scripted_diplomatic_actions')
agreement = one(actions, 'energy_contract_agreement')
cancel = one(actions, 'cancel_energy_agreement')
context, switch, country_ref = base['context'], base['switch'], base['country_ref']


def trigger(nodes, s, c):
    country = s['countries'][c['scope']]
    index = 0
    while index < len(nodes):
        k, op, v = nodes[index]
        group = [nodes[index]]
        index += 1
        if k == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                group.append(nodes[index])
                index += 1
        if k in triggers:
            passed = trigger(triggers[k], s, c) == (v == 'yes')
        elif k == 'custom_trigger_tooltip':
            passed = trigger([n for n in v if n[0] != 'tooltip'], s, c)
        elif k == 'always':
            passed = v == 'yes'
        elif k == 'is_neighbor_of':
            passed = country_ref(s, c, v) in country['neighbors']
        elif k == 'has_opinion':
            target = country_ref(s, c, one(v, 'target'))
            value_node = next(n for n in v if n[0] == 'value')
            passed = base['compare'](country['opinions'].get(target, 0), value_node[1], float(value_node[2]))
        elif k == 'is_in_faction':
            passed = bool(country['allies']) == (v == 'yes')
        elif k == 'any_allied_country':
            passed = any(trigger(v, s, switch(c, ally)) for ally in country['allies'])
        else:
            passed = old_trigger(group, s, c)
        if not passed:
            return False
    return True


def execute(nodes, s, c):
    # These pre-existing external macros do not decide proposal/contract state.
    # Witness their callers instead of pretending to emulate their calculations.
    i = 0
    while i < len(nodes):
        k, op, v = nodes[i]
        group = [nodes[i]]
        i += 1
        if k == 'if':
            while i < len(nodes) and nodes[i][0] in ('else_if', 'else'):
                group.append(nodes[i])
                i += 1
        if k in ('add_opinion_modifier', 'reverse_add_opinion_modifier', 'change_influence_percentage'):
            s.setdefault('external_calls', []).append((c['scope'], k, deepcopy(v)))
        else:
            old_execute(group, s, c)


env['trigger'], env['execute'] = trigger, execute


def state():
    s = base['state']()
    for name, country in s['countries'].items():
        country.update(neighbors=set(s['countries']) - {name},
                       opinions={other: 20 for other in s['countries']}, allies=set())
    return s


def native(sender='A', receiver='B'):
    return context(sender, scope=receiver)


def send(s, sender='A', receiver='B'):
    c = native(sender, receiver)
    if not trigger(one(agreement, 'can_be_sent'), s, c):
        return False
    execute(one(agreement, 'on_sent_effect'), s, c)
    return True


def finish(s, callback='complete_effect', sender='A', receiver='B'):
    execute(one(agreement, callback), s, native(sender, receiver))


def reserved(s, country):
    v = s['countries'][country]['variables']
    return bool(v.get('pending_energy_offer_country', 0) or v.get('eon_energy_framework_pending_sender', 0))


def agreed(s, a='A', b='B'):
    return ('energy_agreement@' + b in s['countries'][a]['flags'] and
            'energy_agreement@' + a in s['countries'][b]['flags'])


cases = []

# Incoming and outgoing queues both reserve both countries, including crossed requests.
for values in product((0, 'C'), repeat=4):
    s = state()
    for (country, variable), value in zip(
        [('A', 'pending_energy_offer_country'), ('A', 'eon_energy_framework_pending_sender'),
         ('B', 'pending_energy_offer_country'), ('B', 'eon_energy_framework_pending_sender')], values):
        if value:
            s['countries'][country]['variables'][variable] = value
    before = deepcopy(s)
    assert send(s) == (not any(values))
    if any(values):
        assert s == before
    else:
        assert reserved(s, 'A') and reserved(s, 'B')
        assert not send(s, 'B', 'A') and not send(s, 'C', 'B') and not send(s, 'A', 'C')
    cases.append('two-country reservation ' + str(values))

# Recheck present eligibility, independent of the original sending conditions.
for changed in ('recipient disappeared', 'sender disappeared', 'direct war', 'not adjacent',
                'opinion dropped', 'recipient already signed', 'sender already signed'):
    s = state()
    assert send(s)
    if changed == 'recipient disappeared': s['countries']['B']['exists'] = False
    elif changed == 'sender disappeared': s['countries']['A']['exists'] = False
    elif changed == 'direct war': s['countries']['B']['wars'].add('A')
    elif changed == 'not adjacent': s['countries']['B']['neighbors'].discard('A')
    elif changed == 'opinion dropped': s['countries']['B']['opinions']['A'] = 10
    elif changed == 'recipient already signed': s['countries']['B']['flags'].add('energy_agreement@A')
    elif changed == 'sender already signed': s['countries']['A']['flags'].add('energy_agreement@B')
    before_flags = deepcopy([s['countries'][c]['flags'] for c in ('A', 'B')])
    assert not trigger(one(agreement, 'can_be_accepted'), s, native())
    finish(s)
    assert before_flags == [s['countries'][c]['flags'] for c in ('A', 'B')]
    assert not reserved(s, 'A') and not reserved(s, 'B') and not s.get('external_calls')
    cases.append('acceptance rechecks ' + changed)

for callback in ('complete_effect', 'reject_effect'):
    s = state(); assert send(s)
    assert trigger(one(agreement, 'can_be_accepted'), s, native())
    finish(s, callback)
    assert agreed(s) == (callback == 'complete_effect')
    assert not reserved(s, 'A') and not reserved(s, 'B')
    before = deepcopy(s); finish(s, callback); assert s == before
    cases.append('current callback and repeated response ' + callback)

# An unrelated callback cannot consume another pair's request or add opinions.
for callback in ('complete_effect', 'reject_effect'):
    s = state(); assert send(s, 'A', 'C')
    before = deepcopy(s); finish(s, callback, 'A', 'B'); assert s == before
    cases.append('wrong-pair callback preserves reservations ' + callback)

# Legacy pre-package request has an outgoing reference only: no acceptance,
# but a matching response can release it safely without creating an agreement.
for callback in ('complete_effect', 'reject_effect'):
    s = state(); s['countries']['A']['variables']['pending_energy_offer_country'] = 'B'
    assert not trigger(one(agreement, 'can_be_accepted'), s, native())
    finish(s, callback)
    assert not agreed(s) and not reserved(s, 'A') and not s.get('external_calls')
    cases.append('legacy outgoing-only response fails closed and unlocks ' + callback)

# Cancellation integrates the actual commercial end helper: both arrays and
# weekly payments stop; partner receives notice FROM the actual cancelling sender.
for direction in (('A', 'B'), ('B', 'A')):
    sender, receiver = direction
    s = state(); base['framework'](s, 'A', 'B'); base['pair'](s, 'A', 'B', -6, .06)
    base['pair'](s, 'A', 'C', -2, .04)
    base['propose'](s, 'A', 'B', -8, .07)
    execute(one(cancel, 'complete_effect'), s, native(sender, receiver))
    assert not agreed(s)
    assert s['countries']['B']['arrays']['energy_contractors'] == []
    assert s['countries']['A']['arrays']['energy_contractors'] == ['C']
    assert base['locked'](s, 'A') and base['locked'](s, 'B')
    notices = [e for e in s['events'] if e['id'] == 'energy_selling.5']
    assert notices == [{'target': receiver, 'id': 'energy_selling.5', 'from': sender}]
    result = base['money'](s)
    assert result['B'] == (0, 0) and base['compare'](result['A'][0], '=', .08)
    base['response'](s, 'B', 'A'); assert not base['locked'](s, 'A') and not base['locked'](s, 'B')
    cases.append('native cancellation ends both payments and sends correctly scoped notice ' + str(direction))

# Withdrawn framework reservations drain only with their original response.
for callback in ('complete_effect', 'reject_effect'):
    s = state(); assert send(s)
    execute(one(cancel, 'complete_effect'), s, native())
    assert all('eon_energy_framework_withdrawn' in s['countries'][c]['flags'] for c in ('A', 'B'))
    assert reserved(s, 'A') and reserved(s, 'B') and not send(s)
    assert not trigger(one(agreement, 'can_be_accepted'), s, native())
    finish(s, callback)
    assert not agreed(s) and not reserved(s, 'A') and not reserved(s, 'B')
    assert not s.get('external_calls')
    assert send(s); finish(s); assert agreed(s)
    cases.append('withdrawn request cannot be replaced before old response ' + callback)

# Inherited ally rule is preserved exactly: at least one ally not at war with
# sender, even if another ally is at war. Changing this policy is a later package.
for all_at_war in (False, True):
    s = state(); s['countries']['B']['allies'] = {'C', 'D'}
    s['countries']['C']['wars'].add('A')
    if all_at_war: s['countries']['D']['wars'].add('A')
    assert send(s) == (not all_at_war)
    cases.append('inherited ally eligibility ' + str(all_at_war))

on_actions = one(ast((ROOT / 'common/on_actions/00_costili.txt').read_text(encoding='utf-8-sig')), 'on_actions')
for name, dying in product(('on_annex', 'on_subject_annexed'), ('A', 'B')):
    block = next(v for k, op, v in on_actions if k == name and 'eon_energy_clear_pair_pending' in str(v))
    s = state(); assert send(s); assert send(s, 'C', 'D')
    unrelated = deepcopy([s['countries'][country]['variables'] for country in ('C', 'D')])
    for country in ('A', 'B'): s['countries'][country]['flags'].add('eon_energy_framework_withdrawn')
    s['countries'][dying]['exists'] = False
    c = context('D', dying) if name == 'on_annex' else context(dying, 'D')
    execute(one(block, 'effect'), s, c)
    assert not reserved(s, 'A') and not reserved(s, 'B')
    assert all('eon_energy_framework_withdrawn' not in s['countries'][country]['flags'] for country in ('A', 'B'))
    assert unrelated == [s['countries'][country]['variables'] for country in ('C', 'D')]
    s['countries'][dying]['exists'] = True
    assert send(s), 'Released tag must not retain its pre-annex request lock'
    cases.append('annex cleans dying and surviving framework reservations, restored tag usable ' + name + '/' + dying)

for name in ('on_annex', 'on_subject_annexed'):
    block = next(v for k, op, v in on_actions if k == name and 'eon_energy_clear_pair_pending' in str(v))
    s = state(); assert send(s); assert send(s, 'C', 'D')
    s['countries']['A']['variables']['eon_energy_framework_pending_sender'] = 'B'
    s['countries']['A']['flags'].add('eon_energy_framework_withdrawn')
    s['countries']['A']['exists'] = False
    c = context('D', 'A') if name == 'on_annex' else context('A', 'D')
    execute(one(block, 'effect'), s, c)
    assert not reserved(s, 'A') and not reserved(s, 'B')
    assert reserved(s, 'C') and reserved(s, 'D')
    s['countries']['A']['exists'] = True; assert send(s)
    cases.append('annex clears both legacy reservation directions while preserving unrelated request ' + name)

old_actions = one(ast(baseline('common/scripted_diplomatic_actions/MDDC_energy_contract_scripted_diplomatic_actions.txt').decode('utf-8-sig')), 'scripted_diplomatic_actions')
s = state(); base['framework'](s, 'A', 'B'); base['pair'](s, 'A', 'B', -6, .06)
base['pair'](s, 'A', 'B', -6, .06)
execute(one(one(old_actions, 'cancel_energy_agreement'), 'complete_effect'), s, native())
old_income, old_expense = base['money'](s)['B']
assert not agreed(s) and old_income == 0 and base['compare'](old_expense, '=', .36)
cases.append('original framework cancellation leaves duplicate payment record reproduced')

paths = ['common/scripted_diplomatic_actions/MDDC_energy_contract_scripted_diplomatic_actions.txt',
         'common/scripted_triggers/eon_energy_framework_triggers.txt',
         'common/scripted_effects/eon_energy_framework_effects.txt']
print(json.dumps({'test_level': 'actual-source symbolic native/commercial integration, not engine proof',
                  'cases_passed': len(cases), 'cases': cases,
                  'external_macros_witnessed_only': ['opinion additions', 'change_influence_percentage'],
                  'source_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}}, indent=2))
