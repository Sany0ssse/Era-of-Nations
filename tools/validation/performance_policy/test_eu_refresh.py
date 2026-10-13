"""Bounded differential execution of the actual EU roster/population AST.

Legacy Parliament allocation, Council tallies and later lifecycle stages are
explicit stateful doubles. A separate recursive source contract proves that
the intervening production stages do not alter roster/population inputs.
Every modeled persistent field and external call receipt is compared, except
the documented GUI invalidation serial; this is not native campaign or FPS proof.
"""
from copy import deepcopy
from dataclasses import asdict
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location(
    "eon_performance_membership_model", ROOT / "tools/validation/eu_membership/test_lifecycle.py")
public = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = public
spec.loader.exec_module(public)
ast, one, BaseModel = public.ast, public.one, public.Model

MEMBER = ROOT / "common/scripted_effects/eon_eu_membership_effects.txt"
LIFECYCLE = ROOT / "common/scripted_effects/eon_eu_lifecycle_effects.txt"
OLD_MEMBER = HERE / "fixtures/eu_eon_eu_membership.txt_baseline.txt"
OLD_LIFECYCLE = HERE / "fixtures/eu_eon_eu_lifecycle.txt_baseline.txt"
CALL = lambda name: (name, "=", "yes")
NEW_HELPER = "eon_eu_daily_membership_update"
DIRTY = "EU_dirty_update_var"


def definitions(path):
    return {key: value for key, _, value in ast(path.read_text("utf-8-sig"))}


def desired_membership(source):
    result = deepcopy(ast(source))
    at = next(i for i, row in enumerate(result) if row[0] == "eon_eu_daily_membership_pulse")
    old = result[at][2]
    assert old[0] == CALL("eon_eu_refresh_membership")
    result[at] = ("eon_eu_daily_membership_pulse", "=", [old[0], CALL(NEW_HELPER)])
    result.insert(at + 1, (NEW_HELPER, "=", old[1:]))
    return result


def desired_lifecycle(source):
    result = deepcopy(ast(source))
    body = one(one(result, "eon_eu_daily_lifecycle_pulse"), "if")
    at = next(i for i, row in enumerate(body) if row == CALL("eon_eu_daily_membership_pulse"))
    body[at] = CALL(NEW_HELPER)
    return result


def desired_file_bytes(member, lifecycle):
    old = b"eon_eu_daily_membership_pulse = {\r\n eon_eu_refresh_membership = yes\r\n"
    new = old + b" eon_eu_daily_membership_update = yes\r\n}\r\n" \
        b"# Internal daily step; the lifecycle caller has refreshed the legal registry.\r\n" \
        b"eon_eu_daily_membership_update = {\r\n"
    assert member.count(old) == 1
    old_call = b"\t\teon_eu_daily_membership_pulse = yes\n"
    assert lifecycle.count(old_call) == 1
    return member.replace(old, new), lifecycle.replace(old_call, b"\t\teon_eu_daily_membership_update = yes\n")


class Runtime(BaseModel):
    """Closed roster/population execution, with named external boundaries."""
    STAGES = {
        "eon_eu_capture_council_deadline_outcome", "eon_eu_ep_capture_deadline_outcome",
        "eon_eu_recount_council_vote", "eon_eu_update_parliament", "eon_edu_daily_pulse",
        "eon_eu_daily_institutions_pulse", "eon_eu_reconcile_council_vote_owner",
        "eon_eu_ep_reconcile_owner", "eon_eu_update_budget", "eon_eu_council_ai_pulse",
    }

    def __init__(self, mode="live"):
        super().__init__()
        self.refreshes = 0
        self.date = 20000101
        member = ast(OLD_MEMBER.read_text("utf-8-sig")) if mode != "live" else ast(MEMBER.read_text("utf-8-sig"))
        lifecycle = ast(OLD_LIFECYCLE.read_text("utf-8-sig")) if mode != "live" else ast(LIFECYCLE.read_text("utf-8-sig"))
        if mode == "desired":
            member = desired_membership(OLD_MEMBER.read_text("utf-8-sig"))
            lifecycle = desired_lifecycle(OLD_LIFECYCLE.read_text("utf-8-sig"))
        self.effects.update({key: val for key, _, val in member})
        self.effects["eon_eu_daily_lifecycle_pulse"] = one(lifecycle, "eon_eu_daily_lifecycle_pulse")
        legacy = definitions(ROOT / "common/scripted_effects/00_eu_scripted_effects.txt")
        for key in ("EU_update_vars", "update_eu_dirty_variable", "eu_screen_selection"):
            self.effects[key] = legacy[key]
        # Non-EU and dead countries test proper every_country filtering too.
        self.nations[5] = public.Nation(5, original_tag="CHI", state_populations=[300])
        self.nations[6] = public.Nation(6, original_tag="USA", state_populations=[90], exists=False)
        self.nations[1].state_populations = [55, 25]
        self.nations[2].state_populations = [60, 0]
        self.nations[1].variables["eurosceptic"] = -0.1
        self.nations[2].variables["eurosceptic"] = 1.3
        self.from_id = 4.02446
        self.global_owner.variables[DIRTY] = 9999

    def trigger(self, rows, stack):
        # This bounded Parliament double chooses fixtures at a real source gate.
        for key, op, val in rows:
            if key == "date":
                date = [int(part) for part in val.split(".")]
                date = date[0] * 10000 + date[1] * 100 + date[2]
                if not public.compare(self.date, op, date):
                    return False
            elif not super().trigger([(key, op, val)], stack):
                return False
        return True

    def effect(self, rows, stack):
        # Transform only additional documented numeric forms before delegating
        # control flow and actual membership/withdrawal to the existing model.
        groups = []
        for row in rows:
            if row[0] in ("else", "else_if"):
                assert groups and groups[-1][0][0] == "if"
                groups[-1].append(row)
            else:
                groups.append([row])
        for group in groups:
            key, op, val = group[0]
            if key == "eon_eu_refresh_membership":
                self.refreshes += 1
            if key in self.STAGES:
                self.stage(key, stack)
            elif key == "hidden_effect":
                self.effect(val, stack)
            elif key == "effect_tooltip":
                pass  # Native tooltip examples have no persistent effects.
            elif key in ("set_global_flag", "clr_global_flag") and isinstance(val, list):
                flag = one(val, "flag")
                if key == "set_global_flag":
                    assert one(val, "value") == "1"
                    self.global_owner.flags.add(flag)
                    self.global_owner.flag_days[flag] = self.value(one(val, "days"), stack)
                else:
                    self.global_owner.flags.discard(flag)
                    self.global_owner.flag_days.pop(flag, None)
            elif key in ("set_variable", "add_to_variable") and any(k == "var" for k, _, _ in val):
                super().effect([(key, op, [(one(val, "var"), "=", one(val, "value"))])], stack)
            elif key in ("multiply_variable", "divide_variable", "subtract_from_variable"):
                name, _, token = val[0]
                owner, name = self.slot(name, stack)
                value = self.value(token, stack)
                old = owner.variables.get(name, 0)
                if key == "multiply_variable": result = old * value
                elif key == "subtract_from_variable": result = old - value
                else:
                    assert value != 0
                    result = old / value
                owner.variables[name] = result
            elif key == "clamp_variable":
                owner, name = self.slot(one(val, "var"), stack)
                owner.variables[name] = min(self.value(one(val, "max"), stack),
                                            max(self.value(one(val, "min"), stack), owner.variables.get(name, 0)))
            elif key == "round_temp_variable":
                self.temp[val] = float(int(self.temp.get(val, 0) + 0.5))
            else:
                # Attached branches must travel together through the existing
                # interpreter. Execute each group before the next native command.
                super().effect(group, stack)

    def stage(self, name, stack):
        self.receipts.append((name, stack[-1].ident))
        g = self.global_owner
        if name == "eon_eu_recount_council_vote":
            g.variables["eon_eu_voters"] = len(g.arrays.get("EU_member", []))
        elif name == "eon_eu_update_parliament" and self.test("eon_eu_union_active", stack[-1].ident):
            if "eon_eu_membership_changed" in g.flags or "eon_eu_parliament_term" not in g.flags:
                # Stateful elected-seat double makes downstream treaty consent
                # change with delegation size. The real allocator is unchanged.
                for ident in g.arrays["EU_member"]:
                    country = self.nations[ident]
                    country.variables["MEP_Total"] = round(200 * country.variables.get("EU_pop_ratio", 0))
                    country.missions.difference_update({"EU_update_vars_mission", "EU_election_5_years"})
                g.flags.discard("eon_eu_membership_changed")
                g.flags.add("eon_eu_parliament_term")
                g.flag_days.setdefault("eon_eu_parliament_term", 1625)

    def persistent(self):
        nations = {ident: asdict(country) for ident, country in self.nations.items()}
        global_state = asdict(self.global_owner)
        global_state["variables"].pop(DIRTY, None)
        return nations, global_state, self.receipts


def setup(model, case):
    if case == "historical":
        for ident in (1, 2): model.nations[ident].ideas.add("EU_member")
        model.global_owner.arrays["EU_member"] = [2, 1, 1]
    elif case == "empty":
        pass
    else:
        model.members((1, 2, 3) if case in ("withdrawal", "last_departure", "seat_change") else (1, 2))
        if case == "mature":
            model.global_owner.flags.add("eon_eu_parliament_term")
            model.global_owner.flags.discard("eon_eu_membership_changed")
        elif case in ("dormant", "rule_disabled", "subject", "unowned"):
            if case == "dormant": model.global_owner.flags.add("eon_eu_dormant")
            if case == "rule_disabled": model.global_owner.flags.add("GAME_RULE_eu_disabled")
            if case == "subject": model.nations[1].subjects = True
            if case == "unowned": model.nations[1].owned = 0
        elif case == "candidate":
            model.call("eon_eu_apply_for_membership_start", 3)
            model.nations[3].arrays["eon_eu_accession_approvals"] = [1, 2]
        elif case == "expired_application":
            model.call("eon_eu_apply_for_membership_start", 3)
            model.nations[3].flags.discard("eon_eu_application_window")
        elif case == "treaty":
            c = model.nations[3]
            c.flags.update({"EU_candidate", "eon_eu_application_window"})
            c.variables["eon_eu_accession_phase"] = 3
            c.arrays["eon_eu_accession_approvals"] = [1, 2]
            c.arrays["eon_eu_accession_ep_approvals"] = [1]
        elif case in ("withdrawal", "last_departure", "legacy_clock"):
            model.call("eon_eu_notify_withdrawal", 1)
            if case == "legacy_clock":
                model.nations[1].flags.discard("eon_eu_withdrawal_clock_started")
            else:
                model.nations[1].flags.discard("eon_eu_withdrawal_deadline")
                model.nations[1].flag_days.pop("eon_eu_withdrawal_deadline", None)
                if case == "last_departure":
                    model.nations[2].exists = model.nations[3].exists = False
        elif case == "seat_change":
            model.nations[3].state_populations = [400]
            model.nations[1].flags.update({"Article_50", "eon_eu_withdrawal_clock_started", "eon_eu_withdrawal_proposal", "eon_eu_withdrawal_deadline"})
            model.nations[1].arrays["eon_eu_withdrawal_ep_approvals"] = [3]
        elif case == "pre_lock":
            model.global_owner.flags.add("eon_eu_daily_lifecycle_done")
            model.global_owner.flags.discard("eon_eu_admission_guard_ready")
        elif case == "stray":
            model.nations[3].ideas.add("EU_member")
            model.nations[3].flags.add("EU_candidate")
            model.nations[3].variables["eon_eu_accession_phase"] = 2
        elif case != "ordinary": raise AssertionError(case)
    model.receipts = []
    model.refreshes = 0
    model.temp = {}


CASES = ("ordinary", "mature", "historical", "empty", "dormant", "rule_disabled", "subject", "unowned",
         "candidate", "expired_application", "treaty", "withdrawal", "last_departure", "legacy_clock",
         "seat_change", "pre_lock", "stray")


class EURefresh(unittest.TestCase):
    def assert_equivalent(self, before, after):
        self.assertEqual(before.persistent(), after.persistent())
        # This serial wraps at 10000. Each omitted active refresh has two dirty
        # bumps; dormant cleanup also invalidates country screens. The retained
        # refreshes and their actual screen-clearing effects still invalidate.
        self.assertGreaterEqual(before.refreshes, after.refreshes)

    def test_live_production_matches_only_authorized_ast_change(self):
        self.assertEqual(ast(MEMBER.read_text("utf-8-sig")), desired_membership(OLD_MEMBER.read_text("utf-8-sig")))
        self.assertEqual(ast(LIFECYCLE.read_text("utf-8-sig")), desired_lifecycle(OLD_LIFECYCLE.read_text("utf-8-sig")))

    def test_all_bytes_outside_two_exact_edit_spans_are_preserved(self):
        member, lifecycle = desired_file_bytes(OLD_MEMBER.read_bytes(), OLD_LIFECYCLE.read_bytes())
        self.assertEqual(MEMBER.read_bytes(), member)
        self.assertEqual(LIFECYCLE.read_bytes(), lifecycle)

    def test_ordinary_live_day_has_two_unconditional_registry_refreshes(self):
        m = Runtime(); setup(m, "ordinary")
        m.call("eon_eu_daily_lifecycle_pulse", 3)
        self.assertEqual(m.refreshes, 2)
        self.assertNotEqual(m.global_owner.variables[DIRTY], 9999)

    def test_desired_and_live_persistent_state_equal_baseline_across_boundaries(self):
        for case in CASES:
            for mode in ("desired", "live"):
                for caller in (3, 5):
                    with self.subTest(case=case, mode=mode, caller=caller):
                        before, after = Runtime("baseline"), Runtime(mode)
                        setup(before, case); setup(after, case)
                        before.call("eon_eu_daily_lifecycle_pulse", caller)
                        after.call("eon_eu_daily_lifecycle_pulse", caller)
                        self.assert_equivalent(before, after)

    def test_direct_public_helper_still_refreshes_current_legal_roster(self):
        for case in CASES:
            before, after = Runtime("baseline"), Runtime("desired")
            setup(before, case); setup(after, case)
            before.nations[1].subjects = after.nations[1].subjects = True
            before.call("eon_eu_daily_membership_pulse", 5)
            after.call("eon_eu_daily_membership_pulse", 5)
            self.assert_equivalent(before, after)
            self.assertEqual(before.refreshes, after.refreshes)

    def test_transition_outcomes_are_observable_not_only_equal_empty_noops(self):
        m = Runtime("desired"); setup(m, "candidate")
        m.call("eon_eu_daily_lifecycle_pulse", 5)
        self.assertEqual(m.nations[3].variables["eon_eu_accession_phase"], 2)
        self.assertIn("EU_candidate", m.nations[3].flags)
        m = Runtime("desired"); setup(m, "withdrawal")
        m.call("eon_eu_daily_lifecycle_pulse", 5)
        self.assertNotIn("EU_member", m.nations[1].ideas)
        self.assertNotIn(1, m.global_owner.arrays["EU_member"])
        m = Runtime("desired"); setup(m, "seat_change")
        m.call("eon_eu_daily_lifecycle_pulse", 5)
        self.assertIn("eon_eu_withdrawal_ep_consent", m.nations[1].flags)

    def test_dirty_wrap_only_difference_is_documented_serial_reduction(self):
        for serial in (0, 9997, 9998, 9999, 10000):
            a, b = Runtime("baseline"), Runtime("desired")
            setup(a, "mature"); setup(b, "mature")
            a.global_owner.variables[DIRTY] = b.global_owner.variables[DIRTY] = serial
            a.call("eon_eu_daily_lifecycle_pulse", 3); b.call("eon_eu_daily_lifecycle_pulse", 3)
            self.assert_equivalent(a, b)
            self.assertEqual((a.global_owner.variables[DIRTY] - b.global_owner.variables[DIRTY]) % 10000, 2)

    def test_post_transition_refresh_is_preserved_and_sensitive(self):
        before, after = Runtime("baseline"), Runtime("desired")
        setup(before, "ordinary"); setup(after, "ordinary")
        # Check both unconditional boundaries, independently of additional
        # refreshes performed by specific transitions inside the membership body.
        body = one(after.effects["eon_eu_daily_lifecycle_pulse"], "if")
        direct = [i for i, row in enumerate(body) if row == CALL("eon_eu_refresh_membership")]
        self.assertEqual(len(direct), 2)
        self.assertLess(direct[0], next(i for i, row in enumerate(body) if row == CALL(NEW_HELPER)))
        self.assertGreater(direct[1], next(i for i, row in enumerate(body) if row == CALL(NEW_HELPER)))
        # Native departure executes during the actual membership body.
        setup(after, "withdrawal")
        after.call("eon_eu_daily_lifecycle_pulse", 5)
        self.assertEqual(after.global_owner.variables["eon_eu_voters"], 2)

    def test_negative_controls_detect_dropped_pre_refresh_and_body_work(self):
        before, mutant = Runtime("baseline"), Runtime("desired")
        setup(before, "historical"); setup(mutant, "historical")
        body = one(mutant.effects["eon_eu_daily_lifecycle_pulse"], "if")
        body.remove(CALL("eon_eu_refresh_membership"))
        before.call("eon_eu_daily_lifecycle_pulse", 5)
        mutant.call("eon_eu_daily_lifecycle_pulse", 5)
        self.assertNotEqual(before.persistent(), mutant.persistent())
        before, mutant = Runtime("baseline"), Runtime("desired")
        setup(before, "candidate"); setup(mutant, "candidate")
        mutant.effects[NEW_HELPER] = []
        before.call("eon_eu_daily_lifecycle_pulse", 5)
        mutant.call("eon_eu_daily_lifecycle_pulse", 5)
        self.assertNotEqual(before.persistent(), mutant.persistent())

    def test_source_intervening_stages_cannot_change_registry_inputs(self):
        effects = {}
        for file in ("00_eu_scripted_effects.txt", "eon_eu_lifecycle_effects.txt", "eon_eu_voting_effects.txt"):
            effects.update(definitions(ROOT / "common/scripted_effects" / file))
        protected = {"EU_member", "EU_candidate", "eon_eu_membership_recognized", "eon_eu_admission_guard_ready",
                     "eon_eu_dormant", "eon_eu_registry_refreshing", "GAME_RULE_eu_disabled", "usoe_formed",
                     "global.EU_member", "global.EU_candidates", "global.EU_member_count",
                     "eon_eu_accession_phase", "eurosceptic", "eon_eu_population_k", "EU_pop_ratio"}
        writes = []
        called = set()
        def walk(rows, chain=()):
            for key, op, val in rows:
                if key in ("limit", "effect_tooltip"): continue
                if key in effects:
                    self.assertNotIn(key, chain)
                    called.add(key); walk(effects[key], chain + (key,))
                elif isinstance(val, list):
                    if key in ("set_variable", "add_to_variable", "subtract_from_variable", "multiply_variable", "divide_variable", "clamp_variable", "add_to_array", "remove_from_array"):
                        name = one(val, "var") if any(k == "var" for k, _, _ in val) else one(val, "array") if any(k == "array" for k, _, _ in val) else val[0][0]
                        writes.append(name)
                    elif key in ("set_global_flag", "set_country_flag"):
                        writes.append(one(val, "flag"))
                    else: walk(val, chain)
                elif key in ("set_global_flag", "clr_global_flag", "set_country_flag", "clr_country_flag", "clear_variable", "clear_array", "add_ideas", "remove_ideas"):
                    writes.append(val)
                # Reject native geographic/identity mutations even if they have
                # different syntax from variable/idea commands.
                self.assertNotIn(key, {"annex_country", "set_autonomy", "transfer_state", "set_state_owner", "add_state_population", "set_state_population"})
        for stage in ("eon_eu_recount_council_vote", "eon_eu_update_parliament"):
            walk(effects[stage], (stage,))
        self.assertNotIn("EU_update_vars", called)
        self.assertNotIn("eon_eu_refresh_membership", called)
        for name in writes:
            # THIS/PREV qualifications change scope, never the field identity.
            normalized = name.split(".", 1)[1] if name.startswith(("THIS.", "PREV.", "ROOT.", "FROM.")) else name
            self.assertNotIn(normalized, protected, name)
        self.assertIn("election_EU_Parliament_in_member_state", called)
        self.assertIn("distribute_EU_budget", called)

    def test_file_bom_and_line_ending_kinds_are_preserved(self):
        for source, fixture in ((MEMBER, OLD_MEMBER), (LIFECYCLE, OLD_LIFECYCLE)):
            old, new = fixture.read_bytes(), source.read_bytes()
            self.assertEqual(old.startswith(b"\xef\xbb\xbf"), new.startswith(b"\xef\xbb\xbf"))
            self.assertEqual(old.count(b"\n") == old.count(b"\r\n"), new.count(b"\n") == new.count(b"\r\n"))
            self.assertEqual(b"\r\n" in old, b"\r\n" in new)


if __name__ == "__main__":
    unittest.main()
