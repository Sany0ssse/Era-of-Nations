"""Execute current delivery, invoice, cash, decisions and hourly callback AST.

Native hour advancement/event delivery and GDP inputs are explicit fixtures.
Finite precision 3/5 decimal arithmetic is adversarial, not native calibration.
"""
from copy import deepcopy
from itertools import permutations
from decimal import Decimal, ROUND_DOWN
import json
from _model import *

cases=[]
event_ast=ast(read('events/eon_energy_settlement_events.txt'))
clock=one(next(body for k,o,body in event_ast if k=='country_event' and one(body,'id')=='eon_energy_settlement.100'),'immediate')
decisions=one(ast(read('common/decisions/eon_energy_settlement_decisions.txt')),'eon_energy_settlement_category')

def rows(s,name):return s['global']['arrays'].get('eon_energy_invoice_'+name,[])
def gv(s,name):return s['global']['vars'].get('eon_energy_settlement_'+name,0)
def cv(s,country,name):return s['countries'][country]['vars'].get(name,0)
def money(s):return sum(cv(s,c,'treasury') for c in s['countries'])+sum(rows(s,'escrow'))
def near(a,b,eps=1e-6):assert abs(a-b)<eps,(a,b)
def accounting(s,original=None):
    eps=1e-5 if 'precision' not in s else 2*10**(-s['precision'])
    for i,charge in enumerate(rows(s,'charge')):
        near(rows(s,'unpaid')[i]+rows(s,'paid')[i],charge,eps)
        near(rows(s,'received')[i]+rows(s,'escrow')[i],rows(s,'paid')[i],eps)
        assert rows(s,'unpaid')[i]>=-eps and rows(s,'escrow')[i]>=-eps
        assert rows(s,'overdue')[i]<=rows(s,'unpaid')[i]+eps
        assert rows(s,'remainder')[i]>=-eps
    if original is not None:near(money(s),original,eps*max(1,len(rows(s,'charge'))))

def fixture(quantity=32,price=.05,cash=500,precision=None,order=(1,2)):
    # Actual inherited domestic demand has a .001 floor. The real source
    # computes 32GW export from 32.001GW generation, not a copied dispatch.
    s=state({1:(quantity+.001,0),2:(0,0)},order)
    if precision is not None:s['precision']=precision
    pair(s,1,2,quantity,price)
    s['countries'][2]['vars']['treasury']=cash
    for country in s['countries'].values():country['ai']=False
    run(s)
    return s

def advance(s,hours=1,daily=False):
    for _ in range(hours):
        s['global']['vars']['date']+=1
        s['global']['vars']['num_days']=100+(s['global']['vars']['date']-2400)//24
        due=[item for item in s.get('scheduled',[]) if item[0]<=s['global']['vars']['date']]
        s['scheduled']=[item for item in s.get('scheduled',[]) if item[0]>s['global']['vars']['date']]
        for when,actor,ident in due:
            assert ident=='eon_energy_settlement.100'
            s['temp']={};execute(clock,s,context(actor))
        if daily and (s['global']['vars']['date']-2400)%24==0:run(s,'eon_energy_delivery_daily_tick')

# Required seven-day example, actual dispatch falls midway without changing price.
s=fixture();initial=money(s);advance(s,72)
s['countries'][1]['vars']['modifier@energy_gain']=16.001;run(s)
advance(s,96)
near(sum(rows(s,'gwh')),3840);near(sum(rows(s,'charge')),1.1428571428571428)
near(cv(s,2,'treasury'),500-1.1428571428571428);accounting(s,initial)
cases.append('3days32+4days16 at .05 =>3840GWh/1.142857B')

# Independent editions freeze the price of already supplied hours.
s=fixture();initial=money(s);advance(s,72)
for c in (1,2):s['countries'][c]['arrays']['energy_contracts_price'][0]=.10
run(s);advance(s,96)
near(sum(rows(s,'charge')),32*.05*3/7+32*.10*4/7)
assert rows(s,'prices')==[.05,.10];accounting(s,initial)
cases.append('changed price never reprices preceding delivered hours')

# Execute the actual send/receiving accept path, not a hand-edited price table.
s=fixture();initial=money(s);advance(s,12)
c=context(1);s['temp']={};write(s,c,'eon_energy_pair_partner',2,True)
execute(effects['eon_energy_read_pair_record'],s,c)
s['countries'][1]['vars'].update(energy_selling_selected_TAG=2,temp_energy_ammount=-16,temp_energy_price=.1)
execute(effects['eon_energy_send_offer'],s,c)
execute(effects['eon_energy_accept_offer'],s,context(2,1));advance(s,156)
assert rows(s,'prices')==[.05,.1] and rows(s,'active')==[0,1]
near(sum(rows(s,'charge')),32*.05*12/168+16*.1*156/168);accounting(s,initial)
cases.append('actual send/accept replacement freezes delivered old price and edition')

# Actual end_pair clears live contracts; frozen invoices remain payable/visible.
s=fixture();initial=money(s);advance(s,24)
write(s,context(1),'eon_energy_pair_partner',2,True);execute(effects['eon_energy_end_pair'],s,context(1))
assert all(not c['arrays']['energy_contractors'] for c in s['countries'].values())
assert trigger(triggers['eon_energy_settlement_accounts_visible'],s,context(2))
decision=one(decisions,'eon_energy_settlement_pay_invoices')
assert trigger(one(decision,'visible'),s,context(2)) and trigger(one(decision,'available'),s,context(2))
execute(one(decision,'complete_effect'),s,context(2));near(sum(rows(s,'paid')),32*.05/7)
advance(s,144);near(sum(rows(s,'gwh')),768);accounting(s,initial)
before=money(s);execute(one(decision,'complete_effect'),s,context(2));near(money(s),before)
cases.append('actual termination+visible free decision+cash payment+repeat')

# Same-hour replacements create an edition but no elapsed phantom delivery.
for reverse in (False,True):
    s=fixture();initial=money(s);advance(s,12)
    write(s,context(2),'eon_energy_pair_partner',1,True);execute(effects['eon_energy_settlement_retire_pair'],s,context(2))
    if reverse:
        for country in s['countries'].values():country['arrays']['energy_contracts_ammount'][0]*=-1
        s['countries'][1]['vars']['modifier@energy_gain']=0;s['countries'][2]['vars']['modifier@energy_gain']=32.001
    run(s);run(s);assert len(rows(s,'buyers'))==2
    advance(s,12);run(s,'eon_energy_settlement_value_accounts')
    near(sum(rows(s,'gwh')),768);near(sum(rows(s,'charge')),32*.05/7)
    assert rows(s,'buyers')==([2,1] if reverse else [2,2]);accounting(s,initial)
    cases.append('same-hour identical/reversed edition '+str(reverse))

# Actual zero-source cyclic dispatch supplies and charges nothing.
s=state({1:(0,0),2:(0,0),3:(0,0)})
pair(s,1,2,32);pair(s,2,3,32);pair(s,3,1,32);run(s);advance(s,168)
assert sum(rows(s,'gwh'))==sum(rows(s,'paid'))==0
cases.append('zero-source cycle has no phantom GWh/income')

# All cash snapshots precede receipts. Debtor2 cannot recycle seller income.
for order in permutations((1,2,3)):
    s=state({1:(32.001,0),2:(0,0),3:(0,0)},order)
    pair(s,1,2,32);pair(s,2,3,16)
    s['countries'][2]['vars']['treasury']=0;s['countries'][3]['vars']['treasury']=100
    run(s);initial=money(s);advance(s,168)
    near(sum(charge for i,charge in enumerate(rows(s,'paid')) if rows(s,'buyers')[i]==2),0)
    assert cv(s,2,'treasury')>0 and cv(s,2,'eon_energy_settlement_arrears')>0
    accounting(s,initial);cases.append('no incoming cash cascade '+str(order))

# Proportional invoice payment including exact available-cash conservation.
for order in permutations((1,2,3)):
    s=state({1:(32.001,0),2:(16.001,0),3:(0,0)},order)
    pair(s,1,3,32);pair(s,2,3,16);s['countries'][3]['vars']['treasury']=.6
    run(s);initial=money(s);advance(s,168)
    paid={seller:rows(s,'paid')[i] for i,seller in enumerate(rows(s,'sellers'))}
    near(paid[1],.4);near(paid[2],.2);near(cv(s,3,'treasury'),0)
    accounting(s,initial);cases.append('pro rata multiple invoices '+str(order))

# Treasury cap reserves paid money, then actual collect-paid decision releases it.
s=fixture();s['countries'][1]['vars']['treasury']=1000000;initial=money(s);advance(s,168)
near(sum(rows(s,'unpaid')),0);near(sum(rows(s,'escrow')),1.6);accounting(s,initial)
assert trigger(triggers['eon_energy_settlement_accounts_visible'],s,context(1))
collect=one(decisions,'eon_energy_settlement_collect_paid')
assert not trigger(one(collect,'available'),s,context(1))
s['countries'][1]['vars']['treasury']-=1;initial-=1
assert trigger(one(collect,'visible'),s,context(1)) and trigger(one(collect,'available'),s,context(1))
execute(one(collect,'complete_effect'),s,context(1));near(sum(rows(s,'escrow')),.6);accounting(s,initial)
execute(one(collect,'complete_effect'),s,context(1));near(sum(rows(s,'escrow')),.6);accounting(s,initial)
cases.append('paid cap claim durable, original seller only, no duplicate charge')

# Both parties are notified only on transition; recovered arrears are distinct
# from newer, not-yet-due consumption during the next period.
s=fixture(cash=.6);initial=money(s);advance(s,168)
near(sum(rows(s,'overdue')),1);near(cv(s,2,'eon_energy_settlement_arrears'),1)
assert 'eon_energy_settlement_in_arrears' in s['countries'][2]['flags']
assert 'eon_energy_settlement_customer_late' in s['countries'][1]['flags']
notifications=list(s['events']);run(s,'eon_energy_settlement_update_status');assert s['events']==notifications
s['countries'][2]['vars']['treasury']+=1;initial+=1
run(s,'eon_energy_settlement_manual_pay',2);near(sum(rows(s,'overdue')),0)
assert 'eon_energy_settlement_in_arrears' not in s['countries'][2]['flags']
assert 'eon_energy_settlement_customer_late' not in s['countries'][1]['flags']
advance(s,24);run(s,'eon_energy_settlement_update_status')
near(cv(s,2,'eon_energy_settlement_payable'),32*.05/7)
near(cv(s,2,'eon_energy_settlement_arrears'),0);accounting(s,initial)
cases.append('actual overdue/recovery notifications once per side, newer accrual remains not due')

# Free supplies still retain their physical history and a visible account after
# ending; they cannot generate cash or a payment requirement.
s=fixture(price=0);initial=money(s);advance(s,24)
write(s,context(1),'eon_energy_pair_partner',2,True);execute(effects['eon_energy_end_pair'],s,context(1))
assert trigger(triggers['eon_energy_settlement_accounts_visible'],s,context(2))
assert not trigger(triggers['eon_energy_settlement_payment_available'],s,context(2))
near(sum(rows(s,'charge')),0);near(sum(rows(s,'gwh')),768);accounting(s,initial)
cases.append('zero-price ended supply keeps visible physical history, no phantom payment')

# War hook stops future flow; previous hourly quantity/price remains owed.
s=fixture();advance(s,12);initial=money(s)
s['countries'][1]['wars'].add(2);s['countries'][2]['wars'].add(1)
hooks=one(ast(read('common/on_actions/eon_energy_settlement_on_actions.txt')),'on_actions')
execute(one(one(hooks,'on_declare_war'),'effect'),s,context(1,2));advance(s,156)
near(sum(rows(s,'gwh')),384);near(sum(rows(s,'paid')),32*.05/14);accounting(s,initial)
cases.append('actual war hook closes earned hours and stops future billing')

# Annexed buyer retains its unpaid invoice. Restoration, not annexer, can pay.
for party in (1,2):
    s=fixture(cash=0 if party==2 else 500);advance(s,12);initial=money(s)
    s['countries'][3]={'vars':{'treasury':500},'arrays':{'energy_contractors':[],'energy_contracts_ammount':[],'energy_contracts_price':[]},'flags':set(),'wars':set(),'exists':True,'ai':False,'ideas':set(),'modifiers':set()};initial+=500
    s['countries'][party]['exists']=False
    execute(one(one(hooks,'on_annex'),'effect'),s,context(3,party))
    advance(s,156);near(cv(s,3,'treasury'),500)
    assert sum(rows(s,'unpaid' if party==2 else 'escrow'))>0
    accounting(s,initial)
    s['countries'][party]['exists']=True
    if party==2:s['countries'][2]['vars']['treasury']+=1;initial+=1
    run(s,'eon_energy_settlement_manual_pay',party if party==2 else 3)
    near(sum(rows(s,'unpaid')),0);near(sum(rows(s,'escrow')),0);accounting(s,initial)
    cases.append('annexed original buyer/seller restoration '+str(party))

# Native scheduled callback duplicates and both midnight hook orders.
for first in ('clock','daily'):
    s=fixture();initial=money(s);advance(s,167)
    s['global']['vars']['date']+=1;s['global']['vars']['num_days']+=1
    anchor=int(gv(s,'anchor'));s['temp']={}
    if first=='clock':execute(clock,s,context(anchor));run(s,'eon_energy_delivery_daily_tick')
    else:run(s,'eon_energy_delivery_daily_tick');execute(clock,s,context(anchor))
    baseline=deepcopy(rows(s,'paid'));count=len(s['scheduled'])
    execute(clock,s,context(anchor));run(s)
    assert rows(s,'paid')==baseline and len(s['scheduled'])==count
    near(sum(rows(s,'gwh')),5376);accounting(s,initial)
    cases.append('midnight hook order and duplicate '+first)

# Failed pulse gap is visible and never fabricates missing hour catch-up.
s=fixture();advance(s,6);run(s,'eon_energy_settlement_value_accounts');earned=sum(rows(s,'gwh'))
s['global']['vars']['date']+=72;s['global']['vars']['num_days']+=3
run(s,'eon_energy_settlement_close_world_interval');assert 'eon_energy_settlement_clock_gap' in s['global']['flags']
near(sum(rows(s,'gwh')),earned)
assert trigger(triggers['eon_energy_settlement_accounts_visible'],s,context(2))
cases.append('multi-day clock gap no fabricated delivery and visible accounting warning')

# Same-hour timer relocation always repairs a new-anchor queue independently.
s=fixture();old=int(gv(s,'anchor'));s['countries'][3]=deepcopy(s['countries'][2]);s['countries'][3]['arrays']={'energy_contractors':[],'energy_contracts_ammount':[],'energy_contracts_price':[]};s['countries'][3]['wars']=set()
s['countries'][old]['exists']=False
execute(one(one(hooks,'on_annex'),'effect'),s,context(3,old))
assert any(owner==3 for when,owner,ident in s['scheduled']);advance(s,2)
assert gv(s,'hour_count')==2;cases.append('same-hour annex timer relocation repairs queue')

# Returning to an earlier anchor in the same hour needs a new ownership epoch.
# Native survival/cancellation of the old country's queued event is a fixture;
# both possibilities must converge to one future chain and one accrued hour.
for cancelled in (False,True):
    s=fixture();s['countries'][3]=deepcopy(s['countries'][2]);s['countries'][3]['arrays']={'energy_contractors':[],'energy_contracts_ammount':[],'energy_contracts_price':[]}
    s['countries'][1]['exists']=False
    if cancelled:s['scheduled']=[item for item in s['scheduled'] if item[1]!=1]
    execute(one(one(hooks,'on_annex'),'effect'),s,context(3,1))
    s['countries'][1]['exists']=True;s['countries'][3]['exists']=False
    if cancelled:s['scheduled']=[item for item in s['scheduled'] if item[1]!=3]
    execute(one(one(hooks,'on_annex'),'effect'),s,context(1,3))
    assert any(actor==1 for when,actor,ident in s['scheduled'])
    assert gv(s,'anchor_epoch')==3
    advance(s,2)
    assert gv(s,'hour_count')==2
    assert len(s['scheduled'])==1 and s['scheduled'][0][1]==1
    cases.append('same-hour Aв†’Bв†’A timer epochs, old queues cancelled='+str(cancelled))

# Positive cash and cap headroom cannot disappear through a prematurely
# rounded near-zero ratio. Execute actual weekly and collection controls.
for precision in (3,5):
    s=fixture(cash=.001,precision=precision);initial=money(s);advance(s,168)
    near(sum(rows(s,'paid')),.001,10**(-precision)/2);near(cv(s,2,'treasury'),0)
    accounting(s,initial);before=sum(rows(s,'paid'));run(s,'eon_energy_settlement_manual_pay',2)
    near(sum(rows(s,'paid')),before,10**(-precision)/2)
    cases.append('reciprocal payment divisor preserves .001 cash at '+str(precision)+'dp')
    s=fixture(precision=precision);s['countries'][1]['vars']['treasury']=1000000
    initial=money(s);advance(s,168)
    write(s,context(1),'treasury',999999.999);initial-=.001
    execute(one(collect,'complete_effect'),s,context(1))
    near(sum(rows(s,'received')),.001,10**(-precision)/2);accounting(s,initial)
    before=sum(rows(s,'received'));execute(one(collect,'complete_effect'),s,context(1))
    near(sum(rows(s,'received')),before,10**(-precision)/2)
    cases.append('reciprocal receipt divisor preserves .001 headroom at '+str(precision)+'dp')
    for order in permutations((1,2,3)):
        s=state({1:(32.001,0),2:(16.001,0),3:(0,0)},order);s['precision']=precision
        pair(s,1,3,32);pair(s,2,3,16);s['countries'][3]['vars']['treasury']=.006
        run(s);initial=money(s);advance(s,168)
        paid={seller:rows(s,'paid')[i] for i,seller in enumerate(rows(s,'sellers'))}
        near(paid[1],.004,10**(-precision)/2);near(paid[2],.002,10**(-precision)/2)
        near(cv(s,3,'treasury'),0);accounting(s,initial)
        cases.append('small-cash multi-invoice reciprocal divisor '+str((precision,order)))

# Developer numeric probe has no treasury/ledger effect and runs only once.
s=fixture();s['debug']=True;initial=money(s);advance(s,1)
assert 'eon_energy_settlement_numeric_probe' in s['global']['flags']
near(sum(rows(s,'gwh')),32);accounting(s,initial)
cases.append('debug-only arithmetic calibration does not mutate cash or add fictitious delivery')

# Explicit serialized model state preserves queued operations and ledger IDs.
s=fixture();advance(s,48);restored=deepcopy(s);advance(s,120);advance(restored,120)
assert s['global']==restored['global'];near(money(s),money(restored));cases.append('serialized source fixture continuation, not native save proof')

# Low fixed-point precision does not sum 168 rounded tiny hourly currency flows.
for precision in (3,5):
    for quantity,price in ((1,.05),(.01,.05),(.001,.05),(16,.05),(32,.05)):
        s=fixture(quantity=quantity,price=price,precision=precision);initial=money(s)
        advance(s,168)
        unit=Decimal(1).scaleb(-precision)
        expected=float((Decimal(str(sum(rows(s,'gwh'))))*Decimal(str(price))/168).quantize(unit,rounding=ROUND_DOWN))
        near(sum(rows(s,'charge')),expected,2*10**(-precision));accounting(s,initial)
        if quantity==1:near(sum(rows(s,'paid')),.05,2*10**(-precision))
        oldcharge=sum(rows(s,'charge'));advance(s,168*4)
        assert sum(rows(s,'charge'))>=oldcharge
        accounting(s,initial);cases.append('finite precision cumulative numerator '+str((precision,quantity,price)))

print(json.dumps({'all_passed':True,'cases_passed':len(cases),'cases':cases,
 'proof_scope':'current ordered source AST with shared execution temporaries, immutable terms, cash/escrow invariants and actual decision/hook paths',
 'not_proven':['native event queue/hourly global.date changes/save-load/annex ordering','native fixed-point precision; 3/5-digit modes are adversarial','native GDP aggregation and display rendering','network losses/capacity and modern EU imbalance settlement']},indent=2))
