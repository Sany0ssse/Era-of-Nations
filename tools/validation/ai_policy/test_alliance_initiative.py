"""Bounded execution of real alliance policy, not a native AI-choice simulator."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/validation/diplomacy_package_03'))
from _support import Model, compare, maybe, one


class PolicyModel(Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for country in self.countries.values():
            country.neighbors = set()
            country.wargoals = set()
            country.justifications = set()
            country.stability = .7
        self.expiring_flags = {}
        self.day = 0

    def trigger(self, nodes, stack=None):
        stack = [self.current] if stack is None else stack
        if len(nodes) == 1:
            key, op, value = nodes[0]
            country = self.countries[stack[-1]]
            if key == 'is_neighbor_of':
                return self.ref(value, stack) in country.neighbors
            if key == 'has_stability':
                return compare(country.stability, op, float(value))
            if key in ('has_wargoal_against', 'is_justifying_wargoal_against'):
                return self.ref(value, stack) in getattr(country, 'wargoals' if key == 'has_wargoal_against' else 'justifications')
            if key == 'any_other_country':
                return any(self.trigger(value, stack + [ident]) for ident, peer in self.countries.items()
                           if peer.exists and ident != country.ident)
        # Evaluate primitives one at a time, with the existing fail-closed interpreter
        # responsible for every other predicate, scope and ordered conditional.
        if len(nodes) > 1 and all(key != 'if' for key, op, value in nodes):
            return all(self.trigger([node], stack) for node in nodes)
        return super().trigger(nodes, stack)

    def effect(self, nodes, stack=None):
        if stack is None:
            self.temp = {}
            stack = [self.current]
        for node in nodes:
            key, op, value = node
            if key == 'set_country_flag' and isinstance(value, list):
                flag = one(value, 'flag')
                assert one(value, 'value') == '1'
                self.countries[stack[-1]].flags.add(flag)
                self.expiring_flags[(stack[-1], flag)] = self.day + int(one(value, 'days'))
            else:
                # Ordered if/else groups must be delivered intact.
                if key == 'if':
                    return super().effect(nodes, stack)
                super().effect([node], stack)

    def advance(self, days):
        self.day += days
        for (ident, flag), expiry in list(self.expiring_flags.items()):
            if expiry <= self.day:
                self.countries[ident].flags.discard(flag)
                del self.expiring_flags[(ident, flag)]

    def ready(self):
        return all(self.trigger(one(self.action, key)) for key in
                   ('allowed', 'visible', 'selectable', 'can_be_sent'))

    def proposal_score(self):
        nodes = maybe(self.action, 'ai_desire', [])
        result = float(maybe(nodes, 'base', '0'))
        for key, op, value in nodes:
            if key == 'modifier' and self.trigger([n for n in value if n[0] != 'add']):
                result += float(one(value, 'add'))
        return result


def fixture():
    model = PolicyModel()
    model.countries[1].ai = True
    model.countries[2].ai = True
    model.countries[1].neighbors.add(2)
    model.countries[2].neighbors.add(1)
    model.countries[1].opinions[2] = 150
    model.countries[2].opinions[1] = 150
    model.countries[3].wargoals.add(1)
    return model


class InitiativeTests(unittest.TestCase):
    def test_ai_can_propose_to_trusted_neighbor_under_direct_threat(self):
        model = fixture()
        self.assertTrue(model.ready(), 'AI cannot initiate the existing consensual alliance action')
        self.assertGreaterEqual(model.proposal_score(), 25)

    def test_threat_is_to_the_protected_country_not_self_or_unrelated_country(self):
        for target, allowed in ((1, True), (2, True), (3, False), (4, False)):
            with self.subTest(target=target):
                model = fixture()
                model.countries[3].wargoals = {target}
                self.assertEqual(model.ready(), allowed)

    def test_defence_and_justification_are_security_needs(self):
        for role in (1, 2):
            for need in ('defensive', 'justification'):
                with self.subTest(role=role, need=need):
                    model = fixture()
                    model.countries[3].wargoals.clear()
                    if need == 'defensive': model.countries[role].defensive = True
                    else: model.countries[3].justifications.add(role)
                    self.assertTrue(model.ready())

    def test_no_global_tension_only_or_distant_enemy_neighbor_spam(self):
        for change in ('peace', 'distant', 'sender_distrust', 'recipient_distrust', 'unstable'):
            with self.subTest(change=change):
                model = fixture()
                if change == 'peace': model.countries[3].wargoals.clear()
                if change == 'distant': model.countries[2].neighbors.clear()
                if change == 'sender_distrust': model.countries[1].opinions[2] = 100
                if change == 'recipient_distrust': model.countries[2].opinions[1] = 100
                if change == 'unstable': model.countries[1].stability = .35
                self.assertFalse(model.ready())
                self.assertEqual(model.proposal_score(), 0)

    def test_potential_partner_must_not_be_preparing_to_attack_the_other_party(self):
        for attacker, target in ((1, 2), (2, 1)):
            for preparation in ('wargoals', 'justifications'):
                with self.subTest(attacker=attacker, preparation=preparation):
                    model = fixture()
                    getattr(model.countries[attacker], preparation).add(target)
                    self.assertFalse(model.ready(), 'An attacker is being selected as a defensive partner')
                    self.assertEqual(model.proposal_score(), 0)

    def test_current_national_rights_tension_and_pending_are_still_binding(self):
        for veto in ('subject', 'faction', 'offensive', 'national_creator', 'national_member',
                     'belarus_neutral', 'join_tension', 'sender_pending', 'recipient_pending'):
            with self.subTest(veto=veto):
                model = fixture()
                if veto == 'subject': model.countries[1].subject = True
                if veto == 'faction': model.make_faction(1, 'faction_template_nato')
                if veto == 'offensive': model.countries[1].offensive = True
                if veto == 'national_creator': model.countries[1].rules['can_create_factions'] = False
                if veto == 'national_member': model.countries[2].rules['can_join_factions'] = False
                if veto == 'belarus_neutral': model.countries[1].ideas.add('BLR_neutrality_politic')
                if veto == 'join_tension': model.countries[2].native_modifiers['join_faction_tension'] = 1.1
                if veto == 'sender_pending': model.countries[1].variables['eon_defensive_alliance_pending_recipient'] = 4
                if veto == 'recipient_pending': model.countries[2].variables['eon_defensive_alliance_pending_sender'] = 4
                self.assertFalse(model.ready())

    def test_reject_releases_reservation_but_keeps_180_day_sender_cooldown(self):
        model = fixture()
        self.assertTrue(model.ready())
        model.action_effect('on_sent_effect')
        self.assertFalse(model.factions, 'Sending must never manufacture consent')
        model.action_effect('reject_effect')
        self.assertEqual(model.countries[1].variables.get('eon_defensive_alliance_pending_recipient', 0), 0)
        self.assertFalse(model.ready())
        model.advance(179)
        self.assertFalse(model.ready())
        model.advance(1)
        self.assertTrue(model.ready())

    def test_acceptance_ignores_sender_cooldown_and_does_not_reapply_offer(self):
        model = fixture()
        self.assertTrue(model.ready())
        self.assertGreater(model.ai_source_score(), 0)
        model.action_effect('on_sent_effect')
        self.assertTrue(model.trigger(one(model.action, 'can_be_accepted')))
        model.action_effect('complete_effect')
        self.assertIsNotNone(model.countries[1].faction)
        self.assertEqual(model.countries[1].faction, model.countries[2].faction)
        snapshot = deepcopy((model.countries, model.factions, model.native_calls))
        model.action_effect('complete_effect')
        self.assertEqual(snapshot, (model.countries, model.factions, model.native_calls))

    def test_human_control_uses_existing_rights_without_ai_restrictions(self):
        model = fixture()
        model.countries[1].ai = False
        model.countries[1].flags.add('eon_defensive_alliance_ai_offer_cooldown')
        model.countries[1].stability = 0
        model.countries[2].neighbors.clear()
        model.countries[3].wargoals.clear()
        self.assertTrue(model.ready())
        self.assertEqual(model.proposal_score(), 0)
        model.action_effect('on_sent_effect')
        model.action_effect('reject_effect')
        self.assertTrue(model.ready())


if __name__ == '__main__':
    unittest.main(verbosity=2)
