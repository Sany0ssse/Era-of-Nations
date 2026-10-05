"""Check the current native mutual investment treaty's actual source lifecycle.

Scope: native sender/receiver mapping, shared temporary values, queue reservation,
fixed terms, pair state and external influence-call parameters. No live game proof.
"""
from copy import deepcopy
from itertools import product
import hashlib
import json
import re

from _support import ROOT, baseline
from _treaty_support import Interpreter, TOKEN, ast, one, countries

ACTION_PATH = 'common/scripted_diplomatic_actions/00_scripted_diplomatic_actions.txt'
raw = (ROOT / ACTION_PATH).read_bytes()
text = raw.decode('utf-8-sig')
actions = one(ast(text), 'scripted_diplomatic_actions')
proposal = one(actions, 'propose_mutual_investment_treaty')
cancel = one(actions, 'cancel_mutual_investment_treaty')
old_text = baseline(ACTION_PATH).decode('utf-8-sig')
old_actions = one(ast(old_text), 'scripted_diplomatic_actions')
old_proposal = one(old_actions, 'propose_mutual_investment_treaty')
cases = []


def vm(sender=1, receiver=2, remove_all=False):
    return Interpreter(countries(), sender, receiver, remove_all)


def send(model):
    if not model.trigger(one(proposal, 'can_be_sent')): return False
    model.effect(one(proposal, 'on_sent_effect'))
    return True


def reply(model, callback='complete_effect'):
    model.effect(one(proposal, callback))


def reserved(model, nation):
    values = model.countries[nation].variables
    return bool(values.get('pending_mutual_investment_treaty_offer', 0) or
                values.get('eon_investment_treaty_pending_sender', 0))


def signed(model):
    a, b = model.sender, model.receiver
    return (f'mutual_investment_treaty_@{b}' in model.countries[a].flags and
            f'mutual_investment_treaty_@{a}' in model.countries[b].flags)


def side_helper(model, owner, partner, helper):
    model.effect(ast(f'set_temp_variable = {{ eon_investment_treaty_partner = {partner} }}\n{helper} = yes'),
                 [model.countries[owner]])
    assert model.temp['eon_investment_treaty_partner'] == partner, 'Helper changed shared input'


# Both countries reserve their queue; no direction or third party overwrites it.
for values in product((0, 3), repeat=4):
    model = vm()
    for (nation, key), value in zip(
        [(1, 'pending_mutual_investment_treaty_offer'), (1, 'eon_investment_treaty_pending_sender'),
         (2, 'pending_mutual_investment_treaty_offer'), (2, 'eon_investment_treaty_pending_sender')], values):
        if value: model.countries[nation].variables[key] = value
    before = deepcopy(model.countries)
    assert send(model) == (not any(values))
    if any(values):
        model.effect(one(proposal, 'on_sent_effect'))
        assert model.countries == before, 'Direct repeated on_sent bypassed reservation'
    else:
        assert reserved(model, 1) and reserved(model, 2)
        for sender, receiver in ((1, 3), (3, 2), (2, 1), (2, 3), (3, 1)):
            probe = Interpreter(model.countries, sender, receiver)
            assert not send(probe), 'Crossed or incoming request overwrote a pending pair'
    cases.append('reservation ' + str(values))

# The fixed source terms are recorded on both endpoints, not inferred for legacy requests.
for sender_version, receiver_version in product((0, 1, 2, 3), repeat=2):
    model = vm(); assert send(model)
    model.countries[1].variables['eon_investment_treaty_pending_terms'] = sender_version
    model.countries[2].variables['eon_investment_treaty_pending_terms'] = receiver_version
    valid = sender_version == receiver_version == 1
    assert model.trigger(one(proposal, 'can_be_accepted')) == valid
    reply(model)
    assert signed(model) == valid
    assert not reserved(model, 1) and not reserved(model, 2)
    assert bool(model.external_calls) == valid
    cases.append('fixed terms protocol ' + str((sender_version, receiver_version)))

# Preserve the original existential allied policy rather than silently changing it to all.
for faction, has_existing_ally, peaceful_ally, hostile_ally in product((False, True), repeat=4):
    model = vm(); target = model.countries[2]
    target.in_faction = faction
    target.allies = ({3} if has_existing_ally else set()) | ({4} if hostile_ally else set())
    if has_existing_ally and not peaceful_ally: model.countries[3].wars.add(1)
    if hostile_ally: model.countries[4].wars.add(1)
    previous_allowed = model.trigger(one(old_proposal, 'selectable'))
    assert model.trigger(one(proposal, 'can_be_sent')) == previous_allowed
    cases.append('original faction policy ' + str((faction, has_existing_ally, peaceful_ally, hostile_ally)))

for changed in ('recipient disappears', 'sender disappears', 'direct war', 'opinion becomes 25',
                'recipient treaty story flag', 'sender treaty story flag',
                'only hostile allies', 'ERI transitional leader', 'ERI flag without transitional leader',
                'non-ERI flag and leader', 'recipient ERI leader'):
    model = vm(); assert send(model)
    donor, target = model.countries[1], model.countries[2]
    invalid = True
    if changed == 'recipient disappears': target.exists = False
    elif changed == 'sender disappears': donor.exists = False
    elif changed == 'direct war': target.wars.add(1)
    elif changed == 'opinion becomes 25': target.opinions[1] = 25
    elif changed == 'recipient treaty story flag': target.flags.add('mutual_investment_treaty_@1')
    elif changed == 'sender treaty story flag': donor.flags.add('mutual_investment_treaty_@2')
    elif changed == 'only hostile allies':
        target.in_faction = True; target.allies = {3}; model.countries[3].wars.add(1)
    elif changed == 'ERI transitional leader':
        donor.original_tag = 'ERI'; donor.flags.add('ETH_transitional_government_FLAG')
        donor.leader = 'Eritrean Transitional Government'
    elif changed == 'ERI flag without transitional leader':
        donor.original_tag = 'ERI'; donor.flags.add('ETH_transitional_government_FLAG'); invalid = False
    elif changed == 'non-ERI flag and leader':
        donor.flags.add('ETH_transitional_government_FLAG'); donor.leader = 'Eritrean Transitional Government'; invalid = False
    elif changed == 'recipient ERI leader':
        target.original_tag = 'ERI'; target.flags.add('ETH_transitional_government_FLAG')
        target.leader = 'Eritrean Transitional Government'; invalid = False
    before_flags = deepcopy((donor.flags, target.flags))
    assert model.trigger(one(proposal, 'can_be_accepted')) == (not invalid)
    reply(model)
    if invalid:
        assert (donor.flags, target.flags) == before_flags
        assert not model.external_calls
    else: assert signed(model)
    assert not reserved(model, 1) and not reserved(model, 2)
    cases.append('acceptance recheck ' + changed)

# Normal acceptance keeps the original four opinions and two +1 influence callers.
for reverse, remove_all, duplicate_count in product((False, True), (False, True), (0, 1, 3)):
    sender, receiver = (2, 1) if reverse else (1, 2)
    model = vm(sender, receiver, remove_all)
    for owner, partner in ((1, 2), (2, 1)):
        model.countries[owner].arrays['permanent_investment_targets'] = [3] + [partner] * duplicate_count + [4, 3]
        model.countries[owner].flags = {'unrelated'}
        model.countries[owner].modifiers = {(3, 'unrelated')}
    assert send(model)
    reply(model)
    assert signed(model)
    for owner, partner in ((1, 2), (2, 1)):
        nation = model.countries[owner]
        assert nation.arrays['permanent_investment_targets'] == [3, 4, 3, partner]
        assert nation.modifiers == {(3, 'unrelated'), (partner, 'mutual_investment_treaty_opinion'), (partner, 'mutual_investment_treaty_trade_opinion')}
        assert nation.projects == ['existing-building', 'pending-project']
    assert model.external_calls == [
        (receiver, 'change_influence_percentage', {'percent_change': 1, 'tag_index': sender, 'influence_target': receiver}),
        (sender, 'change_influence_percentage', {'percent_change': 1, 'tag_index': receiver, 'influence_target': sender})]
    assert len(model.opinion_calls) == 4
    before = deepcopy((model.countries, model.external_calls, model.opinion_calls))
    reply(model); reply(model, 'reject_effect')
    assert (model.countries, model.external_calls, model.opinion_calls) == before, 'Repeated response changed treaty, opinion timers or influence'
    cases.append('acceptance once and target normalization ' + str((reverse, remove_all, duplicate_count)))

for callback in ('complete_effect', 'reject_effect'):
    # A callback from A→B must not unlock the valid current A→C request.
    model = vm(1, 3); assert send(model)
    wrong = Interpreter(model.countries, 1, 2)
    before = deepcopy(model.countries); reply(wrong, callback)
    assert model.countries == before and not wrong.external_calls and not wrong.opinion_calls
    cases.append('wrong pair response ' + callback)
    # Legacy outgoing-only callbacks are drained without assuming new consent.
    model = vm(); model.countries[1].variables['pending_mutual_investment_treaty_offer'] = 2
    assert not model.trigger(one(proposal, 'can_be_accepted'))
    reply(model, callback)
    assert not signed(model) and not reserved(model, 1) and not reserved(model, 2)
    assert not model.external_calls and not model.opinion_calls and not any(n.modifiers for n in model.countries.values())
    cases.append('legacy outgoing-only cleanup ' + callback)
    # Withdrawal retains both reservations and prevents an old window approving a replacement.
    model = vm(); assert send(model)
    model.effect(one(cancel, 'complete_effect'))
    assert all(reserved(model, n) for n in (1, 2))
    assert not model.trigger(one(proposal, 'can_be_accepted')) and not send(model)
    reply(model, callback)
    assert not signed(model) and not model.opinion_calls and not any(n.modifiers for n in model.countries.values())
    assert not reserved(model, 1) and not reserved(model, 2) and not model.external_calls
    assert send(model); reply(model); assert signed(model)
    cases.append('withdrawal drain ' + callback)

# Genuine refusals retain the original bilateral refusal opinion, without agreement effects.
model = vm(); assert send(model); reply(model, 'reject_effect')
assert not signed(model) and not model.external_calls
assert model.countries[1].modifiers == {(2, 'reject_mutual_investment_treaty')}
assert model.countries[2].modifiers == {(1, 'reject_mutual_investment_treaty')}
assert len(model.opinion_calls) == 2
before = deepcopy((model.countries, model.opinion_calls)); reply(model, 'reject_effect')
assert (model.countries, model.opinion_calls) == before
cases.append('genuine refusal exactly once')

# Story installation invalidates both acceptance and a later refusal penalty.
for side in (1, 2):
    model = vm(); assert send(model)
    model.countries[side].flags.add('mutual_investment_treaty_@' + str(3 - side))
    before = deepcopy(model.countries[side].flags)
    reply(model, 'reject_effect')
    assert model.countries[side].flags == before
    assert not any(n.modifiers for n in model.countries.values())
    cases.append('story treaty suppresses stale refusal ' + str(side))

# Cancellation removes the pair symmetrically even if only one standing flag survived.
for reverse, remove_all, duplicate_count, flag_mode in product((False, True), (False, True), (0, 1, 3), ('both', 'sender', 'receiver')):
    sender, receiver = (2, 1) if reverse else (1, 2)
    model = vm(sender, receiver, remove_all)
    for owner, partner in ((1, 2), (2, 1)):
        nation = model.countries[owner]
        nation.arrays['permanent_investment_targets'] = [3] + [partner] * duplicate_count + [4, 3]
        nation.modifiers = {(partner, 'mutual_investment_treaty_opinion'), (partner, 'mutual_investment_treaty_trade_opinion'), (3, 'unrelated')}
        nation.flags = {'unrelated', 'mutual_investment_treaty_@3'}
    for owner in ((sender, receiver) if flag_mode == 'both' else (sender,) if flag_mode == 'sender' else (receiver,)):
        model.countries[owner].flags.add('mutual_investment_treaty_@' + str(3 - owner))
    assert model.trigger(one(cancel, 'visible')) and model.trigger(one(cancel, 'can_be_sent'))
    model.effect(one(cancel, 'complete_effect'))
    for owner in (1, 2):
        nation = model.countries[owner]
        assert nation.arrays['permanent_investment_targets'] == [3, 4, 3]
        assert nation.modifiers == {(3, 'unrelated')}
        assert nation.flags == {'unrelated', 'mutual_investment_treaty_@3'}
        assert nation.projects == ['existing-building', 'pending-project']
    before = deepcopy(model.countries); model.effect(one(cancel, 'complete_effect')); assert model.countries == before
    cases.append('cancellation pair only ' + str((reverse, remove_all, duplicate_count, flag_mode)))

# Cancelling an unrelated pair must not withdraw an active request with a third party.
model = vm(1, 3); assert send(model)
wrong = Interpreter(model.countries, 1, 2); before = deepcopy(model.countries)
wrong.effect(one(cancel, 'complete_effect'))
assert model.countries == before
cases.append('unrelated cancellation preserves pending pair')

# Damaged simultaneous queues retain the other request and its withdrawal marker.
for callback in ('complete_effect', 'reject_effect'):
    model = vm(); assert send(model)
    model.countries[1].variables['eon_investment_treaty_pending_sender'] = 3
    model.countries[1].variables['eon_investment_treaty_withdrawn_partner'] = 3
    reply(model, callback)
    assert model.countries[1].variables['eon_investment_treaty_pending_sender'] == 3
    assert model.countries[1].variables['eon_investment_treaty_withdrawn_partner'] == 3
    assert model.countries[1].variables['eon_investment_treaty_pending_terms'] == 1
    cases.append('unrelated damaged queue is not unlocked ' + callback)

# Actual annex helper clears both countries' standing state and preserves shared input.
for reverse, remove_all, other_pending in product((False, True), (False, True), (False, True)):
    survivor, vanished = (2, 1) if reverse else (1, 2)
    model = vm(sender=4, receiver=survivor, remove_all=remove_all)
    for owner, partner in ((survivor, vanished), (vanished, survivor)):
        nation = model.countries[owner]
        nation.flags = {'unrelated', f'mutual_investment_treaty_@{partner}', 'mutual_investment_treaty_@3'}
        nation.arrays['permanent_investment_targets'] = [3, partner, partner, 4]
        nation.modifiers = {(partner, 'mutual_investment_treaty_opinion'), (partner, 'mutual_investment_treaty_trade_opinion'), (3, 'unrelated')}
        nation.variables.update(pending_mutual_investment_treaty_offer=partner,
                               eon_investment_treaty_pending_terms=1,
                               eon_investment_treaty_withdrawn_partner=partner)
        if other_pending:
            nation.variables['eon_investment_treaty_pending_sender'] = 3
    model.countries[vanished].exists = False
    side_helper(model, survivor, vanished, 'eon_investment_treaty_cleanup_annexed_pair')
    for owner in (survivor, vanished):
        nation = model.countries[owner]
        assert nation.flags == {'unrelated', 'mutual_investment_treaty_@3'}
        assert nation.arrays['permanent_investment_targets'] == [3, 4]
        assert nation.modifiers == {(3, 'unrelated')}
        assert nation.projects == ['existing-building', 'pending-project']
        assert not nation.variables.get('pending_mutual_investment_treaty_offer')
        assert not nation.variables.get('eon_investment_treaty_withdrawn_partner')
        assert nation.variables.get('eon_investment_treaty_pending_sender', 0) == (3 if other_pending else 0)
        assert nation.variables.get('eon_investment_treaty_pending_terms', 0) == (1 if other_pending else 0)
    model.countries[vanished].exists = True
    assert not signed(Interpreter(model.countries, survivor, vanished)), 'Released tag retained an annexed treaty'
    cases.append('annex both sides and release ' + str((reverse, remove_all, other_pending)))

model = vm(); assert send(model)
model.countries[1].variables['unrelated'] = 123
model.effect(ast('eon_investment_treaty_clear_pending = yes'), [model.countries[1]])
assert model.countries[1].variables == {'unrelated': 123}
assert reserved(model, 2)
cases.append('own pending cleanup preserves unrelated variables')

# Reproduce a baseline overwrite directly from its old on_sent callback.
model = vm(); model.countries[1].variables['pending_mutual_investment_treaty_offer'] = 3
model.effect(one(old_proposal, 'on_sent_effect'))
assert model.countries[1].variables['pending_mutual_investment_treaty_offer'] == 2
cases.append('baseline pending overwrite reproduced')
# The old acceptance prefix adds treaty flags even without any pending consent.
model = vm(); prefix = []
for node in one(old_proposal, 'complete_effect'):
    if node[0] == 'THIS': break
    prefix.append(node)
model.effect(prefix); assert signed(model)
cases.append('baseline unguarded grant prefix reproduced')


def blocks(source):
    tokens = [m for m in TOKEN.finditer(source) if not m[0].startswith('#')]
    stack, found = [], []
    for index, token in enumerate(tokens):
        if token[0] == '{':
            item = {'key': tokens[index-2][0], 'start': tokens[index-2].start(),
                    'parent': stack[-1]['key'] if stack else None}
            stack.append(item); found.append(item)
        elif token[0] == '}': stack.pop()['end'] = token.end()
    assert not stack
    return found


def field_bytes(source, action, field):
    found = [b for b in blocks(source) if b['key'] == field and b['parent'] == action]
    assert len(found) == 1, (action, field)
    return source[found[0]['start']:found[0]['end']]


# All AI policy blocks and field values remain byte-exact to the previous package.
for action in ('propose_mutual_investment_treaty', 'cancel_mutual_investment_treaty'):
    assert one(one(old_actions, action), 'cost') == one(one(actions, action), 'cost') == '75'
    assert field_bytes(old_text, action, 'ai_desire') == field_bytes(text, action, 'ai_desire')
assert field_bytes(old_text, 'propose_mutual_investment_treaty', 'ai_acceptance') == field_bytes(text, 'propose_mutual_investment_treaty', 'ai_acceptance')
for action, changed in (
    ('propose_mutual_investment_treaty', {'selectable', 'can_be_sent', 'can_be_accepted', 'on_sent_effect', 'complete_effect', 'reject_effect'}),
    ('cancel_mutual_investment_treaty', {'visible', 'selectable', 'can_be_sent', 'complete_effect'})):
    old = one(old_actions, action); current = one(actions, action)
    assert [(k, op, value) for k, op, value in old if k not in changed] == [(k, op, value) for k, op, value in current if k not in changed]

new_files = ['common/scripted_effects/eon_investment_treaty_effects.txt',
             'common/scripted_triggers/eon_investment_treaty_triggers.txt',
             'localisation/english/eon_investment_treaty_l_english.yml',
             'localisation/russian/eon_investment_treaty_l_russian.yml']
locale = {}
for lang in ('english', 'russian'):
    path = ROOT / f'localisation/{lang}/eon_investment_treaty_l_{lang}.yml'
    data = path.read_bytes(); assert data.startswith(b'\xef\xbb\xbf')
    assert data.count(b'\r\n') == data.count(b'\n')
    # Splitlines excludes CR in the exact grammar validation.
    keys = dict(re.findall(r'^ ([\w.]+):0 "(.*)"$', '\n'.join(data.decode('utf-8-sig').splitlines()), re.M))
    assert len(keys) == 4 and all('?' not in value and '\ufffd' not in value for value in keys.values())
    locale[lang] = keys
assert locale['english'].keys() == locale['russian'].keys()
assert all(key in text for key in locale['english']), 'A new UI tooltip is not referenced'
assert re.search('[А-Яа-я]', ' '.join(locale['russian'].values())), 'Russian text was damaged'

result = {'all_passed': True, 'total_scenarios': len(cases), 'cases': cases,
          'action_source_sha256': hashlib.sha256(raw).hexdigest(),
          'sources': {path: hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in new_files},
          'ai_policy_and_PP_75_unchanged': True,
          'proof_scope': 'actual-source AST callbacks/helpers/ERI eligibility and shared temporary variables; influence macro calls witnessed with +1 inputs',
          'not_proven': ['native delivery and timeout behavior', 'actual influence macro economics', 'AI frequency', 'PP refund', 'save/load', 'arbitrary duplicate old native callbacks after a fresh same-pair offer']}
print(json.dumps(result, ensure_ascii=False, indent=2))
