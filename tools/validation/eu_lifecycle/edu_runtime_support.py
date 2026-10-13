"""V16 source-only EDU backend; historical raw-API fixture stays unchanged.

This builds text only. It cannot install, prepare or launch a native probe.
Exact source gates and complete_effect AST are separate from the terminal raw
API diagnostic; real faction formation, leave and leadership hooks stay strict.
"""
from pathlib import Path
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
import sys

import edu_support as LEGACY
import runtime_support as SHARED

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
SOURCE_METHOD='source complete_effect AST dispatched by event'
LEGACY_SHA256='1142f6728db40869b20fdd2e4e969f32ef1eb366ece649f73abaaa178ce91078'
GOLDEN41='a76c266c4c35fb0146d2fb80e36209d871efe0e5792082be1c423dc1af675896'
CANONICAL_NAMESPACE='eon_native_eu_probe'
CATEGORY_PATH='common/decisions/categories/EU_voting_categories.txt'
AI_PATHS=('common/decisions/eon_edu_decisions.txt','common/decisions/EU_voting_decisions.txt')
AI_IDS=('eon_edu_request_join','eon_edu_accept_request','eon_edu_reject_request',
        'eon_edu_withdraw_request','EU_create_EDU')
CALLS=(('EU_create_EDU','AUS',None,'positive'),
       ('eon_edu_request_join','SWE','AUS','positive'),
       ('eon_edu_accept_request','AUS','SWE','positive'),
       ('eon_edu_request_join','SWE','AUS','positive'),
       ('eon_edu_accept_request','AUS','SWE','positive'),
       ('eon_edu_request_join','FIN','AUS','positive'),
       ('eon_edu_reject_request','AUS','FIN','positive'),
       ('eon_edu_request_join','FIN','AUS','positive'),
       ('eon_edu_withdraw_request','FIN',None,'positive'),
       ('eon_edu_request_join','FIN','AUS','positive'),
       ('eon_edu_request_join','FIN','AUS','positive'),
       ('eon_edu_accept_request','AUS','FIN','positive'),
       ('EU_create_EDU','AUS',None,'explicit_negative'),
       ('EU_create_EDU','AUS',None,'explicit_negative'),
       ('EU_create_EDU','AUS',None,'positive'))
BASE_KEYS=('assertions','expectations','required_elapsed_game_time','required_observations','production_dependency_paths')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def render(nodes):
    return ' '.join(f'{key} {op} '+('{ '+render(value)+' }' if isinstance(value,list) else value) for key,op,value in nodes)


ADAPTER=r'''
    edu_runtime_actions=[]
    def activate(ident,target=None):
        sequence=len(edu_runtime_actions)+1
        expected_ident,actor,expected_target,mode=CALLS[sequence-1]
        assert (ident,target)==(expected_ident,expected_target),('Original EDU call sequence drift',sequence,ident,target)
        action=decisions[ident]
        category=categories['EU_defense_category' if ident=='EU_create_EDU' else 'EU_voting_category']
        gates=[]
        for key in ('allowed','visible'):
            gates.extend(next((v for k,o,v in category if k==key),[]))
        for key in ('allowed','visible','available','target_root_trigger','target_trigger'):
            gates.extend(next((v for k,o,v in action if k==key),[]))
        # Source omits cost. This adapter does not claim native UI default cost.
        assert not any(k in ('cost','custom_cost','custom_cost_trigger','custom_cost_text','cost_trigger') for k,o,v in action)
        context_gate=f'tag = {actor} '+cv('ROOT.id','THIS.id')
        if target:context_gate+=f'FROM = {{ tag = {target} }} '+cv('FROM.id',target+'.id')
        gate=render(gates)+' '+context_gate
        complete=one(action,'complete_effect')
        stamp=f'EDU_HANDLER_ACTION_{sequence:03d}_{ident.upper()}'
        saved=f'global.{namespace}_edu_handler_{sequence:03d}_'
        count=f'global.{namespace}_edu_handler_invocations'
        fields={'attempt':'eon_edu_creation_attempt_serial','request_round':'eon_edu_request_round',
                'request_instance':'eon_edu_request_instance','request_leader':'eon_edu_request_leader',
                'request_result':'eon_edu_request_result','member_instance':'eon_edu_member_instance'}
        def snapshot():return ''.join(setv(saved+k,v) for k,v in fields.items())
        def unchanged():return ''.join(cv(v,saved+k) for k,v in fields.items())
        def witness(stage):
            payload=f'actor=[?ROOT.id] scope=[?THIS.id] sender=[?FROM.id] expected_actor=[?{actor}.id] '
            if target:payload+=f'target=[?{target}.id] '
            payload+='method=source_complete_effect_AST_dispatched_by_event '
            payload+=f'gate=[?{saved}gate] handler_count=[?{count}] '
            payload+=' '.join(k+'=[?'+v+']' for k,v in fields.items())
            payload+=' instance=[?global.eon_edu_instance] generation=[?global.eon_edu_generation_counter]'
            return f'log = "{marker} TRACE {stamp}_{stage} {payload}" '
        text=setv(saved+'gate',0)+setv(saved+'count',count)+snapshot()
        text+='if = { limit = { '+gate+' } '+setv(saved+'gate',1)+' } '
        text+=witness('BEFORE_SOURCE_HANDLER')
        dispatch_gate=gate if mode=='positive' else context_gate
        text+='if = { limit = { '+dispatch_gate+' } '
        text+=f'log = "{marker} TRACE {stamp}_SOURCE_COMPLETE_AST_INVOKED" '
        text+=f'add_to_variable = {{ {count} = 1 }} '+render(complete)+' } '
        text+=witness('AFTER_SOURCE_HANDLER')
        text+=setv(saved+'expected_count',saved+'count')+f'add_to_variable = {{ {saved}expected_count = 1 }} '
        wanted=context_gate+cv(saved+'gate',1 if mode=='positive' else 0)+cv(count,saved+'expected_count')
        if ident=='EU_create_EDU':
            text+=setv(saved+'expected_attempt',saved+'attempt')+f'add_to_variable = {{ {saved}expected_attempt = 1 }} '
            wanted+=cv('eon_edu_creation_attempt_serial',saved+'expected_attempt')
        text+=check('runtime_'+stamp.lower()+'_exact_source_dispatch',wanted,
                    'Declared '+mode+' backend path has actual ROOT equal THIS and actual targeted FROM; exact source gates and one planned callback are observed without using a raw API result')
        edu_runtime_actions.append({'stamp':stamp,'decision':ident,'actor_tag':actor,'target_tag':target,
                                   'gate_mode':mode,'method':SOURCE_METHOD,'replay':sequence==2})
        if sequence==2:
            text+=setv(saved+'expected_round',saved+'request_round')+f'add_to_variable = {{ {saved}expected_round = 1 }} '
            text+=check('runtime_first_request_bound_round_and_instance',cv('eon_edu_request_round',saved+'expected_round')+
                        cv('eon_edu_request_instance','global.eon_edu_instance')+cv('eon_edu_request_leader','AUS.id')+'has_country_flag = eon_edu_request_deadline ',
                        'One exact source request increments its own round once and binds actual leader/current union with a positive deadline')
            text+=snapshot()+witness('BEFORE_SOURCE_REPLAY')
            text+=f'log = "{marker} TRACE {stamp}_EXPLICIT_NEGATIVE_SOURCE_REPLAY" '+render(complete)+' '
            text+=witness('AFTER_SOURCE_REPLAY')
            text+=check('runtime_first_request_source_replay_inert',unchanged()+cv(count,saved+'expected_count')+'has_country_flag = eon_edu_request_deadline ',
                        'Repeated exact request callback cannot renew or duplicate an already active bound request')
        return text
'''


def build_edu_runtime(namespace,marker,*,source=ROOT,terminal_effect=''):
    source=Path(source).resolve()
    assert SHARED.sha(HERE/'edu_support.py')==LEGACY_SHA256,'Historical EDU module changed'
    original=LEGACY.build_edu(namespace,marker,source=source)
    baseline={k:original[k] for k in BASE_KEYS}
    canonical=LEGACY.build_edu(CANONICAL_NAMESPACE,marker,source=source)
    assert fingerprint({k:canonical[k] for k in BASE_KEYS})==GOLDEN41,'Original41 contract drift'
    categories={k:v for k,o,v in LEGACY.ast((source/CATEGORY_PATH).read_text('utf-8-sig'))}
    code=(HERE/'edu_support.py').read_text('utf-8')
    begin=code.index('    def activate(ident,target=None):')
    end=code.index('    def seed(tag):',begin)
    code=code[:begin]+ADAPTER+'\n'+code[end:]
    old="body+=nato_control('nato_unchanged_after_leader_eu_exit')+schedule(B,3008); event(3007,body)"
    new="body+=nato_control('nato_unchanged_after_leader_eu_exit')+schedule(F,3062,1); event(3007,body)\n    event(3062,schedule(B,3008,1))"
    assert code.count(old)==1;code=code.replace(old,new)
    old="body+='clr_country_flag = eon_edu_request_cooldown '+activate('eon_edu_request_join',F)+schedule(F,3012); event(3011,body)"
    new="body+=schedule(F,3060,1); event(3011,body)\n    event(3060,schedule(B,3061,1))\n    body='clr_country_flag = eon_edu_request_cooldown '+activate('eon_edu_request_join',F)+schedule(F,3012); event(3061,body)"
    assert code.count(old)==1;code=code.replace(old,new)
    old="body+=nato_control('nato_unchanged_after_actual_archive')+obs('TERMINAL','instance=[?global.eon_edu_instance] counter=[?global.eon_edu_generation_counter]')+terminal_effect"
    new="""body+=nato_control('nato_unchanged_after_actual_archive')
    body+=setv('global.'+namespace+'_edu_raw_original_permission',0)
    body+='if = { limit = { has_rule = can_join_factions } '+setv('global.'+namespace+'_edu_raw_original_permission',1)+' } '
    body+='set_rule = { can_join_factions = no } '
    body+=bool_obs('RAW_NEGATIVE_SOURCE_AVAILABLE','eon_edu_founder_eligible = yes')
    raw_payload='actor=[?ROOT.id] scope=[?THIS.id] sender=[?FROM.id] expected_actor=[?AUS.id] attempt=[?eon_edu_creation_attempt_serial] generation=[?global.eon_edu_generation_counter] instance=[?global.eon_edu_instance] result=[?eon_edu_creation_result]'
    body+=f'log = "{marker} TRACE EDU_RAW_NEGATIVE_BEGIN {raw_payload}" '
    body+=f'log = "{marker} TRACE EDU_RAW_NEGATIVE_API_REQUESTED" activate_decision = EU_create_EDU '
    body+=f'log = "{marker} TRACE EDU_RAW_NEGATIVE_AFTER {raw_payload}" '
    body+=bool_obs('RAW_NEGATIVE_INTERFACE_ACTIVE','has_decision = EU_create_EDU')
    body+='if = { limit = { '+cv('global.'+namespace+'_edu_raw_original_permission',1)+' } set_rule = { can_join_factions = yes } } '
    body+=obs('TERMINAL','instance=[?global.eon_edu_instance] counter=[?global.eon_edu_generation_counter]')+terminal_effect"""
    assert code.count(old)==1;code=code.replace(old,new)
    old="definitions='add_namespace = '+namespace+'\\n'+''.join(events[n] for n in sorted(events))"
    new="assert len(edu_runtime_actions)==len(CALLS)\n    "+old+"\n    return_runtime_actions=edu_runtime_actions"
    assert code.count(old)==1;code=code.replace(old,new)
    old="'production_dependency_paths':list(SOURCE_PATHS),"
    new="'edu_source_handler_runtime_contract':{'schema':1,'method':SOURCE_METHOD,'positive_dispatch':'source-only; independent of raw API outcome','actions':return_runtime_actions},\n      "+old
    assert code.count(old)==1;code=code.replace(old,new)
    env={'__file__':str(HERE/'edu_support.py'),'__name__':'eon_edu_source_only_internal',
         'CALLS':CALLS,'categories':categories,'render':render,'SOURCE_METHOD':SOURCE_METHOD}
    exec(compile(code,str(HERE/'edu_support.py'),'exec'),env)
    module=env['build_edu'](namespace,marker,source=source,terminal_effect=terminal_effect)
    assert [n for n in module['assertions'] if n in original['assertions']]==original['assertions']
    assert all(module['expectations'][n]==v for n,v in original['expectations'].items())
    assert module['required_elapsed_game_time']==original['required_elapsed_game_time']
    # The obsolete no-copied-handler description belongs to the old method only.
    module['historical_contract']=module.pop('contract')
    module['historical_contract']['no_copied_complete_effect_or_create_helper']=True
    module['contract']={**module['historical_contract'],'kind':'source_only_edu_backend_and_actual_native_hook_coverage',
                        'no_copied_complete_effect_or_create_helper':False,'method':SOURCE_METHOD,
                        'historical_no_copied_handler_field_is_not_v16_method':True}
    module['baseline41_contract']=baseline
    module['baseline41_sha256']=fingerprint(baseline)
    module['baseline41_golden_sha256']=GOLDEN41
    module['baseline41_canonical_namespace']=CANONICAL_NAMESPACE
    module['method']=SOURCE_METHOD
    module['historical_expectations_notice']='Original41 descriptions naming activation APIs are preserved history. They do not establish v16 API clicks; v16 positive paths use exact source AST dispatch.'
    module['startup_effect']=f'set_variable = {{ global.{namespace}_edu_handler_invocations = 0 }} '
    module['production_dependency_paths'].append(CATEGORY_PATH)
    module['production_input_sha256'][CATEGORY_PATH]=SHARED.sha(source/CATEGORY_PATH)
    snapshots={}
    for path in AI_PATHS:
        for category,op,body in LEGACY.ast((source/path).read_text('utf-8-sig')):
            if not isinstance(body,list):continue
            for ident,op,action in body:
                if ident not in AI_IDS:continue
                snapshots[ident]={'path':path,'category':category,'category_ast':categories[category],
                                 'action_ast':action,'complete_effect':LEGACY.one(action,'complete_effect'),
                                 'cost_shape':'source omits cost/custom_cost; native UI cost not claimed'}
    assert set(snapshots)==set(AI_IDS)
    module['actual_source_callback_ast']=snapshots
    module['runtime_overrides']=[]
    for path in AI_PATHS:
        selected=[i for i in AI_IDS if snapshots[i]['path']==path]
        text=(source/path).read_bytes().decode('utf-8')
        overlay=SHARED.ai_weight_overlay(text,selected)
        LEGACY.ast(overlay)
        module['fixture_text'][path]=overlay
        module['runtime_overrides'].append({'corepath':path,'source_sha256':SHARED.sha(source/path),
          'runtime_override_sha256':hashlib.sha256(overlay.encode()).hexdigest(),'selected_ai_action_ids':selected})
    module['fixture_paths']=list(module['fixture_text'])
    module['fixture_text_sha256']={p:hashlib.sha256(t.encode()).hexdigest() for p,t in module['fixture_text'].items()}
    module['private_builder_sha256']={Path(__file__).name:SHARED.sha(Path(__file__)),
                                     'edu_support.py':LEGACY_SHA256,'runtime_support.py':SHARED.sha(HERE/'runtime_support.py')}
    module['edu_raw_api_diagnostic_contract']={
        'kind':'edu_explicit_negative_raw_api_characterization','diagnostic_only':True,
        'begin_trace':'EDU_RAW_NEGATIVE_BEGIN','requested_trace':'EDU_RAW_NEGATIVE_API_REQUESTED','after_trace':'EDU_RAW_NEGATIVE_AFTER',
        'available_observation':'EDU_RAW_NEGATIVE_SOURCE_AVAILABLE','interface_observation':'EDU_RAW_NEGATIVE_INTERFACE_ACTIVE',
        'actor_tag':'AUS','target_tag':None,'counter_fields':['attempt','generation','instance','result'],'expected_available':0,
        'limits':'Declared national joining prohibition; actual raw API counter delta is diagnostic and need not be zero.'}
    module['limits']=[module['historical_expectations_notice'],
      'Positive exact category/action gates bind real ROOT=THIS and targeted FROM; no raw API or adaptive fallback in positive source dispatch.',
      'Two explicit negative source callbacks bypass only frontend availability to test internal production rejection; actor/target context remains bound.',
      'Source omits cost/custom_cost; callback AST has no explicit political-power debit. Native UI cost and decision clicks are not tested.',
      'Fifteen source dispatches and one representative replay require actual log witnesses; original41 predicates and six clock minima remain unchanged.',
      'The separate terminal raw API diagnostic observes actual counter changes under a joining prohibition; no universal no-handler expectation.',
      'Two exact AI-only source overlays isolate the five declared EDU IDs; ordinary production source AI is unchanged.',
      'Actual native formation/leave/leadership hooks remain acceptance requirements. No campaign, native UI selection, multiplayer or save/reload proof.']
    return module


def _trace(text,marker,label,failures):
    matches=list(re.finditer(re.escape(marker+' TRACE '+label)+r'(?:[ \t]|$)([^\r\n]*)',text,re.M))
    if len(matches)!=1:
        failures.append({'missing_or_duplicate_edu_trace':label});return None,None
    pairs=re.findall(r'\b([a-z_]+)=([^\s]+)',matches[0][1]);values=dict(pairs)
    if len(pairs)!=len(values):failures.append({'duplicate_edu_trace_key':label})
    return values,matches[0].start()


def _number(value,*,integral=False,positive=False):
    assert re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',value)
    result=Decimal(value)
    assert result.is_finite() and result>=0 and (not positive or result>0)
    assert not integral or result==result.to_integral_value()
    return result


def edu_source_handler_callback_result(contract,text,marker,observation_lines=None):
    if not contract:return None
    actions=contract.get('actions',[]);failures=[];receipts=[]
    valid=(contract.get('schema')==1 and contract.get('method')==SOURCE_METHOD and isinstance(actions,list)
           and len(actions)==len(CALLS) and all(isinstance(a,dict) for a in actions))
    if not valid:return {'passed':False,'failures':[{'invalid_edu_source_action_contract':True}],'actions':[]}
    stamps=[a.get('stamp') for a in actions]
    valid=all(isinstance(s,str) for s in stamps) and len(set(stamps))==len(stamps)
    for index,(action,call) in enumerate(zip(actions,CALLS),1):
        ident,actor,target,mode=call
        valid=valid and action.get('stamp')==f'EDU_HANDLER_ACTION_{index:03d}_{ident.upper()}'
        valid=valid and all(action.get(k)==v for k,v in (('decision',ident),('actor_tag',actor),('target_tag',target),('gate_mode',mode),('method',SOURCE_METHOD),('replay',index==2)))
    if not valid:return {'passed':False,'failures':[{'invalid_edu_source_action_contract':True}],'actions':[]}
    integral=('gate','handler_count','attempt','request_round','request_result','request_instance','member_instance','instance','generation')
    numeric=integral+('request_leader',)
    for action in actions:
        start=len(failures);stamp=action['stamp']
        before,bp=_trace(text,marker,stamp+'_BEFORE_SOURCE_HANDLER',failures)
        _,ip=_trace(text,marker,stamp+'_SOURCE_COMPLETE_AST_INVOKED',failures)
        after,ap=_trace(text,marker,stamp+'_AFTER_SOURCE_HANDLER',failures)
        rows=[before,after];positions=[bp,ip,ap]
        if action['replay']:
            rb,rp=_trace(text,marker,stamp+'_BEFORE_SOURCE_REPLAY',failures)
            _,ri=_trace(text,marker,stamp+'_EXPLICIT_NEGATIVE_SOURCE_REPLAY',failures)
            ra,rq=_trace(text,marker,stamp+'_AFTER_SOURCE_REPLAY',failures)
            rows.extend((rb,ra));positions.extend((rp,ri,rq))
        if any(v is None for v in rows) or None in positions:
            receipts.append({'stamp':stamp,'passed':False});continue
        if positions!=sorted(positions) or len(set(positions))!=len(positions):failures.append({'edu_source_stage_order_invalid':stamp})
        try:
            actor=before['expected_actor'];_number(actor,positive=True)
            sender=before['sender'];_number(sender,positive=True)
            target=before.get('target')
            for values in rows:
                for key in ('actor','scope','sender','expected_actor'):_number(values[key],positive=True)
                assert values['actor']==values['scope']==values['expected_actor']==actor
                assert values['sender']==sender
                if action['target_tag']:
                    _number(values['target'],positive=True)
                    assert values['sender']==values['target']==target and Decimal(actor)!=Decimal(target)
                assert values['method']=='source_complete_effect_AST_dispatched_by_event'
                for key in numeric:values[key]=_number(values[key],integral=key in integral)
                assert values['gate']==(1 if action['gate_mode']=='positive' else 0)
            assert after['handler_count']==before['handler_count']+1
            if action['decision']=='EU_create_EDU':assert after['attempt']==before['attempt']+1
            if action['decision']=='eon_edu_request_join':
                assert after['request_round']==before['request_round']+1
                assert after['request_instance']==after['instance'] and after['instance']>0
                assert after['request_leader']==Decimal(target)
            if action['replay']:
                assert all(row[key]==after[key] for row in rows[2:] for key in numeric)
        except (AssertionError,KeyError,InvalidOperation,TypeError):failures.append({'edu_source_context_or_delta_invalid':stamp})
        receipts.append({'stamp':stamp,'decision':action['decision'],'gate_mode':action['gate_mode'],'passed':len(failures)==start,'method':SOURCE_METHOD})
    return {'passed':not failures,'failures':failures,'actions':receipts,'method':SOURCE_METHOD,
            'claims_excluded':['GUI click','Native UI cost','Native AI selection','Multiplayer','Raw API inferred as positive acceptance']}


def edu_raw_api_diagnostic_result(contract,text,marker,observation_lines=None):
    if not contract:return None
    failures=[];rows=[];positions=[];delta={}
    for key in ('begin_trace','requested_trace','after_trace'):
        values,pos=_trace(text,marker,contract[key],failures);rows.append(values);positions.append(pos)
    observed={}
    for key in ('available_observation','interface_observation'):
        matches=list(re.finditer(re.escape(marker+' OBS '+contract[key])+r' value=([01])(?:\s|$)',text))
        observed[key]=int(matches[0][1]) if len(matches)==1 else None
        if len(matches)!=1:failures.append({'missing_or_duplicate_edu_raw_observation':contract[key]})
    if observed['available_observation']!=0:failures.append({'edu_raw_context_not_negative':True})
    if None not in positions and not positions[0]<positions[1]<positions[2]:failures.append({'edu_raw_stage_order_invalid':True})
    before,_,after=rows
    try:
        for row in (before,after):
            for key in ('actor','scope','sender','expected_actor'):_number(row[key],positive=True)
            assert row['actor']==row['scope']==row['expected_actor']==row['sender']
        assert all(before[k]==after[k] for k in ('actor','scope','sender','expected_actor'))
        for key in contract['counter_fields']:delta[key]=str(_number(after[key])-_number(before[key]))
    except (AssertionError,KeyError,InvalidOperation,TypeError):failures.append({'edu_raw_context_invalid':True})
    return {'diagnostic_only':True,'controls_valid':not failures,'failures':failures,'actual_counter_delta':delta,
            'interface_active':observed['interface_observation'],'claims_excluded':['GUI click','API universal no-op','Positive backend inferred from API']}
