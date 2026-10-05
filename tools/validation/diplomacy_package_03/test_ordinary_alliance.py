"""Execute ordinary-alliance scripts against explicit bounded native fixtures.

Consent is a manual test transition into the actual complete/reject effect.
This does not test native callback delivery, rule composition, UI or a campaign.
"""
from collections import Counter
from copy import deepcopy
from itertools import product
import json

from _support import ROOT, Model, ast, baseline, maybe, one, source

groups = Counter()
MARKER = 'eon_defensive_alliance_member'
TEMPLATE = 'eon_defensive_alliance_template'
OUTLOOKS = ('democratic', 'communism', 'fascism', 'neutrality', 'nationalist')
RANKS = ('superpower', 'great_power', 'large_power', 'regional_power', 'minor_power', 'non_power')
PENDING_IN = 'eon_defensive_alliance_pending_sender'
PENDING_OUT = 'eon_defensive_alliance_pending_recipient'


def passed(group): groups[group] += 1


def assert_pending(model, sender=1, recipient=2):
    assert model.countries[sender].variables.get(PENDING_OUT, 0) == recipient
    assert model.countries[recipient].variables.get(PENDING_IN, 0) == sender


def assert_no_pending(model, *countries):
    for n in countries:
        assert model.countries[n].variables.get(PENDING_IN, 0) == 0
        assert model.countries[n].variables.get(PENDING_OUT, 0) == 0


def ready(model):
    return model.trigger(one(model.action, 'allowed')) and model.trigger(one(model.action, 'visible')) and model.trigger(one(model.action, 'selectable')) and model.trigger(one(model.action, 'can_be_sent'))


def send(model):
    assert ready(model)
    before = len(model.native_calls)
    model.action_effect('on_sent_effect')
    assert_pending(model)
    assert len(model.native_calls) == before, 'Proposal created/admitted without consent'
    assert all(c.faction is None and MARKER not in c.flags for c in model.countries.values())


def accept(model):
    assert model.trigger(one(model.action, 'can_be_accepted'))
    model.action_effect('complete_effect')
    leader, member = model.countries[1], model.countries[2]
    assert leader.faction is not None and member.faction == leader.faction
    assert model.factions[leader.faction]['leader'] == 1
    assert model.factions[leader.faction]['template'] == (TEMPLATE if model.ncns else None)
    assert MARKER in leader.flags and MARKER in member.flags
    assert_no_pending(model, 1, 2)
    assert not leader.ideas and not member.ideas, 'Ordinary alliance assigned an organisation spirit'
    assert model.countries[3].faction is None and model.countries[4].faction is None


def fixture(outlook='democratic', rank='non_power', **kwargs):
    model = Model(**kwargs)
    for c in model.countries.values():
        if c.exists:
            c.government = outlook
            c.ideas.add(rank)
    return model


# Five ideology defaults change; six ranks retain their own source rules/modifiers.
old_ideologies = one(ast(baseline('common/ideologies/00_ideologies.txt')), 'ideologies')
ideologies = one(source('common/ideologies/00_ideologies.txt'), 'ideologies')
ranks = one(one(source('common/ideas/zz_power_ranking.txt'), 'ideas'), 'country')
rank_thresholds = {}
for rank in RANKS:
    rank_thresholds[rank] = float(maybe(maybe(one(ranks, rank), 'modifier', []), 'join_faction_tension', '0'))
for outlook, rank in product(OUTLOOKS, RANKS):
    old = one(one(old_ideologies, outlook), 'rules')
    new = one(one(ideologies, outlook), 'rules')
    assert one(old, 'can_create_factions') == 'no'
    assert one(new, 'can_create_factions') == 'yes'
    grant = maybe(maybe(one(ranks, rank), 'rule', []), 'can_create_factions', 'no')
    assert (grant == 'yes') == (rank in ('superpower', 'great_power'))
    # The source default is supplied as an effective native rule, not recomposed by the model.
    for override in (None, True, False):
        model = fixture(outlook, rank)
        model.countries[1].rules['can_create_factions'] = override if override is not None else one(new, 'can_create_factions') == 'yes'
        assert model.gate('eon_defensive_alliance_creator_eligible', current=1) == (override is not False)
        passed('30_outlook_rank_pairs_x_3_native_overrides')
    for invalid in ('absent', 'subject', 'faction', 'offensive', 'national_no'):
        model = fixture(outlook, rank)
        c = model.countries[1]
        if invalid == 'absent': c.exists = False
        elif invalid == 'subject': c.subject = True
        elif invalid == 'faction': model.make_faction(1, 'faction_template_nato')
        elif invalid == 'offensive': c.offensive = True
        elif invalid == 'national_no': c.rules['can_create_factions'] = False
        assert not model.gate('eon_defensive_alliance_creator_eligible', current=1), invalid
        passed('creator_current_state_gates')
    for create_right, join_right in product((False, True), repeat=2):
        model = fixture(outlook, rank)
        model.countries[1].rules = {'can_create_factions': create_right, 'can_join_factions': join_right}
        assert model.gate('eon_defensive_alliance_creator_eligible', current=1) == create_right
        assert model.gate('eon_defensive_alliance_member_eligible', current=1) == join_right
        passed('create_and_join_rights_are_independent')
    threshold = rank_thresholds[rank]
    for offset in (-0.001, 0, 0.001):
        model = fixture(outlook, rank, tension=threshold + offset)
        model.countries[2].native_modifiers['join_faction_tension'] = threshold
        assert model.gate('eon_defensive_alliance_member_eligible', current=2) == (offset >= 0)
        assert model.gate('eon_defensive_alliance_creator_eligible', current=2), 'Creation incorrectly inherited a join threshold'
        passed('rank_threshold_below_equal_above')

for idea in ('CIW_member', 'European_Security_Council', 'EDU_major_non_EU_ally', 'BLR_neutrality_politic'):
    for outlook in OUTLOOKS:
        model = fixture(outlook)
        model.countries[1].ideas.add(idea)
        assert not model.gate('eon_defensive_alliance_creator_eligible', current=1)
        assert model.gate('eon_defensive_alliance_member_eligible', current=1) == (idea != 'BLR_neutrality_politic')
        passed('active_national_idea_veto_create_vs_join')

# Installed native modifier composition remains outside this model. Read actual
# intervention-law modifier values and exercise them as effective fixture inputs.
laws = one(one(source('common/ideas/AA_law_military_ideas.txt'), 'ideas'), 'Foreign_Intervention_Law')
law_thresholds = [(key, float(maybe(maybe(nodes, 'modifier', []), 'join_faction_tension')))
                  for key, op, nodes in laws if isinstance(nodes, list)
                  and maybe(maybe(nodes, 'modifier', []), 'join_faction_tension') is not None]
assert len(law_thresholds) >= 5
for law, threshold in law_thresholds:
    for offset in (-0.001, 0, 0.001):
        model = Model(tension=threshold + offset)
        model.countries[2].native_modifiers['join_faction_tension'] = threshold
        assert model.gate('eon_defensive_alliance_member_eligible') == (offset >= 0), law
        passed('preserved_law_threshold_below_equal_above')
for modifier, tension in product((-0.25, 0, 0.25, 1, 1.75), (0, 0.25, 0.5, 1)):
    model = Model(tension=tension)
    model.countries[2].native_modifiers['join_faction_tension'] = modifier
    assert model.gate('eon_defensive_alliance_member_eligible') == (tension >= modifier)
    passed('raw_effective_join_threshold_preserves_negative_and_above_one_values')

template = one(source('common/factions/templates/eon_defensive_alliance.txt'), TEMPLATE)
assert one(template, 'can_leader_join_other_factions') == 'no'
rules = source('common/factions/rules/eon_defensive_alliance_rules.txt')
joining = one(rules, 'eon_defensive_alliance_joining_rule')
calling = one(rules, 'eon_defensive_alliance_call_rule')
assert one(joining, 'type') == 'joining_rules'
assert one(calling, 'type') == 'call_to_war_rules'
for ai, rule in product((False, True), ('yes', 'no')):
    model = Model(current=1); model.countries[1].ai = ai
    model.game_rules['allow_mp_optimizations'] = rule
    assert model.trigger(one(template, 'visible')) == (not ai)
    assert model.trigger(one(template, 'available'))
    for key, op, team in source('common/factions/templates/00_multiplayer.txt'):
        assert model.trigger(one(team, 'visible')) == (not ai and rule == 'yes')
    passed('ordinary_and_team_template_visibility')

# Human sender may offer across all outlooks/ranks; recipient consent is explicit.
for sender_outlook, receiver_outlook, rank, ncns in product(OUTLOOKS, OUTLOOKS, RANKS, (False, True)):
    model = Model(ncns=ncns)
    model.countries[1].government = sender_outlook
    model.countries[2].government = receiver_outlook
    model.countries[1].ideas.add(rank)
    model.countries[2].ideas.add(rank)
    model.countries[2].native_modifiers['join_faction_tension'] = rank_thresholds[rank]
    send(model)
    # Do not let the assertion about organisation spirits confuse rank spirits.
    model.countries[1].ideas.clear(); model.countries[2].ideas.clear()
    accept(model)
    calls = [key for country, key, value in model.native_calls]
    assert calls == [('create_faction_from_template' if ncns else 'create_faction'), 'add_to_faction']
    snapshot = deepcopy((model.countries, model.factions, model.native_calls))
    model.action_effect('complete_effect')
    assert snapshot == (model.countries, model.factions, model.native_calls), 'Replay mutated completed agreement'
    passed('5_sender_x_5_recipient_x_6_ranks_x_2_dlc_consent_paths')

for sender_ai, recipient_ai in product((False, True), repeat=2):
    model = Model(); model.countries[1].ai = sender_ai; model.countries[2].ai = recipient_ai
    assert ready(model) == (not sender_ai)
    passed('human_sender_ai_recipient_policy')

# Four countries: outgoing, incoming, crossed and third-party reservations serialize.
for owner, field, peer in product((1, 2), (PENDING_IN, PENDING_OUT), (1, 2, 3, 4)):
    model = Model(); model.countries[owner].variables[field] = peer
    before = deepcopy(model.countries)
    assert not ready(model)
    model.action_effect('on_sent_effect')
    assert before == model.countries and not model.native_calls
    passed('both_roles_all_nonzero_reservations_block_send')
for kind in ('reject', 'wrong_sender', 'missing_sender_half', 'missing_recipient_half', 'different_sender_peer', 'different_recipient_peer'):
    model = Model(); send(model)
    if kind == 'wrong_sender': model.root = 3
    elif kind == 'missing_sender_half': model.countries[1].variables.pop(PENDING_OUT)
    elif kind == 'missing_recipient_half': model.countries[2].variables.pop(PENDING_IN)
    elif kind == 'different_sender_peer': model.countries[1].variables[PENDING_OUT] = 3
    elif kind == 'different_recipient_peer': model.countries[2].variables[PENDING_IN] = 3
    before = deepcopy(model.countries)
    model.action_effect('reject_effect' if kind == 'reject' else 'complete_effect')
    assert not model.native_calls and not model.factions
    for n in (1, 2, 3, 4):
        for field in (PENDING_IN, PENDING_OUT):
            old = before[n].variables.get(field, 0)
            if (field == PENDING_OUT and n == model.root and old == 2) or (field == PENDING_IN and n == 2 and old == model.root):
                assert model.countries[n].variables.get(field, 0) == 0
            else: assert model.countries[n].variables.get(field, 0) == old, 'Unrelated pending field changed'
    passed('decline_stale_mismatched_and_asymmetric_callbacks')

# Eligibility must be read again when consent returns. Status change retains the
# reservation; only that native response or annex cleanup releases its pair.
for owner, invalid in product((1, 2), ('absent', 'subject', 'faction', 'offensive', 'war', 'right', 'active_veto', 'tension')):
    if owner == 1 and invalid == 'tension': continue
    model = Model(tension=0.5); send(model)
    c = model.countries[owner]
    if invalid == 'absent': c.exists = False
    elif invalid == 'subject': c.subject = True
    elif invalid == 'faction': model.make_faction(owner, 'faction_template_csto')
    elif invalid == 'offensive': c.offensive = True
    elif invalid == 'war': c.wars.add(3-owner)
    elif invalid == 'right': c.rules['can_create_factions' if owner == 1 else 'can_join_factions'] = False
    elif invalid == 'active_veto': c.ideas.add('BLR_neutrality_politic')
    elif invalid == 'tension': c.native_modifiers['join_faction_tension'] = 0.75
    assert_pending(model)
    snapshot = deepcopy(model.factions)
    assert not model.trigger(one(model.action, 'can_be_accepted')), (owner, invalid)
    model.action_effect('complete_effect')
    assert not model.native_calls and model.factions == snapshot
    assert_no_pending(model, 1, 2)
    passed('acceptance_revalidates_current_status_and_rights')

for ncns, create_ok, admit_ok, callbacks in product((False, True), repeat=4):
    model = Model(ncns=ncns, create_success=create_ok, admission_success=admit_ok, callbacks=callbacks)
    send(model); model.action_effect('complete_effect')
    assert_no_pending(model, 1, 2)
    if create_ok and admit_ok:
        assert model.countries[1].faction == model.countries[2].faction and model.countries[1].faction is not None
        assert MARKER in model.countries[1].flags and MARKER in model.countries[2].flags
    else:
        assert not model.factions
        assert all(c.faction is None and MARKER not in c.flags for c in model.countries.values())
    if not create_ok: assert all(key != 'add_to_faction' for n, key, v in model.native_calls)
    passed('external_native_creation_admission_and_callback_outcomes')

for legacy_template, admit_ok, callbacks in product((None, 'faction_template_generic', 'faction_template_nato'), (False, True), (False, True)):
    model = Model(ncns=False, legacy_template=legacy_template, admission_success=admit_ok, callbacks=callbacks)
    send(model); model.action_effect('complete_effect')
    assert_no_pending(model, 1, 2)
    if legacy_template == 'faction_template_nato' or not admit_ok:
        assert not model.factions and all(c.faction is None and MARKER not in c.flags for c in model.countries.values())
        if legacy_template == 'faction_template_nato':
            assert not any(key == 'add_to_faction' for n, key, value in model.native_calls)
    else:
        assert model.countries[1].faction is not None and model.countries[1].faction == model.countries[2].faction
        assert model.factions[model.countries[1].faction]['template'] == legacy_template
        assert MARKER in model.countries[1].flags and MARKER in model.countries[2].flags
    passed('legacy_native_metadata_none_generic_or_incompatible_template')

for ncns, legacy_template, create_ok, admit_ok in product((False, True),
        (None, 'faction_template_generic', 'faction_template_nato'), (False, True), (False, True)):
    if ncns and legacy_template is not None: continue
    model = Model(ncns=ncns, legacy_template=legacy_template, create_success=create_ok, admission_success=admit_ok)
    model.countries[1].flags.add(MARKER)  # Factionless marker inherited from a previous scripted dismantle.
    assert ready(model)
    model.action_effect('on_sent_effect')
    assert_pending(model)
    assert MARKER in model.countries[1].flags and not model.native_calls, 'Send changed membership before consent'
    model.action_effect('complete_effect')
    succeeds = create_ok and admit_ok and (ncns or legacy_template != 'faction_template_nato')
    assert_no_pending(model, 1, 2)
    if succeeds:
        assert model.countries[1].faction is not None and model.countries[2].faction == model.countries[1].faction
        assert MARKER in model.countries[1].flags and MARKER in model.countries[2].flags
    else:
        assert not model.factions and all(c.faction is None and MARKER not in c.flags for c in model.countries.values())
    if not create_ok or (not ncns and legacy_template == 'faction_template_nato'):
        assert not any(key == 'add_to_faction' for n, key, value in model.native_calls), 'Stale leader marker permitted unprotected admission'
    passed('factionless_sender_stale_marker_requires_fresh_creation_witness')

# Guard against dismantling an unexpected third member after failed admission.
model = Model(admission_success=False); send(model)
old_make = model.make_faction
def with_third_member(leader, template=None, members=()):
    return old_make(leader, template, members=(3,))
model.make_faction = with_third_member
model.action_effect('complete_effect')
assert model.countries[1].faction is not None and model.countries[3].faction == model.countries[1].faction
assert model.countries[2].faction is None
assert not any(key == 'dismantle_faction' for n, key, value in model.native_calls)
passed('rollback_preserves_unexpected_third_member')

# Native-created template identity works before marker callbacks. Legacy creation
# is classified only after the native fixture has established the documented pair.
for ncns, partner, same_pair in product((False, True), (0, 2), (False, True)):
    model = Model(ncns=ncns, current=1)
    model.make_faction(1, TEMPLATE if ncns else None, members=(2,) if same_pair else ())
    model.callback('on_create_faction', 1, partner)
    marked = not ncns and partner == 2 and same_pair
    assert (MARKER in model.countries[1].flags) == marked
    assert (MARKER in model.countries[2].flags) == marked
    assert model.gate('eon_defensive_alliance_is_member', current=1) == (ncns or marked)
    passed('native_template_and_documented_legacy_pair_callback')
for invalid in ('subject', 'offensive', 'national_no', 'idea_veto', 'not_leader', 'missing_peer'):
    model = Model(ncns=False, current=1); faction = model.make_faction(1, None, members=(2,))
    if invalid == 'subject': model.countries[1].subject = True
    elif invalid == 'offensive': model.countries[1].offensive = True
    elif invalid == 'national_no': model.countries[1].rules['can_create_factions'] = False
    elif invalid == 'idea_veto': model.countries[1].ideas.add('CIW_member')
    elif invalid == 'not_leader': model.factions[faction]['leader'] = 2
    elif invalid == 'missing_peer': model.countries[2].exists = False
    model.callback('on_create_faction', 1, 2)
    assert all(MARKER not in c.flags for c in model.countries.values())
    passed('legacy_native_creation_guards')

old_templates = [key for path in (ROOT / 'common/factions/templates').glob('*.txt')
                 if path.name != 'eon_defensive_alliance.txt' for key, op, value in ast(path.read_bytes())]
assert len(old_templates) == 73
for old_template in old_templates:
    if old_template == 'faction_template_generic': continue
    model = Model(current=1); model.make_faction(1, old_template, members=(2,))
    model.countries[1].flags.add(MARKER); model.countries[2].flags.add(MARKER)
    assert not model.gate('eon_defensive_alliance_is_member', current=1)
    assert not model.gate('eon_defensive_alliance_is_member', current=2)
    model.effect([('eon_defensive_alliance_mark_leader_membership', '=', 'yes')])
    assert model.factions[model.countries[1].faction]['template'] == old_template
    passed('all_72_nonordinary_templates_reject_stale_markers')
    for callback_name in ('on_join_faction', 'on_offer_join_faction'):
        model.countries[2].flags.add(MARKER)
        current, from_ = (2, 1) if callback_name == 'on_join_faction' else (1, 2)
        model.callback(callback_name, current, from_)
        assert MARKER not in model.countries[2].flags, 'Nonordinary native membership retained a stale candidate marker'
        assert MARKER in model.countries[1].flags, 'Candidate cleanup modified an unrelated leader marker'
        passed('all_72_nonordinary_join_offer_callbacks_clear_only_candidate_stale_marker')
model = Model(current=1); model.make_faction(1, 'faction_template_generic', members=(2,))
assert not model.gate('eon_defensive_alliance_is_member', current=2)
model.countries[1].flags.add(MARKER)
assert model.gate('eon_defensive_alliance_is_member', current=2)
passed('generic_fallback_identity_requires_leader_marker')
model = Model(); model.make_faction(1, None, members=(2,)); model.countries[2].flags.add(MARKER)
assert not model.gate('eon_defensive_alliance_is_member', current=2), 'Own stale marker established an unmarked leader'
model.countries[1].flags.add(MARKER)
assert model.gate('eon_defensive_alliance_is_member', current=2)
model.countries[3].flags.add(MARKER)
assert not model.gate('eon_defensive_alliance_is_member', current=3), 'Factionless stale marker established membership'
passed('identity_requires_actual_leader_or_template')

for ncns, callback_name in product((False, True), ('on_join_faction', 'on_offer_join_faction')):
    model = Model(ncns=ncns); model.make_faction(1, TEMPLATE if ncns else None, members=(2,))
    model.countries[1].flags.add(MARKER)
    current, from_ = (2, 1) if callback_name == 'on_join_faction' else (1, 2)
    model.callback(callback_name, current, from_)
    assert MARKER in model.countries[2].flags
    model.countries[2].flags.discard(MARKER); model.countries[2].faction = None
    model.callback(callback_name, current, from_)
    assert MARKER not in model.countries[2].flags, 'Unjoined invitee marked before actual membership'
    passed('join_offer_callbacks_require_actual_same_faction')
for ncns, old_leader_same, old_marker in product((False, True), repeat=3):
    model = Model(ncns=ncns); faction = model.make_faction(1, TEMPLATE if ncns else None, members=(2, 3))
    model.factions[faction]['leader'] = 2
    if old_marker: model.countries[1].flags.add(MARKER)
    if not old_leader_same: model.countries[1].faction = None
    model.callback('on_assume_faction_leadership', 2, 1)
    eligible = ncns or (old_leader_same and old_marker)
    assert (MARKER in model.countries[2].flags) == eligible
    assert (MARKER in model.countries[3].flags) == eligible
    passed('successor_leader_preserves_actual_ordinary_faction')
for ncns in (False, True):
    model = Model(ncns=ncns); send(model); accept(model)
    model.countries[2].faction = None
    model.callback('on_leave_faction', 2, 1)
    assert MARKER not in model.countries[2].flags and MARKER in model.countries[1].flags
    assert not model.gate('eon_defensive_alliance_is_member', current=2)
    passed('leave_clears_own_marker_only')

for annexed, callback_name in product((1, 2), ('on_annex', 'on_subject_annexed')):
    model = Model(); send(model)
    model.countries[3].variables[PENDING_OUT] = 4; model.countries[4].variables[PENDING_IN] = 3
    model.countries[annexed].flags.add(MARKER)
    if callback_name == 'on_annex': model.callback(callback_name, 4, annexed)
    else: model.callback(callback_name, annexed, 4)
    assert_no_pending(model, 1, 2)
    assert MARKER not in model.countries[annexed].flags
    assert model.countries[3].variables[PENDING_OUT] == 4 and model.countries[4].variables[PENDING_IN] == 3
    passed('actual_annex_callback_releases_only_annexed_pair')
model = Model(); send(model); accept(model)
model.callback('on_annex', 4, 1)
assert MARKER not in model.countries[1].flags and MARKER in model.countries[2].flags
model.countries[1].faction = None; model.factions[model.countries[2].faction]['leader'] = 2
assert model.gate('eon_defensive_alliance_is_member', current=2)
passed('annex_survivor_marker_keeps_actual_successor_identity')

# Current caller for CALL, FROM's war for JOIN_ALLY; differing war fixtures detect
# a scope inversion. Mixed wars are deliberately denied without a selected-WAR scope.
for ncns, caller, defensive, offensive, peer_defensive, peer_offensive in product(
        (False, True), (1, 2), (False, True), (False, True), (False, True), (False, True)):
    model = Model(ncns=ncns, current=caller, from_=3-caller)
    model.make_faction(1, TEMPLATE if ncns else None, members=(2,)); model.countries[1].flags.add(MARKER)
    c, peer = model.countries[caller], model.countries[3-caller]
    c.defensive, c.offensive = defensive, offensive
    peer.defensive, peer.offensive = peer_defensive, peer_offensive
    assert model.gate('eon_defensive_alliance_war_eligible') == (defensive and not offensive)
    assert model.trigger(one(calling, 'trigger')) == (defensive and not offensive)
    assert model.gate('DIPLOMACY_CALL_ALLY_ENABLE_TRIGGER') == (defensive and not offensive)
    assert model.gate('DIPLOMACY_JOIN_ALLY_ENABLE_TRIGGER') == (peer_defensive and not peer_offensive)
    assert not model.trigger(one(calling, 'can_remove'))
    passed('ordinary_defensive_call_and_join_war_scope_matrix')
for offensive in (False, True):
    model = Model(current=1, from_=2); model.countries[1].offensive = offensive
    assert model.gate('DIPLOMACY_CALL_ALLY_ENABLE_TRIGGER')
    assert model.gate('DIPLOMACY_JOIN_ALLY_ENABLE_TRIGGER')
    passed('nonordinary_native_call_paths_unchanged')

for ncns, candidate_invalid, leader_invalid in product((False, True),
        ('none', 'subject', 'faction', 'join_no', 'offensive', 'tension', 'blr'), ('none', 'subject', 'offensive')):
    model = Model(ncns=ncns, current=2, from_=1, tension=0.5)
    model.make_faction(1, TEMPLATE if ncns else None); model.countries[1].flags.add(MARKER)
    candidate, leader = model.countries[2], model.countries[1]
    candidate.rules['can_create_factions'] = False  # Create-only prohibition must not deny native joining.
    if candidate_invalid == 'subject': candidate.subject = True
    elif candidate_invalid == 'faction': model.make_faction(2, 'faction_template_csto')
    elif candidate_invalid == 'join_no': candidate.rules['can_join_factions'] = False
    elif candidate_invalid == 'offensive': candidate.offensive = True
    elif candidate_invalid == 'tension': candidate.native_modifiers['join_faction_tension'] = 0.75
    elif candidate_invalid == 'blr': candidate.ideas.add('BLR_neutrality_politic')
    if leader_invalid == 'subject': leader.subject = True
    elif leader_invalid == 'offensive': leader.offensive = True
    expected = candidate_invalid == leader_invalid == 'none'
    assert model.gate('DIPLOMACY_JOIN_FACTION_ENABLE_TRIGGER') == expected
    assert model.gate('DIPLOMACY_OFFER_JOIN_FACTION_ENABLE_TRIGGER', current=1, from_=2) == expected
    assert model.trigger(one(joining, 'trigger')) == (candidate_invalid == 'none')
    assert not model.trigger(one(joining, 'can_remove'))
    passed('native_join_request_and_invitation_share_current_candidate_policy')

# Actual inherited JOIN and OFFER predicates remain effective for scripted
# formation. Supply branch-specific country/continent/party/SCO native fixtures.
policy_cases = [
    ('NATO_member', {}, {}, False),
    ('faction_resistance_axis_member', {}, {}, False),
    ('faction_resistance_axis_member', {}, {'ideas': {'shia'}}, True),
    ('SOV_warsaw_pact_idea', {'original_tag': 'SOV'}, {'original_tag': 'UKR'}, False),
    ('SOV_warsaw_pact_idea', {'original_tag': 'SOV'}, {'original_tag': 'SOV'}, True),
    (None, {'original_tag': 'UKR'}, {'ideas': {'SOV_warsaw_pact_idea'}, 'original_tag': 'SOV'}, False),
    (None, {'original_tag': 'SOV'}, {'ideas': {'SOV_warsaw_pact_idea'}, 'original_tag': 'SOV'}, True),
    ('S0V_russian_sphere_idea', {}, {'government': 'democratic'}, False),
    ('S0V_russian_sphere_idea', {}, {'government': 'nationalist'}, True),
    ('faction_fifth_international_member', {}, {'arrays': {'ruling_party': [0]}}, False),
    ('faction_fifth_international_member', {}, {'arrays': {'ruling_party': [4]}}, True),
    ('faction_fifth_international_member', {}, {'arrays': {'ruling_party': [19]}}, True),
    ('idea_gcc_member_state', {}, {}, False),
    ('idea_gcc_member_state', {}, {'ideas': {'idea_gcc_member_state'}}, True),
    ('faction_british_commonwealth', {}, {}, False),
    ('faction_british_commonwealth', {}, {'ideas': {'commonwealth_of_nations_member'}}, True),
    ('faction_monroe_alliance', {}, {'continent': 'europe'}, False),
    ('faction_monroe_alliance', {}, {'continent': 'south_america'}, True),
    ('faction_cento_alliance', {}, {'continent': 'europe'}, False),
    ('faction_cento_alliance', {}, {'continent': 'asia'}, False),
    ('faction_imperial_bloc_alliance', {}, {'continent': 'asia'}, False),
    ('faction_imperial_bloc_alliance', {}, {'continent': 'europe'}, False),
    ('faction_brics_alliance', {}, {'continent': 'africa'}, False),
    ('faction_brics_alliance', {}, {'continent': 'australia'}, False),
    ('faction_mto_alliance', {}, {'continent': 'europe'}, False),
    ('faction_mto_alliance', {}, {'continent': 'africa'}, False),
    ('faction_taj_alliance', {}, {'continent': 'europe'}, False),
    ('faction_taj_alliance', {}, {'continent': 'asia'}, False),
    ('faction_fao_alliance', {}, {}, False),
    ('faction_fao_alliance', {}, {'ideas': {'shia'}}, True),
    ('faction_chinese_united_front', {}, {'original_tag': 'UKR'}, False),
    ('faction_chinese_united_front', {}, {'original_tag': 'TAI'}, True),
    (None, {'original_tag': 'CHI', 'is_sco': True}, {'is_sco': False}, False),
    (None, {'original_tag': 'CHI', 'is_sco': True}, {'is_sco': True}, True),
]
for creator_idea, creator_fields, candidate_fields, expected in policy_cases:
    model = Model()
    if creator_idea: model.countries[1].ideas.add(creator_idea)
    for owner, fields in ((1, creator_fields), (2, candidate_fields)):
        for key, value in fields.items(): setattr(model.countries[owner], key, value)
    assert model.gate('eon_defensive_alliance_offer_existing_policy') == expected, (creator_idea, creator_fields, candidate_fields)
    assert ready(model) == expected
    passed('existing_story_policy_actual_branch_fixtures')

# Several inherited OFFER lists lack OR. The adapter preserves these restrictive
# conjunctions even though the corresponding native JOIN geography allows entry.
# This witnesses a baseline policy limitation, not permission to rewrite it here.
for idea, continent in (('faction_cento_alliance', 'asia'), ('faction_imperial_bloc_alliance', 'europe'),
                        ('faction_brics_alliance', 'australia'), ('faction_mto_alliance', 'africa'),
                        ('faction_taj_alliance', 'asia')):
    model = Model(current=2, from_=1)
    model.countries[1].ideas.add(idea); model.countries[2].continent = continent
    model.make_faction(1, TEMPLATE)
    assert model.gate('DIPLOMACY_JOIN_FACTION_ENABLE_TRIGGER')
    assert not model.gate('DIPLOMACY_OFFER_JOIN_FACTION_ENABLE_TRIGGER', current=1, from_=2)
    passed('inherited_story_join_offer_conjunction_asymmetry_preserved')

swiss = one(one(source('common/ideas/Swiss_ideas.txt'), 'ideas'), 'country')
swiss_modifier = float(one(one(one(swiss, 'SWI_swiss_neutrality'), 'modifier'), 'ai_get_ally_desire_factor'))
generic = one(one(source('common/ideas/Generic_ideas.txt'), 'ideas'), 'country')
neutral_modifier = float(one(one(one(one(generic, 'neutrality_idea'), 'modifier'), 'hidden_modifier'), 'ai_get_ally_desire_factor'))
assert swiss_modifier == -1000 and neutral_modifier == -50
for same_outlook, opinion, native_policy in product((False, True), (0, 50, 51, 100, 101, 200), (0, swiss_modifier, neutral_modifier)):
    model = Model(); model.countries[2].ai = True
    model.countries[2].government = 'democratic' if same_outlook else 'nationalist'
    model.countries[2].opinions[1] = opinion
    model.countries[2].native_modifiers['ai_get_ally_desire_factor'] = native_policy
    expected = -50 + (25 if opinion > 50 else 0) + (30 if opinion > 100 else 0) + (10 if same_outlook else 0) + native_policy
    assert model.ai_source_score() == expected
    if native_policy < 0: assert model.ai_source_score() < 0
    assert ready(model), 'Native AI assessment changed human send rights'
    passed('actual_ai_reason_opinion_outlook_and_preserved_neutrality_modifiers')

for kind in ('unsupported_trigger', 'unsupported_effect', 'dotted_prev'):
    model = Model()
    if kind == 'dotted_prev':
        model.countries[1].variables['probe'] = 73
        assert model.value('PREV.PREV.probe', [1, 3, 2]) == 73
    else:
        try:
            (model.trigger if kind == 'unsupported_trigger' else model.effect)([('unmodeled_probe', '=', 'yes')])
        except AssertionError: pass
        else: raise AssertionError('Unknown visited source silently passed')
    passed('interpreter_fail_closed_and_ancestry_probes')

print(json.dumps({'all_passed': True, 'cases_passed': sum(groups.values()), 'total_cases': sum(groups.values()),
                  'groups': groups, 'method': 'actual ordered source AST with explicit native inputs/outcomes',
                  'not_proven': ['HOI4 parsing/UI/campaign', 'native rule and modifier composition',
                                 'native callback delivery/order', 'single-founder legacy callback coverage',
                                 'selected-war identity', 'duplicate older same-pair response versus a newer same-pair offer']}, indent=2))
