"""Actual-source default repayment core and strict existing-button integration.

--red is a pre-integration historical reproduction and explicitly refuses to
masquerade repaired callbacks as old source. Current acceptance should use
--require-integration; test_lifecycle covers construction, expiry and closure.
"""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import _model as m

ROOT = Path(__file__).resolve().parents[3]
DECISIONS = 'common/decisions/bankruptcy_decisions.txt'
EFFECTS = 'common/scripted_effects/eon_debt_default_accounting_effects.txt'
TRIGGERS = 'common/scripted_triggers/eon_debt_default_accounting_triggers.txt'
BUDGET = 'common/scripted_effects/00_budget_effects.txt'
MONEY = 'common/scripted_effects/00_money_system.txt'
OLD_BODY = '''custom_effect_tooltip = debt_default_pay_AMOUNT_from_treasury_tt
set_temp_variable = { treasury_change = -AMOUNT }
modify_treasury_effect = yes
add_to_variable = { debt_default_left = -AMOUNT }
clamp_variable = { var = debt_default_left min = 0 }
'''


def decisions():
    nodes = m.ast(m.read(DECISIONS))
    return {key: body for key, operator, category in nodes for key, operator, body in category
            if key in ('debt_default_pay_10_from_treasury', 'debt_default_pay_50_from_treasury')}


def old_effect(amount):
    return m.ast(OLD_BODY.replace('AMOUNT', str(amount)))


def historical(effects, current=False):
    result = []
    callbacks = decisions() if current else None
    for amount in (10, 50):
        old = old_effect(amount)
        if current:
            old = m.one(callbacks[f'debt_default_pay_{amount}_from_treasury'], 'complete_effect')
            assert old == old_effect(amount), 'RED command requires unchanged historical callbacks'
        model = m.Model(effects, {}, cash=3, claim=2)
        model.effect(old)
        assert model.variables['treasury'] == 3 - amount
        assert model.variables['debt_default_left'] == 0
        assert model.variables['debt'] == 73
        result.append({'nominal': amount, 'cash_debit': amount, 'actual_claim_reduction': 2,
                       'cash_after': model.variables['treasury'], 'aggregate_unchanged': True})
    return result


def historical_interest_gate(current=False):
    old = m.ast('custom_trigger_tooltip = { tooltip = debt_default_pay_from_treasury_trigger_tooltip check_variable = { interest_rate < 5 } }')
    if current:
        for node in decisions().values():
            assert m.one(node, 'available') == old, 'RED interest probe requires actual unchanged old gate'
    model = m.Model({}, {}, 100, 100, interest=10)
    assert not model.trigger(old)
    return {'funded_cash': 100, 'remaining_claim': 100, 'interest_rate': 10,
            'old_current_available': False, 'new_policy': 'Existing cash repayment is not a new loan'}


def validate(integration=False):
    effects = m.definitions(EFFECTS)
    triggers = m.definitions(TRIGGERS)
    budget = m.definitions(BUDGET)
    effects['modify_treasury_effect'] = budget['modify_treasury_effect']
    old = historical(effects)
    old_interest = historical_interest_gate()
    cases = 0
    tests = ((3, 2), (2, 100), (10, 10), (50, 50), (100, .25), (.25, 100),
             (0, 2), (-3, 2), (3, 0), (3, -2), (0, 0), (1000001, 1000001),
             (.002, .001), (5, 5), (100, 100))
    for nominal, gdp in ((10, 100), (50, 100.001)):
        name = f'eon_debt_default_pay_{nominal}'
        for cash, claim in tests:
            for precision in (None, 3, 5):
                model = m.Model(effects, triggers, cash, claim, gdp=gdp, precision=precision)
                model.effect(effects[name])
                payment = min(nominal, max(cash, 0), max(claim, 0))
                assert abs(model.variables['treasury'] - (cash - payment)) < .003
                assert abs(model.variables['debt_default_left'] - (claim - payment)) < .003
                cash_debit = cash - model.variables['treasury']
                claim_reduction = claim - model.variables['debt_default_left']
                assert abs(cash_debit - claim_reduction) < .00001
                assert model.variables['debt'] == 73
                assert model.variables['debt_default_total'] == 999 and model.variables['debt_bailout'] == 123
                assert model.updates == int(payment > 0)
                assert model.trigger(triggers[name + '_available']) == (cash - payment > 0 and claim - payment > 0)
                cases += 1
        model = m.Model(effects, triggers, 20, .25, gdp=gdp)
        model.effect(effects[name]); model.effect(effects[name])
        assert model.variables['treasury'] == 19.75 and model.variables['debt_default_left'] == 0 and model.updates == 1
        cases += 1
        model = m.Model(effects, triggers, nominal * 2, nominal * 3, gdp=gdp)
        model.effect(effects[name]); model.effect(effects[name])
        assert model.variables['treasury'] == 0 and model.variables['debt_default_left'] == nominal and model.updates == 2
        cases += 1  # A new affordable payment is valid while its claim remains.
    policy = 0
    for nominal in (10, 50):
        name = f'eon_debt_default_pay_{nominal}'
        for gdp in (99.999, 100, 100.001):
            for interest in (4.999, 5, 20):
                for active in (False, True):
                    model = m.Model(effects, triggers, 100, 100, gdp=gdp, interest=interest, active=active)
                    allowed = active and (gdp <= 100 if nominal == 10 else gdp > 100)
                    assert model.trigger(triggers[name + '_available']) == allowed
                    model.effect(effects[name])
                    assert model.variables['treasury'] == (100 - nominal if allowed else 100)
                    assert model.variables['debt_default_left'] == (100 - nominal if allowed else 100)
                    assert model.temp['eon_debt_default_payment'] == (nominal if allowed else 0)
                    assert model.updates == int(allowed)
                    policy += 1
    for exists in (False, True):
        for requested in (-3, 0, .25, 10, 50):
            model = m.Model(effects, triggers, 5, 2, exists=exists)
            model.temp['eon_debt_default_requested_payment'] = requested
            model.effect(effects['eon_debt_default_pay_from_cash'])
            payment = min(requested, 5, 2) if exists and requested > 0 else 0
            assert model.variables['treasury'] == 5 - payment and model.variables['debt_default_left'] == 2 - payment
            assert model.temp['eon_debt_default_payment'] == payment and model.updates == int(payment > 0)
            policy += 1
    # Structural money guard: no hidden loan, aggregate-debt edit, or balance clamp.
    def walk(nodes):
        for node in nodes:
            yield node
            if isinstance(node[2], list):
                yield from walk(node[2])
    own_nodes = list(walk(m.ast(m.read(EFFECTS))))
    assert not any(k in ('modify_treasury_effect', 'automated_debt_taker', 'clamp_variable') for k, o, v in own_nodes)
    variable_writes = [(k, v[0][0]) for k, o, v in own_nodes if k in ('add_to_variable', 'subtract_from_variable', 'set_variable')]
    assert variable_writes == [('subtract_from_variable', 'treasury'), ('subtract_from_variable', 'debt_default_left')]
    assert 'ingame_update_setup' in m.definitions(MONEY)
    rejected = []

    def check_mutant(label, changed_effects, changed_triggers, cash=3, claim=2,
                     interest=4, active=True):
        model = m.Model(changed_effects, changed_triggers, cash, claim,
                        interest=interest, active=active)
        model.effect(changed_effects['eon_debt_default_pay_10'])
        payment = min(10, max(cash, 0), max(claim, 0)) if active else 0
        correct = (model.variables['treasury'] == cash - payment and
                   model.variables['debt_default_left'] == claim - payment and
                   model.variables['debt'] == 73 and model.updates == int(payment > 0))
        assert not correct, ('Defective accounting mutant escaped', label)
        rejected.append(label)

    for bound, cash, claim in (('treasury', 2, 100), ('debt_default_left', 100, 2)):
        varied = deepcopy(effects)
        branch = next(v for k, o, v in varied['eon_debt_default_pay_from_cash'] if k == 'if')
        removed = [n for n in branch if n[0] == 'clamp_temp_variable' and m.one(n[2], 'max') == bound]
        assert len(removed) == 1
        branch.remove(removed[0])
        check_mutant('removed_' + bound + '_bound', varied, triggers, cash, claim)
    for variable, replacement in (('treasury', 'eon_debt_default_requested_payment'),
                                  ('debt_default_left', 'eon_debt_default_requested_payment')):
        varied = deepcopy(effects)
        branch = next(v for k, o, v in varied['eon_debt_default_pay_from_cash'] if k == 'if')
        index = next(i for i, n in enumerate(branch) if n[0] == 'subtract_from_variable' and n[2][0][0] == variable)
        branch[index] = ('subtract_from_variable', '=', [(variable, '=', replacement)])
        check_mutant('nominal_' + variable + '_debit', varied, triggers)
    varied = deepcopy(effects)
    branch = next(v for k, o, v in varied['eon_debt_default_pay_from_cash'] if k == 'if')
    index = next(i for i, n in enumerate(branch) if n[0] == 'subtract_from_variable' and n[2][0][0] == 'debt_default_left')
    branch[index] = ('subtract_from_variable', '=', [('debt', '=', 'eon_debt_default_payment')])
    check_mutant('edited_aggregate_debt', varied, triggers)
    for key, interest, active in (('eon_debt_default_payment_period_available', 4, False),):
        varied = deepcopy(triggers)
        policy_nodes = varied['eon_debt_default_payment_policy_available']
        removed = [n for n in policy_nodes if n[0] == key]
        assert len(removed) == 1
        policy_nodes.remove(removed[0])
        check_mutant('removed_mission_policy',
                     effects, varied, interest=interest, active=active)
    varied = deepcopy(triggers)
    varied['eon_debt_default_payment_policy_available'].append(('check_variable', '=', [('interest_rate', '<', '5')]))
    check_mutant('restored_old_interest_gate', effects, varied, interest=20)
    callbacks = decisions()
    integrated = all(any(k == f'eon_debt_default_pay_{amount}' for k, o, v in m.one(callbacks[f'debt_default_pay_{amount}_from_treasury'], 'complete_effect')) for amount in (10, 50))
    if not integrated:
        assert all(m.one(callbacks[f'debt_default_pay_{amount}_from_treasury'], 'complete_effect') == old_effect(amount) for amount in (10, 50)), 'Partial integration cannot be accepted as helper-only'
    if integration:
        assert integrated, 'Existing buttons are not yet connected; helper-only acceptance cannot prove them'
        for amount in (10, 50):
            node = callbacks[f'debt_default_pay_{amount}_from_treasury']
            expected_visible = m.ast('eon_debt_default_payment_period_available = yes\n' +
                                    ('check_variable = { var = gdp_total value = 100 compare = less_than_or_equals }' if amount == 10 else 'check_variable = { gdp_total > 100 }'))
            assert m.one(node, 'visible') == expected_visible, 'Unapproved visibility policy delta'
            expected_available = m.ast('custom_trigger_tooltip = { tooltip = debt_default_pay_from_treasury_trigger_tooltip ' + f'eon_debt_default_pay_{amount}_available = yes' + ' }')
            assert m.one(node, 'available') == expected_available, 'Same tooltip ID and exact cash-repayment helper are required'
            assert m.one(node, 'icon') == 'GFX_decision_bancru_ask_button'
            assert m.one(node, 'ai_will_do') == [('factor', '=', '1000')]
            permitted_effects = ('custom_effect_tooltip', f'eon_debt_default_pay_{amount}')
            assert all(k in permitted_effects for k, o, v in m.one(node, 'complete_effect'))
            model = m.Model(effects, triggers, 3, 2, gdp=100 if amount == 10 else 100.001)
            assert model.trigger(m.one(node, 'visible')) and model.trigger(m.one(node, 'available'))
            model.effect(m.one(node, 'complete_effect'))
            assert model.variables['treasury'] == 1 and model.variables['debt_default_left'] == 0 and model.variables['debt'] == 73
            assert not model.trigger(m.one(node, 'available'))
            model.effect(m.one(node, 'complete_effect'))
            assert model.variables['treasury'] == 1 and model.updates == 1
            for gdp in (99.999, 100, 100.001):
                for interest in (4.999, 5, 20):
                    for active in (False, True):
                        model = m.Model(effects, triggers, 100, 100, gdp=gdp, interest=interest, active=active)
                        visible = active and (gdp <= 100 if amount == 10 else gdp > 100)
                        allowed = visible
                        assert model.trigger(m.one(node, 'visible')) == visible
                        assert model.trigger(m.one(node, 'available')) == allowed
                        model.effect(m.one(node, 'complete_effect'))
                        assert model.variables['treasury'] == (100 - amount if allowed else 100)
                        assert model.variables['debt_default_left'] == (100 - amount if allowed else 100)
                        assert model.variables['debt'] == 73
    paths = [EFFECTS, TRIGGERS, DECISIONS, BUDGET, MONEY,
             'tools/validation/debt_default_accounting/_model.py',
             'tools/validation/debt_default_accounting/test_accounting.py',
             'tools/validation/aid_flag_scope/_model.py']
    return {'cash_claim_cases': cases, 'policy_and_core_cases': policy,
            'historical_red': old, 'historical_old_interest_gate': old_interest,
            'decision_integration_present': integrated,
            'bounded_mutants_rejected': rejected,
            'source_sha256': {p: hashlib.sha256(ROOT.joinpath(p).read_bytes()).hexdigest() for p in paths},
            'all_core_passed': True, 'native_gameplay_proven': False,
            'boundary': 'Actual economy updater call counted; whole native economy and UI need native40'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--red', action='store_true')
    parser.add_argument('--require-integration', action='store_true')
    args = parser.parse_args()
    if args.red:
        effects = {'modify_treasury_effect': m.definitions(BUDGET)['modify_treasury_effect']}
        print(json.dumps({'actual_current_old_callback_failures': historical(effects, current=True),
                          'actual_current_old_interest_gate': historical_interest_gate(current=True)}, indent=2))
        raise SystemExit(1)
    print(json.dumps(validate(args.require_integration), indent=2))
