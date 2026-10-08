"""Ordered current-source service consent and lifecycle; not native HOI4 runtime."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = 'b1568ffc7ae3d0809be0912be68bb76ab4fb0e28'
groups = Counter()
adapter_cases = Counter()

# Definitions only. Each earlier suite is executed and counted separately.
executor_path = ROOT / 'tools/validation/diplomacy_package_16/test_ammo.py'
executor_text = executor_path.read_text(encoding='utf-8')
boundary = '\ndef focus(name):'
assert executor_text.count(boundary) == 1, 'Ordered executor definition boundary changed'
source = {'__file__': str(executor_path), '__name__': 'services_ordered_executor'}
exec(compile(executor_text.split(boundary)[0], str(executor_path), 'exec'), source)
model = source['model']
ast, one, context, switch = (source[name] for name in ('ast', 'one', 'context', 'switch'))
source_trigger, source_execute, source_value = source['trigger'], source['execute'], source['value']
source_country_ref = model['country_ref']

def read(path): return (ROOT / path).read_text(encoding='utf-8-sig')

def country_ref(result, ctx, token):
    if token == 'FROM.FROM': return ctx.get('from_from')
    if token.startswith('PREV.') and all(part == 'PREV' for part in token.split('.')):
        depth = len(token.split('.'))
        assert depth <= len(ctx['previous']), ('Missing previous country frame', token)
        return ctx['previous'][depth-1]
    return source_country_ref(result, ctx, token)

def value(result, ctx, token):
    # Native10 proves shared bare temps and persistent explicitly scoped reads.
    if token == 'FROM.FROM':return country_ref(result,ctx,token)
    if isinstance(token,str) and '.' in token:
        parts=token.split('.')
        if token.startswith('FROM.FROM.'):
            actor=country_ref(result,ctx,'FROM.FROM');tail=token[10:]
        elif parts[0]=='PREV':
            depth=0
            while depth<len(parts) and parts[depth]=='PREV':depth+=1
            assert depth<=len(ctx['previous']),('Missing previous frame',token)
            actor=ctx['previous'][depth-1];tail='.'.join(parts[depth:])
        elif parts[0] in ('ROOT','FROM','THIS') or parts[0] in result['countries']:
            actor=country_ref(result,ctx,parts[0]);tail='.'.join(parts[1:])
        else:return source_value(result,ctx,token)
        if not tail:return actor
        if tail=='id':return actor
        nested=switch(ctx,actor);owner=result['countries'][actor]
        if '^' in tail:
            name,index=tail.split('^',1);rows=owner['arrays'].get(name,[])
            if index=='num':return len(rows)
            ordinal=int(value(result,nested,index));return rows[ordinal] if 0<=ordinal<len(rows) else 0
        if tail.startswith('opinion@'):return owner['opinions'].get(country_ref(result,nested,tail.split('@',1)[1]),0)
        if '@' in tail:
            base, selector = tail.split('@', 1)
            tail = base + '@' + str(country_ref(result, nested, selector))
        return owner['variables'].get(tail,0)
    if isinstance(token, str) and '@' in token and token not in result['temp']:
        base, selector = token.split('@', 1)
        return result['countries'][ctx['scope']]['variables'].get(base + '@' + str(country_ref(result, ctx, selector)), 0)
    return source_value(result,ctx,token)

def flag_name(result, ctx, name):
    # Native24/29: country FLAG suffixes select actual scopes, not scalar aliases.
    # This does not change dynamic VARIABLE address resolution.
    if '@' not in name: return name
    base, target = name.split('@', 1)
    scopes = ('ROOT', 'FROM', 'THIS', 'PREV', 'FROM.FROM')
    if target in scopes or (target.startswith('PREV.PREV') and all(part == 'PREV' for part in target.split('.'))):
        return base + '@' + str(country_ref(result, ctx, target))
    return base + '@literal:' + target


def trigger(nodes, result, ctx):
    index = 0
    while index < len(nodes):
        key, operator, val = nodes[index]; index += 1
        grouped = [(key, operator, val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        country = result['countries'][ctx['scope']]
        if key == 'FROM.FROM':
            actor = country_ref(result, ctx, key)
            passed = actor in result['countries'] and trigger(val, result, switch(ctx, actor))
        elif key == 'has_civil_war': passed = country.get('civil_war', False) == (val == 'yes')
        elif key == 'num_of_military_factories': passed = model['compare'](country['variables'].get(key, 0), operator, value(result, ctx, val))
        elif key == 'has_government':
            target = country_ref(result, ctx, val)
            expected = result['countries'][target]['government'] if target in result['countries'] else val
            passed = country['government'] == expected
        elif key in ('hidden_trigger', 'hidden_effect'): passed = trigger(val, result, ctx)
        else: passed = source_trigger(grouped, result, ctx)
        if not passed: return False
    return True

def execute(nodes, result, ctx):
    index = 0
    while index < len(nodes):
        key, operator, val = nodes[index]; index += 1
        grouped = [(key, operator, val)]
        if key == 'if':
            while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                grouped.append(nodes[index]); index += 1
        country = result['countries'][ctx['scope']]
        if key == 'set_temp_variable' and any('.' in name for name, operator, rhs in val):
            raise AssertionError(('Uncalibrated qualified temporary write', val))
        if key == 'FROM.FROM':
            actor = country_ref(result, ctx, key)
            if actor in result['countries']: execute(val, result, switch(ctx, actor))
        elif key == 'add_timed_idea':
            identity, days = one(val, 'idea'), float(one(val, 'days'))
            country['ideas'].add(identity)
            result.setdefault('idea_timer_declarations', []).append((ctx['scope'], identity, days))
        elif key == 'remove_ideas': country['ideas'].discard(val)
        elif key in ('change_the_military_opinion', 'change_domestic_influence_percentage'):
            result.setdefault('political_macro_calls', []).append((ctx['scope'], key, deepcopy(val), deepcopy(result['temp'])))
        else: source_execute(grouped, result, ctx)

for namespace in (source, source['source'], source['source']['loader'], model):
    namespace['execute'] = execute; namespace['trigger'] = trigger; namespace['value'] = value; namespace['country_ref'] = country_ref; namespace['flag_name'] = flag_name
model['effects']['modify_treasury_effect'] = one(ast(read('common/scripted_effects/00_budget_effects.txt')), 'modify_treasury_effect')
for registry, path in (('effects', 'common/scripted_effects/eon_services_effects.txt'),
                       ('capacity_triggers', 'common/scripted_triggers/eon_services_triggers.txt')):
    if (ROOT / path).exists():
        additions = {key: body for key, op, body in ast(read(path))}
        assert not additions.keys() & model[registry].keys(), 'Services overwrite an earlier helper'
        model[registry].update(additions)

def state(payer=100, provider=100):
    result = source['state']()
    for country in result['countries'].values():
        country['variables'].update(treasury=100, num_of_civilian_factories=50, num_of_military_factories=20)
        country['arrays']['influence_array'] = ['A', 'C', 'D', 'B']
        country.update(original_tag='OTH', civil_war=False)
    result['countries']['A']['variables']['treasury'] = provider
    result['countries']['B']['variables']['treasury'] = payer
    return result

def cash(result): return {actor: data['variables']['treasury'] for actor, data in result['countries'].items()}

def option(events, identity, name):
    found = [val for key, op, val in events[identity] if key == 'option' and one(val, 'name') == name]
    assert len(found) == 1, (identity, name)
    return found[0]

def effect(result, nodes, actor='B', from_='A', from_from=None, scope=None, temporary=None):
    result['temp'] = dict(temporary or {})
    ctx = context(actor, from_, scope=scope); ctx['from_from'] = from_from
    execute(nodes, result, ctx)

def check(result, nodes, actor='A', from_='B', from_from=None, scope=None, temporary=None):
    result['temp'] = dict(temporary or {})
    ctx = context(actor, from_, scope=scope); ctx['from_from'] = from_from
    return trigger(nodes, result, ctx)

def send(result, kind=1, provider='A', receiver='B', force=False):
    events = model['get_event_map'](read('events/00_Influence_events.txt'))
    body = option(events, 'influence.501', 'influence.501.' + ('a' if kind == 1 else 'b'))
    ready = check(result, one(body, 'trigger'), provider, receiver, receiver)
    if ready or force: effect(result, body, provider, receiver, receiver)
    return ready

def reply(result, kind=1, provider='A', receiver='B', accepted=True, force=False):
    events = model['get_event_map'](read('events/eon_services_events.txt'))
    name = 'eon_services.1.' + (('a' if kind == 1 else 'b') if accepted else 'c')
    body = option(events, 'eon_services.1' if kind == 1 else 'eon_services.6', name)
    guards = [val for key, op, val in body if key == 'trigger']
    ready = not guards or check(result, guards[0], receiver, provider)
    if ready or force: effect(result, body, receiver, provider)
    return ready

def action(result, name, actor='A', partner='B', force=False):
    actions = one(ast(read('common/scripted_diplomatic_actions/eon_services_actions.txt')), 'scripted_diplomatic_actions')
    body = one(actions, 'eon_services_' + name)
    ready = all(check(result, one(body, key), actor, None, scope=partner) for key in ('allowed', 'visible', 'selectable', 'can_be_sent'))
    if ready or force: effect(result, one(body, 'complete_effect'), actor, None, scope=partner)
    return ready

def native_hook(result, name, actor='A', from_='B'):
    hooks = one(ast(read('common/on_actions/eon_services_on_actions.txt')), 'on_actions')
    effect(result, one(one(hooks, name), 'effect'), actor, from_)

def daily(result):
    for actor, data in result['countries'].items():
        if data['exists']: native_hook(result, 'on_daily', actor, None)

def flags(result, actor): return result['countries'][actor]['flags']
def vars_(result, actor): return result['countries'][actor]['variables']
def owned(result, actor, kind): return 'eon_services_' + ('logistics' if kind == 1 else 'recon') + '_owned' in flags(result, actor)
def pending(result, actor='A'): return 'eon_services_pending' in flags(result, actor)
def snapshot(result): return {key: deepcopy(val) for key, val in result.items() if key not in ('temp', 'scope_temps')}

def focus(name):
    events = model['get_event_map'](read('events/00_Influence_events.txt'))
    if name == 'legacy_replay':
        result = state(); flags(result, 'A').add('military_services_sent_logistics'); effect(result, option(events, 'influence.506', 'influence.506.a'))
        first = cash(result); effect(result, option(events, 'influence.506', 'influence.506.a'))
        assert cash(result) == first, ('Legacy unsigned callback must not charge a second fee', first, cash(result))
        groups['legacy_unsigned_replay_does_not_repeat_fee'] += 1
    elif name == 'legacy_insufficient':
        result = state(payer=1); flags(result, 'A').add('military_services_sent_logistics'); effect(result, option(events, 'influence.506', 'influence.506.a'))
        assert cash(result)['B'] == 1 and cash(result)['A'] == 100, ('Legacy unsigned callback cannot debit an insolvent payer', cash(result))
        groups['legacy_unsigned_insufficient_payer_no_transfer'] += 1
    elif name == 'cross_kind_reject':
        result = state(); assert send(result, 1); assert reply(result, 1, accepted=False)
        assert send(result, 2); before = snapshot(result)
        reply(result, 1, accepted=False, force=True)
        assert snapshot(result) == before and pending(result), ('Consumed old logistics rejection cannot close a later recon proposal for the same pair', result['countries']['A'])
        groups['consumed_old_response_of_other_type_cannot_close_new_pending_pair'] += 1
    else: raise AssertionError(('Unknown focus', name))

def kind_name(kind): return 'logistics' if kind == 1 else 'recon'
def idea(kind): return 'military_services_' + kind_name(kind) + '_idea'
def family_flag(kind, suffix): return 'eon_services_' + kind_name(kind) + '_' + suffix
def family_var(kind): return 'eon_services_' + kind_name(kind) + '_provider'
def macro_calls(result, name): return [call for call in result.get('political_macro_calls', []) if call[1] == name]
def helper(result, name, actor='A', from_=None, temporary=None):
    effect(result, [('eon_services_' + name, '=', 'yes')], actor, from_, temporary=temporary)

def unrelated(result):
    return {actor: {'variables': {key: deepcopy(val) for key, val in data['variables'].items()
                                if not key.startswith('eon_services_') and key != 'treasury'},
                    'flags': {flag for flag in data['flags'] if not flag.startswith(('eon_services_', 'refused_military_aid'))},
                    'ideas': data['ideas'] - {idea(1), idea(2)}, 'arrays': deepcopy(data['arrays']),
                    'wars': deepcopy(data['wars']), 'faction': data['faction'], 'government': data['government'],
                    'opinions': deepcopy(data['opinions']), 'overlord': data['overlord']}
            for actor, data in result['countries'].items()}

def scenarios():
    for name in ('legacy_replay', 'legacy_insufficient', 'cross_kind_reject'): focus(name)
    for kind, fee, influence in ((1, 3, 1.5), (2, 4, 2)):
        result = state(payer=fee); before = unrelated(result); wealth = sum(cash(result).values())
        assert send(result, kind); assert cash(result)['B'] == fee and cash(result)['A'] == 100
        assert pending(result) and vars_(result, 'A')['eon_services_partner'] == 'B' and vars_(result, 'A')['eon_services_kind'] == kind
        assert not owned(result, 'B', kind) and idea(kind) not in result['countries']['B']['ideas']
        assert {'target': 'B', 'id': 'eon_services.1' if kind == 1 else 'eon_services.6', 'from': 'A'} in result['events']
        assert reply(result, kind); assert cash(result)['B'] == 0 and cash(result)['A'] == 100 + fee
        assert owned(result, 'B', kind) and vars_(result, 'B')[family_var(kind)] == 'A' and idea(kind) in result['countries']['B']['ideas']
        assert not pending(result) and not vars_(result, 'A').get('eon_services_partner') and not vars_(result, 'A').get('eon_services_kind')
        assert sum(cash(result).values()) == wealth and unrelated(result) == before
        assert ('A', 'eon_services_live', 30) in result['timer_declarations']
        assert ('B', family_flag(kind, 'live'), 80) in result['timer_declarations']
        assert ('B', idea(kind), 80) in result['idea_timer_declarations']
        influence_calls = macro_calls(result, 'change_influence_percentage'); assert len(influence_calls) == 1
        assert influence_calls[0][0] == 'B' and influence_calls[0][3]['percent_change'] == influence
        assert influence_calls[0][3]['tag_index'] == 'A' and influence_calls[0][3]['influence_target'] == 'B'
        opinion_calls = macro_calls(result, 'change_the_military_opinion'); assert len(opinion_calls) == 1
        assert opinion_calls[0][0] == 'A' and opinion_calls[0][3]['temp_opinion'] == 3
        groups['two_original_prices_terms_benefits_and_ownership_exact_after_consent_only'] += 1

        before = snapshot(result); reply(result, kind, force=True); reply(result, kind, accepted=False, force=True)
        assert snapshot(result) == before
        groups['accepted_record_consumed_before_duplicate_acceptance_or_rejection'] += 1

        result = state(); assert send(result, kind); before = snapshot(result)
        send(result, kind, force=True); send(result, 3-kind, receiver='D', force=True)
        assert snapshot(result) == before
        groups['same_and_cross_kind_forced_provider_send_cannot_overwrite_one_pending_record'] += 1

        result = state(); assert send(result, kind); before = snapshot(result)
        assert not reply(result, 3-kind, force=True) and snapshot(result) == before
        assert not reply(result, kind, provider='C', force=True) and snapshot(result) == before
        assert not reply(result, kind, receiver='D', force=True) and snapshot(result) == before
        groups['wrong_kind_provider_or_recipient_callback_is_inert'] += 1

        result = state(); assert send(result, kind); assert reply(result, kind, accepted=False)
        assert send(result, 3-kind); before = snapshot(result)
        assert not reply(result, kind, accepted=False, force=True) and snapshot(result) == before
        assert not reply(result, kind, force=True) and snapshot(result) == before
        assert pending(result) and vars_(result, 'A')['eon_services_kind'] == 3-kind
        groups['both_typed_consumed_accept_and_reject_callbacks_cannot_close_or_charge_new_other_type_same_pair'] += 1

        result = state(); assert send(result, kind); wallet = cash(result)
        assert reply(result, kind, accepted=False)
        assert cash(result) == wallet and not pending(result) and not owned(result, 'B', kind)
        calls = macro_calls(result, 'change_domestic_influence_percentage'); assert len(calls) == 1 and calls[0][3]['percent_change'] == 2
        before = snapshot(result); reply(result, kind, accepted=False, force=True); assert snapshot(result) == before
        groups['valid_decline_no_payment_no_bonus_single_original_refusal_political_call'] += 1

        for payer in (0, fee-.01, -1):
            result = state(payer=payer); assert send(result, kind); wallet = cash(result)
            assert not reply(result, kind, force=True)
            assert cash(result) == wallet and not pending(result) and not owned(result, 'B', kind)
            assert not macro_calls(result, 'change_influence_percentage')
            groups['fresh_insufficient_payer_no_money_bonus_or_forced_negative_treasury'] += 1

        for provider, accepted in ((1000000-fee, True), (1000000-fee+.01, False), (1000001, False), (-1000000, True), (-1000001, False)):
            result = state(provider=provider); assert send(result, kind); wallet = cash(result)
            assert reply(result, kind, force=True) == accepted
            if accepted: assert cash(result)['A'] == provider+fee and cash(result)['B'] == 100-fee
            else: assert cash(result) == wallet and not owned(result, 'B', kind)
            groups['fresh_supplier_credit_capacity_and_minimum_preserve_complete_fee'] += 1

        result = state(payer=1000001); assert send(result, kind); wallet = cash(result)
        assert not reply(result, kind, force=True) and cash(result) == wallet and not owned(result, 'B', kind)
        groups['extraordinary_overcap_payer_stock_not_trimmed_by_inherited_treasury_clamp'] += 1

        mutations = ('peace', 'enemy', 'recipient_dead', 'provider_dead', 'influence_lost', 'industry_lost', 'existing_idea', 'existing_ledger', 'ERI_transition')
        for mutation in mutations:
            result = state(); assert send(result, kind)
            if mutation == 'peace': result['countries']['B']['wars'].clear()
            elif mutation == 'enemy': result['countries']['B']['wars'].add('A')
            elif mutation == 'recipient_dead': result['countries']['B']['exists'] = False
            elif mutation == 'provider_dead': result['countries']['A']['exists'] = False
            elif mutation == 'influence_lost': result['countries']['B']['arrays']['influence_array'] = ['C', 'D']
            elif mutation == 'industry_lost': vars_(result, 'A')['num_of_military_factories'] = 10
            elif mutation == 'existing_idea': result['countries']['B']['ideas'].add(idea(kind))
            elif mutation == 'existing_ledger': flags(result, 'B').add(family_flag(kind, 'owned')); vars_(result, 'B')[family_var(kind)] = 'C'
            else: result['countries']['A'].update(original_tag='ERI', leader='Eritrean Transitional Government'); flags(result, 'A').add('ETH_transitional_government_FLAG')
            wallet, previous_ideas = cash(result), deepcopy(result['countries']['B']['ideas'])
            assert not reply(result, kind, force=True)
            assert cash(result) == wallet and not pending(result) and result['countries']['B']['ideas'] == previous_ideas
            assert not macro_calls(result, 'change_influence_percentage')
            groups['fresh_' + mutation + '_cannot_complete_stale_proposal'] += 1

        result = state(); assert send(result, kind); wallet = cash(result)
        assert action(result, 'withdraw_offer') and pending(result) and 'eon_services_cancelled' in flags(result, 'A')
        before = snapshot(result); assert not action(result, 'withdraw_offer', force=True); assert snapshot(result) == before
        assert not reply(result, kind, force=True) and not pending(result) and cash(result) == wallet and not owned(result, 'B', kind)
        groups['free_withdrawal_holds_old_identity_until_reply_and_cannot_be_paid'] += 1

        result = state(); assert send(result, kind); assert action(result, 'withdraw_offer'); flags(result, 'A').discard('eon_services_live'); wallet = cash(result)
        daily(result); assert not pending(result) and 'eon_services_retired_pair@B' in flags(result, 'A') and cash(result) == wallet
        assert not send(result, kind) and not send(result, 3-kind)
        result['countries']['D']['wars'].add('C'); assert send(result, kind, receiver='D')
        before = snapshot(result); reply(result, kind, receiver='B', force=True); assert snapshot(result) == before
        groups['withdrawal_timeout_retired_pair_blocks_both_types_but_other_partner_stays_available'] += 1

        result = state(); assert send(result, kind); flags(result, 'A').discard('eon_services_live'); daily(result)
        assert not pending(result) and 'eon_services_retired_pair@B' in flags(result, 'A') and not owned(result, 'B', kind)
        groups['ordinary_30_day_expiry_retires_signed_pair_without_cash_effect'] += 1

        for bad in (999, 1.5, 0, 'A'):
            result = state(); assert send(result, kind); vars_(result, 'A')['eon_services_partner'] = bad; wallet = cash(result)
            daily(result); assert not pending(result) and 'eon_services_quarantined' in flags(result, 'A') and cash(result) == wallet
            result['countries']['D']['wars'].add('C'); assert not send(result, kind, receiver='D')
            groups['malformed_country_identity_quarantines_provider_only_without_guessed_agreement'] += 1

        for missing in ('pending', 'kind'):
            result = state(); assert send(result, kind)
            if missing == 'pending': flags(result, 'A').discard('eon_services_pending')
            else: vars_(result, 'A')['eon_services_kind'] = 999
            wallet = cash(result); daily(result); assert not pending(result) and cash(result) == wallet
            if missing == 'pending': assert 'eon_services_quarantined' in flags(result, 'A')
            else: assert 'eon_services_retired_pair@B' in flags(result, 'A')
            groups['partial_or_corrupt_provider_record_cannot_be_reused_or_create_payment'] += 1

        result = state(); assert send(result, kind); assert reply(result, kind); wallet = cash(result)
        result['countries']['A']['ideas'].clear(); vars_(result, 'A')['num_of_military_factories'] = 0
        result['countries']['B']['arrays']['influence_array'] = []; result['countries']['A']['government'] = 'fascism'
        daily(result); assert owned(result, 'B', kind) and idea(kind) in result['countries']['B']['ideas'] and cash(result) == wallet
        groups['paid_service_does_not_retroactively_end_for_lost_influence_industry_or_political_entry_condition'] += 1

        for end_reason in ('peace', 'enemy', 'expiry', 'idea_removed', 'provider_dead', 'bad_provider'):
            result = state(); assert send(result, kind); assert reply(result, kind); wallet = cash(result)
            if end_reason == 'peace': result['countries']['B']['wars'].clear()
            elif end_reason == 'enemy': result['countries']['B']['wars'].add('A')
            elif end_reason == 'expiry': flags(result, 'B').discard(family_flag(kind, 'live'))
            elif end_reason == 'idea_removed': result['countries']['B']['ideas'].discard(idea(kind))
            elif end_reason == 'provider_dead': result['countries']['A']['exists'] = False
            else: vars_(result, 'B')[family_var(kind)] = 999
            daily(result); assert not owned(result, 'B', kind) and idea(kind) not in result['countries']['B']['ideas']
            assert not vars_(result, 'B').get(family_var(kind)) and cash(result) == wallet
            before = snapshot(result); daily(result); assert snapshot(result) == before
            groups['active_' + end_reason + '_cleans_owned_bonus_once_without_refund_or_extra_fee'] += 1

        for actor, partner in (('A', 'B'), ('B', 'A')):
            result = state(); assert send(result, kind); assert reply(result, kind); wallet = cash(result)
            assert action(result, 'end_' + kind_name(kind), actor, partner)
            assert not owned(result, 'B', kind) and idea(kind) not in result['countries']['B']['ideas'] and cash(result) == wallet
            before = snapshot(result); assert not action(result, 'end_' + kind_name(kind), actor, partner, True); assert snapshot(result) == before
            groups['either_contract_party_can_end_own_type_without_double_cleanup_or_fee_refund'] += 1

        result = state(); assert send(result, kind); assert reply(result, kind); before = snapshot(result)
        assert not action(result, 'end_' + kind_name(kind), 'C', 'B', True) and snapshot(result) == before
        assert not action(result, 'end_' + kind_name(3-kind), 'A', 'B', True) and snapshot(result) == before
        groups['third_party_and_other_type_cannot_end_an_owned_service'] += 1

        result = state(); result['countries']['B']['ideas'].add(idea(kind)); wallet = cash(result)
        assert not send(result, kind); daily(result)
        assert idea(kind) in result['countries']['B']['ideas'] and cash(result) == wallet
        groups['preupgrade_unsigned_native_idea_blocks_replacement_and_is_not_removed_by_cleanup'] += 1

        result = state(); result['countries']['B']['ideas'].add(idea(kind)); flags(result, 'B').add(family_flag(kind, 'live')); vars_(result, 'B')[family_var(kind)] = 'A'
        daily(result); assert idea(kind) in result['countries']['B']['ideas'] and not vars_(result, 'B').get(family_var(kind))
        groups['orphan_active_live_marker_has_no_right_to_remove_unowned_native_idea'] += 1

        for hook in ('on_annex', 'on_subject_annexed'):
            for victim in ('A', 'B'):
                for already_dead in (False, True):
                    result = state(); assert send(result, kind); assert reply(result, kind); wallet = cash(result)
                    result['countries'][victim]['exists'] = not already_dead
                    root, from_ = ('D', victim) if hook == 'on_annex' else (victim, 'D')
                    native_hook(result, hook, root, from_)
                    assert not owned(result, 'B', kind) and idea(kind) not in result['countries']['B']['ideas'] and cash(result) == wallet
                    before = snapshot(result); native_hook(result, hook, root, from_); assert snapshot(result) == before
                    groups['both_annex_hook_roles_before_and_after_death_clean_contract_without_inheritance_or_refund'] += 1

                    result = state(); assert send(result, kind); wallet = cash(result)
                    result['countries'][victim]['exists'] = not already_dead
                    native_hook(result, hook, root, from_)
                    assert not pending(result) and cash(result) == wallet and not owned(result, 'B', kind)
                    before = snapshot(result); reply(result, kind, force=True); assert snapshot(result) == before
                    groups['both_annex_hook_roles_before_and_after_death_retire_pending_callback_without_fee'] += 1

    result = state(); assert send(result, 1); assert send(result, 2, provider='D'); assert reply(result, 1); assert reply(result, 2, provider='D')
    assert owned(result, 'B', 1) and owned(result, 'B', 2) and cash(result) == {'A': 103, 'B': 93, 'C': 100, 'D': 104}
    assert action(result, 'end_logistics'); assert not owned(result, 'B', 1) and owned(result, 'B', 2)
    groups['independent_types_and_providers_can_coexist_with_separate_payment_and_termination'] += 1

    result = state(); assert send(result, 1); assert send(result, 1, provider='D'); assert reply(result, 1, provider='D'); wallet = cash(result)
    assert not reply(result, 1, force=True) and cash(result) == wallet and vars_(result, 'B')[family_var(1)] == 'D' and not pending(result)
    groups['competing_pending_providers_first_consent_owns_slot_second_cannot_take_fee_or_replace_provider'] += 1

    result = state(); result['countries']['D']['wars'].add('C'); assert send(result, 1); assert send(result, 2, provider='B', receiver='D')
    assert pending(result, 'A') and pending(result, 'B') and reply(result, 1) and reply(result, 2, provider='B', receiver='D')
    assert owned(result, 'B', 1) and owned(result, 'D', 2)
    groups['receiving_contract_does_not_block_distinct_own_provider_pending_channel'] += 1

    result = state(); result['countries']['A']['wars'].add('D'); assert send(result, 1); assert reply(result, 1); assert send(result, 1, provider='B', receiver='A'); assert reply(result, 1, provider='B', receiver='A')
    assert owned(result, 'A', 1) and owned(result, 'B', 1); assert action(result, 'end_logistics')
    assert not owned(result, 'A', 1) and not owned(result, 'B', 1)
    groups['one_end_action_explicitly_terminates_both_matching_directed_same_type_contracts'] += 1

    for legacy in ('military_services_sent_logistics', 'military_services_sent_recon'):
        result = state(); flags(result, 'A').add(legacy); assert not send(result)
        events = model['get_event_map'](read('events/00_Influence_events.txt')); wallet = cash(result)
        effect(result, option(events, 'influence.506', 'influence.506.c'))
        assert cash(result) == wallet and not {legacy} & flags(result, 'A') and not owned(result, 'B', 1)
        groups['legacy_global_offer_flag_locks_new_offer_until_unsigned_notice_closed_without_payment'] += 1

    result = state(); assert send(result); flags(result, 'A').add('military_services_sent_recon'); before = snapshot(result)
    events = model['get_event_map'](read('events/00_Influence_events.txt')); effect(result, option(events, 'influence.506', 'influence.506.c'))
    assert snapshot(result) == before
    groups['legacy_callback_cannot_clear_or_mutate_current_owned_pending_record'] += 1

    for suffix in ('a', 'b', 'c'):
        result = state(payer=1); flags(result, 'A').update(('military_services_sent_logistics', 'military_services_sent_recon'))
        result['countries']['B']['ideas'].update((idea(1), idea(2))); wallet = cash(result)
        effect(result, option(events, 'influence.506', 'influence.506.' + suffix))
        assert cash(result) == wallet and {idea(1), idea(2)} <= result['countries']['B']['ideas']
        assert not {'military_services_sent_logistics', 'military_services_sent_recon'} & flags(result, 'A')
        before = snapshot(result); effect(result, option(events, 'influence.506', 'influence.506.' + suffix)); assert snapshot(result) == before
        groups['every_retained_unsigned_legacy_option_closes_flags_once_preserving_cash_and_old_native_ideas'] += 1

    for kind in (1, 2):
        for invalid in ('peace', 'enemy', 'influence', 'industry', 'provider_dead', 'receiver_dead', 'ERI', 'old_flag', 'orphan_partner', 'orphan_kind'):
            result = state()
            if invalid == 'peace': result['countries']['B']['wars'].clear()
            elif invalid == 'enemy': result['countries']['B']['wars'].add('A')
            elif invalid == 'influence': result['countries']['B']['arrays']['influence_array'] = []
            elif invalid == 'industry': vars_(result, 'A')['num_of_military_factories'] = 10
            elif invalid == 'provider_dead': result['countries']['A']['exists'] = False
            elif invalid == 'receiver_dead': result['countries']['B']['exists'] = False
            elif invalid == 'ERI': result['countries']['A'].update(original_tag='ERI', leader='Eritrean Transitional Government'); flags(result, 'A').add('ETH_transitional_government_FLAG')
            elif invalid == 'old_flag': flags(result, 'A').add('military_services_sent_recon')
            elif invalid == 'orphan_partner': vars_(result, 'A')['eon_services_partner'] = 'D'
            else: vars_(result, 'A')['eon_services_kind'] = 2
            before = snapshot(result); assert not send(result, kind, force=True) and snapshot(result) == before
            groups['selection_' + invalid + '_fresh_guard_cannot_be_bypassed_by_stale_choice'] += 1

        for alternative in ('defense_industry', 'can_sent_military_aid'):
            result = state(); vars_(result, 'A')['num_of_military_factories'] = 0
            (result['countries']['A']['ideas'] if alternative == 'defense_industry' else flags(result, 'A')).add(alternative)
            assert send(result, kind) and reply(result, kind)
            groups['original_alternative_industry_or_national_capability_admission_remains_available'] += 1

        result = state(); result['countries']['A']['ai'] = True; result['countries']['B']['government'] = 'fascism'
        before = snapshot(result); assert not send(result, kind, force=True) and snapshot(result) == before
        groups['original_AI_provider_matching_government_entry_condition_preserved'] += 1
        result['countries']['B']['government'] = 'democratic'; assert send(result, kind) and reply(result, kind)
        groups['same_government_AI_provider_policy_allows_valid_existing_service'] += 1

        result = state(); result['countries']['B']['wars'].clear(); result['countries']['B']['civil_war'] = True
        assert send(result, kind) and reply(result, kind); daily(result); assert owned(result, 'B', kind)
        groups['civil_war_original_admission_and_active_war_requirement_preserved'] += 1

    response_events = model['get_event_map'](read('events/eon_services_events.txt'))
    for identity, event in response_events.items():
        result = state(); assert send(result); before = snapshot(result)
        choices = [val for key, op, val in event if key == 'option' and one(val, 'name') == 'eon_services.ack']
        assert len(choices) == 1
        effect(result, choices[0]); assert snapshot(result) == before
        groups['all_static_and_unmatched_ACKs_have_no_mutable_contract_effect'] += 1

    result = state(); ctx_a = context('A'); ctx_b = switch(ctx_a, 'B')
    result['temp'] = {'fixture_temp': 7}
    assert value(result, ctx_a, 'fixture_temp') == value(result, ctx_b, 'fixture_temp') == 7
    assert value(result, ctx_b, 'PREV.fixture_temp') == 0
    result['countries']['A']['variables']['fixture_temp'] = 11
    assert value(result, ctx_b, 'PREV.fixture_temp') == 11
    execute([('set_temp_variable', '=', [('fixture_temp', '=', '13')])], result, ctx_b)
    assert value(result, ctx_a, 'fixture_temp') == 13
    adapter_cases['native10_shared_execution_temporary_and_scoped_persistent_read'] += 1
    assert flag_name(result, ctx_b, 'probe@PREV') == 'probe@A'
    ctx_c = switch(ctx_b, 'C')
    assert flag_name(result, ctx_c, 'probe@PREV.PREV') == 'probe@A'
    result['temp']['partner_alias'] = 'A'
    result['countries']['B']['variables']['stored_alias'] = 'A'
    assert flag_name(result, ctx_b, 'probe@partner_alias') != 'probe@A'
    assert flag_name(result, ctx_b, 'probe@stored_alias') != 'probe@A'
    assert flag_name(result, ctx_b, 'probe@A') != 'probe@A'
    assert country_ref(result, ctx_b, 'var:stored_alias') == 'A'
    result['countries']['B']['variables']['variable_probe@A'] = 23
    assert value(result, ctx_b, 'variable_probe@A') == value(result, ctx_b, 'variable_probe@stored_alias') == 23
    assert value(result, ctx_b, 'variable_probe@PREV') == 23
    adapter_cases['native29_flag_suffix_scalar_is_not_a_country_scope_variable_alias_still_selects_country'] += 1
    original_selection = model['capacity_triggers']['eon_services_selection_ready']
    mutated_selection = deepcopy(original_selection); replacements = 0
    def mutate_scope(nodes):
        nonlocal replacements
        for index, (key, op, val) in enumerate(nodes):
            if key == 'set_temp_variable' and val == [('eon_services_policy_provider', '=', 'eon_services_selection_provider')]:
                nodes[index] = (key, op, [('eon_services_policy_provider', '=', 'PREV.eon_services_selection_provider')]); replacements += 1
            elif isinstance(val, list): mutate_scope(val)
    mutate_scope(mutated_selection); assert replacements == 1
    model['capacity_triggers']['eon_services_selection_ready'] = mutated_selection
    try:
        result = state(); assert not send(result) and not pending(result)
    finally: model['capacity_triggers']['eon_services_selection_ready'] = original_selection
    result = state(); assert send(result) and pending(result)
    adapter_cases['memory_only_old_scoped_temp_operand_regression_rejected'] += 1

if __name__ == '__main__':
    if sys.argv[1:]:
        assert len(sys.argv) == 3 and sys.argv[1] == '--focus', sys.argv[1:]
        focus(sys.argv[2])
    else: scenarios()
    source_paths = ['events/00_Influence_events.txt', 'common/scripted_effects/eon_services_effects.txt',
                    'common/scripted_triggers/eon_services_triggers.txt', 'common/scripted_diplomatic_actions/eon_services_actions.txt',
                    'common/on_actions/eon_services_on_actions.txt', 'events/eon_services_events.txt',
                    'localisation/english/eon_services_l_english.yml', 'localisation/russian/eon_services_l_russian.yml']
    print(json.dumps({'all_passed': True, 'baseline': BASELINE, 'actual_source_scenarios': sum(groups.values()),
                      'adapter_semantics_cases': sum(adapter_cases.values()), 'groups': dict(groups),
                      'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source_paths},
                      'proof_scope': 'bounded ordered current source service contracts and native10/29 calibrated scalar-read/flag adapter; not native HOI4 runtime'}, indent=2))
