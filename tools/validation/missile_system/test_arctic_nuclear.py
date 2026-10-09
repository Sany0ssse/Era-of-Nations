"""Execute Arctic nuclear gates/payment/payload from current source AST.

Equipment removal, native random outcomes and UI refresh are explicit fixture
boundaries. Exact inverse compares every GUI byte and unchanged damage body
with the adopted baseline. This does not prove native raid/GUI/multiplayer use.
"""
from copy import deepcopy
from pathlib import Path
import json
import re
import subprocess

from test_launch import ast, one, read
import test_reserve_payment as payment
from readiness_model import assert_default_off_contract, is_ready

ROOT = Path(__file__).resolve().parents[3]
GUI = 'common/scripted_guis/arctic_scripted_gui.txt'
TRIGGER = 'common/scripted_triggers/eon_arctic_nuclear_launch_triggers.txt'
BASELINE = '2b6a26e76c80f7923d11ebc2c0694e882253fb32'
SHARED = 'eon_arctic_nuclear_launch_allowed'
SHORT, LONG = payment.SHORT, payment.LONG


def gui_parts(raw):
    gui = one(one(ast(raw.decode('utf-8-sig')), 'scripted_gui'), 'arctic_control_scripted_gui')
    return (one(one(gui, 'triggers'), 'arctic_big_red_button_click_enabled'),
            one(one(gui, 'effects'), 'arctic_big_red_button_click'))


def block_span(raw, key, tabs, occurrences=1):
    matches = list(re.finditer(rb'(?m)^'+b'\t'*tabs+key.encode()+rb' = \{', raw))
    assert len(matches) == occurrences, (key, len(matches))
    start = matches[0].start()
    opening = raw.index(b'{', start)
    depth, quoted, comment, escape = 0, False, False, False
    for index in range(opening, len(raw)):
        char = raw[index]
        if comment:
            if char in (10, 13): comment = False
        elif quoted:
            if escape: escape = False
            elif char == 92: escape = True
            elif char == 34: quoted = False
        elif char == 35: comment = True
        elif char == 34: quoted = True
        elif char == 123: depth += 1
        elif char == 125:
            depth -= 1
            if depth == 0: return start, opening, index+1
    raise AssertionError('Unbalanced GUI block')


def verify_bytes():
    before = subprocess.check_output(['git', 'show', BASELINE+':'+GUI], cwd=ROOT)
    current = (ROOT/GUI).read_bytes()
    ea, eo, ez = block_span(before, 'arctic_big_red_button_click_enabled', 3)
    ca, co, cz = block_span(before, 'arctic_big_red_button_click', 3, 2)
    body = before[co+1:cz-1]
    ha, ho, hz = block_span(body, 'hidden_effect', 4)
    transfer = body[ha:hz+1]
    assert transfer.count(b'send_equipment = {') == transfer.count(b'target = EUU') == 2
    assert b'equipment = '+SHORT.encode() in transfer and b'equipment = '+LONG.encode() in transfer
    payload = body.replace(transfer, b'')
    assert payload.endswith(b'\t\t\t')
    payload = payload[:-3]
    enabled = b'\t\t\tarctic_big_red_button_click_enabled = { eon_arctic_nuclear_launch_allowed = yes }'
    click = (b'\t\t\tarctic_big_red_button_click = {\n\t\t\t\tif = {\n'
             b'\t\t\t\t\tlimit = { eon_arctic_nuclear_launch_allowed = yes }\n'
             b'\t\t\t\t\tset_temp_variable = { eon_nuclear_scripted_request = 1 }\n'
             b'\t\t\t\t\teon_nuclear_scripted_pay_reserve = yes\n'
             b'\t\t\t\t\tif = {\n\t\t\t\t\t\tlimit = { has_country_flag = eon_nuclear_scripted_reserve_paid }')
    click += payload+b'\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t}'
    expected = before[:ea]+enabled+before[ez:ca]+click+before[cz:]
    assert current == expected, 'Unexpected GUI byte/payload/policy change'
    assert current.replace(enabled, before[ea:ez]).replace(click, before[ca:cz]) == before
    assert before.startswith(b'\xef\xbb\xbf') == current.startswith(b'\xef\xbb\xbf')
    assert b'\r' not in current and b'\r' not in before
    old_enabled, old_click = gui_parts(before)
    shared = one(read(TRIGGER), SHARED)
    assert shared == [('eon_nuclear_arsenal_ready', '=', 'yes')]+old_enabled
    return before, old_enabled, old_click


class Model:
    def __init__(self, short=1, long=1, mode='full', intercepted=False, transfer_fails=False, prototype_enabled=None):
        self.state = payment.fixture(short, long, 1, transfer_fails=transfer_fails, prototype_enabled=prototype_enabled)
        self.state['deployed'] = {SHORT: 0, LONG: 0}
        self.safety = mode == 'safety'
        self.remaining = 0 if mode in ('full', 'safety') else int(mode)
        self.shared = one(read(TRIGGER), SHARED)
        self.readiness = one(read('common/scripted_triggers/eon_nuclear_arsenal_triggers.txt'), 'eon_nuclear_arsenal_ready')
        self.command = 100
        self.ideas = set()
        self.controllers = ['B']
        self.enemies = {'B'}
        self.countries = ['A', 'B', 'C']
        self.buildings = {'rocket_site': 1, 'air_base': 0}
        self.bombers, self.navy = 0, 0
        self.techs = {'A': set(), 'B': {'gen_3_light'}, 'C': set()}
        self.scalars = {'global.arctic_military': 1, 'global.arctic_air': 1}
        self.arrays = {name: [1] for name in ('labs', 'military', 'navy', 'air', 'air_strngth', 'air_xp', 'air_ace', 'nuclear', 'unit_org', 'unit_strngth', 'unit_xp')}
        self.index = 0
        self.intercepted = intercepted
        self.news, self.threat, self.dirty = [], 0, 0

    def value(self, token):
        if token == 'eon_nuclear_arsenal_recovery_remaining': return self.remaining
        if token == 'NULL': return None
        if token == 'deployed_navy_manpower_k': return self.navy
        if token == 'num_equipment@strategic_bomber': return self.bombers
        if token in self.scalars: return self.scalars[token]
        if token.startswith('non_damaged_building_level@'): return self.buildings[token.split('@')[1]]
        return payment.value(self.state, token)

    def predicate(self, nodes, actor='A', previous='A'):
        answers = []
        for key, op, body in nodes:
            if key == 'NOT': allowed = not self.predicate(body, actor, previous)
            elif key == 'OR': allowed = any(self.predicate([node], actor, previous) for node in body)
            elif key == 'AND': allowed = self.predicate(body, actor, previous)
            elif key in ('custom_trigger_tooltip', 'custom_override_tooltip'):
                allowed = self.predicate([node for node in body if node[0] != 'tooltip'], actor, previous)
            elif key == SHARED: allowed = self.predicate(self.shared, actor, previous) == (body == 'yes')
            elif key == 'eon_nuclear_arsenal_ready':
                allowed = is_ready(not self.safety, self.state['flags'], self.remaining,
                                   self.state['prototype_enabled']) == (body == 'yes')
            elif key == 'command_power': allowed = self.command > float(body); assert op == '>'
            elif key == 'has_idea': allowed = body in self.ideas
            elif key == 'has_country_flag':
                allowed = self.safety if body == 'eon_nuclear_arsenal_safety_mode' else body in self.state['flags']
            elif key == 'check_variable':
                assert len(body) == 1
                token, comparator, expected = body[0]
                actual, expected = self.value(token), self.value(expected)
                allowed = {'=': actual == expected, '>': actual > expected, '<': actual < expected}[comparator]
            elif key == 'any_country': allowed = any(self.predicate(body, country, actor) for country in self.countries)
            elif key == 'any_controlled_state': allowed = self.predicate(body, actor, previous)
            elif key == 'is_in_array':
                assert one(body, 'array') == 'global.arctic_controllers' and one(body, 'value') == 'THIS'
                allowed = actor in self.controllers
            elif key == 'has_war_with':
                assert body == 'PREV'
                allowed = actor in self.enemies and previous == 'A'
            elif key == 'has_tech': allowed = body in self.techs[actor]
            else: raise AssertionError(('Unknown Arctic predicate', key, op, body))
            answers.append(allowed)
        return all(answers)

    def effect(self, nodes):
        for key, op, body in nodes:
            if key == 'if':
                if self.predicate(one(body, 'limit')): self.effect([node for node in body if node[0] != 'limit'])
            elif key == 'eon_nuclear_scripted_pay_reserve':
                self.state['ready'] = is_ready(not self.safety, self.state['flags'], self.remaining,
                                              self.state['prototype_enabled'])
                payment.execute(payment.HELPER, self.state)
            elif key in ('set_temp_variable', 'add_to_temp_variable', 'multiply_temp_variable'):
                assert len(body) == 1
                variable, comparator, amount = body[0]; assert comparator == '='
                quantity = self.value(amount)
                if key == 'add_to_temp_variable': quantity += self.state['temp'][variable]
                elif key == 'multiply_temp_variable': quantity *= self.state['temp'][variable]
                self.state['temp'][variable] = quantity
            elif key == 'clamp_temp_variable':
                variable = one(body, 'var')
                self.state['temp'][variable] = max(float(one(body, 'min')), min(float(one(body, 'max')), self.state['temp'][variable]))
            elif key == 'for_each_loop':
                assert one(body, 'array') == 'global.arctic_controllers' and one(body, 'index') == 'i'
                for self.index in range(len(self.controllers)):
                    self.effect([node for node in body if node[0] not in ('array', 'index')])
            elif key == 'set_variable':
                for variable, comparator, amount in body:
                    assert comparator == '=' and variable.endswith('^i')
                    name = variable.split('global.arctic_')[1].split('^')[0]
                    value = self.value(amount)
                    if name == 'controllers': self.controllers[self.index] = value
                    else: self.arrays[name][self.index] = value
            elif key == 'random':
                chance = self.value(one(body, 'chance')); assert 20 <= chance <= 70
                if not self.intercepted: self.effect([node for node in body if node[0] != 'chance'])
            elif key == 'add_command_power': self.command += float(body)
            elif key == 'news_event': self.news.append(body)
            elif key == 'add_named_threat': self.threat += float(one(body, 'threat'))
            elif key == 'update_arctic_dirty_variable': self.dirty += 1; assert body == 'yes'
            else: raise AssertionError(('Unknown Arctic effect', key, op, body))


def verify_case(model, effect, allowed):
    before = deepcopy(model)
    enabled, current_effect = gui_parts((ROOT/GUI).read_bytes())
    assert model.predicate(enabled) == allowed
    has_reserve = model.state['stock'][SHORT] > 0 or model.state['stock'][LONG] > 0
    paid = allowed and has_reserve and not model.state['native_transfer_fails']
    model.effect(effect)
    family = SHORT if before.state['stock'][SHORT] > 0 else LONG
    for kind in (SHORT, LONG):
        expected = int(paid and kind == family)
        assert before.state['stock'][kind]-model.state['stock'][kind] == expected
        assert model.state['sink'][kind] == expected
        assert model.state['deployed'][kind] == before.state['deployed'][kind]
    assert model.command == before.command-50*paid
    assert model.threat == 50*paid and model.dirty == int(paid)
    assert bool(model.news) == bool(paid and not model.intercepted)
    if not paid: assert model.controllers == before.controllers and model.arrays == before.arrays
    elif model.intercepted: assert model.controllers == before.controllers
    else: assert model.controllers == [None]*len(before.controllers)


def prototype_model(*args, **kwargs):
    """Retained safety/recovery cases opt into the disabled prototype."""
    return Model(*args, **kwargs, prototype_enabled=True)


def run():
    assert_default_off_contract()
    verify_bytes()
    enabled, effect = gui_parts((ROOT/GUI).read_bytes())
    cases = 0
    for mode in ('full', 'safety', '1', '4'):
        for short, long in ((0, 0), (1, 0), (0, 1), (1, 1), (5, 4)):
            for intercepted in (False, True):
                for transfer_fails in (False, True):
                    model = prototype_model(short, long, mode, intercepted, transfer_fails)
                    verify_case(model, effect, mode == 'full' and short+long > 0)
                    cases += 1
    controls = [('command_exact_50', False), ('command_51', True),
                ('no_use_case', False), ('non_nuclear_power', False), ('nuclear_energy', False),
                ('no_controller', False), ('friendly_controller', False), ('self_controller', False),
                ('mixed_controller', False), ('no_platform', False), ('bomber_platform', True),
                ('naval_platform', True), ('deployed_only_stale_reserve', False)]
    for label, allowed in controls:
        for intercepted in (False, True):
            model = prototype_model(intercepted=intercepted)
            if label.startswith('command_'): model.command = 50 if label == 'command_exact_50' else 51
            elif label in ('no_use_case', 'non_nuclear_power', 'nuclear_energy'): model.ideas.add(label)
            elif label == 'no_controller': model.controllers = []
            elif label == 'friendly_controller': model.enemies = set()
            elif label == 'self_controller': model.controllers = ['A']
            elif label == 'mixed_controller': model.controllers = ['B', 'C']
            elif label == 'no_platform': model.buildings['rocket_site'] = 0
            elif label == 'bomber_platform': model.buildings = {'rocket_site': 0, 'air_base': 1}; model.bombers = 1
            elif label == 'naval_platform': model.buildings['rocket_site'] = 0; model.navy = 1
            elif label == 'deployed_only_stale_reserve':
                model.state['stock'] = {SHORT: 0, LONG: 0}; model.state['deployed'][LONG] = 2
            verify_case(model, effect, allowed); cases += 1
    # A click already queued while enabled must repeat the entire source gate.
    for stale in ('safety', 'recovery', 'stock', 'controller', 'command', 'policy'):
        model = prototype_model(); assert model.predicate(enabled)
        if stale == 'safety': model.safety = True
        elif stale == 'recovery': model.remaining = 2
        elif stale == 'stock': model.state['stock'] = {SHORT: 0, LONG: 0}
        elif stale == 'controller': model.enemies = set()
        elif stale == 'command': model.command = 50
        else: model.ideas.add('no_use_case')
        verify_case(model, effect, False); cases += 1
    mutants = []
    for name in ('shared_readiness_removed', 'effect_gate_removed', 'payment_success_guard_removed', 'request_ten'):
        model = prototype_model()
        mutant = deepcopy(effect)
        outer = mutant[0][2]
        if name == 'shared_readiness_removed':
            model.safety = True; model.shared = [node for node in model.shared if node[0] != 'eon_nuclear_arsenal_ready']
            allowed = False
        elif name == 'effect_gate_removed':
            model.enemies = set(); outer[0] = ('limit', '=', []); allowed = False
        elif name == 'payment_success_guard_removed':
            model.state['native_transfer_fails'] = True
            paid_if = next(node[2] for node in outer if node[0] == 'if')
            paid_if[0] = ('limit', '=', []); allowed = True
        else:
            request = next(node[2] for node in outer if node[0] == 'set_temp_variable')
            request[0] = ('eon_nuclear_scripted_request', '=', '10'); allowed = True
        try: verify_case(model, mutant, allowed)
        except AssertionError: mutants.append(name)
        else: raise AssertionError(('Surviving Arctic mutation', name))
    default_off_cases = 0
    for mode in ('safety', '1', '4'):
        for short, long in ((0, 0), (1, 0), (0, 1)):
            for intercepted in (False, True):
                model = Model(short, long, mode, intercepted)
                verify_case(model, effect, short+long > 0)
                default_off_cases += 1
    # Disabled upkeep does not waive the existing diplomatic/target policy.
    model = Model(mode='safety')
    model.remaining = 4
    model.ideas.add('no_use_case')
    verify_case(model, effect, False)
    default_off_cases += 1
    print(json.dumps({'arctic_source_cases': cases, 'rejected_mutants': mutants,
                      'default_off_arctic_cases': default_off_cases,
                      'full_gui_byte_inverse_preserved': True, 'old_damage_body_preserved': True,
                      'one_reserve_family_paid_per_attempt': True,
                      'native_random_outcome_fixture_only': True,
                      'actual_human_gui_clicks_verified': False, 'native_arctic_use_verified': False}, indent=2))


if __name__ == '__main__': run()
