"""Bounded performance regressions; native wall time is measured separately."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
FILES = (
    'common/on_actions/00_ammo_on_actions.txt',
    'common/scripted_effects/00_ammo_mechanics_effects.txt',
    'common/scripted_effects/eon_energy_delivery_effects.txt',
    'common/scripted_effects/eon_eu_membership_effects.txt',
    'common/scripted_effects/eon_eu_lifecycle_effects.txt',
)


def main():
    reports = {}
    for name in ('test_ammo.py', 'test_ammo_ports.py', 'test_energy_traversal.py', 'test_eu_refresh.py'):
        result = subprocess.run([sys.executable, '-B', str(HERE / name)], cwd=ROOT,
                                capture_output=True, text=True, encoding='utf-8')
        if result.returncode:
            sys.stderr.write(name + '\n' + result.stdout + result.stderr)
            raise SystemExit(result.returncode)
        counts = re.findall(r'^Ran (\d+) tests? in ', result.stderr, re.M)
        assert len(counts) == 1, ('Missing actual unittest result', name)
        reports[name] = {'tests': int(counts[0]), 'passed': True}
    print(json.dumps({
        'source_checks_passed': True,
        'unit_tests': sum(item['tests'] for item in reports.values()),
        'reports': reports,
        'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES},
        'proof_scope': 'actual source AST, bounded state equivalence and traversal counts',
        'native_performance_proven': False,
        'fps_proven': False,
    }, indent=2))


if __name__ == '__main__':
    main()
