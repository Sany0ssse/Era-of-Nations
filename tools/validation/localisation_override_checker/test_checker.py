"""Run the REAL checker against exact approved locale copies and narrow mutants.

Only ignored temporary fixtures are written. Source localisation stays unchanged.
Replacement selection is checked through an actual transitive alias and the
checker's JSON receipt, not a copied localization-resolution implementation.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
CHECKER = ROOT / 'tools/validation/diplomacy_completion/check_localisation.py'
spec = importlib.util.spec_from_file_location('eon_locale_checker', CHECKER)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
SCRATCH = ROOT / '.local/debt-lifecycle-audit/localisation-override-checker/test-fixtures'
SCRATCH.mkdir(parents=True, exist_ok=True)
KEY = 'debt_default_pay_10_from_treasury'
BAILOUT = 'bankruptcy_seek_bailout_from_biggest_influencer_desc'
COMPLETE = 'debt_default_main_mission_complete_trigger'
REWARD = 'change_reactor_grade_material_effect_tt'
MIGRATION_TREATY = 'PROPOSE_MIGRANTS_AGREEMENT_ACTION_DESC'
MIGRATION_RELIEF = 'additional_migrants_agreements_income_tt'


def paths(language):
    return (f'localisation/{language}/MD_money_l_{language}.yml',
            f'localisation/{language}/replace/eon_debt_bailout_replace_l_{language}.yml',
            f'localisation/{language}/replace/eon_debt_default_l_{language}.yml')


def all_provider_paths(language):
    return sorted(set(c.approved_override_files(language)) |
                  {pair[0] for pair in c.approved_override_pairs(language).values()})


def create_fixture(folder):
    for language in ('english', 'russian'):
        for relative in all_provider_paths(language):
            target = folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())
        alias = folder / f'localisation/{language}/eon_alias_probe_l_{language}.yml'
        alias.write_bytes(('\ufeffl_' + language + ':\n' +
                          f' EON_OPEN_ECONOMIC_CONSULTATIONS_TITLE:0 "${KEY}$"\n' +
                          f' EON_WITHDRAW_CONSULTATION_REQUEST_TITLE:0 "${BAILOUT}$"\n' +
                          f' EON_PROPOSE_DEFENSIVE_ALLIANCE_TITLE:0 "${COMPLETE}$"\n' +
                          f' PROPOSE_ENERGY_AGREEMENT_REJECT_TT:0 "${REWARD}$"\n').encode('utf-8'))


def add_private_listener_fixture(folder):
    for relative in (c.PRIVATE_LISTENER, c.PRIVATE_SPRITES, c.PRIVATE_TEXTURE):
        target = folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    for language in ('english', 'russian'):
        relative = f'localisation/{language}/eon_cheat_hotkey_l_{language}.yml'
        target = folder / relative
        target.write_bytes((ROOT / relative).read_bytes())


def line_for(folder, relative, key):
    matches = [line for line in (folder / relative).read_text(encoding='utf-8-sig').splitlines()
               if (match := c.KEY.fullmatch(line)) and match[1] == key]
    assert len(matches) == 1
    return matches[0]


def replace_line(folder, relative, key, replacement):
    target = folder / relative
    raw = target.read_bytes()
    previous = line_for(folder, relative, key).encode('utf-8')
    assert raw.count(previous) == 1
    target.write_bytes(raw.replace(previous, replacement.encode('utf-8'), 1))


def run_case(label, mutate=None, error_marker=None):
    with tempfile.TemporaryDirectory(prefix='case_', dir=SCRATCH) as location:
        folder = Path(location).resolve()
        # Verify the exact resolved cleanup target before TemporaryDirectory's
        # recursive cleanup; it must stay inside this named ignored workspace.
        assert folder.parent == SCRATCH.resolve() and folder != SCRATCH.resolve()
        create_fixture(folder)
        if mutate:
            mutate(folder)
        completed = subprocess.run([sys.executable, str(CHECKER), '--root', str(folder)],
                                   capture_output=True, text=True, encoding='utf-8')
        assert completed.stdout, (label, completed.stderr)
        report = json.loads(completed.stdout)
        if error_marker:
            assert completed.returncode == 1 and not report['checks_passed'], label
            assert any(error_marker in error for error in report['errors']), (label, report['errors'])
            return {'case': label, 'expected_rejection': True,
                    'matching_errors': [error for error in report['errors'] if error_marker in error]}
        assert completed.returncode == 0 and report['checks_passed'], (label, report['errors'])
        assert report['approved_overrides_per_language'] == {'english': 49, 'russian': 49}
        for language in ('english', 'russian'):
            upstream, bailout, default = paths(language)
            for relative in all_provider_paths(language):
                assert report['source_sha256'][relative] == hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            for sample, key, provider in (
                ('EON_OPEN_ECONOMIC_CONSULTATIONS_TITLE', KEY, default),
                ('EON_WITHDRAW_CONSULTATION_REQUEST_TITLE', BAILOUT, bailout),
                ('EON_PROPOSE_DEFENSIVE_ALLIANCE_TITLE', COMPLETE, default),
                ('PROPOSE_ENERGY_AGREEMENT_REJECT_TT', REWARD, f'localisation/{language}/replace/eon_uranium_l_{language}.yml'),
                (MIGRATION_TREATY, MIGRATION_TREATY, f'localisation/{language}/replace/eon_migration_treaty_l_{language}.yml'),
                (MIGRATION_RELIEF, MIGRATION_RELIEF, f'localisation/{language}/replace/eon_migration_relief_l_{language}.yml'),
            ):
                replacement = c.KEY.fullmatch(line_for(folder, provider, key))[2]
                original_provider = c.approved_override_pairs(language)[key][0]
                original = c.KEY.fullmatch(line_for(folder, original_provider, key))[2]
                assert replacement != original, 'The alias probe must distinguish old and replacement values'
                assert report['resolved_text_samples'][language][sample] == replacement
                assert report['approved_override_providers'][language][key] == provider
        return {'case': label, 'pass': True, 'actual_alias_resolution': True,
                'both_provider_hashes_per_language': True}


def new_provider(folder, filename, key=KEY):
    target = folder / 'localisation/english' / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(('\ufeffl_english:\n ' + key + ':0 "Third value"\n').encode('utf-8'))


def main():
    before = {relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
              for language in ('english', 'russian') for relative in all_provider_paths(language)}
    assert len(c.BAILOUT_OVERRIDE_KEYS) == 8
    assert c.DEFAULT_OVERRIDE_KEYS == {
        f'debt_default_pay_{amount}_from_treasury{suffix}'
        for amount in ('10','50') for suffix in ('','_desc','_tt')
    } | {'debt_default_pay_from_treasury_trigger_tooltip', COMPLETE,
         'bankruptcy_default_on_debts_desc', 'bankruptcy_default_on_debts_tt',
         'bankruptcy.13.a', 'bankruptcy.13.b', 'bankruptcy.14.a',
     'debt_default_sell_civilian_factories_desc',
     'debt_default_dismantle_military_factories_desc',
     'debt_default_scrap_dockyard_desc',
     'debt_default_cut_down_government_services_desc'}
    assert not c.BAILOUT_OVERRIDE_KEYS & c.DEFAULT_OVERRIDE_KEYS
    assert c.approved_override_pairs('english').keys() == c.approved_override_pairs('russian').keys()
    assert len(c.MIGRATION_TREATY_OVERRIDE_KEYS) == 14
    assert len(c.MIGRATION_RELIEF_OVERRIDE_KEYS) == 4
    assert not (c.MIGRATION_TREATY_NEW_KEYS | c.MIGRATION_RELIEF_NEW_KEYS) & c.approved_override_pairs('english').keys()
    controls = [run_case('exact_two_providers_use_replace_aliases')]
    uranium = 'localisation/english/replace/eon_uranium_l_english.yml'
    controls.append(run_case('missing_kg_reward_override',
                             lambda f: replace_line(f, uranium, REWARD, ''), 'wrong approved override key set'))
    controls.append(run_case('kg_reward_third_provider',
                             lambda f: new_provider(f, 'eon_third_kg_reward_l_english.yml', REWARD),
                             'invalid approved override providers'))
    upstream, bailout, default = paths('english')
    controls.append(run_case('missing_override_file', lambda f: (f / default).unlink(), 'missing approved override file'))
    controls.append(run_case('third_provider', lambda f: new_provider(f, 'unapproved_l_english.yml'), 'invalid approved override providers'))
    controls.append(run_case('wrong_replace_provider',
                             lambda f: (f / default).rename(f / 'localisation/english/replace/eon_wrong_provider_l_english.yml'),
                             'invalid approved override providers'))
    controls.append(run_case('wrong_upstream_provider',
                             lambda f: (f / upstream).rename(f / 'localisation/english/MD_money_copy_l_english.yml'),
                             'invalid approved override providers'))
    controls.append(run_case('missing_override_key',
                             lambda f: replace_line(f, default, KEY, ''), 'wrong approved override key set'))
    controls.append(run_case('missing_completion_override_key',
                             lambda f: replace_line(f, default, COMPLETE, ''), 'wrong approved override key set'))
    controls.append(run_case('completion_third_provider',
                             lambda f: new_provider(f, 'eon_third_completion_l_english.yml', COMPLETE),
                             'invalid approved override providers'))
    controls.append(run_case('missing_constructor_terms_override',
                             lambda f: replace_line(f, default, 'bankruptcy_default_on_debts_tt', ''),
                             'wrong approved override key set'))
    controls.append(run_case('legacy_option_third_provider',
                             lambda f: new_provider(f, 'eon_third_legacy_option_l_english.yml', 'bankruptcy.13.a'),
                             'invalid approved override providers'))
    controls.append(run_case('missing_asset_description_override',
                             lambda f: replace_line(f, default, 'debt_default_cut_down_government_services_desc', ''),
                             'wrong approved override key set'))
    controls.append(run_case('asset_description_third_provider',
                             lambda f: new_provider(f, 'eon_third_asset_l_english.yml', 'debt_default_scrap_dockyard_desc'),
                             'invalid approved override providers'))
    controls.append(run_case('missing_upstream_key',
                             lambda f: replace_line(f, upstream, KEY, ''), 'invalid approved override providers'))
    controls.append(run_case('unexpected_override_key',
                             lambda f: replace_line(f, default, KEY, line_for(f, default, KEY) + '\n unexpected_old_key:0 "Other"'),
                             'wrong approved override key set'))
    controls.append(run_case('duplicate_replace_row',
                             lambda f: replace_line(f, default, KEY, line_for(f, default, KEY) + '\n' + line_for(f, default, KEY)),
                             'invalid approved override providers'))
    controls.append(run_case('raw_override_value',
                             lambda f: replace_line(f, default, KEY, f' {KEY}:0 "{KEY}"'), 'raw-code value'))
    controls.append(run_case('raw_other_approved_key_value',
                             lambda f: replace_line(f, default, KEY, f' {KEY}:0 "debt_default_pay_50_from_treasury"'),
                             'raw-code value'))
    controls.append(run_case('missing_override_alias_target',
                             lambda f: replace_line(f, default, KEY, f' {KEY}:0 "$EON_MISSING_TARGET$"'), 'missing alias target'))
    controls.append(run_case('override_alias_cycle',
                             lambda f: replace_line(f, default, KEY, f' {KEY}:0 "${KEY}$"'), 'alias cycle'))
    controls.append(run_case('ordinary_duplicate_still_rejected',
                             lambda f: new_provider(f, 'eon_other_alias_l_english.yml', 'EON_OPEN_ECONOMIC_CONSULTATIONS_TITLE'),
                             'duplicate EON_OPEN_ECONOMIC_CONSULTATIONS_TITLE'))
    treaty = 'localisation/english/replace/eon_migration_treaty_l_english.yml'
    relief = 'localisation/english/replace/eon_migration_relief_l_english.yml'
    migration_upstream = 'localisation/english/MDC_diplomatic_actions_l_english.yml'
    controls.append(run_case('migration_treaty_missing_legacy_override',
                             lambda f: replace_line(f, treaty, MIGRATION_TREATY, ''),
                             'wrong approved override key set'))
    controls.append(run_case('migration_relief_missing_legacy_override',
                             lambda f: replace_line(f, relief, MIGRATION_RELIEF, ''),
                             'wrong approved override key set'))
    controls.append(run_case('migration_treaty_third_legacy_provider',
                             lambda f: new_provider(f, 'eon_third_migration_treaty_l_english.yml', MIGRATION_TREATY),
                             'invalid approved override providers'))
    controls.append(run_case('migration_relief_third_legacy_provider',
                             lambda f: new_provider(f, 'eon_third_migration_relief_l_english.yml', MIGRATION_RELIEF),
                             'invalid approved override providers'))
    controls.append(run_case('migration_treaty_wrong_upstream_file',
                             lambda f: (f / migration_upstream).rename(f / 'localisation/english/MDC_diplomatic_actions_copy_l_english.yml'),
                             'invalid approved override providers'))
    controls.append(run_case('migration_relief_wrong_replace_file',
                             lambda f: (f / relief).rename(f / 'localisation/english/replace/eon_wrong_migration_relief_l_english.yml'),
                             'invalid approved override providers'))
    controls.append(run_case('migration_treaty_new_key_duplicate_still_rejected',
                             lambda f: new_provider(f, 'eon_third_migration_new_l_english.yml', 'eon_migration_treaty_offer_available_tt'),
                             'duplicate eon_migration_treaty_offer_available_tt'))
    controls.append(run_case('migration_relief_new_key_duplicate_still_rejected',
                             lambda f: new_provider(f, 'eon_third_reception_new_l_english.yml', 'eon_migration_relief_category'),
                             'duplicate eon_migration_relief_category'))
    controls.append(run_case('migration_treaty_missing_required_new_key',
                             lambda f: replace_line(f, treaty, 'eon_migration_treaty_offer_available_tt', ''),
                             'wrong approved override key set'))
    controls.append(run_case('migration_relief_unexpected_key_still_rejected',
                             lambda f: replace_line(f, relief, MIGRATION_RELIEF,
                                                    line_for(f, relief, MIGRATION_RELIEF) + '\n unreviewed_legacy_key:0 "Other"'),
                             'wrong approved override key set'))
    controls.append(run_case('migration_treaty_alias_cycle',
                             lambda f: replace_line(f, treaty, MIGRATION_TREATY, f' {MIGRATION_TREATY}:0 "${MIGRATION_TREATY}$"'),
                             'alias cycle'))
    controls.append(run_case('approved_hidden_listener_empty_labels', add_private_listener_fixture))
    for language in ('english', 'russian'):
        relative = f'localisation/{language}/eon_cheat_hotkey_l_{language}.yml'
        for key in sorted(c.PRIVATE_BLANK_KEYS):
            def missing_private(f, relative=relative, key=key):
                add_private_listener_fixture(f)
                replace_line(f, relative, key, '')
            controls.append(run_case('missing_private_key_' + language + '_' + key,
                                     missing_private, 'missing ' + key))
            def nonempty_private(f, relative=relative, key=key):
                add_private_listener_fixture(f)
                replace_line(f, relative, key, f' {key}:0 "Not hidden"')
            controls.append(run_case('nonempty_private_key_' + language + '_' + key,
                                     nonempty_private, 'intentional hidden label must be exactly empty'))
    def blank_visible_decision(f):
        add_private_listener_fixture(f)
        target = f / 'common/decisions/eon_visible_blank_probe.txt'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('eon_probe_category = { eon_visible_blank_probe = { } }', encoding='utf-8')
        for language in ('english', 'russian'):
            new_provider(f, 'eon_visible_probe_l_english.yml', 'eon_visible_blank_probe') if language == 'english' else None
        relative = 'localisation/english/eon_visible_probe_l_english.yml'
        replace_line(f, relative, 'eon_visible_blank_probe', ' eon_visible_blank_probe:0 ""')
    controls.append(run_case('empty_visible_decision_still_rejected', blank_visible_decision,
                             'empty or raw-code value for eon_visible_blank_probe'))
    def hidden_alias(f):
        add_private_listener_fixture(f)
        new_provider(f, 'eon_hidden_alias_probe_l_english.yml', 'EON_VISIBLE_ALIAS_PROBE')
        relative = 'localisation/english/eon_hidden_alias_probe_l_english.yml'
        replace_line(f, relative, 'EON_VISIBLE_ALIAS_PROBE', ' EON_VISIBLE_ALIAS_PROBE:0 "$EON_CHEAT_HOTKEY_TT$"')
    controls.append(run_case('hidden_label_cannot_hide_visible_alias', hidden_alias,
                             'hidden label cannot be an alias target'))
    def changed_texture(f):
        add_private_listener_fixture(f)
        target = f / c.PRIVATE_TEXTURE
        raw = bytearray(target.read_bytes())
        raw[-1] ^= 1
        target.write_bytes(raw)
    controls.append(run_case('changed_listener_texture_rejected', changed_texture,
                             'require the reviewed hidden listener'))
    def visible_listener(f):
        add_private_listener_fixture(f)
        target = f / c.PRIVATE_LISTENER
        raw = target.read_bytes()
        assert raw.count(b'buttonText = ""') == 1
        target.write_bytes(raw.replace(b'buttonText = ""', b'buttonText = "Visible label"', 1))
    controls.append(run_case('visible_listener_label_rejected', visible_listener,
                             'require the reviewed hidden listener'))
    after = {relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() for relative in before}
    assert after == before, 'Production localization changed during checker tests'
    print(json.dumps({'checks_passed': True, 'baseline_actual_alias_case': 1, 'hidden_listener_positive_case': 1,
                      'bounded_invalid_cases_rejected': len(controls) - 2,
                      'controls': controls, 'production_locale_sha256': after,
                      'checker_sha256': hashlib.sha256(CHECKER.read_bytes()).hexdigest(),
                      'test_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      'native_ui_rendering_proven': False}, indent=2))


if __name__ == '__main__':
    main()
