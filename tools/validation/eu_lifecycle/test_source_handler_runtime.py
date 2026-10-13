"""Actual-source AST/mutant checks; controlled API is not engine proof."""
from pathlib import Path
from copy import deepcopy
import hashlib
import importlib.util
import json
import sys
import unittest

import runtime_support as R
NATIVE_TESTED=False
EVIDENCE_KIND='ACTUAL_SOURCE_AST_AND_SYNTHETIC_RECEIPT_ONLY'
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('public_source_handler_runtime_model',R.ROOT/'tools/validation/eu_withdrawal_extension/test_lifecycle.py')
old=importlib.util.module_from_spec(spec);sys.modules[spec.name]=old;spec.loader.exec_module(old)
ast,one=old.ast,old.one


def walk(nodes):
    for node in nodes:
        yield node
        if isinstance(node[2],list):yield from walk(node[2])


class AdapterModel(old.ExtensionModel):
    """Interpret current adapter AST; interface API no-op is a declared input."""
    tags=('GER','FRA','ITA','HOL','SPR','CZE','POL')
    def __init__(self):
        super().__init__()
        Nation=old.module.Nation
        self.nations={i:Nation(i,original_tag=tag,variables={'political_power':2000}) for i,tag in enumerate(self.tags,1)}
        self.members(tuple(self.nations))
        self.call('eon_eu_notify_withdrawal',7)
        self.call('eon_eu_extension_propose',7)
        for c in self.nations.values():c.decisions=set()
        self.raw_executes_handler=False

    def owner(self,token,stack):
        if token in self.tags:return self.nations[self.tags.index(token)+1]
        return super().owner(token,stack)

    def trigger(self,nodes,stack):
        index=0
        while index<len(nodes):
            k,op,v=nodes[index];index+=1
            if k=='if':
                branches=[('if',v)]
                while index<len(nodes) and nodes[index][0] in ('else_if','else'):
                    branches.append((nodes[index][0],nodes[index][2]));index+=1
                passed=True
                for kind,body in branches:
                    if kind=='else' or self.trigger(one(body,'limit'),stack):
                        passed=self.trigger([n for n in body if n[0]!='limit'],stack);break
            elif k=='is_EU_potential':passed=v=='yes' # Declared seven European origin inputs.
            elif k=='has_political_power':passed=old.module.compare(stack[-1].variables['political_power'],op,self.value(v,stack))
            elif k=='has_decision':passed=v in stack[-1].decisions
            elif k in self.tags:passed=self.trigger(v,stack+[self.owner(k,stack)])
            else:passed=super().trigger([(k,op,v)],stack)
            if not passed:return False
        return True

    def effect(self,nodes,stack):
        index=0
        while index<len(nodes):
            k,op,v=nodes[index];index+=1
            if k=='log':continue
            if k in self.tags:self.effect(v,stack+[self.owner(k,stack)]);continue
            if k in ('activate_decision','activate_targeted_decision'):
                ident=one(v,'decision') if isinstance(v,list) else v
                stack[-1].decisions.add(ident)
                self.receipts.append(('DECLARED_MODEL_INTERFACE_ACTIVATION',ident,stack[-1].ident))
                if self.raw_executes_handler:self.effect(RUNTIME['actual_source_callback_ast'][ident]['complete_effect'],stack)
                continue
            group=[(k,op,v)]
            if k=='if':
                while index<len(nodes) and nodes[index][0] in ('else_if','else'):
                    group.append(nodes[index]);index+=1
            super().effect(group,stack)

    def event(self,body,actor=1,sender=7):
        self.sender,self.from_id=actor,sender
        self.effect(body,[self.nations[actor]])


RUNTIME=R.build_runtime()
EVENT_AST=ast(next(text for path,text in RUNTIME['fixture_text'].items() if path.startswith('events/')))
EVENTS={one(v,'id'):one(v,'immediate') for k,op,v in EVENT_AST if k=='country_event'}


def first_response():
    return deepcopy(next(v for v in EVENTS.values() if any(k=='log' and s.endswith('BEGIN extension_natural_flag_pair_GER') for k,op,s in v)))


class RuntimeContracts(unittest.TestCase):
    def test_original114_golden_predictions_and_clocks_preserved(self):
        encoded=json.dumps(RUNTIME['baseline114_contract'],sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest(),R.GOLDEN114)
        self.assertEqual(len(RUNTIME['baseline114_contract']['assertions']),114)
        for label,expect in RUNTIME['baseline114_contract']['expectations'].items():
            self.assertEqual(RUNTIME['expectations'][label],expect)
        self.assertEqual(RUNTIME['required_elapsed_game_time'],RUNTIME['baseline114_contract']['required_elapsed_game_time'])
        self.assertNotIn('extension_callback_contract',RUNTIME)

    def test_five_bound_fixture_paths_and_reserved_event_range(self):
        self.assertEqual(len(RUNTIME['fixture_paths']),5)
        self.assertEqual(RUNTIME['events'],60)
        self.assertEqual(len(RUNTIME['assertions']),324)
        numbers=[int(x.rsplit('.',1)[1]) for x in EVENTS]
        self.assertEqual(len(numbers),len(set(numbers)))
        self.assertGreaterEqual(min(numbers),7400);self.assertLessEqual(max(numbers),7599)
        for path,text in RUNTIME['fixture_text'].items():
            self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),RUNTIME['fixture_text_sha256'][path])

    def test_actual_callbacks_gates_and_cost_zero_are_exact_source(self):
        actions={}
        for path in ('common/decisions/eon_eu_membership_decisions.txt','common/decisions/eon_eu_withdrawal_extension_decisions.txt'):
            for category,op,body in ast((R.ROOT/path).read_text('utf-8-sig')):
                for ident,op,action in body:actions[ident]=action
        for ident,snapshot in RUNTIME['actual_source_callback_ast'].items():
            for key,value in snapshot.items():self.assertEqual(value,one(actions[ident],key))
            self.assertEqual(snapshot['cost'],'0')
        text=next(t for p,t in RUNTIME['fixture_text'].items() if p.startswith('events/'))
        self.assertIn('SOURCE_COMPLETE_AST_INVOKED',text)
        self.assertNotIn('ACTIVATE_SUCCEEDED',text)
        self.assertNotIn('CALIBRATION_ACTIVATE_REQUESTED',text)

    def test_ai_overlay_changes_only_eight_declared_weight_blocks(self):
        changed=[];declared=[];expected_changes=[]
        for path in ('common/decisions/eon_eu_membership_decisions.txt','common/decisions/eon_eu_withdrawal_extension_decisions.txt'):
            original=ast((R.ROOT/path).read_text('utf-8-sig'));private=ast(RUNTIME['fixture_text'][path])
            for (_,_,body),(_,_,overlay) in zip(original,private):
                for (ident,_,action),(_,_,candidate) in zip(body,overlay):
                    def rest(rows):return [n for n in rows if n[0]!='ai_will_do']
                    self.assertEqual(rest(action),rest(candidate),ident)
                    if ident in R.AI_IDS:
                        declared.append(ident)
                        self.assertEqual(one(candidate,'ai_will_do'),[('factor','=','0')])
                        if one(action,'ai_will_do')!=[('factor','=','0')]:expected_changes.append(ident)
                    if one(action,'ai_will_do')!=one(candidate,'ai_will_do'):
                        changed.append(ident);self.assertEqual(one(candidate,'ai_will_do'),[('factor','=','0')])
        self.assertEqual(set(declared),set(R.AI_IDS))
        self.assertEqual(set(changed),set(expected_changes))

    def test_all_six_responders_are_independent_pol_origin_events(self):
        actions=RUNTIME['source_handler_runtime_contract']['actions']
        self.assertEqual(len(actions),30)
        self.assertEqual({a['actor_tag'] for a in actions},set(('GER','FRA','ITA','HOL','SPR','CZE')))
        for a in actions:self.assertEqual(a['target_tag'],'POL');self.assertEqual(a['method'],R.SOURCE_METHOD)
        starts=[body for body in EVENTS.values() if sum(k in AdapterModel.tags[:-1] and any(n=='country_event' for n,op,v in value) for k,op,value in body if isinstance(value,list))==6]
        self.assertEqual(len(starts),5)
        for body in starts:
            schedules=[(k,one(value,'country_event')) for k,op,value in body if k in AdapterModel.tags[:-1] and isinstance(value,list)]
            self.assertEqual([t for t,e in schedules],list(AdapterModel.tags[:-1]))
            self.assertEqual([int(one(e,'hours')) for t,e in schedules],[2,4,6,8,10,12])

    def test_local_missing_sixth_attempt_is_pol_self_event_at_hour11(self):
        local_bodies=[]
        starts=[body for body in EVENTS.values() if sum(k in AdapterModel.tags[:-1] and any(n=='country_event' for n,op,v in value) for k,op,value in body if isinstance(value,list))==6]
        for body in starts:
            scheduled=[one(value,'country_event') for k,op,value in body if k=='POL' and isinstance(value,list) and any(n=='country_event' for n,op,v in value)]
            partial=[e for e in scheduled if one(e,'hours')=='11']
            self.assertEqual(len(partial),1)
            local=EVENTS[one(partial[0],'id')];local_bodies.append(local)
            self.assertTrue(any(k=='log' and ('missing_sixth_blocks_final' in v or 'silence_does_not_count_as_abstention' in v) for k,op,v in local))
            invokes=[v for k,op,v in local if k=='if' and any(n=='log' and 'SOURCE_COMPLETE_AST_INVOKED' in s for n,op,s in v)]
            self.assertEqual(len(invokes),1)
            self.assertIn(('check_variable','=',[('var','=','ROOT.id'),('value','=','THIS.id'),('compare','=','equals')]),one(invokes[0],'limit'))
        self.assertEqual(len(local_bodies),5)
        m=AdapterModel()
        for actor in range(1,6):m.call('eon_eu_extension_approve',actor,7)
        m.event(local_bodies[0],7,7)
        self.assertEqual(m.nations[7].variables.get('eon_eu_extension_queued_units',0),0)
        self.assertEqual(m.global_owner.variables.get('eon_private_eu_handler_runtime_handler_invocations',0),0)
        self.assertEqual(m.global_owner.variables.get('eon_private_eu_handler_runtime_fails',0),0)

    def test_actual_adapter_records_delta_and_replay_inert(self):
        m=AdapterModel();m.event(first_response())
        self.assertEqual(m.nations[7].arrays['eon_eu_extension_approvals'],[1])
        self.assertEqual(m.nations[7].variables['eon_eu_extension_answer_count'],1)
        self.assertEqual(m.global_owner.variables.get('eon_private_eu_handler_runtime_fails',0),0)
        self.assertEqual(m.global_owner.variables['eon_private_eu_handler_runtime_handler_invocations'],1)

    def test_raw_api_that_executes_handler_cannot_be_reclassified_as_runtime_pass(self):
        m=AdapterModel();m.raw_executes_handler=True;m.event(first_response())
        self.assertGreater(m.global_owner.variables.get('eon_private_eu_handler_runtime_fails',0),0)

    def test_no_explicit_handler_mutant_is_detected(self):
        body=first_response()
        def erase(nodes):
            for i,(k,op,v) in enumerate(nodes):
                if k=='eon_eu_extension_approve':nodes[i]=('log','=','REMOVED_SOURCE_HANDLER_MUTANT')
                elif isinstance(v,list):erase(v)
        erase(body);m=AdapterModel();m.event(body)
        self.assertGreater(m.global_owner.variables.get('eon_private_eu_handler_runtime_fails',0),0)

    def test_wrong_actual_country_event_sender_and_actor_fail(self):
        for actor,sender in ((2,7),(1,6)):
            m=AdapterModel();m.event(first_response(),actor,sender)
            self.assertGreater(m.global_owner.variables.get('eon_private_eu_handler_runtime_fails',0),0)

    def test_untaken_handler_counter_control_catches_unconditional_invoke(self):
        m=AdapterModel();m.call('eon_eu_extension_approve',1,7)
        body=first_response()
        for k,op,v in walk(body):
            if k=='if' and any(n=='log' and 'SOURCE_COMPLETE_AST_INVOKED' in s for n,op,s in v):
                i=next(i for i,n in enumerate(v) if n[0]=='limit');v[i]=('limit','=',[('always','=','yes')])
        m.event(body)
        self.assertGreater(m.global_owner.variables.get('eon_private_eu_handler_runtime_fails',0),0)

    def test_source_project_identity_mutant_is_detected(self):
        m=AdapterModel()
        one(m.effects['eon_eu_extension_approve'],'if').append(('FROM','=',[('set_variable','=',[('eon_eu_extension_project_notice_serial','=','999')])]))
        m.event(first_response())
        self.assertGreater(m.global_owner.variables.get('eon_private_eu_handler_runtime_fails',0),0)

    def test_veto_silence_abstention_and_consumed_revocation_have_separate_predicates(self):
        names=RUNTIME['expectations']
        self.assertIn('extension_runtime_veto_silence_does_not_count_as_abstention',names)
        self.assertIn('extension_runtime_veto_all_represented_one_no_blocks_agreement',names)
        self.assertIn('extension_runtime_terminal_cleanup_no_extension_or_native_clock',names)
        revoke=[n for n in names if n.endswith('_revocation_cleans_consumed_or_pending_notice')]
        self.assertGreaterEqual(len(revoke),7)
        text=next(t for p,t in RUNTIME['fixture_text'].items() if p.startswith('events/'))
        self.assertIn('eon_eu_extension_reject = yes',text)

    def test_strict_source_handler_receipt_contract_has_independent_raw_and_dispatch_stages(self):
        text=synthetic_receipt()
        result=R.source_handler_callback_result(RUNTIME['source_handler_runtime_contract'],text,'SYNTHETIC_ONLY')
        self.assertTrue(result['passed'],result)
        self.assertEqual(len(result['actions']),30)
        self.assertTrue(all(a['interface_active'] for a in result['actions']))
        self.assertEqual(result['method'],R.SOURCE_METHOD)
        self.assertIn('Decision engine click',result['claims_excluded'])

    def test_receipt_mutants_fail_closed_without_reinterpreting_raw_noop(self):
        text=synthetic_receipt()
        first=RUNTIME['source_handler_runtime_contract']['actions'][0]['stamp']
        lines=text.splitlines()
        variants={}
        for name,stage,oldtoken,newtoken in (
            ('raw_execute','AFTER_RAW_API','answer=0','answer=1'),
            ('wrong_sender','AFTER_EXPLICIT_HANDLER','sender=7','sender=6'),
            ('serial_drift','AFTER_EXPLICIT_HANDLER','project_notice=1','project_notice=2'),
            ('treaty_drift','AFTER_EXPLICIT_HANDLER','treaty=0','treaty=1'),
            ('missing_delta','AFTER_EXPLICIT_HANDLER','answer=1','answer=0'),
            ('double_delta','AFTER_EXPLICIT_HANDLER','answer=1','answer=2'),
            ('replay_delta','AFTER_DIRECT_REPLAY','answer=1','answer=2'),
            ('bad_actor','BEFORE_API','actor=1','actor=2'),
            ('wrong_method','BEFORE_API','method=source_complete_effect_AST_dispatched_by_event','method=DecisionEngineClick')):
            variants[name]='\n'.join(line.replace(oldtoken,newtoken) if ' TRACE '+first+'_'+stage+' ' in line else line for line in lines)
        invoke='SYNTHETIC_ONLY TRACE '+first+'_SOURCE_COMPLETE_AST_INVOKED'
        variants['missing_dispatch_trace']=text.replace(invoke,'SYNTHETIC_ONLY TRACE REMOVED_DISPATCH')
        variants['duplicate_stage']=text+'\n'+next(line for line in lines if ' TRACE '+first+'_AFTER_RAW_API ' in line)
        variants['stage_reorder']='\n'.join(list(reversed(lines)))
        for name,mutant in variants.items():
            with self.subTest(name=name):
                result=R.source_handler_callback_result(RUNTIME['source_handler_runtime_contract'],mutant,'SYNTHETIC_ONLY')
                self.assertFalse(result['passed'],result)

    def test_fractional_opaque_native_country_token_shape_preserves_exact_identity(self):
        # Values follow the installed-engine receipt shape. This synthetic
        # validator input proves parsing, not a native callback execution.
        text=fractional_token_receipt()
        result=R.source_handler_callback_result(RUNTIME['source_handler_runtime_contract'],text,'SYNTHETIC_ONLY')
        self.assertTrue(result['passed'],result)
        self.assertFalse(NATIVE_TESTED)
        self.assertEqual(EVIDENCE_KIND,'ACTUAL_SOURCE_AST_AND_SYNTHETIC_RECEIPT_ONLY')

    def test_fractional_country_identity_mutants_are_rejected(self):
        text=fractional_token_receipt()
        for name,token in (('changed_identity','10782.86162'),('nan','NaN'),('infinite','Infinity'),
                           ('zero','0'),('negative','-10782.86163'),('malformed','10782.86163x')):
            with self.subTest(name=name):
                mutant=text.replace('actor=10782.86163','actor='+token,1)
                result=R.source_handler_callback_result(RUNTIME['source_handler_runtime_contract'],mutant,'SYNTHETIC_ONLY')
                self.assertFalse(result['passed'],result)


def synthetic_receipt():
    """Declared synthetic validator input; deliberately not engine evidence."""
    rows=[]
    for index,action in enumerate(RUNTIME['source_handler_runtime_contract']['actions']):
        actor=AdapterModel.tags.index(action['actor_tag'])+1
        before={k:0 for k in ('answer','yes','no','abstain','approvals','rejections','abstentions','queue','treaty','treaty_proposal')}
        before.update(actor=actor,scope=actor,sender=7,target=7,expected_actor=actor,notice=1,project=1,project_notice=1,electorate=6,gate=1,handler_count=index+2,
                      method='source_complete_effect_AST_dispatched_by_event')
        after=dict(before)
        for k in ('answer',action['increment_array'],action['increment_counter']):after[k]+=1
        after['handler_count']+=1
        stamp=action['stamp']
        def context(stage,values):rows.append('SYNTHETIC_ONLY TRACE '+stamp+'_'+stage+' '+' '.join(f'{k}={v}' for k,v in values.items()))
        def trace(stage):rows.append('SYNTHETIC_ONLY TRACE '+stamp+'_'+stage)
        context('BEFORE_API',before);trace('RAW_UI_ACTIVATION_REQUESTED');context('AFTER_RAW_API',before)
        rows.append('SYNTHETIC_ONLY OBS EXTENSION_'+stamp+'_INTERFACE_ACTIVE value=1')
        context('BEFORE_EXPLICIT_HANDLER',before);trace('SOURCE_COMPLETE_AST_INVOKED');context('AFTER_EXPLICIT_HANDLER',after)
        context('BEFORE_DIRECT_REPLAY',after);trace('EXPLICIT_NEGATIVE_DIRECT_REPLAY');context('AFTER_DIRECT_REPLAY',after)
    return '\n'.join(rows)


def fractional_token_receipt():
    import re
    ids={str(i):f'{10781+i}.86163' for i in range(1,7)}
    ids['7']='10792.03137'
    return re.sub(r'\b(actor|scope|sender|target|expected_actor)=([1-7])\b',
                  lambda m:m[1]+'='+ids[m[2]],synthetic_receipt())


if __name__=='__main__':unittest.main(verbosity=2)
