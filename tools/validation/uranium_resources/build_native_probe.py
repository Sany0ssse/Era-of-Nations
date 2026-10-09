"""Prepare an isolated native uranium/trade probe; never launch or embed it.

The optional prototype resource overlay is only for proving native support before
the production resource definition is ready. It is not the final gameplay model.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
NS = 'eon_private_uranium_probe'
MARKER = 'EON_PRIVATE_URANIUM_PROBE'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_parser():
    spec = importlib.util.spec_from_file_location(
        'uranium_probe_ast', ROOT/'tools/validation/diplomacy_package_03/_support.py')
    parser = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = parser
    spec.loader.exec_module(parser)
    return parser


def build(source, output, prototype_definition=False, export_receipt=None,
          preparation_only=False, start_tag='USA'):
    source, output = source.resolve(), output.resolve()
    assert source.is_dir(), 'Missing source root'
    assert output != source, 'Output must be separate from source'
    assert preparation_only or source not in output.parents, 'Use a sibling fixture for native exports'
    assert not (output/'manifest.json').exists(), 'Use a new directory; keep frozen evidence unchanged'
    assert not (output/'launch-receipt.json').exists(), 'Never rewrite launched evidence'
    if not preparation_only:
        assert source != ROOT.resolve(), 'Native runs require a private source export'
        assert export_receipt and export_receipt.is_file(), 'Provide the frozen source export receipt'
    parser = load_parser()
    original = (source/'common/resources/00_resources.txt').read_bytes()
    resources = parser.one(parser.ast(original), 'resources')
    ids = [key for key, op, value in resources]
    assert ids[:6] == ['oil', 'aluminium', 'rubber', 'tungsten', 'steel', 'chromium']
    assert len(ids) in (6, 7), ids
    fixture = {}
    if prototype_definition:
        assert ids == ['oil', 'aluminium', 'rubber', 'tungsten', 'steel', 'chromium'], ids
        text = original.decode('utf-8-sig')
        closing = text.rfind('}')
        assert closing >= 0 and not text[closing+1:].strip()
        overlay = (text[:closing] + '\turanium = {\n\t\ticon_frame = 7\n'
                   '\t\tcic = 0.125\n\t\tconvoys = 0.1\n\t}\n' + text[closing:])
        fixture['common/resources/00_resources.txt'] = overlay
        resource_ids = ids+['uranium']
    else:
        assert ids == ['oil', 'aluminium', 'rubber', 'tungsten', 'steel', 'chromium', 'uranium'], ids
        resource_ids = ids

    labels, observations = [], []

    def check(label, predicate):
        assert label not in labels
        labels.append(label)
        return ('if = { limit = { '+predicate+' } '
                'add_to_variable = { global.'+NS+'_passes = 1 } '
                'log = "'+MARKER+' PASS '+label+'" } else = { '
                'add_to_variable = { global.'+NS+'_fails = 1 } '
                'log = "'+MARKER+' FAIL '+label+'" }')

    def cv(variable, value, compare='equals'):
        return ('check_variable = { var = '+variable+' value = '+str(value)+
                ' compare = '+compare+' }')

    def observe(label):
        assert label not in observations
        observations.append(label)
        values = ' '.join(name+'=[?'+value+']' for name, value in (
            ('balance', 'resource@uranium'), ('produced', 'resource_produced@uranium'),
            ('imported', 'resource_imported@uranium'), ('exported', 'resource_exported@uranium'),
            ('consumed', 'resource_consumed@uranium')))
        return ('log = "'+MARKER+' OBS '+label+' ROOT=[ROOT.GetTag] THIS=[THIS.GetTag] '+values+'"')

    def queue(number, hours=24):
        return 'country_event = { id = '+NS+'.'+str(number)+' hours = '+str(hours)+' }'

    def event(number, body):
        frame = 'tag = USA ROOT = { tag = USA } CAN = { exists = yes }'
        return ('country_event = { id = '+NS+'.'+str(number)+
                ' hidden = yes is_triggered_only = yes immediate = { '
                'if = { limit = { NOT = { has_global_flag = '+NS+'_event_'+str(number)+' } } '
                'set_global_flag = '+NS+'_event_'+str(number)+' '+check('frame_'+str(number), frame)+
                ' if = { limit = { '+frame+' } '+body+' } else = { log = "'+MARKER+
                ' ABORT wrong_country_frame_'+str(number)+'" } } else = { log = "'+MARKER+
                ' DUPLICATE_EVENT '+str(number)+'" } } }')

    before = ('set_variable = { '+NS+'_imports_before = resource_imported@uranium } '
              'set_variable = { '+NS+'_balance_before = resource@uranium } '
              'CAN = { set_variable = { '+NS+'_produced_before = resource_produced@uranium } }')
    events = [event(1, before+observe('usa_baseline')+' CAN = { '+observe('can_baseline')+
                    ' add_ideas = globalized_trade_economy } '
                    '756 = { '+check('saskatchewan_owned_controlled_by_can',
                                     'is_owned_by = CAN is_controlled_by = CAN')+
                    ' add_resource = { type = uranium amount = 800 } } '+queue(2))]
    events.append(event(2,
        observe('usa_before_import')+' CAN = { '+observe('can_after_resource_added')+
        check('native_produced_uranium_increased',
              cv('resource_produced@uranium', NS+'_produced_before', 'greater_than'))+
        check('native_country_extraction_predicate',
              'has_resources_in_country = { resource = uranium amount > 0 extracted = yes }')+
        check('native_exported_uranium_positive', cv('resource_exported@uranium', 0, 'greater_than'))+' } '
        '756 = { '+check('native_state_uranium_predicate',
                         'has_resources_amount = { resource = uranium amount > 0 }')+' } '
        'set_variable = { '+NS+'_imports_before = resource_imported@uranium } '
        'set_variable = { '+NS+'_balance_before = resource@uranium } '
        'create_import = { resource = uranium amount = 8 exporter = CAN } '+queue(3, 2)))
    events.append(event(3,
        observe('usa_after_import_8')+' CAN = { '+observe('can_after_import_8')+' } '
        'set_temp_variable = { '+NS+'_import_delta = resource_imported@uranium } '
        'subtract_from_temp_variable = { '+NS+'_import_delta = '+NS+'_imports_before } '
        'set_temp_variable = { '+NS+'_balance_delta = resource@uranium } '
        'subtract_from_temp_variable = { '+NS+'_balance_delta = '+NS+'_balance_before } '+
        check('native_create_import_8_delivered', cv(NS+'_import_delta', 8, 'greater_than_or_equals'))+
        check('native_import_increases_balance', cv(NS+'_balance_delta', 8, 'greater_than_or_equals'))+
        check('native_import_only_predicate',
              'has_resources_in_country = { resource = uranium amount > 0 only_imported = yes }')+
        'create_import = { resource = uranium amount = 8 exporter = CAN } '+queue(4, 2)))
    events.append(event(4, observe('usa_after_repeat_import_8')+
                        ' CAN = { '+observe('can_after_repeat_import_8')+' } '
                        'create_import = { resource = uranium amount = 16 exporter = CAN } '+queue(5, 2)))
    events.append(event(5, observe('usa_after_import_16')+' CAN = { '+observe('can_after_import_16')+' } '+
                        check('native_import_16_remains_positive', cv('resource_imported@uranium', 0, 'greater_than'))+
                        queue(6, 30)))
    events.append(event(6, observe('usa_after_24h_without_native_equipment_demand')+
                        ' CAN = { '+observe('can_after_24h_without_native_equipment_demand')+' } '
                        'log = "'+MARKER+' END passes=[?global.'+NS+'_passes] fails=[?global.'+NS+'_fails]" '
                        'set_global_flag = '+NS+'_finished'))
    fixture['events/'+NS+'_events.txt'] = 'add_namespace = '+NS+'\n\n'+'\n\n'.join(events)+'\n'
    fixture['common/on_actions/'+NS+'_on_actions.txt'] = (
        'on_actions = { on_startup = { effect = { '
        'if = { limit = { NOT = { has_global_flag = '+NS+'_booted } } '
        'set_global_flag = '+NS+'_booted set_variable = { global.'+NS+'_passes = 0 } '
        'set_variable = { global.'+NS+'_fails = 0 } '
        'log = "'+MARKER+' STARTUP native_resource_trade_prototype" '
        'USA = { '+queue(1, 1)+' } } } } }\n')
    output.mkdir(parents=True, exist_ok=True)
    for rel, text in fixture.items():
        parser.ast(text)
        path = output/'mod'/rel
        path.parent.mkdir(parents=True, exist_ok=True)
        # HOI4's script lexer treats a new leading BOM as part of the root token.
        # Preserve the original resource-file encoding; new script files have no
        # BOM. Localisation encoding rules must not be applied to script roots.
        prefix = b'\xef\xbb\xbf' if rel == 'common/resources/00_resources.txt' and original.startswith(b'\xef\xbb\xbf') else b''
        path.write_bytes(prefix+text.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8'))
    deps = ['common/resources/00_resources.txt', 'common/ideas/AA_law_economics.txt',
            'common/defines/MD_defines.lua', 'history/states/756-Saskatchewan.txt']
    docs = Path(r'D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation')
    doc_paths = ['dynamic_variables_documentation.md', 'effects_documentation.md', 'triggers_documentation.md']
    manifest = {
        'schema': 1, 'kind': 'native_resource_trade_prototype', 'marker': MARKER,
        'source_root': str(source), 'fixture_root': str(output),
        'preparation_only': preparation_only, 'prototype_resource_definition': prototype_definition,
        'resource_ids': resource_ids, 'expected_native_start_tag': start_tag,
        'expected_enabled_mods': ['mod/era_of_nations.mod'],
        'assertions': labels, 'observation_labels': observations,
        'expected_observation_actors': {label: 'CAN' if label.startswith('can_') else 'USA' for label in observations},
        'minimum_total_native_hours': 50,
        'source_sha256': {rel: sha(source/rel) for rel in deps if rel not in fixture},
        'overlaid_original_sha256': {rel: sha(source/rel) for rel in fixture if (source/rel).exists()},
        'fixture_sha256': {rel: sha(output/'mod'/rel) for rel in fixture},
        'builder_sha256': sha(Path(__file__)),
        'installed_documentation_root': str(docs),
        'installed_documentation_sha256': {rel: sha(docs/rel) for rel in doc_paths if (docs/rel).exists()},
        'source_export_binding': None if not export_receipt else {'path': str(export_receipt.resolve()), 'sha256': sha(export_receipt)},
        'limits': ['Controlled native resource/import probe, not final uranium economy acceptance.',
                   'No human GUI click or rendered seventh icon proof.',
                   'Repeated create_import behavior is recorded rather than guessed.',
                   'No native AI purchase, save/load, multiplayer, campaign balance or nuclear safeguards proof.'],
    }
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return manifest


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source-root', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--prototype-definition', action='store_true')
    cli.add_argument('--export-receipt', type=Path)
    cli.add_argument('--prepare-only', action='store_true')
    cli.add_argument('--start-tag', default='USA')
    args = cli.parse_args()
    result = build(args.source_root, args.output, args.prototype_definition,
                   args.export_receipt, args.prepare_only, args.start_tag)
    print(json.dumps({'fixture_prepared': True, 'assertions': len(result['assertions']),
                      'observations': len(result['observation_labels']),
                      'native_behavior_tested': False, 'manifest': str(args.output/'manifest.json')}))


if __name__ == '__main__':
    main()
