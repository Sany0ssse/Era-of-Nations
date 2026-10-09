"""Prepare a source-bound private native fuel fixture. Never embeds or launches.

The immutable source export is the input. Output overlays deliberately freeze
weekly economy/energy and native fuel GUI AI while the three-country experiment
runs. Original energy.1/10 policies, queues, options and results are untouched.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter
import native_state_trace as state_trace

NS = 'eon_private_fuel_probe'
MARKER = 'EON_PRIVATE_FUEL_PROBE'
P = 'eon_nuclear_fuel_trade_'
UNTOUCHED_UNIT_ON_ACTIONS = {
    'common/on_actions/00_partisans.txt',
    'common/on_actions/99_EGY_on_actions.txt',
    'common/on_actions/99_PER_on_actions.txt',
}


def should_control_on_action(rel, hook):
    return (rel not in UNTOUCHED_UNIT_ON_ACTIONS and
            (hook.startswith(('on_weekly','on_monthly')) or
             (rel=='common/on_actions/00_ai_gui_on_actions.txt' and hook=='on_daily')))


def emit_native_ast(nodes, depth=0):
    """Emit lexical native scalars without applying a second JSON escape pass.

    The shared game parser removes outer quotes but deliberately leaves native
    backslash escapes untouched. Re-quoting a parsed string must preserve those
    lexical escapes, including embedded division names and templates.
    """
    rows = []
    for key, op, value in nodes:
        if key == '__item__':
            rows.append(' ' * depth + str(value))
            continue
        if isinstance(value, list):
            rows += [' ' * depth + key + ' ' + op + ' {',
                     emit_native_ast(value, depth + 1), ' ' * depth + '}']
        else:
            scalar = str(value)
            if key == 'log' or not scalar or re.search(r'\s', scalar):
                # The parser's strip('"') also removes the quote of a final
                # native \" inside the outer string. An odd trailing escape
                # therefore needs that lexical quote restored before closing.
                trailing = len(scalar) - len(scalar.rstrip('\\'))
                if trailing % 2:
                    scalar += '"'
                scalar = '"' + scalar + '"'
            rows.append(' ' * depth + key + ' ' + op + ' ' + scalar)
    return '\n'.join(rows)


def same_ast(left, right):
    """Compare ordered ASTs independently of tuples versus copied JSON lists."""
    return json.loads(json.dumps(left)) == json.loads(json.dumps(right))


def cash_api_overlay(original):
    """Freeze only the current recipient's ordinary cash API in a private run.

    Fuel transaction effects use direct treasury arithmetic and remain outside
    this API. ROOT may be another country when THIS receives an ordinary cost.
    """
    result=json.loads(json.dumps(original))
    matches=[row for row in result if row[0]=='modify_treasury_effect']
    assert len(matches)==1 and isinstance(matches[0][2],list), 'One actual ordinary cash API required'
    body=json.loads(json.dumps(matches[0][2]))
    allowed=[['NOT','=',[['AND','=',[['has_global_flag','=',NS+'_active'],
               ['OR','=',[['tag','=','USA'],['tag','=','HOL']]]]]]]]
    blocked='EON_PRIVATE_FUEL_CASH BLOCKED api=modify_treasury_effect ROOT=[ROOT.GetTag] THIS=[THIS.GetTag] FROM=[FROM.GetTag] cash=[?treasury|8] change=[?treasury_change|8]'
    replacement=[['if','=',[['limit','=',allowed]]+body],['else','=',[['log','=',blocked]]]]
    matches[0][2]=replacement
    return result, {'source':'common/scripted_effects/00_budget_effects.txt',
                    'cash_api_selector':['modify_treasury_effect'],
                    'original_source_ast':json.loads(json.dumps(original)),
                    'original_ast':body,'transformed_ast':replacement,
                    'reason':'Freeze unrelated ordinary treasury changes for THIS USA/HOL only while the private fuel probe is active; log each blocked change. Production fuel arithmetic stays original.'}


def validate_cash_api_overlay(played, declaration):
    """Reject extra code, broadened guards, or changes outside the one API."""
    assert declaration['source']=='common/scripted_effects/00_budget_effects.txt'
    expected,control=cash_api_overlay(declaration['original_source_ast'])
    for field in ('cash_api_selector','original_ast','transformed_ast'):
        assert same_ast(declaration[field],control[field]), 'Changed ordinary cash control '+field
    assert same_ast(played,expected), 'Ordinary cash overlay changed outside the declared recipient guard'


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source-root', required=True, type=Path)
    cli.add_argument('--out', required=True, type=Path)
    cli.add_argument('--startup', action='store_true', help='Otherwise a merged fixture must queue USA event .1 after its physical tests.')
    cli.add_argument('--result-aware', action='store_true', help='Poll private outcome/acknowledgement with nominal two-hour delay and a bounded attempt counter, with a separate 68-hour deadline. Production events stay unchanged.')
    cli.add_argument('--state-trace', action='store_true', help='Add declared read-only option/poll/deadline logs; removing the islands recovers the original executable source exactly.')
    args = cli.parse_args()
    source, out = args.source_root.resolve(), args.out.resolve()
    assert source.is_dir() and (source.parent/'export-receipt.json').is_file(), 'An immutable export with receipt is required'
    assert not (out/'manifest.json').exists(), 'Preserve an existing frozen fixture; use a new output path'
    assert not (out/'launch-receipt.json').exists()
    spec = importlib.util.spec_from_file_location(NS+'_grammar', source/'tools/validation/diplomacy_completion/check_native_grammar.py')
    g = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = g
    spec.loader.exec_module(g)
    p = g.parser
    deps, bindings, predicates, files, events, labels, observations, groups = set(), {}, {}, {}, [], [], [], {}
    bridges, frame_conditions, cases, controls = {}, {}, [], []
    wait_effects, wait_triggers, wait_cases = {}, {}, []
    trace_overlays, private_trace_islands, raw_overrides = [], [], {}
    def trace(label, rel):
        if not args.state_trace:
            return ''
        insertion=state_trace.island(label)
        private_trace_islands.append({'source':rel,'label':label,'insertion':insertion})
        return insertion

    def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
    def ast(rel):
        deps.add(rel)
        return p.ast((source/rel).read_bytes())
    def walk(nodes):
        for k, op, v in nodes:
            yield k, op, v
            if isinstance(v, list): yield from walk(v)
    emit = emit_native_ast
    def bind(name, rel, selector, pred=False):
        nodes=ast(rel)
        for key in selector: nodes=p.one(nodes,key)
        target=predicates if pred else bindings
        target[name]={'source':rel,'selector':selector,'ast':json.loads(json.dumps(nodes))}
        return NS+'_'+name+' = yes'
    def event_nodes(rel, ident):
        found=[v for k,op,v in ast(rel) if k=='country_event' and p.one(v,'id')==ident]
        assert len(found)==1,ident
        return found[0]
    def bind_option(name, ident, option):
        nodes=event_nodes('events/00_Energy_events.txt',ident)
        found=[v for k,op,v in nodes if k=='option' and p.one(v,'name')==option]
        assert len(found)==1,(ident,option)
        bindings[name]={'source':'events/00_Energy_events.txt','event_id':ident,'option_name':option,'option_effect':True,
                        'ast':json.loads(json.dumps([n for n in found[0] if n[0] not in ('name','trigger','ai_chance','ai_will_do','highlight')]))}
        return NS+'_'+name+' = yes'
    def cv(name,value,compare='equals'):
        return 'check_variable = { var = '+name+' value = '+str(value)+' compare = '+compare+' }'
    def guard(label, condition, group):
        assert label not in labels
        labels.append(label); groups[label]=group
        return 'if = { limit = { '+condition+' } add_to_variable = { global.'+NS+'_passes = 1 } log = "'+MARKER+' PASS '+label+'" } else = { add_to_variable = { global.'+NS+'_fails = 1 } log = "'+MARKER+' FAIL '+label+'" }'
    def obs(label, more=''):
        assert label not in observations
        observations.append(label)
        return 'log = "'+MARKER+' OBS '+label+' ROOT=[ROOT.GetTag] THIS=[THIS.GetTag] FROM=[FROM.GetTag] cash=[?treasury] stock=[?var_reactor_material_stockpile] peer_cash=[?HOL.treasury] peer_stock=[?HOL.var_reactor_material_stockpile] phase=[?'+P+'phase] '+more+'"'
    def end(): return 'log = "'+MARKER+' END passes=[?global.'+NS+'_passes] fails=[?global.'+NS+'_fails]" set_global_flag = '+NS+'_finished clr_global_flag = '+NS+'_active'
    def event(number, actor, frm, body):
        condition='tag = '+actor+' ROOT = { tag = '+actor+' }'
        if frm: condition+=' FROM = { tag = '+frm+' }'
        frame_conditions[str(number)]={'actor':actor,'from':frm,'condition':condition}
        frame=guard('frame_'+str(number),condition,'native_frames')
        initialize=('set_variable = { global.'+NS+'_passes = 0 } set_variable = { global.'+NS+'_fails = 0 } ') if number==1 else ''
        events.append('country_event = { id = '+NS+'.'+str(number)+' hidden = yes is_triggered_only = yes immediate = { if = { limit = { NOT = { has_global_flag = '+NS+'_event_'+str(number)+'_done } } set_global_flag = '+NS+'_event_'+str(number)+'_done '+initialize+frame+' if = { limit = { '+condition+' } '+body+' } else = { log = "'+MARKER+' ABORT wrong_native_frame_'+str(number)+'" '+end()+' } } else = { log = "'+MARKER+' DUPLICATE_PRIVATE_EVENT '+str(number)+'" } } }')
    def queue(number,hours=1):return 'country_event = { id = '+NS+'.'+str(number)+' hours = '+str(hours)+' }'
    def owner_queue(peer,target,number,hours=1):
        bridge=9000+number
        assert bridge not in bridges
        bridges[bridge]=(peer,target,number)
        return peer+' = { '+queue(bridge,hours)+' }'
    def fresh():
        return ' '.join(tag+' = { NOT = { has_country_flag = '+P+'reserved } NOT = { has_country_flag = currently_considering_an_offer } '+cv(P+'partner',0)+' }' for tag in ('USA','HOL'))
    def same_assets():
        return ' '.join(tag+' = { '+cv('treasury',NS+'_cash_before')+' '+cv('var_reactor_material_stockpile',NS+'_fuel_before')+' }' for tag in ('USA','HOL'))
    def snapshots():
        return ' '.join(tag+' = { set_variable = { '+NS+'_cash_before = treasury } set_variable = { '+NS+'_fuel_before = var_reactor_material_stockpile } }' for tag in ('USA','HOL'))
    def result_wait(name, kind, quantity, own_stock, peer_stock, accepted, done):
        if not args.result_aware:
            return owner_queue('HOL','USA',done,68)
        buyer,seller=('HOL','USA') if kind==2 else ('USA','HOL')
        prepare=NS+'_wait_prepare_'+str(done)
        poll=NS+'_wait_poll_'+str(done)
        predicate=NS+'_wait_ready_'+str(done)
        ready_flag=NS+'_wait_done_'+str(done)
        poll_bridge,poll_check,deadline_bridge,deadline=10000+done,11000+done,12000+done,13000+done
        setup='set_variable = { '+NS+'_wait_case = '+str(done)+' } set_variable = { '+NS+'_wait_attempts = 0 } clr_country_flag = '+ready_flag+' '
        for tag,stock in (('USA',own_stock+quantity if accepted else own_stock),('HOL',peer_stock-quantity if accepted else peer_stock)):
            setup+=tag+' = { set_variable = { '+NS+'_wait_expected_cash = '+NS+'_cash_before } set_variable = { '+NS+'_wait_expected_stock = '+str(stock)+' } } '
        if accepted:
            setup+=buyer+' = { subtract_from_variable = { '+NS+'_wait_expected_cash = USA.'+NS+'_actual_total } } '+seller+' = { add_to_variable = { '+NS+'_wait_expected_cash = USA.'+NS+'_actual_total } } '
        wait_effects[prepare]=setup
        condition=fresh()+' '+' '.join(tag+' = { NOT = { has_country_flag = '+P+'outgoing } NOT = { has_country_flag = '+P+'incoming } '+cv(P+'phase',0)+' '+cv(P+'cash_escrow',0)+' '+cv(P+'fuel_escrow',0)+' '+cv('treasury',NS+'_wait_expected_cash')+' '+cv('var_reactor_material_stockpile',NS+'_wait_expected_stock')+' }' for tag in ('USA','HOL'))
        wait_triggers[predicate]=condition
        active=cv(NS+'_wait_case',done)+' NOT = { has_country_flag = '+ready_flag+' } NOT = { has_global_flag = '+NS+'_finished }'
        frame='tag = USA ROOT = { tag = USA } FROM = { tag = HOL }'
        ready_label='wait_ready_'+name
        finish=guard(ready_label,predicate+' = yes','result_aware_wait')+' set_country_flag = '+ready_flag+' '
        finish+='log = "'+MARKER+' WAIT_READY '+name+' ROOT=[ROOT.GetTag] THIS=[THIS.GetTag] FROM=[FROM.GetTag] attempts=[?'+NS+'_wait_attempts] cash=[?treasury|8] expected_cash=[?'+NS+'_wait_expected_cash|8] stock=[?var_reactor_material_stockpile|8] expected_stock=[?'+NS+'_wait_expected_stock|8] peer_cash=[?HOL.treasury|8] expected_peer_cash=[?HOL.'+NS+'_wait_expected_cash|8] peer_stock=[?HOL.var_reactor_material_stockpile|8] expected_peer_stock=[?HOL.'+NS+'_wait_expected_stock|8] phase=[?'+P+'phase] partner=[?'+P+'partner] peer_phase=[?HOL.'+P+'phase] peer_partner=[?HOL.'+P+'partner]" '
        finish+=owner_queue('HOL','USA',done,0)
        # Native queued hours1 has repeatedly fired in the current displayed
        # hour. A recurring pending loop must advance to a later native tick,
        # and must still terminate safely if scheduling fails to advance.
        again='HOL = { country_event = { id = '+NS+'.'+str(poll_bridge)+' hours = 2 } }'
        exhausted='add_to_variable = { global.'+NS+'_fails = 1 } log = "'+MARKER+' FAIL wait_attempt_limit_'+name+'" '+end()
        poll_trace=trace(name+'.poll','common/scripted_effects/'+NS+'_effects.txt')
        wait_effects[poll]='if = { limit = { '+active+' } if = { limit = { '+frame+' } if = { limit = { '+cv(NS+'_wait_attempts',72,'less_than')+' } add_to_variable = { '+NS+'_wait_attempts = 1 } '+poll_trace+'if = { limit = { '+predicate+' = yes } '+finish+' } else = { '+again+' } } else = { '+exhausted+' } } else = { log = "'+MARKER+' ABORT wrong_native_wait_frame_'+name+'" '+end()+' } }'
        events.append('country_event = { id = '+NS+'.'+str(poll_check)+' hidden = yes is_triggered_only = yes immediate = { '+poll+' = yes } }')
        events.append('country_event = { id = '+NS+'.'+str(poll_bridge)+' hidden = yes is_triggered_only = yes immediate = { if = { limit = { USA = { '+active+' } } if = { limit = { tag = HOL ROOT = { tag = HOL } FROM = { tag = USA } } USA = { country_event = { id = '+NS+'.'+str(poll_check)+' } } } else = { log = "'+MARKER+' ABORT wrong_native_wait_bridge_'+name+'" '+end()+' } } } }')
        events.append('country_event = { id = '+NS+'.'+str(deadline_bridge)+' hidden = yes is_triggered_only = yes immediate = { if = { limit = { USA = { '+active+' } } if = { limit = { tag = HOL ROOT = { tag = HOL } FROM = { tag = USA } } USA = { country_event = { id = '+NS+'.'+str(deadline)+' } } } else = { log = "'+MARKER+' ABORT wrong_native_deadline_bridge_'+name+'" '+end()+' } } } }')
        deadline_trace=trace(name+'.deadline','events/'+NS+'_events.txt')
        events.append('country_event = { id = '+NS+'.'+str(deadline)+' hidden = yes is_triggered_only = yes immediate = { if = { limit = { '+active+' } '+deadline_trace+'add_to_variable = { global.'+NS+'_fails = 1 } log = "'+MARKER+' FAIL wait_deadline_'+name+'" '+end()+' } } }')
        wait_cases.append({'name':name,'prepare_effect':prepare,'prepare_ast':p.ast(setup.encode()),'poll_effect':poll,'poll_ast':p.ast(wait_effects[poll].encode()),'ready_trigger':predicate,'ready_ast':p.ast(condition.encode()),'ready_label':ready_label,'poll_bridge':poll_bridge,'poll_check':poll_check,'deadline_bridge':deadline_bridge,'deadline':deadline,'observer_bridge':9000+done,'observer':done,'poll_hours':2,'max_poll_attempts':72,'deadline_hours':68,'observer_grace_hours':4})
        return prepare+' = yes '+again+' HOL = { country_event = { id = '+NS+'.'+str(deadline_bridge)+' hours = 68 } }'
    send=bind('gui_send','common/scripted_guis/01_energy_gui.txt',['scripted_gui','energy_scripted_gui','effects','confirm_nuclear_fuel_sell_click'])
    # Existing files use scripted_gui, with exactly one fuel editor root.
    bind('send_ready','common/scripted_triggers/eon_nuclear_fuel_trade_triggers.txt',[P+'send_ready'],True)
    for suffix in ('accept','refuse','acknowledge','daily_cleanup'):
        bind(suffix,'common/scripted_effects/eon_nuclear_fuel_trade_effects.txt',[P+suffix])
    for kind,ident in ((1,'energy.1'),(2,'energy.10')):
        bind_option('response_'+str(kind)+'_accept',ident,ident+'.a')
        bind_option('response_'+str(kind)+'_refuse',ident,ident+'.b')
    observer=event_nodes('events/eon_nuclear_fuel_trade_events.txt','eon_nuclear_fuel_trade.1')
    bindings['old_observer']={'source':'events/eon_nuclear_fuel_trade_events.txt','event_id':'eon_nuclear_fuel_trade.1','event_immediate':True,'ast':json.loads(json.dumps(p.one(observer,'immediate')))}

    # Explicit private controls. The original AST remains bound in the manifest;
    # only the wrapped two actors / native autonomous fuel GUI selection differ.
    control_limit=p.ast(('NOT = { AND = { has_global_flag = '+NS+'_active OR = { tag = USA tag = HOL } } }').encode())
    frozen_hooks=[]
    for path in sorted((source/'common/on_actions').glob('*.txt')):
        rel=path.relative_to(source).as_posix()
        # Keep these native unit registration files byte-identical. They do not
        # supply the private actors' fuel/accounting controls, and re-emitting
        # their embedded unit strings is unnecessary for this experiment.
        if rel in UNTOUCHED_UNIT_ON_ACTIONS:
            continue
        candidate=p.maybe(ast(rel),'on_actions',[])
        for hook_index,(hook,op,value) in enumerate(candidate):
            if isinstance(value,list) and any(node[0]=='effect' for node in value) and should_control_on_action(rel,hook):
                frozen_hooks.append((rel,hook,hook_index))
    for rel,hook,hook_index in frozen_hooks:
        original=ast(rel); copy=p.ast(files[rel].encode()) if rel in files else json.loads(json.dumps(original))
        action=p.one(copy,'on_actions')[hook_index][2]
        for effect_index,node in enumerate(list(action)):
            if node[0]!='effect':continue
            effects=node[2]
            action[effect_index]=['effect','=',[['if','=',[['limit','=',control_limit]]+effects]]]
            controls.append({'source':rel,'on_action_index':hook_index,'on_action':hook,'effect_index':effect_index,'original_ast':effects,'transformed_ast':action[effect_index][2],
                             'reason':'Freeze ordinary weekly accounting/physical fuel and GUI AI setup for USA/HOL while private probe active.'})
        files[rel]=emit(copy)
        assert same_ast(p.ast(files[rel].encode()), copy), 'Native scalar escapes changed while wrapping: ' + rel
    gui_rel='common/scripted_guis/01_energy_gui.txt'
    original=ast(gui_rel); copy=json.loads(json.dumps(original))
    matches=[]
    for k,op,v in walk(copy):
        if k=='confirm_nuclear_fuel_sell_click' and isinstance(v,list):
            weights=p.maybe(v,'ai_will_do',None)
            if weights is not None: matches.append(weights)
    assert len(matches)==1,'Exactly one original fuel GUI AI weight required'
    matches[0].append(['modifier','=',[['factor','=','0'],['has_global_flag','=',NS+'_active']]])
    files[gui_rel]=emit(copy)
    assert same_ast(p.ast(files[gui_rel].encode()), copy), 'Native scalar escapes changed in energy GUI'
    controls.append({'source':gui_rel,'fuel_gui_ai_modifier':['modifier','=',[['factor','=','0'],['has_global_flag','=',NS+'_active']]],
                     'reason':'Freeze autonomous fuel offers globally; manual source GUI callback and production event options stay original.'})

    # Native scripted-GUI AI runs outside ordinary on_actions. Keep only the
    # private accounting subjects' money clicks and mine expansion quiescent;
    # their production fuel replies/results must still run normally.
    actor_zero=p.ast(('modifier = { factor = 0 has_global_flag = '+NS+'_active OR = { tag = USA tag = HOL } }').encode())[0]
    money_rel='common/scripted_guis/MD_money_scripted_gui.txt'
    original=ast(money_rel);copy=json.loads(json.dumps(original));money_weights=[]
    for key,op,body in walk(copy):
        if key=='ai_will_do' and isinstance(body,list):
            money_weights.append(json.loads(json.dumps(body)));body.append(json.loads(json.dumps(actor_zero)))
    assert money_weights,'Original native money GUI AI policies required'
    files[money_rel]=emit(copy)
    assert same_ast(p.ast(files[money_rel].encode()), copy), 'Native scalar escapes changed in money GUI'
    controls.append({'source':money_rel,'original_ai_policy_asts':money_weights,'actor_zero_modifier':actor_zero,
                     'reason':'Freeze original native money GUI AI spending/debt clicks for USA/HOL only while the private fuel probe is active. Click effects remain original.'})

    cash_rel='common/scripted_effects/00_budget_effects.txt'
    deps.add('tools/validation/nuclear_fuel_trade/build_native_probe.py')
    cash_copy,cash_control=cash_api_overlay(ast(cash_rel))
    files[cash_rel]=emit(cash_copy)
    validate_cash_api_overlay(p.ast(files[cash_rel].encode()),cash_control)
    controls.append(cash_control)
    mine_rel='common/decisions/eon_uranium_decisions.txt'
    original=ast(mine_rel);copy=json.loads(json.dumps(original))
    mine_policy=p.one(p.one(p.one(copy,'eon_uranium_category'),'eon_uranium_expand_mine'),'ai_will_do')
    old_mine_policy=json.loads(json.dumps(mine_policy));mine_policy.append(json.loads(json.dumps(actor_zero)))
    files[mine_rel]=emit(copy)
    assert same_ast(p.ast(files[mine_rel].encode()), copy), 'Native scalar escapes changed in mine AI'
    controls.append({'source':mine_rel,'selector':['eon_uranium_category','eon_uranium_expand_mine','ai_will_do'],
                     'original_ai_policy_ast':old_mine_policy,'actor_zero_modifier':actor_zero,
                     'reason':'Freeze only native mine expansion AI policy for USA/HOL during the private fuel probe; availability and actual project effects are unchanged.'})

    body='set_global_flag = '+NS+'_active log = "'+MARKER+' START fixture_loaded" '
    body+=guard('three_representative_countries_and_ai','USA = { exists = yes is_ai = yes } HOL = { exists = yes is_ai = yes } NEP = { exists = yes is_ai = no }','setup')
    body+=guard('initial_no_trade_pending',fresh(),'setup')
    body+=' USA = { clr_country_flag = energy_sell clr_country_flag = open_energy_screen } HOL = { clr_country_flag = energy_sell clr_country_flag = open_energy_screen } '
    body+=owner_queue('HOL','USA',10,1)
    event(1,'USA',None,body)

    plan=[('sell_accept',2,-500,0.5,5000,1000,'a'),('buy_accept',1,500,0.4,1000,5000,'a'),
          ('sell_refuse',2,-500,10,5000,1000,'b'),('buy_refuse',1,500,0.1,1000,5000,'b'),
          ('expired_sale',2,-500,0.5,5000,1000,'b')]
    for index,(name,kind,quantity,price,own_stock,peer_stock,choice) in enumerate(plan):
        start,done=10+index*10,11+index*10
        next_id=10+(index+1)*10 if index<len(plan)-1 else 80
        setup=guard(name+'_pair_free_before_reset',fresh(),'queued_'+name)
        for tag,stock in (('USA',own_stock),('HOL',peer_stock)):
            setup+=' '+tag+' = { set_country_flag = eon_uranium_reactor_stock_in_kg set_variable = { treasury = 500 } set_variable = { var_reactor_material_stockpile = '+str(stock)+' } set_variable = { enrichment_facilities = 0 } set_variable = { nuclear_reactor_fuel_production = 0 } set_variable = { nuclear_fuel_consumption = 1000 } set_variable = { display_income = 0 } set_variable = { display_expense = 0 } clear_variable = '+P+'cash_refund_due clear_variable = '+P+'fuel_refund_due clr_country_flag = energy_sell clr_country_flag = open_energy_screen }'
        setup+=' USA = { remove_opinion_modifier = { target = HOL modifier = '+NS+'_goodwill } } HOL = { remove_opinion_modifier = { target = USA modifier = '+NS+'_goodwill } remove_opinion_modifier = { target = USA modifier = '+NS+'_bad_terms } } '
        if name!='buy_refuse': setup+=' HOL = { add_opinion_modifier = { target = USA modifier = '+NS+'_goodwill } set_variable = { nuclear_reactor_fuel_production = 2000 } } '
        else: setup+=' HOL = { add_opinion_modifier = { target = USA modifier = '+NS+'_bad_terms } } '
        setup+=snapshots()+' set_variable = { nuclear_fuel_selling_selected_TAG = HOL.id } set_variable = { temp_nuclear_fuel_ammount = '+str(quantity)+' } set_variable = { temp_nuclear_fuel_price = '+str(price)+' } '
        setup+=guard(name+'_source_send_gate',NS+'_send_ready = yes','queued_'+name)+' '+send+' '
        pending='has_country_flag = '+P+'reserved has_country_flag = '+P+'outgoing '+cv(P+'phase',1)+' '+cv(P+'quantity',abs(quantity))+' '+cv(P+'price',price)+' '+cv(P+'direction',kind)+' '+cv(P+'partner','HOL')+' HOL = { has_country_flag = '+P+'incoming '+cv(P+'partner','USA')+' '+cv(P+'quantity',abs(quantity))+' '+cv(P+'price',price)+' '+cv(P+'phase',1)+' }'
        setup+=guard(name+'_immutable_pair_and_positive_cash',pending+' '+cv(P+'total',0,'greater_than'),'queued_'+name)
        setup+=' set_variable = { '+NS+'_actual_total = '+P+'total } set_variable = { '+NS+'_quoted_total = '+P+'quoted_total } '
        if kind==2:setup+=guard(name+'_sender_only_fuel_escrow',cv(P+'fuel_escrow',500)+' '+cv(P+'cash_escrow',0)+' '+cv('var_reactor_material_stockpile',own_stock-500)+' HOL = { '+cv('treasury',500)+' '+cv('var_reactor_material_stockpile',peer_stock)+' }','queued_'+name)
        else:setup+=guard(name+'_sender_only_cash_escrow',cv(P+'cash_escrow',P+'total')+' '+cv(P+'fuel_escrow',0)+' '+cv('var_reactor_material_stockpile',own_stock)+' HOL = { '+cv('treasury',500)+' '+cv('var_reactor_material_stockpile',peer_stock)+' }','queued_'+name)
        # Adversarial editor noise cannot mutate agreed quantity, price or peer.
        setup+=' set_variable = { temp_nuclear_fuel_ammount = 16000 } set_variable = { temp_nuclear_fuel_price = 999 } set_variable = { nuclear_fuel_selling_selected_TAG = NEP.id } '
        setup+=guard(name+'_editor_noise_keeps_terms',pending,'queued_'+name)
        if name=='sell_accept':
            setup+=' '+owner_queue('NEP','HOL',70,0)
        if name=='buy_accept':
            setup+=' '+NS+'_old_observer = yes '+guard(name+'_old_observer_keeps_fresh_live_offer',pending+' has_country_flag = '+P+'live','stale_observer')
        if name=='expired_sale':
            setup+=' clr_country_flag = '+P+'live '+NS+'_daily_cleanup = yes '
            setup+=guard(name+'_cleanup_returns_asset_keeps_identity',cv(P+'phase',4)+' has_country_flag = '+P+'reserved HOL = { '+cv(P+'phase',4)+' has_country_flag = '+P+'reserved } '+same_assets(),'expiry')
            setup+=' set_country_flag = { flag = '+P+'live days = 30 value = 1 } HOL = { set_country_flag = { flag = '+P+'live days = 30 value = 1 } } '
            setup+=guard(name+'_restoring_timer_cannot_reopen',cv(P+'phase',4)+' NOT = { '+NS+'_send_ready = yes }','expiry')
        setup+=obs(name+'_sent','recipient_name=[HOL.GetName] kind='+str(kind)+' expected_choice='+choice+' quoted_total=[?'+NS+'_quoted_total] actual_total=[?'+NS+'_actual_total]')+' '+result_wait(name,kind,quantity,own_stock,peer_stock,choice=='a',done)
        event(start,'USA','HOL',setup)
        accepted=choice=='a'
        buyer,seller=('HOL','USA') if kind==2 else ('USA','HOL')
        checks=guard(name+'_original_result_frees_both_slots',fresh(),'queued_'+name)
        if accepted:
            checks+=' '+buyer+' = { set_temp_variable = { '+NS+'_expected_cash = '+NS+'_cash_before } subtract_from_temp_variable = { '+NS+'_expected_cash = USA.'+NS+'_actual_total } } '+seller+' = { set_temp_variable = { '+NS+'_expected_cash = '+NS+'_cash_before } add_to_temp_variable = { '+NS+'_expected_cash = USA.'+NS+'_actual_total } } '
            # Temp vars share the execution scope; persist expected actor values.
            checks+=' '+buyer+' = { set_variable = { '+NS+'_expected_cash_persistent = '+NS+'_cash_before } subtract_from_variable = { '+NS+'_expected_cash_persistent = USA.'+NS+'_actual_total } } '+seller+' = { set_variable = { '+NS+'_expected_cash_persistent = '+NS+'_cash_before } add_to_variable = { '+NS+'_expected_cash_persistent = USA.'+NS+'_actual_total } } '
            conditions=' '.join(tag+' = { '+cv('treasury',NS+'_expected_cash_persistent')+' }' for tag in ('USA','HOL'))
            conditions+=' '+cv('var_reactor_material_stockpile',own_stock+quantity)+' HOL = { '+cv('var_reactor_material_stockpile',peer_stock-quantity)+' }'
            checks+=guard(name+'_one_frozen_transfer_and_exact_cash',conditions,'queued_'+name)
            checks+=' set_temp_variable = { '+NS+'_cash_delta_kusd = treasury } subtract_from_temp_variable = { '+NS+'_cash_delta_kusd = '+NS+'_cash_before } multiply_temp_variable = { '+NS+'_cash_delta_kusd = 1000000 } '
            checks+=guard(name+'_representable_payment_is_positive',buyer+' = { '+cv('treasury',NS+'_cash_before','less_than')+' } '+seller+' = { '+cv('treasury',NS+'_cash_before','greater_than')+' }','cash_precision')
        else:
            checks+=guard(name+'_no_cash_or_fuel_transferred',same_assets(),'queued_'+name)
            checks+=' set_temp_variable = { '+NS+'_cash_delta_kusd = 0 } '
        checks+=obs(name+'_observed','cash_delta_kusd=[?'+NS+'_cash_delta_kusd] actual_total=[?'+NS+'_actual_total] quoted_total=[?'+NS+'_quoted_total] recipient_name=[HOL.GetName]')
        if name=='buy_accept':checks+=' '+owner_queue('USA','HOL',71,0)
        else:checks+=' '+owner_queue('HOL','USA',next_id,1)
        event(done,'USA','HOL',checks)
        cases.append({'name':name,'direction':kind,'queued_event':'energy.1' if kind==1 else 'energy.10','expected_option':'energy.'+('1' if kind==1 else '10')+'.'+choice,'sender':'USA','recipient':'HOL','begin':name+'_sent','done':name+'_observed','minimum_hours':0 if args.result_aware else 62,'direct_response':False})

    # Wrong FROM arrives before the real one-hour production response; no private
    # transfer/event is synthesized. Its frame is independently calibrated.
    wrong=snapshots()+' set_temp_variable = { '+P+'response_kind = 2 } '+NS+'_accept = yes '+NS+'_refuse = yes '
    wrong+=guard('wrong_from_does_not_consume_or_transfer',same_assets()+' USA = { '+cv(P+'phase',1)+' } HOL = { '+cv(P+'phase',1)+' }','invalid_peer')+obs('wrong_from_inert')
    event(70,'HOL','NEP',wrong)
    duplicate=snapshots()+' '+NS+'_response_1_accept = yes '+NS+'_response_1_refuse = yes '
    duplicate+=guard('duplicate_original_options_no_transfer_or_new_record',same_assets()+' '+fresh(),'duplicate')+obs('duplicate_after_real_result')+' '+owner_queue('HOL','USA',30,1)
    event(71,'HOL','USA',duplicate)
    high=guard('high_cash_pair_free',fresh(),'high_cash')
    high+=' USA = { set_country_flag = eon_uranium_reactor_stock_in_kg set_variable = { treasury = 900000 } set_variable = { var_reactor_material_stockpile = 5000 } } HOL = { set_country_flag = eon_uranium_reactor_stock_in_kg set_variable = { treasury = 900000 } set_variable = { var_reactor_material_stockpile = 1000 } } '+snapshots()
    high+=' set_variable = { nuclear_fuel_selling_selected_TAG = HOL.id } set_variable = { temp_nuclear_fuel_ammount = -500 } set_variable = { temp_nuclear_fuel_price = 0.4 } '
    high+=obs('high_cash_before')
    ready=send+' set_variable = { '+NS+'_actual_total = '+P+'total } set_variable = { '+NS+'_quoted_total = '+P+'quoted_total } '
    ready+=guard('high_cash_valid_quote_holds_stock_and_positive_cash',cv(P+'phase',1)+' '+cv(P+'fuel_escrow',500)+' '+cv(P+'total',0,'greater_than')+' '+cv('treasury',900000)+' '+cv('var_reactor_material_stockpile',4500)+' HOL = { '+cv('treasury',900000)+' '+cv('var_reactor_material_stockpile',1000)+' }','high_cash')
    ready+=obs('high_cash_sent','recipient_name=[HOL.GetName] kind=2 expected_choice=a quoted_total=[?'+NS+'_quoted_total] actual_total=[?'+NS+'_actual_total]')+' '+result_wait('high_cash',2,-500,5000,1000,True,81)
    rejected=send+' '+guard('high_cash_rejected_no_free_stock_no_escrow',same_assets()+' '+fresh(),'high_cash')+' '+obs('high_cash_rejected')
    high+=' if = { limit = { '+NS+'_send_ready = yes } '+ready+' set_global_flag = '+NS+'_high_cash_accepted } else = { '+rejected+' } '+obs('high_cash_after')
    high+=' if = { limit = { NOT = { has_global_flag = '+NS+'_high_cash_accepted } } '+end()+' }'
    event(80,'USA','HOL',high)
    observed=guard('high_cash_original_result_frees_both_slots',fresh(),'high_cash')
    observed+=' set_temp_variable = { '+NS+'_seller_delta = treasury } subtract_from_temp_variable = { '+NS+'_seller_delta = '+NS+'_cash_before } HOL = { set_temp_variable = { '+NS+'_buyer_delta = '+NS+'_cash_before } subtract_from_temp_variable = { '+NS+'_buyer_delta = treasury } } '
    observed+=guard('high_cash_valid_settlement_has_equal_positive_payment',cv(NS+'_seller_delta',0,'greater_than')+' '+cv(NS+'_buyer_delta',NS+'_seller_delta')+' '+cv(NS+'_seller_delta',NS+'_actual_total')+' '+cv('var_reactor_material_stockpile',4500)+' HOL = { '+cv('var_reactor_material_stockpile',1500)+' }','high_cash')
    observed+=' set_temp_variable = { '+NS+'_cash_delta_kusd = '+NS+'_seller_delta } multiply_temp_variable = { '+NS+'_cash_delta_kusd = 1000000 } '
    observed+=obs('high_cash_observed','cash_delta_kusd=[?'+NS+'_cash_delta_kusd] actual_total=[?'+NS+'_actual_total] quoted_total=[?'+NS+'_quoted_total] recipient_name=[HOL.GetName]')+' '+end()
    event(81,'USA','HOL',observed)
    cases.append({'name':'high_cash','direction':2,'queued_event':'energy.10','expected_option':'energy.10.a','sender':'USA','recipient':'HOL','begin':'high_cash_sent','done':'high_cash_observed','minimum_hours':0 if args.result_aware else 62,'direct_response':False,'optional_precision_branch':True})
    for bridge,(peer,target,number) in sorted(bridges.items()):event(bridge,peer,None,target+' = { country_event = { id = '+NS+'.'+str(number)+' } }')
    files['common/scripted_effects/'+NS+'_effects.txt']='\n\n'.join(NS+'_'+name+' = {\n'+emit(binding['ast'])+'\n}' for name,binding in bindings.items())
    files['common/scripted_triggers/'+NS+'_triggers.txt']='\n\n'.join(NS+'_'+name+' = {\n'+emit(binding['ast'])+'\n}' for name,binding in predicates.items())
    if args.result_aware:
        files['common/scripted_effects/'+NS+'_effects.txt']+='\n\n'+'\n\n'.join(name+' = {\n'+body+'\n}' for name,body in wait_effects.items())
        files['common/scripted_triggers/'+NS+'_triggers.txt']+='\n\n'+'\n\n'.join(name+' = {\n'+body+'\n}' for name,body in wait_triggers.items())
    files['common/opinion_modifiers/'+NS+'_opinions.txt']='opinion_modifiers = { '+NS+'_goodwill = { value = 250 } '+NS+'_bad_terms = { value = -250 } }'
    for index,text in enumerate(events):
        try:p.ast(text.encode())
        except AssertionError as error:
            out.mkdir(parents=True,exist_ok=True);(out/'prepare-error.txt').write_text(text)
            raise AssertionError(('Private event index',index,str(error))) from error
    files['events/'+NS+'_events.txt']='add_namespace = '+NS+'\n\n'+'\n\n'.join(events)
    if args.startup:files['common/on_actions/'+NS+'_startup.txt']='on_actions = { on_startup = { effect = { USA = { '+queue(1,1)+' } } } }'
    if args.state_trace:
        trace_rel='events/00_Energy_events.txt'
        played, declaration=state_trace.option_overlay((source/trace_rel).read_bytes(),p)
        raw_overrides[trace_rel]=played
        files[trace_rel]=played.decode('utf-8-sig')
        trace_overlays.append(declaration)
        deps.add('tools/validation/nuclear_fuel_trade/native_state_trace.py')
    # Bind every production helper reached by copied callbacks or the source
    # energy events, including read-only root refresh integrations.
    catalog={}
    for folder in ('common/scripted_effects','common/scripted_triggers'):
        for path in (source/folder).glob('*.txt'):
            for name in re.findall(r'^([A-Za-z_][A-Za-z_0-9]*)\s*=\s*\{',path.read_text(encoding='utf-8-sig'),re.M):catalog.setdefault(name,[]).append(path)
    pending=set()
    for rel,text in files.items():
        try:nodes=p.ast(text.encode())
        except AssertionError as error:raise AssertionError((rel,str(error))) from error
        pending.update(k for k,op,v in walk(nodes) if k in catalog)
    pending.update(k for k,op,v in walk(ast('events/00_Energy_events.txt')) if k in catalog)
    seen=set()
    while pending:
        name=pending.pop()
        if name in seen:continue
        seen.add(name)
        for path in catalog[name]:
            deps.add(path.relative_to(source).as_posix())
            for k,op,v in p.ast(path.read_bytes()):
                if k==name:pending.update(child for child,op,item in walk(v) if child in catalog and child not in seen)
    for tag in ('USA','HOL','NEP'):
        paths=list((source/'history/countries').glob(tag+' - *.txt'));assert len(paths)==1
        deps.add(paths[0].relative_to(source).as_posix())
    deps.update(('tools/validation/diplomacy_completion/check_native_grammar.py','tools/validation/diplomacy_package_03/_support.py'))
    deps.update(UNTOUCHED_UNIT_ON_ACTIONS)
    assert not UNTOUCHED_UNIT_ON_ACTIONS.intersection(files), 'Native unit files must never receive private overlays'
    for rel,text in files.items():
        raw=raw_overrides.get(rel,(text.strip().replace('\r\n','\n')+'\n').replace('\n','\r\n').encode('utf-8'))
        if rel not in raw_overrides:assert not raw.startswith(b'\xef\xbb\xbf'),rel
        errors=Counter(g.inspect(p.ast(raw)))
        original=Counter(g.inspect(ast(rel))) if rel in {control['source'] for control in controls}|{row['source'] for row in trace_overlays} else Counter()
        assert not errors-original,(rel,dict(errors-original))
        path=out/'mod'/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    manifest={'schema':1,'namespace':NS,'marker':MARKER,'source_root':str(source),'fixture_root':str(out/'mod'),
              'source_sha256':{rel:sha(source/rel) for rel in sorted(deps)},'fixture_sha256':{rel:sha(out/'mod'/rel) for rel in sorted(files)},
              'source_effect_bindings':bindings,'source_trigger_bindings':predicates,'private_controls':controls,
              'excluded_original_unit_files':sorted(UNTOUCHED_UNIT_ON_ACTIONS),
              'assertions':labels,'assertion_groups':groups,'observation_labels':observations,'actual_ai_cases':cases,
              'conditional_assertions':{'high_cash_accepted':['high_cash_valid_quote_holds_stock_and_positive_cash','high_cash_original_result_frees_both_slots','high_cash_valid_settlement_has_equal_positive_payment','frame_81','frame_9081'],'high_cash_rejected':['high_cash_rejected_no_free_stock_no_escrow']},
              'conditional_observations':['high_cash_sent','high_cash_observed','high_cash_rejected'],
              'private_frame_conditions':frame_conditions,'expected_native_start_tag':'NEP','kickoff_event':NS+'.1',
              'startup_installed':args.startup,'original_energy_events_unchanged':not args.state_trace,
              'limits':['Private weekly/native GUI AI controls apply only during the experiment; production response and result events stay unchanged.',
                        'Expired live flags are explicitly removed; natural 30-day expiry is not claimed.',
                        'The stale observer helper is source-bound and invoked directly; the natural day31 event is outside this bounded run.',
                        'Duplicate callbacks run after the original result naturally releases both AI slots.',
                        'Case actors have neutral displayed budgets. The buy-refusal case sets a negative private opinion modifier and an executable 500kg/$100-per-kg quote, so refusal must come from the unchanged original seller AI rather than a blocked zero-size cash quote.',
                        'No human modal interaction, save/load, multiplayer or campaign balance claim.']}
    manifest['limits'].append('The three original unit on_actions files are excluded from all private overlays and remain exact production bytes. This narrows the private controls compared with older fixtures such as native67, so this run is not a trace-only controlled comparison with native67.')
    if args.result_aware:
        manifest['result_aware_wait']={'poll_hours':2,'max_poll_attempts':72,'deadline_hours':68,'cases':wait_cases}
        manifest['conditional_assertions']['high_cash_accepted'].append('wait_ready_high_cash')
        manifest['limits'].append('Result-aware private polling uses nominal hours2 and a persistent maximum72 attempts to prevent current-tick recurring event starvation. It requires the completed asset outcome and both original slots cleared; source choices remain independently required. Callback delay alone is not business evidence.')
    if args.state_trace:
        manifest['state_trace']={'marker':state_trace.MARKER,'source_overlays':trace_overlays,
                                 'private_islands':private_trace_islands,
                                 'original_energy_events_business_ast_unchanged':True,
                                 'production_source_exact_byte_recovery':True}
        manifest['limits'].append('Optional declared state traces only read variables/flags and write logs. Removing complete declared islands recovers the original source bytes and AST. Printed cash differences are derived by the reader at the native log precision; business assertions retain exact native comparisons.')
    out.mkdir(parents=True,exist_ok=True);mp=out/'manifest.json';mp.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (out/'prepared-freeze.json').write_text(json.dumps({'manifest_sha256':sha(mp),'source_sha256':manifest['source_sha256'],'fixture_sha256':manifest['fixture_sha256']},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'manifest':str(mp),'manifest_sha256':sha(mp),'assertions':len(labels),'actual_queued_ai_cases':len(cases),'fixture_files':len(files),'native_acceptance':False}))


if __name__=='__main__':main()
