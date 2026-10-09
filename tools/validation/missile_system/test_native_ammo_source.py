"""Check native missile-only raids leave reserve families to engine ownership.

This source check proves the accidental reserve transfers were removed. It does
not prove the native engine's one-use consumption; that requires a real raid.
"""
import json
import re
import subprocess
from copy import deepcopy

from test_launch import ROOT, ast, one, read

BASELINE = '2b6a26e76c80f7923d11ebc2c0694e882253fb32'
PATH = 'common/raids/nuclear_raids.txt'
FAMILIES = {'nuclear_missile_equipment', 'nuclear_ballistic_missile_equipment'}


def walk(nodes):
    for key, op, value in nodes:
        yield key, op, value
        if isinstance(value, list):
            yield from walk(value)


def restore_queued_victim(nodes):
    """Invert only the four explicitly declared queue/readiness insertions."""
    gate = one(nodes[0][2], 'limit')
    assert nodes[0][0] == 'if' and gate[0] == ('eon_nuclear_arsenal_ready', '=', 'yes')
    queue = one(nodes[0][2], 'var:ROOT.actor_country')
    expected = [('if', '=', [
        ('limit', '=', [('exists', '=', 'yes'), ('has_capitulated', '=', 'no')]),
        ('set_variable', '=', [('eon_nuclear_queued_shooter', '=', 'PREV')]),
        ('set_variable', '=', [('eon_nuclear_queued_level', '=', 'PREV.arctic_nuclear_level')]),
        ('set_country_flag', '=', 'sugoma'),
        ('PREV', '=', [('set_country_flag', '=', 'sussy_baka')]),
        ('set_global_flag', '=', 'amogus'),
    ])]
    assert queue == expected, 'Only the exact paired queue insertion may be inverted'
    assert nodes[0][2] == [('limit', '=', gate), ('var:ROOT.actor_country', '=', queue)]
    return [
        ('set_variable', '=', [('global.temp_arctic_nuclear_level', '=', 'THIS.arctic_nuclear_level')]),
        ('set_variable', '=', [('global.nuke_striker', '=', 'THIS')]),
        ('if', '=', [('limit', '=', gate[1:]), ('set_global_flag', '=', 'amogus')]),
        ('set_country_flag', '=', 'sussy_baka'),
    ]+nodes[1:]


def run():
    original = one(ast(subprocess.check_output(
        ['git', 'show', BASELINE+':'+PATH], cwd=ROOT).decode('utf-8-sig')), 'types')
    current = one(read(PATH), 'types')
    tactical_missile = one(one(read('common/raids/eon_tactical_nuclear_missile_raid.txt'), 'types'),
                          'eon_tactical_nuclear_missile_strike')
    removed = 0
    outcomes = 0
    paired_victims = 0
    queue_mutants = 0
    moved_actor_flags = 0
    for name in ('state_nuclear_strike', 'strategic_nuclear_strike'):
        before, after = one(original, name), one(current, name)
        requirements = [value for key, op, value in after if key == 'unit_requirements']
        required_families = {one(one(value, 'equipment'), 'type')[0][2]
                             for value in requirements}
        assert required_families == FAMILIES
        assert all(value in ('rocket_site', 'submarine')
                   for key, op, value in one(one(after, 'starting_point'), 'types'))
        old_outcomes, new_outcomes = one(before, 'success_levels'), one(after, 'success_levels')
        assert [key for key, op, value in old_outcomes] == [key for key, op, value in new_outcomes]
        for outcome, op, old in old_outcomes:
            old_actor = one(old, 'actor_effects')
            new_actor = one(one(new_outcomes, outcome), 'actor_effects')

            def normalize(nodes):
                nonlocal removed
                result = []
                for key, operator, value in nodes:
                    if name == 'strategic_nuclear_strike' and (key, operator, value) == ('set_country_flag', '=', 'sugoma'):
                        nonlocal moved_actor_flags
                        moved_actor_flags += 1
                        continue
                    if key == 'hidden_effect':
                        assert len(value) == 2 and all(k == 'send_equipment' for k, o, v in value)
                        assert {one(v, 'equipment') for k, o, v in value} == FAMILIES
                        assert all(one(v, 'target') == 'EUU' for k, o, v in value)
                        assert all(one(v, 'amount') == ('1' if name == 'state_nuclear_strike' else '10')
                                   for k, o, v in value)
                        removed += 2
                        continue
                    result.append((key, operator, normalize(value) if isinstance(value, list) else value))
                return result

            assert normalize(old_actor) == new_actor, (name, outcome, 'Unrelated actor effect changed')
            assert not any(key == 'send_equipment' for key, op, value in walk(new_actor))
            if name == 'strategic_nuclear_strike':
                old_victim = one(one(old, 'victim_effects'), 'var:victim_country')
                new_victim = one(one(one(new_outcomes, outcome), 'victim_effects'), 'var:victim_country')
                assert restore_queued_victim(new_victim) == old_victim, (outcome, 'Unrelated victim payload changed')
                for field in ('eon_nuclear_queued_shooter', 'eon_nuclear_queued_level', 'sugoma'):
                    mutant = deepcopy(new_victim)
                    queue = one(mutant[0][2], 'var:ROOT.actor_country')[0][2]
                    if field == 'sugoma':
                        queue[:] = [node for node in queue if node != ('set_country_flag', '=', field)]
                    else:
                        queue[:] = [node for node in queue if not (
                            node[0] == 'set_variable' and any(k == field for k, o, v in node[2]))]
                    try:
                        restore_queued_victim(mutant)
                    except (AssertionError, TypeError):
                        queue_mutants += 1
                    else:
                        raise AssertionError('Missing queued pair/flag mutant survived')
                paired_victims += 1
            outcomes += 1
    assert removed == 14 and outcomes == 8
    assert paired_victims == moved_actor_flags == 4 and queue_mutants == 12
    models = 0
    for path in ('common/units/equipment/MD_nuclear_missiles.txt',
                 'common/units/equipment/MD_ballistic_missiles.txt'):
        for name, op, equipment in one(read(path), 'equipments'):
            if any(key == 'archetype' and value in FAMILIES for key, op, value in equipment):
                assert one(equipment, 'one_use_only') == 'yes', name
                models += 1
    assert models == 15
    units = one(read('common/units/MD_air_units.txt'), 'sub_units')
    for unit, expected_land in (('nuclear_missile', '10'), ('nuclear_ballistic_missile', '50')):
        body = one(units, unit)
        assert one(body, 'land_air_wing_size') == expected_land
        assert one(body, 'carrier_air_wing_size') == '10'
        assert not any(key == 'submarine_carrier_air_wing_size' for key, op, value in body)
    unit_path = 'common/units/MD_air_units.txt'
    unit_bytes = (ROOT/unit_path).read_bytes()
    assert unit_bytes == subprocess.check_output(['git', 'show', BASELINE+':'+unit_path], cwd=ROOT), 'Original unit capacities/bytes must be retained'
    vanilla_air = ROOT.__class__('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/common/units/air.txt')
    native_nuclear = one(one(ast(vanilla_air.read_text(encoding='utf-8-sig')), 'sub_units'), 'nuclear_missile')
    assert one(native_nuclear, 'land_air_wing_size') == one(native_nuclear, 'carrier_air_wing_size') == '1'
    # EON's country-wide raid needs ten missiles in ONE eligible unit. Vanilla
    # singleton defaults cannot simply replace EON's original delivery sizes.
    # A partial wing satisfying min1 is possible under the shipped UI reserve
    # rule, but the exact firing/consumption of that wing remains native work.
    capacity_checks = 0
    def check_capacity(body, requirement):
        minimum = int(one(one(one(requirement, 'equipment'), 'amount'), 'min'))
        for field in ('land_air_wing_size', 'carrier_air_wing_size'):
            assert int(one(body, field)) >= minimum, 'Native filter requires one matching unit, not summed country inventory'
    for route in (tactical_missile, one(current, 'state_nuclear_strike'), one(current, 'strategic_nuclear_strike')):
        for key, op, requirement in route:
            if key == 'unit_requirements':
                allowed = {value for key, op, value in one(one(requirement, 'equipment'), 'type')}
                for unit in ('nuclear_missile', 'nuclear_ballistic_missile'):
                    body = one(units,unit)
                    if {key for key, op, value in one(body,'need')} & allowed:
                        check_capacity(body,requirement)
                        capacity_checks += 1
    strategic_requirement = next(value for key,op,value in one(current,'strategic_nuclear_strike') if key == 'unit_requirements')
    singleton = [('land_air_wing_size','=','1'), ('carrier_air_wing_size','=','1')]
    try:
        check_capacity(singleton,strategic_requirement)
    except AssertionError:
        pass
    else:
        raise AssertionError('Singleton-wing regression must be rejected for strategic min10')
    # Tactical routes now declare separate payload owners without a guessed
    # selected-family getter: a native one-use missile, or a reserved air payload.
    tactical = one(current, 'tactical_nuclear_strike')
    assert not any(key == 'send_equipment' for key, op, value in walk(tactical))
    assert not any(key == 'send_equipment' for key, op, value in walk(tactical_missile))
    assert one(tactical, 'essential_equipment') == [('nuclear_ballistic_missile_equipment', '=', '1')]
    assert one(tactical_missile, 'essential_equipment') == []
    assert len([node for node in tactical if node[0] == 'unit_requirements']) == 1
    bomber_requirement = one(one(tactical, 'unit_requirements'), 'equipment')
    assert {value for key, op, value in one(bomber_requirement, 'type')} == {'tactical_bomber', 'strategic_bomber'}
    assert one(bomber_requirement, 'modules') == [('__item__', '=', 'spec_nuclear_consent')]
    assert {value for key, op, value in one(one(tactical, 'starting_point'), 'types')} == {'air_base', 'carrier'}
    assert len([node for node in tactical_missile if node[0] == 'unit_requirements']) == 1
    for predicate in ('available', 'launchable'):
        bomber_policy = [node for node in one(tactical, predicate) if node[0] != 'has_equipment']
        assert bomber_policy == one(tactical_missile, predicate)
        stock_guards = [value for key,op,value in one(tactical,predicate) if key == 'has_equipment']
        assert stock_guards == ([[('nuclear_ballistic_missile_equipment', '>', '0')]] if predicate == 'available' else [])
    for outcome, op, effects in one(tactical, 'success_levels'):
        assert effects == one(one(tactical_missile, 'success_levels'), outcome)
    for route in (tactical_missile, one(current, 'state_nuclear_strike'), one(current, 'strategic_nuclear_strike')):
        for predicate in ('available', 'launchable'):
            assert not any(key in ('has_equipment', 'check_if_nuclear_weapons_in_stockpile', 'set_temp_variable')
                           for key, op, value in walk(one(route, predicate)))
    # Installed vanilla uses an equipment archetype in the same payload map.
    vanilla = ROOT.__class__('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/common/raids/paratrooper_raids.txt')
    assert re.search(r'essential_equipment\s*=\s*\{\s*transport_plane_equipment\s*=\s*10\s*\}', vanilla.read_text(encoding='utf-8-sig'))
    raid_docs = vanilla.parent/'_documentation.md'
    documentation = raid_docs.read_text(encoding='utf-8-sig')
    assert 'any unit matching at least one of the unit_requirements blocks' in documentation
    assert 'Having this equipment (in stockpile) is a precondition for *creating* the raid' in documentation
    assert 'will be collected after a raid is created' in documentation
    new_id = 'eon_tactical_nuclear_missile_strike'
    for language in ('english', 'russian'):
        data = (ROOT/'localisation'/language/('eon_tactical_nuclear_missile_l_'+language+'.yml')).read_bytes()
        assert data.startswith(b'\xef\xbb\xbf') and data.count(b'\r\n') == 3 and data.count(b'\n') == 3
        text = data.decode('utf-8-sig')
        for suffix in ('', '_desc'):
            assert len(re.findall(r'^ raid_type_'+new_id+suffix+r':0 "[^"]+"\r?$', text, re.M)) == 1
    sprite = one(read('interface/military_raids/eon_tactical_nuclear_missile.gfx'), 'spriteTypes')
    entry = one(sprite, 'spriteType')
    assert one(entry, 'name') == 'GFX_raid_type_icon_'+new_id
    assert (ROOT/one(entry, 'texturefile')).is_file()
    print(json.dumps({'status': 'PASS', 'missile_only_outcomes': outcomes,
                      'removed_wrong_reserve_transfers': removed, 'one_use_models': models,
                      'scope': 'Source ownership of reserves only; no actual raid consumption proof',
                      'tactical_payload_routes_separated': True,
                      'preserved_original_nuclear_wing_capacity': True,
                      'single_selected_unit_capacity_checks': capacity_checks,
                      'paired_queue_payloads_preserved': paired_victims,
                      'missing_queue_field_mutants_rejected': queue_mutants,
                      'native_essential_payload_consumption_verified': False}, indent=2))


if __name__ == '__main__':
    run()
