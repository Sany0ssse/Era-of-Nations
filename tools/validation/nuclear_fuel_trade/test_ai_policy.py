"""Execute production energy.10 AI policy and native option-weight AST.

Opinions/factions/native export-array membership are declared scenario inputs.
The price, lot and reserve rules are read from the actual event, never copied.
"""
import unittest
import model as b


class BuyerPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m=b.executor()
        nodes=cls.m.ast((b.ROOT/'events/00_Energy_events.txt').read_text(encoding='utf-8-sig'))
        found=[value for key,op,value in nodes if key=='country_event' and cls.m.one(value,'id')=='energy.10']
        assert len(found)==1
        cls.event=found[0];cls.immediate=cls.m.one(cls.event,'immediate')
        base=cls.m.trigger
        def trigger(nodes,state,context):
            index=0
            while index<len(nodes):
                group=[nodes[index]];index+=1
                if group[0][0]=='if':
                    while index<len(nodes) and nodes[index][0] in ('else_if','else'):
                        group.append(nodes[index]);index+=1
                key,op,value=group[0]
                owner=state['countries'][context['scope']]
                if key=='original_tag':
                    if owner.get('original_tag')!=value:return False
                elif key=='is_in_faction_with':
                    peer=cls.m.resolve(state,context,value)
                    if not owner.get('faction') or owner['faction']!=state['countries'][peer].get('faction'):return False
                elif key=='has_opinion':
                    target=cls.m.resolve(state,context,cls.m.one(value,'target'))
                    terms=[node for node in value if node[0]=='value'];assert len(terms)==1
                    if not cls.m.compare(owner.get('opinions',{}).get(target,0),terms[0][1],float(terms[0][2])):return False
                elif key=='is_in_array' and len(value)==1:
                    array,operator,operand=value[0]
                    scope,name=cls.m.target(state,context,array)
                    data=state['global'] if scope=='global' else state['countries'][scope]
                    if cls.m.value(state,context,operand) not in data['arrays'].get(name,[]):return False
                elif not base(group,state,context):return False
            return True
        cls.m.trigger=trigger

    def scenario(self,quantity,stock=1000,consumption=1000,price=.5):
        m=self.m;s=b.state(m,fuel=20000000)
        for actor,tag in ((1,'USA'),(2,'HOL'),(3,'NEP')):
            s['countries'][actor].update(original_tag=tag,faction='fixture-allies',opinions={1:250,2:250,3:250})
        s['countries'][2]['vars'].update(var_reactor_material_stockpile=stock,nuclear_fuel_consumption=consumption)
        b.send(m,s,-quantity,price)
        self.assertIn(b.P+'incoming',s['countries'][2]['flags'],'Scenario must be an executable, affordable original offer')
        context=m.context(2,1)
        m.execute(self.immediate,s,context)
        return s,context

    def weight(self,option_name,s,c):
        option=[v for k,o,v in self.event if k=='option' and self.m.one(v,'name')==option_name]
        self.assertEqual(len(option),1)
        option=option[0];triggers=[v for k,o,v in option if k=='trigger']
        if triggers and not self.m.trigger(triggers[0],s,c):return 0
        chance=self.m.one(option,'ai_chance');weight=float(self.m.one(chance,'base'))
        for key,op,value in chance:
            if key!='modifier':continue
            conditions=[node for node in value if node[0] not in ('factor','add')]
            if self.m.trigger(conditions,s,c):
                factor=[v for k,o,v in value if k=='factor']
                if factor:weight*=float(factor[0])
                add=[v for k,o,v in value if k=='add']
                if add:weight+=float(add[0])
        return weight

    def test_large_expensive_unwanted_lot_cannot_buy_friendly_ally_acceptance(self):
        s,c=self.scenario(1000000,stock=100000,price=10)
        self.assertEqual(s['temp']['ammount_adjuster'],0)
        self.assertLessEqual(s['countries'][2]['vars']['ai_accept_chance'],0)
        self.assertEqual(self.weight('energy.10.a',s,c),0)
        self.assertGreater(self.weight('energy.10.b',s,c),0)

    def test_shortage_benefit_is_bounded_and_does_not_grow_past_reserve_gap(self):
        values=[]
        for quantity in (100,500,25000,25500,1000000):
            s,c=self.scenario(quantity)
            benefit=s['temp']['ammount_adjuster'];values.append(benefit)
            self.assertGreaterEqual(benefit,0);self.assertLessEqual(benefit,50)
        self.assertGreater(values[1],values[0])
        self.assertEqual(values[2:], [50,50,50])

    def test_useful_affordable_lot_has_real_accept_option_but_excess_lot_refuses(self):
        s,c=self.scenario(500)
        self.assertGreater(self.weight('energy.10.a',s,c),0)
        self.assertEqual(self.weight('energy.10.b',s,c),0)
        s,c=self.scenario(1000000)
        self.assertEqual(self.weight('energy.10.a',s,c),0)
        self.assertGreater(self.weight('energy.10.b',s,c),0)

    def test_no_consumption_or_full_reserve_has_no_procurement_demand(self):
        for stock,consumption in ((1000,0),(26000,1000),(100000,1000)):
            s,c=self.scenario(500,stock=stock,consumption=consumption)
            self.assertEqual(s['temp']['ammount_adjuster'],0)
            self.assertEqual(self.weight('energy.10.a',s,c),0)
            self.assertGreater(self.weight('energy.10.b',s,c),0)

    def test_expensive_useful_offer_does_not_accept_through_maximum_bonus(self):
        s,c=self.scenario(25000,price=10)
        self.assertEqual(s['temp']['ammount_adjuster'],50)
        self.assertEqual(self.weight('energy.10.a',s,c),0)
        self.assertGreater(self.weight('energy.10.b',s,c),0)

    def test_native_purchase_refusal_fixture_has_executable_quote_and_real_seller_refusal(self):
        m=self.m;s=b.state(m)
        for actor,tag,stock in ((1,'USA',1000),(2,'HOL',5000),(3,'NEP',0)):
            s['countries'][actor].update(original_tag=tag,faction='fixture-allies',opinions={1:-250,2:0,3:0})
            s['countries'][actor]['vars'].update(var_reactor_material_stockpile=stock,
                nuclear_reactor_fuel_production=0,nuclear_fuel_consumption=1000,
                display_income=0,display_expense=0)
        b.send(m,s,500,.1)
        self.assertEqual(s['countries'][1]['vars'][b.P+'phase'],1)
        self.assertGreater(s['countries'][1]['vars'][b.P+'total'],0)
        self.assertAlmostEqual(s['countries'][1]['vars'][b.P+'quoted_total'],.00005)
        nodes=m.ast((b.ROOT/'events/00_Energy_events.txt').read_text(encoding='utf-8-sig'))
        self.event=next(v for k,o,v in nodes if k=='country_event' and m.one(v,'id')=='energy.1')
        context=m.context(2,1)
        m.execute(m.one(self.event,'immediate'),s,context)
        self.assertLessEqual(s['countries'][2]['vars']['ai_accept_chance'],0)
        self.assertEqual(self.weight('energy.1.a',s,context),0)
        self.assertGreater(self.weight('energy.1.b',s,context),0)


if __name__=='__main__':unittest.main()
