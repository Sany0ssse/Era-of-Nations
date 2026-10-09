"""Execute actual debt GUI callback ASTs; economic aggregation is a boundary.

No independent payment implementation is executed. Expected balance deltas are
the accounting oracle; engine precision/UI/network behavior need native checks.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/validation/diplomacy_package_27'))
import _model as m

GUI = 'common/scripted_guis/MD_money_scripted_gui.txt'
HELPER = 'common/scripted_effects/eon_debt_accounting_effects.txt'
TRIGGERS = 'common/scripted_triggers/eon_debt_accounting_triggers.txt'
gui = m.ast(m.read(GUI))
if (ROOT / HELPER).exists():
    m.effects.update({k: v for k, o, v in m.ast(m.read(HELPER))})
if (ROOT / TRIGGERS).exists():
    m.triggers.update({k: v for k, o, v in m.ast(m.read(TRIGGERS))})


def walk(nodes):
    for k, o, v in nodes:
        yield k, o, v
        if isinstance(v, list):
            yield from walk(v)


callbacks = {}
enabled = {}
for k, o, v in walk(gui):
    if k == 'effects':
        callbacks.update({name: body for name, op, body in v
                          if name.startswith(('debt_bg_', 'bottom_bar_debt_bg_'))})
    elif k == 'triggers':
        enabled.update({name: body for name, op, body in v
                        if name.startswith(('debt_bg_', 'bottom_bar_debt_bg_'))})


def run(name, cash, debt, gdp=2000, interest=5, precision=None, repeat=False):
    s = m.state({1: (0, 0), 2: (0, 0)})
    owner = s['countries'][1]
    owner['vars'].update(treasury=cash, debt=debt, gdp_total=gdp, interest_rate=interest)
    owner['flags'].add('automatically_pay_off_debt_enabled')
    # Deliberately poison inputs; every callback must replace them itself.
    s['temp'].update(eon_debt_repayment_limit=99999, eon_debt_borrowing_principal=99999,
                     eon_debt_manual_payment=42)
    if precision is not None:
        s['precision'] = precision
    updates = m.native['ingame_update_setup']
    m.execute(callbacks[name], s, m.context(1))
    if repeat:
        m.execute(callbacks[name], s, m.context(1))
    return owner, m.native['ingame_update_setup'] - updates


def near(actual, expected, precision=None):
    tolerance = 1e-8 if precision is None else 3 * 10 ** -precision
    assert abs(actual - expected) < tolerance, (actual, expected, precision)


cases = 0
eligibility_cases = 0
for prefix in ('bottom_bar_debt_bg_', 'debt_bg_'):
    for suffix, nominal in (('right_click', 1), ('control_right_click', 10),
                            ('shift_right_click', 100), ('alt_right_click', None)):
        name = prefix + suffix
        for cash, debt in ((20, 2), (2, 2), (.25, 2), (0, 2), (-2, 2),
                           (20, 0), (20, .25), (150, 120), (0, 0),
                           (1000000, 1000000), (.002, .001), (1000001, 1000001)):
            for precision in (None, 3, 5):
                owner, updates = run(name, cash, debt, precision=precision)
                payment = min(max(cash, 0), max(debt, 0), debt if nominal is None else nominal)
                near(owner['vars']['treasury'], cash - payment, precision)
                near(owner['vars']['debt'], debt - payment, precision)
                assert updates == int(payment > 0), (name, updates, payment)
                s = m.state({1: (0, 0)})
                s['countries'][1]['vars'].update(treasury=cash, debt=debt)
                assert m.trigger(enabled[name + '_enabled'], s, m.context(1)) == (payment > 0)
                eligibility_cases += 1
                if payment > 0 and debt - payment == 0:
                    assert 'automatically_pay_off_debt_enabled' not in owner['flags']
                cases += 1
        owner, updates = run(name, 20, .25, repeat=True)
        near(owner['vars']['treasury'], 19.75)
        near(owner['vars']['debt'], 0)
        assert updates == 1, name + ' closed debt must not spend on repeated click'
        cases += 1

borrowing_cases = 0
for prefix in ('debt_bg_', 'bottom_bar_debt_bg_'):
    for suffix, principal, liability in (('click', 1, 1.01), ('control_click', 10, 10.1),
                                         ('shift_click', 100, 101), ('alt_click', 1000, 1010)):
        name = prefix + suffix
        for cash, debt, interest, gdp in (
            (20, 2, 5, 2000), (1000000, 2, 5, 2000),
            (1000000-principal, 1000000-liability, 5, 2000),
            (1000000-principal+.25, 2, 5, 2000),
            (20, 1000000, 5, 2000), (20, 1000000-liability+.25, 5, 2000),
            (-2, 2, 5, 2000), (20, 2, 20, 2000), (20, 2, 5, 1000)):
            owner, updates = run(name, cash, debt, gdp, interest, precision=5)
            permitted = (interest < 20 and cash + principal <= 1000000
                         and debt + liability <= 1000000
                         and not (prefix == 'debt_bg_' and suffix == 'alt_click' and gdp <= 1499))
            near(owner['vars']['treasury'], cash + principal if permitted else cash)
            near(owner['vars']['debt'], debt + liability if permitted else debt)
            assert updates == int(permitted), (name, updates, permitted)
            s = m.state({1: (0, 0)})
            s['precision'] = 5
            s['countries'][1]['vars'].update(treasury=cash, debt=debt, gdp_total=gdp, interest_rate=interest)
            assert m.trigger(enabled[name + '_enabled'], s, m.context(1)) == permitted
            eligibility_cases += 1
            borrowing_cases += 1

automatic_cases = 0
for cash, debt in ((-2, 5), (-2, 1000000), (-2, 999999), (0, 5), (5, 5)):
    s = m.state({1: (0, 0)})
    s['precision'] = 5
    owner = s['countries'][1]
    owner['vars'].update(treasury=cash, debt=debt, gdp_total=100, interest_rate=25)
    m.execute(m.effects['automated_debt_taker'], s, m.context(1))
    principal = 3.5 if cash < 0 else 0
    permitted = principal > 0 and debt + principal * 1.01 <= 1000000
    near(owner['vars']['treasury'], cash + principal if permitted else cash, 5)
    near(owner['vars']['debt'], debt + principal * 1.01 if permitted else debt, 5)
    automatic_cases += 1

print(json.dumps({'repayment_cases': cases, 'borrowing_cases': borrowing_cases,
                  'automatic_cases': automatic_cases,
                  'button_eligibility_cases': eligibility_cases,
                  'gui_callbacks': 16, 'all_passed': True,
                  'source_sha256': {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
                                    for p in (GUI, HELPER, TRIGGERS,
                                              'common/scripted_effects/00_money_system.txt',
                                              'tools/validation/diplomacy_package_27/_model.py') if (ROOT/p).exists()},
                  'economic_update_boundary': 'real helper call counted; whole economy not emulated',
                  'native_gameplay_verified': False}, indent=2))
