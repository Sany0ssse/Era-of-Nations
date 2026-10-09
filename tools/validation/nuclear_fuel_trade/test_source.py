"""Production AST sensitivity checks; mutants run real lifecycle assertions."""
from io import StringIO
from pathlib import Path
import unittest
import model as b
from test_lifecycle import FuelTradeLifecycle


class SourceProof(unittest.TestCase):
    def test_all_nodes_parse_and_helpers_exist_in_actual_source(self):
        m=b.executor()
        for rel in b.FILES:
            text=(b.ROOT/rel).read_text(encoding='utf-8-sig')
            self.assertTrue(m.ast(text))
        for name in ('send','accept','refuse','acknowledge','daily_cleanup',
                     'return_escrow','release_refunds','transfer_annexed_assets'):
            self.assertIn(b.P+name,m.effects)
        for name in ('send_ready','response_ready','response_pair_pending',
                     'acknowledgement_ready','cash_step_available','fuel_step_available'):
            self.assertIn(b.P+name,m.triggers)

    def test_behavioural_mutants_are_rejected_by_independent_invariants(self):
        e,t=b.FILES[:2]
        effects=(b.ROOT/e).read_text(encoding='utf-8-sig')
        triggers=(b.ROOT/t).read_text(encoding='utf-8-sig')
        controls=(
            (e,effects,'limit = { eon_nuclear_fuel_trade_response_ready = yes }',
             'limit = { eon_nuclear_fuel_trade_response_pair_pending = yes }',
             'test_complete_purchase_and_sale_once_with_original_result_roles'),
            (t,triggers,'divide_temp_variable = { eon_nuclear_fuel_trade_quote_total = 1000000 }',
             'divide_temp_variable = { eon_nuclear_fuel_trade_quote_total = 10000 }',
             'test_both_directions_freeze_terms_and_reserve_only_sender_asset'),
            (t,triggers,'check_variable = { eon_nuclear_fuel_trade_partner = FROM }',
             'always = yes', 'test_wrong_peer_kind_or_role_cannot_accept_refuse_or_ack'),
            (t,triggers,'check_variable = { eon_nuclear_fuel_trade_quote_cash_credit = eon_nuclear_fuel_trade_quote_cash }',
             'always = yes', 'test_float32_different_cash_magnitudes_must_credit_exact_same_delta'),
            (t,triggers,'check_variable = { eon_nuclear_fuel_trade_price = PREV.eon_nuclear_fuel_trade_price }',
             'always = yes', 'test_frozen_terms_corruption_fails_without_payment_then_original_refusal_returns_asset'),
            (t,triggers,'NOT = { tag = var:nuclear_fuel_selling_selected_TAG }',
             'always = yes', 'test_invalid_sender_requests_are_inert'),
            (e,effects,'set_variable = { eon_nuclear_fuel_trade_cash_escrow = 0 }\n\t}',
             'set_variable = { ignored_cash_escrow = 0 }\n\t}',
             'test_refusal_refunds_only_sender_once_without_transfer'),
            (t,triggers,'check_variable = { eon_nuclear_fuel_trade_result_kind = 2 }',
             'always = yes', 'test_wrong_result_type_and_pending_ack_are_inert'),
            (e,effects,'add_to_variable = { treasury = eon_nuclear_fuel_trade_total }',
             'add_to_variable = { treasury = eon_nuclear_fuel_trade_quantity }',
             'test_complete_purchase_and_sale_once_with_original_result_roles'),
        )
        for index,(rel,raw,old,new,test) in enumerate(controls,1):
            with self.subTest(mutant=index,test=test):
                self.assertIn(old,raw)
                mutant=raw.replace(old,new,1)
                mutant_class=type('Mutant'+str(index),(FuelTradeLifecycle,),{'overrides':{rel:mutant}})
                result=unittest.TextTestRunner(stream=StringIO(),verbosity=0).run(unittest.TestSuite([mutant_class(test)]))
                self.assertFalse(result.wasSuccessful(),('Surviving behavioural mutant',index,test))
                self.assertEqual(result.errors,[],('Adapter boundary is not product defect evidence',result.errors))
                self.assertTrue(result.failures)


if __name__ == '__main__':
    unittest.main()
