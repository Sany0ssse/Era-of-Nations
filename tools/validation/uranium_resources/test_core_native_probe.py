"""Source bindings and synthetic native evidence rejection; no game launch."""
from datetime import datetime, timedelta
from pathlib import Path
import json
import tempfile

import build_core_native_probe as builder
import analyze_core_native_probe as analyzer


def synthetic(manifest):
    marker = manifest['marker']
    lines = ['[2000.01.01.01] '+marker+' STARTUP source_bound_core']
    lines += ['[2000.01.01.01] '+marker+' PASS '+label for label in manifest['assertions']]
    for index, label in enumerate(manifest['observation_labels']):
        fields = dict.fromkeys(manifest['observation_fields'], 0)
        if label == 'fractional_resource_observation': fields['fraction_after'] = 0.1
        if label == 'raw_to_fuel': fields.update(raw=0, fuel=1000, tails=8000, feed=9000, last_fuel=1000)
        if label == 'finite_deposit_before': fields.update(state_reserve=10000)
        if label == 'finite_deposit_after': fields.update(extracted=10000, delivered=9000, fuel=1000, tails=8000, feed=9000, last_fuel=1000)
        if label == 'captured_deposit_before': fields.update(state_reserve=180000, imported=8)
        if label == 'captured_deposit_after': fields.update(state_reserve=162000, extracted=18000, delivered=18000, fuel=2000, tails=16000, feed=18000, last_fuel=2000, imported=8)
        stamp = datetime(2000, 1, 1)+timedelta(hours=index*12)
        lines.append('['+stamp.strftime('%Y.%m.%d.%H')+'] '+marker+' OBS '+label+
                     ' ROOT=GER THIS=GER '+' '.join(key+'='+str(value) for key, value in fields.items()))
    lines.append('[2000.01.05.01] '+marker+' END passes='+str(len(manifest['assertions']))+' fails=0')
    return '\n'.join(lines)


def main():
    with tempfile.TemporaryDirectory(prefix='eon-uranium-core-controls-') as temporary:
        out = Path(temporary)/'fixture'
        manifest = builder.build(builder.ROOT, out, preparation_only=True)
        assert manifest['preparation_only'] and len(manifest['callback_bindings']) == 6
        for rel in manifest['fixture_sha256']:
            raw = (out/'mod'/rel).read_bytes()
            assert not raw.startswith(b'\xef\xbb\xbf') and b'\r\n' in raw
        analyzer.verify_bindings(builder.ROOT, out, manifest)
        good = synthetic(manifest)
        result = analyzer.parse_log(good, manifest)
        assert len(result['passed']) == len(manifest['assertions']) and not result['failed']
        assert result['native_fractional_resource_0_1_supported']
        marker = manifest['marker']
        changes = [good.replace(marker+' STARTUP source_bound_core', ''),
                   good+'\n'+marker+' STARTUP source_bound_core',
                   good.replace(marker+' PASS '+manifest['assertions'][0], ''),
                   good+'\n'+marker+' PASS '+manifest['assertions'][0],
                   good+'\n'+marker+' PASS unexpected', good.replace('ROOT=GER', 'ROOT=USA', 1),
                   good.replace('THIS=GER', 'THIS=CAN', 1),
                   good.replace(marker+' OBS baseline', marker+' OBS unexpected'),
                   good.replace('fuel=1000', 'fuel=1001', 1),
                   good.replace('delivered=9000', 'delivered=10001'),
                   good.replace('state_reserve=162000', 'state_reserve=161000'),
                   good.replace('fraction_after=0.1', 'fraction_after=-0.1'),
                   good.replace('raw=0', 'raw=nan', 1), good.replace('raw=0', 'raw=0 raw=0', 1),
                   good+'\n'+marker+' ABORT wrong_frame',
                   good.replace('passes='+str(len(manifest['assertions'])), 'passes=0'),
                   good.replace('[2000.01.04.12]', '[2000.01.01.12]'),
                   good.replace('[2000.01.01.00]', '[2000.01.01.25]')]
        for text in changes:
            try: analyzer.parse_log(text, manifest)
            except AssertionError: pass
            else: raise AssertionError('Malformed synthetic core evidence accepted')
        unchanged = analyzer.parse_log(good.replace('fraction_after=0.1', 'fraction_after=0'), manifest)
        assert not unchanged['native_fractional_resource_0_1_supported']
        print(json.dumps({'core_fixture_source_bindings_verified': True, 'callbacks': 6,
                          'assertions': len(manifest['assertions']), 'negative_controls': len(changes),
                          'native_game_behavior_tested': False}))


if __name__ == '__main__': main()
