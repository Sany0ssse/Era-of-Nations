"""Execute whole current annex callbacks with all three agreement families."""
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path
import hashlib
import io
import json
import runpy
import sys

ROOT = Path(__file__).resolve().parents[3]
first = Path(__file__).parent.parent / 'diplomacy_package_01'
sys.path.insert(0, str(first))
with redirect_stdout(io.StringIO()):
    model = runpy.run_path(str(first / 'test_energy.py'))

execute, context = model['execute'], model['context']
ast, one = model['ast'], model['one']
hooks = one(ast((ROOT / 'common/on_actions/00_costili.txt').read_text(encoding='utf-8-sig')), 'on_actions')
cases = []

for name in ('on_annex', 'on_subject_annexed'):
    block = next(v for k, op, v in hooks if k == name and 'eon_energy_clear_pair_pending' in str(v))
    s = model['state'](); countries = s['countries']
    model['framework'](s, 'A', 'B'); model['pair'](s, 'A', 'B', -4, 0.1)
    model['framework'](s, 'C', 'D'); model['pair'](s, 'C', 'D', -2, 0.2)
    model['propose'](s, 'A', 'B', -8, 0.15)

    for a, b in (('A', 'B'), ('A', 'C'), ('B', 'D')):
        for owner, partner in ((a, b), (b, a)):
            countries[owner]['flags'].add('trade_agreement@' + partner)
            variables = countries[owner]['variables']
            variables['signed_trade_agreements'] = variables.get('signed_trade_agreements', 0) + 1
    countries['A']['variables']['pending_trade_offer_country'] = 'B'
    countries['B']['variables']['eon_trade_treaty_pending_sender'] = 'A'
    countries['D']['variables']['pending_trade_offer_country'] = 'C'
    countries['C']['variables']['eon_trade_treaty_pending_sender'] = 'D'

    for a, b in (('A', 'B'), ('B', 'C')):
        for owner, partner in ((a, b), (b, a)):
            countries[owner]['flags'].add('mutual_investment_treaty_@' + partner)
            countries[owner]['arrays'].setdefault('permanent_investment_targets', []).extend([partner, partner])
    countries['A']['variables'].update(pending_mutual_investment_treaty_offer='B', eon_investment_treaty_pending_terms=1)
    countries['B']['variables'].update(eon_investment_treaty_pending_sender='A', eon_investment_treaty_pending_terms=1)
    countries['C']['variables'].update(pending_mutual_investment_treaty_offer='D', eon_investment_treaty_pending_terms=1)
    countries['D']['variables'].update(eon_investment_treaty_pending_sender='C', eon_investment_treaty_pending_terms=1)

    for donor, recipient in (('A', 'B'), ('C', 'A'), ('D', 'B')):
        countries[donor]['variables'].update(eon_investment_offer_partner=recipient, eon_investment_offer_cost=20)
        countries[donor]['flags'].add('this_investment_offer_pending@' + recipient)
    project_records = {}
    for owner, country in countries.items():
        country['arrays']['project_array'] = [-101, 0, 0]
        country['variables'].update(active_projects=1, int_investments=12, treasury=50,
                                    **{'project_building_type^0': 1, 'project_monetary_cost^0': 12,
                                       'project_target_country^0': 'B', 'eon_project_cofinancer^0': 'B'})
        project_records[owner] = (deepcopy(country['arrays']['project_array']), {
            k: v for k, v in country['variables'].items()
            if k in ('active_projects', 'int_investments', 'treasury') or '^0' in k})
    third_energy = {owner: deepcopy(countries[owner]['arrays']['energy_contractors']) for owner in ('C', 'D')}
    countries['A']['exists'] = False
    ctx = context('D', 'A') if name == 'on_annex' else context('A', 'D')
    s['temp'] = {}; execute(one(block, 'effect'), s, ctx)

    assert countries['A']['arrays']['energy_contractors'] == []
    assert countries['B']['arrays']['energy_contractors'] == []
    for owner in ('C', 'D'):
        assert countries[owner]['arrays']['energy_contractors'] == third_energy[owner]
    assert not model['locked'](s, 'A') and not model['locked'](s, 'B')
    assert all('trade_agreement@A' not in data['flags'] for data in countries.values())
    assert not any(flag.startswith('trade_agreement@') for flag in countries['A']['flags'])
    assert countries['A']['variables']['signed_trade_agreements'] == 0
    assert countries['B']['variables']['signed_trade_agreements'] == 1
    assert countries['C']['variables']['signed_trade_agreements'] == 0
    assert countries['D']['variables']['signed_trade_agreements'] == 1
    assert countries['D']['variables']['pending_trade_offer_country'] == 'C'
    assert countries['C']['variables']['eon_trade_treaty_pending_sender'] == 'D'
    assert 'eon_trade_treaty_pending_sender' not in countries['B']['variables']
    assert 'mutual_investment_treaty_@A' not in countries['B']['flags']
    assert 'mutual_investment_treaty_@B' not in countries['A']['flags']
    assert countries['A']['arrays']['permanent_investment_targets'] == []
    assert countries['B']['arrays']['permanent_investment_targets'] == ['C', 'C']
    assert countries['C']['arrays']['permanent_investment_targets'] == ['B', 'B']
    assert countries['C']['variables']['pending_mutual_investment_treaty_offer'] == 'D'
    assert countries['D']['variables']['eon_investment_treaty_pending_sender'] == 'C'
    assert 'eon_investment_treaty_pending_sender' not in countries['B']['variables']
    assert 'eon_investment_offer_partner' not in countries['A']['variables']
    assert 'eon_investment_offer_partner' not in countries['C']['variables']
    assert countries['D']['variables']['eon_investment_offer_partner'] == 'B'
    assert 'this_investment_offer_pending@B' in countries['D']['flags']
    for owner, data in countries.items():
        assert (data['arrays']['project_array'], {
            k: v for k, v in data['variables'].items()
            if k in ('active_projects', 'int_investments', 'treasury') or '^0' in k}) == project_records[owner]

    after = deepcopy(countries)
    s['temp'] = {}; execute(one(block, 'effect'), s, ctx)
    assert countries == after, 'Repeated annex must not alter counters or unrelated records'
    countries['A']['exists'] = True
    assert not any(flag.startswith(('trade_agreement@', 'mutual_investment_treaty_@',
                                    'this_investment_offer_pending@')) for flag in countries['A']['flags'])
    cases.append(name + ': simultaneous cleanup, unrelated pairs, repeated hook and released tag')

print(json.dumps({'cases_passed': len(cases), 'cases': cases,
                  'proof_scope': 'whole actual annex AST and current helpers, shared temporary variables; bounded source model',
                  'limits': 'opinion/GUI rendering and active construction execution are outside this integration model',
                  'on_actions_sha256': hashlib.sha256((ROOT / 'common/on_actions/00_costili.txt').read_bytes()).hexdigest()}, indent=2))
