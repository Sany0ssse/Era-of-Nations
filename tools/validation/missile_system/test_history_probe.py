"""Check the private air-OOB fixture source; this never launches the game."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json

from build_native_probe import NS, build, merge_history
from test_launch import ROOT, ast, one, read


def walk(nodes):
    for node in nodes:
        yield node
        if isinstance(node[2], list):
            yield from walk(node[2])


def run():
    sample = '\ufeffcapital = 1\r\n2000.1.1 = {\r\n# } ignored\r\nname = "{ }" nested = { val = 1 }\r\n}\r\n2001.1.1 = { val = 2 }\r\n'
    fragment = '\r\nset_country_flag = private_test\r\n'
    merged = merge_history(sample, fragment)
    assert merged.replace(fragment, '', 1) == sample
    assert one(ast(merged), '2000.1.1') == one(ast(sample), '2000.1.1')+ast(fragment)
    rejected = 0
    for bad in ('2001.1.1 = { val = 1 }', '2000.1.1 = {} 2000.1.1 = {}'):
        try:
            merge_history(bad, fragment)
        except AssertionError:
            rejected += 1
        else:
            raise AssertionError('Missing/duplicate original date should be rejected')
    fra = list(walk(read('history/countries/FRA - France.txt')))
    mirage, = [body for key, op, body in fra if key == 'create_equipment_variant' and
               any(node == ('name', '=', 'Mirage F1') for node in body)]
    air_techs = one(read('common/technologies/BBA_aircraft.txt'), 'technologies')
    countries = 0
    local = ROOT/'.local/missile-system'
    local.mkdir(parents=True, exist_ok=True)
    # Only generated fixture files are held in this workspace-owned temporary
    # directory; original history and production files are read-only inputs.
    with TemporaryDirectory(prefix='history-probe-test-', dir=local) as directory:
        output = Path(directory).resolve()
        assert output.is_relative_to(local.resolve())
        manifest = build(ROOT, output, preparation_only=True)
        assert len(manifest['assertions']) == 48
        assert sum(manifest['expected_private_starting_aircraft'].values()) == 12
        assert len(manifest['observation_fields']) == 24
        assert not any(value.endswith('@nuclear_ballistic_missile') for value in manifest['observation_fields'].values())
        for tag, capital in (('GER',45), ('FRA',56), ('RAJ',431)):
            original, = (ROOT/'history/countries').glob(tag+' - *.txt')
            private = output/'mod'/original.relative_to(ROOT)
            original_bytes, private_bytes = original.read_bytes(), private.read_bytes()
            original_text, private_text = original_bytes.decode('utf-8'), private_bytes.decode('utf-8')
            newline = '\r\n' if '\r\n' in original_text else '\n'
            position = private_text.index(newline+'\t# Private native missile probe:')
            inserted_length = len(private_text)-len(original_text)
            assert private_text[:position]+private_text[position+inserted_length:] == original_text
            assert private_bytes.startswith(b'\xef\xbb\xbf') == original_bytes.startswith(b'\xef\xbb\xbf')
            original_body = one(ast(original_text), '2000.1.1')
            private_body = one(ast(private_text), '2000.1.1')
            assert private_body[:len(original_body)] == original_body
            appended = private_body[len(original_body):]
            assert one(appended,'set_air_oob') == NS+'_'+tag.lower()
            assert one(appended,'set_country_flag') == NS+'_history_registered'
            assert one(one(appended,'set_variable'), NS+'_history_registration') == '1'
            control, = [body for key, op, body in appended if key == 'create_equipment_variant' and
                        ('name', '=', 'Private fighter control') in body]
            assert one(control,'type') == one(mirage,'type') == 'small_plane_airframe_1'
            assert one(control,'modules') == one(mirage,'modules')
            grants = one(appended,'set_technology')
            assert all((key,'=','1') in grants for key in ('ICBM','IRBM','GLCM','ICBM1','IRBM1','NIRBM1','GLCM1'))
            unlocked_modules = set()
            for key, op, quantity in grants:
                if key in {name for name, op, body in air_techs}:
                    for name, op, values in one(air_techs,key):
                        if name == 'enable_equipment_modules':
                            unlocked_modules.update(item[2] for item in values)
            assert {module for slot, op, module in one(control,'modules')} <= unlocked_modules
            original_state, = (ROOT/'history/states').glob(str(capital)+'-*.txt')
            original_state_text = original_state.read_bytes().decode('utf-8')
            private_state_text = (output/'mod'/original_state.relative_to(ROOT)).read_bytes().decode('utf-8')
            newline = '\r\n' if '\r\n' in original_state_text else '\n'
            assert private_state_text.replace(newline+'\t\t\trocket_site = 10'+newline, '', 1) == original_state_text
            state = one(ast(private_state_text),'state')
            assert one(one(one(state,'history'),'buildings'),'rocket_site') == '10'
            wings = one(one(ast((output/'mod/history/units'/f'{NS}_{tag.lower()}.txt').read_text()),'air_wings'),str(capital))
            equipment = [(key,body) for key, op, body in wings if key != 'name']
            assert len(equipment) == 9
            assert sum(int(one(body,'amount')) for key,body in equipment) == 12
            variants = {one(body,'type'):one(body,'name') for key,op,body in appended if key == 'create_equipment_variant'}
            assert all(one(body,'owner') == tag and one(body,'version_name') == variants[key] for key,body in equipment)
            countries += 1
        events = ast((output/'mod/events'/f'{NS}_events.txt').read_text())
        assert len([1 for key, op, body in events if key == 'country_event']) == 6
        assert len([1 for key, op, body in walk(events) if key == 'hours' and body == '25']) == 3
        assert not any(key == 'load_oob' for key, op, body in walk(events))
    print(json.dumps({'status':'PASS', 'history_merge_cases':1, 'bad_inputs_rejected':rejected,
                      'country_state_oob_controls':countries, 'fixture_assertions':48,
                      'scope':'Fixture source only; duplicate-date and counter inclusion are not established engine behavior'},indent=2))


if __name__ == '__main__':
    run()
