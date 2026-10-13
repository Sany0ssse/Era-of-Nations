"""Actual changed AST finite Boolean model; no full-country, native or speed claim."""
from pathlib import Path
import ast as pyast
import base64, copy, hashlib, json, random, re, unittest

HERE = Path(__file__).resolve().parent
ROOT = Path(SOURCE_ROOT).resolve()
SOURCE = 'common/scripted_effects/00_ai_investment_scripted_effects.txt'
CALLER = 'events/00_AC_events.txt'
P = 'eon_ai_country_encouraged_cache_'
manifest = json.loads((HERE / 'source_catalog.json').read_bytes())
manifest['files'] = [row for row in manifest['files'] if row['path'] in {SOURCE, CALLER}]
# Read the exact already-existing parser definitions only; no imports/main/models run.
parser_path = ROOT / 'tools/validation/diplomacy_package_24/_model.py'
parser_text = parser_path.read_text('utf-8-sig')
boundary = '\neffects = {}\n'
assert parser_text.count(boundary) == 1
ns = {'__file__': str(parser_path)}
exec(compile(parser_text.split(boundary)[0], str(parser_path), 'exec'), ns)
parse = ns['ast']

def node(nodes, name):
    values = [v for k, o, v in nodes if k == name]
    assert len(values) == 1, name
    return values[0]

def fragment(role):
    nodes = node(parse(((HERE / 'before' / SOURCE) if role == 'before' else (ROOT / SOURCE)).read_text('utf-8-sig')), 'AI_country_selection_calculation')
    if role == 'before':
        matches = [n for n in nodes if n[0] == 'if' and ('any_state', '=', [('has_state_flag', '=', 'currently_encouraged_investments')]) in node(n[2], 'limit')]
    else:
        matches = [n for n in nodes if n[0] == 'ROOT' and P + 'active' in str(n)]
    assert len(matches) == 1
    return matches[0], nodes

old, old_body = fragment('before'); new, new_body = fragment('candidate')
event = next(v for k, o, v in parse((ROOT / CALLER).read_text('utf-8-sig')) if k == 'country_event' and node(v, 'id') == 'AC_event.500')
immediate = node(event, 'immediate')
prefix = next(n for n in immediate if n[0] == 'ROOT' and P+'checked' in str(n))
suffix = next(n for n in immediate if n[0] == 'ROOT' and str(n).count(P+'active') == 1 and P+'checked' not in str(n))

class Model:
    """Whitelist for the exact pure island. Shared bare TEMPs are a declared model ABI."""
    def __init__(self, states, temp=None, root=1, this=2):
        self.states = states; self.temp = dict(temp or {}); self.root = root; self.this = this; self.scans = 0
    def condition(self, nodes):
        for k, op, value in nodes:
            if k == 'check_variable':
                name, compare, other = value[0]
                assert len(value) == 1 and compare == '=' and '.' not in name
                if self.temp.get(name, 0) != float(other): return False
            elif k == 'any_state':
                assert value == [('has_state_flag', '=', 'currently_encouraged_investments')]
                self.scans += 1
                if not any(s['encouraged'] for s in self.states): return False
            else: raise AssertionError(('Unknown changed trigger', k))
        return True
    def execute(self, nodes):
        i = 0
        while i < len(nodes):
            k, op, value = nodes[i]; i += 1
            if k == 'ROOT':
                old_scope = self.this; self.this = self.root
                try: self.execute(value)
                finally: self.this = old_scope
            elif k == 'if':
                fallback = nodes[i][2] if i < len(nodes) and nodes[i][0] == 'else' else None
                if fallback is not None: i += 1
                if self.condition(node(value, 'limit')): self.execute([n for n in value if n[0] != 'limit'])
                elif fallback is not None: self.execute(fallback)
            elif k in ('set_temp_variable', 'add_to_temp_variable'):
                assert len(value) == 1
                name, eq, other = value[0]; assert eq == '=' and '.' not in name
                assert name.startswith(P) or name == 'AI_country_score'
                self.temp[name] = float(other) if k == 'set_temp_variable' else self.temp.get(name, 0) + float(other)
            else: raise AssertionError(('Unknown changed effect', k))

def callback(model, eligible, candidate):
    if candidate: model.execute([prefix])
    scores = []
    for scope, exists, allowed, original_score in eligible:
        if not exists or not allowed: continue
        model.this = scope; model.temp['AI_country_score'] = original_score
        model.execute([new if candidate else old]); scores.append((scope, model.temp['AI_country_score']))
    if candidate: model.execute([suffix])
    return scores

class CandidateTests(unittest.TestCase):
    def test_raw_inverse_and_style(self):
        for row in manifest['files']:
            before = (HERE/'before'/row['path']).read_bytes(); after = (ROOT/row['path']).read_bytes(); inv = after
            self.assertEqual(hashlib.sha256(before).hexdigest(), row['before_sha256'])
            self.assertEqual(hashlib.sha256(after).hexdigest(), row['candidate_sha256'])
            self.assertEqual((ROOT/row['path']).read_bytes(), after)
            for z in reversed(row['patches']):
                a=base64.b64decode(z['after_b64']); b=base64.b64decode(z['before_b64']); at=z['offset']; self.assertEqual(inv[at:at+len(a)],a); inv=inv[:at]+b+inv[at+len(a):]
            self.assertEqual(inv, before)
            self.assertEqual(after.startswith(b'\xef\xbb\xbf'), before.startswith(b'\xef\xbb\xbf'))
            self.assertEqual(after.count(b'\r'), before.count(b'\r')); self.assertEqual(before.count(b'\r'), 0)
    def test_exact_unchanged_score_rng_loop_and_public_ids(self):
        self.assertEqual([n for n in old_body if n != old], [n for n in new_body if n != new])
        before=parse((HERE/'before'/SOURCE).read_text('utf-8-sig')); after=parse((ROOT/SOURCE).read_text('utf-8-sig'))
        self.assertEqual([k for k,o,v in before], [k for k,o,v in after])
        self.assertEqual([n for n in before if n[0]!='AI_country_selection_calculation'], [n for n in after if n[0]!='AI_country_selection_calculation'])
        old_event=next(v for k,o,v in parse((HERE/'before'/CALLER).read_text('utf-8-sig')) if k=='country_event' and node(v,'id')=='AC_event.500')
        self.assertEqual(node(old_event,'immediate'), [n for n in immediate if n not in (prefix,suffix)])
        self.assertEqual(str(old_body).count('set_temp_variable_to_random'), 1)
        self.assertEqual(str(new_body).count('set_temp_variable_to_random'), 1)
    def test_table_zero_one_many_missing_stale_and_existence(self):
        for count in (0,1,2,17,31):
            for truth in (False,True):
                for root in (1,20):
                    for stale in ({},{P+'active':1,P+'checked':1,P+'value':int(not truth)}):
                        for excluded in (False,True):
                            states=[{'owner':99,'encouraged':truth}]; eligible=[(i+30,not excluded or i%2==0,not excluded or i%3!=0,i%3) for i in range(count)]
                            a=Model(states,stale,root);b=Model(states,stale,root)
                            self.assertEqual(callback(a,eligible,False),callback(b,eligible,True)); t=sum(ex and ok for _,ex,ok,_ in eligible)
                            self.assertEqual(a.scans,t);self.assertEqual(b.scans,int(t>0));self.assertEqual(b.temp[P+'active'],0)
    def test_reset_between_callbacks_and_public_fallback(self):
        model=Model([{'owner':99,'encouraged':False}]);eligible=[(2,True,True,0),(3,True,True,0)]
        self.assertEqual(callback(model,eligible,True),[(2,0),(3,0)])
        model.states[0]['encouraged']=True
        self.assertEqual(callback(model,eligible,True),[(2,50),(3,50)])
        model.states[0]['encouraged']=False;model.temp['AI_country_score']=8
        model.execute([new]);self.assertEqual(model.temp['AI_country_score'],8)
        model.states[0]['encouraged']=True;model.execute([new]);self.assertEqual(model.temp['AI_country_score'],58)
        self.assertEqual(model.this,3)
    def test_order_ties_and_rng_sequence(self):
        for seed in range(50):
            rng=random.Random(seed);draws=[rng.randrange(25,101) for _ in range(12)];eligible=[(i+2,True,True,70-r) for i,r in enumerate(draws)]
            a=Model([{'owner':99,'encouraged':True}]);b=Model(a.states)
            sa=callback(a,eligible,False);sb=callback(b,eligible,True);self.assertEqual(sa,sb)
            self.assertEqual(max(sa,key=lambda x:x[1]),max(sb,key=lambda x:x[1]))
        # This uses identical synthetic draws plus static unchanged RNG-site/order proof, not native RNG.
    def test_meaningful_mutants_detected(self):
        eligible=[(2,True,True,0),(3,True,True,0)];states=[{'owner':99,'encouraged':True}]
        # Owned-state replacement would remove the original global +50 for both candidates.
        self.assertNotEqual(callback(Model(states),eligible,False),[(2,0),(3,0)])
        # Dropping reset reuses stale false despite changed world flags.
        stale=Model(states,{P+'active':1,P+'checked':1,P+'value':0});stale.temp['AI_country_score']=0;stale.execute([new]);self.assertNotEqual(stale.temp['AI_country_score'],50)
        # Unconditional query before loop regresses zero eligible candidates (old query count0).
        zero=Model(states);zero.condition([('any_state','=',[('has_state_flag','=','currently_encouraged_investments')])]);callback(zero,[],True);self.assertNotEqual(zero.scans,0)


def tests():
 stream=__import__('io').StringIO()
 result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CandidateTests))
 assert result.wasSuccessful() and result.testsRun==6,stream.getvalue()
 return {'checks':6,'actual_current_AST_executed':True,'bounded_pure_island_only':True,'native_callback_array_or_RNG_or_lifetime_proven':False}
