"""V16 source-only extension backend; frozen v15 API receipts stay distinct."""
from pathlib import Path
import hashlib
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
import runtime_support as V15

SOURCE_METHOD=V15.SOURCE_METHOD
V15_SHA256='fa5265d787c44d8f6e378977a11c48a44650a296f67c7e61e5ffb644afc28eb0'

# Derive only observation waits after the frozen original114 contract check.
# Native mission callbacks are day-quantized; the tested minima stay24/48h.
WAIT_CHECKPOINT_DERIVATION=r'''
    for old,new,expected_count in (
        ('final += schedule(LEAVER, base + 20, 30)',
         'final += schedule(LEAVER, base + 20, 49 if kind in ("short", "both") else 30)',1),
        ('start += calibrate_clock(name, kind) + schedule(LEAVER, base + 20, 30)',
         'start += calibrate_clock(name, kind) + schedule(LEAVER, base + 20, 49 if kind in ("short", "both") else 30)',1),
        ('first += schedule(LEAVER, base + 30, 30)',
         'first += schedule(LEAVER, base + 30, 49 if kind == "main" else 25 if kind in ("short", "both") else 30)',2),
    ):
        assert code.count(old)==expected_count,'Frozen wait-checkpoint derivation changed'
        code=code.replace(old,new)
'''


def build_extension_source(namespace,marker,*,source=ROOT,terminal_effect=''):
    assert V15.sha(HERE/'runtime_support.py')==V15_SHA256,'Frozen v15 source changed'
    adapter=V15.ADAPTER
    # Installed native decision sources use strict scalar '<'. Keep the
    # inclusive zero-cost boundary without the unsupported scalar '>=' token.
    old_cost_gate="        gates.append(('has_political_power', '>=', '0'))"
    new_cost_gate="        gates.append(('NOT', '=', [('has_political_power', '<', '0')]))"
    assert adapter.count(old_cost_gate)==1,'Frozen cost-guard derivation changed'
    adapter=adapter.replace(old_cost_gate,new_cost_gate)
    begin=adapter.index("        text += witness('BEFORE_API')")
    end=adapter.index('        # Treaty identity',begin)
    adapter=adapter[:begin]+adapter[end:]
    assert 'activate_decision' not in adapter[adapter.index('        text = snapshot()'):]
    extra=V15.EXTRA
    old='    final += terminal_effect\n    event(2410,final)'
    assert extra.count(old)==1
    extra=extra.replace(old,'''    final += schedule('GER',2430,2)
    event(2410,final)
    raw = 'log = "'+marker+' TRACE EXTENSION_RAW_NEGATIVE_BEGIN actor=[?ROOT.id] scope=[?THIS.id] sender=[?FROM.id] target=[?POL.id] expected_actor=[?GER.id] answer=[?POL.eon_eu_extension_answer_count] queue=[?POL.eon_eu_extension_queued_units]" '
    raw += bool_observation('RAW_NEGATIVE_SOURCE_AVAILABLE','eon_eu_extension_can_approve = yes')
    raw += 'log = "'+marker+' TRACE EXTENSION_RAW_NEGATIVE_API_REQUESTED" activate_targeted_decision = { target = POL decision = eon_eu_extension_approve } '
    raw += 'log = "'+marker+' TRACE EXTENSION_RAW_NEGATIVE_AFTER actor=[?ROOT.id] scope=[?THIS.id] sender=[?FROM.id] target=[?POL.id] expected_actor=[?GER.id] answer=[?POL.eon_eu_extension_answer_count] queue=[?POL.eon_eu_extension_queued_units]" '
    raw += bool_observation('RAW_NEGATIVE_INTERFACE_ACTIVE','has_decision = eon_eu_extension_approve')
    raw += terminal_effect
    event(2430,raw)''')
    code=(HERE/'runtime_support.py').read_text('utf-8')
    a,b=code.index("ADAPTER = r'''"),code.index("EXTRA = r'''")
    code=code[:a]+'ADAPTER = '+repr(adapter)+'\n\n'+code[b:]
    a,b=code.index("EXTRA = r'''"),code.index('\n\ndef sha(')
    code=code[:a]+'EXTRA = '+repr(extra)+'\n'+code[b:]
    contract_guard="    assert hashlib.sha256(json.dumps(original_contract,sort_keys=True,separators=(',',':')).encode()).hexdigest() == GOLDEN114\n"
    assert code.count(contract_guard)==1,'Frozen original114 contract guard changed'
    code=code.replace(contract_guard,contract_guard+WAIT_CHECKPOINT_DERIVATION,1)
    environment={'__file__':str(HERE/'runtime_support.py'),'__name__':'eon_extension_source_only_internal'}
    exec(compile(code,str(HERE/'runtime_support.py'),'exec'),environment)
    module=environment['build_runtime'](namespace,marker,source=source,terminal_effect=terminal_effect)
    module['source_handler_runtime_contract']['positive_dispatch']='source-only; independent of raw API outcome'
    module['raw_api_diagnostic_contract']={
        'kind':'extension_explicit_negative_raw_api_characterization','diagnostic_only':True,
        'begin_trace':'EXTENSION_RAW_NEGATIVE_BEGIN','requested_trace':'EXTENSION_RAW_NEGATIVE_API_REQUESTED',
        'after_trace':'EXTENSION_RAW_NEGATIVE_AFTER','available_observation':'EXTENSION_RAW_NEGATIVE_SOURCE_AVAILABLE',
        'interface_observation':'EXTENSION_RAW_NEGATIVE_INTERFACE_ACTIVE','actor_tag':'GER','target_tag':'POL',
        'counter_fields':['answer','queue'],'expected_available':0,
        'limits':'Observe actual API delta in a closed proposal. No universal no-handler expectation or decision-click acceptance.'}
    module['historical_expectations_notice']='Original114 descriptions may name old activation APIs. Predicates/expectations/clocks are historical and unchanged; v16 evidence method is source complete_effect AST dispatched by event.'
    module['limits']=[
        'Positive backend paths dispatch exact source complete_effect AST only under source gates. No raw API is used in a positive dispatch or as an adaptive fallback.',
        'Raw targeted API is characterized separately after cleanup in a declared negative context. Its actual counter delta is diagnostic, not universally required to be zero.',
        module['historical_expectations_notice'],
        'Two explicitly bound AI-only runtime overlays isolate eight selected IDs; ordinary production AI is unchanged.',
        'Actual ROOT/THIS/FROM, exact response delta1, canonical project/treaty identity and direct replay controls remain required.',
        'Natural1/2-day minima require actual engine dates; no GUI click, native AI selection, multiplayer, save/reload or long-campaign acceptance.'
    ]
    module['private_builder_sha256'][Path(__file__).name]=V15.sha(Path(__file__))
    return module


def source_handler_callback_result(contract,text,marker,observation_lines=None):
    """Require four actual source-only stages; never synthesize API evidence."""
    from decimal import Decimal,InvalidOperation
    if not contract:return None
    failures=[];receipts=[]
    if contract.get('schema')!=1 or contract.get('method')!=SOURCE_METHOD or not contract.get('actions'):
        return {'passed':False,'failures':[{'invalid_source_only_contract':True}],'actions':[]}
    actions=contract['actions']
    if not isinstance(actions,list) or not all(isinstance(a,dict) for a in actions):
        return {'passed':False,'failures':[{'invalid_source_only_action_contract':True}],'actions':[]}
    stamps=[a.get('stamp') for a in actions]
    kinds={'eon_eu_extension_approve':('approvals','yes'),'eon_eu_extension_reject':('rejections','no'),
           'eon_eu_extension_abstain':('abstentions','abstain')}
    if (any(not isinstance(s,str) or not re.fullmatch(r'HANDLER_ACTION_\d{3}_[A-Z_]+',s) for s in stamps) or len(stamps)!=len(set(stamps))
            or any(a.get('method')!=SOURCE_METHOD or a.get('actor_tag') not in ('GER','FRA','ITA','HOL','SPR','CZE')
                   or a.get('target_tag')!='POL' or kinds.get(a.get('decision'))!=(a.get('increment_array'),a.get('increment_counter')) for a in actions)):
        return {'passed':False,'failures':[{'invalid_source_only_action_contract':True}],'actions':[]}
    delta_fields=('answer','yes','no','abstain','approvals','rejections','abstentions')
    identity_fields=('queue','notice','project','project_notice','electorate','treaty','treaty_proposal')
    number_fields=delta_fields+identity_fields+('gate','handler_count')
    tokens=('actor','scope','sender','target','expected_actor')
    def row(label,context=True):
        matches=list(re.finditer(re.escape(marker+' TRACE '+label)+r'(?:[ \t]|$)([^\r\n]*)',text,re.M))
        if len(matches)!=1:
            failures.append({'source_only_missing_or_duplicate_trace':label});return None,None
        pairs=re.findall(r'\b([a-z_]+)=([^\s]+)',matches[0][1]);values=dict(pairs)
        if len(pairs)!=len(values):failures.append({'source_only_duplicate_payload_key':label})
        if not context:return values,matches[0].start()
        try:
            for key in number_fields:
                value=Decimal(values[key]);assert value.is_finite() and value>=0 and value==value.to_integral_value()
                values[key]=int(value)
            for key in tokens:
                assert re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',values[key]) and Decimal(values[key]).is_finite() and Decimal(values[key])>0
            assert values['method']=='source_complete_effect_AST_dispatched_by_event'
        except (KeyError,AssertionError,InvalidOperation):
            failures.append({'source_only_invalid_context':label});return None,matches[0].start()
        return values,matches[0].start()
    for action in contract['actions']:
        initial=len(failures)
        stamp=action['stamp']
        rows=[row(stamp+'_'+s) for s in ('BEFORE_EXPLICIT_HANDLER','AFTER_EXPLICIT_HANDLER','BEFORE_DIRECT_REPLAY','AFTER_DIRECT_REPLAY')]
        _,invoke=row(stamp+'_SOURCE_COMPLETE_AST_INVOKED',False)
        _,repeat=row(stamp+'_EXPLICIT_NEGATIVE_DIRECT_REPLAY',False)
        if any(v is None for v,p in rows) or invoke is None or repeat is None:
            receipts.append({'stamp':stamp,'passed':False});continue
        (before,bp),(after,ap),(replay_before,rbp),(replay_after,rap)=rows
        if not bp<invoke<ap<rbp<repeat<rap:failures.append({'source_only_stage_order_invalid':stamp})
        actor,target=before['expected_actor'],before['target']
        if Decimal(actor)==Decimal(target):failures.append({'source_only_country_identity_invalid':stamp})
        for values,p in rows:
            if any(values[k]!=v for k,v in (('actor',actor),('scope',actor),('expected_actor',actor),('sender',target),('target',target))):
                failures.append({'source_only_country_context_changed':stamp})
            if (values['gate']!=1 or values['queue']!=0 or values['notice']<=0 or values['project']<=0
                    or values['project_notice']!=values['notice'] or values['electorate']!=6
                    or values['treaty'] not in (0,1) or values['treaty_proposal'] not in (0,1)):
                failures.append({'source_only_not_current_canonical_round':stamp})
            if any(values[k]!=before[k] for k in identity_fields):failures.append({'source_only_canonical_identity_changed':stamp})
        wanted=dict.fromkeys(delta_fields,0)
        wanted['answer']=wanted[action['increment_array']]=wanted[action['increment_counter']]=1
        delta={k:after[k]-before[k] for k in delta_fields}
        if delta!=wanted or after['handler_count']!=before['handler_count']+1:
            failures.append({'source_only_explicit_delta_not_one':stamp,'delta':delta})
        if any(v[k]!=after[k] for v in (replay_before,replay_after) for k in number_fields):
            failures.append({'source_only_direct_replay_changed_ledger':stamp})
        if re.search(re.escape(marker+' TRACE '+stamp+'_RAW_UI_ACTIVATION_REQUESTED')+r'(?:\s|$)',text):
            failures.append({'raw_api_in_positive_source_dispatch':stamp})
        receipts.append({'stamp':stamp,'passed':len(failures)==initial,'decision':action['decision'],'actor_tag':action['actor_tag'],
                         'target_tag':action['target_tag'],'explicit_delta':delta,'method':SOURCE_METHOD})
    return {'passed':not failures,'failures':failures,'actions':receipts,'method':SOURCE_METHOD,
            'positive_dispatch':'Source-only; no API observations synthesized as evidence',
            'claims_excluded':['GUI click','Native AI selection','Multiplayer','Raw API inferred as positive backend acceptance']}


def raw_api_diagnostic_result(contract,text,marker,observation_lines=None):
    """Characterize a negative-context API without asserting a zero delta."""
    from decimal import Decimal,InvalidOperation
    if not contract:return None
    failures=[];rows=[];positions=[]
    for field in ('begin_trace','requested_trace','after_trace'):
        label=contract[field]
        matches=list(re.finditer(re.escape(marker+' TRACE '+label)+r'(?:[ \t]|$)([^\r\n]*)',text,re.M))
        if len(matches)!=1:
            failures.append({'missing_or_duplicate_raw_diagnostic_trace':label});rows.append({});positions.append(None)
        else:
            rows.append(dict(re.findall(r'\b([a-z_]+)=([^\s]+)',matches[0][1])));positions.append(matches[0].start())
    values={}
    for field in ('available_observation','interface_observation'):
        label=contract[field]
        matches=list(re.finditer(re.escape(marker+' OBS '+label)+r' value=([01])(?:\s|$)',text))
        values[field]=int(matches[0][1]) if len(matches)==1 else None
        if len(matches)!=1:failures.append({'missing_or_duplicate_raw_diagnostic_observation':label})
    if values['available_observation']!=contract['expected_available']:
        failures.append({'raw_diagnostic_not_explicit_negative':True})
    if None not in positions and not positions[0]<positions[1]<positions[2]:failures.append({'raw_diagnostic_order_invalid':True})
    before,_,after=rows;delta={}
    try:
        for row in (before,after):
            for key in ('actor','scope','sender','target','expected_actor'):
                assert re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',row[key]) and Decimal(row[key]).is_finite() and Decimal(row[key])>0
            assert row['actor']==row['scope']==row['expected_actor'] and row['sender']==row['target'] and Decimal(row['actor'])!=Decimal(row['target'])
        assert all(before[k]==after[k] for k in ('actor','scope','sender','target','expected_actor'))
        for key in contract['counter_fields']:
            a,b=Decimal(before[key]),Decimal(after[key]);assert a.is_finite() and b.is_finite()
            delta[key]=str(b-a)
    except (KeyError,AssertionError,InvalidOperation):failures.append({'raw_diagnostic_context_invalid':True})
    return {'diagnostic_only':True,'controls_valid':not failures,'failures':failures,'actual_counter_delta':delta,
            'interface_active':values['interface_observation'],'claims_excluded':['GUI click','API universal no-op','Positive backend result inferred from API']}


build_source_runtime=build_extension_source
