from pathlib import Path
import hashlib,importlib.util,json,re,unittest
ROOT=Path(__file__).resolve().parents[3]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
import extension_support as NEW
BASE=NEW
GOLDEN114='39f60d06ad216072284d6c9a72ed5c7003857ea2bec47a2c799ceef31ab58166'
def walk(nodes):
    for key,op,value in nodes:
        yield key,op,value
        if isinstance(value,list): yield from walk(value)
class ExtensionProposal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.new=NEW.build_extension('private_extension','PRIVATE_EXTENSION',source=ROOT)
        text=cls.new['fixture_text']['events/private_extension.txt']
        cls.ast=NEW.ast(text)
        cls.events={NEW.one(value,'id'):NEW.one(value,'immediate') for key,op,value in cls.ast if key=='country_event'}
    def test_original114_predictions_clocks_and_source_pins_preserved(self):
        contract={k:self.new[k] for k in ('assertions','expectations','calibrations','required_elapsed_game_time','required_observations')}
        actual=hashlib.sha256(json.dumps(contract,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.assertEqual(actual,GOLDEN114)
        self.assertEqual(len(self.new['assertions']),114)
        self.assertEqual(len(self.new['production_dependency_paths']),9)
        for relative in self.new['production_dependency_paths']:
            self.assertEqual(self.new['production_input_sha256'][relative],hashlib.sha256((ROOT/relative).read_bytes()).hexdigest())
    def test_native_responses_all_dispatched_from_initial_pol_root(self):
        starts=[body for body in self.events.values() if any(key=='log' and 'BEGIN extension_' in value and '_proposal_is_not_agreement' in value for key,op,value in body)]
        self.assertEqual(len(starts),4)
        for body in starts:
            schedule=[]
            for key,op,value in body:
                if key in BASE.MEMBERS+(BASE.LEAVER,) and isinstance(value,list):
                    for name,op,call in value:
                        if name=='country_event': schedule.append((key,int(NEW.one(call,'hours'))))
            self.assertEqual(schedule,[(tag,2*(i+1)) for i,tag in enumerate(BASE.MEMBERS)]+[('POL',16)])
        responder_bodies=[body for body in self.events.values() if any(key=='log' and re.search(r'BEGIN extension_.*_pair_(GER|FRA|ITA|HOL|SPR|CZE)$',value) for key,op,value in body)]
        self.assertEqual(len(responder_bodies),24)
        self.assertFalse(any(key=='country_event' for body in responder_bodies for key,op,value in walk(body)))
    def test_literal_target_guarded_by_exact_native_actor_pair(self):
        found=0
        for body in self.events.values():
            expected=next((re.search(r'_pair_(GER|FRA|ITA|HOL|SPR|CZE)$',value)[1] for key,op,value in body
                if key=='log' and re.search(r'_pair_(GER|FRA|ITA|HOL|SPR|CZE)$',value)),None)
            for key,op,value in body:
                if key!='if':continue
                targeted=[call for name,op,call in value if name=='activate_targeted_decision']
                for call in targeted:
                    found+=1;self.assertEqual(NEW.one(call,'target'),'POL')
                    gate=NEW.one(value,'limit')
                    self.assertIn(('tag','=',expected),gate)
                    self.assertIn(('FROM','=',[('tag','=','POL')]),gate)
        self.assertEqual(found,48)
    def test_context_gate_and_requested_receipts_are_not_fake_callback_proof(self):
        self.assertEqual(len(self.new['diagnostic_observations']),len(set(self.new['diagnostic_observations'])))
        text=self.new['fixture_text']['events/private_extension.txt']
        self.assertIn('answer=[?POL.eon_eu_extension_answer_count]',text)
        self.assertIn('actor=[?ROOT.id] scope=[?THIS.id] sender=[?FROM.id] target=[?POL.id]',text)
        for key in ('ALLOWED','VISIBLE','AVAILABLE','TARGET_ROOT_TRIGGER','TARGET_TRIGGER'):
            self.assertIn('_GATE_'+key,text)
        self.assertIn('ACTIVATE_REQUESTED',text)
        self.assertNotIn('ACTIVATE_SUCCEEDED',text)
    def test_calibration_is_selected_decision_removal_and_actual_native_retry(self):
        text=self.new['fixture_text']['events/private_extension.txt']
        self.assertEqual(len(self.new['extension_callback_contract']['actions']),24)
        removals=[call for key,op,call in walk(self.ast) if key=='remove_targeted_decision']
        self.assertEqual(len(removals),24)
        for call in removals:
            self.assertEqual(NEW.one(call,'target'),'POL')
            self.assertIn(NEW.one(call,'decision'),('eon_eu_extension_approve','eon_eu_extension_abstain'))
        self.assertIn('_RAW_AFTER',text)
        self.assertIn('_ACTIVE_AFTER_REMOVE',text)
        self.assertIn('_CALIBRATION_ACTIVATE_REQUESTED',text)
        for body in self.events.values():
            if any(key=='remove_targeted_decision' for key,op,value in walk(body)):
                ident=next(NEW.one(value,'decision') for key,op,value in walk(body) if key=='remove_targeted_decision')
                self.assertEqual(sum(key=='has_decision' and value==ident for key,op,value in walk(body)),4)
            for key,op,branch in body:
                if key=='if' and any(name=='remove_targeted_decision' for name,op,value in branch):
                    gate=NEW.one(branch,'limit')
                    self.assertTrue(any(name=='custom_trigger_tooltip' and any(n in ('eon_eu_extension_can_approve','eon_eu_extension_can_abstain') for n,op,v in value) for name,op,value in gate))
                    mutation_keys=[name for name,op,value in branch]
                    self.assertLess(mutation_keys.index('remove_targeted_decision'),mutation_keys.index('activate_targeted_decision'))
    def test_no_complete_effect_or_native_call_fallback(self):
        forbidden={'complete_effect','eon_eu_extension_approve','eon_eu_extension_reject','eon_eu_extension_abstain','eon_eu_extension_accept_final','eon_eu_extension_propose'}
        self.assertFalse(any(key in forbidden for key,op,value in walk(self.ast)))
    def test_private_pol_preference_has_raw_witnesses_and_retains_native_ai_and_party(self):
        changes=[value for key,op,value in walk(self.ast) if key=='set_variable' and ('eurosceptic','=','1') in value]
        self.assertEqual(changes,[[('eurosceptic','=','1')]]*6)
        forbidden={'set_politics','set_party_popularity','set_ai_strategy','ai_will_do','set_ai','set_country_leader_ideology'}
        self.assertFalse(any(key in forbidden for key,op,value in walk(self.ast)))
        self.assertFalse(any(key in ('clear_array','add_to_array','remove_from_array','set_array') and 'ruling_party' in str(value) for key,op,value in walk(self.ast)))
        text=self.new['fixture_text']['events/private_extension.txt']
        self.assertEqual(text.count('DECLARED_PRIVATE_BOUNDARY'),6)
        self.assertIn('ruling_party_count=[?ruling_party^num] ruling_party_first=[?ruling_party^0]',text)
        for name in ('NATURAL_FLAG','OLD_MAIN','OLD_SHORT','BOTH_OLD','MAIN_CALLBACK_BEFORE_MIGRATION','SHORT_CALLBACK_BEFORE_MIGRATION'):
            self.assertIn('EXTENSION_'+name+'_POLITICAL_INPUT_BEFORE',self.new['diagnostic_observations'])
            self.assertIn('EXTENSION_'+name+'_POLITICAL_INPUT_AFTER',self.new['diagnostic_observations'])
            self.assertIn('EXTENSION_'+name+'_POLITICAL_INPUT_GOV_EUROSCEPTIC',self.new['diagnostic_observations'])
            self.assertIn('EXTENSION_'+name+'_POLITICAL_INPUT_GOV_EXITEER',self.new['diagnostic_observations'])
        for label in self.new['required_observations']:
            for state in ('ARTICLE50','MEMBER','RECOGNIZED','INITIALIZED','MAIN_AUTHORITY','CLOCK_STARTED','DEADLINE','PROPOSAL','WITHDRAWAL_TREATY','GOV_EUROSCEPTIC','GOV_EXITEER'):
                self.assertIn(label+'_STATE_'+state,self.new['diagnostic_observations'])
if __name__=='__main__':unittest.main(verbosity=2)
