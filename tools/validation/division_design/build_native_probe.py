"""Prepare a private division support compilation/deployment probe; never launch.

This tests loaded templates and country-scoped tutorial registration, not clicks,
the designer's rejection of invalid placements, battle outcomes or multiplayer.
"""
from pathlib import Path
import argparse, hashlib, json, sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ai_templates import parse

NS = 'eon_native_division_probe'
MARK = 'EON_DIVISION_NATIVE_V1'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def build(source, output, light, motor):
    assert not output.exists(), 'Preserve earlier receipts'
    events = []
    assertions = []
    fixtures = {}
    tags = ('NEP', 'GER', 'FRA', 'RAJ')
    def check(label, predicate):
        assertions.append(label)
        return ('if = { limit = { '+predicate+' } log = "'+MARK+' PASS '+label+'" '
                'add_to_variable = { global.'+NS+'_passes = 1 } } else = { '
                'log = "'+MARK+' FAIL '+label+'" add_to_variable = { global.'+NS+'_fails = 1 } } ')
    for i, tag in enumerate(tags, 1):
        body = check(tag+'_scope', 'tag = '+tag+' ROOT = { tag = '+tag+' }')
        body += check(tag+'_human_seen' if tag=='NEP' else tag+'_ai_not_seen',
                      ('has_country_flag = eon_division_design_tutorial_seen' if tag=='NEP'
                       else 'NOT = { has_country_flag = eon_division_design_tutorial_seen }'))
        for label, unit, support in [('foot', 'L_Inf_Bat', light), ('mobile', 'Mot_Inf_Bat', motor)]:
            name = NS+'_'+tag+'_'+label
            body += ('division_template = { name = "'+name+'" is_locked = yes '
                     'regiments = { '+''.join(unit+' = { x = 0 y = '+str(y)+' } ' for y in range(3))+'} '
                     'regimental_support = { '+support+' = { x = 0 y = 0 } } } ')
            body += check(tag+'_'+label+'_template', 'has_template = "'+name+'"')
            # In 1.19.3 this legacy template trigger misses regimental support
            # even when deployed battalion counters below see it. Record the
            # diagnostic, without pretending it proves attachment eligibility.
            body += ('if = { limit = { has_template_containing_unit = '+support+' } '
                     'log = "'+MARK+' OBS '+tag+'_'+label+'_legacy_contains=1" } else = { '
                     'log = "'+MARK+' OBS '+tag+'_'+label+'_legacy_contains=0" } ')
            # A private generated unit in its own country's territory, without equipment grants.
            body += ('capital_scope = { create_unit = { division = "name = '+name+' division_template = '+name+'" owner = '+tag+' } } ')
        body += ('country_event = { id = '+NS+'.'+str(i+10)+' hours = 2 } ')
        events.append('country_event = { id = '+NS+'.'+str(i)+' hidden = yes is_triggered_only = yes immediate = { '+body+'} }')
        later = check(tag+'_light_deployed', 'check_variable = { var = num_battalions_with_type@'+light+' value = 0 compare = greater_than }')
        later += check(tag+'_motor_deployed', 'check_variable = { var = num_battalions_with_type@'+motor+' value = 0 compare = greater_than }')
        later += check(tag+'_seen_persistent' if tag=='NEP' else tag+'_still_ai_no_popup',
                      ('has_country_flag = eon_division_design_tutorial_seen' if tag=='NEP'
                       else 'NOT = { has_country_flag = eon_division_design_tutorial_seen }'))
        later += 'set_global_flag = '+NS+'_'+tag+'_done '
        if tag == tags[-1]:
            later += ('if = { limit = { '+''.join('has_global_flag = '+NS+'_'+t+'_done ' for t in tags)+'} '
                      'log = "'+MARK+' END passes=[?global.'+NS+'_passes] fails=[?global.'+NS+'_fails]" } '
                      'else = { log = "'+MARK+' ABORT unfinished_countries" } ')
        events.append('country_event = { id = '+NS+'.'+str(i+10)+' hidden = yes is_triggered_only = yes immediate = { '+later+'} }')
    fixtures['events/'+NS+'.txt'] = 'add_namespace = '+NS+'\n'+'\n'.join(events)+'\n'
    # Probe-only dynamic getters need synchronized tokens. Production gameplay
    # does not use these getters or modify the existing enumeration/IDs.
    fixtures['common/synchronized_dynamic_tokens/'+NS+'.txt'] = light+'\n'+motor+'\n'
    fixtures['common/on_actions/'+NS+'.txt'] = (
        'on_actions = { on_startup = { effect = { log = "'+MARK+' STARTUP" '
        'set_variable = { global.'+NS+'_passes = 0 } set_variable = { global.'+NS+'_fails = 0 } '+
        ''.join(t+' = { country_event = { id = '+NS+'.'+str(i)+' hours = '+str(6+i)+' } } ' for i,t in enumerate(tags,1))+'} } }\n')
    deps = ('common/units/eon_regimental_support.txt', 'common/units/MD_land_units.txt',
            'common/unit_tags/00_categories.txt', 'common/technologies/infantry.txt',
            'common/ai_templates/MD_generic.txt', 'common/scripted_effects/00_AI_templates.txt',
            'common/defines/MD_defines.lua', 'common/technologies/artillery.txt', 'common/technologies/NSB_artillery.txt',
            'common/on_actions/eon_division_design_tutorial_on_actions.txt', 'events/eon_division_design_tutorial.txt',
            'interface/eon_division_design_tutorial.gfx', 'interface/divisiondesignerview.gui')
    output.mkdir(parents=True)
    for rel, text in fixtures.items():


        parse(text)
        path = output/'mod'/rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8', newline='\n')
    docs = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation')
    manifest = {'kind': 'native_division_design', 'schema': 1, 'marker': MARK, 'assertions': assertions,
                'source_root': str(source), 'expected_start_tag': 'NEP', 'countries': tags,
                'source_sha256': {rel: sha(source/rel) for rel in deps},
                'fixture_sha256': {rel: sha(output/'mod'/rel) for rel in fixtures},
                'documentation_sha256': {f: sha(docs/f) for f in ('effects_documentation.md','triggers_documentation.md','dynamic_variables_documentation.md')},
                'limits': ['Native scripted template registration and deployed support counters only.',
                           'OOB scripting can bypass designer eligibility; this does not test rejection of invalid GUI placements.',
                           'No rendered event clicks, equal-condition battle results, full campaign/save reload or multiplayer acceptance.']}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--light',required=True)
    p.add_argument('--motor',required=True)
    a=p.parse_args()
    result=build(a.source.resolve(),a.output.resolve(),a.light,a.motor)
    print(json.dumps({'prepared':True,'assertions':len(result['assertions']),'native_tested':False}))
