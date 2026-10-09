"""Validate finite budgets and generated state IDs against this checkout."""
from pathlib import Path
import importlib.util
import json
import math

ROOT = Path(__file__).resolve().parents[3]
data = json.loads((ROOT/'tools/data/uranium_2000.json').read_text(encoding='utf-8-sig'))
assert len(data['countries']) == 49
assert math.isclose(sum(c['reported_rar_lt130_tu'] or 0 for c in data['countries']), 3182520)
assert math.isclose(sum(c['observed_1999_production_tu'] or 0 for c in data['countries']), 32179)
seen = set()
for country in data['countries']:
    allocations = country.get('game_seed_allocations', [])
    budget = country['game_resource_budget_tu']
    if budget is None:
        assert not allocations, ('invented unknown reserve', country['tag'])
    else:
        allocated = sum(site['reserve_tu'] for site in allocations)
        assert math.isclose(allocated + country['game_budget_unallocated_tu'], budget, abs_tol=0.001), country['tag']
    for site in allocations:
        ident = site['state_id']
        assert ident not in seen
        seen.add(ident)
        paths = list((ROOT/'history/states').glob(str(ident)+'-*.txt'))
        assert len(paths) == 1, ('missing or ambiguous state', ident)
        assert site['reserve_tu'] > 0
        assert 0 <= site['initial_weekly_tu'] <= site['max_weekly_tu']
assert len(seen) == 78
path = ROOT/'tools/data/build_uranium_seed.py'
spec = importlib.util.spec_from_file_location('uranium_seed_compiler', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert (ROOT/'common/scripted_effects/eon_uranium_seed_effects.txt').read_bytes() == module.compile_seed(data).encode('utf-8')
print(json.dumps({'sourced_seed_passed': True, 'countries': 49, 'finite_state_allocations': len(seen), 'rar_tu': 3182520, 'production_1999_tu': 32179, 'native_game_behavior_tested': False}))
