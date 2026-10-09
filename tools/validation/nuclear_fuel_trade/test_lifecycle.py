"""Behavioural invariants over the actual source AST, not a mirrored model."""
from copy import deepcopy
import unittest
import model as b


class FuelTradeLifecycle(unittest.TestCase):
    overrides = None

    @classmethod
    def setUpClass(cls):
        cls.m = b.executor(cls.overrides)

    def fixture(self, amount=500, **kwargs):
        s = b.state(self.m, **kwargs)
        before = b.assets(s)
        b.send(self.m, s, amount)
        self.assertIn(b.P+'reserved', s['countries'][1]['flags'])
        self.assert_assets(s, before)
        return s, before

    def assert_assets(self, s, before, tolerance=1e-8):
        for actual, wanted in zip(b.assets(s), before):
            self.assertAlmostEqual(actual, wanted, delta=tolerance)

    def assert_clear(self, s, countries=(1,2)):
        for i in countries:
            self.assertNotIn(b.P+'reserved', s['countries'][i]['flags'])
            self.assertNotIn('currently_considering_an_offer', s['countries'][i]['flags'])
            self.assertNotIn(b.P+'partner', s['countries'][i]['vars'])

    def test_actual_seller_export_policy_and_bilateral_embargo_revalidated(self):
        for amount,kind,seller,buyer in ((500,1,2,1),(-500,2,1,2)):
            with self.subTest(amount=amount):
                s=b.state(self.m)
                s['countries'][seller]['flags'].add('eon_nuclear_fuel_exports_blocked')
                before=b.assets(s)
                b.send(self.m,s,amount)
                self.assert_clear(s)
                self.assertEqual(s['events'],[])
                self.assert_assets(s,before)
                s=b.state(self.m)
                s['countries'][buyer]['flags'].add('eon_nuclear_fuel_exports_blocked')
                b.send(self.m,s,amount)
                self.assertIn(b.P+'reserved',s['countries'][1]['flags'])
                for owner,field,other in ((1,'embargoing',2),(2,'embargoing',1),(1,'embargoed_by',2),(2,'embargoed_by',1)):
                    s=b.state(self.m);s['countries'][owner][field]={other};before=b.assets(s)
                    b.send(self.m,s,amount)
                    self.assert_clear(s);self.assertEqual(s['events'],[]);self.assert_assets(s,before)
                    s,before=self.fixture(amount)
                    s['countries'][owner][field]={other}
                    b.respond(self.m,s,kind=kind)
                    self.assertEqual(s['countries'][1]['vars'][b.P+'phase'],5)
                    self.assert_assets(s,before)
                    self.assertEqual(s['countries'][seller]['vars']['var_reactor_material_stockpile'],10000)
                    b.acknowledge(self.m,s,kind=kind,outcome=3)
                    self.assert_clear(s)
                s,before=self.fixture(amount)
                s['countries'][seller]['flags'].add('eon_nuclear_fuel_exports_blocked')
                b.invoke(self.m,s,'daily_cleanup')
                self.assertEqual(s['countries'][1]['vars'][b.P+'phase'],1)
                b.respond(self.m,s,choice='refuse',kind=kind)
                self.assertEqual(s['countries'][1]['vars'][b.P+'phase'],5)
                self.assert_assets(s,before)
                b.acknowledge(self.m,s,kind=kind,outcome=3)
                self.assert_clear(s)

    def test_atomic_fuel_delivery_refreshes_both_current_power_views(self):
        for amount,kind in ((500,1),(-500,2)):
            s,before=self.fixture(amount)
            s['refresh_calls']=[]
            b.respond(self.m,s,kind=kind)
            calls=s['refresh_calls']
            self.assertIn((1,'eon_uranium_refresh_energy'),calls)
            self.assertIn((2,'eon_uranium_refresh_energy'),calls)
            self.assertNotIn((1,'ingame_update_setup'),calls)
            self.assert_assets(s,before)

    def test_send_normalizes_both_existing_participants_before_quote(self):
        for amount,kind in ((500,1),(-500,2)):
            s=b.state(self.m,fuel=25)
            for actor in (1,2):s['countries'][actor]['flags'].discard('eon_uranium_reactor_stock_in_kg')
            visited=[]
            def external_migration(state,actor):
                visited.append(actor)
                # A declared kg outcome from the shared migration boundary,
                # not a copy of the root's conversion coefficient/geology.
                state['countries'][actor]['vars']['var_reactor_material_stockpile']=1500
                state['countries'][actor]['flags'].add('eon_uranium_reactor_stock_in_kg')
            s['unit_initialization_boundary']=external_migration
            b.send(self.m,s,amount)
            self.assertEqual(visited,[1,2])
            self.assertEqual(s['unit_initialization_calls'],[1,2])
            self.assertIn(b.P+'reserved',s['countries'][1]['flags'])
            self.assertEqual(s['countries'][2]['vars']['var_reactor_material_stockpile'],1500)
            before=b.assets(s)
            b.respond(self.m,s,kind=kind)
            self.assert_assets(s,before)
            b.acknowledge(self.m,s,kind=kind)
            b.send(self.m,s,amount)
            self.assertEqual(visited,[1,2],'Already normalized inventories were migrated twice')
        s=b.state(self.m);s['countries'][2]['exists']=False
        b.send(self.m,s)
        self.assertEqual(s['unit_initialization_calls'],[1])
        self.assert_clear(s)

    def test_both_directions_freeze_terms_and_reserve_only_sender_asset(self):
        for amount in (500,-500):
            with self.subTest(amount=amount):
                s, before = self.fixture(amount)
                a, peer = (s['countries'][i]['vars'] for i in (1,2))
                self.assertEqual(a[b.P+'quantity'],500)
                self.assertAlmostEqual(a[b.P+'quoted_total'],.00025)
                self.assertAlmostEqual(a[b.P+'total'],.00025)
                self.assertEqual(a[b.P+'quantity'],peer[b.P+'quantity'])
                if amount > 0:
                    self.assertAlmostEqual(a[b.P+'cash_escrow'],.00025)
                    self.assertEqual(a['var_reactor_material_stockpile'],10000)
                else:
                    self.assertEqual(a[b.P+'fuel_escrow'],500)
                    self.assertEqual(a['treasury'],500)
                self.assertEqual(peer['treasury'],500)
                self.assertEqual(peer['var_reactor_material_stockpile'],10000)
                self.assertEqual(s['events'][0]['id'], 'energy.1' if amount>0 else 'energy.10')
                self.assertEqual(s['events'][0]['sender'],1)
                self.assertEqual(s['events'][0]['target'],2)
                self.assertEqual(s['events'][0]['delay'],{'hours':'1'})

    def test_complete_purchase_and_sale_once_with_original_result_roles(self):
        for amount,kind,result in ((500,1,'energy.2'),(-500,2,'energy.11')):
            with self.subTest(kind=kind):
                s, before = self.fixture(amount)
                b.respond(self.m,s,kind=kind)
                a, peer = (s['countries'][i]['vars'] for i in (1,2))
                self.assertEqual(a['var_reactor_material_stockpile'],10500 if kind==1 else 9500)
                self.assertEqual(peer['var_reactor_material_stockpile'],9500 if kind==1 else 10500)
                self.assertEqual(a[b.P+'phase'],2)
                self.assertEqual(a[b.P+'cash_escrow'],0)
                self.assertEqual(a[b.P+'fuel_escrow'],0)
                self.assertEqual(s['events'][-1],dict(id=result,target=1,sender=2,delay={'hours':'1'}))
                self.assert_assets(s,before)
                snapshot=deepcopy(s['countries']); events=deepcopy(s['events'])
                for choice in ('accept','refuse','accept'):
                    b.respond(self.m,s,choice,kind)
                self.assertEqual(s['countries'],snapshot)
                self.assertEqual(s['events'],events)
                b.acknowledge(self.m,s,kind)
                self.assert_clear(s)
                self.assert_assets(s,before)

    def test_mutable_gui_fields_cannot_change_frozen_contract(self):
        for amount,kind in ((500,1),(-500,2)):
            with self.subTest(kind=kind):
                s,before=self.fixture(amount)
                b.quote(s,amount=-17000,price=400,peer=3)
                b.respond(self.m,s,kind=kind)
                self.assertEqual(s['countries'][2]['vars']['var_reactor_material_stockpile'],9500 if kind==1 else 10500)
                self.assert_assets(s,before)

    def test_wrong_peer_kind_or_role_cannot_accept_refuse_or_ack(self):
        for amount,kind in ((500,1),(-500,2)):
            for actor,peer,response in ((2,3,kind),(2,1,3-kind),(1,2,kind)):
                with self.subTest(kind=kind,actor=actor,peer=peer,response=response):
                    s,before=self.fixture(amount); frozen=deepcopy(s['countries'])
                    b.respond(self.m,s,kind=response,actor=actor,peer=peer)
                    b.respond(self.m,s,'refuse',response,actor,peer)
                    b.acknowledge(self.m,s,response,actor=actor,peer=peer)
                    self.assertEqual(s['countries'],frozen)
                    self.assert_assets(s,before)

    def test_wrong_result_type_and_pending_ack_are_inert(self):
        s,before=self.fixture(); initial=deepcopy(s['countries'])
        b.acknowledge(self.m,s)
        self.assertEqual(s['countries'],initial)
        b.respond(self.m,s)
        settled=deepcopy(s['countries'])
        b.acknowledge(self.m,s,outcome=3)
        self.assertEqual(s['countries'],settled)
        b.acknowledge(self.m,s,outcome=2)
        self.assert_clear(s); self.assert_assets(s,before)

    def test_refusal_refunds_only_sender_once_without_transfer(self):
        for amount,kind,result in ((500,1,'energy.3'),(-500,2,'energy.12')):
            with self.subTest(kind=kind):
                s,before=self.fixture(amount)
                b.respond(self.m,s,'refuse',kind)
                for i in (1,2):
                    self.assertEqual(s['countries'][i]['vars']['var_reactor_material_stockpile'],10000)
                    self.assertAlmostEqual(s['countries'][i]['vars']['treasury'],500)
                self.assert_assets(s,before)
                self.assertEqual(s['events'][-1]['id'],result)
                frozen=deepcopy(s['countries'])
                b.respond(self.m,s,'accept',kind); b.respond(self.m,s,'refuse',kind)
                self.assertEqual(s['countries'],frozen)
                b.acknowledge(self.m,s,kind,outcome=3)
                self.assert_clear(s); self.assert_assets(s,before)

    def test_expiry_or_war_returns_assets_retains_original_modal_until_reply(self):
        for amount,kind in ((500,1),(-500,2)):
            for ending in ('sender_time','recipient_time','war'):
                with self.subTest(kind=kind,ending=ending):
                    s,before=self.fixture(amount)
                    if ending=='war': s['countries'][2]['wars'].add(1)
                    else: s['countries'][1 if ending=='sender_time' else 2]['flags'].discard(b.P+'live')
                    b.invoke(self.m,s,'daily_cleanup')
                    self.assertEqual(s['countries'][1]['vars'][b.P+'phase'],4)
                    self.assert_assets(s,before)
                    self.assertFalse(b.check(self.m,s,'send_ready'))
                    frozen=deepcopy(s['countries'])
                    b.acknowledge(self.m,s,outcome=3,kind=kind)
                    self.assertEqual(s['countries'],frozen)
                    # Restoring a timed flag does not restore consent or escrow.
                    for i in (1,2): s['countries'][i]['flags'].add(b.P+'live')
                    self.assertFalse(b.check(self.m,s,'response_ready',2,1,{b.P+'response_kind':kind}))
                    b.respond(self.m,s,kind=kind)
                    self.assertEqual(s['countries'][1]['vars'][b.P+'phase'],5)
                    b.acknowledge(self.m,s,kind,outcome=3)
                    self.assert_clear(s); self.assert_assets(s,before)

    def test_stock_cash_or_capacity_change_prevents_stale_acceptance(self):
        for amount,kind,field,newvalue in ((500,1,'var_reactor_material_stockpile',0),
                                           (-500,2,'treasury',0),
                                           (-500,2,'var_reactor_material_stockpile',20000000)):
            with self.subTest(kind=kind,field=field):
                s,_=self.fixture(amount)
                s['countries'][2]['vars'][field]=newvalue
                before=b.assets(s)
                b.respond(self.m,s,kind=kind)
                self.assertEqual(s['countries'][1]['vars'][b.P+'phase'],5)
                self.assertEqual(s['countries'][2]['vars'][field],newvalue)
                self.assert_assets(s,before)

    def test_escrow_remains_owned_when_refund_headroom_is_zero(self):
        for amount,kind,field,cap,claim in ((500,1,'treasury',1000000,'cash_refund_due'),
                                          (-500,2,'var_reactor_material_stockpile',20000000,'fuel_refund_due')):
            with self.subTest(kind=kind):
                s,_=self.fixture(amount)
                s['countries'][1]['vars'][field]=cap
                before=b.assets(s)
                b.respond(self.m,s,'refuse',kind)
                self.assertGreater(s['countries'][1]['vars'].get(b.P+claim,0),0)
                self.assertEqual(s['countries'][1]['vars'][field],cap)
                self.assert_assets(s,before)
                b.acknowledge(self.m,s,kind,outcome=3)
                self.assert_clear(s)
                self.assertGreater(s['countries'][1]['vars'].get(b.P+claim,0),0)
                # Returning to the original currency magnitude can represent
                # the exact held debit; mere headroom need not suffice.
                s['countries'][1]['vars'][field]=500 if kind==1 else cap-1000
                before=b.assets(s)
                b.invoke(self.m,s,'daily_cleanup')
                self.assertAlmostEqual(s['countries'][1]['vars'].get(b.P+claim,0),0)
                self.assert_assets(s,before)

    def test_dead_rebound_or_corrupt_partner_refunds_and_retires_exact_pair(self):
        for defect in ('dead','reverse','roles'):
            with self.subTest(defect=defect):
                s,before=self.fixture(-500)
                if defect=='dead': s['countries'][2]['exists']=False
                elif defect=='reverse': s['countries'][2]['vars'][b.P+'partner']=3
                else: s['countries'][2]['flags'].discard(b.P+'incoming')
                b.invoke(self.m,s,'daily_cleanup')
                self.assertNotIn(b.P+'reserved',s['countries'][1]['flags'])
                self.assertIn(b.P+'retired_pair@2',s['countries'][1]['flags'])
                self.assertIn(b.P+'retired_pair@1',s['countries'][2]['flags'])
                self.assert_assets(s,before)
                s['countries'][2]['exists']=True
                self.assertFalse(b.check(self.m,s,'send_ready'))
                b.quote(s,peer=3)
                self.assertTrue(b.check(self.m,s,'send_ready'))

    def test_two_unacknowledged_modals_prevent_reuse_then_clean_result_releases(self):
        s,_=self.fixture()
        b.respond(self.m,s)
        self.assertFalse(b.check(self.m,s,'send_ready'))
        self.assertFalse(b.check(self.m,s,'send_ready',2))
        b.acknowledge(self.m,s)
        self.assertTrue(b.check(self.m,s,'send_ready'))

    def test_invalid_sender_requests_are_inert(self):
        cases = ((0,.5,2),(500,0,2),(500,-.5,2),(500,1001,2),(20000001,.5,2),(500,.5,1),(500,.5,99))
        for quantity,price,peer in cases:
            with self.subTest(quantity=quantity,price=price,peer=peer):
                s=b.state(self.m); b.quote(s,quantity,price,peer=peer)
                frozen=deepcopy(s['countries'])
                self.assertFalse(b.check(self.m,s,'send_ready'))
                b.invoke(self.m,s,'send')
                self.assertEqual(s['countries'],frozen)
                self.assertEqual(s['events'],[])

    def test_sender_shortages_and_counterparty_capacity_are_checked_before_escrow(self):
        for amount,side,field,newvalue in ((500,1,'treasury',0),
                                           (-500,1,'var_reactor_material_stockpile',0),
                                           (500,2,'var_reactor_material_stockpile',0),
                                           (-500,2,'treasury',0),
                                           (500,1,'var_reactor_material_stockpile',20000000),
                                           (-500,2,'var_reactor_material_stockpile',20000000),
                                           (500,2,'treasury',1000000),
                                           (-500,1,'treasury',1000000)):
            with self.subTest(amount=amount,side=side,field=field):
                s=b.state(self.m); b.quote(s,amount)
                s['countries'][side]['vars'][field]=newvalue
                frozen=deepcopy(s['countries'])
                self.assertFalse(b.check(self.m,s,'send_ready'))
                b.invoke(self.m,s,'send'); self.assertEqual(s['countries'],frozen)

    def test_frozen_terms_corruption_fails_without_payment_then_original_refusal_returns_asset(self):
        for field,newvalue in (('quantity',1000),('price',.7),('total',.01),('quoted_total',.02)):
            with self.subTest(field=field):
                s,before=self.fixture(-500)
                s['countries'][2]['vars'][b.P+field]=newvalue
                self.assertFalse(b.check(self.m,s,'response_ready',2,1,{b.P+'response_kind':2}))
                b.respond(self.m,s,kind=2)
                self.assertEqual(s['countries'][1]['vars'][b.P+'phase'],5)
                self.assertEqual(s['countries'][2]['vars']['var_reactor_material_stockpile'],10000)
                self.assert_assets(s,before)

    def test_old_clock_observer_does_not_expire_fresh_offer_after_clean_ack(self):
        s,before=self.fixture()
        b.respond(self.m,s); b.acknowledge(self.m,s)
        b.send(self.m,s)
        frozen=deepcopy(s['countries'])
        # Explicit callback consumption, not native scheduling/time evidence.
        self.m.execute(self.m.one(self.m.events['eon_nuclear_fuel_trade.1'],'immediate'),s,self.m.context(1))
        self.assertEqual(s['countries'],frozen)
        self.assert_assets(s,before)

    def test_diplomatic_contracts_debt_and_raw_resources_remain_unchanged(self):
        s=b.state(self.m)
        for i in (1,2):
            s['countries'][i]['vars'].update(debt=123, resource_produced_uranium=400,
                                           nuclear_reactor_fuel_production=20000)
            s['countries'][i]['flags'].update(('energy_agreement@'+str(3-i),'defensive_treaty@'+str(3-i)))
        protected=lambda: {i:dict(debt=s['countries'][i]['vars']['debt'],
                                 resource=s['countries'][i]['vars']['resource_produced_uranium'],
                                 production=s['countries'][i]['vars']['nuclear_reactor_fuel_production'],
                                 treaties={f for f in s['countries'][i]['flags'] if f.startswith(('energy_agreement','defensive_treaty'))}) for i in (1,2)}
        before=protected()
        b.send(self.m,s); b.respond(self.m,s); b.acknowledge(self.m,s)
        self.assertEqual(protected(),before)

    def test_busy_dead_war_and_retired_sender_requests_are_inert(self):
        for defect in ('busy_sender','busy_peer','legacy_sender','legacy_peer','dead','war','retired_sender','retired_peer'):
            with self.subTest(defect=defect):
                s=b.state(self.m); b.quote(s)
                if defect.startswith('busy_'): s['countries'][1 if defect.endswith('sender') else 2]['flags'].add(b.P+'reserved')
                elif defect.startswith('legacy_'): s['countries'][1 if defect.endswith('sender') else 2]['flags'].add('currently_considering_an_offer')
                elif defect=='dead': s['countries'][2]['exists']=False
                elif defect=='war': s['countries'][1]['wars'].add(2)
                else: s['countries'][1 if defect.endswith('sender') else 2]['flags'].add(b.P+'retired_pair@'+('2' if defect.endswith('sender') else '1'))
                frozen=deepcopy(s['countries'])
                self.assertFalse(b.check(self.m,s,'send_ready'))
                b.invoke(self.m,s,'send'); self.assertEqual(s['countries'],frozen)

    def test_float32_tiny_cash_and_odd_large_fuel_moves_reject_free_transfers(self):
        for cash,fuel,amount in ((900000,10000,500),(500,19000000,1)):
            with self.subTest(cash=cash,fuel=fuel):
                s=b.state(self.m,cash=cash,fuel=fuel,float32=True); b.quote(s,amount)
                frozen=deepcopy(s['countries'])
                self.assertFalse(b.check(self.m,s,'send_ready'))
                b.invoke(self.m,s,'send'); self.assertEqual(s['countries'],frozen)

    def test_float32_different_cash_magnitudes_must_credit_exact_same_delta(self):
        s=b.state(self.m,cash=500,float32=True)
        s['countries'][2]['vars']['treasury']=900000
        b.quote(s); self.assertFalse(b.check(self.m,s,'send_ready'))

    def test_float32_same_magnitude_settlement_is_cash_and_fuel_conserving(self):
        for amount,kind in ((500,1),(-500,2)):
            with self.subTest(kind=kind):
                s,before=self.fixture(amount,float32=True)
                self.assertGreater(s['countries'][1]['vars'][b.P+'total'],0)
                b.respond(self.m,s,kind=kind)
                self.assertEqual(s['countries'][1]['vars'][b.P+'phase'],2)
                self.assert_assets(s,before,1e-7)

    def test_decimal_precision_fail_closed_or_conserve_representable_batched_price(self):
        for precision in (3,5):
            with self.subTest(precision=precision):
                s=b.state(self.m,precision=precision); b.quote(s)
                if precision==3:
                    frozen=deepcopy(s['countries'])
                    self.assertFalse(b.check(self.m,s,'send_ready'))
                    b.invoke(self.m,s,'send'); self.assertEqual(s['countries'],frozen)
                s=b.state(self.m,precision=precision); before=b.assets(s)
                b.send(self.m,s,amount=10000)
                self.assertIn(b.P+'reserved',s['countries'][1]['flags'])
                b.respond(self.m,s)
                self.assertEqual(s['countries'][1]['vars'][b.P+'phase'],2)
                self.assert_assets(s,before,2*10**(-precision))

    def test_annexed_owned_claims_transfer_once_to_valid_successor(self):
        for amount in (500,-500):
            with self.subTest(amount=amount):
                s,before=self.fixture(amount)
                s['countries'][1]['exists']=False
                b.invoke(self.m,s,'transfer_annexed_assets',1,temps={b.P+'successor':3})
                self.assert_assets(s,before)
                frozen=deepcopy(s['countries'])
                b.invoke(self.m,s,'transfer_annexed_assets',1,temps={b.P+'successor':3})
                # Zero scalar claims may be materialized; assets never repeat.
                self.assert_assets(s,before)
                self.assertEqual(s['countries'][3]['vars']['treasury'],frozen[3]['vars']['treasury'])
                self.assertEqual(s['countries'][3]['vars']['var_reactor_material_stockpile'],frozen[3]['vars']['var_reactor_material_stockpile'])

    def test_invalid_annex_successor_preserves_owned_assets(self):
        for successor in (0,1,99):
            with self.subTest(successor=successor):
                s,before=self.fixture(-500); frozen=deepcopy(s['countries'])
                b.invoke(self.m,s,'transfer_annexed_assets',1,temps={b.P+'successor':successor})
                self.assertEqual(s['countries'],frozen); self.assert_assets(s,before)

    def test_legacy_reply_cannot_execute_mutable_old_transfer_or_double_notify(self):
        s=b.state(self.m)
        for i in (1,2): s['countries'][i]['flags'].add('currently_considering_an_offer')
        b.quote(s,19000,50); before=b.assets(s)
        b.respond(self.m,s,'refuse')
        self.assert_assets(s,before)
        self.assertIn(b.P+'retired_pair@2',s['countries'][1]['flags'])
        self.assertNotIn('currently_considering_an_offer',s['countries'][1]['flags'])
        events=deepcopy(s['events'])
        b.respond(self.m,s,'refuse'); self.assertEqual(s['events'],events)

    def test_legacy_result_unlocks_without_replaying_historical_assets(self):
        s=b.state(self.m)
        for i in (1,2): s['countries'][i]['flags'].add('currently_considering_an_offer')
        s['countries'][1]['vars'].update(treasury=499, var_reactor_material_stockpile=10500)
        s['countries'][2]['vars'].update(treasury=501, var_reactor_material_stockpile=9500)
        before=b.assets(s)
        b.acknowledge(self.m,s)
        self.assert_assets(s,before)
        for i in (1,2): self.assertNotIn('currently_considering_an_offer',s['countries'][i]['flags'])
        frozen=deepcopy(s['countries'])
        b.acknowledge(self.m,s)
        self.assertEqual(s['countries'],frozen)


if __name__ == '__main__':
    unittest.main()
