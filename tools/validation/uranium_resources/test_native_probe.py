"""Fixture/analyzer negative controls. These are not recorded game acceptance."""
from datetime import datetime, timedelta
from pathlib import Path
import importlib.util
import json
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builder, analyzer = load('build_native_probe'), load('analyze_native_probe')


def synthetic(manifest):
    lines = ['[2000.01.01.01] '+manifest['marker']+' STARTUP native_resource_trade_prototype']
    for label in manifest['assertions']:
        lines.append('[2000.01.01.01] '+manifest['marker']+' PASS '+label)
    for index, label in enumerate(manifest['observation_labels']):
        actor = manifest['expected_observation_actors'][label]
        day, hour = divmod(index*5, 24)
        date = datetime(2000, 1, 1)+timedelta(days=day, hours=hour)
        imported = 0 if label in ('usa_baseline', 'usa_before_import') or actor == 'CAN' else 8
        balance = imported
        produced = 0 if label == 'can_baseline' else 800
        lines.append('['+date.strftime('%Y.%m.%d.%H')+'] '+manifest['marker']+' OBS '+label+
                     ' ROOT=USA THIS='+actor+' balance='+str(balance)+' produced='+str(produced)+' imported='+str(imported)+
                     ' exported=640 consumed=0')
    lines.append('[2000.01.05.01] '+manifest['marker']+' END passes='+str(len(manifest['assertions']))+' fails=0')
    return '\n'.join(lines)


def expect_reject(manifest, text):
    try:
        analyzer.parse_log(text, manifest)
    except AssertionError:
        return
    raise AssertionError('Malformed evidence accepted')


def main():
    with tempfile.TemporaryDirectory(prefix='eon-uranium-fixture-controls-') as temporary:
        out = Path(temporary)/'probe'
        production_has_uranium = 'uranium' in (ROOT/'common/resources/00_resources.txt').read_text(encoding='utf-8-sig')
        manifest = builder.build(ROOT, out, prototype_definition=not production_has_uranium, preparation_only=True)
        assert len(manifest['assertions']) == 15
        assert len(manifest['observation_labels']) == 12
        assert manifest['preparation_only'] and manifest['kind'] == 'native_resource_trade_prototype'
        for rel in manifest['fixture_sha256']:
            raw = (out/'mod'/rel).read_bytes()
            expected_bom = rel == 'common/resources/00_resources.txt' and (ROOT/rel).read_bytes().startswith(b'\xef\xbb\xbf')
            assert raw.startswith(b'\xef\xbb\xbf') == expected_bom, ('Wrong native script BOM', rel)
        good = synthetic(manifest)
        parsed = analyzer.parse_log(good, manifest)
        assert len(parsed['passed']) == 15 and not parsed['failed']
        marker = manifest['marker']
        mutations = [
            good.replace(marker+' STARTUP native_resource_trade_prototype', ''),
            good+'\n'+marker+' STARTUP native_resource_trade_prototype',
            good.replace(marker+' PASS '+manifest['assertions'][0], ''),
            good+'\n'+marker+' PASS '+manifest['assertions'][0],
            good+'\n'+marker+' PASS unexpected',
            good.replace(marker+' OBS '+manifest['observation_labels'][0], marker+' OBS unknown'),
            good.replace('THIS=CAN', 'THIS=GER', 1),
            good.replace('ROOT=USA', 'ROOT=GER', 1),
            good.replace(marker+' END passes=15 fails=0', ''),
            good.replace(marker+' END passes=15 fails=0', marker+' END passes=14 fails=0'),
            good+'\n'+marker+' ABORT wrong_frame',
            good+'\n'+marker+' DUPLICATE_EVENT 1',
            good.replace('imported=8', 'imported=0'),
            good.replace('balance=8', 'balance=0'),
            good.replace('consumed=0', 'consumed=nan'),
            good.replace('produced=800', 'produced=0'),
            good.replace('exported=640', 'exported=0'),
        ]
        obs_line = next(line for line in good.splitlines() if marker+' OBS usa_after_import_8 ' in line)
        mutations.append(good+'\n'+obs_line)
        lines = good.splitlines()
        indices = [i for i, line in enumerate(lines) if marker+' OBS ' in line]
        lines[indices[0]], lines[indices[1]] = lines[indices[1]], lines[indices[0]]
        mutations.append('\n'.join(lines))
        for text in mutations:
            expect_reject(manifest, text)
        try:
            builder.build(ROOT, out, prototype_definition=not production_has_uranium, preparation_only=True)
        except AssertionError:
            pass
        else:
            raise AssertionError('Frozen manifest overwritten')
        assert all(builder.sha(out/'mod'/rel) == digest for rel, digest in manifest['fixture_sha256'].items())
        print(json.dumps({'fixture_analyzer_controls_passed': True, 'negative_controls': len(mutations)+1,
                          'native_behavior_tested': False, 'fixture_assertions': len(manifest['assertions'])}))


if __name__ == '__main__':
    main()
