"""Execute the current Shift+R callback in a bounded country-flag model.

This is source validation, not proof of native keyboard or multiplayer delivery.
Historical validators are deliberately neither imported nor rewritten.
"""
from collections import Counter
from copy import deepcopy
from functools import lru_cache
from itertools import product
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '79c35a0673186223256a5146e7e2bb6809f5fe5f'
DECISIONS = 'common/decisions/Cheat Decisions.txt'
CATEGORY = 'common/decisions/categories/cheat_decision_categories.txt'
OLD_TEXT = 'common/scripted_localisation/00_cheat_decisions_scripted_localisation.txt'
TRIGGERS = 'common/scripted_triggers/eon_cheat_access_triggers.txt'
EFFECTS = 'common/scripted_effects/eon_cheat_access_effects.txt'
SCRIPT_GUI = 'common/scripted_guis/eon_cheat_hotkey_gui.txt'
SCRIPT_TEXT = 'common/scripted_localisation/eon_cheat_hotkey_scripted_localisation.txt'
GUI = 'interface/eon_cheat_hotkey.gui'
LOCALES = tuple(f'localisation/{lang}/eon_cheat_hotkey_l_{lang}.yml' for lang in ('english', 'russian'))
OLD_GAME = {DECISIONS, CATEGORY, OLD_TEXT}
NEW_GAME = {TRIGGERS, EFFECTS, SCRIPT_GUI, SCRIPT_TEXT, GUI, *LOCALES}
GAME = sorted(OLD_GAME | NEW_GAME)
GAME_PREFIXES = ('common/', 'interface/', 'localisation/', 'events/', 'history/', 'map/', 'gfx/',
                 'descriptions/', 'music/', 'portraits/', 'sound/', 'tutorial/', 'scenario_tests/')
GAME_ROOT_FILES = {'descriptor.mod', 'era_of_nations.mod', 'thumbnail.png'}
PUBLIC_TESTS = {'tools/validation/cheat_hotkey/test_hotkey.py', 'tools/validation/cheat_hotkey/README.md'}
OVERRIDE = 'eon_cheat_override'
OPEN = 'cheat_decisions_open'
SUBSECTIONS = tuple(OPEN+'_'+suffix for suffix in ('factions', 'parties', 'money', 'manpower', 'operatives'))
ALLOW = 'game_rule_allow_cheat_decisions'
TOGGLING = 'game_rule_allow_toggling_cheat_decisions'
ENABLE = 'enable_all_decisions'
TOKEN = re.compile(rb'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|[=<>!]+|[^\s{}=<>!#"]+')
groups = Counter()
boundaries = Counter()


def tokens(raw):
    if isinstance(raw, str): raw = raw.encode('utf-8')
    return [m for m in TOKEN.finditer(raw) if not m[0].startswith(b'#')]


def ast(raw):
    """Parse assignments without discarding order, duplicate keys, or operators."""
    ts = [m[0].decode('utf-8').strip('"').lstrip('\ufeff') for m in tokens(raw)]
    at = 0
    def body():
        nonlocal at
        rows = []
        while at < len(ts) and ts[at] != '}':
            key = ts[at]; at += 1
            assert at < len(ts) and ts[at] in ('=', '==', '!=', '>', '<', '>=', '<='), ('Expected assignment', key)
            op = ts[at]; at += 1
            assert at < len(ts), ('Missing assignment value', key)
            if ts[at] == '{':
                at += 1; value = body()
                assert at < len(ts) and ts[at] == '}', ('Unclosed block', key)
                at += 1
            else: value = ts[at]; at += 1
            rows.append((key, op, value))
        return rows
    result = body()
    assert at == len(ts), 'Extra closing brace'
    return result


def blocks(raw, depth=None):
    stack, found = [], []
    ts = tokens(raw)
    for at, t in enumerate(ts):
        if t[0] == b'{':
            assert at >= 2 and ts[at-1][0] == b'=', 'Anonymous/native token arrays are outside this parser'
            item = {'key': ts[at-2][0].decode().lstrip('\ufeff'), 'start': ts[at-2].start(), 'depth': len(stack)}
            stack.append(item)
        elif t[0] == b'}':
            assert stack, 'Extra closing brace'
            item = stack.pop(); item['end'] = t.end()
            if depth is None or item['depth'] == depth: found.append(item)
    assert not stack, 'Unclosed block'
    return found


def one(nodes, key):
    values = [value for name, op, value in nodes if name == key]
    assert len(values) == 1, ('Expected exactly one key', key, len(values))
    return values[0]


def walk(nodes):
    for row in nodes:
        yield row
        if isinstance(row[2], list): yield from walk(row[2])


def named_block(raw, key, depth=None):
    items = [item for item in blocks(raw, depth) if item['key'] == key]
    assert len(items) == 1, (key, len(items))
    return items[0]


def child_block(raw, parent, field):
    segment = raw[parent['start']:parent['end']]
    item = named_block(segment, field, 1)
    return {**item, 'start': parent['start']+item['start'], 'end': parent['start']+item['end']}


def byte_range(raw, block): return raw[block['start']:block['end']]
def sha(raw): return hashlib.sha256(raw).hexdigest()
def read(path): return (ROOT/path).read_bytes()


@lru_cache(maxsize=None)
def baseline(path):
    return subprocess.check_output(['git', 'show', BASELINE+':'+path], cwd=ROOT)


def check(group, truth, context=None):
    assert truth, (group, context)
    groups[group] += 1


def byte_check(group, truth, context=None):
    assert truth, (group, context)
    boundaries[group] += 1


def frame(actor='A', *, allow=False, toggling=False, enable=False, ai=False, override=False, opened=False, subsections=False):
    flags = set()
    if enable: flags.add(ENABLE)
    if override: flags.add(OVERRIDE)
    if opened: flags.add(OPEN)
    if subsections: flags.update(SUBSECTIONS)
    return {'global': {key for key, present in ((ALLOW, allow), (TOGGLING, toggling)) if present},
            'countries': {'A': {'ai': ai if actor == 'A' else False, 'flags': flags if actor == 'A' else set(), 'unrelated': {'cash': 31}},
                          'B': {'ai': ai if actor == 'B' else False, 'flags': flags if actor == 'B' else set(), 'unrelated': {'cash': 19}},
                          'AI': {'ai': True, 'flags': {OPEN, *SUBSECTIONS, 'ai_unrelated'}, 'unrelated': {'cash': 11}}}}


class Executor:
    """Only the visited native primitives needed for visibility and flag toggles.

    Unknown visited commands, unexpected operators and recursion fail closed.
    No every-country, event, console, account, timer or network implementation.
    """
    def __init__(self, trigger_defs, effect_defs):
        self.triggers = trigger_defs
        self.effects = effect_defs

    def trigger(self, nodes, state, actor, depth=0):
        assert depth < 24, 'Unexpected recursive helper'
        at = 0
        result = True
        while at < len(nodes):
            key, op, value = nodes[at]; at += 1
            assert op == '=', ('Unsupported trigger operator', key, op)
            if key == 'if':
                branches = [(key, op, value)]
                while at < len(nodes) and nodes[at][0] in ('else_if', 'else'):
                    branches.append(nodes[at]); at += 1
                ok = True
                for branch, bop, contents in branches:
                    assert bop == '=' and isinstance(contents, list)
                    if branch == 'else':
                        ok = self.trigger(contents, state, actor, depth+1); break
                    condition = one(contents, 'limit')
                    if self.trigger(condition, state, actor, depth+1):
                        ok = self.trigger([row for row in contents if row[0] != 'limit'], state, actor, depth+1); break
            elif key in ('AND', 'OR', 'NOT'):
                assert isinstance(value, list)
                child_results = [self.trigger([row], state, actor, depth+1) for row in value]
                ok = any(child_results) if key == 'OR' else all(child_results)
                if key == 'NOT': ok = not ok
            elif key == 'has_global_flag': ok = value in state['global']
            elif key == 'has_country_flag': ok = value in state['countries'][actor]['flags']
            elif key == 'is_ai':
                assert value in ('yes', 'no')
                ok = state['countries'][actor]['ai'] == (value == 'yes')
            elif key == 'always':
                assert value in ('yes', 'no'); ok = value == 'yes'
            elif key in self.triggers:
                assert value in ('yes', 'no')
                ok = self.trigger(self.triggers[key], state, actor, depth+1) == (value == 'yes')
            else: raise AssertionError(('Unknown visited trigger', key))
            # Do not short-circuit the model: unsupported later clauses must fail.
            result = result and ok
        return result

    def effect(self, nodes, state, actor, depth=0):
        assert depth < 24, 'Unexpected recursive helper'
        at = 0
        while at < len(nodes):
            key, op, value = nodes[at]; at += 1
            assert op == '=', ('Unsupported effect operator', key, op)
            if key == 'if':
                branches = [(key, op, value)]
                while at < len(nodes) and nodes[at][0] in ('else_if', 'else'):
                    branches.append(nodes[at]); at += 1
                for branch, bop, contents in branches:
                    assert bop == '=' and isinstance(contents, list)
                    if branch == 'else' or self.trigger(one(contents, 'limit'), state, actor, depth+1):
                        self.effect([row for row in contents if row[0] != 'limit'], state, actor, depth+1); break
            elif key in ('hidden_effect', 'effect'):
                assert isinstance(value, list); self.effect(value, state, actor, depth+1)
            elif key == 'set_country_flag':
                assert isinstance(value, str); state['countries'][actor]['flags'].add(value)
            elif key == 'clr_country_flag':
                assert isinstance(value, str); state['countries'][actor]['flags'].discard(value)
            elif key in self.effects:
                assert value == 'yes'; self.effect(self.effects[key], state, actor, depth+1)
            else: raise AssertionError(('Unknown visited effect', key))


def definitions(path):
    nodes = ast(read(path))
    assert len({key for key, op, val in nodes}) == len(nodes), ('Duplicate helper ID', path)
    assert all(op == '=' and isinstance(val, list) for key, op, val in nodes)
    return {key: val for key, op, val in nodes}


def decision_inventory(raw):
    nodes = one(ast(raw), 'cheat_decision_categories')
    assert len(nodes) == 56 and len({key for key, op, value in nodes}) == 56, 'Original 56 decision IDs must be preserved'
    assert all(op == '=' and isinstance(value, list) for key, op, value in nodes)
    return {key: value for key, op, value in nodes}


def bytes_and_inventory(old_decisions, current_decisions):
    original = baseline(DECISIONS); actual = read(DECISIONS)
    byte_check('decision_id_inventory', old_decisions.keys() == current_decisions.keys())
    restored = actual
    changed = []
    for identity in old_decisions:
        if identity == 'game_rule_toggle_cheat_decisions':
            byte_check('global_toggle_raw', byte_range(actual, named_block(actual, identity, 1)) == byte_range(original, named_block(original, identity, 1)))
            continue
        old_parent = named_block(original, identity, 1)
        new_parent = named_block(restored, identity, 1)
        old_visible = child_block(original, old_parent, 'visible')
        new_visible = child_block(restored, new_parent, 'visible')
        assert byte_range(original, old_visible) != byte_range(restored, new_visible), ('Missing visibility change', identity)
        restored = restored[:new_visible['start']]+byte_range(original, old_visible)+restored[new_visible['end']:]
        changed.append(identity)
        byte_check('decision_effect_raw', one(old_decisions[identity], 'complete_effect') == one(current_decisions[identity], 'complete_effect'), identity)
    byte_check('exact_decisions_inverse', len(changed) == 55 and restored == original)

    original, actual = baseline(CATEGORY), read(CATEGORY)
    injected = b'\t\t\thas_country_flag = eon_cheat_override\r\n' if b'\r\n' in original else b'\t\t\thas_country_flag = eon_cheat_override\n'
    byte_check('category_inverse', actual.count(injected) == 1 and actual.replace(injected, b'', 1) == original)

    original, actual = baseline(OLD_TEXT), read(OLD_TEXT)
    old_nodes, new_nodes = ast(original), ast(actual)
    old_named = {one(value, 'name'): value for key, op, value in old_nodes}
    new_named = {one(value, 'name'): value for key, op, value in new_nodes}
    byte_check('old_text_ids', old_named.keys() == new_named.keys() and len(old_named) == 4)
    for identity in old_named:
        if identity != 'show_cheat_decision_status_4': byte_check('unrelated_status_raw_ast', old_named[identity] == new_named[identity], identity)
    status = new_named['show_cheat_decision_status_4']
    branches = [val for key, op, val in status if key == 'text']
    old_branches = [val for key, op, val in old_named['show_cheat_decision_status_4'] if key == 'text']
    byte_check('status_branch_addition', len(branches) == len(old_branches)+1 and branches[1:] == old_branches)
    status_blocks = [item for item in blocks(actual, 0) if one(ast(byte_range(actual, item))[0][2], 'name') == 'show_cheat_decision_status_4']
    assert len(status_blocks) == 1
    parent = status_blocks[0]; segment = byte_range(actual, parent)
    text_blocks = sorted([item for item in blocks(segment, 1) if item['key'] == 'text'], key=lambda item:item['start'])
    branch = text_blocks[0]
    start = parent['start']+branch['start']; end = parent['start']+branch['end']
    # Own one whole inserted text branch, including its indentation and following EOL.
    start = actual.rfind(b'\n', 0, start)+1
    tail = actual[end:]
    end += len(tail)-len(tail.lstrip(b'\r\n'))
    byte_check('status_exact_inverse', actual[:start]+actual[end:] == original)

    for path in OLD_GAME:
        original, actual = baseline(path), read(path)
        byte_check('old_bom_and_eol', original.startswith(b'\xef\xbb\xbf') == actual.startswith(b'\xef\xbb\xbf'), path)
        byte_check('old_bom_and_eol', actual.count(b'\n') == actual.count(b'\r\n') if b'\r\n' in original else b'\r' not in actual, path)
        byte_check('old_bom_and_eol', original.endswith(b'\n') == actual.endswith(b'\n'), path)

    changed = set(subprocess.check_output(['git', 'diff', '--name-only', BASELINE, '--'], cwd=ROOT).decode().splitlines())
    byte_check('old_game_outside_scope', not {path for path in changed if path.startswith(GAME_PREFIXES) or path in GAME_ROOT_FILES} - OLD_GAME - NEW_GAME)
    old_tests = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE, '--', 'tools/validation'], cwd=ROOT).decode().splitlines()
    assert len(old_tests) > 20
    for path in old_tests:
        byte_check('previous_validation_raw', read(path) == baseline(path), path)
    new_files = set(subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=ROOT).decode().splitlines())
    byte_check('untracked_game_scope', not {path for path in new_files if path.startswith(GAME_PREFIXES) or path in GAME_ROOT_FILES} - NEW_GAME)
    byte_check('validation_scope', not {path for path in changed | new_files if path.startswith('tools/validation/')} - PUBLIC_TESTS)


def collect_gui(executor):
    scripted = one(ast(read(SCRIPT_GUI)), 'scripted_gui')
    candidates = [(key, body) for key, op, body in scripted if isinstance(body, list) and any(name == 'effects' for name, op, val in body)]
    assert len(candidates) == 1
    gui_id, gui = candidates[0]
    check('native_callback_wiring', one(gui, 'context_type') == 'player_context')
    check('native_callback_wiring', one(gui, 'parent_window_token') == 'top_bar')
    # Scripted GUI declared player scope is a source binding, not native MP proof.
    props = one(gui, 'effects')
    callback = one(props, 'eon_cheat_toggle_button_click')
    check('native_callback_wiring', callback == [('eon_toggle_cheat_access', '=', 'yes')])
    conditions = one(gui, 'triggers')
    enabled = one(conditions, 'eon_cheat_toggle_button_click_enabled')
    for ai in (False, True):
        s = frame(ai=ai)
        check('gui_human_access', executor.trigger(one(gui, 'visible'), s, 'A') == (not ai), ai)
        check('gui_human_access', executor.trigger(enabled, s, 'A') == (not ai), ai)
    definition = one(ast(read(GUI)), 'guiTypes')
    windows = [(key, value) for key, op, value in definition if key == 'containerWindowType']
    assert len(windows) == 1
    window = windows[0][1]
    check('native_callback_wiring', one(window, 'name') == one(gui, 'window_name'))
    buttons = [value for key, op, value in walk(window) if key == 'buttonType' and one(value, 'name') == 'eon_cheat_toggle_button']
    assert len(buttons) == 1
    button = buttons[0]
    check('native_callback_wiring', one(button, 'shortcut').lower() == 'shift+r')
    check('native_callback_wiring', one(button, 'buttonText') == '[GetEonCheatHotkeyState]')
    check('native_callback_wiring', one(button, 'pdx_tooltip') == 'EON_CHEAT_HOTKEY_TT')
    return callback, window, button


def text_and_category(executor, callback):
    category = one(ast(read(CATEGORY)), 'cheat_decision_categories')
    status = [value for key, op, value in ast(read(OLD_TEXT)) if one(value, 'name') == 'show_cheat_decision_status_4']
    assert len(status) == 1
    named = [value for key, op, value in ast(read(SCRIPT_TEXT)) if one(value, 'name') == 'GetEonCheatHotkeyState']
    assert len(named) == 1
    def display(nodes, state, actor):
        for key, op, value in nodes:
            if key == 'name': continue
            assert key == 'text' and op == '=', ('Unknown localization node', key)
            if executor.trigger(one(value, 'trigger'), state, actor): return one(value, 'localization_key')
        raise AssertionError('No state text branch matches')
    keys = {'EON_CHEAT_HOTKEY_TT'}
    for ai, allow, toggling, enable, override in product((False, True), repeat=5):
        state = frame(ai=ai, allow=allow, toggling=toggling, enable=enable, override=override)
        permitted = not ai
        check('category_human_guard', executor.trigger(one(category, 'allowed'), state, 'A') == permitted)
        check('category_visibility', executor.trigger(one(category, 'visible'), state, 'A') == (allow or toggling or override))
        text = display(named[0], state, 'A'); keys.add(text)
        check('override_label_state', text == ('EON_CHEAT_HOTKEY_ON' if override else 'EON_CHEAT_HOTKEY_OFF'))
        if override and not ai:
            check('override_status_priority', display(status[0], state, 'A') == 'EON_CHEAT_OVERRIDE_ACTIVE_TT')
        if not override:
            expected = 'cheat_decisions_enabled_4_TT' if toggling else 'cheat_decisions_disabled_4_TT'
            check('legacy_status_preserved', display(status[0], state, 'A') == expected)
    for _, _, value in walk(named[0]):
        if isinstance(value, str) and value.startswith('EON_CHEAT_'): keys.add(value)
    for _, _, value in walk(status[0]):
        if isinstance(value, str) and value.startswith('EON_CHEAT_'): keys.add(value)
    locale_maps = []
    for language, path in zip(('english', 'russian'), LOCALES):
        raw = read(path)
        check('new_locale_format', raw.startswith(b'\xef\xbb\xbf') and raw.decode('utf-8-sig').splitlines()[0] == 'l_'+language+':', path)
        found = {}
        for line in raw.decode('utf-8-sig').splitlines()[1:]:
            if not line.strip() or line.lstrip().startswith('#'): continue
            match = re.fullmatch(r'\s+([A-Za-z0-9_.]+):\d*\s+"((?:\\.|[^"\\])*)"\s*', line)
            assert match, ('Invalid localization row', path, line)
            assert match[1] not in found, ('Duplicate locale key', path, match[1])
            found[match[1]] = match[2]
            check('nonempty_locale', bool(match[2]), (path, match[1]))
        locale_maps.append(found)
        check('referenced_locale_keys', keys <= found.keys(), (path, keys-found.keys()))
    check('locale_key_alignment', locale_maps[0].keys() == locale_maps[1].keys())


def behavior(executor, old_decisions, current_decisions, callback):
    # Independence: evaluate baseline AST and actual AST under the same fixture.
    # Each 55 decision gate gets all 8 inherited rule/enable combinations and
    # section masks, including override off; no newgate reimplementation oracle.
    identities = [key for key in old_decisions if key != 'game_rule_toggle_cheat_decisions']
    for identity, (allow, toggling, enable), opened, section_mask in product(identities, product((False, True), repeat=3), (False, True), range(32)):
        state = frame(allow=allow, toggling=toggling, enable=enable, opened=opened)
        state['countries']['A']['flags'].update(flag for at, flag in enumerate(SUBSECTIONS) if section_mask & (1 << at))
        before = executor.trigger(one(old_decisions[identity], 'visible'), state, 'A')
        after = executor.trigger(one(current_decisions[identity], 'visible'), state, 'A')
        check('legacy_visibility_truth_table', before == after, (identity, allow, toggling, enable, opened, section_mask))

    for identity in identities:
        state = frame(override=True, opened=True, subsections=True)
        check('override_all_rules_off', executor.trigger(one(current_decisions[identity], 'visible'), state, 'A'), identity)
        state['global'].update((ALLOW, TOGGLING)); state['countries']['A']['flags'].add(ENABLE)
        state['global'].clear(); state['countries']['A']['flags'].discard(ENABLE)
        check('override_after_global_disable', executor.trigger(one(current_decisions[identity], 'visible'), state, 'A'), identity)

    for actor in ('A', 'B'):
        for allow, toggling, enable in product((False, True), repeat=3):
            state = frame(actor=actor, allow=allow, toggling=toggling, enable=enable)
            state['countries'][actor]['flags'].add('actor_unrelated')
            original = deepcopy(state)
            executor.effect(callback, state, actor)
            check('own_scope_enable', state['countries'][actor]['flags'] == original['countries'][actor]['flags'] | {OVERRIDE, OPEN})
            check('own_scope_enable', state['global'] == original['global'])
            for other in set(state['countries'])-{actor}:
                check('two_humans_no_leak', state['countries'][other] == original['countries'][other], (actor, other))
            state['countries'][actor]['flags'].update(SUBSECTIONS)
            executor.effect(callback, state, actor)
            check('close_all_five_subsections', state == original, (actor, allow, toggling, enable))
            # A fresh reopen is not a no-op and never leaks into the other human.
            executor.effect(callback, state, actor)
            check('repeated_toggle', state['countries'][actor]['flags'] == original['countries'][actor]['flags'] | {OVERRIDE, OPEN})
            executor.effect(callback, state, actor)
            check('repeated_toggle', state == original)

    for override in (False, True):
        state = frame(actor='AI')
        if override: state['countries']['AI']['flags'].add(OVERRIDE)
        original = deepcopy(state)
        executor.effect(callback, state, 'AI')
        check('ai_callback_inert', state == original)
        # AI country flag cannot activate the bypass when inherited rules are off.
        check('ai_override_not_access', not executor.trigger([('eon_cheat_access', '=', 'yes')], state, 'AI'))

    # Closing main decisions elsewhere must not disable the personal override;
    # current helper is still able to deactivate and clean orphaned section flags.
    for mask in range(32):
        state = frame(override=True)
        state['countries']['A']['flags'].update(flag for at, flag in enumerate(SUBSECTIONS) if mask & (1 << at))
        original = deepcopy(state)
        executor.effect(callback, state, 'A')
        expected = deepcopy(original)
        expected['countries']['A']['flags'] -= {OVERRIDE, OPEN, *SUBSECTIONS}
        check('closed_main_cleanup', state == expected, mask)

    # Two players toggling independently: no global permission state is written.
    state = frame(); start = deepcopy(state)
    executor.effect(callback, state, 'A'); executor.effect(callback, state, 'B')
    check('independent_human_overrides', all({OVERRIDE, OPEN} <= state['countries'][tag]['flags'] for tag in ('A', 'B')))
    executor.effect(callback, state, 'A')
    check('independent_human_overrides', not {OVERRIDE, OPEN} & state['countries']['A']['flags'] and {OVERRIDE, OPEN} <= state['countries']['B']['flags'])
    executor.effect(callback, state, 'B')
    check('independent_human_overrides', state == start)

    # Validate the fixture's actual fail-closed boundary rather than claim the
    # engine rejects unknown primitives in the same fashion.
    for kind, command in (('trigger', [('unmodelled_trigger', '=', 'yes')]), ('effect', [('unmodelled_effect', '=', 'yes')])):
        try:
            getattr(executor, kind)(command, frame(), 'A')
        except AssertionError as exc:
            check('model_fail_closed', 'Unknown visited' in str(exc))
        else: raise AssertionError('Unsupported primitive was silently accepted')


def main():
    args = argparse.ArgumentParser()
    args.add_argument('--receipt', type=Path)
    config = args.parse_args()
    before = {path: sha(read(path)) for path in GAME}
    original = decision_inventory(baseline(DECISIONS))
    current = decision_inventory(read(DECISIONS))
    executor = Executor(definitions(TRIGGERS), definitions(EFFECTS))
    assert set(executor.triggers) == {'eon_cheat_access'}
    assert set(executor.effects) == {'eon_toggle_cheat_access'}
    callback, window, button = collect_gui(executor)
    behavior(executor, original, current, callback)
    text_and_category(executor, callback)
    bytes_and_inventory(original, current)
    check('source_stable_during_run', before == {path: sha(read(path)) for path in GAME})
    report = {'baseline': BASELINE, 'result': 'pass', 'source_assertions': sum(groups.values()),
              'visibility_truth_table_rows': groups['legacy_visibility_truth_table'],
              'assertion_groups': dict(sorted(groups.items())), 'byte_checks': sum(boundaries.values()),
              'byte_groups': dict(sorted(boundaries.items())), 'source_sha256': before,
              'public_validation_sha256': {path: sha(read(path)) for path in sorted(PUBLIC_TESTS)},
              'native_runtime': False,
              'proof_limits': ['Actual source callback and flag/visibility model only.',
                               'No native keyboard routing, Shift+R collision, layout or multiplayer synchronization proof.',
                               'No built-in console or engine multiplayer/ironman unlock; inherited cheat action effects are preserved, not executed.',
                               'Previous 01-23 validation files remain byte-identical; no historical source projection or cumulative 7655 rerun.']}
    if config.receipt:
        config.receipt.parent.mkdir(parents=True, exist_ok=True)
        config.receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
