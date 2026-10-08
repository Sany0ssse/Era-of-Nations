"""Check the current package26 source graph and authority/mutation boundaries.

This checks source, not compilation or a native HOI4 save/campaign.
"""
from collections import Counter
from pathlib import Path
import hashlib,json,re
from test_relations import ROOT,P,FILES,TRIGGERS,EFFECTS,DECISIONS,HOOKS,EVENTS,parse,one,NATIVE

checks=Counter()
def assert_(test,group):
 assert test,group
 checks[group]+=1

def walk(nodes):
 for key,operator,value in nodes:
  yield key,operator,value
  if isinstance(value,list):yield from walk(value)

def fields(nodes):return {key:value for key,operator,value in nodes}

def main():
 scripts={};locales={}
 for path in FILES:
  raw=(ROOT/path).read_bytes();decoded=raw.decode('utf-8-sig')
  assert_(raw.replace(b'\r\n',b'').count(b'\n')==0,'game file CRLF '+path)
  assert_(not decoded.startswith('\ufeff'),'single or absent BOM '+path)
  assert_(not re.search(r'\bdr_',decoded),'all package IDs expanded '+path)
  if path.endswith('.yml'):
   assert_(raw.startswith(b'\xef\xbb\xbf'),'locale UTF8 BOM '+path)
   lang=Path(path).parent.name
   assert_(decoded.splitlines()[0]=='l_'+lang+':','locale header '+lang)
   entries=re.findall(r'^\s*('+P+r'[\w.]+):\d+\s+"([^\r\n]*)"\s*$',decoded,re.M)
   keys=[key for key,value in entries]
   assert_(len(keys)==len(set(keys)),'unique locale IDs '+lang)
   assert_(len(entries)==len(decoded.splitlines())-1,'well formed complete locale '+lang)
   locales[lang]=dict(entries)
   for key,value in entries:
    assert_(not any(word in value.lower() for word in ('targeted decision','native simulation','callback','quarantine','maximum eight','8 миссий','техническ')),'player text has diplomatic meaning '+key+' '+lang)
  else:
   scripts[path]=parse(decoded)
   assert_(len(scripts[path])>0,'balanced nonempty script '+path)
 assert_(set(locales['english'])==set(locales['russian']),'locale language parity')
 helpers=set(TRIGGERS)|set(EFFECTS)
 for path,nodes in scripts.items():
  for name,op,value in walk(nodes):
   if name.startswith(P) and value in ('yes','no'):
    assert_(name in helpers,'resolved helper '+name)
   assert_(name not in ('get_country_flag','every_country','every_other_country','white_peace','declare_war_on','create_faction','leave_faction','remove_from_faction','add_to_faction'),'no foreign/native authority '+name)
 for name,body in EFFECTS.items():
  for command,op,value in walk(body):
   if command in ('set_variable','add_to_variable','subtract_from_variable','clear_variable','clamp_variable'):
    if isinstance(value,list):variable=one(value,'var') if command=='clamp_variable' else value[0][0]
    else:variable=value
    assert_(variable.startswith(P) or variable=='treasury','persistent variable mutation owned '+name)
   if command in ('set_country_flag','clr_country_flag'):
    flag=one(value,'flag') if isinstance(value,list) else value
    assert_(flag.startswith(P),'persistent flag mutation owned '+name)
    if isinstance(value,list):
     assert_(fields(value)=={'flag':flag,'value':'1','days':'30'},'request exact finite window '+name)
   if command in ('add_to_array','remove_from_array'):
    assert_(one(value,'array').startswith(P),'array mutation owned '+name)
   if command in ('add_opinion_modifier','remove_opinion_modifier'):
    assert_(one(value,'modifier')=='no_diplomatic_ties','only diplomatic legacy policy mutation '+name)
   if command=='country_event':assert_(one(value,'id') in EVENTS,'resolved informational notice '+name)
 for name,body in DECISIONS.items():
  assert_(one(body,'cost')=='0','no double native decision cost '+name)
  for section in ('visible','available','complete_effect'):
   frame=one(one(body,section),'FROM');pair=one(frame,'PREV')
   assert_(isinstance(pair,list),'exact decision country frame '+name+' '+section)
  available=one(one(one(body,'available'),'FROM'),'PREV')
  completion=one(one(one(body,'complete_effect'),'FROM'),'PREV')
  guarded=one(completion,'if');limit=one(guarded,'limit')
  ready=[key for key,op,value in available if key.startswith(P) and value=='yes']
  assert_(len(ready)==1 and (ready[0],'=','yes') in limit,'current execution repeats availability '+name)
  assert_(all(key in ('set_temp_variable','if') for key,op,value in completion),'no mutation before current guard '+name)
  if name.startswith(P+'accept_'):
   assert_(any(key=='check_variable' and any(v==P+'selected_response_kind' for k,o,v in value) for key,op,value in limit),'accept type matched current record '+name)
  assert_(name in locales['english'] and name+'_desc' in locales['english'],'decision text resolves '+name)
 for eventid,body in EVENTS.items():
  assert_(one(body,'is_triggered_only')=='yes','notice only triggered '+eventid)
  assert_(all(key in ('id','title','desc','is_triggered_only','option') for key,op,value in body),'notice has no immediate transition '+eventid)
  for option in [value for key,op,value in body if key=='option']:
   assert_(set(fields(option))=={'name'},'notice click cannot authorize '+eventid)
   assert_(one(option,'name') in locales['english'],'notice button resolves '+eventid)
  assert_(one(body,'title') in locales['english'] and one(body,'desc') in locales['english'],'notice text resolves '+eventid)
 labels=scripts[FILES[8]]
 defined=set()
 for key,op,body in labels:
  assert_(key=='defined_text','semantic status definition')
  defined.add(one(body,'name'))
  for name,operator,value in body:
   if name=='text':assert_(one(value,'localization_key') in locales['english'],'semantic state text resolves')
 for lang,entries in locales.items():
  for label in re.findall(r'\[('+P+r'\w+_label)\]', '\n'.join(entries.values())):
   assert_(label in defined,'UI status label resolves '+lang+' '+label)
 # AST structure: daily/monthly work follows existing partner scopes only.
 for update in ('daily_update','monthly_update','annexed_owner'):
  loops=[value for key,op,value in EFFECTS[P+update] if key=='for_each_scope_loop']
  assert_(len(loops)==1 and one(loops[0],'array')==P+'partners','only tracked countries iterated '+update)
 for periodic in ('on_daily','on_monthly'):
  effect=one(HOOKS[periodic],'effect')
  assert_(len(effect)==1 and effect[0][0] in EFFECTS,'single namespace periodic callback '+periodic)
 # Every pending duty stores recipient + record + head in aligned source append/remove paths.
 appended=[one(value,'array') for command,op,value in EFFECTS[P+'mark_departure'] if command=='add_to_array']
 removed=[one(value,'array') for command,op,value in walk(EFFECTS[P+'report_departure']) if command=='remove_from_array']
 trio=[P+'departure_'+suffix for suffix in ('partners','records','heads')]
 assert_(appended==trio and removed==trio,'departure queue three source arrays aligned')
 assert_(not any(key in ('clear_array','resize_array') for key,op,value in walk(EFFECTS[P+'mark_departure'])),'new recall cannot clear old records')
 # Installed documentation is corroboration of vocabulary, not a native parser result.
 docs={};effectdoc=NATIVE/'documentation/effects_documentation.md'
 if effectdoc.exists():
  raw=effectdoc.read_bytes();text=raw.decode('utf-8-sig')
  for symbol in ('for_each_loop','for_each_scope_loop','add_to_array','remove_from_array','set_country_flag','clamp_variable'):
   assert_(symbol in text,'installed primary effect API '+symbol)
  docs[str(effectdoc)]=hashlib.sha256(raw).hexdigest()
 print(json.dumps({'all_passed':True,'source_assertions':sum(checks.values()),'groups':dict(checks),
  'decisions':len(DECISIONS),'informational_events':len(EVENTS),'game_files':len(FILES),
  'native_compilation_verified':False,'installed_api_document_sha256':docs,
  'source_sha256':{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in FILES}},indent=2))

if __name__=='__main__':main()
