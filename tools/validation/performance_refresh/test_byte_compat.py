"""Current-source certification and hostile inverse/delegation regressions."""
from pathlib import Path
import copy, hashlib, importlib.util, unittest
from byte_compat import (ROOT, MONEY, DELIVERY, DAMAGE, HELPER, DYNAMIC, NAME,
                         PAIRS, BOUNDARY, certify_sources, restore_adjacent_state_refresh)

PREIMAGES = {
    MONEY: '938ca3a0b62a5f0c9cf6cc8dde82cbf4187ee4d560b2ef567014aa47b4043135',
    DELIVERY: 'bd594c3f8bf41f84237e01d06238d2ff1746d40690f48373baaea490ff4a96f3',
}

def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class Compatibility(unittest.TestCase):
    def test_current_complete_helper_and_dependency_closure_certified(self):
        self.assertEqual(certify_sources(), BOUNDARY)

    def test_exact_pair_inverse_reaches_unchanged_whole_preimages(self):
        for relative, digest in PREIMAGES.items():
            raw = (ROOT / relative).read_bytes()
            restored = restore_adjacent_state_refresh(relative, raw)
            self.assertEqual(hashlib.sha256(restored).hexdigest(), digest)
            self.assertEqual(restored.startswith(b'\xef\xbb\xbf'), raw.startswith(b'\xef\xbb\xbf'))
            self.assertEqual(restored.count(b'\r\n'), raw.count(b'\r\n'))
            self.assertEqual(restore_adjacent_state_refresh(relative, raw.decode('utf-8')), restored.decode('utf-8'))

    def test_foreign_path_passthrough_and_historical_input_rejected(self):
        self.assertEqual(restore_adjacent_state_refresh('foreign.txt', b'unchanged'), b'unchanged')
        for relative in PREIMAGES:
            old = restore_adjacent_state_refresh(relative, (ROOT / relative).read_bytes())
            with self.assertRaises(AssertionError): restore_adjacent_state_refresh(relative, old)

    def test_missing_duplicate_changed_and_extra_call_fail_closed(self):
        for relative, (current, original) in PAIRS.items():
            raw = (ROOT / relative).read_bytes()
            mutants = [raw.replace(current, b'', 1), raw + b'\n' + current,
                       raw.replace(current, current.replace(b' = yes', b' = no'), 1),
                       raw + b'\nROOT = { ' + NAME.encode() + b' = yes }\n',
                       raw.replace(current, current.replace(b' = yes', b' = { }'), 1),
                       raw + b'\n' + original]
            for mutant in mutants:
                self.assertNotEqual(mutant, raw)
                with self.assertRaises(AssertionError): restore_adjacent_state_refresh(relative, mutant)

    def test_unrelated_bytes_are_retained_for_historical_whole_guard(self):
        for relative, digest in PREIMAGES.items():
            raw = (ROOT / relative).read_bytes()
            for mutant in (raw + b'\n', raw + b'\nunknown_foreign_effect = yes\n'):
                restored = restore_adjacent_state_refresh(relative, mutant)
                self.assertNotEqual(hashlib.sha256(restored).hexdigest(), digest)
                self.assertTrue(restored.endswith(mutant[len(raw):]))

    def test_actual_helper_unknown_scope_query_or_extra_command_rejected(self):
        paths = (MONEY, DAMAGE, HELPER, DYNAMIC)
        current = {p: (ROOT / p).read_bytes() for p in paths}
        mutants = [
            (HELPER, current[HELPER].replace(b'PREV.num_of_damaged_civs', b'ROOT.num_of_damaged_civs', 1)),
            (HELPER, current[HELPER].replace(b'damaged_building_level@industrial_complex', b'building_level@industrial_complex', 1)),
            (HELPER, current[HELPER] + b'unknown_foreign_effect = { add_political_power = 999 }\n'),
            (HELPER, current[HELPER].replace(b'every_controlled_state', b'every_owned_state', 1)),
            (MONEY, current[MONEY].replace(b'PREV.total_number_of_controlled_states = 1', b'ROOT.total_number_of_controlled_states = 1', 1)),
            (MONEY, current[MONEY].replace(b'productivity_growth_country_display_effect = {', b'productivity_growth_country_display_effect_bad = {', 1)),
            (DAMAGE, current[DAMAGE] + b'\n'), (DYNAMIC, current[DYNAMIC] + b'\n'),
        ]
        for relative, mutant in mutants:
            self.assertNotEqual(mutant, current[relative])
            data = {**current, relative: mutant}
            with self.assertRaises(AssertionError): certify_sources(read_bytes=data.__getitem__)

    def test_both_models_delegate_only_certified_existing_native_boundaries(self):
        for name, relative in (('refresh_pkg25_model', 'tools/validation/diplomacy_package_25/test_delivery.py'),
                               ('refresh_pkg27_model', 'tools/validation/diplomacy_package_27/_model.py')):
            m = load(name, relative)
            self.assertEqual(m._ECONOMY_NATIVE_BOUNDARY, BOUNDARY)
            original = m.state({1:(40, 15), 2:(0, 7)})
            original['countries'][1]['state_aggregates'] = {'military_fac':7, 'office_park_total':4}
            left, right = copy.deepcopy(original), copy.deepcopy(original)
            m.native.clear(); m.execute(BOUNDARY, left, m.context(2, scope=1))
            native = dict(m.native)
            m.native.clear(); m.execute([(NAME, '=', 'yes')], right, m.context(2, scope=1))
            self.assertEqual(left, right)
            self.assertEqual(dict(m.native), native)
            self.assertEqual(native.get('calculate_damaged_buildings_count'), 1)
            self.assertEqual(native.get('update_state_variables'), 1)
            with self.assertRaises(AssertionError): m.execute([(NAME, '=', 'no')], right, m.context(2, scope=1))
            with self.assertRaises(AssertionError): m.execute([('unknown_foreign_effect', '=', 'yes')], right, m.context(2, scope=1))

    def test_existing_traversal_whole_guard_and_negative_controls_remain_exact(self):
        m = load('refresh_traversal_compat', 'tools/validation/performance_policy/energy_traversal_byte_compat.py')
        raw = (ROOT / DELIVERY).read_bytes().decode('utf-8-sig')
        old = m.restore_energy_traversal(DELIVERY, raw)
        self.assertEqual(hashlib.sha256(old.encode()).hexdigest(), m.CATALOG['before_sha256'])
        self.assertEqual(len(m.negative_controls(raw)), 4)
        with self.assertRaises(AssertionError): m.restore_energy_traversal(DELIVERY, raw+'\nunknown_foreign_effect = yes\n')

if __name__ == '__main__': unittest.main(verbosity=2)
