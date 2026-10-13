"""Strict private AI isolation boundary; no installs, source writes or launches."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/validation/diplomacy_package_02'))
from _treaty_support import ast

RUNTIME_OVERRIDE_ACTIONS_V15 = {
    'common/decisions/eon_eu_membership_decisions.txt': (
        'eon_eu_notify_withdrawal', 'eon_eu_revoke_withdrawal'),
    'common/decisions/eon_eu_withdrawal_extension_decisions.txt': (
        'eon_eu_extension_propose', 'eon_eu_extension_approve',
        'eon_eu_extension_reject', 'eon_eu_extension_abstain',
        'eon_eu_extension_accept_final', 'eon_eu_extension_cancel_proposal'),
}
RUNTIME_OVERRIDE_ACTIONS_V16 = {
    **RUNTIME_OVERRIDE_ACTIONS_V15,
    'common/decisions/eon_edu_decisions.txt': (
        'eon_edu_request_join', 'eon_edu_accept_request',
        'eon_edu_reject_request', 'eon_edu_withdraw_request'),
    'common/decisions/EU_voting_decisions.txt': ('EU_create_EDU',),
}
# Explicit historical default; v16 callers must declare their fixture version.
RUNTIME_OVERRIDE_ACTIONS = RUNTIME_OVERRIDE_ACTIONS_V15


def override_actions(fixture_version=15):
    assert type(fixture_version) is int and fixture_version in (15, 16, 17, 18), 'Unsupported runtime override fixture version'
    return RUNTIME_OVERRIDE_ACTIONS_V15 if fixture_version == 15 else RUNTIME_OVERRIDE_ACTIONS_V16


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_override_bytes(relative, original, override, selected_ids, *, fixture_version=15):
    """Require the whole active AST to equal the version's scoped AI holds.

    The source bytes are retained independently. Only the explicitly listed
    ai_will_do nodes may become factor0; callbacks, prices, targeting, gates,
    nonselected decisions, category metadata and their order remain identical.
    """
    actions = override_actions(fixture_version)
    count_name = 'eight' if fixture_version == 15 else 'thirteen'
    assert relative in actions, 'Unknown private override path'
    wanted = actions[relative]
    assert isinstance(selected_ids, (list, tuple)) and len(selected_ids) == len(set(selected_ids))
    assert set(selected_ids) == set(wanted), f'Require exactly the declared {count_name} selected AI actions'
    original_ast = ast(original.decode('utf-8-sig', errors='strict'))
    override_text = override.decode('utf-8', errors='strict')
    assert '\ufeff' not in override_text, 'Native override identifiers must not contain U+FEFF'
    override_ast = ast(override_text)
    expected = deepcopy(original_ast)
    found = []
    for _, _, category in expected:
        if not isinstance(category, list):
            continue
        for ident, _, action in category:
            if ident not in wanted:
                continue
            assert isinstance(action, list), 'Selected decision needs its actual source body'
            positions = [i for i, node in enumerate(action) if node[0] == 'ai_will_do']
            assert len(positions) == 1, 'Selected action needs exactly one source AI block'
            assert isinstance(action[positions[0]][2], list), 'Source AI block must be structured'
            action[positions[0]] = ('ai_will_do', '=', [('factor', '=', '0')])
            found.append(ident)
    assert len(found) == len(wanted) and set(found) == set(wanted), 'Missing or duplicate selected source decision'
    assert override_ast == expected, f'Override changed source AST outside the exact {count_name} AI holds'
    from runtime_support import ai_weight_overlay
    expected_bytes = ai_weight_overlay(original.decode('utf-8', errors='strict'), wanted).encode('utf-8')
    assert override == expected_bytes, 'Override changed bytes outside the exact selected AI bodies'
    return {
        'path': relative,
        'source_sha256': digest(original),
        'runtime_override_sha256': digest(override),
        'selected_ai_action_ids': list(wanted),
    }


def validate_override_maps(overrides, authoritative, effective, provenance, fixtures, *, fixture_version=15):
    """Bind before/after maps explicitly; unknown substitutions fail closed."""
    actions = override_actions(fixture_version)
    count, count_name = (8, 'two') if fixture_version == 15 else (13, 'four')
    assert isinstance(overrides, dict) and set(overrides) == set(actions), f'Require exactly {count_name} declared private overrides'
    assert set(provenance) == set(actions), f'Require exactly {count_name} authoritative provenance snapshots'
    assert set(authoritative) == set(effective), 'Authoritative/effective dependency keysets differ'
    expected = dict(authoritative)
    fields = {'path', 'source_sha256', 'runtime_override_sha256', 'selected_ai_action_ids'}
    all_ids = []
    for path, record in overrides.items():
        assert isinstance(record, dict) and set(record) == fields, 'Unexpected runtime override metadata'
        assert record['path'] == path, 'Override record path does not match its key'
        ids = record['selected_ai_action_ids']
        assert isinstance(ids, list) and len(ids) == len(set(ids)) and set(ids) == set(actions[path]), 'Selected AI action scope drift'
        all_ids.extend(ids)
        before, after = record['source_sha256'], record['runtime_override_sha256']
        assert all(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) for value in (before, after)), 'Malformed override SHA256'
        assert authoritative.get(path) == provenance[path] == before, 'Authoritative provenance SHA mismatch'
        assert fixtures.get(path) == after, 'Active override does not match the exact fixture bytes'
        expected[path] = after
    assert len(all_ids) == len(set(all_ids)) == count, f'Require exactly {count} isolated AI blocks'
    assert effective == expected, f'Effective source differs outside the {count_name} declared private overrides'
    return True
