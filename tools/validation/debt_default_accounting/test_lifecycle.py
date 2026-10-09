"""Execute actual default construction, expiry, payment and closure AST.

The old RED source is a portable selected-AST fixture with a bound source SHA. Runtime assertions
use the current source; no inverse is applied to behavior. Depression, UI and
subject release are explicit native boundaries (fixtures have no subjects).
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import _model as m

ROOT = Path(__file__).resolve().parents[3]
DECISIONS = 'common/decisions/bankruptcy_decisions.txt'
EVENTS = 'events/00_Econ_events.txt'
EFFECTS = 'common/scripted_effects/eon_debt_default_accounting_effects.txt'
TRIGGERS = 'common/scripted_triggers/eon_debt_default_accounting_triggers.txt'
ON_ACTIONS = 'common/on_actions/eon_debt_default_on_actions.txt'
LEGACY = 'tools/validation/debt_default_accounting/_legacy_default_ast.json'


def entries(text):
    nodes = m.ast(text)
    return {key: body for _, _, category in nodes if isinstance(category,list)
            for key, _, body in category if isinstance(body,list)}


def event_options(text, number):
    event = next(body for key, _, body in m.ast(text) if key == 'country_event'
                 and m.one(body, 'id') == f'bankruptcy.{number}')
    return [body for key, _, body in event if key == 'option']


def execution(option):
    return [node for node in option if node[0] not in ('name', 'trigger', 'ai_chance')]


def fixture(effects, triggers, claim=0, total=0, cash=3, debt=100,
            active=False, overdue=False, interest=20, ai=False, gdp=100, precision=None):
    model = m.Model(effects, triggers, cash, claim, aggregate=debt, active=active,
                    overdue=overdue, interest=interest, ai=ai, gdp=gdp, precision=precision)
    model.variables['debt_default_total'] = total
    return model


def walk(nodes):
    for node in nodes:
        yield node
        if isinstance(node[2], list):
            yield from walk(node[2])


def validate():
    effects, triggers = m.definitions(EFFECTS), m.definitions(TRIGGERS)
    current = entries(m.read(DECISIONS))
    mission, start = current['debt_default_main_mission'], current['bankruptcy_default_on_debts']
    available, timeout, complete = [m.one(mission, key) for key in ('available', 'timeout_effect', 'complete_effect')]
    callbacks = {amount: current[f'debt_default_pay_{amount}_from_treasury'] for amount in (10, 50)}
    # The exact old source reproduces all five defects; its SHA is not optional.
    raw=(ROOT/LEGACY).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == 'e08589f80c4424ce8523c0433c72b0f92e0f105e8f0df89f0533682a4acb956b'
    legacy=json.loads(raw)
    assert legacy['decision_source_sha256'] == '6166390d3fa9b2d34451122f6e4ab21898d3deab44e58cba7aa8b2a39ca09b9b'
    assert legacy['event_source_sha256'] == '8ec35b26955b144e58fb98d5d6127fb15a04c183ae02367b9c6cdf7b1a66f173'
    def tree(nodes):
        return [(k,o,tree(v) if isinstance(v,list) else v) for k,o,v in nodes]
    before={key:tree(body) for key,body in legacy['decisions'].items()}
    before_events={key:tree(body) for key,body in legacy['events'].items()}
    def old_options(number):
        return [v for k,o,v in before_events[f'bankruptcy.{number}'] if k=='option']
    old_effects = {'modify_treasury_effect': m.definitions('common/scripted_effects/00_budget_effects.txt')['modify_treasury_effect']}
    bad = fixture(old_effects, {}, claim=.5, total=50, active=True)
    assert bad.trigger(m.one(before['debt_default_main_mission'], 'available'))
    bad.effect(m.one(before['debt_default_main_mission'], 'complete_effect'))
    assert bad.value('debt_default_left') == 0 and bad.booms == 1
    bad = fixture(old_effects, {}, claim=20, total=50, active=False)
    bad.effect(m.one(before['debt_default_main_mission'], 'timeout_effect'))
    assert bad.value('debt_default_left') == 0 and bad.value('debt_default_total') == 0
    bad = fixture(old_effects, {}, claim=20, total=50, debt=100)
    bad.effect(m.one(before['bankruptcy_default_on_debts'], 'complete_effect'))
    assert bad.value('debt') + bad.value('debt_default_left') == 75
    assert bad.value('debt_default_left') == 50  # Old unpaid20 was overwritten.
    bad = fixture(old_effects, {}, cash=3)
    bad.variables['debt_from_subject'] = 17
    for number in (13,14):
        bad.effect(execution(old_options(number)[0]))
    assert bad.variables['treasury'] == 20 and bad.native_outcomes == ['create_wargoal', 'foreign_autonomy']
    old_red = {'fractional_claim_forgiven': True, 'timeout_claim_erased': True,
               'principal_loss': 25, 'unpaid_record_overwritten': True,
               'unfunded_overlord_cash_created': 17, 'war_autonomy_mutations_present': True}
    cases = 0

    def closure_contract(ceffects=effects, ctriggers=triggers, cmission=mission):
        # Stale positive completion, including 0.5, cannot erase a claim.
        for claim in (-1, .001, .5, 10):
            model = fixture(ceffects, ctriggers, claim=claim, total=50, active=False)
            snapshot = deepcopy(model.variables)
            assert not model.trigger(m.one(cmission, 'available'))
            model.effect(m.one(cmission, 'complete_effect'))
            assert model.variables == snapshot and model.booms == 0
        model = fixture(ceffects, ctriggers, claim=0, total=50, active=False)
        assert model.trigger(m.one(cmission, 'available'))
        model.effect(m.one(cmission, 'complete_effect'))
        assert model.booms == 1 and model.value('debt_default_total') == 0
        assert 'old_gdp' not in model.variables
        model.effect(m.one(cmission, 'complete_effect'))
        assert model.booms == 1  # Mission may already be removed before hook.
        for claim, total in ((0,50),(0,0),(-1,50),(.5,0)):
            model = fixture(ceffects, ctriggers, claim=claim, total=total)
            snapshot = deepcopy(model.variables)
            model.effect(m.one(cmission, 'timeout_effect'))
            assert model.variables == snapshot and not model.flags
        for claim in (.001,.5,10,100):
            model = fixture(ceffects, ctriggers, claim=claim, total=100, cash=7)
            snapshot = deepcopy(model.variables)
            model.effect(m.one(cmission, 'timeout_effect'))
            assert model.variables == snapshot and model.flags == {'eon_debt_default_overdue'}
            model.effect(m.one(cmission, 'timeout_effect'))
            assert model.variables == snapshot and model.flags == {'eon_debt_default_overdue'}
        # Even a queued completion cannot award an overdue balance a timely boom.
        model = fixture(ceffects, ctriggers, claim=0, total=50, overdue=True)
        snapshot = deepcopy(model.variables)
        model.effect(m.one(cmission, 'complete_effect'))
        assert model.variables == snapshot and model.booms == 0

    closure_contract()
    cases += 15
    # Whole existing decision callback, not just a standalone payment formula.
    for nominal, gdp in ((10,100),(50,100.001)):
        callback = callbacks[nominal]
        for interest in (4.999,5,20):
            for claim in (.001,.5,nominal,nominal+5):
                for cash in (.25,7,100):
                    model = fixture(effects,triggers,claim=claim,total=200,cash=cash,
                                    overdue=True,interest=interest,gdp=gdp)
                    assert model.trigger(m.one(callback,'visible')) and model.trigger(m.one(callback,'available'))
                    payment=min(nominal,cash,claim)
                    model.effect(m.one(callback,'complete_effect'))
                    assert model.value('treasury') == cash-payment and model.value('debt_default_left') == claim-payment
                    assert model.value('debt') == 100 and model.value('debt_bailout') == 123 and model.booms == 0
                    if payment == claim:
                        assert not model.flags and model.value('debt_default_total') == 0 and 'old_gdp' not in model.variables
                        snapshot=deepcopy(model.variables)
                        model.effect(m.one(callback,'complete_effect')); model.effect(complete); model.effect(timeout)
                        assert model.variables == snapshot and model.updates == 1 and model.booms == 0
                    else:
                        assert model.flags == {'eon_debt_default_overdue'} and model.value('debt_default_total') == 200
                    cases += 1
    # Before timeout, repayment leaves the certificate for one normal completion.
    model=fixture(effects,triggers,claim=.5,total=50,cash=7,active=True)
    model.effect(m.one(callbacks[10],'complete_effect'))
    assert model.value('debt_default_total') == 50 and model.booms == 0
    model.active=False; model.effect(complete); model.effect(complete)
    assert model.booms == 1 and model.value('treasury') == 6.5 and model.value('debt') == 100
    cases += 1
    # Execute the real country daily hook for a claim settled by another route.
    daily=m.one(m.one(m.one(m.ast(m.read(ON_ACTIONS)), 'on_actions'), 'on_daily'), 'effect')
    assert daily == [('eon_debt_default_finish_overdue_if_settled','=','yes')]
    for claim,total,overdue in ((0,50,True),(.5,50,True),(-1,50,True),
                               (0,0,True),(0,50,False)):
        model=fixture(effects,triggers,claim=claim,total=total,cash=7,overdue=overdue)
        snapshot=deepcopy(model.variables)
        model.effect(daily); model.effect(daily)
        if claim == 0 and total > 0 and overdue:
            assert not model.flags and model.value('debt_default_total') == 0 and 'old_gdp' not in model.variables
        else:
            assert model.variables == snapshot and ('eon_debt_default_overdue' in model.flags) == overdue
        assert model.value('treasury') == 7 and model.value('debt') == 100 and model.booms == 0 and model.updates == 0
        cases += 1
    # No original balance, claim or financial change is lost by declaring default.
    for debt in (.001,.5,1,3,100,1000001):
        model=fixture(effects,triggers,debt=debt)
        assert model.trigger(m.one(start,'available'))
        model.effect(m.one(start,'complete_effect'))
        assert model.value('debt') == debt*.5 and model.value('debt_default_left') == debt*.5
        assert model.value('debt_default_total') == debt*.5 and model.value('debt')+model.value('debt_default_left') == debt
        assert model.value('treasury') == 3 and model.active and model.updates == 0
        assert model.native_outcomes == ['depression','empty_subject_iteration']
        snapshot=deepcopy(model.variables)
        model.effect(m.one(start,'complete_effect'))
        assert model.variables == snapshot and model.native_outcomes == ['depression','empty_subject_iteration']
        cases += 1
    # Guard constructor before ALL inherited depression/subject policy effects.
    for options in ({'claim':20,'total':50}, {'active':True}, {'overdue':True},
                    {'claim':-1}, {'total':-1}, {'debt':0}, {'debt':-1},
                    {'interest':14.999}, {'cash':5}):
        model=fixture(effects,triggers,**options)
        snapshot=deepcopy(model.variables)
        assert not model.trigger(m.one(start,'available'))
        model.effect(m.one(start,'complete_effect'))
        assert model.variables == snapshot and model.native_outcomes == []
        cases += 1
    # AI retains original cash-policy exemption; a subprecision zero quote is inert.
    model=fixture(effects,triggers,cash=100,ai=True)
    assert model.trigger(m.one(start,'available')); model.effect(m.one(start,'complete_effect'))
    assert model.value('treasury') == 100 and model.value('debt_default_left') == 50
    model=fixture(effects,triggers,debt=.000001,precision=5)
    snapshot=deepcopy(model.variables); model.effect(m.one(start,'complete_effect'))
    assert model.variables == snapshot and not model.active and model.native_outcomes == []
    cases += 2
    # Old queued IDs preserve options and AI weights; each option is inert.
    for number in (13,14):
        previous_options=old_options(number)
        options=event_options(m.read(EVENTS),number)
        assert len(previous_options)==len(options)
        for old_option,option in zip(previous_options,options):
            assert m.one(old_option,'name') == m.one(option,'name')
            assert [node for node in old_option if node[0]=='ai_chance'] == [node for node in option if node[0]=='ai_chance']
            assert execution(option) == [('eon_debt_default_legacy_notice','=','yes')]
            model=fixture(effects,triggers,claim=20,total=50,cash=3,overdue=True)
            model.variables['debt_from_subject']=17
            snapshot=deepcopy(model.variables)
            model.effect(execution(option)); model.effect(execution(option))
            assert model.variables == snapshot and model.native_outcomes == [] and model.updates == 0
            cases += 1
    # Neither fresh expiry nor old cached options may dispatch financial/war effects.
    assert list(walk(timeout)) == list(walk(m.ast('if = { limit = { eon_debt_default_timeout_available = yes } set_country_flag = eon_debt_default_overdue }')))
    rejected=[]
    def reject(label, ceffects=effects, ctriggers=triggers, cmission=mission):
        try:
            closure_contract(ceffects,ctriggers,cmission)
        except AssertionError:
            rejected.append(label)
        else:
            raise AssertionError('Lifecycle mutant escaped: '+label)
    varied=deepcopy(triggers)
    node=varied['eon_debt_default_completed_available'][0]
    assert node==('check_variable','=',[('debt_default_left','=','0')])
    varied['eon_debt_default_completed_available'][0]=('check_variable','=',[('debt_default_left','<','1')])
    reject('old_fractional_completion_guard',ctriggers=varied)
    varied=deepcopy(triggers); varied['eon_debt_default_completed_available'].pop(1)
    reject('missing_once_only_total_certificate',ctriggers=varied)
    varied=deepcopy(triggers); varied['eon_debt_default_completed_available'].pop(2)
    reject('overdue_awarded_timely_boom',ctriggers=varied)
    varied=deepcopy(triggers); varied['eon_debt_default_completed_available'].append(('has_active_mission','=','debt_default_main_mission'))
    reject('completion_requires_already_removed_mission',ctriggers=varied)
    varied=deepcopy(mission)
    timeoutbranch=m.one(varied,'timeout_effect')[0][2]
    timeoutbranch.append(('clear_variable','=','debt_default_left'))
    reject('timeout_forgives_unpaid_claim',cmission=varied)
    for variable in ('treasury','int_investments'):
        varied=deepcopy(mission); m.one(varied,'timeout_effect')[0][2].append(('set_variable','=',[(variable,'=','0')]))
        reject('timeout_unfunded_'+variable+'_wipe',cmission=varied)
    # Mutation controls exercise constructor and late metadata paths separately.
    for label,mutate in (
        ('restored_silent_25_percent_writeoff', lambda body: body.append(('multiply_variable','=',[('debt','=','0.5')]))),
        ('rounded_fractional_default_claim', lambda body: body.insert(
            next(i for i,n in enumerate(body) if n[0]=='set_variable' and n[2][0][0]=='debt_default_left')+1,
            ('round_variable','=','debt_default_left'))),
    ):
        changed=deepcopy(m.one(start,'complete_effect'))
        branch=m.one(changed,'if')
        mutate(branch)
        model=fixture(effects,triggers,debt=3)
        model.effect(changed)
        assert model.value('debt') + model.value('debt_default_left') != 3
        rejected.append(label)
    changed=deepcopy(triggers)
    changed['eon_debt_default_start_record_available']=[n for n in changed['eon_debt_default_start_record_available'] if n[0] != 'check_variable' or n[2][0][0] not in ('debt_default_left','debt_default_total')]
    model=fixture(effects,changed,claim=20,total=50,debt=100)
    model.effect(m.one(start,'complete_effect'))
    assert model.value('debt_default_left') != 20
    rejected.append('constructor_overwrites_prior_unpaid_record')
    changed=deepcopy(effects)
    cleanup=m.one(changed['eon_debt_default_finish_overdue_if_settled'],'if')
    limit=m.one(cleanup,'limit')
    limit[1]=('check_variable','=',[('debt_default_left','<','1')])
    model=fixture(changed,triggers,claim=.5,total=50,overdue=True)
    model.effect(daily)
    assert model.value('debt_default_left') != .5
    rejected.append('daily_cleanup_forgives_fractional_claim')
    paths=[DECISIONS,EVENTS,EFFECTS,TRIGGERS,ON_ACTIONS,LEGACY,
           'tools/validation/debt_default_accounting/_model.py',
           'tools/validation/debt_default_accounting/test_lifecycle.py']
    return {'checks_passed':True,'actual_AST_lifecycle_cases':cases,'old_source_RED':old_red,
            'bounded_mutants_rejected':rejected,'source_sha256':{path:hashlib.sha256(ROOT.joinpath(path).read_bytes()).hexdigest() for path in paths},
            'native_gameplay_proven':False,'boundary':'No subject fixtures; depression, subject release, full economy updater and rendered UI require native execution.'}


if __name__ == '__main__':
    print(json.dumps(validate(),indent=2))
