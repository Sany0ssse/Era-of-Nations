"""Check legacy fuel durations and the actual focus-reward tooltip, without HOI4."""
from copy import deepcopy
from pathlib import Path
import json
import math
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from source_model import Source, Model, p, ROOT

GUI = 'common/scripted_guis/01_energy_gui.txt'
EVENTS = 'events/00_Energy_events.txt'
REWARD = 'change_reactor_grade_material_effect'
TOOLTIP = REWARD + '_tt'


def walk(nodes):
    for node in nodes:
        yield node
        if isinstance(node[2], list):
            yield from walk(node[2])


def stock_checks(nodes):
    return [node for node in walk(nodes) if node[0] == 'check_variable'
            and len(node[2]) == 1 and node[2][0][0] == 'var_reactor_material_stockpile']


def actual_predicates(source):
    gui = source.hook(GUI, ['scripted_gui', 'energy_scripted_gui'])
    checks = p.one(gui, 'ai_check')
    and_nodes = [value for key, op, value in walk(checks) if key == 'AND' and stock_checks(value)]
    assert len(and_nodes) == 1
    weights = p.one(p.one(p.one(gui, 'ai_weights'), 'build_enrichment_facility_button_click'), 'ai_will_do')
    modifiers = [value for key, op, value in weights if key == 'modifier' and stock_checks(value)]
    assert len(modifiers) == 1
    weight_predicate = [node for node in modifiers[0] if node[0] not in ('add', 'factor')]
    events = source.hook(EVENTS, [])
    event = [value for key, op, value in events if key == 'country_event' and p.one(value, 'id') == 'energy.10']
    assert len(event) == 1
    immediate = p.one(event[0], 'immediate')
    own = [value for key, op, value in immediate if key == 'if'
           and stock_checks(p.one(value, 'limit'))
           and any(node[2][0][2] == '173100' or node[2][0][2] == '3000'
                   for node in stock_checks(p.one(value, 'limit')))]
    assert len(own) == 1
    suppliers = [value for key, op, value in walk(immediate) if key == 'any_other_country']
    assert len(suppliers) == 1
    return [
        ('gui_low_stock_check', and_nodes[0], 5000, '<'),
        ('gui_low_stock_build_weight', weight_predicate, 5000, '<'),
        ('incoming_offer_low_stock_bonus', p.one(own[0], 'limit'), 3000, '<'),
        ('incoming_offer_alternative_supplier', suppliers[0], 1500, '>'),
    ]


def locale_values():
    values = {}
    for language in ('english', 'russian'):
        raw = (ROOT / f'localisation/{language}/replace/eon_uranium_l_{language}.yml').read_bytes()
        assert raw.startswith(b'\xef\xbb\xbf')
        matches = re.findall(r'^\s*' + TOOLTIP + r':0 "(.*)"\r?$', raw.decode('utf-8-sig'), re.M)
        assert len(matches) == 1
        values[language] = matches[0]
    return values


def verify(source, locales):
    passed = []
    for name, predicate, old_threshold, operator in actual_predicates(source):
        checks = stock_checks(predicate)
        assert len(checks) == 1
        variable, actual_operator, scalar = checks[0][2][0]
        threshold = float(scalar)
        assert actual_operator == operator
        # Preserve the actual old stock duration, not a new procurement policy.
        assert math.isclose(threshold / 1154, old_threshold / 20, rel_tol=1e-12)
        for stock in (threshold - 1, threshold, threshold + 1):
            model = Model(source)
            model.entities['GLOBAL'].arrays['enrichment_countries'] = [1]
            model.country().variables.update(var_reactor_material_stockpile=stock,
                                             nuclear_reactor_fuel_production=2308,
                                             nuclear_fuel_consumption=1154)
            expected = stock < threshold if operator == '<' else stock > threshold
            assert model.trigger(predicate) == expected, (name, stock)
        passed.append(name + '_duration_and_three_boundary_values')

    reward = source.effects[REWARD]
    tooltip_indices = [index for index, node in enumerate(reward)
                       if node == ('custom_effect_tooltip', '=', TOOLTIP)]
    assert len(tooltip_indices) == 1
    index = tooltip_indices[0]
    assert any(node[0] == 'add_to_variable' for node in reward[index + 1:])
    for amount in (0, 100, 500, 1500):
        model = Model(source)
        model.country().variables['var_reactor_material_stockpile'] = 1000
        model.temp['change_resource'] = amount
        # Execute the real prefix up to the render point, with the same shared
        # execution temporary as a focus caller; this is not a native UI test.
        model.effect(reward[:index], [model.current])
        displayed = model.value('eon_legacy_reactor_reward_kg', [model.current])
        assert math.isclose(displayed, amount * 57.7, rel_tol=1e-12, abs_tol=1e-8)
        assert model.country().variables['var_reactor_material_stockpile'] == 1000
        model.effect(reward[index:], [model.current])
        assert math.isclose(model.country().variables['var_reactor_material_stockpile'] - 1000,
                            displayed, rel_tol=1e-12, abs_tol=1e-8)
    passed.append('actual_reward_prefix_displays_exact_kg_before_credit')
    for language, value in locales.items():
        assert '[?eon_legacy_reactor_reward_kg|0+]' in value
        assert '[?change_resource' not in value
        assert ('kg U' if language == 'english' else 'кг U') in value
        passed.append(language + '_override_uses_converted_quantity_and_explicit_unit')
    return passed


def main():
    source, locales = Source(), locale_values()
    passed = verify(source, locales)
    controls = []
    for rel, before, after, label in (
        (GUI, b'< 288500', b'< 5000', 'old_gui_check_threshold'),
        (EVENTS, b'< 173100', b'< 3000', 'old_incoming_offer_threshold'),
        (EVENTS, b'> 86550', b'> 1500', 'old_alternative_supplier_threshold'),
    ):
        mutant = deepcopy(source)
        assert before in mutant.raw[rel]
        mutant.raw[rel] = mutant.raw[rel].replace(before, after, 1)
        try:
            verify(mutant, locales)
        except AssertionError:
            controls.append(label)
        else:
            raise AssertionError('Accepted regression: ' + label)
    mutant = deepcopy(source)
    raw = mutant.raw[GUI]
    index = raw.rfind(b'< 288500')
    assert index > raw.find(b'< 288500')
    mutant.raw[GUI] = raw[:index] + raw[index:].replace(b'< 288500', b'< 5000', 1)
    try:
        verify(mutant, locales)
    except AssertionError:
        controls.append('old_gui_build_weight_threshold')
    else:
        raise AssertionError('Accepted AI construction-weight regression')
    mutant = deepcopy(source)
    nodes = mutant.effects[REWARD]
    tooltip = next(node for node in nodes if node[0] == 'custom_effect_tooltip')
    nodes.remove(tooltip)
    nodes.insert(0, tooltip)
    try:
        verify(mutant, locales)
    except AssertionError:
        controls.append('tooltip_before_converted_reward_is_initialized')
    else:
        raise AssertionError('Accepted tooltip ordering regression')
    mutant_locales = dict(locales)
    mutant_locales['russian'] = mutant_locales['russian'].replace('eon_legacy_reactor_reward_kg', 'change_resource')
    try:
        verify(source, mutant_locales)
    except AssertionError:
        controls.append('tooltip_reports_unconverted_reward')
    else:
        raise AssertionError('Accepted tooltip quantity regression')
    print(json.dumps({'checks_passed': True, 'actual_source_cases': passed,
                      'negative_controls': controls, 'source_sha256': source.sha256,
                      'native_game_behavior_tested': False, 'native_ui_rendering_proven': False}, indent=2))


if __name__ == '__main__':
    main()
