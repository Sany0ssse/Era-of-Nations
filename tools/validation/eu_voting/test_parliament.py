"""Actual EP/mission/law AST controls. Declared deadlines are not native time."""
from pathlib import Path
from copy import deepcopy
import json, os, sys, unittest
ROOT = Path(os.environ.get('EON_WORKSPACE_ROOT', Path(__file__).resolve().parents[3])).resolve()
HERE = Path(__file__).resolve().parent
MODE = 'production' if '--production' in sys.argv else 'candidate'
if '--production' in sys.argv: sys.argv.remove('--production')
SOURCE = ROOT
if '--source' in sys.argv:
    index = sys.argv.index('--source'); SOURCE = Path(sys.argv[index + 1]).resolve()
    del sys.argv[index:index + 2]
sys.path.insert(0, str(HERE))
import eon_eu_frontend_model as council
council.SOURCE = SOURCE
ast, one = council.ast, council.one
def read(path, source=None):
    source = SOURCE if source is None else source
    return ast(council.source_path(path, source).read_text(encoding='utf-8-sig'))
def gui_parts(name):
    return one(one(read('common/scripted_guis/01_european_union_guis.txt'), 'scripted_gui'), name)
def mission(ident): return one(one(read('common/decisions/EU_voting_decisions.txt'), 'EU_voting_category'), ident)
P = 'eu_parliament_available_reforms_button_click'
RESULT = 'EU_parliament_focus_EUXXX_approve'
TIMER = RESULT + '_timer'
IDS = [int(k[8:-11]) for k, _, _ in read('common/scripted_effects/99_EU_voting_scripted_effects.txt', ROOT) if k.startswith('focus_EU') and k.endswith('_QMV_result')]
BASELINE = json.loads((HERE / 'parliament-special-ast.json').read_text(encoding='utf-8'))
def normalized(value): return json.loads(json.dumps(value))
class EpModel(council.FrontModel):
    def __init__(self):
        super().__init__()
        for path in ('common/scripted_effects/eon_eu_voting_effects.txt', 'common/scripted_effects/eon_eu_parliament_effects.txt', 'common/scripted_effects/eon_eu_handoff_effects.txt'):
            if council.source_path(path, SOURCE).exists(): self.effects.update({k: v for k, _, v in read(path)})
        for path in ('common/scripted_triggers/99_EU_voting_scripted_triggers.txt', 'common/scripted_triggers/eon_eu_voting_triggers.txt', 'common/scripted_triggers/eon_eu_parliament_triggers.txt', 'common/scripted_triggers/eon_eu_handoff_triggers.txt'):
            if council.source_path(path, SOURCE).exists(): self.triggers.update({k: v for k, _, v in read(path)})
        self.ep_gui = gui_parts('european_parliament_dynamic_lists')
        self.root_gui = gui_parts('european_union_gui')
        self.global_vars.update(current_active_agenda_disp=0, MEP_Total=600, MEP_Majority=301, num_days=0)
        self.global_vars.update({f'MEP_PG_party_{i}': 0 for i in range(24)})
        self.global_vars.update(MEP_PG_party_0=120, MEP_PG_party_1=200, MEP_PG_party_2=280)
        self.global_arrays['EU_potential_votes'] = [101, 201, 401, 601]
        self.global_arrays['EU_council_votes'] = []
        for country in self.countries.values(): country.arrays['ruling_party'] = [0]
        self.temp['v'] = 101

    def trigger(self, nodes, stack):
        kept = []
        for key, op, value in nodes:
            if key == 'date':
                # Existing date prerequisite is an explicit fixture input (2026).
                if not (op == '>' and value < '2026.1.1'): return False
            elif key == 'meta_trigger':
                self.native_receipts.append(('LOCALIZED_TRIGGER_NOT_EXECUTED', value)); return False
            else: kept.append((key, op, value))
        return super().trigger(kept, stack)

    def effect(self, nodes, stack):
        kept = []
        for node in nodes:
            key, op, value = node
            if key == 'country_event' and isinstance(value, str):
                self.native_receipts.append((key, stack[-1].ident, value))
            elif key in ('set_the_eu_parliament_delay', 'EU_show_display_effects_for_law'):
                # Cooldown/random UI-display helpers are unchanged input boundaries.
                self.native_receipts.append((key, stack[-1].ident))
            else: kept.append(node)
        return super().effect(kept, stack)

    def click_ep(self, key=P, actor=1):
        self.root = self.countries[actor]
        gui = self.ep_gui if key == P else self.root_gui
        self.effect(one(one(gui, 'effects'), key), [self.root])

    def enabled_ep(self, key=P, actor=1):
        self.root = self.countries[actor]
        gui = self.ep_gui if key == P else self.root_gui
        return self.trigger(one(one(gui, 'triggers'), key + '_enabled'), [self.root])

    def timeout_ep(self, holder=2, timer=False):
        self.global_flags.discard('eon_eu_ep_deadline')
        self.global_vars['num_days'] = self.global_vars.get('eon_eu_ep_deadline_day', 14)
        self.root = self.countries[holder]
        self.effect(one(mission(TIMER if timer else RESULT), 'timeout_effect'), [self.root])

    def majority(self): self.click_ep('PG_party_1_influence_click')

    def transfer(self, new=4):
        self.countries[2].ideas.discard('EU_commission_president')
        self.countries[new].ideas.add('EU_commission_president')
        self.global_vars['eucomission'] = self.countries[new].pointer
        self.required('eon_eu_ep_reconcile_owner')

class Regression(unittest.TestCase):
    def test_proposal_no_localized_meta(self):
        m = EpModel(); m.click_ep()
        self.assertFalse(any(r[0] == 'LOCALIZED_META_NOT_EXECUTED' for r in m.native_receipts))
        self.assertIn(RESULT, m.countries[2].missions)

    def test_proposal_rechecks_outsider(self):
        m = EpModel(); m.click_ep(actor=7)
        self.assertEqual(m.global_vars['current_active_agenda_disp'], 0)
        self.assertEqual(m.countries[7].variables['political_power'], 2000)

    def test_proposal_rechecks_suspension(self):
        m = EpModel(); m.countries[1].ideas.add('EUU_voting_rights_suspended'); m.click_ep()
        self.assertEqual(m.global_vars['current_active_agenda_disp'], 0)

    def test_proposal_rechecks_available_numeric_law(self):
        m = EpModel(); m.temp['v'] = 703; m.click_ep()
        self.assertEqual(m.global_vars['current_active_agenda_disp'], 0)

    def test_proposal_rechecks_unsupported_numeric_id(self):
        m = EpModel(); m.temp['v'] = 998; m.global_arrays['EU_potential_votes'].append(998); m.click_ep()
        self.assertEqual(m.global_vars['current_active_agenda_disp'], 0)

    def test_proposal_rechecks_valid_commission_even_single_member(self):
        m = EpModel(); m.countries[2].ideas.discard('EU_commission_president'); m.global_vars['EU_member_count'] = 1; m.click_ep()
        self.assertEqual(m.global_vars['current_active_agenda_disp'], 0)

    def test_proposal_rechecks_live_agenda_and_charges_once(self):
        m = EpModel(); m.click_ep(); m.click_ep()
        self.assertEqual(m.countries[1].variables['political_power'], 1800)
        self.assertEqual(sum(r[0] == 'activate_mission' for r in m.native_receipts), 6)

    def test_proposal_rechecks_budget_block(self):
        m = EpModel(); m.countries[1].flags.add('EU_budget_EP_block'); m.click_ep()
        self.assertEqual(m.global_vars['current_active_agenda_disp'], 0)

    def test_influence_outsider_no_support_or_debit(self):
        m = EpModel(); m.click_ep(); m.click_ep('PG_party_1_influence_click', actor=7)
        self.assertNotIn('global.PG_party_1_support', m.global_flags)
        self.assertEqual(m.countries[7].variables['political_power'], 2000)

    def test_influence_suspended_no_support_or_debit(self):
        m = EpModel(); m.click_ep(); m.countries[1].ideas.add('EUU_voting_rights_suspended'); m.click_ep('PG_party_1_influence_click')
        self.assertNotIn('global.PG_party_1_support', m.global_flags)

    def test_influence_no_duplicate_support_or_fee(self):
        m = EpModel(); m.click_ep(); m.majority(); m.majority()
        self.assertEqual(m.global_vars['active_MEP_Support'], 320)
        self.assertEqual(m.countries[1].variables['political_power'], 1400)

    def test_influence_no_overdraw(self):
        m = EpModel(); m.click_ep(); m.countries[1].variables['political_power'] = 10; m.majority()
        self.assertEqual(m.countries[1].variables['political_power'], 10)
        self.assertNotIn('global.PG_party_1_support', m.global_flags)

    def test_influence_after_deadline_inert(self):
        m = EpModel(); m.click_ep(); m.global_flags.discard('eon_eu_ep_deadline'); m.global_vars['num_days'] = 14; m.majority()
        self.assertNotIn('global.PG_party_1_support', m.global_flags)
        self.assertEqual(m.countries[1].variables['political_power'], 1800)

    def test_pass_no_localized_dispatch_and_unique_council_queue(self):
        m = EpModel(); m.click_ep(); m.majority(); m.click_ep('pass_vote_button_click'); m.click_ep('pass_vote_button_click')
        self.assertEqual(m.global_arrays['EU_council_votes'], [101])
        self.assertNotIn(101, m.global_arrays['EU_potential_votes'])
        self.assertFalse(any(r[0] == 'LOCALIZED_META_NOT_EXECUTED' for r in m.native_receipts))
        self.assertNotIn(101, m.global_arrays.get('EU_passed_votes', []))
        self.assertTrue(all('EUU_cfr_eu' not in c.ideas for c in m.countries.values()))

    def test_pass_outsider_cannot_accept(self):
        m = EpModel(); m.click_ep(); m.majority(); m.click_ep('pass_vote_button_click', actor=7)
        self.assertEqual(m.global_vars['current_active_agenda_disp'], 101)
        self.assertEqual(m.global_arrays['EU_council_votes'], [])

    def test_pass_suspended_cannot_accept(self):
        m = EpModel(); m.click_ep(); m.majority(); m.countries[1].ideas.add('EUU_voting_rights_suspended'); m.click_ep('pass_vote_button_click')
        self.assertEqual(m.global_vars['current_active_agenda_disp'], 101)

    def test_withdraw_ordinary_member_cannot_close(self):
        m = EpModel(); m.click_ep(); m.click_ep('remove_vote_button_click')
        self.assertEqual(m.global_vars['current_active_agenda_disp'], 101)

    def test_withdraw_current_commission_closes_without_approval(self):
        m = EpModel(); m.click_ep(); m.click_ep('remove_vote_button_click', actor=2)
        self.assertEqual(m.global_vars['current_active_agenda_disp'], 0)
        self.assertEqual(m.global_arrays['EU_council_votes'], [])
        self.assertIn(101, m.global_arrays['EU_potential_votes'])

    def test_natural_timeout_declared_boundary_queues_once(self):
        m = EpModel(); m.click_ep(); m.majority(); m.timeout_ep(); m.timeout_ep()
        self.assertEqual(m.global_arrays['EU_council_votes'], [101])
        self.assertIn('focus_EU101_EP_approval', m.global_flags)
        self.assertEqual(m.global_vars['current_active_agenda_disp'], 0)

    def test_failed_round_leaves_no_approval_and_keeps_existing_laws(self):
        m = EpModel(); m.global_arrays['EU_passed_votes'] = [401]; m.global_flags.add('focus_EU401_EP_approval'); m.click_ep(); m.timeout_ep()
        self.assertEqual(m.global_arrays['EU_council_votes'], [])
        self.assertNotIn('focus_EU101_EP_approval', m.global_flags)
        self.assertEqual(m.global_arrays['EU_passed_votes'], [401])
        self.assertIn('focus_EU401_EP_approval', m.global_flags)

    def test_all47_literal_approval_dispatch_without_enactment(self):
        for law in IDS:
            m = EpModel(); m.global_arrays['EU_potential_votes'] = list(IDS); m.global_arrays['EU_passed_votes'] = []
            m.click_ep(); m.majority()
            m.global_vars.update(current_active_agenda_disp=law, eon_eu_ep_agenda=law)
            for c in m.countries.values(): c.variables['eon_eu_ep_mission_agenda'] = law
            m.required('eon_eu_ep_recount_support'); m.timeout_ep()
            self.assertEqual(m.global_arrays['EU_council_votes'], [law], law)
            self.assertIn(f'focus_EU{law}_EP_approval', m.global_flags)
            self.assertEqual(m.global_arrays['EU_passed_votes'], [])

    def test_complete_callback_during_positive_new_round_entirely_inert(self):
        m = EpModel(); m.click_ep(); m.required('eon_eu_ep_close_round'); m.click_ep(); m.majority()
        # Country bindings really are overwritten with the current generation;
        # no injected old var is used as a fictional immutable event payload.
        before = deepcopy((m.global_vars, m.global_arrays, m.global_flags, m.countries[2].missions))
        m.root = m.countries[2]
        m.effect(one(mission(RESULT), 'complete_effect'), [m.root])
        m.effect(one(mission(RESULT), 'timeout_effect'), [m.root])
        m.root = m.countries[3]
        m.effect(one(mission(TIMER), 'timeout_effect'), [m.root])
        self.assertEqual((m.global_vars, m.global_arrays, m.global_flags, m.countries[2].missions), before)
        self.assertIn(TIMER, m.countries[3].missions)

    def test_changed_agenda_same_serial_cannot_resolve_or_transfer(self):
        m = EpModel(); m.click_ep(); m.majority(); m.global_vars['current_active_agenda_disp'] = 401; m.transfer(); m.timeout_ep(holder=4)
        self.assertEqual(m.global_vars['current_active_agenda_disp'], 401)
        self.assertEqual(m.global_arrays['EU_council_votes'], [])
        self.assertEqual(m.global_vars['eon_eu_ep_owner'], m.countries[2].pointer)

    def test_holder_transfer_preserves_original_clock_and_authority(self):
        m = EpModel(); m.click_ep(); m.majority(); m.global_vars['num_days'] = 9; m.transfer()
        self.assertEqual(m.global_vars['eon_eu_ep_deadline_day'], 14)
        self.assertEqual(m.countries[4].mission_days[RESULT], 5)
        self.assertNotIn(RESULT, m.countries[2].missions)
        m.timeout_ep(holder=2)
        self.assertEqual(m.global_arrays['EU_council_votes'], [])
        m.timeout_ep(holder=4)
        self.assertEqual(m.global_arrays['EU_council_votes'], [101])

    def test_vacancy_failure_cannot_change_with_late_group_support(self):
        m = EpModel(); m.click_ep(); m.countries[2].ideas.discard('EU_commission_president')
        m.global_flags.discard('eon_eu_ep_deadline'); m.global_vars['num_days'] = 14
        m.majority(); m.required('eon_eu_ep_reconcile_owner')
        self.assertEqual(m.global_vars['eon_eu_ep_outcome_passed'], 0)
        self.assertEqual(m.global_vars['current_active_agenda_disp'], 101)
        m.transfer(); self.assertEqual(m.global_vars['current_active_agenda_disp'], 0)
        self.assertEqual(m.global_arrays['EU_council_votes'], [])

    def test_last_open_success_survives_postdeadline_mep_change(self):
        m = EpModel(); m.click_ep(); m.majority(); m.global_flags.discard('eon_eu_ep_deadline'); m.global_vars['num_days'] = 14
        m.global_vars.update(MEP_PG_party_0=0, MEP_PG_party_1=0, MEP_Majority=900)
        m.required('eon_eu_ep_recount_support'); m.timeout_ep()
        self.assertEqual(m.global_arrays['EU_council_votes'], [101])

    def test_last_open_failure_survives_postdeadline_majority_lowering(self):
        m = EpModel(); m.click_ep(); m.global_flags.discard('eon_eu_ep_deadline'); m.global_vars['num_days'] = 14
        m.global_vars['MEP_Majority'] = 1; m.required('eon_eu_ep_recount_support'); m.timeout_ep()
        self.assertEqual(m.global_arrays['EU_council_votes'], [])

    def test_positive_flag_authoritative_at_numeric_day_callback_boundary(self):
        m = EpModel(); m.click_ep(); m.majority(); m.global_vars['num_days'] = 14
        self.assertIn('eon_eu_ep_deadline', m.global_flags)
        before = deepcopy((m.global_vars, m.global_arrays, m.global_flags, m.countries[2].missions))
        m.root = m.countries[2]
        m.effect(one(mission(RESULT), 'timeout_effect'), [m.root])
        m.effect(one(mission(RESULT), 'complete_effect'), [m.root])
        m.root = m.countries[3]; m.effect(one(mission(TIMER), 'timeout_effect'), [m.root])
        self.assertEqual((m.global_vars, m.global_arrays, m.global_flags, m.countries[2].missions), before)
        self.assertIn(TIMER, m.countries[3].missions)

    def test_legacy_positive_clock_adopted_without_restart(self):
        m = EpModel(); m.global_vars['current_active_agenda_disp'] = 101
        m.countries[2].missions.add(RESULT); m.countries[2].mission_days[RESULT] = 6
        m.global_flags.add('global.PG_party_0_support'); m.required('eon_eu_ep_reconcile_owner')
        self.assertEqual(m.countries[2].mission_days[RESULT], 6)
        self.assertEqual(m.global_vars['eon_eu_ep_deadline_day'], 6)
        self.assertEqual(m.global_vars['active_MEP_Support'], 120)

    def test_legacy_vacancy_keeps_actual_clock(self):
        m = EpModel(); m.global_vars['current_active_agenda_disp'] = 101
        m.countries[3].missions.add(TIMER); m.countries[3].mission_days[TIMER] = 4
        m.countries[2].ideas.discard('EU_commission_president'); m.required('eon_eu_ep_reconcile_owner')
        self.assertEqual(m.global_vars['current_active_agenda_disp'], 101)
        self.assertIn(TIMER, m.countries[3].missions)
        self.assertNotIn('eon_eu_ep_clock_started', m.global_flags)

    def test_legacy_positive_clock_old_callback_inert(self):
        m = EpModel(); m.global_vars['current_active_agenda_disp'] = 101
        m.countries[2].missions.add(RESULT); m.countries[2].mission_days[RESULT] = 6
        m.root = m.countries[2]; before = deepcopy((m.global_vars, m.global_flags, m.countries[2].missions))
        m.effect(one(mission(RESULT), 'timeout_effect'), [m.root])
        self.assertEqual((m.global_vars, m.global_flags, m.countries[2].missions), before)

    def test_legacy_orphan_closes_without_queue_or_new_clock(self):
        m = EpModel(); m.global_vars['current_active_agenda_disp'] = 101; m.required('eon_eu_ep_reconcile_owner')
        self.assertEqual(m.global_vars['current_active_agenda_disp'], 0)
        self.assertEqual(m.global_arrays['EU_council_votes'], [])
        self.assertNotIn('eon_eu_ep_deadline', m.global_flags)
        self.assertIn(('country_event', 2, 'eon_eu_parliament.1'), m.native_receipts)

    def test_source_special_branches_preserved_ast_and_shared_repeat_field_named(self):
        new = one(one(read('common/scripted_guis/01_european_union_guis.txt'), 'scripted_gui'), 'european_union_gui')
        for section, entries in BASELINE['gui'].items():
            for key, expected in entries.items():
                actual = [n for n in one(one(one(new, section), key), 'else_if') if n[0] != 'limit']
                self.assertEqual(normalized(actual), expected, key)
        for ident, fields in BASELINE['missions'].items():
            actual = mission(ident)
            self.assertEqual(one(actual, 'fire_only_once'), 'no')
            for field, expected in fields.items():
                self.assertEqual(normalized([n for n in one(one(actual, field), 'else_if') if n[0] != 'limit']), expected, (ident, field))
        new_check = one(read('common/scripted_triggers/99_EU_voting_scripted_triggers.txt'), 'EU_parliament_focus_EUXXX_approve_check')
        self.assertEqual(normalized([n for n in one(new_check, 'else_if') if n[0] != 'limit']), BASELINE['approval_check'])

    def test_changed_files_preserve_bom_and_line_endings(self):
        for path, expected in BASELINE['encoding'].items():
            raw = council.source_path(path, SOURCE).read_bytes()
            self.assertEqual(raw.startswith(b'\xef\xbb\xbf'), expected['bom'])
            if expected['crlf']: self.assertNotIn(b'\n', raw.replace(b'\r\n', b''))

    def test_actual_ep_to_council_to_law_full_declared_ast_cycle(self):
        m = EpModel(); m.click_ep(); m.majority(); m.timeout_ep()
        m.temp['v'] = 101; m.root = m.countries[1]
        m.effect(one(one(gui_parts('european_council_voting_dynamic_lists'), 'effects'), council.P), [m.root])
        self.assertEqual(m.global_vars['current_active_vote_disp'], 101)
        for actor in range(1, 7):
            m.root = m.countries[actor]; m.required('eon_eu_support_council_vote')
        m.global_flags.discard('eon_eu_council_vote_deadline'); m.root = m.countries[2]
        m.effect(one(mission('EU_voting_mission_focus_EUXXX_QMV_result'), 'timeout_effect'), [m.root])
        self.assertEqual(m.global_arrays['EU_passed_votes'], [101])
        self.assertEqual(m.global_arrays['EU_council_votes'], [])
        self.assertTrue(all('EUU_cfr_eu' in m.countries[i].ideas for i in range(1, 7)))

    def test_literal_influence_all24_groups_rechecks_and_recounts(self):
        for group in range(24):
            m = EpModel(); m.countries[1].arrays['ruling_party'] = []; m.click_ep()
            m.global_vars.update({f'MEP_PG_party_{i}': 0 for i in range(24)})
            m.global_vars[f'MEP_PG_party_{group}'] = 10
            key = f'PG_party_{group}_influence_click'
            self.assertTrue(m.enabled_ep(key)); m.click_ep(key); m.click_ep(key)
            self.assertEqual(m.global_vars['active_MEP_Support'], 10, group)
            self.assertEqual(m.countries[1].variables['political_power'], 1780, group)
            self.assertFalse(m.enabled_ep(key))

    def test_idle_influence_all24_inert(self):
        m = EpModel()
        for group in range(24):
            m.global_vars[f'MEP_PG_party_{group}'] = 1
            m.click_ep(f'PG_party_{group}_influence_click')
        self.assertEqual(m.countries[1].variables['political_power'], 2000)
        self.assertEqual(m.global_vars.get('active_MEP_Support', 0), 0)

    def test_existing_200_and_300_fee_branches_preserved(self):
        for law, fee in ((101, 200), (201, 200), (401, 200), (601, 300)):
            m = EpModel(); m.temp['v'] = law; m.click_ep()
            self.assertEqual(m.global_vars['current_active_agenda_disp'], law)
            self.assertEqual(m.countries[1].variables['political_power'], 2000 - fee)

    def test_repeated_distinct_ep_stage_uses_same_native_ids_with_new_serial(self):
        m = EpModel(); m.click_ep(); m.majority(); m.timeout_ep()
        first = m.global_vars['eon_eu_ep_instance']
        m.temp['v'] = 201; m.click_ep(); m.majority(); m.timeout_ep()
        self.assertGreater(m.global_vars['eon_eu_ep_instance'], first)
        self.assertEqual(m.global_arrays['EU_council_votes'], [101, 201])
        self.assertNotIn(201, m.global_arrays['EU_potential_votes'])

    def test_parallel_already_queued_law_never_duplicates_at_ep_result(self):
        m = EpModel(); m.click_ep(); m.majority(); m.global_arrays['EU_council_votes'] = [101]; m.timeout_ep()
        self.assertEqual(m.global_arrays['EU_council_votes'], [101])

    def test_already_enacted_law_is_not_requeued_by_delayed_ep_result(self):
        m = EpModel(); m.click_ep(); m.majority(); m.global_arrays['EU_passed_votes'] = [101]; m.timeout_ep()
        self.assertEqual(m.global_arrays['EU_council_votes'], [])
        self.assertEqual(m.global_arrays['EU_passed_votes'], [101])

    def test_suspended_commission_defers_until_lawful_authority_restored(self):
        m = EpModel(); m.click_ep(); m.majority(); m.countries[2].ideas.add('EUU_voting_rights_suspended')
        m.click_ep('pass_vote_button_click'); m.timeout_ep()
        self.assertEqual(m.global_vars['current_active_agenda_disp'], 101)
        self.assertEqual(m.global_arrays['EU_council_votes'], [])
        m.countries[2].ideas.discard('EUU_voting_rights_suspended'); m.required('eon_eu_ep_reconcile_owner')
        self.assertEqual(m.global_arrays['EU_council_votes'], [101])

    def test_closed_window_human_pass_and_withdraw_cannot_rewrite_result(self):
        m = EpModel(); m.click_ep(); m.majority(); m.global_vars['num_days'] = 14; m.global_flags.discard('eon_eu_ep_deadline')
        m.click_ep('pass_vote_button_click'); m.click_ep('remove_vote_button_click', actor=2)
        self.assertEqual(m.global_vars['current_active_agenda_disp'], 101)
        self.assertEqual(m.global_arrays['EU_council_votes'], [])
        m.timeout_ep(); self.assertEqual(m.global_arrays['EU_council_votes'], [101])

    def test_archive_keeps_enacted_laws_and_blocks_late_callbacks(self):
        m = EpModel(); m.global_arrays['EU_passed_votes'] = [401]; m.click_ep(); m.majority(); m.required('eon_eu_ep_close_round')
        m.timeout_ep(); m.timeout_ep(timer=True)
        self.assertEqual(m.global_arrays['EU_passed_votes'], [401])
        self.assertEqual(m.global_arrays['EU_council_votes'], [])

    def test_legacy_expired_timer_is_elapsed_witness_only_then_current_holder_resolves(self):
        m = EpModel(); m.global_vars['current_active_agenda_disp'] = 101
        m.global_flags.update({'global.PG_party_0_support', 'global.PG_party_1_support'})
        m.countries[3].missions.add(TIMER); m.countries[3].mission_days[TIMER] = 0
        m.root = m.countries[3]; m.effect(one(mission(TIMER), 'timeout_effect'), [m.root])
        self.assertEqual(m.global_arrays['EU_council_votes'], [])
        self.assertNotIn('eon_eu_ep_deadline', m.global_flags)
        m.required('eon_eu_ep_reconcile_owner'); self.assertEqual(m.global_arrays['EU_council_votes'], [101])

    def test_legacy_initial_vacancy_retains_elapsed_receipt_until_appointment(self):
        m = EpModel(); m.global_vars['current_active_agenda_disp'] = 101
        m.global_flags.update({'global.PG_party_0_support', 'global.PG_party_1_support'})
        m.countries[2].ideas.discard('EU_commission_president'); m.root = m.countries[3]
        m.effect(one(mission(TIMER), 'timeout_effect'), [m.root])
        self.assertIn('eon_eu_ep_legacy_elapsed', m.global_flags)
        m.required('eon_eu_ep_reconcile_owner')
        self.assertEqual(m.global_vars['current_active_agenda_disp'], 101)
        m.transfer(); self.assertEqual(m.global_arrays['EU_council_votes'], [101])

    def test_independent_sealed_council_closed_actual_casts_cannot_flip_failure(self):
        m = EpModel(); m.global_arrays['EU_council_votes'] = [101]; m.root = m.countries[1]
        m.effect(one(one(gui_parts('european_council_voting_dynamic_lists'), 'effects'), council.P), [m.root])
        for actor in range(1, 7):
            m.root = m.countries[actor]; m.required('eon_eu_support_council_vote' if actor <= 3 else 'eon_eu_reject_council_vote')
        m.countries[2].ideas.discard('EU_commission_president'); m.global_flags.discard('eon_eu_council_vote_deadline')
        for actor in range(1, 7):
            m.root = m.countries[actor]; m.required('eon_eu_support_council_vote')
        m.countries[5].ideas.add('EUU_voting_rights_suspended'); m.countries[6].ideas.discard('EU_member')
        m.countries[4].ideas.add('EU_commission_president'); m.global_vars['eucomission'] = m.countries[4].pointer
        m.required('eon_eu_reconcile_council_vote_owner')
        self.assertNotIn(101, m.global_arrays.get('EU_passed_votes', []))
        self.assertEqual(m.global_vars['current_active_vote_disp'], 0)

RED = [
 'test_proposal_no_localized_meta', 'test_proposal_rechecks_outsider', 'test_proposal_rechecks_suspension',
 'test_proposal_rechecks_available_numeric_law', 'test_proposal_rechecks_unsupported_numeric_id',
 'test_proposal_rechecks_valid_commission_even_single_member', 'test_proposal_rechecks_live_agenda_and_charges_once',
 'test_proposal_rechecks_budget_block', 'test_influence_outsider_no_support_or_debit',
 'test_influence_suspended_no_support_or_debit', 'test_influence_no_duplicate_support_or_fee',
 'test_influence_no_overdraw', 'test_influence_after_deadline_inert',
 'test_pass_no_localized_dispatch_and_unique_council_queue', 'test_pass_outsider_cannot_accept',
 'test_pass_suspended_cannot_accept', 'test_withdraw_current_commission_closes_without_approval',
]
if __name__ == '__main__':
    suite = unittest.TestSuite(Regression(name) for name in RED) if MODE == 'production' else unittest.defaultTestLoader.loadTestsFromTestCase(Regression)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'kind': 'ACTUAL_EP_GUI_MISSION_AST_DECLARED_BOUNDARY_NOT_NATIVE', 'mode': MODE, 'run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors)}))
    raise SystemExit(not result.wasSuccessful())
