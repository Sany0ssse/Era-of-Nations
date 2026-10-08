"""Execute CURRENT invoice/cash AST with explicit historical-meter fixtures.

No copied payment algorithm. This isolates currency allocation from native
clock/physical dispatch, separately tested by test_settlement.py and native.
Legacy arithmetic's actual precision is unknown: 3/5 digits are adversarial.
"""
from decimal import Decimal
from itertools import permutations
from random import Random
import json
from _model import *

cases=0; maximum_quota_error=0
def near(a,b,precision):
    assert abs(a-b)<2*10**(-precision),(a,b,precision)
def rows(s,name):return s['global']['arrays']['eon_energy_invoice_'+name]
def total(s):return sum(c['vars']['treasury'] for c in s['countries'].values())+sum(rows(s,'escrow'))
def ledger(dues,cash,precision,order,receipts=False):
    # A valid historical physical invoice is created by the actual source's
    # immutable-edition helper. The measured duration is a synthetic fixture,
    # not a claim that this delivery occurred in a native campaign.
    actor=9;inputs={actor:(0,0)}|{i+1:(0,0) for i in range(len(dues))}
    s=state(inputs);s['precision']=precision
    for c in s['countries'].values():c['ai']=False
    if not receipts:s['countries'][actor]['vars']['treasury']=cash
    else:s['countries'][actor]['vars']['treasury']=1000000
    for i in order:
        buyer=i+1 if receipts else actor;seller=actor if receipts else i+1
        owner=s['countries'][buyer];row=len(owner['arrays']['energy_contractors'])
        # A zero-money historical row is a free priced physical delivery.
        quantity=dues[i] or 1;price=1 if dues[i] else 0
        owner['arrays']['energy_contractors'].append(seller)
        owner['arrays']['energy_contracts_ammount'].append(quantity)
        owner['arrays']['energy_contracts_price'].append(price)
        c=context(buyer)
        write(s,c,'eon_energy_delivery_partner',seller,True)
        write(s,c,'eon_energy_delivery_row',row,True)
        execute(effects['eon_energy_settlement_identify_invoice'],s,c)
        index=int(value(s,c,'eon_es_invoice_row'))
        measured=float(Decimal(str(quantity))*168)
        write(s,c,'global.eon_es_fixture_row',index)
        write(s,c,'global.eon_energy_invoice_gwh^global.eon_es_fixture_row',measured)
        # Old inactive editions stay payable; free historical rows must not
        # interrupt cumulative processing or change the last eligible target.
        if i%2==0:write(s,c,'global.eon_energy_invoice_active^global.eon_es_fixture_row',0)
    run(s,'eon_energy_settlement_prepare_accounts',actor)
    charge=sum(rows(s,'charge'));original=total(s)
    if receipts:
        run(s,'eon_energy_settlement_settle_world',actor)
        near(sum(rows(s,'escrow')),charge,precision)
        # This is explicit external spending in the fixture, not lost money.
        write(s,context(actor),'treasury',float(Decimal(1000000)-Decimal(str(cash))))
        original=total(s)
        initial=s['countries'][actor]['vars']['treasury']
        # Native country decision complete_effect: actual cash-backed release.
        decisions=one(ast(read('common/decisions/eon_energy_settlement_decisions.txt')),'eon_energy_settlement_category')
        effect=one(one(decisions,'eon_energy_settlement_collect_paid'),'complete_effect')
        execute(effect,s,context(actor))
        available=1000000-initial;allocated=sum(rows(s,'received'))
    else:
        run(s,'eon_energy_settlement_manual_pay',actor)
        available=cash;allocated=sum(rows(s,'paid'))
    near(allocated,min(available,charge),precision)
    near(total(s),original,precision)
    for i,charged in enumerate(rows(s,'charge')):
        near(charged,rows(s,'unpaid')[i]+rows(s,'paid')[i],precision)
        near(rows(s,'paid')[i],rows(s,'received')[i]+rows(s,'escrow')[i],precision)
        assert rows(s,'unpaid')[i]>=0 and rows(s,'escrow')[i]>=0
    # A repeated actual control cannot charge or credit the same money twice.
    paid=deepcopy(rows(s,'paid'));received=deepcopy(rows(s,'received'))
    if receipts:execute(effect,s,context(actor))
    else:run(s,'eon_energy_settlement_manual_pay',actor)
    assert rows(s,'paid')==paid and rows(s,'received')==received
    if charge:
        canonical=rows(s,'received' if receipts else 'paid')
        error=max(abs(got-(min(available,charge)*due/charge)) for got,due in zip(canonical,rows(s,'charge')))
    else:error=0
    return error

for precision in (3,5):
    for dues,cash in (([.1,.2,.3],.05),([1,1],.001),([.001,.001,.001],.002),
                      ([.001,.1,.002],.011),([0,.1,.2,.3],.05),([.05,.05,.05],.15),
                      ([0,0,0],.05),([.01,.02,.03],0),([2.696,2.918,.588],5.333)):
        for order in permutations(range(len(dues))):
            for receipts in (False,True):
                error=ledger(dues,cash,precision,order,receipts)
                maximum_quota_error=max(maximum_quota_error,error)
                cases+=1
    rng=Random(27000+precision)
    for _ in range(200):
        dues=[rng.randint(1,3500)/1000 for _ in range(rng.randint(2,5))]
        cash=rng.randint(0,int(sum(dues)*1000+1))/1000
        order=list(range(len(dues)));rng.shuffle(order)
        for receipts in (False,True):
            error=ledger(dues,cash,precision,order,receipts)
            maximum_quota_error=max(maximum_quota_error,error);cases+=1
print(json.dumps({'all_passed':True,'cases_passed':cases,
  'maximum_observed_absolute_quota_error':maximum_quota_error,
  'proof_scope':'actual current cumulative-quota payment/receipt AST, real controls, synthetic historical meter fixtures, deterministic finite-precision properties',
  'not_proven':['native stored precision','one-quantum quota accuracy (rounded divisor can amplify error)','native historical delivery/clock/save-load']},indent=2))
