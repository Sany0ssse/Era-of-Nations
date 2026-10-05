"""Bounded source interpreter. This checks script invariants, not the HOI4 engine."""
from pathlib import Path
from dataclasses import dataclass, field
from decimal import Decimal
import copy
import hashlib
import itertools
import json
import re
import subprocess

from _support import ROOT
SOURCE = ROOT / 'common/scripted_diplomatic_actions/00_scripted_diplomatic_actions.txt'
BASELINE = '15de79473f59ada089b98d1757a8c1fe34893f9b'

@dataclass
class Node:
    key: str
    op: str
    value: object
    start: int
    end: int

def parse(text):
    pattern = r'"(?:\\.|[^"\\])*"|#[^\n]*|[{}]|>=|<=|=|>|<|[^\s{}=<>#"]+'
    tokens = [(m.group(), m.start(), m.end()) for m in re.finditer(pattern, text) if not m.group().startswith('#')]
    i = 0
    def block():
        nonlocal i
        result = []
        while i < len(tokens) and tokens[i][0] != '}':
            key, start, _ = tokens[i]; i += 1
            op = tokens[i][0]; i += 1
            assert op in ('=', '<', '>', '<=', '>='), (key, op)
            val, _, end = tokens[i]; i += 1
            if val == '{':
                val = block()
                assert tokens[i][0] == '}'
                end = tokens[i][2]; i += 1
            result.append(Node(key, op, val, start, end))
        return result
    result = block()
    assert i == len(tokens), 'Unbalanced source'
    return result

def child(nodes, key):
    found = [n for n in nodes if n.key == key]
    assert len(found) == 1, (key, len(found))
    return found[0]

@dataclass
class Country:
    ident: int
    variables: dict = field(default_factory=dict)
    # Temporary variables belong to one effect evaluation, not a country/save.
    temp: dict = field(default_factory=dict, compare=False)
    captured: list = field(default_factory=list)
    arrays: dict = field(default_factory=dict)
    opinion: set = field(default_factory=set)
    flags: set = field(default_factory=set)
    exists: bool = True
    ai: bool = False
    wars: set = field(default_factory=set)
    projects: list = field(default_factory=list)

class Interpreter:
    def __init__(self, donor, recipient, remove_all=False):
        self.donor, self.recipient = donor, recipient
        self.countries = {donor.ident: donor, recipient.ident: recipient}
        self.temp = {}
        donor.temp = recipient.temp = self.temp
        self.freed = []
        self.remove_all = remove_all
    def country(self, token, stack):
        if token == 'ROOT': return self.donor
        if token == 'THIS': return stack[-1]
        if token == 'PREV': return stack[-2]
        raise ValueError('Unknown country ' + token)
    def value(self, token, stack):
        if isinstance(token, list):
            result = Decimal(0)
            for n in token:
                if n.key == 'value': result = self.value(n.value, stack)
                elif n.key == 'multiply': result *= self.value(n.value, stack)
                else: raise ValueError('Unknown modeled math statement: ' + n.key)
            return result
        try: return Decimal(token)
        except Exception: pass
        if token in ('ROOT', 'THIS', 'PREV'): return Decimal(self.country(token, stack).ident)
        if '.' in token:
            owner, variable = token.split('.', 1)
            country = self.country(owner, stack)
        else: country, variable = stack[-1], token
        if variable == 'id': return Decimal(country.ident)
        return country.temp.get(variable, country.variables.get(variable, Decimal(0)))
    def target(self, token, stack):
        if '.' in token:
            owner, variable = token.split('.', 1)
            return self.country(owner, stack), variable
        return stack[-1], token
    def params(self, nodes): return {n.key: n.value for n in nodes}
    def check(self, nodes, stack):
        p = self.params(nodes)
        if 'var' in p:
            a, b = self.value(p['var'], stack), self.value(p['value'], stack)
            op = p.get('compare', 'equals')
        else:
            assert len(nodes) == 1
            n = nodes[0]
            a, b, op = self.value(n.key, stack), self.value(n.value, stack), n.op
        return {'=': a == b, 'equals': a == b, 'not_equals': a != b,
                '>': a > b, 'greater_than': a > b,
                '<': a < b, 'less_than': a < b,
                '>=': a >= b, 'greater_than_or_equals': a >= b,
                '<=': a <= b, 'less_than_or_equals': a <= b}[op]
    def trigger(self, nodes, stack=None):
        if stack is None:
            self.temp = {}
            self.donor.temp = self.recipient.temp = self.temp
            stack = [self.recipient]
        for n in nodes:
            c, k, v = stack[-1], n.key, n.value
            if k == 'tooltip': continue
            if k in ('ROOT', 'THIS', 'PREV'):
                ok = self.trigger(v, stack + [self.country(k, stack)])
            elif k in ('AND', 'custom_trigger_tooltip'): ok = self.trigger(v, stack)
            elif k == 'NOT': ok = not self.trigger(v, stack)
            elif k == 'OR': ok = any(self.trigger([x], stack) for x in v)
            elif k == 'exists': ok = c.exists == (v == 'yes')
            elif k == 'is_ai': ok = c.ai == (v == 'yes')
            elif k == 'has_war_with': ok = self.country(v, stack).ident in c.wars
            elif k == 'has_captured_operative': ok = self.country(v, stack).ident in c.captured
            elif k == 'check_variable': ok = self.check(v, stack)
            elif k == 'is_in_array':
                p = self.params(v)
                ok = int(self.value(p['value'], stack)) in c.arrays.get(p['array'], [])
            elif k in ('set_temp_variable', 'multiply_temp_variable', 'clamp_temp_variable'):
                self.effect([n], stack); ok = True
            else: raise ValueError('Unknown modeled trigger: ' + k)
            if not ok: return False
        return True
    def flag(self, token, stack):
        for alias in ('ROOT', 'PREV', 'THIS'):
            if '@' + alias in token:
                token = token.replace('@' + alias, '@' + str(self.country(alias, stack).ident))
        return token
    def effect(self, nodes, stack=None):
        if stack is None:
            self.temp = {}
            self.donor.temp = self.recipient.temp = self.temp
            stack = [self.recipient]
        for n in nodes:
            c, k, v = stack[-1], n.key, n.value
            if k in ('log', 'ingame_update_setup', 'custom_effect_tooltip', 'break'): continue
            if k in ('ROOT', 'THIS', 'PREV'):
                self.effect(v, stack + [self.country(k, stack)])
            elif k == 'if':
                if self.trigger(child(v, 'limit').value, stack):
                    self.effect([x for x in v if x.key != 'limit'], stack)
            elif k == 'while_loop_effect':
                limit = child(v, 'limit').value
                rest = [x for x in v if x.key not in ('limit', 'break')]
                count = 0
                while self.trigger(limit, stack):
                    self.effect(rest, stack)
                    count += 1
                    assert count < 1000, 'Nonterminating cleanup'
            elif k in ('set_variable', 'set_temp_variable', 'multiply_variable', 'multiply_temp_variable', 'subtract_from_variable', 'add_to_variable'):
                assert len(v) == 1
                owner, variable = self.target(v[0].key, stack)
                store = owner.temp if 'temp' in k else owner.variables
                value = self.value(v[0].value, stack)
                if k.startswith('set_'): store[variable] = value
                elif k.startswith('multiply_'): store[variable] = store.get(variable, Decimal(0)) * value
                elif k == 'add_to_variable': store[variable] = store.get(variable, Decimal(0)) + value
                else: store[variable] = store.get(variable, Decimal(0)) - value
            elif k in ('clamp_variable', 'clamp_temp_variable'):
                p = self.params(v)
                owner, variable = self.target(p['var'], stack)
                store = owner.temp if 'temp' in k else owner.variables
                value = store.get(variable, Decimal(0))
                if 'max' in p: value = min(value, self.value(p['max'], stack))
                if 'min' in p: value = max(value, self.value(p['min'], stack))
                store[variable] = value
            elif k == 'clear_variable': c.variables.pop(v, None)
            elif k == 'clr_country_flag': c.flags.discard(self.flag(v, stack))
            elif k == 'set_country_flag':
                p = self.params(v); c.flags.add(self.flag(p['flag'], stack))
            elif k in ('add_opinion_modifier', 'reverse_add_opinion_modifier', 'remove_opinion_modifier'):
                p = self.params(v); other = self.country(p['target'], stack)
                item = (other.ident, p['modifier'])
                if k == 'remove_opinion_modifier': c.opinion.discard(item)
                elif k == 'add_opinion_modifier': c.opinion.add(item)
                else: other.opinion.add((c.ident, p['modifier']))
            elif k == 'modify_treasury_effect':
                assert v == 'yes'
                self.effect(TREASURY_HELPER, stack)
            elif k == 'free_random_operative':
                p = self.params(v); captor = self.country(p['captured_by'], stack)
                assert c.ident in captor.captured, 'Freed an absent captive'
                captor.captured.remove(c.ident)
                self.freed.append((c.ident, captor.ident))
            elif k == 'remove_from_array':
                p = self.params(v); value = int(self.value(p['value'], stack)); arr = c.arrays[p['array']]
                if self.remove_all: arr[:] = [x for x in arr if x != value]
                elif value in arr: arr.remove(value)
            else: raise ValueError('Unknown modeled effect: ' + k)

def country(ident, treasury=100, debt=100):
    return Country(ident, {'treasury': Decimal(str(treasury)), 'debt': Decimal(str(debt))})

def financial(c): return (c.variables['treasury'], c.variables['debt'])
def callback(action, name): return child(action.value, name).value

# Expand the actual helper instead of reproducing its arithmetic in a stub.
# The bounded parser intentionally refuses changed/unknown helper statements.
budget_raw = (ROOT / 'common/scripted_effects/00_budget_effects.txt').read_bytes()
budget_text = budget_raw.decode('utf-8-sig')
treasury_matches = list(re.finditer(r'(?ms)^modify_treasury_effect\s*=\s*\{.*?^\}', budget_text))
assert len(treasury_matches) == 1, 'Missing or duplicate treasury helper'
TREASURY_HELPER = child(parse(treasury_matches[0].group()), 'modify_treasury_effect').value
assert all(n.key in ('custom_effect_tooltip', 'add_to_variable', 'clamp_variable', 'ingame_update_setup') for n in TREASURY_HELPER), 'Unmodeled treasury helper statement'

raw = SOURCE.read_bytes()
source = raw.decode('utf-8-sig')
tree = parse(source)
actions = child(tree, 'scripted_diplomatic_actions').value
ids = [n.key for n in actions]
assert len(ids) == len(set(ids)), 'Duplicate action ID remains'
debt = child(actions, 'diplo_action_assume_debt')
ransom = child(actions, 'negotiate_operative_release')
exchange = child(actions, 'negotiate_operative_exchange')
investment = child(actions, 'cancel_mutual_investment_treaty')
assert child(debt.value, 'cost').value == '75'
assert child(investment.value, 'cost').value == '75'
assert child(ransom.value, 'cost').value == child(exchange.value, 'cost').value == '50'

counts = dict(debt_send=0, debt_settlement=0, debt_wrong_pair_refusal_retry=0,
              ransom_send=0, operative_outcomes=0, operative_cross_requests=0,
              debt_changed_country=0, operative_changed_custody_budget=0,
              operative_legacy_safe_refusal=0, investment_both_directions_duplicates=0, baseline_defects=0)

for old_debt, wallet in itertools.product((0, 4, 20, 400), (0, 1, 5, 1000)):
    a, b = country(1, wallet), country(2, debt=old_debt)
    vm = Interpreter(a, b)
    expected = old_debt > 0 and Decimal(wallet) >= Decimal(old_debt) / 4
    assert vm.trigger(callback(debt, 'can_be_sent')) == expected
    vm.effect(callback(debt, 'on_sent_effect'))
    assert a.variables.get('assuming_debt_value', 0) == (Decimal(old_debt) / 4 if expected else 0)
    assert a.variables.get('pending_assume_debt_offer', 0) == (2 if expected else 0)
    assert financial(a)[0] == wallet, 'Snapshot must not debit money'
    counts['debt_send'] += 1

for new_debt, wallet in itertools.product((0, 5, 25, 100, 200), (0, 4, 5, 24, 25, 100)):
    a, b = country(1, 100), country(2, debt=100)
    vm = Interpreter(a, b); vm.effect(callback(debt, 'on_sent_effect'))
    a.variables['treasury'] = Decimal(wallet); b.variables['debt'] = Decimal(new_debt)
    before_a, before_b = financial(a), financial(b)
    amount = Decimal(min(25, new_debt))
    valid = amount > 0 and wallet >= amount
    assert vm.trigger(callback(debt, 'can_be_accepted')) == valid
    vm.effect(callback(debt, 'complete_effect'))
    paid = before_a[0] - a.variables['treasury']
    reduced = before_b[1] - b.variables['debt']
    assert paid == reduced == (amount if valid else 0)
    assert a.variables['treasury'] >= 0 and b.variables['debt'] >= 0
    assert 'assuming_debt_value' not in a.variables and 'pending_assume_debt_offer' not in a.variables
    assert 'assuming_debt_repayment_value' not in a.variables
    result = copy.deepcopy((a, b)); vm.effect(callback(debt, 'complete_effect'))
    assert (a, b) == result, 'Duplicate callback changed settled payment'
    counts['debt_settlement'] += 1

for outcome in ('complete_effect', 'reject_effect'):
    a, b = country(1), country(2)
    Interpreter(a, b).effect(callback(debt, 'on_sent_effect'))
    c = country(3); before = copy.deepcopy(a)
    Interpreter(a, c).effect(callback(debt, outcome))
    assert a == before, 'Wrong partner callback removed another offer'
    vm = Interpreter(a, b); before_money = (financial(a), financial(b))
    vm.effect(callback(debt, 'reject_effect'))
    assert (financial(a), financial(b)) == before_money
    assert vm.trigger(callback(debt, 'can_be_sent')), 'Refusal blocked retry'
    vm.effect(callback(debt, 'on_sent_effect'))
    assert not vm.trigger(callback(debt, 'can_be_sent')), 'Pending offer could be overwritten'
    counts['debt_wrong_pair_refusal_retry'] += 1

for donor_exists, recipient_exists, war in itertools.product((False, True), (False, True), (False, True)):
    a, b = country(1), country(2)
    vm = Interpreter(a, b); vm.effect(callback(debt, 'on_sent_effect'))
    a.exists = donor_exists; b.exists = recipient_exists
    if war: b.wars.add(1)
    valid = donor_exists and recipient_exists and not war
    assert vm.trigger(callback(debt, 'can_be_accepted')) == valid
    before_a, before_b = financial(a), financial(b)
    vm.effect(callback(debt, 'complete_effect'))
    assert before_a[0] - a.variables['treasury'] == before_b[1] - b.variables['debt'] == (25 if valid else 0)
    assert 'pending_assume_debt_offer' not in a.variables and 'assuming_debt_repayment_value' not in a.variables
    counts['debt_changed_country'] += 1

for wallet, target_wallet, captured in itertools.product((0, 1.99, 2, 100), (0, 999998, 999999), (False, True)):
    a, b = country(1, wallet), country(2, target_wallet)
    if captured: b.captured = [1]
    vm = Interpreter(a, b)
    expected = captured and wallet >= 2 and target_wallet <= 999998
    assert vm.trigger(callback(ransom, 'can_be_sent')) == expected
    vm.effect(callback(ransom, 'on_sent_effect'))
    assert a.variables.get('pending_operative_release_mode', 0) == (1 if expected else 0)
    counts['ransom_send'] += 1

for action, mode in ((ransom, 1), (exchange, 2)):
    for outcome, captive_gone, broke, gone, war in itertools.product(('complete_effect', 'reject_effect'), (False, True), (False, True), (False, True), (False, True)):
        a, b = country(1, 10), country(2, 10)
        a.captured = [2, 3, 2]; b.captured = [1, 3, 1]
        vm = Interpreter(a, b); vm.effect(callback(action, 'on_sent_effect'))
        assert a.variables['pending_operative_release_mode'] == mode
        assert not vm.trigger(callback(ransom, 'can_be_sent')) and not vm.trigger(callback(exchange, 'can_be_sent'))
        if captive_gone: b.captured = [3]
        if broke: a.variables['treasury'] = Decimal(1)
        if gone: b.exists = False
        if war: a.wars.add(2); b.wars.add(1)
        before_money = a.variables['treasury'] + b.variables['treasury']
        before_captives = (list(a.captured), list(b.captured))
        valid = not captive_gone and not gone and (mode == 2 or not broke)
        assert vm.trigger(callback(action, 'can_be_accepted')) == valid
        vm.effect(callback(action, outcome))
        succeeds = outcome == 'complete_effect' and valid
        assert len(vm.freed) == ((2 if mode == 2 else 1) if succeeds else 0)
        assert a.variables['treasury'] + b.variables['treasury'] == before_money
        assert (a.variables['treasury'] == (Decimal(1) if broke else Decimal(10)) - (2 if succeeds and mode == 1 else 0))
        if not succeeds: assert (a.captured, b.captured) == before_captives
        assert a.captured.count(3) == b.captured.count(3) == 1
        assert 'pending_negotiate_operative_release_offer' not in a.variables and 'pending_operative_release_mode' not in a.variables
        settled = copy.deepcopy((a, b)); vm.effect(callback(action, outcome))
        assert (a, b) == settled, 'Duplicate operative response changed settlement'
        counts['operative_outcomes'] += 1

for action, wrong_action in ((ransom, exchange), (exchange, ransom)):
    for outcome in ('complete_effect', 'reject_effect'):
        a, b = country(1), country(2); a.captured = [2]; b.captured = [1]
        vm = Interpreter(a, b); vm.effect(callback(action, 'on_sent_effect'))
        before = copy.deepcopy((a, b)); vm.effect(callback(wrong_action, outcome))
        assert (a, b) == before, 'Wrong mode callback changed another request'
        c = country(3); c.captured = [1]
        before_a = copy.deepcopy(a); Interpreter(a, c).effect(callback(action, outcome))
        assert a == before_a, 'Wrong partner callback changed another request'
        counts['operative_cross_requests'] += 1

for action, own_captive_gone, donor_exists, receiver_wallet in itertools.product((ransom, exchange), (False, True), (False, True), (0, 999998, 999999)):
    a, b = country(1, 10), country(2, 10)
    a.captured = [2, 3]; b.captured = [1, 3]
    vm = Interpreter(a, b); vm.effect(callback(action, 'on_sent_effect'))
    if own_captive_gone: a.captured = [3]
    a.exists = donor_exists; b.variables['treasury'] = Decimal(receiver_wallet)
    valid = donor_exists and (not own_captive_gone if action is exchange else receiver_wallet <= 999998)
    assert vm.trigger(callback(action, 'can_be_accepted')) == valid
    before_money = a.variables['treasury'] + b.variables['treasury']
    vm.effect(callback(action, 'complete_effect'))
    assert len(vm.freed) == ((2 if action is exchange else 1) if valid else 0)
    assert a.variables['treasury'] + b.variables['treasury'] == before_money
    assert 'pending_negotiate_operative_release_offer' not in a.variables and 'pending_operative_release_mode' not in a.variables
    counts['operative_changed_custody_budget'] += 1

for action, wrong_pair in itertools.product((ransom, exchange), (False, True)):
    a, b = country(1), country(2); a.captured = [2]; b.captured = [1]
    a.variables['pending_negotiate_operative_release_offer'] = Decimal(2)
    # Missing mode is the pre-patch representation and must never imply approval.
    vm = Interpreter(a, b)
    assert not vm.trigger(callback(action, 'can_be_accepted'))
    before = copy.deepcopy((a, b)); vm.effect(callback(action, 'complete_effect'))
    assert (a, b) == before
    if wrong_pair:
        c = country(3); c.captured = [1]
        Interpreter(a, c).effect(callback(action, 'reject_effect'))
        assert (a, b) == before, 'Legacy rejection touched another pair'
    else:
        vm.effect(callback(action, 'reject_effect'))
        assert 'pending_negotiate_operative_release_offer' not in a.variables
        assert 'pending_operative_release_mode' not in a.variables
        assert (financial(a), financial(b)) == (financial(before[0]), financial(before[1]))
        assert a.captured == before[0].captured and b.captured == before[1].captured and not vm.freed
    counts['operative_legacy_safe_refusal'] += 1

for remove_all, reverse, duplicates in itertools.product((False, True), (False, True), (0, 1, 3)):
    a, b = country(1), country(2)
    donor, receiver = (b, a) if reverse else (a, b)
    for owner, partner in ((a, b), (b, a)):
        owner.arrays['permanent_investment_targets'] = [3] + [partner.ident] * duplicates + [owner.ident, 4, 3]
        owner.opinion = {(partner.ident, 'mutual_investment_treaty_opinion'), (partner.ident, 'mutual_investment_treaty_trade_opinion'), (3, 'unrelated')}
        owner.flags = {'mutual_investment_treaty_@' + str(partner.ident), 'unrelated'}
        owner.projects = ['existing-building', 'pending-project']
    vm = Interpreter(donor, receiver, remove_all=remove_all)
    vm.effect(callback(investment, 'complete_effect'))
    for owner in (a, b):
        assert owner.arrays['permanent_investment_targets'] == [3, owner.ident, 4, 3]
        assert owner.opinion == {(3, 'unrelated')}
        assert owner.flags == {'unrelated'}
        assert owner.projects == ['existing-building', 'pending-project']
    counts['investment_both_directions_duplicates'] += 1

base_raw = subprocess.check_output(['git', 'show', BASELINE + ':common/scripted_diplomatic_actions/00_scripted_diplomatic_actions.txt'], cwd=ROOT)
base_text = base_raw.decode('utf-8-sig')
base_actions = child(parse(base_text), 'scripted_diplomatic_actions').value
changed = {'diplo_action_assume_debt', 'cancel_mutual_investment_treaty', 'negotiate_operative_release', 'negotiate_operative_exchange'}
for n in base_actions:
    if n.key not in changed:
        current = child(actions, n.key)
        assert base_text[n.start:n.end] == source[current.start:current.end], 'Unrelated action changed: ' + n.key
old_debt = child(base_actions, 'diplo_action_assume_debt')
a, b = country(1, 1), country(2, debt=100)
vm = Interpreter(a, b); vm.effect(callback(old_debt, 'on_sent_effect')); vm.effect(callback(old_debt, 'complete_effect'))
assert a.variables['treasury'] < 0, 'Baseline overdraft defect not reproduced'
counts['baseline_defects'] += 1
old_inv = child(base_actions, 'cancel_mutual_investment_treaty')
# Baseline nested ROOT opinion modifiers point to ROOT (self), not the partner.
body = child(child(callback(old_inv, 'complete_effect'), 'THIS').value, 'ROOT').value
assert all(child(n.value, 'target').value == 'ROOT' for n in body if n.key == 'remove_opinion_modifier')
counts['baseline_defects'] += 1
assert [n.key for n in base_actions].count('negotiate_operative_release') == 2
counts['baseline_defects'] += 1
old_ransom = [n for n in base_actions if n.key == 'negotiate_operative_release'][0]
a, b = country(1, 10), country(2, 10); b.captured = [1]
a.variables['pending_negotiate_operative_release_offer'] = Decimal(2)
vm = Interpreter(a, b); vm.effect(callback(old_ransom, 'complete_effect'))
assert a.variables['treasury'] + b.variables['treasury'] == 18, 'Baseline missing recipient credit not reproduced'
assert a.variables['pending_negotiate_operative_release_offer'] == 2, 'Baseline pending cleanup defect not reproduced'
counts['baseline_defects'] += 1

result = {'source_sha256': hashlib.sha256(raw).hexdigest(),
          'budget_source_sha256': hashlib.sha256(budget_raw).hexdigest(), 'counts': counts,
          'total_scenarios': sum(counts.values()), 'all_passed': True,
          'proof_scope': 'actual-source action and treasury-helper AST; COUNTRY/ROOT/PREV and shared temporary variables; bounded interpreter',
          'external_effect_limits': ['ingame_update_setup, tooltip/log rendering and native captive selection are abstracted; treasury helper arithmetic is expanded from source'],
          'not_proven': ['HOI4 callback timing/scopes', 'PP refund', 'AI choice frequency', 'save/load', 'legacy pending request migration', 'same-pair same-mode late callbacks after a retry']}
print(json.dumps(result, indent=2))
