"""Actual consultation AST with native-calibrated flag selectors.

Native24/29 distinguish literal flag suffixes from a real country scope. Only
ROOT/FROM/THIS/PREV are resolved for flags here. Numeric/country variables keep
their separate existing selector semantics. The adapter has no native timer,
popup delivery, GUI, save/load or multiplayer implementation.
"""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
FILES = (
    'common/scripted_effects/eon_consultation_effects.txt',
    'common/scripted_triggers/eon_consultation_triggers.txt',
)


def executor(overrides=None):
    origin = ROOT / 'tools/validation/diplomacy_package_07/test_consultations.py'
    source = origin.read_text(encoding='utf-8')
    boundary = '# Native NOT is NOR'
    assert source.count(boundary) == 1
    legacy_path = ROOT / 'tools/validation/diplomacy_package_01/_support.py'
    spec = importlib.util.spec_from_file_location('consultation_origin_support', legacy_path)
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)
    prior = sys.modules.get('_support')
    sys.modules['_support'] = legacy
    env = {'__file__': str(origin), '__name__': 'consultation_actual_ast_executor'}
    try:
        exec(compile(source.split(boundary)[0], str(origin), 'exec'), env)
    finally:
        if prior is None:
            sys.modules.pop('_support', None)
        else:
            sys.modules['_support'] = prior
    model = env['model']
    for key in ('effects', 'capacity_triggers'):
        for name in list(model[key]):
            if name.startswith('eon_consultation_'):
                del model[key][name]
    for rel, target in zip(FILES, ('effects', 'capacity_triggers')):
        raw = (overrides or {}).get(rel, (ROOT / rel).read_bytes())
        model[target].update({name: body for name, op, body in env['ast'](raw.decode('utf-8-sig'))})

    def native_flag_name(state, context, name):
        if '@' not in name:
            return name
        field, selector = name.split('@', 1)
        if selector in ('ROOT', 'FROM', 'THIS', 'PREV'):
            target = model['country_ref'](state, context, selector)
            assert target is not None, ('Missing actual country flag scope', name, context)
            return field + '@country:' + target
        # Literal country tags and arbitrary scalar names are not resolved.
        return name

    model['flag_name'] = native_flag_name
    env['native_flag_name'] = native_flag_name
    origin_value = model['value']

    def native_value(state, context, expression):
        if isinstance(expression, str) and '.' in expression:
            head, tail = expression.split('.', 1)
            if head in ('ROOT', 'FROM', 'THIS', 'PREV') or head in state['countries']:
                target = model['country_ref'](state, context, head)
                assert target in state['countries'], ('Missing scoped scalar', expression, context)
                if tail == 'id':
                    return target
                # Current core scoped operands are persistent scalar fields.
                # Native10 does not resolve an execution temporary here.
                assert '^' not in tail and '@' not in tail, ('Outside this bounded adapter', expression)
                return state['countries'][target]['variables'].get(tail, 0)
        return origin_value(state, context, expression)

    model['value'] = native_value
    env['value'] = native_value
    env['actions'] = env['ast']((ROOT / 'common/scripted_diplomatic_actions/eon_consultation_actions.txt').read_text(encoding='utf-8-sig'))
    env['actions'] = env['one'](env['actions'], 'scripted_diplomatic_actions')
    env['events'] = {
        env['one'](body, 'id'): body
        for name, op, body in env['ast']((ROOT / 'events/eon_consultation_events.txt').read_text(encoding='utf-8-sig'))
        if name == 'country_event'
    }
    return env


def flag(field, peer):
    return field + '@country:' + peer


def resources(state):
    return {tag: {
        'variables': {key: deepcopy(value) for key, value in country['variables'].items()
                      if not key.startswith('eon_consultation_') and key != 'political_power'},
        'flags': {value for value in country['flags'] if not value.startswith('eon_consultation_')},
        'arrays': deepcopy(country['arrays']),
        'wars': deepcopy(country['wars']),
        'ideas': deepcopy(country['ideas']),
        'opinions': deepcopy(country['opinions']),
    } for tag, country in state['countries'].items()}


def preserved(state):
    result = deepcopy(state['countries'])
    return result


def helper(env, state, name, actor='A', peer='B', temps=None):
    env['effect'](state, [('eon_consultation_' + name, '=', 'yes')], env['context'](actor, peer), temps)


def predicate(env, state, name, actor='A', peer='B', scope=None, temps=None):
    return env['check'](state, [('eon_consultation_' + name, '=', 'yes')],
                        env['context'](actor, peer, scope), temps)


def draft(env, actor='A', peer='B'):
    state = env['state']()
    assert env['action'](state, 'eon_open_economic_consultations', actor, peer)
    env['immediate'](state, 'eon_consultation.0', peer, actor)
    return state


def request(env, topic=1, actor='A', peer='B'):
    state = draft(env, actor, peer)
    event = env['queued'](state, 'eon_consultation.1', actor, peer)
    state['events'].remove(event)
    topic_name = {1: 'trade', 2: 'energy', 3: 'support'}[topic]
    assert env['option_effect'](state, 'eon_consultation.1', 'eon_consultation_topic_' + topic_name, actor, peer)
    return state


def expire(env, state, stage, actor='A', peer='B'):
    window = 'eon_consultation_' + ('draft_window' if stage == 'draft' else 'response_window')
    state['countries'][actor]['flags'].discard(window)
    state['countries'][peer]['flags'].discard(window)
    helper(env, state, 'daily_cleanup', actor, peer)


def consume_reply(env, state, topic=1, choice='accept', actor='A', peer='B'):
    identity = {1: 'eon_consultation.10', 2: 'eon_consultation.11', 3: 'eon_consultation.12'}[topic]
    event = env['queued'](state, identity, peer, actor)
    state['events'].remove(event)
    option = 'eon_consultation_' + ('accept_talks' if choice == 'accept' else 'decline_talks')
    env['option_effect'](state, identity, option, peer, actor, force=True)


def clear_recent(state, actor='A', peer='B'):
    state['countries'][actor]['flags'].discard(flag('eon_consultation_recent_contact', peer))
    state['countries'][peer]['flags'].discard(flag('eon_consultation_recent_contact', actor))
