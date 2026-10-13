"""Run actual institutional AST in a narrow model; native HOI4 remains required."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/validation/aid_flag_scope'))
from _model import ast, one, compare


def walk(nodes):
    for key, operator, value in nodes:
        yield key, operator, value
        if isinstance(value, list):
            yield from walk(value)


class Model:
    def __init__(self):
        self.effects = dict((k, v) for k, o, v in ast((ROOT / 'common/scripted_effects/eon_eu_institutions_effects.txt').read_text(encoding='utf-8-sig')))
        self.triggers = dict((k, v) for k, o, v in ast((ROOT / 'common/scripted_triggers/eon_eu_institutions_triggers.txt').read_text(encoding='utf-8-sig')))
        self.g, self.gf, self.ga, self.temp = {}, set(), {'EU_member': []}, {}
        self.tags = {'EUU': 999, 'ITA': 1, 'FRA': 2, 'HOL': 3, 'SPR': 4, 'GER': 5}
        self.c = {i: {'vars': {'population': 100, 'MEP_Total': 100, 'eon_eu_office_nominee_generation': 1},
                      'flags': set(), 'ideas': {'EU_member', 'the_euro'}, 'exists': True, 'ai': True,
                      'coastal': True, 'opinion': 50} for i in range(1, 6)}
        self.c[999] = {'vars': {}, 'flags': set(), 'ideas': set(), 'exists': False, 'ai': True, 'coastal': False, 'opinion': 0}
        self.ga['EU_member'] = list(range(1, 6))
        self.gf.add('eon_eu_active')
        self.events, self.boundaries = [], []

    def val(self, x, stack):
        try: return float(x)
        except (TypeError, ValueError): pass
        if x == 'THIS': return stack[-1]
        if x == 'ROOT': return stack[0]
        if x == 'PREV': return stack[-2]
        if x.startswith('var:'): return self.val(x[4:], stack)
        if x in self.tags: return self.tags[x]
        if x.startswith('global.'):
            x = x[7:]
            if '^' in x:
                a, index = x.split('^', 1); values = self.ga.get(a, [])
                idx = int(self.val(index, stack)); return values[idx] if 0 <= idx < len(values) else 0
            if x.endswith('^num'): return len(self.ga.get(x[:-4], []))
            return self.g.get(x, 0)
        if '.' in x:
            prefix, x = x.split('.', 1)
            return self.val(x, stack + [self.val(prefix, stack)])
        if x in self.temp: return self.temp[x]
        if x == 'id': return stack[-1]
        return self.c[stack[-1]]['vars'].get(x, 0)

    def write(self, x, y, stack):
        if x.startswith('global.'): self.g[x[7:]] = y
        elif '.' in x:
            p, n = x.split('.', 1); self.c[self.val(p, stack)]['vars'][n] = y
        else: self.c[stack[-1]]['vars'][x] = y

    def trigger(self, nodes, stack):
        for key, op, b in nodes:
            country = self.c[stack[-1]]
            if key == 'eon_eu_is_active_member':
                ok = country['exists'] and 'EU_member' in country['ideas'] and stack[-1] in self.ga['EU_member'] and 'eon_eu_active' in self.gf
                ok = ok == (b == 'yes')
            elif key in self.triggers: ok = self.trigger(self.triggers[key], stack) == (b == 'yes')
            elif key in ('AND', 'custom_trigger_tooltip'): ok = self.trigger([n for n in b if n[0] != 'tooltip'], stack)
            elif key == 'OR': ok = any(self.trigger([n], stack) for n in b)
            elif key == 'NOT': ok = not self.trigger(b, stack)
            elif key == 'always': ok = b == 'yes'
            elif key == 'exists': ok = country['exists'] == (b == 'yes')
            elif key == 'is_ai': ok = country['ai'] == (b == 'yes')
            elif key == 'has_idea': ok = b in country['ideas']
            elif key == 'has_country_flag': ok = b in country['flags']
            elif key == 'has_global_flag': ok = b in self.gf
            elif key == 'check_variable':
                if any(n[0] == 'var' for n in b):
                    left, right = one(b, 'var'), one(b, 'value')
                    name = next((n[2] for n in b if n[0] == 'compare'), 'equals')
                    oper = {'equals': '=', 'not_equals': '!=', 'less_than': '<',
                            'less_than_or_equals': '<=', 'greater_than': '>',
                            'greater_than_or_equals': '>='}[name]
                else:
                    left, oper, right = b[0]
                ok = compare(self.val(left, stack), oper, self.val(right, stack))
            elif key == 'is_in_array':
                if b[0][0] == 'array': name, item = one(b, 'array'), one(b, 'value')
                else: name, _, item = b[0]
                ok = self.val(item, stack) in self.ga.get(name.removeprefix('global.'), [])
            elif key == 'any_owned_state': ok = country['coastal'] and self.trigger(b, stack)
            elif key == 'is_coastal': ok = b == 'yes'
            elif key == 'has_opinion':
                target = one(b, 'target')
                assert target in ('THIS', 'ROOT', 'PREV', 'FROM', 'OWNER', 'CONTROLLER', 'OCCUPIED', 'CAPITAL')
                ok = self.val(target, stack) in self.c and compare(country['opinion'], b[-1][1], float(b[-1][2]))
            elif key == 'any_of_scopes':
                arr = one(b, 'array').removeprefix('global.')
                ok = any(self.trigger([n for n in b if n[0] != 'array'], stack + [c]) for c in self.ga.get(arr, []))
            elif key in ('THIS', 'ROOT', 'PREV') or key.startswith('var:') or key in self.tags:
                token = self.val(key, stack); ok = token in self.c and self.trigger(b, stack + [token])
            elif key == 'date': ok = compare(2000.0101, op, float(b.replace('.', '', 1)))
            else: raise AssertionError(('unknown trigger', key, op, b))
            if not ok: return False
        return True

    def effect(self, nodes, stack):
        i = 0
        while i < len(nodes):
            key, op, b = nodes[i]; i += 1
            country = self.c[stack[-1]]
            if key == 'if':
                branches = [('if', b)]
                while i < len(nodes) and nodes[i][0] in ('else_if', 'else'):
                    branches.append((nodes[i][0], nodes[i][2])); i += 1
                for kind, branch in branches:
                    if kind == 'else' or self.trigger(one(branch, 'limit'), stack):
                        self.effect([n for n in branch if n[0] != 'limit'], stack); break
            elif key in self.effects: self.effect(self.effects[key], stack)
            elif key == 'eon_eu_recount_council_vote':
                self.boundaries.append(key)
                for c in self.ga['EU_member']:
                    self.c[c]['vars']['eon_eu_voting_population_k'] = self.c[c]['vars']['population']
            elif key in ('set_temp_variable', 'add_to_temp_variable', 'subtract_from_temp_variable', 'multiply_temp_variable', 'divide_temp_variable'):
                name, _, value = b[0]; amount = self.val(value, stack)
                old = self.val(name, stack)
                self.temp[name] = {'set_temp_variable': lambda: amount, 'add_to_temp_variable': lambda: old + amount,
                    'subtract_from_temp_variable': lambda: old - amount, 'multiply_temp_variable': lambda: old * amount,
                    'divide_temp_variable': lambda: old / amount}[key]()
            elif key in ('set_variable', 'add_to_variable', 'subtract_from_variable', 'multiply_variable', 'divide_variable'):
                name, _, value = b[0]; amount = self.val(value, stack); old = self.val(name, stack)
                self.write(name, {'set_variable': lambda: amount, 'add_to_variable': lambda: old + amount,
                    'subtract_from_variable': lambda: old - amount, 'multiply_variable': lambda: old * amount,
                    'divide_variable': lambda: old / amount}[key](), stack)
            elif key == 'clear_array': self.ga[b.removeprefix('global.')] = []
            elif key == 'add_to_array':
                if b[0][0] == 'array': name, v = one(b, 'array'), one(b, 'value')
                else: name, _, v = b[0]
                self.ga.setdefault(name.removeprefix('global.'), []).append(self.val(v, stack))
            elif key == 'remove_from_array':
                if b[0][0] == 'array': name, v = one(b, 'array'), one(b, 'value')
                else: name, _, v = b[0]
                arr = self.ga.get(name.removeprefix('global.'), []); item = self.val(v, stack)
                if item in arr: arr.remove(item)
            elif key in ('set_global_flag', 'clr_global_flag', 'set_country_flag', 'clr_country_flag'):
                fl = one(b, 'flag') if isinstance(b, list) else b
                flags = self.gf if 'global' in key else country['flags']
                flags.add(fl) if key.startswith('set_') else flags.discard(fl)
            elif key == 'add_timed_idea': country['ideas'].add(one(b, 'idea'))
            elif key == 'remove_ideas':
                if isinstance(b, str): country['ideas'].discard(b)
                else: raise AssertionError('list idea removal not modeled')
            elif key == 'for_each_scope_loop':
                for c in list(self.ga.get(one(b, 'array').removeprefix('global.'), [])):
                    self.effect([n for n in b if n[0] != 'array'], stack + [c])
            elif key == 'every_possible_country':
                for c in sorted(self.c):
                    if self.trigger(one(b, 'limit'), stack + [c]):
                        self.effect([n for n in b if n[0] != 'limit'], stack + [c])
            elif key in ('THIS', 'ROOT', 'PREV') or key.startswith('var:') or key in self.tags:
                token = self.val(key, stack)
                if token in self.c: self.effect(b, stack + [token])
            elif key in ('custom_effect_tooltip', 'log'): pass
            elif key == 'country_event': self.events.append((stack[-1], one(b, 'id')))
            elif key == 'update_eu_dirty_variable': self.boundaries.append(key)
            else: raise AssertionError(('unknown effect', key, op, b))

    def run(self, effect, country=1): self.effect(self.effects[effect], [country])
    def ready(self, country=1, office=1):
        self.temp['eon_eu_office_requested_id'] = office
        return self.trigger(self.triggers['eon_eu_office_nomination_ready'], [country])
    def open(self, country=1, office=1):
        self.temp['eon_eu_office_requested_id'] = office; self.run('eon_eu_open_office_ballot', country)
    def votes(self, yes, no=()):
        for c in yes: self.run('eon_eu_cast_office_yes', c)
        for c in no: self.run('eon_eu_cast_office_no', c)
    def expire(self):
        self.gf.discard('eon_eu_office_ballot_deadline'); self.run('eon_eu_resolve_office_ballot')


class Institutions(unittest.TestCase):
    def test_vacancy_gate_and_nonmembers(self):
        m = Model(); self.assertTrue(m.ready())
        m.c[1]['ideas'].discard('EU_member'); self.assertFalse(m.ready())
        m.c[1]['ideas'].add('EU_member'); m.c[2]['ideas'].add('EU_commission_president'); self.assertFalse(m.ready())

    def test_open_duplicate_and_live_deadline(self):
        m = Model(); m.open(); snapshot = deepcopy((m.g, m.ga, m.gf))
        m.open(2, 2); self.assertEqual(snapshot, (m.g, m.ga, m.gf))
        m.votes([1,2,3,4]); m.run('eon_eu_resolve_office_ballot'); self.assertEqual(m.g['eon_eu_office_phase'], 1)

    def test_commission_two_stage_and_exact_once(self):
        m = Model(); m.open(); m.votes([1,2,3,4]); m.expire()
        self.assertEqual(m.g['eon_eu_office_phase'], 2); self.assertNotIn('EU_commission_president', m.c[1]['ideas'])
        m.votes([1,2,3]); m.expire(); self.assertIn('EU_commission_president', m.c[1]['ideas'])
        snap = deepcopy((m.g, m.ga, m.gf, m.c)); m.expire(); self.assertEqual(snap, (m.g, m.ga, m.gf, m.c))

    def test_parliament_weighted_majority_not_states(self):
        m = Model(); m.c[1]['vars']['MEP_Total'] = 401
        m.open(1, 2); m.votes([1], [2,3,4,5]); m.expire(); self.assertIn('EU_parliament_president', m.c[1]['ideas'])

    def test_exact_ep_half_fails(self):
        m = Model(); m.c[1]['vars']['MEP_Total'] = 400
        m.open(1, 2); m.votes([1], [2,3,4,5]); m.expire(); self.assertNotIn('EU_parliament_president', m.c[1]['ideas'])

    def test_reinforced_qmv_requires_population_even_with_one_opponent(self):
        m = Model(); m.c[5]['vars']['population'] = 900
        m.open(1, 3); m.votes([1,2,3,4], [5]); m.expire()
        self.assertNotIn('ECB_president', m.c[1]['ideas'])

    def test_parliament_chair_majority_valid_votes_excludes_abstentions(self):
        m = Model(); m.open(1, 2); m.votes([1,2], [3]); m.expire()
        self.assertIn('EU_parliament_president', m.c[1]['ideas'])

    def test_commission_confirmation_requires_all_seats_not_cast_votes(self):
        m = Model(); m.open(); m.votes([1,2,3,4]); m.expire()
        m.votes([1,2], [3]); m.expire()
        self.assertNotIn('EU_commission_president', m.c[1]['ideas'])

    def test_new_commission_stage_clears_displayed_prior_choices(self):
        m = Model(); m.open(); m.votes([1,2,3,4]); m.expire()
        self.assertEqual(m.g['eon_eu_office_phase'], 2)
        self.assertEqual(m.g['eon_eu_office_yes'], 0)
        self.assertEqual(m.g['eon_eu_office_ep_yes'], 0)

    def test_closed_ballot_clears_parliament_display(self):
        m = Model(); m.open(1, 2); m.votes([1,2,3]); m.expire()
        self.assertEqual(m.g['eon_eu_office_ep_total'], 0)
        self.assertEqual(m.g['eon_eu_office_ep_yes'], 0)

    def test_ep_rejection_cannot_fall_through_to_council_majority(self):
        m = Model(); m.c[5]['vars']['MEP_Total'] = 500
        m.open(1, 2); m.votes([1,2,3,4], [5]); m.expire()
        self.assertNotIn('EU_parliament_president', m.c[1]['ideas'])

    def test_reject_change_and_abstain_remove_counts(self):
        m = Model(); m.open(1, 2); m.votes([1]); m.votes([], [1]); m.run('eon_eu_cast_office_abstain', 1)
        m.run('eon_eu_recount_office_ballot'); self.assertEqual(m.g['eon_eu_office_yes'], 0); self.assertEqual(m.g['eon_eu_office_no'], 0)

    def test_departed_member_cannot_vote_or_hold(self):
        m = Model(); m.open(1, 2); m.c[1]['ideas'].discard('EU_member'); m.votes([1,2,3,4,5]); m.expire()
        self.assertNotIn('EU_parliament_president', m.c[1]['ideas']); self.assertEqual(m.g['eon_eu_office_id'], 0)

    def test_ecb_only_eurozone_and_nonrenewable_cohort(self):
        m = Model(); m.c[1]['ideas'].discard('the_euro'); self.assertFalse(m.ready(1, 3))
        m.c[1]['ideas'].add('the_euro'); m.c[5]['ideas'].discard('the_euro')
        m.open(1, 3); m.votes([1,2,3], [4]); m.expire(); self.assertIn('ECB_president', m.c[1]['ideas'])
        m.c[1]['ideas'].discard('ECB_president'); self.assertFalse(m.ready(1, 3))
        m.c[1]['vars']['eon_eu_office_nominee_generation'] += 1; self.assertTrue(m.ready(1, 3))

    def test_council_two_terms_same_cohort(self):
        m = Model(); m.gf.add('treaty_of_lisbon')
        for term in (1, 2):
            m.open(1, 4); m.votes([1,2,3,4]); m.expire(); self.assertIn('EU_council_president', m.c[1]['ideas'])
            m.c[1]['ideas'].discard('EU_council_president'); m.gf.discard('eon_eu_office_appointment_cooldown')
            m.c[1]['flags'].discard('eon_eu_office_nomination_cooldown')
        self.assertFalse(m.ready(1, 4))

    def test_frontex_two_thirds_not_unanimity(self):
        m = Model(); m.gf.add('frontex_ExDir'); m.open(1, 6); m.votes([1,2,3,4], [5]); m.expire()
        self.assertIn('frontex_ExDir', m.c[1]['ideas'])

    def test_frontex_exact_two_thirds_passes_without_rounding(self):
        m = Model(); m.ga['EU_member'] = [1,2,3]; m.gf.add('frontex_ExDir')
        m.open(1, 6); m.votes([1,2], [3]); m.expire(); self.assertIn('frontex_ExDir', m.c[1]['ideas'])

    def test_uninitialized_new_ecb_nominee_can_stand(self):
        m = Model(); m.c[1]['vars'].pop('eon_eu_office_nominee_generation')
        self.assertTrue(m.ready(1, 3)); m.open(1, 3)
        self.assertEqual(m.g['eon_eu_office_nominee_generation'], 1)

    def test_reform_slots_remain_locked(self):
        m = Model()
        for office in (4,6,7,8,9,10): self.assertFalse(m.ready(1, office))
        self.assertTrue(m.ready(1, 5))

    def test_close_does_not_fabricate_appointments(self):
        m = Model(); m.open(); m.run('eon_eu_close_institutions')
        self.assertEqual(m.g['eon_eu_office_id'], 0); self.assertFalse(m.ga['eon_eu_office_supporters'])
        self.assertNotIn('eon_eu_office_ballot_deadline', m.gf)

    def test_invalid_old_holder_reconciles(self):
        m = Model(); m.c[1]['ideas'].add('EU_commission_president'); m.c[1]['ideas'].discard('EU_member')
        m.g['eucomission'] = 1; m.run('eon_eu_reconcile_office_holders')
        self.assertEqual(m.g['eucomission'], 999); self.assertNotIn('EU_commission_president', m.c[1]['ideas'])

    def test_rotating_presidency_live_distinct_and_advances(self):
        m = Model(); m.run('eon_eu_rotate_council_presidency'); first = m.g['eon_eu_council_rotating_holder']
        m.gf.discard('eon_eu_council_rotating_term'); m.run('eon_eu_rotate_council_presidency')
        self.assertNotEqual(first, m.g['eon_eu_council_rotating_holder']); self.assertEqual(m.g.get('eucouncil', 999), 999)

    def test_notification_has_no_delayed_vote_callback(self):
        events = ast((ROOT / 'events/eon_eu_institutions_events.txt').read_text(encoding='utf-8-sig'))
        notified = next(v for k, o, v in events if k == 'country_event' and one(v, 'id') == 'eon_eu_institutions.1')
        options = [v for k, o, v in notified if k == 'option']
        self.assertEqual(options, [[('name', '=', 'eon_eu_institutions_ack')]])

    def test_ai_replaces_exhausted_person_not_country(self):
        m = Model(); m.c[1]['vars']['eon_eu_ecb_appointed_generation'] = 1
        m.temp['eon_eu_office_requested_id'] = 3; m.run('eon_eu_ai_select_office_nominee')
        self.assertEqual(m.c[1]['vars']['eon_eu_office_nominee_generation'], 2)
        self.assertEqual(m.g['eon_eu_office_nominee'], 1)

    def test_generation_cannot_change_pending_nominee(self):
        m = Model(); m.c[1]['vars']['eon_eu_ecb_appointed_generation'] = 1
        m.open(1, 2); before = m.c[1]['vars']['eon_eu_office_nominee_generation']
        m.run('eon_eu_refresh_nominee_cohort', 1); self.assertEqual(before, m.c[1]['vars']['eon_eu_office_nominee_generation'])

    def test_new_holder_blocks_late_pending_appointment(self):
        m = Model(); m.open(1, 2); m.votes([1,2,3,4,5])
        m.c[2]['ideas'].add('EU_parliament_president'); m.expire()
        self.assertNotIn('EU_parliament_president', m.c[1]['ideas'])
        self.assertIn('EU_parliament_president', m.c[2]['ideas'])

    def test_ai_campaign_loop_opens_then_resolves_without_gui(self):
        m = Model(); m.gf.add('eon_eu_institutions_initialized')
        m.run('eon_eu_daily_institutions_pulse')
        self.assertEqual(m.g['eon_eu_office_id'], 1)
        m.run('eon_eu_daily_institutions_pulse'); self.assertEqual(m.g['eon_eu_office_yes'], 5)
        m.gf.discard('eon_eu_office_ballot_deadline'); m.run('eon_eu_daily_institutions_pulse')
        self.assertEqual(m.g['eon_eu_office_phase'], 2)
        m.run('eon_eu_daily_institutions_pulse')
        m.gf.discard('eon_eu_office_ballot_deadline'); m.run('eon_eu_daily_institutions_pulse')
        self.assertIn('EU_commission_president', m.c[1]['ideas'])

    def test_occupied_offices_not_removed_when_another_ballot_closes(self):
        m = Model(); m.c[4]['ideas'].add('EU_foreign_minister'); m.g['euforeignaffairs'] = 4
        m.open(1, 2); m.votes([1,2,3,4,5]); m.expire()
        self.assertIn('EU_foreign_minister', m.c[4]['ideas']); self.assertEqual(m.g['euforeignaffairs'], 4)

    def test_full_fractional_country_token_stays_exact(self):
        m = Model(); token = 10180.05432; m.c[token] = m.c.pop(1)
        m.ga['EU_member'][0] = token; m.tags['ITA'] = token
        m.open(token, 2); m.votes([token,2,3,4,5]); m.gf.discard('eon_eu_office_ballot_deadline')
        m.run('eon_eu_resolve_office_ballot', token)
        self.assertEqual(m.g['euparliamentpresident'], token)
        self.assertIn('EU_parliament_president', m.c[token]['ideas'])

    def test_suspended_member_cannot_change_council_choice(self):
        m = Model(); m.open(1, 5); m.c[2]['ideas'].add('EUU_voting_rights_suspended'); m.votes([2])
        self.assertNotIn(2, m.ga['eon_eu_office_supporters'])
        m.run('eon_eu_recount_office_ballot'); self.assertEqual(m.g['eon_eu_office_voters'], 4)

    def test_suspended_member_ep_seats_still_participate(self):
        m = Model(); m.open(1, 2); m.c[2]['ideas'].add('EUU_voting_rights_suspended'); m.votes([2])
        self.assertIn(2, m.ga['eon_eu_office_supporters']); self.assertEqual(m.g['eon_eu_office_ep_yes'], 100)

    def test_council_suspension_preserves_ep_candidate_origin_without_council_vote(self):
        m = Model(); m.c[1]['ideas'].add('EUU_voting_rights_suspended')
        actual = dict((k,v) for k,o,v in ast((ROOT/'common/scripted_triggers/eon_eu_voting_triggers.txt').read_text('utf-8-sig')))
        m.triggers['eon_eu_can_vote'] = actual['eon_eu_can_vote']
        self.assertTrue(m.ready(1,2))
        self.assertFalse(m.trigger(m.triggers['eon_eu_can_vote'],[1]))
        m.gf.update(('treaty_of_lisbon','frontex_ExDir','EU_finance_minister','euro_army','euro_navy','EU_UNSC'))
        for office in (1,3,4,5,6,7,8,9,10): self.assertFalse(m.ready(1,office),office)
        m.open(1,2);m.votes([1,2,3,4,5]);m.expire()
        self.assertIn('EU_parliament_president',m.c[1]['ideas'])
        self.assertFalse(m.trigger(m.triggers['eon_eu_can_vote'],[1]))

    def test_genuine_opposition_prevents_appointment(self):
        m = Model(); m.open(1, 5); m.votes([1,2], [3,4,5]); m.expire()
        self.assertNotIn('EU_foreign_minister', m.c[1]['ideas'])
        self.assertIn('eon_eu_office_nomination_cooldown', m.c[1]['flags'])

    def test_no_voters_no_empty_unanimity(self):
        m = Model(); m.open(1, 5); m.ga['EU_member'] = []; m.expire()
        self.assertNotIn('EU_foreign_minister', m.c[1]['ideas'])
        self.assertEqual(m.g['eon_eu_office_id'], 0)

    def test_native_catalog_ids_and_terms(self):
        m = Model()
        definitions = ast((ROOT / 'common/ideas/EU_ideas.txt').read_text(encoding='utf-8-sig'))
        catalog = {k for k,o,v in one(one(definitions, 'ideas'), 'country')}
        expected = {1: ('EU_commission_president', 1825), 2: ('EU_parliament_president', 913),
                    3: ('ECB_president', 2920), 4: ('EU_council_president', 913),
                    5: ('EU_foreign_minister', 1825), 6: ('frontex_ExDir', 1825),
                    7: ('EU_finance_minister', 1825), 8: ('EUU_euroarmy_sc', 1825),
                    9: ('EUU_euronavy_sc', 1825), 10: ('EUU_ambassador_unsc', 1825)}
        for office, (idea, days) in expected.items():
            award = one(m.effects[f'eon_eu_appoint_office_{office}'], 'add_timed_idea')
            self.assertIn(idea, catalog); self.assertEqual(one(award, 'idea'), idea)
            self.assertEqual(float(one(award, 'days')), days)

    def test_native_check_variable_uses_supported_inclusive_grammar(self):
        for kind, folder in (('effects', 'scripted_effects'), ('triggers', 'scripted_triggers')):
            path = ROOT / 'common' / folder / f'eon_eu_institutions_{kind}.txt'
            for key, operator, value in walk(ast(path.read_text(encoding='utf-8-sig'))):
                if key == 'check_variable':
                    with self.subTest(file=str(path), condition=value):
                        self.assertFalse(any(op in ('>=', '<=') for field, op, target in value),
                                         'Native inclusive comparison requires var/value/compare long form')

    def test_native_opinion_uses_supported_scope_target(self):
        source = ast((ROOT / 'common/scripted_effects/eon_eu_institutions_effects.txt').read_text(encoding='utf-8-sig'))
        targets = [one(value, 'target') for key, operator, value in walk(source) if key == 'has_opinion']
        self.assertTrue(targets)
        self.assertTrue(all(target in ('THIS', 'ROOT', 'PREV', 'FROM', 'OWNER', 'CONTROLLER', 'OCCUPIED', 'CAPITAL')
                            for target in targets), 'Use a supported native scope target after resolving the nominee scope')

    def test_timed_institution_flags_have_explicit_positive_value(self):
        paths = ('common/scripted_effects/eon_eu_institutions_effects.txt',
                 'common/decisions/eon_eu_institutions_decisions.txt',
                 'events/eon_eu_institutions_events.txt')
        timed = []
        for relative in paths:
            for key, operator, value in walk(ast((ROOT / relative).read_text(encoding='utf-8-sig'))):
                if key in ('set_global_flag', 'set_country_flag') and isinstance(value, list):
                    if any(field == 'days' for field, op, target in value):
                        timed.append((relative, value))
                        with self.subTest(file=relative, flag=one(value, 'flag')):
                            declared = [target for field, op, target in value if field == 'value']
                            self.assertEqual(declared, ['1'],
                                             'Timed native flags must explicitly set value=1 before has_flag guards')
        self.assertTrue(timed)

    def test_ai_checks_voter_opinion_toward_a_nonroot_nominee(self):
        m = Model(); m.c[1]['opinion'] = -50; m.c[3]['opinion'] = 50
        m.open(3, 2); m.run('eon_eu_ai_office_voting', country=1)
        self.assertIn(1, m.ga['eon_eu_office_rejecters'])
        self.assertIn(3, m.ga['eon_eu_office_supporters'])

    def test_legacy_ecb_holder_gets_nonrenewable_receipt(self):
        m = Model(); m.c[3]['ideas'].add('ECB_president')
        m.run('eon_eu_initialize_historical_offices')
        self.assertEqual(m.c[3]['vars']['eon_eu_ecb_appointed_generation'], 1)
        m.c[3]['ideas'].discard('ECB_president'); self.assertFalse(m.ready(3, 3))


if __name__ == '__main__': unittest.main(verbosity=2)
