"""Source and differential regressions; native time/FPS require separate runs."""
from pathlib import Path
import hashlib, json, re, subprocess, sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SOURCES = (
    'common/scripted_effects/00_money_system.txt',
    'common/scripted_effects/eon_energy_delivery_effects.txt',
    'common/scripted_effects/eon_economy_state_refresh_effects.txt',
    'common/scripted_effects/eon_migration_treaty_effects.txt',
    'common/scripted_effects/eon_migration_relief_effects.txt',
)

def main():
    reports = {}
    for name in ('test_economy_refresh.py', 'test_migration_monthly.py', 'test_byte_compat.py', 'test_sanctions_income_compat.py', 'test_weekly_optimization_compat.py', '../migration_treaty/test_lifecycle.py'):
        result = subprocess.run([sys.executable, '-B', str(HERE / name)], cwd=ROOT,
            capture_output=True, text=True, encoding='utf-8')
        if result.returncode:
            sys.stderr.write(name+'\n'+result.stdout+result.stderr)
            raise SystemExit(result.returncode)
        counts = re.findall(r'^Ran (\d+) tests? in ', result.stderr, re.M)
        assert len(counts) == 1, ('Missing actual unittest result', name)
        reports[name] = {'tests': int(counts[0]), 'passed': True}
    print(json.dumps({'source_checks_passed': True,
        'unit_tests': sum(r['tests'] for r in reports.values()), 'reports': reports,
        'source_sha256': {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES},
        'proof_scope': 'actual current source, strict byte/dependency guards and bounded differential worlds',
        'native_campaign_proven': False, 'native_performance_proven': False, 'fps_proven': False}, indent=2))

if __name__ == '__main__': main()
