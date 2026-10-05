"""Read actual trade-treaty branches; bounded model, not the HOI4 engine.

Native callbacks use ROOT = sender and THIS = receiver. Temporary variables
share one evaluation environment. Existing political triggers and Singapore's
modifier calculation are expanded from source. Influence/GUI macros are witnessed
at their callers; their full calculations and native delivery need engine tests.
"""
from copy import deepcopy
from itertools import product
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASELINE = 'd4ec4a02a1a6dac362554ac85d4b001fbf32f488'
ACTION_PATH = 'common/scripted_diplomatic_actions/00_scripted_diplomatic_actions.txt'
TRIGGER_PATH = 'common/scripted_triggers/eon_trade_treaty_triggers.txt'
EFFECT_PATH = 'common/scripted_effects/eon_trade_treaty_effects.txt'
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|[=<>!]+|[^\s{}=<>!#"]+')


def ast(text):
    tokens = [m[0].strip('"') for m in TOKEN.finditer(text.lstrip('\ufeff'))
              if not m[0].startswith('#')]
    i = 0

    def block():
        nonlocal i
        result = []
        while i < len(tokens) and tokens[i] != '}':
            key = tokens[i]; i += 1
            assert i < len(tokens) and tokens[i] in ('=', '>', '<', '>=', '<=', '!='), key
            op = tokens[i]; i += 1
            if tokens[i] == '{':
                i += 1; value = block()
                assert tokens[i] == '}'; i += 1
            else:
                value = tokens[i]; i += 1
            result.append((key, op, value))
        return result

    result = block()
    assert i == len(tokens), 'Unbalanced source'
    return result


def one(nodes, key):
    found = [value for name, op, value in nodes if name == key]
    assert len(found) == 1, (key, len(found))
    return found[0]


def read(relative):
    return (ROOT / relative).read_bytes().decode('utf-8-sig')


def baseline(relative):
    return subprocess.check_output(['git', 'show', BASELINE + ':' + relative], cwd=ROOT)


effects = dict((key, value) for key, op, value in ast(read(EFFECT_PATH)))
triggers = dict((key, value) for key, op, value in ast(read(TRIGGER_PATH)))
eri_nodes = ast(read('common/scripted_triggers/99_ERI_scripted_triggers.txt'))
triggers['ERI_is_not_transitional_government'] = one(eri_nodes, 'ERI_is_not_transitional_government')
sin_text = read('common/scripted_effects/99_SIN_scripted_effects.txt')
sin_start = sin_text.index('SIN_calculate_singaporean_trade_agreements = {')
sin_end = sin_text.index('\n}', sin_start) + 2
effects['SIN_calculate_singaporean_trade_agreements'] = one(ast(sin_text[sin_start:sin_end]), 'SIN_calculate_singaporean_trade_agreements')
current = one(ast(read(ACTION_PATH)), 'scripted_diplomatic_actions')
old = one(ast(baseline(ACTION_PATH).decode('utf-8-sig')), 'scripted_diplomatic_actions')
trade, cancel = one(current, 'propose_improved_trade_agreement'), one(current, 'cancel_trade_agreement')
old_trade, old_cancel = one(old, 'propose_improved_trade_agreement'), one(old, 'cancel_trade_agreement')


def context(sender='A', receiver='B'):
    return {'root': sender, 'scope': receiver, 'previous': ()}


def switch(c, target):
    return {**c, 'scope': target, 'previous': (c['scope'],) + c['previous']}


def country_ref(s, c, expression):
    if expression.startswith('var:'):
        return value(s, c, expression[4:])
    if expression == 'ROOT': return c['root']
    if expression == 'THIS': return c['scope']
    if expression == 'PREV':
        assert c['previous'], 'PREV used without an enclosing country scope'
        return c['previous'][0]
    assert expression in s['countries'], ('Unknown country', expression)
    return expression


def value(s, c, expression):
    if isinstance(expression, (float, int)): return expression
    try: return float(expression)
    except ValueError: pass
    if expression in ('ROOT', 'THIS', 'PREV') or expression.startswith('var:'):
        return country_ref(s, c, expression)
    if expression in s['countries']: return expression
    if expression == 'id': return c['scope']
    if '.' in expression:
        head, tail = expression.split('.', 1)
        return value(s, switch(c, country_ref(s, c, head)), tail)
    return s['temp'].get(expression, s['countries'][c['scope']]['variables'].get(expression, 0))


def flag(s, c, expression):
    if '@' not in expression: return expression
    name, alias = expression.split('@', 1)
    return name + '@' + str(country_ref(s, c, alias))


def compare(a, op, b):
    if op == '=': return abs(a - b) < 1e-8 if isinstance(a, (float, int)) and isinstance(b, (float, int)) else a == b
    return {'>': lambda: a > b, '<': lambda: a < b, '>=': lambda: a >= b,
            '<=': lambda: a <= b, '!=': lambda: a != b}[op]()


def grouped(nodes):
    i = 0
    while i < len(nodes):
        node = nodes[i]; i += 1; branches = [node]
        if node[0] == 'if':
            while i < len(nodes) and nodes[i][0] in ('else_if', 'else'):
                branches.append(nodes[i]); i += 1
        yield node, branches


def trigger(nodes, s, c):
    country = s['countries'][c['scope']]
    for (key, op, val), branches in grouped(nodes):
        if key == 'if':
            passed = True
            for branch_name, branch_op, body in branches:
                limit = [v for k, o, v in body if k == 'limit']
                if not limit or trigger(limit[0], s, c):
                    passed = trigger([n for n in body if n[0] != 'limit'], s, c); break
        elif key in triggers: passed = trigger(triggers[key], s, c) == (val == 'yes')
        elif key in ('AND', 'custom_trigger_tooltip'): passed = trigger([n for n in val if n[0] != 'tooltip'], s, c)
        elif key == 'OR': passed = any(trigger([n], s, c) for n in val)
        elif key == 'NOT': passed = not trigger(val, s, c)
        elif key == 'always': passed = val == 'yes'
        elif key == 'exists': passed = country['exists'] == (val == 'yes')
        elif key == 'has_country_flag': passed = flag(s, c, val) in country['flags']
        elif key == 'check_variable':
            assert len(val) == 1
            variable, operator, rhs = val[0]
            passed = compare(value(s, c, variable), operator, value(s, c, rhs))
        elif key == 'has_opinion':
            target = country_ref(s, c, one(val, 'target'))
            operator, rhs = [(o, v) for k, o, v in val if k == 'value'][0]
            passed = compare(country['opinions'].get(target, 0), operator, float(rhs))
        elif key == 'has_war_with': passed = country_ref(s, c, val) in country['wars']
        elif key == 'has_idea': passed = val in country['ideas']
        elif key == 'tag': passed = c['scope'] == val
        elif key == 'original_tag': passed = country['original_tag'] == val
        elif key == 'has_country_leader': passed = country['leader'] == one(val, 'name')
        elif key == 'is_in_faction': passed = bool(country['allies']) == (val == 'yes')
        elif key == 'any_allied_country': passed = any(trigger(val, s, switch(c, a)) for a in country['allies'])
        elif key in ('ROOT', 'THIS', 'PREV') or key.startswith('var:'):
            passed = trigger(val, s, switch(c, country_ref(s, c, key)))
        else: raise AssertionError(('Unhandled trade trigger', key))
        if not passed: return False
    return True


def execute(nodes, s, c):
    for (key, op, val), branches in grouped(nodes):
        country = s['countries'][c['scope']]
        if key == 'if':
            for branch_name, branch_op, body in branches:
                limit = [v for k, o, v in body if k == 'limit']
                if not limit or trigger(limit[0], s, c):
                    execute([n for n in body if n[0] != 'limit'], s, c); break
        elif key in effects: execute(effects[key], s, c)
        elif key in ('ROOT', 'THIS', 'PREV') or key.startswith('var:'):
            execute(val, s, switch(c, country_ref(s, c, key)))
        elif key in ('set_variable', 'set_temp_variable', 'add_to_variable', 'multiply_variable'):
            dest = s['temp'] if 'temp' in key else country['variables']
            name, operator, rhs = val[0]
            if isinstance(rhs, list):
                result = 0
                for math_key, math_op, math_value in rhs:
                    if math_key == 'value': result = value(s, c, math_value)
                    elif math_key == 'multiply': result *= value(s, c, math_value)
                    else: raise AssertionError(('Unhandled source math', math_key))
            else: result = value(s, c, rhs)
            if key.startswith('set'): dest[name] = result
            elif key.startswith('add'): dest[name] = dest.get(name, 0) + result
            else: dest[name] = dest.get(name, 0) * result
        elif key == 'clamp_variable':
            p = {k: v for k, o, v in val}; result = country['variables'].get(p['var'], 0)
            if 'min' in p: result = max(result, value(s, c, p['min']))
            if 'max' in p: result = min(result, value(s, c, p['max']))
            country['variables'][p['var']] = result
        elif key == 'clear_variable': country['variables'].pop(val, None)
        elif key == 'set_country_flag': country['flags'].add(flag(s, c, val if isinstance(val, str) else one(val, 'flag')))
        elif key == 'clr_country_flag': country['flags'].discard(flag(s, c, val))
        elif key in ('add_opinion_modifier', 'reverse_add_opinion_modifier', 'remove_opinion_modifier'):
            target = country_ref(s, c, one(val, 'target')); modifier = one(val, 'modifier')
            if key == 'add_opinion_modifier': country['modifiers'].add((target, modifier))
            elif key == 'reverse_add_opinion_modifier': s['countries'][target]['modifiers'].add((c['scope'], modifier))
            else: country['modifiers'].discard((target, modifier))
        elif key == 'change_influence_percentage':
            s['external_influence'].append((c['scope'], value(s, c, 'tag_index'), value(s, c, 'influence_target'), value(s, c, 'percent_change')))
        elif key == 'ingame_update_setup': s['external_refresh'].append(c['scope'])
        elif key == 'hidden_effect': execute(val, s, c)
        elif key in ('log', 'custom_effect_tooltip'): pass
        else: raise AssertionError(('Unhandled trade effect', key))


def state():
    names = ('A', 'B', 'C', 'D', 'SWI', 'SIN', 'ERI')
    return {'countries': {name: {'exists': True, 'variables': {}, 'flags': set(),
                                'modifiers': set(), 'opinions': {n: 80 for n in names},
                                'wars': set(), 'ideas': set(), 'allies': set(),
                                'original_tag': name, 'leader': ''} for name in names},
            'temp': {}, 'external_influence': [], 'external_refresh': []}


def stable(s):
    return {k: deepcopy(v) for k, v in s.items() if k != 'temp'}


def perform(s, nodes, sender='A', receiver='B'):
    s['temp'] = {}; execute(nodes, s, context(sender, receiver))


def send(s, sender='A', receiver='B'):
    if not trigger(one(trade, 'can_be_sent'), s, context(sender, receiver)): return False
    perform(s, one(trade, 'on_sent_effect'), sender, receiver); return True


def finish(s, name='complete_effect', sender='A', receiver='B'):
    perform(s, one(trade, name), sender, receiver)


def reserved(s, name):
    return bool(s['countries'][name]['variables'].get('pending_trade_offer_country', 0) or
                s['countries'][name]['variables'].get('eon_trade_treaty_pending_sender', 0))


def signed(s, a='A', b='B'):
    return 'trade_agreement@' + b in s['countries'][a]['flags'] and 'trade_agreement@' + a in s['countries'][b]['flags']


def establish(s, a='A', b='B'):
    s['temp'] = {'eon_trade_treaty_partner': b}; execute(effects['eon_trade_treaty_establish_pair'], s, context(a, a))


cases = []
for busy in product((0, 'C'), repeat=4):
    s = state()
    for (country, name), partner in zip((('A', 'pending_trade_offer_country'), ('A', 'eon_trade_treaty_pending_sender'),
                                        ('B', 'pending_trade_offer_country'), ('B', 'eon_trade_treaty_pending_sender')), busy):
        if partner: s['countries'][country]['variables'][name] = partner
    before = stable(s); assert send(s) == (not any(busy))
    if any(busy): assert stable(s) == before
    else:
        assert reserved(s, 'A') and reserved(s, 'B')
        assert not send(s, 'A', 'C') and not send(s, 'B', 'A') and not send(s, 'C', 'B')
        assert send(s, 'C', 'D'), 'An unrelated pair can still negotiate'
        before = stable(s); perform(s, one(trade, 'on_sent_effect')); assert stable(s) == before
    cases.append('two-party queue ' + str(busy))

for sender, receiver in (('A', 'B'), ('B', 'A')):
    for response in ('complete_effect', 'reject_effect'):
        s = state(); establish(s, 'C', 'D'); other = deepcopy((s['countries']['C'], s['countries']['D']))
        assert send(s, sender, receiver)
        assert trigger(one(trade, 'can_be_accepted'), s, context(sender, receiver))
        finish(s, response, sender, receiver)
        assert signed(s) == (response == 'complete_effect')
        assert not reserved(s, sender) and not reserved(s, receiver)
        assert (s['countries']['C'], s['countries']['D']) == other
        if response == 'complete_effect':
            assert [s['countries'][x]['variables']['signed_trade_agreements'] for x in ('A', 'B')] == [1, 1]
            assert s['external_influence'] == [(receiver, sender, receiver, 1), (sender, receiver, sender, 1)]
        before = stable(s); finish(s, response, sender, receiver); assert stable(s) == before
        cases.append('valid response and duplicate ' + sender + ' ' + response)

for change in ('receiver disappeared', 'sender disappeared', 'war', 'opinion', 'ERI government',
               'sender flagged', 'receiver flagged', 'both flagged', 'allied enemy'):
    s = state(); assert send(s)
    if change == 'receiver disappeared': s['countries']['B']['exists'] = False
    elif change == 'sender disappeared': s['countries']['A']['exists'] = False
    elif change == 'war': s['countries']['B']['wars'].add('A')
    elif change == 'opinion': s['countries']['B']['opinions']['A'] = 10
    elif change == 'ERI government':
        s['countries']['A'].update(original_tag='ERI', leader='Eritrean Transitional Government')
        s['countries']['A']['flags'].add('ETH_transitional_government_FLAG')
    elif change == 'sender flagged': s['countries']['A']['flags'].add('trade_agreement@B')
    elif change == 'receiver flagged': s['countries']['B']['flags'].add('trade_agreement@A')
    elif change == 'both flagged': establish(s)
    else:
        s['countries']['B']['allies'].add('C'); s['countries']['C']['wars'].add('A')
    before = [(deepcopy(s['countries'][x]['flags']), deepcopy(s['countries'][x]['modifiers']), s['countries'][x]['variables'].get('signed_trade_agreements', 0)) for x in ('A', 'B')]
    assert not trigger(one(trade, 'can_be_accepted'), s, context())
    finish(s)
    after = [(s['countries'][x]['flags'], s['countries'][x]['modifiers'], s['countries'][x]['variables'].get('signed_trade_agreements', 0)) for x in ('A', 'B')]
    assert after == before and not s['external_influence']
    assert not reserved(s, 'A') and not reserved(s, 'B')
    cases.append('acceptance revalidates ' + change)

for eu, opinion in product((False, True), (10, 11, 50, 51)):
    s = state(); s['countries']['SWI']['opinions']['A'] = opinion
    if eu: s['countries']['A']['ideas'].add('EU_member')
    assert send(s, 'A', 'SWI') == (opinion > (10 if eu else 50))
    cases.append('preserved Swiss/EU admission ' + str((eu, opinion)))

for response in ('complete_effect', 'reject_effect'):
    s = state(); assert send(s, 'A', 'C'); before = stable(s)
    finish(s, response, 'A', 'B'); assert stable(s) == before
    finish(s, response, 'B', 'C'); assert stable(s) == before
    cases.append('unrelated callback preserves reservations ' + response)
    s = state(); s['countries']['A']['variables']['pending_trade_offer_country'] = 'B'
    assert not trigger(one(trade, 'can_be_accepted'), s, context())
    finish(s, response); assert not reserved(s, 'A') and not signed(s)
    assert not s['external_influence'] and not s['countries']['A']['modifiers']
    cases.append('legacy outbound-only safe cleanup ' + response)

# Storyline signing during a native request does not invalidate the actual treaty.
for response in ('complete_effect', 'reject_effect'):
    s = state(); assert send(s); establish(s); before = [(deepcopy(s['countries'][n]['flags']), deepcopy(s['countries'][n]['modifiers']), s['countries'][n]['variables']['signed_trade_agreements']) for n in ('A', 'B')]
    assert not trigger(one(trade, 'can_be_accepted'), s, context())
    finish(s, response)
    assert before == [(s['countries'][n]['flags'], s['countries'][n]['modifiers'], s['countries'][n]['variables']['signed_trade_agreements']) for n in ('A', 'B')]
    assert not s['external_influence'] and not reserved(s, 'A') and not reserved(s, 'B')
    cases.append('storyline signed before native response ' + response)

for flags, count_a, count_b in product(((False, False), (True, False), (False, True), (True, True)), (-3, 0, 1, 5), (-3, 0, 1, 5)):
    s = state(); establish(s, 'A', 'C')
    for name, partner, own_flag, count in (('A', 'B', flags[0], count_a), ('B', 'A', flags[1], count_b)):
        s['countries'][name]['variables']['signed_trade_agreements'] = count
        if own_flag:
            s['countries'][name]['flags'].add('trade_agreement@' + partner)
            s['countries'][name]['modifiers'].update(((partner, 'mutual_trade_agreement'), (partner, 'mutual_trade_opinion')))
    existing_other = deepcopy(s['countries']['C'])
    assert trigger(one(cancel, 'visible'), s, context()) == any(flags)
    perform(s, one(cancel, 'complete_effect'))
    assert not signed(s) and 'trade_agreement@C' in s['countries']['A']['flags']
    assert s['countries']['C'] == existing_other
    for name, has_flag, before_count in (('A', flags[0], count_a), ('B', flags[1], count_b)):
        assert s['countries'][name]['variables']['signed_trade_agreements'] == (max(0, before_count - 1) if has_flag else before_count)
        partner = 'B' if name == 'A' else 'A'
        assert ((partner, 'broke_trade_agreement') in s['countries'][name]['modifiers']) == any(flags)
    before = stable(s); perform(s, one(cancel, 'complete_effect')); assert stable(s) == before
    cases.append('side-specific cancellation ' + str((flags, count_a, count_b)))

# Withdrawal retains the reservation until the original response is consumed.
for response in ('complete_effect', 'reject_effect'):
    s = state(); assert send(s); establish(s)
    perform(s, one(cancel, 'complete_effect'))
    assert not signed(s) and reserved(s, 'A') and reserved(s, 'B')
    assert not send(s, 'A', 'B')
    assert not trigger(one(trade, 'can_be_accepted'), s, context())
    before = deepcopy((s['countries']['A']['modifiers'], s['countries']['B']['modifiers']))
    finish(s, response)
    assert before == (s['countries']['A']['modifiers'], s['countries']['B']['modifiers'])
    assert not reserved(s, 'A') and not reserved(s, 'B') and not signed(s)
    assert send(s, 'A', 'B')
    cases.append('withdrawn response drains safely ' + response)

# Helper annex API is called by the root-owned on_actions integration.
for pending in ('outgoing matching', 'incoming matching', 'unrelated outgoing', 'unrelated incoming', 'none'):
    s = state(); establish(s); establish(s, 'A', 'C'); establish(s, 'C', 'D')
    variable = 'pending_trade_offer_country' if 'outgoing' in pending else 'eon_trade_treaty_pending_sender'
    if pending != 'none':
        s['countries']['A']['variables'][variable] = 'B' if 'matching' in pending else 'D'
        s['countries']['A']['flags'].add('eon_trade_treaty_withdrawn')
    s['countries']['B']['exists'] = False
    other = deepcopy((s['countries']['C'], s['countries']['D']))
    s['temp'] = {'eon_trade_treaty_partner': 'B'}
    execute(effects['eon_trade_treaty_cleanup_annexed_pair'], s, context('A', 'A'))
    assert not signed(s) and 'trade_agreement@C' in s['countries']['A']['flags']
    assert s['countries']['A']['variables']['signed_trade_agreements'] == 1
    assert s['countries']['B']['variables']['signed_trade_agreements'] == 0
    assert (s['countries']['C'], s['countries']['D']) == other
    if 'unrelated' in pending:
        assert s['countries']['A']['variables'][variable] == 'D'
        assert 'eon_trade_treaty_withdrawn' in s['countries']['A']['flags']
    else: assert not reserved(s, 'A') and 'eon_trade_treaty_withdrawn' not in s['countries']['A']['flags']
    before = stable(s); execute(effects['eon_trade_treaty_cleanup_annexed_pair'], s, context('A', 'A')); assert stable(s) == before
    assert not any(mod == 'broke_trade_agreement' for name in ('A', 'B') for target, mod in s['countries'][name]['modifiers'])
    cases.append('annex removes only vanished partner ' + pending)

for sender, receiver in (('SIN', 'B'), ('A', 'SIN')):
    s = state(); assert send(s, sender, receiver); finish(s, sender=sender, receiver=receiver)
    sin = s['countries']['SIN']['variables']
    assert sin['signed_trade_agreements'] == 1
    assert compare(sin['SIN_foreign_influence_strength'], '=', 0.02)
    assert compare(sin['SIN_bureaucracy_cost_multiplier_modifier_strength'], '=', 0.02)
    assert 'SIN' in s['external_refresh']
    perform(s, one(cancel, 'complete_effect'), sender, receiver)
    assert sin['signed_trade_agreements'] == sin['SIN_foreign_influence_strength'] == sin['SIN_bureaucracy_cost_multiplier_modifier_strength'] == 0
    cases.append('Singapore sender and receiver refresh ' + sender)

for flags, a_count, b_count in product(((False, False), (True, False), (False, True), (True, True)), (-3, 5), (-3, 5)):
    s = state()
    for country, partner, flag_present, count in (('A', 'B', flags[0], a_count), ('B', 'A', flags[1], b_count)):
        s['countries'][country]['variables']['signed_trade_agreements'] = count
        if flag_present: s['countries'][country]['flags'].add('trade_agreement@' + partner)
    establish(s)
    assert signed(s)
    assert s['countries']['A']['variables']['signed_trade_agreements'] == (a_count if flags[0] else max(0, a_count) + 1)
    assert s['countries']['B']['variables']['signed_trade_agreements'] == (b_count if flags[1] else max(0, b_count) + 1)
    before = stable(s); establish(s); assert stable(s) == before
    cases.append('pair helper accounts only newly created own flags ' + str((flags, a_count, b_count)))

s = state(); assert send(s); s['countries']['A']['flags'].add('eon_trade_treaty_withdrawn')
perform(s, effects['eon_trade_treaty_clear_pending'], 'A', 'A')
assert not reserved(s, 'A') and 'eon_trade_treaty_withdrawn' not in s['countries']['A']['flags']
before = stable(s); perform(s, effects['eon_trade_treaty_clear_pending'], 'A', 'A'); assert stable(s) == before
assert reserved(s, 'B'), 'Own clear does not touch another country; annex pair integration clears survivors'
cases.append('annexed own request state clears without altering survivors')

# Pure pair helpers do not add native influence and are idempotent for retries.
s = state(); establish(s); before = stable(s); establish(s); assert stable(s) == before
assert not s['external_influence']
cases.append('pair establishment idempotent without native influence')

defects = []
s = state(); perform(s, one(old_trade, 'on_sent_effect'), 'A', 'B'); perform(s, one(old_trade, 'on_sent_effect'), 'A', 'C')
assert s['countries']['A']['variables']['pending_trade_offer_country'] == 'C'
perform(s, one(old_trade, 'reject_effect'), 'A', 'B')
assert not reserved(s, 'A'); defects.append('old request overwritten and old rejection clears new request')
s = state(); perform(s, one(old_trade, 'on_sent_effect')); s['countries']['B']['wars'].add('A')
perform(s, one(old_trade, 'complete_effect')); assert signed(s)
defects.append('old acceptance signs after direct war begins')
perform(s, one(old_trade, 'complete_effect'))
assert s['countries']['A']['variables']['signed_trade_agreements'] == 2 and len(s['external_influence']) == 4
defects.append('old acceptance repeat inflates counters and influence')
s = state(); establish(s); perform(s, one(old_cancel, 'complete_effect')); perform(s, one(old_cancel, 'complete_effect'))
assert s['countries']['A']['variables']['signed_trade_agreements'] == -1
defects.append('old repeated cancellation creates negative signed count')
s = state(); perform(s, one(old_trade, 'on_sent_effect'), 'A', 'SIN'); perform(s, one(old_trade, 'complete_effect'), 'A', 'SIN')
assert s['countries']['SIN']['variables']['signed_trade_agreements'] == 1 and 'SIN_foreign_influence_strength' not in s['countries']['SIN']['variables']
defects.append('old Singapore receiver lacks modifier refresh')
cases.extend('baseline defect ' + d for d in defects)

# Preserve the policies and calculations as AST, including the any/allied nuance.
assert triggers['eon_trade_treaty_terms_available'][2:] == one(old_trade, 'selectable')
for action, previous in ((trade, old_trade), (cancel, old_cancel)):
    for key in ('allowed', 'cost', 'requires_acceptance', 'show_acceptance_on_action_button', 'icon', 'ai_desire'):
        assert one(action, key) == one(previous, key), ('Changed inherited policy', key)
assert one(trade, 'ai_acceptance') == one(old_trade, 'ai_acceptance')

def influence_branches(nodes):
    result = []
    for k, o, v in nodes:
        if isinstance(v, list):
            if any(name == 'change_influence_percentage' for name, op, value in v):
                result.append([n for n in v if n[0] in ('set_temp_variable', 'change_influence_percentage')])
            result.extend(influence_branches(v))
    return result

assert influence_branches(one(trade, 'complete_effect')) == influence_branches(one(old_trade, 'complete_effect'))
old_raw, new_raw = baseline(ACTION_PATH), (ROOT / ACTION_PATH).read_bytes()
assert old_raw.startswith(b'\xef\xbb\xbf') == new_raw.startswith(b'\xef\xbb\xbf')
assert old_raw.count(b'\r\n') == new_raw.count(b'\r\n') == 0
assert old_raw.endswith(b'\n') == new_raw.endswith(b'\n')
for language in ('english', 'russian'):
    raw = (ROOT / f'localisation/{language}/eon_trade_treaty_l_{language}.yml').read_bytes()
    assert raw.startswith(b'\xef\xbb\xbf')
    keys = re.findall(r'^ ([A-Za-z0-9_]+):', raw.decode('utf-8-sig'), re.M)
    assert len(keys) == len(set(keys)) == 5
    assert all(key in keys for key in ('eon_trade_treaty_no_pending_tt', 'eon_trade_treaty_response_valid_tt',
                                     'eon_trade_treaty_propose_desc', 'eon_trade_treaty_accept_desc', 'eon_trade_treaty_cancel_desc'))

print(json.dumps({'all_passed': True, 'total_cases': len(cases), 'cases': cases,
                  'baseline_defects_reproduced': defects,
                  'source_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in (ACTION_PATH, TRIGGER_PATH, EFFECT_PATH)},
                  'preserved': ['Swiss/EU/ERI/allied policy AST', '75 PP and AI scoring', 'native influence source branches', 'BOM/EOL/EOF'],
                  'proof_scope': 'source-driven symbolic callbacks and helper annex API; native game delivery, AI, full influence/GUI calculations and root-owned on_actions require separate acceptance'}, indent=2))
