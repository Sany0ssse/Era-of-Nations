"""Current directed no-ties registry and native grammar checks.

This executes current effect islands and verifies the complete bounded legacy
byte delta. It does not prove an engine campaign or migration of existing saves.
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import hashlib,json,re,subprocess
from test_relations import ROOT,P,FILES,NATIVE,parse,one,state,ctx,condition,execute,decision,establish,legacy_no_ties

BASELINE='c1420b108dee2d129018951c9ba73c1f6bfc4360'
LEGACY={
 'events/Iraq.txt':7,
 'events/Iran.txt':6,
 'common/national_focus/Iraq_Focus_Tree.txt':2,
 'common/national_focus/Iran_Focus_Tree.txt':2,
 'common/national_focus/Greece_Focus_Tree.txt':5,
 'common/national_focus/Germany_Focus_Tree.txt':2,
 'common/national_focus/Botswana_Focus_Tree.txt':2,
 'history/countries/PER - Iran.txt':4,
 'common/decisions/Iran.txt':2,
 'common/scripted_effects/eon_per_usa_normalization_effects.txt':2,
}
OPINION=re.compile(rb'\b(?P<kind>add_opinion_modifier|reverse_add_opinion_modifier|remove_opinion_modifier)\s*=\s*\{(?P<body>[^{}]*)\}')
NO_TIES=re.compile(rb'\bmodifier\s*=\s*no_diplomatic_ties\b')
checks=Counter()

def assert_(ready,group):
 assert ready,group
 checks[group]+=1

def mirror_island(original,match):
 target=re.search(rb'\btarget\s*=\s*([^\s}]+)',match['body'])[1]
 prefix=original[original.rfind(b'\n',0,match.start())+1:match.start()]
 indent=re.match(rb'[ \t]*',prefix)[0]
 unit=b'\t' if b'\t' in indent else b' '
 newline=b'\r\n' if b'\r\n' in original else b'\n'
 known=(P+'legacy_known@').encode();active=(P+'legacy_no_ties@').encode()
 if match['kind']==b'reverse_add_opinion_modifier':
  lines=[b'hidden_effect = {',unit+target+b' = {',unit*2+b'set_country_flag = '+known+b'PREV',
   unit*2+b'set_country_flag = '+active+b'PREV',unit+b'}',b'}']
 else:
  command=b'clr_country_flag' if match['kind']==b'remove_opinion_modifier' else b'set_country_flag'
  lines=[b'hidden_effect = {',unit+b'set_country_flag = '+known+target,unit+command+b' = '+active+target,b'}']
 return newline+newline.join(indent+line for line in lines)

def bind_target(nodes,target,peer):
 def remap(token):
  if token==target:return peer
  return token.replace('@'+target,'@'+peer)
 return [(remap(k),o,bind_target(v,target,peer) if isinstance(v,list) else remap(v)) for k,o,v in nodes]

def source_inventory():
 sites=[]
 for path,count in LEGACY.items():
  original=subprocess.check_output(['git','show',BASELINE+':'+path],cwd=ROOT)
  current=(ROOT/path).read_bytes()
  found=[]
  def append(match):
   if not NO_TIES.search(match['body']):return match[0]
   line=original[:match.start()].count(b'\n')+1
   # These are the two existing non-executing examples in GRE_denounce_nato.
   if path=='common/national_focus/Greece_Focus_Tree.txt' and line in (5417,5418):
    assert_('effect_tooltip = {' in original[max(0,match.start()-200):match.start()].decode('utf-8-sig')
     or line==5418,'Greece two examples remain presentation only')
    return match[0]
   island=mirror_island(original,match)
   target=re.search(rb'\btarget\s*=\s*([^\s}]+)',match['body'])[1].decode()
   record={'path':path,'line_before':line,'kind':match['kind'].decode(),'target':target,
    'source':(match[0]+island).decode('utf-8-sig')}
   found.append(record);sites.append(record)
   return match[0]+island
  expected=OPINION.sub(append,original)
  if path=='common/decisions/Iran.txt':
   expected=expected.replace(b'has_opinion_modifier = no_diplomatic_ties',
    b'PER = { PREV = { eon_diplomatic_relations_legacy_pair_active = yes } }',1)
  assert_(len(found)==count,'complete reviewed mutation inventory '+path)
  assert_(current==expected,'only exact reviewed metadata/query byte delta '+path)
  assert_(current.startswith(b'\xef\xbb\xbf')==original.startswith(b'\xef\xbb\xbf'),'legacy BOM retained '+path)
  assert_(b'\r\n' in current if b'\r\n' in original else b'\r\n' not in current,'legacy newline style retained '+path)
 # In the new generic effects, each opinion mutation is immediately followed by
 # the exact matching directed receipt; all four execute in the same scope.
 generic=(ROOT/FILES[1]).read_bytes()
 own=[]
 for match in OPINION.finditer(generic):
  if not NO_TIES.search(match['body']):continue
  assert_(re.search(rb'\btarget\s*=\s*PREV\b',match['body']) is not None,'generic only explicit PREV opinion target')
  action=b'clr_country_flag' if match['kind']==b'remove_opinion_modifier' else b'set_country_flag'
  receipt=b' set_country_flag = eon_diplomatic_relations_legacy_known@PREV '+action+b' = eon_diplomatic_relations_legacy_no_ties@PREV'
  assert_(generic[match.end():].startswith(receipt),'generic metadata follows same scoped mutation')
  own.append({'path':FILES[1],'line_before':generic[:match.start()].count(b'\n')+1,
   'kind':match['kind'].decode(),'target':'PREV','source':(match[0]+receipt).decode()})
 assert_(len(own)==4,'all four generic break/restore directed mutations covered')
 # Exhaustive token inventory excludes declarations and checks, but never a real
 # current effect. An extra unmanaged national add/removal must fail this suite.
 all_matches=[]
 for root in ('common','events','history'):
  for file in (ROOT/root).rglob('*.txt'):
   raw=file.read_bytes()
   if b'no_diplomatic_ties' not in raw:continue
   for match in OPINION.finditer(raw):
    if NO_TIES.search(match['body']):all_matches.append(file.relative_to(ROOT).as_posix())
 assert_(Counter(all_matches)==Counter({**LEGACY,'common/national_focus/Greece_Focus_Tree.txt':7,FILES[1]:4}),
  'whole current source has no unmanaged no-ties effect or omitted tooltip')
 return sites+own

def effects_in_both_frames(sites):
 for record in sites:
  for actor,peer in (('A','B'),('B','C')):
   r=state();legacy_no_ties(r,'A','D')
   # Test the native removal against an actually populated same-pair receipt.
   if record['kind']=='remove_opinion_modifier':legacy_no_ties(r,actor,peer)
   before=deepcopy(r)
   nodes=bind_target(parse(record['source']),record['target'],peer)
   context=ctx(actor,peer)|{'prev':[peer]}
   if record['kind']=='reverse_add_opinion_modifier':
    # The primitive reverses only the native opinion effect. The following
    # explicit target scope must independently record peer -> actor via PREV.
    execute(nodes,r,context)
    owner,partner=peer,actor
   else:
    execute(nodes,r,context);owner,partner=actor,peer
   wanted=record['kind']!='remove_opinion_modifier'
   flags=r['countries'][owner]['flags'];opinions=r['countries'][owner]['opinion_modifiers']
   assert_(P+'legacy_known@'+partner in flags,'site records exact known pair')
   assert_((P+'legacy_no_ties@'+partner in flags)==wanted,'site records exact active state')
   assert_(((partner,'no_diplomatic_ties') in opinions)==wanted,'original native opinion effect preserved')
   for country,data in r['countries'].items():
    for field in ('flags','opinion_modifiers'):
     now=deepcopy(data[field]);old=deepcopy(before['countries'][country][field])
     if country==owner:
      if field=='flags':
       now.discard(P+'legacy_known@'+partner);old.discard(P+'legacy_known@'+partner)
       now.discard(P+'legacy_no_ties@'+partner);old.discard(P+'legacy_no_ties@'+partner)
      else:now.discard((partner,'no_diplomatic_ties'));old.discard((partner,'no_diplomatic_ties'))
     assert_(now==old,'site preserves every other directed pair and native opinion')

def current_guard_boundaries():
 def pair(r,name,actor='A',peer='B'):
  return condition([(P+'legacy_'+name,'=','yes')],r,ctx(actor,peer)|{'prev':[peer]})
 r=state();legacy_no_ties(r,'A','B')
 assert_(pair(r,'pair_active') and not pair(r,'pair_active','A','C'),'fresh directed history separates third country')
 assert_(not decision(r,'mission_charge') and decision(r,'mission_charge','A','C'),'fresh unrelated partner is not blocked by scalar no_ties')
 r=state();legacy_no_ties(r,'B','A')
 assert_(not decision(r,'mission_charge') and decision(r,'mission_charge','A','C'),'reverse-only restriction closes exact bilateral pair')
 r=state();r['global_flags'].clear();r['countries']['A']['opinion_modifiers'].add(('B','no_diplomatic_ties'))
 assert_(pair(r,'pair_unknown_restricted') and not pair(r,'pair_active'),'unknown save does not invent specific active restriction')
 assert_(not decision(r,'mission_charge') and not decision(r,'mission_charge','A','C'),'unknown save fails closed even for uncertain third partner')
 assert_(not pair(r,'pair_unknown_restricted','B','A'),'scalar restriction remains directed rather than global')
 # The status label keeps ambiguous old-save state separate from confirmed rupture.
 texts=one(parse((ROOT/FILES[8]).read_text(encoding='utf-8-sig'))[0][2],'name')
 assert_(texts==P+'relation_label','current diplomatic status label identity')
 # A later exact bilateral agreement can resolve one old pair without claiming
 # that the other country's historic opinion restrictions have disappeared.
 r['countries']['A']['opinion_modifiers'].add(('D','no_diplomatic_ties'))
 establish(r)
 assert_(pair(r,'pair_known') and not pair(r,'pair_restricted'),'mutual current review resolves one unknown old pair')
 assert_(('D','no_diplomatic_ties') in r['countries']['A']['opinion_modifiers'] and pair(r,'pair_unknown_restricted','A','D'),
  'mutual review does not adopt or remove another unknown historic restriction')
 assert_(decision(r,'mission_charge') and not decision(r,'mission_charge','A','D'),'reviewed pair allowed while unknown pair still closed')
 r=state();r['global_flags'].clear()
 assert_(not pair(r,'pair_restricted') and decision(r,'mission_charge'),'old save with no country-wide modifier safely permits an unrestricted pair')
 for pp,wanted in ((9.999,False),(10.,True),(10.001,True)):
  r=state();r['countries']['A']['pp']=pp
  assert_(decision(r,'mission_charge')==wanted,'native inclusive PP boundary')
 for level,minimum in (('charge',.01),('ambassador',.02)):
  for amount,wanted in ((minimum-.000001,False),(minimum,True),(minimum+.000001,True)):
   r=state();r['countries']['A']['variables']['treasury']=amount
   assert_(decision(r,'mission_'+level)==wanted,'documented explicit treasury inclusive boundary')
 for text in ('check_variable = { treasury >= 0 }','has_political_power >= 10',
  'has_opinion_modifier = { target = PREV modifier = no_diplomatic_ties }'):
  try:condition(parse(text),state(),ctx()|{'prev':['B']})
  except AssertionError:pass
  else:raise AssertionError(('Unsupported native syntax accepted by model',text))
  assert_(True,'strict adapter rejects native-incompatible grammar')

def primary_source_constraints():
 history=ROOT/FILES[-1]
 assert_(parse(history.read_text(encoding='utf-8-sig'))==[('set_global_flag','=',P+'legacy_registry_initialized')],
  'fresh initialization has one history-only global receipt')
 matches=[]
 for root in ('common','events','history'):
  for file in (ROOT/root).rglob('*.txt'):
   if re.search(rb'\bset_global_flag\s*=\s*eon_diplomatic_relations_legacy_registry_initialized\b',file.read_bytes()):matches.append(file)
 assert_(matches==[history],'on_startup daily or load cannot falsely certify old-save history')
 triggerdoc=(NATIVE/'documentation/triggers_documentation.md').read_text(encoding='utf-8-sig')
 opinion=triggerdoc.split('\n## has_opinion_modifier\n',1)[1].split('\n## ',1)[0]
 assert_('* Supported Targets: none' in opinion,'installed scalar opinion query has no target API')
 explicit=triggerdoc.split('\n## check_variable\n',1)[1].split('\n## ',1)[0]
 assert_('greater_than_or_equals' in explicit and 'less_than_or_equals' in explicit,'installed explicit inclusive variable comparisons')
 effectdoc=(NATIVE/'documentation/effects_documentation.md').read_text(encoding='utf-8-sig')
 globalflag=effectdoc.split('\n## set_global_flag\n',1)[1].split('\n## ',1)[0]
 assert_('* Supported Scopes: any' in globalflag,'installed global flag valid in general history scope')
 for path in FILES:
  if path.endswith('.yml'):continue
  nodes=parse((ROOT/path).read_text(encoding='utf-8-sig'))
  def walk(nodes):
   for key,operator,value in nodes:
    yield key,operator,value
    if isinstance(value,list):yield from walk(value)
  for key,operator,value in walk(nodes):
   assert_(operator not in ('>=','<='),'current relations game grammar has no unsupported inclusive shorthand')
   if key=='has_opinion_modifier':assert_(isinstance(value,str),'current relations opinion query is scalar only')

def main():
 sites=source_inventory();effects_in_both_frames(sites);current_guard_boundaries();primary_source_constraints()
 paths=sorted(set(LEGACY)|set(FILES)|{'common/scripted_triggers/eon_per_usa_normalization_triggers.txt'})
 print(json.dumps({'all_passed':True,'source_assertions':sum(checks.values()),'groups':dict(checks),
  'real_mutation_sites':len(sites),'legacy_real_mutation_sites':sum(LEGACY.values()),'tooltip_only_sites':2,
  'site_inventory':[{k:v for k,v in item.items() if k!='source'} for item in sites],
  'source_sha256':{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in paths},
  'native_runtime':False,'native_old_save_migration_verified':False,'native_new_registry_save_load_verified':False,
  'proof_scope':'current exact pair metadata at every real legacy/generic no-ties mutation, current strict AST guards; native compile, campaign and save/load require separate acceptance'},indent=2))

if __name__=='__main__':main()
