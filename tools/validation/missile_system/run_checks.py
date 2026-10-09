"""Run focused missile/arsenal source checks without launching the game."""
from pathlib import Path
import json
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
scripts = sorted(HERE.glob('test_*.py'))
scripts.extend(sorted((HERE.parent/'nuclear_arsenal').glob('test_*.py')))
groups = []
for path in scripts:
    process = subprocess.run([sys.executable, '-B', str(path)], capture_output=True,
                             text=True, encoding='utf-8')
    if process.returncode:
        sys.stderr.write(process.stdout + process.stderr)
        raise SystemExit(process.returncode)
    item = {'script': str(path.relative_to(HERE.parent)).replace('\\', '/'),
            'checks_passed': True}
    if process.stdout.strip(): item['report'] = json.loads(process.stdout)
    else:
        match = re.search(r'Ran (\d+) tests?', process.stderr)
        assert match and '\nOK' in process.stderr, ('No test receipt', path)
        item['unittest_cases'] = int(match[1])
    groups.append(item)
print(json.dumps({'focused_groups_passed': len(groups), 'groups': groups,
                  'native_game_behavior_tested': False,
                  'human_ui_verified': False, 'multiplayer_verified': False}, indent=2))
