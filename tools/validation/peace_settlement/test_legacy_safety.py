"""Execute bounded branches of the current legacy peace AST; not native proof.

Catches undeclared/zero divisors, tied-score subject seizure, collateral peace,
forced annex on mutual consent, and a stale forced-peace callback.
"""
from pathlib import Path
from copy import deepcopy
import hashlib, json, math, re, unittest
ROOT = Path(__file__).resolve().parents[3]
PATHS = {
    'peace': 'common/scripted_effects/peace_deal_scripted_effects.txt',
    'annex': 'common/on_actions/00_costili.txt',
    'recovery': 'common/on_actions/00_postwar_recovery.txt',
    'force': 'common/scripted_diplomatic_actions/MDC_enforce_peace_options.txt',
}
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|[=<>!]+|[^\s{}=<>!#"]+')
def parse(text):
    tokens = [m[0].strip('"') for m in TOKEN.finditer(text.lstrip('\ufeff')) if not m[0].startswith('#')]
    n = 0
    def block():
        nonlocal n
        out = []
        while n < len(tokens) and tokens[n] != '}':
            key = tokens[n]; n += 1
            if n >= len(tokens) or tokens[n] not in ('=', '<', '>', '<=', '>=', '!=', '=='):
                out.append(('__item__', '=', key)); continue
            op = tokens[n]; n += 1
            if tokens[n] == '{':
                n += 1; value = block(); assert tokens[n] == '}'; n += 1
            else: value = tokens[n]; n += 1
            out.append((key, op, value))
        return out
    out = block(); assert n == len(tokens); return out
def one(nodes, name):
    found = [v for k, o, v in nodes if k == name]
    assert len(found) == 1, (name, len(found))
    return found[0]
def walk(nodes):
    for k, o, v in nodes:
        yield k, o, v
        if isinstance(v, list): yield from walk(v)
def lists(nodes):
    yield nodes
    for k, o, v in nodes:
        if isinstance(v, list): yield from lists(v)
def source(name): return parse((ROOT / PATHS[name]).read_text(encoding='utf-8-sig'))
def math_window(nodes, target):
    candidates = [rows for rows in lists(nodes) if any(k == 'set_temp_variable' and any(a == target for a, _, _ in v) for k, _, v in rows)]
    assert candidates, target
    return candidates

class VM:
    def __init__(self, actor='A', partner='B'):
        self.root, self.other = actor, partner
        self.vars = {}; self.calls = []; self.call_flags = []; self.call_targets = []
        self.countries = {t: {'flags': set(), 'subjects': [], 'allies': [], 'properties': {
            'is_ai': 'yes', 'is_faction_leader': 'no', 'has_capitulated': 'no',
            'num_of_owned_factories': 0, 'num_owned_states': 0,
            'stability': .5, 'overall_productivity': 1,
            'industrial_complex_total': 0, 'num_of_damaged_civs': 0,
            'prev_stability': .5, 'prev_productivity': 1,
            'prev_num_of_factories': 0, 'prev_num_of_damaged_factories': 0,
        }} for t in ('A', 'B', 'P', 'Q', 'C', 'SOV', 'CHE')}
        self.countries[actor]['subjects'] = ['P']
        self.countries[partner]['subjects'] = ['Q']
        self.countries[actor]['allies'] = ['C']
    def ref(self, expr, scope, previous=()):
        parts = expr.split('.')
        if parts[0] == 'ROOT': out = self.root
        elif parts[0] == 'FROM': out = self.other
        elif parts[0] == 'THIS': out = scope
        elif parts[0] == 'PREV':
            count = len(parts)
            assert all(p == 'PREV' for p in parts), expr
            return previous[count - 1] if len(previous) >= count else self.other
        else: out = expr
        return out
    def value(self, expr, scope, previous=()):
        try: return float(expr)
        except (ValueError, TypeError): pass
        expr = expr.removeprefix('var:')
        if '.' in expr:
            prefix, key = expr.rsplit('.', 1)
            target = self.ref(prefix, scope, previous)
            return self.countries[target]['properties'].get(key, 0)
        return self.vars.get(expr, self.countries[scope]['properties'].get(expr, 0))
    def flag(self, expr, scope, previous=()):
        if '@' not in expr: return expr
        name, target = expr.split('@', 1)
        return name + '@' + self.ref(target, scope, previous)
    def condition(self, rows, scope, previous=()):
        results = []
        for k, op, v in rows:
            if k == 'AND': yes = self.condition(v, scope, previous)
            elif k == 'OR': yes = any(self.condition([r], scope, previous) for r in v)
            elif k == 'NOT': yes = not any(self.condition([r], scope, previous) for r in v)
            elif k in ('ROOT', 'FROM', 'THIS', 'PREV') or k.startswith('PREV.'):
                yes = self.condition(v, self.ref(k, scope, previous), (scope,) + previous)
            elif k == 'check_variable':
                key, cmp, val = v[0]; a, b = self.value(key, scope, previous), self.value(val, scope, previous)
                yes = {'=': a == b, '>': a > b, '<': a < b, '>=': a >= b, '<=': a <= b}[cmp]
            elif k == 'has_country_flag': yes = self.flag(v, scope, previous) in self.countries[scope]['flags']
            elif k == 'has_global_flag': yes = False
            elif k == 'all_owned_state': yes = True  # Fully occupied subject fixture.
            elif k == 'has_war_with': yes = True
            elif k == 'is_in_faction_with': yes = True
            elif k == 'always': yes = v == 'yes'
            elif k == 'tag': yes = scope == v
            else:
                assert k in ('is_ai', 'is_faction_leader', 'has_capitulated'), k
                yes = self.countries[scope]['properties'][k] == v
            results.append(yes)
        return all(results)
    def execute(self, rows, scope=None, previous=(), math_only=False):
        scope = scope or self.other; branch = None
        for k, op, v in rows:
            if k == 'limit': continue
            if k in ('if', 'else_if', 'else'):
                if k == 'if': branch = False
                if k != 'else' and math_only and any(a not in ('check_variable','AND','OR','NOT') for a, _, _ in one(v, 'limit')): continue
                take = not branch and (k == 'else' or self.condition(one(v, 'limit'), scope, previous))
                if take: self.execute(v, scope, previous, math_only); branch = True
            elif k in ('set_temp_variable','add_to_temp_variable','subtract_from_temp_variable','multiply_temp_variable','divide_temp_variable'):
                key, _, expr = v[0]; amount = self.value(expr, scope, previous)
                if k == 'set_temp_variable': self.vars[key] = amount
                elif k == 'add_to_temp_variable': self.vars[key] = self.vars.get(key, 0) + amount
                elif k == 'subtract_from_temp_variable': self.vars[key] = self.vars.get(key, 0) - amount
                elif k == 'multiply_temp_variable': self.vars[key] = self.vars.get(key, 0) * amount
                else:
                    assert amount > 0, ('non-positive/undefined denominator', key, expr, amount)
                    self.vars[key] = self.vars.get(key, 0) / amount
            elif k == 'clamp_temp_variable':
                key = one(v, 'var'); self.vars[key] = min(self.value(one(v, 'max'), scope), max(self.value(one(v, 'min'), scope), self.vars[key]))
            elif k in ('ROOT', 'FROM', 'THIS', 'PREV') or k.startswith('PREV.') or k in self.countries:
                if not math_only: self.execute(v, self.ref(k, scope, previous), (scope,) + previous)
            elif k.startswith('every_'):
                if math_only: continue
                targets = (self.countries[scope]['subjects'] if k == 'every_subject_country' else
                           self.countries[scope]['allies'] if k == 'every_allied_country' else list(self.countries))
                for target in targets:
                    if any(a == 'limit' for a, _, _ in v) and not self.condition(one(v, 'limit'), target, (scope,) + previous): continue
                    self.execute(v, target, (scope,) + previous)
            elif k in ('white_peace','start_peace_conference','set_autonomy','annex_country','add_timed_idea','add_offsite_building'):
                if not math_only:
                    self.calls.append((k, scope, deepcopy(v))); self.call_flags.append({t:set(d['flags']) for t,d in self.countries.items()})
                    self.call_targets.append(self.ref(one(v,'tag'),scope,previous) if k=='start_peace_conference' else None)
            elif k == 'set_country_flag':
                if not math_only:self.countries[scope]['flags'].add(self.flag(one(v,'flag') if isinstance(v,list) else v,scope,previous))
            elif k in ('log','set_global_flag','clr_country_flag'): pass
            else:
                assert math_only or k in ('cost','requires_acceptance','show_acceptance_on_action_button','icon','receive_description','accept_title','accept_description'), k

class LegacySafetyTests(unittest.TestCase):
    def test_occupied_subjects_remain_with_overlord_when_score_tied(self):
        body = one(source('peace'), 'trigger_peace_deal')
        ending = body[next(i for i, row in enumerate(body) if row[0] == 'if' and any(k == 'check_variable' and any(a == 'ceasefire_score_root' and val == 'var:ceasefire_score_this' for a, _, val in v) for k, _, v in one(row[2], 'limit'))):]
        m = VM(); m.vars.update(ceasefire_score_root=.2, ceasefire_score_this=.2); m.execute(ending)
        self.assertEqual([k for k, _, _ in m.calls], ['white_peace'], 'Tied consent seized subjects or ended collateral wars')
        self.assertEqual(m.calls[0][1:], ('B','ROOT'))
    def test_legacy_dispatch_marks_reciprocal_consent_through_async_conference(self):
        body=one(source('peace'),'trigger_peace_deal')
        at=next(i for i,row in enumerate(body) if row[0]=='if' and any(k=='check_variable' and any(a=='ceasefire_score_root' and val=='var:ceasefire_score_this' for a,_,val in v) for k,_,v in one(row[2],'limit')))
        ending=body[max(0,at-2):]
        for root_score,partner_score in ((.2,.2),(.8,.2),(.2,.8)):
            m=VM();m.vars.update(ceasefire_score_root=root_score,ceasefire_score_this=partner_score)
            m.execute(ending)
            self.assertEqual(len(m.calls),1)
            self.assertIn('eon_consensual_peace@B',m.call_flags[0]['A'])
            self.assertIn('eon_consensual_peace@A',m.call_flags[0]['B'])
            if root_score != partner_score:
                winner,loser=('B','A') if root_score>partner_score else ('A','B')
                self.assertEqual(m.calls[0][0],'start_peace_conference')
                self.assertEqual(m.calls[0][1],winner,'Conference ran in the losing country scope')
                self.assertEqual(m.call_targets[0],loser,'Conference tag did not resolve to the loser')
                self.assertAlmostEqual(m.value(one(m.calls[0][2],'score_factor'),winner),abs(root_score-partner_score))
                self.assertIn('custom_peace_in_progress',m.call_flags[0][winner])
                self.assertNotIn('custom_peace_in_progress',m.call_flags[0][loser])
            consentflags=[value for k,_,value in walk(ending) if k=='set_country_flag' and (one(value,'flag') if isinstance(value,list) else value).startswith('eon_consensual_peace@')]
            self.assertEqual(len(consentflags),2)
            self.assertTrue(all(not isinstance(v,list) or not any(k=='days' for k,_,_ in v) for v in consentflags),'Consent expired while native conference remained open')

    def test_conference_only_includes_signatories_and_native_subject_scope(self):
        body = one(source('peace'), 'trigger_peace_deal')
        conference = [v for k, _, v in walk(body) if k == 'start_peace_conference']
        self.assertEqual(len(conference), 2)
        for call in conference:
            self.assertEqual(one(call, 'winner_scope'), 'LIMITED', 'Consent included non-signing faction members')
            self.assertEqual(one(call, 'loser_scope'), 'LIMITED', 'Consent included non-signing faction members')
    def test_zero_factory_ratio_and_undeclared_subject_divisor(self):
        body = one(source('peace'), 'trigger_peace_deal')
        for variable in ('subject_ic', 'faction_members_ic', 'controlled_states_value'):
            candidates = math_window(body, variable)
            for rows in candidates:
                # Isolate the actual ratio prelude through its divide/guard before score use.
                start = next(i for i, (k, _, v) in enumerate(rows) if k == 'set_temp_variable' and any(a == variable for a, _, _ in v))
                m = VM(); m.vars.update(subject_score=.3, member_score=.3, ceasefire_score_this=.2, ceasefire_score_root=.2)
                m.execute(rows[max(0,start-1):], math_only=True)
                self.assertTrue(all(math.isfinite(v) for v in m.vars.values()))
    def test_subject_ratio_positive_factories_keeps_fraction(self):
        body = one(source('peace'), 'trigger_peace_deal')
        for rows in math_window(body, 'subject_ic'):
            if not any(k == 'set_temp_variable' and any(a == 'overlord_ic' for a, _, _ in v) for k, _, v in rows): continue
            start = next(i for i, (k, _, v) in enumerate(rows) if k == 'set_temp_variable' and any(a == 'subject_ic' for a, _, _ in v))
            m = VM(); m.countries['B']['properties']['num_of_owned_factories'] = 2
            m.countries['A']['properties']['num_of_owned_factories'] = 10
            m.vars.update(subject_score=.5,ceasefire_score_this=0,ceasefire_score_root=0)
            m.execute(rows[start-1:], scope='B', previous=('A',), math_only=True)
            self.assertAlmostEqual(m.vars['subject_ic'], .2)
            self.assertAlmostEqual(m.vars['subject_score'], .1)
    def test_normal_zero_damage_peace_has_finite_recovery_math(self):
        actions = one(source('recovery'), 'on_actions'); body = one(one(actions,'on_peace'), 'effect')
        for stable, productivity, factories, damage in ((.5,1,0,0),(0,0,0,0),(.5,1,10,0),(.5,1,10,5)):
            m=VM();m.countries['B']['properties'].update(stability=stable,overall_productivity=productivity,industrial_complex_total=factories,prev_num_of_damaged_factories=damage)
            m.execute(body)
            self.assertTrue(all(math.isfinite(v) for v in m.vars.values()))
    def test_every_division_has_a_positive_denominator_guard(self):
        def divisions(rows, guards=()):
            for k, _, value in rows:
                if k == 'divide_temp_variable':
                    yield value, guards
                if isinstance(value, list):
                    fresh = guards + (one(value, 'limit'),) if k in ('if','else_if') else guards
                    yield from divisions(value, fresh)
        counts=[]
        for body in (one(source('peace'),'trigger_peace_deal'),one(one(one(source('recovery'),'on_actions'),'on_peace'),'effect')):
            count=0
            for division,guards in divisions(body):
                denominator=division[0][2].removeprefix('var:')
                protecting=[(k,op,val) for guard in guards for k,_,value in walk(guard) if k=='check_variable' for k,op,val in value if k==denominator and op=='>' and val=='0']
                self.assertTrue(protecting,('Missing positive guard',division))
                m=VM();m.vars[denominator]=0
                self.assertFalse(m.condition([('check_variable','=',protecting)],'B'))
                m.vars[denominator]=2
                self.assertTrue(m.condition([('check_variable','=',protecting)],'B'))
                count+=1
            counts.append(count)
        self.assertEqual(counts,[18,4])

    def test_positive_recovery_ratios_preserve_existing_reward(self):
        body=one(one(one(source('recovery'),'on_actions'),'on_peace'),'effect')
        m=VM();m.countries['B']['properties'].update(stability=.25,prev_stability=.75,overall_productivity=2,prev_productivity=6,industrial_complex_total=5,prev_num_of_factories=15,num_of_damaged_civs=6,prev_num_of_damaged_factories=2)
        m.execute(body)
        self.assertEqual([m.vars[k] for k in ('stability_postwar_rate','productivity_postwar_rate','factories_postwar_rate','factories_fixing_postwar_rate')],[3,3,3,3])
        self.assertEqual([k for k,_,_ in m.calls],['add_timed_idea','add_offsite_building'])
    def test_mutual_consent_does_not_auto_annex_but_one_flag_does_not_spoof(self):
        actions=one(source('annex'),'on_actions'); callbacks=[one(v,'effect') for k,_,v in actions if k=='on_peaceconference_ended']
        for reciprocal,want in ((True,False),(False,True)):
            m=VM();m.countries['A']['flags'].update(('annex_on_peace_conference@B','eon_consensual_peace@B'))
            if reciprocal:m.countries['B']['flags'].add('eon_consensual_peace@A')
            for body in callbacks:m.execute(body,scope='A')
            self.assertEqual(any(k=='annex_country' for k,_,_ in m.calls),want)
        for reciprocal,want in ((True,False),(False,True)):
            m=VM('SOV','CHE');m.countries['SOV']['flags'].add('eon_consensual_peace@CHE')
            if reciprocal:m.countries['CHE']['flags'].add('eon_consensual_peace@SOV')
            for body in callbacks:m.execute(body,scope='SOV')
            self.assertEqual(any(k=='annex_country' for k,_,_ in m.calls),want)
    def test_old_forced_peace_button_and_queued_callback_cannot_end_wars(self):
        body=one(one(source('force'),'scripted_diplomatic_actions'),'enforce_peace')
        m=VM()
        for field in ('allowed','visible','selectable','can_be_sent','can_be_accepted'):
            self.assertFalse(m.condition(one(body,field),'B'),field)
        m.execute(one(body,'complete_effect'))
        self.assertEqual(m.calls,[],'Saved stale force-peace callback changed war state')

if __name__=='__main__':
    unittest.main(verbosity=2)
