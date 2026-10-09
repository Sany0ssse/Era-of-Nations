"""Exact permitted uranium repairs for historical electricity byte guards.

This is a frozen, explicit canonical patch, never a runtime-generated allowlist.
All unmatched GUI/effect bytes are still compared to the historical baseline.
"""
from pathlib import Path

GUI_PATCH_BASELINE = '3aa416cbd7030898d881db1f34bce3335b974cde'
LEGACY_REACTOR_REWARD = b'change_reactor_grade_material_effect = {\n\tcustom_effect_tooltip = change_reactor_grade_material_effect_tt\n\tadd_to_variable = { var_reactor_material_stockpile = change_resource }\n}'
KG_REACTOR_REWARD = b'change_reactor_grade_material_effect = {\n\teon_uranium_initialize = yes\n\t# Legacy focus rewards used abstract units: preserve their weeks of fuel.\n\tset_temp_variable = { eon_legacy_reactor_reward_kg = change_resource }\n\tmultiply_temp_variable = { eon_legacy_reactor_reward_kg = 57.7 }\n\tcustom_effect_tooltip = change_reactor_grade_material_effect_tt\n\tadd_to_variable = { var_reactor_material_stockpile = eon_legacy_reactor_reward_kg }\n}'

GUI_REPAIRS = [
    (b'\t\t\t\tcustom_trigger_tooltip = { tooltip = eon_energy_counter_partner_locked_tt NOT = { has_country_flag = eon_energy_counter_draft_owner } }\n\t\t\t}\n\t\t\tbuild_enrichment_facility_button_click_enabled = {\n\t\t\t\tNOT = { has_active_mission = bankruptcy_incoming_collapse }\n\t\t\t\tNOT = { has_active_mission = energy_building_enrichment_facilities }\n\t\t\t}\n\t\t\tbuild_enrichment_facility_button_shift_click_enabled = {\n\t\t\t\tNOT = { has_active_mission = bankruptcy_incoming_collapse }\n\t\t\t\tNOT = { has_active_mission = energy_building_enrichment_facilities }\n\t\t\t}\n\t\t\tbuild_battery_park_button_click_enabled = {\n\t\t\t\tNOT = { has_active_mission = bankruptcy_incoming_collapse }\n',
     b'\t\t\t\tcustom_trigger_tooltip = { tooltip = eon_energy_counter_partner_locked_tt NOT = { has_country_flag = eon_energy_counter_draft_owner } }\n\t\t\t}\n\t\t\tbuild_enrichment_facility_button_click_enabled = {\n\t\t\t\tset_temp_variable = { eon_requested_facilities = 1 }\n\t\t\t\tcustom_trigger_tooltip = { tooltip = eon_enrichment_ready_tt eon_enrichment_project_ready = yes }\n\t\t\t}\n\t\t\tbuild_enrichment_facility_button_shift_click_enabled = {\n\t\t\t\tset_temp_variable = { eon_requested_facilities = 3 }\n\t\t\t\tcustom_trigger_tooltip = { tooltip = eon_enrichment_ready_tt eon_enrichment_project_ready = yes }\n\t\t\t}\n\t\t\tbuild_battery_park_button_click_enabled = {\n\t\t\t\tNOT = { has_active_mission = bankruptcy_incoming_collapse }\n'),
    (b'\t\t\t\tcheck_variable = { temp_energy_price > 0 }\n\t\t\t}\n\t\t\tincrease_nuclear_fuel_ammount_number_click_enabled = {\n\t\t\t\tvar:nuclear_fuel_selling_selected_TAG = {\n\t\t\t\t\tcheck_variable = { var_reactor_material_stockpile > PREV.temp_nuclear_fuel_ammount }\n\t\t\t\t}\n\t\t\t}\n\t\t\tdecrease_nuclear_fuel_ammount_number_click_enabled = {\n\t\t\t\tset_temp_variable = { nuclear_fuel_check = var_reactor_material_stockpile }\n\t\t\t\tmultiply_temp_variable = { nuclear_fuel_check = -1 }\n\t\t\t\tcheck_variable = { temp_nuclear_fuel_ammount > nuclear_fuel_check }\n\t\t\t}\n\t\t\tdecrease_nuclear_fuel_price_number_click_enabled = {\n\t\t\t\tcheck_variable = { temp_nuclear_fuel_price > 0 }\n\t\t\t}\n\t\t\tconfirm_energy_sell_click_enabled = {\n',
     b'\t\t\t\tcheck_variable = { temp_energy_price > 0 }\n\t\t\t}\n\t\t\tincrease_nuclear_fuel_ammount_number_click_enabled = {\n\t\t\t\tNOT = { has_country_flag = eon_nuclear_fuel_trade_reserved }\n\t\t\t\tset_temp_variable = { eon_fuel_arrow_amount = temp_nuclear_fuel_ammount }\n\t\t\t\tadd_to_temp_variable = { eon_fuel_arrow_amount = 100 }\n\t\t\t\tNOT = { check_variable = { eon_fuel_arrow_amount > 20000000 } }\n\t\t\t\tNOT = { check_variable = { eon_fuel_arrow_amount < -20000000 } }\n\t\t\t}\n\t\t\tdecrease_nuclear_fuel_ammount_number_click_enabled = {\n\t\t\t\tNOT = { has_country_flag = eon_nuclear_fuel_trade_reserved }\n\t\t\t\tset_temp_variable = { eon_fuel_arrow_amount = temp_nuclear_fuel_ammount }\n\t\t\t\tadd_to_temp_variable = { eon_fuel_arrow_amount = -100 }\n\t\t\t\tNOT = { check_variable = { eon_fuel_arrow_amount > 20000000 } }\n\t\t\t\tNOT = { check_variable = { eon_fuel_arrow_amount < -20000000 } }\n\t\t\t}\n\t\t\tdecrease_nuclear_fuel_price_number_click_enabled = {\n\t\t\t\tNOT = { has_country_flag = eon_nuclear_fuel_trade_reserved }\n\t\t\t\tcheck_variable = { temp_nuclear_fuel_price > 0 }\n\t\t\t}\n\t\t\tconfirm_energy_sell_click_enabled = {\n'),
    (b'\t\t\t\t\t\t\t}\n\t\t\t}\n\t\t\tconfirm_nuclear_fuel_sell_click_enabled = {\n\t\t\t\tNOT = { has_country_flag = currently_considering_an_offer }\n\t\t\t\tNOT = { tag = nuclear_fuel_selling_selected_TAG }\n\t\t\t\thas_variable = nuclear_fuel_selling_selected_TAG\n\t\t\t\tvar:nuclear_fuel_selling_selected_TAG = { NOT = { has_country_flag = currently_considering_an_offer } }\n\t\t\t}\n\n\t\t\ttotal_ffp_bg_visible = { has_country_flag = energy_main }\n',
     b'\t\t\t\t\t\t\t}\n\t\t\t}\n\t\t\tconfirm_nuclear_fuel_sell_click_enabled = {\n\t\t\t\tcustom_trigger_tooltip = { tooltip = eon_nuclear_fuel_trade_unavailable_tt eon_nuclear_fuel_trade_send_ready = yes }\n\t\t\t}\n\n\t\t\ttotal_ffp_bg_visible = { has_country_flag = energy_main }\n'),
    (b'\t\t\t}\n\t\t\t# Other Buttons\n\t\t\tbuild_enrichment_facility_button_click = {\n\t\t\t\tlog = "[GetDateText]: [Root.GetName]: Energy GUI build_enrichment_facility_button"\n\t\t\t\tclr_country_flag = build_three_enrichment_facility\n\t\t\t\tclr_country_flag = single_enrichment_facility\n\t\t\t\tset_country_flag = single_enrichment_facility\n\t\t\t\tset_variable = { enrichment_facility_time = 120 }\n\t\t\t\tactivate_mission = energy_building_enrichment_facilities\n\t\t\t\tif = { limit = { NOT = { is_in_array = { global.enrichment_countries = THIS.id } } }\n\t\t\t\t\trandom_list = {\n\t\t\t\t\t\t30 = {\n',
     b'\t\t\t}\n\t\t\t# Other Buttons\n\t\t\tbuild_enrichment_facility_button_click = {\n\t\t\t\tset_temp_variable = { eon_requested_facilities = 1 }\n\t\t\t\tif = {\n\t\t\t\t\tlimit = { eon_enrichment_project_ready = yes }\n\t\t\t\t\teon_enrichment_begin_project = yes\n\t\t\t\tif = { limit = { NOT = { is_in_array = { global.enrichment_countries = THIS.id } } }\n\t\t\t\t\trandom_list = {\n\t\t\t\t\t\t30 = {\n'),
    (b'\t\t\t\t\t\t70 = { }\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t}\n\t\t\tbuild_enrichment_facility_button_shift_click = {\n\t\t\t\tlog = "[GetDateText]: [Root.GetName]: Energy GUI build_enrichment_facility_button"\n\t\t\t\tclr_country_flag = build_three_enrichment_facility\n\t\t\t\tclr_country_flag = single_enrichment_facility\n\t\t\t\tset_country_flag = build_three_enrichment_facility\n\t\t\t\tset_variable = { enrichment_facility_time = 290 }\n\t\t\t\tactivate_mission = energy_building_enrichment_facilities\n\t\t\t\tif = { limit = { NOT = { is_in_array = { global.enrichment_countries = THIS.id } } }\n\t\t\t\t\trandom_list = {\n\t\t\t\t\t\t30 = {\n',
     b'\t\t\t\t\t\t70 = { }\n\t\t\t\t\t}\n\t\t\t\t}\n\n\t\t\t\t}\n\t\t\t}\n\t\t\tbuild_enrichment_facility_button_shift_click = {\n\t\t\t\tset_temp_variable = { eon_requested_facilities = 3 }\n\t\t\t\tif = {\n\t\t\t\t\tlimit = { eon_enrichment_project_ready = yes }\n\t\t\t\t\teon_enrichment_begin_project = yes\n\t\t\t\tif = { limit = { NOT = { is_in_array = { global.enrichment_countries = THIS.id } } }\n\t\t\t\t\trandom_list = {\n\t\t\t\t\t\t30 = {\n'),
    (b'\t\t\t\t\t\t70 = { }\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t}\n\t\t\tbuild_battery_park_button_click = {\n\t\t\t\tlog = "[GetDateText]: [Root.GetName]: Energy GUI build_battery_park_button_click"\n',
     b'\t\t\t\t\t\t70 = { }\n\t\t\t\t\t}\n\t\t\t\t}\n\n\t\t\t\t}\n\t\t\t}\n\t\t\tbuild_battery_park_button_click = {\n\t\t\t\tlog = "[GetDateText]: [Root.GetName]: Energy GUI build_battery_park_button_click"\n'),
    (b'\t\t\t\t\t\t\t}\n\t\t\t}\n\t\t\tcountry_view_flag_button1_click = {\n\t\t\t\tclear_variable = nuclear_fuel_selling_selected_TAG\n\t\t\t\tclear_array = temp_nuclear_fuel_sell_selection_countries\n\t\t\t\tevery_other_country = {\n\t\t\t\t\tif = {\n\t\t\t\t\t\tlimit = { has_nuclear_reactors = yes }\n\t\t\t\t\t\tROOT = { add_to_array = { temp_nuclear_fuel_sell_selection_countries = PREV.id } }\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t\tset_country_flag = open_nuclear_fuel_sell_country_selection\n\t\t\t\tingame_update_setup = yes\n\t\t\t}\n\t\t\tincrease_energy_ammount_number_click = {\n\t\t\t\tadd_to_variable = { temp_energy_ammount = 1 }\n',
     b'\t\t\t\t\t\t\t}\n\t\t\t}\n\t\t\tcountry_view_flag_button1_click = {\n\t\t\t\tif = { limit = { NOT = { has_country_flag = eon_nuclear_fuel_trade_reserved } }\n\t\t\t\tclear_variable = nuclear_fuel_selling_selected_TAG\n\t\t\t\tclear_array = temp_nuclear_fuel_sell_selection_countries\n\t\t\t\tevery_other_country = {\n\t\t\t\t\tif = {\n\t\t\t\t\t\tlimit = { exists = yes OR = { has_nuclear_reactors = yes check_variable = { enrichment_facilities > 0 } check_variable = { var_reactor_material_stockpile > 0 } } }\n\t\t\t\t\t\tROOT = { add_to_array = { temp_nuclear_fuel_sell_selection_countries = PREV.id } }\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t\tset_country_flag = open_nuclear_fuel_sell_country_selection\n\t\t\t\tingame_update_setup = yes\n\n\t\t\t\t}\n\t\t\t}\n\t\t\tincrease_energy_ammount_number_click = {\n\t\t\t\tadd_to_variable = { temp_energy_ammount = 1 }\n'),
    (b'\t\t\t\tingame_update_setup = yes\n\t\t\t}\n\t\t\tincrease_nuclear_fuel_ammount_number_click = {\n\t\t\t\tadd_to_variable = { temp_nuclear_fuel_ammount = 100 }\n\t\t\t\tingame_update_setup = yes\n\t\t\t}\n\t\t\tdecrease_nuclear_fuel_ammount_number_click = {\n\t\t\t\tadd_to_variable = { temp_nuclear_fuel_ammount = -100 }\n\t\t\t\tingame_update_setup = yes\n\t\t\t}\n\t\t\tincrease_nuclear_fuel_price_number_click = {\n\t\t\t\tadd_to_variable = { temp_nuclear_fuel_price = 0.01 }\n\t\t\t\tingame_update_setup = yes\n\t\t\t}\n\t\t\tdecrease_nuclear_fuel_price_number_click = {\n\t\t\t\tadd_to_variable = { temp_nuclear_fuel_price = -0.01 }\n\t\t\t\tingame_update_setup = yes\n\t\t\t}\n\t\t\tconfirm_energy_sell_click = {\n\t\t\t\tif = {\n',
     b'\t\t\t\tingame_update_setup = yes\n\t\t\t}\n\t\t\tincrease_nuclear_fuel_ammount_number_click = {\n\t\t\t\tif = { limit = { NOT = { has_country_flag = eon_nuclear_fuel_trade_reserved } }\n\t\t\t\tadd_to_variable = { temp_nuclear_fuel_ammount = 100 }\n\t\t\t\tingame_update_setup = yes\n\n\t\t\t\t}\n\t\t\t}\n\t\t\tdecrease_nuclear_fuel_ammount_number_click = {\n\t\t\t\tif = { limit = { NOT = { has_country_flag = eon_nuclear_fuel_trade_reserved } }\n\t\t\t\tadd_to_variable = { temp_nuclear_fuel_ammount = -100 }\n\t\t\t\tingame_update_setup = yes\n\n\t\t\t\t}\n\t\t\t}\n\t\t\tincrease_nuclear_fuel_price_number_click = {\n\t\t\t\tif = { limit = { NOT = { has_country_flag = eon_nuclear_fuel_trade_reserved } }\n\t\t\t\tadd_to_variable = { temp_nuclear_fuel_price = 0.01 }\n\t\t\t\tingame_update_setup = yes\n\n\t\t\t\t}\n\t\t\t}\n\t\t\tdecrease_nuclear_fuel_price_number_click = {\n\t\t\t\tif = { limit = { NOT = { has_country_flag = eon_nuclear_fuel_trade_reserved } }\n\t\t\t\tadd_to_variable = { temp_nuclear_fuel_price = -0.01 }\n\t\t\t\tingame_update_setup = yes\n\n\t\t\t\t}\n\t\t\t}\n\t\t\tconfirm_energy_sell_click = {\n\t\t\t\tif = {\n'),
    (b'\t\t\t\t\t\t\t}\n\t\t\t}\n\t\t\tconfirm_nuclear_fuel_sell_click = {\n\t\t\t\tif = {\n\t\t\t\t\tlimit = { check_variable = { temp_nuclear_fuel_ammount > 0 } }\n\t\t\t\t\tset_country_flag = currently_considering_an_offer\n\t\t\t\t\tvar:nuclear_fuel_selling_selected_TAG = {\n\t\t\t\t\t\tset_country_flag = currently_considering_an_offer\n\t\t\t\t\t\tcountry_event = energy.1\n\t\t\t\t\t}\n\t\t\t\t\tif = {\n\t\t\t\t\t\tlimit = { is_ai = yes }\n\t\t\t\t\t\tset_country_flag = { flag = energy_nuclear_calldown@nuclear_fuel_selling_selected_TAG days = 365 value = 1 }\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t\telse_if = {\n\t\t\t\t\tlimit = { check_variable = { temp_nuclear_fuel_ammount < 0 } }\n\t\t\t\t\tset_country_flag = currently_considering_an_offer\n\t\t\t\t\tvar:nuclear_fuel_selling_selected_TAG = {\n\t\t\t\t\t\tset_country_flag = currently_considering_an_offer\n\t\t\t\t\t\tcountry_event = energy.10\n\t\t\t\t\t}\n\t\t\t\t\tif = {\n\t\t\t\t\t\tlimit = { is_ai = yes }\n\t\t\t\t\t\tset_country_flag = { flag = energy_nuclear_calldown@nuclear_fuel_selling_selected_TAG days = 365 value = 1 }\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t}\n\t\t}\n\n',
     b'\t\t\t\t\t\t\t}\n\t\t\t}\n\t\t\tconfirm_nuclear_fuel_sell_click = {\n\t\t\t\teon_nuclear_fuel_trade_send = yes\n\t\t\t}\n\t\t}\n\n'),
    (b'\t\t\t\t\tbase = 10000\n\t\t\t\t\tmodifier = {\n\t\t\t\t\t\tfactor = 0\n\t\t\t\t\t\thas_country_flag = energy_nuclear_calldown@nuclear_fuel_selling_selected_TAG\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t}\n',
     b'\t\t\t\t\tbase = 10000\n\t\t\t\t\tmodifier = {\n\t\t\t\t\t\tfactor = 0\n\t\t\t\t\t\tvar:nuclear_fuel_selling_selected_TAG = { PREV = { has_country_flag = energy_nuclear_calldown@PREV } }\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t}\n'),
    (b'\t\teffects = {\n\t\t\tcountry_list_flag_button_click = {\n\t\t\t\tset_variable = { nuclear_fuel_selling_selected_TAG = ROOT.temp_nuclear_fuel_sell_selection_countries^i }\n\t\t\t\tset_variable = { temp_nuclear_fuel_price = 0.05 }\n\t\t\t\tclr_country_flag = open_nuclear_fuel_sell_country_selection\n\t\t\t\tingame_update_setup = yes\n\t\t\t}\n',
     b'\t\teffects = {\n\t\t\tcountry_list_flag_button_click = {\n\t\t\t\tset_variable = { nuclear_fuel_selling_selected_TAG = ROOT.temp_nuclear_fuel_sell_selection_countries^i }\n\t\t\t\tset_variable = { temp_nuclear_fuel_price = 0.5 }\n\t\t\t\tclr_country_flag = open_nuclear_fuel_sell_country_selection\n\t\t\t\tingame_update_setup = yes\n\t\t\t}\n'),
    (b'\n\t\t\t\t\tcheck_variable = { var_reactor_material_stockpile < 5000 }\n', b'\n\t\t\t\t\t# Preserve the legacy fuel duration after converting stock units to kg.\n\t\t\t\t\tcheck_variable = { var_reactor_material_stockpile < 288500 }\n'),
    (b'\n\t\t\t\t\t\tcheck_variable = { var_reactor_material_stockpile < 5000 }\n', b'\n\t\t\t\t\t\t# Preserve the legacy fuel duration after converting stock units to kg.\n\t\t\t\t\t\tcheck_variable = { var_reactor_material_stockpile < 288500 }\n'),
]

def restore_uranium_reward(data):
    assert data.count(KG_REACTOR_REWARD) == 1, 'Changed/missing canonical kg reward wrapper'
    return data.replace(KG_REACTOR_REWARD, LEGACY_REACTOR_REWARD)


def restore_uranium_gui(data):
    for before, after in reversed(GUI_REPAIRS):
        assert data.count(after) == 1, 'Changed/missing canonical uranium GUI patch'
        data = data.replace(after, before)
    return data


def negative_controls(energy, gui, expected_energy, expected_gui):
    """Reject altered conversion/initialization and unrelated effect/UI bytes."""
    cases = []
    for label, mutated in (
        ('wrong_reward_scale', energy.replace(b'= 57.7 }', b'= 57.8 }', 1)),
        ('missing_reward_initialization', energy.replace(b'\teon_uranium_initialize = yes\n', b'', 1)),
    ):
        try:
            restored = restore_uranium_reward(mutated)
            assert restored == expected_energy
        except AssertionError:
            cases.append(label)
        else:
            raise AssertionError('Accepted negative control: '+label)
    unrelated_energy = energy.replace(b'add_fuel = 50000', b'add_fuel = 50001', 1)
    assert unrelated_energy != energy
    assert restore_uranium_reward(unrelated_energy) != expected_energy
    cases.append('unrelated_energy_effect_change')
    for label, mutated in (
        ('wrong_gui_reward_capacity', gui.replace(b'eon_requested_facilities = 3', b'eon_requested_facilities = 4', 1)),
        ('unconverted_gui_low_stock_threshold', gui.replace(b'< 288500', b'< 5000', 1)),
        ('unrelated_gui_fuel_action', gui.replace(b'buy_fuel_for_money_button_click', b'buy_fuel_for_money_button_broken', 1)),
    ):
        assert mutated != gui
        try:
            restored = restore_uranium_gui(mutated)
            assert restored == expected_gui
        except AssertionError:
            cases.append(label)
        else:
            raise AssertionError('Accepted negative control: '+label)
    return cases
