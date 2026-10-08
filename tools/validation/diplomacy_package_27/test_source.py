"""Current package27 byte/API/ledger guards. This is not a native compiler."""
from pathlib import Path
import hashlib, importlib.util, json, re, subprocess, sys
from _model import ROOT, ast, one, read

BASELINE = 'f2832b6bfd980066163d0a69a6306169c992c5d7'
CHANGED = ['common/scripted_effects/eon_energy_delivery_effects.txt',
           'common/scripted_effects/eon_energy_contract_effects.txt']
NEW = ['common/scripted_effects/eon_energy_settlement_effects.txt',
       'common/scripted_triggers/eon_energy_settlement_triggers.txt',
       'common/on_actions/eon_energy_settlement_on_actions.txt',
       'common/decisions/categories/eon_energy_settlement_categories.txt',
       'common/decisions/eon_energy_settlement_decisions.txt',
       'events/eon_energy_settlement_events.txt',
       'localisation/english/eon_energy_settlement_l_english.yml',
       'localisation/russian/eon_energy_settlement_l_russian.yml']
checks = 0
def check(value, why):
    global checks
    checks += 1
    assert value, why
def baseline(path):
    return subprocess.check_output(['git','show',BASELINE+':'+path],cwd=ROOT)
def walk(nodes):
    for key, op, value in nodes:
        yield key, op, value
        if isinstance(value, list): yield from walk(value)
def expected_delivery(old):
    old=old.replace('# No network capacity, transport loss, collateral, arrears or cash receipt is\n# inferred. Prices retain the inherited billions/GW/week convention.',
                    '# Physical dispatch stays here; package27 meters intervals and settles cash.\n# Prices retain the inherited billions/GW/week convention.')
    old=old.replace(' # Replace the OLD energy component inside the current budget, never charge\n # treasury here. The inherited weekly treasury_rate remains the sole debit.',
                    ' # Replace the OLD energy forecast in the displayed budget. Package27 is the\n # only energy cash debit; weekly national cash excludes these forecasts.')
    old=old.replace('  set_global_flag = eon_energy_delivery_running\n',
                    '  set_global_flag = eon_energy_delivery_running\n  eon_energy_settlement_close_world_interval = yes\n')
    old=old.replace('PREV.eon_energy_delivery_send_mirror','eon_energy_delivery_send_mirror')
    old=old.replace('PREV.eon_energy_delivery_send_positive','eon_energy_delivery_send_positive')
    return old.replace('  clr_global_flag = eon_energy_delivery_running\n',
                        '  eon_energy_settlement_open_world_interval = yes\n  clr_global_flag = eon_energy_delivery_running\n')
def expected_contract(old):
    old=old.replace('eon_energy_end_pair = {\n',
                    'eon_energy_end_pair = {\n\teon_energy_settlement_close_world_interval = yes\n\teon_energy_settlement_retire_pair = yes\n')
    return old.replace('\t\tset_temp_variable = { eon_energy_pair_partner = FROM }\n',
                        '\t\tset_temp_variable = { eon_energy_pair_partner = FROM }\n\t\teon_energy_settlement_close_world_interval = yes\n\t\teon_energy_settlement_retire_pair = yes\n')
for path, transform in zip(CHANGED,(expected_delivery,expected_contract)):
    old=baseline(path); current=(ROOT/path).read_bytes()
    check(current.startswith(b'\xef\xbb\xbf')==old.startswith(b'\xef\xbb\xbf'),path+' BOM')
    check(current.count(b'\r\n')==old.count(b'\r\n'),path+' EOL')
    expected=transform(old.decode('utf-8')).encode('utf-8')
    check(current==expected,path+' only exact interval/retirement hooks, two comments and shared dispatch temporaries')

# Proven execution-temporary and country-key flag repairs are byte-bound.
SCOPE_REPAIRS={
 'common/scripted_triggers/eon_energy_delivery_triggers.txt':
  [(f'PREV.{name}',name) for name in ('eon_energy_delivery_partner','eon_energy_delivery_local_amount',
    'eon_energy_delivery_mirror_row','eon_energy_delivery_local_price','eon_energy_delivery_read_mirror')]+[
   (' has_country_flag = energy_agreement@eon_energy_delivery_partner\n',
    ' var:eon_energy_delivery_partner = {\n  PREV = { has_country_flag = energy_agreement@PREV }\n }\n')],
 'common/scripted_triggers/eon_energy_capacity_triggers.txt': [
  ('set_temp_variable = { eon_energy_capacity_quantity = PREV.eon_energy_capacity_quantity }',
   '# Quantity is an execution temporary shared with the supplier.'),
  ('set_temp_variable = { PREV.eon_energy_projected_balance = eon_energy_projected_balance }',
   '# The calculated execution temporary is already visible to the caller.')],
 'common/scripted_triggers/eon_energy_negotiation_triggers.txt':
  [('PREV.eon_energy_response_mirror_amount','eon_energy_response_mirror_amount'),
   ('\thas_country_flag = energy_agreement@eon_energy_response_partner\n',
    '\tvar:eon_energy_response_partner = {\n\t\tPREV = { has_country_flag = energy_agreement@PREV }\n\t}\n')]
}
for path,repairs in SCOPE_REPAIRS.items():
 old=baseline(path);expected=old
 for before,after in repairs:
  check(before.encode() in expected,path+' expected original operand '+before)
  expected=expected.replace(before.encode(),after.encode())
 check((ROOT/path).read_bytes()==expected,path+' exact temporary and peer-scope flag repairs only')
 check(expected.startswith(b'\xef\xbb\xbf')==old.startswith(b'\xef\xbb\xbf') and
       expected.count(b'\r\n')==old.count(b'\r\n'),path+' original BOM/EOL preserved')

spec=importlib.util.spec_from_file_location('eon_native_guard27',ROOT/'tools/validation/diplomacy_completion/check_native_grammar.py')
native=importlib.util.module_from_spec(spec);sys.modules[spec.name]=native;spec.loader.exec_module(native)
for path in NEW:
    raw=(ROOT/path).read_bytes()
    check(b'\r' not in raw,path+' LF style')
    if path.endswith('.txt'):
        check(bool(ast(read(path))),path+' source parses')
        check(not native.inspect(ast(read(path))),path+' documented native comparison grammar')
    else:check(raw.startswith(b'\xef\xbb\xbf'),path+' localization UTF8 BOM')

source=read(NEW[0]);effects=dict((k,v) for k,o,v in ast(source))
columns=['buyers','sellers','quantity','prices','active','gwh','charge','unpaid','overdue','paid','escrow','received','numerator','remainder']
identify=list(walk(effects['eon_energy_settlement_identify_invoice']))
added=[one(v,'array') for k,o,v in identify if k=='add_to_array']
check(added==['global.eon_energy_invoice_'+c for c in columns],'All immutable edition columns appended once, in parallel')
for key,op,value in walk(ast(source)):
    if isinstance(value,str) and 'global.eon_energy_invoice_' in value and '^' in value:
        check(value.split('^',1)[1]=='num' or value.split('^',1)[1].startswith('global.'),'Global ledger index has explicit global scalar or native length: '+value)
    if 'global.eon_energy_invoice_' in key and '^' in key:
        check(key.split('^',1)[1].startswith('global.'),'Global ledger write index has explicit global scalar: '+key)
check(not any(k=='remove_from_array' for k,o,v in walk(ast(source))),'No invoice compaction can shift immutable edition IDs')
accrual=effects['eon_energy_settlement_accrue_open_interval']
check(not any(k in ('divide_variable','divide_temp_variable') for k,o,v in walk(accrual)),'No hourly rounded tiny currency division')
check('global.eon_energy_invoice_gwh' in str(accrual),'Hourly interval accumulates actual physical GWh')
settle=effects['eon_energy_settlement_settle_world']
check([k for k,o,v in settle]==['eon_energy_settlement_prepare_accounts','every_country','for_each_loop','eon_energy_settlement_release_paid_claims'],'Freeze all cash then all debit, then receipts')
check([k for k,o,v in effects['eon_energy_settlement_release_paid_claims']]==['eon_energy_settlement_prepare_accounts','eon_energy_settlement_prepare_receipts','every_country','eon_energy_settlement_update_status'],'Cash-backed claim release snapshots receipt headroom')
check(source.count('subtract_from_variable = { treasury = eon_es_payment }')==1,'One energy cash debit primitive')
check(source.count('add_to_variable = { treasury = eon_es_receipt }')==1,'One energy cash credit primitive')
check('add_political_power' not in source and 'treasury_change' not in source,'No PP or hidden treasury_change substitutes cash')
check('pay_ratio' not in source and 'receipt_ratio' not in source,'No near-zero cash/debt or headroom/claim stored ratio')
check('divide_temp_variable = { eon_es_pay_target = eon_energy_settlement_pay_divisor }' in source,'Cumulative invoice target uses reciprocal debt/cash divisor')
check('divide_temp_variable = { eon_es_receipt_target = eon_energy_settlement_receipt_divisor }' in source,'Cumulative paid-claim target uses reciprocal claim/headroom divisor')
check('eon_es_processed_due = eon_energy_settlement_payable' in source and 'eon_es_pay_target = eon_energy_settlement_cash_snapshot' in source,'Final buyer quota uses frozen available cash directly')
check('eon_es_processed_claim = eon_energy_settlement_paid_claim' in source and 'eon_es_receipt_target = eon_energy_settlement_receipt_budget' in source,'Final seller quota uses separate frozen headroom budget')
for key,op,value in walk(ast(source)):
    if key in ('add_to_variable','subtract_from_variable','multiply_variable','divide_variable',
               'add_to_temp_variable','subtract_from_temp_variable','multiply_temp_variable','divide_temp_variable'):
        check('global.date' not in str(value),'No undocumented date arithmetic')
queue=effects['eon_energy_settlement_queue_clock']
calls=[v for k,o,v in walk(queue) if k=='country_event']
check(len(calls)==1 and one(calls[0],'hours')=='1' and one(calls[0],'id')=='eon_energy_settlement.100','Native numeric ID one-hour clock queue')
check(not any(k in ('days','random','random_hours','random_days') for k,o,v in walk(queue)),'No variable/random timer delays')
clock=next(v for k,o,v in ast(read(NEW[5])) if k=='country_event' and one(v,'id')=='eon_energy_settlement.100')
check(one(clock,'hidden')==one(clock,'is_triggered_only')=='yes','Clock hidden and triggered-only')
check('is_debug' in str(clock) and 'EON_ES_CLOCK' in str(clock),'Developer-only native clock diagnostic')
probe=[v for k,o,v in one(clock,'immediate') if k=='if' and 'EON_ES_NUMERIC' in str(v)]
check(len(probe)==1,'One developer numeric calibration branch')
check('is_debug' in str(one(probe[0],'limit')) and 'eon_energy_settlement_numeric_probe' in str(one(probe[0],'limit')),'Numeric calibration is debug-only and once')
check(all(k in ('limit','set_global_flag','set_temp_variable','multiply_temp_variable','divide_temp_variable','log') for k,o,v in probe[0]),'Calibration cannot mutate ledger, treasury, contracts or daily latch')
check('eon_energy_settlement_last_queue_epoch' in str(queue) and 'global.eon_energy_settlement_anchor_epoch' in str(effects['eon_energy_settlement_activate_clock']),'Fresh timer ownership epoch defeats stale same-hour country queue latch')
check('eon_energy_delivery_reconcile_world' not in str(clock),'No world64-round dispatch on hourly clock')
events=[v for k,o,v in ast(read(NEW[5])) if k=='country_event']
ids=[one(v,'id') for v in events]
check(len(set(ids))==len(ids)==6 and all(re.fullmatch(r'eon_energy_settlement\.\d+',i) for i in ids),'Distinct numeric event IDs')
for event in events[1:]:
    check(all([k for k,o,v in opt]==['name'] for key,op,opt in event if key=='option'),'Informational options grant no assets')
decisions=one(ast(read(NEW[4])),'eon_energy_settlement_category')
for key,op,decision in decisions:
    check(one(decision,'cost')=='0',key+' no PP cost')
    check(one(one(decision,'ai_will_do'),'factor')=='0',key+' manual UI only; automatic cash is separate')
keys=[]
for lang in ('english','russian'):
    text=read(f'localisation/{lang}/eon_energy_settlement_l_{lang}.yml')
    found=re.findall(r'^ ([^ :]+):',text,re.M)
    check(len(found)==len(set(found)),lang+' no duplicate localization IDs')
    check('???' not in text,lang+' no damaged literal Unicode')
    keys.append(set(found))
check(keys[0]==keys[1] and len(keys[0])==20,'EN/RU complete matching localization keys')
check('eon_energy_settlement.1.gap' in read(NEW[5]),'Unknown-time accounting gap is visible to players')
docs=Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation')
e=(docs/'effects_documentation.md').read_text(encoding='utf-8-sig')
d=(docs/'dynamic_variables_documentation.md').read_text(encoding='utf-8-sig')
c=(docs/'script_concept_documentation.md').read_text(encoding='utf-8-sig')
check('country_event' in e and 'hours' in e,'Installed primary native timer API exists')
check('date' in d and 'num_days' in d,'Installed primary date/day variables exist; no hourly units inferred')
check('fixed point arithmetic' in c,'Installed primary math expressions fixed-point, legacy variable precision not inferred')
if __name__=='__main__':
    print(json.dumps({'checks_passed':True,'checks':checks,'baseline':BASELINE,
      'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in CHANGED+list(SCOPE_REPAIRS)+NEW},
      'proof_scope':'exact owned-byte hooks, actual ledger/cash barrier, API/grammar/localization',
      'native_clock_or_campaign_proven':False},indent=2))
