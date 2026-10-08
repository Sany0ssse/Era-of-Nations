"""Actual-source lifecycle checks; no native/UI/MP acceptance claim."""
from copy import deepcopy
import unittest

import _support as s

PREFIX = 'eon_consultation_ui_'
DECISIONS = s.definitions(s.UI_FILES[3])[PREFIX + 'category']
DECISIONS = {name: body for name, op, body in DECISIONS}
ACTIONS = {name: body for name, op, body in s.definitions(s.UI_FILES[2])['scripted_diplomatic_actions']}
EVENTS = {s.one(body, 'id'): body for name, op, body in s.parse((s.ROOT / s.UI_FILES[5]).read_text(encoding='utf-8-sig')) if name == 'country_event'}
OLD_EVENTS = {s.one(body, 'id'): body for name, op, body in s.parse((s.ROOT / s.BASE_FILES[7]).read_text(encoding='utf-8-sig')) if name == 'country_event'}

def ready(result, name, actor='A', peer='B', fields=('allowed', 'target_root_trigger', 'target_trigger', 'visible', 'available')):
    body = DECISIONS[PREFIX + name]
    return all(s.condition(s.one(body, field), result, s.ctx(actor, peer)) for field in fields)

def click(result, name, actor='A', peer='B', force=False):
    enabled = ready(result, name, actor, peer)
    if enabled or force:
        s.execute(s.one(DECISIONS[PREFIX + name], 'complete_effect'), result, s.ctx(actor, peer))
    return enabled

def action(result, actor='A', peer='B', force=False):
    body = ACTIONS['eon_open_consultation_panel']
    context = s.native_ctx(actor, peer)
    enabled = all(s.condition(s.one(body, field), result, context) for field in ('allowed', 'visible', 'selectable', 'can_be_sent'))
    if enabled or force:
        s.execute(s.one(body, 'complete_effect'), result, context)
    return enabled

def ack(result, event_id, actor='A', peer='B'):
    event = EVENTS.get(event_id, OLD_EVENTS.get(event_id))
    for name, op, body in event:
        if name == 'option':
            s.execute([n for n in body if n[0] not in ('name', 'ai_chance')], result, s.ctx(actor, peer))

def snapshot_cash(result):
    return {tag: (country['pp'], country['variables'].get('treasury')) for tag, country in result['countries'].items()}

def prepared_mutator(name, semantics):
    topic = 2 if name == 'energy_editor' else 3 if name == 'aid_draft' else 1
    r = s.active_pair(s.state(semantics), topic=topic)
    if name == 'energy_editor':
        r['countries']['A']['flags'].add('energy_agreement@B')
        r['countries']['B']['flags'].add('energy_agreement@A')
    elif name == 'aid_draft':
        r['countries']['A']['variables'].update(gdp_total=100, num_of_civilian_factories=50)
        r['countries']['B']['variables'].update(gdp_total=50, num_of_civilian_factories=20)
        r['countries']['B']['arrays']['influence_array'] = [s.IDS['A']]
    elif not name.startswith('trade_propose_'):
        terms = 180 if name == 'trade_counter_90' or name == 'trade_accept_180' else 90
        sender, recipient = ('B', 'A') if name in ('trade_review', 'trade_decline', 'trade_accept_90', 'trade_accept_180', 'trade_counter_90', 'trade_counter_180') else ('A', 'B')
        assert click(r, 'trade_propose_' + str(terms), sender, recipient)
        if name not in ('trade_review', 'trade_withdraw'):
            assert click(r, 'trade_review', recipient, sender)
        if name in ('trade_notice', 'trade_end_request', 'trade_end_accept'):
            assert click(r, 'trade_accept_' + str(terms), recipient, sender)
            if name == 'trade_end_accept':
                assert click(r, 'trade_end_request', 'B', 'A')
                assert click(r, 'trade_review', 'A', 'B')
    return r

class LifecycleTests(unittest.TestCase):
    def test_open_both_sides_all_topics_costs_nothing_and_does_not_extend(self):
        for semantics in ('native',):
            for actor, peer in (('A', 'B'), ('B', 'A')):
                for topic in (1, 2, 3):
                    with self.subTest(semantics=semantics, actor=actor, topic=topic):
                        r = s.active_pair(s.state(semantics), actor, peer, topic)
                        for country in r['countries'].values():
                            country['pp'] = 0
                        before = s.stable(r)
                        self.assertTrue(action(r, actor, peer))
                        self.assertEqual(r['events'][-1], {'id': 'eon_consultation_ui.1', 'scope': actor, 'root': actor, 'from': peer})
                        r['day'] = 12
                        unchanged = s.stable(r)
                        self.assertTrue(click(r, 'status', actor, peer))
                        self.assertTrue(action(r, actor, peer))
                        self.assertEqual(s.stable(r), unchanged)
                        r['day'] = 0
                        self.assertEqual(s.stable(r), before)

    def test_topics_have_only_their_own_visible_actions(self):
        for topic in (1, 2, 3):
            r = s.active_pair(s.state(), topic=topic)
            for name in ('trade_visible', 'energy_visible', 'support_visible'):
                expected = topic == {'trade_visible': 1, 'energy_visible': 2, 'support_visible': 3}[name]
                self.assertEqual(s.condition([(PREFIX + name, '=', 'yes')], r, s.ctx()), expected)

    def test_cache_only_filters_existence_and_self(self):
        r = s.state()
        for name, body in DECISIONS.items():
            with self.subTest(name=name):
                self.assertTrue(s.condition(s.one(body, 'target_root_trigger'), r, s.ctx()))
                self.assertTrue(s.condition(s.one(body, 'target_trigger'), r, s.ctx()))
                self.assertFalse(s.condition(s.one(body, 'target_trigger'), r, s.ctx('A', 'A')))
                r['countries']['B']['exists'] = False
                self.assertFalse(s.condition(s.one(body, 'target_trigger'), r, s.ctx()))
                r['countries']['B']['exists'] = True
                r['countries']['A']['exists'] = False
                self.assertFalse(s.condition(s.one(body, 'target_root_trigger'), r, s.ctx()))
                r['countries']['A']['exists'] = True
                # Cached candidates deliberately remain broad across future topic/phase.
                self.assertFalse(ready(r, name.removeprefix(PREFIX)))

    def test_unsafe_live_actions_fail_closed_on_liveness_identity_role_and_topic(self):
        def mutate(r, defect):
            a, b = r['countries']['A'], r['countries']['B']
            if defect == 'expiry_a': a['expires']['eon_consultation_active_window'] = 0
            elif defect == 'expiry_b': b['expires']['eon_consultation_active_window'] = 0
            elif defect == 'war_a': a['wars'].add('B')
            elif defect == 'war_b': b['wars'].add('A')
            elif defect == 'dead_a': a['exists'] = False
            elif defect == 'dead_b': b['exists'] = False
            elif defect == 'wrong_a_partner': a['variables']['eon_consultation_partner'] = s.IDS['C']
            elif defect == 'wrong_b_partner': b['variables']['eon_consultation_partner'] = s.IDS['C']
            elif defect == 'extra_a_role': a['flags'].add('eon_consultation_outgoing')
            elif defect == 'extra_b_role': b['flags'].add('eon_consultation_incoming')
            elif defect == 'missing_role': b['flags'].remove('eon_consultation_active')
            elif defect == 'topic_mismatch': b['variables']['eon_consultation_topic'] = 3
            elif defect == 'topic_zero': a['variables']['eon_consultation_topic'] = b['variables']['eon_consultation_topic'] = 0
            elif defect == 'topic_invalid': a['variables']['eon_consultation_topic'] = b['variables']['eon_consultation_topic'] = 4
            else: raise AssertionError(defect)
        defects = ('expiry_a', 'expiry_b', 'war_a', 'war_b', 'dead_a', 'dead_b', 'wrong_a_partner', 'wrong_b_partner', 'extra_a_role', 'extra_b_role', 'missing_role', 'topic_mismatch', 'topic_zero', 'topic_invalid')
        for semantics in ('native',):
            for defect in defects:
                for name in ('trade_propose_90', 'trade_propose_180', 'trade_review', 'trade_accept_90', 'trade_accept_180', 'trade_counter_90', 'trade_counter_180', 'trade_decline', 'trade_withdraw', 'energy_editor', 'aid_draft'):
                    with self.subTest(semantics=semantics, defect=defect, name=name):
                        r = s.active_pair(s.state(semantics), topic=2 if name == 'energy_editor' else 3 if name == 'aid_draft' else 1)
                        mutate(r, defect)
                        before = s.stable(r)
                        self.assertFalse(click(r, name, force=True))
                        self.assertEqual(s.stable(r), before)

    def test_wrong_selected_target_and_self_never_mutate(self):
        for peer in ('C', 'A'):
            for name in DECISIONS:
                r = s.active_pair(s.state())
                before = s.stable(r)
                self.assertFalse(click(r, name.removeprefix(PREFIX), peer=peer, force=True))
                self.assertEqual(s.stable(r), before)
            r = s.active_pair(s.state())
            before = s.stable(r)
            self.assertFalse(action(r, peer=peer, force=True))
            self.assertEqual(s.stable(r), before)

    def test_each_real_enabled_mutator_is_blocked_if_the_channel_becomes_invalid(self):
        names = [name.removeprefix(PREFIX) for name in DECISIONS if name.removeprefix(PREFIX) not in ('status', 'end', 'debt_guidance')]
        for semantics in ('native',):
            for name in names:
                if name == 'aid_draft' and semantics == 'country':
                    # The separate differential aid test records this precise
                    # interpreter limitation rather than claiming availability.
                    self.assertFalse(ready(prepared_mutator(name, semantics), name))
                    continue
                for defect in ('expiry_a', 'expiry_b', 'war_a', 'war_b', 'dead_a', 'dead_b', 'wrong_a_partner', 'wrong_b_partner', 'extra_a_role', 'extra_b_role', 'topic_mismatch', 'wrong_topic'):
                    with self.subTest(semantics=semantics, name=name, defect=defect):
                        r = prepared_mutator(name, semantics)
                        self.assertTrue(ready(r, name), 'Scenario must start with this exact action reachable')
                        a, b = r['countries']['A'], r['countries']['B']
                        if defect == 'expiry_a': a['expires']['eon_consultation_active_window'] = 0
                        elif defect == 'expiry_b': b['expires']['eon_consultation_active_window'] = 0
                        elif defect == 'war_a': a['wars'].add('B')
                        elif defect == 'war_b': b['wars'].add('A')
                        elif defect == 'dead_a': a['exists'] = False
                        elif defect == 'dead_b': b['exists'] = False
                        elif defect == 'wrong_a_partner': a['variables']['eon_consultation_partner'] = s.IDS['C']
                        elif defect == 'wrong_b_partner': b['variables']['eon_consultation_partner'] = s.IDS['C']
                        elif defect == 'extra_a_role': a['flags'].add('eon_consultation_incoming')
                        elif defect == 'extra_b_role': b['flags'].add('eon_consultation_outgoing')
                        elif defect == 'topic_mismatch': b['variables']['eon_consultation_topic'] = a['variables']['eon_consultation_topic'] % 3 + 1
                        elif defect == 'wrong_topic': a['variables']['eon_consultation_topic'] = b['variables']['eon_consultation_topic'] = a['variables']['eon_consultation_topic'] % 3 + 1
                        before = s.stable(r)
                        self.assertFalse(click(r, name, force=True))
                        self.assertEqual(s.stable(r), before)

    def test_expired_or_warring_pair_remains_information_and_cleanup_only(self):
        for defect in ('expired', 'war'):
            r = s.active_pair(s.state(), topic=3)
            if defect == 'expired': r['day'] = 30
            else: r['countries']['A']['wars'].add('B')
            before = s.stable(r)
            self.assertTrue(action(r))
            self.assertTrue(click(r, 'status'))
            self.assertTrue(click(r, 'debt_guidance'))
            self.assertFalse(ready(r, 'aid_draft'))
            self.assertEqual(s.stable(r), before)

    def test_every_old_notice_and_new_panel_ack_is_permanently_inert(self):
        for old_topic, new_topic in ((1, 1), (1, 2), (3, 3)):
            for event_id in [*EVENTS, *[f'eon_consultation.{n}' for n in range(20, 28)]]:
                r = s.active_pair(s.state(), topic=old_topic)
                # These contexts may be stale even after samepair/sametopic reuse.
                s.execute([('eon_consultation_end_active', '=', 'yes')], r, s.ctx())
                s.active_pair(r, topic=new_topic)
                r['countries']['A']['variables'].update(treasury=999, eon_framework_negotiation_trade_status_B=123)
                before = s.stable(r)
                ack(r, event_id)
                self.assertEqual(s.stable(r), before, event_id)

    def test_real_trade_proposal_cost_and_response_consent(self):
        for semantics in ('native',):
            for actor, peer in (('A', 'B'), ('B', 'A')):
                for terms in (90, 180):
                    with self.subTest(semantics=semantics, actor=actor, terms=terms):
                        r = s.active_pair(s.state(semantics), actor, peer)
                        initial = snapshot_cash(r)
                        self.assertTrue(click(r, 'trade_propose_' + str(terms), actor, peer))
                        self.assertEqual(r['countries'][actor]['pp'], initial[actor][0] - 75)
                        self.assertEqual(r['countries'][peer]['pp'], initial[peer][0])
                        self.assertNotIn('trade_agreement@' + peer, r['countries'][actor]['flags'])
                        self.assertEqual(r['countries'][peer]['variables']['eon_framework_negotiation_trade_status@' + actor], 2)
                        before = s.stable(r)
                        self.assertFalse(click(r, 'trade_propose_' + str(terms), actor, peer, True))
                        self.assertFalse(click(r, 'trade_accept_' + str(terms), peer, actor, True))
                        self.assertEqual(s.stable(r), before)
                        self.assertTrue(click(r, 'trade_review', peer, actor))
                        cash_before = snapshot_cash(r)
                        self.assertTrue(click(r, 'trade_accept_' + str(terms), peer, actor))
                        self.assertIn('trade_agreement@' + peer, r['countries'][actor]['flags'])
                        self.assertIn('trade_agreement@' + actor, r['countries'][peer]['flags'])
                        self.assertEqual(snapshot_cash(r), cash_before)
                        before = s.stable(r)
                        self.assertFalse(click(r, 'trade_accept_' + str(terms), peer, actor, True))
                        self.assertEqual(s.stable(r), before)

    def test_fractional_pp_trade_boundary_and_national_gate(self):
        for amount in (74, 74.01, 74.99, 75, 75.01):
            r = s.active_pair(s.state())
            r['countries']['A']['pp'] = amount
            before = s.stable(r)
            self.assertEqual(click(r, 'trade_propose_90', force=True), amount >= 75)
            if amount < 75: self.assertEqual(s.stable(r), before)
            else: self.assertAlmostEqual(r['countries']['A']['pp'], amount - 75)
        r = s.active_pair(s.state(), 'ERI', 'B')
        r['countries']['ERI'].update(leader='Eritrean Transitional Government')
        r['countries']['ERI']['flags'].add('ETH_transitional_government_FLAG')
        before = s.stable(r)
        self.assertFalse(click(r, 'trade_propose_90', 'ERI', 'B', True))
        self.assertEqual(s.stable(r), before)

    def test_trade_counter_is_real_new_round_and_costs_once(self):
        r = s.active_pair(s.state())
        self.assertTrue(click(r, 'trade_propose_90'))
        self.assertTrue(click(r, 'trade_review', 'B', 'A'))
        before_cash = snapshot_cash(r)
        self.assertTrue(click(r, 'trade_counter_180', 'B', 'A'))
        self.assertEqual(r['countries']['B']['pp'], before_cash['B'][0] - 75)
        self.assertEqual(r['countries']['A']['variables']['eon_framework_negotiation_trade_round@B'], 2)
        self.assertFalse(click(r, 'trade_accept_180', 'A', 'B', True))
        self.assertTrue(click(r, 'trade_review', 'A', 'B'))
        self.assertTrue(click(r, 'trade_accept_180', 'A', 'B'))
        self.assertIn('trade_agreement@B', r['countries']['A']['flags'])

    def test_end_keeps_independent_agreements_and_sent_framework(self):
        for actor, peer in (('A', 'B'), ('B', 'A')):
            r = s.active_pair(s.state(), actor, peer)
            self.assertTrue(click(r, 'trade_propose_90', actor, peer))
            for owner, partner in ((actor, peer), (peer, actor)):
                c = r['countries'][owner]
                c['flags'].update(('energy_agreement@' + partner, 'mutual_investment_treaty_@' + partner, 'eon_aid_reserved'))
                c['variables'].update(eon_aid_partner=s.IDS[partner], eon_aid_amount=5, debt=44)
                c['arrays']['energy_contractors'] = [s.IDS[partner]]
            before = s.stable(r)
            self.assertTrue(click(r, 'end', actor, peer))
            after = s.stable(r)
            for tag in after['countries']:
                for obj in (before, after):
                    c = obj['countries'][tag]
                    c['flags'] = {x for x in c['flags'] if not x.startswith('eon_consultation_')}
                    c['variables'] = {k: v for k, v in c['variables'].items() if not k.startswith('eon_consultation_')}
                    c['expires'] = {k: v for k, v in c['expires'].items() if not k.startswith('eon_consultation_')}
            self.assertEqual(after, before)
            self.assertEqual(r['countries'][peer]['variables']['eon_framework_negotiation_trade_status@' + actor], 2)
            self.assertNotIn('eon_consultation_active', r['countries'][actor]['flags'])

    def test_aid_draft_exact_source_uses_native_shared_temps_without_cash_transfer(self):
        # Native10 proves shared unscoped execution temps and no PREV.temp read.
        # No donor/recipient temps are preplanted to make this path pass.
        for semantics in ('native',):
            for actor, peer in (('A', 'B'), ('B', 'A')):
                r = s.active_pair(s.state(semantics), actor, peer, 3)
                r['countries'][actor]['variables'].update(gdp_total=100, num_of_civilian_factories=50)
                r['countries'][peer]['variables'].update(gdp_total=50, num_of_civilian_factories=20)
                r['countries'][peer]['arrays']['influence_array'] = [s.IDS[actor]]
                before_cash = snapshot_cash(r)
                enabled = click(r, 'aid_draft', actor, peer, True)
                self.assertTrue(enabled)
                self.assertEqual(snapshot_cash(r), before_cash)
                if enabled:
                    self.assertIn('eon_aid_draft_owner', r['countries'][actor]['flags'])
                    self.assertIn('eon_aid_draft_recipient', r['countries'][peer]['flags'])
                    self.assertEqual(r['countries'][actor]['variables']['eon_aid_partner'], s.IDS[peer])
                    self.assertEqual(r['countries'][peer]['variables']['eon_aid_partner'], s.IDS[actor])
                    self.assertEqual(r['countries'][actor]['variables']['eon_aid_escrow'], 0)
                    before = s.stable(r)
                    self.assertFalse(click(r, 'aid_draft', actor, peer, True))
                    self.assertEqual(s.stable(r), before)

    def test_unknown_dependencies_raise(self):
        r = s.state()
        with self.assertRaises(AssertionError): s.condition([('unknown_trigger', '=', 'yes')], r, s.ctx())
        with self.assertRaises(AssertionError): s.execute([('unknown_effect', '=', 'yes')], r, s.ctx())

if __name__ == '__main__':
    unittest.main()
