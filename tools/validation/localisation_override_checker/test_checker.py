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


def paths(language):
    return (f'localisation/{language}/MD_money_l_{language}.yml',
            f'localisation/{language}/replace/eon_debt_bailout_replace_l_{language}.yml',
            f'localisation/{language}/replace/eon_debt_default_l_{language}.yml')


def create_fixture(folder):
    for language in ('english', 'russian'):
        for relative in paths(language) + (f'localisation/{language}/0_energy_l_{language}.yml', f'localisation/{language}/replace/eon_uranium_l_{language}.yml'):
            target = folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())
        alias = folder / f'localisation/{language}/eon_alias_probe_l_{language}.yml'
        alias.write_bytes(('\ufeffl_' + language + ':\n' +
                          f' EON_OPEN_ECONOMIC_CONSULTATIONS_TITLE:0 "${KEY}$"\n' +
                          f' EON_WITHDRAW_CONSULTATION_REQUEST_TITLE:0 "${BAILOUT}$"\n' +
                          f' EON_PROPOSE_DEFENSIVE_ALLIANCE_TITLE:0 "${COMPLETE}$"\n' +
                          f' PROPOSE_ENERGY_AGREEMENT_REJECT_TT:0 "${REWARD}$"\n').encode('utf-8'))


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
        assert report['approved_overrides_per_language'] == {'english': 31, 'russian': 31}
        for language in ('english', 'russian'):
            upstream, bailout, default = paths(language)
            for relative in (upstream, bailout, default):
                assert report['source_sha256'][relative] == hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            for sample, key, provider in (
                ('EON_OPEN_ECONOMIC_CONSULTATIONS_TITLE', KEY, default),
                ('EON_WITHDRAW_CONSULTATION_REQUEST_TITLE', BAILOUT, bailout),
                ('EON_PROPOSE_DEFENSIVE_ALLIANCE_TITLE', COMPLETE, default),
                ('PROPOSE_ENERGY_AGREEMENT_REJECT_TT', REWARD, f'localisation/{language}/replace/eon_uranium_l_{language}.yml'),
            ):
                replacement = c.KEY.fullmatch(line_for(folder, provider, key))[2]
                original_provider = f'localisation/{language}/0_energy_l_{language}.yml' if key == REWARD else upstream
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
              for language in ('english', 'russian') for relative in paths(language)}
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
    after = {relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() for relative in before}
    assert after == before, 'Production localization changed during checker tests'
    print(json.dumps({'checks_passed': True, 'baseline_actual_alias_case': 1,
                      'bounded_invalid_cases_rejected': len(controls) - 1,
                      'controls': controls, 'production_locale_sha256': after,
                      'checker_sha256': hashlib.sha256(CHECKER.read_bytes()).hexdigest(),
                      'test_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      'native_ui_rendering_proven': False}, indent=2))


if __name__ == '__main__':
    main()
