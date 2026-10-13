"""Actual candidate AST lifecycle regressions; supplied timer/war facts only."""
from copy import deepcopy
from itertools import product
import unittest
from support import load


class LiveExpiryTests(unittest.TestCase):
    def setUp(self):
        self.t = load()
        self.b = self.t['source']
        self.cases = 0

    def flag(self, result, actor, flag):
        return flag in result['countries'][actor]['flags']

    def triad(self, result, prefix, reserved):
        return [self.flag(result, a, prefix + reserved) for a in ('A', 'B', 'C')]

    def no_retired(self, result):
        self.assertFalse(any('retired_pair@' in f for d in result['countries'].values() for f in d['flags']))

    def terms_snapshot(self, result):
        return {a: {'variables': {k: deepcopy(v) for k, v in d['variables'].items() if k.startswith('eon_mediation_terms_')},
                    'flags': {f for f in d['flags'] if f.startswith('eon_mediation_terms_')}}
                for a, d in result['countries'].items()}

    def expire_terms(self, result, actor='A'):
        result['countries'][actor]['flags'].discard('eon_mediation_terms_response_window')
        self.t['native_daily'](result, 'C')

    def setup_terms(self, stage=1, topic=2, duration=90):
        result = self.t['active_base']()
        self.t['offer'](result, topic, duration)
        if stage == 2:
            self.assertTrue(self.t['response'](result, topic, duration, 1))
        return result

    def acknowledge_terms(self, result, stage, topic, duration, accept=False):
        # The original queued modal is consumed exactly once. Forced accept is a
        # hostile stale callback, not an enabled GUI button or forced native AI.
        return self.t['response'](result, topic, duration, stage, accept=accept, force=accept)

    def test_base_live_expiry_ack_and_retry(self):
        for stage, topic, actor, accept in product((1, 2), (1, 2), ('A', 'B', 'C'), (False, True)):
            with self.subTest(stage=stage, topic=topic, actor=actor, accept=accept):
                result = self.b['state'](); self.b['request'](result, topic)
                if stage == 2: self.assertTrue(self.b['answer_mediator'](result, topic))
                external, pp = self.b['snapshot_other_state'](result), self.b['pp'](result)
                result['countries'][actor]['flags'].discard('eon_mediation_response_window')
                self.b['native_hook'](result, 'on_daily', 'C')
                self.assertEqual(self.triad(result, 'eon_mediation_', 'reserved'), [True] * 3)
                self.assertEqual(self.triad(result, 'eon_mediation_', 'expired'), [True] * 3)
                self.b['assert_session'](result, stage, topic)
                stable = deepcopy(result)
                for member in ('A', 'B', 'C'): self.b['native_hook'](result, 'on_daily', member)
                # TEMP scratch is not an observable persistent state guarantee.
                stable.pop('temp', None); now = deepcopy(result); now.pop('temp', None)
                self.assertEqual(now, stable)
                event, receiver, sender = ('eon_mediation.' + str((9 if stage == 1 else 19) + topic), 'C' if stage == 1 else 'B', 'A' if stage == 1 else 'C')
                self.assertEqual(self.b['ai_weight'](result, event, 'eon_mediation_accept', receiver, sender), 0)
                self.assertEqual(self.b['ai_weight'](result, event, 'eon_mediation_decline', receiver, sender), 1)
                if stage == 1: self.b['answer_mediator'](result, topic, accept=accept, force=accept)
                else: self.b['answer_opponent'](result, topic, accept=accept, force=accept)
                self.assertEqual(self.triad(result, 'eon_mediation_', 'reserved'), [False] * 3)
                self.assertEqual(sum(e['id'] == 'eon_mediation.37' for e in result['events']), 3)
                settled = deepcopy(result['countries']); events = deepcopy(result['events'])
                self.b['option_effect'](result, event, 'eon_mediation_decline', receiver, sender, force=True)
                self.assertEqual(result['countries'], settled); self.assertEqual(result['events'], events)
                self.no_retired(result)
                self.assertEqual(self.b['snapshot_other_state'](result), external); self.assertEqual(self.b['pp'](result), pp)
                self.b['clear_cooldown'](result); self.b['request'](result, topic)
                self.b['assert_session'](result, 1, topic)

    def test_terms_live_expiry_literals_ack_and_retry(self):
        for stage, topic, duration, actor, accept in product((1, 2), (1, 2), (30, 60, 90), ('A', 'B', 'C'), (False, True)):
            with self.subTest(stage=stage, topic=topic, duration=duration, actor=actor, accept=accept):
                result = self.setup_terms(stage, topic, duration)
                base, windows, external = self.t['snapshot_base'](result), self.t['base_windows'](result), self.t['snapshot_external'](result)
                self.expire_terms(result, actor)
                self.t['assert_terms'](result, stage, topic, duration)
                self.assertEqual(self.triad(result, 'eon_mediation_terms_', 'expired'), [True] * 3)
                stable = deepcopy(result['countries']); event_count = len(result['events'])
                for member in ('A', 'B', 'C'): self.t['native_daily'](result, member)
                self.assertEqual(result['countries'], stable); self.assertEqual(len(result['events']), event_count)
                wrong = 30 if duration != 30 else 90
                receiver, sender = ('C', 'A') if stage == 1 else ('B', 'C')
                self.t['option_effect'](result, self.t['event_id'](topic, wrong, stage), 'eon_mediation_terms_decline', receiver, sender, force=True)
                self.assertEqual(result['countries'], stable)
                self.acknowledge_terms(result, stage, topic, duration, accept)
                self.assertEqual(self.triad(result, 'eon_mediation_terms_', 'reserved'), [False] * 3)
                self.assertEqual(sum(e['id'] == 'eon_mediation_terms.35' for e in result['events']), 3)
                self.assertEqual(self.t['snapshot_base'](result), base); self.assertEqual(self.t['base_windows'](result), windows)
                self.assertEqual(self.t['snapshot_external'](result), external)
                self.no_retired(result)
                self.t['offer'](result, topic, duration)
                self.t['assert_terms'](result, 1, topic, duration)

    def test_old_terms_cannot_apply_or_clear_new_same_triad_base(self):
        for stage, withdrawing, new_topic, accept in product((1, 2), ('A', 'B', 'C'), (1, 2), (False, True)):
            with self.subTest(stage=stage, withdrawing=withdrawing, new_topic=new_topic, accept=accept):
                result = self.setup_terms(stage)
                self.assertTrue(self.b['action'](result, 'eon_withdraw_mediation', withdrawing, 'C' if withdrawing != 'C' else 'A'))
                self.assertEqual(self.triad(result, 'eon_mediation_', 'reserved'), [False] * 3)
                self.assertEqual(self.triad(result, 'eon_mediation_terms_', 'reserved'), [True] * 3)
                self.assertEqual(self.triad(result, 'eon_mediation_terms_', 'expired'), [True] * 3)
                self.b['clear_cooldown'](result); self.t['active_base'](new_topic, result=result)
                base, windows = self.t['snapshot_base'](result), self.t['base_windows'](result)
                self.acknowledge_terms(result, stage, 2, 90, accept)
                self.assertEqual(self.t['snapshot_base'](result), base); self.assertEqual(self.t['base_windows'](result), windows)
                self.assertEqual(self.triad(result, 'eon_mediation_terms_', 'reserved'), [False] * 3)
                self.no_retired(result)
                self.t['offer'](result, 1, 60)

    def test_annex_current_triads_preserves_unrelated_expired_terms(self):
        for stage, hook, still_exists in product((1, 2), ('on_annex', 'on_subject_annexed'), (False, True)):
            with self.subTest(stage=stage, hook=hook, still_exists=still_exists):
                result = self.setup_terms(stage)
                self.assertTrue(self.b['action'](result, 'eon_withdraw_mediation', 'A', 'C'))
                self.b['clear_cooldown'](result)
                result['countries']['A']['wars'].add('D'); result['countries']['D']['wars'].add('A')
                self.t['active_base'](1, 'A', 'D', 'C', result)
                held = self.terms_snapshot(result)
                result['countries']['D']['exists'] = still_exists
                self.b['native_hook'](result, hook, 'B' if hook == 'on_annex' else 'D', 'D' if hook == 'on_annex' else 'B')
                self.assertEqual(self.terms_snapshot(result), held)
                self.assertFalse(any(self.b['reserved'](result, a) for a in ('A', 'D', 'C')))
                self.acknowledge_terms(result, stage, 2, 90)
                self.assertEqual(self.triad(result, 'eon_mediation_terms_', 'reserved'), [False] * 3)

    def test_annex_old_terms_actor_clears_only_old_terms_with_new_base_live(self):
        for stage, hook, still_exists in product((1, 2), ('on_annex', 'on_subject_annexed'), (False, True)):
            with self.subTest(stage=stage, hook=hook, still_exists=still_exists):
                result = self.setup_terms(stage)
                self.assertTrue(self.b['action'](result, 'eon_withdraw_mediation', 'A', 'C'))
                self.b['clear_cooldown'](result)
                result['countries']['A']['wars'].add('D'); result['countries']['D']['wars'].add('A')
                self.t['active_base'](1, 'A', 'D', 'C', result)
                base, windows = self.t['snapshot_base'](result), self.t['base_windows'](result)
                result['countries']['B']['exists'] = still_exists
                self.b['native_hook'](result, hook, 'D' if hook == 'on_annex' else 'B', 'B' if hook == 'on_annex' else 'D')
                self.assertEqual(self.triad(result, 'eon_mediation_terms_', 'reserved'), [False] * 3)
                self.assertEqual(self.t['snapshot_base'](result), base); self.assertEqual(self.t['base_windows'](result), windows)
                self.assertTrue(any('eon_mediation_terms_retired_pair@' in f for d in result['countries'].values() for f in d['flags']))

    def test_corrupt_new_base_force_preserves_held_other_triad_terms(self):
        for stage in (1, 2):
            with self.subTest(stage=stage):
                result = self.setup_terms(stage)
                self.assertTrue(self.b['action'](result, 'eon_withdraw_mediation', 'A', 'C'))
                self.b['clear_cooldown'](result)
                result['countries']['A']['wars'].add('D'); result['countries']['D']['wars'].add('A')
                self.t['active_base'](1, 'A', 'D', 'C', result)
                held = self.terms_snapshot(result)
                result['countries']['D']['variables']['eon_mediation_topic'] = 999
                self.b['native_hook'](result, 'on_daily', 'A')
                self.assertEqual(self.terms_snapshot(result), held)
                self.assertFalse(any(self.b['reserved'](result, a) for a in ('A', 'D', 'C')))
                self.acknowledge_terms(result, stage, 2, 90)
                self.assertEqual(self.triad(result, 'eon_mediation_terms_', 'reserved'), [False] * 3)

    def test_corrupt_and_dead_force_cleanup_still_retire(self):
        for stage, actor, defect in product((1, 2), ('A', 'B', 'C'), ('dead', 'topic', 'stage', 'duration')):
            with self.subTest(stage=stage, actor=actor, defect=defect):
                result = self.setup_terms(stage)
                if defect == 'dead': result['countries'][actor]['exists'] = False
                else: result['countries'][actor]['variables']['eon_mediation_terms_' + defect] = 999
                self.t['native_daily'](result, 'A')
                self.assertEqual(self.triad(result, 'eon_mediation_terms_', 'reserved'), [False] * 3)
                self.assertTrue(any('eon_mediation_terms_retired_pair@' in f for d in result['countries'].values() for f in d['flags']))

    def test_fresh_consents_remain_eligible(self):
        for topic, duration in product((1, 2), (30, 60, 90)):
            with self.subTest(topic=topic, duration=duration):
                result = self.t['active_base']()
                self.t['offer'](result, topic, duration)
                self.assertTrue(self.t['response'](result, topic, duration, 1))
                self.assertTrue(self.t['response'](result, topic, duration, 2))
                self.b['assert_session'](result, 3, topic)
                self.assertEqual(self.t['base_windows'](result), {a: duration for a in ('A', 'B', 'C')})

    def test_dead_base_and_corrupt_base_still_force_cleanup(self):
        for phase, actor, defect in product((1, 2), ('A', 'B', 'C'), ('dead', 'topic')):
            with self.subTest(phase=phase, actor=actor, defect=defect):
                result = self.b['state'](); self.b['request'](result)
                if phase == 2: self.assertTrue(self.b['answer_mediator'](result))
                if defect == 'dead': result['countries'][actor]['exists'] = False
                else: result['countries'][actor]['variables']['eon_mediation_topic'] = 999
                self.b['native_hook'](result, 'on_daily', 'A')
                self.assertEqual(self.triad(result, 'eon_mediation_', 'reserved'), [False] * 3)
                self.assertTrue(any('eon_mediation_retired_pair@' in f for d in result['countries'].values() for f in d['flags']))

    def test_known_mutants_are_rejected_by_observable_outcomes(self):
        # Old eager cleanup loses the held modal. This is a counterexample, not
        # a replacement implementation used by the positive lifecycle tests.
        result = self.setup_terms()
        self.t['model']['effects']['eon_mediation_terms_mark_expired'] = self.t['ast']('eon_mediation_terms_force_cleanup = yes')
        self.expire_terms(result)
        self.assertNotEqual(self.triad(result, 'eon_mediation_terms_', 'reserved'), [True] * 3)

        self.setUp(); result = self.setup_terms()
        self.assertTrue(self.b['action'](result, 'eon_withdraw_mediation', 'A', 'C'))
        self.b['clear_cooldown'](result); self.t['active_base'](1, result=result)
        before = self.t['snapshot_base'](result)
        # Deleting the expiry guards lets the old literal modify a later base.
        def remove_expired(nodes):
            return [(k, op, remove_expired(v) if isinstance(v, list) else v)
                    for k, op, v in nodes
                    if not (k == 'NOT' and v == self.t['ast']('has_country_flag = eon_mediation_terms_expired'))]
        registry = self.t['model']['capacity_triggers']
        registry['eon_mediation_terms_offer_valid'] = remove_expired(registry['eon_mediation_terms_offer_valid'])
        self.acknowledge_terms(result, 1, 2, 90, True)
        # Stage1 advances into stage2 despite the new base; its old literal must
        # remain forbidden. A second stale accept then actually changes it.
        self.assertEqual(self.triad(result, 'eon_mediation_terms_', 'reserved'), [True] * 3)
        self.assertTrue(self.t['response'](result, 2, 90, 2))
        self.assertNotEqual(self.t['snapshot_base'](result), before)

        self.setUp(); result = self.setup_terms()
        self.assertTrue(self.b['action'](result, 'eon_withdraw_mediation', 'A', 'C'))
        self.b['clear_cooldown'](result)
        result['countries']['A']['wars'].add('D'); result['countries']['D']['wars'].add('A')
        self.t['active_base'](1, 'A', 'D', 'C', result)
        before = self.terms_snapshot(result)
        self.t['model']['effects']['eon_mediation_terms_before_forced_base_clear'] = self.t['ast']('eon_mediation_terms_force_cleanup = yes')
        self.b['native_hook'](result, 'on_annex', 'B', 'D')
        self.assertNotEqual(self.terms_snapshot(result), before)


if __name__ == '__main__':
    unittest.main()
