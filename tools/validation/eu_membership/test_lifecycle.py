"""EU source contracts and bounded execution; not HOI4 campaign acceptance."""
from pathlib import Path
from dataclasses import dataclass, field
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/validation/diplomacy_package_02'))
from _treaty_support import ast, one, compare, Country


class SourceContracts(unittest.TestCase):
    def test_timed_membership_flags_set_value_one_explicitly(self):
        seen=[]
        def walk(nodes):
            for key,op,value in nodes:
                if key in ('set_country_flag','set_global_flag') and isinstance(value,list) and any(k=='days' for k,op,v in value):
                    seen.append(one(value,'flag'))
                    self.assertEqual(one(value,'value'),'1')
                if isinstance(value,list):walk(value)
        source=ast((ROOT/'common/scripted_effects/eon_eu_membership_effects.txt').read_text(encoding='utf-8-sig'))
        walk(source)
        self.assertGreater(len(seen),0)
    def test_symbolic_variable_comparisons_use_explicit_native_form(self):
        def walk(nodes):
            for key,op,value in nodes:
                self.assertNotIn(op,('>=','<='),'Native parser does not accept inclusive shorthand')
                if key=='check_variable' and len(value)==1:
                    rhs=value[0][2]
                    try:float(rhs)
                    except ValueError:self.fail(f'Symbolic comparison must be explicit: {value}')
                if isinstance(value,list):walk(value)
        files=list((ROOT/'common').glob('**/eon_eu_membership*.txt'))+[ROOT/'events/eon_eu_membership_events.txt']
        for path in files:walk(ast(path.read_text(encoding='utf-8-sig')))

    def test_population_loop_filter_is_an_if_not_an_effect_named_limit(self):
        source=one(ast((ROOT/'common/scripted_effects/00_eu_scripted_effects.txt').read_text()),'EU_update_vars')
        def walk(nodes):
            for key,op,value in nodes:
                if key=='for_each_scope_loop':self.assertNotIn('limit',[k for k,op,v in value])
                if isinstance(value,list):walk(value)
        walk(source)
    def test_new_membership_scripts_have_no_native_parser_bom(self):
        files=list((ROOT/'common').glob('**/eon_eu_membership*.txt'))+[ROOT/'events/eon_eu_membership_events.txt']
        for path in files:
            with self.subTest(path=str(path)):
                self.assertNotIn(b'\xef\xbb\xbf',path.read_bytes())
        for language in ('english','russian'):
            path=ROOT/f'localisation/{language}/eon_eu_membership_l_{language}.yml'
            self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))
    def test_member_is_live_and_sovereign(self):
        data = ast((ROOT / 'common/scripted_triggers/eon_eu_membership_triggers.txt').read_text(encoding='utf-8-sig'))
        member = one(data, 'eon_eu_is_active_member')
        self.assertEqual(one(member, 'eon_eu_is_live_legal_member'), 'yes')
        self.assertIn(('NOT', '=', [('has_global_flag', '=', 'eon_eu_dormant')]), member)

    def test_no_instant_legacy_accession(self):
        data = ast((ROOT / 'common/decisions/EU_voting_decisions.txt').read_text(encoding='utf-8-sig'))
        action = one(one(data, 'EU_apply_for_membership_category'), 'EU_apply_for_membership')
        self.assertEqual(one(one(action, 'complete_effect'), 'eon_eu_apply_for_membership_start'), 'yes')

    def test_post_exit_ideas_survive_departure_and_cancel_only_on_reentry(self):
        model=Model();nation=model.nations[3]
        ideas=one(one(ast((ROOT/'common/ideas/EU_ideas.txt').read_text(encoding='utf-8-sig')),'ideas'),'country')
        for ident in ('withdrawal_treaty','no_deal_exit'):
            idea=one(ideas,ident)
            self.assertTrue(model.trigger(one(idea,'allowed'),[nation]))
            self.assertFalse(model.trigger(one(idea,'cancel'),[nation]))
            nation.ideas.add('EU_member')
            self.assertTrue(model.trigger(one(idea,'cancel'),[nation]))
            nation.ideas.discard('EU_member')

    def test_one_member_exit_does_not_clear_all_union_law_receipts(self):
        source=ast((ROOT/'common/scripted_effects/00_eu_scripted_effects.txt').read_text())
        data=str(one(source,'leaving_EU'))
        self.assertNotIn("('EU_clear_voting', '=', 'yes')",data)
        self.assertIn("('eon_eu_recount_council_vote', '=', 'yes')",data)


@dataclass
class Nation(Country):
    ideas: set = field(default_factory=set)
    subjects: bool = False
    owned: int = 1
    elections: bool = True
    missions: set = field(default_factory=set)
    flag_days: dict = field(default_factory=dict)
    state_populations: list = field(default_factory=list)
    faction_template: str = ''
    ai: bool = False


class Model:
    """Execute actual membership AST. Explicit external boundaries are receipts,
    not simulations of the legacy budget, office appointment or mission engine."""
    BOUNDARIES = {'update_eu_dirty_variable', 'eu_screen_selection', 'EU_update_vars',
                  'eon_eu_close_council_vote', 'eon_eu_close_institutions', 'eon_eu_reset_institutional_laws'}

    def __init__(self):
        self.nations = {n: Nation(n, original_tag=tag, variables={'MEP_Total': seats, 'eon_eu_voting_population_k': pop}, state_populations=[pop])
                        for n,tag,seats,pop in [(1,'GER',100,80),(2,'FRA',80,60),(3,'UKR',50,40),(4.02446,'CZE',20,10)]}
        self.global_owner = Nation(0)
        self.sender = 1
        self.from_id = 3
        self.temp = {}
        self.receipts = []
        self.effects = {k:v for k,op,v in ast((ROOT/'common/scripted_effects/eon_eu_membership_effects.txt').read_text(encoding='utf-8-sig'))}
        self.triggers = {k:v for k,op,v in ast((ROOT/'common/scripted_triggers/eon_eu_membership_triggers.txt').read_text(encoding='utf-8-sig'))}
        self.effects.update({k:v for k,op,v in ast((ROOT/'common/scripted_effects/eon_eu_withdrawal_extension_effects.txt').read_text(encoding='utf-8-sig'))})
        self.triggers.update({k:v for k,op,v in ast((ROOT/'common/scripted_triggers/eon_eu_withdrawal_extension_triggers.txt').read_text(encoding='utf-8-sig'))})
        voting = ast((ROOT/'common/scripted_triggers/eon_eu_voting_triggers.txt').read_text(encoding='utf-8-sig'))
        self.triggers['eon_eu_can_vote'] = one(voting, 'eon_eu_can_vote')
        org = one(one(ast((ROOT/'common/ideas/AA_Organizations.txt').read_text()),'ideas'),'country')
        self.idea = one(org,'EU_member')

    def owner(self, token, stack):
        if token == 'global': return self.global_owner
        if token == 'ROOT': return self.nations[self.sender]
        if token == 'FROM': return self.nations[self.from_id]
        if token == 'THIS': return stack[-1]
        if token == 'PREV': return stack[-2]
        if token.startswith('var:'): return self.nations[self.value(token[4:],stack)]
        return self.nations[float(token)]

    def slot(self, name, stack):
        if '.' in name:
            prefix,name=name.split('.',1)
            return self.owner(prefix,stack),name
        return stack[-1],name

    def value(self, token, stack):
        try: return float(token)
        except ValueError: pass
        if token in ('ROOT','FROM','THIS','PREV'): return self.owner(token,stack).ident
        obj,name=self.slot(token,stack)
        if name=='id':return obj.ident
        if '^' in name:
            ary,ix=name.split('^',1)
            if ix=='num':return len(obj.arrays.get(ary,[]))
            ix=int(self.value(ix,stack))
            return obj.arrays.get(ary,[])[ix] if ix<len(obj.arrays.get(ary,[])) else 0
        return self.temp.get(token,obj.variables.get(name,0))

    def arr(self, nodes, stack):
        if any(k=='array' for k,op,v in nodes): return self.slot(one(nodes,'array'),stack),self.value(one(nodes,'value'),stack)
        assert len(nodes)==1,nodes
        key,op,val=nodes[0]
        return self.slot(key,stack),self.value(val,stack)

    def trigger(self, nodes, stack):
        for k,op,v in nodes:
            c=stack[-1]
            if k in self.triggers: ok=self.trigger(self.triggers[k],stack)==(v=='yes')
            elif k in ('ROOT','FROM','THIS','PREV') or k.startswith('var:'): ok=self.trigger(v,stack+[self.owner(k,stack)])
            elif k=='OR':ok=any(self.trigger([n],stack) for n in v)
            elif k in ('AND','hidden_trigger','custom_trigger_tooltip'):ok=self.trigger(v,stack)
            elif k=='NOT':ok=not self.trigger(v,stack)
            elif k in ('tooltip',):continue
            elif k=='always':ok=v=='yes'
            elif k=='has_idea':ok=v in c.ideas
            elif k=='has_active_mission':ok=v in c.missions  # Controlled presence, not mission-engine emulation.
            elif k=='is_ai':ok=c.ai==(v=='yes')
            elif k=='has_faction_template':ok=c.faction_template==v
            elif k=='any_allied_country':
                ok=any(self.trigger(v,stack+[ally]) for ally in self.nations.values()
                       if ally.ident!=c.ident and c.faction_template and ally.faction_template==c.faction_template)
            elif k=='exists':ok=c.exists==(v=='yes')
            elif k=='is_subject':ok=c.subjects==(v=='yes')
            elif k=='any_owned_state':
                assert v==[('always','=','yes')]
                ok=c.owned>0
            elif k=='is_EU_potential':ok=(c.original_tag in {'GER','FRA','UKR','CZE'})==(v=='yes')
            elif k=='has_elections':ok=c.elections==(v=='yes')
            elif k=='has_war':ok=bool(c.wars)==(v=='yes')
            elif k=='has_global_flag':ok=v in self.global_owner.flags
            elif k=='has_country_flag':ok=v in c.flags
            elif k=='tag':ok=c.ident==self.owner(v,stack).ident
            elif k=='check_variable':
                if any(name=='var' for name,op,value in v):
                    key=one(v,'var');val=one(v,'value')
                    operator={'equals':'=','not_equals':'!=','greater_than':'>','less_than':'<','greater_than_or_equals':'>=','less_than_or_equals':'<='}[one(v,'compare')]
                else:
                    assert len(v)==1,v
                    key,operator,val=v[0]
                ok=compare(self.value(key,stack),operator,self.value(val,stack))
            elif k=='is_in_array':
                (obj,name),member=self.arr(v,stack)
                ok=member in obj.arrays.get(name,[])
            elif k in ('all_of_scopes','any_of_scopes'):
                obj,name=self.slot(one(v,'array'),stack)
                body=[n for n in v if n[0]!='array']
                vals=[self.trigger(body,stack+[self.nations[n]]) for n in list(obj.arrays.get(name,[]))]
                ok=(all(vals) if k=='all_of_scopes' else any(vals))
            else:raise ValueError('Unmodelled trigger '+k)
            if not ok:return False
        return True

    def effect(self, nodes, stack):
        i=0
        while i<len(nodes):
            k,op,v=nodes[i];i+=1;c=stack[-1]
            if k in self.effects:self.effect(self.effects[k],stack)
            elif k in self.BOUNDARIES:
                self.receipts.append((k,c.ident))
                if k=='eu_screen_selection':c.flags.difference_update({'show_offices_screen','show_eu_parliament','show_eu_fiscal','show_euro_info','show_euro_voting'})
            elif k=='leaving_EU':
                # Executed in native probes. Bounded tests only bind its membership cleanup boundary.
                self.receipts.append((k,c.ident))
                if 'EUU_do_not_remove_eu_idea' not in c.flags:self.idea_remove(c,stack)
                self.effect(self.effects['eon_eu_clear_country_access'],stack)
                self.effect(self.effects['eon_eu_refresh_membership'],stack)
            elif k=='if':
                branches=[('if',v)]
                while i<len(nodes) and nodes[i][0] in ('else','else_if'):
                    branches.append((nodes[i][0],nodes[i][2]));i+=1
                for typ,body in branches:
                    if typ=='else' or self.trigger(one(body,'limit'),stack):
                        self.effect([n for n in body if n[0]!='limit'],stack);break
            elif k in ('ROOT','FROM','THIS','PREV') or k.startswith('var:'):self.effect(v,stack+[self.owner(k,stack)])
            elif k=='every_country':
                limit=next((q for n,op,q in v if n=='limit'),[])
                for obj in list(self.nations.values()):
                    if obj.exists and self.trigger(limit,stack+[obj]):self.effect([n for n in v if n[0]!='limit'],stack+[obj])
            elif k=='every_owned_state':
                for pop in c.state_populations:
                    state=Nation(-c.ident,variables={'state_population_k':pop})
                    self.effect(v,stack+[state])
            elif k=='for_each_scope_loop':
                obj,name=self.slot(one(v,'array'),stack)
                assert not any(n=='limit' for n,op,q in v),'Scope loops require an if effect, not direct limit'
                body=[n for n in v if n[0]!='array']
                for ident in list(obj.arrays.get(name,[])):
                    target=self.nations[ident]
                    self.effect(body,stack+[target])
            elif k=='while_loop_effect':
                counter=0
                while self.trigger(one(v,'limit'),stack):
                    self.effect([n for n in v if n[0]!='limit'],stack);counter+=1
                    assert counter<1000
            elif k in ('set_variable','add_to_variable'):
                assert len(v)==1,v
                name,op,val=v[0];obj,key=self.slot(name,stack);number=self.value(val,stack)
                obj.variables[key]=number if k=='set_variable' else obj.variables.get(key,0)+number
            elif k in ('set_temp_variable','add_to_temp_variable','multiply_temp_variable','divide_temp_variable'):
                name,op,val=v[0];number=self.value(val,stack)
                if k=='set_temp_variable':self.temp[name]=number
                elif k=='add_to_temp_variable':self.temp[name]=self.temp.get(name,0)+number
                elif k=='multiply_temp_variable':self.temp[name]=self.temp.get(name,0)*number
                else:
                    assert number!=0, 'Division by zero'
                    self.temp[name]=self.temp.get(name,0)/number
            elif k=='clear_variable':
                obj,name=self.slot(v,stack);obj.variables.pop(name,None)
            elif k=='clear_array':
                obj,name=self.slot(v,stack);obj.arrays[name]=[]
            elif k in ('add_to_array','remove_from_array'):
                (obj,name),member=self.arr(v,stack);array=obj.arrays.setdefault(name,[])
                if k=='add_to_array':array.append(member)
                elif member in array:array.remove(member)
            elif k in ('set_country_flag','clr_country_flag'):
                flag=one(v,'flag') if isinstance(v,list) else v
                if k=='set_country_flag':
                    c.flags.add(flag)
                    if isinstance(v,list):
                        assert one(v,'value')=='1','Timed flags require explicit native value=1'
                        c.flag_days[flag]=float(one(v,'days'))
                else:c.flags.discard(flag);c.flag_days.pop(flag,None)
            elif k in ('set_global_flag','clr_global_flag'):
                if k=='set_global_flag':self.global_owner.flags.add(v)
                else:self.global_owner.flags.discard(v)
            elif k=='add_ideas':
                if v=='EU_member' and v not in c.ideas:
                    c.ideas.add(v);self.effect(one(self.idea,'on_add'),stack)
                else:c.ideas.add(v)
            elif k=='remove_ideas':
                if v=='EU_member':self.idea_remove(c,stack)
                else:c.ideas.discard(v)
            elif k=='add_timed_idea':c.ideas.add(one(v,'idea'))
            elif k=='activate_mission':c.missions.add(v)
            elif k=='remove_mission':c.missions.discard(v)
            elif k in ('country_event','news_event'):
                ident=one(v,'id') if isinstance(v,list) else v
                self.receipts.append(('event' if k=='country_event' else 'news',c.ident,ident,stack[-2].ident if len(stack)>1 else self.sender))
            elif k=='leave_faction':
                assert v=='yes'
                c.faction_template=''
            elif k in ('log','custom_effect_tooltip'):pass
            else:raise ValueError('Unmodelled effect '+k)

    def idea_remove(self,c,stack):
        if 'EU_member' in c.ideas:
            c.ideas.remove('EU_member');self.effect(one(self.idea,'on_remove'),stack)

    def call(self,name,who=3,from_id=None):
        self.sender=who
        if from_id is not None:self.from_id=from_id
        self.temp={}
        self.effect(self.effects[name],[self.nations[who]])

    def test(self,name,who=3,from_id=None):
        self.sender=who
        if from_id is not None:self.from_id=from_id
        return self.trigger(self.triggers[name],[self.nations[who]])

    def members(self,ids=(1,2)):
        # Explicit legal fixture input: initial loaded history passes the actual
        # closing boundary; later added fixture members use a one-use consent
        # receipt. This is not a proof of native ratification or engine startup.
        if 'eon_eu_admission_guard_ready' not in self.global_owner.flags:
            for n in ids:self.nations[n].ideas.add('EU_member')
            self.call('eon_eu_close_historical_admission')
        else:
            for n in ids:
                if 'EU_member' not in self.nations[n].ideas:
                    self.sender=n
                    self.nations[n].flags.add('eon_eu_admission_commit')
                    self.effect([('add_ideas','=','EU_member')],[self.nations[n]])
        self.global_owner.arrays['EU_member']=list(ids)
        self.call('eon_eu_refresh_membership')


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.m=Model();self.m.members()

    def test_registry_deduplicates_and_filters_dead_subjects(self):
        self.m.members((1,2,3))  # Explicit already-admitted member fixture.
        self.m.global_owner.arrays['EU_member']=[1,1,2,3]
        self.m.nations[3].subjects=True
        self.m.call('eon_eu_refresh_membership')
        self.assertEqual(self.m.global_owner.arrays['EU_member'],[1,2])
        self.assertIn('EU_member',self.m.nations[3].ideas)

    def test_budget_draft_flags_and_missions_clear_scoped_and_idempotently(self):
        flags={'EU_budget_draft','EU_mff_draft','EU_budget_EP_block','EU_mff_EP_block'}
        missions={'EU_budget_draft_preparations','EU_mff_draft_preparations',
                  'EU_budget_draft_ongoing','EU_budget_draft_ongoing_president',
                  'EU_mff_draft_ongoing','EU_mff_draft_ongoing_president'}
        for ident in (1,2):
            nation=self.m.nations[ident]
            nation.flags.update(flags|{'unrelated_budget_notice'})
            nation.flag_days.update({flag:17 for flag in flags})
            nation.missions.update(missions|{'unrelated_mission'})
        self.m.call('eon_eu_clear_country_access',1)
        self.m.call('eon_eu_clear_country_access',1)
        former=self.m.nations[1];other=self.m.nations[2]
        self.assertFalse(former.flags.intersection(flags))
        self.assertFalse(set(former.flag_days).intersection(flags))
        self.assertFalse(former.missions.intersection(missions))
        self.assertIn('unrelated_budget_notice',former.flags)
        self.assertIn('unrelated_mission',former.missions)
        self.assertTrue(flags.issubset(other.flags))
        self.assertTrue(missions.issubset(other.missions))
        self.assertTrue(all(other.flag_days[flag]==17 for flag in flags))

    def test_formal_departure_then_readmission_cannot_restore_stale_budget_flags(self):
        flags={'EU_budget_draft','EU_mff_draft','EU_budget_EP_block','EU_mff_EP_block'}
        former=self.m.nations[1];current=self.m.nations[2]
        former.flags.update(flags);current.flags.update(flags)
        self.m.call('eon_eu_refresh_membership',1)
        self.assertTrue(flags.issubset(former.flags))
        self.assertTrue(flags.issubset(current.flags))
        self.m.sender=1
        self.m.idea_remove(former,[former])
        self.assertNotIn('EU_member',former.ideas)
        self.assertFalse(former.flags.intersection(flags))
        self.assertTrue(flags.issubset(current.flags))
        self.m.members((1,2))
        self.m.call('eon_eu_refresh_membership',1)
        self.m.call('eon_eu_refresh_membership',1)
        self.assertTrue(self.m.test('eon_eu_is_active_member',1))
        self.assertFalse(former.flags.intersection(flags))
        self.assertTrue(flags.issubset(current.flags))

    def test_exited_country_clears_access_and_money(self):
        c=self.m.nations[1];c.flags.update({'new_EU_open','show_euro_voting','EU_candidate','Article_50'})
        c.variables.update(EU_subsidies=7,EU_budget_contribution_weekly=2)
        self.m.call('eon_eu_clear_country_access',1)
        self.assertFalse(c.flags.intersection({'new_EU_open','show_euro_voting','EU_candidate','Article_50'}))
        self.assertEqual(c.variables['EU_subsidies'],0)
        self.assertEqual(c.variables['EU_budget_contribution_weekly'],0)

    def test_empty_union_dormant_not_resurrected_by_idea(self):
        self.m.nations[1].exists=False;self.m.nations[2].exists=False
        self.m.call('eon_eu_refresh_membership')
        self.assertIn('eon_eu_dormant',self.m.global_owner.flags)
        self.assertEqual(self.m.global_owner.arrays['EU_member'],[])
        self.m.nations[1].exists=True;self.m.nations[1].ideas.add('EU_member')
        self.m.call('eon_eu_refresh_membership')
        self.assertEqual(self.m.global_owner.arrays['EU_member'],[])
        self.assertNotIn('EU_member',self.m.nations[1].ideas)
        self.assertFalse(self.m.test('eon_eu_is_active_member',1))

    def test_application_needs_every_current_member(self):
        self.m.call('eon_eu_apply_for_membership_start')
        self.m.call('eon_eu_endorse_application',1,3)
        self.m.call('eon_eu_progress_accession')
        self.assertEqual(self.m.nations[3].variables['eon_eu_accession_phase'],1)
        self.m.call('eon_eu_endorse_application',2,3)
        self.m.call('eon_eu_progress_accession')
        self.assertEqual(self.m.nations[3].variables['eon_eu_accession_phase'],2)
        self.assertIn('EU_candidate',self.m.nations[3].flags)
        self.assertNotIn('EU_member',self.m.nations[3].ideas)
        self.assertEqual(self.m.nations[3].flag_days['eon_eu_negotiation_period'],180)

    def candidate(self):
        c=self.m.nations[3];c.flags.add('EU_candidate');c.variables['eon_eu_accession_phase']=2

    def treaty(self):
        self.candidate();self.m.call('eon_eu_submit_accession_treaty')
        self.m.call('eon_eu_ratify_member_accession',1,3);self.m.call('eon_eu_ratify_member_accession',2,3)

    def test_negotiation_period_blocks_early_treaty(self):
        self.candidate();self.m.nations[3].flags.add('eon_eu_negotiation_period')
        self.m.call('eon_eu_submit_accession_treaty')
        self.assertEqual(self.m.nations[3].variables['eon_eu_accession_phase'],2)

    def test_government_unanimity_without_ep_does_not_admit(self):
        self.treaty();self.m.call('eon_eu_progress_accession');self.m.call('eon_eu_ratify_accession_treaty')
        self.assertEqual(self.m.nations[3].variables['eon_eu_accession_phase'],3)
        self.assertNotIn('EU_member',self.m.nations[3].ideas)

    def test_ep_seats_and_final_ratification_are_separate(self):
        self.treaty();self.m.call('eon_eu_support_accession_ep',1,3);self.m.call('eon_eu_progress_accession')
        c=self.m.nations[3]
        self.assertEqual(c.variables['eon_eu_accession_phase'],4)
        self.assertNotIn('EU_member',c.ideas)
        self.m.call('eon_eu_ratify_accession_treaty')
        self.assertIn('EU_member',c.ideas)
        self.assertNotIn('EU_candidate',c.flags)
        self.assertEqual(self.m.global_owner.arrays['EU_member'].count(3),1)
        self.m.call('eon_eu_ratify_accession_treaty')
        self.assertEqual(self.m.global_owner.arrays['EU_member'].count(3),1)

    def test_withdrawn_ep_ballot_revalidated_before_entry(self):
        self.treaty();self.m.call('eon_eu_support_accession_ep',1,3);self.m.call('eon_eu_progress_accession')
        c=self.m.nations[3];c.arrays['eon_eu_accession_ep_approvals']=[]
        self.m.call('eon_eu_ratify_accession_treaty')
        self.assertNotIn('EU_member',c.ideas)
        self.assertNotIn('eon_eu_accession_ep_consent',c.flags)

    def test_rejection_clears_old_consents_preserves_candidate(self):
        self.treaty();self.m.call('eon_eu_reject_application',1,3)
        c=self.m.nations[3]
        self.assertIn('EU_candidate',c.flags)
        self.assertEqual(c.variables['eon_eu_accession_phase'],2)
        self.assertEqual(c.arrays['eon_eu_accession_approvals'],[])
        self.assertEqual(c.flag_days['eon_eu_application_cooldown'],90)

    def test_expired_application_cannot_reuse_late_response(self):
        self.m.call('eon_eu_apply_for_membership_start');c=self.m.nations[3]
        c.flags.discard('eon_eu_application_window')
        self.m.call('eon_eu_endorse_application',1,3)
        self.m.call('eon_eu_progress_accession')
        self.assertEqual(c.variables['eon_eu_accession_phase'],0)
        self.assertNotIn('EU_member',c.ideas)

    def test_nonmember_cannot_endorse_or_cast_ep(self):
        self.treaty();self.m.call('eon_eu_endorse_application',4.02446,3);self.m.call('eon_eu_support_accession_ep',4.02446,3)
        self.assertNotIn(4.02446,self.m.nations[3].arrays.get('eon_eu_accession_approvals',[]))
        self.assertNotIn(4.02446,self.m.nations[3].arrays.get('eon_eu_accession_ep_approvals',[]))

    def test_article50_preserves_membership_and_clock(self):
        self.m.call('eon_eu_notify_withdrawal',1)
        c=self.m.nations[1]
        self.assertIn('EU_member',c.ideas)
        self.assertEqual(c.flag_days['eon_eu_withdrawal_deadline'],730)
        self.assertTrue(self.m.test('eon_eu_is_active_member',1))
        self.m.call('eon_eu_notify_withdrawal',1)
        self.assertEqual(c.flag_days['eon_eu_withdrawal_deadline'],730)

    def test_unilateral_revocation_preserves_membership(self):
        self.m.call('eon_eu_notify_withdrawal',1);self.m.call('eon_eu_propose_withdrawal_treaty',1)
        self.m.call('eon_eu_revoke_withdrawal',1)
        c=self.m.nations[1]
        self.assertIn('EU_member',c.ideas);self.assertNotIn('Article_50',c.flags)
        self.assertNotIn('EU_exit',c.missions)
        self.assertEqual(c.flag_days['cant_invoke_article_50'],180)

    def test_withdrawal_own_council_vote_excluded(self):
        self.m.members((1,2,3));self.m.call('eon_eu_notify_withdrawal',1);self.m.call('eon_eu_propose_withdrawal_treaty',1)
        self.m.nations[1].arrays['eon_eu_withdrawal_approvals']=[1,2]
        self.m.call('eon_eu_recount_withdrawal',1)
        self.assertNotIn('eon_eu_withdrawal_council_consent',self.m.nations[1].flags)
        self.m.call('eon_eu_approve_withdrawal_treaty',3,1);self.m.call('eon_eu_recount_withdrawal',1)
        self.assertIn('eon_eu_withdrawal_council_consent',self.m.nations[1].flags)

    def test_early_exit_requires_ep_and_final_consent(self):
        self.m.members((1,2,3));self.m.call('eon_eu_notify_withdrawal',1);self.m.call('eon_eu_propose_withdrawal_treaty',1)
        self.m.call('eon_eu_approve_withdrawal_treaty',2,1);self.m.call('eon_eu_approve_withdrawal_treaty',3,1)
        self.m.call('eon_eu_finish_withdrawal',1)
        self.assertIn('EU_member',self.m.nations[1].ideas)
        self.m.call('eon_eu_support_withdrawal_ep',2,1);self.m.call('eon_eu_support_withdrawal_ep',3,1)
        self.assertIn('EU_member',self.m.nations[1].ideas)
        self.m.call('eon_eu_finish_withdrawal',1)
        self.assertNotIn('EU_member',self.m.nations[1].ideas)
        self.assertNotIn(1,self.m.global_owner.arrays['EU_member'])

    def test_deadline_exit_no_consent_required(self):
        self.m.call('eon_eu_notify_withdrawal',1);self.m.nations[1].flags.discard('eon_eu_withdrawal_deadline')
        self.m.call('eon_eu_force_deadline_withdrawal',1)
        self.assertNotIn('EU_member',self.m.nations[1].ideas)
        self.assertIn('no_deal_exit',self.m.nations[1].ideas)

    def test_refounding_exact_pair_and_full_country_token(self):
        self.m.nations[1].exists=False;self.m.nations[2].exists=False;self.m.call('eon_eu_refresh_membership')
        self.m.call('eon_eu_propose_refounding',3,4.02446)
        self.assertEqual(self.m.nations[3].variables['eon_eu_refound_target'],4.02446)
        self.m.call('eon_eu_accept_refounding',4.02446,3)
        self.assertEqual(self.m.global_owner.arrays['EU_member'],[3,4.02446])
        self.assertNotIn('eon_eu_dormant',self.m.global_owner.flags)
        self.m.call('eon_eu_accept_refounding',4.02446,3)
        self.assertEqual(self.m.global_owner.arrays['EU_member'],[3,4.02446])

    def test_expired_founder_offer_never_forms_union(self):
        self.m.nations[1].exists=False;self.m.nations[2].exists=False;self.m.call('eon_eu_refresh_membership')
        self.m.call('eon_eu_propose_refounding',3,4.02446)
        self.m.nations[3].flags.discard('eon_eu_refound_outgoing')
        self.m.call('eon_eu_accept_refounding',4.02446,3)
        self.assertIn('eon_eu_dormant',self.m.global_owner.flags)
        self.assertEqual(self.m.global_owner.arrays['EU_member'],[])

    def test_candidate_endorsement_cannot_ratify_treaty(self):
        self.candidate();self.m.call('eon_eu_submit_accession_treaty')
        self.m.call('eon_eu_endorse_application',1,3)
        self.assertEqual(self.m.nations[3].arrays['eon_eu_accession_approvals'],[])
        self.m.call('eon_eu_ratify_member_accession',1,3)
        self.assertEqual(self.m.nations[3].arrays['eon_eu_accession_approvals'],[1])

    def test_exact_half_ep_is_not_majority(self):
        self.m.nations[1].variables['MEP_Total']=90
        self.m.nations[2].variables['MEP_Total']=90
        self.treaty();self.m.call('eon_eu_support_accession_ep',1,3)
        self.assertNotIn('eon_eu_accession_ep_consent',self.m.nations[3].flags)

    def test_new_member_requires_new_consent_before_admission(self):
        self.treaty();self.m.call('eon_eu_support_accession_ep',1,3);self.m.call('eon_eu_progress_accession')
        self.m.members((1,2,4.02446))  # A real additional legal-member fixture, not a stray idea.
        self.m.call('eon_eu_ratify_accession_treaty')
        self.assertNotIn('EU_member',self.m.nations[3].ideas)

    def test_wrong_sender_cannot_consume_founder_offer(self):
        self.m.nations[1].ideas.clear();self.m.nations[2].ideas.clear();self.m.call('eon_eu_refresh_membership')
        self.m.call('eon_eu_propose_refounding',3,4.02446)
        self.m.call('eon_eu_accept_refounding',4.02446,1)
        self.assertIn('eon_eu_dormant',self.m.global_owner.flags)
        self.assertEqual(self.m.global_owner.arrays['EU_member'],[])

    def test_subordinated_legal_member_can_recover_while_union_operates(self):
        self.m.nations[2].subjects=True;self.m.call('eon_eu_refresh_membership')
        self.assertIn('EU_member',self.m.nations[2].ideas)
        self.assertFalse(self.m.test('eon_eu_is_active_member',2))
        self.m.nations[2].subjects=False;self.m.call('eon_eu_refresh_membership')
        self.assertTrue(self.m.test('eon_eu_is_active_member',2))

    def test_suspended_council_member_still_ratifies_accession_nationally(self):
        self.m.nations[2].ideas.add('EUU_voting_rights_suspended')
        self.m.call('eon_eu_refresh_membership')
        self.assertEqual(self.m.global_owner.arrays['EU_member'],[1,2])
        self.assertFalse(self.m.test('eon_eu_can_vote',2))
        self.candidate();self.m.call('eon_eu_submit_accession_treaty')
        self.m.call('eon_eu_ratify_member_accession',1,3)
        self.m.call('eon_eu_support_accession_ep',1,3)
        self.assertEqual(self.m.nations[3].variables['eon_eu_treaty_ep_total_display'],180)
        self.assertFalse(self.m.test('eon_eu_all_members_approved',3))
        self.m.call('eon_eu_progress_accession')
        self.m.call('eon_eu_ratify_accession_treaty')
        self.assertEqual(self.m.nations[3].variables['eon_eu_accession_phase'],3)
        self.assertNotIn('EU_member',self.m.nations[3].ideas)
        decisions=one(ast((ROOT/'common/decisions/eon_eu_membership_decisions.txt').read_text()),'eon_eu_membership_category')
        action=one(decisions,'eon_eu_member_ratify_accession')
        self.m.sender=2;self.m.from_id=3;self.m.temp={}
        for section in ('allowed','target_root_trigger','target_trigger','visible','available'):
            self.assertTrue(self.m.trigger(one(action,section),[self.m.nations[2]]),section)
        self.m.temp={}
        self.m.effect(one(action,'complete_effect'),[self.m.nations[2]])
        self.assertEqual(self.m.nations[3].arrays['eon_eu_accession_approvals'],[1,2])
        self.m.effect(one(action,'complete_effect'),[self.m.nations[2]])
        self.assertEqual(self.m.nations[3].arrays['eon_eu_accession_approvals'],[1,2])
        self.assertTrue(self.m.test('eon_eu_all_members_approved',3))
        self.m.call('eon_eu_progress_accession')
        self.assertEqual(self.m.nations[3].variables['eon_eu_accession_phase'],4)
        self.m.call('eon_eu_ratify_accession_treaty')
        self.assertIn('EU_member',self.m.nations[3].ideas)
        self.assertFalse(self.m.test('eon_eu_can_vote',2))

    def test_suspended_government_is_not_in_withdrawal_council_denominator(self):
        self.m.members((1,2,3,4.02446));self.m.nations[2].ideas.add('EUU_voting_rights_suspended')
        self.m.call('eon_eu_notify_withdrawal',1);self.m.call('eon_eu_propose_withdrawal_treaty',1)
        self.m.call('eon_eu_approve_withdrawal_treaty',3,1);self.m.call('eon_eu_approve_withdrawal_treaty',4.02446,1)
        self.m.call('eon_eu_recount_withdrawal',1)
        self.assertIn('eon_eu_withdrawal_council_consent',self.m.nations[1].flags)

    def test_legacy_population_cache_does_not_use_recruitable_manpower(self):
        source=ast((ROOT/'common/scripted_effects/00_eu_scripted_effects.txt').read_text())
        data=str(one(source,'EU_update_vars'))
        self.assertNotIn('max_manpower_k',data)
        self.assertIn('state_population_k',data)

    def test_withdrawal_recounts_residents_before_using_population_threshold(self):
        self.m.nations[5]=Nation(5,original_tag='POL',variables={'MEP_Total':25,'eon_eu_voting_population_k':500},state_populations=[1])
        self.m.members((1,2,3,4.02446,5))
        self.m.call('eon_eu_notify_withdrawal',1);self.m.call('eon_eu_propose_withdrawal_treaty',1)
        for country in (2,3,4.02446):self.m.call('eon_eu_approve_withdrawal_treaty',country,1)
        self.m.call('eon_eu_recount_withdrawal',1)
        self.assertIn('eon_eu_withdrawal_council_consent',self.m.nations[1].flags)
        self.assertEqual(self.m.nations[5].variables['eon_eu_voting_population_k'],1)

    def test_legacy_monitor_cannot_clear_or_rearm_votes(self):
        decisions=one(ast((ROOT/'common/decisions/EU_voting_decisions.txt').read_text()),'EU_voting_category')
        for ident in ('EU_update_vars_mission','EU_clear_voting_mission'):
            self.assertEqual(one(one(decisions,ident),'timeout_effect'),[])
        events=ast((ROOT/'events/EU_events.txt').read_text())
        monitor=[v for k,op,v in events if k=='country_event' and one(v,'id') in ('EUupdate.1','EUupdate.2')]
        self.assertNotIn("('EU_clear_voting', '=', 'yes')",str(monitor))
        self.assertNotIn("('activate_mission', '=', 'EU_update_vars_mission')",str(monitor))
        self.assertNotIn("('activate_mission', '=', 'EU_clear_voting_mission')",str(monitor))

    def test_treaty_parliament_rejects_stale_inactive_delegation_seats(self):
        self.m.call('eon_eu_apply_for_membership_start',3)
        self.m.nations[3].variables['eon_eu_accession_phase']=3
        self.m.nations[4.02446].ideas.add('EU_member')
        self.m.nations[4.02446].subjects=True
        self.m.nations[4.02446].variables['MEP_Total']=1000
        self.m.global_owner.arrays['EU_member'].append(4.02446)
        self.m.nations[3].arrays['eon_eu_accession_ep_approvals']=[2,4.02446]
        self.m.call('eon_eu_recount_treaty_parliament',3)
        self.assertNotIn('eon_eu_accession_ep_consent',self.m.nations[3].flags)
        self.assertEqual(self.m.nations[3].variables['eon_eu_treaty_ep_total_display'],180)

    def faction_exit_node(self):
        # Execute the actual leaving_EU delegation with the dedicated production
        # EDU interpreter; faction mutations/hooks remain declared model boundaries.
        import importlib.util
        path=ROOT/'tools/validation/edu_protocol/_protocol_model.py'
        spec=importlib.util.spec_from_file_location('eon_membership_edu_model',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        source=ast((ROOT/'common/scripted_effects/00_eu_scripted_effects.txt').read_text())
        def walk(nodes):
            for k,op,v in nodes:
                yield k,op,v
                if isinstance(v,list):yield from walk(v)
        leaving=list(walk(one(source,'leaving_EU')))
        matches=[n for n in leaving if n[0]=='eon_edu_depart_eu']
        self.assertEqual(matches,[('eon_edu_depart_eu','=','yes')])
        names=[k for k,op,v in leaving]
        self.assertLess(names.index('eon_edu_depart_eu'),names.index('eon_eu_clear_country_access'))
        return module.Model(),module.context,matches

    def test_eu_withdrawal_preserves_nato_even_when_edu_exists(self):
        from copy import deepcopy
        model,context,exit_node=self.faction_exit_node()
        model.decision('EU_create_EDU',1)
        nato=model.make_foreign_faction(3,[4])
        for actor in (3,4):model.c[actor]['ideas'].add('NATO_member')
        model.c[3]['ideas'].discard('EU_member');model.c[3]['active']=False
        snapshot=deepcopy((model.c[3],model.c[4],model.factions[nato]))
        model.effect(exit_node,context(3,3,1))
        self.assertEqual((model.c[3],model.c[4],model.factions[nato]),snapshot)
        self.assertEqual(model.leader(3),3)
        self.assertIn('EDU',model.gf)
        self.assertEqual(model.c[1]['vars']['eon_edu_member_instance'],model.g['eon_edu_instance'])

    def test_eu_withdrawal_leaves_actual_edu_without_requiring_other_eu_ally(self):
        model,context,exit_node=self.faction_exit_node()
        model.decision('EU_create_EDU',1)
        nato=model.make_foreign_faction(3,[4])
        self.assertFalse(any(model.same(1,actor) for actor in model.c if actor!=1))
        model.c[1]['ideas'].discard('EU_member');model.c[1]['active']=False
        model.effect(exit_node,context(1,1,5))
        self.assertIsNone(model.c[1]['faction'])
        self.assertEqual(model.c[1]['vars']['eon_edu_departure_result'],1)
        self.assertNotIn('EDU',model.gf)
        self.assertEqual(model.c[3]['faction'],nato)
        self.assertEqual(model.c[4]['faction'],nato)
        self.assertEqual(model.g['eon_edu_generation_counter'],1)

    def test_withdrawal_ep_is_majority_of_votes_cast_with_real_no_and_abstention(self):
        self.m.members((1,2,3,4.02446))
        self.m.call('eon_eu_notify_withdrawal',1);self.m.call('eon_eu_propose_withdrawal_treaty',1)
        self.m.call('eon_eu_support_withdrawal_ep',3,1)
        self.m.call('eon_eu_reject_withdrawal_ep',4.02446,1)
        # 50 yes, 20 no, 180 abstain: less than half all seats, majority of votes cast.
        self.assertIn('eon_eu_withdrawal_ep_consent',self.m.nations[1].flags)
        self.assertEqual(self.m.nations[1].variables['eon_eu_treaty_withdrawal_ep_no_display'],20)
        self.m.call('eon_eu_reject_withdrawal_ep',2,1)
        self.assertNotIn('eon_eu_withdrawal_ep_consent',self.m.nations[1].flags)
        self.m.call('eon_eu_abstain_withdrawal_ep',2,1)
        self.assertIn('eon_eu_withdrawal_ep_consent',self.m.nations[1].flags)
        self.m.call('eon_eu_reject_withdrawal_ep',3,1)
        self.assertNotIn(3,self.m.nations[1].arrays['eon_eu_withdrawal_ep_approvals'])
        self.assertNotIn('eon_eu_withdrawal_ep_consent',self.m.nations[1].flags)

    def test_withdrawal_own_ep_can_vote_no_then_yes_then_abstain(self):
        self.m.call('eon_eu_notify_withdrawal',1);self.m.call('eon_eu_propose_withdrawal_treaty',1)
        self.m.call('eon_eu_reject_own_withdrawal_ep',1)
        self.assertEqual(self.m.nations[1].arrays['eon_eu_withdrawal_ep_rejections'],[1])
        self.m.call('eon_eu_support_own_withdrawal_ep',1)
        self.assertEqual(self.m.nations[1].arrays['eon_eu_withdrawal_ep_approvals'],[1])
        self.assertEqual(self.m.nations[1].arrays['eon_eu_withdrawal_ep_rejections'],[])
        self.m.call('eon_eu_abstain_own_withdrawal_ep',1)
        self.assertEqual(self.m.nations[1].arrays['eon_eu_withdrawal_ep_approvals'],[])
        self.assertNotIn('eon_eu_withdrawal_ep_consent',self.m.nations[1].flags)

    def test_actual_accession_marks_parliament_and_budget_dirty(self):
        self.treaty()
        for member in (1,2):
            self.m.call('eon_eu_ratify_member_accession',member,3)
            self.m.call('eon_eu_support_accession_ep',member,3)
        self.m.call('eon_eu_progress_accession',3)
        self.m.global_owner.flags.discard('eon_eu_membership_changed')
        self.m.call('eon_eu_ratify_accession_treaty',3)
        self.assertIn('EU_member',self.m.nations[3].ideas)
        self.assertIn('eon_eu_membership_changed',self.m.global_owner.flags)

    def test_actual_departure_marks_parliament_and_budget_dirty(self):
        self.m.global_owner.flags.discard('eon_eu_membership_changed')
        self.m.idea_remove(self.m.nations[1],[self.m.nations[1]])
        self.assertNotIn('EU_member',self.m.nations[1].ideas)
        self.assertIn('eon_eu_membership_changed',self.m.global_owner.flags)

    def test_replayed_callbacks_do_not_start_another_parliament_refresh(self):
        self.m.global_owner.flags.discard('eon_eu_membership_changed')
        self.m.effect(one(self.m.idea,'on_add'),[self.m.nations[1]])
        self.assertNotIn('eon_eu_membership_changed',self.m.global_owner.flags)
        self.m.idea_remove(self.m.nations[1],[self.m.nations[1]])
        self.m.global_owner.flags.discard('eon_eu_membership_changed')
        self.m.effect(one(self.m.idea,'on_remove'),[self.m.nations[1]])
        self.assertNotIn('eon_eu_membership_changed',self.m.global_owner.flags)

    def test_direct_exit_has_transition_guard_before_removing_idea(self):
        source=one(ast((ROOT/'common/scripted_effects/00_eu_scripted_effects.txt').read_text()),'leaving_EU')
        body=one(source,'if')
        self.assertLess(next(i for i,n in enumerate(body) if n[0]=='eon_eu_member_removed'),next(i for i,n in enumerate(body) if n[0]=='if'))

    def test_application_notifies_only_other_active_human_members_once(self):
        self.m.members((1,2,4.02446))
        self.m.nations[2].ai=True;self.m.nations[4.02446].subjects=True
        self.m.call('eon_eu_refresh_membership',3);self.m.receipts.clear()
        self.m.call('eon_eu_apply_for_membership_start',3)
        self.m.call('eon_eu_apply_for_membership_start',3)
        notices=[x for x in self.m.receipts if x[0]=='event' and x[2]=='eon_eu_membership.9']
        self.assertEqual(notices,[('event',1,'eon_eu_membership.9',3)])

    def test_accession_treaty_notifies_human_government_and_ep_once(self):
        self.candidate();self.m.nations[2].ai=True;self.m.receipts.clear()
        self.m.call('eon_eu_submit_accession_treaty',3)
        self.m.call('eon_eu_submit_accession_treaty',3)
        notices=[x for x in self.m.receipts if x[0]=='event' and x[2]=='eon_eu_membership.10']
        self.assertEqual(notices,[('event',1,'eon_eu_membership.10',3)])

    def test_withdrawal_proposal_notifies_other_human_members_once(self):
        self.m.members((1,2,3,4.02446));self.m.nations[2].ai=True
        self.m.nations[4.02446].subjects=True;self.m.call('eon_eu_refresh_membership',1)
        self.m.call('eon_eu_notify_withdrawal',1);self.m.receipts.clear()
        self.m.call('eon_eu_propose_withdrawal_treaty',1)
        self.m.call('eon_eu_propose_withdrawal_treaty',1)
        notices=[x for x in self.m.receipts if x[0]=='event' and x[2]=='eon_eu_membership.11']
        self.assertEqual(notices,[('event',3,'eon_eu_membership.11',1)])

    def test_incoming_popups_are_informational_and_cannot_cast_stale_votes(self):
        source=ast((ROOT/'events/eon_eu_membership_events.txt').read_text())
        for ident in ('eon_eu_membership.9','eon_eu_membership.10','eon_eu_membership.11'):
            event=next(v for k,op,v in source if k=='country_event' and one(v,'id')==ident)
            self.assertEqual(one(event,'option'),[('name','=','eon_eu_membership.ok')])
            self.assertNotIn('immediate',[k for k,op,v in event])


if __name__ == '__main__':
    unittest.main()
