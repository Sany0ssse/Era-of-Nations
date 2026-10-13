"""Actual Council GUI/mission AST regression controls; no native campaign proof."""
import unittest
from eon_eu_frontend_model import FrontModel, P, S, ROOT, HERE, ast, one, read, mission, walk

AGENDA_IDS = (101, 102, 103, 104, 105, 201, 202, 203, 204, 205, 206, 207, 208, 301, 302, 303, 304, 305, 306, 307, 308, 401, 402, 403, 404, 405, 406, 407, 408, 601, 602, 603, 703, 110, 111, 112, 605, 606, 607, 608, 609, 610, 611, 650, 651, 652, 653)

class FrontendRegressions(unittest.TestCase):
    def test_proposal_has_no_localized_meta_dispatch(self):
        model = FrontModel(); model.click(P)
        self.assertFalse(any(r[0] == 'LOCALIZED_META_NOT_EXECUTED' for r in model.native_receipts))

    def test_result_and_timer_have_no_localized_meta(self):
        for ident in ('EU_voting_mission_focus_EUXXX_QMV_result', 'EU_voting_mission_focus_EUXXX_QMV_result_timer'):
            self.assertFalse(any(n[0] in ('meta_effect', 'meta_trigger') for n in walk(mission(ident))))

    def test_proposal_revalidates_invalid_actor(self):
        model = FrontModel(); model.click(P, actor=7)
        self.assertEqual(model.global_vars['current_active_vote_disp'], 0)
        self.assertEqual(model.countries[7].variables['political_power'], 2000)

    def test_proposal_revalidates_suspended_actor(self):
        model = FrontModel(); model.countries[1].ideas.add('EUU_voting_rights_suspended'); model.click(P)
        self.assertEqual(model.global_vars['current_active_vote_disp'], 0)

    def test_proposal_does_not_replace_existing_agenda(self):
        model = FrontModel(); model.global_vars['current_active_vote_disp'] = 401; model.click(P)
        self.assertEqual(model.global_vars['current_active_vote_disp'], 401)
        self.assertEqual(model.countries[1].variables['political_power'], 2000)

    def test_proposal_rejects_numeric_unsupported_agenda(self):
        model = FrontModel(); model.temp['v'] = 999; model.global_arrays['EU_council_votes'].append(999); model.click(P)
        self.assertEqual(model.global_vars['current_active_vote_disp'], 0)

    def test_proposal_rejects_not_available_agenda(self):
        model = FrontModel(); model.temp['v'] = 104; model.click(P)
        self.assertEqual(model.global_vars['current_active_vote_disp'], 0)

    def test_proposal_rejects_missing_commission_owner_even_single_member(self):
        model = FrontModel(); model.countries[2].ideas.discard('EU_commission_president')
        model.global_vars['EU_member_count'] = 1
        model.click(P)
        self.assertEqual(model.global_vars['current_active_vote_disp'], 0)

    def test_proposal_clears_all_prior_ballots_and_influence_flags(self):
        model = FrontModel(); model.global_arrays['eon_eu_council_abstainers'] = [model.countries[3].pointer]
        model.countries[3].flags.add('current_vote_influenced'); model.click(P)
        self.assertEqual(model.global_arrays['eon_eu_council_abstainers'], [])
        self.assertNotIn('current_vote_influenced', model.countries[3].flags)
        self.assertEqual(model.global_vars['eon_eu_unanswered_members'], 6)

    def test_each_single_officeholder_is_fee_exempt(self):
        for office in ('EU_commission_president', 'EU_council_president', 'EU_parliament_president'):
            model = FrontModel(); model.countries[1].ideas.add(office); model.click(P)
            self.assertEqual(model.countries[1].variables['political_power'], 2000, office)

    def test_paid_proposal_charges_once_on_repeat(self):
        model = FrontModel(); model.click(P); model.click(P)
        self.assertEqual(model.countries[1].variables['political_power'], 1500)

    def test_proposal_schedules_existing_mission_ids_once(self):
        model = FrontModel(); model.click(P)
        results = [r for r in model.native_receipts if r[0] == 'activate_mission']
        self.assertEqual(len(results), 6)
        self.assertEqual(sum(r[2] == 'EU_voting_mission_focus_EUXXX_QMV_result' for r in results), 1)

    def sway_model(self):
        model = FrontModel(); model.click(P)
        model.root = model.countries[1]; model.required('eon_eu_support_council_vote')
        model.root = model.countries[3]; model.required('eon_eu_reject_council_vote')
        model.countries[3].ai = True
        return model

    def test_sway_enabled_debit_cost_identical_and_cannot_overdraw(self):
        model = self.sway_model(); model.countries[1].variables['political_power'] = 900
        self.assertFalse(model.enabled(S, target=3))
        model.click(S, target=3)
        self.assertEqual(model.countries[1].variables['political_power'], 900)

    def test_sway_changes_canonical_ballot_once_not_incremented_duplicates(self):
        model = self.sway_model(); model.click(S, target=3); model.click(S, target=3)
        self.assertEqual(model.global_vars['EU_active_vote_yes'], 2)
        self.assertEqual(model.global_vars['EU_active_vote_no'], 0)
        self.assertEqual(model.global_arrays['EU_active_vote_supporters'].count(model.countries[3].pointer), 1)
        self.assertEqual(model.countries[1].variables['political_power'], 500)

    def test_sway_invalid_actor_cannot_edit_live_country_vote(self):
        model = self.sway_model(); model.global_arrays['EU_active_vote_supporters'].append(model.countries[7].pointer)
        model.click(S, actor=7, target=3)
        self.assertIn(model.countries[3].pointer, model.global_arrays['EU_active_vote_rejecters'])
        self.assertEqual(model.countries[7].variables['political_power'], 2000)

    def test_sway_suspended_actor_cannot_edit_vote(self):
        model = self.sway_model(); model.countries[1].ideas.add('EUU_voting_rights_suspended'); model.click(S, target=3)
        self.assertIn(model.countries[3].pointer, model.global_arrays['EU_active_vote_rejecters'])

    def test_sway_abstention_or_unanswered_is_not_interpreted_as_rejection(self):
        for callback in ('eon_eu_abstain_council_vote', 'eon_eu_close_council_vote'):
            model = self.sway_model(); model.root = model.countries[1]; model.required(callback); model.click(S, target=3)
            self.assertEqual(model.countries[1].variables['political_power'], 1500)

    def test_sway_weights_residents_without_cached_legacy_ratio(self):
        model = self.sway_model(); model.states[103].population = 10000
        model.countries[3].variables['EU_pop_ratio'] = .9
        model.click(S, target=3)
        self.assertAlmostEqual(model.global_vars['EU_pop_ratio_yes'], 110000 / 510000)
        self.assertAlmostEqual(model.countries[1].variables['political_power'], 1500 - 7500 * (10000 / 510000))

    def test_actual_law_result_full_start_ballots_declared_timeout(self):
        model = FrontModel(); model.click(P)
        model.ballot(range(1, 7)); model.timeout()
        self.assertEqual(model.global_vars['current_active_vote_disp'], 0)
        self.assertEqual(model.global_arrays['EU_passed_votes'], [101])
        self.assertTrue(all('EUU_cfr_eu' in model.countries[i].ideas for i in range(1, 7)))

    def test_actual_law_result_does_not_pass_unanswered_members(self):
        model = FrontModel(); model.click(P); model.ballot([1]); model.timeout()
        self.assertEqual(model.global_vars['current_active_vote_disp'], 0)
        self.assertNotIn(101, model.global_arrays.get('EU_passed_votes', []))

    def test_result_replay_does_not_repeat_law_or_passed_receipt(self):
        model = FrontModel(); model.click(P); model.ballot(range(1, 7)); model.timeout(); model.timeout()
        self.assertEqual(model.global_arrays['EU_passed_votes'], [101])

    def test_changed_numeric_agenda_rejects_stale_timeout(self):
        model = FrontModel(); model.click(P); model.global_vars['current_active_vote_disp'] = 401; model.timeout()
        self.assertEqual(model.global_vars['current_active_vote_disp'], 401)
        self.assertNotIn(101, model.global_arrays.get('EU_passed_votes', []))

    def test_same_agenda_new_generation_rejects_stale_timeout(self):
        model = FrontModel(); model.click(P); model.global_vars['eon_eu_council_vote_instance'] = 2; model.timeout()
        self.assertEqual(model.global_vars['current_active_vote_disp'], 101)

    def test_former_office_holder_cannot_resolve(self):
        model = FrontModel(); model.click(P); model.ballot(range(1, 7))
        model.countries[2].ideas.discard('EU_commission_president'); model.timeout()
        self.assertEqual(model.global_vars['current_active_vote_disp'], 101)
        self.assertNotIn(101, model.global_arrays.get('EU_passed_votes', []))

    def test_complete_callback_rechecks_majority_before_early_result(self):
        model = FrontModel(); model.click(P); model.ballot([1])
        model.root = model.countries[2]
        model.effect(one(mission('EU_voting_mission_focus_EUXXX_QMV_result'), 'complete_effect'), [model.root])
        self.assertEqual(model.global_vars['current_active_vote_disp'], 101)
        model.ballot(range(1, 7))
        model.effect(one(mission('EU_voting_mission_focus_EUXXX_QMV_result'), 'complete_effect'), [model.root])
        self.assertEqual(model.global_vars['current_active_vote_disp'], 101)
        self.assertNotIn(101, model.global_arrays.get('EU_passed_votes', []))
        model.global_flags.discard('eon_eu_council_vote_deadline')
        model.effect(one(mission('EU_voting_mission_focus_EUXXX_QMV_result'), 'complete_effect'), [model.root])
        self.assertEqual(model.global_arrays['EU_passed_votes'], [101])

    def test_same_owner_new_round_positive_deadline_makes_old_generic_callbacks_inert(self):
        model = FrontModel(); model.click(P); model.ballot(range(1, 7))
        model.required('eon_eu_archive_council_round')
        model.click(P); model.ballot(range(1, 7))
        # Native fixed mission callbacks have no immutable payload. Country vars
        # are already overwritten with the NEW round, as real callbacks see them.
        before_vars = dict(model.global_vars)
        before_flags = set(model.global_flags)
        before_arrays = {k: list(v) for k, v in model.global_arrays.items()}
        before_missions = {i: (set(c.missions), dict(c.mission_days)) for i, c in model.countries.items()}
        before_receipts = list(model.native_receipts)
        for owner, ident in ((2, 'EU_voting_mission_focus_EUXXX_QMV_result'), (3, 'EU_voting_mission_focus_EUXXX_QMV_result_timer')):
            model.root = model.countries[owner]
            self.assertEqual(model.root.variables['eon_eu_council_mission_instance'], model.global_vars['eon_eu_council_vote_instance'])
            for callback in ('timeout_effect', 'complete_effect'):
                model.effect(one(mission(ident), callback), [model.root])
        self.assertEqual(model.global_vars, before_vars)
        self.assertEqual(model.global_flags, before_flags)
        self.assertEqual(model.global_arrays, before_arrays)
        self.assertEqual({i: (set(c.missions), dict(c.mission_days)) for i, c in model.countries.items()}, before_missions)
        self.assertEqual(model.native_receipts, before_receipts)

    def test_expired_current_timer_generic_wakeup_can_snapshot_without_commission_enactment(self):
        model = FrontModel(); model.click(P); model.ballot(range(1, 7))
        model.countries[2].ideas.discard('EU_commission_president')
        model.global_flags.discard('eon_eu_council_vote_deadline')
        model.root = model.countries[3]
        model.effect(one(mission('EU_voting_mission_focus_EUXXX_QMV_result_timer'), 'timeout_effect'), [model.root])
        self.assertEqual(model.global_vars['eon_eu_council_outcome_yes'], 1)
        self.assertEqual(model.global_vars['current_active_vote_disp'], 101)
        self.assertNotIn(101, model.global_arrays.get('EU_passed_votes', []))
        self.assertNotIn('EU_voting_mission_focus_EUXXX_QMV_result_timer', model.root.missions)

    def test_shortened_ui_timer_does_not_end_unexpired_canonical_deadline(self):
        model = FrontModel(); model.click(P); model.ballot(range(1, 7))
        model.root = model.countries[2]
        model.effect(one(mission('EU_voting_mission_focus_EUXXX_QMV_result'), 'timeout_effect'), [model.root])
        self.assertEqual(model.global_vars['current_active_vote_disp'], 101)
        self.assertIn('eon_eu_council_vote_deadline', model.global_flags)

    def test_commission_vacancy_retains_round_and_original_deadline(self):
        model = FrontModel(); model.click(P); model.countries[2].ideas.discard('EU_commission_president')
        deadline = model.global_vars['eon_eu_council_vote_deadline_day']
        model.root = model.countries[1]; model.required('eon_eu_reconcile_council_vote_owner')
        self.assertEqual(model.global_vars['current_active_vote_disp'], 101)
        self.assertEqual(model.global_vars['eon_eu_council_vote_deadline_day'], deadline)
        self.assertIn('eon_eu_council_vote_deadline', model.global_flags)

    def test_owner_transfer_keeps_deadline_and_rejects_old_callback(self):
        model = FrontModel(); model.click(P); model.countries[2].ideas.discard('EU_commission_president')
        model.countries[4].ideas.add('EU_commission_president')
        model.global_vars.update(eucomission=model.countries[4].pointer, num_days=6)
        model.root = model.countries[1]; model.required('eon_eu_reconcile_council_vote_owner')
        self.assertEqual(model.global_vars['eon_eu_council_vote_deadline_day'], 14)
        self.assertEqual(model.flag_days[('set_global_flag', 1, 'eon_eu_council_vote_deadline')], 14)
        self.assertIn(('add_days_mission_timeout', 4, 'EU_voting_mission_focus_EUXXX_QMV_result', -6), model.native_receipts)
        model.ballot(range(1, 7)); model.timeout(2)
        self.assertEqual(model.global_vars['current_active_vote_disp'], 101)
        model.timeout(4)
        self.assertEqual(model.global_arrays['EU_passed_votes'], [101])

    def test_resumed_holder_resolves_expired_round_once(self):
        model = FrontModel(); model.click(P); model.ballot(range(1, 7))
        model.countries[2].ideas.discard('EU_commission_president')
        model.global_flags.discard('eon_eu_council_vote_deadline')
        model.root = model.countries[1]; model.required('eon_eu_reconcile_council_vote_owner')
        self.assertEqual(model.global_vars['current_active_vote_disp'], 101)
        model.countries[4].ideas.add('EU_commission_president'); model.global_vars['eucomission'] = model.countries[4].pointer
        model.required('eon_eu_reconcile_council_vote_owner'); model.required('eon_eu_reconcile_council_vote_owner')
        self.assertEqual(model.global_arrays['EU_passed_votes'], [101])

    def test_archive_invalidates_pending_round_before_callbacks(self):
        model = FrontModel(); model.click(P); model.ballot(range(1, 7))
        model.required('eon_eu_archive_council_round'); model.timeout()
        self.assertEqual(model.global_vars['current_active_vote_disp'], 0)
        self.assertNotIn(101, model.global_arrays.get('EU_passed_votes', []))

    def test_all_47_routes_match_existing_named_result_once(self):
        model = FrontModel()
        pins = {'agenda_ids': AGENDA_IDS}
        body = model.effects.get('eon_eu_dispatch_current_council_result', [])
        calls = [k for k, _, v in walk(body) if k.startswith('focus_EU') and k.endswith('_QMV_result')]
        self.assertEqual(set(calls), {f'focus_EU{i}_QMV_result' for i in pins['agenda_ids']})
        self.assertEqual(len(calls), 47)

    def legacy_model(self, result=8, timer=None):
        model = FrontModel()
        model.global_vars.update(current_active_vote_disp=101, EUXXX_council_agenda=101)
        model.global_flags.add('focus_EU101_QMV_voted')
        if result is not None:
            model.countries[2].missions.add('EU_voting_mission_focus_EUXXX_QMV_result')
            model.countries[2].mission_days['EU_voting_mission_focus_EUXXX_QMV_result'] = result
        if timer is not None:
            model.countries[3].missions.add('EU_voting_mission_focus_EUXXX_QMV_result_timer')
            model.countries[3].mission_days['EU_voting_mission_focus_EUXXX_QMV_result_timer'] = timer
        return model

    def test_legacy_existing_clock_is_adopted_without_restart(self):
        model = self.legacy_model(result=5)
        model.required('eon_eu_reconcile_council_vote_owner')
        self.assertEqual(model.flag_days[('set_global_flag', 1, 'eon_eu_council_vote_deadline')], 5)
        self.assertEqual(model.countries[2].mission_days['EU_voting_mission_focus_EUXXX_QMV_result'], 5)
        self.assertFalse(any(r[0] == 'activate_mission' for r in model.native_receipts))

    def test_legacy_dual_clocks_preserve_earliest_and_calibrate_current_owner(self):
        model = self.legacy_model(result=8, timer=3)
        model.required('eon_eu_reconcile_council_vote_owner')
        self.assertEqual(model.flag_days[('set_global_flag', 1, 'eon_eu_council_vote_deadline')], 3)
        self.assertEqual(model.countries[2].mission_days['EU_voting_mission_focus_EUXXX_QMV_result'], 3)
        self.assertEqual(model.countries[3].mission_days['EU_voting_mission_focus_EUXXX_QMV_result_timer'], 3)

    def test_legacy_sole_timer_is_clock_not_enactment_authority(self):
        model = self.legacy_model(result=None, timer=2)
        model.required('eon_eu_reconcile_council_vote_owner')
        self.assertEqual(model.flag_days[('set_global_flag', 1, 'eon_eu_council_vote_deadline')], 2)
        self.assertEqual(model.countries[2].mission_days['EU_voting_mission_focus_EUXXX_QMV_result'], 2)
        self.assertEqual(model.global_vars['eon_eu_council_vote_owner'], model.countries[2].pointer)
        self.assertNotIn(101, model.global_arrays.get('EU_passed_votes', []))

    def test_legacy_expired_clock_never_gets_fresh_deadline(self):
        model = self.legacy_model(result=0)
        model.required('eon_eu_reconcile_council_vote_owner')
        self.assertNotIn('eon_eu_council_vote_deadline', model.global_flags)
        self.assertEqual(model.global_vars['current_active_vote_disp'], 0)
        self.assertNotIn(101, model.global_arrays.get('EU_passed_votes', []))

    def test_legacy_result_expired_callback_before_first_daily_resolves_once(self):
        model = self.legacy_model(result=None); model.ballot(range(1, 7))
        model.root = model.countries[2]
        body = one(mission('EU_voting_mission_focus_EUXXX_QMV_result'), 'timeout_effect')
        model.effect(body, [model.root]); model.effect(body, [model.root])
        self.assertEqual(model.global_arrays['EU_passed_votes'], [101])
        self.assertNotIn('eon_eu_council_vote_deadline', model.global_flags)
        self.assertFalse(any(r[0] == 'activate_mission' for r in model.native_receipts))

    def test_legacy_timer_expired_callback_before_first_daily_resolves_only_via_commission(self):
        model = self.legacy_model(result=8); model.ballot(range(1, 7))
        model.root = model.countries[3]
        model.effect(one(mission('EU_voting_mission_focus_EUXXX_QMV_result_timer'), 'timeout_effect'), [model.root])
        self.assertEqual(model.global_arrays['EU_passed_votes'], [101])
        self.assertIn(('country', 2, 'focus_EU101_QMV_result'), model.trace)
        self.assertNotIn(('country', 3, 'focus_EU101_QMV_result'), model.trace)

    def test_legacy_before_daily_retention_does_not_cancel_positive_clock(self):
        model = self.legacy_model(result=8)
        self.assertFalse(model.trigger(one(mission('EU_voting_mission_focus_EUXXX_QMV_result'), 'cancel_trigger'), [model.countries[2]]))
        self.assertTrue(model.trigger(one(mission('EU_voting_mission_focus_EUXXX_QMV_result'), 'visible'), [model.countries[2]]))

    def test_legacy_initial_vacancy_expiry_is_retained_until_lawful_holder_returns(self):
        model = self.legacy_model(result=8); model.ballot(range(1, 7))
        model.countries[2].ideas.discard('EU_commission_president')
        self.assertFalse(model.trigger(one(mission('EU_voting_mission_focus_EUXXX_QMV_result'), 'cancel_trigger'), [model.countries[2]]))
        # Actual timeout witness, not an unexpired source mission with injected callback.
        model.countries[2].mission_days['EU_voting_mission_focus_EUXXX_QMV_result'] = 0
        model.root = model.countries[2]
        model.effect(one(mission('EU_voting_mission_focus_EUXXX_QMV_result'), 'timeout_effect'), [model.root])
        model.countries[2].missions.clear(); model.countries[2].mission_days.clear()
        self.assertIn('eon_eu_legacy_council_expired_callback', model.global_flags)
        self.assertEqual(model.global_vars['current_active_vote_disp'], 101)
        model.countries[4].ideas.add('EU_commission_president'); model.global_vars['eucomission'] = model.countries[4].pointer
        model.root = model.countries[1]; model.required('eon_eu_reconcile_council_vote_owner')
        self.assertEqual(model.global_arrays['EU_passed_votes'], [101])
        self.assertNotIn('eon_eu_council_vote_deadline', model.global_flags)

    def test_legacy_generic_callback_cannot_expire_an_actual_positive_clock(self):
        for owner, kind in ((2, 'result'), (3, 'result_timer')):
            model = self.legacy_model(result=8, timer=3); model.ballot(range(1, 7))
            before = (dict(model.global_vars), set(model.global_flags), list(model.native_receipts), {i: set(c.missions) for i, c in model.countries.items()})
            model.root = model.countries[owner]
            model.effect(one(mission('EU_voting_mission_focus_EUXXX_QMV_' + kind), 'timeout_effect'), [model.root])
            self.assertEqual((dict(model.global_vars), set(model.global_flags), list(model.native_receipts), {i: set(c.missions) for i, c in model.countries.items()}), before)

    def test_legacy_transfer_existing_clock_requires_current_commission_and_keeps_remaining(self):
        model = self.legacy_model(result=6)
        model.countries[2].ideas.discard('EU_commission_president')
        model.countries[4].ideas.add('EU_commission_president'); model.global_vars['eucomission'] = model.countries[4].pointer
        model.required('eon_eu_reconcile_council_vote_owner')
        self.assertEqual(model.countries[4].mission_days['EU_voting_mission_focus_EUXXX_QMV_result'], 6)
        self.assertNotIn('EU_voting_mission_focus_EUXXX_QMV_result', model.countries[2].missions)
        self.assertEqual(model.global_vars['eon_eu_council_vote_owner'], model.countries[4].pointer)

    def test_legacy_orphan_without_actual_clock_cannot_invent_new_deadline(self):
        model = self.legacy_model(result=None)
        model.required('eon_eu_reconcile_council_vote_owner')
        self.assertEqual(model.global_vars['current_active_vote_disp'], 0)
        self.assertNotIn('eon_eu_council_vote_deadline', model.global_flags)
        self.assertNotIn(101, model.global_arrays.get('EU_passed_votes', []))

    def test_legacy_mismatched_agenda_or_already_passed_cannot_adopt(self):
        for mode in ('agenda', 'already_passed'):
            model = self.legacy_model()
            if mode == 'agenda': model.global_vars['EUXXX_council_agenda'] = 401
            else: model.global_arrays['EU_passed_votes'] = [101]
            model.required('eon_eu_migrate_legacy_council_round')
            self.assertNotIn('eon_eu_council_vote_clock_started', model.global_flags)
            self.assertNotIn('eon_eu_council_vote_deadline', model.global_flags)

    def test_legacy_valid_original_clock_recovers_without_localized_flag(self):
        model = self.legacy_model(result=4); model.global_flags.discard('focus_EU101_QMV_voted')
        model.required('eon_eu_reconcile_council_vote_owner')
        self.assertEqual(model.flag_days[('set_global_flag', 1, 'eon_eu_council_vote_deadline')], 4)

    def test_supported_orphan_without_any_receipt_or_clock_closes_once_and_keeps_laws(self):
        model = self.legacy_model(result=None)
        model.global_flags.discard('focus_EU101_QMV_voted')
        model.countries[1].ideas.add('EUU_cfr_eu')
        model.countries[1].flags.add('focus_EU101_QMV_yes')
        model.global_arrays['EU_passed_votes'] = [101]
        model.required('eon_eu_reconcile_council_vote_owner'); model.required('eon_eu_reconcile_council_vote_owner')
        self.assertEqual(model.global_vars['current_active_vote_disp'], 0)
        self.assertIn('EUU_cfr_eu', model.countries[1].ideas)
        self.assertIn('focus_EU101_QMV_yes', model.countries[1].flags)
        self.assertEqual(model.global_arrays['EU_passed_votes'], [101])
        self.assertEqual(model.native_receipts.count(('country_event', 2, 'eon_eu_council.1')), 1)

    def test_unsupported_or_mismatched_mode_orphan_remains_untouched(self):
        for mode in ('unsupported', 'mismatched'):
            model = self.legacy_model(result=None)
            if mode == 'unsupported': model.global_vars.update(current_active_vote_disp=999, EUXXX_council_agenda=999)
            else: model.global_vars['EUXXX_council_agenda'] = 401
            model.required('eon_eu_reconcile_council_vote_owner')
            self.assertEqual(model.global_vars['current_active_vote_disp'], 999 if mode == 'unsupported' else 101)
            self.assertFalse(any(r[0] == 'country_event' for r in model.native_receipts))

    def test_legacy_vacancy_with_valid_timer_cannot_be_cleaned_as_orphan(self):
        model = self.legacy_model(result=None, timer=4)
        model.global_flags.discard('focus_EU101_QMV_voted')
        model.countries[2].ideas.discard('EU_commission_president')
        model.required('eon_eu_reconcile_council_vote_owner')
        self.assertEqual(model.global_vars['current_active_vote_disp'], 101)
        self.assertIn('EU_voting_mission_focus_EUXXX_QMV_result_timer', model.countries[3].missions)

    def test_closed_window_rejects_support_reject_abstain_sway_and_ai(self):
        model = self.sway_model(); model.global_flags.discard('eon_eu_council_vote_deadline')
        before = {key: list(model.global_arrays.get(key, [])) for key in ('EU_active_vote_supporters', 'EU_active_vote_rejecters', 'eon_eu_council_abstainers')}
        model.root = model.countries[4]
        for callback in ('eon_eu_support_council_vote', 'eon_eu_reject_council_vote', 'eon_eu_abstain_council_vote'):
            model.required(callback)
        model.click(S, target=3)
        model.countries[4].ai = True; model.required('eon_eu_council_ai_pulse')
        self.assertEqual({key: list(model.global_arrays.get(key, [])) for key in before}, before)
        self.assertEqual(model.countries[1].variables['political_power'], 1500)

    def test_deadline_pass_failure_cannot_change_with_later_casts_and_vacancy(self):
        model = FrontModel(); model.click(P); model.ballot([1, 2, 3], [4, 5, 6])
        model.countries[2].ideas.discard('EU_commission_president')
        model.global_flags.discard('eon_eu_council_vote_deadline')
        model.root = model.countries[4]; model.required('eon_eu_support_council_vote')
        model.required('eon_eu_capture_council_deadline_outcome')
        self.assertEqual(model.global_vars['eon_eu_council_outcome_yes'], 0)
        model.countries[4].ideas.add('EU_commission_president'); model.global_vars['eucomission'] = model.countries[4].pointer
        model.required('eon_eu_reconcile_council_vote_owner')
        self.assertNotIn(101, model.global_arrays.get('EU_passed_votes', []))

    def test_membership_change_between_expiry_and_capture_cannot_rewrite_last_open_tally(self):
        model = FrontModel(); model.click(P); model.ballot([1, 2, 3], [4, 5, 6])
        self.assertEqual(model.global_vars['eon_eu_council_open_outcome_yes'], 0)
        model.global_flags.discard('eon_eu_council_vote_deadline')
        model.countries[5].ideas.add('EUU_voting_rights_suspended'); model.countries[6].ideas.discard('EU_member')
        model.required('eon_eu_recount_council_vote')
        self.assertEqual(model.global_vars['eon_eu_voters'], 4)
        model.required('eon_eu_capture_council_deadline_outcome')
        self.assertEqual(model.global_vars['eon_eu_council_outcome_yes'], 0)
        model.timeout()
        self.assertNotIn(101, model.global_arrays.get('EU_passed_votes', []))

    def test_successful_deadline_cannot_be_rewritten_by_later_membership_losses(self):
        model = FrontModel(); model.click(P); model.ballot([1, 2, 3, 4], [5, 6])
        self.assertEqual(model.global_vars['eon_eu_council_open_outcome_yes'], 1)
        model.global_flags.discard('eon_eu_council_vote_deadline')
        model.countries[3].ideas.discard('EU_member'); model.countries[4].ideas.discard('EU_member')
        model.required('eon_eu_recount_council_vote'); model.required('eon_eu_capture_council_deadline_outcome')
        self.assertEqual(model.global_vars['eon_eu_council_outcome_yes'], 1)
        model.timeout()
        self.assertEqual(model.global_arrays['EU_passed_votes'], [101])

    def test_deadline_outcome_capture_is_idempotent_and_new_round_replaces_snapshot(self):
        model = FrontModel(); model.click(P); model.ballot([1])
        model.global_flags.discard('eon_eu_council_vote_deadline')
        model.required('eon_eu_capture_council_deadline_outcome')
        model.global_arrays['EU_active_vote_supporters'] = [c.pointer for c in model.countries.values()]
        model.required('eon_eu_capture_council_deadline_outcome')
        self.assertEqual(model.global_vars['eon_eu_council_outcome_yes'], 0)
        prior = model.global_vars['eon_eu_council_outcome_instance']
        model.required('eon_eu_archive_council_round'); model.click(P)
        self.assertNotEqual(model.global_vars['eon_eu_council_outcome_instance'], prior)

    def test_changed_agenda_same_serial_cannot_transfer_capture_or_enact(self):
        model = FrontModel(); model.click(P); model.ballot(range(1, 7))
        model.countries[2].ideas.discard('EU_commission_president')
        model.countries[4].ideas.add('EU_commission_president')
        model.global_vars.update(current_active_vote_disp=401, EUXXX_council_agenda=401, eucomission=model.countries[4].pointer)
        model.global_flags.discard('eon_eu_council_vote_deadline')
        model.required('eon_eu_reconcile_council_vote_owner')
        self.assertNotEqual(model.global_vars['eon_eu_council_outcome_instance'], model.global_vars['eon_eu_council_vote_instance'])
        self.assertEqual(model.global_vars['eon_eu_council_vote_owner'], model.countries[2].pointer)
        model.timeout(4)
        self.assertEqual(model.global_vars['current_active_vote_disp'], 401)
        self.assertNotIn(401, model.global_arrays.get('EU_passed_votes', []))

    def test_deadline_outcome_is_bound_to_original_agenda_as_well_as_serial(self):
        model = FrontModel(); model.click(P); model.ballot(range(1, 7))
        model.global_flags.discard('eon_eu_council_vote_deadline'); model.required('eon_eu_capture_council_deadline_outcome')
        self.assertEqual(model.global_vars['eon_eu_council_outcome_agenda'], 101)
        model.global_vars.update(current_active_vote_disp=401, EUXXX_council_agenda=401)
        self.assertFalse(model.trigger([('eon_eu_council_deadline_outcome_current', '=', 'yes')], [model.root]))

    def test_carry_legacy_open_tally_to_adopted_serial_before_expired_capture(self):
        model = self.legacy_model(result=3); model.ballot([1, 2, 3], [4, 5, 6])
        self.assertEqual(model.global_vars['eon_eu_council_open_outcome_yes'], 0)
        model.countries[2].mission_days['EU_voting_mission_focus_EUXXX_QMV_result'] = 0
        model.countries[5].ideas.discard('EU_member'); model.countries[6].ideas.discard('EU_member')
        model.required('eon_eu_reconcile_council_vote_owner')
        self.assertNotIn(101, model.global_arrays.get('EU_passed_votes', []))

    def test_legacy_stale_same_agenda_expiry_cannot_reopen_new_generation(self):
        model = self.legacy_model(result=8); model.required('eon_eu_reconcile_council_vote_owner')
        generation = model.global_vars['eon_eu_council_vote_instance']
        model.required('eon_eu_archive_council_round')
        model.root = model.countries[1]; model.click(P)
        self.assertGreater(model.global_vars['eon_eu_council_vote_instance'], generation)
        model.root = model.countries[2]
        model.effect(one(mission('EU_voting_mission_focus_EUXXX_QMV_result'), 'timeout_effect'), [model.root])
        self.assertEqual(model.global_vars['current_active_vote_disp'], 101)
        self.assertIn('eon_eu_council_vote_deadline', model.global_flags)

if __name__ == '__main__':
    unittest.main(verbosity=2)
