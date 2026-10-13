"""Validate the private test panel's actual AST and bounded country effects.

This is a new, narrowly scoped source/model validator. Importing the historical
hotkey module supplies its parser only; its tests and inventories never run.
Native keyboard delivery, visual layout, caps and two-client MP are not modeled.
"""
from collections import Counter
from copy import deepcopy
from decimal import Decimal
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct

GAME = (
    'interface/eon_cheat_hotkey.gui',
    'common/scripted_effects/eon_cheat_access_effects.txt',
    'localisation/english/eon_cheat_hotkey_l_english.yml',
    'localisation/russian/eon_cheat_hotkey_l_russian.yml',
    'interface/eon_debug_panel.gui',
    'common/scripted_effects/eon_debug_panel_effects.txt',
    'common/scripted_guis/eon_debug_panel_gui.txt',
)
CONTEXT = 'common/scripted_guis/eon_cheat_hotkey_gui.txt'
SPRITES = 'interface/MD_protest_decision.gfx'
EMPTY_TEXTURE = 'gfx/interface/scripted_gui/expected_spending/empty.dds'
PARSER = 'tools/validation/cheat_hotkey/test_hotkey.py'
HISTORICAL = (PARSER, 'tools/validation/cheat_hotkey/README.md')
OVERRIDE, OPEN, AMOUNT = 'eon_cheat_override', 'cheat_decisions_open', 'eon_debug_amount'
SUBFLAGS = {OPEN+'_'+suffix for suffix in ('factions', 'parties', 'money', 'manpower', 'operatives')}
COUNTERS = ('army_experience', 'navy_experience', 'air_experience', 'command_power', 'political_power')
NATIVE_EFFECTS = {
    'army_experience': 'army_experience', 'navy_experience': 'navy_experience',
    'air_experience': 'air_experience', 'add_command_power': 'command_power',
    'add_political_power': 'political_power',
}
# These are behavioral expectations, independent of the parsed helper bodies.
ACTION_DELTAS = {
    'xp': (1, 1, 1, 0, 0), 'army': (1, 0, 0, 0, 0),
    'navy': (0, 1, 0, 0, 0), 'air': (0, 0, 1, 0, 0),
    'cp': (0, 0, 0, 1, 0), 'pp': (0, 0, 0, 0, 1),
}
VALID_AMOUNTS = (1, 10, 100, 1000)
INVALID_AMOUNTS = (0, 5, -1, 1000000, None)
groups = Counter()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def check(group, condition, context=None):
    assert condition, (group, context)
    groups[group] += 1


def new_state():
    return {
        'global': {'unrelated_global'},
        'countries': {
            tag: {
                'ai': tag == 'AI', 'flags': {'unrelated_'+tag},
                'variables': {'unrelated_value': i*19},
                'counters': dict(zip(COUNTERS, (i*7, i*11, i*13, i*17, i*23))),
                'unrelated': {'cash': i*31, 'equipment': {'tank': i*5}},
            }
            for i, tag in enumerate(('A', 'B', 'AI'), 1)
        },
    }


def amount_in(state, actor):
    return state['countries'][actor]['variables'].get(AMOUNT, 0)


def eligible(state, actor):
    country = state['countries'][actor]
    return not country['ai'] and OVERRIDE in country['flags']


class Model:
    """Execute visited native primitives, rejecting all unmodeled commands.

    The five counters represent requested effect deltas. Native clamps, GUI
    event delivery and transport are deliberately outside this source model.
    """
    def __init__(self, module, effects):
        self.one = module.one
        self.effects = effects

    def scalar(self, value, state, actor):
        assert isinstance(value, str), ('Expected scalar', value)
        try:
            return Decimal(value)
        except Exception:
            variables = state['countries'][actor]['variables']
            assert value in variables, ('Missing effect variable', value)
            return Decimal(str(variables[value]))

    def trigger(self, nodes, state, actor, depth=0):
        assert depth < 24, 'Unexpected recursion'
        results = []
        for key, op, value in nodes:
            assert op == '=', ('Unknown trigger operator', key, op)
            if key in ('AND', 'OR', 'NOT'):
                assert isinstance(value, list)
                children = [self.trigger([row], state, actor, depth+1) for row in value]
                outcome = any(children) if key == 'OR' else all(children)
                if key == 'NOT':
                    outcome = not outcome
            elif key == 'is_ai':
                assert value in ('yes', 'no')
                outcome = state['countries'][actor]['ai'] == (value == 'yes')
            elif key == 'has_country_flag':
                outcome = value in state['countries'][actor]['flags']
            elif key == 'has_global_flag':
                outcome = value in state['global']
            elif key == 'always':
                assert value in ('yes', 'no')
                outcome = value == 'yes'
            elif key == 'check_variable':
                assert isinstance(value, list) and len(value) == 1
                variable, comparison, target = value[0]
                assert comparison == '=', ('Unmodeled variable comparison', comparison)
                outcome = Decimal(str(state['countries'][actor]['variables'].get(variable, 0))) == Decimal(target)
            else:
                raise AssertionError(('Unknown visited trigger', key))
            results.append(outcome)
        return all(results)

    def effect(self, nodes, state, actor, depth=0):
        assert depth < 24, 'Unexpected recursion'
        at = 0
        while at < len(nodes):
            key, op, value = nodes[at]
            at += 1
            assert op == '=', ('Unknown effect operator', key, op)
            if key == 'if':
                branches = [(key, op, value)]
                while at < len(nodes) and nodes[at][0] in ('else_if', 'else'):
                    branches.append(nodes[at])
                    at += 1
                for kind, branch_op, body in branches:
                    assert branch_op == '=' and isinstance(body, list)
                    if kind == 'else' or self.trigger(self.one(body, 'limit'), state, actor, depth+1):
                        self.effect([row for row in body if row[0] != 'limit'], state, actor, depth+1)
                        break
            elif key in ('hidden_effect', 'effect'):
                assert isinstance(value, list)
                self.effect(value, state, actor, depth+1)
            elif key == 'set_country_flag':
                assert isinstance(value, str)
                state['countries'][actor]['flags'].add(value)
            elif key == 'clr_country_flag':
                assert isinstance(value, str)
                state['countries'][actor]['flags'].discard(value)
            elif key == 'set_variable':
                assert isinstance(value, list) and len(value) == 1
                variable, var_op, amount = value[0]
                assert var_op == '='
                state['countries'][actor]['variables'][variable] = self.scalar(amount, state, actor)
            elif key in NATIVE_EFFECTS:
                state['countries'][actor]['counters'][NATIVE_EFFECTS[key]] += self.scalar(value, state, actor)
            elif key in self.effects:
                assert value == 'yes', ('Expected scripted effect yes', key, value)
                self.effect(self.effects[key], state, actor, depth+1)
            else:
                raise AssertionError(('Unknown visited effect', key))


def expected_toggle(before, actor):
    expected = deepcopy(before)
    country = expected['countries'][actor]
    if country['ai']:
        return expected
    if OVERRIDE in country['flags']:
        country['flags'].difference_update({OVERRIDE, OPEN, *SUBFLAGS})
    else:
        country['flags'].update({OVERRIDE, OPEN})
        country['variables'][AMOUNT] = 100
    return expected


def behavior(model, panel, listener, module):
    callbacks = dict((key, value) for key, op, value in module.one(panel, 'effects'))
    triggers = dict((key, value) for key, op, value in module.one(panel, 'triggers'))
    visible = module.one(panel, 'visible')
    hotkey = module.one(module.one(listener, 'effects'), 'eon_cheat_toggle_button_click')

    # Each actor has nonzero, different counters; a mutation of the wrong country
    # or additional counter is caught by whole-state comparison, not a call log.
    for actor in ('A', 'B', 'AI'):
        for override in (False, True):
            for amount in (*VALID_AMOUNTS, *INVALID_AMOUNTS):
                before = new_state()
                if override:
                    before['countries'][actor]['flags'].add(OVERRIDE)
                if amount is not None:
                    before['countries'][actor]['variables'][AMOUNT] = amount
                check('panel_visibility', model.trigger(visible, before, actor) == eligible(before, actor), (actor, override, amount))
                for action, multipliers in ACTION_DELTAS.items():
                    callback = f'eon_debug_{action}_button_click'
                    permitted = eligible(before, actor) and amount in VALID_AMOUNTS
                    check('action_enable', model.trigger(triggers[callback+'_enabled'], before, actor) == permitted, (actor, override, amount, action))
                    expected = deepcopy(before)
                    if permitted:
                        for counter, multiplier in zip(COUNTERS, multipliers):
                            expected['countries'][actor]['counters'][counter] += amount*multiplier
                    state = deepcopy(before)
                    # Deliberately run even a disabled/stale callback: the helper
                    # itself must defend against unauthorized or invalid input.
                    model.effect(callbacks[callback], state, actor)
                    check('exact_country_counter_result', state == expected, (actor, override, amount, action))
                    check('other_country_unchanged', all(state['countries'][tag] == before['countries'][tag] for tag in before['countries'] if tag != actor), (actor, action))
                    check('global_unchanged', state['global'] == before['global'], (actor, action))

    for actor in ('A', 'B', 'AI'):
        for override in (False, True):
            for amount in VALID_AMOUNTS:
                before = new_state()
                before['countries'][actor]['variables'][AMOUNT] = -999
                if override:
                    before['countries'][actor]['flags'].add(OVERRIDE)
                callback = f'eon_debug_amount_{amount}_button_click'
                check('selector_enable', model.trigger(triggers[callback+'_enabled'], before, actor) == eligible(before, actor), (actor, override, amount))
                expected = deepcopy(before)
                if eligible(before, actor):
                    expected['countries'][actor]['variables'][AMOUNT] = amount
                state = deepcopy(before)
                model.effect(callbacks[callback], state, actor)
                check('selector_exact_result', state == expected, (actor, override, amount))

    for actor in ('A', 'B', 'AI'):
        for override in (False, True):
            for opened in (False, True):
                for subs in (False, True):
                    before = new_state()
                    if override:
                        before['countries'][actor]['flags'].add(OVERRIDE)
                    if opened:
                        before['countries'][actor]['flags'].add(OPEN)
                    if subs:
                        before['countries'][actor]['flags'].update(SUBFLAGS)
                    before['countries'][actor]['variables'][AMOUNT] = -5
                    expected = expected_toggle(before, actor)
                    state = deepcopy(before)
                    model.effect(hotkey, state, actor)
                    check('hotkey_exact_state', state == expected, (actor, override, opened, subs))
                    check('hotkey_counters_unchanged', all(state['countries'][tag]['counters'] == before['countries'][tag]['counters'] for tag in before['countries']), actor)

    # Close is not a second opener, and a callback captured before closure must
    # be harmless after the flag disappears, even when dispatched directly.
    for actor in ('A', 'B', 'AI'):
        for override in (False, True):
            before = new_state()
            before['countries'][actor]['flags'].update({OPEN, *SUBFLAGS})
            before['countries'][actor]['variables'][AMOUNT] = 100
            if override:
                before['countries'][actor]['flags'].add(OVERRIDE)
            callback = 'eon_debug_close_button_click'
            permitted = eligible(before, actor)
            check('close_enable', model.trigger(triggers[callback+'_enabled'], before, actor) == permitted, (actor, override))
            expected = expected_toggle(before, actor) if permitted else deepcopy(before)
            state = deepcopy(before)
            model.effect(callbacks[callback], state, actor)
            check('close_exact_state', state == expected, (actor, override))
            for name, effect in callbacks.items():
                after_close = deepcopy(state)
                model.effect(effect, after_close, actor)
                check('stale_callback_no_effect', after_close == state, (actor, override, name))

    # Human countries can select distinct amounts simultaneously, then reopening
    # A must not reset B's selector or resources.
    state = new_state()
    model.effect(hotkey, state, 'A')
    model.effect(hotkey, state, 'B')
    model.effect(callbacks['eon_debug_amount_10_button_click'], state, 'A')
    model.effect(callbacks['eon_debug_amount_1000_button_click'], state, 'B')
    before = deepcopy(state)
    model.effect(callbacks['eon_debug_cp_button_click'], state, 'A')
    model.effect(callbacks['eon_debug_xp_button_click'], state, 'B')
    expected = deepcopy(before)
    expected['countries']['A']['counters']['command_power'] += 10
    for counter in COUNTERS[:3]:
        expected['countries']['B']['counters'][counter] += 1000
    check('two_country_different_amounts', state == expected)
    b_before = deepcopy(state['countries']['B'])
    model.effect(hotkey, state, 'A')
    model.effect(hotkey, state, 'A')
    check('reopen_resets_only_actor_amount', amount_in(state, 'A') == 100 and state['countries']['B'] == b_before)

    # Personal access is independent of both legacy game-rule flags. The
    # existing rules and the other country's resources survive each transition.
    for allow in (False, True):
        for toggling in (False, True):
            state = new_state()
            if allow:
                state['global'].add('game_rule_allow_cheat_decisions')
            if toggling:
                state['global'].add('game_rule_allow_toggling_cheat_decisions')
            before = deepcopy(state)
            model.effect(hotkey, state, 'A')
            expected = expected_toggle(before, 'A')
            check('legacy_rules_personal_open', state == expected, (allow, toggling))
            model.effect(callbacks['eon_debug_cp_button_click'], state, 'A')
            expected['countries']['A']['counters']['command_power'] += 100
            check('legacy_rules_personal_counter_result', state == expected, (allow, toggling))
            before_close = deepcopy(state)
            model.effect(hotkey, state, 'A')
            check('legacy_rules_personal_close', state == expected_toggle(before_close, 'A'), (allow, toggling))

    # Country flags/variables are shared by co-op controllers of one country.
    # This is an explicit state-scope clarification, not a multiplayer test.
    controllers = {'pc_1': 'A', 'pc_2': 'A', 'friend': 'B'}
    state = new_state()
    model.effect(hotkey, state, controllers['pc_1'])
    model.effect(callbacks['eon_debug_amount_10_button_click'], state, controllers['pc_2'])
    before = deepcopy(state)
    for controller in ('pc_1', 'pc_2'):
        model.effect(callbacks['eon_debug_cp_button_click'], state, controllers[controller])
    expected = deepcopy(before)
    expected['countries']['A']['counters']['command_power'] += 20
    check('coop_shared_country_result', state == expected)
    model.effect(callbacks['eon_debug_close_button_click'], state, controllers['pc_2'])
    check('coop_close_shared_visibility', not model.trigger(visible, state, controllers['pc_1']))

    for kind in ('trigger', 'effect'):
        try:
            getattr(model, kind)([('unmodeled_'+kind, '=', 'yes')], new_state(), 'A')
        except AssertionError as error:
            check('model_rejects_unknown_primitives', 'Unknown visited' in str(error), kind)
        else:
            raise AssertionError(('Unknown primitive accepted', kind))


def collect(module, raw):
    nodes = module.ast(raw)
    check('duplicate_top_level_helpers', len({key for key, op, val in nodes}) == len(nodes))
    check('effect_definition_types', all(op == '=' and isinstance(val, list) for key, op, val in nodes))
    return dict((key, val) for key, op, val in nodes)


def locale(raw):
    entries = re.findall(r'^\s+([\w]+):\d+\s+"([^\r\n]*)"\s*$', raw.decode('utf-8-sig'), re.M)
    check('locale_unique_keys', len(entries) == len(set(key for key, value in entries)))
    return dict(entries)


def bindings(module, sources, panel, listener, effects):
    gui = module.one(module.ast(sources[GAME[4]]), 'guiTypes')
    window = module.one(gui, 'containerWindowType')
    check('panel_window_binding', module.one(window, 'name') == module.one(panel, 'window_name') == 'eon_debug_panel_window')
    check('panel_player_context', module.one(panel, 'context_type') == 'player_context')
    check('panel_topbar_parent', module.one(panel, 'parent_window_token') == 'top_bar')
    check('listener_player_context', module.one(listener, 'context_type') == 'player_context')
    buttons = {module.one(body, 'name'): body for key, op, body in window if key == 'buttonType'}
    check('panel_unique_button_names', len(buttons) == sum(key == 'buttonType' for key, op, body in window))
    expected = {f'eon_debug_amount_{amount}_button' for amount in VALID_AMOUNTS} | {f'eon_debug_{action}_button' for action in ACTION_DELTAS} | {'eon_debug_close_button'}
    check('panel_exact_button_set', set(buttons) == expected)
    callbacks = module.one(panel, 'effects')
    triggers = module.one(panel, 'triggers')
    check('panel_unique_callback_names', len(callbacks) == len({key for key, op, body in callbacks}))
    check('panel_unique_trigger_names', len(triggers) == len({key for key, op, body in triggers}))
    check('every_button_callback', {key for key, op, body in callbacks} == {name+'_click' for name in expected})
    check('every_button_guard', {key for key, op, body in triggers} == {name+'_click_enabled' for name in expected})
    check('every_callback_helper_exists', all(key in effects or key in ('if', 'limit', 'is_ai', 'has_country_flag') for row in callbacks for key, op, value in module.walk(row[2])))
    check('no_new_panel_shortcuts', not any(key == 'shortcut' for key, op, val in module.walk(gui)))
    hot_gui = module.one(module.ast(sources[GAME[0]]), 'guiTypes')
    hot_window = module.one(hot_gui, 'containerWindowType')
    hot_button = module.one(hot_window, 'buttonType')
    check('hotkey_window_binding', module.one(hot_window, 'name') == module.one(listener, 'window_name'))
    check('hotkey_button_binding', module.one(hot_button, 'name') == 'eon_cheat_toggle_button')
    check('hotkey_unchanged_single_shortcut', [(key, value) for key, op, value in module.walk(hot_gui) if key == 'shortcut'] == [('shortcut', 'shift+r')])
    check('listener_one_callback_only', [key for key, op, value in module.one(listener, 'effects')] == ['eon_cheat_toggle_button_click'])
    check('listener_empty_label', module.one(hot_button, 'buttonText') == '')
    check('listener_original_container_size', module.one(module.one(hot_window, 'size'), 'width') == '123' and module.one(module.one(hot_window, 'size'), 'height') == '34')
    sprite_name = module.one(hot_button, 'quadTextureSprite')
    sprites = module.one(module.ast(sources[SPRITES]), 'spriteTypes')
    sprite_matches = [body for key, op, body in sprites if module.one(body, 'name') == sprite_name]
    check('listener_existing_sprite_unique', len(sprite_matches) == 1)
    check('listener_existing_empty_sprite_binding', module.one(sprite_matches[0], 'texturefile').replace('\\', '/') == EMPTY_TEXTURE)
    texture = sources[EMPTY_TEXTURE]
    check('listener_dds_dxt1', texture[:4] == b'DDS ' and texture[84:88] == b'DXT1')
    height, width = struct.unpack_from('<II', texture, 12)
    blocks = ((width+3)//4)*((height+3)//4)
    check('listener_dds_single_surface_size', len(texture) == 128+blocks*8)
    # DXT1 transparent color requires c0 <= c1 and color index 3. Every
    # source pixel in this existing sprite is transparent, including padding.
    transparent = all(struct.unpack_from('<H', texture, offset)[0] <= struct.unpack_from('<H', texture, offset+2)[0]
                      and struct.unpack_from('<I', texture, offset+4)[0] == 0xffffffff
                      for offset in range(128, len(texture), 8))
    check('listener_texture_all_alpha_zero', transparent)
    check('listener_unscaled_button', not any(key == 'scale' for key, op, value in hot_button))
    check('listener_original_transparent_button_size', (width, height) == (28, 28))
    for path in GAME[2:4]:
        loc = locale(sources[path])
        check('listener_empty_tooltip', loc[module.one(hot_button, 'pdx_tooltip')] == '', path)
        for key in ('EON_CHEAT_HOTKEY_ON', 'EON_CHEAT_HOTKEY_OFF'):
            check('listener_empty_status_locale', loc[key] == '', (path, key))
        for key, op, value in module.walk(gui):
            if key in ('buttonText', 'text') and value:
                check('panel_localization_binding', value in loc and bool(loc[value]), (path, value))
        check('no_hotkey_public_locale_advertisement', not re.search(r'shift\s*\+\s*r', sources[path].decode('utf-8-sig'), re.I), path)
    for path in (GAME[1], GAME[5], GAME[6]):
        nodes = module.ast(sources[path])
        banned = {'log', 'country_event', 'news_event', 'every_country', 'random_country', 'set_global_flag', 'clr_global_flag', 'set_rule', 'set_game_rule', 'send_chat', 'console_command', 'execute_console'}
        check('no_broadcast_global_console_primitives', not any(key in banned for key, op, value in module.walk(nodes)), path)
        for key, op, value in module.walk(nodes):
            if key in ('set_country_flag', 'clr_country_flag'):
                check('only_owned_country_flags', value in {OVERRIDE, OPEN, *SUBFLAGS}, (path, value))
            if key == 'set_variable':
                check('only_owned_amount_variable', [var for var, var_op, amount in value] == [AMOUNT], path)
    expected_helpers = {'eon_toggle_cheat_access'} | {f'eon_debug_set_amount_{amount}' for amount in VALID_AMOUNTS} | {f'eon_debug_add_{action}' for action in ACTION_DELTAS}
    check('exact_supported_helper_set', set(effects) == expected_helpers)
    action_keys = {'if', 'limit', 'is_ai', 'has_country_flag', 'OR', 'check_variable', AMOUNT, *NATIVE_EFFECTS}
    for action in ACTION_DELTAS:
        body = effects['eon_debug_add_'+action]
        check('action_only_documented_country_effects', all(key in action_keys for key, op, value in module.walk(body)), action)
    selector_keys = {'if', 'limit', 'is_ai', 'has_country_flag', 'set_variable', AMOUNT}
    for amount in VALID_AMOUNTS:
        check('selector_only_owned_variable_effect', all(key in selector_keys for key, op, value in module.walk(effects[f'eon_debug_set_amount_{amount}'])), amount)


def main():
    args = argparse.ArgumentParser()
    public_root = Path(__file__).resolve().parents[3]
    args.add_argument('--root', type=Path, default=public_root if (public_root/PARSER).is_file() else Path.cwd())
    args.add_argument('--source-root', type=Path)
    args.add_argument('--manifest', type=Path)
    args.add_argument('--receipt', type=Path)
    config = args.parse_args()
    root = config.root.resolve()
    source_root = (config.source_root or root).resolve()
    historical_before = {path: sha((root/path).read_bytes()) for path in HISTORICAL}
    sources = {path: (source_root/path).read_bytes() for path in GAME}
    for path in (CONTEXT, SPRITES, EMPTY_TEXTURE):
        sources[path] = (root/path).read_bytes()
    before = {path: sha(raw) for path, raw in sources.items()}
    manifest_sha256 = None
    if config.manifest:
        manifest_raw = config.manifest.read_bytes()
        manifest_sha256 = sha(manifest_raw)
        manifest = json.loads(manifest_raw)
        check('candidate_manifest_exact_files', set(manifest['candidate_sha256']) == set(GAME))
        for path in GAME:
            check('candidate_manifest_sha256', before[path] == manifest['candidate_sha256'][path], path)
        for path in (CONTEXT, SPRITES, EMPTY_TEXTURE):
            check('unchanged_listener_dependency_pin', before[path] == manifest['source_sha256'][path], path)
    spec = spec_from_file_location('historical_cheat_ast_only', root/PARSER)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    check('historical_tests_not_run', not module.groups and not module.boundaries)
    effects = collect(module, sources[GAME[1]])
    for key, value in collect(module, sources[GAME[5]]).items():
        check('helper_names_unique_across_files', key not in effects, key)
        effects[key] = value
    panel = module.one(module.one(module.ast(sources[GAME[6]]), 'scripted_gui'), 'eon_debug_panel')
    listener = module.one(module.one(module.ast(sources[CONTEXT]), 'scripted_gui'), 'eon_cheat_hotkey')
    bindings(module, sources, panel, listener, effects)
    behavior(Model(module, effects), panel, listener, module)
    check('input_sources_stable_during_run', before == {path: sha((source_root/path if path in GAME else root/path).read_bytes()) for path in sources})
    historical_after = {path: sha((root/path).read_bytes()) for path in HISTORICAL}
    check('historical_validator_files_unchanged', historical_before == historical_after)
    check('historical_tests_not_run_after_parser_use', not module.groups and not module.boundaries)
    if config.manifest:
        check('candidate_manifest_stable_during_run', sha(config.manifest.read_bytes()) == manifest_sha256)
    report = {
        'result': 'pass', 'source_assertions': sum(groups.values()),
        'assertion_groups': dict(sorted(groups.items())),
        'source_root': str(source_root), 'source_sha256': before,
        'candidate_manifest_sha256': manifest_sha256,
        'historical_validation_sha256': historical_before,
        'validator_sha256': sha(Path(__file__).read_bytes()),
        'native_runtime': False, 'native_multiplayer': False,
        'proof_limits': [
            'Actual candidate GUI bindings, parsed effects and exact bounded country-state results only.',
            'Counter model records requested native deltas; it does not model engine caps or serialization.',
            'No native shortcut delivery, invisible hitbox, rendering, native console unlock or arbitrary command evaluation proof.',
            'No two-client multiplayer synchronization, no-chat runtime acceptance or campaign validation.',
            'Co-op mapping demonstrates country-scoped shared state, not independent client state or network behavior.',
            'Historical hotkey module imported for its parser only; no legacy inventory or cumulative tests were run.',
        ],
    }
    if config.receipt:
        config.receipt.parent.mkdir(parents=True, exist_ok=True)
        config.receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
