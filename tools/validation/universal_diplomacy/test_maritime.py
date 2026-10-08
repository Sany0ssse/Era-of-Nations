"""Execute actual maritime AST with explicit country inputs; not a native campaign.

The strict adapter checks actor/PREV frames, payment, cooldown and fail-closed
mutations. Native ships, sea combat, randomness, UI and multiplayer need separate
engine validation. Unknown visited syntax fails rather than guessing its behavior.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
P = 'eon_maritime_sanctions_'
FILES = [
    'common/scripted_triggers/' + P + 'triggers.txt',
    'common/scripted_effects/' + P + 'effects.txt',
    'common/decisions/00_sanctions_decisions.txt',
    'common/on_actions/00_sanctions_on_actions.txt',
    'common/on_actions/00_ai_gui_on_actions.txt',
    'events/00_Sanctions_events.txt',
    'events/' + P + 'events.txt',
    *[f'localisation/{lang}/MD_decisions_l_{lang}.yml' for lang in ('english', 'russian')],
    *[f'localisation/{lang}/{P}l_{lang}.yml' for lang in ('english', 'russian')],
    'common/scripted_effects/00_sanctions_scripted_effects.txt',
]
spec = importlib.util.spec_from_file_location('maritime_grammar',
    ROOT / 'tools/validation/diplomacy_completion/check_native_grammar.py')
grammar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grammar)
parse, one = grammar.parser.ast, grammar.parser.one


def load(path): return parse((ROOT / path).read_bytes())
TRIGGERS = {k: v for k, op, v in load(FILES[0])}
EFFECTS = {k: v for k, op, v in load(FILES[1])}
DECISIONS = {k: v for k, op, v in one(load(FILES[2]), 'sanctions_decision_category')}
EVENTS = {one(v, 'id'): v for path in FILES[5:7]
          for k, op, v in load(path) if k == 'country_event'}
COUNTRIES = ('USA', 'GER', 'BRA', 'UKR', 'SWI', 'NEP', 'MEX', 'CAN')


def state():
    return {'day': 0, 'temps': {}, 'events': [], 'random_success': True,
            'countries': {tag: {'exists': True, 'subject': False,
                'coastal': tag not in ('SWI', 'NEP'), 'coast_controller': tag,
                'num_ships': 4, 'ai': False,
                'cp': 100., 'convoy': 8, 'other_convoys': 0, 'treasury': 7., 'manpower': 1000,
                'flags': {}, 'wars': set(), 'faction': None, 'naps': set(),
                'arrays': {'sanctions_targets': []}, 'intel': {}} for tag in COUNTRIES}}


def context(actor='GER', peer='MEX'):
    return {'scope': actor, 'prev': [peer], 'root': actor, 'from': peer}


def reference(ctx, token):
    if token == 'THIS': return ctx['scope']
    if token == 'PREV': return ctx['prev'][0] if ctx['prev'] else None
    if token == 'ROOT': return ctx['root']
    if token == 'FROM': return ctx['from']
    if token in COUNTRIES: return token
    raise AssertionError(('Unknown country scope', token))


def switch(ctx, tag):
    return ctx | {'scope': tag, 'prev': [ctx['scope'], *ctx['prev']]}


def flag_key(ctx, token):
    prefix, marker, target = token.partition('@')
    return prefix + '@' + reference(ctx, target) if marker else token


def flag(s, ctx, token):
    deadline = s['countries'][ctx['scope']]['flags'].get(flag_key(ctx, token))
    return deadline is not None and (deadline == -1 or deadline > s['day'])


def value(s, ctx, token):
    if token in s['temps']: return s['temps'][token]
    country = s['countries'][ctx['scope']]
    if token == 'num_ships': return country['num_ships']
    if token.startswith('civilian_intel@'):
        return country['intel'].get(reference(ctx, token.partition('@')[2]), 0)
    try: return float(token)
    except ValueError: raise AssertionError(('Unknown numeric input', token))


def compare(left, op, right):
    return {'=': left == right, '<': left < right, '>': left > right}[op]


def condition(nodes, s, ctx):
    results = []
    country = s['countries'][ctx['scope']]
    for key, op, data in nodes:
        if key in TRIGGERS:
            results.append(condition(TRIGGERS[key], s, ctx) == (data == 'yes'))
        elif key in ('ROOT', 'FROM', 'THIS', 'PREV') or key in COUNTRIES:
            tag = reference(ctx, key)
            results.append(tag is not None and condition(data, s, switch(ctx, tag)))
        elif key in ('AND', 'OR', 'NOT'):
            items = [condition([item], s, ctx) for item in data]
            results.append(all(items) if key == 'AND' else any(items) if key == 'OR' else not all(items))
        elif key == 'always': results.append(data == 'yes')
        elif key == 'exists': results.append(country['exists'] == (data == 'yes'))
        elif key == 'is_subject': results.append(country['subject'] == (data == 'yes'))
        elif key == 'is_ai': results.append(country['ai'] == (data == 'yes'))
        elif key == 'tag': results.append(ctx['scope'] == reference(ctx, data))
        elif key == 'is_coastal': results.append(country['coastal'] == (data == 'yes'))
        elif key == 'any_owned_state':
            # Enter an explicitly owned state; PREV now refers to its owning country.
            # Fixtures contain one representative owned state with independent control.
            state_frame = ctx | {'prev': [ctx['scope'], *ctx['prev']], 'state_scope': True}
            results.append(condition(data, s, state_frame))
        elif key == 'is_controlled_by':
            assert ctx.get('state_scope'), 'is_controlled_by requires a state scope'
            results.append(country['coast_controller'] == reference(ctx, data))
        elif key == 'check_variable':
            variable, operator, wanted = data[0]
            results.append(compare(value(s, ctx, variable), operator, value(s, ctx, wanted)))
        elif key == 'command_power': results.append(compare(country['cp'], op, value(s, ctx, data)))
        elif key == 'has_equipment':
            equipment, operator, wanted = data[0]
            assert equipment in ('convoy', 'convoy_1')
            stock = country['convoy'] + (country['other_convoys'] if equipment == 'convoy' else 0)
            results.append(compare(stock, operator, value(s, ctx, wanted)))
        elif key == 'is_in_array':
            array, operator, member = data[0]
            assert operator == '='
            results.append(reference(ctx, member) in country['arrays'].get(array, []))
        elif key == 'has_country_flag': results.append(flag(s, ctx, data))
        elif key == 'has_war_with': results.append(reference(ctx, data) in country['wars'])
        elif key == 'has_non_aggression_pact_with': results.append(reference(ctx, data) in country['naps'])
        elif key == 'is_in_faction_with':
            peer = s['countries'][reference(ctx, data)]
            results.append(country['faction'] is not None and peer['faction'] == country['faction'])
        else: raise AssertionError(('Unknown trigger', key, op, data))
    return all(results)


def execute(nodes, s, ctx):
    branch = None
    for key, op, data in nodes:
        country = s['countries'][ctx['scope']]
        if key in ('if', 'else_if', 'else'):
            if key == 'if': branch = False
            assert branch is not None
            allowed = not branch and (key == 'else' or condition(one(data, 'limit'), s, ctx))
            if allowed:
                execute([node for node in data if node[0] != 'limit'], s, ctx)
                branch = True
            continue
        branch = None
        if key in EFFECTS:
            assert data == 'yes'
            execute(EFFECTS[key], s, ctx)
        elif key in ('ROOT', 'FROM', 'THIS', 'PREV') or key in COUNTRIES:
            execute(data, s, switch(ctx, reference(ctx, key)))
        elif key in ('every_possible_country', 'every_other_country', 'random_other_country'):
            matches = []
            for tag in s['countries']:
                if key != 'every_possible_country' and (tag == ctx['scope'] or not s['countries'][tag]['exists']): continue
                nested = switch(ctx, tag)
                if condition(one(data, 'limit'), s, nested): matches.append(nested)
            for nested in matches[:1] if key == 'random_other_country' else matches:
                execute([node for node in data if node[0] != 'limit'], s, nested)
        elif key == 'random':
            chance = value(s, ctx, one(data, 'chance'))
            if chance > 0 and s['random_success']:
                execute([node for node in data if node[0] != 'chance'], s, ctx)
        elif key == 'add_command_power': country['cp'] += value(s, ctx, data)
        elif key == 'set_country_flag':
            if isinstance(data, list):
                fields = {k: v for k, op, v in data}
                deadline = s['day'] + int(fields['days']) if 'days' in fields else -1
                country['flags'][flag_key(ctx, fields['flag'])] = deadline
            else: country['flags'][flag_key(ctx, data)] = -1
        elif key == 'clr_country_flag': country['flags'].pop(flag_key(ctx, data), None)
        elif key == 'set_temp_variable':
            name, operator, wanted = data[0]
            assert operator == '='
            s['temps'][name] = value(s, ctx, wanted)
        elif key == 'multiply_temp_variable':
            name, operator, multiplier = data[0]
            s['temps'][name] *= value(s, ctx, multiplier)
        elif key == 'clamp_temp_variable':
            fields = {k: v for k, op, v in data}
            name = fields['var']
            s['temps'][name] = min(value(s, ctx, fields['max']), max(value(s, ctx, fields['min']), s['temps'][name]))
        elif key == 'add_equipment_to_stockpile':
            # Only the concrete stockpile calls used by this product are modeled.
            # Separate native23 calibration, not this adapter, established 11/9.
            fields = {k: v for k, op, v in data}
            assert set(fields) == {'type', 'amount'} and fields['type'] == 'convoy_1'
            amount = value(s, ctx, fields['amount'])
            assert amount in (-1, 1) and country['convoy'] + amount >= 0
            country['convoy'] += amount
        elif key == 'country_event': s['events'].append((ctx['scope'], one(data, 'id')))
        elif key in ('custom_effect_tooltip', 'log', 'name'): pass
        else: raise AssertionError(('Unknown effect', key, op, data))


def prepare(s, actor='GER', peer='MEX'):
    s['countries'][actor]['arrays']['sanctions_targets'].append(peer)
    s['countries'][actor]['wars'].add(peer)
    s['countries'][peer]['wars'].add(actor)
    s['countries'][actor]['intel'][peer] = 1
    return context(actor, peer)


def effect(s, name, ctx):
    execute(EFFECTS[P + name], s, ctx)
    s['temps'].clear()


class MaritimeTests(unittest.TestCase):
    def test_four_countries_same_paid_guarded_cycle(self):
        for actor in ('USA', 'GER', 'BRA', 'UKR'):
            with self.subTest(actor=actor):
                s = state(); ctx = prepare(s, actor)
                unrelated = deepcopy(s['countries']['CAN'])
                # Actual decision adapters enter actor/PREVtarget; repeat costs nothing.
                execute(one(DECISIONS['start_shadow_fleet_hunt'], 'complete_effect'), s, context(actor))
                effect(s, 'start', ctx)
                self.assertEqual(s['countries'][actor]['cp'], 75)
                effect(s, 'intercept', ctx); effect(s, 'intercept', ctx)
                self.assertEqual(s['countries'][actor]['convoy'], 9)
                self.assertEqual(s['countries']['MEX']['convoy'], 7)
                self.assertEqual(s['countries']['CAN'], unrelated)
                self.assertEqual(s['countries'][actor]['treasury'], 7)
                self.assertEqual(s['countries']['MEX']['treasury'], 7)
                self.assertEqual(len(s['events']), 2)

    def test_gate_failures_are_noops_even_forced(self):
        reasons = ('peace', 'wrong_opponent', 'no_sanctions', 'puppet', 'no_ships',
                   'no_coast', 'no_controlled_coast', 'peer_no_coast', 'peer_no_controlled_coast', 'peer_no_convoys', 'same_faction',
                   'nap', 'no_cp', 'peer_extinct', 'actor_extinct')
        for reason in reasons:
            with self.subTest(reason=reason):
                s = state(); ctx = prepare(s)
                actor, peer = s['countries']['GER'], s['countries']['MEX']
                if reason == 'peace': actor['wars'].clear(); peer['wars'].clear()
                elif reason == 'wrong_opponent': actor['wars'] = {'CAN'}
                elif reason == 'no_sanctions': actor['arrays']['sanctions_targets'].clear()
                elif reason == 'puppet': actor['subject'] = True
                elif reason == 'no_ships': actor['num_ships'] = 0
                elif reason == 'no_coast': actor['coastal'] = False
                elif reason == 'no_controlled_coast': actor['coast_controller'] = 'CAN'
                elif reason == 'peer_no_coast': peer['coastal'] = False
                elif reason == 'peer_no_controlled_coast': peer['coast_controller'] = 'CAN'
                elif reason == 'peer_no_convoys': peer['convoy'] = 0
                elif reason == 'same_faction': actor['faction'] = peer['faction'] = 'same'
                elif reason == 'nap': actor['naps'].add('MEX')
                elif reason == 'no_cp': actor['cp'] = 24.99
                elif reason == 'peer_extinct': peer['exists'] = False
                else: actor['exists'] = False
                before = deepcopy(s)
                effect(s, 'start', ctx); effect(s, 'intercept', ctx)
                self.assertEqual(s, before)
        for actor in ('SWI', 'NEP'):
            s = state(); ctx = prepare(s, actor); before = deepcopy(s)
            effect(s, 'start', ctx)
            self.assertEqual(s, before)

    def test_start_minimum_exactly_25_and_no_double_payment(self):
        s = state(); ctx = prepare(s); s['countries']['GER']['cp'] = 25
        effect(s, 'start', ctx); effect(s, 'start', ctx)
        self.assertEqual(s['countries']['GER']['cp'], 0)
        self.assertTrue(flag(s, ctx, P + 'operation@PREV'))

    def test_monthly_ai_plans_each_country_without_global_gui_gate(self):
        monthly = one(one(load(FILES[3]), 'on_actions'), 'on_monthly')
        monthly_effect = one(monthly, 'effect')
        ai_branch = monthly_effect[0]
        self.assertEqual(ai_branch[0], 'if')
        self.assertEqual(one(one(ai_branch[2], 'random'), 'chance'), '4')
        for actor in ('USA', 'GER', 'BRA', 'UKR'):
            with self.subTest(actor=actor):
                s = state(); ctx = prepare(s, actor)
                s['countries'][actor]['ai'] = True
                unrelated = deepcopy(s['countries']['CAN'])
                execute([ai_branch], s, ctx); execute([ai_branch], s, ctx)
                self.assertEqual(s['countries'][actor]['cp'], 75)
                self.assertTrue(flag(s, ctx, P + 'operation@PREV'))
                self.assertFalse(s['events'])
                self.assertEqual(s['countries']['CAN'], unrelated)
                # The tick can resolve in the same month, still under the same gates.
                effect(s, 'tick', ctx)
                self.assertEqual(s['countries']['MEX']['convoy'], 7)
        for reason in ('human', 'peace', 'no_cp', 'puppet', 'landlocked'):
            with self.subTest(reason=reason):
                s = state(); ctx = prepare(s)
                actor = s['countries']['GER']; actor['ai'] = True
                if reason == 'human': actor['ai'] = False
                elif reason == 'peace': actor['wars'].clear()
                elif reason == 'no_cp': actor['cp'] = 24
                elif reason == 'puppet': actor['subject'] = True
                else: actor['coastal'] = False
                before = deepcopy(s); execute([ai_branch], s, ctx)
                self.assertEqual(s, before)

    def test_stop_restart_and_elapsed_time_preserve_pair_cooldown(self):
        s = state(); ctx = prepare(s)
        effect(s, 'start', ctx); effect(s, 'intercept', ctx)
        deadline = s['countries']['GER']['flags'][P + 'cooldown@MEX']
        effect(s, 'stop', ctx)
        self.assertEqual(s['countries']['GER']['flags'][P + 'cooldown@MEX'], deadline)
        s['day'] = 1
        effect(s, 'start', ctx); effect(s, 'intercept', ctx)
        self.assertEqual(s['countries']['GER']['cp'], 50)
        self.assertEqual(s['countries']['MEX']['convoy'], 7)
        s['day'] = 89; effect(s, 'intercept', ctx)
        self.assertEqual(s['countries']['MEX']['convoy'], 7)
        s['day'] = 90; effect(s, 'intercept', ctx)
        self.assertEqual(s['countries']['MEX']['convoy'], 6)

    def test_changed_conditions_block_execution_and_monthly_cleanup(self):
        for reason in ('peace', 'revoked', 'annexed', 'ships_lost', 'convoys_lost', 'expired'):
            with self.subTest(reason=reason):
                s = state(); ctx = prepare(s); effect(s, 'start', ctx)
                actor, peer = s['countries']['GER'], s['countries']['MEX']
                if reason == 'peace': actor['wars'].clear()
                elif reason == 'revoked': actor['arrays']['sanctions_targets'].clear()
                elif reason == 'annexed': peer['exists'] = False
                elif reason == 'ships_lost': actor['num_ships'] = 0
                elif reason == 'convoys_lost': peer['convoy'] = 0
                else: s['day'] = 90
                snapshot = deepcopy(s)
                effect(s, 'intercept', ctx)
                self.assertEqual(s, snapshot)
                effect(s, 'tick', ctx)
                self.assertFalse(flag(s, ctx, 'shadow_fleet_hunt@PREV'))
                self.assertFalse(flag(s, ctx, P + 'operation@PREV'))
                self.assertFalse(s['events'])

    def test_actual_lift_and_extinct_cleanup_preserve_cooldown(self):
        inherited = {k: v for k, op, v in load(FILES[-1])}
        # Execute just the narrow maritime call added to the inherited complex
        # economic cleanup. Its other legacy economic loops are outside this adapter.
        lift = inherited['revoke_sanctions'][0]
        self.assertEqual(lift, ('ROOT', '=', [(P + 'stop', '=', 'yes')]))
        extinct = one(inherited['revoke_sanctions_non_exist_country'], 'every_country')
        self.assertIn((P + 'stop', '=', 'yes'), extinct)
        for actor in ('USA', 'GER', 'BRA', 'UKR'):
            s = state(); ctx = prepare(s, actor)
            effect(s, 'start', ctx); effect(s, 'intercept', ctx)
            saved_deadline = s['countries'][actor]['flags'][P + 'cooldown@MEX']
            target_context = context('MEX', actor) | {'root': actor}
            execute([lift], s, target_context)
            self.assertFalse(flag(s, ctx, P + 'operation@PREV'))
            self.assertFalse(flag(s, ctx, 'shadow_fleet_hunt@PREV'))
            self.assertEqual(s['countries'][actor]['flags'][P + 'cooldown@MEX'], saved_deadline)
            # Re-imposing sanctions/restarting still cannot recapture immediately.
            effect(s, 'start', ctx); effect(s, 'intercept', ctx)
            self.assertEqual(s['countries']['MEX']['convoy'], 7)
            s['countries']['MEX']['exists'] = False
            execute([(P + 'stop', '=', 'yes')], s, ctx)
            self.assertFalse(flag(s, ctx, P + 'operation@PREV'))
            self.assertEqual(s['countries'][actor]['flags'][P + 'cooldown@MEX'], saved_deadline)

    def test_legacy_receipt_pair_scope_and_92_day_quarter_boundary(self):
        s = state(); ctx = prepare(s)
        s['countries']['GER']['flags']['shadow_fleet_hunt@MEX'] = -1
        effect(s, 'intercept', ctx); effect(s, 'tick', ctx)
        self.assertFalse(s['events'])
        self.assertFalse(flag(s, ctx, 'shadow_fleet_hunt@PREV'))
        s['day'] = 1; effect(s, 'start', ctx)
        # A monthly pulse resolves before the old 92-day quarterly boundary.
        s['day'] = 31; effect(s, 'tick', ctx)
        self.assertEqual(s['countries']['MEX']['convoy'], 7)
        s['day'] = 62; effect(s, 'tick', ctx)
        self.assertEqual(s['countries']['MEX']['convoy'], 7)
        wrong = context('GER', 'CAN')
        s['countries']['GER']['wars'].add('CAN')
        s['countries']['GER']['arrays']['sanctions_targets'].append('CAN')
        before = deepcopy(s); effect(s, 'intercept', wrong)
        self.assertEqual(s, before)
        s['day'] = 93; effect(s, 'tick', ctx)
        self.assertEqual(s['countries']['MEX']['convoy'], 7)

    def test_old_queued_and_new_notification_events_are_inert(self):
        for identity in [f'sanctions.{number}' for number in range(5, 10)] + [P[:-1] + '.1', P[:-1] + '.2']:
            event = EVENTS[identity]
            self.assertFalse(any(key == 'immediate' for key, op, value in event))
            s = state(); before = deepcopy(s)
            for key, op, option in event:
                if key == 'option': execute(option, s, context())
            self.assertEqual(s, before)
        s = state(); before = deepcopy(s)
        execute(one(DECISIONS['shadow_fleet_PMC_deploy'], 'complete_effect'), s, context())
        self.assertEqual(s, before)
        self.assertFalse(condition(one(DECISIONS['shadow_fleet_PMC_deploy'], 'available'), s, context()))

    def test_integrations_grammar_localisation_and_original_encoding(self):
        for path in FILES[:7]: self.assertEqual(grammar.inspect(load(path)), [], path)
        effects = (ROOT / FILES[1]).read_text(encoding='utf-8-sig')
        self.assertNotRegex(effects, r'create_wargoal|modify_treasury|add_named_threat|USA|SOV|PMC_shadow_fleet')
        monthly = one(one(load(FILES[3]), 'on_actions'), 'on_monthly')
        monthly_effect = one(monthly, 'effect')
        self.assertEqual(monthly_effect[1], (P + 'tick', '=', 'yes'))
        self.assertNotIn('sanctions.5', (ROOT / FILES[3]).read_text())
        self.assertNotIn('sanctions.6', (ROOT / FILES[3]).read_text())
        ai = (ROOT / FILES[4]).read_text()
        head = ai[:ai.index('show_eu4_like_ages_window')]
        self.assertNotIn(P, ai)
        self.assertNotIn('naval_power_of_the_continent', head)
        self.assertNotIn('PMC_shadow_fleet', head)
        stop = DECISIONS[P + 'stop_operation']
        self.assertFalse(any(key == 'target_array' for key, op, value in stop))
        # Tracked inherited game files were LF, locale BOMs must remain present.
        for path in FILES[2:6] + FILES[7:9] + FILES[-1:]:
            raw = (ROOT / path).read_bytes()
            self.assertNotIn(b'\r\n', raw, path)
        for path in FILES[7:11]: self.assertTrue((ROOT / path).read_bytes().startswith(b'\xef\xbb\xbf'), path)
        for language in ('english', 'russian'):
            path = ROOT / f'localisation/{language}/{P}l_{language}.yml'
            keys = re.findall(r'^\s+([^\s:]+):', path.read_text(encoding='utf-8-sig'), re.M)
            self.assertEqual(len(keys), len(set(keys)))
            for key in ('stop_operation', 'stop_operation_desc', 'legacy_cancelled',
                        'legacy_cancelled_title', 'intercept_title', 'intercept_desc',
                        'loss_title', 'loss_desc', 'acknowledge'):
                self.assertIn(P + key, keys)
            legacy = ROOT / f'localisation/{language}/MD_decisions_l_{language}.yml'
            self.assertEqual(len(re.findall(r'^ start_shadow_fleet_hunt:', legacy.read_text(encoding='utf-8-sig'), re.M)), 1)

    def test_removed_war_guard_mutant_is_detected(self):
        key = P + 'pair_eligible'; original = TRIGGERS[key]
        try:
            TRIGGERS[key] = [node for node in original if node[0] != 'has_war_with']
            s = state(); ctx = prepare(s); s['countries']['GER']['wars'].clear()
            effect(s, 'start', ctx); effect(s, 'intercept', ctx)
            self.assertEqual(s['countries']['MEX']['convoy'], 7,
                             'Removing the actual wartime guard must reproduce the old defect')
        finally: TRIGGERS[key] = original
        s = state(); ctx = prepare(s); s['countries']['GER']['wars'].clear()
        effect(s, 'start', ctx); effect(s, 'intercept', ctx)
        self.assertEqual(s['countries']['MEX']['convoy'], 8)

    def test_concrete_transfer_conserves_stock_and_rejects_aggregate_only_target(self):
        s = state(); ctx = prepare(s)
        s['countries']['GER']['convoy'] = 0
        s['countries']['MEX']['convoy'] = 1
        s['countries']['MEX']['other_convoys'] = 5
        effect(s, 'start', ctx); effect(s, 'intercept', ctx)
        self.assertEqual(s['countries']['GER']['convoy'], 1)
        self.assertEqual(s['countries']['MEX']['convoy'], 0)
        self.assertEqual(s['countries']['MEX']['other_convoys'], 5)
        self.assertTrue(flag(s, ctx, P + 'cooldown@PREV'))
        for actor in ('USA', 'GER', 'BRA', 'UKR'):
            s = state(); ctx = prepare(s, actor)
            # Aggregate readiness may see other convoy types, but concrete removal
            # must never fabricate convoy_1 or consume a cooldown from an empty pool.
            s['countries']['MEX']['convoy'] = 0
            s['countries']['MEX']['other_convoys'] = 5
            effect(s, 'start', ctx)
            self.assertTrue(flag(s, ctx, P + 'operation@PREV'))
            before = deepcopy(s); effect(s, 'intercept', ctx)
            self.assertEqual(s, before)
            self.assertFalse(flag(s, ctx, P + 'cooldown@PREV'))

    def test_old_send_equipment_mutant_is_not_assumed_to_transfer(self):
        key = P + 'intercept'; original = EFFECTS[key]
        mutant = deepcopy(original)
        branch = mutant[0][2]
        target_index = next(index for index, node in enumerate(branch)
                            if node[0] == 'PREV' and node[2][0][0] == 'add_equipment_to_stockpile')
        branch[target_index] = ('PREV', '=', [('send_equipment', '=', [
            ('equipment', '=', 'convoy'), ('amount', '=', '1'), ('target', '=', 'PREV')])])
        try:
            EFFECTS[key] = mutant
            s = state(); ctx = prepare(s); effect(s, 'start', ctx)
            with self.assertRaisesRegex(AssertionError, 'Unknown effect.*send_equipment'):
                effect(s, 'intercept', ctx)
            self.assertEqual(s['countries']['GER']['convoy'], 8)
            self.assertEqual(s['countries']['MEX']['convoy'], 8)
        finally: EFFECTS[key] = original
        body = one(EFFECTS[key], 'if')
        self.assertEqual(one(one(one(body, 'limit'), 'PREV'), 'has_equipment'),
                         [('convoy_1', '>', '0')])
        self.assertNotIn('send_equipment', (ROOT / FILES[1]).read_text())

    def test_effect_only_state_iterator_mutant_is_rejected(self):
        key = P + 'actor_eligible'; original = TRIGGERS[key]
        mutant = deepcopy(original)
        for index, (name, operator, body) in enumerate(mutant):
            if name == 'any_owned_state':
                mutant[index] = ('any_owned_controlled_state', operator, body)
        try:
            TRIGGERS[key] = mutant
            s = state(); ctx = prepare(s)
            with self.assertRaisesRegex(AssertionError, 'Unknown trigger'):
                effect(s, 'start', ctx)
            self.assertEqual(s['countries']['GER']['cp'], 100)
        finally: TRIGGERS[key] = original

    def test_documented_state_scope_and_owned_controlled_coast(self):
        expected = [('is_coastal', '=', 'yes'), ('is_controlled_by', '=', 'PREV')]
        self.assertEqual(one(TRIGGERS[P + 'actor_eligible'], 'any_owned_state'), expected)
        target = one(TRIGGERS[P + 'pair_eligible'], 'PREV')
        self.assertEqual(one(target, 'any_owned_state'), expected)
        s = state(); ctx = prepare(s, 'BRA')
        # Another country's controlled coast cannot stand in for Brazil's own coast.
        s['countries']['BRA']['coast_controller'] = 'CAN'
        effect(s, 'start', ctx)
        self.assertFalse(flag(s, ctx, P + 'operation@PREV'))
        s['countries']['BRA']['coast_controller'] = 'BRA'
        s['countries']['MEX']['coast_controller'] = 'CAN'
        effect(s, 'start', ctx)
        self.assertFalse(flag(s, ctx, P + 'operation@PREV'))
        s['countries']['MEX']['coast_controller'] = 'MEX'
        effect(s, 'start', ctx)
        self.assertTrue(flag(s, ctx, P + 'operation@PREV'))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MaritimeTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'tests_passed': result.wasSuccessful(), 'tests_run': result.testsRun,
        'proof_scope': 'actual-source AST with explicit country and clock inputs',
        'native_campaign_proven': False,
        'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in FILES}}, indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
