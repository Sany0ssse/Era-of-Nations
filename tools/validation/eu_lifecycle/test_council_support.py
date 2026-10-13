"""Council native source-coupling and negative-contract tests; no engine acceptance."""
from copy import deepcopy
from pathlib import Path
import hashlib, tempfile, unittest
from council_support import build_council, source_contract, validate_contract, core_valid_round_setup, DEPENDENCIES, RESULT, TIMER, ast, one, walk

HERE = Path(__file__).resolve().parent
SOURCE = Path(__file__).resolve().parents[3]
NS = 'eon_native_eu_probe'
MARK = 'EON_EU_NATIVE_V14'

class NativeContracts(unittest.TestCase):
    def module(self): return build_council(NS, MARK, source=SOURCE)
    def changed_source(self, relative, before, after):
        temporary = tempfile.TemporaryDirectory(prefix='eon_council_contract_')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name in DEPENDENCIES:
            output = root / name; output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes((SOURCE / name).read_bytes())
        path = root / relative; old = path.read_text('utf-8-sig')
        self.assertIn(before, old)
        path.write_text(old.replace(before, after, 1), encoding='utf-8')
        return root

    def test_only_existing_event_asset_and_approved_ids(self):
        m = self.module()
        self.assertEqual(set(m['fixture_text']), {f'events/{NS}.txt'})
        numbers = [int(one(body, 'id').split('.')[-1]) for key, _, body in ast(m['fixture_text'][f'events/{NS}.txt']) if key == 'country_event']
        self.assertEqual(len(numbers), len(set(numbers)))
        self.assertEqual(len(numbers), 8)
        self.assertTrue(all(7000 <= n <= 7199 for n in numbers))

    def test_exact_source_and_callback_binding(self):
        m = self.module()
        self.assertEqual(set(m['production_input_sha256']), set(DEPENDENCIES))
        for name, digest in m['production_input_sha256'].items():
            self.assertEqual(digest, hashlib.sha256((SOURCE / name).read_bytes()).hexdigest())
        self.assertFalse(m['contract']['ui_click_verified'])
        self.assertFalse(m['contract']['claim_of_immutable_callback_payload'])

    def test_actual_native_actor_event_roots_for_proposals(self):
        text = self.module()['fixture_text'][f'events/{NS}.txt']
        schedules = []
        for key, _, body in walk(ast(text)):
            if key in ('FRA', 'ITA'):
                for child, _, fields in body:
                    if child == 'country_event': schedules.append((key, one(fields, 'id'), one(fields, 'hours')))
        self.assertIn(('FRA', NS + '.7010', '2'), schedules)
        self.assertIn(('ITA', NS + '.7002', '217'), schedules)
        self.assertIn('tag = FRA ROOT = { tag = FRA }', text)
        self.assertIn('tag = ITA ROOT = { tag = ITA }', text)

    def test_full_cycle_trace_does_not_clear_ai_ballots_or_seed_outcome(self):
        m = self.module()
        text = m['fixture_text'][f'events/{NS}.txt']
        self.assertNotIn('clear_array = global.EU_active_vote_supporters', text)
        self.assertNotIn('clear_array = global.EU_active_vote_rejecters', text)
        self.assertNotIn('clear_array = global.eon_eu_council_abstainers', text)
        validate_contract(m, NS)
        self.assertEqual(m['contract']['real_fourteen_day_traces'], 2)

    def test_two_natural_fourteen_day_minimums_and_real_clocks(self):
        m = self.module()
        contracts = m['required_elapsed_game_time']
        self.assertEqual(sum(c['minimum_hours'] == 336 for c in contracts), 2)
        self.assertTrue(m['contract']['true_scheduler_result_required'])
        self.assertEqual(m['contract']['fixed_mission_ids'], [RESULT, TIMER])
        self.assertEqual([c['private_days'] for c in m['calibrations']], [5, 3, 1, 1])

    def test_actual_daily_fallback_source_helpers_and_route_receipt(self):
        m = self.module()
        keys = [k for k, _, _ in walk(ast(m['on_daily_effect']))]
        self.assertEqual(keys.count('eon_eu_capture_council_deadline_outcome'), 1)
        self.assertEqual(keys.count('eon_eu_reconcile_council_vote_owner'), 1)
        self.assertLess(keys.index('eon_eu_capture_council_deadline_outcome'), keys.index('eon_eu_reconcile_council_vote_owner'))
        self.assertIn('COUNCIL_DAILY_BEFORE', m['on_daily_effect'])
        self.assertIn('COUNCIL_DAILY_AFTER', m['on_daily_effect'])
        self.assertIn('COUNCIL_DAILY_FALLBACK_ROUTE_RECEIPT', m['required_observations'])
        self.assertNotIn('COUNCIL_DAILY_BEFORE', m['required_observations'])
        self.assertFalse(m['contract']['daily_fallback']['full_world_coordinator_claim'])

    def test_missing_scheduled_source_capture_mutant_is_rejected(self):
        m = self.module(); m['on_daily_effect'] = m['on_daily_effect'].replace('eon_eu_capture_council_deadline_outcome = yes', 'eon_eu_recount_council_vote = yes')
        with self.assertRaisesRegex(AssertionError, 'each actual source helper'): validate_contract(m, NS)

    def test_reordered_scheduled_fallback_mutant_is_rejected(self):
        m = self.module(); m['on_daily_effect'] = m['on_daily_effect'].replace('eon_eu_capture_council_deadline_outcome = yes eon_eu_reconcile_council_vote_owner = yes', 'eon_eu_reconcile_council_vote_owner = yes eon_eu_capture_council_deadline_outcome = yes')
        with self.assertRaisesRegex(AssertionError, 'capture must precede'): validate_contract(m, NS)

    def test_ungated_daily_fallback_mutant_is_rejected(self):
        m = self.module(); m['on_daily_effect'] = m['on_daily_effect'].replace('has_global_flag = ' + NS + '_council_scheduler_trace', 'always = yes', 1)
        with self.assertRaisesRegex(AssertionError, 'private-trace gated'): validate_contract(m, NS)

    def test_scheduled_fabricated_result_mutant_is_rejected(self):
        m = self.module(); m['on_daily_effect'] = m['on_daily_effect'].replace('eon_eu_capture_council_deadline_outcome = yes', 'set_variable = { global.eon_eu_council_outcome_yes = 1 } eon_eu_capture_council_deadline_outcome = yes')
        with self.assertRaisesRegex(AssertionError, 'Never seed'): validate_contract(m, NS)

    def test_scheduled_manual_deadline_expiry_mutant_is_rejected(self):
        m = self.module(); m['on_daily_effect'] = m['on_daily_effect'].replace('eon_eu_capture_council_deadline_outcome = yes', 'clr_global_flag = eon_eu_council_vote_deadline eon_eu_capture_council_deadline_outcome = yes')
        with self.assertRaisesRegex(AssertionError, 'manually expire'): validate_contract(m, NS)

    def test_final_original_legacy_timeout_cannot_use_scheduled_fallback(self):
        m = self.module(); path = f'events/{NS}.txt'
        m['fixture_text'][path] = m['fixture_text'][path].replace('clr_global_flag = ' + NS + '_council_scheduler_trace', 'log = "fallback deliberately left active"', 1)
        with self.assertRaisesRegex(AssertionError, 'Disable daily fallback'): validate_contract(m, NS)

    def test_lowered_actual_daily_counter_contract_is_rejected(self):
        m = self.module()
        item = m['expectations']['council_native_actual_private_on_daily_calls_production_fallback']
        item['predicate'] = item['predicate'].replace('value = 28', 'value = 0', 1)
        with self.assertRaisesRegex(AssertionError, 'counter remains bounded'): validate_contract(m, NS)

    def test_no_extra_inventory_asset_mutant(self):
        m = self.module(); m['fixture_text']['common/on_actions/extra.txt'] = ''
        with self.assertRaisesRegex(AssertionError, 'five assets'): validate_contract(m, NS)

    def test_manual_deadline_expiry_mutant_is_rejected(self):
        m = self.module(); path = f'events/{NS}.txt'
        m['fixture_text'][path] = m['fixture_text'][path].replace('immediate = {', 'immediate = { clr_global_flag = eon_eu_council_vote_deadline ', 1)
        with self.assertRaisesRegex(AssertionError, 'manually expire'): validate_contract(m, NS)

    def test_private_fabricated_result_mutant_is_rejected(self):
        m = self.module(); path = f'events/{NS}.txt'
        m['fixture_text'][path] = m['fixture_text'][path].replace('immediate = {', 'immediate = { set_variable = { global.eon_eu_council_outcome_yes = 1 } ', 1)
        with self.assertRaisesRegex(AssertionError, 'Never seed'): validate_contract(m, NS)

    def test_private_fabricated_instance_mutant_is_rejected(self):
        m = self.module(); path = f'events/{NS}.txt'
        m['fixture_text'][path] = m['fixture_text'][path].replace('immediate = {', 'immediate = { set_variable = { global.eon_eu_council_vote_instance = 1 } ', 1)
        with self.assertRaisesRegex(AssertionError, 'Never seed'): validate_contract(m, NS)

    def test_lowered_native_elapsed_minimum_mutant_is_rejected(self):
        m = self.module()
        next(c for c in m['required_elapsed_game_time'] if c['minimum_hours'] == 336)['minimum_hours'] = 335
        with self.assertRaisesRegex(AssertionError, 'genuine14'): validate_contract(m, NS)

    def test_production_mission_clock_change_rejected(self):
        root = self.changed_source('common/decisions/EU_voting_decisions.txt', 'days_mission_timeout = 14', 'days_mission_timeout = 1')
        # First occurrence belongs EP: specifically mutate Council result below.
        path = root / 'common/decisions/EU_voting_decisions.txt'
        text = path.read_text('utf-8'); location = text.index(RESULT + ' = {')
        path.write_text(text[:location] + text[location:].replace('days_mission_timeout = 14', 'days_mission_timeout = 1', 1), encoding='utf-8')
        with self.assertRaisesRegex(AssertionError, 'actual14'): source_contract(root)

    def test_changed_actual_gui_callback_rejected(self):
        root = self.changed_source('common/scripted_guis/01_european_union_guis.txt', 'eu_council_available_reforms_button_click = { eon_eu_start_council_proposal = yes }', 'eu_council_available_reforms_button_click = { add_political_power = -500 }')
        with self.assertRaisesRegex(AssertionError, 'GUI proposal'): source_contract(root)

    def test_missing_before_refresh_seam_rejected(self):
        root = self.changed_source('common/scripted_effects/eon_eu_lifecycle_effects.txt', 'eon_eu_capture_council_deadline_outcome = yes', 'eon_eu_recount_council_vote = yes')
        with self.assertRaises((AssertionError, ValueError)): source_contract(root)

    def test_core_setup_creates_actual_round_without_canonical_receipt_writes(self):
        text = core_valid_round_setup(101)
        self.assertIn('eon_eu_appoint_office_1 = yes', text)
        self.assertIn('eon_eu_start_council_proposal = yes', text)
        self.assertIn('set_temp_variable = { v = 101 }', text)
        self.assertIn('clear_array = global.EU_active_vote_supporters', text)
        self.assertNotIn('set_variable = { global.eon_eu_council_', text)
        self.assertNotIn('flag = eon_eu_council_vote_deadline', text)
        ai_input = core_valid_round_setup(101, clear_ballots=False)
        self.assertNotIn('clear_array = global.EU_active_vote_supporters', ai_input)
        self.assertTrue(self.module()['contract']['original_golden144_predicates_unchanged'])

if __name__ == '__main__': unittest.main(verbosity=2)
