"""Synthetic staged-enrichment acceptance controls; not native behavior proof."""
from datetime import datetime, timedelta
from pathlib import Path
import json
import tempfile

import build_enrichment_checkpoint_native_probe as builder
import analyze_enrichment_checkpoint_native_probe as analyzer
import build_core_native_probe as core
import analyze_core_native_probe as core_analyzer
from test_core_native_probe import synthetic as core_synthetic


def synthetic(manifest):
    marker = manifest['marker']
    lines = ['[2000.01.01.01] '+marker+' STARTUP staged_enrichment']
    lines += ['[2000.01.01.01] '+marker+' PASS '+label for label in manifest['assertions']]
    lines += ['[2000.01.01.01] '+marker+' CHECKPOINT '+position+' '+name+' ROOT=GER THIS=GER'
              for name in manifest['checkpoints'] for position in ('BEFORE', 'AFTER')]
    states = [(100, 0, 0, 0), (25, 0, 3, 75), (25, 0, 3, 75), (25, 3, 0, 0),
              (75, 3, 1, 25), (75, 3, 1, 25), (100, 3, 0, 0), (100, 3, 0, 0)]
    for index, (label, values) in enumerate(zip(manifest['observation_labels'], states)):
        fields = dict(zip(('treasury', 'facilities', 'count', 'escrow'), values))
        fields['timer'] = 1095 if index in (1, 2) else 730 if index in (4, 5) else 0
        fields.update(paid=int(index in (1, 2, 4, 5)), active=int(index in (1, 2, 4, 5)),
                      allowed_no_active=0, allowed_yes_active=int(index > 0),
                      money_delta=(0, 75, 75, 0, 25, 25, 25, 25)[index])
        stamp = datetime(2000, 1, 2)+timedelta(hours=index*2)
        lines.append('['+stamp.strftime('%Y.%m.%d.%H')+'] '+marker+' OBS '+label+
                     ' ROOT=GER THIS=GER '+' '.join(key+'='+str(value) for key, value in fields.items()))
    lines.append('[2000.01.04.01] '+marker+' END passes='+str(len(manifest['assertions']))+' fails=0')
    return '\n'.join(lines)


def main():
    with tempfile.TemporaryDirectory(prefix='eon-enrichment-controls-') as temporary:
        base = Path(temporary)
        out = base/'enrichment'
        manifest = builder.build(builder.ROOT, out, preparation_only=True)
        analyzer.verify_bindings(builder.ROOT, out, manifest)
        for rel in manifest['fixture_sha256']:
            assert not (out/'mod'/rel).read_bytes().startswith(b'\xef\xbb\xbf')
        good, marker = synthetic(manifest), manifest['marker']
        assert not analyzer.parse_log(good, manifest)['failed']
        # Spending between native events is not a callback charge. Exact +25
        # same-event refund remains required and measured independently.
        # Replace the AFTER_WAIT entry only; the GUI call retains its exact25 charge.
        drift = good[:good.index(' OBS single_after_native_wait ')] + good[good.index(' OBS single_after_native_wait '):].replace('treasury=75', 'treasury=74.5', 1).replace('treasury=100', 'treasury=99.5')
        assert analyzer.parse_log(drift, manifest)['callback_local_treasury_deltas']['cancel_refund'] == 25
        changes = [good.replace(marker+' STARTUP staged_enrichment', ''),
                   good+'\n'+marker+' STARTUP staged_enrichment',
                   good.replace(marker+' PASS '+manifest['assertions'][0], ''),
                   good.replace('ROOT=GER', 'ROOT=USA', 1),
                   good.replace('CHECKPOINT BEFORE initialize', 'CHECKPOINT AFTER initialize', 1),
                   good.replace('CHECKPOINT AFTER actual_gui_triple', 'CHECKPOINT AFTER wrong_callback', 1),
                   good.replace('treasury=25', 'treasury=24', 1),
                   good.replace('facilities=3', 'facilities=6', 1),
                   good.replace('escrow=75', 'escrow=0', 1),
                   good.replace('treasury=100', 'treasury=nan', 1),
                   good.replace('money_delta=75', 'money_delta=74', 1),
                   good.replace('OBS triple_after_native_wait ROOT=GER THIS=GER treasury=25 facilities=0 count=3 escrow=75 timer=1095 paid=1 active=1',
                                'OBS triple_after_native_wait ROOT=GER THIS=GER treasury=25 facilities=0 count=3 escrow=75 timer=1095 paid=1 active=0'),
                   good.replace('[2000.01.02.04]', '[2000.01.02.02]'),
                   good+'\n'+marker+' ABORT wrong_frame']
        for text in changes:
            try: analyzer.parse_log(text, manifest)
            except AssertionError: pass
            else: raise AssertionError('Invalid staged-enrichment evidence accepted')
        materials = core.build(builder.ROOT, base/'materials', preparation_only=True,
                               materials_only=True, after_enrichment=True)
        assert len(materials['callback_bindings']) == 2 and len(materials['observation_labels']) == 8
        assert all('gui' not in binding['alias'] and 'mission' not in binding['alias'] for binding in materials['callback_bindings'])
        events = (base/'materials/mod/events'/f'{core.NS}_events.txt').read_text(encoding='utf-8')
        assert 'remove_mission' not in events and 'set_technology' not in events and core.NS+'_gui_' not in events
        assert events.count('country_event = { id = '+core.NS+'.') == 11 # six declarations, five next-stage queues
        core_analyzer.verify_bindings(builder.ROOT, base/'materials', materials)
        assert not core_analyzer.parse_log(core_synthetic(materials), materials)['failed']
        print(json.dumps({'staged_enrichment_controls_verified': True, 'negative_controls': len(changes),
                          'materials_only_callbacks': 2, 'materials_only_events': 6, 'native_game_behavior_tested': False}))


if __name__ == '__main__': main()
