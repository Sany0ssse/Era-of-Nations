"""Synthetic source/evidence contracts; never native acceptance."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import shutil
import tempfile
import unittest

import edu_confirmation_runtime_support as C
import edu_runtime_support as V16
import build_native_probe as B
from analyze_native_probe import runtime_provenance_problems,analyze
from runtime_override_support import override_actions

NS='eon_native_eu_probe';MARK='SYNTHETIC_V17_ONLY'


def receipt(route='creation_return'):
    actor='10792.03137';rows=[MARK+' RUN_BEGIN',MARK+' OBS EDU_START actor='+actor+' founder='+actor]
    for n,(stamp,instance) in enumerate((('EDU_SOURCE_00',12),('EDU_SOURCE_14',14)),1):
        payload=f'actor={actor} scope={actor} sender={actor} attempt={n+2} reserved={instance} intent={instance} constructor_instance={instance}'
        rows.extend((MARK+' TRACE '+stamp+'_BEFORE_SOURCE_HANDLER actor='+actor+' scope='+actor,
          'EON_EDU CREATE_DECISION actor='+actor+' scope='+actor+' sender='+actor,
          'EON_EDU CTOR_BEFORE '+payload+f' factionless=1 confirmation_before={n-1} constructor_before={n-1} native_before=0',
          'EON_EDU CONFIRM_COMMIT '+payload+f' route={route} instance={instance} confirmation={n}',
          'EON_EDU CTOR_RETURN '+payload+f' remaining_intent=0 in_faction=1 is_leader=1 result=1 instance={instance} member_instance={instance} return_receipt={instance} confirmation={n} constructor={n} native=0',
          MARK+' TRACE '+stamp+'_AFTER_SOURCE_HANDLER actor='+actor+' scope='+actor))
        if n==1:rows.append(MARK+' OBS EDU_ACTUAL_CREATE_RETURN actor='+actor+' scope='+actor+' sender='+actor)
    rows.extend(('EON_EDU LEAVE_HOOK actor='+actor+' scope='+actor+' sender='+actor,
                 MARK+' OBS EDU_TERMINAL instance=14 counter=14',MARK+' RUN_END passes=518 fails=0'))
    return '\n'.join(rows)


def contract():
    return {'schema':1,'method':C.METHOD,'expected_authorized_confirmations':2,
      'creation_stamps':['EDU_SOURCE_00','EDU_SOURCE_14'],
      'start_observation':'EDU_START','end_observation':'EDU_TERMINAL',
      'required_creation_actor_observation':'EDU_ACTUAL_CREATE_RETURN',
      'migration_map':dict(C.MIGRATION),'native_hook_diagnostics':['EON_EDU FORMED_HOOK','EON_EDU LEADERSHIP_HOOK'],
      'required_leave_log':'EON_EDU LEAVE_HOOK'}


class V17ConfirmationContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old=V16.build_edu_runtime(NS,MARK)
        cls.new=C.build_edu_confirmation(NS,MARK)

    def test_exact_two_label_migration_keeps_other39_handlers_and_clocks(self):
        old,new=self.old,self.new
        self.assertEqual(hashlib.sha256(Path(V16.__file__).read_bytes()).hexdigest(),C.V16_SHA256)
        self.assertEqual(new['baseline41_sha256'],old['baseline41_sha256'])
        self.assertEqual(new['baseline41_golden_sha256'],V16.GOLDEN41)
        self.assertEqual(new['assertions'],[C.MIGRATION.get(x,x) for x in old['assertions']])
        for label,value in old['expectations'].items():
            if label not in C.MIGRATION:self.assertEqual(new['expectations'][label],value)
        for key in ('edu_source_handler_runtime_contract','actual_source_callback_ast','required_elapsed_game_time',
                    'required_observations','baseline41_contract','runtime_overrides'):
            self.assertEqual(new[key],old[key],key)
        path=f'events/{NS}.txt';original=V16.LEGACY.ast(old['fixture_text'][path]);migrated=V16.LEGACY.ast(new['fixture_text'][path])
        def undo(nodes):
            out=[]
            for key,op,value in nodes:
                if isinstance(value,list):
                    for previous,current in C.MIGRATION.items():
                        if value==V16.LEGACY.ast(new['expectations'][current]['predicate']):
                            value=V16.LEGACY.ast(old['expectations'][previous]['predicate']);break
                    else:value=undo(value)
                else:
                    for previous,current in C.MIGRATION.items():value=value.replace(current,previous)
                out.append((key,op,value))
            return out
        self.assertEqual(undo(migrated),original,'Only two assertion blocks may migrate')
        for p in old['fixture_text']:
            if p!=path:self.assertEqual(old['fixture_text'][p],new['fixture_text'][p])

    def test_actual_creation_receipt_passes_without_fabricating_native_hooks(self):
        result=C.edu_confirmation_result(contract(),receipt(),MARK)
        self.assertTrue(result['passed'],result)
        self.assertEqual(result['native_hook_counts'],{'EON_EDU FORMED_HOOK':0,'EON_EDU LEADERSHIP_HOOK':0})

    def test_forged_or_unbound_creation_frames_fail_closed(self):
        base=receipt()
        for before,after in (
            ('factionless=1','factionless=0'),('in_faction=1','in_faction=0'),('is_leader=1','is_leader=0'),
            ('remaining_intent=0','remaining_intent=12'),('result=1','result=3'),
            ('reserved=12 intent=12','reserved=13 intent=12'),('return_receipt=12','return_receipt=11'),
            ('confirmation=1','confirmation=2'),('actor=10792.03137 scope=10792.03137','actor=10793.03137 scope=10793.03137')):
            with self.subTest(before=before):
                self.assertFalse(C.edu_confirmation_result(contract(),base.replace(before,after,1),MARK)['passed'])
        missing='\n'.join(r for r in base.splitlines() if not r.startswith('EON_EDU CTOR_BEFORE'))
        self.assertFalse(C.edu_confirmation_result(contract(),missing,MARK)['passed'])
        first=next(r for r in base.splitlines() if r.startswith('EON_EDU CTOR_BEFORE'))
        self.assertFalse(C.edu_confirmation_result(contract(),first+'\n'+base.replace(first+'\n','',1),MARK)['passed'])
        self.assertFalse(C.edu_confirmation_result(contract(),base.replace('EON_EDU LEAVE_HOOK','UNRELATED_LEAVE_HOOK'),MARK)['passed'])
        for kind in ('label','count'):
            c=contract()
            if kind=='label':c['migration_map'].pop(next(iter(C.MIGRATION)))
            else:c['expected_authorized_confirmations']=1
            self.assertFalse(C.edu_confirmation_result(c,base,MARK)['passed'])

    def test_native_route_requires_real_hook_and_keeps_absence_diagnostic(self):
        text=receipt()
        for n,instance in ((1,12),(2,14)):
            actor='10792.03137'
            line=next(r for r in text.splitlines() if r.startswith('EON_EDU CONFIRM_COMMIT') and f'instance={instance} ' in r)
            text=text.replace(line,'EON_EDU FORMED_HOOK actor='+actor+' scope='+actor+' sender='+actor+'\n'+line.replace('route=creation_return','route=native_formed'),1)
            line=next(r for r in text.splitlines() if r.startswith('EON_EDU CTOR_BEFORE') and f'reserved={instance} ' in r)
            text=text.replace(line,line.replace(f'constructor_before={n-1} native_before=0',f'constructor_before=0 native_before={n-1}'),1)
            line=next(r for r in text.splitlines() if r.startswith('EON_EDU CTOR_RETURN') and f'reserved={instance} ' in r)
            text=text.replace(line,line.replace(f'return_receipt={instance}', 'return_receipt=0').replace(f'constructor={n} native=0',f'constructor=0 native={n}'),1)
        result=C.edu_confirmation_result(contract(),text,MARK)
        self.assertTrue(result['passed'],result)
        self.assertEqual(result['native_hook_counts']['EON_EDU FORMED_HOOK'],2)
        self.assertFalse(C.edu_confirmation_result(contract(),text.replace('EON_EDU FORMED_HOOK','NO_REAL_HOOK'),MARK)['passed'])

    def test_v17_composition_binds_provenance_and_retains_explicit_v16_path(self):
        modules=[self.new]
        from extension_source_runtime_support import build_source_runtime
        modules.append(build_source_runtime(NS,MARK))
        modules += [fn(NS,MARK,source=B.ROOT) for fn in B.default_additive_builders().values()]
        paths={p for m in modules for p in m['production_dependency_paths']}
        paths.add('common/decisions/EU_POTEF_decisions.txt')
        for area in ('membership','voting','institutions'):
            for kind in ('effects','triggers'):paths.add(f'common/scripted_{kind}/eon_eu_{area}_{kind}.txt')
        paths.update(('common/scripted_effects/eon_eu_lifecycle_effects.txt','common/scripted_triggers/eon_eu_financial_triggers.txt'))
        with tempfile.TemporaryDirectory(prefix='synthetic-v17-',dir=B.ROOT/'.local') as tmp:
            base=Path(tmp);source=base/'authoritative-source'
            for rel in paths:
                dst=source/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(B.ROOT/rel,dst)
            m=B.build_v17(source,base/'template')
            self.assertEqual((m['fixture_version'],m['marker']),(17,'EON_EU_NATIVE_V17'))
            self.assertEqual((len(m['assertions']),m['events'],len(m['fixture_sha256'])),(518,145,9))
            self.assertEqual(m['baseline41_migration_map'],C.MIGRATION)
            self.assertEqual(m['edu_confirmation_contract']['method'],C.METHOD)
            self.assertEqual(m['edu_source_handler_runtime_contract'],self.new['edu_source_handler_runtime_contract'])
            self.assertIn('edu_v16_base',m['native_builder_inputs'])
            self.assertEqual(m['edu_runtime_method'],C.METHOD)
            effective=base/'effective';shutil.copytree(source,effective)
            provenance=base/'provenance'
            for rel in m['fixture_sha256']:
                dst=effective/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(base/'template/mod'/rel,dst)
            for rel in override_actions(17):
                dst=provenance/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/rel,dst)
            bound=deepcopy(m);bound.update(source_root=str(effective),fixture_root=str(base/'template/mod'),provenance_root=str(provenance))
            self.assertEqual(runtime_provenance_problems(bound,effective,base/'template/mod'),[])
            for kind in ('migration','predicate','method'):
                mutant=deepcopy(bound)
                if kind=='migration':mutant['baseline41_migration_map']={}
                elif kind=='predicate':mutant['expectations'][next(iter(C.MIGRATION.values()))]['predicate']='always = yes'
                else:mutant['edu_runtime_method']=V16.SOURCE_METHOD
                self.assertTrue(runtime_provenance_problems(mutant,effective,base/'template/mod'))
            old=B.build_v16(source,base/'v16',validate_only=True)
            self.assertEqual(old['fixture_version'],16)
            for label,value in old['baseline41_contract']['expectations'].items():self.assertEqual(old['expectations'][label],value)
            # A ledger-only synthetic PASS cannot replace the actual constructor frames.
            gp=base/'game.log';ep=base/'error.log';mp=base/'bound.json'
            gp.write_text('\n'.join([m['marker']+' STARTUP fixture_version=17',m['marker']+' RUN_BEGIN']+
              [m['marker']+' '+s+' '+label for label in m['assertions'] for s in ('BEGIN','PASS','END')]+
              [m['marker']+' RUN_END passes=518 fails=0']),encoding='utf-8')
            ep.write_text('',encoding='utf-8');mp.write_text(json.dumps(bound),encoding='utf-8')
            evidence=analyze(mp,gp,ep)
            self.assertFalse(evidence['passed']);self.assertFalse(evidence['edu_callback_evidence']['passed'])


if __name__=='__main__':unittest.main()
