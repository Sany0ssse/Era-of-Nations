"""Source-contract controls for V18; generated fixtures are not game acceptance."""
from copy import deepcopy
from pathlib import Path
import tempfile
import shutil
import hashlib
import unittest
import fixture_isolation_runtime_support as I
from edu_support import ast
import build_native_probe as B
from analyze_native_probe import runtime_provenance_problems

NS='eon_native_eu_probe';MARK='EON_EU_NATIVE_V18'


def events(module):
    return {next(v for k,o,v in fields if k=='id'):next(v for k,o,v in fields if k=='immediate')
            for key,op,fields in ast(module['fixture_text'][f'events/{NS}.txt']) if key=='country_event'}


def walk(nodes):
    for key,op,value in nodes:
        yield key,op,value
        if isinstance(value,list):yield from walk(value)


def removal_log():
    rows=[MARK+' TRACE '+I.REMOVAL_FRAMES[0]+' actor=1 scope=1 expected_actor=1 target=2 leader=1 shared=1 factionless=0 confirmed=1 member=8 return_receipt=0 leave=2 leave_before=2',
          'EON_EDU LEAVE_HOOK actor=2 scope=2 sender=1',
          MARK+' TRACE '+I.REMOVAL_FRAMES[1]+' actor=1 scope=1 expected_actor=1 target=2 leader=1 shared=0 factionless=1 confirmed=0 member=0 return_receipt=0 leave=3 leave_before=2',
          MARK+' TRACE '+I.REMOVAL_FRAMES[2]+' actor=1 scope=1 expected_actor=1 target=2 leader=1 shared=0 factionless=1 confirmed=0 member=0 return_receipt=0 leave=3 leave_before=2',
          MARK+' PASS '+I.REMOVE_LABEL,MARK+' BEGIN '+I.LEGACY_REMOVE]
    return '\n'.join([MARK+' RUN_BEGIN']+rows+[MARK+' RUN_END passes=519 fails=0'])


def cleanup_log(taken):
    rows=[]
    for action in I.cleanup_contract()['actions']:
        stamp=action['stamp'];payload='actor=4 scope=4 target=4 expected_actor=4 '+ ' '.join(k+'=0' for k in ('answer','yes','no','abstain','approvals','rejections','abstentions','queue','notice','project','project_notice','electorate','treaty','treaty_proposal'))+' gate='+str(int(taken))+' handler_count='
        rows.append(MARK+' OBS '+action['condition_observation']+' value='+str(int(taken)))
        rows.append(MARK+' TRACE '+action['before_trace']+' '+payload+'2')
        if taken:rows.append(MARK+' TRACE '+action['invoke_trace'])
        rows.append(MARK+' TRACE '+action['after_trace']+' '+payload+str(2+int(taken)))
        for suffix in ('planned_or_untaken_dispatch_count','revocation_cleans_consumed_or_pending_notice'):
            rows.append(MARK+' PASS extension_runtime_'+stamp.removeprefix('HANDLER_').lower()+'_'+suffix)
    return '\n'.join([MARK+' RUN_BEGIN']+rows+[MARK+' RUN_END passes=519 fails=0'])


class Isolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.edu=I.build_edu_isolated(NS,MARK)
        cls.ext=I.build_extension_isolated(NS,MARK)

    def test_actual_raw_removal_uses_leader_and_unrelated_creation_follows_new_cleanup(self):
        e=events(self.edu); before=e[NS+'.3003'];after=e[NS+'.3004']
        self.assertFalse(any(k in ('create_faction','dismantle_faction') for k,o,v in walk(before)))
        removals=[(k,v) for k,o,v in before if isinstance(v,list) and any(x=='remove_from_faction' for x,_,_ in v)]
        self.assertEqual(removals,[('AUS',[('remove_from_faction','=','SWE')])])
        logs=[(index,value) for index,(key,op,value) in enumerate(after) if key=='log']
        new_end=next(i for i,v in logs if v==MARK+' END '+I.REMOVE_LABEL)
        old_begin=next(i for i,v in logs if v==MARK+' BEGIN '+I.LEGACY_REMOVE)
        create=next(i for i,(k,o,v) in enumerate(after) if k=='SWE' and any(n=='create_faction' for n,_,_ in v))
        self.assertLess(new_end,create);self.assertLess(create,old_begin)
        self.assertIn('is_in_faction = no',self.edu['expectations'][I.REMOVE_LABEL]['predicate'])

    def test_both_cleanup_adapters_emit_checks_outside_original_condition(self):
        for ident,stamp in ((7401,I.CLEANUP_STAMPS[0]),(7448,I.CLEANUP_STAMPS[1])):
            body=events(self.ext)[NS+'.'+str(ident)]
            begins=[v for k,o,v in body if k=='log' and v.startswith(MARK+' BEGIN extension_runtime_action_')]
            suffix=stamp.removeprefix('HANDLER_').lower()
            self.assertIn(MARK+' BEGIN extension_runtime_'+suffix+'_planned_or_untaken_dispatch_count',begins)
            self.assertIn(MARK+' BEGIN extension_runtime_'+suffix+'_revocation_cleans_consumed_or_pending_notice',begins)

    def test_new_condition_witnesses_preserve_actual_required_observation_order(self):
        text=self.ext['fixture_text'][f'events/{NS}.txt'];original=I.EXT.build_source_runtime(NS,MARK)
        names=self.ext['required_observations']
        self.assertEqual([n for n in names if n in original['required_observations']],original['required_observations'])
        positions=[text.index(MARK+' OBS '+label+' ') for label in names]
        self.assertEqual(positions,sorted(positions))
        for action in I.cleanup_contract()['actions']:
            before=text.index(MARK+' OBS '+action['condition_observation']+' ')
            self.assertLess(before,text.index(MARK+' TRACE '+action['before_trace']+' '))

    def test_each_cleanup_handler_and_gate_retain_original_article50_condition(self):
        for ident,num in ((7401,1),(7448,55)):
            body=events(self.ext)[NS+'.'+str(ident)];matches=[]
            for key,op,value in body:
                if key!='if':continue
                names=[k for k,o,v in value]
                if 'limit' in names and any(k=='log' and isinstance(v,str) and f'HANDLER_ACTION_{num:03d}_EON_EU_REVOKE_WITHDRAWAL_SOURCE_COMPLETE_AST_INVOKED' in v for k,o,v in value):matches.append(value)
                if 'limit' in names and any(k=='set_variable' and any(n==f'global.{NS}_handler_{num:03d}_gate' and x=='1' for n,o,x in v) for k,o,v in value if isinstance(v,list)):matches.append(value)
            self.assertEqual(len(matches),2)
            for value in matches:self.assertIn(('has_country_flag','=','Article_50'),next(v for k,o,v in value if k=='limit'))

    def test_all_prior_predicates_clocks_handlers_and_migrations_are_exact(self):
        old=I.V17.build_edu_confirmation(NS,MARK)
        self.assertEqual([n for n in self.edu['assertions'] if n!=I.REMOVE_LABEL],old['assertions'])
        for label,value in old['expectations'].items():self.assertEqual(self.edu['expectations'][label],value)
        for key in ('required_elapsed_game_time','baseline41_contract','baseline41_migration_map','edu_source_handler_runtime_contract'):
            self.assertEqual(self.edu[key],old[key])
        oldext=I.EXT.build_source_runtime(NS,MARK)
        for key in ('assertions','expectations','required_elapsed_game_time','baseline114_contract','source_handler_runtime_contract'):
            self.assertEqual(self.ext[key],oldext[key])

    def test_isolated_native_witnesses_are_accepted_only_in_strict_order(self):
        self.assertTrue(I.edu_removal_isolation_result(I.removal_contract(),removal_log(),MARK)['passed'])
        rows=removal_log().splitlines();rows[2],rows[4]=rows[4],rows[2]
        self.assertFalse(I.edu_removal_isolation_result(I.removal_contract(),'\n'.join(rows),MARK)['passed'])

    def test_wrong_context_and_fabricated_removal_receipts_are_rejected(self):
        for old,new in (('actor=1 scope=1 expected_actor=1','actor=1 scope=2 expected_actor=1'),
                        ('factionless=1','factionless=0'),('member=0','member=8'),
                        ('return_receipt=0 leave=3','return_receipt=8 leave=3'),
                        ('EON_EDU LEAVE_HOOK','NO_NATIVE_HOOK'),('actor=2 scope=2 sender=1','actor=1 scope=1 sender=1')):
            with self.subTest(change=old):self.assertFalse(I.edu_removal_isolation_result(I.removal_contract(),removal_log().replace(old,new),MARK)['passed'])

    def test_duplicate_or_missing_removal_frame_is_not_accepted(self):
        rows=removal_log().splitlines()
        for text in ('\n'.join(rows[:1]+rows[2:]),removal_log()+'\n'+rows[1]):
            self.assertFalse(I.edu_removal_isolation_result(I.removal_contract(),text,MARK)['passed'])

    def test_cleanup_taken_and_untaken_receipts_are_both_required(self):
        for taken in (True,False):
            with self.subTest(taken=taken):self.assertTrue(I.extension_cleanup_dispatch_result(I.cleanup_contract(),cleanup_log(taken),MARK)['passed'])

    def test_untaken_cleanup_cannot_invoke_or_fake_increment(self):
        text=cleanup_log(False)
        for changed in (text.replace('handler_count=2','handler_count=3',1),
                        text+'\n'+MARK+' TRACE '+I.cleanup_contract()['actions'][0]['invoke_trace'],
                        text.replace('value=0','value=1').replace('gate=0','gate=1')):
            self.assertFalse(I.extension_cleanup_dispatch_result(I.cleanup_contract(),changed,MARK)['passed'])

    def test_taken_cleanup_requires_original_condition_and_exact_one_invoke(self):
        text=cleanup_log(True)
        for changed in (text.replace('value=1','value=0',1),text.replace('_SOURCE_COMPLETE_AST_INVOKED','_MISSING_INVOKE',1),
                        text+'\n'+MARK+' TRACE '+I.cleanup_contract()['actions'][0]['invoke_trace']):
            self.assertFalse(I.extension_cleanup_dispatch_result(I.cleanup_contract(),changed,MARK)['passed'])

    def test_missing_conditional_checks_stays_failure(self):
        text=cleanup_log(False);rows=text.splitlines()
        self.assertFalse(I.extension_cleanup_dispatch_result(I.cleanup_contract(),'\n'.join(rows[:-2]+rows[-1:]),MARK)['passed'])

    def test_manifest_contracts_cannot_forge_context_or_condition(self):
        r=I.removal_contract();r['source_input']='SWE = { remove_from_faction = THIS }'
        self.assertFalse(I.edu_removal_isolation_result(r,removal_log(),MARK)['passed'])
        c=I.cleanup_contract();c['actions'][0]['original_condition']='always = yes'
        self.assertFalse(I.extension_cleanup_dispatch_result(c,cleanup_log(True),MARK)['passed'])

    def test_actual_fixture_wrong_context_or_early_creation_mutants_fail(self):
        path=f'events/{NS}.txt'
        for old,new in (('AUS = { remove_from_faction = SWE }','SWE = { remove_from_faction = THIS }'),
                        (f'log = "{MARK} END {I.REMOVE_LABEL}" SWE = {{ create_faction = "Private EDU unrelated control" }}',
                         f'SWE = {{ create_faction = "Private EDU unrelated control" }} log = "{MARK} END {I.REMOVE_LABEL}"')):
            m=deepcopy(self.edu);self.assertIn(old,m['fixture_text'][path]);m['fixture_text'][path]=m['fixture_text'][path].replace(old,new)
            with self.assertRaises(AssertionError):I.validate_removal_fixture(m,NS,MARK)

    def test_untaken_receipt_cannot_hide_canonical_ledger_change(self):
        text=cleanup_log(False);a=I.cleanup_contract()['actions'][0]['after_trace']
        line=next(r for r in text.splitlines() if 'TRACE '+a+' ' in r)
        self.assertFalse(I.extension_cleanup_dispatch_result(I.cleanup_contract(),text.replace(line,line.replace('queue=0','queue=1')),MARK)['passed'])

    def test_omitted_original_cleanup_source_gate_is_rejected(self):
        path=f'events/{NS}.txt';m=deepcopy(self.ext)
        definitions=ast(m['fixture_text'][path]);changed=False
        for key,op,fields in definitions:
            if key!='country_event' or next(v for k,o,v in fields if k=='id')!=NS+'.7401':continue
            for k,o,body in next(v for k,o,v in fields if k=='immediate'):
                if k!='if':continue
                if any(n=='set_variable' and (f'global.{NS}_handler_001_gate','=','1') in v for n,o,v in body if isinstance(v,list)):
                    next(v for n,o,v in body if n=='limit').remove(('has_country_flag','=','Article_50'));changed=True
        self.assertTrue(changed);m['fixture_text'][path]=I.render(definitions)
        with self.assertRaises(AssertionError):I.validate_cleanup_fixture(m,NS,MARK)

    def test_unknown_version_never_inherits_v18_override_family(self):
        from runtime_override_support import override_actions
        for version in (19,0,'18',True):
            with self.assertRaises(AssertionError):override_actions(version)

    def test_source_bound_analyzer_rejects_forged_v18_contract_and_predicate(self):
        from runtime_override_support import override_actions
        with tempfile.TemporaryDirectory(prefix='synthetic-v18-bound-',dir=B.ROOT/'.local') as tmp:
            base=Path(tmp);m=B.build(B.ROOT,base/'template',authoritative_template=True)
            effective=base/'effective';provenance=base/'provenance'
            for rel in override_actions(18):
                dst=provenance/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(B.ROOT/rel,dst)
            for rel in m['fixture_sha256']:
                dst=effective/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(base/'template/mod'/rel,dst)
            bound=deepcopy(m);bound.update(source_root=str(effective),fixture_root=str(base/'template/mod'),provenance_root=str(provenance))
            self.assertEqual(runtime_provenance_problems(bound,effective,base/'template/mod'),[])
            for kind in ('version','condition','scope','predicate'):
                mutant=deepcopy(bound)
                if kind=='version':mutant['fixture_version']=19;mutant['marker']='EON_EU_NATIVE_V19'
                elif kind=='condition':mutant['extension_cleanup_dispatch_contract']['actions'][0]['original_condition']='always = yes'
                elif kind=='scope':mutant['edu_removal_isolation_contract']['removal_actor']='SWE'
                else:mutant['expectations'][I.REMOVE_LABEL]['predicate']='always = yes'
                with self.subTest(kind=kind):self.assertTrue(runtime_provenance_problems(mutant,effective,base/'template/mod'))

    def test_default_v18_composition_has_one_new_assertion_and_historical_v17_path(self):
        with tempfile.TemporaryDirectory(prefix='synthetic-v18-',dir=B.ROOT/'.local') as tmp:
            m=B.build(B.ROOT,Path(tmp)/'template',validate_only=True,authoritative_template=True)
            old=B.build_v17(B.ROOT,Path(tmp)/'historical',validate_only=True,authoritative_template=True)
            self.assertEqual((m['fixture_version'],m['marker'],len(m['assertions']),m['events'],len(m['fixture_sha256'])),(18,MARK,519,145,9))
            self.assertEqual((old['fixture_version'],len(old['assertions']),old['events'],len(old['fixture_sha256'])),(17,518,145,9))
            self.assertEqual([n for n in m['assertions'] if n!=I.REMOVE_LABEL],old['assertions'])
            changes=[]
            for label,value in old['expectations'].items():
                if m['expectations'][label]!=value:
                    changes.append(label);expected=deepcopy(value)
                    before=f'var = global.{NS}_fixture_version value = 17 compare = equals'
                    self.assertEqual(expected['predicate'].count(before),1)
                    expected['predicate']=expected['predicate'].replace(before,before.replace('value = 17','value = 18'))
                    self.assertEqual(m['expectations'][label],expected)
            self.assertEqual(changes,['actual_original_startup_has_fifteen_recognized_members_once'])
            self.assertEqual(m['required_elapsed_game_time'],old['required_elapsed_game_time'])
            self.assertEqual(m['baseline41_migration_map'],old['baseline41_migration_map'])


if __name__=='__main__':unittest.main(verbosity=2)
