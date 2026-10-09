"""Bounded source lifecycle; no real popup consumption or native clock claim."""
from copy import deepcopy
import unittest

import _support as s


class ConsultationLifecycle(unittest.TestCase):
    overrides = None

    @classmethod
    def setUpClass(cls):
        cls.e = s.executor(cls.overrides)

    def assert_released(self, state, actor='A', peer='B'):
        for tag in (actor, peer):
            c = state['countries'][tag]
            self.assertNotIn('eon_consultation_reserved', c['flags'])
            self.assertNotIn('eon_consultation_expired', c['flags'])
            self.assertNotIn('eon_consultation_partner', c['variables'])
            self.assertNotIn('eon_consultation_topic', c['variables'])

    def assert_retained(self, state, roles, topic, actor='A', peer='B'):
        for tag, partner, role in ((actor, peer, roles[0]), (peer, actor, roles[1])):
            c = state['countries'][tag]
            self.assertIn('eon_consultation_reserved', c['flags'])
            self.assertIn('eon_consultation_expired', c['flags'])
            self.assertIn('eon_consultation_' + role, c['flags'])
            self.assertNotIn(s.flag('eon_consultation_retired_pair', partner), c['flags'])
            self.assertEqual(c['variables']['eon_consultation_partner'], partner)
            self.assertEqual(c['variables']['eon_consultation_topic'], topic)

    def test_native_flag_literal_scalar_and_scope_are_distinct(self):
        e = self.e; state = e['state'](); c = e['context']('A', 'B')
        state['temp']['probe_peer'] = 'B'
        proper = e['native_flag_name'](state, c, 'probe@FROM')
        self.assertEqual(proper, s.flag('probe', 'B'))
        self.assertNotEqual(proper, e['native_flag_name'](state, c, 'probe@B'))
        self.assertEqual(e['native_flag_name'](state, c, 'probe@probe_peer'), 'probe@probe_peer')
        state['countries']['A']['flags'].add(proper)
        self.assertTrue(e['check'](state, e['ast']('has_country_flag = probe@FROM'), c))
        self.assertFalse(e['check'](state, e['ast']('has_country_flag = probe@probe_peer'), c))
        e['effect'](state, e['ast']('clr_country_flag = probe@probe_peer'), c)
        self.assertIn(proper, state['countries']['A']['flags'])
        e['effect'](state, e['ast']('clr_country_flag = probe@FROM'), c)
        self.assertNotIn(proper, state['countries']['A']['flags'])

    def test_retired_gate_checks_each_actual_direction_and_ignores_wrong_pair(self):
        for owner, peer in (('A', 'B'), ('B', 'A')):
            with self.subTest(owner=owner):
                state = self.e['state']()
                state['countries'][owner]['flags'].add(s.flag('eon_consultation_retired_pair', peer))
                before = s.preserved(state)
                self.assertFalse(self.e['action'](state, 'eon_open_economic_consultations'))
                self.e['action'](state, 'eon_open_economic_consultations', force=True)
                self.assertEqual(s.preserved(state), before)
        state = self.e['state']()
        state['countries']['B']['flags'].add(s.flag('eon_consultation_retired_pair', 'C'))
        self.assertTrue(self.e['action'](state, 'eon_open_economic_consultations'))

    def test_draft_expiry_keeps_original_reservation_until_cancel_or_stale_send(self):
        for option in ('eon_consultation_cancel_agenda', 'eon_consultation_topic_trade'):
            with self.subTest(option=option):
                state = s.draft(self.e); before = s.resources(state)
                pp = self.e['pp'](state)
                s.expire(self.e, state, 'draft')
                self.assert_retained(state, ('draft_owner', 'draft_recipient'), 0)
                self.assertFalse(self.e['action'](state, 'eon_open_economic_consultations'))
                self.assertEqual(self.e['pp'](state), pp)
                self.assertEqual(s.resources(state), before)
                again = deepcopy({key: value for key, value in state.items() if key != 'temp'})
                s.helper(self.e, state, 'daily_cleanup')
                self.assertEqual({key: value for key, value in state.items() if key != 'temp'}, again)
                event = self.e['queued'](state, 'eon_consultation.1', 'A', 'B')
                state['events'].remove(event)
                self.e['option_effect'](state, 'eon_consultation.1', option, 'A', 'B', force=True)
                self.assert_released(state)
                self.assertEqual(self.e['pp'](state), pp)
                self.assertEqual(s.resources(state), before)
                self.assertTrue(self.e['action'](state, 'eon_open_economic_consultations'))

    def test_expired_request_consumes_original_reply_without_agreement_or_extra_pp(self):
        for topic in (1, 2, 3):
            for choice in ('accept', 'refuse'):
                with self.subTest(topic=topic, choice=choice):
                    state = s.request(self.e, topic); before = s.resources(state)
                    self.assertEqual(self.e['pp'](state)['A'], 30)
                    s.expire(self.e, state, 'request')
                    self.assert_retained(state, ('outgoing', 'incoming'), topic)
                    for name in ('eon_open_economic_consultations', 'eon_withdraw_consultation_request'):
                        self.assertFalse(self.e['action'](state, name))
                    s.consume_reply(self.e, state, topic, choice)
                    self.assert_released(state)
                    self.assertEqual(s.resources(state), before)
                    self.assertEqual(self.e['pp'](state)['A'], 30)
                    self.assertTrue(any(ev['id'] == 'eon_consultation.26' for ev in state['events']))
                    self.assertFalse(any(ev['id'] in ('eon_consultation.20', 'eon_consultation.21', 'eon_consultation.22') for ev in state['events']))
                    self.assertFalse(self.e['action'](state, 'eon_open_economic_consultations'))
                    s.clear_recent(state)
                    self.assertTrue(self.e['action'](state, 'eon_open_economic_consultations'))

    def test_expiry_markers_fail_closed_even_if_time_windows_restored(self):
        for stage in ('draft', 'request'):
            for expired_side in ('A', 'B'):
                with self.subTest(stage=stage, side=expired_side):
                    state = s.draft(self.e) if stage == 'draft' else s.request(self.e)
                    state['countries'][expired_side]['flags'].add('eon_consultation_expired')
                    if stage == 'draft':
                        self.assertFalse(s.predicate(self.e, state, 'draft_send_ready', temps={'eon_consultation_proposed_topic': 1}))
                    else:
                        self.assertFalse(s.predicate(self.e, state, 'response_valid', 'B', 'A', temps={'eon_consultation_response_topic': 1}))
                        self.assertFalse(self.e['action'](state, 'eon_withdraw_consultation_request'))
                        s.consume_reply(self.e, state)
                        self.assert_released(state)

    def test_wrong_peer_or_topic_cannot_consume_reserved_expired_modal(self):
        for peer, topic in (('C', 1), ('A', 2)):
            with self.subTest(peer=peer, topic=topic):
                state = s.request(self.e); s.expire(self.e, state, 'request')
                before = s.preserved(state)
                s.helper(self.e, state, 'accept_request', 'B', peer, {'eon_consultation_response_topic': topic})
                s.helper(self.e, state, 'refuse_request', 'B', peer, {'eon_consultation_response_topic': topic})
                s.helper(self.e, state, 'resolve_invalid_request', 'B', peer, {'eon_consultation_response_topic': topic})
                self.assertEqual(s.preserved(state), before)

    def test_withdraw_and_expired_reason_are_distinct_and_repeat_callbacks_inert(self):
        for expired in (False, True):
            with self.subTest(expired=expired):
                state = s.request(self.e)
                self.assertTrue(self.e['action'](state, 'eon_withdraw_consultation_request'))
                if expired:
                    s.expire(self.e, state, 'request')
                state['events'] = [ev for ev in state['events'] if ev['id'] != 'eon_consultation.24']
                s.consume_reply(self.e, state)
                self.assert_released(state)
                self.assertTrue(any(ev['id'] == ('eon_consultation.26' if expired else 'eon_consultation.24') for ev in state['events']))
                before = s.preserved(state)
                notices = deepcopy(state['events'])
                s.helper(self.e, state, 'accept_request', 'B', 'A', {'eon_consultation_response_topic': 1})
                s.helper(self.e, state, 'refuse_request', 'B', 'A', {'eon_consultation_response_topic': 1})
                self.assertEqual(s.preserved(state), before)
                self.assertEqual(state['events'], notices)

    def test_dead_corrupt_and_annex_records_keep_exact_pair_retirement(self):
        for defect in ('dead', 'wrong_reverse', 'annexed'):
            with self.subTest(defect=defect):
                state = s.request(self.e); before = s.resources(state)
                if defect == 'dead':
                    state['countries']['B']['exists'] = False
                    s.helper(self.e, state, 'daily_cleanup')
                elif defect == 'wrong_reverse':
                    state['countries']['B']['variables']['eon_consultation_partner'] = 'C'
                    s.helper(self.e, state, 'daily_cleanup')
                else:
                    s.helper(self.e, state, 'cleanup_annexed_pair', temps={'eon_consultation_annexed_partner': 'B'})
                self.assertNotIn('eon_consultation_reserved', state['countries']['A']['flags'])
                self.assertIn(s.flag('eon_consultation_retired_pair', 'B'), state['countries']['A']['flags'])
                self.assertIn(s.flag('eon_consultation_retired_pair', 'A'), state['countries']['B']['flags'])
                self.assertEqual(s.resources(state), before)

    def test_active_close_war_and_time_expiry_preserve_separate_contracts(self):
        for ending in ('end', 'war', 'time'):
            with self.subTest(ending=ending):
                state = s.request(self.e, 2); s.consume_reply(self.e, state, 2)
                before = s.resources(state)
                if ending == 'end':
                    self.assertTrue(self.e['action'](state, 'eon_end_economic_consultations'))
                else:
                    if ending == 'war':
                        state['countries']['A']['wars'].add('B')
                        before = s.resources(state)
                    else:
                        state['countries']['A']['flags'].discard('eon_consultation_active_window')
                    s.helper(self.e, state, 'daily_cleanup')
                self.assert_released(state)
                self.assertEqual(s.resources(state), before)
                self.assertNotIn(s.flag('eon_consultation_retired_pair', 'B'), state['countries']['A']['flags'])

    def test_expiry_draft_and_reply_helpers_are_exact_and_daily_bilateral(self):
        for stage in ('draft', 'request'):
            for owner, peer in (('A', 'B'), ('B', 'A')):
                with self.subTest(stage=stage, owner=owner):
                    state = s.draft(self.e) if stage == 'draft' else s.request(self.e)
                    window = 'eon_consultation_' + ('draft_window' if stage == 'draft' else 'response_window')
                    state['countries'][owner]['flags'].discard(window)
                    s.helper(self.e, state, 'daily_cleanup', owner, peer)
                    self.assert_retained(state, ('draft_owner', 'draft_recipient') if stage == 'draft' else ('outgoing', 'incoming'), 0 if stage == 'draft' else 1)
                    name = 'expired_draft_current' if stage == 'draft' else 'expired_response_current'
                    actor, partner = ('A', 'B') if stage == 'draft' else ('B', 'A')
                    temps = {} if stage == 'draft' else {'eon_consultation_response_topic': 1}
                    self.assertTrue(s.predicate(self.e, state, name, actor, partner, temps=temps))
                    self.assertFalse(s.predicate(self.e, state, name, actor, 'C', temps=temps))

    def test_force_withdraw_expired_and_end_pending_do_not_release_original(self):
        for operation in ('withdraw_request', 'end_active'):
            with self.subTest(operation=operation):
                state = s.request(self.e); s.expire(self.e, state, 'request')
                before, notices = s.preserved(state), deepcopy(state['events'])
                s.helper(self.e, state, operation)
                self.assertEqual(s.preserved(state), before)
                self.assertEqual(state['events'], notices)

    def test_execution_temps_are_shared_and_scoped_reads_are_persistent(self):
        state = self.e['state'](); state['temp']['probe'] = 81
        c = self.e['context']('A', 'B', 'B', ('A',))
        self.assertEqual(self.e['value'](state, c, 'probe'), 81)
        self.assertEqual(self.e['value'](state, c, 'PREV.probe'), 0)
        state['countries']['A']['variables']['probe'] = 17
        self.assertEqual(self.e['value'](state, c, 'PREV.probe'), 17)
        self.assertEqual(self.e['value'](state, c, 'probe'), 81)

    def test_unknown_core_effect_or_trigger_is_rejected(self):
        for mode in ('check', 'effect'):
            with self.subTest(mode=mode):
                with self.assertRaises(AssertionError):
                    self.e[mode](self.e['state'](), [('eon_consultation_unknown_fixture', '=', 'yes')], self.e['context']('A', 'B'))


if __name__ == '__main__':
    unittest.main()
