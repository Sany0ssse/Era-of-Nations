"""Prepare a private no-GoT native history observer; never launch the game.

The probe observes actual source startup grants and evaluates the frozen source
production predicates natively. It does not claim that adding a stockpile or a
forced production line establishes ordinary equipment production availability.
"""
from pathlib import Path
import argparse
import hashlib
import json

from generate_non_got_history import ACTION, DESTINATION, EFFECT, FLAG, records, render
from test_research import ROOT, ast, get

NS = 'eon_private_non_got_missile_probe'
MARKER = 'EON_PRIVATE_NON_GOT_MISSILE_PROBE'
COUNTRIES = ('USA', 'GER', 'BRA', 'UKR')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clause(nodes):
    return ' '.join(f'{key} {op} {{ {clause(value)} }}' if isinstance(value, list)
                    else f'{key} {op} {value}' for key, op, value in nodes)


def build(source, output, export_receipt=None, preparation_only=False, start_tag='NEP'):
    source, output = source.resolve(), output.resolve()
    assert source.is_dir() and source != output
    assert not (output / 'manifest.json').exists() and not (output / 'launch-receipt.json').exists()
    if not preparation_only:
        assert source != ROOT.resolve() and source not in output.parents
        assert export_receipt and export_receipt.is_file()
    rows = records(source)
    assert (source / DESTINATION).read_text(encoding='utf-8-sig') == render(rows)
    selected = {row['tag']: row for row in rows if row['tag'] in COUNTRIES}
    assert set(selected) == set(COUNTRIES)
    equipment = {key: value for key, _, value in get(ast(
        (source / 'common/units/equipment/MD_guided_missiles.txt').read_text(encoding='utf-8-sig')), 'equipments')}
    assertions, fixture = [], {}

    def check(label, predicate):
        assert label not in assertions
        assertions.append(label)
        return ('if = { limit = { '+predicate+' } add_to_variable = { global.'+NS+'_passes = 1 } '
                'log = "'+MARKER+' PASS '+label+'" } else = { add_to_variable = { global.'+NS+'_fails = 1 } '
                'log = "'+MARKER+' FAIL '+label+'" } ')

    def cv(var, value):
        return f'check_variable = {{ var = {var} value = {value} compare = equals }} '

    initial = check('observer_initial_frame', f'tag = {start_tag} ROOT = {{ tag = {start_tag} }}')
    initial += check('got_disabled_in_native_engine', 'NOT = { has_dlc = "Gotterdammerung" }')
    initial += check('initial_date_within_adapter_window', 'date < 2000.1.2')
    for tag in COUNTRIES:
        row = selected[tag]
        body = check(tag.lower()+'_country_frame', f'tag = {tag} exists = yes ROOT = {{ tag = {start_tag} }}')
        body += check(tag.lower()+'_source_adapter_initialized', f'has_country_flag = {FLAG}')
        body += check(tag.lower()+'_missile_project_completed', 'is_special_project_completed = sp:sp_missile_project_non_got')
        for tech in row['techs'] + row['hidden']:
            body += check(tag.lower()+'_source_tech_'+tech.lower(), 'has_tech = '+tech)
        body += check(tag.lower()+'_nuclear_tree_not_granted', 'NOT = { has_tech = ICBM1 } NOT = { has_tech = NIRBM1 }')
        if row['launchers'] is not None:
            body += check(tag.lower()+'_absolute_source_launcher_counter', cv('num_launchers_set', row['launchers']))
        if 'GLCM_non_got' in row['techs']:
            for model in range(0, 9):
                guard = get(equipment[f'guided_missile_equipment_{model}'], 'can_be_produced')
                expected = 'GLCM_non_got' if model == 0 else f'GLCM{model}_non_got'
                text = clause(guard)
                if expected not in row['techs']:
                    text = 'NOT = { '+text+' }'
                body += check(tag.lower()+f'_actual_source_production_guard_glcm{model}', text)
        else:
            body += check(tag.lower()+'_no_unsupported_glcm_grants', 'NOT = { has_tech = GLCM_non_got }')
        body += f'set_variable = {{ {NS}_baseline_launchers = num_launchers_set }} '
        body += ('log = "'+MARKER+' OBS '+tag.lower()+'_initial ROOT=[ROOT.GetTag] THIS=[THIS.GetTag] '
                 'launchers=[?num_launchers_set]" ')
        initial += tag+' = { '+body+' } '
    initial += 'every_country = { '+EFFECT+' = yes } '
    for tag in COUNTRIES:
        initial += tag+' = { '+check(tag.lower()+'_repeat_initialization_no_additive_launcher',
                                    cv('num_launchers_set', NS+'_baseline_launchers'))+' } '
    # Native event scheduling can run the first hour inclusively. An extra
    # scheduled hour preserves at least 48 hours between observed timestamps.
    initial += 'country_event = { id = '+NS+'.2 hours = 49 } '
    later = check('observer_later_frame', f'tag = {start_tag} ROOT = {{ tag = {start_tag} }}')
    later += check('later_date_outside_adapter_window', 'NOT = { date < 2000.1.2 }')
    # Clear only the private fixture's initialization marker to expose the date
    # gate. No source history, real save, research or arsenal is modified.
    later += 'GER = { clr_country_flag = '+FLAG+' '+EFFECT+' = yes } '
    later += 'GER = { '+check('ger_after_date_window_not_reinitialized', 'NOT = { has_country_flag = '+FLAG+' }')+' } '
    later += ('log = "'+MARKER+' OBS observer_later ROOT=[ROOT.GetTag] THIS=[THIS.GetTag] launchers=[?num_launchers_set]" '
              'log = "'+MARKER+' END passes=[?global.'+NS+'_passes] fails=[?global.'+NS+'_fails]" '
              'set_global_flag = '+NS+'_finished ')
    events = []
    for number, body in ((1, initial), (2, later)):
        events.append('country_event = { id = '+NS+'.'+str(number)+' hidden = yes is_triggered_only = yes immediate = { '
                      'if = { limit = { NOT = { has_global_flag = '+NS+'_event_'+str(number)+' } } '
                      'set_global_flag = '+NS+'_event_'+str(number)+' '+body+
                      '} else = { log = "'+MARKER+' DUPLICATE_EVENT '+str(number)+'" } } }')
    fixture['events/'+NS+'_events.txt'] = 'add_namespace = '+NS+'\n'+'\n'.join(events)+'\n'
    fixture['common/on_actions/'+NS+'_on_actions.txt'] = (
        'on_actions = { on_startup = { effect = { if = { limit = { NOT = { has_global_flag = '+NS+'_booted } } '
        'set_global_flag = '+NS+'_booted set_variable = { global.'+NS+'_passes = 0 } set_variable = { global.'+NS+'_fails = 0 } '
        'log = "'+MARKER+' STARTUP native_no_got_missile_history" '+start_tag+' = { country_event = { id = '+NS+'.1 hours = 1 } } } } } }\n')
    output.mkdir(parents=True, exist_ok=True)
    for rel, text in fixture.items():
        ast(text)
        path = output / 'mod' / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode('utf-8'))
    deps = [DESTINATION, ACTION, 'common/technologies/non_got_missiles.txt', 'common/script_enums.txt',
            'common/units/equipment/MD_guided_missiles.txt', 'common/special_projects/projects/missile_projects.txt',
            *[row['source'] for row in rows]]
    manifest = dict(schema=1, kind='native_no_got_missile_history', marker=MARKER,
                    source_root=str(source), fixture_root=str(output), preparation_only=preparation_only,
                    expected_native_start_tag=start_tag, expected_enabled_mods=['mod/era_of_nations.mod'],
                    assertions=assertions, observed_countries=list(COUNTRIES), history_rows=selected,
                    source_country_count=len(rows), source_glcm_country_count=sum('GLCM_non_got' in row['techs'] for row in rows),
                    source_sha256={rel: sha(source / rel) for rel in deps},
                    fixture_sha256={rel: sha(output / 'mod' / rel) for rel in fixture},
                    builder_sha256=sha(Path(__file__)), minimum_total_native_hours=48,
                    source_export_binding=None if not export_receipt else dict(path=str(export_receipt.resolve()), sha256=sha(export_receipt)),
                    limits=['Four representative native countries; 28 configurations have source binding, not 28 native runs.',
                            'Production predicates are evaluated from frozen source; actual production UI and ordinary factory output are unverified.',
                            'No native raid preparation, firing, launcher GUI, save/load or multiplayer proof.',
                            'The later date gate is a fresh private campaign check, not a save-file edit.'])
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source-root', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--export-receipt', type=Path)
    cli.add_argument('--prepare-only', action='store_true')
    cli.add_argument('--start-tag', default='NEP')
    args = cli.parse_args()
    result = build(args.source_root, args.output, args.export_receipt, args.prepare_only, args.start_tag)
    print(json.dumps(dict(prepared=True, assertions=len(result['assertions']), native_tested=False,
                          manifest=str(args.output / 'manifest.json'))))
