"""Execute current production EU extension AST, not staged helpers or game time.

Native mission presence and flag expiry are controlled inputs. Legacy finance,
office and full leaving_EU remain declared shared-model boundaries. News records
are API call receipts; they do not prove rendering, multiplayer UX or campaign.
"""
from pathlib import Path
import importlib.util
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("eon_extension_public_model", ROOT / "tools/validation/eu_membership/test_lifecycle.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
Model, ast, one = module.Model, module.ast, module.one
PROTO = GAME_INPUT_ROOT = ROOT
EFFECTS = "common/scripted_effects/eon_eu_withdrawal_extension_effects.txt"
TRIGGERS = "common/scripted_triggers/eon_eu_withdrawal_extension_triggers.txt"
DECISIONS = "common/decisions/eon_eu_withdrawal_extension_decisions.txt"
EVENTS = "events/eon_eu_withdrawal_extension_events.txt"
CALL = lambda key: (key, "=", "yes")


def find(nodes, key):
    for name, op, value in nodes:
        if name == key:
            return value
        if isinstance(value, list):
            result = find(value, key)
            if result is not None:
                return result


class ExtensionModel(Model):
    def __init__(self):
        super().__init__()
        source = ast((ROOT / "common/decisions/EU_voting_decisions.txt").read_text("utf-8-sig"))
        self.legacy = {ident: find(source, ident) for ident in ("EU_exit", "EU_exit_three_month")}

    def advance_flag_days(self, days):
        # Explicit boundary inputs, never native elapsed-calendar proof.
        for nation in self.nations.values():
            for key, remaining in list(nation.flag_days.items()):
                remaining -= days
                if remaining <= 0:
                    nation.flag_days.pop(key, None)
                    nation.flags.discard(key)
                else:
                    nation.flag_days[key] = remaining

    def timeout(self, ident, who=1):
        self.sender = who
        self.temp = {}
        self.effect(one(self.legacy[ident], "timeout_effect"), [self.nations[who]])

    def actual_remove_callback(self, ident, who=1):
        # Execute actual remove_effect AST as a callback ordering control. This
        # deliberately makes no claim that the interpreter schedules missions.
        self.sender = who
        self.temp = {}
        self.effect(one(self.legacy[ident], "remove_effect"), [self.nations[who]])

    def perform_decision(self, ident, who=1, from_id=1):
        action = one(one(ast((ROOT / DECISIONS).read_text("utf-8")), "eon_eu_membership_category"), ident)
        self.sender, self.from_id = who, from_id
        stack = [self.nations[who]]
        if not self.trigger(one(action, "visible"), stack) or not self.trigger(one(action, "available"), stack):
            return False
        if any(key == "target_trigger" for key, op, value in action):
            if not self.trigger(one(action, "target_root_trigger"), stack) or not self.trigger(one(action, "target_trigger"), stack):
                return False
        self.effect(one(action, "complete_effect"), stack)
        return True


class ExtensionLifecycle(unittest.TestCase):
    def setUp(self):
        self.m = ExtensionModel()
        self.m.members((1, 2, 3))
        self.m.call("eon_eu_notify_withdrawal", 1)
        self.c = self.m.nations[1]

    def propose(self):
        self.m.call("eon_eu_extension_propose", 1)

    def approvals(self):
        self.m.call("eon_eu_extension_approve", 2, 1)
        self.m.call("eon_eu_extension_approve", 3, 1)

    def agreement(self):
        self.propose()
        self.approvals()
        self.m.call("eon_eu_extension_accept_final", 1)

    def test_proposal_never_grants_extension_or_resets_remaining_period(self):
        self.m.advance_flag_days(81)
        self.propose()
        self.assertEqual(self.c.flag_days["eon_eu_withdrawal_deadline"], 649)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)
        self.assertEqual(self.c.flag_days["eon_eu_extension_proposal_window"], 30)

    def test_partial_unanimity_never_queues(self):
        self.propose()
        self.m.call("eon_eu_extension_approve", 2, 1)
        self.m.call("eon_eu_extension_accept_final", 1)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)
        self.assertNotIn("eon_eu_extension_council_consent", self.c.flags)

    def test_explicit_abstention_does_not_veto_unanimity_but_missing_response_does(self):
        self.propose()
        self.m.call("eon_eu_extension_approve", 2, 1)
        self.m.call("eon_eu_extension_accept_final", 1)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)
        self.m.call("eon_eu_extension_abstain", 3, 1)
        self.m.call("eon_eu_extension_accept_final", 1)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 1)

    def test_all_explicit_abstentions_still_require_separate_leaver_acceptance(self):
        self.propose()
        self.m.call("eon_eu_extension_abstain", 2, 1)
        self.m.call("eon_eu_extension_abstain", 3, 1)
        self.assertIn("eon_eu_extension_council_consent", self.c.flags)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)
        self.m.call("eon_eu_extension_accept_final", 1)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 1)

    def test_zero_other_eligible_governments_is_not_unanimity(self):
        self.m.nations[2].ideas.add("EUU_voting_rights_suspended")
        self.m.nations[3].ideas.add("EUU_voting_rights_suspended")
        self.propose()
        self.m.call("eon_eu_extension_accept_final", 1)
        self.assertEqual(self.c.variables["eon_eu_extension_electorate_total"], 0)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)

    def test_unanimity_requires_separate_withdrawing_state_final_acceptance(self):
        self.propose()
        self.approvals()
        self.assertIn("eon_eu_extension_council_consent", self.c.flags)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)
        self.assertIn("EU_member", self.c.ideas)

    def test_final_acceptance_does_not_consume_or_reset_remaining_period(self):
        self.m.advance_flag_days(115)
        self.agreement()
        self.assertEqual(self.c.flag_days["eon_eu_withdrawal_deadline"], 615)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 1)
        self.assertNotIn("withdrawal_treaty", self.c.ideas)
        self.assertNotIn("eon_eu_withdrawal_ep_consent", self.c.flags)

    def test_exact_one_unit_consumed_only_when_current_period_expires(self):
        self.agreement()
        self.m.call("eon_eu_force_deadline_withdrawal", 1)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 1)
        self.assertEqual(self.c.flag_days["eon_eu_withdrawal_deadline"], 730)
        self.m.advance_flag_days(730)
        self.m.call("eon_eu_force_deadline_withdrawal", 1)
        self.assertIn("EU_member", self.c.ideas)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)
        self.assertEqual(self.c.flag_days["eon_eu_withdrawal_deadline"], 365)
        self.m.call("eon_eu_force_deadline_withdrawal", 1)
        self.assertIn("EU_member", self.c.ideas)
        self.assertEqual(self.c.flag_days["eon_eu_withdrawal_deadline"], 365)

    def test_second_expiry_without_new_agreement_exits_and_cleans_queue(self):
        self.agreement()
        self.m.advance_flag_days(730)
        self.m.call("eon_eu_force_deadline_withdrawal", 1)
        self.m.advance_flag_days(365)
        self.m.call("eon_eu_force_deadline_withdrawal", 1)
        self.assertNotIn("EU_member", self.c.ideas)
        self.assertIn("no_deal_exit", self.c.ideas)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)
        self.assertNotIn("eon_eu_extension_notice_initialized", self.c.flags)

    def test_one_queue_cap_and_final_replay_are_inert(self):
        self.agreement()
        serial = self.c.variables["eon_eu_extension_proposal_serial"]
        self.m.call("eon_eu_extension_accept_final", 1)
        self.propose()
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 1)
        self.assertEqual(self.c.variables["eon_eu_extension_proposal_serial"], serial)
        self.assertNotIn("eon_eu_extension_proposal", self.c.flags)

    def test_new_project_after_consumption_requires_fresh_answers(self):
        self.agreement()
        self.m.advance_flag_days(730)
        self.m.call("eon_eu_force_deadline_withdrawal", 1)
        previous = self.c.variables["eon_eu_extension_proposal_serial"]
        self.propose()
        self.m.call("eon_eu_extension_accept_final", 1)
        self.assertEqual(self.c.variables["eon_eu_extension_proposal_serial"], previous + 1)
        self.assertEqual(self.c.arrays["eon_eu_extension_approvals"], [])
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)

    def test_rejection_abstention_and_reapproval_change_only_current_country_answer(self):
        self.propose()
        self.approvals()
        self.m.call("eon_eu_extension_reject", 2, 1)
        self.assertEqual(self.c.arrays["eon_eu_extension_approvals"], [3])
        self.assertEqual(self.c.arrays["eon_eu_extension_rejections"], [2])
        self.assertNotIn("eon_eu_extension_council_consent", self.c.flags)
        self.m.call("eon_eu_extension_abstain", 2, 1)
        self.assertEqual(self.c.arrays["eon_eu_extension_rejections"], [])
        self.assertEqual(self.c.arrays["eon_eu_extension_abstentions"], [2])
        self.assertIn("eon_eu_extension_council_consent", self.c.flags)
        self.m.call("eon_eu_extension_approve", 2, 1)
        self.assertEqual(self.c.arrays["eon_eu_extension_abstentions"], [])
        self.assertIn("eon_eu_extension_council_consent", self.c.flags)

    def test_explicit_abstention_is_deduplicated_and_replaced_by_rejection_or_approval(self):
        self.propose()
        for unused in range(3):
            self.m.call("eon_eu_extension_abstain", 2, 1)
        self.assertEqual(self.c.arrays["eon_eu_extension_abstentions"], [2])
        self.assertEqual(self.c.variables["eon_eu_extension_answer_count"], 1)
        self.assertNotIn("eon_eu_extension_council_consent", self.c.flags)
        self.m.call("eon_eu_extension_reject", 2, 1)
        self.assertEqual(self.c.arrays["eon_eu_extension_abstentions"], [])
        self.assertEqual(self.c.arrays["eon_eu_extension_rejections"], [2])
        self.m.call("eon_eu_extension_approve", 2, 1)
        self.assertEqual(self.c.arrays["eon_eu_extension_rejections"], [])
        self.assertEqual(self.c.arrays["eon_eu_extension_approvals"], [2])

    def test_duplicate_approve_reject_do_not_duplicate_ids(self):
        self.propose()
        for unused in range(3):
            self.m.call("eon_eu_extension_approve", 2, 1)
        self.assertEqual(self.c.arrays["eon_eu_extension_approvals"], [2])
        for unused in range(3):
            self.m.call("eon_eu_extension_reject", 2, 1)
        self.assertEqual(self.c.arrays["eon_eu_extension_approvals"], [])
        self.assertEqual(self.c.arrays["eon_eu_extension_rejections"], [2])

    def test_withdrawing_state_and_outsider_cannot_cast_government_assent(self):
        self.propose()
        self.m.call("eon_eu_extension_approve", 1, 1)
        self.m.call("eon_eu_extension_approve", 4.02446, 1)
        self.assertEqual(self.c.arrays["eon_eu_extension_approvals"], [])

    def test_suspended_member_cannot_answer_and_is_excluded_from_required_unanimity(self):
        self.m.nations[3].ideas.add("EUU_voting_rights_suspended")
        self.propose()
        self.m.call("eon_eu_extension_approve", 3, 1)
        self.m.call("eon_eu_extension_approve", 2, 1)
        self.m.call("eon_eu_extension_accept_final", 1)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 1)

    def test_restored_government_rights_are_recounted_at_final(self):
        self.m.nations[3].ideas.add("EUU_voting_rights_suspended")
        self.propose()
        self.m.call("eon_eu_extension_approve", 2, 1)
        self.assertIn("eon_eu_extension_council_consent", self.c.flags)
        self.m.nations[3].ideas.remove("EUU_voting_rights_suspended")
        self.m.call("eon_eu_extension_accept_final", 1)
        self.assertNotIn("eon_eu_extension_council_consent", self.c.flags)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)

    def test_new_member_requires_its_own_answer_including_fractional_id(self):
        self.propose()
        self.approvals()
        self.m.members((1, 2, 3, 4.02446))  # Explicit legal admission fixture; never a stray idea.
        self.m.call("eon_eu_extension_accept_final", 1)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)
        self.m.call("eon_eu_extension_approve", 4.02446, 1)
        self.assertIn(4.02446, self.c.arrays["eon_eu_extension_approvals"])
        self.m.call("eon_eu_extension_accept_final", 1)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 1)

    def test_departed_government_is_not_required_and_stale_ids_do_not_count_twice(self):
        self.propose()
        self.m.call("eon_eu_extension_approve", 2, 1)
        self.c.arrays["eon_eu_extension_approvals"].extend([2, 4.02446])
        self.m.nations[3].ideas.remove("EU_member")
        self.m.call("eon_eu_extension_accept_final", 1)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 1)

    def test_late_response_and_final_acceptance_after_project_expiry_are_inert(self):
        self.propose()
        self.approvals()
        self.m.advance_flag_days(30)
        self.m.call("eon_eu_extension_reject", 2, 1)
        self.m.call("eon_eu_extension_accept_final", 1)
        self.assertEqual(self.c.arrays["eon_eu_extension_rejections"], [])
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)
        self.m.call("eon_eu_extension_daily_pulse", 1)
        self.assertNotIn("eon_eu_extension_proposal", self.c.flags)
        self.assertEqual(self.c.flag_days["eon_eu_extension_cooldown"], 90)
        self.assertEqual(self.c.arrays["eon_eu_extension_approvals"], [])

    def test_expiry_cooldown_does_not_restart_on_repeated_daily_pass(self):
        self.propose()
        self.m.advance_flag_days(30)
        self.m.call("eon_eu_extension_daily_pulse", 1)
        self.m.advance_flag_days(4)
        self.m.call("eon_eu_extension_daily_pulse", 1)
        self.assertEqual(self.c.flag_days["eon_eu_extension_cooldown"], 86)
        self.assertFalse(self.m.test("eon_eu_extension_can_propose", 1))
        self.m.advance_flag_days(86)
        self.assertTrue(self.m.test("eon_eu_extension_can_propose", 1))

    def test_cancel_project_preserves_article50_and_remaining_time(self):
        self.propose()
        self.m.call("eon_eu_extension_cancel_proposal", 1)
        self.assertIn("Article_50", self.c.flags)
        self.assertIn("EU_member", self.c.ideas)
        self.assertEqual(self.c.flag_days["eon_eu_withdrawal_deadline"], 730)
        self.assertEqual(self.c.flag_days["eon_eu_extension_cooldown"], 90)

    def test_revoke_clears_queue_and_invalidates_monotonic_notice_once(self):
        self.agreement()
        old_serial = self.c.variables["eon_eu_extension_notice_serial"]
        self.m.call("eon_eu_revoke_withdrawal", 1)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)
        self.assertGreater(self.c.variables["eon_eu_extension_notice_serial"], old_serial)
        invalid_serial = self.c.variables["eon_eu_extension_notice_serial"]
        self.m.call("eon_eu_extension_daily_pulse", 1)
        self.m.call("eon_eu_extension_daily_pulse", 1)
        self.assertEqual(self.c.variables["eon_eu_extension_notice_serial"], invalid_serial)

    def test_later_notice_cannot_inherit_queue_or_old_project_answers(self):
        self.agreement()
        old = self.c.variables["eon_eu_extension_notice_serial"]
        self.m.call("eon_eu_revoke_withdrawal", 1)
        self.m.advance_flag_days(180)
        self.m.call("eon_eu_notify_withdrawal", 1)
        self.assertGreater(self.c.variables["eon_eu_extension_notice_serial"], old)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)
        self.assertEqual(self.c.arrays["eon_eu_extension_approvals"], [])
        self.assertEqual(self.c.flag_days["eon_eu_withdrawal_deadline"], 730)

    def test_stale_queued_notice_serial_cannot_extend_deadline(self):
        self.agreement()
        self.c.variables["eon_eu_extension_notice_serial"] += 1
        self.m.advance_flag_days(730)
        self.m.call("eon_eu_force_deadline_withdrawal", 1)
        self.assertNotIn("EU_member", self.c.ideas)

    def test_stale_project_notice_serial_blocks_responses_and_final(self):
        self.propose()
        self.c.variables["eon_eu_extension_project_notice_serial"] += 1
        self.approvals()
        self.m.call("eon_eu_extension_accept_final", 1)
        self.assertEqual(self.c.arrays["eon_eu_extension_approvals"], [])
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)

    def test_stale_queue_project_serial_cannot_extend_deadline(self):
        self.agreement()
        self.c.variables["eon_eu_extension_queued_proposal_serial"] += 1
        self.m.advance_flag_days(730)
        self.m.call("eon_eu_force_deadline_withdrawal", 1)
        self.assertNotIn("EU_member", self.c.ideas)

    def test_old_save_native_exit_remaining_is_authoritative_not_new_730_days(self):
        self.m.call("eon_eu_extension_clear_notice", 1)
        self.c.flags.discard("eon_eu_withdrawal_clock_started")
        self.c.flags.discard("eon_eu_withdrawal_deadline")
        self.c.flag_days.pop("eon_eu_withdrawal_deadline", None)
        self.m.call("eon_eu_extension_migrate_clock", 1)
        self.assertIn("eon_eu_legacy_exit_clock_authoritative", self.c.flags)
        self.assertNotIn("eon_eu_withdrawal_deadline", self.c.flags)
        self.agreement()
        self.m.call("eon_eu_force_deadline_withdrawal", 1)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 1)
        self.m.timeout("EU_exit")
        self.assertIn("EU_member", self.c.ideas)
        self.assertEqual(self.c.flag_days["eon_eu_withdrawal_deadline"], 365)
        self.assertNotIn("eon_eu_legacy_exit_clock_authoritative", self.c.flags)

    def test_old_three_month_save_keeps_its_real_mission_until_callback(self):
        self.m.call("eon_eu_extension_clear_notice", 1)
        self.c.missions = {"EU_exit_three_month"}
        self.c.flags.discard("eon_eu_withdrawal_deadline")
        self.c.flag_days.pop("eon_eu_withdrawal_deadline", None)
        self.m.call("eon_eu_extension_migrate_clock", 1)
        self.agreement()
        self.m.call("eon_eu_extension_daily_pulse", 1)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 1)
        self.m.timeout("EU_exit_three_month")
        self.assertEqual(self.c.flag_days["eon_eu_withdrawal_deadline"], 365)

    def old_notice_without_extension_marker(self, missions):
        self.m = ExtensionModel()
        self.m.members((1, 2, 3))
        self.c = self.m.nations[1]
        self.m.sender = 1
        # Explicit saved legacy inputs. No current notify, no guessed date and
        # no manually called initializer; callbacks are the real expiry receipt.
        self.m.effect([("set_country_flag", "=", "Article_50")]
                      + [("activate_mission", "=", mission) for mission in missions], [self.c])

    def test_main_legacy_timeout_before_first_daily_recovers_known_expiry_without_new_period(self):
        self.old_notice_without_extension_marker(("EU_exit",))
        self.c.missions.discard("EU_exit")
        self.m.timeout("EU_exit")
        self.assertNotIn("EU_member", self.c.ideas)
        self.assertIn("no_deal_exit", self.c.ideas)
        self.assertNotIn("eon_eu_withdrawal_deadline", self.c.flag_days)

    def test_short_legacy_timeout_before_first_daily_keeps_still_active_main_clock(self):
        self.old_notice_without_extension_marker(("EU_exit", "EU_exit_three_month"))
        self.c.missions.discard("EU_exit_three_month")
        self.m.timeout("EU_exit_three_month")
        self.assertIn("EU_member", self.c.ideas)
        self.assertIn("eon_eu_extension_notice_initialized", self.c.flags)
        self.assertIn("eon_eu_legacy_exit_clock_authoritative", self.c.flags)
        self.assertNotIn("eon_eu_legacy_short_clock_authoritative", self.c.flags)
        self.assertNotIn("eon_eu_withdrawal_deadline", self.c.flag_days)
        self.c.missions.discard("EU_exit")
        self.m.timeout("EU_exit")
        self.assertNotIn("EU_member", self.c.ideas)

    def test_sole_short_legacy_timeout_before_first_daily_recovers_known_expiry(self):
        self.old_notice_without_extension_marker(("EU_exit_three_month",))
        self.c.missions.discard("EU_exit_three_month")
        self.m.timeout("EU_exit_three_month")
        self.assertNotIn("EU_member", self.c.ideas)
        self.assertIn("no_deal_exit", self.c.ideas)
        self.assertNotIn("eon_eu_withdrawal_deadline", self.c.flag_days)

    def test_new_initialized_notice_stale_legacy_callback_does_not_reset_serial_or_deadline(self):
        serial = self.c.variables["eon_eu_extension_notice_serial"]
        self.m.advance_flag_days(17)
        self.m.timeout("EU_exit")
        self.m.timeout("EU_exit_three_month")
        self.assertIn("EU_member", self.c.ideas)
        self.assertEqual(self.c.variables["eon_eu_extension_notice_serial"], serial)
        self.assertEqual(self.c.flag_days["eon_eu_withdrawal_deadline"], 713)

    def test_legacy_callbacks_after_actual_revoke_do_not_resurrect_old_notice(self):
        self.agreement()
        self.m.call("eon_eu_revoke_withdrawal", 1)
        invalid_serial = self.c.variables["eon_eu_extension_notice_serial"]
        self.m.timeout("EU_exit")
        self.m.timeout("EU_exit_three_month")
        self.assertIn("EU_member", self.c.ideas)
        self.assertNotIn("Article_50", self.c.flags)
        self.assertNotIn("eon_eu_extension_notice_initialized", self.c.flags)
        self.assertEqual(self.c.variables["eon_eu_extension_notice_serial"], invalid_serial)

    def test_secondary_three_month_clock_does_not_override_old_main_clock(self):
        self.m.call("eon_eu_extension_clear_notice", 1)
        self.c.missions = {"EU_exit", "EU_exit_three_month"}
        self.m.call("eon_eu_extension_migrate_clock", 1)
        self.agreement()
        self.m.timeout("EU_exit_three_month")
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 1)
        self.assertIn("eon_eu_legacy_exit_clock_authoritative", self.c.flags)

    def test_new_notice_old_mission_callback_cannot_bypass_extended_flag(self):
        self.agreement()
        self.m.advance_flag_days(730)
        self.m.call("eon_eu_force_deadline_withdrawal", 1)
        self.m.timeout("EU_exit")
        self.m.timeout("EU_exit_three_month")
        self.assertIn("EU_member", self.c.ideas)
        self.assertEqual(self.c.flag_days["eon_eu_withdrawal_deadline"], 365)

    def test_legacy_callback_then_daily_and_daily_then_callback_both_consume_once(self):
        for callback_first in (True, False):
            with self.subTest(callback_first=callback_first):
                self.setUp()
                self.m.call("eon_eu_extension_clear_notice", 1)
                self.m.call("eon_eu_extension_migrate_clock", 1)
                self.agreement()
                if callback_first:
                    self.m.timeout("EU_exit")
                    self.m.call("eon_eu_extension_daily_pulse", 1)
                else:
                    self.c.missions.discard("EU_exit")
                    self.m.call("eon_eu_extension_daily_pulse", 1)
                    self.m.timeout("EU_exit")
                self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)
                self.assertIn("EU_member", self.c.ideas)
                self.assertEqual(self.c.flag_days["eon_eu_withdrawal_deadline"], 365)

    def test_repeated_migration_preserves_serial_and_existing_positive_flag_remainder(self):
        self.m.call("eon_eu_extension_clear_notice", 1)
        self.c.missions.clear()
        self.m.advance_flag_days(123)
        self.m.call("eon_eu_extension_migrate_clock", 1)
        serial = self.c.variables["eon_eu_extension_notice_serial"]
        self.m.call("eon_eu_extension_migrate_clock", 1)
        self.assertEqual(self.c.variables["eon_eu_extension_notice_serial"], serial)
        self.assertEqual(self.c.flag_days["eon_eu_withdrawal_deadline"], 607)

    def test_known_old_clock_already_expired_without_mission_finishes_via_actual_daily_ast(self):
        # Actual notification followed by explicit previous-save boundary inputs:
        # the old version had a known clock but no extension fields. No AST is
        # replaced and no initializer is manually called before actual daily.
        self.m.call("eon_eu_extension_clear_notice", 1)
        self.assertNotIn("eon_eu_extension_notice_initialized", self.c.flags)
        self.assertIn("eon_eu_withdrawal_clock_started", self.c.flags)
        self.m.advance_flag_days(730)
        self.c.missions.discard("EU_exit")
        self.assertNotIn("eon_eu_withdrawal_deadline", self.c.flags)
        # Execute the actual production daily pulse, not a manually called begin_notice.
        self.m.call("eon_eu_daily_membership_pulse", 1)
        self.assertNotIn("EU_member", self.c.ideas)
        self.assertIn("no_deal_exit", self.c.ideas)
        self.assertNotIn("eon_eu_withdrawal_deadline", self.c.flags)
        self.assertNotIn("eon_eu_withdrawal_deadline", self.c.flag_days)
        self.assertNotIn("eon_eu_extension_notice_initialized", self.c.flags)

    def test_fake_article50_without_any_genuine_clock_does_not_create_new_period(self):
        self.m.call("eon_eu_extension_clear_notice", 1)
        self.c.missions.clear()
        self.c.flags.discard("eon_eu_withdrawal_clock_started")
        self.c.flags.discard("eon_eu_withdrawal_deadline")
        self.c.flag_days.pop("eon_eu_withdrawal_deadline", None)
        self.m.call("eon_eu_extension_migrate_clock", 1)
        self.propose()
        self.assertNotIn("eon_eu_extension_notice_initialized", self.c.flags)
        self.assertNotIn("eon_eu_withdrawal_deadline", self.c.flags)
        self.assertNotIn("eon_eu_extension_proposal", self.c.flags)

    def test_orphan_notice_deadline_is_inert_but_actual_revoke_decision_remains_available(self):
        self.m.call("eon_eu_extension_clear_notice", 1)
        self.c.missions.clear()
        self.c.flags.discard("eon_eu_withdrawal_clock_started")
        self.c.flags.discard("eon_eu_withdrawal_deadline")
        self.c.flag_days.pop("eon_eu_withdrawal_deadline", None)
        self.m.receipts.clear()
        self.m.call("eon_eu_force_deadline_withdrawal", 1)
        self.assertIn("EU_member", self.c.ideas)
        self.assertIn("Article_50", self.c.flags)
        self.assertNotIn("eon_eu_withdrawal_deadline", self.c.flags)
        self.assertNotIn("no_deal_exit", self.c.ideas)
        actions = one(ast((ROOT / "common/decisions/eon_eu_membership_decisions.txt").read_text("utf-8-sig")), "eon_eu_membership_category")
        action = one(actions, "eon_eu_revoke_withdrawal")
        self.m.sender = 1
        self.assertTrue(self.m.trigger(one(action, "visible"), [self.c]))
        self.assertTrue(self.m.trigger(one(action, "available"), [self.c]))
        self.m.effect(one(action, "complete_effect"), [self.c])
        self.assertIn("EU_member", self.c.ideas)
        self.assertNotIn("Article_50", self.c.flags)
        self.assertEqual([r for r in self.m.receipts if r[0] == "news"], [("news", 1, "EU_news.22", 1)])

    def test_full_access_cleanup_and_archive_clear_extension_states(self):
        self.agreement()
        self.m.call("eon_eu_clear_country_access", 1)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)
        self.assertNotIn("eon_eu_extension_notice_initialized", self.c.flags)
        self.setUp()
        self.agreement()
        for nation in self.m.nations.values():
            if "EU_member" in nation.ideas:
                nation.exists = False
        self.m.call("eon_eu_refresh_membership", 1)
        self.assertIn("eon_eu_dormant", self.m.global_owner.flags)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)

    def test_actual_agreed_withdrawal_chain_cleans_previously_queued_extension(self):
        self.agreement()
        self.m.call("eon_eu_propose_withdrawal_treaty", 1)
        self.m.call("eon_eu_approve_withdrawal_treaty", 2, 1)
        self.m.call("eon_eu_approve_withdrawal_treaty", 3, 1)
        self.m.call("eon_eu_support_own_withdrawal_ep", 1)
        self.m.call("eon_eu_finish_withdrawal", 1)
        self.assertNotIn("EU_member", self.c.ideas)
        self.assertIn("withdrawal_treaty", self.c.ideas)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)
        self.assertNotIn("eon_eu_extension_notice_initialized", self.c.flags)

    def test_actual_annex_membership_clause_uses_cleanup_and_preserves_other_countries(self):
        self.agreement()
        self.c.exists = False
        source = ast((GAME_INPUT_ROOT / "common/on_actions/01_on_actions.txt").read_text("utf-8-sig"))
        def clauses(nodes):
            for key, op, body in nodes:
                if key == "if" and find(one(body, "limit"), "has_idea") == "EU_member" and find(body, "leaving_EU") == "yes":
                    yield (key, op, body)
                if isinstance(body, list):
                    yield from clauses(body)
        matched = list(clauses(one(find(source, "on_annex"), "effect")))
        self.assertEqual(len(matched), 1)
        self.m.sender, self.m.from_id = 2, 1
        # Existing Council recount is an external receipt; this test is the annex membership clause.
        self.m.BOUNDARIES = self.m.BOUNDARIES | {"eon_eu_recount_council_vote"}
        self.m.effect(matched, [self.m.nations[2]])
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)
        self.assertNotIn("eon_eu_extension_notice_initialized", self.c.flags)
        self.assertIn("EU_member", self.m.nations[2].ideas)

    def test_actual_refounding_after_archive_does_not_restore_old_extension(self):
        self.agreement()
        for nation in self.m.nations.values():
            if "EU_member" in nation.ideas:
                nation.exists = False
        self.m.call("eon_eu_refresh_membership", 1)
        self.m.nations[1].exists = self.m.nations[2].exists = True
        self.m.call("eon_eu_propose_refounding", 1, 2)
        self.m.call("eon_eu_accept_refounding", 2, 1)
        self.assertIn("EU_member", self.c.ideas)
        self.assertNotIn("Article_50", self.c.flags)
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 0)
        self.assertNotIn("eon_eu_extension_notice_initialized", self.c.flags)

    def test_phase_start_notification_targets_other_humans_once_and_ok_never_votes(self):
        self.m.nations[3].ai = True
        self.m.receipts.clear()
        self.propose()
        self.propose()
        notices = [r for r in self.m.receipts if r[0] == "event" and r[2] == "eon_eu_withdrawal_extension.1"]
        self.assertEqual(notices, [("event", 2, "eon_eu_withdrawal_extension.1", 1)])
        event = next(v for k, op, v in ast((PROTO / EVENTS).read_text("utf-8"))
                     if k == "country_event" and one(v, "id") == "eon_eu_withdrawal_extension.1")
        option = one(event, "option")
        self.assertEqual(option, [("name", "=", "eon_eu_withdrawal_extension.ok")])
        self.assertEqual(self.c.arrays["eon_eu_extension_approvals"], [])

    def test_actual_targeted_decision_scope_and_separate_own_final_action(self):
        self.assertTrue(self.m.perform_decision("eon_eu_extension_propose", 1, 1))
        self.assertFalse(self.m.perform_decision("eon_eu_extension_approve", 1, 1))
        self.assertFalse(self.m.perform_decision("eon_eu_extension_approve", 4.02446, 1))
        self.assertTrue(self.m.perform_decision("eon_eu_extension_approve", 2, 1))
        self.assertTrue(self.m.perform_decision("eon_eu_extension_approve", 3, 1))
        self.assertFalse(self.m.perform_decision("eon_eu_extension_accept_final", 2, 1))
        self.assertTrue(self.m.perform_decision("eon_eu_extension_accept_final", 1, 1))
        self.assertEqual(self.c.variables["eon_eu_extension_queued_units"], 1)


class ProductionSourceContracts(unittest.TestCase):
    def test_scripts_have_no_bom_inclusive_shorthand_or_direct_loop_limit(self):
        seen_timed = []
        def walk(nodes):
            for key, op, value in nodes:
                self.assertNotIn(op, (">=", "<="))
                if key == "for_each_scope_loop":
                    self.assertNotIn("limit", [name for name, op, val in value])
                if key in ("set_country_flag", "set_global_flag") and isinstance(value, list) and any(name == "days" for name, op, val in value):
                    self.assertEqual(one(value, "value"), "1")
                    self.assertGreater(float(one(value, "days")), 0)
                    seen_timed.append(one(value, "flag"))
                if isinstance(value, list):
                    walk(value)
        for path in (ROOT / name for name in (EFFECTS, TRIGGERS, DECISIONS, EVENTS)):
            self.assertNotIn(b"\xef\xbb\xbf", path.read_bytes())
            walk(ast(path.read_text("utf-8")))
        self.assertEqual(len(seen_timed), 3)

    def test_all_ui_references_have_english_and_russian_bom_localisation(self):
        actions = one(ast((PROTO / DECISIONS).read_text("utf-8")), "eon_eu_membership_category")
        references = set()
        for key, op, value in actions:
            references.update((key, key + "_desc", key + "_requirements"))
        for key, op, event in ast((PROTO / EVENTS).read_text("utf-8")):
            if key == "country_event":
                references.update((one(event, "title"), one(event, "desc"), one(one(event, "option"), "name")))
        for language in ("english", "russian"):
            path = PROTO / f"localisation/{language}/eon_eu_withdrawal_extension_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            keys = re.findall(r"^ ([^ :]+):0 ", path.read_text("utf-8-sig"), re.M)
            self.assertEqual(len(keys), len(set(keys)))
            self.assertEqual(set(keys), references)
        self.assertEqual(len(references), 25)

    def test_all_events_are_information_only(self):
        for key, op, event in ast((PROTO / EVENTS).read_text("utf-8")):
            if key == "country_event":
                self.assertEqual(one(event, "is_triggered_only"), "yes")
                self.assertEqual([name for name, op, val in one(event, "option")], ["name"])
                self.assertNotIn("immediate", [name for name, op, val in event])

    def test_extension_has_no_ep_authority_and_does_not_restart_mission(self):
        source = (PROTO / EFFECTS).read_text("utf-8") + (PROTO / TRIGGERS).read_text("utf-8")
        self.assertNotIn("has_country_flag = eon_eu_withdrawal_ep_consent", source)
        self.assertNotIn("activate_mission", source)
        self.assertNotIn("add_days_mission_timeout", source)
        self.assertNotIn("days = 730 value", source)


class RevocationNewsControls(unittest.TestCase):
    def setUp(self):
        self.case = ExtensionLifecycle()
        self.case.setUp()
        self.m, self.c = self.case.m, self.case.c
        self.m.receipts.clear()

    def news(self):
        return [receipt for receipt in self.m.receipts if receipt[0] == "news" and receipt[2] == "EU_news.22"]

    def test_actual_revoke_once_and_replayed_remove_callbacks_emit_exactly_one_news(self):
        self.case.agreement()
        self.m.call("eon_eu_revoke_withdrawal", 1)
        self.m.call("eon_eu_revoke_withdrawal", 1)
        self.m.actual_remove_callback("EU_exit")
        self.m.actual_remove_callback("EU_exit_three_month")
        self.assertEqual(self.news(), [("news", 1, "EU_news.22", 1)])

    def test_agreed_exit_and_later_remove_callbacks_never_announce_revocation(self):
        self.case.test_actual_agreed_withdrawal_chain_cleans_previously_queued_extension()
        self.m.actual_remove_callback("EU_exit")
        self.m.actual_remove_callback("EU_exit_three_month")
        self.assertEqual(self.news(), [])

    def test_archive_and_no_deal_then_remove_callbacks_never_announce_revocation(self):
        for archive in (True, False):
            with self.subTest(archive=archive):
                self.setUp()
                if archive:
                    for nation in self.m.nations.values():
                        if "EU_member" in nation.ideas:
                            nation.exists = False
                    self.m.call("eon_eu_refresh_membership", 1)
                else:
                    self.m.advance_flag_days(730)
                    self.m.call("eon_eu_force_deadline_withdrawal", 1)
                self.m.actual_remove_callback("EU_exit")
                self.m.actual_remove_callback("EU_exit_three_month")
                self.assertEqual(self.news(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
