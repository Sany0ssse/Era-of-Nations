"""Pure source grammar and exact byte inverses for six zero-weight decisions."""
from pathlib import Path
import hashlib, re

ROOT = Path(__file__).resolve().parents[3]
SOURCE = 'common/decisions/eon_framework_negotiation_decisions.txt'
TRIGGERS = 'common/scripted_triggers/eon_framework_negotiation_triggers.txt'
CATEGORY = 'common/decisions/categories/eon_framework_negotiation_categories.txt'
IDS = tuple('eon_framework_negotiation_' + kind + '_' + action
            for kind in ('trade','investment') for action in ('withdraw','end_request','status'))
PREDICATES = ('allowed','target_root_trigger','target_trigger','visible','available')
TOKEN = re.compile(r'\s+|#[^\n]*|"(?:\\.|[^"\\])*"|>=|<=|!=|[{}=<>]|[^\s{}=<>#]+')
def sha(data): return hashlib.sha256(data).hexdigest()
def parse(text):
 tokens=[(m[0],m.start(),m.end()) for m in TOKEN.finditer(text.lstrip('\ufeff'))
         if not m[0].isspace() and not m[0].startswith('#')]
 pos=0
 def group(nested=False):
  nonlocal pos
  out=[]
  while pos<len(tokens):
   key,start,end=tokens[pos]
   if key=='}':
    if not nested: raise ValueError('unmatched close')
    pos+=1; return out,end
   pos+=1
   if pos>=len(tokens) or tokens[pos][0] not in ('=','>','<','>=','<=','!='):
    raise ValueError('expected operator for '+key)
   op=tokens[pos][0];pos+=1
   if pos>=len(tokens):raise ValueError('missing value')
   value,_,end=tokens[pos];pos+=1
   if value=='{':value,end=group(True)
   elif value in ('}','=','>','<','>=','<=','!='):raise ValueError('invalid scalar')
   out.append({'key':key,'op':op,'value':value,'start':start,'end':end})
  if nested:raise ValueError('unclosed block')
  return out,len(text)
 return group()[0]
def fields(nodes):
 out={}
 for n in nodes:
  if n['key'] in out:raise ValueError('duplicate field '+n['key'])
  out[n['key']]=n
 return out
def shape(nodes):
 return [(n['key'],n['op'],shape(n['value']) if isinstance(n['value'],list) else n['value']) for n in nodes]
def decisions(data):
 text=data.decode('utf-8-sig');top=fields(parse(text))
 return text,fields(top['eon_framework_negotiation_category']['value'])

SCOPES={'THIS','ROOT','PREV','FROM'}
LOGIC={'AND','OR','NOT','if','else_if','else','limit'}
READ={'always','exists','is_ai','tag','original_tag','has_country_flag','has_war_with'}
ARGS={'check_variable':{'var','value','compare'},'has_country_leader':{'name'}}
def pure(nodes,registry,closure=None,stack=()):
 closure={} if closure is None else closure
 for n in nodes:
  k,v=n['key'],n['value']
  if k=='has_political_power' and not isinstance(v,list) and n['op'] in ('=','<','>','<=','>='):
   continue
  if n['op']!='=':raise ValueError('unexpected direct predicate comparison: '+k)
  if k in registry:
   if v not in ('yes','no') or k in stack:raise ValueError('invalid helper/cycle: '+k)
   closure[k]=registry[k]
   pure(registry[k]['value'],registry,closure,stack+(k,))
  elif k in SCOPES or k in LOGIC:
   if not isinstance(v,list):raise ValueError('expected scoped body: '+k)
   pure(v,registry,closure,stack)
  elif k in READ:
   if isinstance(v,list):raise ValueError('expected read scalar: '+k)
  elif k in ARGS:
   if not isinstance(v,list):raise ValueError('expected arguments: '+k)
   for arg in v:
    if isinstance(arg['value'],list):raise ValueError('nested write in read: '+k)
    if k=='has_country_leader' and arg['key'] not in ARGS[k]:raise ValueError('unknown leader argument')
   if k=='check_variable' and len(v)!=1:
    if set(fields(v))!=ARGS[k]:raise ValueError('unknown variable read arguments')
  elif k=='custom_trigger_tooltip':
   if not isinstance(v,list):raise ValueError('tooltip body')
   pure([x for x in v if x['key']!='tooltip'],registry,closure,stack)
  else:raise ValueError('non-whitelisted predicate: '+k)
 return closure

def certify(before,candidate,trigger_bytes,category_bytes):
 btext,bdec=decisions(before);ctext,cdec=decisions(candidate)
 registry=fields(parse(trigger_bytes.decode('utf-8-sig')))
 cat=fields(fields(parse(category_bytes.decode('utf-8-sig')))['eon_framework_negotiation_category']['value'])
 assert shape(cat['allowed']['value'])==[('always','=','yes')]
 assert shape(cat['visible']['value'])==[('exists','=','yes')]
 assert set(bdec)==set(cdec)
 closures={};spans=[]
 for ident,decision in bdec.items():
  bf=fields(decision['value']);cf=fields(cdec[ident]['value'])
  if ident not in IDS:
   assert shape(decision['value'])==shape(cdec[ident]['value']);continue
  assert shape(bf['ai_will_do']['value'])==[('factor','=','0')]
  assert shape(bf['target_root_trigger']['value'])==[('exists','=','yes')]
  assert shape(cf['target_root_trigger']['value'])==[('exists','=','yes'),('is_ai','=','no')]
  assert bf.keys()==cf.keys()
  for key in bf:
   if key!='target_root_trigger':assert shape([bf[key]])==shape([cf[key]])
  closure={}
  for key in PREDICATES:pure(bf[key]['value'],registry,closure)
  closures[ident]={k:{'body_sha256':sha(trigger_bytes.decode('utf-8-sig')[v['start']:v['end']].encode('utf-8'))} for k,v in closure.items()}
  old=bf['target_root_trigger'];new=cf['target_root_trigger']
  spans.append({'id':ident,'before_start':len(btext[:old['start']].encode()),'before_end':len(btext[:old['end']].encode()),
                'after_start':len(ctext[:new['start']].encode()),'after_end':len(ctext[:new['end']].encode()),
                'line':btext[:old['start']].count('\n')+1,
                'before_hex':btext[old['start']:old['end']].encode().hex(),
                'after_hex':ctext[new['start']:new['end']].encode().hex()})
 # Character AST spans are decoded without BOM. Correct to whole raw offsets.
 bom=3 if before.startswith(b'\xef\xbb\xbf') else 0
 cbom=3 if candidate.startswith(b'\xef\xbb\xbf') else 0
 assert bom==cbom
 for p in spans:
  p['before_start']+=bom;p['before_end']+=bom;p['after_start']+=cbom;p['after_end']+=cbom
 inverse=candidate
 for p in sorted(spans,key=lambda p:p['after_start'],reverse=True):
  assert inverse[p['after_start']:p['after_end']]==bytes.fromhex(p['after_hex'])
  inverse=inverse[:p['after_start']]+bytes.fromhex(p['before_hex'])+inverse[p['after_end']:]
 assert inverse==before,'whole-byte inverse failed'
 return {'patches':spans,'closure':closures,'decision_count':len(bdec),
         'nonzero_weight_decisions_unchanged':sum(shape(fields(x['value'])['ai_will_do']['value'])!=[('factor','=','0')] for x in bdec.values()),
         'zero_weight_decisions_excluded_for_temp_predicates':[k for k,v in bdec.items() if k not in IDS and shape(fields(v['value'])['ai_will_do']['value'])==[('factor','=','0')]]}
