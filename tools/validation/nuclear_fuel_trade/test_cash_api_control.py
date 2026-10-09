"""Execute the source-bound ordinary cash guard with independent recipient cases."""
import copy
import re
import unittest
import model as b
from build_native_probe import cash_api_overlay, validate_cash_api_overlay, same_ast, NS


def walk(nodes):
    for key,op,value in nodes:
        yield key,op,value
        if isinstance(value,list):yield from walk(value)


class CashApiControl(unittest.TestCase):
    def original(self,m):
        return m.ast((b.ROOT/'common/scripted_effects/00_budget_effects.txt').read_text(encoding='utf-8-sig'))

    def test_actual_cash_api_guard_targets_this_and_keeps_other_helpers_exact(self):
        m=b.executor();original=self.original(m);played,control=cash_api_overlay(original)
        validate_cash_api_overlay(played,control)
        actual_original=m.one(original,'modify_treasury_effect')
        self.assertEqual([key for key,op,value in actual_original],['custom_effect_tooltip','add_to_variable','clamp_variable'])
        self.assertTrue(same_ast([node for node in played if node[0]!='modify_treasury_effect'],[node for node in original if node[0]!='modify_treasury_effect']))
        oldresolve,oldexecute=m.resolve,m.execute
        def resolve(s,c,key):return {'USA':1,'HOL':2,'NEP':3}[key] if key in ('USA','HOL','NEP') else oldresolve(s,c,key)
        def execute(nodes,s,c):
            i=0
            while i<len(nodes):
                group=[nodes[i]];i+=1
                if group[0][0]=='if':
                    while i<len(nodes) and nodes[i][0] in ('else_if','else'):group.append(nodes[i]);i+=1
                if group[0][0]=='log':s.setdefault('logs',[]).append(group[0][2])
                else:oldexecute(group,s,c)
        m.resolve,m.execute=resolve,execute
        guarded=m.one(played,'modify_treasury_effect')
        for active in (False,True):
            for recipient in (1,2,3):
                for root in (1,3):
                    with self.subTest(active=active,recipient=recipient,root=root):
                        s=b.state(m);s['temp']={'treasury_change':-6.88242}
                        if active:s['global']['flags'].add(NS+'_active')
                        context=m.context(recipient,3);context['root']=root
                        m.execute(guarded,s,context)
                        blocked=active and recipient in (1,2)
                        self.assertEqual(s['countries'][recipient]['vars']['treasury'],500 if blocked else 500-6.88242)
                        self.assertEqual(len(s.get('logs',[])),1 if blocked else 0)
                        self.assertTrue(all(s['countries'][other]['vars']['treasury']==500 for other in (1,2,3) if other!=recipient))

    def test_guard_binding_rejects_extra_code_broadened_scope_and_nonfixture_damage(self):
        m=b.executor();played,control=cash_api_overlay(self.original(m))
        mutants=[]
        modified=copy.deepcopy(played);m.one(modified,'modify_treasury_effect')[1][2].append(['set_variable','=',[['treasury','=','500']]])
        mutants.append((modified,control))
        modified=copy.deepcopy(played);m.one(m.one(m.one(modified,'modify_treasury_effect'),'if'),'limit').clear()
        mutants.append((modified,control))
        modified=copy.deepcopy(played);next(row for row in modified if row[0]!='modify_treasury_effect')[2].append(['add_to_variable','=',[['treasury','=','1']]])
        mutants.append((modified,control))
        changed=copy.deepcopy(control);changed['original_ast'].append(['always','=','yes']);mutants.append((played,changed))
        for changed,declaration in mutants:
            with self.assertRaises(AssertionError):validate_cash_api_overlay(changed,declaration)

    def test_all_eight_original_fuel_options_transitive_helpers_exclude_ordinary_cash_api(self):
        m=b.executor();catalog={}
        for folder in ('common/scripted_effects','common/scripted_triggers'):
            for path in (b.ROOT/folder).glob('*.txt'):
                raw=path.read_text(encoding='utf-8-sig')
                if not re.search(r'^[A-Za-z_][A-Za-z_0-9]*\s*=\s*\{',raw,re.M):continue
                for key,op,value in m.ast(raw):
                    if isinstance(value,list):catalog.setdefault(key,[]).append(value)
        roots=[];names=[]
        for key,op,event in m.ast((b.ROOT/'events/00_Energy_events.txt').read_text(encoding='utf-8-sig')):
            if key!='country_event':continue
            if m.one(event,'id') not in ('energy.1','energy.2','energy.3','energy.10','energy.11','energy.12'):continue
            for key,op,value in event:
                if key=='option':names.append(m.one(value,'name'));roots.extend(value)
        self.assertEqual(len(names),8)
        queue={key for key,op,value in walk(roots) if key in catalog};seen=set()
        while queue:
            name=queue.pop()
            if name in seen:continue
            seen.add(name)
            for body in catalog[name]:queue.update(key for key,op,value in walk(body) if key in catalog and key not in seen)
        self.assertIn('eon_nuclear_fuel_trade_accept',seen)
        self.assertNotIn('modify_treasury_effect',seen)

    def test_blocked_cash_reader_rejects_wrong_recipient_mutation_and_nonfinite_logs(self):
        from analyze_native_probe import read_blocked_cash_records
        good='[12:00:00][2000.01.02.20]: EON_PRIVATE_FUEL_CASH BLOCKED api=modify_treasury_effect ROOT=NEP THIS=HOL FROM=USA cash=499.99975 change=-6.88242'
        errors=[]
        require=lambda ok,message:errors.append(message) if not ok else None
        rows=read_blocked_cash_records(good,require)
        self.assertFalse(errors);self.assertEqual(rows[0]['recipient_this'],'HOL')
        self.assertEqual(rows[0]['change'],'-6.88242')
        absent=read_blocked_cash_records(good.replace('FROM=USA','FROM='),require)
        self.assertFalse(errors);self.assertEqual(absent[0]['from'],'','Ordinary un-targeted decision may have no FROM country')
        for mutant in (good.replace('THIS=HOL','THIS=NEP'),good.replace('change=-6.88242','change=NaN'),
                       good.replace('cash=499.99975','cash=Infinity'),good.replace('api=modify_treasury_effect','api=other'),
                       good+' change=-2',good.replace('FROM=USA ','')):
            errors=[];read_blocked_cash_records(mutant,lambda ok,message:errors.append(message) if not ok else None)
            self.assertTrue(errors,'Corrupted diagnostic cash logs must not silently pass')


if __name__=='__main__':unittest.main()
