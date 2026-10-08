"""Cross-package definition, format and notice checks; not native script compilation."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASELINE = 'c1420b108dee2d129018951c9ba73c1f6bfc4360'
GAME_ROOTS = {'common', 'events', 'interface', 'localisation', 'history'}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def main():
    changed = set(git('diff', '--name-only', '-z', BASELINE).decode().split('\0'))
    changed.update(git('ls-files', '--others', '--exclude-standard', '-z').decode().split('\0'))
    paths = sorted(p for p in changed if p and p.split('/')[0] in GAME_ROOTS)
    definitions = set()
    for folder in ('common/scripted_effects', 'common/scripted_triggers'):
        for path in (ROOT / folder).glob('*.txt'):
            definitions.update(re.findall(r'(?m)^\s*(eon_[\w]+)\s*=\s*\{', path.read_text(encoding='utf-8-sig')))
    refs = []
    source_sha = {}
    for relative in paths:
        path = ROOT / relative
        raw = path.read_bytes()
        source_sha[relative] = hashlib.sha256(raw).hexdigest()
        text = raw.decode('utf-8-sig')
        if relative.endswith('.yml'):
            assert raw.startswith(b'\xef\xbb\xbf'), ('Missing localization BOM', relative)
            continue
        # Inline calls are common inside actual decision and callback guards.
        # Check all call tokens, not only statements occupying a whole line.
        for name in re.findall(r'\b(eon_[\w]+)\s*=\s*(?:yes|no)\b', text):
            assert name in definitions, ('Undefined custom effect/trigger', relative, name)
            refs.append((relative, name))
        baseline = subprocess.run(['git', 'show', BASELINE + ':' + relative], cwd=ROOT, capture_output=True)
        if baseline.returncode == 0:
            old = baseline.stdout
            assert raw.startswith(b'\xef\xbb\xbf') == old.startswith(b'\xef\xbb\xbf'), ('Changed BOM', relative)
            if b'\r\n' in old and b'\n' not in old.replace(b'\r\n', b''):
                assert b'\n' not in raw.replace(b'\r\n', b''), ('Introduced bare LF', relative)
    # Diplomatic notification windows never perform consent or resource mutations.
    notice = ROOT / 'events/eon_diplomatic_relations_events.txt'
    if notice.is_file():
        text = notice.read_text(encoding='utf-8-sig')
        assert not re.search(r'\beon_diplomatic_relations_[\w]+\s*=\s*yes', text), 'Mission notice must not authorize a transition'
        assert not re.search(r'\b(?:add_to_variable|subtract_from_variable|add_to_array|set_country_flag)\s*=', text), 'Mission notice must not mutate agreement state'
    print(json.dumps({
        'checks_passed': True,
        'changed_game_files': len(paths),
        'feature_baseline_commit': BASELINE,
        'custom_call_references_checked': len(refs),
        'source_sha256': source_sha,
        'native_compilation_proven': False,
        'proof_scope': 'definition references, BOM/EOL preservation and informational mission notices',
    }, indent=2))


if __name__ == '__main__':
    main()
