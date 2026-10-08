"""Check real source boundaries and native API documentation, not a byte journal."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from _model import ROOT, ast, one, variable_comparison

BASE = 'c1420b108dee2d129018951c9ba73c1f6bfc4360'

def original(path):
    return subprocess.check_output(['git', 'show', BASE+':'+path], cwd=ROOT)

def native_comparison_repairs(text, path):
    """The exact three inherited edits authorized by native probe 02.

    Compare real baseline source directly after these literal syntax repairs;
    this is not a mutation journal or normalization of arbitrary source changes.
    """
    replacements = {
        'common/scripted_effects/00_investment_scripted_effects.txt': [
            ('check_variable = { int_investments >= project_monetary_cost^project }',
             'check_variable = { var = int_investments value = project_monetary_cost^project compare = greater_than_or_equals }')],
        'common/scripted_triggers/eon_investment_project_triggers.txt': [
            ('check_variable = { treasury >= eon_investment_offer_cost }',
             'check_variable = { var = treasury value = eon_investment_offer_cost compare = greater_than_or_equals }'),
            ('check_variable = { treasury >= PREV.eon_investment_offer_cofunding }',
             'check_variable = { var = treasury value = PREV.eon_investment_offer_cofunding compare = greater_than_or_equals }')],
    }
    for before, after in replacements.get(path, []):
        assert text.count(before) == 1, (path, before)
        text = text.replace(before, after, 1)
    return text

def locate(text, name, start=0):
    match = re.search(r'(?m)^\s*'+re.escape(name)+r' = \{', text[start:])
    assert match, name
    a = start+match.start()
    brace = text.index('{', a); depth=0; quote=False; comment=False
    for b in range(brace, len(text)):
        char=text[b]
        if char == '\n': comment=False
        if comment: continue
        if char == '"': quote=not quote
        if quote: continue
        if char == '#': comment=True; continue
        if char == '{': depth+=1
        elif char == '}':
            depth-=1
            if not depth: return a, b+1, text[a:b+1]
    raise AssertionError(name)

existing = [
    'common/scripted_effects/00_investment_scripted_effects.txt',
    'common/scripted_effects/eon_investment_project_effects.txt',
    'common/scripted_triggers/eon_investment_project_triggers.txt',
    'common/scripted_guis/01_investment_scripted_gui.txt',
]
for path in existing:
    old=original(path); current=(ROOT/path).read_bytes()
    assert old.startswith(b'\xef\xbb\xbf') == current.startswith(b'\xef\xbb\xbf')
    assert (b'\r\n' in old) == (b'\r\n' in current)
    assert old.endswith(b'\n') == current.endswith(b'\n')

path=existing[0]
old=native_comparison_repairs(original(path).decode('utf-8-sig'),path); current=(ROOT/path).read_text(encoding='utf-8-sig')
for name in ('complete_project', 'end_project'):
    _,_,base=locate(old,name)
    legacy='eon_investment_lifecycle_legacy_'+name
    _,_,body=locate(current,legacy)
    assert body.replace(legacy+' = {',name+' = {',1) == base
    start,end,wrapper=locate(current,name)
    marker=current.rfind('# Protocol 24 has a separate construction ledger and daily clock.',0,start)
    assert marker >= 0
    current=current[:marker]+current[end+2:]
    current=current.replace(legacy+' = {',name+' = {',1)
assert current == old, 'Unrelated original functions changed'

path=existing[1]
old=original(path).decode('utf-8-sig'); current=(ROOT/path).read_text(encoding='utf-8-sig')
current=current[:current.index('\n# Protocol 24: investor country scope;')]
a,b,_=locate(current,'eon_investment_execute_offer')
_,_,base=locate(old,'eon_investment_execute_offer')
current=current[:a]+base+current[b:]
assert current == old, 'Offer staging or unrelated helpers changed'

path=existing[2]
old=native_comparison_repairs(original(path).decode('utf-8-sig'),path); current=(ROOT/path).read_text(encoding='utf-8-sig')
current=current[:current.index('\n# Country scope, project is the immutable index.')]
current=current.replace('\n\t\tOWNER = { exists = yes check_variable = { id = PREV.PREV.eon_investment_offer_partner } }','',1)
assert current == old, 'Original building conditions changed'

# Replace only the four authorized nested GUI blocks by their real base source.
path=existing[3]
old=original(path).decode('utf-8-sig'); current=(ROOT/path).read_text(encoding='utf-8-sig')
for name in ('AC_build_button_click', 'AC_build_button_click_enabled'):
    a,b,_=locate(current,name); _,_,base=locate(old,name)
    current=current[:a]+base+current[b:]
for name in ('AC_show_Investment_window','AC_allied_construction_window'):
    a,b,parent=locate(current,name); _,_,old_parent=locate(old,name)
    c,d,_=locate(parent,'visible'); _,_,base=locate(old_parent,'visible')
    current=current[:a]+parent[:c]+base+parent[d:]+current[b:]
assert current == old, 'Other GUI controls or properties changed'

source_paths=existing+[
    'common/on_actions/eon_investment_lifecycle_on_actions.txt',
    'events/eon_investment_lifecycle_events.txt',
    'localisation/english/eon_investment_lifecycle_l_english.yml',
    'localisation/russian/eon_investment_lifecycle_l_russian.yml',
]
for path in source_paths:
    data=(ROOT/path).read_bytes()
    if path.endswith('.txt'):
        ast(data.decode('utf-8-sig'))
    else:
        assert data.startswith(b'\xef\xbb\xbf')
        keys=re.findall(r'^\s+(\S+):',data.decode('utf-8-sig'),re.M)
        assert len(keys)==len(set(keys))==19
english=(ROOT/source_paths[-2]).read_text(encoding='utf-8-sig')
russian=(ROOT/source_paths[-1]).read_text(encoding='utf-8-sig')
assert set(re.findall(r'^\s+(\S+):',english,re.M)) == set(re.findall(r'^\s+(\S+):',russian,re.M))
events=[one(node,'id') for key,op,node in ast((ROOT/source_paths[-3]).read_text()) if key=='country_event']
assert events==[f'eon_investment_lifecycle.{i}' for i in range(1,10)]
for key,op,node in ast((ROOT/source_paths[-3]).read_text()):
    if key=='country_event':
        assert one(one(node,'option'),'name')=='eon_investment_lifecycle.ack'
        assert len(one(node,'option'))==1, 'Informational acknowledgement mutated a later project'

project_source=(ROOT/existing[1]).read_text(encoding='utf-8-sig')
project_ast=ast(project_source)
native_build=one(project_ast,'eon_investment_lifecycle_native_build')
try_build=one(project_ast,'eon_investment_lifecycle_try_build')
complete=one(project_ast,'eon_investment_lifecycle_complete_unit')
def nested(nodes):
    for node in nodes:
        yield node
        if isinstance(node[2],list): yield from nested(node[2])
native_comparison_count=0
for path in source_paths:
    if path.endswith('.txt'):
        for key, operator, body in nested(ast((ROOT/path).read_text(encoding='utf-8-sig'))):
            if key == 'check_variable':
                assert operator == '=', (path, operator)
                variable_comparison(body)
                native_comparison_count+=1
assert native_comparison_count > 0
assert [node[2] for node in nested(native_build) if node[0]=='set_temp_variable' and 'eon_project_build_result' in node[2][0][0]] == [[('PREV.eon_project_build_result','=','1')]]*15
assert [node[2] for node in nested(try_build) if node[0]=='set_temp_variable'] == [[('PREV.eon_project_build_result','=','-1')]]
cofund_ops=[node for node in nested(complete) if node[0] in ('add_to_variable','subtract_from_variable') and isinstance(node[2],list) and node[2][0][0] in ('eon_construction_contributions','eon_investment_contribution_spent','eon_investment_contribution_losses')]
assert len(cofund_ops)==3 and all(node[2][0][2]=='PREV.eon_project_spent_contribution' for node in cofund_ops)
release_state=one(one(project_ast,'eon_investment_lifecycle_release_project'),'var:project_array^project')
loop_pos=next(i for i,node in enumerate(release_state) if node[0]=='for_each_loop')
assert release_state[loop_pos-1] == ('set_temp_variable','=',[('eon_project_state_break','=','0')])

native=Path(r'D:\SteamLibrary\steamapps\common\Hearts of Iron IV\documentation')
api={}
if native.exists():
    for filename, snippets in {
        'dynamic_variables_documentation.md':['## Dynamic variables for scope state','### building_level','building_level@arms_factory'],
        'effects_documentation.md':['## add_building_construction','## clamp_temp_variable','max = num_cats','## for_each_loop'],
        'triggers_documentation.md':['## check_variable', 'compare = equals',
            '# less_than, less_than_or_equals', '# greater_than, greater_than_or_equals',
            '# equals, not_equals', 'check_variable = { varname = 0 }',
            'check_variable = { varname > 12 }', 'check_variable = { varname < 42 }'],
    }.items():
        raw=(native/filename).read_bytes(); text=raw.decode('utf-8-sig')
        assert all(snippet in text for snippet in snippets), (filename,snippets)
        api[filename]=hashlib.sha256(raw).hexdigest()
    vanilla=native.parent/'common/scripted_effects/00_scripted_effects.txt'
    if vanilla.exists():
        raw=vanilla.read_bytes(); text=raw.decode('utf-8-sig')
        assert 'set_temp_variable = { ROOT.best_leader = this }' in text
        assert 'add_to_temp_variable = { PREV.leader_score = num_of_factories }' in text
        assert 'check_variable = { ROOT.best_leader_score < leader_score }' in text
        api['installed_vanilla_00_scripted_effects.txt']=hashlib.sha256(raw).hexdigest()

groups=['Existing game BOM/EOL/EOF preserved', 'Legacy bodies unchanged except documented native comparison repair',
        'Other inherited effect bytes unchanged', 'Proposal staging helpers unchanged',
        'Original building eligibility unchanged except documented comparison syntax', 'Other GUI controls byte-identical',
        'Current game AST parses', 'Event IDs unique and acknowledgements passive',
        'EN/RU keys and UTF-8 BOMs agree', 'Scoped build/cofund outputs and state-loop reset',
        'Every current check_variable uses documented full or short native grammar']
if api: groups.append('Installed primary native API supports building-level check and primitives')
print(json.dumps({'all_passed':True, 'source_checks':len(groups), 'check_groups':groups,
    'unrelated_source_bytes_exact':True, 'game_format_preserved':True,
    'native_api_documentation_present':bool(api), 'native_api_documentation_sha256':api,
    'native_comparisons_checked':native_comparison_count,
    'inherited_native_comparison_repairs':3,
    'source_sha256':{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in source_paths},
    'proof_scope':'Actual baseline bytes, current AST, passive notifications and installed primary native API support; no engine run'},indent=2))
