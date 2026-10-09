"""Exercise actual scripted AI callers after an eligible request is selected.

Reserve payment uses the real helper AST. Candidate selection, native stockpile
removal and the random damage result are explicit fixture boundaries. The
damage payload is never executed. Its paid-attempt marker is independent of
interception or damage; an intercepted attack still spends its missile.
This suite also executes the actual daily retaliation queue control flow across
country orders. Native raid creation, event scheduling, stockpile removal,
target availability and random damage remain
explicit fixture boundaries; this is not a campaign or human UI test.
"""
from copy import deepcopy
from itertools import permutations
import json

from test_launch import one, read
from test_reserve_payment import HELPER as PAYMENT, SHORT, LONG, execute as pay
from readiness_model import assert_default_off_contract, is_ready

SUCCESS = 'eon_nuclear_scripted_launch_succeeded'
PAID = 'eon_nuclear_scripted_reserve_paid'
STRATEGIC = 'launch_nuclear_ai_country_strike'
TACTICAL = ('launch_tactical_nuclear_ai_strike', 'launch_tactical_nuclear_ai_first_strike')
LAUNCHES = (STRATEGIC,) + TACTICAL


def walk(nodes):
    for node in nodes:
        yield node
        if isinstance(node[2], list):
            yield from walk(node[2])


def contains(nodes, keys):
    return any(key in keys for key, op, value in walk(nodes))


def after_limit(nodes):
    return [node for node in nodes if node[0] != 'limit']


def damage_frame(body):
    """Replace damage with a bounded fixture, without inventing an outcome flag."""
    assert one(body, 'chance') == 'ai_nuke_success_chance'
    assert contains(body, {'launch_nuke', 'damage_units'})
    assert ('set_country_flag', '=', SUCCESS) not in list(walk(body)), 'An intercepted paid attempt is still an attack'
    return [('chance', '=', 'ai_nuke_success_chance'), ('__fixture_damage__', '=', 'yes')]


def check_event_guards(nodes, paid=False, selected=False):
    """A refusal must not produce a report event or a retaliation callback."""
    count = 0
    for key, op, value in nodes:
        if key == 'country_event' and value in ('nuclear_ai_raid.1', 'nuclear_ai_raid.2'):
            assert paid and selected, 'Strike report must be inside payment and eligible-target guards'
            count += 1
        elif isinstance(value, list) and key != 'limit':
            limits = [body for name, operator, body in value if name == 'limit']
            gate = limits[0] if limits else []
            next_paid = paid or ('has_country_flag', '=', PAID) in list(walk(gate))
            next_selected = selected or contains(gate, {'any_owned_state', 'any_controlled_state', 'capital_scope'})
            count += check_event_guards(after_limit(value), next_paid, next_selected)
    return count


def project(nodes):
    """Reduce only the huge damage helpers, keeping payment/outcome control flow."""
    output = []
    for key, op, value in nodes:
        if key == 'random' and isinstance(value, list) and ('chance', '=', 'ai_nuke_success_chance') in value:
            output.append((key, op, damage_frame(value)))
        elif key in ('set_country_flag', 'clr_country_flag') and value == SUCCESS:
            output.append((key, op, value))
        elif key == 'eon_nuclear_scripted_pay_reserve':
            output.append((key, op, value))
        elif key == 'set_temp_variable' and any(name in ('eon_nuclear_scripted_actor', 'eon_nuclear_scripted_request') for name, assignment, source in value):
            output.append((key, op, value))
        elif key == 'random_list':
            output.append((key, op, [(weight, operator, project(branch)) for weight, operator, branch in value]))
        elif isinstance(value, list) and key != 'limit':
            reduced = project(after_limit(value))
            if reduced:
                if key in ('if', 'else_if'):
                    gate = one(value, 'limit')
                    # Source selection rules remain a fixture boundary. Preserve
                    # the newly relevant payment, readiness and outcome gates.
                    if any(name in ('eon_nuclear_arsenal_ready', 'exists') or
                           name == 'has_country_flag' and item in (SUCCESS, PAID)
                           for name, operator, item in walk(gate)):
                        reduced.insert(0, ('limit', '=', gate))
                    else:
                        reduced.insert(0, ('limit', '=', []))
                elif key in ('every_neighbor_country', 'every_enemy_country'):
                    selectors = [node for node in one(value, 'limit')
                                 if node[0] in ('any_controlled_state', 'any_owned_state', 'capital_scope')]
                    assert len(selectors) == 1, 'Candidate needs its actual state selector before payment'
                    reduced.insert(0, ('limit', '=', selectors))
                output.append((key, op, reduced))
    return output


class Runtime:
    def __init__(self, short=0, long=0, ready=True, hit=True, targets=('GER',), branch=0, transfer_fails=False, eligible_state=True, prototype_enabled=None):
        self.countries = {tag: {'flags': {SUCCESS}, 'vars': {'arctic_nuclear_level': 0},
                                'stock': {SHORT: 0, LONG: 0}, 'threat': 0, 'damage': 0, 'ready': True,
                                'capitulated': False}
                          for tag in ('USA', 'GER', 'FRA', 'SOV')}
        self.countries['USA']['stock'] = {SHORT: short, LONG: long}
        self.countries['USA']['ready'] = ready
        self.root, self.origin = 'GER', 'USA'
        self.temp = {'v': 'USA'}
        self.variables = {'global.nuke_striker': 'USA', 'global.temp_arctic_nuclear_level': 0}
        self.global_flags = set()
        self.hit, self.targets, self.branch = hit, list(targets), branch
        self.transfer_fails = transfer_fails
        self.eligible_state = eligible_state
        self.helpers = {}
        self.after_strategic_hook = None
        self.launch_frames = []
        self.prototype_enabled = prototype_enabled

    def scope(self, name, stack):
        if name == 'ROOT':
            return self.root
        if name == 'FROM':
            return self.origin
        if name == 'PREV':
            return stack[-2]
        if name == 'THIS':
            return stack[-1]
        if name.startswith('var:'):
            return self.value(name[4:], stack)
        return name

    def value(self, name, stack):
        if name in self.temp:
            return self.temp[name]
        if name.startswith('global.'):
            return self.variables.get(name, 0)
        if name in ('ROOT', 'FROM', 'THIS', 'PREV') or name.startswith('var:'):
            return self.scope(name, stack)
        if name.endswith('.arctic_nuclear_level'):
            source = name.removesuffix('.arctic_nuclear_level')
            country = self.value(source, stack) if source in self.temp else self.scope(source, stack)
            return self.countries[country]['vars']['arctic_nuclear_level']
        if name in self.countries[stack[-1]]['vars']:
            return self.countries[stack[-1]]['vars'][name]
        if name in ('eon_nuclear_queued_shooter', 'eon_nuclear_queued_level'):
            return 0
        return float(name)

    def predicate(self, nodes, stack):
        if stack[-1] not in self.countries and not str(stack[-1]).startswith('state:'):
            return False
        result = []
        for key, op, value in nodes:
            if key in ('AND', 'custom_override_tooltip'):
                allowed = self.predicate(value, stack)
            elif key == 'OR':
                allowed = any(self.predicate([child], stack) for child in value)
            elif key == 'NOT':
                allowed = not self.predicate(value, stack)
            elif key == 'has_country_flag':
                allowed = value in self.countries[stack[-1]]['flags']
            elif key == 'has_variable':
                variables = self.variables if value.startswith('global.') else self.countries[stack[-1]]['vars']
                allowed = value in variables or value in self.temp
            elif key == 'check_variable':
                assert len(value) == 1
                name, operator, expected = value[0]
                assert operator == '>'
                allowed = self.value(name, stack) > self.value(expected, stack)
            elif key == 'has_global_flag':
                allowed = value in self.global_flags
            elif key == 'has_capitulated':
                allowed = self.countries[stack[-1]]['capitulated'] == (value == 'yes')
            elif key == 'eon_nuclear_arsenal_ready':
                country = self.countries[stack[-1]]
                allowed = is_ready(country['ready'], country['flags'],
                                   country['vars'].get('eon_nuclear_arsenal_recovery_remaining', 0),
                                   self.prototype_enabled) == (value == 'yes')
            elif key == 'exists':
                allowed = stack[-1] in self.countries
            elif key in ('any_controlled_state', 'any_owned_state', 'capital_scope'):
                # The copied native selector is retained in the AST. Whether a
                # state meets its military/fallout criteria is a fixture input;
                # test_ai_gates independently checks the six exact source copies.
                allowed = (self.eligible_state.get(stack[-1], False)
                           if isinstance(self.eligible_state, dict) else self.eligible_state)
            elif key == 'any_country':
                allowed = any(self.predicate(value, stack+[tag]) for tag in self.countries)
            elif key in ('ROOT', 'FROM', 'PREV', 'THIS') or key.startswith('var:'):
                allowed = self.predicate(value, stack+[self.scope(key, stack)])
            else:
                raise AssertionError(('Unsupported outcome gate', key, op, value))
            result.append(allowed)
        return all(result)

    def execute(self, nodes, stack):
        taken = False
        for key, op, value in nodes:
            if key in ('if', 'else_if'):
                if key == 'if':
                    taken = False
                if not taken and self.predicate(one(value, 'limit'), stack):
                    taken = True
                    self.execute(after_limit(value), stack)
            elif key == 'else':
                if not taken:
                    taken = True
                    self.execute(value, stack)
            elif key in ('set_country_flag', 'clr_country_flag'):
                flags = self.countries[stack[-1]]['flags']
                flags.add(value) if key == 'set_country_flag' else flags.discard(value)
            elif key in ('set_global_flag', 'clr_global_flag'):
                self.global_flags.add(value) if key == 'set_global_flag' else self.global_flags.discard(value)
            elif key in ('set_variable', 'set_temp_variable', 'add_to_variable'):
                for name, assignment, source in value:
                    amount = self.value(source, stack)
                    variables = self.temp if key == 'set_temp_variable' else self.variables if name.startswith('global.') else self.countries[stack[-1]]['vars']
                    variables[name] = variables.get(name, 0)+amount if key == 'add_to_variable' else amount
            elif key == 'clear_variable':
                variables = self.variables if value.startswith('global.') else self.countries[stack[-1]]['vars']
                variables.pop(value, None)
                self.temp.pop(value, None)
            elif key == 'add_named_threat':
                self.countries[stack[-1]]['threat'] += float(one(value, 'threat'))
            elif key in LAUNCHES:
                frame = (self.value('global.nuke_striker', stack), self.value('global.temp_arctic_nuclear_level', stack), stack[-1])
                self.execute(self.helpers[key], stack)
                if key == STRATEGIC and SUCCESS in self.countries[stack[-1]]['flags']:
                    self.launch_frames.append(frame)
                if key == STRATEGIC and self.after_strategic_hook:
                    self.after_strategic_hook(self)
            elif key == 'eon_nuclear_scripted_pay_reserve':
                country = self.countries[stack[-1]]
                state = {'stock': country['stock'], 'deployed': {SHORT: 0, LONG: 0},
                         'sink': {SHORT: 0, LONG: 0}, 'variables': country['vars'],
                         'flags': country['flags'], 'temp': self.temp, 'ready': country['ready'],
                         'native_transfer_fails': self.transfer_fails, 'prototype_enabled': self.prototype_enabled}
                pay(PAYMENT, state)
            elif key in ('ROOT', 'FROM', 'PREV', 'THIS') or key.startswith('var:'):
                self.execute(value, stack+[self.scope(key, stack)])
            elif key in ('every_other_country', 'every_enemy_country', 'every_neighbor_country'):
                for country in self.targets:
                    candidate_stack = stack+[country]
                    if key == 'every_other_country' or self.predicate(one(value, 'limit'), candidate_stack):
                        self.execute(after_limit(value), candidate_stack)
            elif key == 'every_country':
                for country in self.countries:
                    if self.predicate(next((v for k, o, v in value if k == 'limit'), []), stack+[country]):
                        self.execute(after_limit(value), stack+[country])
            elif key in ('every_owned_state', 'random_owned_state', 'random_controlled_state', 'capital_scope'):
                # Exactly one eligible state is provided for each fixture victim.
                self.execute(after_limit(value), stack+['state:'+stack[-1]])
            elif key == 'random_list':
                self.execute(value[self.branch][2], stack)
            elif key == 'random':
                assert one(value, 'chance') == 'ai_nuke_success_chance'
                if self.hit:
                    self.execute([node for node in value if node[0] != 'chance'], stack)
            elif key == '__fixture_damage__':
                self.countries[stack[-2]]['damage'] += 1
            else:
                raise AssertionError(('Unsupported outcome effect', key, op, value))


def prototype_runtime(*args, **kwargs):
    """Explicitly enable only the retained prototype contract in old matrices."""
    return Runtime(*args, **kwargs, prototype_enabled=True)


def minimal_callers(nodes, launch):
    candidates = [value for key, op, value in walk(nodes)
                  if key in ('if', 'else_if') and contains(after_limit(value), {launch})]
    return [body for body in candidates if not any(key in ('if', 'else_if') and contains(after_limit(child), {launch})
                                                  for key, op, child in walk(after_limit(body)))]


def unguard_outcomes(nodes):
    """Mutation: remove outcome conditions, leaving their consequences intact."""
    result = []
    for key, op, value in nodes:
        if key == 'if' and any(name == 'has_country_flag' and flag == SUCCESS for name, operator, flag in walk(one(value, 'limit'))):
            result.extend(unguard_outcomes(after_limit(value)))
        else:
            result.append((key, op, unguard_outcomes(value) if isinstance(value, list) else value))
    return result


def exercise_daily_queue(actions, helpers):
    """Read actual daily code, varying country order and one-family payment."""
    daily = one(one(actions, 'on_daily'), 'effect')
    # Check the source binding around the call before executing scenarios.
    requests = [body for body in minimal_callers(daily, STRATEGIC)]
    assert len(requests) == 1
    request = after_limit(requests[0])
    # The selected pair lives on the target; globals are only a helper frame.
    launch_index = request.index((STRATEGIC, '=', 'yes'))
    assert request[launch_index-3:launch_index] == [
        ('set_temp_variable', '=', [('eon_nuclear_daily_queue_shooter', '=', 'eon_nuclear_queued_shooter')]),
        ('set_variable', '=', [('global.nuke_striker', '=', 'eon_nuclear_queued_shooter')]),
        ('set_variable', '=', [('global.temp_arctic_nuclear_level', '=', 'eon_nuclear_queued_level')]),
    ]
    report_candidates = [value for key, op, value in request if key == 'if'
                         and one(value, 'limit') == [('has_country_flag', '=', SUCCESS)]]
    assert len(report_candidates) == 1
    report = report_candidates[0]
    assert one(report, 'limit') == [('has_country_flag', '=', SUCCESS)]
    scoped = one(report, 'var:eon_nuclear_daily_queue_shooter')
    report = one(scoped, 'if')
    assert one(report, 'limit') == [('exists', '=', 'yes'), ('has_capitulated', '=', 'no'),
                                   ('eon_nuclear_arsenal_ready', '=', 'yes'), ('has_country_flag', '=', 'sussy_baka')]
    assert ('clr_country_flag', '=', 'sussy_baka') in report

    scenarios = [
        dict(short=0), dict(short=9), dict(short=10), dict(short=20), dict(short=0, long=10),
        dict(short=10, long=10), dict(short=10, transfer_fails=True), dict(short=10, ready=False),
        dict(short=10, eligible_state=False), dict(short=10, eligible_state={'GER': False, 'FRA': True}),
        dict(short=10, target_capitulated=True), dict(short=10, shooter_capitulated=True),
        dict(short=10, missing_shooter=True), dict(short=20, hit=False),
    ]
    cases = 0
    for config in scenarios:
        for order in permutations(('USA', 'GER', 'FRA', 'SOV')):
            for replace_context in (False, True):
                arguments = {key: value for key, value in config.items()
                             if key not in ('target_capitulated', 'shooter_capitulated', 'missing_shooter')}
                runtime = prototype_runtime(**arguments)
                runtime.helpers = helpers
                runtime.global_flags.add('amogus')
                runtime.countries['USA']['flags'].add('sussy_baka')
                for target in ('GER', 'FRA'):
                    runtime.countries[target]['flags'].add('sugoma')
                runtime.countries['GER']['capitulated'] = config.get('target_capitulated', False)
                runtime.countries['USA']['capitulated'] = config.get('shooter_capitulated', False)
                for target in ('GER', 'FRA'):
                    runtime.countries[target]['vars'].update(eon_nuclear_queued_shooter=0 if config.get('missing_shooter') else 'USA', eon_nuclear_queued_level=2)
                incoming = {'global.nuke_striker': 'SOV', 'global.temp_arctic_nuclear_level': 99}
                runtime.variables.update(incoming)
                if replace_context:
                    def replace(current):
                        current.variables['global.nuke_striker'] = 'SOV'
                        current.variables['global.temp_arctic_nuclear_level'] = 99
                    runtime.after_strategic_hook = replace
                expected_stock = dict(runtime.countries['USA']['stock'])
                expected_targets = []
                for target in (country for country in order if country in ('GER', 'FRA')):
                    eligible = (runtime.eligible_state.get(target, False) if isinstance(runtime.eligible_state, dict)
                                else runtime.eligible_state)
                    permitted = (runtime.countries['USA']['ready'] and not runtime.countries['USA']['capitulated']
                                 and not config.get('missing_shooter') and not runtime.countries[target]['capitulated']
                                 and eligible and not runtime.transfer_fails)
                    family = SHORT if expected_stock[SHORT] >= 10 else LONG if expected_stock[LONG] >= 10 else None
                    if permitted and family:
                        expected_stock[family] -= 10
                        expected_targets.append(target)
                for country in order:
                    runtime.root = country
                    runtime.execute(daily, [country])
                # A shooter processed before the final refused target cancels
                # on its next callback; it must never invent a paid attack.
                for country in order:
                    runtime.root = country
                    runtime.execute(daily, [country])
                attempted = bool(expected_targets)
                assert runtime.countries['USA']['stock'] == expected_stock, (config, order, expected_targets)
                assert runtime.countries['USA']['threat'] == (100 if attempted else 0), (config, order)
                assert ('hrucker' in runtime.countries['USA']['flags']) == attempted, (config, order)
                for target in ('GER', 'FRA'):
                    assert runtime.countries[target]['damage'] == int(target in expected_targets and runtime.hit)
                    assert runtime.countries[target]['threat'] == 0 and 'hrucker' not in runtime.countries[target]['flags']
                assert runtime.countries['SOV']['stock'][SHORT] == runtime.countries['SOV']['threat'] == 0
                assert 'hrucker' not in runtime.countries['SOV']['flags']
                assert all(not country['flags'] & {'sugoma', 'sussy_baka'} for country in runtime.countries.values())
                assert 'amogus' not in runtime.global_flags
                assert all(not set(country['vars']) & {'eon_nuclear_queued_shooter', 'eon_nuclear_queued_level'} for country in runtime.countries.values())
                assert {key: runtime.variables[key] for key in incoming} == incoming, (config, order, 'Incoming unrelated frame changed')
                assert runtime.launch_frames == [('USA', 2, target) for target in expected_targets]
                cases += 1
    refused = prototype_runtime(short=0)
    refused.helpers = helpers
    refused.global_flags.add('amogus')
    refused.countries['USA']['flags'].add('sussy_baka')
    refused.countries['GER']['flags'].add('sugoma')
    refused.countries['GER']['vars'].update(eon_nuclear_queued_shooter='USA', eon_nuclear_queued_level=2)
    refused.root = 'GER'
    refused.execute(unguard_outcomes(daily), ['GER'])
    assert refused.countries['USA']['threat'] == 100, 'Unpaid daily-report mutant must be detected'
    return cases


def run():
    assert_default_off_contract()
    raw_helpers = {name: body for name, op, body in read('common/scripted_effects/00_ai_nuclear_raids.txt')}
    frames = 0
    markers = 0
    events = 0
    helpers = {}
    for name in LAUNCHES:
        body = raw_helpers[name]
        assert body[0] == ('clr_country_flag', '=', SUCCESS), (name, 'Stale outcome must be reset before readiness')
        events += check_event_guards(body)
        for key, op, value in walk(body):
            if key == 'random' and ('chance', '=', 'ai_nuke_success_chance') in value:
                damage_frame(value)
                frames += 1
            elif key == 'if' and isinstance(value, list):
                gate = one(value, 'limit')
                if ('has_country_flag', '=', PAID) in list(walk(gate)):
                    attempted = after_limit(value)
                    assert attempted[0] == ('set_country_flag', '=', SUCCESS), 'Attempt marker must follow successful payment before event/damage'
                    assert contains(attempted[1:], {'country_event', 'random'})
                    markers += 1
        helpers[name] = project(body)
    assert frames == markers == events == 7

    actions = one(read('common/on_actions/00_ai_nuclear_raids.txt'), 'on_actions')
    war = [value for key, op, value in actions if key == 'on_war_relation_added' and contains(value, {STRATEGIC})]
    assert len(war) == 1
    war_callers = minimal_callers(war[0], STRATEGIC)
    assert len(war_callers) == 4
    cases = 0
    mutants = 0
    for body in war_callers:
        for stock, ready, hit, transfer_fails in ((10, True, True, False), (9, True, True, False),
                                                  (10, False, True, False), (10, True, False, False),
                                                  (10, True, True, True)):
            runtime = prototype_runtime(stock, ready=ready, hit=hit, transfer_fails=transfer_fails)
            runtime.helpers = helpers
            # Each caller provides an explicit ROOT/FROM shooter and target.
            assigns = [source for key, op, value in walk(after_limit(body)) if key == 'set_temp_variable'
                       for variable, operator, source in value if variable == 'global.nuke_striker']
            assert len(assigns) == 1
            if assigns[0] == 'ROOT':
                runtime.root, runtime.origin = 'USA', 'GER'
            runtime.execute(after_limit(body), [runtime.root])
            attempted = stock >= 10 and ready and not transfer_fails
            assert ('hrucker' in runtime.countries['USA']['flags']) == attempted
            assert runtime.countries['USA']['threat'] == (100 if attempted else 0)
            assert runtime.countries['GER']['damage'] == int(attempted and hit)
            assert bool(runtime.global_flags) == (attempted and body in war_callers[:2])
            cases += 1
        no_target = prototype_runtime(short=10, eligible_state=False)
        no_target.helpers = helpers
        if assigns[0] == 'ROOT':
            no_target.root, no_target.origin = 'USA', 'GER'
        no_target.execute(after_limit(body), [no_target.root])
        assert no_target.countries['USA']['stock'][SHORT] == 10
        assert no_target.countries['USA']['threat'] == 0
        assert 'hrucker' not in no_target.countries['USA']['flags']
        assert SUCCESS not in no_target.countries['GER']['flags']
        assert not no_target.global_flags
        cases += 1
        runtime = prototype_runtime(short=0)
        runtime.helpers = helpers
        if assigns[0] == 'ROOT':
            runtime.root, runtime.origin = 'USA', 'GER'
        runtime.execute(unguard_outcomes(after_limit(body)), [runtime.root])
        assert runtime.countries['USA']['threat'] > 0, 'Missing-result-guard mutant was not exposed'
        mutants += 1

    monthly = [value for key, op, value in actions if key == 'on_monthly']
    last_stand = [body for block in monthly for body in minimal_callers(block, STRATEGIC)]
    assert len(last_stand) == 1
    for hit in (True, False):
        runtime = prototype_runtime(short=10, targets=('GER', 'FRA'), hit=hit)
        runtime.root, runtime.origin = 'USA', 'GER'
        runtime.helpers = helpers
        runtime.execute(after_limit(last_stand[0]), ['USA'])
        assert runtime.countries['GER']['vars']['nukes_strikes_count'] == 1
        assert runtime.countries['FRA']['vars'].get('nukes_strikes_count', 0) == 0
        assert runtime.countries['GER']['damage'] == int(hit) and runtime.countries['FRA']['damage'] == 0
        assert 'hrucker' in runtime.countries['USA']['flags']
        assert runtime.countries['USA']['stock'][SHORT] == 0
        cases += 1
    for stock, ready, eligible_state, targets in ((0, True, True, ('GER', 'FRA')),
                                                 (10, False, True, ('GER', 'FRA')),
                                                 (10, True, False, ('GER', 'FRA')),
                                                 (10, True, True, ())):
        refused = prototype_runtime(short=stock, ready=ready, eligible_state=eligible_state, targets=targets)
        refused.root, refused.origin, refused.helpers = 'USA', 'GER', helpers
        refused.execute(after_limit(last_stand[0]), ['USA'])
        assert 'hrucker' not in refused.countries['USA']['flags']
        assert all(country['vars'].get('nukes_strikes_count', 0) == 0
                   for country in refused.countries.values())
        assert all(country['damage'] == 0 for country in refused.countries.values())
        cases += 1
    mutant = prototype_runtime(short=10, targets=('GER', 'FRA'))
    mutant.root, mutant.origin, mutant.helpers = 'USA', 'GER', helpers
    mutant.execute(unguard_outcomes(after_limit(last_stand[0])), ['USA'])
    assert mutant.countries['FRA']['vars']['nukes_strikes_count'] == 1
    mutants += 1

    for name in TACTICAL:
        callers = [body for block in monthly for body in minimal_callers(block, name)]
        assert len(callers) == 1
        for targets, hit, branch, stock in ((('GER',), True, 0, 1), (('GER',), False, 0, 1),
                                            ((), True, 0, 1), (('GER',), True, 3, 1),
                                            (('GER',), True, 0, 0)):
            runtime = prototype_runtime(short=stock, targets=targets, hit=hit, branch=branch)
            runtime.root, runtime.origin, runtime.helpers = 'USA', 'GER', helpers
            runtime.execute(after_limit(callers[0]), ['USA'])
            attempted = bool(targets) and branch != 3 and stock > 0
            assert ('hrucker' in runtime.countries['USA']['flags']) == attempted
            assert (SUCCESS in runtime.countries['USA']['flags']) == attempted
            assert runtime.countries['GER']['damage'] == int(attempted and hit)
            cases += 1
        mutant = prototype_runtime(short=0)
        mutant.root, mutant.origin, mutant.helpers = 'USA', 'GER', helpers
        mutant.execute(unguard_outcomes(after_limit(callers[0])), ['USA'])
        assert 'hrucker' in mutant.countries['USA']['flags']
        mutants += 1
        for branch in range(3):
            runtime = prototype_runtime(short=10, eligible_state=False, branch=branch)
            runtime.root, runtime.origin, runtime.helpers = 'USA', 'GER', helpers
            runtime.execute(after_limit(callers[0]), ['USA'])
            assert runtime.countries['USA']['stock'][SHORT] == 10
            assert 'hrucker' not in runtime.countries['USA']['flags']
            assert SUCCESS not in runtime.countries['USA']['flags']
            assert runtime.countries['GER']['damage'] == 0
            cases += 1

    callbacks = minimal_callers(read('events/00_Nuclear_ai_events.txt'), STRATEGIC)
    assert len(callbacks) == 1
    for stock, hit in ((10, True), (0, True), (10, False)):
        runtime = prototype_runtime(short=stock, hit=hit)
        runtime.helpers = helpers
        runtime.variables['global.nuke_striker'] = 'SOV'
        runtime.execute(after_limit(callbacks[0]), ['GER'])
        assert runtime.countries['USA']['threat'] == (100 if stock >= 10 else 0)
        assert runtime.variables['global.nuke_striker'] == 'SOV'
        cases += 1
    mutant = prototype_runtime(short=0)
    mutant.helpers = helpers
    mutant.execute(unguard_outcomes(after_limit(callbacks[0])), ['GER'])
    assert mutant.countries['USA']['threat'] == 100
    mutants += 1

    default_off_cases = 0
    for body in war_callers:
        runtime = Runtime(short=10, ready=False)
        runtime.helpers = helpers
        runtime.countries['USA']['flags'].add('eon_nuclear_arsenal_safety_mode')
        runtime.countries['USA']['vars']['eon_nuclear_arsenal_recovery_remaining'] = 4
        assigns = [source for key, op, value in walk(after_limit(body)) if key == 'set_temp_variable'
                   for variable, operator, source in value if variable == 'global.nuke_striker']
        if assigns[0] == 'ROOT':
            runtime.root, runtime.origin = 'USA', 'GER'
        runtime.execute(after_limit(body), [runtime.root])
        assert runtime.countries['USA']['stock'][SHORT] == 0
        assert runtime.countries['USA']['threat'] == 100
        assert runtime.countries['GER']['damage'] == 1
        default_off_cases += 1
    for name in LAUNCHES:
        request = 10 if name == STRATEGIC else 1
        runtime = Runtime(short=request, ready=False)
        runtime.helpers = helpers
        runtime.countries['USA']['flags'].add('eon_nuclear_arsenal_safety_mode')
        runtime.countries['USA']['vars']['eon_nuclear_arsenal_recovery_remaining'] = 4
        runtime.execute(helpers[name], ['GER'])
        assert runtime.countries['USA']['stock'][SHORT] == 0
        assert SUCCESS in runtime.countries['GER']['flags']
        assert runtime.countries['GER']['damage'] == 1
        default_off_cases += 1
    daily_cases = exercise_daily_queue(actions, helpers)
    print(json.dumps({'status': 'PASS', 'actual_source_outcome_cases': cases,
                      'missing_guard_mutants_detected': mutants, 'paid_attempt_markers': markers,
                      'independent_hit_frames': frames, 'paid_target_guarded_reports': events,
                      'actual_daily_queue_order_cases': daily_cases, 'daily_unpaid_report_mutant_detected': True,
                      'default_off_stale_actual_caller_cases': default_off_cases,
                      'scope': 'Actual caller and daily-queue AST, country order, outcome binding and source payment; target/hit/removal/callback fixtures, no native strike'}, indent=2))


if __name__ == '__main__':
    run()
