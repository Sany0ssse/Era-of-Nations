"""Actual-source AST and synthetic receipts only; no native runtime acceptance."""
from copy import deepcopy
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

import extension_source_runtime_support as EXT
import edu_runtime_support as EDU
import test_source_handler_runtime as OLD

NATIVE_TESTED=False
EVIDENCE_KIND='ACTUAL_SOURCE_AST_AND_SYNTHETIC_RECEIPT_ONLY'
sys.dont_write_bytecode=True
ast,one,walk=OLD.ast,OLD.one,OLD.walk
NS='eon_native_eu_probe'; MARK='SYNTHETIC_ONLY'
EX=EXT.build_source_runtime(NS,MARK)
EU=EDU.build_edu_runtime(NS,MARK)


def events(module):
    text=next(t for p,t in module['fixture_text'].items() if p.startswith('events/'))
    return {one(body,'id'):one(body,'immediate') for k,o,body in ast(text) if k=='country_event'}


EX_EVENTS=events(EX); EU_EVENTS=events(EU)


def extension_response():
    return deepcopy(next(body for body in EX_EVENTS.values() if any(k=='log' and v.endswith('BEGIN extension_natural_flag_pair_GER') for k,o,v in body)))


def extension_receipt():
    text=OLD.fractional_token_receipt()
    return '\n'.join(line for line in text.splitlines() if not any(s in line for s in
                     ('_BEFORE_API ','_RAW_UI_ACTIVATION_REQUESTED','_AFTER_RAW_API ','_INTERFACE_ACTIVE ')))


def edu_receipt():
    """Declared synthetic validator input, never a game log."""
    tokens={'AUS':'10792.03137','SWE':'10782.86163','FIN':'10783.97274'}
    rows=[]
    for index,a in enumerate(EU['edu_source_handler_runtime_contract']['actions']):
        actor=tokens[a['actor_tag']];target=tokens.get(a['target_tag'])
        before=dict(actor=actor,scope=actor,sender=target or actor,expected_actor=actor,
                    method='source_complete_effect_AST_dispatched_by_event',gate=1 if a['gate_mode']=='positive' else 0,
                    handler_count=index,attempt=0,request_round=0,request_instance=0,request_leader=0,
                    request_result=0,member_instance=0,instance=1,generation=1)
        if target:before['target']=target
        after=dict(before);after['handler_count']+=1
        if a['decision']=='EU_create_EDU':after['attempt']+=1
        if a['decision']=='eon_edu_request_join':
            after.update(request_round=1,request_instance=1,request_leader=target)
        stamp=a['stamp']
        def context(stage,v):rows.append(MARK+' TRACE '+stamp+'_'+stage+' '+' '.join(f'{k}={x}' for k,x in v.items()))
        def trace(stage):rows.append(MARK+' TRACE '+stamp+'_'+stage)
        context('BEFORE_SOURCE_HANDLER',before);trace('SOURCE_COMPLETE_AST_INVOKED');context('AFTER_SOURCE_HANDLER',after)
        if a['replay']:
            context('BEFORE_SOURCE_REPLAY',after);trace('EXPLICIT_NEGATIVE_SOURCE_REPLAY');context('AFTER_SOURCE_REPLAY',after)
    return '\n'.join(rows)


def raw_receipt(module,edu=False,delta=1):
    key='edu_raw_api_diagnostic_contract' if edu else 'raw_api_diagnostic_contract';c=module[key]
    before=dict(actor='10782.86163',scope='10782.86163',sender='10792.03137')
    before['expected_actor']=before['actor']
    if edu:before['sender']=before['actor']
    else:before['target']=before['sender']
    for name in c['counter_fields']:before[name]=0
    after=dict(before);after[c['counter_fields'][0]]=delta
    def row(label,values):return MARK+' TRACE '+label+' '+' '.join(f'{k}={v}' for k,v in values.items())
    return '\n'.join((MARK+' OBS '+c['available_observation']+' value=0',row(c['begin_trace'],before),
      MARK+' TRACE '+c['requested_trace'],row(c['after_trace'],after),MARK+' OBS '+c['interface_observation']+' value=1'))


spec=importlib.util.spec_from_file_location('v16_edu_source_protocol_model',EDU.ROOT/'tools/validation/edu_protocol/_protocol_model.py')
PROTO=importlib.util.module_from_spec(spec);sys.modules[spec.name]=PROTO;spec.loader.exec_module(PROTO)


class EDUModel(PROTO.Model):
    tags=('AUS','SWE','FIN','POL','USA')
    def val(self,key,frame):
        if key in self.tags:return self.tags.index(key)+1
        return super().val(key,frame)

    def trigger(self,nodes,frame):
        for key,op,body in nodes:
            if key=='tag':ok=frame['scope']==self.val(body,frame)
            elif key=='is_EU_potential':ok=(frame['scope'] in (1,2,3))==(body=='yes')
            elif key in self.tags:ok=self.trigger(body,PROTO.switch(frame,self.val(key,frame)))
            else:ok=super().trigger([(key,op,body)],frame)
            if not ok:return False
        return True

    def effect(self,nodes,frame):
        position=0
        while position<len(nodes):
            key,op,body=nodes[position];position+=1
            if key in ('activate_decision','activate_targeted_decision'):
                raise AssertionError('Positive source-only path unexpectedly used raw API')
            if key in self.tags:self.effect(body,PROTO.switch(frame,self.val(key,frame)));continue
            group=[(key,op,body)]
            if key=='if':
                while position<len(nodes) and nodes[position][0] in ('else_if','else'):
                    group.append(nodes[position]);position+=1
            super().effect(group,frame)

    def actual_event(self,body,actor,target):self.effect(body,PROTO.context(actor,actor,target))


def edu_first_request():
    body=EU_EVENTS[NS+'.3002']
    begin=next(i for i,(k,o,v) in enumerate(body) if k=='set_variable' and v[0][0].endswith('_002_gate'))
    end=next(i for i,(k,o,v) in enumerate(body) if k=='log' and v.endswith('BEGIN edu_actual_request_has_bound_target_and_positive_deadline'))
    return deepcopy(body[begin:end])


class V16SourceRuntime(unittest.TestCase):
    def test_generated_zero_cost_guard_uses_legal_inclusive_boundary_and_rejects_malformed_mutant(self):
        guard=('NOT','=',[('has_political_power','<','0')])
        def validate(table):
            guards=[]
            for body in table.values():
                for k,o,v in walk(body):
                    if k=='has_political_power':self.assertEqual((o,v),('<','0'),'Native scalar political-power grammar')
                    if k=='if' and any(n=='log' and 'SOURCE_COMPLETE_AST_INVOKED' in s for n,p,s in v):
                        gate=one(v,'limit');self.assertIn(guard,gate);guards.append(guard)
            self.assertEqual(len(guards),67)
        validate(EX_EVENTS)
        m=OLD.AdapterModel()
        for value in (-0.5,-0.000001,0,0.000001,0.5,2000):
            m.nations[1].variables['political_power']=value
            self.assertEqual(m.trigger([guard],[m.nations[1]]),value>=0)
        mutant=deepcopy(EX_EVENTS)
        def corrupt(nodes):
            for i,(k,o,v) in enumerate(nodes):
                if (k,o,v)==guard:
                    nodes[i]=('has_political_power','>=','0');return True
                if isinstance(v,list) and corrupt(v):return True
            return False
        self.assertTrue(any(corrupt(body) for body in mutant.values()))
        with self.assertRaises(AssertionError):validate(mutant)

    def test_historical_modules_remain_exact_and_baselines_preserved(self):
        self.assertEqual(EDU.SHARED.sha(EDU.HERE/'edu_support.py'),EDU.LEGACY_SHA256)
        self.assertEqual(EXT.V15.sha(EXT.HERE/'runtime_support.py'),EXT.V15_SHA256)
        self.assertEqual(EDU.fingerprint(EU['baseline41_contract']),EDU.GOLDEN41)
        self.assertEqual(EDU.fingerprint(EX['baseline114_contract']),EXT.V15.GOLDEN114)
        for module,key in ((EU,'baseline41_contract'),(EX,'baseline114_contract')):
            baseline=module[key]
            self.assertEqual([n for n in module['assertions'] if n in baseline['assertions']],baseline['assertions'])
            for n,v in baseline['expectations'].items():self.assertEqual(module['expectations'][n],v)
            self.assertEqual(module['required_elapsed_game_time'],baseline['required_elapsed_game_time'])

    def test_v16_native_wait_checkpoints_change_only_hours_after_original_contract_guard(self):
        kinds={'natural_flag':'flag','old_main':'main','old_short':'short','both_old':'both',
               'main_callback_before_migration':'main','short_callback_before_migration':'both'}
        def waits(module):
            result={}
            table=events(module)
            for case,kind in kinds.items():
                values=[]
                for suffix in ('_START','_AFTER_DAY'):
                    label=MARK+' OBS EXTENSION_'+case.upper()+suffix+' '
                    matches=[body for body in table.values() if any(k=='log' and isinstance(v,str) and v.startswith(label) for k,o,v in walk(body))]
                    self.assertEqual(len(matches),1,case+suffix)
                    calls=[v for k,o,v in walk(matches[0]) if k=='country_event' and isinstance(v,list)
                           and str(one(v,'id')).startswith(NS+'.') and any(n=='hours' for n,p,s in v)]
                    self.assertEqual(len(calls),1,case+suffix)
                    values.append(int(one(calls[0],'hours')))
                result[case]=tuple(values)
            return result
        expected={case:(49 if kind in ('short','both') else 30,
                        49 if kind=='main' else 25 if kind in ('short','both') else 30)
                  for case,kind in kinds.items()}
        self.assertEqual(waits(EX),expected)
        with patch.object(EXT,'WAIT_CHECKPOINT_DERIVATION','',create=True):
            before=EXT.build_source_runtime(NS,MARK)
        self.assertEqual(waits(before),{case:(30,30) for case in kinds})
        self.assertEqual(EX['baseline114_contract'],before['baseline114_contract'])
        self.assertEqual(EX['baseline114_sha256'],EXT.V15.GOLDEN114)
        for key in ('assertions','expectations','required_observations','required_elapsed_game_time',
                    'source_handler_runtime_contract','actual_source_callback_ast','calibrations'):
            self.assertEqual(EX[key],before[key],key)
        self.assertEqual(EX['events'],before['events'])
        self.assertEqual(set(EX['fixture_text']),set(before['fixture_text']))
        changes=[]
        def compare(a,b,path=()):
            self.assertIs(type(a),type(b),path)
            if isinstance(a,(list,tuple)):
                self.assertEqual(len(a),len(b),path)
                for i,(x,y) in enumerate(zip(a,b)):compare(x,y,path+(i,))
            elif a!=b:changes.append((path,a,b))
        event_path='events/'+NS+'.txt'
        old_ast=ast(before['fixture_text'][event_path]);new_ast=ast(EX['fixture_text'][event_path])
        compare(old_ast,new_ast)
        wanted_changes=sum(x!=y for case in kinds for x,y in zip((30,30),expected[case]))
        self.assertEqual(len(changes),wanted_changes)
        self.assertGreater(wanted_changes,0)
        for path,old,new in changes:
            node=old_ast
            for index in path[:-1]:node=node[index]
            self.assertEqual(tuple(node[:2]),('hours','='))
            self.assertEqual(path[-1],2)
            self.assertEqual(old,'30');self.assertIn(new,('49','25'))
        for fixture_path,text in EX['fixture_text'].items():
            if fixture_path!=event_path:self.assertEqual(text,before['fixture_text'][fixture_path])
        # A schedule removal or a different value cannot be hidden by the AST boundary.
        with patch.object(EXT,'WAIT_CHECKPOINT_DERIVATION','',create=True):
            unchanged=EXT.build_source_runtime(NS,MARK)
        self.assertNotEqual(waits(unchanged),expected)

    def test_census_unique_ids_bound_hashes_and_no_local_dependencies(self):
        for module,count,assertions in ((EX,61,257),(EU,19,58)):
            self.assertEqual(module['events'],count);self.assertEqual(len(module['assertions']),assertions)
            self.assertEqual(len(module['assertions']),len(set(module['assertions'])))
            self.assertEqual(len(events(module)),count)
            for path,text in module['fixture_text'].items():self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),module['fixture_text_sha256'][path])
            for path,digest in module['production_input_sha256'].items():self.assertEqual(EDU.SHARED.sha(EDU.ROOT/path),digest)
        for path in (EXT.__file__,EDU.__file__):self.assertNotIn('.local',Path(path).read_text())
        self.assertFalse(NATIVE_TESTED)

    def test_positive_source_paths_have_no_raw_api_or_native_hook_fabrication(self):
        for module,table,raw in ((EX,EX_EVENTS,'EXTENSION_RAW_NEGATIVE_API_REQUESTED'),(EU,EU_EVENTS,'EDU_RAW_NEGATIVE_API_REQUESTED')):
            for ident,body in table.items():
                calls=[k for k,o,v in walk(body) if k in ('activate_decision','activate_targeted_decision')]
                if calls:self.assertTrue(any(k=='log' and raw in v for k,o,v in walk(body)))
                self.assertFalse({'eon_edu_on_formed','eon_edu_on_leave','eon_edu_on_assume_leadership','eon_edu_on_offer_join'}.intersection(k for k,o,v in walk(body)))
        self.assertEqual(EX['source_handler_runtime_contract']['positive_dispatch'],'source-only; independent of raw API outcome')
        self.assertEqual(EU['edu_source_handler_runtime_contract']['positive_dispatch'],'source-only; independent of raw API outcome')

    def test_extension_actual_adapter_executes_one_response_and_replay_inert_without_api(self):
        m=OLD.AdapterModel();m.raw_executes_handler=True;m.event(extension_response())
        self.assertEqual(m.nations[7].arrays['eon_eu_extension_approvals'],[1])
        self.assertEqual(m.nations[7].variables['eon_eu_extension_answer_count'],1)
        self.assertEqual(m.global_owner.variables.get(NS+'_fails',0),0)
        self.assertEqual(m.global_owner.variables[NS+'_handler_invocations'],1)
        self.assertFalse(any(isinstance(row,tuple) and row[0]=='DECLARED_MODEL_INTERFACE_ACTIVATION' for row in m.receipts))

    def test_extension_missing_handler_wrong_actor_sender_and_unconditional_mutants_fail(self):
        variants=[]
        body=extension_response()
        for k,o,v in walk(body):
            if k=='if' and any(n=='log' and 'SOURCE_COMPLETE_AST_INVOKED' in s for n,op,s in v):
                for i,n in enumerate(v):
                    if n[0]=='eon_eu_extension_approve':v[i]=('log','=','REMOVED_HANDLER')
        variants.append((body,1,7,False))
        variants.extend((extension_response(),actor,sender,False) for actor,sender in ((2,7),(1,6)))
        body=extension_response()
        for k,o,v in walk(body):
            if k=='if' and any(n=='log' and 'SOURCE_COMPLETE_AST_INVOKED' in s for n,op,s in v):
                i=next(i for i,n in enumerate(v) if n[0]=='limit');v[i]=('limit','=',[('always','=','yes')])
        variants.append((body,1,7,True))
        for body,actor,sender,already in variants:
            m=OLD.AdapterModel()
            if already:m.call('eon_eu_extension_approve',1,7)
            m.event(body,actor,sender);self.assertGreater(m.global_owner.variables.get(NS+'_fails',0),0)

    def test_extension_source_identity_mutant_and_veto_cleanup_controls_remain(self):
        m=OLD.AdapterModel()
        one(m.effects['eon_eu_extension_approve'],'if').append(('FROM','=',[('set_variable','=',[('eon_eu_extension_project_notice_serial','=','999')])]))
        m.event(extension_response());self.assertGreater(m.global_owner.variables.get(NS+'_fails',0),0)
        for n in ('extension_runtime_veto_silence_does_not_count_as_abstention','extension_runtime_veto_all_represented_one_no_blocks_agreement','extension_runtime_terminal_cleanup_no_extension_or_native_clock'):
            self.assertIn(n,EX['expectations'])

    def test_extension_actual_four_stage_receipts_require_delta1_identity_and_replay(self):
        contract=EX['source_handler_runtime_contract'];text=extension_receipt()
        self.assertTrue(EXT.source_handler_callback_result(contract,text,MARK)['passed'])
        stamp=contract['actions'][0]['stamp']
        for stage,a,b in (('AFTER_EXPLICIT_HANDLER','sender=10792.03137','sender=10792.03138'),
                          ('AFTER_EXPLICIT_HANDLER','project_notice=1','project_notice=2'),
                          ('AFTER_EXPLICIT_HANDLER','treaty=0','treaty=1'),
                          ('AFTER_EXPLICIT_HANDLER','answer=1','answer=0'),
                          ('AFTER_EXPLICIT_HANDLER','answer=1','answer=2'),
                          ('AFTER_DIRECT_REPLAY','answer=1','answer=2'),
                          ('BEFORE_EXPLICIT_HANDLER','actor=10782.86163','actor=NaN')):
            mutant='\n'.join(line.replace(a,b) if ' TRACE '+stamp+'_'+stage+' ' in line else line for line in text.splitlines())
            self.assertFalse(EXT.source_handler_callback_result(contract,mutant,MARK)['passed'])
        self.assertFalse(EXT.source_handler_callback_result(contract,'\n'.join(reversed(text.splitlines())),MARK)['passed'])
        self.assertFalse(EXT.source_handler_callback_result(contract,text+'\n'+MARK+' TRACE '+stamp+'_RAW_UI_ACTIVATION_REQUESTED',MARK)['passed'])

    def test_extension_duplicate_or_malformed_action_contract_fails_closed(self):
        for change in ('stamp','actor_tag','target_tag','increment_array','decision','method'):
            contract=deepcopy(EX['source_handler_runtime_contract'])
            contract['actions'][1][change]=contract['actions'][0][change] if change=='stamp' else 'UNSUPPORTED'
            self.assertFalse(EXT.source_handler_callback_result(contract,extension_receipt(),MARK)['passed'])
        contract=deepcopy(EX['source_handler_runtime_contract']);contract['actions'][1]['stamp']={}
        self.assertFalse(EXT.source_handler_callback_result(contract,extension_receipt(),MARK)['passed'])

    def test_raw_negative_diagnostics_characterize_nonzero_delta_without_positive_acceptance(self):
        for module,edu,fn in ((EX,False,EXT.raw_api_diagnostic_result),(EU,True,EDU.edu_raw_api_diagnostic_result)):
            contract=module['edu_raw_api_diagnostic_contract' if edu else 'raw_api_diagnostic_contract']
            for delta in (0,1,2):
                result=fn(contract,raw_receipt(module,edu,delta),MARK)
                self.assertTrue(result['controls_valid'],result);self.assertTrue(result['diagnostic_only'])
                self.assertEqual(result['actual_counter_delta'][contract['counter_fields'][0]],str(delta))
                self.assertNotIn('passed',result)

    def test_raw_positive_context_missing_duplicate_or_reordered_diagnostics_fail(self):
        for module,edu,fn in ((EX,False,EXT.raw_api_diagnostic_result),(EU,True,EDU.edu_raw_api_diagnostic_result)):
            contract=module['edu_raw_api_diagnostic_contract' if edu else 'raw_api_diagnostic_contract'];text=raw_receipt(module,edu)
            variants=(text.replace('value=0','value=1',1),text.replace(contract['requested_trace'],'REMOVED'),
                      text+'\n'+text.splitlines()[1],'\n'.join(reversed(text.splitlines())),text.replace('scope=10782.86163','scope=10782.86162',1))
            for v in variants:self.assertFalse(fn(contract,v,MARK)['controls_valid'])

    def test_edu_exact_source_callbacks_categories_and_omitted_cost_are_bound(self):
        for ident,snapshot in EU['actual_source_callback_ast'].items():
            category=one(ast((EDU.ROOT/snapshot['path']).read_text('utf-8-sig')),snapshot['category'])
            self.assertEqual(snapshot['action_ast'],one(category,ident))
            self.assertEqual(snapshot['category_ast'],one(ast((EDU.ROOT/EDU.CATEGORY_PATH).read_text('utf-8-sig')),snapshot['category']))
            self.assertEqual(snapshot['complete_effect'],one(snapshot['action_ast'],'complete_effect'))
            self.assertFalse(any(k in ('cost','custom_cost') for k,o,v in snapshot['action_ast']))
        self.assertIn('native UI cost not claimed',EU['actual_source_callback_ast']['EU_create_EDU']['cost_shape'])

    def test_edu_only_five_declared_ai_fields_change_with_original_handlers_preserved(self):
        declared=[]
        for record in EU['runtime_overrides']:
            path=record['corepath'];source=ast((EDU.ROOT/path).read_text('utf-8-sig'));overlay=ast(EU['fixture_text'][path])
            for (_,_,category),(_,_,private) in zip(source,overlay):
                for (ident,_,action),(_,_,changed) in zip(category,private):
                    self.assertEqual([n for n in action if n[0]!='ai_will_do'],[n for n in changed if n[0]!='ai_will_do'])
                    if ident in EDU.AI_IDS:
                        self.assertEqual(one(changed,'ai_will_do'),[('factor','=','0')]);declared.append(ident)
                    else:self.assertEqual(action,changed)
            self.assertEqual(record['runtime_override_sha256'],EU['fixture_text_sha256'][path])
        self.assertEqual(set(declared),set(EDU.AI_IDS));self.assertEqual(len(declared),5)

    def test_edu_fin_requests_have_real_aus_origin_relay_and_preserved_expiry_order(self):
        def schedules(n):return [(k,one(v,'country_event')) for k,o,v in EU_EVENTS[NS+'.'+str(n)] if k in EDUModel.tags and isinstance(v,list) and any(a=='country_event' for a,b,c in v)]
        self.assertEqual([(k,one(e,'id')) for k,e in schedules(3007)],[('AUS',NS+'.3062')])
        self.assertEqual([(k,one(e,'id')) for k,e in schedules(3062)],[('FIN',NS+'.3008')])
        self.assertEqual([(k,one(e,'id')) for k,e in schedules(3011)],[('AUS',NS+'.3060')])
        self.assertEqual([(k,one(e,'id')) for k,e in schedules(3060)],[('FIN',NS+'.3061')])
        self.assertFalse(any(k=='eon_edu_request_join_effect' for k,o,v in walk(EU_EVENTS[NS+'.3011'])))
        self.assertTrue(any(k=='eon_edu_request_join_effect' for k,o,v in walk(EU_EVENTS[NS+'.3061'])))
        self.assertEqual(next(c for c in EU['required_elapsed_game_time'] if c['start_observation']=='EDU_REQUEST_EXPIRY_CLOCK')['minimum_hours'],24)

    def test_edu_actual_adapter_request_round_and_replay_with_declared_native_model_boundaries(self):
        m=EDUModel();m.decision('EU_create_EDU');m.actual_event(edu_first_request(),2,1)
        self.assertEqual(m.c[2]['vars']['eon_edu_request_round'],1)
        self.assertEqual(m.c[2]['vars']['eon_edu_request_leader'],1)
        self.assertEqual(m.g[NS+'_edu_handler_invocations'],1)
        self.assertEqual(m.g.get(NS+'_fails',0),0)
        self.assertTrue(any(row[0]=='native_create_unproved' for row in m.boundaries if isinstance(row,tuple)))

    def test_edu_missing_handler_wrong_actor_sender_and_source_gate_mutants_fail(self):
        for kind in ('missing','wrong_actor','wrong_sender','category_closed','unconditional'):
            m=EDUModel();m.decision('EU_create_EDU');body=edu_first_request();actor,target=2,1
            if kind=='wrong_actor':actor=3
            if kind=='wrong_sender':target=3
            if kind=='category_closed':m.gf.add('GAME_RULE_eu_disabled')
            if kind=='unconditional':m.decision('eon_edu_request_join',2,1)
            if kind in ('missing','unconditional'):
                for k,o,v in walk(body):
                    if k=='if' and any(n=='log' and 'SOURCE_COMPLETE_AST_INVOKED' in s for n,p,s in v):
                        for i,n in enumerate(v):
                            if kind=='missing' and n[0]=='eon_edu_request_join_effect':v[i]=('log','=','REMOVED_HANDLER')
                            if kind=='unconditional' and n[0]=='limit':v[i]=('limit','=',[('always','=','yes')])
            m.actual_event(body,actor,target);self.assertGreater(m.g.get(NS+'_fails',0),0,kind)

    def test_edu_positive_and_explicit_negative_actions_have_exact_unique_schema(self):
        actions=EU['edu_source_handler_runtime_contract']['actions']
        self.assertEqual(len(actions),15);self.assertEqual(sum(a['gate_mode']=='explicit_negative' for a in actions),2)
        self.assertEqual(sum(a['replay'] for a in actions),1)
        self.assertEqual(len({a['stamp'] for a in actions}),15)
        self.assertEqual(EU['startup_effect'],f'set_variable = {{ global.{NS}_edu_handler_invocations = 0 }} ')

    def test_edu_fractional_country_receipt_and_request_replay_are_strict(self):
        c=EU['edu_source_handler_runtime_contract'];text=edu_receipt()
        self.assertTrue(EDU.edu_source_handler_callback_result(c,text,MARK)['passed'])
        stamp=c['actions'][1]['stamp']
        for stage,a,b in (('AFTER_SOURCE_HANDLER','sender=10792.03137','sender=10792.03138'),
                          ('AFTER_SOURCE_HANDLER','request_leader=10792.03137','request_leader=10792.03138'),
                          ('AFTER_SOURCE_HANDLER','request_round=1','request_round=2'),
                          ('AFTER_SOURCE_REPLAY','request_instance=1','request_instance=2'),
                          ('BEFORE_SOURCE_HANDLER','actor=10782.86163','actor=NaN'),
                          ('BEFORE_SOURCE_HANDLER','gate=1','gate=0')):
            mutant='\n'.join(line.replace(a,b) if ' TRACE '+stamp+'_'+stage+' ' in line else line for line in text.splitlines())
            self.assertFalse(EDU.edu_source_handler_callback_result(c,mutant,MARK)['passed'])
        self.assertFalse(EDU.edu_source_handler_callback_result(c,'\n'.join(reversed(text.splitlines())),MARK)['passed'])

    def test_edu_duplicate_contract_wrong_mode_or_target_fails_closed(self):
        for key in ('stamp','gate_mode','target_tag','decision','method'):
            c=deepcopy(EU['edu_source_handler_runtime_contract']);c['actions'][1][key]=c['actions'][0][key] if key=='stamp' else 'UNSUPPORTED'
            self.assertFalse(EDU.edu_source_handler_callback_result(c,edu_receipt(),MARK)['passed'])
        c=deepcopy(EU['edu_source_handler_runtime_contract']);c['actions'].pop()
        self.assertFalse(EDU.edu_source_handler_callback_result(c,edu_receipt(),MARK)['passed'])
        c=deepcopy(EU['edu_source_handler_runtime_contract']);c['actions'][1]['stamp']={}
        self.assertFalse(EDU.edu_source_handler_callback_result(c,edu_receipt(),MARK)['passed'])

    def test_edu_callback_cost_drift_and_explicit_source_freeze_are_checked(self):
        with tempfile.TemporaryDirectory() as taskdir:
            source=Path(taskdir)
            for path in EU['production_dependency_paths']:
                destination=source/path;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(EDU.ROOT/path,destination)
            path=source/EDU.AI_PATHS[0];text=path.read_text('utf-8-sig')
            path.write_text(text.replace('eon_edu_request_join = {','eon_edu_request_join = { cost = 10',1),encoding='utf-8')
            with self.assertRaises(AssertionError):EDU.build_edu_runtime(NS,MARK,source=source)
            path.write_text(text.replace('eon_edu_request_join_effect = yes','unknown_callback = yes',1),encoding='utf-8')
            with self.assertRaises(AssertionError):EDU.build_edu_runtime(NS,MARK,source=source)
            path.write_text(text+'\n# Frozen input control\n',encoding='utf-8')
            frozen=EDU.build_edu_runtime(NS,MARK,source=source)
            self.assertNotEqual(frozen['production_input_sha256'][EDU.AI_PATHS[0]],EU['production_input_sha256'][EDU.AI_PATHS[0]])

    def test_native_hooks_two_commits_and_opaque_source_ids_are_not_optional(self):
        self.assertTrue(EU['contract']['missing_leave_hook_acceptance_blocker'])
        self.assertEqual(EU['contract']['expected_authorized_formed_commits'],2)
        for label in ('edu_scripted_remove_fires_real_leave_cleanup','edu_native_dismantle_clears_all_actual_member_receipts','edu_actual_native_leadership_hook_reconciles','edu_pending_destroy_recreate_never_commits_foreign_instance'):
            self.assertEqual(EU['expectations'][label],EU['baseline41_contract']['expectations'][label])
            self.assertNotIn('has_dlc',EU['expectations'][label]['predicate'])
        self.assertNotIn('native UI cost verified',' '.join(EU['limits']))

    def test_raw_edu_diagnostic_is_after_original_archive_and_before_terminal(self):
        body=EDU.render(EU_EVENTS[NS+'.3015'])
        self.assertLess(body.index('END edu_nato_unchanged_after_actual_archive'),body.index('EDU_RAW_NEGATIVE_BEGIN'))
        self.assertLess(body.index('EDU_RAW_NEGATIVE_AFTER'),body.index('EDU_TERMINAL'))
        self.assertEqual(body.count('activate_decision = EU_create_EDU'),1)
        self.assertNotIn('clear_variable = global.eon_edu_instance',body[body.index('EDU_RAW_NEGATIVE_BEGIN'):])

    def test_terminal_composition_is_once_and_historical_factory_is_unmodified(self):
        module=EDU.build_edu_runtime(NS,MARK,terminal_effect='log = "PRIVATE_NEXT_MODULE" ')
        text=next(t for p,t in module['fixture_text'].items() if p.startswith('events/'))
        self.assertEqual(text.count('PRIVATE_NEXT_MODULE'),1)
        old=EDU.LEGACY.build_edu(NS,MARK)
        self.assertEqual(old['events'],16);self.assertEqual(len(old['assertions']),41)
        self.assertTrue(old['contract']['no_copied_complete_effect_or_create_helper'])
        oldext=EXT.V15.build_runtime(NS,MARK)
        self.assertEqual(oldext['events'],60);self.assertEqual(len(oldext['assertions']),324)


if __name__=='__main__':unittest.main(verbosity=2)
