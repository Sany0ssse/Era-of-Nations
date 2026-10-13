"""Source AST handoff regressions. Declared fixture clocks are not native time."""
from pathlib import Path
from copy import deepcopy
import hashlib,json,unittest
import test_voting as vote
import eon_eu_frontend_model as front
import test_parliament as ep

HERE=Path(__file__).resolve().parent
BASE=json.loads((HERE/'handoff-source-baseline.json').read_text(encoding='utf-8'))
ast,one=front.ast,front.one
EF='common/scripted_effects/eon_eu_handoff_effects.txt'
TR='common/scripted_triggers/eon_eu_handoff_triggers.txt'
VT='common/scripted_triggers/eon_eu_voting_triggers.txt'
VE='common/scripted_effects/eon_eu_voting_effects.txt'
LC='common/scripted_effects/eon_eu_lifecycle_effects.txt'
LAW='common/scripted_effects/99_EU_voting_scripted_effects.txt'
def normalized(value):return json.loads(json.dumps(value))
def digest(value):return hashlib.sha256(json.dumps(value,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def available():return front.source_path(EF,front.SOURCE).exists()
def record(model,law=101):
    prefix=f'eon_eu_handoff_{law}_'
    return {key:value for key,value in model.global_vars.items() if key.startswith(prefix)}
def bounded_state(model):
    # The handler may recount its census on a denied proposal. These protected
    # fields prove that denial cannot debit or claim, without pretending that
    # every diagnostic temporary/census field is immutable.
    return deepcopy(([(i,c.variables['political_power']) for i,c in model.countries.items()],
      model.global_vars.get('current_active_vote_disp',0),
      model.global_vars.get('eon_eu_council_vote_instance',0),
      {k:v for k,v in model.global_vars.items() if k.startswith('eon_eu_handoff_')},
      model.global_arrays.get('EU_council_votes',[]),model.global_arrays.get('EU_passed_votes',[])))
def delay(model):
    model.global_flags.add('delay_next_council_vote')
    model.countries[1].flags.add('delay_player_next_council_vote')
def expire_council(model):
    model.global_vars['num_days']=model.global_vars['eon_eu_council_vote_deadline_day']
    model.timeout()
def approved(test,law=101):
    if not available():test.skipTest('No handoff source in this selected current baseline.')
    model=ep.EpModel();model.temp['v']=law;model.click_ep();model.majority()
    serial=model.global_vars['eon_eu_ep_instance']
    model.timeout_ep()
    test.assertEqual(model.global_vars[f'eon_eu_handoff_{law}_ep_serial'],serial)
    test.assertEqual(model.global_vars[f'eon_eu_handoff_{law}_status'],1)
    test.assertEqual(model.global_vars[f'eon_eu_handoff_{law}_mode'],1)
    return model

class SourceContracts(unittest.TestCase):
    def test_all_three_loaders_bind_exact_selected_handoff_helpers(self):
        models=(vote.VoteModel(),front.FrontModel(),ep.EpModel())
        if available():
            effects={k:v for k,_,v in front.read(EF)}
            triggers={k:v for k,_,v in front.read(TR)}
            self.assertEqual(len(effects),8)
            self.assertEqual(len([k for k in triggers if k.startswith('eon_eu_handoff_pending_')]),47)
            for model in models:
                for key,body in effects.items():self.assertEqual(model.effects[key],body)
                for key,body in triggers.items():self.assertEqual(model.triggers[key],body)
        else:
            for model in models:self.assertNotIn('eon_eu_handoff_issue',model.effects)

    def test_new_presentation_support_keeps_unknown_primitives_fail_closed(self):
        model=vote.VoteModel()
        with self.assertRaisesRegex(AssertionError,'Unmodeled trigger'):
            model.trigger([('invented_handoff_trigger','=','yes')],[model.root])
        with self.assertRaisesRegex(AssertionError,'Unmodeled effect'):
            model.effect([('invented_handoff_effect','=','yes')],[model.root])

    def test_source_reader_has_selected_override_and_unchanged_fallback(self):
        changed='common/scripted_effects/eon_eu_parliament_effects.txt'
        self.assertEqual(front.source_path(changed,front.SOURCE),front.SOURCE/changed)
        unchanged='common/scripted_triggers/eon_eu_parliament_triggers.txt'
        expected=front.SOURCE/unchanged
        if not expected.exists():expected=front.ROOT/unchanged
        self.assertEqual(front.source_path(unchanged,front.SOURCE),expected)
        self.assertEqual(ep.read(unchanged),front.read(unchanged))

    def test_thirteen_guards_allow_only_two_exact_cooldown_exceptions(self):
        actual=normalized(one(front.read(VT),'eon_eu_council_proposal_ready'))
        old=BASE['proposal_ready'];self.assertEqual(len(old),13)
        expected=deepcopy(old)
        if available():
            for index in (5,6):
                expected[index]=['OR','=',[old[index],['eon_eu_handoff_selected_pending','=','yes']]]
        self.assertEqual(actual,expected)
        for index in set(range(13))-{5,6}:self.assertEqual(actual[index],old[index])

    def test_free_policy_and_exact_visible_500_fee_preserved(self):
        self.assertEqual(normalized(one(front.read(VT),'eon_eu_council_proposal_free')),BASE['proposal_free'])
        body=one(one(front.read(VE),'eon_eu_start_council_proposal'),'if')
        fees=[node for node in body if node[0]=='if' and ('add_political_power','=','-500') in node[2]]
        self.assertEqual(normalized(fees),[BASE['fee_branch']])
        self.assertNotIn('hidden_effect',str(fees))

    def test_existing_sov_influence_scope_has_negative_and_member_controls(self):
        model=front.FrontModel();actor=model.countries[1];model.root=actor
        actor.EU_external_sov_influence_15=True
        body=model.triggers['eon_eu_council_proposal_ready'][11]
        self.assertFalse(model.trigger([body],[actor]))
        sov=model.countries[7]
        sov.ideas.add('EU_member');sov.flags.add('eon_eu_membership_recognized')
        model.global_arrays['EU_member'].append(sov.pointer)
        self.assertTrue(model.trigger([body],[actor]))
        sov.ideas.discard('EU_member')
        self.assertFalse(model.trigger([body],[actor]))

    def test_literal_law_results_and_original_special_history_unchanged(self):
        self.assertEqual(digest(front.read(LAW)),BASE['legacy_law_result_ast_sha256'])
        self.assertEqual(hashlib.sha256((HERE/'parliament-special-ast.json').read_bytes()).hexdigest(),BASE['special_history_sha256'])

    def test_archive_has_only_named_prefix_then_exact_old_body(self):
        body=one(front.read(LC),'eon_eu_reset_institutional_laws')
        if available():
            self.assertEqual(body[0],('eon_eu_handoff_archive','=','yes'))
            body=body[1:]
        self.assertEqual(digest(body),BASE['archive_body_ast_sha256'])

    def test_hidden_bookkeeping_wrappers_execute_as_visible_bodies(self):
        if not available():self.skipTest('No handoff source in selected baseline.')
        effects={k:v for k,_,v in front.read(EF)}
        for key,body in effects.items():
            self.assertEqual([n[0] for n in body],['hidden_effect'],key)
            self.assertNotIn('add_political_power',str(body),key)
        for factory in (vote.VoteModel,front.FrontModel,ep.EpModel):
            wrapped=factory();literal=factory()
            wrapped.required('eon_eu_handoff_initialize')
            literal.effect(one(effects['eon_eu_handoff_initialize'],'hidden_effect'),[literal.root])
            self.assertEqual(wrapped.global_vars,literal.global_vars)
            self.assertEqual(wrapped.global_vars['eon_eu_approval_epoch'],1)

    def test_tooltip_and_hidden_trigger_preserve_positive_and_negative_truth(self):
        model=approved(self);model.temp['v']=101;model.root=model.countries[1]
        body=model.triggers['eon_eu_handoff_selected_pending']
        tooltip=one(body,'custom_trigger_tooltip')
        self.assertEqual(one(tooltip,'tooltip'),'eon_eu_handoff_selected_pending_tt')
        literal=one(tooltip,'hidden_trigger')
        for law in (101,201,998):
            model.temp['v']=law
            self.assertEqual(model.trigger(body,[model.root]),model.trigger(literal,[model.root]))
            self.assertEqual(model.trigger(body,[model.root]),law==101)

class HandoffTransitions(unittest.TestCase):
    def test_legacy_route_charges_once_and_never_invents_receipt(self):
        model=front.FrontModel();before=model.countries[1].variables['political_power']
        model.click(front.P);serial=model.global_vars['eon_eu_council_vote_instance']
        model.click(front.P)
        self.assertEqual(model.countries[1].variables['political_power'],before-500)
        self.assertEqual(model.global_vars['eon_eu_council_vote_instance'],serial)
        self.assertEqual(record(model),{})

    def test_matching_pending_bypasses_both_cooldowns_but_charges_once(self):
        model=approved(self);delay(model);model.temp['v']=101
        before=model.countries[1].variables['political_power'];issued=record(model)
        self.assertTrue(model.enabled(front.P))
        model.click(front.P);serial=model.global_vars['eon_eu_council_vote_instance']
        self.assertEqual(model.countries[1].variables['political_power'],before-500)
        self.assertEqual(model.global_vars['eon_eu_handoff_101_status'],2)
        self.assertEqual(model.global_vars['eon_eu_handoff_101_council_serial'],serial)
        self.assertEqual(model.global_vars['eon_eu_handoff_101_ep_serial'],issued['eon_eu_handoff_101_ep_serial'])
        self.assertIn('delay_next_council_vote',model.global_flags)
        self.assertIn('delay_player_next_council_vote',model.countries[1].flags)
        before=bounded_state(model);model.click(front.P);self.assertEqual(bounded_state(model),before)

    def test_newer_parliament_close_retains_other_law_pending_identity(self):
        model=approved(self);first=record(model)
        model.temp['v']=201;model.click_ep();model.majority();model.timeout_ep()
        self.assertEqual(record(model),first)
        self.assertGreater(model.global_vars['eon_eu_handoff_201_ep_serial'],model.global_vars['eon_eu_handoff_101_ep_serial'])
        second=record(model,201);delay(model);model.temp['v']=101;model.click(front.P)
        self.assertEqual(model.global_vars['eon_eu_handoff_101_status'],2)
        self.assertEqual(record(model,201),second)
        expire_council(model)
        self.assertEqual(model.global_vars['eon_eu_handoff_101_status'],4)
        self.assertEqual(record(model,201),second)

    def test_wrong_id_epoch_serial_and_consumed_status_deny_before_fee(self):
        if not available():self.skipTest('No handoff source in selected baseline.')
        faults=('wrong_id','stale_epoch','zero_ep_serial','already_claimed','claimed_serial','approval_missing','queue_missing','already_enacted')
        for fault in faults:
            with self.subTest(fault=fault):
                model=approved(self);delay(model);model.temp['v']=101
                if fault=='wrong_id':model.temp['v']=201;model.global_arrays['EU_council_votes'].append(201)
                elif fault=='stale_epoch':model.global_vars['eon_eu_handoff_101_epoch']+=1
                elif fault=='zero_ep_serial':model.global_vars['eon_eu_handoff_101_ep_serial']=0
                elif fault=='already_claimed':model.global_vars['eon_eu_handoff_101_status']=2
                elif fault=='claimed_serial':model.global_vars['eon_eu_handoff_101_council_serial']=1
                elif fault=='approval_missing':model.global_flags.discard('focus_EU101_EP_approval')
                elif fault=='queue_missing':model.global_arrays['EU_council_votes']=[]
                elif fault=='already_enacted':model.global_arrays['EU_passed_votes']=[101]
                before=bounded_state(model)
                self.assertFalse(model.enabled(front.P));model.click(front.P)
                self.assertEqual(bounded_state(model),before)

    def test_all_other_eleven_pre_fee_gates_still_block_valid_pending(self):
        if not available():self.skipTest('No handoff source in selected baseline.')
        # These are declared source inputs, never state changes to a running game.
        faults=((0,'suspended'),(1,'dormant'),(2,'membership_array'),(3,'queue'),(4,'unsupported'),
                (7,'active_round'),(8,'insufficient_pp'),(9,'commission'),(10,'foreign_chi'),(11,'foreign_sov'),(12,'eurosceptic'))
        for index,fault in faults:
            with self.subTest(gate=index,fault=fault):
                model=approved(self);delay(model);model.temp['v']=101;actor=model.countries[1]
                model.root=actor;guards=model.triggers['eon_eu_council_proposal_ready']
                self.assertEqual([model.trigger([node],[actor]) for node in guards],[True]*13)
                if fault=='suspended':actor.ideas.add('EUU_voting_rights_suspended')
                elif fault=='dormant':model.global_flags.add('eon_eu_dormant')
                elif fault=='membership_array':model.global_arrays['EU_member'].remove(actor.pointer)
                elif fault=='queue':model.global_arrays['EU_council_votes']=[]
                elif fault=='unsupported':model.temp['v']=998;model.global_arrays['EU_council_votes'].append(998)
                elif fault=='active_round':model.global_vars['current_active_vote_disp']=201
                elif fault=='insufficient_pp':actor.variables['political_power']=500
                elif fault=='commission':model.countries[2].ideas.discard('EU_commission_president')
                elif fault=='foreign_chi':actor.EU_external_chi_influence_15=True
                elif fault=='foreign_sov':actor.EU_external_sov_influence_15=True
                elif fault=='eurosceptic':actor.variables['eurosceptic']=.4
                self.assertFalse(model.trigger([guards[index]],[actor]))
                before=bounded_state(model);self.assertFalse(model.enabled(front.P));model.click(front.P)
                self.assertEqual(bounded_state(model),before)

    def test_human_root_through_ai_commission_issues_actual_majority_receipt(self):
        if not available():self.skipTest('No handoff source in selected baseline.')
        model=ep.EpModel();model.click_ep();model.majority()
        # Declare AI authority at the acceptance phase. This checks ROOT versus
        # THIS source scope; it is not an AI proposal/mission scheduling claim.
        model.countries[2].ai=True
        model.click_ep('pass_vote_button_click',actor=1)
        self.assertEqual(model.global_arrays['EU_council_votes'],[101])
        self.assertEqual(model.global_vars['eon_eu_handoff_101_status'],1)
        self.assertEqual(model.global_vars['eon_eu_handoff_101_mode'],2)
        self.assertGreaterEqual(model.global_vars['eon_eu_handoff_101_support'],model.global_vars['eon_eu_handoff_101_majority'])
        self.assertTrue(model.countries[2].ai);self.assertFalse(model.countries[1].ai)

    def test_direct_issue_without_verified_round_cannot_forge_receipt(self):
        if not available():self.skipTest('No handoff source in selected baseline.')
        model=ep.EpModel();model.global_flags.add('focus_EU101_EP_approval')
        model.global_arrays['EU_council_votes']=[101];model.root=model.countries[2]
        before=bounded_state(model);model.required('eon_eu_handoff_issue')
        self.assertEqual(bounded_state(model),before)
        self.assertEqual(record(model),{})

    def test_adopted_receipt_finalizes_once_after_actual_source_majority(self):
        model=approved(self);delay(model);model.temp['v']=101;model.click(front.P)
        for actor in range(1,7):
            model.root=model.countries[actor];model.required('eon_eu_support_council_vote')
        expire_council(model)
        self.assertEqual(model.global_arrays['EU_passed_votes'],[101])
        self.assertEqual(model.global_vars['eon_eu_handoff_101_status'],3)
        self.assertTrue(all('EUU_cfr_eu' in model.countries[i].ideas for i in range(1,7)))
        before=bounded_state(model);model.timeout();model.click(front.P)
        self.assertEqual(bounded_state(model),before)

    def test_failure_consumes_exception_but_retains_ordinary_paid_retry(self):
        model=approved(self);delay(model);model.temp['v']=101;model.click(front.P)
        expire_council(model)
        self.assertEqual(model.global_vars['eon_eu_handoff_101_status'],4)
        self.assertEqual(model.global_vars['EUU_recently_failed_vote'],101)
        self.assertIn(101,model.global_arrays['EU_council_votes'])
        old=record(model);before=bounded_state(model);model.click(front.P)
        self.assertEqual(bounded_state(model),before)
        # Explicit declared elapsed cooldown inputs, not a natural-clock proof.
        model.global_flags.discard('delay_next_council_vote')
        model.countries[1].flags.discard('delay_player_next_council_vote')
        pp=model.countries[1].variables['political_power'];serial=model.global_vars['eon_eu_council_vote_instance']
        model.click(front.P)
        self.assertEqual(model.global_vars['eon_eu_council_vote_instance'],serial+1)
        self.assertEqual(model.countries[1].variables['political_power'],pp-500)
        self.assertEqual(record(model),old)

    def test_archive_epoch_invalidates_receipt_and_late_closed_callbacks(self):
        model=approved(self);delay(model);model.temp['v']=101;model.click(front.P)
        old_epoch=model.global_vars['eon_eu_approval_epoch']
        model.required('eon_eu_handoff_archive')
        # Run the actual Council archive seam. Other EU/EDU reset systems have
        # their own interpreters and are deliberately outside this model test.
        model.required('eon_eu_close_council_vote')
        self.assertEqual(model.global_vars['eon_eu_approval_epoch'],old_epoch+1)
        self.assertEqual(model.global_vars['eon_eu_handoff_101_status'],0)
        self.assertEqual(model.global_vars['eon_eu_handoff_101_ep_serial'],0)
        before=bounded_state(model);model.timeout();model.timeout_ep();model.click(front.P)
        self.assertEqual(bounded_state(model),before)

    def test_missing_exception_control_blocks_then_actual_helper_restores(self):
        model=approved(self);delay(model);model.temp['v']=101
        actual=model.triggers['eon_eu_handoff_selected_pending']
        model.triggers['eon_eu_handoff_selected_pending']=[('always','=','no')]
        before=bounded_state(model);self.assertFalse(model.enabled(front.P));model.click(front.P)
        self.assertEqual(bounded_state(model),before)
        model.triggers['eon_eu_handoff_selected_pending']=actual
        self.assertTrue(model.enabled(front.P));model.click(front.P)
        self.assertEqual(model.global_vars['eon_eu_handoff_101_status'],2)

if __name__=='__main__':unittest.main(verbosity=2)
