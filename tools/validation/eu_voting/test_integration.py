"""Cross-file EU entry points and current-byte format checks."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/validation/diplomacy_package_02'))
from _treaty_support import ast, one


def source(name):
    return ast((ROOT / name).read_text(encoding='utf-8-sig'))


def raw_native_ep_text(data):
    """The three new native EP files use literal identifiers, not BOM tokens.

    Native109 parsed offset-zero U+FEFF as a script definition and as part of
    the first synchronized bare ID. Deliberately do not decode utf-8-sig here:
    it concealed this engine boundary in the earlier AST checks. This policy
    is scoped to those new nonlocalization files, not existing game sources.
    """
    text = data.decode('utf-8', errors='strict')
    if '\ufeff' in text:
        raise ValueError('U+FEFF must not become a native EP identifier/token')
    return text


class Entrypoints(unittest.TestCase):
    def test_native_parliament_first_definitions_are_raw_utf8_identifiers(self):
        expected = {
            'common/scripted_effects/eon_eu_parliament_effects.txt': 'eon_eu_ep_pay_existing_proposal_cost',
            'common/scripted_triggers/eon_eu_parliament_triggers.txt': 'eon_eu_ep_special_context',
        }
        for name, ident in expected.items():
            with self.subTest(path=name):
                text = raw_native_ep_text((ROOT / name).read_bytes())
                definitions = ast(text)
                self.assertGreater(len(definitions), 1)
                self.assertEqual(definitions[0][0], ident)
                self.assertIsInstance(definitions[0][2], list)
                self.assertEqual(len([row for row in definitions if row[0] == ident]), 1)

    def test_native_parliament_synchronized_tokens_are_exact_bare_ids(self):
        path = ROOT / 'common/synchronized_dynamic_tokens/eon_eu_parliament_tokens.txt'
        text = raw_native_ep_text(path.read_bytes())
        self.assertEqual(text.split(), ['EU_parliament_focus_EUXXX_approve',
                                      'EU_parliament_focus_EUXXX_approve_timer'])

    def test_native_ep_encoding_rejects_prefix_interior_and_invalid_utf8_mutants(self):
        # Valid literal identifiers are positive controls. The original
        # standalone-BOM line and BOM-prefixed bare-ID mutations must fail
        # before any utf-8-sig decoding or AST normalization can hide them.
        for valid in (b'helper = { always = yes }\r\n', b'EU_parliament_focus_EUXXX_approve\r\n'):
            self.assertEqual(raw_native_ep_text(valid), valid.decode('utf-8'))
            for mutant in (b'\xef\xbb\xbf' + valid,
                           b'\xef\xbb\xbf\r\n' + valid,
                           valid + b'\xef\xbb\xbf'):
                with self.subTest(data=mutant):
                    with self.assertRaisesRegex(ValueError, 'native EP identifier/token'):
                        raw_native_ep_text(mutant)
            with self.assertRaises(UnicodeDecodeError):
                raw_native_ep_text(valid + b'\xff')

    def test_parliament_localization_keeps_single_required_utf8_bom(self):
        for language in ('english', 'russian'):
            path = ROOT / f'localisation/{language}/eon_eu_parliament_l_{language}.yml'
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b'\xef\xbb\xbf'), str(path))
            self.assertNotIn(b'\xef\xbb\xbf', raw[3:], str(path))
            self.assertTrue(raw.decode('utf-8-sig').startswith('l_' + language + ':'), str(path))

    def test_ui_is_gated_before_retained_open_flag(self):
        from copy import deepcopy
        from eon_eu_frontend_model import FrontModel

        gui = one(one(source('common/scripted_guis/01_european_union_guis.txt'), 'scripted_gui'), 'european_union_gui')
        self.assertEqual(one(gui, 'visible')[0], ('eon_eu_can_view_union', '=', 'yes'))
        triggers = one(gui, 'triggers')
        conditional = {}
        for name, _, body in triggers:
            if name.endswith('_click_enabled'):
                if body[0][0] == 'if': conditional[name] = body
                else: self.assertIn(body[0][0], ('eon_eu_is_active_member', 'eon_eu_can_view_union'), name)
        expected = {f'PG_party_{i}_influence_click_enabled' for i in range(24)}
        expected.update(('pass_vote_button_click_enabled', 'remove_vote_button_click_enabled'))
        self.assertEqual(set(conditional), expected)

        def fixture(agenda):
            model = FrontModel()
            model.triggers.update({k: v for k, _, v in source('common/scripted_triggers/eon_eu_parliament_triggers.txt')})
            model.global_vars.update(current_active_agenda_disp=agenda, MEP_Majority=1,
                                     active_MEP_Support=50, eon_eu_ep_instance=1,
                                     eon_eu_ep_agenda=agenda, eon_eu_ep_owner=model.countries[2].pointer)
            model.global_vars.update({f'MEP_PG_party_{i}': 10 for i in range(24)})
            model.countries[2].variables.update(eon_eu_ep_mission_instance=1, eon_eu_ep_mission_agenda=agenda)
            if agenda == 101:
                model.global_flags.update(('eon_eu_ep_clock_started', 'eon_eu_ep_deadline'))
            return model

        for agenda in (101, 998, 999, 0):
            for candidate in (False, True):
                model = fixture(agenda)
                outsider = model.countries[7]
                # A retained open-screen receipt cannot confer member authority.
                outsider.flags.add('show_euro_offices')
                if candidate: outsider.flags.add('EU_candidate')
                for name, body in conditional.items():
                    with self.subTest(agenda=agenda, candidate=candidate, button=name):
                        model.root = outsider
                        self.assertFalse(model.trigger(body, [outsider]))
                for name, body in conditional.items():
                    # Special withdrawal retains an engine-localized predicate;
                    # negative access checks stop before that native boundary.
                    if agenda in (998, 999) and name == 'remove_vote_button_click_enabled': continue
                    actor = model.countries[2 if name == 'remove_vote_button_click_enabled' else 1]
                    model.root = actor
                    self.assertEqual(model.trigger(body, [actor]), agenda != 0, (agenda, name))

        # Meaningful missing-gate control: ordinary/special group and acceptance
        # entry points would admit the otherwise eligible outsider without the
        # actual member checks; idle remains closed by its own source branch.
        for agenda in (101, 998, 999):
            model = fixture(agenda)
            model.triggers = deepcopy(model.triggers)
            model.triggers['eon_eu_is_active_member'] = [('always', '=', 'yes')]
            model.triggers['eon_eu_ep_member_can_participate'] = [('always', '=', 'yes')]
            outsider = model.countries[7]; model.root = outsider
            for name in ('PG_party_0_influence_click_enabled', 'pass_vote_button_click_enabled'):
                self.assertTrue(model.trigger(conditional[name], [outsider]), (agenda, name))

    def test_office_buttons_nominate_instead_of_awarding(self):
        gui = one(one(source('common/scripted_guis/01_european_union_guis.txt'), 'scripted_gui'), 'european_union_gui')
        effects = one(gui, 'effects')
        mapping = {'eu_president_commission_back': 1, 'eu_parliament_president_back': 2,
                   'eu_central_bank_president_back': 3, 'eu_president_council_back': 4,
                   'foreign_affairs_security_back': 5, 'eu_frontex_director_back': 6,
                   'eu_minister_economy_finance_back': 7, 'eu_sec_general_euro_army_back': 8,
                   'eu_sec_general_euro_navy_back': 9, 'eu_ambassador_to_un_back': 10}
        for name, ident in mapping.items():
            body = one(effects, name + '_click')
            self.assertEqual(body, [('set_temp_variable', '=', [('eon_eu_office_requested_id', '=', str(ident))]),
                                    ('eon_eu_open_office_ballot', '=', 'yes')])

    def test_actual_gui_ballots_use_canonical_callbacks(self):
        gui = one(one(source('common/scripted_guis/01_european_union_guis.txt'), 'scripted_gui'), 'european_union_gui')
        effects = one(gui, 'effects')
        self.assertEqual(one(effects, 'support_council_vote_button_click'), [('eon_eu_support_council_vote', '=', 'yes')])
        self.assertEqual(one(effects, 'reject_council_vote_button_click'), [('eon_eu_reject_council_vote', '=', 'yes')])
        self.assertEqual(one(effects, 'EU_Article_50_click'), [('eon_eu_notify_withdrawal', '=', 'yes')])

    def test_daily_coordinator_exists_without_monitor_or_ai_requirement(self):
        path = ROOT / 'common/on_actions/eon_eu_lifecycle_on_actions.txt'
        self.assertTrue(path.exists(), 'Missing independent EU clock')
        body = one(one(source(str(path.relative_to(ROOT))), 'on_actions'), 'on_daily')
        self.assertEqual(one(body, 'effect'), [('eon_eu_daily_lifecycle_pulse', '=', 'yes')])

    def test_all_legacy_law_results_recount_current_members(self):
        for name, _, body in source('common/scripted_effects/99_EU_voting_scripted_effects.txt'):
            if name.startswith('focus_EU') and name.endswith('_QMV_result'):
                self.assertEqual(body[0], ('eon_eu_recount_council_vote', '=', 'yes'), name)

    def test_candidate_entry_opens_information_screen(self):
        gui = one(one(source('common/scripted_guis/international_systems_scripted_gui.txt'), 'scripted_gui'), 'International_systems_list_main')
        button = one(one(gui, 'effects'), 'international_orgs_list_button_click')
        eu = [body for key, _, body in button if key == 'else_if'][0]
        choices = [body for key, _, body in eu if key == 'if' and isinstance(body, list) and ('limit', '=', [('eon_eu_is_active_member', '=', 'yes')]) in body]
        self.assertTrue(choices, 'Candidate enters an active-members-only blank office screen')
        self.assertIn('show_euro_info', str(eu))

    def test_ai_neutral_weight_does_not_override_legacy_no_vote(self):
        effect = one(source('common/scripted_effects/eon_eu_voting_effects.txt'), 'eon_eu_council_ai_pulse')
        self.assertNotIn("('EU_AI_focus_modifier_yes_vote', '>=', '0')", str(effect))
        self.assertIn("('EU_AI_focus_modifier_yes_vote', '>', '0')", str(effect))

    def test_no_embedded_bom_in_new_game_scripts(self):
        for directory in ('common', 'events', 'localisation/english', 'localisation/russian'):
            for path in (ROOT / directory).rglob('eon_eu*'):
                if path.is_file():
                    data = path.read_bytes()
                    self.assertNotIn(b'\xef\xbb\xbf', data.removeprefix(b'\xef\xbb\xbf'), str(path))

    def test_inclusive_variable_comparisons_use_documented_long_form(self):
        def visit(body, path):
            for key, op, value in body:
                if key == 'check_variable' and isinstance(value, list):
                    for entry in value:
                        self.assertNotIn(entry[1], ('>=', '<='), (path, entry))
                if isinstance(value, list): visit(value, path)
        for directory in ('common', 'events'):
            for path in (ROOT / directory).rglob('eon_eu*.txt'):
                visit(ast(path.read_text(encoding='utf-8-sig')), str(path))

    def test_timed_flags_have_nonzero_values_visible_to_native_engine(self):
        def visit(body, path):
            for key, _, value in body:
                if key in ('set_country_flag', 'set_global_flag') and isinstance(value, list):
                    if any(entry[0] == 'days' for entry in value):
                        self.assertIn(('value', '=', '1'), value, (path, value))
                if isinstance(value, list): visit(value, path)
        for directory in ('common', 'events'):
            for path in (ROOT / directory).rglob('eon_eu*.txt'):
                visit(ast(path.read_text(encoding='utf-8-sig')), str(path))

    def test_legacy_extension_cannot_promise_a_nonexistent_deadline_change(self):
        categories = source('common/decisions/EU_voting_decisions.txt')
        bodies = [one(body, 'EU_extend_Article_50') for _, _, body in categories
                  if isinstance(body, list) and any(row[0] == 'EU_extend_Article_50' for row in body)]
        self.assertEqual(len(bodies), 1)
        self.assertEqual(one(bodies[0], 'allowed'), [('always', '=', 'no')])

    def test_role_budget_refresh_does_not_call_parliament_elections(self):
        effects = source('common/scripted_effects/eon_eu_lifecycle_effects.txt')
        budget = one(effects, 'eon_eu_update_budget')
        self.assertNotIn('election_EU_Parliament', str(budget))
        self.assertNotIn('clear_EU_Parliament', str(budget))
        parliament = one(effects, 'eon_eu_update_parliament')
        self.assertNotIn('eon_eu_budget_changed', str(parliament))
        body = one(budget, 'if')
        names = [key for key, _, _ in body]
        self.assertLess(names.index('update_EU_budget_call_rate'), names.index('set_variable'))
        self.assertLess(names.index('set_variable'), names.index('distribute_EU_budget'))
        daily = one(one(effects, 'eon_eu_daily_lifecycle_pulse'), 'if')
        names = [key for key, _, _ in daily]
        self.assertLess(names.index('eon_eu_daily_institutions_pulse'), names.index('eon_eu_update_budget'))

    def test_archive_releases_defence_union_creation_receipt(self):
        import importlib.util
        from copy import deepcopy
        path=ROOT/'tools/validation/edu_protocol/_protocol_model.py'
        spec=importlib.util.spec_from_file_location('eon_archive_edu_model',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        lifecycle=source('common/scripted_effects/eon_eu_lifecycle_effects.txt')
        body=one(lifecycle,'eon_eu_reset_institutional_laws')
        from eon_eu_frontend_model import source_path
        handoff=source_path('common/scripted_effects/eon_eu_handoff_effects.txt')
        prefix=[('eon_eu_handoff_archive','=','yes')] if handoff.exists() else []
        self.assertEqual(body[:len(prefix)+1],prefix+[('eon_edu_dissolve_confirmed_union','=','yes')])
        edu_delegation=body[len(prefix)]
        def walk(nodes):
            for k,op,v in nodes:
                yield k,op,v
                if isinstance(v,list):yield from walk(v)
        self.assertFalse(any(k=='clr_global_flag' and v=='EDU' for k,op,v in walk(body)))
        daily=one(one(lifecycle,'eon_eu_daily_lifecycle_pulse'),'if')
        self.assertIn(('eon_edu_daily_pulse','=','yes'),daily)
        model=module.Model();model.decision('EU_create_EDU',1)
        model.decision('eon_edu_request_join',2,1);model.decision('eon_edu_accept_request',1,2)
        nato=model.make_foreign_faction(3,[4])
        for actor in (3,4):
            model.c[actor]['ideas'].add('NATO_member')
            model.c[actor]['vars']['eon_edu_member_instance']=0  # Undefined native variables already read as zero.
            model.c[actor]['vars']['eon_edu_constructor_confirmed_instance']=0
        snapshot=deepcopy((model.c[3],model.c[4],model.factions[nato]))
        instance=model.g['eon_edu_instance'];model.c[1]['dismantle_fail']=True
        # All other archive systems are outside this interpreter. Run the actual
        # source delegation, then the unconditional dormant-union EDU retry.
        model.effect([edu_delegation],module.context(5,5))
        self.assertTrue(model.same(1,2));self.assertIn('EDU',model.gf)
        for actor in (1,2):self.assertEqual(model.c[actor]['vars']['eon_edu_member_instance'],instance)
        model.union_active=False;model.c[1]['dismantle_fail']=False
        model.effect([('eon_edu_daily_pulse','=','yes')],module.context(5,5))
        for actor in (1,2):self.assertIsNone(model.c[actor]['faction'])
        self.assertNotIn('EDU',model.gf)
        self.assertEqual((model.c[3],model.c[4],model.factions[nato]),snapshot)
        self.assertEqual(model.g['eon_edu_generation_counter'],instance)

    def test_existing_game_bom_and_eol_styles_preserved(self):
        changed = subprocess.check_output(['git', 'diff', 'HEAD', '--name-only'], cwd=ROOT, text=True).splitlines()
        for name in changed:
            if not name.startswith(('common/', 'events/', 'localisation/')): continue
            old = subprocess.check_output(['git', 'show', 'HEAD:' + name], cwd=ROOT)
            new = (ROOT / name).read_bytes()
            for data in (old, new): self.assertNotIn(b'\r\r\n', data)
            def style(data):
                return (data.startswith(b'\xef\xbb\xbf'), b'\r\n' in data,
                        b'\n' in data.replace(b'\r\n', b''), b'\r' in data.replace(b'\r\n', b''))
            self.assertEqual(style(old), style(new), name)


if __name__ == '__main__': unittest.main(verbosity=2)
