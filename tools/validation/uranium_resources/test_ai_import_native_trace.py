"""Reject incomplete/misbound native AI dispatch traces; no delivery proof."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile

import analyze_ai_import_native_trace as analyzer
from build_native_probe import ROOT, load_parser
from build_core_native_probe import render


def trace():
    lines = []
    for index, (buyer, seller, amount) in enumerate((('ENG', 'CAN', 112), ('USA', 'SAF', 168), ('RAJ', 'FRA', 8))):
        date = '2000.01.01.'+str(13+index*3)
        lines += ['['+date+'] EON_PRIVATE_IMPORT BEFORE buyer='+buyer+' seller='+seller+' amount='+str(amount),
                  'create_import = { resource = uranium amount = '+str(amount)+' exporter = '+seller+' }',
                  '['+date+'] EON_PRIVATE_IMPORT AFTER buyer='+buyer]
    return '\n'.join(lines)


def main():
    good = trace()
    result = analyzer.parse_log(good, {})
    assert result['native_ai_import_dispatch_count'] == 3 and result['native_ai_import_dispatch_country_count'] == 3
    assert not result['native_import_delivery_verified'] and not result['native_import_retention_verified']
    factory_trace = good.replace('amount=112', 'factories=3').replace('amount = 112', 'factories = 3').replace('amount=168', 'factories=2').replace('amount = 168', 'factories = 2').replace('amount=8', 'factories=1').replace('amount = 8', 'factories = 1')
    parsed_factories = analyzer.parse_log(factory_trace, {})
    assert [row['factories'] for row in parsed_factories['native_ai_import_dispatches']] == [3, 2, 1]
    assert not parsed_factories['native_import_delivery_verified']
    changes = [good.replace('exporter = CAN', 'exporter = PREV'),
               good.replace('exporter = CAN', 'exporter = USA'),
               good.replace('amount = 112', 'amount = 120'),
               good.replace('amount=112', 'amount=111'),
               good.replace('AFTER buyer=ENG', 'AFTER buyer=USA'),
               good.replace('[2000.01.01.13] EON_PRIVATE_IMPORT AFTER', '[2000.01.01.14] EON_PRIVATE_IMPORT AFTER'),
               good.replace('[2000.01.01.13] EON_PRIVATE_IMPORT AFTER buyer=ENG', ''),
               good.replace('BEFORE buyer=ENG seller=CAN', 'BEFORE buyer=ENG seller=ENG'),
               good.replace('resource = uranium', 'resource = oil', 1),
               '\n'.join(good.splitlines()[:-3]), factory_trace.replace('factories = 3', 'factories = 4'),
               factory_trace.replace('factories=3', 'factories=0')]
    for candidate in changes:
        try: analyzer.parse_log(candidate, {})
        except AssertionError: pass
        else: raise AssertionError('Malformed native AI dispatch evidence accepted')
    parser = load_parser()
    original = parser.ast((ROOT/'common/scripted_effects/eon_uranium_effects.txt').read_bytes())
    private = deepcopy(original)
    daily = parser.one(private, 'eon_uranium_daily')
    daily[:0] = [('log', '=', 'EON_PRIVATE_IMPORT DAILY_START country=[THIS.GetTag]'),
                 ('log', '=', 'EON_PRIVATE_IMPORT BEFORE buyer=[THIS.GetTag] seller=CAN amount=8'),
                 ('log', '=', 'EON_PRIVATE_IMPORT AFTER buyer=[THIS.GetTag]')]
    count = 0

    def debug(nodes):
        nonlocal count
        for key, op, value in nodes:
            if key == 'meta_effect': value.append(('debug', '=', 'yes')); count += 1
            elif isinstance(value, list): debug(value)
    debug(daily)
    assert count == 1
    with tempfile.TemporaryDirectory(prefix='eon-ai-trace-controls-') as temporary:
        directory = Path(temporary)
        path = directory/'common/scripted_effects/eon_uranium_effects.txt'
        path.parent.mkdir(parents=True)
        path.write_text(render(private), encoding='utf-8')
        binding = analyzer.verify_daily_trace(directory, ROOT)
        assert binding['trace_controls'] == {'trace_logs': 3, 'meta_debug': 1}
        daily.append(('set_variable', '=', parser.ast('unapproved = 1')))
        path.write_text(render(private), encoding='utf-8')
        try: analyzer.verify_daily_trace(directory, ROOT)
        except AssertionError: pass
        else: raise AssertionError('Unapproved private daily effect accepted')
    print(json.dumps({'native_ai_dispatch_trace_controls_verified': True, 'negative_controls': len(changes)+1,
                      'native_import_delivery_verified': False, 'native_game_behavior_tested': False}))


if __name__ == '__main__': main()
