"""Private humanitarian scoring island; never installs, starts a game or changes profiles."""
from pathlib import Path
from copy import deepcopy
from itertools import product
import hashlib
import json

ROOT = Path(SOURCE_ROOT).resolve()
OUT = Path(__file__).resolve().parent
REL = 'common/scripted_diplomatic_actions/eon_humanitarian_aid_actions.txt'
TRIGGERS = 'common/scripted_triggers/eon_humanitarian_aid_triggers.txt'
sha = lambda raw: hashlib.sha256(raw).hexdigest()

# Reuse current bounded humanitarian definitions; do not run its lifecycle suite.
adapter = ROOT / 'tools/validation/humanitarian_aid/test_aid.py'
source = adapter.read_text(encoding='utf-8-sig')
boundary = '\n# Inspect current integration order without executing the migration registry.'
assert source.count(boundary) == 1
ns = {'__file__': str(adapter), '__name__': 'private_ai_desire_actual_ast'}
exec(compile(source.split(boundary)[0], str(adapter), 'exec'), ns)
ast, one = ns['ast'], ns['one']

before = (OUT / 'before' / REL).read_bytes()
eol = b'\r\n' if b'\r\n' in before else b'\n'
island = b'   modifier = { factor = 0 NOT = { eon_humanitarian_aid_offer_ready = yes } }' + eol
assert before.count(island) == 1
offset = before.index(island)
after = (ROOT / REL).read_bytes()
assert after == before[:offset] + before[offset + len(island):], 'Exact current scoring island required'
assert after.startswith(b'\xef\xbb\xbf') == before.startswith(b'\xef\xbb\xbf')
assert after.count(b'\r\n') == before.count(b'\r\n') - int(eol == b'\r\n')
assert after[:offset] + island + after[offset:] == before

old_actions = one(ast(before.decode('utf-8-sig')), 'scripted_diplomatic_actions')
new_actions = one(ast(after.decode('utf-8-sig')), 'scripted_diplomatic_actions')
old_offer = one(old_actions, 'eon_offer_humanitarian_aid')
new_offer = one(new_actions, 'eon_offer_humanitarian_aid')
old_weight, new_weight = (one(o, 'ai_desire') for o in (old_offer, new_offer))
removed_ast = ('modifier', '=', [('factor', '=', '0'), ('NOT', '=', [('eon_humanitarian_aid_offer_ready', '=', 'yes')])])
assert old_weight[-1] == removed_ast
assert old_weight[:-1] == new_weight
assert [r for r in old_offer if r[0] != 'ai_desire'] == [r for r in new_offer if r[0] != 'ai_desire']
assert one(old_actions, 'eon_withdraw_humanitarian_aid') == one(new_actions, 'eon_withdraw_humanitarian_aid')
assert set(r[0] for r in old_actions) == set(r[0] for r in new_actions)
assert new_weight[0] == ('base', '=', '0')
assert [r for r in new_weight if r[0] == 'modifier'][0][2] == [
 ('add', '=', '1'), ('eon_humanitarian_aid_offer_ready', '=', 'yes'),
 ('ROOT', '=', [('check_variable', '=', [('var', '=', 'treasury'), ('value', '=', '1'), ('compare', '=', 'greater_than_or_equals')]),
               ('check_variable', '=', [('display_income', '>', 'display_expense')])])]

# The removed assessment may overwrite one TEMP field, but never persistent data.
helpers = ns['m']['capacity_triggers']
allowed_scalar = {'exists', 'has_war', 'tag', 'has_war_with', 'is_subject', 'has_country_flag'}
allowed_blocks = {'OR', 'NOT', 'ROOT', 'PREV', 'check_variable', 'set_temp_variable', 'add_to_temp_variable'}
closure = {}
def inspect(nodes, stack=()):
 for key, op, value in nodes:
  if key in helpers:
   assert op == '=' and value in ('yes', 'no') and key not in stack
   closure[key] = helpers[key]
   inspect(helpers[key], stack + (key,))
  elif key in allowed_scalar:
   assert op == '=' and isinstance(value, str)
  elif key in allowed_blocks:
   assert op == '=' and isinstance(value, list)
   if key in {'OR', 'NOT', 'ROOT', 'PREV'}: inspect(value, stack)
   else: assert all(isinstance(v, str) for _, _, v in value)
  else: raise AssertionError(('Unknown/impure readiness primitive', key, op, value))
inspect([('eon_humanitarian_aid_offer_ready', '=', 'yes')])
assert one(helpers['eon_humanitarian_aid_cash_available'], 'set_temp_variable') == [('eon_humanitarian_aid_projected_fund', '=', 'eon_refugee_relief_fund')]
assert one(helpers['eon_humanitarian_aid_cash_available'], 'add_to_temp_variable') == [('eon_humanitarian_aid_projected_fund', '=', '0.1')]
assert sum(key == 'set_temp_variable' for body in closure.values() for key, _, _ in body) == 1
assert sum(key == 'add_to_temp_variable' for body in closure.values() for key, _, _ in body) == 1

original_trigger = ns['trigger']
def traced_trigger(nodes, state, frame):
 for key, _, value in nodes:
  if key == 'eon_humanitarian_aid_offer_ready': state['readiness_calls'] += 1
  if key in ('set_temp_variable', 'add_to_temp_variable'):
   state['temp_trace'].append((key, frame['scope'], deepcopy(value)))
 return original_trigger(nodes, state, frame)
ns['m']['trigger'] = traced_trigger

def score(nodes, state, donor=101, recipient=202):
 state['readiness_calls'] = 0
 state['temp_trace'] = []
 value = 0
 for key, op, body in nodes:
  assert op == '='
  if key in ('base', 'factor'):
   assert isinstance(body, str)
   value = float(body)
  elif key == 'modifier':
   checks = [r for r in body if r[0] not in ('add', 'factor')]
   if traced_trigger(checks, state, ns['frame'](donor, recipient)):
    for operation, operator, amount in body:
     if operation == 'add': value += float(amount)
     elif operation == 'factor': value *= float(amount)
  else: raise AssertionError(('Unknown score primitive', key))
 return value

groups = {}
positive = negative = 0
temp_witnesses = []
def compare(case, group):
 global positive, negative
 old, new = deepcopy(case), deepcopy(case)
 old['temp'] = {'unrelated_existing_temp': 812.25, 'eon_humanitarian_aid_projected_fund': -77.5}
 new['temp'] = deepcopy(old['temp'])
 initial_countries = deepcopy(case['countries'])
 old_score, new_score = score(old_weight, old), score(new_weight, new)
 assert old_score == new_score, ('Score mismatch', group, case)
 assert old_score in (0, 1)
 assert old['temp'] == new['temp'], ('TEMP final value drift', group, old['temp'], new['temp'])
 assert old['countries'] == new['countries'] == initial_countries
 assert old['readiness_calls'] == 2 and new['readiness_calls'] == 1
 for result in (old, new):
  assert not result['debits'] and not result['events'] and not result['effect_trace']
 # Compare all modeled state other than intentionally fewer readiness/TEMP writes.
 assert {k: v for k, v in old.items() if k not in ('readiness_calls', 'temp_trace')} == {k: v for k, v in new.items() if k not in ('readiness_calls', 'temp_trace')}
 if old_score: positive += 1
 else: negative += 1
 groups[group] = groups.get(group, 0) + 1
 if group == 'explicit_TEMP_witnesses':
  temp_witnesses.append({'score': old_score, 'final_TEMP': old['temp'],
                         'old_readiness_calls': old['readiness_calls'], 'candidate_readiness_calls': new['readiness_calls'],
                         'old_TEMP_trace': old['temp_trace'], 'candidate_TEMP_trace': new['temp_trace']})

def fixture():
 s = ns['state'](treasury=2, fund=0, hosted=1)
 for actor in s['countries']:
  s['countries'][actor]['variables'].update(display_income=2, display_expense=1)
 return s

# Exhaustive combinations of admission, need, record ownership and pair restrictions.
for bits in product((False, True), repeat=12):
 s=fixture(); donor=s['countries'][101]; receiver=s['countries'][202]
 donor['exists'], receiver['exists'], donor['subject'] = bits[:3]
 receiver['variables']['eon_refugees_hosted'] = int(bits[3])
 receiver['wars'] = {404} if bits[4] else set()
 if bits[5]: receiver['wars'].add(101)
 if bits[6]: donor['wars'].add(202)
 for on, flag in zip(bits[7:11], ('eon_humanitarian_aid_pending', 'eon_humanitarian_aid_live', 'eon_humanitarian_aid_cancelled', 'eon_humanitarian_aid_quarantined')):
  if on: donor['flags'].add(flag)
 donor['variables']['eon_humanitarian_aid_partner'] = 202 if bits[11] else 0
 compare(s, '4096_admission_need_and_owned_slot_combinations')

# Exact lower/upper payment boundaries and profitable/break-even/loss-making budgets.
for fund, treasury, net, retired, cooldown in product(
 (-1, 0, 9.89999, 9.9, 9.90001, 10),
 (-.1, .099999, .1, .999999, 1, 1000000, 1000000.01),
 (-1, 0, 1), (False, True), (False, True)):
 s=fixture(); donor=s['countries'][101]; receiver=s['countries'][202]
 donor['variables']['treasury'] = treasury
 donor['variables']['display_income'] = 1 + net
 receiver['variables']['eon_refugee_relief_fund'] = fund
 if retired: donor['flags'].add('eon_humanitarian_aid_retired_pair@202')
 if cooldown: donor['flags'].add('eon_humanitarian_aid_cooldown@202')
 compare(s, '504_cash_profit_and_pair_boundaries')

for recipient in (101, 202, 303, 404):
 s=fixture()
 # Test native-context relocation through the exact source readiness helper.
 original_frame=ns['frame']
 ns['frame']=lambda donor, ignored, receiver=recipient: original_frame(donor, receiver)
 try: compare(s, 'self_and_three_distinct_recipient_frames')
 finally: ns['frame']=original_frame

for case_name in ('ready_profitable', 'ready_unprofitable', 'fund_above_limit', 'no_need'):
 s=fixture()
 if case_name == 'ready_unprofitable': s['countries'][101]['variables']['display_income']=0
 elif case_name == 'fund_above_limit': s['countries'][202]['variables']['eon_refugee_relief_fund']=9.90001
 elif case_name == 'no_need': s['countries'][202]['variables']['eon_refugees_hosted']=0
 compare(s, 'explicit_TEMP_witnesses')
 temp_witnesses[-1]['case'] = case_name

# Strict island admission: absent/duplicated original islands and foreign bytes fail.
def admissible(old, candidate):
 assert old.count(island) == 1, 'Original island is absent or duplicated'
 cut=old.index(island)
 expected=old[:cut] + old[cut+len(island):]
 assert candidate == expected, 'Foreign bytes or incorrect scoring island'
 assert candidate[:cut] + island + candidate[cut:] == old
 return True
assert admissible(before, after)
mutants={
 'foreign_cost': after.replace(b'  cost = 0', b'  cost = 75', 1),
 'foreign_base': after.replace(b'   base = 0', b'   base = 2', 1),
 'foreign_eligibility': after.replace(b'ROOT = { is_subject = no }', b'ROOT = { is_subject = yes }', 1),
 'original_island_retained': before,
 'two_original_islands': before[:offset] + island + before[offset:]}
for label, mutant in mutants.items():
 try: admissible(before, mutant)
 except AssertionError: pass
 else: raise AssertionError(('Foreign byte mutation accepted', label))
for original in (after, before[:offset] + island + before[offset:]):
 try: admissible(original, after)
 except AssertionError: pass
 else: raise AssertionError('Absent/duplicate before island accepted')
groups['strict_owned_byte_admission_negative_controls'] = len(mutants) + 2

# Restore only the private executor namespace; no source writes.
ns['m']['trigger'] = original_trigger
assert sum(groups.values()) == 4615 and positive + negative == 4608
assert (ROOT/REL).read_bytes()==after
report={'status':'ACTUAL_CURRENT_HUMANITARIAN_AI_SCORE_AST_PASS_NOT_NATIVE',
 'checks':sum(groups.values()),'actual_model_cases':4608,'negative_byte_cases':7,
 'groups':groups,'score_one_cases':positive,'score_zero_cases':negative,
 'TEMP_witnesses':temp_witnesses,'actual_current_AST_executed':True,
 'native_scheduler_or_AI_choice_or_FPS_proven':False,'public_written':False}
