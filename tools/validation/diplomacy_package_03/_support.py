"""Ordered actual-source interpreter for ordinary-alliance control flow.

Native rules, effective modifiers, tension, DLC and native effect outcomes are
explicit fixture inputs. This is not a HOI4 engine or its consent UI. Unknown
visited statements fail closed. Temporary variables share one invocation frame.
"""
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '5fa82c4bd9df099fc92c110983191fe8d4fdc47e'
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|[=<>!]+|[^\s{}=<>!#"]+')
BASELINE_BYTES = {}


@lru_cache(maxsize=None)
def baseline(path):
    if path in BASELINE_BYTES: return BASELINE_BYTES[path]
    return subprocess.check_output(['git', 'show', BASELINE + ':' + path], cwd=ROOT)


def prime_baselines(paths):
    """Read preserved blobs in one git process, including binary-safe byte lengths."""
    paths = list(dict.fromkeys(paths))
    assert all('\n' not in path and '\r' not in path for path in paths)
    result = subprocess.run(['git', 'cat-file', '--batch'], cwd=ROOT,
                            input=''.join(BASELINE + ':' + path + '\n' for path in paths).encode('utf-8'),
                            capture_output=True, check=True)
    offset = 0
    for path in paths:
        end = result.stdout.index(b'\n', offset)
        header = result.stdout[offset:end].split()
        assert len(header) == 3 and header[1] == b'blob', ('Missing baseline blob', path, header)
        length = int(header[2]); offset = end + 1
        BASELINE_BYTES[path] = result.stdout[offset:offset + length]
        offset += length
        assert result.stdout[offset:offset+1] == b'\n'; offset += 1
    assert offset == len(result.stdout), 'Unexpected git batch output'


def ast(source):
    if isinstance(source, bytes): source = source.decode('utf-8-sig')
    tokens = [m[0].strip('"') for m in TOKEN.finditer(source.lstrip('\ufeff'))
              if not m[0].startswith('#')]
    index = 0
    def body():
        nonlocal index
        result = []
        while index < len(tokens) and tokens[index] != '}':
            key = tokens[index]; index += 1
            if index == len(tokens) or tokens[index] not in ('=', '==', '<', '>', '<=', '>=', '!='):
                result.append(('__item__', '=', key)); continue
            op = tokens[index]; index += 1
            assert index < len(tokens), ('Missing value', key)
            if tokens[index] == '{':
                index += 1; value = body()
                assert index < len(tokens) and tokens[index] == '}', ('Unclosed block', key)
                index += 1
            else: value = tokens[index]; index += 1
            result.append((key, op, value))
        return result
    result = body(); assert index == len(tokens), 'Extra closing brace'
    return result


@lru_cache(maxsize=None)
def source(path): return ast((ROOT / path).read_bytes())


def one(nodes, key):
    matches = [v for k, op, v in nodes if k == key]
    assert len(matches) == 1, (key, len(matches))
    return matches[0]


def maybe(nodes, key, default=None):
    matches = [v for k, op, v in nodes if k == key]
    assert len(matches) <= 1, (key, len(matches))
    return matches[0] if matches else default


def compare(left, op, right):
    return {'=': left == right, '==': left == right, '!=': left != right,
            '<': left < right, '>': left > right, '<=': left <= right,
            '>=': left >= right}[op]


@dataclass
class Country:
    ident: int
    exists: bool = True
    subject: bool = False
    ai: bool = False
    government: str = 'democratic'
    original_tag: str = 'GEN'
    rules: dict = field(default_factory=lambda: {'can_create_factions': True, 'can_join_factions': True})
    native_modifiers: dict = field(default_factory=lambda: {'join_faction_tension': 0.0, 'ai_get_ally_desire_factor': 0.0})
    variables: dict = field(default_factory=dict)
    flags: set = field(default_factory=set)
    ideas: set = field(default_factory=set)
    wars: set = field(default_factory=set)
    defensive: bool = False
    offensive: bool = False
    faction: int | None = None
    is_sco: bool = False
    arrays: dict = field(default_factory=dict)
    continent: str = 'europe'
    opinions: dict = field(default_factory=dict)


class Model:
    def __init__(self, countries=None, root=1, from_=1, current=2, ncns=True,
                 tension=1.0, create_success=True, admission_success=True,
                 callbacks=True, create_callback_partner=0, legacy_template=None):
        self.countries = countries or {n: Country(n) for n in range(1, 5)}
        self.countries[0] = Country(0, exists=False, rules={})
        self.root, self.from_, self.current = root, from_, current
        self.ncns, self.tension = ncns, tension
        self.create_success, self.admission_success = create_success, admission_success
        self.callbacks, self.create_callback_partner = callbacks, create_callback_partner
        self.legacy_template = legacy_template
        self.game_rules = {'allow_mp_optimizations': 'no'}
        self.temp, self.factions, self.native_calls = {}, {}, []
        self.next_faction = 100
        self.effects, self.triggers = {}, {}
        for kind, target in (('effects', self.effects), ('triggers', self.triggers)):
            for path in sorted((ROOT / ('common/scripted_' + kind)).glob('eon_defensive_alliance*_' + kind + '.txt')):
                for key, op, value in source(str(path.relative_to(ROOT)).replace('\\', '/')):
                    assert key not in target, ('Duplicate helper', key)
                    target[key] = value
        native = source('common/scripted_triggers/00_game_rule_triggers.txt')
        for key in ('DIPLOMACY_CALL_ALLY_ENABLE_TRIGGER', 'DIPLOMACY_JOIN_ALLY_ENABLE_TRIGGER',
                    'DIPLOMACY_JOIN_FACTION_ENABLE_TRIGGER', 'DIPLOMACY_OFFER_JOIN_FACTION_ENABLE_TRIGGER'):
            self.triggers[key] = one(native, key)
        self.triggers['is_same_government_THIS_ROOT'] = one(source(
            'common/scripted_triggers/00_influence_scripted_triggers.txt'), 'is_same_government_THIS_ROOT')
        action_source = one(source('common/scripted_diplomatic_actions/eon_defensive_alliance_action.txt'),
                            'scripted_diplomatic_actions')
        self.action = one(action_source, 'eon_propose_defensive_alliance')
        on_action_source = source('common/on_actions/eon_defensive_alliance_on_actions.txt')
        self.on_actions = one(on_action_source, 'on_actions')

    def ref(self, token, stack):
        if token == 'ROOT': return self.root
        if token == 'FROM': return self.from_
        if token == 'THIS': return stack[-1]
        if token == 'PREV':
            assert len(stack) > 1, 'PREV without ancestor'
            return stack[-2]
        if token.startswith('var:'): return int(self.value(token[4:], stack))
        try: result = int(token)
        except ValueError:
            matches = [n for n, c in self.countries.items() if c.original_tag == token]
            assert len(matches) == 1, ('Unknown country reference', token)
            result = matches[0]
        assert result in self.countries, ('Unknown country id', result)
        return result

    def value(self, token, stack):
        assert isinstance(token, str), ('Non-scalar value', token)
        if token.startswith('var:'): token = token[4:]
        try: return float(token)
        except ValueError: pass
        if token in ('ROOT', 'THIS', 'FROM', 'PREV'): return self.ref(token, stack)
        if token.startswith('modifier@'):
            name = token.split('@', 1)[1]
            assert name in self.countries[stack[-1]].native_modifiers, ('Unknown native modifier', name)
            return self.countries[stack[-1]].native_modifiers[name]
        if token in ('threat', 'global.threat'): return self.tension
        parts, owner, ancestor = token.split('.'), stack[-1], len(stack) - 1
        while len(parts) > 1:
            scope = parts.pop(0)
            if scope == 'PREV':
                ancestor -= 1; assert ancestor >= 0, 'Dotted PREV without ancestor'
                owner = stack[ancestor]
            elif scope in ('ROOT', 'FROM', 'THIS'):
                owner = self.ref(scope, stack)
            else: raise AssertionError(('Unknown variable scope', scope))
        key = parts[0]
        if key == 'id': return owner
        return self.temp.get(key, self.countries[owner].variables.get(key, 0))

    def flag(self, token, stack):
        if '@' not in token: return token
        name, target = token.split('@', 1)
        return name + '@' + str(self.ref(target, stack))

    def variable_check(self, nodes, stack):
        if any(k == 'var' for k, op, v in nodes):
            key, amount = one(nodes, 'var'), one(nodes, 'value')
            mode = maybe(nodes, 'compare', 'equals')
            operator = {'equals': '=', 'not_equals': '!=', 'greater_than': '>',
                        'greater_than_or_equals': '>=', 'less_than': '<',
                        'less_than_or_equals': '<='}[mode]
        else:
            assert len(nodes) == 1, ('Unexpected variable check', nodes)
            key, operator, amount = nodes[0]
        return compare(self.value(key, stack), operator, self.value(amount, stack))

    def trigger(self, nodes, stack=None):
        stack = [self.current] if stack is None else stack
        index = 0
        while index < len(nodes):
            key, op, value = nodes[index]; index += 1
            country = self.countries[stack[-1]]
            if key == 'tooltip': continue
            if key in self.triggers: passed = self.trigger(self.triggers[key], stack) == (value == 'yes')
            elif key in ('ROOT', 'FROM', 'THIS', 'PREV') or key.startswith('var:'):
                passed = self.trigger(value, stack + [self.ref(key, stack)])
            elif key == 'faction_leader':
                leader = self.factions[country.faction]['leader'] if country.faction is not None else 0
                passed = self.trigger(value, stack + [leader])
            elif key == 'capital_scope':
                # Only the explicit fixture continent is read; no state/geography simulation.
                passed = self.trigger(value, stack + [country.ident])
            elif key in ('AND', 'custom_trigger_tooltip', 'hidden_trigger'): passed = self.trigger(value, stack)
            elif key == 'NOT': passed = not self.trigger(value, stack)
            elif key == 'OR': passed = any(self.trigger([n], stack) for n in value)
            elif key == 'if':
                branches = [value]
                while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                    branches.append(nodes[index][2]); index += 1
                passed = True
                for branch in branches:
                    if self.trigger(maybe(branch, 'limit', []), stack):
                        passed = self.trigger([n for n in branch if n[0] != 'limit'], stack); break
            elif key in ('set_temp_variable', 'clamp_temp_variable'):
                self.effect([(key, op, value)], stack); passed = True
            elif key == 'always': passed = value == 'yes'
            elif key == 'exists': passed = country.exists == (value == 'yes')
            elif key == 'is_subject': passed = country.subject == (value == 'yes')
            elif key == 'is_ai': passed = country.ai == (value == 'yes')
            elif key == 'has_government':
                expected = self.countries[self.ref(value, stack)].government if value in ('FROM', 'ROOT', 'PREV', 'THIS') or value.startswith('var:') else value
                passed = country.government == expected
            elif key == 'original_tag': passed = country.original_tag == value
            elif key == 'tag': passed = country.ident == self.ref(value, stack)
            elif key == 'has_idea': passed = value in country.ideas
            elif key == 'has_country_flag': passed = self.flag(value, stack) in country.flags
            elif key == 'has_rule':
                if isinstance(value, str): passed = country.rules.get(value, False)
                else:
                    assert len(value) == 1
                    rule, operator, expected = value[0]; assert operator == '='
                    passed = country.rules.get(rule, False) == (expected == 'yes')
            elif key == 'has_game_rule': passed = self.game_rules.get(one(value, 'rule')) == one(value, 'option')
            elif key == 'has_dlc':
                assert value == 'No Compromise, No Surrender', ('Unknown DLC', value)
                passed = self.ncns
            elif key == 'has_defensive_war': passed = country.defensive == (value == 'yes')
            elif key == 'has_offensive_war': passed = country.offensive == (value == 'yes')
            elif key == 'has_war_with': passed = self.ref(value, stack) in country.wars
            elif key == 'has_opinion':
                target = self.ref(one(value, 'target'), stack)
                term = next(node for node in value if node[0] == 'value')
                passed = compare(country.opinions.get(target, 0), term[1], self.value(term[2], stack))
            elif key == 'is_in_faction': passed = (country.faction is not None) == (value == 'yes')
            elif key == 'is_faction_leader':
                leader = country.faction is not None and self.factions[country.faction]['leader'] == country.ident
                passed = leader == (value == 'yes')
            elif key == 'is_in_faction_with':
                passed = country.faction is not None and country.faction == self.countries[self.ref(value, stack)].faction
            elif key == 'has_faction_template':
                passed = country.faction is not None and self.factions[country.faction]['template'] == value
            elif key == 'num_faction_members':
                number = sum(c.faction == country.faction for c in self.countries.values()) if country.faction is not None else 0
                passed = compare(number, op, self.value(value, stack))
            elif key == 'check_variable': passed = self.variable_check(value, stack)
            elif key == 'threat': passed = compare(self.tension, op, self.value(value, stack))
            elif key == 'is_sco': passed = country.is_sco == (value == 'yes')
            elif key == 'is_on_continent': passed = country.continent == value
            elif key == 'is_in_array':
                if any(k == 'array' for k, op, v in value):
                    array, item = one(value, 'array'), one(value, 'value')
                else:
                    assert len(value) == 1
                    array, operator, item = value[0]; assert operator == '='
                passed = self.value(item, stack) in country.arrays.get(array, [])
            elif key == 'any_allied_country':
                passed = any(self.trigger(value, stack + [n]) for n, c in self.countries.items()
                             if n != country.ident and country.faction is not None and c.faction == country.faction)
            else: raise AssertionError(('Unsupported trigger', key, op, value))
            if not passed: return False
        return True

    def effect(self, nodes, stack=None):
        if stack is None: self.temp = {}; stack = [self.current]
        index = 0
        while index < len(nodes):
            key, op, value = nodes[index]; index += 1
            country = self.countries[stack[-1]]
            if key in ('log', 'custom_effect_tooltip'): continue
            if key in self.effects:
                assert value == 'yes'; self.effect(self.effects[key], stack)
            elif key in ('ROOT', 'FROM', 'THIS', 'PREV') or key.startswith('var:'):
                self.effect(value, stack + [self.ref(key, stack)])
            elif key == 'faction_leader':
                assert country.faction is not None
                self.effect(value, stack + [self.factions[country.faction]['leader']])
            elif key in ('every_allied_country', 'every_faction_member', 'every_other_country', 'every_country'):
                if key in ('every_allied_country', 'every_faction_member'):
                    targets = [n for n, c in self.countries.items() if country.faction is not None and c.faction == country.faction
                               and (key == 'every_faction_member' or n != country.ident)]
                else: targets = [n for n, c in self.countries.items() if c.exists and (key == 'every_country' or n != country.ident)]
                for target in targets:
                    nested = stack + [target]
                    if self.trigger(maybe(value, 'limit', []), nested):
                        self.effect([n for n in value if n[0] != 'limit'], nested)
            elif key == 'if':
                branches = [value]
                while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                    branches.append(nodes[index][2]); index += 1
                for branch in branches:
                    if self.trigger(maybe(branch, 'limit', []), stack):
                        self.effect([n for n in branch if n[0] != 'limit'], stack); break
            elif key in ('set_variable', 'set_temp_variable'):
                assert len(value) == 1
                name, operator, amount = value[0]; assert operator == '='
                (self.temp if key == 'set_temp_variable' else country.variables)[name] = self.value(amount, stack)
            elif key == 'clamp_temp_variable':
                name = one(value, 'var')
                self.temp[name] = min(self.value(one(value, 'max'), stack), max(self.value(one(value, 'min'), stack), self.temp.get(name, 0)))
            elif key == 'clear_variable': country.variables.pop(value, None)
            elif key == 'set_country_flag': country.flags.add(self.flag(value, stack))
            elif key == 'clr_country_flag': country.flags.discard(self.flag(value, stack))
            elif key in ('create_faction', 'create_faction_from_template'):
                self.native_calls.append((country.ident, key, value))
                if self.create_success:
                    assert country.faction is None, 'Native creation would overwrite existing faction'
                    template = (one(value, 'template') if isinstance(value, list) else value) if key.endswith('from_template') else self.legacy_template
                    self.make_faction(country.ident, template)
                    if self.callbacks: self.callback('on_create_faction', country.ident, self.create_callback_partner)
            elif key == 'add_to_faction':
                target = self.ref(value, stack); self.native_calls.append((country.ident, key, target))
                if self.admission_success:
                    assert country.faction is not None and self.countries[target].faction is None
                    self.countries[target].faction = country.faction
                    if self.callbacks:
                        self.callback('on_offer_join_faction', country.ident, target)
                        self.callback('on_join_faction', target, country.ident)
            elif key == 'dismantle_faction':
                assert value == 'yes'; self.native_calls.append((country.ident, key, value))
                old = country.faction
                if old is not None:
                    for c in self.countries.values():
                        if c.faction == old: c.faction = None
                    self.factions.pop(old)
            else: raise AssertionError(('Unsupported effect', key, op, value))

    def make_faction(self, leader, template=None, members=()):
        ident = self.next_faction; self.next_faction += 1
        self.factions[ident] = {'leader': leader, 'template': template}
        for n in (leader, *members): self.countries[n].faction = ident
        return ident

    def callback(self, name, current, from_):
        matches = [v for k, op, v in self.on_actions if k == name]
        saved = (self.root, self.from_, self.current, self.temp)
        self.root, self.current, self.from_ = current, current, from_
        self.temp = {}
        try:
            for nodes in matches: self.effect(maybe(nodes, 'effect', []), [current])
        finally: self.root, self.from_, self.current, self.temp = saved

    def gate(self, key, current=None, from_=None, root=None):
        saved = (self.root, self.from_, self.current, self.temp)
        if current is not None: self.current = current
        if from_ is not None: self.from_ = from_
        if root is not None: self.root = root
        self.temp = {}
        try: return self.trigger(self.triggers[key], [self.current])
        finally: self.root, self.from_, self.current, self.temp = saved

    def action_effect(self, key):
        self.effect(one(self.action, key))

    def ai_source_score(self):
        """Actual reason arithmetic only; not native acceptance probability."""
        self.temp = {}; result = 0.0
        for key, op, reason in one(self.action, 'ai_acceptance'):
            result += self.value(one(reason, 'base'), [self.current])
            for name, operator, modifier in reason:
                if name == 'base': continue
                assert name == 'modifier', ('Unknown AI reason term', name)
                if self.trigger([n for n in modifier if n[0] != 'add']):
                    result += self.value(one(modifier, 'add'), [self.current])
        return result


def blocks(data):
    """Raw byte boundaries, including parent/depth, for exact restore checks."""
    token = re.compile(rb'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|[=<>!]+|[^\s{}=<>!#"]+')
    tokens = [m for m in token.finditer(data) if not m[0].startswith(b'#')]
    stack, result = [], []
    for i, item in enumerate(tokens):
        if item[0] == b'{':
            assert i >= 2 and tokens[i-1][0] == b'='
            block = {'key': tokens[i-2][0].decode('utf-8-sig'), 'start': tokens[i-2].start(),
                     'depth': len(stack), 'parent': stack[-1]['key'] if stack else None}
            stack.append(block); result.append(block)
        elif item[0] == b'}':
            assert stack, 'Extra closing brace'; stack.pop()['end'] = item.end()
    assert not stack, 'Unclosed block'
    return result


def format_preserved(before, after):
    assert before.startswith(b'\xef\xbb\xbf') == after.startswith(b'\xef\xbb\xbf'), 'BOM changed'
    def eol(data):
        return (b'\r\n' in data, b'\n' in data.replace(b'\r\n', b''), b'\r' in data.replace(b'\r\n', b''))
    assert eol(before) == eol(after), 'Line endings changed/mixed'
    assert before.endswith(b'\n') == after.endswith(b'\n'), 'EOF newline changed'
    after.decode('utf-8-sig')
