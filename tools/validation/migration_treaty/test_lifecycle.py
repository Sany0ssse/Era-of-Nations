"""Execute the actual treaty AST in a bounded model; this is not HOI4 acceptance."""
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
import sys
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/validation/diplomacy_package_02'))
from _treaty_support import Country, Interpreter as Base, ast, one, compare


@dataclass
class PopulationState:
    owner: int
    population_k: float = 100
    controlled: bool = True


@dataclass
class Nation(Country):
    ideas: set = field(default_factory=set)
    subject_of: int | None = None
    states: list = field(default_factory=list)
    flag_days: dict = field(default_factory=dict)


class Interpreter(Base):
    def __init__(self, countries, sender=1, receiver=2, from_id=None):
        self.countries, self.sender, self.receiver = countries, sender, receiver
        self.from_id = receiver if from_id is None else from_id
        self.temp, self.external_calls, self.opinion_calls = {}, [], []
        self.remove_all = False
        self.effects = {k: v for k, op, v in ast((ROOT / 'common/scripted_effects/eon_migration_treaty_effects.txt').read_text(encoding='utf-8-sig'))}
        self.triggers = {k: v for k, op, v in ast((ROOT / 'common/scripted_triggers/eon_migration_treaty_triggers.txt').read_text(encoding='utf-8-sig'))}
        self.actions = {k: v for k, op, v in one(ast((ROOT / 'common/scripted_diplomatic_actions/MDC_migration.txt').read_text(encoding='utf-8-sig')), 'scripted_diplomatic_actions')}
        self.hooks = {k: v for k, op, v in one(ast((ROOT / 'common/on_actions/eon_migration_treaty_on_actions.txt').read_text(encoding='utf-8-sig')), 'on_actions')}

    def country(self, token, stack):
        if token == 'FROM':
            return self.countries[self.from_id]
        return super().country(token, stack)

    def value(self, token, stack):
        if token == 'FROM':
            return self.from_id
        return super().value(token, stack)

    def trigger(self, nodes, stack=None):
        if stack is None:
            stack = [self.countries[self.receiver]]
        for key, op, value in nodes:
            current = stack[-1]
            if key == 'FROM':
                passed = self.trigger(value, stack + [self.country('FROM', stack)])
            elif key == 'has_dynamic_modifier':
                passed = one(value, 'modifier') in current.modifiers
            elif key == 'has_idea':
                passed = value in current.ideas
            elif key == 'tag':
                passed = current.ident == self.country(value, stack).ident
            elif key == 'is_subject':
                passed = (current.subject_of is not None) == (value == 'yes')
            elif key == 'is_subject_of':
                passed = current.subject_of == self.country(value, stack).ident
            elif key == 'any_owned_state':
                passed = any(self.trigger(value, stack + [state]) for state in current.states)
            elif key == 'is_owned_and_controlled_by':
                passed = current.owner == self.country(value, stack).ident and current.controlled
            elif key == 'state_population_k':
                passed = compare(current.population_k, op, float(value))
            else:
                passed = super().trigger([(key, op, value)], stack)
            if not passed:
                return False
        return True

    def effect(self, nodes, stack=None):
        if stack is None:
            self.temp = {}
            stack = [self.countries[self.receiver]]
        index = 0
        while index < len(nodes):
            key, op, value = nodes[index]
            index += 1
            current = stack[-1]
            if key == 'if':
                branches = [('if', value)]
                while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                    branches.append((nodes[index][0], nodes[index][2]))
                    index += 1
                for kind, branch in branches:
                    if kind == 'else' or self.trigger(one(branch, 'limit'), stack):
                        self.effect([node for node in branch if node[0] != 'limit'], stack)
                        break
            elif key in ('every_country', 'every_possible_country'):
                limit = next((v for k, op, v in value if k == 'limit'), [])
                for nation in sorted(self.countries.values(), key=lambda nation: nation.ident):
                    if (nation.exists or key == 'every_possible_country') and self.trigger(limit, stack + [nation]):
                        self.effect([node for node in value if node[0] != 'limit'], stack + [nation])
            elif key == 'FROM':
                self.effect(value, stack + [self.country('FROM', stack)])
            elif key in ('add_dynamic_modifier', 'remove_dynamic_modifier'):
                modifier = one(value, 'modifier')
                if key == 'add_dynamic_modifier':
                    current.modifiers.add(modifier)
                else:
                    current.modifiers.discard(modifier)
            elif key == 'set_country_flag' and isinstance(value, list):
                flag = self.flag(one(value, 'flag'), stack)
                current.flags.add(flag)
                current.flag_days[flag] = float(one(value, 'days'))
            elif key == 'clr_country_flag':
                flag = self.flag(value, stack)
                current.flags.discard(flag)
                current.flag_days.pop(flag, None)
            elif key == 'add_to_variable':
                name, operator, amount = value[0]
                if '.' in name:
                    target, name = name.split('.', 1)
                    owner = self.country(target, stack)
                else:
                    owner = current
                owner.variables[name] = owner.variables.get(name, 0) + self.value(amount, stack)
            else:
                super().effect([(key, op, value)], stack)

    def callback(self, name, action='propose_migrants_agreement'):
        self.effect(one(self.actions[action], name))

    def hook(self, name):
        self.effect(one(self.hooks[name], 'effect'), [self.countries[self.sender]])


def setup():
    countries = {ident: Nation(ident, opinions={peer: 30 for peer in range(1, 5)}, states=[PopulationState(ident)]) for ident in range(1, 5)}
    countries[2].modifiers.add('high_unemployment_modifier')
    countries[3].modifiers.add('high_unemployment_modifier')
    return countries


def recruitment_snapshot(countries):
    return {ident: (deepcopy(nation.variables), set(nation.flags), set(nation.modifiers), deepcopy(nation.states), nation.subject_of)
            for ident, nation in countries.items()}


class TreatyLifecycle(unittest.TestCase):
    def test_bilateral_roles_cooldown_and_duplicate_callbacks(self):
        nations = setup()
        model = Interpreter(nations)
        self.assertTrue(model.trigger(one(model.actions['propose_migrants_agreement'], 'can_be_sent')))
        model.callback('on_sent_effect')
        pending = recruitment_snapshot(nations)
        model.callback('on_sent_effect')
        self.assertEqual(recruitment_snapshot(nations), pending)
        self.assertEqual(nations[1].variables['pending_migration_agreement_country'], 2)
        self.assertEqual(nations[2].variables['eon_migration_treaty_pending_sender'], 1)
        self.assertEqual(nations[1].flag_days['migration_agreement_cooldown@2'], 120)
        self.assertEqual(nations[2].flag_days['migration_agreement_cooldown@1'], 120)
        model.callback('complete_effect')
        self.assertAlmostEqual(nations[1].variables['migrants_add'], .05)
        self.assertAlmostEqual(nations[2].variables['migrants_cut'], -.05)
        self.assertIn('migration_agreement_migrants_add@2', nations[1].flags)
        self.assertIn('migration_agreement_migrants_cut@1', nations[2].flags)
        once, opinion_count = recruitment_snapshot(nations), len(model.opinion_calls)
        model.callback('complete_effect')
        self.assertEqual(recruitment_snapshot(nations), once)
        self.assertEqual(len(model.opinion_calls), opinion_count)
        self.assertEqual(nations[1].states[0].population_k, 100)
        self.assertEqual(nations[2].states[0].population_k, 100)

    def test_invalid_execution_drains_exact_pending_without_contract(self):
        for invalid in ('war', 'exporter_closed', 'importer_closed', 'exporter_no_jobs', 'opinion',
                        'exporter_annexed', 'importer_annexed', 'no_control', 'zero_population', 'subject_changed', 'allied_war'):
            with self.subTest(invalid=invalid):
                nations = setup()
                model = Interpreter(nations)
                model.callback('on_sent_effect')
                if invalid == 'war': nations[2].wars.add(1)
                elif invalid == 'exporter_closed': nations[2].ideas.add('closed_borders')
                elif invalid == 'importer_closed': nations[1].ideas.add('closed_borders')
                elif invalid == 'exporter_no_jobs': nations[2].modifiers.discard('high_unemployment_modifier')
                elif invalid == 'opinion': nations[2].opinions[1] = 9
                elif invalid == 'exporter_annexed': nations[2].exists = False
                elif invalid == 'importer_annexed': nations[1].exists = False
                elif invalid == 'no_control': nations[2].states[0].controlled = False
                elif invalid == 'zero_population': nations[1].states[0].population_k = 0
                elif invalid == 'subject_changed': nations[2].subject_of = 3
                elif invalid == 'allied_war':
                    nations[2].in_faction = True
                    nations[2].allies.add(3)
                    nations[3].wars.add(1)
                self.assertFalse(model.trigger(one(model.actions['propose_migrants_agreement'], 'can_be_accepted')))
                model.callback('complete_effect')
                self.assertNotIn('migration_agreement_migrants_add@2', nations[1].flags)
                self.assertNotIn('migration_agreement_migrants_cut@1', nations[2].flags)
                self.assertNotIn('pending_migration_agreement_country', nations[1].variables)
                self.assertNotIn('eon_migration_treaty_pending_sender', nations[2].variables)

    def test_wrong_pair_response_preserves_original_and_third_country(self):
        nations = setup()
        model = Interpreter(nations)
        model.callback('on_sent_effect')
        before = recruitment_snapshot(nations)
        wrong = Interpreter(nations, sender=1, receiver=3)
        wrong.callback('complete_effect')
        wrong.callback('reject_effect')
        self.assertEqual(recruitment_snapshot(nations), before)
        wrong = Interpreter(nations, sender=4, receiver=2)
        wrong.callback('complete_effect')
        self.assertEqual(recruitment_snapshot(nations), before)

    def test_reject_is_idempotent_and_does_not_change_subject_autonomy(self):
        nations = setup()
        nations[2].subject_of = 1
        nations[2].variables['autonomy_ratio'] = .6
        model = Interpreter(nations)
        model.callback('on_sent_effect')
        model.callback('reject_effect')
        once, opinion_count = recruitment_snapshot(nations), len(model.opinion_calls)
        model.callback('reject_effect')
        self.assertEqual(recruitment_snapshot(nations), once)
        self.assertEqual(len(model.opinion_calls), opinion_count)
        self.assertEqual(nations[2].variables['autonomy_ratio'], .6)

    def test_cancel_both_initiator_roles_repeated_and_one_sided(self):
        for reverse in (False, True):
            for one_sided in (False, True):
                with self.subTest(reverse=reverse, one_sided=one_sided):
                    nations = setup()
                    model = Interpreter(nations)
                    model.callback('on_sent_effect')
                    model.callback('complete_effect')
                    if one_sided:
                        nations[2].flags.discard('migration_agreement_migrants_cut@1')
                    cancel = Interpreter(nations, sender=2 if reverse else 1, receiver=1 if reverse else 2)
                    self.assertTrue(cancel.trigger(one(cancel.actions['cancel_migrants_agreement'], 'can_be_sent')))
                    cancel.callback('complete_effect', 'cancel_migrants_agreement')
                    self.assertEqual(nations[1].variables['migrants_add'], 0)
                    self.assertEqual(nations[2].variables['migrants_cut'], 0)
                    self.assertNotIn('migrants_agreement_add', nations[1].modifiers)
                    self.assertNotIn('migrants_agreement_cut', nations[2].modifiers)
                    once = recruitment_snapshot(nations)
                    cancel.callback('complete_effect', 'cancel_migrants_agreement')
                    self.assertEqual(recruitment_snapshot(nations), once)
                    self.assertEqual(nations[1].states[0].population_k, 100)
                    self.assertEqual(nations[2].states[0].population_k, 100)

    def test_reconciliation_retains_other_partners_and_repairs_drift(self):
        nations = setup()
        nations[1].flags.update(('migration_agreement_migrants_add@2', 'migration_agreement_migrants_add@3'))
        nations[2].flags.add('migration_agreement_migrants_cut@1')
        nations[3].flags.add('migration_agreement_migrants_cut@1')
        nations[1].variables['migrants_add'] = 500
        model = Interpreter(nations)
        model.effect(model.effects['eon_migration_treaty_reconcile_country'], [nations[1]])
        self.assertAlmostEqual(nations[1].variables['migrants_add'], .1)
        model.callback('complete_effect', 'cancel_migrants_agreement')
        self.assertAlmostEqual(nations[1].variables['migrants_add'], .05)
        self.assertIn('migration_agreement_migrants_add@3', nations[1].flags)
        self.assertIn('migration_agreement_migrants_cut@1', nations[3].flags)
        nations[3].exists = False
        model.effect(model.effects['eon_migration_treaty_reconcile_country'], [nations[1]])
        self.assertEqual(nations[1].variables['migrants_add'], 0)
        self.assertNotIn('migrants_agreement_add', nations[1].modifiers)

    def test_legacy_offer_cannot_establish_new_contract(self):
        nations = setup()
        nations[1].variables['pending_migration_agreement_country'] = 2
        model = Interpreter(nations)
        model.callback('complete_effect')
        self.assertNotIn('migration_agreement_migrants_add@2', nations[1].flags)
        self.assertNotIn('pending_migration_agreement_country', nations[1].variables)

    def test_no_proposal_during_pending_cooldown_conflicting_role_or_self(self):
        for invalid in ('incoming_pending', 'outgoing_pending', 'sender_pending', 'cooldown', 'sender_cooldown', 'importer_exports', 'exporter_imports', 'self'):
            with self.subTest(invalid=invalid):
                nations = setup()
                if invalid == 'incoming_pending': nations[2].variables['eon_migration_treaty_pending_sender'] = 3
                elif invalid == 'outgoing_pending': nations[2].variables['pending_migration_agreement_country'] = 3
                elif invalid == 'sender_pending': nations[1].variables['pending_migration_agreement_country'] = 3
                elif invalid == 'cooldown': nations[2].flags.add('migration_agreement_cooldown@1')
                elif invalid == 'sender_cooldown': nations[1].flags.add('migration_agreement_cooldown@2')
                elif invalid == 'importer_exports': nations[1].modifiers.add('migrants_agreement_cut')
                elif invalid == 'exporter_imports': nations[2].modifiers.add('migrants_agreement_add')
                model = Interpreter(nations, receiver=1 if invalid == 'self' else 2)
                before = recruitment_snapshot(nations)
                self.assertFalse(model.trigger(one(model.actions['propose_migrants_agreement'], 'can_be_sent')))
                model.callback('on_sent_effect')
                self.assertEqual(recruitment_snapshot(nations), before)

    def test_source_encoding_ids_and_no_population_or_autonomy_mutation(self):
        action = (ROOT / 'common/scripted_diplomatic_actions/MDC_migration.txt').read_bytes()
        self.assertTrue(action.startswith(b'##### Created by denzzerr #####\n'))
        self.assertNotIn(b'\r', action)
        self.assertFalse(action.endswith(b'\n'))
        self.assertEqual(set(Interpreter(setup()).actions), {'propose_migrants_agreement', 'cancel_migrants_agreement'})
        effect = (ROOT / 'common/scripted_effects/eon_migration_treaty_effects.txt').read_text(encoding='utf-8-sig')
        self.assertNotIn('add_manpower', effect)
        self.assertNotIn('add_autonomy_ratio', action.decode('utf-8-sig'))
        for language in ('english', 'russian'):
            path = ROOT / f'localisation/{language}/replace/eon_migration_treaty_l_{language}.yml'
            self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))

    def test_existing_prices_icons_and_ai_policy_preserved(self):
        baseline = subprocess.check_output([
            'git', 'show', '9fa45d8e009c6858213ff341cc68c5609ccef9a5:common/scripted_diplomatic_actions/MDC_migration.txt'
        ], cwd=ROOT).decode('utf-8-sig')
        original = {k: v for k, op, v in one(ast(baseline), 'scripted_diplomatic_actions')}
        current = Interpreter(setup()).actions
        for action in original:
            for field in ('allowed', 'cost', 'icon', 'requires_acceptance', 'show_acceptance_on_action_button', 'ai_desire'):
                self.assertEqual(one(current[action], field), one(original[action], field))
        self.assertEqual(one(current['propose_migrants_agreement'], 'ai_acceptance'),
                         one(original['propose_migrants_agreement'], 'ai_acceptance'))

    def test_annex_and_subject_annex_clear_exact_pair_and_dormant_tags(self):
        for hook in ('on_annex', 'on_subject_annexed'):
            for dying_importer in (False, True):
                with self.subTest(hook=hook, dying_importer=dying_importer):
                    nations = setup()
                    model = Interpreter(nations)
                    model.callback('on_sent_effect')
                    model.callback('complete_effect')
                    dying = 1 if dying_importer else 2
                    survivor = 2 if dying_importer else 1
                    nations[3].flags.add(f'migration_agreement_migrants_add@{dying}')
                    nations[dying].flags.add('migration_agreement_migrants_cut@3')
                    nations[3].exists = False  # Even a dormant country's flags must be removed.
                    nations[4].variables.update(pending_migration_agreement_country=3,
                                               eon_migration_treaty_pending_terms=1)
                    nations[survivor].variables.update(pending_migration_agreement_country=dying,
                                                      eon_migration_treaty_pending_terms=1)
                    if hook == 'on_annex':
                        native = Interpreter(nations, sender=4, from_id=dying)
                    else:
                        native = Interpreter(nations, sender=dying, from_id=4)
                    populations = {ident: deepcopy(nation.states) for ident, nation in nations.items()}
                    native.hook(hook)
                    once = recruitment_snapshot(nations)
                    native.hook(hook)
                    self.assertEqual(recruitment_snapshot(nations), once)
                    self.assertNotIn('pending_migration_agreement_country', nations[survivor].variables)
                    self.assertEqual(nations[4].variables['pending_migration_agreement_country'], 3)
                    self.assertEqual(nations[4].variables['eon_migration_treaty_pending_terms'], 1)
                    self.assertEqual(nations[dying].variables['migrants_add'], 0)
                    self.assertEqual(nations[dying].variables['migrants_cut'], 0)
                    for ident, nation in nations.items():
                        for flag in nation.flags:
                            self.assertFalse(flag.startswith('migration_agreement_') and
                                             (ident == dying or flag.endswith(f'@{dying}')))
                        self.assertEqual(nation.states, populations[ident])
                    nations[dying].exists = False
                    nations[dying].exists = True  # Simulate a later country release.
                    nations[3].exists = True
                    for nation in nations.values():
                        native.effect(native.effects['eon_migration_treaty_reconcile_country'], [nation])
                        self.assertEqual(nation.variables['migrants_add'], 0)
                        self.assertEqual(nation.variables['migrants_cut'], 0)

    def test_legacy_dead_partner_monthly_cleanup_and_revival(self):
        for pending_direction in ('outgoing', 'incoming', 'none'):
            with self.subTest(pending_direction=pending_direction):
                nations = setup()
                nations[1].flags.add('migration_agreement_migrants_add@2')
                nations[2].flags.add('migration_agreement_migrants_cut@1')
                nations[1].variables['migrants_add'] = .05
                nations[2].variables['migrants_cut'] = -.05
                nations[1].modifiers.add('migrants_agreement_add')
                nations[2].modifiers.add('migrants_agreement_cut')
                nations[2].exists = False
                if pending_direction == 'outgoing':
                    nations[1].variables.update(pending_migration_agreement_country=2,
                                               eon_migration_treaty_pending_terms=1)
                elif pending_direction == 'incoming':
                    nations[1].variables.update(eon_migration_treaty_pending_sender=2,
                                               eon_migration_treaty_pending_terms=1)
                nations[3].variables.update(pending_migration_agreement_country=4,
                                           eon_migration_treaty_pending_terms=1)
                model = Interpreter(nations)
                model.effect(model.effects['eon_migration_treaty_reconcile_country'], [nations[1]])
                self.assertNotIn('migration_agreement_migrants_add@2', nations[1].flags)
                self.assertNotIn('migration_agreement_migrants_cut@1', nations[2].flags)
                self.assertNotIn('pending_migration_agreement_country', nations[1].variables)
                self.assertNotIn('eon_migration_treaty_pending_sender', nations[1].variables)
                self.assertNotIn('eon_migration_treaty_pending_terms', nations[1].variables)
                self.assertEqual(nations[2].variables['migrants_cut'], 0)
                self.assertNotIn('migrants_agreement_cut', nations[2].modifiers)
                self.assertEqual(nations[3].variables['pending_migration_agreement_country'], 4)
                nations[2].exists = True
                model.effect(model.effects['eon_migration_treaty_reconcile_country'], [nations[2]])
                self.assertEqual(nations[2].variables['migrants_cut'], 0)
                self.assertFalse(model.trigger(model.triggers['eon_migration_treaty_pair_active']))

    def test_live_unanswered_reservation_stays_locked_through_reconciliation(self):
        nations = setup()
        model = Interpreter(nations)
        model.callback('on_sent_effect')
        original_sender = deepcopy(nations[1].variables)
        original_receiver = deepcopy(nations[2].variables)
        for nation in (nations[1], nations[2]):
            for key in list(nation.flags):  # Cooldown expiry does not imply consent or queue release.
                if key.startswith('migration_agreement_cooldown@'):
                    nation.flags.discard(key)
            model.effect(model.effects['eon_migration_treaty_reconcile_country'], [nation])
        for key, value in original_sender.items():
            self.assertEqual(nations[1].variables[key], value)
        for key, value in original_receiver.items():
            self.assertEqual(nations[2].variables[key], value)
        self.assertFalse(model.trigger(model.triggers['eon_migration_treaty_send_ready']))
        before = recruitment_snapshot(nations)
        model.callback('on_sent_effect')
        self.assertEqual(recruitment_snapshot(nations), before)

    def test_annex_preserves_an_unrelated_active_treaty(self):
        nations = setup()
        model = Interpreter(nations)
        model.callback('on_sent_effect')
        model.callback('complete_effect')
        nations[3].flags.add('migration_agreement_migrants_add@4')
        nations[4].flags.add('migration_agreement_migrants_cut@3')
        nations[3].variables['migrants_add'] = .05
        nations[4].variables['migrants_cut'] = -.05
        nations[3].modifiers.add('migrants_agreement_add')
        nations[4].modifiers.add('migrants_agreement_cut')
        model.hook('on_annex')  # ROOT=1, FROM=2; 3<->4 has no relationship to that annex.
        self.assertIn('migration_agreement_migrants_add@4', nations[3].flags)
        self.assertIn('migration_agreement_migrants_cut@3', nations[4].flags)
        self.assertAlmostEqual(nations[3].variables['migrants_add'], .05)
        self.assertAlmostEqual(nations[4].variables['migrants_cut'], -.05)
        self.assertIn('migrants_agreement_add', nations[3].modifiers)
        self.assertIn('migrants_agreement_cut', nations[4].modifiers)


if __name__ == '__main__':
    unittest.main(verbosity=2)
