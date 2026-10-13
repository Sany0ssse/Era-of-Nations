"""Narrow source/API/byte guards for package25; no native compilation claim."""
from pathlib import Path
import hashlib,json,re,subprocess,sys,importlib.util
from test_delivery import ROOT,ast,one,read,variable_comparison,GUI_FILE
sys.path.insert(0, str(ROOT/'tools/validation/debt_accounting'))
from byte_compat import restore_debt_accounting

# Exact canonical uranium changes are restored before historical whole-byte guards.
_uranium_spec=importlib.util.spec_from_file_location('eon_uranium_byte_compat',
    ROOT/'tools/validation/uranium_resources/byte_compat.py')
_uranium_bytes=importlib.util.module_from_spec(_uranium_spec)
_uranium_spec.loader.exec_module(_uranium_bytes)

# Project only the later frozen energy-AI policy island before the old GUI
# comparison; its independent negative controls retain the byte boundary.
_ai_energy_spec=importlib.util.spec_from_file_location('eon_ai_energy_byte_compat',
    ROOT/'tools/validation/ai_policy/energy_byte_compat.py')
_ai_energy_bytes=importlib.util.module_from_spec(_ai_energy_spec)
_ai_energy_spec.loader.exec_module(_ai_energy_bytes)

# Exact later arsenal insertion is removed only for historical byte comparisons.
_arsenal_spec=importlib.util.spec_from_file_location('eon_arsenal_budget_byte_compat',
    ROOT/'tools/validation/missile_system/byte_compat.py')
_arsenal_bytes=importlib.util.module_from_spec(_arsenal_spec)
_arsenal_spec.loader.exec_module(_arsenal_bytes)

# Explicit native98 migration islands supplement the c1420b historical baseline.
# Their exact bytes/digests are restored before comparing all foreign money code.
_migration_spec=importlib.util.spec_from_file_location('eon_migration_money_byte_compat',
    ROOT/'tools/validation/migration_relief/byte_compat.py')
_migration_bytes=importlib.util.module_from_spec(_migration_spec)
_migration_spec.loader.exec_module(_migration_bytes)

# The annual-to-weekly EU grant correction is an independent exact calculation
# projection. Migration's seven islands and the two eligibility gates stay exact.
_eu_weekly_spec=importlib.util.spec_from_file_location('eon_eu_weekly_byte_compat',
    ROOT/'tools/validation/eu_weekly_cash/byte_compat.py')
_eu_weekly_bytes=importlib.util.module_from_spec(_eu_weekly_spec)
_eu_weekly_spec.loader.exec_module(_eu_weekly_bytes)

# Exact later consensual-peace guards are projected out before old assertions.
_peace_spec=importlib.util.spec_from_file_location('eon_peace_legacy_source_compat',
    ROOT/'tools/validation/peace_settlement/legacy_source_compat.py')
_peace_bytes=importlib.util.module_from_spec(_peace_spec)
_peace_spec.loader.exec_module(_peace_bytes)


# Exact certified adjacent damage/state boundary only; unknown effects stay closed.
_economy_spec=importlib.util.spec_from_file_location('eon_economy_refresh_compat',
    ROOT/'tools/validation/performance_refresh/byte_compat.py')
_economy_bytes=importlib.util.module_from_spec(_economy_spec)
_economy_spec.loader.exec_module(_economy_bytes)

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
# Later EU eligibility changes are permitted only at these exact two money
# gates. Restore them before the historical comparison; all other bytes stay
# subject to the original before/after guards and their explicit migrations.
EU_FINANCE_REPLACEMENTS = (
    ('\t# EU\n\tif = {\n\t\tlimit = {\n\t\t\teon_eu_is_budget_participant = yes\n'
     '\t\t\tNOT = { has_idea = EUU_subsidies_suspended }\n',
     '\t# EU\n\tif = {\n\t\tlimit = {\n\t\t\tis_in_array = { global.EU_member = THIS }\n'
     '\t\t\tNOT = { has_idea = EUU_subsidies_suspended }\n'),
    ('\t# European Union Contribution Expenses\n'
     '\tif = { limit = { eon_eu_is_budget_participant = yes }\n'
     '\t\tadd_to_variable = { additional_expenses_rate = EU_budget_contribution_weekly }\n\t}\n',
     '\t# European Union Contribution Expenses\n'
     '\tif = { limit = { has_idea = EU_member }\n'
     '\t\tadd_to_variable = { additional_expenses_rate = EU_budget_contribution_weekly }\n\t}\n'),
)

def restore_eu_finance_eligibility(text):
    if text.count('eon_eu_is_budget_participant = yes') != 2:
        raise AssertionError('Exactly two current EU finance gate references required')
    for current, original in EU_FINANCE_REPLACEMENTS:
        if text.count(current) != 1:
            raise AssertionError('Exact unique current EU finance gate required')
        text = text.replace(current, original, 1)
    return text

money=read('common/scripted_effects/00_money_system.txt');oldmoney=baseline(CHANGED[1]).decode('utf-8-sig')
money=_economy_bytes.restore_adjacent_state_refresh(CHANGED[1],money)
money=_arsenal_bytes.restore_arsenal_budget(CHANGED[1],money)
check(_migration_bytes.CATALOG['baseline_commit']==BASELINE and
      len(_migration_bytes.CATALOG['islands'])==7,'Seven explicit native98 migration money islands')
check(all(oldmoney.count(item['original'])==1 for item in _migration_bytes.CATALOG['islands']),
      'Every migration original is exact and unique in historical Git bytes')
migration_money_negative_controls=_migration_bytes.negative_controls(money)
check(len(migration_money_negative_controls)==14,'All changed-island and foreign-byte migration mutants rejected')
money=_migration_bytes.restore_migration_money(CHANGED[1],money)
money=_eu_weekly_bytes.restore_weekly_subsidy(CHANGED[1],money)
before='\t########ENERGY SELLING SYSTEM###########';after='\t#Propaganda Medrese'
current_eu_money=money
money=restore_eu_finance_eligibility(current_eu_money)
check(all(money.count(original)==1 for current,original in EU_FINANCE_REPLACEMENTS),
      'Exactly two EU finance gates restored to historical member eligibility')
eu_finance_negative_controls=[]
for index,(current,original) in enumerate(EU_FINANCE_REPLACEMENTS,1):
    mutant=current_eu_money.replace(current,original,1)
    try: restore_eu_finance_eligibility(mutant)
    except AssertionError: eu_finance_negative_controls.append('missing current gate '+str(index))
    else: raise AssertionError('Missing current EU gate was silently accepted')
try: restore_eu_finance_eligibility(current_eu_money+EU_FINANCE_REPLACEMENTS[0][0])
except AssertionError: eu_finance_negative_controls.append('extra current gate')
else: raise AssertionError('Extra EU eligibility reference was silently accepted')
for marker,region in (('\t\tset_variable = { additional_income_agrarian_economy = weekly_harvest_billion }\n','prefix'),('\t# Cartel Mechanic Costs\n','suffix')):
    check(current_eu_money.count(marker)==1,'One unrelated-byte mutant anchor '+region)
    mutant=restore_eu_finance_eligibility(current_eu_money.replace(marker,marker+'# unrelated mutation\n',1))
    part=(lambda value: value.split(before,1)[0]) if region=='prefix' else (lambda value: value.split(after,1)[1])
    check(hashlib.sha256(part(mutant).encode('utf-8')).digest()!=hashlib.sha256(part(money).encode('utf-8')).digest(),
          'Unrelated '+region+' mutation remains visible to exact byte guard')
    eu_finance_negative_controls.append('unrelated '+region+' byte mutation')
check(len(eu_finance_negative_controls)==5,'All narrow EU finance restoration negative controls rejected')
check(money.split(before)[0]==oldmoney.split(before)[0],'Money bytes before owned energy section')
money_without_cash=restore_debt_accounting(CHANGED[1], money)
for kind,energy in [('expense','energy_buying_expenses'),('income','energy_selling_income')]:
    addition=('\t# Energy forecasts remain visible; actual invoices settle separately.\n'
              f'\tset_variable = {{ eon_cash_{kind}_rate = display_{kind} }}\n'
              f'\tsubtract_from_variable = {{ eon_cash_{kind}_rate = {energy} }}\n'
              f'\tclamp_variable = {{ var = eon_cash_{kind}_rate max = 1000000 }}\n')
    check(money_without_cash.count(addition)==1,'Explicit energy cash exclusion '+kind)
    money_without_cash=money_without_cash.replace(addition,'')
addition=('\tset_variable = { eon_treasury_cash_rate = eon_cash_income_rate }\n'
          '\tsubtract_from_variable = { eon_treasury_cash_rate = eon_cash_expense_rate }\n')
check(money_without_cash.count(addition)==1,'Explicit separate cash rate')
money_without_cash=money_without_cash.replace(addition,'')
old_debt_pause=('\t\t\tNOT = {\n'
                '\t\t\t\thas_active_mission = cheap_loan_from_the_imf_mission\n'
                '\t\t\t\thas_country_flag = paused_debt_repayment\n'
                '\t\t\t}\n')
new_debt_pause=('\t\t\tNOT = {\n\t\t\t\tOR = {\n'
                '\t\t\t\t\thas_active_mission = cheap_loan_from_the_imf_mission\n'
                '\t\t\t\t\thas_country_flag = paused_debt_repayment\n'
                '\t\t\t\t}\n\t\t\t}\n')
check(money_without_cash.count(new_debt_pause)==1,'Explicit either-condition debt pause')
money_without_cash=money_without_cash.replace(new_debt_pause,old_debt_pause)
check(money_without_cash.split(after,1)[1]==oldmoney.split(after,1)[1],
      'Money bytes after energy section preserved except exact cash exclusion and debt pause guard')
section=money.split(before,1)[1].split(after,1)[0]
check([k for k,o,v in ast(section)]==['eon_energy_delivery_calculate_bill','add_to_variable','add_to_variable'],'Only actual billing uses existing rate fields')
costili=_peace_bytes.restore_consensual_annex_guards((ROOT/'common/on_actions/00_costili.txt').read_bytes()).decode('utf-8-sig');oldcostili=baseline(CHANGED[2]).decode('utf-8-sig')
start='\ton_monthly = {\n\t\teffect = {\n\t\t\tif = {\n\t\t\t\tlimit = { check_variable = { energy_balance < -1 } }'
begin=oldcostili.index(start);end=oldcostili.index('\ton_daily = {',begin)
newcomment='\t# Electricity shortages reduce daily actual deliveries proportionally.\n\t# Contract terms survive and recover; no monthly blanket export cancellation.\n'
expected_costili=oldcostili[:begin]+newcomment+oldcostili[end:]
old_embargo='\t\t\t\tremove_dynamic_modifier = {\tmodifier = embargo_dynamic_modifier\t}\n'
new_embargo=('\t\t\t\tif = {\n'
             '\t\t\t\t\tlimit = { has_dynamic_modifier = embargo_dynamic_modifier }\n'
             '\t\t\t\t\tremove_dynamic_modifier = {\tmodifier = embargo_dynamic_modifier\t}\n'
             '\t\t\t\t}\n')
check(expected_costili.count(old_embargo)==2,'Two exact original annex embargo removals')
expected_costili=expected_costili.replace(old_embargo,new_embargo)
check(costili==expected_costili,'Only monthly electricity cancellation and two guarded annex embargo removals change')
energy=read(CHANGED[0]);oldenergy=baseline(CHANGED[0]).decode('utf-8-sig')
check(energy.split('\t# Energy Use from Buildings')[1].split('\t# Net Energy Balance Calculations')[0]==oldenergy.split('\t# Energy Use from Buildings')[1].split('\t# Net Energy Balance Calculations')[0],'Domestic demand bytes preserved')
check(energy.split('\t# Calculate the Non-Electric Fuel Consumption')[1].split('energy_on_daily = {')[0]==oldenergy.split('\t# Calculate the Non-Electric Fuel Consumption')[1].split('energy_on_daily = {')[0],'Non-electric fuel bytes preserved')
energy_without_uranium=_uranium_bytes.restore_uranium_reward(energy.encode('utf-8')).decode('utf-8')
check(energy_without_uranium.split('# Effect: random_renewable_variable_calculation')[1]==oldenergy.split('# Effect: random_renewable_variable_calculation')[1],'Unrelated energy effects preserved except exact kg reward migration wrapper')
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
check('PREV.eon_energy_capacity_quantity' not in capacity,'Supplier reads the shared execution quantity')
check('PREV.eon_energy_projected_balance' not in capacity and '# The calculated execution temporary is already visible to the caller.' in capacity,'Supplier output remains in the shared execution temporary before shortage predicate')
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
expected=oldnegotiation
old_offer_flag='\thas_country_flag = energy_agreement@eon_energy_response_partner\n'
new_offer_flag=('\tvar:eon_energy_response_partner = {\n'
                '\t\tPREV = { has_country_flag = energy_agreement@PREV }\n\t}\n')
check(expected.count(old_offer_flag)==1,'One original offer scalar-suffix flag read')
expected=expected.replace(old_offer_flag,new_offer_flag)
check(normalize_native(ast(negotiation))==normalize_native(ast(expected)),
      'Negotiation AST preserves predicates and shared mirror operands except exact peer-scope flag guard')
delivery=read(NEW[1])
check(delivery.count(' var:eon_energy_delivery_partner = {\n  PREV = { has_country_flag = energy_agreement@PREV }\n }\n')==1,
      'Delivery reads caller agreement through exact peer/PREV roundtrip')
check('energy_agreement@eon_energy_delivery_partner' not in delivery and
      'energy_agreement@eon_energy_response_partner' not in negotiation,
      'No countryflag read resolves a scalar temporary as a country selector')

# The GUI source is byte-bound separately: exactly two caller flag predicates
# change; every button, effect, national guard and unrelated byte is retained.
GUI_BASELINE='21207b33f48305dc4cd1db4a0df5aeff3f472e46'
old_gui=subprocess.check_output(['git','show',GUI_BASELINE+':'+GUI_FILE],cwd=ROOT)
expected_gui=old_gui
for indent in (b'\t'*4,b'\t'*6):
    before=b'\n'+indent+b'has_country_flag = energy_agreement@energy_selling_selected_TAG\n'
    after=(b'\n'+indent+b'var:energy_selling_selected_TAG = {\n'+indent+
           b'\tPREV = { has_country_flag = energy_agreement@PREV }\n'+indent+b'}\n')
    check(expected_gui.count(before)==1,'One original caller GUIflag guard at exact indentation')
    expected_gui=expected_gui.replace(before,after)
current_gui=(ROOT/GUI_FILE).read_bytes()
gui_before_ai_policy=_ai_energy_bytes.restore_energy_ai(GUI_FILE,current_gui)
check(_uranium_bytes.restore_uranium_gui(gui_before_ai_policy)==expected_gui,
      'Entire GUI bytes equal original except exact peer/PREV, uranium, and frozen energy-AI islands')
energy_ai_negative_controls=_ai_energy_bytes.negative_controls(GUI_FILE,current_gui)
check(len(energy_ai_negative_controls)==4,
      'Energy-AI ownership rejects changed, missing, duplicate and unrelated GUI bytes')
uranium_negative_controls=_uranium_bytes.negative_controls(energy.encode('utf-8'),gui_before_ai_policy,
    energy_without_uranium.encode('utf-8'),expected_gui)
check(len(uranium_negative_controls)==6,'All uranium-wrapper, migrated-stock and unrelated-byte negative controls rejected')
check(current_gui.startswith(b'\xef\xbb\xbf')==old_gui.startswith(b'\xef\xbb\xbf') and
      current_gui.count(b'\r\n')==old_gui.count(b'\r\n'),'GUI original BOM/LF preserved')
check('energy_agreement@energy_selling_selected_TAG' not in read(GUI_FILE),
      'Both button and guarded producer reject scalar flag addressing')
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
    'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in CHANGED+NEW+[GUI_FILE]},
    'uranium_byte_guard_negative_controls':uranium_negative_controls,
    'energy_ai_byte_guard_negative_controls':energy_ai_negative_controls,
    'energy_ai_byte_compat_sha256':hashlib.sha256(Path(_ai_energy_spec.origin).read_bytes()).hexdigest(),
    'energy_ai_canonical_islands_sha256':hashlib.sha256((ROOT/'tools/validation/ai_policy/canonical_energy_ai.json').read_bytes()).hexdigest(),
    'eu_finance_byte_guard_negative_controls':eu_finance_negative_controls,
    'migration_money_byte_guard_negative_controls':migration_money_negative_controls,
    'migration_money_byte_compat_sha256':hashlib.sha256(Path(_migration_spec.origin).read_bytes()).hexdigest(),
    'migration_money_islands_sha256':hashlib.sha256(_migration_bytes.CATALOG_PATH.read_bytes()).hexdigest(),
    'uranium_byte_compat_sha256':hashlib.sha256(Path(_uranium_spec.origin).read_bytes()).hexdigest(),
    'proof_limitations':['Byte/API/localisation/source guards only','No native compilation, campaign, performance or multiplayer acceptance'],
    'native_campaign_verified':False},indent=2))
