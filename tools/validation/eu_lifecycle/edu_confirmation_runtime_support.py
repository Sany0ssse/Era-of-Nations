"""V17 source-confirmation evidence; V16 native-hook expectations stay history.

Only builds/validates fixtures. No install, launch, model hook or game mutation.
"""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import hashlib
import re

import edu_runtime_support as V16

ROOT=Path(__file__).resolve().parents[3]
METHOD='source complete_effect AST with actual constructor-return confirmation'
V16_SHA256='e0d224ac958de66112b9cdcf7a481fa243558192a3e1eaaabb07f0db4daa7451'
MIGRATION={
 'edu_actual_formed_hook_commits_after_decision':'edu_actual_creation_confirmation_commits_bound_instance',
 'edu_actual_native_leadership_hook_reconciles':'edu_actual_leadership_transfer_preserves_confirmed_topology',
}


def migrated_expectations(expectations,namespace):
    first,second=MIGRATION
    first_predicate=expectations[first]['predicate']
    counter=f'check_variable = {{ var = eon_edu_formed_hook_serial value = global.{namespace}_edu_initial_formed compare = greater_than }} '
    assert first_predicate.count(counter)==1
    first_predicate=first_predicate.replace(counter,
      'check_variable = { var = eon_edu_confirmation_commit_serial value = 0 compare = greater_than } '
      'check_variable = { var = global.eon_edu_instance value = 0 compare = greater_than } ')
    second_predicate=expectations[second]['predicate']
    counter=f'check_variable = {{ var = eon_edu_leadership_hook_serial value = global.{namespace}_edu_leadership_before compare = greater_than }} '
    assert second_predicate.count(counter)==1
    second_predicate=second_predicate.replace(counter,'')
    return {first:{'predicate':first_predicate,'expected':'Actual constructor cycle confirms a positive bound instance, actual leader/member and result1; native formation delivery is observed separately.'},
             second:{'predicate':second_predicate,'expected':'Actual set_faction_leader preserves the current confirmed faction topology; native leadership dispatch is observed separately.'}}


def build_edu_confirmation(namespace,marker,*,source=ROOT,terminal_effect=''):
    path=Path(V16.__file__)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==V16_SHA256,'Historical V16 EDU module changed'
    original=V16.build_edu_runtime(namespace,marker,source=source,terminal_effect=terminal_effect)
    module=deepcopy(original)
    updated=migrated_expectations(original['expectations'],namespace)
    event_path=f'events/{namespace}.txt'
    text=module['fixture_text'][event_path]
    for old,new in MIGRATION.items():
        before=original['expectations'][old]['predicate']
        assert text.count(before)==1,('Unique historical predicate required',old)
        text=text.replace(before,updated[old]['predicate'],1)
        assert text.count(old)==4,('Unique historical assertion block required',old)
        text=text.replace(old,new)
    V16.LEGACY.ast(text)
    module['fixture_text'][event_path]=text
    module['assertions']=[MIGRATION.get(label,label) for label in original['assertions']]
    module['expectations']={MIGRATION.get(label,label):updated.get(label,value) for label,value in original['expectations'].items()}
    for label in original['baseline41_contract']['assertions']:
        if label not in MIGRATION:assert module['expectations'][label]==original['expectations'][label]
    stamps=[a['stamp'] for a in original['edu_source_handler_runtime_contract']['actions']
            if a['decision']=='EU_create_EDU' and a['gate_mode']=='positive']
    assert len(stamps)==2
    contract={'schema':1,'method':METHOD,'expected_authorized_confirmations':2,'creation_stamps':stamps,
      'start_observation':'EDU_START','end_observation':'EDU_TERMINAL',
      'required_creation_actor_observation':'EDU_ACTUAL_CREATE_RETURN',
      'migration_map':dict(MIGRATION),
      'native_hook_diagnostics':['EON_EDU FORMED_HOOK','EON_EDU LEADERSHIP_HOOK'],
      'required_leave_log':'EON_EDU LEAVE_HOOK'}
    module['contract']={**original['contract'],'kind':'source_only_edu_actual_creation_confirmation','method':METHOD,
      'required_hook_logs':['EON_EDU LEAVE_HOOK'],'expected_authorized_formed_commits':0,
      'native_formed_and_leadership_are_diagnostics':True}
    module['method']=METHOD
    module['edu_confirmation_contract']=contract
    module['baseline41_migration_map']=dict(MIGRATION)
    module['historical_expectations_notice']='V16/41 remains immutable failed history. V17 migrates exactly two native counter assertions; the other39 predicates and all six elapsed minima remain exact.'
    module['fixture_text_sha256']={p:hashlib.sha256(t.encode()).hexdigest() for p,t in module['fixture_text'].items()}
    module['private_builder_sha256']['edu_confirmation_runtime_support.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    module['private_builder_sha256']['edu_runtime_support.py']=V16_SHA256
    module['limits']=[module['historical_expectations_notice'],
      'Positive paths dispatch exact source complete_effect with source gates and actual ROOT/THIS/FROM. Raw API remains separate diagnostic.',
      'Two source constructor frames must prove factionless before, actual faction leader after, matching reserved intent/generation and current confirmation receipt/result1.',
      'Native formed/leadership counters are diagnostic only; actual leave cleanup remains mandatory for identity safety.',
      'No manual native hook delivery, native GUI clicks, campaign, multiplayer or save/reload proof.']
    return module


def edu_confirmation_result(contract,text,marker,observation_lines=None):
    failures=[];cycles=[]
    try:
        assert contract['schema']==1 and contract['method']==METHOD
        assert contract['expected_authorized_confirmations']==2 and contract['migration_map']==MIGRATION
        stamps=contract['creation_stamps']
        assert isinstance(stamps,list) and len(stamps)==len(set(stamps))==2
        assert all(isinstance(s,str) and re.fullmatch('[A-Za-z0-9_]+',s) for s in stamps)
        assert contract['native_hook_diagnostics']==['EON_EDU FORMED_HOOK','EON_EDU LEADERSHIP_HOOK']
        assert contract['required_leave_log']=='EON_EDU LEAVE_HOOK'
        def rows(label):
            return list(re.finditer(re.escape(label)+r'(?:[ \t]|$)([^\r\n]*)',text,re.M))
        def unique(label):
            found=rows(label)
            assert len(found)==1,('Missing/duplicate frame',label,len(found))
            return found[0]
        def values(row):
            pairs=re.findall(r'\b([a-z_]+)=([^\s]+)',row[1]);result=dict(pairs)
            assert len(pairs)==len(result),'Duplicate frame fields'
            return result
        def number(value,positive=False):
            assert re.fullmatch('[0-9]+(?:\\.[0-9]+)?',value),'Malformed numeric frame field'
            value=Decimal(value)
            assert value.is_finite() and value>=0 and (not positive or value>0)
            assert value==value.to_integral_value(),'Counter must be integral'
            return value
        def country(value):
            assert re.fullmatch('[0-9]+(?:\\.[0-9]+)?',value)
            assert Decimal(value).is_finite() and Decimal(value)>0
            return value
        run_begin=unique(marker+' RUN_BEGIN');run_end=unique(marker+' RUN_END')
        start=unique(marker+' OBS '+contract['start_observation'])
        end=unique(marker+' OBS '+contract['end_observation'])
        original_return=unique(marker+' OBS '+contract['required_creation_actor_observation'])
        assert run_begin.start()<start.start()<original_return.start()<end.start()<run_end.start(),'Invalid RUN/EDU window'
        start_values=values(start);actor=country(start_values['founder'])
        assert start_values['actor']==actor
        context=values(original_return)
        assert country(context['actor'])==context['scope']==actor,'Creation observation actor mismatch'
        before_rows=rows('EON_EDU CTOR_BEFORE');after_rows=rows('EON_EDU CTOR_RETURN')
        commits=rows('EON_EDU CONFIRM_COMMIT')
        assert len(before_rows)==len(after_rows)==len(commits)==2,'Exactly two actual constructor cycles required'
        previous_instance=previous_attempt=previous_position=0
        previous_confirmation=None
        for index,stamp in enumerate(stamps):
            dispatch=unique(marker+' TRACE '+stamp+'_BEFORE_SOURCE_HANDLER')
            finished=unique(marker+' TRACE '+stamp+'_AFTER_SOURCE_HANDLER')
            before,after,commit=before_rows[index],after_rows[index],commits[index]
            assert start.start()<dispatch.start()<before.start()<commit.start()<after.start()<finished.start()<end.start()
            assert previous_position<dispatch.start()
            assert all(values(r)['actor']==values(r)['scope']==actor for r in (dispatch,finished,before,after,commit)),'Constructor frame actor mismatch'
            b,a,c=values(before),values(after),values(commit)
            assert number(b['factionless'])==number(a['in_faction'])==number(a['is_leader'])==1,'Actual faction witness absent'
            attempt=number(b['attempt'],True);instance=number(b['reserved'],True)
            assert attempt>previous_attempt and instance>previous_instance
            assert number(b['intent'],True)==number(b['constructor_instance'],True)==instance
            for key in ('attempt','reserved','intent','constructor_instance'):
                assert number(a[key],True)==number(b[key],True),(key,'Constructor binding mismatch')
            assert number(a['remaining_intent'])==0
            assert number(a['result'])==1 and number(a['instance'],True)==number(a['member_instance'],True)==instance
            assert number(c['attempt'],True)==attempt and number(c['instance'],True)==instance
            count=number(a['confirmation'],True)
            assert count==number(b['confirmation_before'])+1==number(c['confirmation'],True)
            assert previous_confirmation is None or number(b['confirmation_before'])==previous_confirmation
            route=c['route']
            if route=='creation_return':
                assert number(a['return_receipt'],True)==instance
                assert number(a['constructor'],True)==number(b['constructor_before'])+1
                assert number(a['native'])==number(b['native_before'])
            else:
                assert route=='native_formed','Unknown confirmation route'
                assert number(a['return_receipt'])==0
                assert number(a['constructor'])==number(b['constructor_before'])
                assert number(a['native'],True)==number(b['native_before'])+1
                hooks=[r for r in rows('EON_EDU FORMED_HOOK') if before.start()<r.start()<commit.start()]
                assert len(hooks)==1 and values(hooks[0])['actor']==values(hooks[0])['scope']==actor,'Native route has no actual hook witness'
            cycles.append({'actor':actor,'attempt':str(attempt),'instance':str(instance),'route':route,'confirmation':str(count)})
            previous_instance,previous_attempt,previous_position=instance,attempt,finished.start()
            previous_confirmation=count
        assert before_rows[0].start()<original_return.start()<before_rows[1].start()
        leave=[r for r in rows(contract['required_leave_log']) if start.start()<r.start()<end.start()]
        assert leave and all(country(values(r)['actor'])==values(r)['scope'] for r in leave),'Missing actual leave cleanup witness'
        hook_counts={label:sum(start.start()<r.start()<end.start() for r in rows(label)) for label in contract['native_hook_diagnostics']}
        return {'passed':True,'failures':[],'creation_context':context,'creation_cycles':cycles,'native_hook_counts':hook_counts,
          'native_hooks_are_diagnostic_only':True,'required_leave_count':len(leave)}
    except (AssertionError,KeyError,TypeError,ValueError) as error:
        failures.append({'invalid_actual_edu_confirmation':str(error)})
    return {'passed':False,'failures':failures,'creation_cycles':cycles,'native_hooks_are_diagnostic_only':True}
