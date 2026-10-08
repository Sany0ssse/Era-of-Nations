"""Inspect a recorded native startup against every tested changed game path."""
from pathlib import Path
import argparse
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[3]
LEGACY = ('events/00_Influence_events.txt', 'common/scripted_diplomatic_actions/00_scripted_diplomatic_actions.txt',
          'common/scripted_triggers/00_game_rule_triggers.txt', 'common/scripted_effects/!_energy_effects.txt',
          'common/scripted_effects/00_investment_scripted_effects.txt', 'common/scripted_effects/00_money_system.txt',
          'common/on_actions/00_costili.txt', 'common/on_actions/01_on_actions.txt')


def main():
    arguments = argparse.ArgumentParser()
    arguments.add_argument('probe_directory', type=Path)
    args = arguments.parse_args()
    directory = args.probe_directory.resolve()
    receipt = json.loads((directory / 'start-receipt.json').read_text(encoding='utf-8-sig'))
    snapshot = json.loads((directory / 'tested-source.json').read_text(encoding='utf-8-sig'))
    logs = Path(receipt['intended_user_dir']) / 'logs'
    errors = (logs / 'error.log').read_text(encoding='utf-8-sig')
    system = (logs / 'system.log').read_text(encoding='utf-8-sig')
    setup = (logs / 'setup.log').read_text(encoding='utf-8-sig')
    game = (logs / 'game.log').read_text(encoding='utf-8-sig')
    paths = tuple(snapshot['source_sha256']) + LEGACY
    matched = [line for line in errors.splitlines() if 'eon_' in line or any(path in line for path in paths)]
    mismatches = [path for path, digest in snapshot['source_sha256'].items()
                  if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest]
    started = bool(re.search(r'Startup time: \d+ms', setup))
    active = 'Active Mod: Era of Nations' in system and 'Active Mod Count: 1' in system
    passed = started and active and not matched and not mismatches
    report = {'native_diplomacy_startup_passed': passed,
              'frontend_startup_completed': started, 'expected_only_mod_active': active,
              'tested_game_source_files': len(snapshot['source_sha256']),
              'source_hash_mismatches': mismatches,
              'diplomacy_error_lines': len(matched), 'diplomacy_errors': matched,
              'singleplayer_launch_observed': '[[ Launching SINGLEPLAYER-game ]]' in game,
              'new_campaign_initialization_observed': 'on_startup init completed' in game,
              'total_error_log_lines': len(errors.splitlines()),
              'other_startup_issues_remain': bool(errors.splitlines()),
              'native_campaign_proven': False, 'native_save_load_proven': False,
              'native_multiplayer_proven': False,
              'proof_scope': 'native frontend load for current changed game files and explicit legacy diplomacy dependencies'}
    (directory / 'native-startup-result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
