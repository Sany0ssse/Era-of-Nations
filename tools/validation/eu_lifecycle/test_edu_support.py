"""Native fixture contract checks; never confuse generated text with a game run."""
from copy import deepcopy
from pathlib import Path
import hashlib
import shutil
import tempfile
import unittest
from edu_support import build_edu,ROOT,SOURCE_PATHS,ast

def walk(nodes):
    for key,op,value in nodes:
        yield key,op,value
        if isinstance(value,list): yield from walk(value)

def validate_contract(result):
    assert set(result['fixture_text'])=={'events/eon_native_eu_probe.txt'}
    nodes=list(walk(ast(next(iter(result['fixture_text'].values())))))
    forbidden={'eon_edu_create_decision_effect','eon_edu_accept_request_effect',
      'eon_edu_request_join_effect','eon_edu_reject_request_effect','eon_edu_withdraw_request_effect',
      'eon_edu_on_formed','eon_edu_on_leave','eon_edu_on_assume_leadership','create_faction_from_template'}
    assert not forbidden.intersection(k for k,o,v in nodes), 'Copied/helper native fallback'
    activations=[v for k,o,v in nodes if k=='activate_decision']
    assert activations.count('EU_create_EDU')==4
    assert activations.count('eon_edu_withdraw_request')==1
    targeted=[{k:v for k,o,v in body} for key,op,body in nodes if key=='activate_targeted_decision']
    expected={'eon_edu_request_join':6,'eon_edu_accept_request':3,'eon_edu_reject_request':1}
    for ident,count in expected.items(): assert sum(v['decision']==ident for v in targeted)==count
    assert all(v['target']=='AUS' for v in targeted if v['decision']=='eon_edu_request_join')
    # Mandatory native hook checks may not turn unsupported hooks into a PASS.
    for label in ('scripted_remove_fires_real_leave_cleanup','native_dismantle_clears_all_actual_member_receipts',
                  'actual_native_leadership_hook_reconciles','pending_destroy_recreate_never_commits_foreign_instance'):
        predicate=result['expectations']['edu_'+label]['predicate']
        assert 'has_dlc' not in predicate and 'OR = {' not in predicate
    assert result['contract']['missing_leave_hook_acceptance_blocker'] is True
    assert result['contract']['expected_authorized_formed_commits']==2
    assert len(result['assertions'])==len(set(result['assertions']))
    assert set(result['assertions'])==set(result['expectations'])
    assert len(result['observations'])==len(set(result['observations']))
    assert {n for n,o,v in nodes if n=='activate_decision'}
    return nodes

class EDUFixture(unittest.TestCase):
    def setUp(self): self.result=build_edu('eon_native_eu_probe','EON_EU_NATIVE_V14')
    def test_actual_activations_and_strict_hook_contract(self): validate_contract(self.result)
    def test_unique_private_ids_and_terminal_composition(self):
        result=build_edu('eon_native_eu_probe','EON_EU_NATIVE_V14',terminal_effect='log = "PRIVATE_NEXT_MODULE" ')
        text=next(iter(result['fixture_text'].values()))
        events=[v for k,o,v in ast(text) if k=='country_event']
        ids=[next(v for k,o,v in body if k=='id') for body in events]
        self.assertEqual(ids,[f'eon_native_eu_probe.{n}' for n in range(3000,3016)])
        self.assertEqual(text.count('PRIVATE_NEXT_MODULE'),1)
        self.assertTrue(text.rfind('PRIVATE_NEXT_MODULE')>text.rfind('id = eon_native_eu_probe.3015'))
    def test_production_dependencies_are_actual_bytes(self):
        self.assertEqual(set(self.result['production_dependency_paths']),set(SOURCE_PATHS))
        for path,digest in self.result['production_input_sha256'].items():
            self.assertEqual(digest,hashlib.sha256((ROOT/path).read_bytes()).hexdigest())
    def test_explicit_source_parameter_binds_frozen_source_not_live_checkout(self):
        with tempfile.TemporaryDirectory() as taskdir:
            source=Path(taskdir)
            for relative in SOURCE_PATHS:
                path=source/relative; path.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(ROOT/relative,path)
            path=source/SOURCE_PATHS[0]; path.write_bytes(path.read_bytes()+b'\n# Frozen-only control\n')
            frozen=build_edu('eon_native_eu_probe','EON_EU_NATIVE_V14',source=source)
            self.assertNotEqual(frozen['production_input_sha256'][SOURCE_PATHS[0]],self.result['production_input_sha256'][SOURCE_PATHS[0]])
    def test_production_callback_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as taskdir:
            source=Path(taskdir)
            for relative in SOURCE_PATHS:
                path=source/relative; path.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(ROOT/relative,path)
            path=source/SOURCE_PATHS[2]
            text=path.read_text('utf-8-sig').replace('eon_edu_accept_request_effect = yes','eon_edu_unproved_fallback = yes')
            path.write_text(text,encoding='utf-8')
            with self.assertRaises(AssertionError): build_edu('eon_native_eu_probe','EON_EU_NATIVE_V14',source=source)
    def test_native_helper_fallback_mutant_is_rejected(self):
        broken=deepcopy(self.result); path=next(iter(broken['fixture_text']))
        broken['fixture_text'][path]=broken['fixture_text'][path].replace('activate_decision = EU_create_EDU','eon_edu_create_decision_effect = yes',1)
        with self.assertRaises(AssertionError): validate_contract(broken)
    def test_missing_native_hook_auto_pass_mutant_is_rejected(self):
        broken=deepcopy(self.result)
        broken['expectations']['edu_native_dismantle_clears_all_actual_member_receipts']['predicate']='OR = { has_dlc = "No Compromise, No Surrender" always = yes } '
        with self.assertRaises(AssertionError): validate_contract(broken)
    def test_wrong_target_admission_mutant_is_rejected(self):
        broken=deepcopy(self.result); path=next(iter(broken['fixture_text']))
        broken['fixture_text'][path]=broken['fixture_text'][path].replace('target = AUS decision = eon_edu_request_join','target = USA decision = eon_edu_request_join',1)
        with self.assertRaises(AssertionError): validate_contract(broken)
    def test_clocks_require_actual_elapsed_game_time(self):
        clocks=self.result['required_elapsed_game_time']
        self.assertEqual(len(clocks),6)
        for item in clocks:
            self.assertIn(item['start_observation'],self.result['observations'])
            self.assertIn(item['end_observation'],self.result['observations'])
            self.assertGreaterEqual(item['minimum_hours'],1)
        expiry=next(v for v in clocks if v['start_observation']=='EDU_REQUEST_EXPIRY_CLOCK')
        self.assertEqual(expiry['minimum_hours'],24)
    def test_metadata_adoption_is_observation_not_automatic_assertion_pass(self):
        self.assertFalse(any('legacy_adopt' in name for name in self.result['assertions']))
        text=next(iter(self.result['fixture_text'].values()))
        self.assertIn('has_dlc = "No Compromise, No Surrender" has_faction_template = faction_template_edu',text)
        self.assertIn('EDU_LEGACY_ADOPT_SUPPORTED_PATH',self.result['observations'])
        self.assertIn('EDU_LEGACY_ADOPT_UNAVAILABLE_PATH',self.result['observations'])
    def test_pending_recreation_input_is_declared_and_policy_valid_before_native_mutations(self):
        text=next(iter(self.result['fixture_text'].values()))
        start=text.index('id = eon_native_eu_probe.3012 '); end=text.index('id = eon_native_eu_probe.3013 ',start)
        body=text[start:end]
        self.assertLess(body.index('eon_edu_creation_intent = global.eon_edu_generation_counter'),body.index('dismantle_faction = yes'))
        self.assertLess(body.index('eon_edu_creation_policy_still_valid = yes'),body.index('dismantle_faction = yes'))
        self.assertIn('declared private policy-valid pending intent',' '.join(self.result['limits']).lower())
    def test_unrelated_nato_controls_require_actual_positive_membership_and_leader(self):
        entries=[v for k,v in self.result['expectations'].items() if k.startswith('edu_nato_unchanged')]
        self.assertEqual(len(entries),4)
        for entry in entries:
            self.assertIn('is_in_faction = yes',entry['predicate'])
            self.assertIn('is_in_faction_with = USA',entry['predicate'])
            self.assertIn('nato_leader',entry['predicate'])
            self.assertNotIn('has_faction_template',entry['predicate'])

if __name__=='__main__': unittest.main(verbosity=2)
