"""v15 source/receipt contracts. Synthetic roots/logs are not native proof."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta

import build_native_probe as B
from analyze_native_probe import runtime_provenance_problems, analyze
from runtime_override_support import RUNTIME_OVERRIDE_ACTIONS
from runtime_support import GOLDEN114, SOURCE_METHOD, build_runtime, source_handler_callback_result


class V15NativeContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='synthetic-v15-',dir=B.ROOT/'.local')
        cls.base = Path(cls.temp.name)
        runtime = build_runtime(B.NS, B.MARK_V15, source=B.ROOT)
        edu = B.build_edu(B.NS, B.MARK_V15, source=B.ROOT)
        extra = B.default_additive_builders()
        modules = [runtime, edu] + [f(B.NS,B.MARK_V15,source=B.ROOT) for f in extra.values()]
        paths = set(p for m in modules for p in m['production_dependency_paths'])
        paths.add('common/decisions/EU_POTEF_decisions.txt')
        for area in ('membership','voting','institutions'):
            for kind in ('effects','triggers'): paths.add(f'common/scripted_{kind}/eon_eu_{area}_{kind}.txt')
        paths.update(('common/scripted_effects/eon_eu_lifecycle_effects.txt','common/scripted_triggers/eon_eu_financial_triggers.txt'))
        cls.source = cls.base/'authoritative-source'
        for rel in paths:
            target=cls.source/rel;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(B.ROOT/rel,target)
        cls.validated = B.build_v15(cls.source,cls.base/'validate-only',validate_only=True)
        cls.written = B.build_v15(cls.source,cls.base/'template')
        cls.effective = cls.base/'effective-source';shutil.copytree(cls.source,cls.effective)
        cls.provenance = cls.base/'authoritative-provenance'
        for rel in cls.written['fixture_sha256']:
            dst=cls.effective/rel;dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(cls.base/'template/mod'/rel,dst)
        for rel in RUNTIME_OVERRIDE_ACTIONS:
            dst=cls.provenance/rel;dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(cls.source/rel,dst)
        cls.bound=deepcopy(cls.written)
        cls.bound.update(source_root=str(cls.effective),fixture_root=str(cls.base/'template/mod'),provenance_root=str(cls.provenance))

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def test_v15_default_composition_derives_counts_and_requires_both_modules(self):
        m=self.written
        self.assertEqual(m['fixture_version'],15);self.assertEqual(m['marker'],'EON_EU_NATIVE_V15')
        self.assertEqual(len(m['assertions']), m['core_assertions']+sum(x['assertions'] for x in m['native_modules'].values()))
        self.assertEqual(len(m['assertions']),568);self.assertEqual(m['events'],141)
        self.assertEqual(m['native_modules']['extension']['assertions'],324)
        self.assertEqual(m['native_modules']['extension']['events'],60)
        self.assertEqual(m['additive_module_contract']['required'],['council','parliament'])
        self.assertTrue(m['additive_module_contract']['acceptance_ready'])
        self.assertEqual(m['coordinator_isolation_contract']['declared_hold_days'],180)

    def test_exact_seven_files_merge_runtime_without_standalone_metadata(self):
        m=self.written;self.assertEqual(len(m['fixture_sha256']),7)
        self.assertTrue(set(RUNTIME_OVERRIDE_ACTIONS)<=set(m['fixture_sha256']))
        self.assertNotIn('descriptor.mod',m['fixture_sha256'])
        text=(self.base/'template/mod'/f'common/on_actions/{B.NS}.txt').read_text()
        self.assertEqual(text.count('STARTUP'),1)
        self.assertIn('STARTUP fixture_version=15',text)
        self.assertIn(f'global.{B.NS}_handler_invocations = 0',text)
        self.assertIn('COUNCIL_DAILY',text);self.assertIn('PARLIAMENT_SOURCE_DAILY_RECONCILE',text)

    def test_validate_only_and_written_have_same_runtime_binding_no_write(self):
        self.assertFalse((self.base/'validate-only').exists())
        for k in ('assertions','expectations','native_modules','runtime_overrides','source_sha256',
                  'effective_source_sha256','provenance_sha256','fixture_sha256','source_handler_runtime_contract',
                  'baseline114_contract','baseline114_sha256','required_elapsed_game_time'):
            self.assertEqual(self.validated[k],self.written[k],k)

    def test_baseline144_and114_are_preserved_and_method_is_separate(self):
        m=self.written;self.assertEqual(m['baseline_v12_contract_sha256'],B.BASELINE_V12_SHA256)
        self.assertEqual(m['baseline114_sha256'],GOLDEN114)
        self.assertEqual(hashlib.sha256(json.dumps(m['baseline114_contract'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),GOLDEN114)
        self.assertEqual(m['extension_runtime_method'],SOURCE_METHOD)
        self.assertTrue(m['negative_native109_history_preserved'])
        self.assertNotIn('extension_callback_contract',m)
        self.assertEqual(len(m['source_handler_runtime_contract']['actions']),30)

    def test_original_sidecars_and_effective_files_are_independently_validated(self):
        self.assertEqual(runtime_provenance_problems(self.bound,self.effective,self.base/'template/mod'),[])
        for rel,row in self.bound['runtime_overrides'].items():
            self.assertEqual(row['source_sha256'],self.bound['source_sha256'][rel])
            self.assertEqual(row['runtime_override_sha256'],self.bound['effective_source_sha256'][rel])
            self.assertNotEqual(row['source_sha256'],row['runtime_override_sha256'])

    def test_swapping_original_and_effective_maps_or_roots_fails(self):
        for kind in ('source','effective','provenance','root','idset','extra','old_api'):
            m=deepcopy(self.bound);rel=next(iter(RUNTIME_OVERRIDE_ACTIONS))
            if kind=='source':m['source_sha256'][rel]=m['effective_source_sha256'][rel]
            elif kind=='effective':m['effective_source_sha256'][rel]=m['source_sha256'][rel]
            elif kind=='provenance':m['provenance_sha256'][rel]='0'*64
            elif kind=='root':m['provenance_root']=str(self.effective)
            elif kind=='idset':m['runtime_overrides'][rel]['selected_ai_action_ids'].append('ninth')
            elif kind=='extra':m['runtime_overrides'][rel]['extra']='unknown'
            else:m['extension_callback_contract']={'schema':1}
            with self.subTest(kind=kind):self.assertTrue(runtime_provenance_problems(m,self.effective,self.base/'template/mod'))

    def test_non_ai_active_or_provenance_mutation_is_detected(self):
        rel=next(iter(RUNTIME_OVERRIDE_ACTIONS))
        for root in (self.effective,self.provenance):
            p=root/rel;old=p.read_bytes()
            try:
                p.write_bytes(old+b'\n# foreign edit\n')
                self.assertTrue(runtime_provenance_problems(self.bound,self.effective,self.base/'template/mod'))
            finally:p.write_bytes(old)

    def test_builder_rejects_foreign_runtime_asset_and_unknown_ai_edit(self):
        original=build_runtime
        for kind in ('asset','bytes'):
            def mutant(*args,**kwargs):
                m=original(*args,**kwargs)
                if kind=='asset':m['fixture_text']['common/ideas/unreviewed.txt']='foreign = { }\n'
                else:
                    rel=next(iter(RUNTIME_OVERRIDE_ACTIONS));m['fixture_text'][rel]+='\n# foreign edit\n'
                return m
            with self.subTest(kind=kind):
                with patch('runtime_support.build_runtime',mutant):
                    with self.assertRaises(AssertionError):B.build_v15(self.source,self.base/('rejected-'+kind),validate_only=True)

    def test_public_builder_inputs_hash_actual_normal_public_files(self):
        for name,row in self.written['native_builder_inputs'].items():
            p=Path(row['path']);self.assertTrue(p.is_relative_to(B.ROOT/'tools/validation'),name)
            self.assertEqual(row['sha256'],hashlib.sha256(p.read_bytes()).hexdigest())
        self.assertIn('runtime_override',self.written['native_builder_inputs'])
        self.assertIn('extension_base',self.written['native_builder_inputs'])
        for name in ('runtime_support.py','runtime_override_support.py','build_native_probe.py','analyze_native_probe.py'):
            self.assertNotIn('.local/',(B.ROOT/'tools/validation/eu_lifecycle'/name).read_text())

    def test_analyzer_requires_backend_receipts_instead_of_assertion_counts(self):
        area=self.base/'synthetic-missing-backend';area.mkdir()
        m=deepcopy(self.bound);m['required_observations']=[];m['required_elapsed_game_time']=[]
        m['required_named_factions']=[]
        # Removing all clocks is itself rejected by the immutable114 contract.
        manifest=area/'manifest.json';manifest.write_text(json.dumps(m))
        text=[m['marker']+' STARTUP fixture_version=15',m['marker']+' RUN_BEGIN']
        for label in m['assertions']:text.extend(m['marker']+' '+s+' '+label for s in ('BEGIN','PASS','END'))
        text.append(m['marker']+f' RUN_END passes={len(m["assertions"])} fails=0')
        log=area/'game.log';log.write_text('\n'.join(text));errors=area/'error.log';errors.write_text('')
        result=analyze(manifest,log,errors)
        self.assertFalse(result['passed']);self.assertFalse(result['source_handler_runtime_evidence']['passed'])
        self.assertIsNone(result['extension_callback_evidence'])
        self.assertTrue(any('source_handler_runtime_contract_failed' in p for p in result['problems']))

    def test_full_synthetic_analyzer_accepts_paired_provenance_and_backend_only_method(self):
        from test_source_handler_runtime import fractional_token_receipt
        area=self.base/'synthetic-full-positive';area.mkdir()
        m=deepcopy(self.bound);marker=m['marker']
        lines=[marker+' STARTUP fixture_version=15',marker+' RUN_BEGIN']
        for label in m['assertions']:lines.extend(marker+' '+s+' '+label for s in ('BEGIN','PASS','END'))
        backend=fractional_token_receipt().replace('SYNTHETIC_ONLY',marker).splitlines()
        # Interface OBS is explicitly optional UI diagnostic. The strict
        # backend validator independently requires all30 actual trace groups.
        lines.extend('[2000.01.01.01] '+line for line in backend)
        groups={}
        for action in m['source_handler_runtime_contract']['actions']:
            stamp=action['stamp'];selected=[line for line in backend if stamp+'_' in line]
            interface='EXTENSION_'+stamp+'_INTERFACE_ACTIVE'
            groups[interface]=selected
        atomic={};diag=m['faction_identity_diagnostic']
        for field in ('required_native_preconditions','structure_positive_labels','clock_advance_labels','natural_flag_positive_labels'):
            atomic.update(dict.fromkeys(diag.get(field,[]),1))
        for field in ('structure_negative_labels','marker_positive_labels','marker_negative_labels','control_positive_labels',
                      'control_negative_labels','natural_flag_negative_labels'):
            atomic.update(dict.fromkeys(diag.get(field,[]),0))
        atomic[diag['no_dlc_label']]=0
        for index,label in enumerate(m['required_observations']):
            dt=datetime(2000,1,1)+timedelta(hours=400*index)
            stamp='['+((dt-timedelta(days=1)).strftime('%Y.%m.%d')+'.24' if dt.hour==0 else dt.strftime('%Y.%m.%d.%H'))+'] '
            if label in groups:
                continue
            payload='value='+str(atomic.get(label,1))
            if label in ('NATO_NEXT_NATIVE_HOUR_NAMES','NATO_AFTER_EU_EXIT_NAMES'):payload='usa=NATO pol=NATO'
            if label=='EDU_START':payload='actor=1078.5 founder=1078.5'
            elif label=='EDU_ACTUAL_CREATE_RETURN':payload='actor=1078.5 scope=1078.5 sender=1080.22'
            lines.append(stamp+marker+' OBS '+label+' '+payload)
            if label=='EDU_START':
                pair=' actor=1078.5 scope=1078.5 sender=1080.22'
                lines.extend(stamp+trace+pair for trace in ('EON_EDU CREATE_DECISION','EON_EDU FORMED_HOOK','EON_EDU FORMED_COMMIT',
                                                         'EON_EDU LEAVE_HOOK','EON_EDU LEADERSHIP_HOOK','EON_EDU FORMED_HOOK','EON_EDU FORMED_COMMIT'))
        lines.append(marker+f' RUN_END passes={len(m["assertions"])} fails=0')
        manifest=area/'manifest.json';manifest.write_text(json.dumps(m))
        log=area/'game.log';log.write_text('\n'.join(lines));errors=area/'error.log';errors.write_text('')
        result=analyze(manifest,log,errors)
        self.assertTrue(result['passed'],result['problems'])
        self.assertEqual(result['source_handler_runtime_evidence']['method'],SOURCE_METHOD)
        self.assertIsNone(result['extension_callback_evidence'])
        self.assertIn('Decision engine click',result['source_handler_runtime_evidence']['claims_excluded'])


if __name__=='__main__':unittest.main(verbosity=2)
