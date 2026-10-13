"""V16 composition/provenance controls; synthetic logs are not native proof."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta

import build_native_probe as B
from analyze_native_probe import analyze, runtime_provenance_problems
from runtime_override_support import override_actions
from extension_source_runtime_support import build_source_runtime
from edu_runtime_support import build_edu_runtime, GOLDEN41
from runtime_support import GOLDEN114


class V16NativeContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='synthetic-v16-',dir=B.ROOT/'.local')
        cls.base=Path(cls.temp.name);cls.source=cls.base/'authoritative-source'
        modules=[build_source_runtime(B.NS,B.MARK,source=B.ROOT),build_edu_runtime(B.NS,B.MARK,source=B.ROOT)]
        modules += [fn(B.NS,B.MARK,source=B.ROOT) for fn in B.default_additive_builders().values()]
        paths={p for m in modules for p in m['production_dependency_paths']}
        paths.add('common/decisions/EU_POTEF_decisions.txt')
        for area in ('membership','voting','institutions'):
            for kind in ('effects','triggers'):paths.add(f'common/scripted_{kind}/eon_eu_{area}_{kind}.txt')
        paths.update(('common/scripted_effects/eon_eu_lifecycle_effects.txt','common/scripted_triggers/eon_eu_financial_triggers.txt'))
        for rel in paths:
            dst=cls.source/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(B.ROOT/rel,dst)
        cls.validated=B.build_v16(cls.source,cls.base/'validate-only',validate_only=True)
        cls.written=B.build_v16(cls.source,cls.base/'template')
        cls.effective=cls.base/'effective-source';shutil.copytree(cls.source,cls.effective)
        cls.provenance=cls.base/'authoritative-provenance'
        for rel in cls.written['fixture_sha256']:
            dst=cls.effective/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(cls.base/'template/mod'/rel,dst)
        for rel in override_actions(16):
            dst=cls.provenance/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(cls.source/rel,dst)
        cls.bound=deepcopy(cls.written)
        cls.bound.update(source_root=str(cls.effective),fixture_root=str(cls.base/'template/mod'),provenance_root=str(cls.provenance))

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_default_v16_derives_counts_and_preserves_three_golden_contracts(self):
        m=self.written
        self.assertEqual((m['fixture_version'],m['marker']),(16,'EON_EU_NATIVE_V16'))
        self.assertEqual(len(m['assertions']),m['core_assertions']+sum(x['assertions'] for x in m['native_modules'].values()))
        self.assertEqual(m['baseline_v12_contract_sha256'],B.BASELINE_V12_SHA256)
        self.assertEqual(m['baseline114_sha256'],GOLDEN114)
        self.assertEqual(m['baseline41_sha256'],GOLDEN41)
        self.assertEqual(hashlib.sha256(json.dumps(m['baseline41_contract'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),GOLDEN41)
        for key in ('baseline114_contract','baseline41_contract'):
            for label,value in m[key]['expectations'].items():self.assertEqual(m['expectations'][label],value)
            for clock in m[key]['required_elapsed_game_time']:self.assertIn(clock,m['required_elapsed_game_time'])
        self.assertTrue(m['additive_module_contract']['acceptance_ready'])
        self.assertEqual(m['coordinator_isolation_contract']['declared_hold_days'],180)

    def test_exact_nine_fixtures_four_sidecars_and_both_source_methods(self):
        m=self.written
        self.assertEqual(len(m['fixture_sha256']),9)
        self.assertEqual(set(m['runtime_overrides']),set(override_actions(16)))
        self.assertEqual(sum(len(r['selected_ai_action_ids']) for r in m['runtime_overrides'].values()),13)
        self.assertEqual(runtime_provenance_problems(self.bound,self.effective,self.base/'template/mod'),[])
        self.assertEqual(m['source_handler_runtime_contract']['positive_dispatch'],'source-only; independent of raw API outcome')
        self.assertEqual(m['edu_source_handler_runtime_contract']['positive_dispatch'],'source-only; independent of raw API outcome')
        self.assertNotIn('extension_callback_contract',m)
        startup=(self.base/'template/mod'/f'common/on_actions/{B.NS}.txt').read_text()
        self.assertIn('STARTUP fixture_version=16',startup)
        self.assertIn(f'global.{B.NS}_edu_handler_invocations = 0',startup)
        self.assertFalse((self.base/'validate-only').exists())
        for k in ('assertions','expectations','native_modules','runtime_overrides','source_sha256','effective_source_sha256','provenance_sha256','fixture_sha256','baseline41_contract','edu_source_handler_runtime_contract'):
            self.assertEqual(self.validated[k],m[k],k)

    def test_v15_metadata_missing_edu_provenance_or_weakened_original41_is_rejected(self):
        for kind in ('version','sidecar','hash','predicate','clock','method'):
            m=deepcopy(self.bound)
            if kind=='version':m['fixture_version']=15;m['marker']='EON_EU_NATIVE_V15'
            elif kind=='sidecar':m['provenance_sha256'].pop('common/decisions/eon_edu_decisions.txt')
            elif kind=='hash':m['baseline41_sha256']='0'*64
            elif kind=='predicate':
                label=m['baseline41_contract']['assertions'][0];m['expectations'][label]['predicate']='always = yes'
            elif kind=='clock':m['required_elapsed_game_time'].remove(m['baseline41_contract']['required_elapsed_game_time'][0])
            else:m['edu_source_handler_runtime_contract']['positive_dispatch']='raw API fallback'
            with self.subTest(kind=kind):self.assertTrue(runtime_provenance_problems(m,self.effective,self.base/'template/mod'))

    def test_pass_only_assertions_cannot_replace_source_dispatch_or_native_hooks(self):
        marker=self.bound['marker'];labels=self.bound['assertions']
        text=f'{marker} STARTUP\n{marker} RUN_BEGIN\n'
        text+=''.join(f'{marker} BEGIN {label}\n{marker} PASS {label}\n{marker} END {label}\n' for label in labels)
        text+=f'{marker} RUN_END passes={len(labels)} fails=0\n'
        mp=self.base/'manifest.bound.json';gp=self.base/'game.log';ep=self.base/'error.log'
        mp.write_text(json.dumps(self.bound),encoding='utf-8');gp.write_text(text,encoding='utf-8');ep.write_text('',encoding='utf-8')
        result=analyze(mp,gp,ep)
        self.assertFalse(result['passed'])
        self.assertFalse(result['source_handler_runtime_evidence']['passed'])
        self.assertFalse(result['edu_source_handler_runtime_evidence']['passed'])
        self.assertFalse(result['edu_callback_evidence']['passed'])
        self.assertFalse(result['raw_api_diagnostic_evidence']['controls_valid'])
        self.assertFalse(result['edu_raw_api_diagnostic_evidence']['controls_valid'])

    def test_coherent_synthetic_backend_receipt_and_same_constructor_run_bindings(self):
        from test_v16_source_handler_runtime import extension_receipt, edu_receipt, raw_receipt, EX, EU
        m=deepcopy(self.bound);marker=m['marker'];actor='10792.03137'
        lines=[marker+' STARTUP fixture_version=16',marker+' RUN_BEGIN']
        for label in m['assertions']:lines.extend(marker+' '+s+' '+label for s in ('BEGIN','PASS','END'))
        payloads={}
        for block in (extension_receipt(),edu_receipt(),raw_receipt(EX),raw_receipt(EU,edu=True)):
            for row in block.replace('SYNTHETIC_ONLY',marker).splitlines():
                if ' OBS ' in row:
                    label,payload=row.split(' OBS ',1)[1].split(' ',1);payloads[label]=payload
                else:lines.append('[2000.01.01.01] '+row)
        for label,payload in payloads.items():
            if label not in m['required_observations']:
                lines.append('[2000.01.01.01] '+marker+' OBS '+label+' '+payload)
        diag=m['faction_identity_diagnostic'];atomic={}
        for field in ('required_native_preconditions','structure_positive_labels','clock_advance_labels','natural_flag_positive_labels'):
            atomic.update(dict.fromkeys(diag.get(field,[]),1))
        for field in ('structure_negative_labels','marker_positive_labels','marker_negative_labels','control_positive_labels','control_negative_labels','natural_flag_negative_labels'):
            atomic.update(dict.fromkeys(diag.get(field,[]),0))
        atomic[diag['no_dlc_label']]=0
        for index,label in enumerate(m['required_observations']):
            dt=datetime(2000,1,1)+timedelta(hours=400*index)
            prefix='['+((dt-timedelta(days=1)).strftime('%Y.%m.%d')+'.24' if dt.hour==0 else dt.strftime('%Y.%m.%d.%H'))+'] '
            payload=payloads.get(label,'value='+str(atomic.get(label,1)))
            if label in ('NATO_NEXT_NATIVE_HOUR_NAMES','NATO_AFTER_EU_EXIT_NAMES'):payload='usa=NATO pol=NATO'
            if label=='EDU_START':payload=f'actor={actor} founder={actor}'
            elif label=='EDU_ACTUAL_CREATE_RETURN':payload=f'actor={actor} scope={actor} sender=1080.22'
            lines.append(prefix+marker+' OBS '+label+' '+payload)
            if label=='EDU_START':
                pair=f' actor={actor} scope={actor} sender=1080.22'
                lines.extend(prefix+trace+pair for trace in ('EON_EDU CREATE_DECISION','EON_EDU FORMED_HOOK','EON_EDU FORMED_COMMIT','EON_EDU LEAVE_HOOK','EON_EDU LEADERSHIP_HOOK','EON_EDU FORMED_HOOK','EON_EDU FORMED_COMMIT'))
        lines.append(marker+f' RUN_END passes={len(m["assertions"])} fails=0')
        mp=self.base/'combined-manifest.json';gp=self.base/'combined-game.log';ep=self.base/'combined-error.log'
        mp.write_text(json.dumps(m),encoding='utf-8');ep.write_text('',encoding='utf-8')
        text='\n'.join(lines);gp.write_text(text,encoding='utf-8')
        positive=analyze(mp,gp,ep)
        self.assertTrue(positive['passed'],positive['problems'])
        self.assertTrue(positive['edu_callback_evidence']['passed'])
        self.assertTrue(positive['edu_source_handler_runtime_evidence']['passed'])
        self.assertIn('GUI click',positive['edu_source_handler_runtime_evidence']['claims_excluded'])
        first=m['edu_source_handler_runtime_contract']['actions'][0]['stamp']+'_BEFORE_SOURCE_HANDLER'
        trace=next(row for row in lines if ' TRACE '+first+' ' in row)
        # Exact trace content before RUN_BEGIN cannot satisfy the planned dispatch.
        gp.write_text(trace+'\n'+text.replace(trace+'\n','',1),encoding='utf-8')
        outside=analyze(mp,gp,ep)
        self.assertTrue(any('source_runtime_trace_outside_run' in p for p in outside['problems']))
        # Individually valid native actor contexts must belong to the source constructor.
        alternate=text.replace('actor='+actor+' founder='+actor,'actor=10793.03137 founder=10793.03137')
        alternate=alternate.replace('actor='+actor+' scope='+actor+' sender=1080.22','actor=10793.03137 scope=10793.03137 sender=1080.22')
        gp.write_text(alternate,encoding='utf-8');wrong=analyze(mp,gp,ep)
        self.assertTrue(any('edu_source_creation_actor_differs_from_native_hook' in p for p in wrong['problems']))


if __name__=='__main__':unittest.main()
