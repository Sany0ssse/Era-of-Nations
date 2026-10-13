"""EDU production source-AST tests; no native/GUI/campaign claims."""
from copy import deepcopy
from pathlib import Path
import unittest
from _protocol_model import Model, ast, one, walk, HERE


class Protocol(unittest.TestCase):
    def live(self):
        m = Model(); m.decision('EU_create_EDU'); return m

    def test_create_uses_actor_not_optional_sender_and_commits_after_success(self):
        m = Model(); m.decision('EU_create_EDU', 1, 5)
        self.assertEqual(m.leader(1), 1); self.assertIsNone(m.c[5]['faction'])
        self.assertIn('EDU', m.gf); self.assertEqual(m.g['eon_edu_instance'], 1)
        self.assertEqual(m.c[1]['vars']['eon_edu_member_instance'], 1)
        self.assertEqual(m.c[1]['vars']['eon_edu_creation_attempt_serial'], 1)
        self.assertEqual(len(m.news), 1); self.assertEqual(m.logs[0][:3], (1, 1, 5))

    def test_failed_native_creation_no_global_receipt_or_news(self):
        m = Model(); m.c[1]['create_fail'] = True; m.decision('EU_create_EDU')
        self.assertNotIn('EDU', m.gf); self.assertEqual(m.g.get('eon_edu_instance', 0), 0)
        self.assertEqual(m.news, []); self.assertIsNone(m.c[1]['faction'])
        self.assertEqual(m.c[1]['vars']['eon_edu_creation_result'], 2)
        self.assertEqual(m.events, [(1,'eon_edu.7')])
        self.assertEqual(m.c[1]['vars'].get('eon_edu_constructor_confirmed_instance', 0), 0)
        self.assertEqual(m.c[1]['vars'].get('eon_edu_formed_hook_serial', 0), 0)
        self.assertEqual(m.c[1]['vars'].get('eon_edu_constructor_commit_serial', 0), 0)

    def test_successful_constructor_return_confirms_without_native_hook(self):
        m = Model(); m.native_formation_hooks = False
        m.decision('EU_create_EDU', 1, 5)
        self.assertEqual(m.leader(1), 1)
        self.assertIn('EDU', m.gf)
        self.assertEqual(m.g['eon_edu_instance'], 1)
        self.assertEqual(m.c[1]['vars']['eon_edu_member_instance'], 1)
        self.assertEqual(m.c[1]['vars'].get('eon_edu_formed_hook_serial', 0), 0)
        self.assertEqual(m.c[1]['vars'].get('eon_edu_constructor_commit_serial', 0), 1)
        self.assertEqual(m.c[1]['vars'].get('eon_edu_native_formation_commit_serial', 0), 0)
        self.assertEqual(m.c[1]['vars'].get('eon_edu_creation_intent', 0), 0)
        self.assertEqual(len(m.news), 1)

    def test_return_confirmation_replay_and_late_native_hook_preserve_actual_cohort(self):
        m = Model(); m.native_formation_hooks = False; m.decision('EU_create_EDU')
        m.decision('eon_edu_request_join', 2, 1); m.decision('eon_edu_accept_request', 1, 2)
        snapshot = deepcopy((m.g, m.gf, m.c[1]['vars']['eon_edu_member_instance'],
                             m.c[2]['vars']['eon_edu_member_instance'], m.news, m.events))
        m.run('eon_edu_confirm_created_faction'); m.run('eon_edu_confirm_created_faction')
        m.run('eon_edu_on_formed'); m.run('eon_edu_on_formed')
        self.assertEqual((m.g, m.gf, m.c[1]['vars']['eon_edu_member_instance'],
                          m.c[2]['vars']['eon_edu_member_instance'], m.news, m.events), snapshot)
        self.assertEqual(m.c[1]['vars']['eon_edu_formed_hook_serial'], 2)
        self.assertEqual(m.c[1]['vars']['eon_edu_constructor_commit_serial'], 1)
        self.assertEqual(m.c[1]['vars'].get('eon_edu_native_formation_commit_serial', 0), 0)

    def test_confirmation_requires_current_constructor_provenance_actor_clock_leader_and_policy(self):
        for field in ('no_faction', 'not_leader', 'expired', 'wrong_actor', 'old_generation',
                      'missing_witness', 'wrong_witness', 'policy', 'already_committed'):
            m = Model(); m.formation_mode = 'deferred'; m.begin_interrupted_constructor()
            m.temp['eon_edu_confirmation_origin'] = 2
            if field == 'no_faction': m.c[1]['faction'] = None
            elif field == 'not_leader': m.factions[m.c[1]['faction']]['leader'] = 2
            elif field == 'expired': m.day = 1
            elif field == 'wrong_actor': m.g['eon_edu_creation_actor'] = 3
            elif field == 'old_generation': m.g['eon_edu_generation_counter'] = 2
            elif field == 'missing_witness': m.c[1]['vars']['eon_edu_creation_constructor_instance'] = 0
            elif field == 'wrong_witness': m.c[1]['vars']['eon_edu_creation_constructor_instance'] = 2
            elif field == 'policy': m.c[1]['join'] = False
            else: m.gf.add('EDU')
            with self.subTest(field=field):
                m.run('eon_edu_confirm_created_faction')
                self.assertEqual(m.g.get('eon_edu_instance', 0), 0)
                self.assertEqual(m.c[1]['vars'].get('eon_edu_member_instance', 0), 0)
                self.assertEqual(m.news, [])
        for primitive in ('eon_edu_creation_constructor_bound', 'eon_edu_creation_policy_still_valid',
                          'is_faction_leader'):
            control = Model(); control.formation_mode = 'deferred'; control.begin_interrupted_constructor()
            control.temp['eon_edu_confirmation_origin'] = 2
            if primitive == 'eon_edu_creation_constructor_bound': control.c[1]['vars']['eon_edu_creation_constructor_instance'] = 0
            elif primitive == 'eon_edu_creation_policy_still_valid': control.c[1]['join'] = False
            else: control.factions[control.c[1]['faction']]['leader'] = 2
            broken = deepcopy(control)
            branch = broken.effects['eon_edu_confirm_created_faction'][0][2]
            branch[0] = ('limit', '=', [n for n in branch[0][2] if n[0] != primitive])
            with self.subTest(mutant=primitive):
                control.run('eon_edu_confirm_created_faction'); self.assertNotIn('EDU', control.gf)
                broken.run('eon_edu_confirm_created_faction'); self.assertIn('EDU', broken.gf)

    def test_constructor_receipt_clears_on_leave_archive_and_actual_dissolution(self):
        for route in ('leave', 'archive', 'dissolve'):
            m = Model(); m.native_formation_hooks = False; m.decision('EU_create_EDU')
            m.make_foreign_faction(4, [5]); foreign = m.c[5]['faction']
            if route == 'leave': m.leave(1)
            elif route == 'archive': m.run('eon_edu_close')
            else: m.run('eon_edu_dissolve_confirmed_union')
            with self.subTest(route=route):
                self.assertEqual(m.c[1]['vars'].get('eon_edu_constructor_confirmed_instance', 0), 0)
                self.assertEqual(m.c[5]['faction'], foreign)
                if route == 'leave':
                    m.make_foreign_faction(1); m.run('eon_edu_on_formed')
                    self.assertFalse(m.trigger(m.triggers['eon_edu_is_confirmed_member'],
                                              {'root':1,'scope':1,'from':None,'prev':()}))

    def test_verified_scripted_departure_clears_receipts_without_native_leave_hook(self):
        def forget_verified_cleanup(nodes):
            return [(key, op, forget_verified_cleanup(body) if isinstance(body, list) else body)
                    for key, op, body in nodes
                    if not (key == 'clear_variable' and body in
                            ('eon_edu_member_instance', 'eon_edu_constructor_confirmed_instance'))]
        for first_remove_fail in (False, True):
            m = Model(); m.native_formation_hooks = False; m.decision('EU_create_EDU')
            m.decision('eon_edu_request_join', 2, 1); m.decision('eon_edu_accept_request', 1, 2)
            m.native_leave_hooks = False; m.native_leadership_hooks = False
            m.c[1]['remove_fail'] = first_remove_fail
            broken = deepcopy(m)
            broken.effects['eon_edu_depart_eu'] = forget_verified_cleanup(broken.effects['eon_edu_depart_eu'])
            m.run('eon_edu_depart_eu', 1)
            broken.run('eon_edu_depart_eu', 1)
            with self.subTest(first_remove_fail=first_remove_fail):
                if first_remove_fail:
                    self.assertTrue(m.same(1, 2)); self.assertEqual(m.leader(2), 2)
                    self.assertEqual(m.c[1]['vars']['eon_edu_departure_result'], 2)
                    self.assertEqual(m.c[1]['vars']['eon_edu_member_instance'], 1)
                    self.assertEqual(m.c[1]['vars']['eon_edu_constructor_confirmed_instance'], 1)
                    m.c[1]['remove_fail'] = False; m.run('eon_edu_depart_eu', 1)
                    broken.c[1]['remove_fail'] = False; broken.run('eon_edu_depart_eu', 1)
                self.assertIsNone(m.c[1]['faction']); self.assertEqual(m.leader(2), 2)
                self.assertEqual(m.c[1]['vars']['eon_edu_departure_result'], 1)
                self.assertEqual(m.c[1]['vars']['eon_edu_member_instance'], 0)
                self.assertEqual(m.c[1]['vars']['eon_edu_constructor_confirmed_instance'], 0)
                self.assertEqual(m.c[1]['vars'].get('eon_edu_leave_hook_serial', 0), 0)
                self.assertEqual(m.c[1]['vars'].get('eon_edu_leadership_hook_serial', 0), 0)
                m.make_foreign_faction(1); m.run('eon_edu_on_formed', 1)
                self.assertFalse(m.trigger(m.triggers['eon_edu_is_confirmed_member'],
                                          {'root':1,'scope':1,'from':None,'prev':()}))
                self.assertIsNone(broken.c[1]['faction'])
                self.assertEqual(broken.c[1]['vars']['eon_edu_constructor_confirmed_instance'], 1)
                broken.make_foreign_faction(1); broken.run('eon_edu_on_formed', 1)
                self.assertTrue(broken.trigger(broken.triggers['eon_edu_is_confirmed_member'],
                                              {'root':1,'scope':1,'from':None,'prev':()}))

    def test_creation_revalidates_reform_minister_influence_and_factionless(self):
        for field in ('reform', 'minister', 'influence', 'foreign_faction', 'inactive', 'subject', 'offensive', 'join_permission', 'neutral'):
            m = Model()
            if field == 'reform': m.c[1]['ideas'].discard('European_Security_Council')
            elif field == 'minister': m.c[1]['ideas'].discard('EU_foreign_minister')
            elif field == 'foreign_faction': m.make_foreign_faction(1)
            elif field == 'join_permission': m.c[1]['join'] = False
            elif field == 'inactive': m.c[1]['active'] = False
            else: m.c[1][field] = False if field == 'influence' else True
            with self.subTest(field=field):
                self.assertFalse(m.available('EU_create_EDU'))
                m.decision('EU_create_EDU'); self.assertNotIn('EDU', m.gf)

    def test_creation_does_not_pull_or_strip_other_nato_members(self):
        m = Model(); m.make_foreign_faction(4, [3]); m.c[3]['ideas'].add('NATO_member')
        snap = deepcopy(m.c[3]); m.decision('EU_create_EDU')
        self.assertEqual(m.c[3], snap); self.assertFalse(m.same(1, 3))

    def test_duplicate_creation_counts_attempt_but_no_duplicate_news(self):
        m = self.live(); m.decision('EU_create_EDU')
        self.assertEqual(m.g['eon_edu_instance'], 1); self.assertEqual(len(m.news), 1)
        self.assertEqual(m.c[1]['vars']['eon_edu_creation_attempt_serial'], 2)
        self.assertEqual(m.c[1]['vars']['eon_edu_native_formation_commit_serial'], 1)
        self.assertEqual(m.c[1]['vars'].get('eon_edu_constructor_commit_serial', 0), 0)
        self.assertEqual(m.c[1]['vars']['eon_edu_formed_hook_serial'], 1)

    def test_explicit_request_then_accept_is_pair_bound_exact_once(self):
        m = self.live(); m.decision('eon_edu_request_join', 2, 1)
        self.assertIsNone(m.c[2]['faction']); self.assertEqual(m.c[2]['vars']['eon_edu_request_leader'], 1)
        self.assertFalse(m.available('eon_edu_accept_request', 3, 2))
        m.decision('eon_edu_accept_request', 3, 2); self.assertIsNone(m.c[2]['faction'])
        m.decision('eon_edu_accept_request', 1, 2); self.assertTrue(m.same(1, 2))
        self.assertEqual(m.c[2]['vars']['eon_edu_request_instance'], 0)
        self.assertEqual(m.c[2]['vars']['eon_edu_request_result'], 1)
        snap = deepcopy((m.c, m.g, m.events)); m.decision('eon_edu_accept_request', 1, 2)
        self.assertEqual((m.c, m.g, m.events), snap)

    def test_each_candidate_request_is_independent_no_global_lock(self):
        m = self.live(); m.decision('eon_edu_request_join', 2, 1); m.decision('eon_edu_request_join', 3, 1)
        m.decision('eon_edu_reject_request', 1, 2)
        self.assertEqual(m.c[2]['vars']['eon_edu_request_result'], 2)
        self.assertEqual(m.c[3]['vars']['eon_edu_request_instance'], 1)
        m.decision('eon_edu_accept_request', 1, 3); self.assertTrue(m.same(1, 3))

    def test_rejection_and_withdrawal_close_only_current_candidate(self):
        m = self.live(); m.decision('eon_edu_request_join', 2, 1)
        m.decision('eon_edu_withdraw_request', 2)
        self.assertEqual(m.c[2]['vars']['eon_edu_request_result'], 3)
        m.decision('eon_edu_accept_request', 1, 2); self.assertIsNone(m.c[2]['faction'])

    def test_expiry_no_join_and_cooldown_then_retry(self):
        m = self.live(); m.decision('eon_edu_request_join', 2, 1); m.expire(42)
        self.assertEqual(m.c[2]['vars']['eon_edu_request_result'], 4)
        self.assertFalse(m.available('eon_edu_request_join', 2, 1))
        m.decision('eon_edu_accept_request', 1, 2); self.assertIsNone(m.c[2]['faction'])
        m.expire(14); m.decision('eon_edu_request_join', 2, 1)
        self.assertEqual(m.c[2]['vars']['eon_edu_request_round'], 2)

    def test_accept_revalidates_every_national_and_current_membership_boundary(self):
        for field in ('subject', 'offensive', 'neutral', 'join', 'threshold', 'active', 'foreign_faction'):
            m = self.live(); m.decision('eon_edu_request_join', 2, 1)
            if field == 'foreign_faction': m.make_foreign_faction(3, [2])
            elif field == 'threshold': m.c[2][field] = 2
            else: m.c[2][field] = False if field in ('join', 'active') else True
            with self.subTest(field=field):
                m.decision('eon_edu_accept_request', 1, 2); self.assertFalse(m.same(1, 2))
                m.run('eon_edu_daily_pulse'); self.assertEqual(m.c[2]['vars']['eon_edu_request_instance'], 0)

    def test_native_add_failure_retains_live_request_without_false_acceptance(self):
        m = self.live(); m.decision('eon_edu_request_join', 2, 1); m.c[2]['join_fail'] = True
        m.decision('eon_edu_accept_request', 1, 2)
        self.assertIsNone(m.c[2]['faction']); self.assertEqual(m.c[2]['vars']['eon_edu_request_instance'], 1)
        self.assertNotEqual(m.c[2]['vars'].get('eon_edu_request_result'), 1)

    def test_changed_actual_leader_invalidates_old_application(self):
        m = self.live(); m.decision('eon_edu_request_join', 3, 1)
        m.c[2]['faction'] = m.c[1]['faction']; m.c[2]['vars']['eon_edu_member_instance'] = 1
        m.factions[m.c[1]['faction']]['leader'] = 2
        m.run('eon_edu_on_assume_leadership', 2, 1)
        m.decision('eon_edu_accept_request', 1, 3); m.decision('eon_edu_accept_request', 2, 3)
        self.assertIsNone(m.c[3]['faction']); m.run('eon_edu_daily_pulse')
        self.assertEqual(m.c[3]['vars']['eon_edu_request_result'], 5)

    def test_dismantle_same_founder_recreation_invalidates_old_instance(self):
        m = self.live(); m.decision('eon_edu_request_join', 2, 1)
        m.c[1]['faction'] = None; m.run('eon_edu_on_leave', 1); m.run('eon_edu_daily_pulse')
        m.decision('EU_create_EDU', 1); self.assertEqual(m.g['eon_edu_instance'], 2)
        m.decision('eon_edu_accept_request', 1, 2); self.assertFalse(m.same(1, 2))

    def test_new_foreign_faction_cannot_inherit_country_receipt_when_formation_hook_fires(self):
        m = self.live(); m.c[1]['faction'] = None; m.make_foreign_faction(1)
        m.run('eon_edu_on_formed', 1)
        self.assertFalse(m.trigger(m.triggers['eon_edu_is_confirmed_member'], {'root':1,'scope':1,'from':None,'prev':()}))
        m.run('eon_edu_daily_pulse'); self.assertNotIn('EDU', m.gf)

    def test_identity_does_not_depend_on_idea_during_exit_cleanup(self):
        m = self.live(); m.c[1]['ideas'].discard('EU_member'); m.c[1]['active'] = False
        self.assertTrue(m.trigger(m.triggers['eon_edu_is_confirmed_member'], {'root':1,'scope':1,'from':None,'prev':()}))

    def test_close_preserves_monotonic_instance_without_touching_other_factions(self):
        m = self.live(); m.make_foreign_faction(4, [5]); faction = m.c[5]['faction']
        m.run('eon_edu_close'); self.assertNotIn('EDU', m.gf)
        self.assertEqual(m.g['eon_edu_instance'], 1); self.assertEqual(m.c[5]['faction'], faction)

    def test_stale_informational_events_have_no_accept_option(self):
        m = Model()
        for key, op, body in m.events_source:
            if key == 'country_event':
                for option in [n[2] for n in body if n[0] == 'option']:
                    self.assertFalse(any(k in ('eon_edu_accept_request_effect', 'add_to_faction') for k,o,v in walk(option)))

    def test_source_forbids_permission_bypass_and_bulk_nato_mutation(self):
        m = Model(); nodes = [n for b in m.effects.values() for n in walk(b)]
        self.assertFalse(any(k in ('allowdiplo','ai_accept','remove_ideas','set_rule') for k,o,v in nodes))
        for name,body in m.effects.items():
            if name not in ('eon_edu_depart_eu','eon_edu_dissolve_confirmed_union'):
                self.assertFalse(any(k in ('remove_from_faction','dismantle_faction') for k,o,v in walk(body)))
        self.assertFalse(any(k == 'has_rule' and v == 'can_create_factions' for b in m.triggers.values() for k,o,v in walk(b)))
        for k,o,v in nodes:
            if k == 'set_country_flag' and isinstance(v,list) and any(n[0]=='days' for n in v): self.assertEqual(one(v,'value'),'1')

    def test_ai_request_accept_or_refuse_weights_are_political_and_mutually_exclusive(self):
        m = self.live(); m.decision('eon_edu_request_join', 2, 1)
        self.assertGreater(m.ai_weight('eon_edu_accept_request', 1, 2), 0)
        self.assertEqual(m.ai_weight('eon_edu_reject_request', 1, 2), 0)
        m.c[1]['opinions'] = {2:-20}
        self.assertEqual(m.ai_weight('eon_edu_accept_request', 1, 2), 0)
        self.assertGreater(m.ai_weight('eon_edu_reject_request', 1, 2), 0)
        m.c[3]['opinions'] = {1:-20}
        self.assertEqual(m.ai_weight('eon_edu_request_join', 3, 1), 0)

    def test_interrupted_constructor_native_hook_can_complete_current_handshake(self):
        m=Model(); m.formation_mode='deferred'; m.begin_interrupted_constructor()
        self.assertIsNotNone(m.c[1]['faction']); self.assertNotIn('EDU',m.gf)
        self.assertEqual(m.c[1]['vars'].get('eon_edu_member_instance',0),0)
        self.assertGreater(m.c[1]['vars']['eon_edu_creation_intent'],0)
        m.deliver_formed()
        self.assertIn('EDU',m.gf); self.assertEqual(m.c[1]['vars']['eon_edu_creation_intent'],0)
        self.assertEqual(len(m.news),1)

    def test_pending_original_destroyed_recreated_before_delayed_callback_cannot_be_blessed(self):
        m=Model(); m.formation_mode='deferred'; m.begin_interrupted_constructor()
        m.leave(1); m.make_foreign_faction(1); m.deliver_formed()
        self.assertNotIn('EDU',m.gf); self.assertEqual(m.c[1]['vars'].get('eon_edu_member_instance',0),0)
        self.assertEqual(len(m.news),0)

    def test_completed_edu_then_unrelated_same_founder_recreation_is_not_blessed(self):
        m=self.live(); m.leave(1); m.make_foreign_faction(1); m.run('eon_edu_on_formed',1)
        self.assertFalse(m.trigger(m.triggers['eon_edu_is_confirmed_member'],{'root':1,'scope':1,'from':None,'prev':()}))
        self.assertEqual(m.c[1]['vars'].get('eon_edu_creation_intent',0),0)
        self.assertEqual(len(m.news),1)

    def test_wrong_actor_callback_does_not_consume_other_creation_intent(self):
        m=Model(); m.formation_mode='deferred'; m.begin_interrupted_constructor()
        m.make_foreign_faction(3); m.run('eon_edu_on_formed',3)
        self.assertNotIn('EDU',m.gf); self.assertGreater(m.c[1]['vars']['eon_edu_creation_intent'],0)
        m.deliver_formed(); self.assertIn('EDU',m.gf)

    def test_missing_callback_intent_expires_and_reservation_is_not_reused(self):
        m=Model(); m.formation_mode='deferred'; m.begin_interrupted_constructor(); reserved=m.g['eon_edu_generation_counter']
        m.expire(1); self.assertNotIn('EDU',m.gf)
        self.assertEqual(m.g['eon_edu_creation_actor'],0); self.assertEqual(m.c[1]['vars']['eon_edu_creation_intent'],0)
        m.leave(1); m.decision('EU_create_EDU'); self.assertGreater(m.g['eon_edu_generation_counter'],reserved)

    def test_creation_serializes_only_pending_formation_not_candidate_admissions(self):
        m=Model(); m.formation_mode='deferred'; m.begin_interrupted_constructor()
        m.c[2]['ideas'].update({'European_Security_Council','EU_foreign_minister'})
        self.assertFalse(m.available('EU_create_EDU',2)); m.decision('EU_create_EDU',2)
        self.assertIsNone(m.c[2]['faction']); m.deliver_formed()
        m.decision('eon_edu_request_join',2,1); m.decision('eon_edu_request_join',3,1)
        self.assertEqual(m.c[2]['vars']['eon_edu_request_instance'],m.g['eon_edu_instance'])
        self.assertEqual(m.c[3]['vars']['eon_edu_request_instance'],m.g['eon_edu_instance'])

    def test_no_leave_hook_pending_recreation_is_an_explicit_native_acceptance_blocker(self):
        m=Model(); m.formation_mode='deferred'; m.begin_interrupted_constructor()
        m.leave(1,hook=False); m.make_foreign_faction(1); m.deliver_formed()
        self.assertIn('EDU',m.gf)
        # A documented positive counterexample, NOT intended game behavior:
        # without the engine's leave cleanup, the public API has no native
        # faction identifier to distinguish this unrelated current faction.
        # Native acceptance must fail if this bypass actually occurs.
        # The same identity boundary applies to a committed return receipt:
        # without a leave callback it cannot identify a new unknown faction.
        m = Model(); m.native_formation_hooks = False; m.decision('EU_create_EDU')
        m.leave(1, hook=False); m.make_foreign_faction(1); m.run('eon_edu_on_formed')
        self.assertIn('EDU', m.gf)
        self.assertEqual(m.c[1]['vars']['eon_edu_constructor_confirmed_instance'], 1)

    def test_localisation_all_new_implicit_and_explicit_keys_have_en_ru_text(self):
        import re
        m = Model(); needed = set()
        for key,o,body in m.decisions:
            needed.update((key, key+'_desc'))
        for nodes in (*m.triggers.values(), m.events_source):
            for key,o,body in walk(nodes):
                if key in ('tooltip','title','desc','name') and isinstance(body,str): needed.add(body)
        for locale in ('english','russian'):
            p = HERE / f'localisation/{locale}/eon_edu_l_{locale}.yml'
            raw = p.read_bytes(); self.assertTrue(raw.startswith(b'\xef\xbb\xbf'))
            text = raw.decode('utf-8-sig'); self.assertTrue(text.startswith('l_'+locale+':'))
            keys = re.findall(r'^ ([A-Za-z0-9_.]+):(?:\d+)?\s+"(.+)"\r?$', text, re.M)
            self.assertEqual(len(keys), len(dict(keys)), 'duplicate localization keys')
            self.assertFalse(needed - dict(keys).keys(), (locale, needed - dict(keys).keys()))

    def test_negative_source_mutants_expose_pair_clock_instance_and_national_bypasses(self):
        for mutant in ('pair', 'clock', 'instance', 'national'):
            control = self.live(); control.decision('eon_edu_request_join', 2, 1)
            broken = deepcopy(control)
            if mutant == 'pair':
                control.c[2]['vars']['eon_edu_request_leader'] = 3
                broken.c[2]['vars']['eon_edu_request_leader'] = 3
                nodes = broken.triggers['eon_edu_reply_pair_live']
                nodes[1] = ('FROM','=',[n for n in nodes[1][2] if n[0] != 'check_variable'])
            elif mutant == 'clock':
                control.day = broken.day = 42
                broken.triggers['eon_edu_request_active'] = [n for n in broken.triggers['eon_edu_request_active'] if n[0] != 'has_country_flag']
            elif mutant == 'instance':
                for m in (control, broken):
                    m.g['eon_edu_instance'] = 2; m.c[1]['vars']['eon_edu_member_instance'] = 2
                broken.triggers['eon_edu_request_active'] = [n for n in broken.triggers['eon_edu_request_active'] if not (n[0] == 'check_variable' and any(p[0]=='var' for p in n[2]))]
            elif mutant == 'national':
                control.c[2]['join'] = broken.c[2]['join'] = False
                node = broken.triggers['eon_edu_accept_available'][0]
                broken.triggers['eon_edu_accept_available'] = [(node[0],node[1],[n for n in node[2] if n[0] != 'FROM'])]
            with self.subTest(mutant=mutant):
                control.decision('eon_edu_accept_request',1,2); self.assertFalse(control.same(1,2))
                broken.decision('eon_edu_accept_request',1,2); self.assertTrue(broken.same(1,2))

    def test_additional_native_gates_cannot_fall_through_for_inactive_edu_leader(self):
        m = self.live()
        source = {k:v for k,o,v in ast((HERE/'common/scripted_triggers/00_game_rule_triggers.txt').read_text(encoding='utf-8-sig'))}
        gates = {}
        for ident in ('DIPLOMACY_JOIN_FACTION_ENABLE_TRIGGER','DIPLOMACY_OFFER_JOIN_FACTION_ENABLE_TRIGGER'):
            clauses = [n for n in source[ident] if n[0]=='if' and any(k=='eon_edu_is_confirmed_member' for k,o,v in walk(n[2]))]
            self.assertEqual(len(clauses),1)
            gates[ident] = clauses
        self.assertEqual(set(gates), {'DIPLOMACY_JOIN_FACTION_ENABLE_TRIGGER','DIPLOMACY_OFFER_JOIN_FACTION_ENABLE_TRIGGER'})
        join = {'root':2,'scope':2,'from':1,'prev':()}
        offer = {'root':1,'scope':1,'from':2,'prev':()}
        self.assertTrue(m.trigger(gates['DIPLOMACY_JOIN_FACTION_ENABLE_TRIGGER'],join))
        self.assertTrue(m.trigger(gates['DIPLOMACY_OFFER_JOIN_FACTION_ENABLE_TRIGGER'],offer))
        m.c[1]['active'] = False
        self.assertFalse(m.trigger(gates['DIPLOMACY_JOIN_FACTION_ENABLE_TRIGGER'],join))
        self.assertFalse(m.trigger(gates['DIPLOMACY_OFFER_JOIN_FACTION_ENABLE_TRIGGER'],offer))
        m.c[1]['active'] = True; m.c[2]['join'] = False
        self.assertFalse(m.trigger(gates['DIPLOMACY_JOIN_FACTION_ENABLE_TRIGGER'],join))
        self.assertFalse(m.trigger(gates['DIPLOMACY_OFFER_JOIN_FACTION_ENABLE_TRIGGER'],offer))

    def test_simulated_native_join_hook_closes_matching_request_once(self):
        m = self.live(); m.decision('eon_edu_request_join',2,1)
        m.c[2]['faction'] = m.c[1]['faction']
        m.run('eon_edu_on_join',2,1)
        self.assertEqual(m.c[2]['vars']['eon_edu_request_result'],1)
        self.assertEqual(m.c[2]['vars']['eon_edu_request_instance'],0)
        notifications = [e for e in m.events if e==(2,'eon_edu.2')]
        self.assertEqual(len(notifications),1)
        m.run('eon_edu_on_offer_join',1,2)
        self.assertEqual(len([e for e in m.events if e==(2,'eon_edu.2')]),1)

    def test_simulated_offer_hook_and_scripted_commit_do_not_duplicate_acceptance(self):
        m = self.live(); m.decision('eon_edu_request_join',2,1)
        m.c[2]['faction'] = m.c[1]['faction']
        m.run('eon_edu_on_offer_join',1,2)
        m.run('eon_edu_commit_actual_join',2)
        self.assertEqual(len([e for e in m.events if e==(2,'eon_edu.2')]),1)

    def return_confirmed_pair(self):
        m = Model(); m.native_formation_hooks = False; m.decision('EU_create_EDU')
        m.decision('eon_edu_request_join', 2, 1); m.decision('eon_edu_accept_request', 1, 2)
        m.native_leave_hooks = False; m.native_leadership_hooks = False
        m.make_foreign_faction(4, [5])
        return m

    def test_both_departure_routes_use_actual_leader_and_prev_with_foreign_root(self):
        for departing in (1, 2):
            m = self.return_confirmed_pair()
            unrelated = deepcopy((m.c[4], m.c[5], m.factions[m.c[5]['faction']]))
            m.c[departing]['ideas'].discard('EU_member'); m.c[departing]['active'] = False
            frame = {'root':5, 'scope':departing, 'from':4, 'prev':(5,)}
            m.effect(m.effects['eon_edu_depart_eu'], frame)
            with self.subTest(departing=departing):
                remaining = 3 - departing
                self.assertIsNone(m.c[departing]['faction'])
                self.assertEqual(m.leader(remaining), remaining)
                self.assertEqual(m.c[departing]['vars']['eon_edu_departure_result'], 1)
                self.assertEqual(m.c[departing]['vars']['eon_edu_member_instance'], 0)
                self.assertEqual(m.c[departing]['vars']['eon_edu_constructor_confirmed_instance'], 0)
                self.assertEqual([b for b in m.boundaries if isinstance(b, tuple) and b[0] == 'native_remove_unproved'],
                                 [('native_remove_unproved', remaining, departing)])
                self.assertEqual((m.c[4], m.c[5], m.factions[m.c[5]['faction']]), unrelated)
                self.assertEqual(m.c[departing]['vars'].get('eon_edu_leave_hook_serial', 0), 0)

    def test_failed_leader_scoped_remove_keeps_receipts_then_retry_cleans_both_routes(self):
        for departing in (1, 2):
            m = self.return_confirmed_pair()
            receipts = tuple(m.c[departing]['vars'].get(k, 0) for k in
                             ('eon_edu_member_instance', 'eon_edu_constructor_confirmed_instance'))
            m.c[departing]['remove_fail'] = True
            frame = {'root':5, 'scope':departing, 'from':4, 'prev':(5,)}
            m.effect(m.effects['eon_edu_depart_eu'], frame)
            with self.subTest(departing=departing):
                self.assertTrue(m.same(1, 2))
                self.assertEqual(m.c[departing]['vars']['eon_edu_departure_result'], 2)
                self.assertEqual(tuple(m.c[departing]['vars'].get(k, 0) for k in
                                       ('eon_edu_member_instance', 'eon_edu_constructor_confirmed_instance')), receipts)
                self.assertEqual(m.events.count((departing, 'eon_edu.8')), 1)
                m.c[departing]['remove_fail'] = False
                m.effect(m.effects['eon_edu_depart_eu'], frame)
                self.assertIsNone(m.c[departing]['faction'])
                self.assertEqual(m.c[departing]['vars']['eon_edu_departure_result'], 1)
                self.assertEqual(m.c[departing]['vars']['eon_edu_member_instance'], 0)
                self.assertEqual(m.c[departing]['vars']['eon_edu_constructor_confirmed_instance'], 0)
                self.assertEqual(m.c[departing]['vars'].get('eon_edu_leave_hook_serial', 0), 0)

    def test_actual_removal_guards_reject_wrong_cohort_and_foreign_faction(self):
        source = Model().effects['eon_edu_depart_eu']
        removals = [body for key, op, body in walk(source)
                    if key == 'faction_leader' and any(k == 'remove_from_faction' for k, o, v in walk(body))]
        self.assertEqual(len(removals), 2)
        def without_confirmation(nodes):
            return [(k, o, without_confirmation(v) if isinstance(v, list) else v)
                    for k, o, v in nodes if k != 'eon_edu_is_confirmed_member']
        for route, block in enumerate(removals):
            for case in ('wrong_cohort', 'foreign_faction'):
                m = self.return_confirmed_pair()
                if case == 'wrong_cohort': m.c[1]['vars']['eon_edu_member_instance'] = 2
                else: m.c[2]['faction'] = m.c[4]['faction']
                frame = {'root':5, 'scope':2, 'from':4, 'prev':(5,)}
                snapshot = deepcopy((m.c, m.factions, m.g, m.gf))
                broken = deepcopy(m)
                with self.subTest(route=route, case=case):
                    m.effect(source, frame)
                    self.assertEqual((m.c, m.factions, m.g, m.gf), snapshot)
                    # Invoke the exact source dispatch block separately to expose
                    # its own cohort guard, rather than only the outer entry gate.
                    m.effect([('faction_leader', '=', block)], frame)
                    self.assertEqual((m.c, m.factions, m.g, m.gf), snapshot)
                    broken.effect([('faction_leader', '=', without_confirmation(block))], frame)
                    self.assertIsNone(broken.c[2]['faction'])
        # The model policy itself refuses nonleaders and cross-faction targets.
        m = self.return_confirmed_pair(); snapshot = deepcopy((m.c, m.factions))
        m.effect([('remove_from_faction', '=', 'THIS')], {'root':5,'scope':2,'from':4,'prev':(5,)})
        m.effect([('remove_from_faction', '=', 'FROM')], {'root':5,'scope':1,'from':4,'prev':(5,)})
        self.assertEqual((m.c, m.factions), snapshot)

    def test_depart_nonleader_leaves_edu_but_preserves_leader_and_nato(self):
        m=self.live(); m.decision('eon_edu_request_join',2,1); m.decision('eon_edu_accept_request',1,2)
        m.make_foreign_faction(4,[5]); foreign=m.c[5]['faction']
        m.c[2]['ideas'].discard('EU_member'); m.c[2]['active']=False
        m.run('eon_edu_depart_eu',2)
        self.assertIsNone(m.c[2]['faction']); self.assertEqual(m.leader(1),1)
        self.assertEqual(m.c[5]['faction'],foreign); self.assertEqual(m.leader(4),4)

    def test_depart_leader_transfers_to_actual_active_member_before_leaving(self):
        m=self.live(); m.decision('eon_edu_request_join',2,1); m.decision('eon_edu_accept_request',1,2)
        m.c[1]['ideas'].discard('EU_member'); m.c[1]['active']=False
        m.run('eon_edu_depart_eu',1)
        self.assertIsNone(m.c[1]['faction']); self.assertEqual(m.leader(2),2)
        self.assertTrue(m.trigger(m.triggers['eon_edu_is_confirmed_member'],{'root':2,'scope':2,'from':None,'prev':()}))

    def test_depart_last_confirmed_leader_dismantles_actual_edu(self):
        m=self.live(); m.run('eon_edu_depart_eu',1)
        self.assertIsNone(m.c[1]['faction']); self.assertNotIn('EDU',m.gf)

    def test_depart_failed_transfer_does_not_blindly_dismantle_or_leave(self):
        m=self.live(); m.decision('eon_edu_request_join',2,1); m.decision('eon_edu_accept_request',1,2)
        m.c[2]['transfer_fail']=True; m.run('eon_edu_depart_eu',1)
        self.assertTrue(m.same(1,2)); self.assertEqual(m.leader(1),1)
        self.assertEqual(m.c[1]['vars']['eon_edu_departure_result'],2)

    def test_dissolve_actual_edu_before_receipt_clear_preserves_unrelated_faction(self):
        m=self.live(); m.decision('eon_edu_request_join',2,1); m.decision('eon_edu_accept_request',1,2)
        m.make_foreign_faction(4,[5]); foreign=m.c[5]['faction']
        m.run('eon_edu_dissolve_confirmed_union')
        self.assertIsNone(m.c[1]['faction']); self.assertIsNone(m.c[2]['faction'])
        self.assertNotIn('EDU',m.gf); self.assertEqual(m.c[5]['faction'],foreign)

    def test_depart_uses_current_country_when_called_from_foreign_root(self):
        m=self.live(); m.decision('eon_edu_request_join',2,1); m.decision('eon_edu_accept_request',1,2)
        m.effect(m.effects['eon_edu_depart_eu'],{'root':5,'scope':1,'from':None,'prev':(5,)})
        self.assertIsNone(m.c[1]['faction']); self.assertEqual(m.leader(2),2); self.assertIsNone(m.c[5]['faction'])

    def test_failed_native_departure_is_observable_once_and_retries_formal_exit(self):
        for member in (1,2):
            with self.subTest(member=member):
                m=self.live(); m.decision('eon_edu_request_join',2,1); m.decision('eon_edu_accept_request',1,2)
                m.c[member]['ideas'].discard('EU_member'); m.c[member]['active']=False
                m.c[member]['remove_fail']=True
                m.run('eon_edu_depart_eu',member); m.run('eon_edu_depart_eu',member)
                self.assertTrue(m.same(1,2)); self.assertIn('EDU',m.gf)
                self.assertEqual(m.c[member]['vars']['eon_edu_departure_result'],2)
                self.assertEqual(m.events.count((member,'eon_edu.8')),1)
                m.c[member]['remove_fail']=False; m.run('eon_edu_daily_pulse')
                self.assertIsNone(m.c[member]['faction'])
                self.assertEqual(m.c[member]['vars']['eon_edu_departure_result'],1)

    def test_failed_last_leader_dismantle_preserves_receipt_until_success(self):
        m=self.live(); m.c[1]['dismantle_fail']=True
        m.run('eon_edu_depart_eu'); m.run('eon_edu_depart_eu')
        self.assertIn('EDU',m.gf); self.assertEqual(m.c[1]['vars']['eon_edu_departure_result'],2)
        self.assertEqual(m.events.count((1,'eon_edu.8')),1)
        m.c[1]['ideas'].discard('EU_member'); m.c[1]['active']=False
        m.c[1]['dismantle_fail']=False; m.run('eon_edu_daily_pulse')
        self.assertNotIn('EDU',m.gf); self.assertIsNone(m.c[1]['faction'])

    def test_full_union_archive_retries_failed_actual_dismantle(self):
        m=self.live(); m.c[1]['dismantle_fail']=True; m.union_active=False
        m.run('eon_edu_daily_pulse'); self.assertIn('EDU',m.gf)
        m.c[1]['dismantle_fail']=False; m.run('eon_edu_daily_pulse')
        self.assertNotIn('EDU',m.gf); self.assertIsNone(m.c[1]['faction'])

    def test_subject_pause_while_union_exists_preserves_actual_cohort(self):
        m=self.live(); m.c[1]['subject']=True; m.c[1]['active']=False
        m.run('eon_edu_daily_pulse')
        self.assertIn('EDU',m.gf); self.assertEqual(m.leader(1),1)
        self.assertTrue(m.trigger(m.triggers['eon_edu_is_confirmed_member'],{'root':1,'scope':1,'from':None,'prev':()}))

    def test_adopt_only_unique_actual_edu_template_without_creation_news(self):
        m=Model(); m.make_foreign_faction(1,[2]); fid=m.c[1]['faction']
        m.factions[fid]['template']='faction_template_edu'
        m.run('eon_edu_adopt_legacy_template',5)
        self.assertIn('EDU',m.gf); self.assertEqual(len(m.news),0)
        self.assertGreater(m.c[1]['vars']['eon_edu_legacy_adoption_serial'],0)
        self.assertEqual(m.c[2]['vars']['eon_edu_member_instance'],m.g['eon_edu_instance'])

    def test_legacy_adoption_cannot_guess_unknown_or_multiple_factions(self):
        for kind in ('unknown','nato','multiple'):
            with self.subTest(kind=kind):
                m=Model(); m.make_foreign_faction(1,[2]); first=m.c[1]['faction']
                if kind=='nato': m.factions[first]['template']='faction_template_nato'
                if kind=='multiple':
                    m.factions[first]['template']='faction_template_edu'
                    m.make_foreign_faction(3,[4]); m.factions[m.c[3]['faction']]['template']='faction_template_edu'
                m.gf.add('EDU'); m.run('eon_edu_adopt_legacy_template')
                self.assertEqual(m.g.get('eon_edu_instance',0),0)
                self.assertEqual(m.c[1]['faction'],first)
                self.assertEqual(m.c[1]['vars'].get('eon_edu_member_instance',0),0)

    def test_legacy_adoption_never_rebinds_current_cohort(self):
        m=self.live(); serial=m.g['eon_edu_instance']; m.make_foreign_faction(3,[4])
        m.factions[m.c[3]['faction']]['template']='faction_template_edu'
        m.run('eon_edu_adopt_legacy_template'); self.assertEqual(m.g['eon_edu_instance'],serial)
        self.assertEqual(m.c[3]['vars'].get('eon_edu_member_instance',0),0)

    def test_legacy_adoption_does_not_bypass_pending_formation_handshake(self):
        m=Model(); m.formation_mode='deferred'; m.begin_interrupted_constructor()
        m.factions[m.c[1]['faction']]['template']='faction_template_edu'
        m.run('eon_edu_adopt_legacy_template')
        self.assertNotIn('EDU',m.gf); self.assertEqual(len(m.news),0)
        m.deliver_formed(); self.assertIn('EDU',m.gf); self.assertEqual(len(m.news),1)

    def test_actual_shared_seams_preserve_identity_until_native_mutation(self):
        import sys
        sys.path.insert(0,str(HERE/'tools/validation/diplomacy_package_02'))
        from _treaty_support import ast as full_ast
        legacy={k:v for k,o,v in full_ast((HERE/'common/scripted_effects/00_eu_scripted_effects.txt').read_text('utf-8-sig'))}
        life={k:v for k,o,v in full_ast((HERE/'common/scripted_effects/eon_eu_lifecycle_effects.txt').read_text('utf-8-sig'))}
        leaving=list(walk(legacy['leaving_EU']))
        depart=[i for i,n in enumerate(leaving) if n[0]=='eon_edu_depart_eu']
        self.assertEqual(len(depart),1)
        self.assertFalse(any(k=='clear_variable' and v=='eon_edu_member_instance' for k,o,v in leaving[:depart[0]]))
        self.assertFalse(any(k=='clr_global_flag' and v=='EDU' for k,o,v in leaving))
        # Legal EU removal can precede military departure: the identity trigger
        # deliberately depends on the actual cohort, not EU ideas/registry.
        member_trigger=Model().triggers['eon_edu_is_confirmed_member']
        self.assertFalse(any(k in ('has_idea','eon_eu_is_active_member') for k,o,v in walk(member_trigger)))
        reset=life['eon_eu_reset_institutional_laws']
        # The legislative handoff archive is intentionally before military
        # dissolution. It invalidates old approval receipts without touching
        # the confirmed EDU identity required by the native cleanup helper.
        self.assertEqual(reset[:2], [
            ('eon_eu_handoff_archive', '=', 'yes'),
            ('eon_edu_dissolve_confirmed_union', '=', 'yes'),
        ])
        self.assertEqual(sum(k == 'eon_edu_dissolve_confirmed_union'
                             for k, o, v in reset), 1)
        handoff = {k: v for k, o, v in full_ast(
            (HERE / 'common/scripted_effects/eon_eu_handoff_effects.txt').read_text('utf-8-sig'))}
        m = self.live()
        m.decision('eon_edu_request_join', 2, 1)
        m.decision('eon_edu_accept_request', 1, 2)
        m.make_foreign_faction(4, [5])
        foreign = m.c[5]['faction']
        for helper in ('eon_eu_handoff_archive', 'eon_eu_handoff_initialize'):
            m.effects[helper] = handoff[helper]
        m.g.update(eon_eu_approval_epoch=3, eon_eu_handoff_101_status=2)
        def identity():
            return deepcopy((m.c, m.gf, m.factions, m.news, m.events,
                             m.logs, m.temp, {k: v for k, v in m.g.items()
                                            if k.startswith('eon_edu_')}))
        before_archive = identity()
        m.run('eon_eu_handoff_archive')
        self.assertEqual(m.g['eon_eu_approval_epoch'], 4)
        self.assertEqual(m.g['eon_eu_handoff_101_status'], 0)
        self.assertEqual(identity(), before_archive)
        m.run('eon_edu_dissolve_confirmed_union')
        self.assertIsNone(m.c[1]['faction'])
        self.assertIsNone(m.c[2]['faction'])
        self.assertNotIn('EDU', m.gf)
        self.assertEqual(m.c[5]['faction'], foreign)
        self.assertFalse(any(k=='clr_global_flag' and v=='EDU' for k,o,v in walk(reset)))
        daily=life['eon_eu_daily_lifecycle_pulse']
        self.assertEqual(daily[0][0],'eon_eu_close_historical_admission')
        lock=next(v for k,o,v in daily if k=='if')
        keys=[k for k,o,v in lock]
        self.assertIn('eon_edu_daily_pulse',keys)
        self.assertLess(max(i for i,k in enumerate(keys) if k=='eon_eu_refresh_membership'),keys.index('eon_edu_daily_pulse'))
        # The retry is a direct coordinator child; an active-union condition
        # cannot make dormant archive native failures permanently unreachable.
        self.assertTrue(any(k=='eon_edu_daily_pulse' and v=='yes' for k,o,v in lock))


if __name__ == '__main__': unittest.main(verbosity=2)
