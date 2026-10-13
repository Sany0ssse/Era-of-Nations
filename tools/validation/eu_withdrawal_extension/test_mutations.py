"""Confirm important behavioral tests fail when the proposed AST is broken.

Only in-memory AST mutations; no source or fixture file is rewritten.
"""
from pathlib import Path
import hashlib
import json
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_lifecycle import ExtensionLifecycle, ExtensionModel, RevocationNewsControls, one, CALL


def remove_check(nodes, name):
    return [entry for entry in nodes
            if not (entry[0] == "check_variable" and
                    (any(key == name for key, op, value in entry[2]) or
                     any(key == "var" and value == name for key, op, value in entry[2])))]


class MutationGuards(unittest.TestCase):
    def rejects(self, test_name, mutate):
        case = ExtensionLifecycle(test_name)
        case.setUp()
        mutate(case.m)
        with self.assertRaises(AssertionError):
            getattr(case, test_name)()

    def test_missing_unanimity_gate_is_detected(self):
        def mutate(m):
            body = one(m.effects["eon_eu_extension_accept_final"], "if")
            body[0] = ("limit", "=", [("always", "=", "yes")])
        self.rejects("test_partial_unanimity_never_queues", mutate)

    def test_instant_queue_on_proposal_is_detected(self):
        def mutate(m):
            one(m.effects["eon_eu_extension_propose"], "if").append(
                ("set_variable", "=", [("eon_eu_extension_queued_units", "=", "1")]))
        self.rejects("test_proposal_never_grants_extension_or_resets_remaining_period", mutate)

    def test_consuming_before_positive_clock_expires_is_detected(self):
        def mutate(m):
            body = one(m.effects["eon_eu_extension_resolve_deadline"], "if")
            limit = one(body, "limit")
            limit[:] = [entry for entry in limit if entry != ("NOT", "=", [("has_country_flag", "=", "eon_eu_withdrawal_deadline")])]
        self.rejects("test_exact_one_unit_consumed_only_when_current_period_expires", mutate)

    def test_reusing_queue_from_another_notice_is_detected(self):
        def mutate(m):
            m.triggers["eon_eu_extension_queue_current"] = remove_check(m.triggers["eon_eu_extension_queue_current"], "eon_eu_extension_queued_notice_serial")
        self.rejects("test_stale_queued_notice_serial_cannot_extend_deadline", mutate)

    def test_old_timeout_direct_exit_bypass_is_detected(self):
        def mutate(m):
            block = m.legacy["EU_exit"]
            index = next(i for i, (key, op, value) in enumerate(block) if key == "timeout_effect")
            block[index] = ("timeout_effect", "=", [CALL("leaving_EU")])
        self.rejects("test_old_save_native_exit_remaining_is_authoritative_not_new_730_days", mutate)

    def test_missing_queue_cleanup_on_revoke_is_detected(self):
        def mutate(m):
            m.effects["eon_eu_extension_clear_notice"] = [entry for entry in m.effects["eon_eu_extension_clear_notice"]
                if entry != ("set_variable", "=", [("eon_eu_extension_queued_units", "=", "0")])]
        self.rejects("test_revoke_clears_queue_and_invalidates_monotonic_notice_once", mutate)

    def test_vacuous_unanimity_without_governments_is_detected(self):
        def mutate(m):
            m.triggers["eon_eu_extension_final_ready"] = remove_check(m.triggers["eon_eu_extension_final_ready"], "eon_eu_extension_electorate_total")
            proposal_if = one(m.effects["eon_eu_extension_recount"], "if")
            gate = [value for key, op, value in proposal_if if key == "if"][0]
            limit = one(gate, "limit")
            limit[:] = remove_check(limit, "eon_eu_extension_electorate_total")
        self.rejects("test_zero_other_eligible_governments_is_not_unanimity", mutate)

    def test_treating_explicit_abstention_as_missing_response_is_detected(self):
        def mutate(m):
            m.triggers["eon_eu_extension_final_ready"] = [
                (key, op, [(name, cmp, "eon_eu_extension_yes_count" if name == "var" and value == "eon_eu_extension_answer_count" else value)
                           for name, cmp, value in body]) if key == "check_variable" else (key, op, body)
                for key, op, body in m.triggers["eon_eu_extension_final_ready"]]
        self.rejects("test_explicit_abstention_does_not_veto_unanimity_but_missing_response_does", mutate)

    def test_requiring_positive_flag_for_expired_known_clock_migration_is_detected(self):
        original_init = ExtensionModel.__init__
        def broken_init(model):
            original_init(model)
            outer = one(model.effects["eon_eu_extension_migrate_clock"], "if")
            known_clock = [body for key, op, body in outer if key == "else_if"][-1]
            one(known_clock, "limit").append(("has_country_flag", "=", "eon_eu_withdrawal_deadline"))
        # The scenario creates a genuine prior-version fixture itself; keep the
        # deliberate source mutation on that newly constructed model too.
        with patch.object(ExtensionModel, "__init__", broken_init):
            self.rejects("test_known_old_clock_already_expired_without_mission_finishes_via_actual_daily_ast", lambda model: None)

    def test_missing_first_callback_recovery_is_detected(self):
        original_init = ExtensionModel.__init__
        def broken_init(model):
            original_init(model)
            model.effects["eon_eu_extension_legacy_timeout"].pop(0)
        with patch.object(ExtensionModel, "__init__", broken_init):
            self.rejects("test_main_legacy_timeout_before_first_daily_recovers_known_expiry_without_new_period", lambda model: None)

    def test_first_short_callback_overriding_main_authority_is_detected(self):
        original_init = ExtensionModel.__init__
        def broken_init(model):
            original_init(model)
            recovery = [body for key, op, body in model.effects["eon_eu_extension_legacy_short_timeout"] if key == "if"][0]
            choice = [body for key, op, body in recovery if key == "if"][0]
            one(choice, "limit")[:] = [("always", "=", "no")]
        with patch.object(ExtensionModel, "__init__", broken_init):
            self.rejects("test_short_legacy_timeout_before_first_daily_keeps_still_active_main_clock", lambda model: None)


class NewsMutationGuard(unittest.TestCase):
    def test_generic_remove_callback_false_revocation_is_detected(self):
        case = RevocationNewsControls("test_agreed_exit_and_later_remove_callbacks_never_announce_revocation")
        case.setUp()
        actual = case.m.legacy["EU_exit"]
        index = next(i for i, node in enumerate(actual) if node[0] == "remove_effect")
        actual[index] = ("remove_effect", "=", [("news_event", "=", [("id", "=", "EU_news.22")])])
        with self.assertRaises(AssertionError):
            case.test_agreed_exit_and_later_remove_callbacks_never_announce_revocation()


def load_tests(loader, tests, pattern):
    # Imported acceptance classes are fixtures, not another suite to recount.
    return unittest.TestSuite((loader.loadTestsFromTestCase(MutationGuards),
                               loader.loadTestsFromTestCase(NewsMutationGuard)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
