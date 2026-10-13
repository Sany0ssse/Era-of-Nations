"""Run the peace regressions; this report is source/model evidence only."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    tests = []
    for name in ['test_transport.py', 'test_execution.py', 'test_legacy_safety.py', 'test_legacy_source_compat.py', 'test_native_grammar.py', 'test_ai_pair_context.py', 'test_subject_pair_scope.py', 'test_reserved_selectors.py']:
        p = subprocess.run([sys.executable, '-B', str(HERE / name)], cwd=ROOT,
                           capture_output=True, text=True, encoding='utf-8')
        tests.append({'suite': name, 'passed': p.returncode == 0,
                      'diagnostic': p.stdout + p.stderr})
    files = []
    for folder in ['common/scripted_diplomatic_actions', 'common/scripted_triggers',
                   'common/scripted_effects', 'common/on_actions', 'events',
                   'localisation/english', 'localisation/russian']:
        files.extend((ROOT/folder).glob('eon_peace_settlement*'))
    for rel in ['common/scripted_diplomatic_actions/peace_deal.txt',
                'common/scripted_diplomatic_actions/MDC_enforce_peace_options.txt',
                'common/scripted_effects/peace_deal_scripted_effects.txt',
                'common/on_actions/00_costili.txt', 'common/on_actions/00_postwar_recovery.txt',
                'localisation/english/peace_deals_l_english.yml',
                'localisation/russian/peace_deals_l_russian.yml']:
        files.append(ROOT/rel)
    report = {'checks_passed': all(t['passed'] for t in tests), 'suites': tests,
              'source_sha256': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
              'native_execution_proven_by_this_runner': False,
              'native_human_choice_proven': False,
              'two_client_multiplayer_proven': False}
    print(json.dumps(report, indent=2))
    return 0 if report['checks_passed'] else 1


if __name__ == '__main__': raise SystemExit(main())
