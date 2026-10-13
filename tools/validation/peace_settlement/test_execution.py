"""Execute actual new peace effects with explicit native success/failure inputs.

This adapter checks cash atomicity and consumption ordering, not engine war scope.
Native receipts separately verify the primitive that the adapter cannot emulate.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/validation/diplomacy_package_03'))
from _support import ast, one


class Execution(unittest.TestCase):
    def setUp(self):
        path = ROOT / 'common/scripted_effects/eon_peace_settlement_effects.txt'
        self.assertTrue(path.exists(), 'The guarded exact-term execution path is missing')
        self.effects = dict((k, v) for k, _, v in ast(path.read_bytes()))

    def run_effect(self, suffix, valid=True, native_success=True, callback_cash_use=0):
        countries = {'sender': {'treasury': 20., 'flags': set()},
                     'recipient': {'treasury': 7., 'flags': set()}}
        trace = []
        war = [True]
        def execute(nodes, current='recipient', previous='sender'):
            nonlocal valid
            last_if = None
            for key, _, value in nodes:
                if key == 'if':
                    condition = one(value, 'limit')
                    ok = True
                    for ck, cop, cv in condition:
                        if ck.startswith('eon_peace_accept_'): ok &= valid
                        elif ck == 'NOT':
                            assert cv == [('has_war_with', '=', 'ROOT')]
                            ok &= not war[0]
                        else: raise AssertionError(('Unknown checked condition', ck))
                    last_if = ok
                    if ok: execute([row for row in value if row[0] != 'limit'], current, previous)
                elif key == 'else':
                    assert last_if is not None
                    if not last_if: execute(value, current, previous)
                elif key == 'ROOT': execute(value, 'sender', current)
                elif key.startswith('eon_peace_reject_'):
                    trace.append('consume')
                    valid = False
                elif key == 'eon_peace_native_statusquo':
                    self.assertIn('consume', trace, 'Claim the consent before native callbacks')
                    trace.append('native')
                    countries['sender']['treasury'] = max(0, countries['sender']['treasury'] - callback_cash_use)
                    if native_success: war[0] = False
                elif key in ('add_to_variable', 'subtract_from_variable', 'set_variable'):
                    name, op, amount = value[0]
                    if name == 'treasury':
                        self.assertIn('consume', trace)
                        if current == 'recipient':
                            self.assertFalse(war[0], 'No transfer unless actual war ended')
                            trace.append('cash')
                        else:
                            if key == 'subtract_from_variable':
                                self.assertGreaterEqual(countries[current]['treasury'], float(amount))
                            trace.append('escrow')
                    amount = float(amount)
                    if key == 'set_variable': countries[current][name] = amount
                    else: countries[current][name] = countries[current].get(name, 0) + amount * (1 if key == 'add_to_variable' else -1)
                elif key in ('set_truce', 'set_country_flag', 'country_event', 'log'):
                    trace.append(key)
                elif key == 'trigger_peace_deal': trace.append('legacy')
                else: raise AssertionError(('Unmodelled executed effect', key))
        # 'valid' is intentionally a supplied action guard fact, not native consent.
        execute(self.effects['eon_peace_execute_' + suffix])
        return countries, trace, war[0]

    def test_exact_one_time_payment_after_native_success(self):
        for suffix, amount in [('payment_5', 5), ('payment_10', 10)]:
            state, trace, war = self.run_effect(suffix)
            self.assertEqual(state['sender']['treasury'], 20 - amount)
            self.assertEqual(state['recipient']['treasury'], 7 + amount)
            self.assertEqual(trace.count('native'), 1)
            self.assertEqual(trace.count('consume'), 1)
            self.assertFalse(war)

    def test_stale_refused_duplicate_and_insufficient_cash_are_inert(self):
        for suffix in ['statusquo', 'armistice_90', 'armistice_180', 'payment_5', 'payment_10', 'conference']:
            state, trace, war = self.run_effect(suffix, valid=False)
            self.assertEqual(trace, [])
            self.assertEqual(state['sender']['treasury'], 20)
            self.assertEqual(state['recipient']['treasury'], 7)
            self.assertTrue(war)

    def test_native_failure_never_transfers_money(self):
        for suffix in ['payment_5', 'payment_10']:
            state, trace, war = self.run_effect(suffix, native_success=False)
            self.assertEqual(state['sender']['treasury'], 20)
            self.assertEqual(state['recipient']['treasury'], 7)
            self.assertNotIn('cash', trace)
            self.assertTrue(war)

    def test_no_cash_in_statusquo_or_armistice(self):
        for suffix in ['statusquo', 'armistice_90', 'armistice_180']:
            state, trace, war = self.run_effect(suffix)
            self.assertNotIn('cash', trace)
            self.assertFalse(war)

    def test_native_callback_cannot_spend_promised_cash(self):
        state, trace, war = self.run_effect('payment_10', callback_cash_use=18)
        self.assertGreaterEqual(state['sender']['treasury'], 0)
        self.assertEqual(state['recipient']['treasury'], 17)


if __name__ == '__main__': unittest.main(verbosity=2)
