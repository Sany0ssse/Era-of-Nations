"""Prepare a prototype-only active upkeep observer, without launching the game.

The fixture seeds private reserve equipment, exercises current source helpers,
and observes four ordinary country on_weekly pulses. It never fabricates weekly
progress by invoking the helper once per frame or changing the campaign clock.
Current production disables this incomplete prototype. Preparing against that
source does not enable it: the active-cycle native assertions will fail by
design. Use a separately authorized, frozen test-only enabled clone for a new
active-cycle experiment; existing native83 receipts retain their old bindings.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('arsenal_probe_parser', ROOT/'tools/validation/diplomacy_package_03/_support.py')
p = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = p
spec.loader.exec_module(p)
NS = 'eon_private_upkeep'
MARKER = 'EON_PRIVATE_UPKEEP'
COUNTRIES = ('GER', 'FRA', 'RAJ')
FIELDS = {
    'total': 'eon_nuclear_arsenal_total', 'reserve': 'eon_nuclear_arsenal_reserve',
    'deployed': 'eon_nuclear_arsenal_deployed', 'cost': 'eon_nuclear_arsenal_weekly_cost',
    'expense': 'additional_expenses_rate', 'remaining': 'eon_nuclear_arsenal_recovery_remaining',
    'full_cost': NS+'_full_cost', 'full_expense': NS+'_full_expense',
    'treasury': 'treasury', 'treasury_before': NS+'_treasury_before',
    'base_expense': NS+'_base_expense', 'rate_before': NS+'_rate_before',
    'rate_after': NS+'_rate_after', 'gdp_pc': 'gdp_per_capita',
    'workforce_gdp': 'total_workforce_gdp_c_modifier_var',
    'mining': 'additional_expense_GER_subventions_mining',
    'agrar': 'additional_expense_GER_subventions_agrar',
    'income': 'additional_income_rate', 'income_before': NS+'_income_before',
    'latch': NS+'_observed_latch',
}
MONEY_REL = 'common/scripted_effects/00_money_system.txt'
WEEKLY_REL = 'common/on_actions/01_on_actions.txt'
HOOK = ('\t# Arsenal sustainment is a weekly cash expense; existing silo/bomber costs stay in military spending.\n'
        '\teon_nuclear_arsenal_refresh = yes\n'
        '\tadd_to_variable = { additional_expenses_rate = eon_nuclear_arsenal_weekly_cost }\n')


def expense_reference(raw):
    """Copy the exact production effect body, removing only the new hook."""
    source = raw.decode('utf-8')
    matches = list(re.finditer(r'^calculate_additional_expense_rate = \{', source, re.M))
    assert len(matches) == 1
    begin = matches[0].end()
    depth = 1
    for token in p.TOKEN.finditer(source, begin):
        if token[0] == '{': depth += 1
        elif token[0] == '}': depth -= 1
        if depth == 0:
            body = source[begin:token.start()]
            assert p.ast(body) == p.one(p.ast(raw), 'calculate_additional_expense_rate')
            assert body.count(HOOK) == 1, 'Changed arsenal expense hook'
            reference = body.replace(HOOK, '', 1)
            assert 'eon_nuclear_arsenal_' not in reference
            return reference
    raise AssertionError('Unclosed production expense effect')


def weekly_instrumentation(raw):
    """Private logs only; each insertion has an exact inverse for hash binding."""
    replacements = []
    fields = ('ROOT=[ROOT.GetTag] THIS=[THIS.GetTag] '
              f'weeks=[?{NS}_weeks] remaining=[?eon_nuclear_arsenal_recovery_remaining] '
              'cost=[?eon_nuclear_arsenal_weekly_cost] expense=[?additional_expenses_rate] treasury=[?treasury]')
    def line(stage):
        return (f'\t\t\tif = {{ limit = {{ has_country_flag = {NS}_active }} '
                f'set_temp_variable = {{ {NS}_observed_latch = 0 }} '
                'if = { limit = { has_country_flag = eon_nuclear_arsenal_weekly_processed } '
                f'set_temp_variable = {{ {NS}_observed_latch = 1 }} }} '
                f'log = "{MARKER} TRACE {stage} {fields} active=1 latch=[?{NS}_observed_latch]" }}\n').encode('utf-8')
    for needle, before, after in (
        (b'\t\t\teon_nuclear_arsenal_weekly = yes\n', 'production_before', 'production_after'),
        (b'\t\t\t# Update money system right before adjusting weekly value\n\t\t\tingame_update_setup = yes\n', None, 'production_budget'),
        (b'\t\t\tadd_to_variable = { treasury = treasury_rate_gain }\n', None, 'production_cash'),
    ):
        assert raw.count(needle) == 1, ('Ambiguous upstream weekly integration', needle)
        new = (line(before) if before else b'')+needle+(line(after) if after else b'')
        raw = raw.replace(needle, new, 1)
        replacements.append(dict(original=needle.decode('utf-8'), instrumented=new.decode('utf-8')))
    return raw, replacements


def restore_weekly_instrumentation(raw, replacements):
    for change in reversed(replacements):
        old, new = change['original'].encode('utf-8'), change['instrumented'].encode('utf-8')
        assert raw.count(new) == 1, 'Changed private weekly instrumentation'
        raw = raw.replace(new, old, 1)
    assert MARKER.encode('utf-8') not in raw
    return raw


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source, output, export_receipt=None, preparation_only=False, start_tag='NEP', start_delay_hours=56):
    source, output = source.resolve(), output.resolve()
    assert source.is_dir() and source != output
    assert not (output/'manifest.json').exists() and not (output/'launch-receipt.json').exists()
    if not preparation_only:
        assert source != ROOT.resolve() and source not in output.parents
        assert export_receipt and export_receipt.is_file()
    assert start_delay_hours >= 1 and start_tag not in COUNTRIES
    upkeep_source = p.ast((source/'common/scripted_effects/eon_nuclear_arsenal_effects.txt').read_bytes())
    trigger_source = p.ast((source/'common/scripted_triggers/eon_nuclear_arsenal_triggers.txt').read_bytes())
    enabled_gate = p.maybe(trigger_source, 'eon_nuclear_arsenal_enabled')
    source_disabled = enabled_gate == [('always', '=', 'no')]
    def walk(nodes):
        for node in nodes:
            yield node
            if isinstance(node[2], list): yield from walk(node[2])
    latch = [value for key, op, value in walk(p.one(upkeep_source, 'eon_nuclear_arsenal_weekly'))
             if key == 'set_country_flag' and isinstance(value, list)
             and p.maybe(value, 'flag') == 'eon_nuclear_arsenal_weekly_processed']
    assert len(latch) == 1 and dict((key, value) for key, op, value in latch[0]) == {
        'flag': 'eon_nuclear_arsenal_weekly_processed', 'days': '6', 'value': '1'}, 'V4 requires the native-grounded explicit value1 latch'
    assertions, observation_labels, observation_actors = [], [], {}

    def cv(variable, value, comparison='equals'):
        return f'check_variable = {{ var = {variable} value = {value} compare = {comparison} }} '

    def check(label, predicate):
        assert label not in assertions
        assertions.append(label)
        return (f'if = {{ limit = {{ {predicate} }} add_to_variable = {{ global.{NS}_passes = 1 }} '
                f'log = "{MARKER} PASS {label}" }} else = {{ add_to_variable = {{ global.{NS}_fails = 1 }} '
                f'log = "{MARKER} FAIL {label}" }} ')

    def observe(tag, phase):
        label = tag.lower()+'_'+phase
        assert label not in observation_labels
        observation_labels.append(label)
        observation_actors[label] = tag
        # Preserve enough precision to diagnose native fixed-point arithmetic.
        return (f'set_temp_variable = {{ {NS}_observed_ready = 0 }} '
                f'if = {{ limit = {{ eon_nuclear_arsenal_ready = yes }} set_temp_variable = {{ {NS}_observed_ready = 1 }} }} '
                f'set_temp_variable = {{ {NS}_observed_safety = 0 }} '
                f'if = {{ limit = {{ has_country_flag = eon_nuclear_arsenal_safety_mode }} set_temp_variable = {{ {NS}_observed_safety = 1 }} }} '
                f'set_temp_variable = {{ {NS}_observed_latch = 0 }} '
                'if = { limit = { has_country_flag = eon_nuclear_arsenal_weekly_processed } '
                f'set_temp_variable = {{ {NS}_observed_latch = 1 }} }} '
                f'log = "{MARKER} OBS {label} ROOT=[ROOT.GetTag] THIS=[THIS.GetTag] '
                f'step=[?{NS}_weeks] ready=[?{NS}_observed_ready] safety=[?{NS}_observed_safety] '+
                ' '.join(f'{name}=[?{variable}]' for name, variable in FIELDS.items())+'" ')

    close_delta = cv(NS+'_delta', -11, 'greater_than')+cv(NS+'_delta', 11, 'less_than')

    def capture_budget(tag, phase):
        # No full GDP/economy refresh between these three rate calculations.
        # The legacy expense effect also increments energy sales income; restore
        # that accumulator so this observer cannot change the cash-flow input.
        body = (f'set_variable = {{ {NS}_income_before = additional_income_rate }} '
                'calculate_additional_expense_rate = yes '
                f'set_variable = {{ {NS}_rate_before = additional_expenses_rate }} '
                f'{NS}_expense_reference = yes '
                f'set_variable = {{ {NS}_base_expense = additional_expenses_rate }} '
                'calculate_additional_expense_rate = yes '
                f'set_variable = {{ {NS}_rate_after = additional_expenses_rate }} '
                f'set_variable = {{ additional_income_rate = {NS}_income_before }} '
                f'set_variable = {{ {NS}_delta = {NS}_rate_after }} '
                f'subtract_from_variable = {{ {NS}_delta = {NS}_rate_before }} '
                f'multiply_variable = {{ {NS}_delta = 1000000 }} ')
        body += check(tag.lower()+'_'+phase+'_rate_repeatable', close_delta)
        body += (f'set_variable = {{ {NS}_delta = {NS}_rate_after }} '
                 f'subtract_from_variable = {{ {NS}_delta = {NS}_base_expense }} '
                 f'subtract_from_variable = {{ {NS}_delta = eon_nuclear_arsenal_weekly_cost }} '
                 f'multiply_variable = {{ {NS}_delta = 1000000 }} ')
        body += check(tag.lower()+'_'+phase+'_budget_once', close_delta)
        body += check(tag.lower()+'_'+phase+'_income_preserved', cv('additional_income_rate', NS+'_income_before'))
        return body

    events, startup, weekly = [], [], []
    for index, tag in enumerate(COUNTRIES, 1):
        setup = check(tag.lower()+'_initial_frame', f'tag = {tag} ROOT = {{ tag = {tag} }}')
        setup += ('set_technology = { ICBM1 = 1 NIRBM1 = 1 popup = no } '
                  'add_equipment_to_stockpile = { type = nuclear_missile_equipment_1 amount = 3 producer = THIS } '
                  'add_equipment_to_stockpile = { type = nuclear_ballistic_missile_equipment_1 amount = 5 producer = THIS } '
                  f'set_variable = {{ {NS}_treasury_before = treasury }} set_variable = {{ {NS}_weeks = 0 }} '
                  'eon_nuclear_arsenal_refresh = yes eon_nuclear_arsenal_refresh = yes ')
        setup += check(tag.lower()+'_refresh_free', cv('treasury', NS+'_treasury_before'))
        setup += check(tag.lower()+'_arsenal_positive', cv('eon_nuclear_arsenal_total', 0, 'greater_than'))
        setup += check(tag.lower()+'_default_full_ready', 'eon_nuclear_arsenal_ready = yes')
        setup += 'ingame_update_setup = yes '
        setup += capture_budget(tag, 'full_before')
        setup += (f'set_variable = {{ {NS}_full_cost = eon_nuclear_arsenal_weekly_cost }} '
                  f'set_variable = {{ {NS}_full_expense = additional_expenses_rate }} ')
        setup += observe(tag, 'full_before')
        setup += 'eon_nuclear_arsenal_set_safety = yes '
        setup += check(tag.lower()+'_safety_blocks', 'NOT = { eon_nuclear_arsenal_ready = yes }')
        setup += (f'set_variable = {{ {NS}_expected_cost = {NS}_full_cost }} '
                  f'multiply_variable = {{ {NS}_expected_cost = 0.35 }} '
                  f'set_variable = {{ {NS}_delta = eon_nuclear_arsenal_weekly_cost }} '
                  f'subtract_from_variable = {{ {NS}_delta = {NS}_expected_cost }} '
                  f'multiply_variable = {{ {NS}_delta = 1000000 }} ')
        setup += check(tag.lower()+'_safety_cost', close_delta)
        setup += capture_budget(tag, 'safety')
        setup += observe(tag, 'safety')
        setup += ('eon_nuclear_arsenal_resume_full = yes eon_nuclear_arsenal_resume_full = yes '
                  'eon_nuclear_arsenal_refresh = yes ingame_update_setup = yes eon_nuclear_arsenal_refresh = yes ')
        setup += check(tag.lower()+'_refresh_does_not_recover', cv('eon_nuclear_arsenal_recovery_remaining', 4)+
                       'NOT = { eon_nuclear_arsenal_ready = yes }')
        setup += capture_budget(tag, 'resume')
        setup += observe(tag, 'resume')
        setup += f'set_country_flag = {NS}_active set_variable = {{ {NS}_weeks = 0 }} '
        events.append(f'country_event = {{ id = {NS}.{index} hidden = yes is_triggered_only = yes immediate = {{ '
                      f'if = {{ limit = {{ NOT = {{ has_country_flag = {NS}_initial }} }} '
                      f'set_country_flag = {NS}_initial {setup} }} else = {{ log = "{MARKER} DUPLICATE_EVENT {tag}" }} }} }}')
        startup.append(f'{tag} = {{ country_event = {{ id = {NS}.{index} hours = {start_delay_hours} }} }} ')
        body = f'add_to_variable = {{ {NS}_weeks = 1 }} '
        for step in range(1, 5):
            frame = check(tag.lower()+f'_week_{step}_frame', f'tag = {tag}')
            frame += check(tag.lower()+f'_week_{step}_remaining', cv('eon_nuclear_arsenal_recovery_remaining', 4-step))
            expected_ready = 'eon_nuclear_arsenal_ready = yes' if step == 4 else 'NOT = { eon_nuclear_arsenal_ready = yes }'
            frame += check(tag.lower()+f'_week_{step}_readiness', expected_ready)
            frame += (f'set_variable = {{ {NS}_before_duplicate = eon_nuclear_arsenal_recovery_remaining }} '
                      'eon_nuclear_arsenal_weekly = yes ')
            frame += check(tag.lower()+f'_week_{step}_duplicate_blocked', cv('eon_nuclear_arsenal_recovery_remaining', NS+'_before_duplicate'))
            frame += capture_budget(tag, f'week_{step}')
            frame += observe(tag, f'week_{step}')
            if step == 4:
                frame += f'clr_country_flag = {NS}_active set_global_flag = {NS}_{tag}_done '
            body += f'if = {{ limit = {{ {cv(NS+"_weeks", step)} }} {frame} }} '
        weekly.append(f'if = {{ limit = {{ tag = {tag} has_country_flag = {NS}_active }} {body} }} ')
    weekly.append('if = { limit = { NOT = { has_global_flag = '+NS+'_finished } '+
                  ' '.join('has_global_flag = '+NS+'_'+tag+'_done' for tag in COUNTRIES)+' } '
                  'set_global_flag = '+NS+'_finished log = "'+MARKER+' END passes=[?global.'+NS+'_passes] fails=[?global.'+NS+'_fails]" } ')
    reference = expense_reference((source/MONEY_REL).read_bytes())
    instrumented, replacements = weekly_instrumentation((source/WEEKLY_REL).read_bytes())
    fixture = {
        'events/eon_private_upkeep_events.txt': 'add_namespace = '+NS+'\n'+'\n'.join(events)+'\n',
        'common/on_actions/zz_eon_private_upkeep.txt': (
            f'on_actions = {{ on_startup = {{ effect = {{ set_variable = {{ global.{NS}_passes = 0 }} '
            f'set_variable = {{ global.{NS}_fails = 0 }} log = "{MARKER} STARTUP native_nuclear_arsenal_upkeep" '+
            ''.join(startup)+'} } on_weekly = { effect = { '+''.join(weekly)+'} } }\n'),
        f'common/scripted_effects/{NS}_expense_reference.txt': f'{NS}_expense_reference = {{'+reference+'}\n',
        WEEKLY_REL: instrumented.decode('utf-8'),
    }
    output.mkdir(parents=True, exist_ok=True)
    for rel, content in fixture.items():
        p.ast(content)
        path = output/'mod'/rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode('utf-8'))
    dependencies = ('common/scripted_effects/eon_nuclear_arsenal_effects.txt',
                    'common/scripted_triggers/eon_nuclear_arsenal_triggers.txt',
                    'common/scripted_effects/00_money_system.txt', 'common/on_actions/01_on_actions.txt',
                    'common/units/equipment/MD_nuclear_missiles.txt',
                    'common/units/equipment/MD_ballistic_missiles.txt')
    docs = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation')
    manifest = {
        'schema': 1, 'kind': 'native_nuclear_arsenal_upkeep', 'fixture_version': 4,
        'marker': MARKER, 'source_root': str(source), 'fixture_root': str(output),
        'preparation_only': preparation_only, 'expected_native_start_tag': start_tag,
        'prototype_only': True, 'source_disabled_by_constant_gate': source_disabled,
        'active_cycle_acceptance_expected_with_this_source': not source_disabled,
        'expected_enabled_mods': ['mod/era_of_nations.mod'], 'observed_countries': list(COUNTRIES),
        'assertions': assertions, 'observation_labels': observation_labels,
        'expected_observation_actors': observation_actors,
        'observation_fields': ['step', 'ready', 'safety', *FIELDS],
        'source_sha256': {rel: sha(source/rel) for rel in dependencies},
        'fixture_sha256': {rel: sha(output/'mod'/rel) for rel in fixture},
        'builder_sha256': sha(Path(__file__)),
        'installed_documentation_root': str(docs),
        'installed_documentation_sha256': {rel: sha(docs/rel) for rel in
                ('effects_documentation.md', 'dynamic_variables_documentation.md', 'triggers_documentation.md')},
        'source_export_binding': None if not export_receipt else
                {'path': str(export_receipt.resolve()), 'sha256': sha(export_receipt)},
        'game_prices': {'fixed': 0.002, 'weapon': 0.00002, 'deployed_premium': 0.00004, 'safety_share': 0.35},
        'numeric_tolerance': 0.000011, 'weekly_interval_hours': 168,
        'monetary_comparison_scale': 1000000, 'budget_reference_mode': 'same_input_exact_hook_inverse',
        'expense_reference_body_sha256': hashlib.sha256(reference.encode('utf-8')).hexdigest(),
        'private_weekly_replacements': replacements,
        'weekly_trace_stages': ['production_before', 'production_after', 'production_budget', 'production_cash'],
        'weekly_latch_contract': {'flag': 'eon_nuclear_arsenal_weekly_processed', 'days': 6, 'value': 1},
        'limits': ['Private reserve equipment is seeded; this is not research, production or manual silo loading proof.',
                   'Four real country weekly callbacks establish scripted upkeep recovery, not weapon engineering or real-world certification.',
                   'Inventory counter interpretation requires separate positive physical missile calibration; native85/86 getters mismatch deployed nuclear equipment.',
                   'A disabled source intentionally fails active-cycle expectations; this builder never enables its gate.',
                   'No human raid UI, actual missile firing, save/load, ordinary autonomous AI or multiplayer proof.'],
    }
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source-root', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--export-receipt', type=Path)
    cli.add_argument('--prepare-only', action='store_true')
    cli.add_argument('--start-tag', default='NEP')
    cli.add_argument('--start-delay-hours', type=int, default=56)
    args = cli.parse_args()
    result = build(args.source_root, args.output, args.export_receipt, args.prepare_only, args.start_tag, args.start_delay_hours)
    print(json.dumps({'prepared': True, 'assertions': len(result['assertions']), 'native_game_launched': False,
                      'manifest': str(args.output/'manifest.json')}))
