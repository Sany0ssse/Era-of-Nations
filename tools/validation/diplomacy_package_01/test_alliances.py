"""Execute the changed effect AST in a bounded symbolic model, not the HOI4 engine.

Native admission is modeled both with and without on_offer_join_faction callbacks.
remove_ideas uses the actual idea on_remove helper; native leaving uses the full
actual on_leave_faction effect. Supported source statements fail closed.
"""
from pathlib import Path
from copy import deepcopy
from itertools import product
import re, json, hashlib

from _support import ROOT as root, baseline
token = re.compile(rb'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|[=<>!]+|[^\s{}=<>!#"]+')

def parse(data):
    tokens = [m[0].decode('utf-8-sig').strip('"') for m in token.finditer(data) if not m[0].startswith(b'#')]
    i = 0
    def body():
        nonlocal i
        out = []
        while i < len(tokens) and tokens[i] != '}':
            key = tokens[i]; i += 1
            assert tokens[i] == '=', (key, tokens[i]); i += 1
            if tokens[i] == '{':
                i += 1; value = body(); assert tokens[i] == '}'; i += 1
            else:
                value = tokens[i]; i += 1
            out.append((key, value))
        return out
    result = body(); assert i == len(tokens)
    return result

def raw_block(data, name):
    tokens = [m for m in token.finditer(data) if not m[0].startswith(b'#')]
    i = [i for i, t in enumerate(tokens) if t[0] == name.encode() and tokens[i+1][0] == b'=' and tokens[i+2][0] == b'{'][-1]
    depth = 1; start = tokens[i+2].end()
    for t in tokens[i+3:]:
        if t[0] == b'{': depth += 1
        elif t[0] == b'}': depth -= 1
        if depth == 0: return data[start:t.start()]
    raise AssertionError('Unclosed block')

def block(data, name): return parse(raw_block(data,name))

def csto_branch(name):
    outer = block((root/'common/on_actions/00_on_actions.txt').read_bytes(), name)
    effect = dict(outer)['effect']
    for key, value in effect:
        if key == 'if' and b'CSTO_member' in repr(value).encode(): return value
    raise AssertionError('No CSTO branch')

offer_branch = csto_branch('on_offer_join_faction')
leave_branch = csto_branch('on_leave_faction')
leave_effect = dict(block((root/'common/on_actions/00_on_actions.txt').read_bytes(), 'on_leave_faction'))['effect']
baseline_leave_effect = dict(block(baseline('common/on_actions/00_on_actions.txt'), 'on_leave_faction'))['effect']
on_actions_source=(root/'common/on_actions/00_on_actions.txt').read_bytes()
on_actions_baseline=baseline('common/on_actions/00_on_actions.txt')
current_leave_body=raw_block(on_actions_source,'on_leave_faction')
baseline_leave_body=raw_block(on_actions_baseline,'on_leave_faction')
assert on_actions_source.replace(current_leave_body,b'',1)==on_actions_baseline.replace(baseline_leave_body,b'',1), 'Other on_actions bytes changed'
original = {}; changed = {}
for org in ['NATO', 'CSTO']:
    path = root/f'common/scripted_effects/00_{org}_effects.txt'
    changed.update(dict(parse(path.read_bytes())))
    original.update(dict(parse(baseline(str(path.relative_to(root)).replace("\\", "/")))))

class Model:
    def __init__(self, state, effects, offer_callback=False, transfer=False, native_leave_effect=None):
        self.s = state; self.effects = effects
        self.offer_callback = offer_callback; self.transfer = transfer
        self.native_leave_effect = leave_effect if native_leave_effect is None else native_leave_effect
        self.depth = 0

    def ref(self, key, stack):
        return {'THIS': stack[-1], 'ROOT': self.s['root'], 'PREV': stack[-2] if len(stack)>1 else self.s['root'], 'FROM': self.s.get('from', 'APP')}.get(key, key)

    def trigger(self, nodes, stack):
        c = self.s['countries'][stack[-1]]
        for key, value in nodes:
            if key == 'NOT': passed = not self.trigger(value, stack)
            elif key == 'OR': passed = any(self.trigger([n], stack) for n in value)
            elif key == 'has_idea': passed = value in c['ideas']
            elif key == 'has_country_flag': passed = value in c['flags']
            elif key == 'has_faction_template': passed = c['faction'] is not None and self.s['templates'].get(c['faction']) == value
            elif key == 'is_faction_leader': passed = c['faction'] is not None and self.s['leaders'].get(c['faction']) == stack[-1]
            elif key == 'is_in_faction_with':
                other = self.s['countries'][self.ref(value, stack)]
                passed = c['faction'] is not None and c['faction'] == other['faction']
            elif key == 'has_military_access_to': passed = (stack[-1], self.ref(value, stack)) in self.s['access']
            elif key == 'is_in_array':
                name, target = value[0]; passed = self.ref(target, stack) in self.s['arrays'][name]
            elif key == 'check_variable':
                name, expected = value[0]; passed = c['temp'].get(name, 0) == int(expected)
            elif key == 'tag': passed = stack[-1] == self.ref(value,stack)
            elif key in self.s['countries'] or key in ['ROOT', 'PREV', 'FROM', 'THIS']:
                passed = self.trigger(value, stack+[self.ref(key, stack)])
            else: raise AssertionError(('Unsupported trigger', key, value))
            if not passed: return False
        return True

    def execute(self, nodes, stack):
        self.depth += 1; assert self.depth < 30, 'Callback recursion'
        i = 0
        while i < len(nodes):
            key, value = nodes[i]; i += 1
            tag = stack[-1]; c = self.s['countries'][tag]
            if key == 'if':
                branches = [value]
                while i < len(nodes) and nodes[i][0] in ['else_if', 'else']:
                    branches.append(nodes[i][1]); i += 1
                for branch in branches:
                    if self.trigger(dict(branch).get('limit', []), stack):
                        self.execute([(k,v) for k,v in branch if k != 'limit'], stack); break
            elif key in self.effects: self.execute(self.effects[key], stack)
            elif key == 'while_loop_effect':
                iterations = 0
                while self.trigger(dict(value)['limit'], stack):
                    self.execute([(k,v) for k,v in value if k != 'limit'], stack)
                    iterations += 1; assert iterations <= 100, 'Unbounded loop'
            elif key in self.s['countries'] or key in ['ROOT', 'PREV', 'FROM', 'THIS']:
                self.execute(value, stack+[self.ref(key, stack)])
            elif key == 'set_temp_variable':
                name, amount = value[0]; c['temp'][name] = int(amount)
            elif key == 'set_country_flag': c['flags'].add(value)
            elif key == 'clr_country_flag': c['flags'].discard(value)
            elif key == 'add_to_array':
                name, target = value[0]; self.s['arrays'][name].append(self.ref(target, stack))
            elif key == 'remove_from_array':
                name, target = value[0]; target = self.ref(target, stack)
                if target in self.s['arrays'][name]: self.s['arrays'][name].remove(target)
            elif key == 'add_ideas': c['ideas'].add(value)
            elif key == 'remove_ideas':
                if value in c['ideas']:
                    c['ideas'].remove(value)
                    if value in ['NATO_member', 'CSTO_member']:
                        self.execute(self.effects[value.split('_')[0]+'_leave_idea'], stack)
            elif key == 'add_to_tech_sharing_group': c['sharing'].add(value)
            elif key == 'remove_from_tech_sharing_group': c['sharing'].discard(value)
            elif key == 'leave_faction':
                if c['faction'] is not None:
                    c['faction'] = None
                    # Full source on_leave_faction callback and its ROOT scope.
                    old_root = self.s['root']; self.s['root'] = tag
                    self.execute(self.native_leave_effect, stack)
                    self.s['root'] = old_root
            elif key == 'add_to_faction':
                target = self.ref(value, stack); joining = self.s['countries'][target]
                if joining['faction'] is None or self.transfer:
                    if joining['faction'] is not None and joining['faction'] != c['faction']:
                        # Model a permitted native transfer as old exit before new admission.
                        self.execute([('leave_faction','yes')], [target])
                    joining['faction'] = c['faction']
                    if self.offer_callback:
                        old_root, old_from = self.s['root'], self.s.get('from')
                        self.s['root'], self.s['from'] = tag, target
                        self.execute([('if', offer_branch)], [tag])
                        self.s['root'] = old_root
                        if old_from is None: self.s.pop('from')
                        else: self.s['from'] = old_from
            elif key in ['random_scope_in_array', 'for_each_scope_loop']:
                name = dict(value)['array']; scopes = list(self.s['arrays'][name])
                scopes = [other for other in scopes if self.trigger(dict(value).get('limit', []), stack+[other])]
                if key == 'random_scope_in_array': scopes = scopes[-1:] # Select a stale decoy if permitted.
                for other in scopes: self.execute([(k,v) for k,v in value if k not in ['array','limit']], stack+[other])
            elif key in ['add_opinion_modifier', 'reverse_add_opinion_modifier', 'remove_opinion_modifier']:
                pair = (tag, self.ref(dict(value)['target'], stack), dict(value)['modifier'])
                if key == 'reverse_add_opinion_modifier': pair = (pair[1], pair[0], pair[2])
                if key == 'remove_opinion_modifier':
                    self.s['opinions'].discard(pair)
                    if 'opinion_stacks' in self.s:self.s['opinion_stacks'].pop(pair,None)
                else:
                    self.s['opinions'].add(pair)
                    if 'opinion_stacks' in self.s:self.s['opinion_stacks'][pair]=self.s['opinion_stacks'].get(pair,0)+1
            elif key == 'diplomatic_relation':
                rel = dict(value); assert rel['relation'] == 'military_access'
                pair = (tag, self.ref(rel['country'], stack))
                if rel['active'] == 'yes': self.s['access'].add(pair)
                else: self.s['access'].discard(pair)
            elif key == 'hidden_effect': self.execute(value, stack)
            elif key == 'news_event': self.s['news'].append((tag, dict(value)['id']))
            elif key == 'country_event': self.s['events'].append((tag, dict(value)['id'] if isinstance(value,list) else value))
            elif key == 'custom_effect_tooltip': pass
            else: raise AssertionError(('Unsupported effect', key, value))
        self.depth -= 1

def state(org, app_faction=None, idea=False, array=False, leader=True, decoy=True, nested=False, access=0):
    member = org+'_member'; name = 'global.nato_members' if org == 'NATO' else 'global.CSTO_member'
    def country(faction=None, ideas=()): return {'faction': faction, 'ideas': set(ideas), 'flags': set(), 'sharing': set(), 'temp': {}}
    s = {'countries': {'APP':country(app_faction, [member] if idea else []), 'LEADER':country(org,[member]), 'MEMBER':country(org,[member]), 'DECOY':country('unrelated',[member]), 'ORIGIN':country()},
         'arrays': {'global.nato_members': [], 'global.CSTO_member': []},
         'leaders': {org:'LEADER' if leader else 'NONEXISTENT', 'unrelated':'DECOY'},
         'templates': {org:'faction_template_'+org.lower(), 'unrelated':'faction_template_other'},
         'news':[], 'events':[], 'opinions':set(), 'access':set(), 'root':'ORIGIN' if nested else 'APP'}
    s['arrays'][name] = ['LEADER','MEMBER']+(['DECOY'] if decoy else [])+(['APP'] if array else [])
    if access&1: s['access'].add(('LEADER','APP'))
    if access&2: s['access'].add(('APP','LEADER'))
    if idea: s['countries']['APP']['sharing'].add(org+'_Tech_Share')
    return s

def observable(s):
    out = deepcopy(s)
    for c in out['countries'].values(): c.pop('temp')
    return out

counts = {'join':0, 'exit':0, 'on_remove':0, 'native_leave':0, 'native_transfer':0, 'native_callback_regressions':0, 'membership_reconcile_regressions':0, 'benefit_reconciliation':0, 'regressions':0}
for org, callback, nested, transfer, access in product(['NATO','CSTO'], [False,True], [False,True], [False,True], range(4)):
    s=state(org, nested=nested, access=access); model=Model(s,changed,callback,transfer)
    model.execute(changed[org+'_join'], ['APP'])
    member=org+'_member'; name='global.nato_members' if org=='NATO' else 'global.CSTO_member'
    assert s['countries']['APP']['faction']==org and member in s['countries']['APP']['ideas']
    assert s['arrays'][name].count('APP')==1 and s['countries']['APP']['sharing']=={org+'_Tech_Share'}
    assert len(s['news'])==1 and s['news'][0][0]=='APP'
    assert s['countries']['ORIGIN']['sharing']==set() and s['countries']['ORIGIN']['faction'] is None
    if org=='NATO':
        assert {('LEADER','APP'),('APP','LEADER'),('MEMBER','APP'),('APP','MEMBER')} <= s['access']
        assert ('DECOY','APP') not in s['access'] and ('APP','DECOY') not in s['access']
    once=observable(s); model.execute(changed[org+'_join'], ['APP']); assert observable(s)==once
    counts['join']+=1

for org, faction, idea, array, leader, callback, nested, transfer in product(['NATO','CSTO'], [None,'unrelated','NATO','CSTO'], [False,True], [False,True], [False,True], [False,True], [False,True], [False,True]):
    s=state(org, faction,idea,array,leader,True,nested); before=observable(s); model=Model(s,changed,callback,transfer)
    model.execute(changed[org+'_join'], ['APP'])
    succeeded=faction==org or (leader and (faction is None or transfer))
    member=org+'_member'; name='global.nato_members' if org=='NATO' else 'global.CSTO_member'
    if succeeded:
        assert s['countries']['APP']['faction']==org
        assert member in s['countries']['APP']['ideas'] and s['arrays'][name].count('APP')==1, (org,faction,idea,array,leader,callback,nested,transfer,s['arrays'][name],s['countries']['APP']['ideas'])
        # An existing spirit can be cleaned up when leaving an unrelated faction;
        # its exit news is distinct from the guarded target admission news.
        recorded_exit = idea or array
        native_exit_news = int(transfer and faction is not None and faction != org and recorded_exit)
        assert len(s['news'])==(0 if idea else 1)+native_exit_news, (org,faction,idea,array,leader,callback,nested,transfer,s['news'])
    else:
        assert observable(s)==before, ('Failed admission changed state',org,faction,idea,array,leader,callback,nested,transfer)
    counts['join']+=1

for org, faction, idea, array, nested in product(['NATO','CSTO'], [None,'unrelated','NATO','CSTO'], [False,True], [False,True], [False,True]):
    s=state(org,faction,idea,array,nested=nested)
    member=org+'_member'; name='global.nato_members' if org=='NATO' else 'global.CSTO_member'
    expected_change=idea or array or faction==org
    model=Model(s,changed); model.execute(changed[org+'_leave'], ['APP'])
    assert s['countries']['APP']['faction']==(None if faction==org else faction)
    assert member not in s['countries']['APP']['ideas'] and 'APP' not in s['arrays'][name]
    assert org+'_Tech_Share' not in s['countries']['APP']['sharing']
    assert len(s['news'])==int(expected_change) and not s['countries']['APP']['flags']
    once=observable(s); model.execute(changed[org+'_leave'], ['APP']); assert observable(s)==once
    counts['exit']+=1

for org, faction, array, nested in product(['NATO','CSTO'], [None,'unrelated','NATO','CSTO'], [False,True], [False,True]):
    s=state(org,faction,True,array,nested=nested); model=Model(s,changed)
    model.execute([('remove_ideas', org+'_member')], ['APP'])
    # If the array is missing and idea removal already completed, the callback
    # cannot distinguish stale sharing in an unrelated faction; this is bounded.
    expected=array or faction==org
    if expected:
        assert s['countries']['APP']['faction']==(None if faction==org else faction)
        assert len(s['news'])==1 and not s['countries']['APP']['flags']
        assert org+'_Tech_Share' not in s['countries']['APP']['sharing']
    else:
        assert s['countries']['APP']['faction']==faction and len(s['news'])==0
    counts['on_remove']+=1

for org,nested in product(['NATO','CSTO'],[False,True]):
    s=state(org,org,True,True,nested=nested); model=Model(s,changed)
    model.execute([('leave_faction','yes')], ['APP'])
    assert s['countries']['APP']['ideas']==set() and not s['countries']['APP']['sharing']
    name='global.nato_members' if org=='NATO' else 'global.CSTO_member'
    assert 'APP' not in s['arrays'][name] and len(s['news'])==1
    counts['native_leave']+=1

# Reconstruct the exact reviewed pre-callback helper sources, verified by their
# recorded SHA-256. Those sources added the spirit only in first-join/news guard.
pre_reconcile={}
current_nato_source=(root/'common/scripted_effects/00_NATO_effects.txt').read_bytes()
loop_body=raw_block(raw_block(current_nato_source,'NATO_join'),'for_each_scope_loop')
current_loop=b'\t\tfor_each_scope_loop = {'+loop_body+b'}\n'
assert current_nato_source.count(current_loop)==1
prior_loop=current_loop.replace(b'\t\t\t\t\tNOT = { tag = PREV }\n',b'',1)
prior_loop=prior_loop.replace(b'\t\t\t\tremove_opinion_modifier = { target = PREV modifier = NATO_member_modifier }\n',b'',1)
prior_loop=prior_loop.replace(b'\t\t\t\tPREV = {\n\t\t\t\t\tremove_opinion_modifier = { target = PREV modifier = NATO_member_modifier }\n\t\t\t\t}\n',b'',1)
prior_loop=b''.join((b'\t'+line if line.strip() else line) for line in prior_loop.splitlines(keepends=True))
pre_benefits_source=current_nato_source.replace(current_loop,b'',1).replace(b'\t\t\tcustom_effect_tooltip = NATO_join_tt',prior_loop+b'\t\t\tcustom_effect_tooltip = NATO_join_tt',1)
assert hashlib.sha256(pre_benefits_source).hexdigest()=='4b7adb4d14771a959f6c6331b8eb3796b4d6d55a0a009aea62efff136c9a8b21'
pre_reconcile_hashes={'NATO':'be6415177961891ea85d6fe7ebba933bf650604498b9089dd58a3bc2e3989882','CSTO':'4d006921f8f4125c6376d023a16ed9c65c0695b5bc473da56667a88c6565c4d3'}
for org in ['NATO','CSTO']:
    raw=pre_benefits_source if org=='NATO' else (root/f'common/scripted_effects/00_{org}_effects.txt').read_bytes()
    if org=='NATO':
        raw=raw.replace(b'\t\t# Native exit callbacks may remove an old spirit during a faction transfer.\n\t\tadd_ideas = NATO_member\n',b'',1)
        raw=raw.replace(b'\t\t\tcustom_effect_tooltip = NATO_join_tt',b'\t\t\tadd_ideas = NATO_member\n\t\t\tcustom_effect_tooltip = NATO_join_tt',1)
    else:
        raw=raw.replace(b'\t\tadd_ideas = CSTO_member\n',b'',1)
        raw=raw.replace(b'\t\t\thidden_effect = { news_event = { id = CSTO.4 hours = 6 } }',b'\t\t\tadd_ideas = CSTO_member\n\t\t\thidden_effect = { news_event = { id = CSTO.4 hours = 6 } }',1)
        raw=raw.rstrip(b'\n')+b'\n' # Reviewed precursor inherited an extra EOF LF.
    assert hashlib.sha256(raw).hexdigest()==pre_reconcile_hashes[org]
    pre_reconcile.update(dict(parse(raw)))
for org,callback,nested,array in product(['NATO','CSTO'],[False,True],[False,True],[False,True]):
    if org=='CSTO' and callback:continue # Its native offer independently repairs the spirit.
    old=state(org,'unrelated',True,array,decoy=False,nested=nested)
    Model(old,pre_reconcile,callback,True).execute(pre_reconcile[org+'_join'],['APP'])
    assert old['countries']['APP']['faction']==org and org+'_member' not in old['countries']['APP']['ideas']
    current=state(org,'unrelated',True,array,decoy=False,nested=nested)
    Model(current,changed,callback,True).execute(changed[org+'_join'],['APP'])
    assert current['countries']['APP']['faction']==org and current['countries']['APP']['ideas']=={org+'_member'}
    assert current['countries']['APP']['sharing']=={org+'_Tech_Share'}
    counts['membership_reconcile_regressions']+=1

pre_benefits=dict(changed);pre_benefits.update(dict(parse(pre_benefits_source)))
required_access={('APP','LEADER'),('LEADER','APP'),('APP','MEMBER'),('MEMBER','APP')}
required_opinions={(a,b,'NATO_member_modifier') for a,b in required_access}
def stale_nato_state(array,nested,access):
    s=state('NATO','unrelated',True,array,decoy=False,nested=nested,access=access)
    s['access'].update([('APP','MEMBER'),('MEMBER','APP')]);s['opinions'].update(required_opinions)
    # Native add_opinion documentation does not promise no stacking. Exercise
    # conservative stacking semantics and existing repeated entries explicitly.
    s['opinion_stacks']={pair:3 for pair in required_opinions}
    return s
for callback,nested,array,access,allowed in product([False,True],[False,True],[False,True],range(4),[False,True]):
    old=stale_nato_state(array,nested,access);initial=observable(old)
    Model(old,pre_benefits,callback,allowed).execute(pre_benefits['NATO_join'],['APP'])
    current=stale_nato_state(array,nested,access);model=Model(current,changed,callback,allowed)
    model.execute(changed['NATO_join'],['APP'])
    if allowed:
        assert old['countries']['APP']['faction']=='NATO' and old['countries']['APP']['ideas']=={'NATO_member'}
        assert not required_access&old['access'] and not required_opinions&old['opinions']
        assert required_access<=current['access'] and required_opinions<=current['opinions']
        assert all(current['opinion_stacks'].get(pair)==1 for pair in required_opinions)
        assert ('APP','APP') not in current['access'] and ('APP','APP','NATO_member_modifier') not in current['opinions']
        assert len(current['news'])==1 # Old recorded exit, no duplicate first-join announcement.
        once=observable(current);model.execute(changed['NATO_join'],['APP']);assert observable(current)==once
    else:assert observable(current)==initial and observable(old)==initial
    counts['benefit_reconciliation']+=1
for nested,access in product([False,True],range(4)):
    old=state('NATO','NATO',True,True,decoy=False,nested=nested,access=access)
    Model(old,pre_benefits).execute(pre_benefits['NATO_join'],['APP'])
    assert not required_access<=old['access']
    current=state('NATO','NATO',True,True,decoy=False,nested=nested,access=access)
    current['opinions'].update(required_opinions);current['opinion_stacks']={pair:3 for pair in required_opinions}
    model=Model(current,changed);model.execute(changed['NATO_join'],['APP'])
    assert required_access<=current['access'] and required_opinions<=current['opinions']
    assert all(current['opinion_stacks'].get(pair)==1 for pair in required_opinions)
    assert ('APP','APP') not in current['access'] and ('APP','APP','NATO_member_modifier') not in current['opinions']
    assert current['news']==[];once=observable(current);model.execute(changed['NATO_join'],['APP']);assert observable(current)==once
    counts['benefit_reconciliation']+=1

def transfer_state(old,new,nested=False,duplicates=1,old_idea=True):
    s=state(old,old,old_idea,True,decoy=False,nested=nested)
    def country(faction,ideas): return {'faction':faction,'ideas':set(ideas),'flags':set(),'sharing':set(),'temp':{}}
    s['countries']['NEW_LEADER']=country(new,[new+'_member'])
    s['countries']['NEW_MEMBER']=country(new,[new+'_member'])
    s['templates'][new]='faction_template_'+new.lower();s['leaders'][new]='NEW_LEADER'
    old_array='global.nato_members' if old=='NATO' else 'global.CSTO_member'
    new_array='global.nato_members' if new=='NATO' else 'global.CSTO_member'
    s['arrays'][old_array]=['LEADER','MEMBER']+['APP']*duplicates
    s['arrays'][new_array]=['NEW_LEADER','NEW_MEMBER']
    s['countries']['APP']['sharing'].add(old+'_Tech_Share')
    if old=='NATO':
        for other in ['LEADER','MEMBER']:
            s['access'].update([('APP',other),(other,'APP')])
            s['opinions'].update([('APP',other,'NATO_member_modifier'),(other,'APP','NATO_member_modifier')])
    return s

for old,new,callback,nested,allowed,duplicates in product(['NATO','CSTO'],['NATO','CSTO'],[False,True],[False,True],[False,True],[1,2]):
    if old==new:continue
    s=transfer_state(old,new,nested,duplicates); initial=observable(s)
    model=Model(s,changed,callback,allowed);model.execute(changed[new+'_join'],['APP'])
    old_array='global.nato_members' if old=='NATO' else 'global.CSTO_member'
    new_array='global.nato_members' if new=='NATO' else 'global.CSTO_member'
    if allowed:
        assert s['countries']['APP']['faction']==new and s['countries']['APP']['ideas']=={new+'_member'}
        assert s['countries']['APP']['sharing']=={new+'_Tech_Share'} and not s['countries']['APP']['flags']
        assert 'APP' not in s['arrays'][old_array] and s['arrays'][new_array].count('APP')==1
        assert len(s['news'])==2, (old,new,callback,nested,duplicates,s['news'])
        if old=='NATO':
            assert not {('APP','LEADER'),('LEADER','APP'),('APP','MEMBER'),('MEMBER','APP')}&s['access']
            assert not any('APP' in (a,b) and modifier=='NATO_member_modifier' and ('LEADER' in (a,b) or 'MEMBER' in (a,b)) for a,b,modifier in s['opinions'])
        assert s['countries']['ORIGIN']['sharing']==set() and s['countries']['ORIGIN']['faction'] is None
        once=observable(s);model.execute(changed[new+'_join'],['APP']);assert observable(s)==once
    else:assert observable(s)==initial, 'A failed native transfer must retain the old membership'
    counts['native_transfer']+=1

# Inherited on_leave callback defects fail with baseline callback source while
# using the same fixed central helpers; the current full callback must pass.
for nested,duplicates,old_idea,callback in product([False,True],[1,2],[False,True],[False,True]):
    old=transfer_state('NATO','CSTO',nested,duplicates,old_idea)
    Model(old,changed,callback,True,baseline_leave_effect).execute(changed['CSTO_join'],['APP'])
    assert old['countries']['APP']['faction']=='CSTO'
    assert 'APP' in old['arrays']['global.nato_members'] and 'NATO_Tech_Share' in old['countries']['APP']['sharing']
    current=transfer_state('NATO','CSTO',nested,duplicates,old_idea)
    Model(current,changed,callback,True).execute(changed['CSTO_join'],['APP'])
    assert current['countries']['APP']['ideas']=={'CSTO_member'} and current['countries']['APP']['sharing']=={'CSTO_Tech_Share'}
    assert 'APP' not in current['arrays']['global.nato_members'] and current['arrays']['global.CSTO_member'].count('APP')==1
    assert len(current['news'])==2 and not current['countries']['APP']['flags']
    counts['native_callback_regressions']+=1
for nested,duplicates,callback in product([False,True],[1,2],[False,True]):
    old=transfer_state('CSTO','NATO',nested,duplicates,False)
    Model(old,changed,callback,True,baseline_leave_effect).execute(changed['NATO_join'],['APP'])
    assert 'APP' in old['arrays']['global.CSTO_member'] and 'CSTO_Tech_Share' in old['countries']['APP']['sharing']
    current=transfer_state('CSTO','NATO',nested,duplicates,False)
    Model(current,changed,callback,True).execute(changed['NATO_join'],['APP'])
    assert current['countries']['APP']['ideas']=={'NATO_member'} and current['countries']['APP']['sharing']=={'NATO_Tech_Share'}
    assert 'APP' not in current['arrays']['global.CSTO_member'] and current['arrays']['global.nato_members'].count('APP')==1
    assert len(current['news'])==2 and not current['countries']['APP']['flags']
    counts['native_callback_regressions']+=1
for nested in [False,True]:
    old=transfer_state('CSTO','NATO',nested,2,False)
    Model(old,changed,native_leave_effect=baseline_leave_effect).execute([('leave_faction','yes')],['APP'])
    assert 'APP' in old['arrays']['global.CSTO_member'] and 'CSTO_Tech_Share' in old['countries']['APP']['sharing']
    current=transfer_state('CSTO','NATO',nested,2,False)
    Model(current,changed).execute([('leave_faction','yes')],['APP'])
    assert current['countries']['APP']['faction'] is None and current['countries']['APP']['ideas']==set()
    assert 'APP' not in current['arrays']['global.CSTO_member'] and not current['countries']['APP']['sharing']
    assert len(current['news'])==1 and not current['countries']['APP']['flags']
    counts['native_callback_regressions']+=1
for nested,old_idea in product([False,True],[False,True]):
    old=transfer_state('NATO','CSTO',nested,2,old_idea)
    Model(old,changed,native_leave_effect=baseline_leave_effect).execute([('leave_faction','yes')],['APP'])
    assert 'APP' in old['arrays']['global.nato_members'] and 'NATO_Tech_Share' in old['countries']['APP']['sharing']
    current=transfer_state('NATO','CSTO',nested,2,old_idea)
    Model(current,changed).execute([('leave_faction','yes')],['APP'])
    assert current['countries']['APP']['faction'] is None and current['countries']['APP']['ideas']==set()
    assert 'APP' not in current['arrays']['global.nato_members'] and not current['countries']['APP']['sharing']
    assert len(current['news'])==1 and not current['countries']['APP']['flags']
    counts['native_callback_regressions']+=1

# If the engine invokes old exit after assigning the new faction, the NATO
# cleanup must clear recorded old membership while preserving current CSTO.
for old,new,old_idea,nested in product(['NATO','CSTO'],['NATO','CSTO'],[False,True],[False,True]):
    if old==new:continue
    s=transfer_state(old,new,nested,2,old_idea)
    # Native faction has changed before the callback, while new organization
    # benefits have not yet been assigned by offer/admission effects.
    s['countries']['APP']['faction']=new
    old_root=s['root'];s['root']='APP';Model(s,changed).execute(leave_effect,['APP']);s['root']=old_root
    old_array='global.nato_members' if old=='NATO' else 'global.CSTO_member'
    assert s['countries']['APP']['faction']==new and 'APP' not in s['arrays'][old_array]
    assert old+'_Tech_Share' not in s['countries']['APP']['sharing'] and not s['countries']['APP']['flags']
    Model(s,changed).execute(changed[new+'_join'],['APP'])
    assert s['countries']['APP']['ideas']=={new+'_member'} and s['countries']['APP']['sharing']=={new+'_Tech_Share'}
    counts['native_leave']+=1

# Reproduce concrete pre-change defects from the preserved source.
for org in ['NATO','CSTO']:
    s=state(org, leader=False); Model(s,original).execute(original[org+'_join'],['APP'])
    assert s['countries']['APP']['faction']=='unrelated' and org+'_member' in s['countries']['APP']['ideas']; counts['regressions']+=1
    s=state(org,'unrelated',True,True); Model(s,original).execute(original[org+'_leave'],['APP'])
    assert s['countries']['APP']['faction'] is None and len(s['news'])>1; counts['regressions']+=1
s=state('CSTO',nested=True,decoy=False); Model(s,original).execute(original['CSTO_join'],['APP'])
assert s['countries']['ORIGIN']['faction']=='CSTO' and s['countries']['ORIGIN']['sharing']=={'CSTO_Tech_Share'}
assert s['countries']['APP']['faction'] is None; counts['regressions']+=1

assert set(original)==set(changed), 'Existing scripted effect IDs must be preserved'
assert original['NATO_show_non_ratified_countries']==changed['NATO_show_non_ratified_countries']
report={'test_level':'source-driven symbolic model, not engine or campaign proof', 'case_counts':counts, 'total_cases':sum(counts.values()),
        'behavior_checked':['correct template despite stale unrelated faction leader', 'membership granted only after native admission', 'nested caller distinct from ROOT', 'native callback on/off', 'native foreign-faction transfer allowed/disallowed', 'repeat join and exit', 'asymmetric preexisting access', 'idea on_remove reentrancy', 'full actual native leave callback', 'NATO to CSTO and CSTO to NATO transfers', 'failed native transfer keeps old membership', 'native exit with missing idea and recorded NATO/CSTO membership', 'stale target spirit removed by native exit is reconciled on successful admission', 'NATO access and opinions restored after stale transfer', 'repeated NATO pair benefits remain single under conservative stacking semantics', 'member excluded from self access/opinions', 'membership array repair', 'unrelated faction preserved'],
        'limits':['Native add_to_faction acceptance and template trigger need runtime verification.', 'Historical/national accession and unanimous ratification procedures are unchanged.', 'Only the current member is deduplicated when its helper executes; no bulk migration is performed.', 'An external removal with missing member array and unrelated faction cannot identify the removed membership from these guards; stale tech sharing in that corrupt state requires broader reconciliation.'],
        'source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ['common/scripted_effects/00_NATO_effects.txt','common/scripted_effects/00_CSTO_effects.txt','common/on_actions/00_on_actions.txt']}}
print(json.dumps(report,indent=2))
