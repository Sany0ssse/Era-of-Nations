"""Exact fused-boundary inverse; behavioral models delegate native aggregation.

The entire CURRENT helper is certified against exact before islands and their
dependency closure. No GDP/finance algorithm is simulated or projected here.
Unknown bytes remain visible to each consumer's historical whole-file guard.
"""
from pathlib import Path
import copy, hashlib, importlib.util

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
MONEY = 'common/scripted_effects/00_money_system.txt'
DELIVERY = 'common/scripted_effects/eon_energy_delivery_effects.txt'
DAMAGE = 'common/scripted_effects/00_damaged_buildings_count.txt'
HELPER = 'common/scripted_effects/eon_economy_state_refresh_effects.txt'
DYNAMIC = 'common/dynamic_modifiers/00_money_dynamic_modifiers.txt'
NAME = 'eon_economy_refresh_state_and_damage'
FIXTURE_SHA = '47fd8b2686ebd67705f4a2664404ed55d9df6a8387a6e2d8d9b20b3df8087717'
HELPER_SHA = '125166a536bc287069e2cd5fcf4e67331f217fbeb15fb2dfd22e789667572c6d'
DAMAGE_SHA = '2354acfdb03805661b4b33cf11d8d3a895e50e0330026d188a6b39f3adb1eae2'
DYNAMIC_SHA = 'af9a6b67eab84f495bbf09b018676f47c85a864600634cc9f43093ab511d2939'
PAIRS = {
    MONEY: (b'\teon_economy_refresh_state_and_damage = yes',
            b'\tcalculate_damaged_buildings_count = yes\n\tupdate_state_variables = yes'),
    DELIVERY: (b' eon_economy_refresh_state_and_damage = yes',
               b' calculate_damaged_buildings_count = yes\n update_state_variables = yes'),
}
BOUNDARY = [('calculate_damaged_buildings_count', '=', 'yes'),
            ('update_state_variables', '=', 'yes')]
_spec = importlib.util.spec_from_file_location('economy_refresh_source_parser',
    ROOT / 'tools/validation/diplomacy_package_03/_support.py')
_parser = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_parser)
ast, one = _parser.ast, _parser.one

# Exact sanctions-policy deletion inverse only; old historical digests stay fixed.
_sanctions_spec = importlib.util.spec_from_file_location('eon_sanctions_income_compat',
    HERE / 'sanctions_income_byte_compat.py')
_sanctions_bytes = importlib.util.module_from_spec(_sanctions_spec)
_sanctions_spec.loader.exec_module(_sanctions_bytes)

# Exact weekly tax inverse precedes existing sanctions and state inverses.
_weekly_spec = importlib.util.spec_from_file_location('eon_weekly_optimization_compat',
    HERE / 'weekly_optimization_byte_compat.py')
_weekly_bytes = importlib.util.module_from_spec(_weekly_spec)
_weekly_spec.loader.exec_module(_weekly_bytes)

def sha(raw): return hashlib.sha256(raw).hexdigest()

def raw_body(text, key):
    needle = key + ' = {'
    assert text.count(needle) == 1, ('Exact unique helper definition', key)
    start = text.index(needle) + len(needle)
    depth, quoted, comment, escaped = 1, False, False, False
    for end in range(start, len(text)):
        c = text[end]
        if comment:
            if c == '\n': comment = False
            continue
        if quoted:
            if escaped: escaped = False
            elif c == '\\': escaped = True
            elif c == '"': quoted = False
            continue
        if c == '#': comment = True
        elif c == '"': quoted = True
        elif c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0: return text[start:end]
    raise AssertionError(('Unclosed helper', key))

def walk(nodes):
    for k, op, v in nodes:
        yield k, op, v
        if isinstance(v, list): yield from walk(v)

def tokens(nodes):
    for k, op, v in walk(nodes):
        yield k
        if isinstance(v, str): yield v

def certify_sources(root=ROOT, read_bytes=None):
    read = read_bytes or (lambda rel: (root / rel).read_bytes())
    fixture = (HERE / 'fixtures/baseline_state_refresh.txt').read_bytes()
    assert sha(fixture) == FIXTURE_SHA, 'Exact before helper-island fixture required'
    before_text = fixture.decode('utf-8-sig')
    old = {k:v for k, op, v in ast(fixture)}
    raw_helper = read(HELPER)
    assert sha(raw_helper) == HELPER_SHA, 'Whole certified CURRENT combined helper required'
    parsed = ast(raw_helper)
    assert len(parsed) == 1 and parsed[0][:2] == (NAME, '='), 'One fused helper only'
    money_text = read(MONEY).decode('utf-8-sig')
    for name in ('update_state_variables', 'productivity_growth_country_display_effect',
                 'productivity_growth_controlled_display_effect'):
        assert raw_body(money_text, name) == raw_body(before_text, name), ('Original public helper bytes', name)
    raw_damage = read(DAMAGE)
    assert sha(raw_damage) == DAMAGE_SHA, 'Original full damage source required'
    assert one(ast(raw_damage), 'calculate_damaged_buildings_count') == old['calculate_damaged_buildings_count']
    damage = one(old['calculate_damaged_buildings_count'], 'hidden_effect')
    state = old['update_state_variables']
    di = [i for i,n in enumerate(damage) if n[0] == 'every_controlled_state']
    si = [i for i,n in enumerate(state) if n[0] == 'hidden_effect']
    assert len(di) == len(si) == 1, 'Exact original walk boundaries required'
    di, si = di[0], si[0]
    hidden = state[si][2]
    li = [i for i,n in enumerate(hidden) if n[0] == 'every_controlled_state']
    assert len(li) == 1
    li = li[0]
    expected = [('hidden_effect', '=', damage[:di])] + state[:si]
    expected += [('hidden_effect', '=', hidden[:li] + [('every_controlled_state', '=', damage[di][2] + hidden[li][2])] + damage[di+1:])]
    expected += state[si+1:]
    assert parsed[0][2] == expected, 'Full current helper must contain only exact original commuted islands'
    # Commutation proof: country begin and state aggregation/display closure
    # neither read/write moved damage counters nor mutate traversal facts.
    moved = set()
    for k, op, v in walk(old['calculate_damaged_buildings_count']):
        if k == 'set_variable': moved.add(v[0][0])
        elif k == 'add_to_variable': moved.add(v[0][0].removeprefix('PREV.'))
    state_body = hidden[li][2] + old['productivity_growth_controlled_display_effect']
    closure = state + old['productivity_growth_country_display_effect'] + old['productivity_growth_controlled_display_effect']
    def bare(t): return t.removeprefix('THIS.').removeprefix('PREV.').removeprefix('ROOT.')
    assert not moved & {bare(t) for t in tokens(closure)}, 'Moved damage dependency appeared in state closure'
    destructive = {'set_state_controller', 'set_state_owner', 'transfer_state', 'add_building_construction',
                   'remove_building', 'set_capital', 'country_event', 'state_event', 'random_list', 'random',
                   'add_manpower', 'add_to_state_population', 'set_variable_to_random'}
    assert not destructive & {k for k, op, v in walk(state_body)}, 'Physical traversal facts must stay unchanged'
    calls = {k for k, op, v in walk(state_body) if v == 'yes' and k not in {'always', 'is_coastal'}}
    assert calls == {'productivity_growth_controlled_display_effect'}, ('Unreviewed state dependency', calls)
    raw_dynamic = read(DYNAMIC)
    assert sha(raw_dynamic) == DYNAMIC_SHA, 'Reviewed dynamic-modifier dependency source required'
    dynamic = one(ast(raw_dynamic), 'productivity_and_employment_modifier')
    assert not moved & set(tokens(dynamic)), 'Dynamic modifier reads moved damage counters'
    assert all(k in {'enable', 'industrial_capacity_factory', 'industrial_capacity_dockyard',
                     'production_speed_buildings_factor', 'production_speed_agriculture_district_factor',
                     'monthly_population'} for k, op, v in dynamic)
    return copy.deepcopy(BOUNDARY)

def restore_adjacent_state_refresh(relative, raw):
    if relative not in PAIRS: return raw
    if isinstance(raw, str): return restore_adjacent_state_refresh(relative, raw.encode('utf-8')).decode('utf-8')
    assert isinstance(raw, bytes), 'Byte inverse requires bytes or str'
    if relative == MONEY: raw = _weekly_bytes.restore_tax_membership_guard(relative, raw)
    if relative == MONEY: raw = _sanctions_bytes.restore_sanctions_income_loop(relative, raw)
    certify_sources()
    current, original = PAIRS[relative]
    assert raw.count(current) == 1 and raw.count(original) == 0, 'Exact unique CURRENT adjacent-call span required'
    assert raw.count(NAME.encode()) == 1, 'No extra fused-call reference may be projected'
    return raw.replace(current, original, 1)

def certified_native_boundary():
    """Return only two existing native delegates; never simulate GDP or finance."""
    return certify_sources()
