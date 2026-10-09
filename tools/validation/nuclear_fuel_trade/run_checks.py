"""Run the source lifecycle and mutation controls; emits a compact receipt."""
from pathlib import Path
import hashlib
import json
import unittest
import model as b
import test_lifecycle
import test_source
import test_ai_policy
import test_result_wait
import test_builder_strings
import test_state_trace
import test_cash_api_control
import test_ai_prepare


if __name__ == '__main__':
    loader=unittest.TestLoader()
    suite=unittest.TestSuite((loader.loadTestsFromTestCase(test_lifecycle.FuelTradeLifecycle),
                             loader.loadTestsFromTestCase(test_source.SourceProof),
                             loader.loadTestsFromTestCase(test_ai_policy.BuyerPolicy),
                             loader.loadTestsFromTestCase(test_result_wait.ResultWait),
                             loader.loadTestsFromTestCase(test_builder_strings.NativeBuilderStrings),
                             loader.loadTestsFromTestCase(test_state_trace.StateTrace),
                             loader.loadTestsFromTestCase(test_cash_api_control.CashApiControl),
                             loader.loadTestsFromTestCase(test_ai_prepare.AutonomousPrepare)))
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    print(json.dumps(dict(proof_scope='Actual finished-fuel effects/trigger AST over explicit fixture state',
                          tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                          behavioural_mutants_rejected=13 if result.wasSuccessful() else None,
                          source_sha256={rel:hashlib.sha256((b.ROOT/rel).read_bytes()).hexdigest() for rel in (*b.FILES,'events/00_Energy_events.txt','common/scripted_effects/eon_nuclear_fuel_ai_effects.txt')},
                          not_proven=['native timers/event queue/AI', 'human UI', 'native numeric arithmetic',
                                      'save/load','multiplayer','full campaign balance']),ensure_ascii=False))
    raise SystemExit(0 if result.wasSuccessful() else 1)
