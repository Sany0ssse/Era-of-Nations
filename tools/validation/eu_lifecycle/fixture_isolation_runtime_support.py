"""Current V18 fixture isolation; V16/V17 evidence remains immutable history.

Only produces/validates private source-bound fixtures. Never installs or runs.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import re
from decimal import Decimal,InvalidOperation

import edu_confirmation_runtime_support as V17
import extension_source_runtime_support as EXT

ROOT=Path(__file__).resolve().parents[3]
METHOD=V17.METHOD
REMOVE_LABEL='edu_verified_leader_scoped_remove_has_isolated_native_cleanup'
LEGACY_REMOVE='edu_scripted_remove_fires_real_leave_cleanup'
CLEANUP_STAMPS=('HANDLER_ACTION_001_EON_EU_REVOKE_WITHDRAWAL',
                'HANDLER_ACTION_055_EON_EU_REVOKE_WITHDRAWAL')
REMOVAL_FRAMES=('EDU_RAW_REMOVAL_ONLY_BEFORE','EDU_RAW_REMOVAL_ONLY_AFTER',
                'EDU_RAW_REMOVAL_ONLY_BEFORE_UNRELATED_CREATE')


def cv(name,value,compare='equals'):
    return f'check_variable = {{ var = {name} value = {value} compare = {compare} }} '


def scope(tag,body):return f'{tag} = {{ {body} }} '


def removal_expectation(namespace):
    p=f'global.{namespace}_edu_'
    return {'predicate':scope('SWE','is_in_faction = no '+cv('eon_edu_leave_hook_serial',p+'candidate_leave_before','greater_than')+
                    cv('eon_edu_member_instance',0)+cv('eon_edu_constructor_confirmed_instance',0)+
                    'NOT = { eon_edu_is_confirmed_member = yes } ')+scope('AUS','is_faction_leader = yes eon_edu_is_confirmed_member = yes '),
            'expected':'Actual leader-scoped raw removal leaves SWE factionless with native leave cleanup and both cohort receipts cleared before any unrelated creation.'}


def removal_contract():
    return {'schema':1,'kind':'actual_leader_scoped_raw_removal_before_unrelated_creation',
              'assertion':REMOVE_LABEL,'historical_assertion':LEGACY_REMOVE,'frames':list(REMOVAL_FRAMES),
              'removal_actor':'AUS','target':'SWE','removal_event':3003,'cleanup_event':3004,
              'source_input':'AUS = { remove_from_faction = SWE }',
              'forbidden_before_isolated_assertion':['create_faction','dismantle_faction']}


def cleanup_contract():
    return {'schema':1,'kind':'always_emitted_original_condition_gated_cleanup','actions':[
        {'stamp':stamp,'original_condition':'has_country_flag = Article_50',
         'condition_observation':'EXTENSION_CLEANUP_'+stamp.removeprefix('HANDLER_')+'_ORIGINAL_CONDITION',
         'before_trace':stamp+'_BEFORE_EXPLICIT_HANDLER','after_trace':stamp+'_AFTER_EXPLICIT_HANDLER',
         'invoke_trace':stamp+'_SOURCE_COMPLETE_AST_INVOKED'} for stamp in CLEANUP_STAMPS]}


def render(nodes):
    def value(v):
        if isinstance(v,list):return '{ '+render(v)+' }'
        return json.dumps(v) if any(c.isspace() for c in v) or '"' in v else v
    return ' '.join(value(v) if k=='__item__' else f'{k} {o} {value(v)}' for k,o,v in nodes)+' '


def brace_end(text,begin):
    depth=0;quoted=escaped=comment=False
    for i in range(begin,len(text)):
        c=text[i]
        if comment:
            if c in '\r\n':comment=False
        elif quoted:
            if escaped:escaped=False
            elif c=='\\':escaped=True
            elif c=='"':quoted=False
        elif c=='#':comment=True
        elif c=='"':quoted=True
        elif c=='{':depth+=1
        elif c=='}':
            depth-=1
            if depth==0:return i
    raise AssertionError('Unclosed fixture block')


def seal(module):
    module['fixture_text_sha256']={p:hashlib.sha256(t.encode()).hexdigest() for p,t in module['fixture_text'].items()}
    module['private_builder_sha256'][Path(__file__).name]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return module


def event_bodies(module,namespace):
    return {next(v for k,o,v in fields if k=='id'):next(v for k,o,v in fields if k=='immediate')
            for key,op,fields in V17.V16.LEGACY.ast(module['fixture_text'][f'events/{namespace}.txt']) if key=='country_event'}


def walk(nodes):
    for k,o,v in nodes:
        yield k,o,v
        if isinstance(v,list):yield from walk(v)


def validate_removal_fixture(module,namespace,marker):
    events=event_bodies(module,namespace);before=events[namespace+'.3003'];after=events[namespace+'.3004']
    assert not any(k in ('create_faction','dismantle_faction') for k,o,v in walk(before))
    removals=[(k,v) for k,o,v in before if isinstance(v,list) and any(n=='remove_from_faction' for n,_,_ in v)]
    assert removals==[('AUS',[('remove_from_faction','=','SWE')])],'Only actual leader may remove the exact target'
    end=next(i for i,(k,o,v) in enumerate(after) if k=='log' and v==marker+' END '+REMOVE_LABEL)
    legacy=next(i for i,(k,o,v) in enumerate(after) if k=='log' and v==marker+' BEGIN '+LEGACY_REMOVE)
    creations=[i for i,(k,o,v) in enumerate(after) if isinstance(v,list) and any(n=='create_faction' for n,_,_ in v)]
    assert len(creations)==1 and end<creations[0]<legacy
    assert not any(k in ('create_faction','dismantle_faction') for k,o,v in walk(after[:end+1]))
    assert module['expectations'][REMOVE_LABEL]==removal_expectation(namespace)
    assert module['edu_removal_isolation_contract']==removal_contract()


def validate_cleanup_fixture(module,namespace,marker):
    events=event_bodies(module,namespace)
    for ident,num,stamp in ((7401,1,CLEANUP_STAMPS[0]),(7448,55,CLEANUP_STAMPS[1])):
        body=events[namespace+'.'+str(ident)];gated=[]
        for key,op,value in body:
            if key!='if' or not isinstance(value,list):continue
            is_gate=any(k=='set_variable' and any(n==f'global.{namespace}_handler_{num:03d}_gate' and x=='1' for n,o,x in v) for k,o,v in value if isinstance(v,list))
            is_handler=any(k=='log' and v==marker+' TRACE '+stamp+'_SOURCE_COMPLETE_AST_INVOKED' for k,o,v in value)
            if is_gate or is_handler:gated.append(value)
        assert len(gated)==2
        for value in gated:assert ('has_country_flag','=','Article_50') in next(v for k,o,v in value if k=='limit')
        top_logs=[v for k,o,v in body if k=='log']
        for suffix in ('planned_or_untaken_dispatch_count','revocation_cleans_consumed_or_pending_notice'):
            label='extension_runtime_'+stamp.removeprefix('HANDLER_').lower()+'_'+suffix
            assert marker+' BEGIN '+label in top_logs and marker+' END '+label in top_logs
    assert module['extension_cleanup_dispatch_contract']==cleanup_contract()


def build_edu_isolated(namespace,marker,*,source=ROOT,terminal_effect=''):
    original=V17.build_edu_confirmation(namespace,marker,source=source,terminal_effect=terminal_effect)
    module=deepcopy(original);path=f'events/{namespace}.txt';text=module['fixture_text'][path]
    p=f'global.{namespace}_edu_';w=f'global.{namespace}_removal_'
    def frame(label):
        flags={'leader':'AUS = { is_faction_leader = yes }',
               'shared':'SWE = { is_in_faction_with = AUS }',
               'factionless':'SWE = { is_in_faction = no }',
               'confirmed':'SWE = { eon_edu_is_confirmed_member = yes }'}
        body=''
        for key,predicate in flags.items():
            body+=f'set_variable = {{ {w}{key} = 0 }} if = {{ limit = {{ {predicate} }} set_variable = {{ {w}{key} = 1 }} }} '
        body+=f'log = "{marker} TRACE {label} actor=[?ROOT.id] scope=[?THIS.id] expected_actor=[?AUS.id] target=[?SWE.id] leader=[?{w}leader] shared=[?{w}shared] factionless=[?{w}factionless] confirmed=[?{w}confirmed] member=[?SWE.eon_edu_member_instance] return_receipt=[?SWE.eon_edu_constructor_confirmed_instance] leave=[?SWE.eon_edu_leave_hook_serial] leave_before=[?{p}candidate_leave_before]" '
        return body
    matches=list(re.finditer(r'SWE\s*=\s*\{\s*remove_from_faction\s*=\s*THIS\s+create_faction\s*=\s*"Private EDU unrelated control"\s*\}\s*',text))
    assert len(matches)==1,'Historical combined removal/create input changed'
    old=matches[0][0]
    text=text.replace(old,frame(REMOVAL_FRAMES[0])+'AUS = { remove_from_faction = SWE } '+frame(REMOVAL_FRAMES[1]),1)
    expectation=removal_expectation(namespace);predicate=expectation['predicate']
    block=(f'log = "{marker} BEGIN {REMOVE_LABEL}" if = {{ limit = {{ {predicate} }} '
           f'log = "{marker} PASS {REMOVE_LABEL}" add_to_variable = {{ global.{namespace}_passes = 1 }} }} '
           f'else = {{ log = "{marker} FAIL {REMOVE_LABEL}" add_to_variable = {{ global.{namespace}_fails = 1 }} }} '
           f'log = "{marker} END {REMOVE_LABEL}" ')
    boundary=f'log = "{marker} BEGIN {LEGACY_REMOVE}" '
    assert text.count(boundary)==1
    text=text.replace(boundary,frame(REMOVAL_FRAMES[2])+block+'SWE = { create_faction = "Private EDU unrelated control" } '+boundary,1)
    V17.V16.LEGACY.ast(text);module['fixture_text'][path]=text
    index=module['assertions'].index(LEGACY_REMOVE);module['assertions'].insert(index,REMOVE_LABEL)
    module['expectations'][REMOVE_LABEL]=expectation
    assert all(module['expectations'][label]==value for label,value in original['expectations'].items())
    module['edu_removal_isolation_contract']=removal_contract()
    module['method']=METHOD;module['contract']['method']=METHOD
    module['limits'].append('V18 adds one isolated raw-removal assertion before unrelated creation. All prior V17 predicates, two historical migrations, fifteen source handlers and six elapsed minima remain exact; no native hook is synthesized.')
    validate_removal_fixture(module,namespace,marker)
    return seal(module)


def build_extension_isolated(namespace,marker,*,source=ROOT,terminal_effect=''):
    original=EXT.build_source_runtime(namespace,marker,source=source,terminal_effect=terminal_effect)
    module=deepcopy(original);path=f'events/{namespace}.txt';text=module['fixture_text'][path];records=[]
    outer='if = { limit = { has_country_flag = Article_50 } '
    for stamp in CLEANUP_STAMPS:
        anchor=text.index(stamp+'_BEFORE_EXPLICIT_HANDLER')
        begin=text.rfind(outer,0,anchor);assert begin>=0,('Missing original conditional wrapper',stamp)
        end=brace_end(text,text.index('{',begin));old=text[begin:end+1]
        parsed=V17.V16.LEGACY.ast(old);assert len(parsed)==1 and parsed[0][0]=='if'
        nodes=parsed[0][2];assert nodes[0]==('limit','=',[('has_country_flag','=','Article_50')])
        nodes=deepcopy(nodes[1:]);gated=0
        for key,op,body in nodes:
            if key!='if' or not isinstance(body,list):continue
            is_gate=any(k=='set_variable' and any(n.endswith('_gate') and v=='1' for n,o,v in value) for k,o,value in body if isinstance(value,list))
            is_handler=any(k=='log' and value==marker+' TRACE '+stamp+'_SOURCE_COMPLETE_AST_INVOKED' for k,o,value in body)
            if is_gate or is_handler:
                limit=next(v for k,o,v in body if k=='limit');limit.insert(0,('has_country_flag','=','Article_50'));gated+=1
        assert gated==2,('Only source gate and source invocation receive original condition',stamp,gated)
        condition='EXTENSION_CLEANUP_'+stamp.removeprefix('HANDLER_')+'_ORIGINAL_CONDITION'
        condition_text=f'if = {{ limit = {{ has_country_flag = Article_50 }} log = "{marker} OBS {condition} value=1" }} else = {{ log = "{marker} OBS {condition} value=0" }} '
        text=text[:begin]+condition_text+render(nodes)+text[end+1:]
        records.append({'stamp':stamp,'original_condition':'has_country_flag = Article_50',
                        'condition_observation':condition,'before_trace':stamp+'_BEFORE_EXPLICIT_HANDLER',
                        'after_trace':stamp+'_AFTER_EXPLICIT_HANDLER','invoke_trace':stamp+'_SOURCE_COMPLETE_AST_INVOKED'})
        condition_position=text.index(marker+' OBS '+condition+' ')
        following=[(text.index(marker+' OBS '+label+' '),label) for label in original['required_observations']
                   if text.index(marker+' OBS '+label+' ')>condition_position]
        assert following,('Conditional receipt needs a following original clock witness',stamp)
        anchor=min(following)[1]
        for names in ('observations','required_observations'):
            if condition not in module[names]:module[names].insert(module[names].index(anchor),condition)
    module['fixture_text'][path]=text
    assert module['assertions']==original['assertions'] and module['expectations']==original['expectations']
    assert module['required_elapsed_game_time']==original['required_elapsed_game_time']
    assert records==cleanup_contract()['actions']
    module['extension_cleanup_dispatch_contract']=cleanup_contract()
    module['limits'].append('V18 always emits the four planned/untaken checks for two conditional cleanup adapters. Original Article50 condition still gates exact source invocation; untaken frames never manufacture cleanup or consent.')
    validate_cleanup_fixture(module,namespace,marker)
    return seal(module)


def unique_row(text,marker,kind,label):
    rows=list(re.finditer(re.escape(marker+' '+kind+' '+label)+r'(?:[ \t]|$)([^\r\n]*)',text,re.M))
    assert len(rows)==1,('Missing/duplicate isolation frame',label,len(rows))
    pairs=re.findall(r'\b([a-z_]+)=([^\s]+)',rows[0][1]);values=dict(pairs)
    assert len(values)==len(pairs),'Duplicate isolation field'
    return values,rows[0].start()


def integer(values,key):
    value=Decimal(values[key]);assert value.is_finite() and value>=0 and value==value.to_integral_value()
    return int(value)


def run_window(text,marker):
    positions=[]
    for token in ('RUN_BEGIN','RUN_END'):
        rows=list(re.finditer(re.escape(marker+' '+token)+r'(?:[ \t]|$)',text,re.M))
        assert len(rows)==1,('Require one run boundary',token)
        positions.append(rows[0].start())
    begin,end=positions
    assert begin<end
    return begin,end


def edu_removal_isolation_result(contract,text,marker):
    try:
        assert contract==removal_contract()
        rows=[unique_row(text,marker,'TRACE',label) for label in REMOVAL_FRAMES]
        begin,end=run_window(text,marker)
        (before,bp),(after,ap),(cleanup,cp)=rows
        _,passed=unique_row(text,marker,'PASS',REMOVE_LABEL)
        _,old=unique_row(text,marker,'BEGIN',LEGACY_REMOVE)
        assert begin<bp<ap<cp<passed<old<end,'Removal/check/create ordering invalid'
        actor,target=before['expected_actor'],before['target']
        assert Decimal(actor)>0 and Decimal(target)>0 and Decimal(actor)!=Decimal(target)
        for values,pos in rows:
            assert values['actor']==values['scope']==values['expected_actor']==actor and values['target']==target,'Wrong removal context'
            assert integer(values,'leader')==1
        assert integer(before,'shared')==integer(before,'confirmed')==1 and integer(before,'factionless')==0 and integer(before,'member')>0
        assert integer(after,'factionless')==1 and integer(after,'shared')==0,'Removal did not happen before unrelated creation'
        assert integer(cleanup,'factionless')==1 and integer(cleanup,'shared')==integer(cleanup,'confirmed')==0
        assert integer(cleanup,'member')==integer(cleanup,'return_receipt')==0
        assert integer(cleanup,'leave')>integer(before,'leave')==integer(cleanup,'leave_before')
        hooks=list(re.finditer(r'EON_EDU LEAVE_HOOK(?:[ \t]|$)([^\r\n]*)',text,re.M))
        matched=[h for h in hooks if bp<h.start()<cp and dict(re.findall(r'\b([a-z_]+)=([^\s]+)',h[1])).get('actor')==target
                 and dict(re.findall(r'\b([a-z_]+)=([^\s]+)',h[1])).get('scope')==target]
        assert len(matched)==1,'Require actual target native leave hook inside isolated removal window'
        return {'passed':True,'failures':[],'frames':[v for v,p in rows]}
    except (AssertionError,KeyError,TypeError,ValueError,InvalidOperation) as error:
        return {'passed':False,'failures':[{'invalid_isolated_raw_removal':str(error)}]}


def extension_cleanup_dispatch_result(contract,text,marker):
    try:
        assert contract==cleanup_contract()
        begin,end=run_window(text,marker)
        receipts=[]
        for action in contract['actions']:
            assert action['original_condition']=='has_country_flag = Article_50'
            condition,cp=unique_row(text,marker,'OBS',action['condition_observation'])
            before,bp=unique_row(text,marker,'TRACE',action['before_trace']);after,ap=unique_row(text,marker,'TRACE',action['after_trace'])
            assert begin<cp<bp<ap<end
            gate=integer(before,'gate');assert gate in (0,1) and integer(after,'gate')==gate
            assert integer(condition,'value') in (0,1) and (not gate or integer(condition,'value')==1)
            assert before['actor']==before['scope']==before['target']==before['expected_actor']
            assert all(before[k]==after[k] for k in ('actor','scope','target','expected_actor'))
            count=integer(after,'handler_count')-integer(before,'handler_count');assert count==gate
            if not gate:
                for key in ('answer','yes','no','abstain','approvals','rejections','abstentions','queue','notice','project','project_notice','electorate','treaty','treaty_proposal'):
                    assert integer(before,key)==integer(after,key),('Untaken cleanup changed canonical ledger',key)
            invokes=list(re.finditer(re.escape(marker+' TRACE '+action['invoke_trace'])+r'(?:[ \t]|$)',text,re.M))
            assert len(invokes)==gate and (not invokes or bp<invokes[0].start()<ap)
            for suffix in ('planned_or_untaken_dispatch_count','revocation_cleans_consumed_or_pending_notice'):
                label='extension_runtime_'+action['stamp'].removeprefix('HANDLER_').lower()+'_'+suffix
                _,p=unique_row(text,marker,'PASS',label);assert ap<p<end
            receipts.append({'stamp':action['stamp'],'taken':bool(gate),'original_condition':integer(condition,'value')})
        return {'passed':True,'failures':[],'actions':receipts}
    except (AssertionError,KeyError,TypeError,ValueError,InvalidOperation) as error:
        return {'passed':False,'failures':[{'invalid_conditional_cleanup_receipt':str(error)}]}
