"""Exact inverse of arsenal hooks and the market accumulator reset.

This never hides an entire economic block. Unknown edits to the new hook fail;
the caller must still compare all remaining bytes against its prior baseline.
Actual behavior checks always execute current game source.
"""
INSERTIONS = {
    'common/scripted_effects/00_money_system.txt': (
        b'\t# Arsenal sustainment is a weekly cash expense; existing silo/bomber costs stay in military spending.\n'
        b'\teon_nuclear_arsenal_refresh = yes\n'
        b'\tadd_to_variable = { additional_expenses_rate = eon_nuclear_arsenal_weekly_cost }\n'),
    'common/on_actions/01_on_actions.txt': (
        b'\t\t\t# Only the weekly pulse advances arsenal readiness; menu/budget refreshes never do.\n'
        b'\t\t\teon_nuclear_arsenal_weekly = yes\n'),
}

MARKET_BEFORE = (b'\tif = { limit = { check_variable = { market_purchase_factories > 0 } }\n'
                 b'\t\t#start the math\n')
MARKET_RESET = b'\t\tset_temp_variable = { market_purchase_factories_cost = 0 }\n'
MARKET_AFTER = MARKET_BEFORE.replace(b'\t\t#start the math\n', MARKET_RESET+b'\t\t#start the math\n')


def restore_arsenal_budget(relative, raw):
    if isinstance(raw, str):
        return restore_arsenal_budget(relative, raw.encode('utf-8')).decode('utf-8')
    if relative not in INSERTIONS: return raw
    insertion = INSERTIONS[relative]
    if b'eon_nuclear_arsenal_' not in raw: return raw
    assert raw.count(insertion) == 1, 'Altered/duplicate arsenal budget hook: '+relative
    result = raw.replace(insertion, b'', 1)
    assert b'eon_nuclear_arsenal_' not in result, 'Unexpected remaining arsenal hook: '+relative
    if relative == 'common/scripted_effects/00_money_system.txt':
        assert result.count(MARKET_AFTER) == 1 and result.count(MARKET_RESET) == 1, 'Altered/missing/duplicate market accumulator reset'
        result = result.replace(MARKET_AFTER, MARKET_BEFORE, 1)
    return result
