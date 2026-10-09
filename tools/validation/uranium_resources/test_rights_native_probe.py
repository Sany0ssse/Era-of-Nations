"""Synthetic uranium-only native rights evidence controls; not native proof."""
from pathlib import Path
from datetime import datetime, timedelta
import json
import tempfile

import build_rights_native_probe as builder
import analyze_rights_native_probe as analyzer


def synthetic(manifest):
    marker = manifest['marker']
    lines = ['[2000.01.01.01] '+marker+' STARTUP native_resource_rights']
    lines += ['[2000.01.01.01] '+marker+' PASS '+label for label in manifest['assertions']]
    for index, label in enumerate(manifest['observation_labels']):
        fields = dict.fromkeys(manifest['observation_fields'], 0)
        fields.update(state_flow=200, state_reserve=2000000)
        if label.startswith('ger_'): fields.update(produced=200, balance=100)
        if label in ('nep_after_rights', 'nep_before_material_settlement', 'nep_after_material_settlement'):
            fields.update(produced=200, balance=100)
        if label == 'nep_after_material_settlement': fields.update(raw=10000, delivered=10000)
        stamp = datetime(2000, 1, 1)+timedelta(hours=index*8)
        lines.append('['+stamp.strftime('%Y.%m.%d.%H')+'] '+marker+' OBS '+label+
                     ' ROOT='+manifest['expected_observation_roots'][label]+' THIS='+manifest['expected_observation_actors'][label]+' '+
                     ' '.join(key+'='+str(value) for key, value in fields.items()))
    lines.append('[2000.01.04.01] '+marker+' END passes='+str(len(manifest['assertions']))+' fails=0')
    return '\n'.join(lines)


def main():
    with tempfile.TemporaryDirectory(prefix='eon-uranium-rights-controls-') as temporary:
        out = Path(temporary)/'fixture'
        manifest = builder.build(builder.ROOT, out, preparation_only=True, after_core=True)
        assert manifest['preparation_only'] and manifest['after_core']
        for rel in manifest['fixture_sha256']:
            raw = (out/'mod'/rel).read_bytes()
            assert not raw.startswith(b'\xef\xbb\xbf') and b'\r\n' in raw
        good, marker = synthetic(manifest), manifest['marker']
        result = analyzer.parse_log(good, manifest)
        assert result['native_material_credit_matches_rights_balance'] and len(result['passed']) == 13
        mutations = [good.replace(marker+' STARTUP native_resource_rights', ''),
                     good+'\n'+marker+' STARTUP native_resource_rights',
                     good.replace(marker+' PASS '+manifest['assertions'][0], ''),
                     good+'\n'+marker+' PASS '+manifest['assertions'][0],
                     good.replace('ROOT=GER', 'ROOT=USA', 1),
                     good.replace('THIS=NEP', 'THIS=CAN', 1),
                     good.replace('balance=100', 'balance=0'),
                     good.replace('raw=0', 'raw=nan', 1),
                     good.replace('raw=0', 'raw=0 raw=0', 1),
                     good+'\n'+marker+' ABORT wrong_frame']
        for text in mutations:
            try: analyzer.parse_log(text, manifest)
            except AssertionError: pass
            else: raise AssertionError('Malformed synthetic rights evidence accepted')
        missing = analyzer.parse_log(good.replace('raw=10000', 'raw=0'), manifest)
        assert not missing['native_material_credit_matches_rights_balance']
        print(json.dumps({'rights_fixture_controls_verified': True, 'negative_controls': len(mutations),
                          'material_mismatch_control': True, 'native_game_behavior_tested': False}))


if __name__ == '__main__': main()
