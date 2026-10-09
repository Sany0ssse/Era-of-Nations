"""Check native probe scopes against the failures observed in runs 89 and 90."""
from pathlib import Path
import json, tempfile, unittest
from build_native_probe import ROOT, build
from analyze_native_probe import analyze
from test_ai_templates import parse

IDS=('eon_regimental_light_artillery','eon_regimental_motorized_artillery')

def walk(nodes, parents=()):
    for node in nodes:
        yield node,parents
        if isinstance(node.value,list):
            yield from walk(node.value,parents+(node.key,))

class FixtureScopes(unittest.TestCase):
    def test_analyzer_requires_an_existing_error_log(self):
        with tempfile.TemporaryDirectory(prefix='eon-division-analysis-') as temp:
            base=Path(temp)
            manifest=base/'manifest.json'
            game=base/'game.log'
            errors=base/'missing-error.log'
            manifest.write_text(json.dumps({
                'marker':'EON_TEST','assertions':['sample'],
                'source_root':str(base),'source_sha256':{},'fixture_sha256':{},
                'countries':['NEP'],'limits':['Synthetic analyzer test only.']
            }),encoding='utf-8')
            game.write_text('EON_TEST PASS sample\nEON_TEST END passes=1 fails=0\n',encoding='utf-8')
            with self.assertRaisesRegex(AssertionError,'error log'):
                analyze(manifest,game,errors)

    def test_fixture_uses_state_creation_and_country_valid_evidence(self):
        with tempfile.TemporaryDirectory(prefix='eon-division-probe-') as temp:
            output=Path(temp).resolve()/'fixture'
            self.assertTrue(output.is_relative_to(Path(temp).resolve()))
            manifest=build(ROOT,output,*IDS)
            source=(output/'mod/events/eon_native_division_probe.txt').read_text()
            nodes=list(walk(parse(source)))
            creates=[parents for node,parents in nodes if node.key=='create_unit']
            self.assertEqual(len(creates),8)
            self.assertTrue(all(parents[-1]=='capital_scope' for parents in creates))
            self.assertNotIn('has_unit_type',{node.key for node,parents in nodes})
            self.assertEqual(len(manifest['assertions']),28)
            self.assertEqual(len(set(manifest['assertions'])),28)
            self.assertEqual(sum('_deployed' in x for x in manifest['assertions']),8)
            self.assertTrue(all('support_registered' not in x for x in manifest['assertions']))
            self.assertEqual(source.count('_legacy_contains=0'),8)
            self.assertEqual(set((output/'mod/common/synchronized_dynamic_tokens/eon_native_division_probe.txt').read_text().split()),set(IDS))

if __name__=='__main__':
    unittest.main(verbosity=2)
