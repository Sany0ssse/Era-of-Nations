"""Current native-AI policy source regressions; never substitutes for a campaign."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
FILES = (
    'common/scripted_effects/00_ai_strategy_scripted_effects.txt',
    'common/ai_strategy/MD_econ_ai.txt', 'common/ai_strategy/BOT.txt',
    'common/ai_strategy/default.txt',
    'common/scripted_guis/01_energy_gui.txt',
    'common/on_actions/00_ai_gui_on_actions.txt',
    'common/scripted_diplomatic_actions/MDDC_energy_contract_scripted_diplomatic_actions.txt',
    'common/scripted_diplomatic_actions/eon_defensive_alliance_action.txt',
    'common/scripted_triggers/eon_defensive_alliance_offer_triggers.txt',
    'common/scripted_effects/eon_defensive_alliance_offer_effects.txt',
    'common/scripted_triggers/eon_defensive_alliance_ai_triggers.txt',
    'common/scripted_triggers/eon_energy_ai_policy_triggers.txt',
)


def main():
    results = {}
    for name in ('test_strategy.py', 'test_energy_policy.py', 'test_alliance_initiative.py', 'test_alliance_responses.py', 'test_energy_selector.py'):
        result = subprocess.run([sys.executable, '-B', str(HERE / name)], cwd=ROOT,
                                capture_output=True, text=True, encoding='utf-8')
        if result.returncode:
            sys.stderr.write(name + '\n' + result.stdout + result.stderr)
            raise SystemExit(result.returncode)
        counts = re.findall(r'^Ran (\d+) tests? in ', result.stderr, re.M)
        assert len(counts) == 1, ('Missing actual unittest result', name)
        results[name] = {'tests': int(counts[0]), 'passed': True}
    print(json.dumps({
        'source_checks_passed': True,
        'unit_tests': sum(item['tests'] for item in results.values()),
        'reports': results,
        'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES},
        'proof_scope': 'bounded execution of actual source with explicit engine inputs',
        'native_ai_choice_proven': False,
        'long_campaign_proven': False,
        'multiplayer_proven': False,
    }, indent=2))


if __name__ == '__main__':
    main()
