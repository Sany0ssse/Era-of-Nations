"""Representative-country embassy regressions using the current source AST.

The eligible fixture inputs are explicit. This is source execution, not native
HOI4 AI, user interface, save/load or multiplayer acceptance.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
ADAPTER = ROOT / 'tools/validation/diplomacy_package_26/test_relations.py'
spec = importlib.util.spec_from_file_location('universal_relations_adapter', ADAPTER)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
COUNTRIES = ('USA', 'GER', 'UKR', 'BRA', 'SWI', 'NEP')
for country in COUNTRIES:
    m.IDS.setdefault(country, len(m.IDS) + 1)
P = m.P


def cycle(state, actor, peer='F'):
    operations = (('propose', actor, peer), ('accept_relations', peer, actor),
        ('mission_ambassador', actor, peer), ('accept_ambassador', peer, actor),
        ('propose_head', actor, peer), ('accept_head', peer, actor),
        ('credentials', actor, peer))
    return [m.decision(state, name, owner, partner) for name, owner, partner in operations]


class RelationsTests(unittest.TestCase):
    def test_six_countries_complete_directed_embassies(self):
        for country in COUNTRIES:
            with self.subTest(country=country):
                state = m.state()
                third_country = deepcopy(state['countries']['G'])
                self.assertEqual(cycle(state, country), [True] * 7)
                self.assertEqual(m.var(state, 'mission_level', country, 'F'), 2)
                self.assertEqual(m.var(state, 'mission_level', 'F', country), 0)
                self.assertEqual(m.var(state, 'active_head', country, 'F'), 1)
                self.assertTrue(m.flag(state, 'established', country, 'F'))
                self.assertTrue(m.flag(state, 'established', 'F', country))
                self.assertEqual(state['countries'][country]['variables']['treasury'], 4.98)
                self.assertEqual(state['countries'][country]['pp'], 90)
                self.assertEqual(state['countries']['F']['variables']['treasury'], 5)
                self.assertEqual(state['countries']['G'], third_country)
                self.assertEqual(cycle(state, 'F', country), [False, False, True, True, True, True, True])
                self.assertEqual(m.var(state, 'mission_level', country, 'F'), 2)
                self.assertEqual(m.var(state, 'mission_level', 'F', country), 2)

    def test_guards_apply_to_each_representative_country(self):
        for country in COUNTRIES:
            for reason in ('funds', 'political_power', 'war'):
                with self.subTest(country=country, reason=reason):
                    state = m.state()
                    if reason == 'funds': state['countries'][country]['variables']['treasury'] = 0.01
                    elif reason == 'political_power': state['countries'][country]['pp'] = 9
                    else:
                        state['countries'][country]['wars'].add('F')
                        state['countries']['F']['wars'].add(country)
                    before = m.stable(state)
                    self.assertFalse(m.decision(state, 'mission_ambassador', country, 'F'))
                    m.decision(state, 'mission_ambassador', country, 'F', force=True)
                    self.assertEqual(m.stable(state), before)

    def test_native_temporary_scope_and_durable_round_trip(self):
        state = m.state()
        context = m.ctx('USA', 'BRA')
        nodes = m.parse('set_temp_variable = { sample = 42 } FROM = { set_variable = { unscoped = sample } set_variable = { scoped = PREV.sample } set_temp_variable = { sample = 43 } }')
        m.execute(nodes, state, context)
        self.assertEqual(state['countries']['BRA']['variables']['unscoped'], 42)
        self.assertEqual(state['countries']['BRA']['variables']['scoped'], 0)
        self.assertEqual(m.value(state, context, 'sample'), 43)
        state['countries']['USA']['variables']['sample'] = 8
        nested = m.switch(context, 'BRA')
        self.assertEqual(m.value(state, nested, 'PREV.sample'), 8)
        self.assertEqual(m.value(state, nested, 'sample'), 43)
        durable = m.rehydrate(state)
        self.assertEqual(durable['execution_temps'], {})
        self.assertEqual(m.value(durable, context, 'sample'), 8)

    def test_old_dispatch_scoped_temporary_mutant_is_rejected(self):
        identity = P + 'dispatch'
        original = m.EFFECTS[identity]
        mutant = deepcopy(original)
        partner = m.one(mutant, 'PREV')
        for node_index, (command, operator, data) in enumerate(partner):
            if command != 'set_variable': continue
            field, comparison, value = data[0]
            if field in {P + 'in_' + name + '@PREV' for name in ('kind', 'level', 'head')}:
                data[0] = (field, comparison, 'PREV.' + value)
        try:
            m.EFFECTS[identity] = mutant
            for country in COUNTRIES:
                with self.subTest(country=country):
                    state = m.state()
                    self.assertTrue(m.decision(state, 'propose', country, 'F'))
                    self.assertEqual(m.var(state, 'out_kind', country, 'F'), 1)
                    self.assertEqual(m.var(state, 'in_kind', 'F', country), 0)
                    self.assertFalse(m.decision(state, 'accept_relations', 'F', country))
        finally: m.EFFECTS[identity] = original

    def test_iran_us_national_policy_remains_pair_specific(self):
        for party in (8, 9):
            for actor, partner in (('PER', 'USA'), ('USA', 'PER')):
                state = m.state()
                state['countries']['PER']['arrays']['ruling_party'] = [party]
                self.assertFalse(m.decision(state, 'propose', actor, partner))
            state = m.state()
            state['countries']['PER']['arrays']['ruling_party'] = [party]
            self.assertTrue(m.decision(state, 'propose', 'PER', 'BRA'))
            self.assertTrue(m.decision(state, 'propose', 'BRA', 'USA'))
        state = m.state()
        state['countries']['PER']['arrays']['ruling_party'] = [5]
        self.assertEqual(cycle(state, 'PER', 'USA'), [True] * 7)

    def test_actual_source_has_no_scoped_temp_reads(self):
        paths = [*m.FILES[:4], ADAPTER.relative_to(ROOT).as_posix()]
        sources = [(ROOT / path).read_text(encoding='utf-8-sig') for path in paths[:4]]
        text = '\n'.join(sources)
        names = set(re.findall(r'\bset_temp_variable\s*=\s*\{\s*(\w+)\s*=', text))
        self.assertTrue(names)
        pattern = r'\b(?:PREV|ROOT|FROM|THIS)\.(?:' + '|'.join(map(re.escape, sorted(names))) + r')\b'
        self.assertIsNone(re.search(pattern, text))
        self.assertEqual(m.one(m.DECISIONS[P + 'mission_ambassador'], 'allowed'), [('always', '=', 'yes')])
        for path in m.FILES[:2]:
            blob = (ROOT / path).read_bytes()
            self.assertEqual(blob.count(b'\n'), blob.count(b'\r\n'))


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RelationsTests))
    print(json.dumps({'all_passed': result.wasSuccessful(), 'tests': result.testsRun,
        'representative_countries': list(COUNTRIES), 'scope': 'current source AST; supplied eligible states',
        'old_scoped_temp_dispatch_rejected_for_countries': len(COUNTRIES),
        'native_runtime': False, 'multiplayer': False,
        'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in [*m.FILES[:2], ADAPTER.relative_to(ROOT).as_posix()]}}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
