"""Current AST regressions for native10 execution-temporary scope semantics.

Temporary scope was calibrated in the engine separately. These tests exercise
current source and reject the preceding scoped-read mistakes. Native29 also
calibrated country-key flags. These tests do not claim native
physical aggregation, clock delivery, save/load or multiplayer proof.
"""
from copy import deepcopy
import json
from _model import *

cases=[]

def near(actual,wanted):
    assert abs(actual-wanted)<1e-7,(actual,wanted)

def rewrite(nodes,before,after):
    """Mutate only an exact operand, retaining the current parsed command tree."""
    result=[]
    for key,operator,body in nodes:
        body=rewrite(body,before,after) if isinstance(body,list) else after if body==before else body
        result.append((key,operator,body))
    return result

def old_guard_operands(nodes,names):
    result=[]
    for key,operator,body in nodes:
        if key=='check_variable':
            body=[(k,o,'PREV.'+v if v in names else v) for k,o,v in body]
        elif isinstance(body,list):body=old_guard_operands(body,names)
        result.append((key,operator,body))
    return result

def old_scalar_flag_guard(nodes,partner):
    result=[]
    proper=[('PREV','=',[('has_country_flag','=','energy_agreement@PREV')])]
    for key,operator,body in nodes:
        if key=='var:'+partner and body==proper:
            result.append(('has_country_flag','=','energy_agreement@'+partner))
        else:
            result.append((key,operator,old_scalar_flag_guard(body,partner) if isinstance(body,list) else body))
    return result

def physical():
    s=state({1:(30,5),2:(0,5),3:(0,5)})
    pair(s,1,2,10,.05)
    return s

def invoice():
    s=state({1:(30,5),2:(0,5),3:(0,5)})
    columns={'buyers':[2],'sellers':[1],'quantity':[10],'prices':[.05],
             'active':[1],'gwh':[1680],'charge':[.5],'unpaid':[.5],
             'overdue':[.5],'paid':[0],'escrow':[0],'received':[0],
             'numerator':[84],'remainder':[0]}
    s['global']['arrays'].update({'eon_energy_invoice_'+k:v for k,v in columns.items()})
    return s

# Equal names do not turn a persistent country record into an execution temp.
s=physical();actor=context(1);peer=switch(actor,2)
s['countries'][1]['vars']['scope_probe']=11
s['countries'][2]['vars']['scope_probe']=22
write(s,actor,'scope_probe',37,True)
near(value(s,actor,'scope_probe'),37);near(value(s,peer,'scope_probe'),37)
near(value(s,peer,'PREV.scope_probe'),11)
near(value(s,peer,'THIS.scope_probe'),22)
write(s,peer,'scope_probe',41,True);near(value(s,actor,'scope_probe'),41)
assert s['countries'][1]['vars']['scope_probe']==11 and s['countries'][2]['vars']['scope_probe']==22
try:write(s,peer,'PREV.scope_probe',99,True)
except AssertionError:pass
else:raise AssertionError('An unmodeled scoped temporary write must not be silently emulated')
near(value(s,actor,'scope_probe'),41)
s['temp']={};near(value(s,actor,'scope_probe'),11)
cases.append('shared invocation temporary; scoped persistent read; clean next invocation')

# Native29: a scalar country's numeric value cannot select the keyed flag.
# Native24 separately confirmed literal flag writes/clears use the literal key.
s=physical();actor=context(1,2);peer=switch(actor,2)
s['temp']={'flag_peer':2};s['countries'][1]['vars']['stored_flag_peer']=2
proper=flag(s,actor,'energy_agreement@FROM')
assert proper=='energy_agreement@2' and proper in s['countries'][1]['flags']
for suffix in ('flag_peer','stored_flag_peer','GER'):
    assert flag(s,actor,'energy_agreement@'+suffix)=='energy_agreement@'+suffix
    assert not trigger(ast('has_country_flag = energy_agreement@'+suffix),s,actor)
assert flag(s,peer,'energy_agreement@PREV')=='energy_agreement@1'
assert flag(s,peer,'probe@THIS')=='probe@2' and flag(s,peer,'probe@ROOT')=='probe@1'
execute(ast('set_country_flag = energy_agreement@flag_peer clr_country_flag = energy_agreement@flag_peer'),s,actor)
assert proper in s['countries'][1]['flags'] and 'energy_agreement@flag_peer' not in s['countries'][1]['flags']
cases.append('proper scope flags remain distinct from temporary, persistent-alias and literal-tag suffixes')

# Actual loops publish their row/value inputs to nested scopes in one invocation.
s=physical();s['countries'][1]['arrays']['scope_rows']=[2,3]
body=ast('for_each_loop = { array = scope_rows value = scope_peer index = scope_row '
         'var:scope_peer = { set_variable = { observed_peer = scope_peer } '
         'set_variable = { observed_row = scope_row } } }')
execute(body,s,context(1))
assert [s['countries'][c]['vars']['observed_peer'] for c in (2,3)]==[2,3]
assert [s['countries'][c]['vars']['observed_row'] for c in (2,3)]==[0,1]
cases.append('actual loop temporaries survive nested country frame')

# The supplier computes a shortage in the same invocation as its caller. An
# explicitly scoped input would instead read zero and falsely approve the deal.
s=physical();run(s);s['temp']={};c=context(2)
for key,val in (('eon_energy_capacity_partner',1),('eon_energy_capacity_amount',30)):
    write(s,c,key,val,True)
assert not trigger(triggers['eon_energy_proposed_capacity_available'],s,c)
near(value(s,c,'eon_energy_projected_balance'),-5)
original=deepcopy(triggers['eon_energy_proposed_capacity_available'])
try:
    def old_quantity(nodes):
        result=[]
        for key,operator,body in nodes:
            if key=='var:eon_energy_capacity_partner':
                body=body[:1]+ast('set_temp_variable = { eon_energy_capacity_quantity = PREV.eon_energy_capacity_quantity }')+body[1:]
            elif isinstance(body,list):body=old_quantity(body)
            result.append((key,operator,body))
        return result
    triggers['eon_energy_proposed_capacity_available']=old_quantity(original)
    assert trigger(triggers['eon_energy_proposed_capacity_available'],s,c)
    near(value(s,c,'eon_energy_projected_balance'),25)
finally:triggers['eon_energy_proposed_capacity_available']=original
cases.append('actual supplier shortage returns to caller; old scoped quantity falsely approves')

# A real mirrored contract dispatches equally; the old pair selector rejects it.
s=physical();run(s);near(delivered(s,1,2),-10);near(delivered(s,2,1),10);conservation(s)
original=deepcopy(triggers['eon_energy_delivery_pair_current'])
try:
    triggers['eon_energy_delivery_pair_current']=old_guard_operands(original,('eon_energy_delivery_partner',))
    s=physical();run(s);near(delivered(s,1,2),0);near(delivered(s,2,1),0)
finally:triggers['eon_energy_delivery_pair_current']=original
cases.append('current10GW transfer passes; previous scoped pair selector delivers0')

original=deepcopy(triggers['eon_energy_delivery_pair_current'])
try:
    triggers['eon_energy_delivery_pair_current']=old_scalar_flag_guard(original,'eon_energy_delivery_partner')
    assert triggers['eon_energy_delivery_pair_current']!=original
    s=physical();run(s);near(delivered(s,1,2),0);near(delivered(s,2,1),0)
finally:triggers['eon_energy_delivery_pair_current']=original
s=physical();run(s);near(delivered(s,1,2),-10);near(delivered(s,2,1),10);conservation(s)
s['countries'][1]['flags'].remove('energy_agreement@2')
s['countries'][1]['flags'].add('energy_agreement@3');run(s)
near(delivered(s,1,2),0);near(delivered(s,2,1),0)
cases.append('old scalar flag suffix blocks physical10GW; proper caller flag required for exact peer')

# Valid terms alone cannot hide a broken recipient transfer primitive.
original=deepcopy(effects['eon_energy_delivery_dispatch_round'])
try:
    mutant=rewrite(original,'eon_energy_delivery_send_mirror','PREV.eon_energy_delivery_send_mirror')
    mutant=rewrite(mutant,'eon_energy_delivery_send_positive','PREV.eon_energy_delivery_send_positive')
    effects['eon_energy_delivery_dispatch_round']=mutant
    s=physical();run(s);near(delivered(s,1,2),-10);near(delivered(s,2,1),0)
    try:conservation(s)
    except AssertionError:pass
    else:raise AssertionError('Previous recipient primitive must fail physical conservation')
finally:effects['eon_energy_delivery_dispatch_round']=original
cases.append('previous scoped recipient primitive fails independent physical conservation')

# Native country totals gate payment and receipts. Both directions need the
# execution input, while ledger/country money remains persistent and distinct.
s=invoice();run(s,'eon_energy_settlement_settle_world')
near(s['countries'][2]['vars']['treasury'],499.5)
near(s['countries'][1]['vars']['treasury'],500.5)
near(s['countries'][3]['vars']['treasury'],500)
assert s['global']['arrays']['eon_energy_invoice_unpaid']==[0]
assert s['global']['arrays']['eon_energy_invoice_paid']==[.5]
assert s['global']['arrays']['eon_energy_invoice_received']==[.5]
run(s,'eon_energy_settlement_settle_world')
near(s['countries'][2]['vars']['treasury'],499.5);near(s['countries'][1]['vars']['treasury'],500.5)
original=deepcopy(effects['eon_energy_settlement_prepare_accounts'])
try:
    # Change only guarded right operands; loop/scope/temporary writes are valid.
    effects['eon_energy_settlement_prepare_accounts']=old_guard_operands(original,('eon_es_total_buyer','eon_es_total_seller'))
    s=invoice();run(s,'eon_energy_settlement_settle_world')
    near(s['countries'][2]['vars']['treasury'],500);near(s['countries'][1]['vars']['treasury'],500)
    assert s['global']['arrays']['eon_energy_invoice_unpaid']==[.5]
finally:effects['eon_energy_settlement_prepare_accounts']=original
cases.append('current invoice pays both exact countries once; previous scoped totals never pay')

# Actual proposal inputs/price are persistent per side. The mirror amount is
# shared only for this validation, including when a supplier checks an offer.
s=physical();run(s);s['temp']={};c=context(1)
write(s,c,'eon_energy_pair_partner',2,True);execute(effects['eon_energy_read_pair_record'],s,c)
s['countries'][1]['vars'].update(energy_selling_selected_TAG=2,temp_energy_ammount=-8,temp_energy_price=.07)
execute(effects['eon_energy_send_offer'],s,c)
s['temp']={};c=context(2,1);write(s,c,'eon_energy_response_partner',1,True)
assert trigger(triggers['eon_energy_offer_identity_current'],s,c)
near(s['countries'][1]['vars']['eon_energy_offer_amount'],-8)
near(s['countries'][2]['vars']['eon_energy_offer_amount'],8)
near(s['countries'][1]['vars']['eon_energy_offer_price'],.07)
near(s['countries'][2]['vars']['eon_energy_offer_price'],.07)
original=deepcopy(triggers['eon_energy_offer_identity_current'])
try:
    triggers['eon_energy_offer_identity_current']=old_guard_operands(original,('eon_energy_response_mirror_amount',))
    assert not trigger(triggers['eon_energy_offer_identity_current'],s,c)
finally:triggers['eon_energy_offer_identity_current']=original
try:
    triggers['eon_energy_offer_identity_current']=old_scalar_flag_guard(original,'eon_energy_response_partner')
    assert triggers['eon_energy_offer_identity_current']!=original
    assert not trigger(triggers['eon_energy_offer_identity_current'],s,c)
finally:triggers['eon_energy_offer_identity_current']=original
assert trigger(triggers['eon_energy_offer_identity_current'],s,c)
s['countries'][2]['flags'].remove('energy_agreement@1')
s['countries'][2]['flags'].add('energy_agreement@3')
assert not trigger(triggers['eon_energy_offer_identity_current'],s,c)
s['countries'][2]['flags'].remove('energy_agreement@3')
s['countries'][2]['flags'].add('energy_agreement@1')
assert trigger(triggers['eon_energy_offer_identity_current'],s,c)
cases.append('old scalar offer flag fails; proper incoming exact-peer flag succeeds and wrong pair fails')
s['temp']={};execute(effects['eon_energy_accept_offer'],s,context(2,1))
near(delivered(s,1,2),-8);near(delivered(s,2,1),8)
conservation(s)
cases.append('actual proposal/validation/acceptance preserves persistent price; old temp mirror fails')

# Complete current helpers from negotiation to 168 metered clock callbacks and
# one settlement; the numeric calendar/queue delivery remain fixture boundaries.
clock=one(next(v for k,o,v in ast(read('events/eon_energy_settlement_events.txt'))
               if k=='country_event' and one(v,'id')=='eon_energy_settlement.100'),'immediate')
for hour in range(168):
    s['global']['vars']['date']+=1
    s['global']['vars']['num_days']=100+(s['global']['vars']['date']-2400)//24
    ready=[event for event in s.get('scheduled',[]) if event[0]<=s['global']['vars']['date']]
    s['scheduled']=[event for event in s.get('scheduled',[]) if event[0]>s['global']['vars']['date']]
    for when,actor,ident in ready:
        assert ident=='eon_energy_settlement.100'
        s['temp']={};execute(clock,s,context(actor))
assert s['global']['arrays']['eon_energy_invoice_gwh']==[0,1344]
near(sum(s['global']['arrays']['eon_energy_invoice_charge']),.56)
near(sum(s['global']['arrays']['eon_energy_invoice_paid']),.56)
near(sum(s['global']['arrays']['eon_energy_invoice_received']),.56)
near(sum(s['global']['arrays']['eon_energy_invoice_unpaid']),0)
near(s['countries'][2]['vars']['treasury'],499.44)
near(s['countries'][1]['vars']['treasury'],500.56)
near(s['countries'][3]['vars']['treasury'],500)
run(s,'eon_energy_settlement_settle_world')
near(s['countries'][2]['vars']['treasury'],499.44);near(s['countries'][1]['vars']['treasury'],500.56)
cases.append('negotiated8GW .07 price ->1344GWh -> exact .56 cash once in168 fixture hours')

print(json.dumps({'all_passed':True,'cases_passed':len(cases),'cases':cases,
                  'native_campaign_verified':False},indent=2))
