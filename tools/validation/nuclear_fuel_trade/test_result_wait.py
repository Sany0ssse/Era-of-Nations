"""Execute generated private waiter AST; no native queue/AI simulation claim."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import shutil
import subprocess
import sys
import unittest
import model as b

NS='eon_private_fuel_probe'
TAGS={'USA':1,'HOL':2,'NEP':3}


class ResultWait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=TemporaryDirectory(prefix='eon-fuel-wait-')
        cls.source=Path(cls.tmp.name)/'source';cls.source.mkdir()
        (cls.source.parent/'export-receipt.json').write_text('{}')
        for folder in ('common/scripted_effects','common/scripted_triggers','common/on_actions'):
            shutil.copytree(b.ROOT/folder,cls.source/folder)
        paths=['common/scripted_guis/01_energy_gui.txt','common/scripted_guis/MD_money_scripted_gui.txt',
               'common/decisions/eon_uranium_decisions.txt','events/00_Energy_events.txt',b.FILES[2],
               'tools/validation/diplomacy_completion/check_native_grammar.py',
               'tools/validation/nuclear_fuel_trade/build_native_probe.py',
               'tools/validation/diplomacy_package_03/_support.py']
        paths += [str(next((b.ROOT/'history/countries').glob(tag+' - *.txt')).relative_to(b.ROOT)) for tag in TAGS]
        for rel in paths:
            out=cls.source/rel;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(b.ROOT/rel,out)
        cls.out=Path(cls.tmp.name)/'fixture'
        subprocess.run([sys.executable,str(b.ROOT/'tools/validation/nuclear_fuel_trade/build_native_probe.py'),
                        '--source-root',str(cls.source),'--out',str(cls.out),'--result-aware'],check=True,capture_output=True,text=True)
        cls.manifest=json.loads((cls.out/'manifest.json').read_text())
        for path in (cls.out/'mod').rglob('*'):
            if path.is_file():
                destination=cls.source/path.relative_to(cls.out/'mod');destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(path,destination)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def adapter(self):
        m=b.executor()
        for folder,catalog in (('scripted_effects',m.effects),('scripted_triggers',m.triggers)):
            catalog.update({k:v for k,o,v in m.ast((self.out/'mod/common'/folder/(NS+'_'+('effects' if folder=='scripted_effects' else 'triggers')+'.txt')).read_text())})
        oldexecute,oldtrigger,oldvalue,oldresolve=m.execute,m.trigger,m.value,m.resolve
        def value(s,c,key):
            if isinstance(key,str) and key in TAGS:return TAGS[key]
            if isinstance(key,str) and '.' in key and key.split('.',1)[0] in TAGS:
                tag,tail=key.split('.',1);return oldvalue(s,m.switch(c,TAGS[tag]),'THIS.'+tail)
            return oldvalue(s,c,key)
        def resolve(s,c,key):return TAGS[key] if key in TAGS else oldresolve(s,c,key)
        def groups(nodes):
            i=0
            while i<len(nodes):
                group=[nodes[i]];i+=1
                if group[0][0]=='if':
                    while i<len(nodes) and nodes[i][0] in ('else_if','else'):group.append(nodes[i]);i+=1
                yield group
        def execute(nodes,s,c):
            for group in groups(nodes):
                key,op,body=group[0]
                if key in TAGS:execute(body,s,m.switch(c,TAGS[key]))
                elif key=='log':s.setdefault('logs',[]).append(body)
                else:oldexecute(group,s,c)
        def trigger(nodes,s,c):
            for group in groups(nodes):
                key,op,body=group[0]
                passed=trigger(body,s,m.switch(c,TAGS[key])) if key in TAGS else oldtrigger(group,s,c)
                if not passed:return False
            return True
        m.value,m.resolve,m.execute,m.trigger=value,resolve,execute,trigger
        return m

    def pending(self,name='sell_accept',kind=2,accepted=True):
        m=self.adapter();s=b.state(m)
        spec=next(row for row in self.manifest['result_aware_wait']['cases'] if row['name']==name)
        own,peer=(5000,1000) if kind==2 else (1000,5000)
        for country,stock in ((1,own),(2,peer)):
            s['countries'][country]['vars'].update(var_reactor_material_stockpile=stock,
                                                   **{NS+'_cash_before':500,NS+'_fuel_before':stock})
        b.send(m,s,-500 if kind==2 else 500,.5)
        self.assertEqual(s['countries'][1]['vars'][b.P+'phase'],1)
        s['countries'][1]['vars'][NS+'_actual_total']=s['countries'][1]['vars'][b.P+'total']
        m.execute([(spec['prepare_effect'],'=','yes')],s,m.context(1,2))
        return m,s,spec

    def ready(self,m,s,spec):return m.trigger([(spec['ready_trigger'],'=','yes')],s,m.context(1,2))
    def poll(self,m,s,spec,peer=2):m.execute([(spec['poll_effect'],'=','yes')],s,m.context(1,peer))

    def test_accept_requires_real_response_and_original_result_acknowledgement(self):
        m,s,spec=self.pending();before=b.assets(s)
        self.assertFalse(self.ready(m,s,spec))
        self.poll(m,s,spec)
        self.assertFalse(any(row['id']==NS+'.'+str(spec['observer_bridge']) for row in s['events']))
        b.respond(m,s,'accept',2)
        self.assertFalse(self.ready(m,s,spec))
        b.acknowledge(m,s,2,2,1,3)
        self.assertFalse(self.ready(m,s,spec))
        b.acknowledge(m,s,2,2)
        self.assertTrue(self.ready(m,s,spec))
        s['events']=[];self.poll(m,s,spec);self.poll(m,s,spec)
        observers=[row for row in s['events'] if row['id']==NS+'.'+str(spec['observer_bridge'])]
        self.assertEqual(len(observers),1)
        self.assertEqual((observers[0]['target'],observers[0]['sender']),(2,1))
        self.assertEqual(b.assets(s),before)

    def test_refusal_requires_cleared_original_pair_and_unchanged_assets(self):
        m,s,spec=self.pending('sell_refuse');before=b.assets(s)
        b.respond(m,s,'refuse',2);self.assertFalse(self.ready(m,s,spec))
        b.acknowledge(m,s,2,3);self.assertTrue(self.ready(m,s,spec))
        self.assertEqual(b.assets(s),before)

    def test_purchase_waiter_uses_buyer_debit_and_seller_credit(self):
        m,s,spec=self.pending('buy_accept',1);before=b.assets(s)
        b.respond(m,s,'accept',1);self.assertFalse(self.ready(m,s,spec))
        b.acknowledge(m,s,1,2);self.assertTrue(self.ready(m,s,spec))
        self.assertLess(s['countries'][1]['vars']['treasury'],500)
        self.assertGreater(s['countries'][2]['vars']['treasury'],500)
        self.assertEqual(b.assets(s),before)

    def test_deadline_terminates_probe_without_fabricating_business_outcome(self):
        m,s,spec=self.pending();before=b.assets(s);phase=s['countries'][1]['vars'][b.P+'phase']
        nodes=m.ast((self.out/'mod/events'/(NS+'_events.txt')).read_text())
        event=next(body for key,op,body in nodes if key=='country_event' and m.one(body,'id')==NS+'.'+str(spec['deadline']))
        m.execute(m.one(event,'immediate'),s,m.context(1,2))
        self.assertIn(NS+'_finished',s['global']['flags'])
        self.assertEqual(s['countries'][1]['vars'][b.P+'phase'],phase)
        self.assertEqual(b.assets(s),before)
        self.assertFalse(self.ready(m,s,spec))
        self.assertTrue(any('FAIL wait_deadline_sell_accept' in line for line in s['logs']))

    def test_cleared_flags_cannot_hide_duplicate_goods_or_premature_cash(self):
        for variable,delta in (('var_reactor_material_stockpile',500),('treasury',-.0001)):
            with self.subTest(variable=variable):
                m,s,spec=self.pending();b.respond(m,s,'accept',2);b.acknowledge(m,s,2,2)
                self.assertTrue(self.ready(m,s,spec))
                s['countries'][1]['vars'][variable]+=delta
                self.assertFalse(self.ready(m,s,spec));s['events']=[];self.poll(m,s,spec)
                self.assertFalse(any(row['id']==NS+'.'+str(spec['observer_bridge']) for row in s['events']))

    def test_wrong_from_and_stale_case_do_not_queue_observer(self):
        m,s,spec=self.pending();b.respond(m,s,'accept',2);b.acknowledge(m,s,2,2)
        s['events']=[];self.poll(m,s,spec,3)
        self.assertFalse(s['events']);self.assertTrue(any('ABORT wrong_native_wait_frame' in line for line in s['logs']))
        m,s,spec=self.pending();b.respond(m,s,'accept',2);b.acknowledge(m,s,2,2)
        s['countries'][1]['vars'][NS+'_wait_case']+=1;s['events']=[];self.poll(m,s,spec)
        self.assertFalse(s['events'])

    def test_pending_wait_uses_two_hours_and_terminates_without_clock_progress(self):
        m,s,spec=self.pending();before=b.assets(s);s['events']=[]
        for _ in range(100):self.poll(m,s,spec)
        self.assertEqual(s['countries'][1]['vars'][NS+'_wait_attempts'],72)
        polls=[row for row in s['events'] if row['id']==NS+'.'+str(spec['poll_bridge'])]
        self.assertEqual(len(polls),72)
        self.assertTrue(all(row['delay']=={'hours':'2'} for row in polls))
        self.assertIn(NS+'_finished',s['global']['flags'])
        self.assertTrue(any('FAIL wait_attempt_limit_sell_accept' in line for line in s['logs']))
        self.assertFalse(any(row['id']==NS+'.'+str(spec['observer_bridge']) for row in s['events']))
        self.assertEqual(b.assets(s),before)
        self.assertEqual(s['countries'][1]['vars'][b.P+'phase'],1)

    def test_all_generated_recurring_schedules_have_positive_later_tick_delay(self):
        m=self.adapter()
        def walk(nodes):
            for key,op,body in nodes:
                yield key,op,body
                if isinstance(body,list):yield from walk(body)
        event_nodes=m.ast((self.out/'mod/events'/(NS+'_events.txt')).read_text())
        for spec in self.manifest['result_aware_wait']['cases']:
            ident=NS+'.'+str(spec['poll_bridge'])
            found=[body for key,op,body in walk(event_nodes+[(spec['poll_effect'],'=',m.effects[spec['poll_effect']])])
                   if key=='country_event' and isinstance(body,list) and m.one(body,'id')==ident
                   and not any(node[0]=='is_triggered_only' for node in body)]
            self.assertEqual(len(found),2,(spec['name'],len(found)))
            self.assertTrue(all(m.one(body,'hours')=='2' for body in found),spec['name'])
            self.assertEqual(spec['max_poll_attempts'],72)

    def test_first_native_frame_is_counted_after_initialization_once(self):
        m=self.adapter();s=b.state(m)
        nodes=m.ast((self.out/'mod/events'/(NS+'_events.txt')).read_text())
        event=next(body for key,op,body in nodes if key=='country_event' and m.one(body,'id')==NS+'.1')
        initial=m.one(m.one(event,'immediate'),'if')
        # Execute the actual counter initialization and frame guard prefix,
        # before the separate setup frame enters native AI/world predicates.
        body=[node for node in initial if node[0]!='limit']
        setup=max(index for index,node in enumerate(body)
                  if node[0]=='if' and m.one(node[2],'limit')==m.ast('tag = USA ROOT = { tag = USA }'))
        m.execute(body[:setup],s,m.context(1,0))
        self.assertEqual(s['global']['vars'][NS+'_passes'],1)
        self.assertEqual(s['global']['vars'][NS+'_fails'],0)
        self.assertEqual(sum('PASS frame_1' in row for row in s['logs']),1)
        def walk(items):
            for key,op,value in items:
                yield key,op,value
                if isinstance(value,list):yield from walk(value)
        counters={NS+'_passes',NS+'_fails'}
        late_resets=[node for node in walk(body[setup:]) if node[0]=='set_variable'
                     and any(k.removeprefix('global.') in counters and value=='0' for k,o,value in node[2])]
        self.assertFalse(late_resets,'No later reset may discard an already logged frame result')

    def test_buy_refusal_declares_quote_budget_and_negative_opinion_inputs(self):
        m=self.adapter()
        nodes=m.ast((self.out/'mod/events'/(NS+'_events.txt')).read_text())
        event=next(body for key,op,body in nodes if key=='country_event' and m.one(body,'id')==NS+'.40')
        def walk(items):
            for key,op,value in items:
                yield key,op,value
                if isinstance(value,list):yield from walk(value)
        assignments={}
        for key,op,body in walk(m.one(event,'immediate')):
            if key=='set_variable':
                for k,o,value in body:assignments.setdefault(k,value)
        self.assertEqual(assignments['temp_nuclear_fuel_price'],'0.1')
        self.assertEqual(assignments['temp_nuclear_fuel_ammount'],'500')
        self.assertEqual(assignments['display_income'],'0')
        self.assertEqual(assignments['display_expense'],'0')
        self.assertTrue(any(key=='add_opinion_modifier' and m.one(body,'modifier')==NS+'_bad_terms'
                            for key,op,body in walk(m.one(event,'immediate'))))
        opinions=m.one(m.ast((self.out/'mod/common/opinion_modifiers'/(NS+'_opinions.txt')).read_text()),'opinion_modifiers')
        self.assertEqual(m.one(m.one(opinions,NS+'_bad_terms'),'value'),'-250')

    def test_generated_source_binding_and_reader_negative_controls(self):
        result=subprocess.run([sys.executable,str(b.ROOT/'tools/validation/nuclear_fuel_trade/check_recorded_reader.py'),
                               '--manifest',str(self.out/'manifest.json')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        receipt=json.loads(result.stdout)
        self.assertGreaterEqual(len(receipt['rejected_controls']),12)
        self.assertTrue(receipt['strict_missing_receipt_rejected'])

    def test_private_ai_freeze_applies_to_subjects_only_and_preserves_clicks(self):
        m=self.adapter();s=b.state(m);s['global']['flags'].add(NS+'_active')
        controls=self.manifest['private_controls']
        for row in [item for item in controls if 'actor_zero_modifier' in item]:
            body=row['actor_zero_modifier'][2]
            condition=[node for node in body if node[0]!='factor']
            self.assertTrue(m.trigger(condition,s,m.context(1)))
            self.assertTrue(m.trigger(condition,s,m.context(2)))
            self.assertFalse(m.trigger(condition,s,m.context(3)))
            s['global']['flags'].remove(NS+'_active')
            self.assertFalse(m.trigger(condition,s,m.context(1)))
            s['global']['flags'].add(NS+'_active')
        rel='common/scripted_guis/MD_money_scripted_gui.txt'
        original=m.ast((b.ROOT/rel).read_text(encoding='utf-8-sig'))
        overlay=m.ast((self.out/'mod'/rel).read_text(encoding='utf-8-sig'))
        def strip_private(nodes):
            result=[]
            for key,op,body in nodes:
                if key=='ai_will_do':body=body[:-1]
                if isinstance(body,list):body=strip_private(body)
                result.append((key,op,body))
            return result
        self.assertEqual(strip_private(overlay),original)


if __name__=='__main__':unittest.main()
