"""Synthetic controls for final native rights ordering; never native proof."""
from datetime import datetime, timedelta
from pathlib import Path
import json
import tempfile

import build_final_rights_native_probe as builder
import analyze_final_rights_native_probe as analyzer


def synthetic(manifest):
    marker = manifest['marker']
    lines = ['[2000.01.01.01] '+marker+' STARTUP final_resource_rights']
    lines += ['[2000.01.01.01] '+marker+' PASS '+label for label in manifest['assertions']]
    for label in manifest['observation_labels']:
        fields = dict.fromkeys(manifest['observation_fields'], 0)
        fields.update(state_flow=90, state_reserve=9000, recipient_delivery_before=9000, final_reserve_before=9000)
        hour = 6 if label == 'owner_first_before_rights' else 70 if label == 'recipient_first_before_rights' else 100 if label.startswith('recipient_first') else 40
        frame = manifest['expected_observation_frames'][label]
        fields.update(balance=90 if frame['actor'] == 'NEP' else 0)
        settled = 'after_owner' in label or 'after_recipient' in label or label == 'owner_first_before_recipient_settlement' or label == 'recipient_first_before_owner_settlement'
        if settled: fields.update(state_flow=0, state_reserve=0, state_extracted=9000, state_recipient=2)
        if label.endswith('after_recipient_settlement'): fields.update(raw=9000, delivered=9000, rights_supply=9000)
        stamp = datetime(2000, 1, 1)+timedelta(hours=hour)
        lines.append('['+stamp.strftime('%Y.%m.%d.%H')+'] '+marker+' OBS '+label+
                     ' ROOT='+frame['root']+' THIS='+frame['actor']+' '+
                     ' '.join(key+'='+str(value) for key, value in fields.items()))
    lines.append('[2000.01.06.01] '+marker+' END passes='+str(len(manifest['assertions']))+' fails=0')
    return '\n'.join(lines)


def main():
    with tempfile.TemporaryDirectory(prefix='eon-final-rights-controls-') as temporary:
        out = Path(temporary)/'fixture'
        manifest = builder.build(builder.ROOT, out, preparation_only=True)
        for rel in manifest['fixture_sha256']:
            raw = (out/'mod'/rel).read_bytes()
            assert not raw.startswith(b'\xef\xbb\xbf') and b'\r\n' in raw
        good, marker = synthetic(manifest), manifest['marker']
        accepted = analyzer.parse_log(good, manifest)
        assert accepted['both_native_final_rights_orders_passed'], accepted['final_rights_order_checks']
        malformed = [good.replace(marker+' STARTUP final_resource_rights', ''),
                     good+'\n'+marker+' STARTUP final_resource_rights',
                     good.replace(marker+' PASS '+manifest['assertions'][0], ''),
                     good+'\n'+marker+' PASS '+manifest['assertions'][0],
                     good.replace('ROOT=GER', 'ROOT=USA', 1),
                     good.replace('THIS=NEP', 'THIS=CAN', 1),
                     good.replace('raw=0', 'raw=nan', 1),
                     good.replace('raw=0', 'raw=0 raw=0', 1),
                     good+'\n'+marker+' ABORT wrong_frame']
        for log in malformed:
            try: analyzer.parse_log(log, manifest)
            except AssertionError: pass
            else: raise AssertionError('Malformed final rights evidence was accepted')
        behavioural = [good.replace('raw=9000', 'raw=0', 1),
                       good.replace('state_extracted=9000', 'state_extracted=18000'),
                       good.replace('state_recipient=2', 'state_recipient=0'),
                       good.replace('raw=9000', 'raw=18000'),
                       good.replace('[2000.01.02.16] '+marker+' OBS owner_first_after_recipient_settlement',
                                    '[2000.01.02.17] '+marker+' OBS owner_first_after_recipient_settlement')]
        for log in behavioural:
            result = analyzer.parse_log(log, manifest)
            assert not result['both_native_final_rights_orders_passed'], result['final_rights_order_checks']
        print(json.dumps({'final_rights_fixture_controls_verified': True,
                          'negative_controls': len(malformed)+len(behavioural),
                          'assertions': len(manifest['assertions']), 'observations': len(manifest['observation_labels']),
                          'native_game_behavior_tested': False}))


if __name__ == '__main__': main()
