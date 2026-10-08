"""Narrow source/API/byte guards for package25; no native compilation claim."""
from pathlib import Path
import hashlib,json,re,subprocess
from test_delivery import ROOT,ast,one,read,variable_comparison

BASELINE='c1420b108dee2d129018951c9ba73c1f6bfc4360'
checks=0
def check(condition,why):
    global checks
    checks+=1;assert condition,why
def baseline(path):return subprocess.check_output(['git','show',BASELINE+':'+path],cwd=ROOT)
CHANGED=['common/scripted_effects/!_energy_effects.txt','common/scripted_effects/00_money_system.txt',
         'common/on_actions/00_costili.txt','common/scripted_effects/eon_energy_contract_effects.txt',
         'common/scripted_triggers/eon_energy_capacity_triggers.txt',
         'common/scripted_triggers/eon_energy_negotiation_triggers.txt']
NEW=['common/scripted_effects/eon_energy_delivery_effects.txt','common/scripted_triggers/eon_energy_delivery_triggers.txt',
     'common/on_actions/eon_energy_delivery_on_actions.txt','events/eon_energy_delivery_events.txt',
     'common/decisions/eon_energy_delivery_decisions.txt','common/decisions/categories/eon_energy_delivery_categories.txt',
     'localisation/english/eon_energy_delivery_l_english.yml','localisation/russian/eon_energy_delivery_l_russian.yml']
for path in CHANGED:
    b=(ROOT/path).read_bytes();old=baseline(path)
    check(b.startswith(b'\xef\xbb\xbf')==old.startswith(b'\xef\xbb\xbf'),path+' BOM preserved')
    check(b.count(b'\r\n')==old.count(b'\r\n'),path+' original EOL style preserved')
    check(ast(read(path))!=[],path+' parses')
for path in NEW:
    b=(ROOT/path).read_bytes();check(bool(b),path+' exists')
    if path.endswith('.yml'):check(b.startswith(b'\xef\xbb\xbf'),path+' UTF8 BOM')
    else:check(bool(ast(read(path))),path+' parses')
money=read('common/scripted_effects/00_money_system.txt');oldmoney=baseline(CHANGED[1]).decode('utf-8-sig')
before='\t########ENERGY SELLING SYSTEM###########';after='\t#Propaganda Medrese'
check(money.split(before)[0]==oldmoney.split(before)[0],'Money bytes before owned energy section')
check(money.split(after,1)[1]==oldmoney.split(after,1)[1],'Money bytes after owned energy section')
section=money.split(before,1)[1].split(after,1)[0]
check([k for k,o,v in ast(section)]==['eon_energy_delivery_calculate_bill','add_to_variable','add_to_variable'],'Only actual billing uses existing rate fields')
costili=read('common/on_actions/00_costili.txt');oldcostili=baseline(CHANGED[2]).decode('utf-8-sig')
start='\ton_monthly = {\n\t\teffect = {\n\t\t\tif = {\n\t\t\t\tlimit = { check_variable = { energy_balance < -1 } }'
begin=oldcostili.index(start);end=oldcostili.index('\ton_daily = {',begin)
newcomment='\t# Electricity shortages reduce daily actual deliveries proportionally.\n\t# Contract terms survive and recover; no monthly blanket export cancellation.\n'
check(costili==oldcostili[:begin]+newcomment+oldcostili[end:],'Only old monthly cancellation block changes')
energy=read(CHANGED[0]);oldenergy=baseline(CHANGED[0]).decode('utf-8-sig')
check(energy.split('\t# Energy Use from Buildings')[1].split('\t# Net Energy Balance Calculations')[0]==oldenergy.split('\t# Energy Use from Buildings')[1].split('\t# Net Energy Balance Calculations')[0],'Domestic demand bytes preserved')
check(energy.split('\t# Calculate the Non-Electric Fuel Consumption')[1].split('energy_on_daily = {')[0]==oldenergy.split('\t# Calculate the Non-Electric Fuel Consumption')[1].split('energy_on_daily = {')[0],'Non-electric fuel bytes preserved')
check(energy.split('# Effect: random_renewable_variable_calculation')[1]==oldenergy.split('# Effect: random_renewable_variable_calculation')[1],'Unrelated energy effects preserved')
daily=one(ast(energy),'energy_on_daily');check(daily[0][0]=='eon_energy_delivery_daily_tick','Global snapshot before native storage update')
helper=read(NEW[0]);check('treasury_change' not in helper and 'add_to_variable = { treasury =' not in helper,'No second cash debit/credit')
check('energy_contracts_ammount value' not in helper,'Actual arrays do not replace signed contractual arrays')
for key in ('eon_energy_delivery_prepare_round','eon_energy_delivery_dispatch_round','eon_energy_delivery_commit_round'):
    check(helper.count(key+' = yes')==1,'One synchronous round stage '+key)
check('global.eon_energy_delivery_round < 64' in helper and 'global.eon_energy_delivery_delta > 0.001' in helper,'Explicit numerical budget/tolerance')
check('global.num_days' in helper and 'days = 1' not in helper,'Documented date latch, no guessed global TTL')
check('eon_energy_delivery_conservative_incomplete' in helper,'Convergence limit is visible state')
contract=read(CHANGED[3]);check(contract.count('eon_energy_delivery_reconcile_world = yes')==2,'Establishment/end refresh complete reciprocal tables')
capacity=read(CHANGED[4]);check('eon_energy_capacity_old_amount = eon_energy_delivery_read_amount' in capacity,'Release actual old supply')
check('eon_energy_capacity_quantity = PREV.eon_energy_capacity_quantity' in capacity,'Supplier receives caller quantity explicitly')
check('PREV.eon_energy_projected_balance = eon_energy_projected_balance' in capacity,'Caller receives supplier output before shortage predicate')
negotiation=read(CHANGED[5]);oldnegotiation=baseline(CHANGED[5]).decode('utf-8-sig')
def normalize_native(nodes):
    """Normalize native syntax only; never mask altered operands or predicates."""
    result=[]
    for key,op,body in nodes:
        if key=='check_variable':
            body=[variable_comparison(body)]
        elif isinstance(body,list):body=normalize_native(body)
        elif key=='has_war_with' and body.startswith('var:'):body=body[4:]
        result.append((key,op,body))
    return result
expected=oldnegotiation.replace('eon_energy_offer_amount = eon_energy_response_mirror_amount',
                                'eon_energy_offer_amount = PREV.eon_energy_response_mirror_amount')
check(normalize_native(ast(negotiation))==normalize_native(ast(expected)),
      'Negotiation AST preserves predicates/operands except explicit scoped mirror; native syntax normalized')
def walk(nodes):
    for key,op,body in nodes:
        yield key,op,body
        if isinstance(body,list):yield from walk(body)
for path in (NEW[0],NEW[1],CHANGED[4],CHANGED[5],'common/scripted_effects/eon_energy_ai_effects.txt'):
    nodes=list(walk(ast(read(path))))
    check(all(op not in ('>=','<=') for key,op,body in nodes),path+' has no unsupported native comparison shorthand')
    for key,op,body in nodes:
        if key=='check_variable':variable_comparison(body)
    check(all(not(key=='has_war_with' and isinstance(body,str) and body.startswith('eon_')) for key,op,body in nodes),
          path+' variable war targets use var:')
for key in ('eon_energy_delivered','eon_energy_delivery_next','eon_energy_delivery_partners','eon_energy_delivery_terms','eon_energy_delivery_prices'):
    check('clear_array = '+key in helper,'New world starts with clean '+key)
sprite=read('interface/MD_decisions.gfx');check('name = "GFX_decision_energy_buy_button"' in sprite,'Status decision sprite exists')
keys=[]
for language in ('english','russian'):
    path=f'localisation/{language}/eon_energy_delivery_l_{language}.yml';text=read(path)
    found=re.findall(r'^ ([^ :]+):',text,re.M);check(len(found)==len(set(found)),'No duplicate '+language+' loc IDs')
    keys.append(set(found))
check(keys[0]==keys[1],'EN/RU keys agree')
events=ast(read(NEW[3]));ids=[one(v,'id') for k,o,v in events if k=='country_event']
check(len(ids)==len(set(ids))==3,'Three distinct informational event IDs')
for k,o,v in events:
    if k=='country_event':
        options=[body for name,op,body in v if name=='option']
        check(all([name for name,op,body in opt]==['name'] for opt in options),'Report options grant no resources')

if __name__=='__main__':print(json.dumps({'suite':'package25 source boundaries','checks':checks,
    'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in CHANGED+NEW},
    'proof_limitations':['Byte/API/localisation/source guards only','No native compilation, campaign, performance or multiplayer acceptance'],
    'native_campaign_verified':False},indent=2))
