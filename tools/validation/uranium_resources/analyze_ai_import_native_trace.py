"""Verify source-bound native AI meta dispatch; never infer trade delivery."""
from pathlib import Path
import argparse
import importlib.util
import json
import re

from build_native_probe import ROOT, load_parser, sha
from build_core_native_probe import canonical

TRACE = 'EON_PRIVATE_IMPORT'


def parse_log(text, manifest):
    lines, requests = text.splitlines(), []
    before = re.compile(TRACE+r' BEFORE buyer=([A-Z][A-Z0-9]{2}) seller=([A-Z][A-Z0-9]{2}) (amount|factories)=([0-9]+)(?:\s|$)')
    after = re.compile(TRACE+r' AFTER buyer=([A-Z][A-Z0-9]{2})(?:\s|$)')
    generated = re.compile(r'^\s*create_import\s*=\s*\{\s*resource\s*=\s*uranium\s+(amount|factories)\s*=\s*([0-9]+)\s+exporter\s*=\s*([A-Z][A-Z0-9]{2})\s*\}\s*$')
    pending, after_count, generated_count = None, 0, 0
    for index, line in enumerate(lines, 1):
        match = before.search(line)
        if match:
            assert pending is None, 'Native request began before previous dispatch returned'
            buyer, seller, trace_argument, amount = match.groups()
            amount = int(amount)
            assert buyer != seller and amount >= 1
            dates = re.findall(r'\[(\d{4}\.\d{2}\.\d{2}\.\d{2})\]', line)
            assert dates
            pending = {'buyer': buyer, 'seller': seller, 'quantity': amount, 'trace_argument': trace_argument, 'native_date': dates[-1],
                       'before_line': index, 'generated_line': None, 'after_line': None}
        elif re.search(r'create_import\s*=', line):
            match = generated.fullmatch(line)
            assert pending and match and not pending['generated_line'], 'Unexpected, malformed or unbound native meta command'
            argument, amount, seller = match.groups()
            assert (int(amount), seller) == (pending['quantity'], pending['seller'])
            if pending['trace_argument'] == 'factories': assert argument == 'factories'
            if argument == 'amount': assert int(amount) >= 8 and int(amount) % 8 == 0
            pending['native_command_argument'] = argument
            pending[argument] = int(amount)
            pending['generated_line'] = index
            generated_count += 1
        elif after.search(line):
            match = after.search(line)
            assert pending and pending['generated_line'] and match[1] == pending['buyer']
            dates = re.findall(r'\[(\d{4}\.\d{2}\.\d{2}\.\d{2})\]', line)
            assert dates and dates[-1] == pending['native_date'], 'Dispatch return changed native hour'
            pending['after_line'] = index
            requests.append(pending)
            pending = None
            after_count += 1
    assert pending is None, 'Native dispatch did not return'
    assert len(requests) == after_count == generated_count and len(requests) >= 3
    assert len({request['buyer'] for request in requests}) >= 2
    return {'passed': ['dispatch_'+str(index+1) for index in range(len(requests))], 'failed': [],
            'native_ai_import_dispatches': requests, 'native_ai_import_dispatch_count': len(requests),
            'native_ai_import_dispatch_country_count': len({request['buyer'] for request in requests}),
            'native_import_delivery_verified': False, 'native_import_retention_verified': False}


def verify_daily_trace(private_source, production_source):
    parser = load_parser()
    rel = 'common/scripted_effects/eon_uranium_effects.txt'
    played = parser.one(parser.ast((private_source/rel).read_bytes()), 'eon_uranium_daily')
    production = parser.one(parser.ast((production_source/rel).read_bytes()), 'eon_uranium_daily')
    removed = {'trace_logs': 0, 'meta_debug': 0}

    def normalize(nodes, inside_meta=False):
        result = []
        for key, operator, value in nodes:
            if key == 'log' and isinstance(value, str) and value.startswith(TRACE+' '):
                assert operator == '=' and re.match(TRACE+r' (DAILY_START|BEFORE|AFTER) ', value)
                removed['trace_logs'] += 1
                continue
            if inside_meta and key == 'debug':
                assert operator == '=' and value == 'yes'
                removed['meta_debug'] += 1
                continue
            if isinstance(value, list): value = normalize(value, inside_meta or key == 'meta_effect')
            result.append((key, operator, value))
        return result

    normalized = normalize(played)
    assert removed == {'trace_logs': 3, 'meta_debug': 1}, ('Unexpected private daily trace changes', removed)
    assert normalized == production, 'Played daily helper differs beyond declared logging/debug controls'
    return {'production_daily_ast_sha256': canonical(production), 'played_daily_ast_sha256': canonical(played),
            'normalized_played_daily_ast_sha256': canonical(normalized), 'trace_controls': removed,
            'production_effects_sha256': sha(production_source/rel), 'played_effects_sha256': sha(private_source/rel)}


def analyze(manifest_path, launch_path, game_log, production_source=ROOT):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    assert manifest['kind'] == 'native_staged_uranium_enrichment'
    binding = verify_daily_trace(Path(manifest['source_root']), production_source)
    path = Path(__file__).with_name('analyze_native_probe.py')
    spec = importlib.util.spec_from_file_location('uranium_ai_dispatch_receipt_verifier', path)
    evidence = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evidence)
    evidence.parse_log = parse_log
    result = evidence.analyze(manifest_path, launch_path, game_log)
    result['native_scripted_ai_import_dispatch_verified'] = result.pop('native_resource_trade_prototype_passed')
    result['actual_production_daily_binding'] = binding
    result['receipt_verifier_sha256'] = sha(path)
    result['analyzer_sha256'] = sha(Path(__file__))
    result['limits'] = ['Actual native meta import dispatch and return only; no imported-resource delivery or retention observation.',
                        'Played helper equals production daily AST after removing exactly3 trace logs and1 meta debug flag.',
                        'Launch/profile/export/source/fixture/documentation receipts are checked through the bound native family.',
                        'This diagnostic does not accept incomplete enrichment, material, mining, rights or finished-fuel families.']
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--manifest', type=Path, required=True)
    cli.add_argument('--launch-receipt', type=Path, required=True)
    cli.add_argument('--game-log', type=Path, required=True)
    cli.add_argument('--production-source', type=Path, default=ROOT)
    args = cli.parse_args()
    result = analyze(args.manifest, args.launch_receipt, args.game_log, args.production_source)
    print(json.dumps(result, indent=2))
    if not result['native_scripted_ai_import_dispatch_verified']: raise SystemExit(1)


if __name__ == '__main__': main()
