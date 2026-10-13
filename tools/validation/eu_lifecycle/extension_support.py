"""Native extension scenarios built from actual production decision gates; no launcher actions.

This module is a public v13 builder dependency. Returned event definitions and
contracts merge into a fresh source-bound probe, leaving production untouched.
It binds production decision gates and executes native activation APIs under
actual country-event scopes, with no complete_effect fallback. It does not claim
GUI clicks, target-list rendering or multiplayer popup verification.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("eon_extension_native_ast", ROOT / "tools/validation/diplomacy_package_02/_treaty_support.py")
SUPPORT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SUPPORT
SPEC.loader.exec_module(SUPPORT)
ast, one = SUPPORT.ast, SUPPORT.one
MEMBERS = ("GER", "FRA", "ITA", "HOL", "SPR", "CZE")
LEAVER = "POL"
PREFIX = "global.eon_private_eu_extension_"


def render(nodes):
    def value(v):
        if isinstance(v, list):
            return "{ " + render(v) + " }"
        if re.search(r'[\s{}"]', v):
            return json.dumps(v)
        return v
    return " ".join(value(v) if k == "__item__" else f"{k} {op} {value(v)}" for k, op, v in nodes)


def build_extension(namespace, marker, *, terminal_effect="", source=ROOT):
    source = Path(source).resolve()
    assert source.is_dir()
    assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", namespace)
    assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", marker)
    decision_paths = ("common/decisions/eon_eu_membership_decisions.txt",
                      "common/decisions/eon_eu_withdrawal_extension_decisions.txt")
    actions = {}
    action_categories = {}
    category_path = "common/decisions/categories/eon_eu_membership_categories.txt"
    categories = {name: body for name, op, body in ast((source / category_path).read_text("utf-8-sig"))}
    for relative in decision_paths:
        for category, op, body in ast((source / relative).read_text("utf-8-sig")):
            for ident, op, action in body:
                assert ident not in actions
                actions[ident] = action
                action_categories[ident] = category

    decision_sequence = 0

    def decision(ident, expected_actor=None):
        nonlocal decision_sequence
        decision_sequence += 1
        # Bind real frontend gates. Pair event dispatch must
        # have ROOT=responder, FROM=POL; no handler carries delayed acceptance.
        action = actions[ident]
        gates = []
        for key in ("allowed", "visible", "available", "target_root_trigger", "target_trigger"):
            gates.extend(next((body for name, op, body in action if name == key), []))
        targeted = any(key == "target_trigger" for key, op, value in action)
        activate = f"activate_targeted_decision = {{ target = POL decision = {ident} }} " if targeted else f"activate_decision = {ident} "
        stamp = f"ACTION_{decision_sequence:03d}_{ident.upper()}"
        diagnostics = context(stamp + "_BEFORE", expected_actor)
        for key in ("allowed", "visible"):
            gate = next((body for name, op, body in categories[action_categories[ident]] if name == key), [("always", "=", "yes")])
            diagnostics += bool_observation(stamp + "_CATEGORY_" + key.upper(), render(gate))
        for key in ("allowed", "visible", "available", "target_root_trigger", "target_trigger"):
            gate = next((body for name, op, body in action if name == key), [("always", "=", "yes")])
            diagnostics += bool_observation(stamp + "_GATE_" + key.upper(), render(gate))
        if targeted:
            # Literal POL is documented target syntax; its identity must still
            # match the actual event FROM, never repair a broken native pair.
            assert expected_actor in MEMBERS
            gates.append(("tag", "=", expected_actor))
            gates.append(("FROM", "=", [("tag", "=", "POL")]))
            diagnostics += bool_observation(stamp + "_PAIR_TARGET_POL", f"tag = {expected_actor} FROM = {{ tag = POL }}")
        actor_expression = expected_actor or "THIS"
        requested = f'log = "{marker} TRACE EXTENSION_{stamp}_ACTIVATE_REQUESTED actor=[?ROOT.id] scope=[?THIS.id] target=[?POL.id] sender=[?FROM.id] expected_actor=[?{actor_expression}.id]" '
        if targeted:
            action_callback_contract.append({"decision": ident, "actor_tag": expected_actor, "target_tag": "POL",
                "before_observation": "EXTENSION_" + stamp + "_BEFORE",
                "requested_trace": "EXTENSION_" + stamp + "_ACTIVATE_REQUESTED",
                "raw_after_observation": "EXTENSION_" + stamp + "_RAW_AFTER",
                "calibration_before_observation": "EXTENSION_" + stamp + "_CALIBRATION_BEFORE",
                "remove_requested_trace": "EXTENSION_" + stamp + "_REMOVE_REQUESTED",
                "calibration_requested_trace": "EXTENSION_" + stamp + "_CALIBRATION_ACTIVATE_REQUESTED",
                "active_after_remove_observation": "EXTENSION_" + stamp + "_ACTIVE_AFTER_REMOVE",
                "after_observation": "EXTENSION_" + stamp + "_AFTER",
                "increment_array": "abstentions" if ident == "eon_eu_extension_abstain" else "approvals",
                "increment_counter": "abstain" if ident == "eon_eu_extension_abstain" else "yes"})
        # No direct complete_effect fallback may turn unsupported native decision
        # activation or category registration into a false feature PASS.
        diagnostics += bool_observation(stamp + "_ACTIVE_BEFORE", f"has_decision = {ident}")
        text = diagnostics + "if = { limit = { " + render(gates) + " } " + requested + activate + " } "
        text += context(stamp + "_RAW_AFTER", expected_actor)
        text += bool_observation(stamp + "_ACTIVE_RAW_AFTER", f"has_decision = {ident}")
        if targeted:
            # The real response guard excludes a country already recorded.
            # A raw response makes this calibration unreachable. Preexisting
            # AI answers also cannot turn a missing native delta into proof.
            calibration = context(stamp + "_CALIBRATION_BEFORE", expected_actor)
            calibration += f'log = "{marker} TRACE EXTENSION_{stamp}_REMOVE_REQUESTED actor=[?ROOT.id] scope=[?THIS.id] target=[?POL.id] sender=[?FROM.id] expected_actor=[?{expected_actor}.id]" '
            calibration += f"remove_targeted_decision = {{ target = POL decision = {ident} }} "
            calibration += bool_observation(stamp + "_ACTIVE_AFTER_REMOVE", f"has_decision = {ident}")
            calibration += f'log = "{marker} TRACE EXTENSION_{stamp}_CALIBRATION_ACTIVATE_REQUESTED actor=[?ROOT.id] scope=[?THIS.id] target=[?POL.id] sender=[?FROM.id] expected_actor=[?{expected_actor}.id]" '
            calibration += activate
            text += "if = { limit = { " + render(gates) + " } " + calibration + " } "
        text += context(stamp + "_AFTER", expected_actor)
        text += bool_observation(stamp + "_ACTIVE_AFTER", f"has_decision = {ident}")
        return text

    events, assertions, expectations, observations, elapsed, calibrations = {}, [], {}, [], [], []
    diagnostic_observations = []
    action_callback_contract = []

    def scope(tag, body):
        return f"{tag} = {{ {body} }} "

    def cv(name, value, compare="equals"):
        return f"check_variable = {{ var = {name} value = {value} compare = {compare} }} "

    def setv(name, value):
        return f"set_variable = {{ {name} = {value} }} "

    def flag(name, yes=True):
        return f"has_country_flag = {name} " if yes else f"NOT = {{ has_country_flag = {name} }} "

    def check(label, predicate, expected):
        label = "extension_" + label
        assert label not in expectations
        assertions.append(label)
        expectations[label] = {"predicate": predicate, "expected": expected}
        return (f'log = "{marker} BEGIN {label}" if = {{ limit = {{ {predicate} }} '
                f'log = "{marker} PASS {label}" add_to_variable = {{ global.{namespace}_passes = 1 }} }} '
                f'else = {{ log = "{marker} FAIL {label}" add_to_variable = {{ global.{namespace}_fails = 1 }} }} '
                f'log = "{marker} END {label}" ')

    def obs(label):
        label = "EXTENSION_" + label
        assert label not in observations
        observations.append(label)
        text = f'log = "{marker} OBS {label} date=[?global.date] queue=[?eon_eu_extension_queued_units] serial=[?eon_eu_extension_notice_serial] main_days=[?days_mission_timeout@EU_exit] short_days=[?days_mission_timeout@EU_exit_three_month] eurosceptic=[?eurosceptic] ruling_party_count=[?ruling_party^num] ruling_party_first=[?ruling_party^0]" '
        for key, predicate in (
            ("ARTICLE50", "has_country_flag = Article_50"),
            ("MEMBER", "has_idea = EU_member"),
            ("RECOGNIZED", "has_country_flag = eon_eu_membership_recognized"),
            ("INITIALIZED", "has_country_flag = eon_eu_extension_notice_initialized"),
            ("MAIN_AUTHORITY", "has_country_flag = eon_eu_legacy_exit_clock_authoritative"),
            ("CLOCK_STARTED", "has_country_flag = eon_eu_withdrawal_clock_started"),
            ("DEADLINE", "has_country_flag = eon_eu_withdrawal_deadline"),
            ("PROPOSAL", "has_country_flag = eon_eu_extension_proposal"),
            ("WITHDRAWAL_TREATY", "has_idea = withdrawal_treaty"),
            ("GOV_EUROSCEPTIC", "gov_is_eurosceptical = yes"),
            ("GOV_EXITEER", "gov_is_EUexiteer = yes")):
            text += bool_observation(label.removeprefix("EXTENSION_") + "_STATE_" + key, predicate)
        return text

    def private_political_boundary(label):
        # Declared private POL preference input; do not replace government,
        # native AI, voting weights or ruling-party array.
        name = "EXTENSION_" + label.upper() + "_POLITICAL_INPUT"
        for suffix in ("_BEFORE", "_AFTER"):
            assert name + suffix not in diagnostic_observations
            diagnostic_observations.append(name + suffix)
        text = f'log = "{marker} OBS {name}_BEFORE actor=[?ROOT.id] scope=[?THIS.id] eurosceptic=[?eurosceptic] ruling_party_count=[?ruling_party^num] ruling_party_first=[?ruling_party^0]" '
        text += f'log = "{marker} TRACE {name}_DECLARED_PRIVATE_BOUNDARY actor=[?ROOT.id] scope=[?THIS.id] eurosceptic=1 native_ai=unchanged ruling_party=unchanged" '
        text += setv("eurosceptic", 1)
        text += f'log = "{marker} OBS {name}_AFTER actor=[?ROOT.id] scope=[?THIS.id] eurosceptic=[?eurosceptic] ruling_party_count=[?ruling_party^num] ruling_party_first=[?ruling_party^0]" '
        text += bool_observation(label.upper() + "_POLITICAL_INPUT_GOV_EUROSCEPTIC", "gov_is_eurosceptical = yes")
        text += bool_observation(label.upper() + "_POLITICAL_INPUT_GOV_EXITEER", "gov_is_EUexiteer = yes")
        return text

    def context(label, expected_actor=None):
        actor_expression = expected_actor or "THIS"
        label = "EXTENSION_" + label
        assert label not in diagnostic_observations
        diagnostic_observations.append(label)
        return (f'log = "{marker} OBS {label} actor=[?ROOT.id] scope=[?THIS.id] sender=[?FROM.id] target=[?POL.id] expected_actor=[?{actor_expression}.id] '
                'answer=[?POL.eon_eu_extension_answer_count] electorate=[?POL.eon_eu_extension_electorate_total] '
                'yes=[?POL.eon_eu_extension_yes_count] no=[?POL.eon_eu_extension_no_count] abstain=[?POL.eon_eu_extension_abstain_count] '
                'approvals=[?POL.eon_eu_extension_approvals^num] rejections=[?POL.eon_eu_extension_rejections^num] '
                'abstentions=[?POL.eon_eu_extension_abstentions^num] queue=[?POL.eon_eu_extension_queued_units] '
                'notice=[?POL.eon_eu_extension_notice_serial] project=[?POL.eon_eu_extension_proposal_serial]" ')

    def bool_observation(label, predicate):
        label = "EXTENSION_" + label
        assert label not in diagnostic_observations
        diagnostic_observations.append(label)
        return (f'if = {{ limit = {{ {predicate} }} log = "{marker} OBS {label} value=1" }} '
                f'else = {{ log = "{marker} OBS {label} value=0" }} ')

    def event(number, body):
        assert number not in events
        text = f"country_event = {{ id = {namespace}.{number} hidden = yes is_triggered_only = yes immediate = {{ {body} }} }}\n"
        ast(text)
        events[number] = text

    def schedule(tag, number, hours=1):
        return scope(tag, f"country_event = {{ id = {namespace}.{number} hours = {hours} }} ")

    def calibrate_clock(name, kind):
        # Obtain real consent first. Read the actual remaining native mission
        # days, then adjust by an additive delta; never deactivate/restart it.
        text = obs(name.upper() + "_BEFORE_CALIBRATION")
        clocks = []
        if kind != "short":
            clocks.append(("EU_exit", 2))
        if kind in ("short", "both"):
            clocks.append(("EU_exit_three_month", 1))
        for mission, target in clocks:
            before = "eon_private_extension_before_" + mission
            delta = "eon_private_extension_delta_" + mission
            text += check(name + "_" + mission + "_positive_before_shortening", "has_active_mission = " + mission + " " + cv("days_mission_timeout@" + mission, target, "greater_than"),
                          "Real native mission retains a positive long period until consent or explicit old-callback fixture is ready")
            text += setv(before, "days_mission_timeout@" + mission) + setv(delta, target)
            text += f"subtract_from_variable = {{ {delta} = {before} }} add_days_mission_timeout = {{ mission = {mission} days = {delta} }} "
            text += check(name + "_" + mission + "_exact_short_remaining", "has_active_mission = " + mission + " " + cv("days_mission_timeout@" + mission, target),
                          "Supported dynamic remaining-days/additive API produces exact private target without restarting mission")
        if kind == "flag":
            text += f"set_country_flag = {{ flag = eon_eu_withdrawal_deadline days = 1 value = 1 }} "
        text += setv(PREFIX + name + "_date", "global.date") + obs(name.upper() + "_START")
        return text

    q = "eon_eu_extension_queued_units"
    deadline = "eon_eu_withdrawal_deadline"
    init = "eon_eu_extension_notice_initialized"
    main_authority = "eon_eu_legacy_exit_clock_authoritative"

    # Exact independent starts, 100-ID blocks leave room for future assertions.
    cases = ((1800, "natural_flag", "flag", True),
             (1900, "old_main", "main", True),
             (2000, "old_short", "short", True),
             (2100, "both_old", "both", True),
             (2200, "main_callback_before_migration", "main", False),
             (2300, "short_callback_before_migration", "both", False))
    setup = check("countries_live", " ".join(scope(tag, "exists = yes is_subject = no any_owned_state = { always = yes }") for tag in MEMBERS + (LEAVER,)),
                  "Seven representative sovereigns own states; missing live countries cannot fake consent")
    setup += "clr_global_flag = eon_eu_dormant clr_global_flag = GAME_RULE_eu_disabled clr_global_flag = usoe_formed "
    setup += "set_global_flag = { flag = eon_eu_daily_lifecycle_done days = 180 value = 1 } "
    # Private existing-lawful-member inputs, explicit one-use grants only. These
    # do not prove historical bootstrap or Article49; their suites do that.
    for tag in MEMBERS + (LEAVER,):
        setup += scope(tag, "if = { limit = { NOT = { has_idea = EU_member } } set_country_flag = eon_eu_admission_commit add_ideas = EU_member } "
                       "remove_ideas = EUU_voting_rights_suspended remove_ideas = no_deal_exit remove_ideas = withdrawal_treaty ")
    setup += "eon_eu_refresh_membership = yes "
    setup += check("recognized_fixture_registry", "has_global_flag = eon_eu_admission_guard_ready " + cv("global.EU_member_count", 7) + " ".join(scope(tag, "eon_eu_is_active_member = yes has_country_flag = eon_eu_membership_recognized") for tag in MEMBERS + (LEAVER,)),
                   "Only explicit legal fixture members are live; admission guard remains enabled")
    setup += schedule(LEAVER, cases[0][0])
    event(1799, setup)

    for position, (base, name, kind, agree) in enumerate(cases):
        next_entry = cases[position + 1][0] if position + 1 < len(cases) else None
        start = private_political_boundary(name) + "if = { limit = { has_country_flag = Article_50 } " + decision("eon_eu_revoke_withdrawal") + " } "
        start += "if = { limit = { NOT = { has_idea = EU_member } } set_country_flag = eon_eu_admission_commit add_ideas = EU_member } "
        start += "remove_ideas = no_deal_exit remove_ideas = withdrawal_treaty clr_country_flag = cant_invoke_article_50 eon_eu_refresh_membership = yes "
        start += decision("eon_eu_notify_withdrawal")
        start += check(name + "_real_notice", "tag = POL eon_eu_withdrawal_current = yes " + flag(init) + flag(deadline) + "has_active_mission = EU_exit ",
                       "Actual production notification decision starts recognized Article50 and native main mission")
        start += obs(name.upper() + "_NOTICE_START")
        # All shortening is declared private calibration, never runtime policy.
        if kind != "flag":
            start += "eon_eu_extension_clear_notice = yes clr_country_flag = eon_eu_withdrawal_clock_started "
            start += f"clr_country_flag = {deadline} "
            if kind == "short":
                start += "remove_mission = EU_exit "
            if kind in ("short", "both"):
                start += "activate_mission = EU_exit_three_month "
            start += check(name + "_legacy_clock_is_real", ("has_active_mission = EU_exit " if kind != "short" else "") +
                           ("has_active_mission = EU_exit_three_month " if kind in ("short", "both") else "") + flag(init, False),
                           "Saved old-clock fixture has actual native missions and no extension marker")
        calibrations.append({"case": name, "flag_deadline_days": 1 if kind == "flag" else None,
                             "native_main_target_remaining_days": 2 if kind != "short" else None,
                             "native_short_target_remaining_days": 1 if kind in ("short", "both") else None,
                             "mission_adjustment": "read days_mission_timeout@ID; additive target-minus-actual delta; no restart",
                             "shortening_after_actual_acceptance": agree,
                             "legacy_saved_inputs": kind != "flag", "before_first_migration": not agree})
        if agree:
            start += "eon_eu_force_deadline_withdrawal = yes " + decision("eon_eu_extension_propose")
            start += check(name + "_proposal_is_not_agreement", flag("eon_eu_extension_proposal") + cv(q, 0),
                           "Actual proposal decision creates a current30-day project without a queued extension")
            # All actual responder events originate independently in the
            # initial POL ROOT; nested current scope cannot promise FROM.
            for responder_index, responder_tag in enumerate(MEMBERS):
                start += schedule(responder_tag, base + responder_index + 1, (responder_index + 1) * 2)
            start += schedule(LEAVER, base + 10, 16)
            event(base, start)
            for index, tag in enumerate(MEMBERS):
                body = check(name + "_pair_" + tag, f"tag = {tag} FROM = {{ tag = POL }} ", "Actual event ROOT is responder and FROM is current withdrawing state")
                ident = "eon_eu_extension_abstain" if index == len(MEMBERS) - 1 else "eon_eu_extension_approve"
                body += decision(ident, expected_actor=tag)
                body += scope("FROM", check(name + "_response_" + tag, cv("eon_eu_extension_answer_count", index + 1) + cv(q, 0),
                                            "Actual targeted decision records one response without granting final acceptance"))
                if index < len(MEMBERS) - 1:
                    if index == len(MEMBERS) - 2:
                        body += scope("FROM", decision("eon_eu_extension_accept_final") + check(name + "_missing_sixth_blocks_final", cv(q, 0),
                                     "Five represented governments cannot auto-agree for an unanswered sixth"))
                event(base + index + 1, body)
            final = decision("eon_eu_extension_accept_final")
            final += check(name + "_leaver_final_queues_only_one_without_ep", cv(q, 1) + flag("eon_eu_withdrawal_ep_consent", False) + "has_idea = EU_member ",
                           "Six represented responses include explicit abstention; leaver explicitly accepts without EP extension approval")
            final += decision("eon_eu_extension_accept_final") + decision("eon_eu_extension_propose")
            final += check(name + "_replay_does_not_stack", cv(q, 1) + flag("eon_eu_extension_proposal", False), "Replayed actual final/proposal cannot stack more than one agreement")
            final += calibrate_clock(name, kind)
            final += schedule(LEAVER, base + 20, 30)
            event(base + 10, final)
        else:
            # Do not call migration, pulse or force-deadline before genuine engine
            # timeout. This probes callbacks that precede the first daily pass.
            start += calibrate_clock(name, kind) + schedule(LEAVER, base + 20, 30)
            event(base, start)
        first = obs(name.upper() + "_AFTER_DAY")
        elapsed.append({"start_observation": "EXTENSION_" + name.upper() + "_START", "end_observation": "EXTENSION_" + name.upper() + "_AFTER_DAY", "minimum_hours": 24})
        first += check(name + "_actual_date_advanced", cv("global.date", PREFIX + name + "_date", "greater_than"), "Native date advances; independent log analyzer additionally requires at least24 real game hours")
        if kind in ("main", "both"):
            authority = flag(main_authority) if agree or kind == "both" else flag(init, False)
            first += check(name + "_main_remaining_not_reset_or_shortened", "has_idea = EU_member has_active_mission = EU_exit " +
                           authority + (cv(q, 1) if agree else "") + flag(deadline, False),
                           "Real two-day main clock retains its remaining time; a short callback cannot fabricate730 or prematurely exit")
            first += schedule(LEAVER, base + 30, 30)
        else:
            first += check(name + "_native_boundary_before_manual_pulse", flag(deadline, False), "One-day country flag or sole native short mission has really ended before any manual pulse") if kind == "flag" else ""
            first += "eon_eu_force_deadline_withdrawal = yes "
            first += check(name + "_exact_one_natural_extension", "has_idea = EU_member " + flag(deadline) + cv(q, 0), "Natural one-day boundary consumes one agreed unit and starts positive365-day period")
            first += "eon_eu_force_deadline_withdrawal = yes "
            first += check(name + "_next_pulse_keeps_extension", "has_idea = EU_member " + flag(deadline) + cv(q, 0), "Repeated production pulse cannot consume twice or leave during positive extension")
            first += schedule(LEAVER, base + 30, 30)
        event(base + 20, first)
        last = obs(name.upper() + "_AFTER_TWO_DAYS")
        elapsed.append({"start_observation": "EXTENSION_" + name.upper() + "_START", "end_observation": "EXTENSION_" + name.upper() + "_AFTER_TWO_DAYS", "minimum_hours": 48})
        if agree:
            last += check(name + "_natural_callbacks_preserve_positive_extension", "has_idea = EU_member " + flag(deadline) + cv(q, 0) + flag(main_authority, False),
                          "Natural legacy callbacks consume the accepted unit once or leave an existing positive extension intact")
        else:
            last += check(name + "_early_callback_finishes_without_new730", "NOT = { has_idea = EU_member } has_idea = no_deal_exit " + flag(init, False) + flag(deadline, False),
                          "Actual native callback before migration completes old known clock; no new730 period or suspended membership")
        last += schedule(LEAVER, next_entry) if next_entry is not None else terminal_effect
        event(base + 30, last)
    inputs = decision_paths + (category_path, "common/scripted_triggers/99_EU_scripted_triggers.txt", "common/scripted_effects/eon_eu_withdrawal_extension_effects.txt", "common/scripted_triggers/eon_eu_withdrawal_extension_triggers.txt",
                              "common/scripted_effects/eon_eu_membership_effects.txt", "common/scripted_triggers/eon_eu_membership_triggers.txt", "common/decisions/EU_voting_decisions.txt")
    remap = {number: 2000 + index for index, number in enumerate(sorted(events))}
    assert min(remap.values()) >= 2000 and max(remap.values()) <= 2099
    external_targets = {int(number) for number in re.findall(re.escape(namespace) + r"\.(\d+)\b", terminal_effect)}
    def remap_ids(text):
        def replacement(match):
            number = int(match[1])
            assert number in remap or number in external_targets, ('Unbound extension event reference', number)
            return namespace + "." + str(remap[number] if number in remap else number)
        return re.sub(re.escape(namespace) + r"\.(\d+)\b", replacement, text)
    definitions = remap_ids("".join(events[n] for n in sorted(events)))
    return {"fixture_text": {f"events/{namespace}.txt": "add_namespace = " + namespace + "\n" + definitions},
            "entry_event_id": f"{namespace}.{remap[1799]}", "terminal_event_id": f"{namespace}.{max(remap.values())}",
            "entry_effect": remap_ids(schedule(LEAVER, 1799)), "assertions": assertions,
            "assertion_records": [{"label": name, **expectations[name]} for name in assertions], "expectations": expectations,
            "observations": observations, "production_dependency_paths": list(inputs),
            "required_observations": observations, "diagnostic_observations": diagnostic_observations, "extension_callback_contract": {"schema": 1, "actions": action_callback_contract}, "required_elapsed_game_time": elapsed,
            "production_input_sha256": {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in inputs},
            "calibrations": calibrations, "events": len(events),
            "limits": ["Actual native activate_decision/activate_targeted_decision under source-bound frontend gates; no complete_effect fallback or UI-click proof",
                       "Seven privately admitted recognized fixture members; no claim of native Article49 ratification in this module",
                       "Native one-day flag and one/two-day mission boundaries, not natural365/730-day campaign",
                       "Source coordinator daily lock held90days so callbacks-before-firstmigration are observable; automatic whole-world coordination tested separately",
                       "No launcher, production save, subscribed Workshop or source mutation by this module"]}
