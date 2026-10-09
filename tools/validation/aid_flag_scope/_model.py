"""Narrow current-AST aid gate interpreter, never a native campaign simulator.

Native29 calibrated country-flag selectors: actual ROOT/FROM/THIS/PREV scopes
select a country; scalar suffixes remain literal. Temporary values are shared
within the execution. Scope-qualified VARIABLE reads still read persistent data.
No economic updater, event delivery, refund, or native GUI rendering is modeled.
"""
from copy import deepcopy
import re

TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|[=<>!]+|[^\s{}=<>!#"]+')


def ast(text):
    tokens = [m[0].strip('"') for m in TOKEN.finditer(text.lstrip('\ufeff'))
              if not m[0].startswith('#')]
    position = 0

    def parse():
        nonlocal position
        result = []
        while position < len(tokens) and tokens[position] != '}':
            key = tokens[position]
            position += 1
            assert tokens[position] in ('=', '<', '>', '<=', '>=', '!=', '==')
            operator = tokens[position]
            position += 1
            if tokens[position] == '{':
                position += 1
                value = parse()
                assert tokens[position] == '}'
                position += 1
            else:
                value = tokens[position]
                position += 1
            result.append((key, operator, value))
        return result

    result = parse()
    assert position == len(tokens)
    return result


def one(nodes, key):
    values = [v for k, o, v in nodes if k == key]
    assert len(values) == 1, (key, len(values))
    return values[0]


def context(root, recipient, from_=None):
    return {'root': root, 'scope': recipient, 'from': from_, 'prev': ()}


def switch(frame, country):
    return {**frame, 'scope': country, 'prev': (frame['scope'],) + frame['prev']}


def value(state, frame, key):
    try:
        return float(key)
    except (TypeError, ValueError):
        pass
    if key == 'ROOT':
        return frame['root']
    if key == 'THIS':
        return frame['scope']
    if key == 'FROM':
        return frame['from']
    if key == 'PREV':
        assert frame['prev'], 'PREV without a real prior country frame'
        return frame['prev'][0]
    if key.startswith('var:'):
        return value(state, frame, key[4:])
    explicit = '.' in key and key.split('.', 1)[0] in ('ROOT', 'THIS', 'FROM', 'PREV')
    if explicit:
        prefix, key = key.split('.', 1)
        return persistent(state, switch(frame, value(state, frame, prefix)), key)
    if key in state['temp']:
        return state['temp'][key]
    if key in state['tags']:
        return state['tags'][key]
    return persistent(state, frame, key)


def persistent(state, frame, key):
    country = state['countries'].get(frame['scope'], {})
    if key == 'id':
        return frame['scope']
    if '^' in key:
        name, index = key.split('^', 1)
        values = country.get('arrays', {}).get(name, [])
        index = int(value(state, frame, index))
        return values[index] if 0 <= index < len(values) else 0
    return country.get('vars', {}).get(key, 0)


def flag(state, frame, key):
    if '@' in key:
        prefix, selector = key.split('@', 1)
        if selector in ('ROOT', 'THIS', 'FROM', 'PREV'):
            return (prefix, value(state, frame, selector))
    # No substitution of scalar aliases or literal country tags into flag keys.
    return key


def compare(left, operator, right):
    return {'=': lambda: left == right, '==': lambda: left == right,
            '!=': lambda: left != right, '>': lambda: left > right,
            '<': lambda: left < right, '>=': lambda: left >= right,
            '<=': lambda: left <= right}[operator]()


def trigger(nodes, state, frame, definitions):
    position = 0
    while position < len(nodes):
        key, operator, body = nodes[position]
        position += 1
        country = state['countries'].get(frame['scope'], {})
        if key in definitions:
            passed = trigger(definitions[key], state, frame, definitions) == (body == 'yes')
        elif key == 'NOT':
            passed = not trigger(body, state, frame, definitions)
        elif key in ('AND', 'custom_trigger_tooltip'):
            meaningful = [node for node in body if node[0] != 'tooltip']
            passed = trigger(meaningful, state, frame, definitions)
        elif key == 'OR':
            passed = any(trigger([node], state, frame, definitions) for node in body)
        elif key == 'if':
            branches = [body]
            while position < len(nodes) and nodes[position][0] in ('else_if', 'else'):
                branches.append(nodes[position][2])
                position += 1
            passed = True
            for branch in branches:
                limits = [v for k, o, v in branch if k == 'limit']
                if not limits or trigger(limits[0], state, frame, definitions):
                    passed = trigger([node for node in branch if node[0] != 'limit'],
                                     state, frame, definitions)
                    break
        elif key == 'exists':
            passed = country.get('exists', False) == (body == 'yes')
        elif key in ('tag', 'original_tag'):
            passed = country.get('tag') == body if key == 'original_tag' else frame['scope'] == value(state, frame, body)
        elif key == 'has_war_with':
            passed = value(state, frame, body) in country.get('wars', set())
        elif key == 'has_country_leader':
            passed = country.get('leader') == one(body, 'name')
        elif key == 'has_country_flag':
            passed = flag(state, frame, body) in country.get('flags', set())
        elif key == 'check_variable':
            if any(k == 'var' for k, o, v in body):
                operations = {'greater_than_or_equals': '>=', 'less_than_or_equals': '<=',
                              'greater_than': '>', 'less_than': '<', 'equals': '='}
                left, right = one(body, 'var'), one(body, 'value')
                choices = [v for k, o, v in body if k == 'compare']
                operation = operations[choices[0]] if choices else '='
            else:
                assert len(body) == 1
                left, operation, right = body[0]
            passed = compare(value(state, frame, left), operation, value(state, frame, right))
        elif key in ('set_temp_variable', 'multiply_temp_variable'):
            assert len(body) == 1
            name, op, source = body[0]
            assert op == '=' and '.' not in name
            source = value(state, frame, source)
            state['temp'][name] = source if key == 'set_temp_variable' else value(state, frame, name) * source
            passed = True
        elif key in ('ROOT', 'THIS', 'FROM', 'PREV') or key.startswith('var:'):
            selected = value(state, frame, key)
            passed = selected in state['countries'] and trigger(body, state, switch(frame, selected), definitions)
        else:
            raise AssertionError(('Unhandled actual aid trigger', key, operator, body))
        if not passed:
            return False
    return True


def write_flags(nodes, state, frame):
    """Execute only extracted current source flag-writer scope islands."""
    for key, operator, body in nodes:
        if key == 'set_country_flag':
            assert isinstance(body, str)
            state['countries'][frame['scope']]['flags'].add(flag(state, frame, body))
        elif key == 'PREV' or key.startswith('var:'):
            selected = value(state, frame, key)
            assert selected in state['countries']
            write_flags(body, state, switch(frame, selected))
        else:
            raise AssertionError(('Non-writer island', key))


def fixture(donor=101, recipient=202, other=303):
    countries = {}
    for identity, tag in ((donor, 'USA'), (recipient, 'SWI'), (other, 'GER')):
        countries[identity] = {'exists': True, 'tag': tag, 'flags': set(), 'wars': set(),
                              'vars': {'gdp_total': 20, 'num_of_civilian_factories': 5, 'treasury': 100},
                              'arrays': {'influence_array': []}}
    countries[donor]['vars'].update(gdp_total=100, num_of_civilian_factories=50)
    countries[recipient]['arrays']['influence_array'] = [donor]
    return {'countries': countries, 'tags': {'USA': donor, 'SWI': recipient, 'GER': other, 'ERI': 404},
            'temp': {'eon_aid_policy_donor': donor}}, donor, recipient, other


def evaluate(definitions, name, state, frame):
    return trigger(definitions[name], deepcopy(state), frame, definitions)
