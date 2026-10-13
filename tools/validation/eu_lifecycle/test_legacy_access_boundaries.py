"""Execute admission/legacy timer counterexamples against production AST.

The shared bounded executor treats legacy budget calculations as receipts.
These tests prove access boundaries, never a running HOI4 campaign.
"""
from pathlib import Path
import importlib.util
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "eon_eu_admission_boundary_model",
    ROOT / "tools/validation/eu_membership/test_lifecycle.py",
)
SUPPORT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SUPPORT
SPEC.loader.exec_module(SUPPORT)
ast, one = SUPPORT.ast, SUPPORT.one

BUDGET_MISSIONS = (
    "EU_budget_yearly_timer", "EU_budget_draft_preparations",
    "EU_budget_draft_ongoing", "EU_budget_draft_ongoing_president",
    "EU_mff_yearly_timer", "EU_mff_draft_preparations",
    "EU_mff_draft_ongoing", "EU_mff_draft_ongoing_president",
)
MEMBER_RIGHT_MISSIONS = BUDGET_MISSIONS + (
    "EU_update_vars_mission", "EU_clear_voting_mission",
    "EU_election_2004", "EU_election_5_years",
    "EU_parliament_focus_EUXXX_approve",
    "EU_parliament_focus_EUXXX_approve_timer",
    "EU_voting_mission_focus_EUXXX_QMV_result",
    "EU_voting_mission_focus_EUXXX_QMV_result_timer",
    "eurozone_reforms", "troika_reforms", "EU_military_exercise_mission",
    "EU_exit", "EU_exit_three_month", "pre_accession_assistance_program",
)


def read(relative):
    return ast((ROOT / relative).read_text(encoding="utf-8-sig"))


def descend(nodes):
    for node in nodes:
        yield node
        if isinstance(node[2], list):
            yield from descend(node[2])


def action(ident, category="EU_parliament_category"):
    data = read("common/decisions/EU_voting_decisions.txt")
    matches = [v for k, op, category_body in data if isinstance(category_body, list)
               for name, op, v in category_body if name == ident]
    assert len(matches) == 1, (ident, len(matches))
    return matches[0]


class BoundaryModel(SUPPORT.Model):
    BOUNDARIES = SUPPORT.Model.BOUNDARIES | {
        "set_EU_gdp", "EU_save_budget_values", "EU_save_mff_values",
        "update_EU_budget_call_rate", "update_EU_average_eco_lvl",
        "EU_global_click_cost", "EU_country_call_rate_cost_calc",
        "reset_MEP_support_party_x", "all_MEP_support_draft",
        "assess_MEP_support_party_x", "news_event",
    }

    def effect(self, nodes, stack):
        # Native tooltips describe effects; they do not execute them.
        nodes = [node for node in nodes if node[0] != "effect_tooltip"]
        return super().effect(nodes, stack)


def active_model():
    model = BoundaryModel()
    model.members()
    for ident in (1, 2):
        model.nations[ident].flags.add("eon_eu_membership_recognized")
    model.global_owner.flags.add("eon_eu_admission_guard_ready")
    model.receipts.clear()  # Exclude setup refresh; witnesses begin at the tested callback.
    return model


class AdmissionBoundary(unittest.TestCase):
    def test_unapproved_runtime_grant_cannot_admit_an_outsider(self):
        model = active_model()
        model.effect([("add_ideas", "=", "EU_member")], [model.nations[3]])
        self.assertNotIn("EU_member", model.nations[3].ideas)
        self.assertNotIn(3, model.global_owner.arrays["EU_member"])

    def test_ex_member_cannot_reenter_through_a_stray_grant(self):
        model = active_model()
        model.call("leaving_EU", 1) if "leaving_EU" in model.effects else model.effect(
            [("leaving_EU", "=", "yes")], [model.nations[1]])
        model.sender = 1
        model.effect([("add_ideas", "=", "EU_member")], [model.nations[1]])
        self.assertNotIn("EU_member", model.nations[1].ideas)
        self.assertNotIn(1, model.global_owner.arrays["EU_member"])
        self.assertNotIn("eon_eu_membership_recognized", model.nations[1].flags)

    def test_rejected_stray_grant_preserves_a_legitimate_negotiation(self):
        model = active_model()
        nation = model.nations[3]
        nation.flags.update({"EU_candidate", "eon_eu_negotiation_period"})
        nation.variables["eon_eu_accession_phase"] = 2
        model.effect([("add_ideas", "=", "EU_member")], [nation])
        self.assertNotIn("EU_member", nation.ideas)
        self.assertIn("EU_candidate", nation.flags)
        self.assertIn("eon_eu_negotiation_period", nation.flags)
        self.assertEqual(nation.variables["eon_eu_accession_phase"], 2)

    def test_latent_history_idea_is_not_membership_when_a_country_appears(self):
        model = active_model()
        nation = model.nations[3]
        nation.ideas.add("EU_member")  # History was loaded while the country did not exist.
        nation.exists = False
        nation.owned = 0
        model.call("eon_eu_refresh_membership")
        nation.exists = True
        nation.owned = 1
        model.call("eon_eu_refresh_membership")
        self.assertNotIn(3, model.global_owner.arrays["EU_member"])
        self.assertNotIn("EU_member", nation.ideas)

    def test_explicit_commit_is_single_use_and_recognizes_the_member(self):
        model = active_model()
        nation = model.nations[3]
        nation.flags.add("eon_eu_admission_commit")
        model.effect([("add_ideas", "=", "EU_member")], [nation])
        self.assertIn("EU_member", nation.ideas)
        self.assertIn("eon_eu_membership_recognized", nation.flags)
        self.assertNotIn("eon_eu_admission_commit", nation.flags)
        self.assertEqual(model.global_owner.arrays["EU_member"].count(3), 1)

    def test_recognized_subordinated_member_recovers_existing_legal_membership(self):
        model = active_model()
        nation = model.nations[2]
        nation.subjects = True
        model.call("eon_eu_refresh_membership")
        self.assertIn("EU_member", nation.ideas)
        self.assertIn("eon_eu_membership_recognized", nation.flags)
        self.assertFalse(model.test("eon_eu_is_active_member", 2))
        nation.subjects = False
        model.call("eon_eu_refresh_membership")
        self.assertTrue(model.test("eon_eu_is_active_member", 2))

    def test_historical_bootstrap_is_explicit_and_closes_once(self):
        model = BoundaryModel()
        self.assertTrue("eon_eu_close_historical_admission" in model.effects,
                        "Historical admission has no explicit one-time closing boundary")
        model.nations[1].ideas.add("EU_member")
        model.nations[3].ideas.add("EU_member")
        model.nations[3].exists = False
        model.nations[3].owned = 0
        model.call("eon_eu_close_historical_admission", 1)
        self.assertIn("eon_eu_admission_guard_ready", model.global_owner.flags)
        self.assertIn("eon_eu_membership_recognized", model.nations[1].flags)
        self.assertNotIn("eon_eu_membership_recognized", model.nations[3].flags)
        model.nations[3].exists = True
        model.nations[3].owned = 1
        model.call("eon_eu_close_historical_admission", 1)
        self.assertNotIn("eon_eu_membership_recognized", model.nations[3].flags)

    def test_wartime_application_and_candidacy_are_not_automatic_membership(self):
        model = active_model()
        nation = model.nations[3]
        nation.wars.add(4.02446)
        self.assertTrue(model.test("eon_eu_application_ready"))
        model.call("eon_eu_apply_for_membership_start")
        self.assertEqual(nation.variables["eon_eu_accession_phase"], 1)
        self.assertNotIn("EU_member", nation.ideas)
        model.call("eon_eu_endorse_application", 1, 3)
        model.call("eon_eu_progress_accession")
        self.assertNotIn("EU_candidate", nation.flags)
        model.call("eon_eu_endorse_application", 2, 3)
        model.call("eon_eu_progress_accession")
        self.assertIn("EU_candidate", nation.flags)
        self.assertNotIn("EU_member", nation.ideas)

    def test_wartime_final_accession_still_requires_actual_consents(self):
        model = active_model()
        nation = model.nations[3]
        nation.wars.add(4.02446)
        nation.flags.add("EU_candidate")
        nation.variables["eon_eu_accession_phase"] = 2
        self.assertTrue(model.test("eon_eu_treaty_submission_ready"))
        model.call("eon_eu_submit_accession_treaty")
        model.call("eon_eu_ratify_member_accession", 1, 3)
        model.call("eon_eu_support_accession_ep", 1, 3)
        model.call("eon_eu_progress_accession")
        model.call("eon_eu_ratify_accession_treaty")
        self.assertNotIn("EU_member", nation.ideas)
        model.call("eon_eu_ratify_member_accession", 2, 3)
        model.call("eon_eu_progress_accession")
        model.call("eon_eu_ratify_accession_treaty")
        self.assertIn("EU_member", nation.ideas)
        self.assertIn("eon_eu_membership_recognized", nation.flags)


class LegacyMissionBoundary(unittest.TestCase):
    def test_exit_clears_all_existing_member_right_missions(self):
        model = active_model()
        nation = model.nations[1]
        nation.missions.update(MEMBER_RIGHT_MISSIONS)
        model.call("eon_eu_clear_country_access", 1)
        self.assertFalse(nation.missions.intersection(MEMBER_RIGHT_MISSIONS))

    def test_archiving_clears_stale_member_right_missions(self):
        model = active_model()
        for nation in model.nations.values():
            nation.missions.update(MEMBER_RIGHT_MISSIONS)
            nation.owned = 0
        model.call("eon_eu_refresh_membership")
        self.assertIn("eon_eu_dormant", model.global_owner.flags)
        for nation in model.nations.values():
            self.assertFalse(nation.missions.intersection(MEMBER_RIGHT_MISSIONS), nation.ident)

    def test_member_cleanup_preserves_an_independent_external_counter_exercise(self):
        model = active_model()
        model.nations[3].missions.add("counter_military_exercise_mission")
        model.call("eon_eu_clear_country_access", 3)
        self.assertIn("counter_military_exercise_mission", model.nations[3].missions)

    def test_lost_ecb_office_cannot_finish_a_presidential_budget_draft(self):
        model = active_model()
        nation = model.nations[1]
        model.sender = 1
        model.effect(one(action("EU_budget_draft_ongoing_president"), "timeout_effect"), [nation])
        self.assertNotEqual(model.global_owner.variables.get("current_active_agenda_disp"), 999)
        self.assertNotIn("EU_parliament_focus_EUXXX_approve", nation.missions)
        self.assertFalse(any(name == "set_EU_gdp" for name, *rest in model.receipts))

    def test_valid_current_ecb_holder_can_finish_a_presidential_budget_draft(self):
        model = active_model()
        nation = model.nations[1]
        nation.ideas.add("ECB_president")
        model.sender = 1
        model.effect(one(action("EU_budget_draft_ongoing_president"), "timeout_effect"), [nation])
        self.assertEqual(model.global_owner.variables.get("current_active_agenda_disp"), 999)
        self.assertIn("EU_parliament_focus_EUXXX_approve", nation.missions)

    def test_legacy_withdrawal_button_starts_the_real_proposal(self):
        model = active_model()
        model.call("eon_eu_notify_withdrawal", 1)
        model.sender = 1
        model.effect(one(action("EU_withdrawal_treaty"), "complete_effect"), [model.nations[1]])
        self.assertIn("eon_eu_withdrawal_proposal", model.nations[1].flags)
        self.assertNotIn("withdrawal_treaty", model.nations[1].flags)
        self.assertIn("EU_member", model.nations[1].ideas)


def _reject_stale_budget_callback(mission):
    def test(self):
        model = active_model()
        nation = model.nations[3]  # No membership and no office, even if a saved mission survives.
        model.sender = 3
        model.effect(one(action(mission), "timeout_effect"), [nation])
        self.assertFalse(model.receipts, "A former member executed a union-wide budget calculation/event")
        self.assertFalse(nation.missions.intersection(MEMBER_RIGHT_MISSIONS))
        self.assertNotIn("current_active_agenda_disp", model.global_owner.variables)
        self.assertFalse(any(flag.startswith("focus_EU") for flag in nation.flags))
    return test


for _mission in BUDGET_MISSIONS:
    setattr(LegacyMissionBoundary, "test_stale_timeout_" + _mission,
            _reject_stale_budget_callback(_mission))


class RuntimeGrantContracts(unittest.TestCase):
    def test_belarus_reward_starts_an_application_without_member_or_faction_rewards(self):
        body = one(one(read("common/decisions/Belarus.txt"), "BLR_euroitegration"), "blr_eu_join")
        complete = one(body, "complete_effect")
        self.assertIn(("eon_eu_apply_for_membership_start", "=", "yes"), list(descend(complete)))
        self.assertNotIn(("add_ideas", "=", "EU_member"), list(descend(complete)))
        self.assertFalse({"add_to_faction", "EU_clear_voting"}.intersection(k for k, op, v in descend(complete)))

    def test_hungarian_referendum_is_an_application_not_external_admission(self):
        event = next(v for k, op, v in read("events/Hungary.txt")
                     if k == "country_event" and one(v, "id") == "hungary_hsp.2")
        option = one(event, "option")
        self.assertIn(("eon_eu_apply_for_membership_start", "=", "yes"), list(descend(option)))
        self.assertNotIn(("add_ideas", "=", "EU_member"), list(descend(option)))
        self.assertNotIn(("EU_clear_voting", "=", "yes"), list(descend(option)))

    def test_bootstrap_guard_is_called_from_a_real_startup_hook(self):
        hooks = []
        for path in (ROOT / "common/on_actions").glob("*.txt"):
            for key, op, value in descend(ast(path.read_text(encoding="utf-8-sig"))):
                if key == "on_startup":
                    hooks.extend(descend(value))
        self.assertTrue(("on_startup_euu_action", "=", "yes") in hooks,
                        "Real startup does not call the EU startup helper")
        startup = one(read("common/scripted_effects/00_eu_scripted_effects.txt"), "on_startup_euu_action")
        keys = [k for k, op, v in descend(startup)]
        self.assertLess(keys.index("eon_eu_close_historical_admission"),
                        keys.index("eon_eu_refresh_membership"))


class StartupBoundaryModel(BoundaryModel):
    def __init__(self):
        super().__init__()
        self.disable_rule = False

    def trigger(self, nodes, stack):
        for node in nodes:
            if node[0] == "has_game_rule":
                if not (one(node[2], "rule") == "rule_disable_eu" and self.disable_rule):
                    return False
            elif not super().trigger([node], stack):
                return False
        return True

    def effect(self, nodes, stack):
        expanded = []
        for key, op, value in nodes:
            if key == "remove_ideas" and isinstance(value, list):
                expanded.extend((key, op, v) for k, op, v in value)
            else:
                expanded.append((key, op, value))
        return super().effect(expanded, stack)

    def real_startup_admission_boundary(self):
        # Execute the actual disable-rule/history-stamp startup prefix. Voting-rule
        # UI/cache configuration is outside this admission model; then use the
        # actual first refresh call found in that same production startup effect.
        startup = one(read("common/scripted_effects/00_eu_scripted_effects.txt"), "on_startup_euu_action")
        end = next(i for i, n in enumerate(startup) if n[0] == "eon_eu_close_historical_admission")
        self.sender = 1
        self.effect(startup[:end + 1], [self.nations[1]])
        refresh = next(n for n in descend(startup) if n[0] == "eon_eu_refresh_membership")
        self.effect([refresh], [self.nations[1]])


class ActualStartupAdmission(unittest.TestCase):
    def loaded(self):
        model = StartupBoundaryModel()
        for ident in (1, 2):
            model.sender = ident
            model.effect([("add_ideas", "=", "EU_member")], [model.nations[ident]])
        return model

    def test_history_callbacks_defer_then_actual_startup_preserves_loaded_members(self):
        model = self.loaded()
        self.assertNotIn("eon_eu_dormant", model.global_owner.flags)
        self.assertEqual(model.global_owner.arrays.get("EU_member", []), [])
        model.real_startup_admission_boundary()
        self.assertEqual(model.global_owner.arrays["EU_member"], [1, 2])
        self.assertNotIn("eon_eu_dormant", model.global_owner.flags)
        for ident in (1, 2):
            self.assertIn("eon_eu_membership_recognized", model.nations[ident].flags)

    def test_old_save_loaded_members_are_recognized_only_at_first_startup_boundary(self):
        model = self.loaded()
        model.nations[3].ideas.add("EU_member")
        model.real_startup_admission_boundary()
        self.assertEqual(model.global_owner.arrays["EU_member"], [1, 2, 3])
        model.sender = 4.02446
        model.effect([("add_ideas", "=", "EU_member")], [model.nations[4.02446]])
        self.assertNotIn("EU_member", model.nations[4.02446].ideas)

    def test_disabled_eu_real_startup_never_restores_ideas_or_recognition(self):
        model = self.loaded()
        model.disable_rule = True
        model.real_startup_admission_boundary()
        self.assertEqual(model.global_owner.arrays["EU_member"], [])
        self.assertIn("GAME_RULE_eu_disabled", model.global_owner.flags)
        for nation in model.nations.values():
            self.assertNotIn("EU_member", nation.ideas)
            self.assertNotIn("eon_eu_membership_recognized", nation.flags)

    def test_latent_nonexisting_history_country_cannot_gain_rights_later(self):
        model = self.loaded()
        nation = model.nations[3]
        nation.ideas.add("EU_member")
        nation.exists = False
        nation.owned = 0
        model.real_startup_admission_boundary()
        self.assertNotIn("eon_eu_membership_recognized", nation.flags)
        nation.exists = True
        nation.owned = 1
        model.call("eon_eu_refresh_membership")
        self.assertNotIn("EU_member", nation.ideas)
        self.assertNotIn(3, model.global_owner.arrays["EU_member"])


class DailyLoadBoundaryModel(StartupBoundaryModel):
    # Admission and registry helpers execute actual production AST. Adjacent
    # voting, budget, office and EDU identity systems are explicit receipts for
    # this admission boundary. Dedicated EDU source/native suites must execute
    # eon_edu_daily_pulse; this model cannot establish its faction behavior.
    BOUNDARIES = StartupBoundaryModel.BOUNDARIES | {
        "eon_eu_recount_council_vote", "eon_eu_update_parliament",
        "eon_eu_daily_institutions_pulse", "eon_eu_update_budget",
        "eon_eu_council_ai_pulse",
        # Legislative scheduling is an explicit adjacent-system boundary here;
        # Council/EP actual-source suites and native modules test these helpers.
        "eon_eu_capture_council_deadline_outcome", "eon_eu_ep_capture_deadline_outcome",
        "eon_eu_reconcile_council_vote_owner", "eon_eu_ep_reconcile_owner",
        "eon_edu_daily_pulse",
    }
    def effect(self, nodes, stack):
        # These boundary tests represent positive flags, never native timer expiry.
        normalized = []
        for key, op, value in nodes:
            if key == 'set_global_flag' and isinstance(value, list):
                assert one(value, 'value') == '1', 'Require explicit native-positive timed flag'
                value = one(value, 'flag')
            normalized.append((key, op, value))
        return super().effect(normalized, stack)

    def __init__(self):
        super().__init__()
        self.effects['eon_eu_daily_lifecycle_pulse'] = one(
            read('common/scripted_effects/eon_eu_lifecycle_effects.txt'),
            'eon_eu_daily_lifecycle_pulse')


class DailyOldSaveAdmission(unittest.TestCase):
    def loaded_without_startup(self):
        model = DailyLoadBoundaryModel()
        # Prior loaded save is an explicit input, not an on_startup simulation.
        for ident in (1, 2):
            model.nations[ident].ideas.add('EU_member')
        return model

    def test_first_actual_daily_adopts_loaded_members_then_closes_raw_grants(self):
        model = self.loaded_without_startup()
        model.call('eon_eu_daily_lifecycle_pulse')
        self.assertIn('eon_eu_admission_guard_ready', model.global_owner.flags)
        self.assertEqual([1, 2], model.global_owner.arrays['EU_member'])
        for ident in (1, 2):
            self.assertIn('eon_eu_membership_recognized', model.nations[ident].flags)
        model.sender = 4.02446
        model.effect([('add_ideas', '=', 'EU_member')], [model.nations[4.02446]])
        self.assertNotIn('EU_member', model.nations[4.02446].ideas)

    def test_post_load_guard_closes_even_while_prior_daily_lock_is_positive(self):
        model = self.loaded_without_startup()
        model.global_owner.flags.add('eon_eu_daily_lifecycle_done')
        model.call('eon_eu_daily_lifecycle_pulse')
        self.assertIn('eon_eu_admission_guard_ready', model.global_owner.flags)
        for ident in (1, 2):
            self.assertIn('eon_eu_membership_recognized', model.nations[ident].flags)
        model.global_owner.flags.remove('eon_eu_daily_lifecycle_done')
        model.call('eon_eu_daily_lifecycle_pulse')
        self.assertEqual([1, 2], model.global_owner.arrays['EU_member'])

    def test_later_daily_does_not_adopt_a_stray_grant_after_boundary_closed(self):
        model = self.loaded_without_startup()
        model.call('eon_eu_daily_lifecycle_pulse')
        model.nations[3].ideas.add('EU_member')
        model.global_owner.flags.remove('eon_eu_daily_lifecycle_done')
        model.call('eon_eu_daily_lifecycle_pulse')
        self.assertNotIn('EU_member', model.nations[3].ideas)
        self.assertNotIn(3, model.global_owner.arrays['EU_member'])


if __name__ == "__main__":
    unittest.main(verbosity=2)
