"""Execute the diplomatic-menu bridge against the unchanged package26 AST.

The declared action frame is THIS=recipient, ROOT=actor. FROM deliberately names
a third country; the stock action documentation does not define that scope.
This is source/model evidence, never native UI, event-delivery or AI acceptance.
"""
from collections import Counter
from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
LEGACY = ROOT / 'tools/validation/diplomacy_package_26/test_relations.py'
spec = importlib.util.spec_from_file_location('relations_menu_package26', LEGACY)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
P, UI = m.P, m.P + 'ui_'
FILES = [
    *m.FILES,
    'common/scripted_diplomatic_actions/eon_diplomatic_relations_ui_actions.txt',
    'common/scripted_localisation/eon_diplomatic_relations_ui_localisation.txt',
    *[f'localisation/{lang}/eon_diplomatic_relations_ui_l_{lang}.yml'
      for lang in ('english', 'russian')],
    LEGACY.relative_to(ROOT).as_posix(),
]
ACTIONS = dict((name, body) for name, op, body in m.one(
    m.parse((ROOT / FILES[10]).read_text(encoding='utf-8-sig')),
    'scripted_diplomatic_actions'))
NAMES = tuple(name.removeprefix(P) for name in m.DECISIONS)
ORIGINAL_CONDITION, ORIGINAL_STATE, ORIGINAL_DECISION = m.condition, m.state, m.decision
EVIDENCE = {}


def walk(nodes):
    for node in nodes:
        yield node
        if isinstance(node[2], list):
            yield from walk(node[2])


def hashes():
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in FILES}


def model_state():
    result = ORIGINAL_STATE()
    # Named model inputs only. No game/source state is changed.
    for country in result['countries'].values():
        country['is_ai'] = False
    return result


def ui_dollar_aliases(value):
    # This owned UI uses plain text or $KEY$ aliases. This deliberately narrow
    # grammar is not a universal description of the engine's localisation API.
    aliases, cursor = [], 0
    while (start := value.find('$', cursor)) != -1:
        token = re.match(r'\$([A-Za-z_][A-Za-z0-9_.]*)\$', value[start:])
        if token is None:
            raise ValueError(f'Malformed UI dollar substitution at {start}: {value!r}')
        aliases.append(token.group(1))
        cursor = start + token.end()
    return tuple(aliases)


def unwrap_readiness(nodes, expected_key=None):
    # Only the documented presentation seam is transparent. Do not drop an
    # arbitrary hidden subtree, unknown metadata or a changed scope.
    assert len(nodes) == 1 and nodes[0][:2] == ('custom_trigger_tooltip', '=')
    wrapper = nodes[0][2]
    assert [n[:2] for n in wrapper] == [('tooltip', '='), ('hidden_trigger', '=')]
    key, hidden = wrapper[0][2], wrapper[1][2]
    assert key in {UI + name + '_ready_tt' for name in NAMES}
    if expected_key is not None:
        assert key == expected_key
    assert len(hidden) == 2 and hidden[0] == ('tooltip_evaluation', '=', 'eval')
    assert hidden[1][:2] == ('ROOT', '=') and isinstance(hidden[1][2], list)
    return [hidden[1]]


def condition(nodes, result, context):
    # Extend only the new primitive; retain the original evaluator's whole
    # if/else chains, scope switches and unknown-command refusal.
    adapted = []
    for name, op, value in nodes:
        if (name == 'custom_trigger_tooltip' and isinstance(value, list)
                and any(key == 'tooltip' and data in {UI + name + '_ready_tt' for name in NAMES}
                        for key, op, data in value)):
            adapted.extend(unwrap_readiness([(name, op, value)]))
        elif name == 'is_ai':
            assert op == '=' and value in ('yes', 'no'), ('Invalid is_ai', name, op, value)
            ready = result['countries'][context['scope']]['is_ai'] == (value == 'yes')
            adapted.append(('always', '=', 'yes' if ready else 'no'))
        else:
            adapted.append((name, op, value))
    return ORIGINAL_CONDITION(adapted, result, context)


@contextmanager
def adapter():
    previous = m.condition, m.state, m.decision, m.checks
    m.condition, m.state = condition, model_state
    try:
        yield
    finally:
        m.condition, m.state, m.decision, m.checks = previous


def native_context(actor, peer, third=None):
    if third is None:
        third = next(tag for tag in ('D', 'F', 'G') if tag not in (actor, peer))
    assert third not in (actor, peer), ('FROM witness must be independent', actor, peer, third)
    return {'scope': peer, 'prev': [], 'root': actor, 'from': third}


def action(result, name, actor='A', peer='B', force=False, third=None, body=None):
    body = ACTIONS[UI + name] if body is None else body
    context = native_context(actor, peer, third)
    result['execution_temps'] = {}
    ready = all(m.condition(m.one(body, field), result, context)
                for field in ('allowed', 'visible', 'selectable', 'can_be_sent'))
    if ready or force:
        # Completion must reconstruct its selected terms independently of
        # readiness/hover temporary state.
        result['execution_temps'] = {}
        m.execute(m.one(body, 'complete_effect'), result, context)
    return ready


def inner(body, section):
    return m.one(m.one(m.one(body, section), 'FROM'), 'PREV')


def label_definitions(relative):
    return {m.one(body, 'name'): body for name, op, body in
            m.parse((ROOT / relative).read_text(encoding='utf-8-sig'))}


def selected_label(body, result, context):
    for name, op, text in body:
        if name != 'text':
            continue
        triggers = [value for key, operator, value in text if key == 'trigger']
        if not triggers or m.condition(triggers[0], result, context):
            return m.one(text, 'localization_key')
    raise AssertionError('No label fallback')


def fixture(name):
    r, actor, peer = m.state(), 'A', 'B'
    if name == 'status':
        assert ORIGINAL_DECISION(r, 'propose')
    elif name.startswith('accept_'):
        preparation = {'accept_relations': 'propose', 'accept_charge': 'mission_charge',
                       'accept_ambassador': 'mission_ambassador', 'accept_head': 'propose_head'}[name]
        if name == 'accept_head':
            m.mission(r)
        assert ORIGINAL_DECISION(r, preparation)
        actor, peer = 'B', 'A'
    elif name in ('decline', 'withdraw'):
        assert ORIGINAL_DECISION(r, 'propose')
        if name == 'decline':
            actor, peer = 'B', 'A'
    elif name in ('propose_head', 'credentials', 'persona_non_grata_approved'):
        m.mission(r)
        if name != 'propose_head':
            assert ORIGINAL_DECISION(r, 'propose_head')
            assert ORIGINAL_DECISION(r, 'accept_head', 'B', 'A')
        if name == 'persona_non_grata_approved':
            actor, peer = 'B', 'A'
    elif name in ('recall', 'persona_non_grata', 'close', 'close_host', 'break',
                  'exit_facilities', 'report_departure'):
        m.establish(r)
        m.mission(r)
        m.head(r)
        if name in ('persona_non_grata', 'close_host'):
            actor, peer = 'B', 'A'
        if name in ('exit_facilities', 'report_departure'):
            assert ORIGINAL_DECISION(r, 'recall')
            if name == 'exit_facilities':
                actor, peer = 'B', 'A'
            else:
                assert ORIGINAL_DECISION(r, 'exit_facilities', 'B', 'A')
    return r, actor, peer


class MenuTests(unittest.TestCase):
    def test_exact_twenty_bridge_bodies_and_repeat_guards(self):
        self.assertEqual(len(NAMES), 20)
        self.assertEqual(set(ACTIONS), {UI + name for name in NAMES})
        for name in NAMES:
            with self.subTest(action=name):
                old, new = m.DECISIONS[P + name], ACTIONS[UI + name]
                self.assertEqual(m.one(new, 'allowed'), [('ROOT', '=', [('is_ai', '=', 'no')])])
                self.assertEqual(m.one(new, 'cost'), '0')
                self.assertEqual(m.one(new, 'requires_acceptance'), 'no')
                self.assertEqual(m.one(new, 'show_acceptance_on_action_button'), 'no')
                self.assertEqual(m.one(new, 'ai_desire'), [('factor', '=', '0')])
                self.assertFalse(any(key == 'on_sent_effect' for key, op, value in new))
                self.assertEqual(m.one(new, 'visible'), [
                    ('exists', '=', 'yes'), ('NOT', '=', [('tag', '=', 'ROOT')]),
                    ('ROOT', '=', [('exists', '=', 'yes'), *inner(old, 'visible')])])
                for field in ('selectable', 'can_be_sent'):
                    self.assertEqual(unwrap_readiness(m.one(new, field), UI + name + '_ready_tt'),
                                     [('ROOT', '=', inner(old, 'available'))])
                self.assertEqual(m.one(new, 'complete_effect'), [('ROOT', '=', inner(old, 'complete_effect'))])
                self.assertFalse(any(key == 'FROM' or (isinstance(value, str) and '@FROM' in value)
                                     for key, op, value in walk(new)))

    def test_full_original_lifecycle_through_native_actions(self):
        m.checks = Counter()
        with redirect_stdout(io.StringIO()) as baseline_output:
            m.main()
        baseline = json.loads(baseline_output.getvalue())
        m.checks = Counter()
        trace = []

        def dispatch(result, name, actor='A', peer='B', force=False):
            reference = deepcopy(result)
            old_ready = ORIGINAL_DECISION(reference, name, actor, peer, force)
            new_ready = action(result, name, actor, peer, force)
            self.assertEqual(new_ready, old_ready, (name, actor, peer, force))
            # Exact durable world equality includes all countries, finances,
            # flags, expiry windows, records and unrelated legacy channels.
            self.assertEqual(m.stable(result), m.stable(reference), (name, actor, peer, force))
            old_events = [(e['id'], e['scope'], e['root']) for e in reference['events']]
            new_events = [(e['id'], e['scope'], e['root']) for e in result['events']]
            self.assertEqual(new_events, old_events)
            trace.append((name, actor, peer, force))
            return new_ready

        m.decision = dispatch
        try:
            with redirect_stdout(io.StringIO()) as menu_output:
                m.main()
        finally:
            m.decision = ORIGINAL_DECISION
        menu = json.loads(menu_output.getvalue())
        self.assertEqual(menu['groups'], baseline['groups'])
        self.assertEqual(menu['current_source_assertions'], baseline['current_source_assertions'])
        self.assertEqual(set(row[0] for row in trace), set(NAMES) - {'status'})
        EVIDENCE.update(original_lifecycle_assertions=baseline['current_source_assertions'],
                        menu_lifecycle_assertions=menu['current_source_assertions'],
                        exact_cross_route_dispatches=len(trace))

    def test_every_action_has_a_reachable_positive_case(self):
        for name in NAMES:
            with self.subTest(action=name):
                r, actor, peer = fixture(name)
                reference = deepcopy(r)
                self.assertTrue(ORIGINAL_DECISION(reference, name, actor, peer))
                self.assertTrue(action(r, name, actor, peer))
                self.assertEqual(m.stable(r), m.stable(reference))

    def test_human_menu_ai_legacy_category_and_no_hover_mutations(self):
        category = m.one(m.parse((ROOT / m.FILES[3]).read_text(encoding='utf-8-sig')), P + 'category')
        for is_ai in (False, True):
            r = m.state()
            r['countries']['A']['is_ai'] = is_ai
            self.assertEqual(m.condition(m.one(category, 'visible'), r, m.ctx()), is_ai)
            self.assertEqual(ORIGINAL_DECISION(deepcopy(r), 'propose'), not is_ai)
            self.assertEqual(action(r, 'propose'), not is_ai)
        # Nine pure factor-zero legacy UI entries deliberately exclude AI
        # actors. Human diplomatic actions retain their original ready cases.
        player_only = ('status', 'propose', 'propose_head', 'withdraw', 'recall',
                       'persona_non_grata', 'close', 'close_host', 'break')
        for name in NAMES:
            body = m.DECISIONS[P + name]
            root_filter = [('exists', '=', 'yes')]
            if name in player_only:
                root_filter.append(('is_ai', '=', 'no'))
                self.assertEqual(m.one(body, 'ai_will_do'), [('factor', '=', '0')])
            self.assertEqual(m.one(body, 'target_root_trigger'), root_filter, name)
            if name not in player_only:
                r, actor, peer = fixture(name)
                r['countries'][actor]['is_ai'] = True
                self.assertTrue(ORIGINAL_DECISION(deepcopy(r), name, actor, peer), name)
                self.assertFalse(action(deepcopy(r), name, actor, peer), name)
        for name in player_only:
            for exists, is_ai in ((True, False), (True, True), (False, False), (False, True)):
                with self.subTest(action=name, exists=exists, is_ai=is_ai):
                    r, actor, peer = fixture(name)
                    r['countries'][actor]['exists'] = exists
                    r['countries'][actor]['is_ai'] = is_ai
                    expected = exists and not is_ai
                    self.assertEqual(m.condition(m.one(m.DECISIONS[P + name], 'target_root_trigger'),
                                                 r, m.ctx(actor, peer)), expected)
                    self.assertEqual(ORIGINAL_DECISION(deepcopy(r), name, actor, peer), expected)
                    self.assertEqual(action(deepcopy(r), name, actor, peer), expected)
        EVIDENCE.update(player_only_legacy_root_filters=len(player_only),
                        player_only_root_filter_model_cases=len(player_only) * 4)
        for name in NAMES:
            r, actor, peer = fixture(name)
            before = m.stable(r)
            for field in ('allowed', 'visible', 'selectable', 'can_be_sent'):
                m.condition(m.one(ACTIONS[UI + name], field), r, native_context(actor, peer))
            self.assertEqual(m.stable(r), before, name)

    def test_country_roles_and_from_are_independent(self):
        for actor, peer, third in (('GER', 'GRE', 'USA'), ('GRE', 'USA', 'GER'), ('USA', 'GER', 'GRE')):
            r = m.state()
            third_before = deepcopy(r['countries'][third])
            self.assertTrue(action(r, 'mission_charge', actor, peer, third=third))
            self.assertTrue(action(r, 'accept_charge', peer, actor, third=third))
            self.assertEqual(m.var(r, 'mission_level', actor, peer), 1)
            self.assertEqual(m.var(r, 'mission_level', peer, actor), 0)
            self.assertEqual(r['countries'][actor]['pp'], 90)
            self.assertEqual(r['countries'][peer]['pp'], 100)
            self.assertEqual(r['countries'][third], third_before)

    def test_no_fee_before_consent_exact_fee_once_and_monthly_upkeep(self):
        for level, upfront, upkeep in (('charge', .01, .001), ('ambassador', .02, .002)):
            r = m.state()
            self.assertTrue(action(r, 'mission_' + level))
            self.assertEqual((r['countries']['A']['pp'], r['countries']['A']['variables']['treasury']), (100, 5))
            self.assertTrue(action(r, 'accept_' + level, 'B', 'A'))
            self.assertEqual((r['countries']['A']['pp'], r['countries']['A']['variables']['treasury']), (90, 5 - upfront))
            self.assertEqual((r['countries']['B']['pp'], r['countries']['B']['variables']['treasury']), (100, 5))
            previous = m.stable(r)
            self.assertFalse(action(r, 'accept_' + level, 'B', 'A', force=True))
            self.assertEqual(m.stable(r), previous)
            m.hook(r, 'on_monthly')
            self.assertEqual(r['countries']['A']['variables']['treasury'], round(5 - upfront - upkeep, 6))

    def test_native_pp_and_treasury_boundaries_at_send_and_current_acceptance(self):
        for level, cost in (('charge', .01), ('ambassador', .02)):
            for pp, cash, wanted in ((9.5, cost, False), (10, cost - .000001, False), (10, cost, True)):
                r = m.state()
                r['countries']['A']['pp'] = pp
                r['countries']['A']['variables']['treasury'] = cash
                self.assertEqual(action(r, 'mission_' + level), wanted)
            r = m.state()
            self.assertTrue(action(r, 'mission_' + level))
            r['countries']['A']['pp'] = 9.5
            before = m.stable(r)
            self.assertFalse(action(r, 'accept_' + level, 'B', 'A', force=True))
            self.assertEqual(m.stable(r), before)

    def test_latest_kind_level_head_and_clock_guard_for_forced_callback(self):
        for fault in ('kind', 'level', 'head', 'expiry', 'sender_gone', 'recipient_gone', 'war', 'budget'):
            r = m.state()
            self.assertTrue(action(r, 'mission_ambassador'))
            if fault in ('kind', 'level', 'head'):
                r['countries']['B']['variables'][P + 'in_' + fault + '@A'] = 999
            elif fault == 'expiry':
                r['day'] = 30
            elif fault == 'sender_gone':
                r['countries']['A']['exists'] = False
            elif fault == 'recipient_gone':
                r['countries']['B']['exists'] = False
            elif fault == 'war':
                r['countries']['A']['wars'].add('B')
                r['countries']['B']['wars'].add('A')
            else:
                r['countries']['A']['variables']['treasury'] = .01
            before = m.stable(r)
            self.assertFalse(action(r, 'accept_ambassador', 'B', 'A', force=True), fault)
            self.assertEqual(m.stable(r), before, fault)
        r = m.state()
        self.assertTrue(action(r, 'mission_charge'))
        before = m.stable(r)
        self.assertFalse(action(r, 'accept_ambassador', 'B', 'A', force=True))
        self.assertEqual(m.stable(r), before)
        self.assertTrue(action(r, 'accept_charge', 'B', 'A'))

    def test_self_and_gone_partner_forced_callbacks_do_not_mutate(self):
        for name in NAMES:
            for self_target in (False, True):
                r, actor, peer = fixture(name)
                if self_target:
                    peer = actor
                else:
                    r['countries'][peer]['exists'] = False
                before = m.stable(r)
                self.assertFalse(action(r, name, actor, peer, force=True), (name, self_target))
                self.assertEqual(m.stable(r), before, (name, self_target))

    def test_six_localisation_labels_match_owner_partner_records(self):
        legacy = label_definitions(m.FILES[8])
        menu = label_definitions(FILES[11])
        expected = {UI + suffix for suffix in ('relation_label', 'mission_label', 'incoming_label',
                                             'outgoing_label', 'departure_label', 'protection_label')}
        self.assertEqual(set(menu), expected)
        cases = [m.state()]
        for name in NAMES:
            r, actor, peer = fixture(name)
            self.assertTrue(action(r, name, actor, peer))
            cases.append(r)
        # Unknown and directed legacy restrictions must not read a third pair.
        r = m.state()
        r['global_flags'].discard(P + 'legacy_registry_initialized')
        r['countries']['A']['opinion_modifiers'].add(('C', 'no_diplomatic_ties'))
        cases.append(r)
        r = m.state()
        m.legacy_no_ties(r, 'B', 'A')
        cases.append(r)
        for r in cases:
            for actor, peer in (('A', 'B'), ('B', 'A'), ('A', 'C')):
                for name, body in menu.items():
                    old_name = P + name.removeprefix(UI)
                    expected_key = selected_label(legacy[old_name], r, m.ctx(actor, peer))
                    self.assertEqual(selected_label(body, r, native_context(actor, peer)), expected_key,
                                     (name, actor, peer))

    def test_locale_engine_keys_aliases_labels_and_numeric_direction(self):
        indices = {}
        for lang in ('english', 'russian'):
            paths = [f'localisation/{lang}/eon_diplomatic_relations_l_{lang}.yml',
                     f'localisation/{lang}/eon_diplomatic_relations_ui_l_{lang}.yml']
            entries = {}
            for relative in paths:
                raw = (ROOT / relative).read_bytes()
                self.assertTrue(raw.startswith(b'\xef\xbb\xbf'), relative)
                self.assertNotIn(b'\n', raw.replace(b'\r\n', b''), relative)
                text = raw.decode('utf-8-sig')
                self.assertEqual(text.splitlines()[0], 'l_' + lang + ':')
                rows = re.findall(r'^\s*([\w.]+):\d+\s+"([^\r\n]*)"\s*$', text, re.M)
                self.assertEqual(len(rows), len(text.splitlines()) - 1, relative)
                for key, value in rows:
                    self.assertNotIn(key, entries)
                    self.assertTrue(value.strip() and value != key, key)
                    if relative == f'localisation/{lang}/eon_diplomatic_relations_ui_l_{lang}.yml':
                        ui_dollar_aliases(value)
                    entries[key] = value
            indices[lang] = entries
            for name, body in ACTIONS.items():
                title, desc = name.upper() + '_TITLE', name.upper() + '_ACTION_DESC'
                self.assertIn(title, entries)
                self.assertIn(desc, entries)
                self.assertIn(name + '_ready_tt', entries)
                if name == UI + 'status':
                    reference = entries[P + 'status_desc'].replace('[FROM.GetName]', '[THIS.GetName]').replace('[?FROM.', '[?THIS.')
                    reference = re.sub(r'\[\?(eon_diplomatic_relations_[^\]]+)\]', r'[?ROOT.\1]', reference).replace('@FROM', '@THIS')
                    reference = re.sub(r'\[eon_diplomatic_relations_(relation|mission|incoming|outgoing|departure|protection)_label\]', r'[eon_diplomatic_relations_ui_\1_label]', reference)
                    self.assertEqual(entries[m.one(body, 'send_description')], reference)
                    self.assertNotIn('[', entries[desc])
                else:
                    self.assertEqual(entries[m.one(body, 'send_description')], '$' + desc + '$')
            for alias in re.findall(r'\$([\w.]+)\$', '\n'.join(entries.values())):
                self.assertIn(alias, entries)
            for name in re.findall(r'\[(eon_diplomatic_relations_ui_\w+_label)\]', '\n'.join(entries.values())):
                self.assertIn(name, label_definitions(FILES[11]))
            self.assertIn('[?ROOT.' + P + 'active_head@THIS|0]', entries[UI + 'status_send_desc'])
            self.assertIn('[?THIS.' + P + 'current_departure@ROOT|0]', entries[UI.upper() + 'EXIT_FACILITIES_ACTION_DESC'])
            self.assertIn('[?ROOT.' + P + 'current_departure@THIS|0]', entries[UI.upper() + 'REPORT_DEPARTURE_ACTION_DESC'])
        self.assertEqual(set(indices['english']), set(indices['russian']))
        for relative in FILES[:12]:
            raw = (ROOT / relative).read_bytes()
            self.assertNotIn(b'\n', raw.replace(b'\r\n', b''), relative)

    def test_ui_dollar_substitution_syntax_and_mutants(self):
        valid = {
            '10 political power and 0.02 billion USD': (),
            '10 политических очков и 0.02 млрд долларов': (),
            '$ACTION_DESC$': ('ACTION_DESC',),
            'before $UI.KEY_2$ after': ('UI.KEY_2',),
            '$FIRST$$SECOND$': ('FIRST', 'SECOND'),
        }
        for value, expected in valid.items():
            with self.subTest(valid=value):
                self.assertEqual(ui_dollar_aliases(value), expected)
        for value in ('$', '$0.02 billion', '$0.02 млрд', '$KEY', 'KEY$',
                      '$$', '$0.02$', '$KEY WITH SPACE$', '$KEY$ trailing $',
                      '$FIRST$$SECOND', '$KEY|0$'):
            with self.subTest(malformed=value):
                with self.assertRaisesRegex(ValueError, 'Malformed UI dollar substitution'):
                    ui_dollar_aliases(value)

    def test_scope_and_guard_mutants_are_observable(self):
        r = m.state()
        correct = deepcopy(r)
        self.assertTrue(action(correct, 'mission_charge'))
        mutant = deepcopy(ACTIONS[UI + 'mission_charge'])
        mutant = [(key, op, [('FROM', '=', m.one(value, 'ROOT'))]) if key == 'complete_effect'
                  else (key, op, value) for key, op, value in mutant]
        self.assertTrue(action(r, 'mission_charge', body=mutant))
        self.assertNotEqual(m.stable(r), m.stable(correct))
        self.assertFalse(m.flag(r, 'out_pending', 'A', 'B'))
        r = m.state()
        self.assertTrue(action(r, 'mission_charge'))
        mutant = deepcopy(ACTIONS[UI + 'accept_ambassador'])
        # Removing the action's exact selected-type guard permits the generic
        # helper to accept a different current charge proposal. The negative
        # control proves the type guard is needed in addition to helper safety.
        root_body = [('if', '=', [('limit', '=', [(P + 'response_ready', '=', 'yes')]),
                                  (P + 'accept_response', '=', 'yes')])]
        mutant = [(key, op, [('ROOT', '=', root_body)]) if key == 'complete_effect'
                  else (key, op, value) for key, op, value in mutant]
        before = m.stable(r)
        self.assertFalse(action(r, 'accept_ambassador', 'B', 'A', force=True, body=mutant))
        self.assertNotEqual(m.stable(r), before)
        self.assertEqual(m.var(r, 'mission_level'), 1)


    def test_tooltip_metadata_and_extra_hidden_nodes_are_refused(self):
        source = m.one(ACTIONS[UI + 'mission_charge'], 'selectable')
        for mode in ('no_eval', 'legacy'):
            mutant = deepcopy(source)
            mutant[0][2][1][2][0] = ('tooltip_evaluation', '=', mode)
            with self.assertRaises(AssertionError):
                unwrap_readiness(mutant)
        mutant = deepcopy(source)
        mutant[0][2][1][2].append(('always', '=', 'yes'))
        with self.assertRaises(AssertionError):
            unwrap_readiness(mutant)

    def test_tooltip_wrong_scope_mutant_is_refused(self):
        source = deepcopy(m.one(ACTIONS[UI + 'mission_charge'], 'selectable'))
        hidden = source[0][2][1][2]
        hidden[1] = ('FROM', '=', hidden[1][2])
        with self.assertRaises(AssertionError):
            unwrap_readiness(source)

    def test_tooltip_guard_removal_mutant_is_observable(self):
        r = m.state()
        self.assertTrue(action(r, 'mission_charge'))
        source = m.one(ACTIONS[UI + 'accept_ambassador'], 'selectable')
        context = native_context('B', 'A')
        self.assertFalse(m.condition(source, deepcopy(r), context))
        mutant = deepcopy(source)
        hidden = mutant[0][2][1][2]
        hidden[1] = ('ROOT', '=', [(P + 'response_ready', '=', 'yes')])
        unwrapped = unwrap_readiness(mutant)
        self.assertNotEqual(unwrapped, [('ROOT', '=', inner(m.DECISIONS[P + 'accept_ambassador'], 'available'))])
        self.assertTrue(m.condition(mutant, deepcopy(r), context))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    before = hashes()
    with adapter():
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=1).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(MenuTests))
    after = hashes()
    if before != after:
        raise AssertionError('Source changed during menu validation')
    report = {
        'checks_passed': result.wasSuccessful(), 'tests': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
        'actions': len(ACTIONS), **EVIDENCE,
        'source_sha256': after,
        'native_context': 'THIS=target, ROOT=actor; FROM deliberately independent',
        'native_ui_verified': False, 'native_campaign_verified': False,
        'native_ai_timing_verified': False, 'native_multiplayer_verified': False,
        'proof_scope': 'current menu AST, exact legacy durable state, guarded callback and localisation direction',
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not result.wasSuccessful():
        sys.stderr.write(stream.getvalue())
        raise SystemExit(1)


if __name__ == '__main__':
    main()
