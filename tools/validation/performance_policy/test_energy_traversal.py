"""Actual delivery AST equivalence and byte ownership, not campaign timing."""
from pathlib import Path
from copy import deepcopy
from collections import Counter
import hashlib,json,sys,unittest,inspect
from energy_traversal_byte_compat import CATALOG,restore_energy_traversal,negative_controls,_economy_bytes

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/validation/diplomacy_package_25'))
import test_delivery as m
PATH=CATALOG['path']
NAME=CATALOG['function']
ARRAY='eon_energy_delivery_participants'
BREAK='eon_energy_delivery_participant_loop_break'
PHASES=('prepare_round','dispatch_round','commit_round','apply_country')
BASE=m.one(m.ast(CATALOG['original']),NAME)
CURRENT=m.one(m.ast((ROOT/PATH).read_text(encoding='utf-8-sig')),NAME)

def clean(s):
    value=deepcopy(s)
    assert value['global']['arrays'].get(ARRAY,[])==[]
    value['global']['arrays'].pop(ARRAY,None)
    value['temp'].pop(BREAK,None)
    return value

class EnergyTraversal(unittest.TestCase):
    def tearDown(self):m.effects[NAME]=deepcopy(CURRENT)
    def test_01_exact_owned_body(self):
        raw=(ROOT/PATH).read_bytes()
        self.assertEqual(hashlib.sha256(_economy_bytes.restore_adjacent_state_refresh(PATH,raw)).hexdigest(),CATALOG['after_sha256'])
        restored=restore_energy_traversal(PATH,raw.decode('utf-8-sig'))
        self.assertEqual(hashlib.sha256(restored.encode()).hexdigest(),CATALOG['before_sha256'])
        self.assertEqual(raw.startswith(b'\xef\xbb\xbf'),CATALOG['before_bom'])
        self.assertNotIn(b'\r\n',raw) if CATALOG['newline']=='LF' else self.assertNotIn(b'\n',raw.replace(b'\r\n',b''))
        self.assertEqual(len(negative_controls(raw.decode('utf-8-sig'))),4)
    def test_02_existing_actual_source_98_scenarios(self):
        results=[]
        for body in (BASE,CURRENT):
            m.effects[NAME]=deepcopy(body);m.groups.clear();m.native.clear()
            results.append(m.tests())
        self.assertEqual(results[0],results[1])
        self.assertEqual(sum(results[0].values()),98)
    def compare_case(self,initial,operation=None,hostile_break=False):
        signatures=[]
        for body in (BASE,CURRENT):
            s=deepcopy(initial);m.effects[NAME]=deepcopy(body)
            if hostile_break:
                # Source helpers share one invocation frame; preserve caller's
                # unrelated break, but give new loops their own explicit zero.
                s['temp']={'break':1,BREAK:99}
                m.execute(m.effects[NAME],s,m.context(200))
            else:m.run(s,actor=200)
            if operation:operation(s)
            m.conservation(s);signatures.append(clean(s))
        self.assertEqual(signatures[0],signatures[1])
    def test_03_200_countries_chain(self):
        inputs={i:(0,5) for i in range(1,201)}
        inputs.update({1:(40,10),2:(0,5),3:(0,4),4:(20,5)})
        s=m.state(inputs)
        for edge in ((1,2,20),(2,3,12),(4,3,10)):m.pair(s,*edge)
        self.compare_case(s)
    def test_04_empty_contracts_and_former_participant_cleanup(self):
        self.compare_case(m.state({i:(0,5) for i in range(1,201)}))
        s=m.state({i:(30 if i==1 else 0,5) for i in range(1,201)});m.pair(s,1,2,10)
        def terminate(state):
            for owner,partner in ((1,2),(2,1)):
                data=state['countries'][owner]
                for field in ('energy_contractors','energy_contracts_ammount','energy_contracts_price'):data['arrays'][field].clear()
                data['flags'].discard('energy_agreement@'+str(partner))
            m.run(state,actor=200)
            for owner in (1,2):self.assertNotIn('eon_energy_delivery_participant',state['countries'][owner]['flags'])
        self.compare_case(s,terminate)
    def test_05_annex_and_war_rebuild(self):
        s=m.state({i:(30 if i==1 else 0,5) for i in range(1,201)});m.pair(s,1,2,10)
        def annex(state):state['countries'][2]['exists']=False;m.run(state,actor=200)
        self.compare_case(s,annex)
        def war(state):
            state['countries'][1]['wars'].add(2);state['countries'][2]['wars'].add(1)
            m.run(state,actor=200)
        self.compare_case(s,war)
    def test_06_preserve_root_prev_and_country_order(self):
        s=m.state({i:(30 if i==1 else 0,5) for i in (200,3,1,2)});m.pair(s,1,2,10)
        signatures=[]
        original=m.execute
        for body in (BASE,CURRENT):
            records=[];m.effects[NAME]=deepcopy(body)
            def trace(nodes,state,context):
                for phase in PHASES:
                    if nodes is m.effects['eon_energy_delivery_'+phase]:
                        records.append((phase,context['scope'],context['root'],context['from_'],context['prev']))
                return original(nodes,state,context)
            m.execute=trace
            try:m.run(deepcopy(s),actor=200)
            finally:m.execute=original
            self.assertTrue(records)
            self.assertTrue(all(record[2]==200 and record[4]==(200,) for record in records))
            signatures.append(records)
        self.assertEqual(signatures[0],signatures[1])
    def test_07_unrelated_break_does_not_truncate_new_phase(self):
        s=m.state({i:(30 if i==1 else 0,5) for i in range(1,201)});m.pair(s,1,2,10)
        self.compare_case(s,hostile_break=True)
    def test_08_scope_iterator_fail_closed_and_explicit_global_tokens(self):
        s=m.state({1:(0,5)});s['global']['arrays']['tokens']=[1]
        with self.assertRaises(AssertionError):
            m.execute(m.ast('for_each_scope_loop = { array = global.tokens break = b0 UNKNOWN_NATIVE_EFFECT = yes }'),s,m.context(1))
        with self.assertRaises(AssertionError):
            m.execute(m.ast('for_each_scope_loop = { array = local_unknown break = b0 always = yes }'),s,m.context(1))
    def test_09_actual_phase_visits_follow_participants(self):
        inputs={i:(0,5) for i in range(1,201)}
        inputs.update({1:(40,10),2:(0,5),3:(0,4),4:(20,5)})
        counts=[];original=m.execute
        interpreter=inspect.getsource(original)
        for iterator in ('every_country','for_each_scope_loop'):
            needle="        elif k=='"+iterator+"':\n"
            self.assertEqual(interpreter.count(needle),1)
            addition=("            perf_phase=next((p for p in eon_perf_phase_names if 'eon_energy_delivery_'+p in str(v)),None)\n"
                      "            if perf_phase:\n"
                      "                eon_perf_visits[k]+=sum(d['exists'] for d in s['countries'].values()) if k=='every_country' else len(s['global']['arrays'][eon_perf_array])\n")
            interpreter=interpreter.replace(needle,needle+addition,1)
        for body in (BASE,CURRENT):
            visits=Counter();state=m.state(inputs);m.effects[NAME]=deepcopy(body)
            for edge in ((1,2,20),(2,3,12),(4,3,10)):m.pair(state,*edge)
            m.__dict__.update(eon_perf_phase_names=PHASES,eon_perf_visits=visits,eon_perf_array=ARRAY)
            exec(compile(interpreter,'<test-only iterator counters>','exec'),m.__dict__)
            try:m.run(state,actor=200)
            finally:m.execute=original
            counts.append(visits)
        self.assertEqual(counts[0],Counter(every_country=2000))
        self.assertEqual(counts[1],Counter(for_each_scope_loop=40))

if __name__=='__main__':unittest.main()
