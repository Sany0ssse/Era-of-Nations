"""Run current completion packages without counting historical checks as live proof."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def run(relative, *arguments):
    result = subprocess.run(
        [sys.executable, '-B', str(ROOT / relative), *arguments], cwd=ROOT,
        capture_output=True, text=True, encoding='utf-8',
    )
    if result.returncode:
        sys.stderr.write(relative + '\n' + result.stdout + result.stderr)
        raise SystemExit(result.returncode)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RuntimeError('Expected structured proof from ' + relative)


def main():
    # Windows console defaults cannot encode all mission class names.
    # Keep the aggregate proof JSON and diagnostics consistently UTF-8.
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    reports = {}
    reports['localisation'] = run('tools/validation/diplomacy_completion/check_localisation.py')
    reports['localisation_override_boundaries'] = run('tools/validation/localisation_override_checker/test_checker.py')
    reports['consultation_ui'] = run('tools/validation/diplomacy_channel_ui/run_checks.py')
    reports['consultation_lifecycle_completion'] = run('tools/validation/consultation_lifecycle_completion/run_checks.py')
    for number in (24, 25, 26, 27, 28):
        path = f'tools/validation/diplomacy_package_{number}/run_checks.py'
        if not (ROOT / path).is_file():
            raise RuntimeError('Completion work is incomplete: missing ' + path)
        reports[f'package_{number}'] = run(path)
    reports['cheat_hotkey'] = run('tools/validation/diplomacy_completion/check_hotkey_regression.py')
    reports['native_grammar'] = run('tools/validation/diplomacy_completion/check_native_grammar.py')
    reports['support_native_compatibility'] = run('tools/validation/diplomacy_completion/check_support_native_compat.py')
    reports['ordinary_alliance'] = run('tools/validation/diplomacy_package_03/test_ordinary_alliance.py')
    reports['weekly_cash'] = run('tools/validation/diplomacy_completion/check_weekly_cash.py')
    reports['debt_accounting'] = run('tools/validation/debt_accounting/run_checks.py')
    reports['debt_bailout'] = run('tools/validation/debt_bailout/run_checks.py')
    reports['aid_flag_scope'] = run('tools/validation/aid_flag_scope/test_scope.py', '--json')
    reports['debt_default_accounting'] = run('tools/validation/debt_default_accounting/test_accounting.py', '--require-integration')
    reports['debt_default_lifecycle'] = run('tools/validation/debt_default_accounting/test_lifecycle.py')
    reports['debt_default_assets'] = run('tools/validation/debt_default_accounting/test_assets.py')
    reports['debt_default_asset_source_boundaries'] = run('tools/validation/debt_default_accounting/test_asset_source.py')
    reports['debt_default_source_boundaries'] = run('tools/validation/debt_default_accounting/test_source_compat.py')
    reports['annex_embargo_cleanup'] = run('tools/validation/diplomacy_completion/check_annex_embargo_cleanup.py')
    reports['integration_sources'] = run('tools/validation/diplomacy_completion/check_integration_sources.py')
    check = subprocess.run(
        ['git', '-c', 'core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol',
         'diff', '--check'], cwd=ROOT, capture_output=True, text=True, encoding='utf-8',
    )
    if check.returncode:
        sys.stderr.write(check.stdout + check.stderr)
        raise SystemExit(check.returncode)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    own_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    print(json.dumps({
        'checks_passed': True,
        'base_head': head,
        'runner_sha256': own_sha,
        'reports': reports,
        'native_campaign_proven': False,
        'multiplayer_proven': False,
        'full_diplomacy_objective_complete': False,
        'proof_scope': 'current package source checks; no historical cumulative scenario claim',
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
