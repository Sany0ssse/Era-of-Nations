"""CURRENT-AST monthly equivalence and strict byte-boundary proof.

This is source-model evidence, not native order, timing, or campaign acceptance.
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import base64
import hashlib
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools/validation/migration_relief'))
from test_flows import Model, Country, State, ast, one
ARRAY = 'global.eon_migration_treaty_dead_cache'
READY = 'eon_migration_treaty_dead_cache_ready'
BREAKER = 'eon_migration_treaty_dead_cache_break'
TREATY = 'common/scripted_effects/eon_migration_treaty_effects.txt'
RELIEF = 'common/scripted_effects/eon_migration_relief_effects.txt'
def sha(raw): return hashlib.sha256(raw).hexdigest()

MANIFEST = json.loads((HERE / 'canonical_migration_monthly.json').read_text(encoding='utf-8'))

def before_island(row):
    raw = (HERE / row['baseline_fixture']).read_bytes()
    assert sha(raw) == row['before_island_sha256'], 'Historical fixture changed'
    return raw

def load(lane, path):
    assert lane in ('baseline', 'candidate')
    # Candidate always executes ACTUAL installed source. Only historical
    # baseline helper bodies come from small immutable before-island fixtures.
    row = next(f for f in MANIFEST['files'] if f['path'] == path)
    raw = (ROOT / path).read_bytes()
    assert sha(raw) == row['after_sha256'], 'Current source differs from reviewed candidate'
    helpers = {k: v for k, op, v in ast(raw.decode('utf-8-sig'))}
    if lane == 'baseline':
        helpers[row['helper']] = ast(before_island(row).decode('utf-8-sig'))[0][2]
    return helpers

def restore(path, raw):
    row = next(f for f in MANIFEST['files'] if f['path'] == path)
    before, after = before_island(row), base64.b64decode(row['after_island_b64'])
    assert raw.count(after) == 1, 'Missing/duplicated reviewed island'
    result = raw.replace(after, before, 1)
    assert sha(result) == row['before_sha256'], 'Unreviewed source bytes'
    return result

class Monthly(Model):
    def __init__(self, countries=None, states=None, root=1, lane='baseline', order=None):
        self.visits = Counter()
        self.native_order = order or list(countries or range(1, 5))
        self.helper_stack = []
        self.semantic_ops = []
        self.flow_receipts = []
        super().__init__(countries=countries, states=states, root=root)
        self.effects.update(load(lane, RELIEF))
        self.effects.update(load(lane, TREATY))
        self.triggers.update({k: v for k, op, v in ast((ROOT / 'common/scripted_triggers/eon_migration_treaty_triggers.txt').read_text(encoding='utf-8-sig'))})
        for country in self.countries.values():
            country.opinions = set()
            country.ai = False
        self.trace.clear(); self.semantic_ops.clear(); self.visits.clear()

    def run(self, effect, actor=1):
        # Constructor registers countries, including identifiers overlapping
        # state IDs in a large-world cost fixture. Ledger effects are STATE.
        is_state = effect in ('eon_migration_prepare_state_ledger', 'eon_migration_recount_state',
                              'eon_migration_process_refugee_cohorts')
        target = self.states[actor] if is_state else self.countries[actor]
        self.effect([(effect, '=', 'yes')], [target])

    def trigger(self, nodes, stack):
        for node in nodes:
            key, op, value = node
            if key == 'is_ai':
                assert isinstance(stack[-1], Country)
                passed = getattr(stack[-1], 'ai', False) == (value == 'yes')
            elif key == 'any_neighbor_country':
                assert isinstance(stack[-1], Country)
                passed = any(self.trigger(value, stack + [self.countries[i]]) for i in stack[-1].neighbors)
            else:
                # Delegate the entire original sequence, so conditional trigger
                # if/else adjacency is never split or silently normalized.
                if key == 'if': return super().trigger(nodes, stack)
                passed = super().trigger([node], stack)
            if not passed: return False
        return True

    def effect(self, nodes, stack):
        index = 0
        while index < len(nodes):
            key, op, value = nodes[index]
            current = stack[-1]
            if key in self.effects:
                assert value == 'yes'
                flow = None
                if key == 'eon_migration_move_population':
                    flow = tuple(self.global_vars.get(k, 0) for k in ('eon_migration_kind', 'eon_migration_source_state', 'eon_migration_target_state'))
                self.trace.append((current.kind, current.ident, key))
                self.helper_stack.append(key)
                self.effect(self.effects[key], stack)
                self.helper_stack.pop()
                if flow is not None:
                    self.flow_receipts.append(flow + (self.temp['eon_migration_moved_people'],))
            elif key in ('every_country', 'every_possible_country'):
                selected = [self.countries[i] for i in self.native_order]
                if key == 'every_country': selected = [c for c in selected if c.exists]
                limit = next((v for k, o, v in value if k == 'limit'), [])
                for target in selected:
                    self.visits[(key, self.helper_stack[-1] if self.helper_stack else 'outside')] += 1
                    if self.trigger(limit, stack + [target]):
                        self.effect([n for n in value if n[0] != 'limit'], stack + [target])
            elif key == 'for_each_scope_loop':
                assert one(value, 'array') == ARRAY
                breaker = one(value, 'break')
                assert breaker == BREAKER
                assert {k for k, o, v in value} == {'array', 'break', 'if'}
                for pointer in list(self.global_arrays.get(ARRAY[7:], [])):
                    if self.temp.get(breaker, 0) != 0: break
                    matches = [c for c in self.countries.values() if c.pointer == pointer]
                    assert len(matches) == 1, ('Unknown or ambiguous country token', pointer)
                    self.visits[(key, self.helper_stack[-1])] += 1
                    self.effect([n for n in value if n[0] not in ('array', 'break')], stack + [matches[0]])
            elif key == 'clear_array':
                assert value == ARRAY
                self.global_arrays[ARRAY[7:]] = []
            elif key == 'remove_opinion_modifier':
                target = self.scope(one(value, 'target'), stack)
                assert isinstance(target, Country)
                self.semantic_ops.append((key, self.context(stack), target.ident, one(value, 'modifier')))
                current.opinions.discard((target.ident, one(value, 'modifier')))
            elif key == 'remove_dynamic_modifier':
                modifier = one(value, 'modifier') if isinstance(value, list) else value
                assert modifier in ('migrants_agreement_add', 'migrants_agreement_cut')
                self.semantic_ops.append((key, self.context(stack), modifier))
                current.modifiers.discard(modifier)
            else:
                end = index + 1
                if key == 'if':
                    while end < len(nodes) and nodes[end][0] in ('else', 'else_if'): end += 1
                if key not in ('if', 'ROOT', 'THIS', 'PREV', 'owner', 'controller') and not key.startswith('var:'):
                    owned = key in ('set_global_flag', 'clr_global_flag') and value == READY
                    owned |= key == 'add_to_array' and isinstance(value, list) and one(value, 'array') == ARRAY
                    if key == 'set_temp_variable' and any(n[0] == BREAKER for n in value):
                        owned |= one(value, BREAKER) == '0'
                    if not owned:
                        self.semantic_ops.append((key, self.context(stack), deepcopy(value)))
                super().effect(nodes[index:end], stack)
                index = end
                continue
            index += 1

    def context(self, stack):
        return (self.root.ident, tuple((s.kind, s.ident) for s in stack))

    def persistent(self):
        assert READY not in self.global_flags
        assert not self.global_arrays.get(ARRAY[7:], [])
        values = deepcopy((self.countries, self.states, self.global_vars, self.global_arrays,
                           self.global_flags, self.flag_days, self.manpower_calls))
        values[3].pop(ARRAY[7:], None)
        return values

    def observed_temp(self):
        return {k: v for k, v in self.temp.items() if k != BREAKER}

def fixture(case='empty', lane='baseline', total=8, live=5, reverse=False, root=1):
    countries = {i: Country(i, exists=i <= live) for i in range(1, total + 1)}
    states = {100+i: State(100+i, 100000, i, i, {i}) for i in range(1, min(live, 5)+1)}
    order = list(reversed(countries)) if reverse else list(countries)
    m = Monthly(countries, states, root=root, lane=lane, order=order)
    for c in countries.values():
        c.variables.update(treasury=10, display_income=2, display_expense=1,
                           average_worker_fulfillment=.7, migrants_add=.4, migrants_cut=-.3,
                           eon_refugee_relief_fund=.3, eon_refugee_weekly_fund_paid=.01)
        c.modifiers.update(('migrants_agreement_add', 'migrants_agreement_cut'))
        c.flags.add('eon_refugee_fund_week_consumed')
        c.opinions.add((3, 'unrelated'))
    if case in ('reciprocal', 'labour', 'mixed'):
        importer, exporter = (3, 4) if case == 'mixed' else (1, 2)
        countries[importer].flags.add(f'migration_agreement_migrants_add@{exporter}')
        countries[exporter].flags.add(f'migration_agreement_migrants_cut@{importer}')
    if case in ('dead_flags', 'mixed', 'two_dead', 'hostile_break', 'one_sided_live'):
        countries[1].flags.update(('migration_agreement_migrants_add@6', 'migration_agreement_cooldown@6'))
        countries[1].opinions.add((6, 'migration_agreement_opinion'))
    if case in ('dead_flags', 'mixed', 'two_dead'):
        countries[6].flags.add('migration_agreement_migrants_cut@1')
        countries[6].opinions.add((1, 'migration_agreement_opinion'))
    if case in ('queued_dead', 'mixed', 'two_dead'):
        countries[1].variables.update(pending_migration_agreement_country=countries[6].pointer,
                                     eon_migration_treaty_pending_sender=countries[3].pointer,
                                     eon_migration_treaty_pending_terms=1)
        countries[6].variables.update(pending_migration_agreement_country=countries[1].pointer,
                                     eon_migration_treaty_pending_terms=1)
    if case == 'two_dead':
        countries[1].flags.add('migration_agreement_migrants_cut@7')
        countries[7].flags.add('migration_agreement_migrants_add@1')
        countries[1].variables['pending_migration_agreement_country'] = countries[7].pointer
    if case in ('return', 'longterm', 'dead_origin'):
        m.ledger(102, 1, 10000, fresh=1000, age=60 if case == 'longterm' else 3)
        if case == 'dead_origin': countries[1].exists = False
    if case in ('displacement', 'closed', 'onward', 'mixed', 'ai_policy'):
        countries[1].at_war = True
        countries[1].wars = {5}; countries[5].wars = {1}; countries[5].at_war = True
        countries[1].neighbors = {2, 3}; countries[2].neighbors = {1, 3}; countries[3].neighbors = {1, 2}
        states[101].variables['damaged_building_level@infrastructure'] = .6
        if case in ('onward', 'mixed'):
            m.ledger(102, 1, 50000, fresh=1000, age=4)
            countries[3].variables['eon_refugee_policy'] = 2
        if case == 'closed': countries[2].ideas.add('closed_borders'); countries[3].ideas.add('closed_borders')
        if case == 'ai_policy': countries[2].ai = True
    if case == 'one_sided_live': countries[2].flags.add('migration_agreement_migrants_cut@3')
    if case == 'hostile_break': m.temp.update({'break': 1, 'unrelated_break': 9, BREAKER: 1})
    m.trace.clear(); m.semantic_ops.clear(); m.visits.clear(); m.manpower_calls.clear()
    return m

def execute(m, pulse=False):
    m.run('eon_migration_monthly_pulse' if pulse else 'eon_migration_monthly_world_update', m.root.ident)
    return m

class Proof(unittest.TestCase):
    def equal(self, a, b):
        self.assertEqual(a.persistent(), b.persistent())
        self.assertEqual(a.trace, b.trace, 'Ordered actual helper dispatch changed')
        self.assertEqual(a.semantic_ops, b.semantic_ops, 'Ordered effects/ROOT/PREV changed')
        self.assertEqual(a.observed_temp(), b.observed_temp())
        self.assertEqual(a.flow_receipts, b.flow_receipts)

    def test_01_exact_source_inverse_and_unchanged_bindings(self):
        for row in MANIFEST['files']:
            new = (ROOT / row['path']).read_bytes()
            self.assertEqual(sha(new), row['after_sha256'])
            restored = restore(row['path'], new)
            self.assertEqual(sha(restored), row['before_sha256'])
            self.assertEqual(restored.startswith(b'\xef\xbb\xbf'), new.startswith(b'\xef\xbb\xbf'))
            self.assertEqual(new.count(b'\n') == new.count(b'\r\n'), restored.count(b'\n') == restored.count(b'\r\n'))
        for path, expected in MANIFEST['unchanged_bindings'].items():
            self.assertEqual(sha((ROOT / path).read_bytes()), expected)

    def test_02_full_month_actual_ast_state_effect_order_and_root_permutations(self):
        for case in ('empty', 'reciprocal', 'labour', 'dead_flags', 'queued_dead', 'two_dead',
                     'one_sided_live', 'return', 'longterm', 'dead_origin', 'displacement',
                     'closed', 'onward', 'mixed', 'ai_policy', 'hostile_break'):
            for reverse, root in ((False, 1), (True, 3)):
                for random_branch in (0, 1):
                    with self.subTest(case=case, reverse=reverse, root=root, weighted_branch=random_branch):
                        a, b = fixture(case, reverse=reverse, root=root), fixture(case, 'candidate', reverse=reverse, root=root)
                        a.random_branch = b.random_branch = random_branch
                        execute(a); execute(b)
                        self.equal(a, b)
                        self.assertEqual(sum(s.population for s in a.states.values()), 500000)
                        self.assertEqual({c.ident: c.variables['treasury'] for c in a.countries.values()}, {i: 10 for i in range(1, 9)})

    def test_03_fixture_really_exercises_all_population_kinds_and_finance(self):
        for case, counter, kind in [('return', 'eon_refugee_month_returned', 2), ('displacement', 'eon_refugee_month_arrived', 1), ('onward', 'eon_refugee_month_arrived', 3), ('labour', 'eon_labor_month_arrived', 4)]:
            with self.subTest(case=case):
                m = execute(fixture(case, 'candidate'))
                self.assertTrue(m.manpower_calls)
                self.assertGreater(sum(c.variables.get(counter, 0) for c in m.countries.values()), 0)
                self.assertTrue(any(r[0] == kind and r[3] > 0 for r in m.flow_receipts))
        a, b = execute(fixture('return')), execute(fixture('return', 'candidate'))
        for m in (a, b):
            # Model the next weekly lock expiry; no source release is added.
            m.countries[2].flags.discard('eon_refugee_fund_week_consumed')
            m.run('eon_migration_relief_weekly', 2)
        self.equal(a, b)
        self.assertLess(b.countries[2].variables['eon_refugee_relief_fund'], .3)

    def test_04_fresh_month_rebuild_fallback_newly_dead_and_once_lock(self):
        a, b = execute(fixture('mixed'), True), execute(fixture('mixed', 'candidate'), True)
        self.equal(a, b)
        # Pulse reentry consumes nothing twice; untouched timer remains exact.
        av, bv = deepcopy(a.persistent()), deepcopy(b.persistent())
        execute(a, True); execute(b, True)
        self.assertEqual(a.persistent(), av); self.assertEqual(b.persistent(), bv)
        # Between months a previously live queued peer disappears. The ordinary
        # helper must use the original scan, not a stale empty snapshot.
        for m in (a, b):
            m.countries[3].exists = False
            m.countries[1].variables['pending_migration_agreement_country'] = m.countries[3].pointer
            m.trace.clear(); m.semantic_ops.clear(); m.visits.clear()
            m.run('eon_migration_treaty_reconcile_country', 1)
        self.equal(a, b)
        self.assertEqual(a.visits, b.visits)
        for m in (a, b): m.global_flags.discard('eon_migration_month_consumed'); m.trace.clear(); m.semantic_ops.clear()
        execute(a, True); execute(b, True); self.equal(a, b)

    def test_05_actual_full_month_budget_baseline_red_candidate_green(self):
        a = execute(fixture(total=200, live=180))
        b = execute(fixture(lane='candidate', total=200, live=180))
        self.equal(a, b)
        old = a.visits[('every_possible_country', 'eon_migration_treaty_cleanup_dead_partners')]
        prep = b.visits[('every_possible_country', 'eon_migration_monthly_world_update')]
        new = b.visits[('for_each_scope_loop', 'eon_migration_treaty_cleanup_dead_partners')]
        self.assertEqual((old, prep, new), (36000, 200, 3600))
        with self.assertRaises(AssertionError): assert old <= 3800
        self.assertLessEqual(prep + new, 3800)
        self.assertEqual(a.visits[('every_country', 'eon_migration_treaty_refresh_counters')], 32400)
        self.assertEqual(a.visits[('every_country', 'eon_migration_treaty_refresh_counters')], b.visits[('every_country', 'eon_migration_treaty_refresh_counters')])

    def test_06_unreviewed_missing_duplicate_adjacent_and_business_source_negative(self):
        for row in MANIFEST['files']:
            path = row['path']; raw = (ROOT / path).read_bytes()
            island = base64.b64decode(row['after_island_b64'])
            mutations = [raw.replace(island, b'', 1), raw + island, raw + b'# unrelated change\n',
                         b'# unrelated prefix\n' + raw, raw.replace(b' = 0', b' = 2', 1),
                         raw.replace(b'PREV', b'ROOT', 1)]
            for mutant in mutations:
                with self.assertRaises(AssertionError): restore(path, mutant)

    def test_07_queue_guard_snapshot_order_and_cleanup_negatives(self):
        truth = execute(fixture('queued_dead'))
        mutant = fixture('queued_dead', 'candidate')
        cleanup = mutant.effects['eon_migration_treaty_cleanup_dead_partners']
        loop = one(cleanup[0][2], 'for_each_scope_loop')
        limit = one(one(loop, 'if'), 'limit')
        # Drop both queued-partner checks, retaining all flag checks.
        prev_or = one(one(one(limit, 'OR'), 'PREV'), 'OR')
        prev_or[:] = [n for n in prev_or if n[0] != 'check_variable']
        execute(mutant)
        self.assertNotEqual(truth.persistent(), mutant.persistent())
        truth = execute(fixture('two_dead'))
        mutant = fixture('two_dead', 'candidate')
        original = mutant.effect
        def corrupt(nodes, stack):
            if any(k == 'for_each_scope_loop' for k, o, v in nodes):
                mutant.global_arrays[ARRAY[7:]] = list(reversed(mutant.global_arrays[ARRAY[7:]]))
            original(nodes, stack)
        mutant.effect = corrupt
        execute(mutant)
        self.assertNotEqual(truth.trace, mutant.trace)
        # Skipping final scratch cleanup must fail persistent proof.
        mutant = fixture('empty', 'candidate')
        mutant.effects['eon_migration_monthly_world_update'] = [n for n in mutant.effects['eon_migration_monthly_world_update'] if n != ('clr_global_flag', '=', READY)]
        execute(mutant)
        with self.assertRaises(AssertionError): mutant.persistent()

    def test_08_closed_native_primitive_model_and_existence_invariant(self):
        m = fixture('mixed', 'candidate')
        with self.assertRaises(AssertionError): m.effect(ast('for_each_scope_loop = { array = local_unknown break = b }'), [m.root])
        with self.assertRaises(AssertionError): m.effect(ast('create_country = INVALID'), [m.root])
        # The snapshot is used only in the first country pass. All reachable
        # source commands are pinned; events/existence/owner mutations are
        # forbidden by the actual-AST closure, rather than assumed absent.
        first = next(v for k, o, v in load('baseline', RELIEF)['eon_migration_monthly_world_update'] if k == 'every_country')
        seen, commands = set(), set()
        def walk(nodes):
            for k, o, v in nodes:
                if k in m.effects:
                    if k not in seen: seen.add(k); walk(m.effects[k])
                elif k in m.triggers:
                    if k not in seen: seen.add(k); walk(m.triggers[k])
                else:
                    commands.add(k)
                    if isinstance(v, list): walk(v)
        walk(first)
        dangerous = {'country_event', 'news_event', 'release', 'release_puppet', 'annex_country',
                     'transfer_state', 'create_dynamic_country', 'create_country', 'set_owner',
                     'declare_war_on', 'add_ideas', 'remove_ideas'}
        self.assertFalse(commands & dangerous)
        for helper in ('eon_migration_initialize_country', 'eon_migration_treaty_cleanup_annexed_pair',
                       'eon_migration_refresh_country', 'eon_migration_update_home_safety'):
            self.assertIn(helper, seen)
        modifiers = {k: v for k, o, v in ast((ROOT/'common/dynamic_modifiers/demographics_dynamic_modifiers.txt').read_text(encoding='utf-8-sig'))}
        modifiers.update({k: v for k, o, v in ast((ROOT/'common/dynamic_modifiers/eon_migration_relief_modifiers.txt').read_text(encoding='utf-8-sig'))})
        for name in ('migrants_agreement_add', 'migrants_agreement_cut', 'eon_refugee_reception_modifier'):
            self.assertFalse({k for k, o, v in modifiers[name]} & dangerous)

if __name__ == '__main__': unittest.main(verbosity=2)
