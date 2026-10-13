"""Strict current-money projection for the older debt byte boundary only.

Accepted later snippets are reversed exactly; the caller still compares every
remaining byte with the fixed debt baseline. Behavior tests execute current
source. This deliberately does not accept already-projected historical input.
"""
from pathlib import Path
import hashlib
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[3]
SOURCE_PATH = 'common/scripted_effects/00_money_system.txt'


def _module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = result
    spec.loader.exec_module(result)
    return result


arsenal = _module('debt_current_arsenal', 'tools/validation/missile_system/byte_compat.py')
migration = _module('debt_current_migration', 'tools/validation/migration_relief/byte_compat.py')
weekly = _module('debt_current_weekly_eu', 'tools/validation/eu_weekly_cash/byte_compat.py')
economy = _module('debt_current_economy', 'tools/validation/performance_refresh/byte_compat.py')

# These exact two gates are also reviewed by package25. Digests bind their
# accepted bytes; no whole EU or economic function is restored here.
EU_FINANCE_ISLANDS = (
    (
        b'\t# EU\n\tif = {\n\t\tlimit = {\n\t\t\teon_eu_is_budget_participant = yes\n'
        b'\t\t\tNOT = { has_idea = EUU_subsidies_suspended }\n',
        b'\t# EU\n\tif = {\n\t\tlimit = {\n\t\t\tis_in_array = { global.EU_member = THIS }\n'
        b'\t\t\tNOT = { has_idea = EUU_subsidies_suspended }\n',
        '078d47459fed267b3335f2ed859934e250f3a5977eda1741747ba0c4b4567aeb',
        'a00300edd9d074f679ba4f167f3e35a3ae88f77f0e07abbbf96d7661b24b77ef',
    ),
    (
        b'\t# European Union Contribution Expenses\n'
        b'\tif = { limit = { eon_eu_is_budget_participant = yes }\n'
        b'\t\tadd_to_variable = { additional_expenses_rate = EU_budget_contribution_weekly }\n\t}\n',
        b'\t# European Union Contribution Expenses\n'
        b'\tif = { limit = { has_idea = EU_member }\n'
        b'\t\tadd_to_variable = { additional_expenses_rate = EU_budget_contribution_weekly }\n\t}\n',
        'ccbe0ab55a031c5f8295ac3ca7dfd701698438b753a364aa5df0f4cc34448f03',
        '3bbeaef261f41f815e3f6359cef10eb2ea949a099427caffb59690bf39a9139d',
    ),
)


def project_current_money(relative, raw):
    if relative != SOURCE_PATH:
        return raw
    if isinstance(raw, str):
        return project_current_money(relative, raw.encode('utf-8')).decode('utf-8')
    assert isinstance(raw, bytes), 'Current-money byte projection requires bytes or str'
    raw = economy.restore_adjacent_state_refresh(relative, raw)
    # The shared arsenal helper accepts its older baseline too. This caller
    # operates on current source and requires both accepted insertions first.
    assert raw.count(arsenal.INSERTIONS[SOURCE_PATH]) == 1, 'One exact current arsenal money hook required'
    assert raw.count(arsenal.MARKET_RESET) == 1, 'One exact current market reset required'
    result = arsenal.restore_arsenal_budget(relative, raw)
    # decode utf-8 preserves an existing BOM character for byte-exact reencode.
    result = migration.restore_migration_money(relative, result.decode('utf-8')).encode('utf-8')
    result = weekly.restore_weekly_subsidy(relative, result)
    assert result.count(b'eon_eu_is_budget_participant = yes') == 2, 'Exactly two current EU finance gates required'
    for current, original, current_digest, original_digest in EU_FINANCE_ISLANDS:
        assert hashlib.sha256(current).hexdigest() == current_digest, 'EU finance current catalog digest changed'
        assert hashlib.sha256(original).hexdigest() == original_digest, 'EU finance original catalog digest changed'
        assert result.count(current) == 1, 'One exact current EU finance island required'
        result = result.replace(current, original, 1)
    return result
