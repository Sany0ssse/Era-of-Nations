"""Current hotkey behavior with a feature-specific frozen source boundary.

The original hotkey runner's whole-worktree inventory rejects any subsequent
diplomacy edit. That historical publication check is not a current regression
gate. Its unchanged behavior functions are executed here; no source projection,
historical counter adjustment, or replacement of that original check occurs.
"""
from pathlib import Path
import importlib.util
import json
import subprocess

ROOT = Path(__file__).resolve().parents[3]
FROZEN = 'a5f2ccc585b704bd99dbdf93595bf29ab573a62a'


def main():
    path = ROOT / 'tools/validation/cheat_hotkey/test_hotkey.py'
    spec = importlib.util.spec_from_file_location('current_hotkey_regression', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source_hashes = {}
    for relative in module.GAME:
        current = module.read(relative)
        frozen = subprocess.check_output(['git', 'show', FROZEN + ':' + relative], cwd=ROOT)
        assert current == frozen, ('Hotkey source changed outside this package', relative)
        source_hashes[relative] = module.sha(current)
    original = module.decision_inventory(module.baseline(module.DECISIONS))
    current = module.decision_inventory(module.read(module.DECISIONS))
    executor = module.Executor(module.definitions(module.TRIGGERS), module.definitions(module.EFFECTS))
    assert set(executor.triggers) == {'eon_cheat_access'}
    assert set(executor.effects) == {'eon_toggle_cheat_access'}
    callback, window, button = module.collect_gui(executor)
    module.behavior(executor, original, current, callback)
    module.text_and_category(executor, callback)
    assert source_hashes == {relative: module.sha(module.read(relative)) for relative in module.GAME}
    print(json.dumps({
        'checks_passed': True,
        'frozen_feature_commit': FROZEN,
        'behavior_assertions': sum(module.groups.values()),
        'behavior_groups': dict(module.groups),
        'source_sha256': source_hashes,
        'original_runner_sha256': module.sha(path.read_bytes()),
        'original_whole_worktree_inventory': 'not applicable: it rejects intentional packages 24-26',
        'proof_scope': 'unchanged current hotkey source and original behavior functions; no native keyboard or multiplayer proof',
        'native_runtime_verified': False,
    }, indent=2))


if __name__ == '__main__':
    main()
