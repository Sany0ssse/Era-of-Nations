"""Small, read-only source audit for nine human diplomacy adapters."""
from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parents[3]
SOURCE = 'common/decisions/eon_diplomatic_relations_decisions.txt'
BEFORE_SHA = '677ab4dac6e12f952b0a7db376cb7268a8c613dcb05ada491ebe91457986efba'
IDS = tuple('eon_diplomatic_relations_' + x for x in (
    'status', 'propose', 'propose_head', 'withdraw', 'recall',
    'persona_non_grata', 'close', 'close_host', 'break'))
INPUTS = (
    SOURCE,
    'common/scripted_triggers/eon_diplomatic_relations_triggers.txt',
    'common/scripted_triggers/00_political_triggers.txt',
    'common/scripted_diplomatic_actions/eon_diplomatic_relations_ui_actions.txt',
    'common/decisions/categories/eon_diplomatic_relations_categories.txt',
    'common/decisions/eon_consultation_ui_decisions.txt',
    'common/decisions/eon_framework_negotiation_decisions.txt',
)
PREDICATES = ('allowed', 'visible', 'available', 'target_root_trigger', 'target_trigger')
TOKEN = re.compile(r'\s+|\#[^\n]*|"(?:\\.|[^"\\])*"|>=|<=|!=|[{}=<>]|[^\s{}=<>#"]+')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def parse(text):
    """Preserve character spans; recognize blocks, scalar comparisons and lists."""
    ts = [(m[0], m.start(), m.end()) for m in TOKEN.finditer(text)
          if not m[0].isspace() and not m[0].startswith('#')]
    pos = 0
    def group(nested=False):
        nonlocal pos
        out = []
        while pos < len(ts):
            key, start, finish = ts[pos]
            if key == '}':
                if not nested:
                    raise ValueError('unmatched close')
                pos += 1
                return out, finish
            if key in ('{', '=', '<', '>', '<=', '>=', '!='):
                raise ValueError('expected key: ' + key)
            pos += 1
            if pos >= len(ts) or ts[pos][0] not in ('=', '<', '>', '<=', '>=', '!='):
                out.append({'key': key, 'op': None, 'value': None, 'start': start, 'end': finish})
                continue
            op = ts[pos][0]
            pos += 1
            if pos >= len(ts):
                raise ValueError('missing value')
            value, _, finish = ts[pos]
            pos += 1
            if value == '{':
                value, finish = group(True)
            elif value in ('}', '=', '<', '>', '<=', '>=', '!='):
                raise ValueError('invalid value')
            out.append({'key': key, 'op': op, 'value': value, 'start': start, 'end': finish})
        if nested:
            raise ValueError('unclosed block')
        return out, len(text)
    return group()[0]

def fields(nodes):
    result = {}
    for node in nodes:
        if node['key'] in result:
            raise ValueError('duplicate field ' + node['key'])
        result[node['key']] = node
    return result

def decisions(text):
    top = fields(parse(text))
    return fields(top['eon_diplomatic_relations_category']['value'])

def trigger_registry():
    result = {}
    for rel in INPUTS[1:3]:
        text = (ROOT / rel).read_text(encoding='utf-8-sig')
        for node in parse(text):
            if node['key'] in result:
                raise ValueError('duplicate trigger ' + node['key'])
            result[node['key']] = (rel, text, node)
    return result

SCOPES = {'THIS', 'ROOT', 'PREV', 'FROM', 'PER'}
LOGIC = {'AND', 'OR', 'NOT', 'if', 'else_if', 'else', 'limit'}
READ_SCALARS = {'always', 'exists', 'is_ai', 'tag', 'original_tag',
                'has_war_with', 'has_country_flag', 'has_global_flag',
                'has_opinion_modifier', 'has_idea', 'has_political_power'}

def pure(nodes, registry, closure=None, stack=()):
    """Whitelist supported read-only grammar; reject every unknown operation."""
    closure = {} if closure is None else closure
    for node in nodes:
        key, value = node['key'], node['value']
        if node['op'] != '=':
            raise ValueError('unexpected trigger comparison outside read arguments: ' + key)
        if key in registry:
            if value not in ('yes', 'no'):
                raise ValueError('nonboolean helper: ' + key)
            if key in stack:
                raise ValueError('helper cycle: ' + key)
            if key not in closure:
                rel, text, definition = registry[key]
                closure[key] = {
                    'path': rel, 'line': text[:definition['start']].count('\n') + 1,
                    'body_sha256': sha(text[definition['start']:definition['end']].encode('utf-8')),
                }
                pure(definition['value'], registry, closure, stack + (key,))
        elif key in SCOPES | LOGIC:
            if not isinstance(value, list):
                raise ValueError('scalar scope/logic: ' + key)
            pure(value, registry, closure, stack)
        elif key in READ_SCALARS:
            if isinstance(value, list) or value is None:
                raise ValueError('invalid read-only scalar: ' + key)
        elif key in ('check_variable', 'is_in_array'):
            if not isinstance(value, list) or not value:
                raise ValueError('invalid read arguments: ' + key)
            for arg in value:
                if arg['op'] not in ('=', '<', '>', '<=', '>=', '!=') or isinstance(arg['value'], list) or arg['value'] is None:
                    raise ValueError('non-scalar read argument: ' + key)
        elif key == 'custom_trigger_tooltip':
            if not isinstance(value, list):
                raise ValueError('invalid tooltip')
            tip = [x for x in value if x['key'] == 'tooltip']
            if len(tip) != 1 or tip[0]['op'] != '=' or not isinstance(tip[0]['value'], str):
                raise ValueError('invalid tooltip key')
            pure([x for x in value if x['key'] != 'tooltip'], registry, closure, stack)
        else:
            raise ValueError('unknown or impure trigger operation: ' + key)
    return closure

def audit_source(text):
    registry = trigger_registry()
    ds = decisions(text)
    ui = fields(parse((ROOT / INPUTS[3]).read_text(encoding='utf-8-sig')))
    actions = fields(ui['scripted_diplomatic_actions']['value'])
    result = {}
    for id in IDS:
        fs = fields(ds[id]['value'])
        ai = fs['ai_will_do']['value']
        if [(x['key'], x['op'], x['value']) for x in ai] != [('factor', '=', '0')]:
            raise ValueError('not literal-zero AI: ' + id)
        for disallowed in ('days_mission_timeout', 'days_remove', 'days_re_enable', 'timeout_effect', 'remove_effect', 'cancel_trigger'):
            if disallowed in fs:
                raise ValueError('mission/cadence field: ' + id)
        closure = {}
        for key in PREDICATES:
            pure(fs[key]['value'], registry, closure)
        ui_id = id.replace('eon_diplomatic_relations_', 'eon_diplomatic_relations_ui_', 1)
        if ui_id not in actions:
            raise ValueError('missing direct UI: ' + id)
        # Existing complete-effect/business helper text is bound, never rewritten.
        result[id] = {'closure': closure, 'direct_ui_id': ui_id,
                      'direct_ui_line': (ROOT / INPUTS[3]).read_text(encoding='utf-8-sig')[:actions[ui_id]['start']].count('\n') + 1}
    return result
