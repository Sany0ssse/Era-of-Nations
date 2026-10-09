"""Actual autonomous offer-preparation AST with explicit native fixture inputs.

The deterministic random-country oracle belongs to source_model. This suite
does not prove native random selection, GUI scheduling, or autonomous campaign
procurement. Send checks run the existing actual finished-fuel source adapter.
"""
from pathlib import Path
import copy
import importlib.util
import sys
import unittest
import model as fuel

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('fuel_prepare_uranium_source_model',
    ROOT/'tools/validation/uranium_resources/source_model.py')
u=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=u
spec.loader.exec_module(u)
AI='eon_nuclear_fuel_ai_prepare_offer'
REL='common/scripted_effects/eon_nuclear_fuel_ai_effects.txt'


class PrepareModel(u.Model):
    def trigger(self,nodes,stack):
        # has_nuclear_reactors is a declared native building input. Other
        # predicates and all quantity arithmetic still execute the source AST.
        native=[node for node in nodes if node[0]=='has_nuclear_reactors']
        for key,operator,value in native:
            assert operator=='=' and value in ('yes','no')
            present=self.entities[stack[-1]].native['building_level@nuclear_reactor']>0
            if present!=(value=='yes'):return False
        return super().trigger([node for node in nodes if node[0]!='has_nuclear_reactors'],stack)


class AutonomousPrepare(unittest.TestCase):
    def fixture(self,stock=1000,consumption=1000,production=0,peer_stock=35000,
                peer_consumption=1000,peer_production=0,raw=None):
        source=u.Source()
        body=source.hook(REL,[AI]) if raw is None else u.p.one(u.p.ast(raw),AI)
        source.effects[AI]=body
        m=PrepareModel(source)
        for name,own_stock,use,output in (('AAA',stock,consumption,production),
                                        ('BBB',peer_stock,peer_consumption,peer_production)):
            actor=m.entities[name]
            actor.ai=True
            actor.native['building_level@nuclear_reactor']=1
            actor.variables.update(treasury=500,var_reactor_material_stockpile=own_stock,
                nuclear_fuel_consumption=use,nuclear_reactor_fuel_production=output,
                nuclear_fuel_selling_selected_TAG=2,temp_nuclear_fuel_ammount=777,
                temp_nuclear_fuel_price=999)
        return m

    def prepare(self,m):
        before={key:(copy.deepcopy(entity.variables),set(entity.flags))
                for key,entity in m.entities.items() if entity.kind=='country'}
        m.effect([(AI,'=','yes')])
        # Preparation changes editor fields, never reserves or transfers assets.
        for key,(variables,flags) in before.items():
            actor=m.entities[key]
            self.assertEqual(actor.variables.get('treasury'),variables.get('treasury'))
            self.assertEqual(actor.variables.get('var_reactor_material_stockpile'),variables.get('var_reactor_material_stockpile'))
            self.assertEqual(actor.flags,flags)
        return m.entities['AAA'].variables

    def actual_send(self,m):
        executor=fuel.executor();s=fuel.state(executor)
        for name in ('AAA','BBB'):
            actor=m.entities[name];country=s['countries'][actor.ident]
            country['vars'].update(actor.variables)
            country['flags'].update(actor.flags)
            country.update(exists=actor.exists,ai=actor.ai,
                wars={m.entities[key].ident for key in actor.wars},
                embargoing={m.entities[key].ident for key in actor.embargoing},
                embargoed_by={other.ident for other in m.entities.values()
                              if other.kind=='country' and name in other.embargoing})
        before=fuel.assets(s)
        fuel.invoke(executor,s,'send',actor=1)
        self.assertEqual(fuel.assets(s),before)
        return s

    def test_buy_targets_26_weeks_and_supplier_retains_10_weeks(self):
        m=self.fixture();v=self.prepare(m)
        self.assertEqual(v['nuclear_fuel_selling_selected_TAG'],2)
        self.assertEqual(v['temp_nuclear_fuel_ammount'],25000)
        self.assertEqual(v['temp_nuclear_fuel_price'],.5)
        self.assertEqual(m.entities['BBB'].variables['var_reactor_material_stockpile']-v['temp_nuclear_fuel_ammount'],10000)
        s=self.actual_send(m)
        self.assertIn(fuel.P+'outgoing',s['countries'][1]['flags'])
        self.assertIn(fuel.P+'incoming',s['countries'][2]['flags'])
        self.assertEqual(s['events'][0]['id'],'energy.1')

    def test_buy_requires_below_4_weeks_reactors_and_output_shortage(self):
        for settings in ({'stock':4000},{'stock':1000,'production':1000},
                         {'stock':0,'consumption':0}):
            with self.subTest(settings=settings):
                m=self.fixture(**settings);self.assertEqual(self.prepare(m).get('nuclear_fuel_selling_selected_TAG',0),0)
        m=self.fixture();m.entities['AAA'].native['building_level@nuclear_reactor']=0
        self.assertEqual(self.prepare(m).get('nuclear_fuel_selling_selected_TAG',0),0)
        m=self.fixture(stock=3999)
        self.assertEqual(self.prepare(m)['temp_nuclear_fuel_ammount'],22001)
        # The actual minimum executable lot may exceed a tiny 26-week gap.
        m=self.fixture(stock=0,consumption=1)
        self.assertEqual(self.prepare(m)['temp_nuclear_fuel_ammount'],100)

    def test_purchase_candidates_require_exists_peace_embargo_access_exports_and_reserve(self):
        cases=('nonexistent','war','supplier_embargo','buyer_embargo','exports_blocked','reserved','insufficient_10week_surplus')
        for case in cases:
            with self.subTest(case=case):
                m=self.fixture();a,b=m.entities['AAA'],m.entities['BBB']
                if case=='nonexistent':b.exists=False
                elif case=='war':b.wars.add('AAA')
                elif case=='supplier_embargo':b.embargoing.add('AAA')
                elif case=='buyer_embargo':a.embargoing.add('BBB')
                elif case=='exports_blocked':b.flags.add('eon_nuclear_fuel_exports_blocked')
                elif case=='reserved':b.flags.add(fuel.P+'reserved')
                elif case=='insufficient_10week_surplus':b.variables['var_reactor_material_stockpile']=34999
                self.assertEqual(self.prepare(m).get('nuclear_fuel_selling_selected_TAG',0),0)
        # An importer may block its own exports and still seek an external seller.
        m=self.fixture();m.entities['AAA'].flags.add('eon_nuclear_fuel_exports_blocked')
        self.assertEqual(self.prepare(m)['nuclear_fuel_selling_selected_TAG'],2)

    def test_sale_preserves_26week_seller_buffer_and_caps_lot_at_chosen_buyer_need(self):
        m=self.fixture(stock=50000,production=2000,peer_stock=1000,peer_consumption=500)
        v=self.prepare(m)
        self.assertEqual(v['nuclear_fuel_selling_selected_TAG'],2)
        self.assertEqual(v['temp_nuclear_fuel_ammount'],-12000)
        self.assertEqual(v['temp_nuclear_fuel_price'],.5)
        self.assertGreaterEqual(m.entities['AAA'].variables['var_reactor_material_stockpile']+v['temp_nuclear_fuel_ammount'],26000)
        self.assertEqual(m.entities['BBB'].variables['var_reactor_material_stockpile']-v['temp_nuclear_fuel_ammount'],13000)
        s=self.actual_send(m)
        self.assertEqual(s['events'][0]['id'],'energy.10')

    def test_sale_requires_surplus_output_stock_and_buyer_below_4_weeks(self):
        cases=({'stock':26000},{'production':1000},{'peer_stock':2000},
               {'peer_consumption':0,'peer_stock':0})
        for settings in cases:
            with self.subTest(settings=settings):
                base=dict(stock=50000,production=2000,peer_stock=1000,peer_consumption=500)
                base.update(settings);m=self.fixture(**base)
                self.assertEqual(self.prepare(m).get('nuclear_fuel_selling_selected_TAG',0),0)
        m=self.fixture(stock=50000,production=2000,peer_stock=1000,peer_consumption=500)
        m.entities['BBB'].native['building_level@nuclear_reactor']=0
        self.assertEqual(self.prepare(m).get('nuclear_fuel_selling_selected_TAG',0),0)

    def test_human_or_busy_sender_is_inert_and_nested_candidates_do_not_replace_parent_temps(self):
        for busy in ('human',fuel.P+'reserved','currently_considering_an_offer'):
            m=self.fixture();a=m.entities['AAA']
            if busy=='human':a.ai=False
            else:a.flags.add(busy)
            before=copy.deepcopy(a.variables)
            self.assertEqual(self.prepare(m),before)
        for selling in (False,True):
            m=(self.fixture(stock=50000,production=2000,peer_stock=1000,peer_consumption=500)
               if selling else self.fixture())
            m.entities['AAA'].variables['eon_fuel_ai_buy_quantity']=999999
            m.entities['BBB'].variables['eon_fuel_ai_buy_quantity']=9
            m.entities['CCC']=u.Entity('country',3,'CCC',ai=True,
                variables=dict(treasury=500,var_reactor_material_stockpile=1000 if selling else 2000000,
                               nuclear_fuel_consumption=4000 if selling else 17,nuclear_reactor_fuel_production=0))
            m.entities['CCC'].native['building_level@nuclear_reactor']=1
            v=self.prepare(m)
            self.assertEqual(v['nuclear_fuel_selling_selected_TAG'],2)
            self.assertEqual(v['temp_nuclear_fuel_ammount'],-12000 if selling else 25000)

    def test_send_revalidates_changed_peer_and_legacy_busy_flag_after_preparation(self):
        for change in ('nonexistent','war','embargo','reserved','legacy_busy'):
            with self.subTest(change=change):
                m=self.fixture();v=self.prepare(m)
                self.assertEqual(v['nuclear_fuel_selling_selected_TAG'],2)
                peer=m.entities['BBB']
                if change=='nonexistent':peer.exists=False
                elif change=='war':peer.wars.add('AAA');m.entities['AAA'].wars.add('BBB')
                elif change=='embargo':peer.embargoing.add('AAA')
                elif change=='reserved':peer.flags.add(fuel.P+'reserved')
                elif change=='legacy_busy':peer.flags.add('currently_considering_an_offer')
                s=self.actual_send(m)
                self.assertFalse(s['events'])
                self.assertNotIn(fuel.P+'outgoing',s['countries'][1]['flags'])

    def test_busy_candidate_is_skipped_for_both_buy_and_sale_with_optional_free_alternative(self):
        for selling in (False,True):
            for alternative in (False,True):
                with self.subTest(selling=selling,alternative=alternative):
                    m=(self.fixture(stock=50000,production=2000,peer_stock=1000,peer_consumption=500)
                       if selling else self.fixture())
                    peer=m.entities['BBB']
                    peer.flags.add('currently_considering_an_offer')
                    if alternative:
                        free=copy.deepcopy(peer)
                        free.ident=3;free.tag='CCC'
                        free.flags.remove('currently_considering_an_offer')
                        m.entities['CCC']=free
                    v=self.prepare(m)
                    self.assertEqual(v.get('nuclear_fuel_selling_selected_TAG',0),3 if alternative else 0)
                    if alternative:
                        self.assertEqual(v['temp_nuclear_fuel_ammount'],-12000 if selling else 25000)

    def test_actual_source_mutations_break_buffer_peer_and_quantity_invariants(self):
        raw=(ROOT/REL).read_text(encoding='utf-8-sig')
        cases=(
            ('26week_target',raw.replace('eon_fuel_ai_buffer = 26','eon_fuel_ai_buffer = 2',1),
             {},lambda v:self.assertEqual(v['temp_nuclear_fuel_ammount'],25000)),
            ('4week_threshold',raw.replace('eon_fuel_ai_low_buffer = 4','eon_fuel_ai_low_buffer = 6',1),
             {'stock':4000},lambda v:self.assertEqual(v.get('nuclear_fuel_selling_selected_TAG',0),0)),
            ('10week_supplier_keep',raw.replace('eon_fuel_ai_keep = 10','eon_fuel_ai_keep = 0',1),
             {'peer_stock':34999},lambda v:self.assertEqual(v.get('nuclear_fuel_selling_selected_TAG',0),0)),
            ('chosen_buyer_lot_cap',raw.replace('clamp_temp_variable = { var = eon_fuel_ai_sell_quantity min = 0 max = eon_fuel_ai_buyer_need }','',1),
             {'stock':50000,'production':2000,'peer_stock':1000,'peer_consumption':500},
             lambda v:self.assertEqual(v['temp_nuclear_fuel_ammount'],-12000)),
        )
        for name,changed,settings,assertion in cases:
            with self.subTest(mutant=name):
                self.assertNotEqual(changed,raw,'A mutant must change actual production AST')
                m=self.fixture(raw=changed,**settings);v=self.prepare(m)
                with self.assertRaises(AssertionError):assertion(v)


if __name__=='__main__':unittest.main()
