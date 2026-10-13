"""Read production POTEF callbacks with explicit legacy-calculation receipts.

These are access-boundary regressions, not a simulation of a federation election.
The sovereign USoE path remains a separate state-authority context.
"""
from pathlib import Path
import importlib.util
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "eon_eu_federation_access_model",
    ROOT / "tools/validation/eu_lifecycle/test_legacy_access_boundaries.py",
)
SUPPORT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SUPPORT
SPEC.loader.exec_module(SUPPORT)
one, read, descend = SUPPORT.one, SUPPORT.read, SUPPORT.descend


def mission(ident):
    data = read("common/decisions/EU_POTEF_decisions.txt")
    values = [v for k, op, body in data for name, op, v in body if name == ident]
    assert len(values) == 1, ident
    return values[0]


class FederationModel(SUPPORT.BoundaryModel):
    BOUNDARIES = SUPPORT.BoundaryModel.BOUNDARIES | {
        "POTEF_election", "set_POTEF_elect", "election_POTEF_in_member_state",
        "add_relative_party_popularity",
    }

    def owner(self, token, stack):
        if token == "EUU":
            return self.nations[5]
        return super().owner(token, stack)

    def effect(self, nodes, stack):
        # Native every_possible_country includes the nonexisting utility scope.
        # The inherited every_country intentionally includes only existing states.
        while any(k == "every_possible_country" for k, op, v in nodes):
            index = next(i for i, n in enumerate(nodes) if n[0] == "every_possible_country")
            super().effect(nodes[:index], stack)
            body = nodes[index][2]
            limit = next((v for k, op, v in body if k == "limit"), [])
            for nation in self.nations.values():
                if self.trigger(limit, stack + [nation]):
                    self.effect([n for n in body if n[0] != "limit"], stack + [nation])
            nodes = nodes[index + 1:]
        return super().effect(nodes, stack)


def model():
    m = FederationModel()
    m.nations[5] = SUPPORT.SUPPORT.Nation(5, original_tag="EUU", exists=False, owned=0)
    m.members()
    m.global_owner.flags.update({"eon_eu_admission_guard_ready", "european_federation"})
    for ident in (1, 2):
        m.nations[ident].flags.add("eon_eu_membership_recognized")
    m.global_owner.variables["eupresfederation"] = 1
    m.receipts.clear()
    return m


def execute(m, ident, who, section="timeout_effect"):
    m.sender = who
    m.temp = {}
    m.effect(one(mission(ident), section), [m.nations[who]])


class FederationAuthority(unittest.TestCase):
    def test_queued_campaign_cannot_execute_after_union_archive(self):
        m = model()
        m.global_owner.flags.discard("european_federation")
        m.global_owner.flags.add("eon_eu_dormant")
        m.global_owner.variables["EU_member_count"] = 0
        execute(m, "EU_POTEF_election_campaign", 5)
        self.assertFalse(m.receipts, "Archived utility scope executed a federation election")

    def test_former_member_campaign_cannot_execute_while_another_union_is_active(self):
        m = model()
        m.global_owner.flags.add("ongoing_potef_election")
        execute(m, "EU_POTEF_election_campaign", 3)
        self.assertFalse(m.receipts)

    def test_disabled_union_cannot_execute_a_saved_campaign(self):
        m = model()
        m.global_owner.flags.update({"ongoing_potef_election", "GAME_RULE_eu_disabled"})
        execute(m, "EU_POTEF_election_campaign", 1)
        self.assertFalse(m.receipts)

    def test_current_member_campaign_still_executes_its_legacy_election(self):
        m = model()
        m.global_owner.flags.add("ongoing_potef_election")
        execute(m, "EU_POTEF_election_campaign", 1)
        self.assertIn(("POTEF_election", 1), m.receipts)
        self.assertIn(("set_POTEF_elect", 1), m.receipts)

    def test_nonexisting_utility_campaign_can_coordinate_an_active_federation(self):
        m = model()
        m.global_owner.flags.add("ongoing_potef_election")
        execute(m, "EU_POTEF_election_campaign", 5)
        self.assertIn(("POTEF_election", 5), m.receipts)
        self.assertIn(("set_POTEF_elect", 5), m.receipts)

    def test_current_term_expiry_opens_a_real_current_campaign(self):
        m = model()
        m.nations[1].ideas.add("EU_president")
        execute(m, "EU_POTEF_term", 1)
        self.assertIn("EU_POTEF_election_campaign", m.nations[1].missions)
        self.assertIn("ongoing_potef_election", m.global_owner.flags)

    def test_lost_presidential_office_cannot_open_a_campaign(self):
        m = model()
        execute(m, "EU_POTEF_term", 1)
        self.assertNotIn("EU_POTEF_election_campaign", m.nations[1].missions)

    def test_stale_presidential_pointer_cannot_open_a_campaign(self):
        m = model()
        m.nations[1].ideas.add("EU_president")
        m.global_owner.variables["eupresfederation"] = 5
        execute(m, "EU_POTEF_term", 1)
        self.assertNotIn("EU_POTEF_election_campaign", m.nations[1].missions)

    def test_archive_cleanup_includes_the_utility_and_nonexisting_old_holder(self):
        m = model()
        self.assertTrue("eon_eu_close_federation_authority" in m.effects,
                        "No all-country federation archive cleanup exists")
        for nation in m.nations.values():
            nation.missions.update({"EU_POTEF_election_campaign", "EU_POTEF_term"})
            nation.ideas.add("EU_president")
        m.global_owner.flags.add("ongoing_potef_election")
        m.call("eon_eu_close_federation_authority", 1)
        self.assertNotIn("ongoing_potef_election", m.global_owner.flags)
        self.assertEqual(m.global_owner.variables["eupresfederation"], 5)
        for nation in m.nations.values():
            self.assertFalse(nation.missions.intersection({"EU_POTEF_election_campaign", "EU_POTEF_term"}))
            self.assertNotIn("EU_president", nation.ideas)


class OutsiderSanctionAuthority(unittest.TestCase):
    def target(self):
        m = model()
        m.nations[3].flags.add("EU_POTEF_environmental_imperialism_target")
        m.nations[3].variables["eon_eu_potef_environmental_issuer"] = 1
        m.nations[1].ideas.add("EU_president")
        m.nations[1].flags.add("environmental_imperialism")
        return m

    def test_current_issuer_can_complete_a_mission_in_an_outsider(self):
        m = self.target()
        execute(m, "EU_POTEF_environmental_imperialism_mission", 3)
        self.assertNotIn("EU_member", m.nations[3].ideas)
        self.assertIn("USoE_environmental_sanctions", m.nations[3].ideas)
        self.assertTrue(any(r[:3] == ("event", 1, "USoEevent.6") for r in m.receipts))

    def test_archived_union_cannot_impose_a_queued_outsider_sanction(self):
        m = self.target()
        m.global_owner.flags.discard("european_federation")
        m.global_owner.flags.add("eon_eu_dormant")
        m.global_owner.variables["EU_member_count"] = 0
        execute(m, "EU_POTEF_environmental_imperialism_mission", 3)
        self.assertNotIn("USoE_environmental_sanctions", m.nations[3].ideas)
        self.assertFalse(m.receipts)

    def test_utility_sentinel_is_not_a_sanction_issuer(self):
        m = self.target()
        m.global_owner.variables["eupresfederation"] = 5
        execute(m, "EU_POTEF_environmental_imperialism_mission", 3)
        self.assertNotIn("USoE_environmental_sanctions", m.nations[3].ideas)
        self.assertFalse(m.receipts)

    def test_departed_issuer_cannot_use_a_replacement_presidents_pointer(self):
        m = self.target()
        m.nations[3].variables["eon_eu_potef_environmental_issuer"] = 4.02446
        execute(m, "EU_POTEF_environmental_imperialism_mission", 3)
        self.assertNotIn("USoE_environmental_sanctions", m.nations[3].ideas)
        self.assertFalse(m.receipts)

    def test_cancelled_target_receipt_cannot_execute_after_refounding(self):
        m = self.target()
        m.nations[3].flags.discard("EU_POTEF_environmental_imperialism_target")
        execute(m, "EU_POTEF_environmental_imperialism_mission", 3)
        self.assertNotIn("USoE_environmental_sanctions", m.nations[3].ideas)
        self.assertFalse(m.receipts)


if __name__ == "__main__":
    unittest.main(verbosity=2)
