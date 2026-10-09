"""Execute actual finished-fuel source AST; numeric/clock/UI remain boundaries.

No copied business algorithm: the game's effects and predicates drive this
adapter. Country_event records sender/target/delay. It does not run native AI,
deliver human popups, advance flags, save/load, or simulate multiplayer.
Float32 is a deliberately explicit magnitude/rounding mode, not a claim that
every native operation uses exactly this representation.
"""
from pathlib import Path
import importlib.util
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
FILES = (
    'common/scripted_effects/eon_nuclear_fuel_trade_effects.txt',
    'common/scripted_triggers/eon_nuclear_fuel_trade_triggers.txt',
    'events/eon_nuclear_fuel_trade_events.txt',
)
P = 'eon_nuclear_fuel_trade_'


def executor(overrides=None):
    path = ROOT / 'tools/validation/diplomacy_package_27/_model.py'
    spec = importlib.util.spec_from_file_location('nuclear_fuel_trade_base', path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    for rel, target in zip(FILES[:2], ('effects', 'triggers')):
        text = (overrides or {}).get(rel, (ROOT / rel).read_text(encoding='utf-8-sig'))
        getattr(m, target).update({k:v for k,o,v in m.ast(text)})
    m.events = {m.one(v, 'id'):v for k,o,v in m.ast((ROOT/FILES[2]).read_text(encoding='utf-8-sig')) if k=='country_event'}
    base_execute, base_write, base_trigger = m.execute, m.write, m.trigger

    def write(s, c, key, val, temp=False):
        if s.get('float32'):
            val = struct.unpack('f', struct.pack('f', float(val)))[0]
        base_write(s, c, key, val, temp)

    def execute(nodes, s, c):
        i = 0
        while i < len(nodes):
            group = [nodes[i]]; i += 1
            if group[0][0] == 'if':
                while i < len(nodes) and nodes[i][0] in ('else_if', 'else'):
                    group.append(nodes[i]); i += 1
            k,op,v = group[0]
            if k in ('update_energy_dirty_variable','ingame_update_setup','eon_uranium_refresh_energy'):
                s.setdefault('refresh_calls', []).append((c['scope'], k))
            elif k=='eon_uranium_initialize':
                # Shared geology/old-unit migration is an explicit integration
                # boundary, never a second implementation of its business rules.
                s.setdefault('unit_initialization_calls',[]).append(c['scope'])
                owner=s['countries'][c['scope']]
                if 'eon_uranium_reactor_stock_in_kg' not in owner['flags']:
                    callback=s.get('unit_initialization_boundary')
                    assert callable(callback),'Declare stock units or provide the explicit migration boundary fixture'
                    callback(s,c['scope'])
                    assert 'eon_uranium_reactor_stock_in_kg' in owner['flags']
            elif k == 'country_event':
                ident = v if isinstance(v, str) else m.one(v, 'id')
                delay = {} if isinstance(v, str) else {a:b for a,o,b in v if a in ('hours','days')}
                s['events'].append(dict(id=ident, target=c['scope'], sender=c['prev'][0] if c['prev'] else c['scope'], delay=delay))
            else:
                base_execute(group, s, c)

    def trigger(nodes, s, c):
        i = 0
        while i < len(nodes):
            group = [nodes[i]]; i += 1
            if group[0][0] == 'if':
                while i < len(nodes) and nodes[i][0] in ('else_if', 'else'):
                    group.append(nodes[i]); i += 1
            if group[0][0] in ('is_embargoed_by','is_embargoing'):
                field='embargoed_by' if group[0][0]=='is_embargoed_by' else 'embargoing'
                if m.resolve(s,c,group[0][2]) not in s['countries'][c['scope']].get(field,set()):
                    return False
            elif group[0][0] in ('divide_temp_variable','clamp_temp_variable'):
                execute(group, s, c)
            elif not base_trigger(group, s, c):
                return False
        return True

    m.write, m.execute, m.trigger = write, execute, trigger
    return m


def state(m, cash=500, fuel=10000, float32=False, precision=None):
    s = m.state({i:(0,0) for i in (1,2,3)})
    s['float32'] = float32
    if precision is not None:
        s['precision'] = precision
    for i in s['countries']:
        s['countries'][i]['vars'].update(treasury=cash, var_reactor_material_stockpile=fuel)
        s['countries'][i]['flags'].add('eon_uranium_reactor_stock_in_kg')
    s['events'] = []
    return s


def invoke(m, s, name, actor=1, peer=None, temps=None):
    s['temp'] = dict(temps or {})
    m.execute([(P+name, '=', 'yes')], s, m.context(actor, peer))


def check(m, s, name, actor=1, peer=None, temps=None):
    s['temp'] = dict(temps or {})
    return m.trigger([(P+name, '=', 'yes')], s, m.context(actor, peer))


def quote(s, amount=500, price=.5, actor=1, peer=2):
    s['countries'][actor]['vars'].update(nuclear_fuel_selling_selected_TAG=peer,
                                      temp_nuclear_fuel_ammount=amount,
                                      temp_nuclear_fuel_price=price)


def send(m, s, amount=500, price=.5, actor=1, peer=2):
    quote(s, amount, price, actor, peer)
    invoke(m, s, 'send', actor)
    return s


def respond(m, s, choice='accept', kind=1, actor=2, peer=1):
    invoke(m, s, choice, actor, peer, {P+'response_kind':kind})


def acknowledge(m, s, kind=1, outcome=2, actor=1, peer=2):
    invoke(m, s, 'acknowledge', actor, peer,
           {P+'response_kind':kind, P+'result_kind':outcome})


def assets(s):
    cash = fuel = 0
    for d in s['countries'].values():
        v = d['vars']
        cash += v.get('treasury',0) + v.get(P+'cash_escrow',0) + v.get(P+'cash_refund_due',0)
        fuel += v.get('var_reactor_material_stockpile',0) + v.get(P+'fuel_escrow',0) + v.get(P+'fuel_refund_due',0)
    return cash, fuel
