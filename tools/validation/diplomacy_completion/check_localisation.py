"""Check EON player-facing EN/RU keys, including implicit diplomatic UI keys.

HOI4 scripted diplomatic actions use UPPERCASE_ID_TITLE and
UPPERCASE_ID_ACTION_DESC in the diplomacy list. An explicit send_description
does not supply either of those keys. This check is not a rendered UI test.
"""
from collections import defaultdict
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/validation/diplomacy_package_03'))
from _support import ast

KEY = re.compile(r'^\s*([\w.@-]+)\s*:\s*(?:\d+)?\s*"((?:\\.|[^"\\])*)"\s*(?:#.*)?$')
KEY_START = re.compile(r'^\s*((?:eon_|EON_)[\w.@-]+)\s*:')
ALIAS = re.compile(r'\$([A-Za-z_][\w.]*)(?:\|[^$]*)?\$')
RAW_KEY = re.compile(r'(?:eon_|EON_)[\w.]+')
SCRIPTED = re.compile(r'\[(?:[A-Za-z_]\w*\.)*((?:eon_|EON_)\w+)\]')
EXPLICIT = {'title', 'desc', 'text', 'tooltip', 'custom_effect_tooltip',
            'localization_key', 'send_description', 'receive_description',
            'accept_title', 'accept_description', 'reject_title',
            'reject_description', 'cost_string'}

# These retained internal IDs are deliberately empty, never player-facing.
# The separate private_debug_panel validator also checks the alpha-zero asset,
# current GUI bindings and effects. This checker independently pins that same
# reviewed transparent texture before granting any narrow text exception.
PRIVATE_BLANK_KEYS = frozenset(('EON_CHEAT_HOTKEY_ON', 'EON_CHEAT_HOTKEY_OFF', 'EON_CHEAT_HOTKEY_TT'))
PRIVATE_LISTENER = 'interface/eon_cheat_hotkey.gui'
PRIVATE_SPRITES = 'interface/MD_protest_decision.gfx'
PRIVATE_TEXTURE = 'gfx/interface/scripted_gui/expected_spending/empty.dds'
PRIVATE_TEXTURE_SHA256 = '474073fbf54a233c851906639d5c05c30e13e562b798ef1ed8af68869b10f474'


def private_listener_is_hidden(root, sources, errors):
    if not (root / PRIVATE_LISTENER).is_file():
        return False

    def one(nodes, key):
        values = [value for name, op, value in nodes if name == key and op == '=']
        if len(values) != 1:
            raise ValueError('expected exactly one ' + key)
        return values[0]

    try:
        raw = {relative: (root / relative).read_bytes()
               for relative in (PRIVATE_LISTENER, PRIVATE_SPRITES, PRIVATE_TEXTURE)}
        sources.update({relative: hashlib.sha256(data).hexdigest() for relative, data in raw.items()})
        window = one(one(ast(raw[PRIVATE_LISTENER]), 'guiTypes'), 'containerWindowType')
        button = one(window, 'buttonType')
        assert one(window, 'name') == 'eon_cheat_hotkey_window'
        assert {name for name, op, value in window} == {'name', 'position', 'orientation', 'size', 'buttonType'}
        assert one(button, 'name') == 'eon_cheat_toggle_button'
        assert one(button, 'buttonText') == ''
        assert one(button, 'pdx_tooltip') == 'EON_CHEAT_HOTKEY_TT'
        assert one(button, 'quadTextureSprite') == 'GFX_expected_spending_empty'
        sprites = [body for key, op, body in one(ast(raw[PRIVATE_SPRITES]), 'spriteTypes')
                   if key.lower() == 'spritetype' and isinstance(body, list)
                   and one(body, 'name') == 'GFX_expected_spending_empty']
        assert len(sprites) == 1 and one(sprites[0], 'texturefile') == PRIVATE_TEXTURE
        assert sources[PRIVATE_TEXTURE] == PRIVATE_TEXTURE_SHA256
        return True
    except (OSError, ValueError, AssertionError) as error:
        errors.append('Private blank labels require the reviewed hidden listener: ' + str(error))
        return False


def intentional_private_blank(language, key, value, provider, hidden_listener):
    return (hidden_listener and key in PRIVATE_BLANK_KEYS and value == ''
            and provider == f'localisation/{language}/eon_cheat_hotkey_l_{language}.yml')


# Only these reviewed old IDs may have an upstream row plus a replace row.
# File membership, key sets, and the exact two-provider pair are all required.
BAILOUT_OVERRIDE_KEYS = {
    'bankruptcy_seek_bailout_from_' + route + '_' + suffix
    for route in ('biggest_influencer', 'second_biggest_influencer', 'neighbour', 'overlord')
    for suffix in ('desc', 'tt')
}
DEFAULT_OVERRIDE_KEYS = {
    'debt_default_pay_' + amount + '_from_treasury' + suffix
    for amount in ('10', '50') for suffix in ('', '_desc', '_tt')
} | {'debt_default_pay_from_treasury_trigger_tooltip',
     'debt_default_main_mission_complete_trigger',
     'bankruptcy_default_on_debts_desc', 'bankruptcy_default_on_debts_tt',
     'bankruptcy.13.a', 'bankruptcy.13.b', 'bankruptcy.14.a',
     'debt_default_sell_civilian_factories_desc',
     'debt_default_dismantle_military_factories_desc',
     'debt_default_scrap_dockyard_desc',
     'debt_default_cut_down_government_services_desc'}


URANIUM_OVERRIDE_KEYS = {
    'build_enrichment_facility_button_tt', 'TOTAL_WEEKLY_NUCLEAR_MATERIAL_PRODUCTION_TT',
    'URANIUM_ENRICHMENT', 'energy.1.d', 'energy.10.d',
    'change_reactor_grade_material_effect_tt',
}

MIGRATION_TREATY_OVERRIDE_KEYS = {
    'propose_migrants_agreement', 'migrants_agreement_add', 'migrants_agreement_cut',
    'cancel_migrants_agreement',
} | {
    prefix + suffix
    for prefix in ('PROPOSE_MIGRANTS_AGREEMENT_', 'CANCEL_MIGRANTS_AGREEMENT_')
    for suffix in ('ACTION_DESC', 'DESC', 'ACTION_TITLE', 'TITLE', 'TOOLTIP')
}
MIGRATION_TREATY_NEW_KEYS = {
    'eon_migration_treaty_offer_available_tt', 'eon_migration_treaty_response_valid_tt',
}
MIGRATION_RELIEF_OVERRIDE_KEYS = {
    'additional_migrants_agreements_income_tt', 'MAXIMUM_MIGRATION_RATE_TT_DELAYED',
    'NET_MIGRATION_RATE_TT_DELAYED', 'EMPLOYMENT_TOOLTIP_DELAYED',
}
MIGRATION_RELIEF_NEW_KEYS = {
    'eon_migration_relief_category', 'eon_migration_relief_category_desc',
    'eon_migration_policy_paused', 'eon_migration_policy_regulated', 'eon_migration_policy_expanded',
    'eon_migration_admission_paused', 'eon_migration_admission_paused_desc',
    'eon_migration_admission_regulated', 'eon_migration_admission_regulated_desc',
    'eon_migration_admission_expanded', 'eon_migration_admission_expanded_desc',
    'eon_migration_expand_reception_capacity', 'eon_migration_expand_reception_capacity_desc',
    'eon_refugee_reception_modifier', 'eon_refugee_reception_modifier_tt',
    'eon_migration_population_flow_tt',
}


def approved_override_files(language):
    return {
        f'localisation/{language}/replace/eon_debt_bailout_replace_l_{language}.yml': BAILOUT_OVERRIDE_KEYS,
        f'localisation/{language}/replace/eon_debt_default_l_{language}.yml': DEFAULT_OVERRIDE_KEYS,
        f'localisation/{language}/replace/eon_uranium_l_{language}.yml': URANIUM_OVERRIDE_KEYS,
        f'localisation/{language}/replace/eon_migration_treaty_l_{language}.yml': MIGRATION_TREATY_OVERRIDE_KEYS | MIGRATION_TREATY_NEW_KEYS,
        f'localisation/{language}/replace/eon_migration_relief_l_{language}.yml': MIGRATION_RELIEF_OVERRIDE_KEYS | MIGRATION_RELIEF_NEW_KEYS,
    }


def approved_override_pairs(language):
    upstream = f'localisation/{language}/MD_money_l_{language}.yml'
    pairs = {}
    for provider, keys in approved_override_files(language).items():
        for key in keys:
            if key in MIGRATION_TREATY_NEW_KEYS | MIGRATION_RELIEF_NEW_KEYS:
                continue  # New IDs still require one provider, never two.
            original = (f'localisation/{language}/MDC_diplomatic_actions_l_{language}.yml'
                        if key in MIGRATION_TREATY_OVERRIDE_KEYS else
                        f'localisation/{language}/0_energy_l_{language}.yml'
                        if key in URANIUM_OVERRIDE_KEYS else upstream)
            pairs[key] = (original, provider)
    return pairs


def validate_override_files(language, file_keys, errors):
    for provider, expected in approved_override_files(language).items():
        if provider not in file_keys:
            errors.append(f'{language}: missing approved override file {provider}')
        elif file_keys[provider] != expected:
            errors.append(f'{language}: wrong approved override key set in {provider}: ' + repr({
                'missing': sorted(expected - file_keys[provider]),
                'unexpected': sorted(file_keys[provider] - expected),
            }))


def select_approved_override(language, key, rows, errors):
    """Choose the actual replace value only for an exact reviewed two-row pair."""
    expected = approved_override_pairs(language)[key]
    providers = [row[1] for row in rows]
    if len(rows) != 2 or sorted(providers) != sorted(expected):
        errors.append(f'{language}: invalid approved override providers for {key}: ' +
                      repr(providers) + '; expected exactly ' + repr(expected))
        return None
    return next(row for row in rows if row[1] == expected[1])


def is_eon(key):
    return isinstance(key, str) and key.startswith(('eon_', 'EON_'))


def walk(nodes):
    for key, operator, value in nodes:
        yield key, operator, value
        if isinstance(value, list):
            yield from walk(value)


def main():
    global ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT,
                        help='Mod source root; defaults to this checkout')
    ROOT = parser.parse_args().root.resolve()
    errors = []
    languages = {}
    owned_keys = {}
    sources = {}
    selected_overrides = {}
    eon_file_count = 0
    for language in ('english', 'russian'):
        index = defaultdict(list)
        own_keys = set()
        file_keys = {}
        approved_files = approved_override_files(language)
        upstream_files = {pair[0] for pair in approved_override_pairs(language).values()}
        for path in sorted((ROOT / 'localisation' / language).rglob('*.yml')):
            raw = path.read_bytes()
            text = raw.decode('utf-8-sig')
            relative = path.relative_to(ROOT).as_posix()
            own = path.name.startswith('eon_')
            file_keys[relative] = set()
            # Both providers are evidence even though replace is authoritative.
            if relative in upstream_files or relative in approved_files:
                sources[relative] = hashlib.sha256(raw).hexdigest()
            if own:
                eon_file_count += 1
                sources[relative] = hashlib.sha256(raw).hexdigest()
                if not raw.startswith(b'\xef\xbb\xbf'):
                    errors.append(f'{relative}: missing UTF-8 BOM')
                headers = [line.rstrip() for line in text.splitlines()
                           if re.fullmatch(r'l_\w+:[ \t]*', line)]
                if headers != ['l_' + language + ':']:
                    errors.append(f'{relative}: wrong or repeated language header')
            for number, line in enumerate(text.splitlines(), 1):
                match = KEY.fullmatch(line)
                if match:
                    key, value = match.groups()
                    index[key].append((value, relative, number))
                    file_keys[relative].add(key)
                    if own:
                        own_keys.add(key)
                elif (KEY_START.match(line) or (own and line.strip()
                      and not line.lstrip().startswith(('#', 'l_')))):
                    errors.append(f'{relative}:{number}: malformed localisation line')
        languages[language] = index
        owned_keys[language] = own_keys
        validate_override_files(language, file_keys, errors)
        selected_overrides[language] = {
            key: select_approved_override(language, key, index.get(key, []), errors)
            for key in approved_override_pairs(language)
        }

    required = defaultdict(set)
    action_ids = []
    decision_ids = []
    category_ids = []
    scripted_names = set()
    game_paths = set()

    def require(key, origin, any_key=False):
        if isinstance(key, str) and (any_key or is_eon(key)):
            required[key].add(origin)

    folders = ('common/scripted_diplomatic_actions', 'common/decisions',
               'common/decisions/categories', 'common/scripted_localisation',
               'common/scripted_effects', 'common/scripted_triggers', 'events')
    for folder in folders:
        pattern = '*.txt' if folder == 'common/scripted_diplomatic_actions' else 'eon_*.txt'
        for path in sorted((ROOT / folder).glob(pattern)):
            relative = path.relative_to(ROOT).as_posix()
            nodes = ast(path.read_bytes())
            game_paths.add(relative)
            sources[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            for key, operator, value in walk(nodes):
                if key in EXPLICIT and isinstance(value, str):
                    require(value, relative + ': ' + key,
                            any_key=folder == 'common/scripted_diplomatic_actions')
            if folder == 'common/scripted_diplomatic_actions':
                for wrapper, operator, actions in nodes:
                    if wrapper != 'scripted_diplomatic_actions':
                        continue
                    for ident, operator, body in actions:
                        if not isinstance(body, list):
                            continue
                        action_ids.append(ident)
                        require(ident.upper() + '_TITLE', relative + ': diplomacy button', any_key=True)
                        require(ident.upper() + '_ACTION_DESC', relative + ': diplomacy tooltip', any_key=True)
                        for field, operator, rules in body:
                            if field == 'ai_acceptance' and isinstance(rules, list):
                                for reason, operator, rule in rules:
                                    require(reason, relative + ': AI acceptance reason')
            elif folder == 'common/decisions':
                for category, operator, body in nodes:
                    if not isinstance(body, list):
                        continue
                    for ident, operator, decision in body:
                        if is_eon(ident) and isinstance(decision, list):
                            decision_ids.append(ident)
                            require(ident, relative + ': decision name')
                            require(ident + '_desc', relative + ': decision description')
            elif folder == 'common/decisions/categories':
                for ident, operator, body in nodes:
                    if is_eon(ident) and isinstance(body, list):
                        category_ids.append(ident)
                        require(ident, relative + ': category name')
                        require(ident + '_desc', relative + ': category description')
            elif folder == 'common/scripted_localisation':
                for kind, operator, body in nodes:
                    if kind == 'defined_text' and isinstance(body, list):
                        scripted_names.update(value for key, op, value in body
                                              if key == 'name' and isinstance(value, str))
            elif folder == 'events':
                for kind, operator, body in nodes:
                    if kind not in ('country_event', 'news_event') or not isinstance(body, list):
                        continue
                    for field, operator, option in body:
                        if field == 'option' and isinstance(option, list):
                            for key, operator, value in option:
                                if key == 'name':
                                    require(value, relative + ': event option')

    hidden_listener = private_listener_is_hidden(ROOT, sources, errors)
    private_labels_present = ((ROOT / PRIVATE_LISTENER).is_file()
                              or any(PRIVATE_BLANK_KEYS & set(index) for index in languages.values()))
    if private_labels_present:
        for key in PRIVATE_BLANK_KEYS:
            require(key, PRIVATE_LISTENER + ': retained hidden label', any_key=True)
        for language, index in languages.items():
            for key in PRIVATE_BLANK_KEYS:
                rows = index.get(key, [])
                if rows and (len(rows) != 1 or not intentional_private_blank(language, key, *rows[0][:2], hidden_listener)):
                    errors.append(f'{language}: intentional hidden label must be exactly empty in its sole approved provider: {key}')

    # Follow static aliases in every own localisation value, even if a future
    # action is not visible in the current campaign. Do not depend on EN fallback.
    alias_edges = 0
    checked_keys = 0
    scripted_references = 0
    resolved_samples = {}
    for language, index in languages.items():
        for key, origins in sorted(required.items()):
            if key not in index:
                errors.append(f'{language}: missing {key} ({sorted(origins)[0]})')
            else:
                selected = selected_overrides[language].get(key)
                rows = ([selected] if selected is not None else [] if key in selected_overrides[language] else index[key])
                for value, provider, number in rows:
                    if provider not in sources:
                        sources[provider] = hashlib.sha256((ROOT / provider).read_bytes()).hexdigest()
                    if ((not value.strip() or value.strip() == key)
                            and not intentional_private_blank(language, key, value, provider, hidden_listener)):
                        errors.append(f'{language}: empty or raw-code value for {key}')
        own_keys = sorted(owned_keys[language] | {key for key in index if is_eon(key)})
        for key in own_keys:
            rows = index[key]
            checked_keys += 1
            if key not in selected_overrides[language] and len(rows) != 1:
                errors.append(f'{language}: duplicate {key}: ' + ', '.join(r[1] for r in rows))

        def resolve(key, trail):
            nonlocal alias_edges
            if key in trail:
                errors.append(f'{language}: alias cycle: ' + ' -> '.join((*trail, key)))
                return ''
            if key not in index:
                errors.append(f'{language}: missing alias target {key}')
                return ''
            if key in selected_overrides[language]:
                selected = selected_overrides[language][key]
                if selected is None:
                    return ''  # Exact provider error was already recorded.
            else:
                selected = index[key][0]
            value, provider, number = selected
            if provider not in sources:
                sources[provider] = hashlib.sha256((ROOT / provider).read_bytes()).hexdigest()
            if (intentional_private_blank(language, key, value, provider, hidden_listener) and trail):
                errors.append(f'{language}: hidden label cannot be an alias target in visible text: {key}')
            if ((not value.strip() or value.strip() == key or RAW_KEY.fullmatch(value.strip())
                    or value.strip() in selected_overrides[language])
                    and not intentional_private_blank(language, key, value, provider, hidden_listener)):
                errors.append(f'{language}: empty or raw-code value for {key}')
            # Count and validate substitutions through the whole alias chain.
            # This is static text expansion, not the engine's scope formatter.
            def expand(match):
                nonlocal alias_edges
                alias_edges += 1
                return resolve(match[1], (*trail, key))
            return ALIAS.sub(expand, value)

        for key in own_keys:
            resolve(key, ())
        # Custom functions can be used by inherited windows as well as owned
        # text, e.g. [From.EON_GetInvestmentOfferBuilding]. Numeric [?...] scope
        # expressions are deliberately excluded from this function lookup.
        for key, rows in index.items():
            for value, provider, number in rows:
                for function in SCRIPTED.findall(value):
                    scripted_references += 1
                    if provider not in sources:
                        sources[provider] = hashlib.sha256((ROOT / provider).read_bytes()).hexdigest()
                    if function not in scripted_names:
                        errors.append(f'{language}: undefined scripted text {function} in {key}')
        resolved_samples[language] = {
            key: resolve(key, ()) for key in (
                'EON_OPEN_ECONOMIC_CONSULTATIONS_TITLE',
                'EON_WITHDRAW_CONSULTATION_REQUEST_TITLE',
                'EON_PROPOSE_DEFENSIVE_ALLIANCE_TITLE',
                'PROPOSE_ENERGY_AGREEMENT_REJECT_TT',
                'PROPOSE_MIGRANTS_AGREEMENT_ACTION_DESC',
                'additional_migrants_agreements_income_tt') if key in index
        }

    if owned_keys['english'] != owned_keys['russian']:
        errors.append('Own EN/RU localisation key sets differ: ' + repr({
            'english_only': sorted(owned_keys['english'] - owned_keys['russian']),
            'russian_only': sorted(owned_keys['russian'] - owned_keys['english']),
        }))

    report = {
        'checks_passed': not errors,
        'languages': ['english', 'russian'],
        'diplomatic_actions': len(action_ids),
        'decisions': len(decision_ids),
        'decision_categories': len(category_ids),
        'required_ui_keys': len(required),
        'eon_localisation_files': eon_file_count,
        'localised_keys_checked': checked_keys,
        'alias_edges_checked': alias_edges,
        'scripted_text_references_checked': scripted_references,
        'game_source_files': len(game_paths),
        'source_sha256': sources,
        'approved_overrides_per_language': {
            language: sum(row is not None for row in selected.values())
            for language, selected in selected_overrides.items()
        },
        'approved_override_providers': {
            language: {key: row[1] for key, row in selected.items() if row is not None}
            for language, selected in selected_overrides.items()
        },
        'reviewed_hidden_listener': hidden_listener,
        'intentional_blank_internal_keys': sorted(PRIVATE_BLANK_KEYS) if hidden_listener else [],
        'resolved_text_samples': resolved_samples,
        'errors': errors,
        'native_ui_rendering_proven': False,
        'proof_scope': 'all custom diplomatic action titles/descriptions and explicit text fields; EON decisions, events, tooltips, EN/RU syntax/BOM, duplicates and transitive aliases',
    }
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
