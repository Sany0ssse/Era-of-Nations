"""Build an isolated EU lifecycle fixture; never install it or launch HOI4.

The fixture calls production helpers. Seeded membership, deadlines, populations
and national delegations are test boundaries, not copied implementations.
"""
from pathlib import Path
import argparse
import hashlib
import inspect
import re
import json
import stat
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/validation/diplomacy_package_02'))
from _treaty_support import ast
from faction_identity_diagnostic import build_diagnostic
from extension_support import build_extension
from edu_support import build_edu
from council_support import core_valid_round_setup

def default_additive_builders():
    """Actual acceptance composition; missing public modules fail closed."""
    from council_support import build_council
    from parliament_support import build_parliament
    return {'council': build_council, 'parliament': build_parliament}

ADDITIVE_RANGES = {'council': (7000, 7199), 'parliament': (7200, 7399)}
EDU_TRACE_LABELS = ('CREATE_DECISION', 'FORMED_HOOK', 'FORMED_COMMIT', 'LEAVE_HOOK', 'LEADERSHIP_HOOK',
                    'DISSOLVE_FAILED', 'DEPART_TRANSFER_FAILED', 'DEPART_FAILED', 'LEGACY_TEMPLATE_ADOPT')
EDU_TRACE_LABELS_V17 = ('CREATE_DECISION','CTOR_BEFORE','CTOR_RETURN','FORMED_COMMIT',
                      'CONFIRM_COMMIT','CONFIRM_COMMIT','FORMED_HOOK','LATE_FORMED_ACK',
                      'LEAVE_HOOK','LEADERSHIP_HOOK','DISSOLVE_FAILED','DEPART_TRANSFER_FAILED',
                      'DEPART_FAILED','LEGACY_TEMPLATE_ADOPT')

def verified_builder_inputs(additional_module_builders, extension_builder=build_extension, edu_builder=build_edu):
    """Pin the actual public implementations used by this composition."""
    builders = {'extension': extension_builder, 'edu': edu_builder,
                'diagnostic': build_diagnostic, 'source_ast': ast,
                'core_council': core_valid_round_setup, **additional_module_builders}
    if extension_builder is not build_extension:
        from runtime_override_support import validate_override_bytes
        builders['runtime_override'] = validate_override_bytes
        builders['extension_base'] = build_extension
    if edu_builder is not build_edu:
        from runtime_support import build_runtime
        builders['extension_v15_base'] = build_runtime
        builders['edu_base'] = build_edu
        from edu_runtime_support import build_edu_runtime
        builders['edu_v16_base'] = build_edu_runtime
    inputs = {}
    for name, builder in builders.items():
        path = Path(inspect.getsourcefile(builder) or '').resolve()
        assert path.is_file(), 'Builder needs a real hash-bound source file: ' + name
        inputs[name] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    inputs['builder'] = {'path': str(Path(__file__).resolve()), 'sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    return inputs


def verify_edu_trace_source(source, fixture_version=14):
    relative = 'common/scripted_effects/eon_edu_effects.txt'
    path = source / relative
    text = path.read_text('utf-8-sig')
    actual = tuple(re.findall(r'log\s*=\s*"EON_EDU ([A-Z_]+)', text))
    assert actual in (EDU_TRACE_LABELS,EDU_TRACE_LABELS_V17), 'Require all actual plain EON_EDU witnesses in the exact reviewed source catalog'
    if fixture_version>=17:
        assert actual==EDU_TRACE_LABELS_V17,'V17 requires actual constructor/confirmation source witnesses'
    assert '[EON EDU]' not in text, 'Old bracket-localization trace must not be accepted as native evidence'
    return {'path': relative, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'prefix': 'EON_EDU', 'labels': list(actual if fixture_version>=17 else EDU_TRACE_LABELS),
            'actual_labels':list(actual),
            'historical_catalog_compatibility':fixture_version<17 and actual==EDU_TRACE_LABELS_V17}

NS = 'eon_native_eu_probe'
MARK_V14 = 'EON_EU_NATIVE_V14'
MARK_V15 = 'EON_EU_NATIVE_V15'
MARK = 'EON_EU_NATIVE_V18'
P = NS + '_'
CONTROLLED_COORDINATOR_HOLD_DAYS = 180
DOCS = Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation')
# Frozen v12 golden contract: all144 ordered labels, predicates and explanations.
BASELINE_V12_SHA256 = '0a8c1fd1f2c8704b9a81573b7151cb2dd00265607c5711ef31ef20b858113602'
ADMISSION_BOUNDARY_ASSERTIONS = ('actual_original_startup_has_fifteen_recognized_members_once', 'unapproved_european_grant_cannot_admit_poland', 'recognized_member_callback_replay_preserves_membership', 'eight_stale_outsider_budget_callbacks_are_inert', 'active_federation_allows_territoryless_utility_organizer', 'stale_federation_campaign_callback_cannot_appoint_president', 'outsider_environmental_mission_has_actual_current_issuer', 'current_issuer_environmental_timeout_applies_actual_sanction', 'lost_issuer_environmental_callback_cancels_without_sanction', 'current_president_term_callback_starts_real_campaign', 'federation_cleanup_closes_president_and_pending_authority', 'rejected_raw_grant_preserves_real_application', 'final_article49_consumes_single_use_admission_authority', 'post_exit_raw_reward_cannot_restore_membership', 'cold_prior_save_first_daily_closes_guard_under_old_lock', 'cold_prior_save_later_raw_reward_is_rejected')

MEMBERS = ('GER', 'FRA', 'ITA', 'HOL', 'SPR', 'CZE')
COUNTRIES = ('NEP', *MEMBERS, 'POL')
ROLES = ('EU_commission_president', 'EU_parliament_president', 'ECB_president',
         'EU_council_president', 'EU_foreign_minister', 'frontex_ExDir',
         'EU_finance_minister', 'EUU_euroarmy_sc', 'EUU_euronavy_sc', 'EUU_ambassador_unsc')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cv(name, value, compare='equals'):
    return f'check_variable = {{ var = {name} value = {value} compare = {compare} }} '


def setv(name, value):
    return f'set_variable = {{ {name} = {value} }} '


def g(name):
    return 'global.' + P + name


def scope(tag, body):
    return f'{tag} = {{ {body} }} '


def flag(name, yes=True):
    return ('' if yes else 'NOT = { ') + f'has_country_flag = {name} ' + ('' if yes else '} ')


def contains(array, value='THIS', yes=True):
    return ('' if yes else 'NOT = { ') + f'is_in_array = {{ array = {array} value = {value} }} ' + ('' if yes else '} ')


def render_source_ast(nodes):
    """Serialize extracted production AST, never a hand-written callback copy."""
    def render_value(value):
        if isinstance(value, list):
            return '{ ' + render_source_ast(value) + ' }'
        return json.dumps(value, ensure_ascii=False) if any(ch.isspace() for ch in value) or '"' in value else value
    return ' '.join(render_value(value) if key == '__item__' else
                    f'{key} {op} {render_value(value)}' for key, op, value in nodes)


def production_callback(source, relative, ident, phase):
    definitions = ast((source / relative).read_text(encoding='utf-8-sig'))
    matches = [value for _, _, category in definitions if isinstance(category, list)
               for key, _, value in category if key == ident]
    assert len(matches) == 1, (relative, ident, len(matches))
    callbacks = [value for key, _, value in matches[0] if key == phase]
    assert len(callbacks) == 1, (relative, ident, phase, len(callbacks))
    text = render_source_ast(callbacks[0])
    assert ast(text) == callbacks[0], 'Production callback extraction must preserve AST exactly'
    return text + ' '


def build_world_scheduler(namespace, marker, *, terminal_effect=''):
    """One real on_daily EP vacancy/AI/14-day completion trace.

    Setup establishes lawful existing members and a declared Commission origin.
    After unlocking, no production helper or deadline clear runs in the fixture.
    """
    prefix = 'global.' + namespace + '_world_'
    observations, assertions, expectations, events = [], [], {}, {}
    def check(label, predicate, expected):
        label = 'world_scheduler_' + label
        assertions.append(label)
        expectations[label] = {'predicate': predicate, 'expected': expected}
        return (f'log = "{marker} BEGIN {label}" if = {{ limit = {{ {predicate} }} '
                f'log = "{marker} PASS {label}" add_to_variable = {{ global.{namespace}_passes = 1 }} }} '
                f'else = {{ log = "{marker} FAIL {label}" add_to_variable = {{ global.{namespace}_fails = 1 }} }} '
                f'log = "{marker} END {label}" ')
    def obs(label):
        label = 'WORLD_SCHEDULER_' + label
        observations.append(label)
        return (f'log = "{marker} OBS {label} date=[?global.date] days=[?{prefix}daily_callbacks] '
                'office=[?global.eon_eu_office_id] phase=[?global.eon_eu_office_phase] '
                'ep_yes=[?global.eon_eu_office_ep_yes] ep_total=[?global.eon_eu_office_ep_total]" ')
    def event(number, body):
        events[number] = f'country_event = {{ id = {namespace}.{number} hidden = yes is_triggered_only = yes immediate = {{ {body} }} }}\n'
    def schedule(number, hours):
        return f'NEP = {{ country_event = {{ id = {namespace}.{number} hours = {hours} }} }} '
    # EDU controls leave one lawful Austrian member. Establish six declared
    # lawful inputs before this independent world scheduler control; no guard
    # bypass or post-unlock manual coordinator is permitted.
    body = 'set_global_flag = eon_eu_registry_refreshing '
    body += 'every_country = { set_country_flag = eon_eu_leaving_in_progress remove_ideas = EU_member clr_country_flag = eon_eu_leaving_in_progress eon_eu_clear_country_access = yes } '
    body += 'clr_global_flag = eon_eu_dormant clr_global_flag = GAME_RULE_eu_disabled clr_global_flag = usoe_formed '
    for tag in MEMBERS:
        body += scope(tag, 'eon_eu_clear_country_access = yes set_country_flag = eon_eu_admission_commit add_ideas = EU_member remove_ideas = EUU_voting_rights_suspended ')
    body += 'clr_global_flag = eon_eu_registry_refreshing eon_eu_refresh_membership = yes '
    body += 'eon_eu_clear_office_ballot = yes eon_eu_initialize_historical_offices = yes '
    body += 'every_country = { remove_ideas = EU_commission_president remove_ideas = EU_parliament_president } '
    body += 'GER = { eon_eu_appoint_office_1 = yes } eon_eu_reconcile_office_holders = yes '
    body += 'for_each_scope_loop = { array = global.EU_member if = { limit = { eon_eu_is_active_member = yes } '
    body += 'clr_country_flag = eon_eu_office_nomination_cooldown set_variable = { eurosceptic = 0 } '
    body += 'every_other_country = { limit = { eon_eu_is_active_member = yes } add_opinion_modifier = { target = PREV modifier = EU_member_opinion } } } } '
    body += 'clr_global_flag = eon_eu_office_appointment_cooldown '
    body += check('prepared_live_commission_and_ep_vacancy',
                  'eon_eu_union_active = yes GER = { eon_eu_is_active_member = yes has_idea = EU_commission_president } '
                  'NOT = { any_country = { has_idea = EU_parliament_president } } ' +
                  cv('global.eon_eu_office_id', 0) + 'has_global_flag = eon_eu_institutions_initialized ',
                  'Declared Commission-origin input is assigned by actual production appoint helper; only Parliament chair is the first vacant institution, with an active recognized registry')
    body += setv(prefix + 'daily_callbacks', 0) + setv(prefix + 'unlocked_date', 'global.date')
    body += 'set_global_flag = ' + namespace + '_world_scheduler_trace clr_global_flag = eon_eu_daily_lifecycle_done '
    body += obs('UNLOCKED') + schedule(6001, 49)
    event(6000, body)
    body = obs('OPEN_CHECKPOINT')
    body += check('actual_on_daily_opens_ep_ballot',
                  cv(prefix + 'daily_callbacks', 2, 'greater_than_or_equals') +
                  cv('global.eon_eu_office_id', 2) + cv('global.eon_eu_office_phase', 1) +
                  'has_global_flag = eon_eu_office_ballot_deadline '
                  'var:global.eon_eu_office_nominee = { is_ai = yes eon_eu_is_active_member = yes } '
                  'NOT = { any_country = { has_idea = EU_parliament_president } } ',
                  'After at least48 actual game hours, real on_daily production scheduling opened the EP election; fixture made no manual daily/helper/vote/deadline calls after unlock')
    body += setv(prefix + 'opened_date', 'global.date') + schedule(6002, 385)
    event(6001, body)
    body = obs('COMPLETED_CHECKPOINT') + setv(prefix + 'ep_holders', 0)
    body += 'every_country = { limit = { eon_eu_is_active_member = yes has_idea = EU_parliament_president } add_to_variable = { ' + prefix + 'ep_holders = 1 } } '
    body += check('natural_fourteen_day_window_ai_fills_one_ep_chair',
                  cv(prefix + 'daily_callbacks', 16, 'greater_than_or_equals') + cv(prefix + 'ep_holders', 1) +
                  'NOT = { ' + cv('global.eon_eu_office_id', 2) + ' } '
                  'var:global.euparliamentpresident = { eon_eu_is_active_member = yes is_ai = yes has_idea = EU_parliament_president } ',
                  'After16 more actual game days, natural14-day EP ballot and real daily AI appoint exactly one current chair; another legitimate institution ballot is permitted and this does not prove all offices or long campaigns')
    body += 'clr_global_flag = ' + namespace + '_world_scheduler_trace ' + terminal_effect
    event(6002, body)
    return {'fixture_text': {f'events/{namespace}.txt': 'add_namespace = ' + namespace + '\n' + ''.join(events.values())},
            'entry_event_id': f'{namespace}.6000', 'terminal_event_id': f'{namespace}.6002',
            'entry_effect': schedule(6000, 2), 'events': len(events),
            'assertions': assertions, 'expectations': expectations, 'observations': observations,
            'required_elapsed_game_time': [
                {'start_observation': observations[0], 'end_observation': observations[1], 'minimum_hours': 48},
                {'start_observation': observations[1], 'end_observation': observations[2], 'minimum_hours': 384}],
            'on_daily_effect': 'if = { limit = { has_global_flag = ' + namespace + '_world_scheduler_trace } add_to_variable = { ' + prefix + 'daily_callbacks = 1 } } ',
            'limits': ['One actual on_daily EP vacancy election with natural14-day deadline; fixture requests49/385 hours and analyzer requires48/384 actual hours. Only pre-unlock setup uses production helpers or clears pauses; no post-unlock manual source helper, vote or deadline expiry. This is one office trace, not a2035campaign or multiplayer proof.']}


def validate_output_paths(source, output, authoritative_template=False):
    """Keep normal frozen-source safety and narrowly allow private root templates.

    The opt-in creates fixtures only below the authoritative checkout's .local,
    never common/events/history. Existing symlinks or Windows junctions anywhere
    in the private route are rejected, including links pointing back inside it.
    """
    raw_output = output.absolute()
    source, output = source.resolve(), output.resolve()
    assert source.is_dir(), 'Require an existing frozen production source'
    assert not output.exists(), 'Preserve previous native receipts'
    assert '.local' in output.parts, 'Fixture output must remain private under .local'
    if not authoritative_template:
        assert output != source and source not in output.parents, 'Never add fixtures to production source'
    else:
        assert source == ROOT.resolve(), 'Authoritative templates require this exact checkout source'
        private_root = source / '.local'
        assert private_root in output.parents, 'Authoritative templates must stay below checkout/.local'
        assert private_root in raw_output.parents, 'Use the literal checkout/.local route'
        route = [private_root]
        route.extend(reversed([path for path in raw_output.parents if private_root in path.parents]))
        route.append(raw_output)
        for path in route:
            try:
                info = path.lstat()
            except FileNotFoundError:
                continue
            attributes = getattr(info, 'st_file_attributes', 0)
            assert not path.is_symlink() and not attributes & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024), 'Private template route cannot contain symlinks or junctions: ' + str(path)
        assert private_root.resolve() == private_root, 'Private root cannot redirect outside the checkout'
        # Existing native fixture assets in production would make a private
        # template ambiguous. Never overwrite or reinterpret those objects.
        base = NS + '_faction_identity_diagnostic'
        for relative in (f'events/{NS}.txt', f'common/on_actions/{NS}.txt',
                         f'common/factions/goals/{base}.txt',
                         f'localisation/english/{base}_l_english.yml',
                         f'localisation/russian/{base}_l_russian.yml'):
            assert not (source / relative).exists(), 'Native fixture collides with a production asset: ' + relative
    return source, output


def validate_additive_daily_effect(source, name, module, namespace):
    text = module.get('on_daily_effect', '')
    assert isinstance(text, str), 'Additive daily effect must be explicit text: ' + name
    if not text:
        return None
    nodes = ast(text)
    catalog = set()
    for relative in module['production_dependency_paths']:
        if relative.startswith('common/scripted_effects/'):
            catalog.update(key for key, _, value in ast((source / relative).read_text('utf-8-sig')) if isinstance(value, list))
    helpers = set()
    trace_flags = []
    holds = []
    def conditions(items):
        for key, _, value in items:
            if key == 'has_global_flag' and isinstance(value, str) and value.startswith(namespace + '_') and value.endswith('_trace'):
                trace_flags.append(value)
            if isinstance(value, list):
                conditions(value)
    def effects(items):
        for key, _, value in items:
            if key == 'limit':
                assert isinstance(value, list)
                conditions(value)
            elif key == 'array':
                assert isinstance(value, str)
            elif key in ('if', 'else', 'hidden_effect', 'every_country', 'every_other_country', 'for_each_scope_loop', 'ROOT', 'FROM', 'THIS', 'PREV') or re.fullmatch(r'[A-Z]{3}', key) or key.startswith('var:'):
                assert isinstance(value, list), 'Daily scope needs a block: ' + key
                effects(value)
            elif key == 'log':
                assert isinstance(value, str)
            elif key in ('add_to_variable', 'set_variable'):
                assert isinstance(value, list) and value
                assert all(variable.startswith('global.' + namespace + '_') for variable, _, _ in value), 'Daily observer can only change private counters'
            elif key == 'set_global_flag':
                # This exact legacy proposal hold is a declared fixture input,
                # not a vote/withdrawal deadline or whole-country AI override.
                assert value == [('flag', '=', 'EP_AI_hold_their_vote'), ('days', '=', '2'), ('value', '=', '1')], 'Daily flag writes cannot expire or rewrite a production deadline'
                holds.append('EP_AI_hold_their_vote')
            else:
                assert key in catalog and value == 'yes', 'Daily effect must call an actual source-bound production helper: ' + key
                helpers.add(key)
    effects(nodes)
    assert trace_flags and helpers, 'Additive daily observer needs a private trace gate and actual production helpers'
    return {'sha256': hashlib.sha256(text.encode()).hexdigest(), 'source_helpers': sorted(helpers),
            'private_trace_flags': sorted(set(trace_flags)), 'declared_proposal_holds': sorted(set(holds))}


def build(source, output, docs=DOCS, validate_only=False, authoritative_template=False,
          additional_module_builders=None, required_additional_modules=None, legacy_api_compatibility=False, fixture_version=None):
    # Explicit {} is reserved for structural base/injected module tests. The
    # normal build/CLI always includes both real legislative acceptance modules.
    fixture_version = (14 if legacy_api_compatibility else 18) if fixture_version is None else fixture_version
    assert type(fixture_version) is int and fixture_version in (14, 15, 16, 17, 18), 'Unsupported native fixture version'
    assert not legacy_api_compatibility or fixture_version == 14, 'Historical API compatibility is v14 only'
    legacy_api_compatibility = fixture_version == 14
    MARK = {14: MARK_V14, 15: MARK_V15, 16: 'EON_EU_NATIVE_V16',17:'EON_EU_NATIVE_V17',18:'EON_EU_NATIVE_V18'}[fixture_version]
    edu_builder = build_edu
    if fixture_version == 14:
        extension_builder = build_extension
    elif fixture_version == 15:
        from runtime_support import build_runtime
        extension_builder = build_runtime
    else:
        from extension_source_runtime_support import build_source_runtime
        from edu_runtime_support import build_edu_runtime
        extension_builder, edu_builder = build_source_runtime, build_edu_runtime
        if fixture_version>=17:
            from edu_confirmation_runtime_support import build_edu_confirmation
            edu_builder=build_edu_confirmation
        if fixture_version==18:
            from fixture_isolation_runtime_support import build_extension_isolated,build_edu_isolated
            extension_builder,edu_builder=build_extension_isolated,build_edu_isolated
    default_acceptance = additional_module_builders is None
    additional_module_builders = dict(default_additive_builders() if default_acceptance else additional_module_builders)
    if required_additional_modules is None:
        required_additional_modules = ('council', 'parliament') if default_acceptance else ()
    required_additional_modules = tuple(required_additional_modules)
    assert set(additional_module_builders) <= set(ADDITIVE_RANGES), 'Unreviewed additive module'
    assert len(required_additional_modules) == len(set(required_additional_modules)), 'Duplicate required additive module'
    assert set(required_additional_modules) <= set(ADDITIVE_RANGES), 'Unreviewed required additive module'
    assert set(required_additional_modules) <= set(additional_module_builders), 'Required Council/EP module omitted'
    builder_inputs = verified_builder_inputs(additional_module_builders, extension_builder, edu_builder)
    source, output = validate_output_paths(source, output, authoritative_template)
    edu_trace_source = verify_edu_trace_source(source,fixture_version)
    docs = docs.resolve()
    assertions, expectations, observations, events = [], {}, [], {}

    def check(label, predicate, expected):
        assert label not in expectations
        assertions.append(label)
        expectations[label] = {'predicate': predicate.strip(), 'expected': expected}
        return (f'log = "{MARK} BEGIN {label}" '
                f'if = {{ limit = {{ {predicate} }} log = "{MARK} PASS {label}" '
                f'add_to_variable = {{ {g("passes")} = 1 }} }} '
                f'else = {{ log = "{MARK} FAIL {label}" add_to_variable = {{ {g("fails")} = 1 }} }} '
                f'log = "{MARK} END {label}" ')

    def obs(label, values):
        assert label not in observations
        observations.append(label)
        return f'log = "{MARK} OBS {label} {values}" '

    def obs_bool(label, predicate):
        """Record one atomic native condition without changing assertion counts."""
        assert label not in observations
        observations.append(label)
        return (f'if = {{ limit = {{ {predicate} }} log = "{MARK} OBS {label} value=1" }} '
                f'else = {{ log = "{MARK} OBS {label} value=0" }} ')

    def faction_observations(stage):
        """Expose native faction state without assuming template/tick behavior."""
        text = obs(stage + '_NAMES', 'usa=[USA.GetFactionName] pol=[POL.GetFactionName]')
        for tag in ('USA', 'POL'):
            for name, predicate in (
                ('EXISTS', 'exists = yes'),
                ('IN_FACTION', 'is_in_faction = yes'),
                ('LEADER', 'is_faction_leader = yes'),
                ('NATO_TEMPLATE', 'has_faction_template = faction_template_nato'),
                ('EDU_TEMPLATE', 'has_faction_template = faction_template_edu'),
            ):
                text += obs_bool(stage + '_' + tag + '_' + name, scope(tag, predicate))
            leader_label = stage + '_' + tag + '_LEADER_TOKEN'
            leader_message = obs(leader_label, 'token=[?THIS.id]')
            text += ('if = { limit = { ' + scope(tag, 'is_in_faction = yes') + '} ' +
                     scope(tag, scope('faction_leader', leader_message)) + '} '
                     f'else = {{ log = "{MARK} OBS {leader_label} token=0" }} ')
        text += obs_bool(stage + '_POL_WITH_USA', scope('POL', 'is_in_faction_with = USA'))
        return text

    def event(number, body):
        assert number not in events
        events[number] = f'country_event = {{ id = {NS}.{number} hidden = yes is_triggered_only = yes immediate = {{ {body} }} }}\n'

    def schedule(tag, number, hours=1):
        return scope(tag, f'country_event = {{ id = {NS}.{number} hours = {hours} }} ')

    def end():
        return f'log = "{MARK} RUN_END passes=[?{g("passes")}] fails=[?{g("fails")}]" '

    def reset_ballots():
        return ('eon_eu_close_council_vote = yes eon_eu_clear_office_ballot = yes '
                'set_global_flag = { flag = eon_eu_office_appointment_cooldown days = 90 value = 1 } ')

    def seed_member(tag):
        return scope(tag, 'eon_eu_clear_country_access = yes '
                     'set_country_flag = eon_eu_admission_commit add_ideas = EU_member '
                     'remove_ideas = EUU_voting_rights_suspended ' + setv('eurosceptic', 0) +
                     setv('breach_of_EU_value', 0) + setv('MEP_Total', 20) + setv('gdp_total', 100) +
                     setv('eon_eu_office_nominee_generation', 1))

    # One private test event runs after real startup initialization. Global locks
    # prevent callbacks from reconstructing the registry midway through setup.
    body = f'log = "{MARK} RUN_BEGIN" '
    body += check('native_representative_countries_exist', ' '.join(scope(tag, 'exists = yes is_subject = no any_owned_state = { always = yes }') for tag in COUNTRIES),
                  'All eight fixed representative countries are live sovereign state owners in this private 2000 start')
    body += check('actual_original_startup_has_fifteen_recognized_members_once',
                  cv(g('fixture_version'), fixture_version) + cv(g('startup_count'), 1) +
                  'has_global_flag = eon_eu_admission_guard_ready NOT = { has_global_flag = eon_eu_dormant } ' +
                  cv('global.EU_member_count', 15) + cv('global.EU_member^num', 15) +
                  scope('GER', 'has_idea = EU_member ' + flag('eon_eu_membership_recognized')) +
                  'all_of_scopes = { array = global.EU_member has_country_flag = eon_eu_membership_recognized eon_eu_is_active_member = yes } ',
                  'Actual production on_startup closes loaded history once: original fifteen members are recognized and sovereign before any private cleanup or admission input; startup counter is one and fixture version is fourteen')
    # This small engine-contract witness separates timed-flag representation
    # from production lifecycle failures. No-value flags are observations only.
    body += f'set_global_flag = {P}scalar_global '
    body += f'set_global_flag = {{ flag = {P}timed_global_default days = 7 }} '
    body += f'set_global_flag = {{ flag = {P}timed_global_positive days = 7 value = 1 }} '
    body += f'set_country_flag = {P}scalar_country '
    body += f'set_country_flag = {{ flag = {P}timed_country_default days = 7 }} '
    body += f'set_country_flag = {{ flag = {P}timed_country_positive days = 7 value = 1 }} '
    body += obs_bool('FLAG_CONTRACT_SCALAR_GLOBAL', f'has_global_flag = {P}scalar_global ')
    body += obs_bool('FLAG_CONTRACT_TIMED_GLOBAL_DEFAULT', f'has_global_flag = {P}timed_global_default ')
    body += obs_bool('FLAG_CONTRACT_TIMED_GLOBAL_POSITIVE', f'has_global_flag = {P}timed_global_positive ')
    body += obs_bool('FLAG_CONTRACT_SCALAR_COUNTRY', flag(P + 'scalar_country'))
    body += obs_bool('FLAG_CONTRACT_TIMED_COUNTRY_DEFAULT', flag(P + 'timed_country_default'))
    body += obs_bool('FLAG_CONTRACT_TIMED_COUNTRY_POSITIVE', flag(P + 'timed_country_positive'))
    body += check('native_timed_global_flag_with_positive_value_is_visible', f'has_global_flag = {P}timed_global_positive ', 'Native global timed flag explicitly carrying value1 is visible immediately')
    body += check('native_timed_country_flag_with_positive_value_is_visible', flag(P + 'timed_country_positive'), 'Native country timed flag explicitly carrying value1 is visible immediately')
    # These independent one-day witnesses are NEVER manually cleared. The final
    # event waits a real in-game day after the lifecycle chain before checking.
    body += f'set_global_flag = {{ flag = {P}natural_global_one_day days = 1 value = 1 }} '
    body += f'set_country_flag = {{ flag = {P}natural_country_one_day days = 1 value = 1 }} '
    body += check('native_one_day_global_flag_starts_visible', f'has_global_flag = {P}natural_global_one_day ', 'Separate actual one-day global timer starts visible and is never consumed by fixture effects')
    body += check('native_one_day_country_flag_starts_visible', flag(P + 'natural_country_one_day'), 'Separate actual one-day NEP timer starts visible and is never consumed by fixture effects')
    for name in ('scalar_global', 'timed_global_default', 'timed_global_positive'):
        body += f'clr_global_flag = {P}{name} '
    for name in ('scalar_country', 'timed_country_default', 'timed_country_positive'):
        body += f'clr_country_flag = {P}{name} '
    body += obs('STARTUP_PRE_COORDINATOR', 'count=[?global.EU_member_count] size=[?global.EU_member^num]')
    body += obs_bool('STARTUP_PRE_GER_LEGAL_MEMBER', scope('GER', 'has_idea = EU_member '))
    body += obs_bool('STARTUP_PRE_DORMANT', 'has_global_flag = eon_eu_dormant ')
    body += 'clr_global_flag = eon_eu_daily_lifecycle_done eon_eu_daily_lifecycle_pulse = yes '
    body += obs('STARTUP_POST_COORDINATOR', 'count=[?global.EU_member_count] size=[?global.EU_member^num]')
    body += obs_bool('STARTUP_POST_DAILY_LOCK', 'has_global_flag = eon_eu_daily_lifecycle_done ')
    body += obs_bool('STARTUP_POST_UNION_ACTIVE', 'eon_eu_union_active = yes ')
    body += obs_bool('STARTUP_POST_DORMANT', 'has_global_flag = eon_eu_dormant ')
    body += obs_bool('STARTUP_POST_REFRESHING', 'has_global_flag = eon_eu_registry_refreshing ')
    body += obs_bool('STARTUP_POST_GER_LIVE', scope('GER', 'eon_eu_is_active_member = yes '))
    body += check('actual_daily_coordinator_reconciles_startup_union', 'has_global_flag = eon_eu_daily_lifecycle_done eon_eu_union_active = yes ' +
                  cv('global.EU_member_count', 'global.EU_member^num') + 'all_of_scopes = { array = global.EU_member eon_eu_is_active_member = yes } ',
                  'Actual production daily coordinator executes startup membership, population, Parliament and institution helpers before controlled private seeding')
    body += obs('STARTUP_PARLIAMENT_SEATS', 'global=[?global.MEP_Total] germany=[?GER.MEP_Total]')
    body += check('actual_startup_parliament_has_live_delegation_and_total', cv('global.MEP_Total', 0, 'greater_than') + scope('GER', cv('MEP_Total', 0, 'greater_than')),
                  'Actual unseeded production startup Parliament has a positive total and positive live GER delegation; private20-seat data cannot satisfy this earlier check')
    # Explicit prior-save input simulation: omit the new recognition stamps
    # while retaining the already-loaded real history and positive daily lock.
    # This is a native migration-helper proof, never an actual save/reload test.
    body += 'clr_global_flag = eon_eu_admission_guard_ready every_country = { clr_country_flag = eon_eu_membership_recognized } '
    body += 'eon_eu_daily_lifecycle_pulse = yes '
    body += check('cold_prior_save_first_daily_closes_guard_under_old_lock',
                  'has_global_flag = eon_eu_admission_guard_ready has_global_flag = eon_eu_daily_lifecycle_done '
                  'NOT = { has_global_flag = eon_eu_dormant } ' + cv('global.EU_member_count', 15) +
                  cv('global.EU_member^num', 15) +
                  'all_of_scopes = { array = global.EU_member has_country_flag = eon_eu_membership_recognized eon_eu_is_active_member = yes } ',
                  'Actual production first-daily post-load recognition adopts loaded fifteen-member input once, even under existing positive daily lock; fixture simulated absent stamps and did not call startup or close helper directly')
    body += scope('POL', 'add_ideas = EU_member ')
    body += check('cold_prior_save_later_raw_reward_is_rejected',
                  scope('POL', 'NOT = { has_idea = EU_member } ' + flag('eon_eu_membership_recognized', False) + contains('global.EU_member', yes=False)) +
                  cv('global.EU_member_count', 15),
                  'Following real migration boundary, raw European outsider idea is rejected without allowing an indefinitely open old-save admission state')
    body += f'set_global_flag = {{ flag = eon_eu_daily_lifecycle_done days = {CONTROLLED_COORDINATOR_HOLD_DAYS} value = 1 }} '
    body += 'set_global_flag = eon_eu_registry_refreshing '
    body += 'every_country = { set_country_flag = eon_eu_leaving_in_progress remove_ideas = EU_member clr_country_flag = eon_eu_leaving_in_progress eon_eu_clear_country_access = yes } '
    body += 'clr_global_flag = eon_eu_dormant clr_global_flag = GAME_RULE_eu_disabled clr_global_flag = usoe_formed '
    body += 'clear_array = global.EU_member clear_array = global.EU_candidates '
    body += ''.join(seed_member(tag) for tag in MEMBERS)
    body += scope('POL', 'eon_eu_clear_country_access = yes clr_country_flag = eon_eu_application_cooldown ' + setv('eurosceptic', 0) + setv('breach_of_EU_value', 0) + setv('MEP_Total', 20) + 'set_politics = { ruling_party = democratic elections_allowed = yes } ')
    body += 'clr_global_flag = eon_eu_registry_refreshing eon_eu_refresh_membership = yes ' + reset_ballots()
    body += setv(g('expected_resident_population_k'), 0)
    for tag in MEMBERS:
        body += scope(tag, setv(g(tag.lower() + '_resident_population_k'), 0) +
                      'every_owned_state = { add_to_variable = { ' + g('expected_resident_population_k') + ' = state_population_k } '
                      'add_to_variable = { ' + g(tag.lower() + '_resident_population_k') + ' = state_population_k } } ')
    body += obs('INITIAL_REGISTRY', 'count=[?global.EU_member_count] size=[?global.EU_member^num]')
    body += check('canonical_registry_has_exactly_six_live_members', cv('global.EU_member_count', 6) + cv('global.EU_member^num', 6) + ''.join(scope(tag, contains('global.EU_member')) for tag in MEMBERS),
                  'Rebuilt registry contains each of six seeded live members exactly once')
    body += scope('GER', 'add_to_array = { global.EU_member = THIS } add_to_array = { global.EU_member = THIS } ')
    body += scope('NEP', 'add_to_array = { global.EU_member = THIS } ')
    body += 'eon_eu_refresh_membership = yes '
    body += check('refresh_removes_duplicates_and_stale_outsider', cv('global.EU_member_count', 6) + cv('global.EU_member^num', 6) + scope('NEP', contains('global.EU_member', yes=False)),
                  'Duplicate GER and stale outsider NEP entries cannot become legal membership')
    body += check('outsider_cannot_view_vote_or_apply', scope('NEP', 'eon_eu_can_view_union = no eon_eu_can_vote = no eon_eu_application_ready = no '),
                  'Non-European outsider NEP has no member/candidate screen, Council vote or Article49 application')
    body += check('ordinary_members_have_shared_union_access', ''.join(scope(tag, 'eon_eu_can_view_union = yes eon_eu_can_vote = yes') for tag in MEMBERS),
                  'The same production access gates apply to GER/FRA/ITA/HOL/SPR/CZE')
    body += check('live_canonical_members_have_budget_eligibility', ''.join(scope(tag, 'eon_eu_is_budget_participant = yes ') for tag in MEMBERS),
                  'The payment eligibility gate requires active legal membership plus canonical registry participation for all six representatives; no weekly cash settlement is claimed')

    # An otherwise eligible European outsider exercises the production on_add
    # guard. NEP alone would be insufficient because the idea's allowed gate
    # already excludes non-European countries before this callback.
    body += scope('POL', 'add_ideas = EU_member ')
    body += check('unapproved_european_grant_cannot_admit_poland', scope('POL',
                  'NOT = { has_idea = EU_member } ' + flag('eon_eu_membership_recognized', False) +
                  contains('global.EU_member', yes=False)) + cv('global.EU_member_count', 6),
                  'Actual raw add_ideas to eligible European POL is rejected by production admission callback, without private commit authorization or registry membership')
    body += scope('GER', 'eon_eu_member_added = yes ')
    body += check('recognized_member_callback_replay_preserves_membership', scope('GER',
                  'has_idea = EU_member ' + flag('eon_eu_membership_recognized') + contains('global.EU_member')) +
                  cv('global.EU_member_count', 6) + cv('global.EU_member^num', 6),
                  'Replaying actual on_add handler for recognized GER neither re-admits nor removes an existing member')

    # Execute stale callbacks extracted from the bound production decision
    # source. Invoking exact timeout AST proves its guard, not a UI click.
    budget_paths = ('EU_budget_yearly_timer', 'EU_budget_draft_preparations',
                    'EU_budget_draft_ongoing', 'EU_budget_draft_ongoing_president',
                    'EU_mff_yearly_timer', 'EU_mff_draft_preparations',
                    'EU_mff_draft_ongoing', 'EU_mff_draft_ongoing_president')
    body += setv(g('stale_budget_gdp_before'), 'global.EU_gdp')
    body += setv(g('stale_budget_pp_before'), 'global.EU_budget_draft_invested_PP')
    body += setv(g('stale_mff_pp_before'), 'global.EU_mff_draft_invested_PP')
    for ident in budget_paths:
        body += scope('NEP', production_callback(source, 'common/decisions/EU_voting_decisions.txt', ident, 'timeout_effect'))
    body += check('eight_stale_outsider_budget_callbacks_are_inert',
                  cv('global.EU_gdp', g('stale_budget_gdp_before')) +
                  cv('global.EU_budget_draft_invested_PP', g('stale_budget_pp_before')) +
                  cv('global.EU_mff_draft_invested_PP', g('stale_mff_pp_before')) +
                  scope('NEP', flag('EU_budget_EP_block', False) + flag('EU_mff_EP_block', False) +
                        ' '.join('NOT = { has_active_mission = ' + ident + ' }' for ident in budget_paths)),
                  'Exact source timeout AST for eight legacy budget/MFF missions cannot change draft investments, GDP, flags or active mission state for outsider NEP')

    # Positive and negative federation authority controls use actual production
    # triggers plus exact source mission callbacks; temporary inputs are declared.
    body += 'set_global_flag = european_federation set_global_flag = ongoing_potef_election '
    body += check('active_federation_allows_territoryless_utility_organizer',
                  scope('EUU', 'eon_eu_potef_campaign_owner_current = yes eon_eu_potef_campaign_current = yes '),
                  'Actual active six-member federation allows technical EUU organizer without demanding territory or sovereign-member status')
    body += 'clr_global_flag = european_federation ' + setv(g('potef_pointer_before_stale'), 'global.eupresfederation')
    body += scope('GER', production_callback(source, 'common/decisions/EU_POTEF_decisions.txt', 'EU_POTEF_election_campaign', 'timeout_effect'))
    body += check('stale_federation_campaign_callback_cannot_appoint_president',
                  cv('global.eupresfederation', g('potef_pointer_before_stale')) +
                  'NOT = { any_country = { has_idea = EU_president } } ' +
                  scope('GER', 'NOT = { has_active_mission = EU_POTEF_election_campaign } '),
                  'Source campaign timeout after federation authority ends cannot run an election or replace the actual president pointer')
    body += 'set_global_flag = european_federation clr_global_flag = ongoing_potef_election '
    body += scope('GER', 'add_ideas = EU_president set_country_flag = environmental_imperialism ')
    body += scope('NEP', 'remove_ideas = USoE_environmental_sanctions set_country_flag = EU_POTEF_environmental_imperialism_target ' +
                  setv('eon_eu_potef_environmental_issuer', 'GER.id'))
    body += check('outsider_environmental_mission_has_actual_current_issuer',
                  scope('NEP', 'NOT = { has_idea = EU_member } eon_eu_potef_environmental_current = yes '),
                  'Environmental recipient can be an outsider; actual recognized GER president with matching full token provides authority')
    body += scope('NEP', production_callback(source, 'common/decisions/EU_POTEF_decisions.txt', 'EU_POTEF_environmental_imperialism_mission', 'timeout_effect'))
    body += check('current_issuer_environmental_timeout_applies_actual_sanction',
                  scope('NEP', 'has_idea = USoE_environmental_sanctions ' + flag('EU_POTEF_environmental_imperialism_target', False)),
                  'Exact production timeout applies sanction to outsider NEP and consumes its target flag when actual issuer authority is current')
    body += scope('NEP', 'remove_ideas = USoE_environmental_sanctions set_country_flag = EU_POTEF_environmental_imperialism_target ' +
                  setv('eon_eu_potef_environmental_issuer', 'GER.id'))
    body += scope('GER', 'remove_ideas = EU_president ')
    body += scope('NEP', production_callback(source, 'common/decisions/EU_POTEF_decisions.txt', 'EU_POTEF_environmental_imperialism_mission', 'timeout_effect'))
    body += check('lost_issuer_environmental_callback_cancels_without_sanction',
                  scope('NEP', 'NOT = { has_idea = USoE_environmental_sanctions } ' + flag('EU_POTEF_environmental_imperialism_target', False) +
                        cv('eon_eu_potef_environmental_issuer', 0)),
                  'Exact source timeout after issuer loses presidency removes target and pointer without applying sanction or redirecting to another president')
    body += scope('GER', 'add_ideas = EU_president ' + production_callback(source, 'common/decisions/EU_POTEF_decisions.txt', 'EU_POTEF_term', 'timeout_effect'))
    body += check('current_president_term_callback_starts_real_campaign',
                  'has_global_flag = ongoing_potef_election ' + scope('GER', 'has_active_mission = EU_POTEF_election_campaign '),
                  'Exact production term callback for recognized current president activates native campaign mission and sets its election marker')
    body += 'eon_eu_close_federation_authority = yes clr_global_flag = european_federation '
    body += check('federation_cleanup_closes_president_and_pending_authority',
                  'NOT = { has_global_flag = ongoing_potef_election } NOT = { any_country = { has_idea = EU_president } } ' +
                  cv('global.eupresfederation', 'EUU.id') + scope('GER', 'NOT = { has_active_mission = EU_POTEF_election_campaign } ') +
                  scope('NEP', cv('eon_eu_potef_environmental_issuer', 0)),
                  'Actual shared cleanup clears pending campaign, office and full issuer pointer across utility/member/outsider scopes')

    # Actual state populations, duplicate normalization and reversible ballots.
    body += core_valid_round_setup(101, owner='ITA', clear_ballots=True)
    body += scope('GER', 'eon_eu_support_council_vote = yes eon_eu_support_council_vote = yes ')
    body += check('duplicate_council_yes_is_idempotent', cv('global.EU_active_vote_yes', 1) + cv('global.EU_active_vote_supporters^num', 1), 'Repeated GER support records one yes')
    body += scope('GER', 'eon_eu_reject_council_vote = yes ')
    body += check('council_yes_to_no_removes_old_vote', cv('global.EU_active_vote_yes', 0) + cv('global.EU_active_vote_no', 1) + cv('global.EU_active_vote_supporters^num', 0), 'Changing GER yes to no removes the old yes')
    body += scope('GER', 'eon_eu_abstain_council_vote = yes ')
    body += check('council_no_to_abstain_is_exclusive', cv('global.EU_active_vote_no', 0) + cv('global.eon_eu_council_abstainers^num', 1), 'Abstention replaces no without a second ballot')
    body += ''.join(scope(tag, 'eon_eu_support_council_vote = yes ') for tag in MEMBERS[:3])
    body += check('three_of_six_cannot_pass_qmv', 'eon_eu_council_vote_passes = no ' + cv('global.EU_active_vote_yes', 3), '50 percent of states is below the 55 percent threshold')
    body += scope('HOL', 'eon_eu_support_council_vote = yes ')
    body += check('four_of_six_pass_qmv_with_resident_population', 'eon_eu_council_vote_passes = yes ' + cv('global.eon_eu_voters', 6) + cv('global.eon_eu_voting_population_k', g('expected_resident_population_k')) +
                  ''.join(scope(tag, cv('eon_eu_voting_population_k', g(tag.lower() + '_resident_population_k'))) for tag in MEMBERS),
                  'Four of six representative members pass and each aggregate equals independently captured actual owned-state population, not army manpower')
    body += scope('GER', setv(g('ger_population_before_manpower'), 'eon_eu_voting_population_k') + 'add_manpower = 50000 ')
    body += 'eon_eu_recount_council_vote = yes '
    body += check('army_reserves_do_not_change_population_weights', scope('GER', cv('eon_eu_voting_population_k', g('ger_population_before_manpower'))) + cv('global.eon_eu_voting_population_k', g('expected_resident_population_k')),
                  'Adding army manpower leaves state-resident Council weights unchanged')
    body += scope('GER', 'add_to_array = { global.EU_active_vote_supporters = THIS } ')
    body += scope('NEP', 'add_to_array = { global.EU_active_vote_supporters = THIS } ')
    body += 'eon_eu_recount_council_vote = yes '
    body += check('recount_discards_duplicate_and_outsider_ballots', cv('global.EU_active_vote_yes', 4) + cv('global.EU_active_vote_supporters^num', 4), 'Recount normalizes raw duplicate GER and outsider NEP yes entries')
    body += scope('GER', 'add_ideas = EUU_voting_rights_suspended ') + 'eon_eu_recount_council_vote = yes '
    body += check('suspended_council_vote_excluded_from_denominator', cv('global.eon_eu_voters', 5) + cv('global.EU_active_vote_yes', 3) + scope('GER', 'eon_eu_can_vote = no ' + contains('global.EU_active_vote_supporters', yes=False)),
                  'Suspended GER contributes neither Council ballot nor Council electorate population')
    body += scope('GER', 'remove_ideas = EUU_voting_rights_suspended ')
    body += core_valid_round_setup(103, owner='ITA', clear_ballots=True)
    body += check('unanswered_member_blocks_unanimity', 'eon_eu_council_vote_passes = no ', 'Treaty agenda103 cannot pass with unanswered delegations')
    body += ''.join(scope(tag, 'eon_eu_support_council_vote = yes ') for tag in MEMBERS)
    body += check('all_six_yes_pass_unanimous_treaty_agenda', 'eon_eu_council_vote_passes = yes ' + cv('global.EU_active_vote_yes', 6), 'Every current electorate member has answered yes')
    body += scope('CZE', 'eon_eu_abstain_council_vote = yes ')
    body += check('explicit_abstention_does_not_block_unanimity', 'eon_eu_council_vote_passes = yes ' + cv('global.EU_active_vote_no', 0) + cv('global.eon_eu_unanswered_members', 0), 'Explicit abstention is permitted under the Council unanimity abstraction')
    body += scope('CZE', 'eon_eu_reject_council_vote = yes ')
    body += check('explicit_no_blocks_unanimity', 'eon_eu_council_vote_passes = no ', 'An actual no blocks the unanimous agenda')
    # Isolated inclusive threshold predicates complement aggregate ballots above.
    body += core_valid_round_setup(101, owner='ITA', clear_ballots=True) + setv('global.eon_eu_voters', 20) + setv('global.eon_eu_yes_fraction', .55) + setv('global.EU_pop_ratio_yes', .65) + setv('global.eon_eu_opposing_members', 9)
    body += check('qmv_includes_exact_55_and_65_percent', 'eon_eu_council_vote_passes = yes ', 'Seeded predicate boundary: exactly55 percent states and65 percent population passes')
    body += setv('global.EU_pop_ratio_yes', .649) + setv('global.eon_eu_opposing_members', 4)
    body += check('four_opponents_can_block_insufficient_population', 'eon_eu_council_vote_passes = no ', 'Seeded predicate boundary: four opponents plus64.9 percent population blocks')
    body += setv('global.eon_eu_opposing_members', 3)
    body += check('three_opponents_cannot_form_blocking_minority', 'eon_eu_council_vote_passes = yes ', 'Seeded predicate boundary: three opponents cannot form the four-state blocking minority')
    body += 'eon_eu_close_council_vote = yes '
    body += check('closing_vote_clears_agenda_and_all_ballots', cv('global.current_active_vote_disp', 0) + cv('global.EU_active_vote_supporters^num', 0) + cv('global.EU_active_vote_rejecters^num', 0) + cv('global.eon_eu_council_abstainers^num', 0), 'Closure consumes agenda and every ballot collection')
    body += core_valid_round_setup(101, owner='ITA', clear_ballots=True) + 'eon_eu_council_ai_pulse = yes '
    body += setv(g('ai_council_answered'), 'global.EU_active_vote_yes') + 'add_to_variable = { ' + g('ai_council_answered') + ' = global.EU_active_vote_no } '
    body += 'add_to_variable = { ' + g('ai_council_answered') + ' = global.eon_eu_council_abstainers^num } '
    body += check('native_council_ai_dispatch_answers_each_eligible_member_once', cv(g('ai_council_answered'), 6) + cv('global.eon_eu_unanswered_members', 0) + cv('global.eon_eu_voters', 6) +
                  'all_of_scopes = { array = global.EU_member is_ai = yes OR = { '
                  'AND = { ' + contains('global.EU_active_vote_supporters') + contains('global.EU_active_vote_rejecters', yes=False) + '} '
                  'AND = { ' + contains('global.EU_active_vote_rejecters') + contains('global.EU_active_vote_supporters', yes=False) + '} } } ',
                  'Actual Council AI pulse invokes agenda101 meta_effect and gives exactly one exclusive ballot to each eligible AI, without assuming all votes are yes')
    body += setv(g('ai_council_first_yes'), 'global.EU_active_vote_yes') + setv(g('ai_council_first_no'), 'global.EU_active_vote_no')
    body += 'eon_eu_council_ai_pulse = yes '
    body += check('repeated_native_council_ai_pulse_does_not_repeat_ballots', cv('global.EU_active_vote_yes', g('ai_council_first_yes')) + cv('global.EU_active_vote_no', g('ai_council_first_no')) +
                  cv('global.EU_active_vote_supporters^num', 'global.EU_active_vote_yes') + cv('global.EU_active_vote_rejecters^num', 'global.EU_active_vote_no') + cv('global.eon_eu_unanswered_members', 0),
                  'Second actual AI dispatch leaves yes/no counts and canonical ballot lengths unchanged')
    body += 'eon_eu_close_council_vote = yes '

    # Historical office proxy initialization, vacancy, finite cohorts and rotation.
    body += 'eon_eu_close_institutions = yes clr_global_flag = eon_eu_institutions_initialized '
    body += scope('HOL', 'add_ideas = the_euro ') + 'eon_eu_initialize_historical_offices = yes eon_eu_reconcile_office_holders = yes '
    body += check('fresh_2000_has_four_historical_origin_proxies', scope('ITA', 'has_idea = EU_commission_president ') + scope('FRA', 'has_idea = EU_parliament_president ') + scope('HOL', 'has_idea = ECB_president ') + scope('SPR', 'has_idea = EU_foreign_minister '),
                  'Fresh 2000 start maps Prodi/Fontaine/Duisenberg/Solana to national-origin proxies without government control claims')
    body += 'eon_eu_update_budget = yes '
    body += obs('HISTORICAL_OFFICE_BUDGET', 'budget=[?global.EU_total_budget] expenditure=[?global.EU_total_exp] italy_admin=[?ITA.EU_admin_subsidies]')
    body += check('actual_seeded_union_budget_matches_positive_current_expenditure', cv('global.EU_total_budget', 0, 'greater_than') + cv('global.EU_total_exp', 'global.EU_total_budget') + cv('global.EU_total_exp', 0, 'greater_than'),
                  'Actual budget helper uses seeded GDP100 and existing production call rates to calculate positive matched income/expenditure; no subsidies or expense values are seeded')
    body += scope('GER', 'set_temp_variable = { eon_eu_office_requested_id = 1 } ')
    body += scope('GER', check('filled_office_cannot_be_nominated', 'eon_eu_office_nomination_ready = no ', 'Existing Commission term blocks a second nomination'))
    body += scope('ITA', 'remove_ideas = EU_commission_president ') + 'eon_eu_reconcile_office_holders = yes '
    body += 'eon_eu_update_budget = yes '
    body += check('removed_commission_origin_loses_administrative_budget_cache', scope('ITA', cv('EU_admin_subsidies', 0)),
                  'Removing and reconciling the ITA Commission holder triggers actual allocation refresh; former office origin retains no administrative subsidy')
    body += scope('GER', 'set_temp_variable = { eon_eu_office_requested_id = 1 } ' + check('expired_office_is_vacant_and_nominatable', 'eon_eu_office_nomination_ready = yes ', 'Removing the timed holder simulates expiry; the vacancy becomes nominatable'))
    body += 'set_global_flag = treaty_of_lisbon '
    body += scope('GER', setv('eon_eu_council_served_generation', 1) + setv('eon_eu_council_nominee_terms', 2) + 'set_temp_variable = { eon_eu_office_requested_id = 4 } ' + check('same_council_nominee_has_maximum_two_terms', 'eon_eu_office_nominee_eligible = no ', 'Same national nominee cohort cannot receive a third European Council term'))
    body += scope('GER', 'clr_country_flag = eon_eu_national_nominees_recently_refreshed eon_eu_refresh_nominee_cohort = yes ' + check('fresh_nominee_cohort_restores_future_eligibility', cv('eon_eu_office_nominee_generation', 2) + 'eon_eu_office_nominee_eligible = yes ', 'Explicit new nominee cohort increments identity and does not renew the exhausted person'))
    body += scope('HOL', 'set_temp_variable = { eon_eu_office_requested_id = 3 } ' + check('ecb_historical_nominee_is_nonrenewable', 'eon_eu_office_nominee_eligible = no ', 'The historical ECB nominee cohort cannot be reappointed'))
    body += setv('global.eon_eu_council_rotating_holder', 0) + 'clr_global_flag = eon_eu_council_rotating_term eon_eu_rotate_council_presidency = yes ' + setv(g('rotation_first'), 'global.eon_eu_council_rotating_holder')
    body += obs('ROTATION_FIRST_STATE', 'holder=[?global.eon_eu_council_rotating_holder] first=[?eon_eu_rotation_first] selected=[?eon_eu_rotation_selected]')
    body += obs_bool('ROTATION_FIRST_TERM', 'has_global_flag = eon_eu_council_rotating_term ')
    body += obs_bool('ROTATION_FIRST_LIVE', 'var:global.eon_eu_council_rotating_holder = { eon_eu_is_active_member = yes } ')
    body += check('council_rotation_starts_with_live_member', 'has_global_flag = eon_eu_council_rotating_term var:global.eon_eu_council_rotating_holder = { eon_eu_is_active_member = yes } ', 'Six-month presidency selects an eligible live member')
    body += 'clr_global_flag = eon_eu_council_rotating_term eon_eu_rotate_council_presidency = yes '
    body += check('expired_rotation_moves_to_next_member', 'NOT = { ' + cv('global.eon_eu_council_rotating_holder', g('rotation_first')) + '} var:global.eon_eu_council_rotating_holder = { eon_eu_is_active_member = yes } ', 'Consumed term moves to the next live eligible country in the registry')
    # Same APIs as the user decisions; no GUI clicks or additional human players.
    body += scope('GER', 'set_temp_variable = { eon_eu_office_requested_id = 1 } eon_eu_open_office_ballot = yes ')
    body += obs('MANUAL_COMMISSION_OPEN_STATE', 'id=[?global.eon_eu_office_id] phase=[?global.eon_eu_office_phase] nominee=[?global.eon_eu_office_nominee]')
    body += obs_bool('MANUAL_COMMISSION_OPEN_DEADLINE', 'has_global_flag = eon_eu_office_ballot_deadline ')
    body += obs_bool('MANUAL_COMMISSION_GER_NOMINATABLE', scope('GER', 'eon_eu_office_nomination_ready = yes '))
    body += check('commission_nomination_opens_separate_council_ballot', cv('global.eon_eu_office_id', 1) + cv('global.eon_eu_office_phase', 1) + 'has_global_flag = eon_eu_office_ballot_deadline ', 'Commission first stage is a finite separate Council ballot')
    body += scope('GER', 'eon_eu_cast_office_yes = yes eon_eu_cast_office_yes = yes ')
    body += check('office_repeated_yes_is_idempotent', cv('global.eon_eu_office_supporters^num', 1), 'Repeated office support creates one entry')
    body += scope('GER', 'eon_eu_cast_office_no = yes ')
    body += check('office_vote_change_is_exclusive', cv('global.eon_eu_office_supporters^num', 0) + cv('global.eon_eu_office_rejecters^num', 1), 'Office yes-to-no removes the original choice')
    body += ''.join(scope(tag, 'eon_eu_cast_office_yes = yes ') for tag in MEMBERS)
    body += 'clr_global_flag = eon_eu_office_ballot_deadline eon_eu_resolve_office_ballot = yes '
    body += check('commission_council_success_requires_new_ep_ballot', cv('global.eon_eu_office_id', 1) + cv('global.eon_eu_office_phase', 2) + cv('global.eon_eu_office_supporters^num', 0) + scope('GER', 'NOT = { has_idea = EU_commission_president } '), 'Council success opens fresh EP consent, without prematurely appointing the nominee')
    body += scope('GER', 'add_ideas = EUU_voting_rights_suspended ' + check('council_suspension_does_not_remove_ep_mandate', 'eon_eu_can_cast_office_ballot = yes ', 'Suspended government Council rights do not silence national Parliament seats'))
    body += ''.join(scope(tag, 'eon_eu_cast_office_yes = yes ') for tag in MEMBERS[:3])
    body += 'eon_eu_recount_office_ballot = yes '
    body += check('exact_half_ep_seats_is_not_majority', 'eon_eu_office_ep_majority_passed = no ' + cv('global.eon_eu_office_ep_yes', 60) + cv('global.eon_eu_office_ep_total', 120), 'Sixty of120 national-delegation seats is exactly half, not majority consent')
    body += scope('GER', 'remove_ideas = EUU_voting_rights_suspended ') + scope('HOL', 'eon_eu_cast_office_yes = yes ')
    body += 'clr_global_flag = eon_eu_office_ballot_deadline eon_eu_resolve_office_ballot = yes '
    body += check('ep_majority_appoints_commission_and_consumes_ballot', scope('GER', 'has_idea = EU_commission_president ') + cv('global.eon_eu_office_id', 0) + cv('global.eon_eu_office_supporters^num', 0), 'Eighty of120 seats approve; appointment consumes the request')
    body += 'eon_eu_update_budget = yes '
    body += obs('APPOINTED_OFFICE_BUDGET', 'budget=[?global.EU_total_budget] expenditure=[?global.EU_total_exp] germany_admin=[?GER.EU_admin_subsidies] italy_admin=[?ITA.EU_admin_subsidies]')
    body += check('actual_office_budget_moves_to_new_holder_without_parliament_reelection', scope('ITA', cv('EU_admin_subsidies', 0)) + scope('GER', cv('EU_admin_subsidies', 0, 'greater_than')) +
                  ''.join(scope(tag, cv('MEP_Total', 20)) for tag in MEMBERS),
                  'Actual budget update after Commission appointment allocates to GER, clears ITA and preserves all six seeded20-seat delegations; role change does not rerun Parliament elections')
    body += 'eon_eu_resolve_office_ballot = yes '
    body += check('repeated_office_resolution_does_not_duplicate_holder', scope('GER', 'has_idea = EU_commission_president ') + cv('global.eon_eu_office_id', 0), 'Repeated consumed callback remains inert')
    # Actual backend AI stages must work without a human nomination/GUI tab.
    body += scope('GER', 'remove_ideas = EU_commission_president ') + 'eon_eu_reconcile_office_holders = yes '
    for tag in MEMBERS:
        body += scope(tag, 'clr_country_flag = eon_eu_office_nomination_cooldown every_other_country = { '
                      'limit = { eon_eu_is_active_member = yes } add_opinion_modifier = { target = PREV modifier = EU_member_opinion } } ')
    body += 'clr_global_flag = eon_eu_office_appointment_cooldown eon_eu_daily_institutions_pulse = yes '
    body += check('native_ai_backend_opens_vacant_commission_ballot', cv('global.eon_eu_office_id', 1) + cv('global.eon_eu_office_phase', 1) +
                  'has_global_flag = eon_eu_office_ballot_deadline var:global.eon_eu_office_nominee = { eon_eu_is_active_member = yes is_ai = yes } ',
                  'Actual daily institutions backend nominates a live AI Commission candidate without a GUI or manual open-ballot helper')
    body += 'eon_eu_daily_institutions_pulse = yes '
    body += check('native_ai_backend_casts_council_office_votes', cv('global.eon_eu_office_yes', 5, 'greater_than_or_equals') + 'eon_eu_office_enhanced_qmv_passed = yes ',
                  'Actual AI voting records at least five of six positive seeded-friendly Council delegations and meets72/65')
    body += 'clr_global_flag = eon_eu_office_ballot_deadline eon_eu_daily_institutions_pulse = yes '
    body += check('native_ai_backend_council_success_opens_ep_stage', cv('global.eon_eu_office_id', 1) + cv('global.eon_eu_office_phase', 2) + cv('global.eon_eu_office_supporters^num', 0),
                  'Production backend consumes the simulated Council deadline and opens fresh Parliament consent')
    body += 'eon_eu_daily_institutions_pulse = yes '
    body += check('native_ai_backend_casts_separate_ep_votes', 'eon_eu_office_ep_majority_passed = yes ' + cv('global.eon_eu_office_ep_yes', 100, 'greater_than_or_equals'),
                  'Production AI independently supports the second-stage Parliament ballot with over half of all120 seeded seats')
    body += 'clr_global_flag = eon_eu_office_ballot_deadline eon_eu_daily_institutions_pulse = yes '
    body += setv(g('ai_commission_holders'), 0) + 'every_country = { limit = { eon_eu_is_active_member = yes has_idea = EU_commission_president } add_to_variable = { ' + g('ai_commission_holders') + ' = 1 } } '
    body += check('native_ai_backend_appoints_one_live_commission_holder', cv(g('ai_commission_holders'), 1) + cv('global.eon_eu_office_id', 0) + cv('global.eon_eu_office_supporters^num', 0) +
                  'var:global.eucomission = { eon_eu_is_active_member = yes is_ai = yes has_idea = EU_commission_president } ',
                  'Actual backend completes both AI consent stages, appoints one live holder and consumes ballots; no campaign timing or player click is claimed')
    body += 'set_global_flag = { flag = eon_eu_office_appointment_cooldown days = 90 value = 1 } '
    body += obs('AFTER_SINGLE_EVENT', 'passes=[?' + g('passes') + '] fails=[?' + g('fails') + ']')
    body += schedule('POL', 2)
    event(1, body)

    # Applicant-rooted stages dispatch member-rooted replies. Each reply asserts
    # native ROOT/FROM before executing a production pair helper. Delayed handoff
    # keeps log triplets in one deterministic manifest order.
    body = check('poland_is_reform_ready_sovereign_applicant', 'tag = POL eon_eu_application_ready = yes ', 'POL is a live peaceful elected European applicant; test reform proxies are explicitly seeded')
    body += obs('POL_BEFORE_APPLICATION_STATE', 'phase=[?eon_eu_accession_phase] approvals=[?eon_eu_accession_approvals^num]')
    body += obs_bool('POL_BEFORE_APPLICATION_WINDOW', flag('eon_eu_application_window'))
    body += 'eon_eu_apply_for_membership_start = yes '
    body += obs('POL_AFTER_APPLICATION_STATE', 'phase=[?eon_eu_accession_phase] approvals=[?eon_eu_accession_approvals^num]')
    body += obs_bool('POL_AFTER_APPLICATION_WINDOW', flag('eon_eu_application_window'))
    body += obs_bool('POL_AFTER_APPLICATION_MEMBER', 'has_idea = EU_member ')
    body += obs_bool('POL_AFTER_APPLICATION_CURRENT', 'eon_eu_application_current = yes ')
    body += check('application_opens_phase_one_without_membership', cv('eon_eu_accession_phase', 1) + flag('eon_eu_application_window') + 'NOT = { has_idea = EU_member } ', 'Actual application API opens365-day request with no membership benefits')
    body += 'add_ideas = EU_member '
    body += check('rejected_raw_grant_preserves_real_application',
                  'NOT = { has_idea = EU_member } ' + flag('eon_eu_membership_recognized', False) +
                  cv('eon_eu_accession_phase', 1) + flag('eon_eu_application_window') + cv('eon_eu_accession_approvals^num', 0),
                  'Actual rejected raw idea while POL has a genuine phase-one application preserves its negotiation state and does not register membership')
    body += schedule('GER', 3) + schedule('POL', 4, 2)
    event(2, body)
    next_id = 3
    for index, tag in enumerate(MEMBERS):
        body = check('application_reply_' + tag.lower() + '_native_pair', f'tag = {tag} FROM = {{ tag = POL }} ', f'Native response ROOT is{tag}, FROM is applicantPOL')
        body += 'eon_eu_endorse_application = yes eon_eu_endorse_application = yes '
        if index == 0:
            body += 'FROM = { ' + obs('POL_AFTER_FIRST_REPLY_STATE', 'phase=[?eon_eu_accession_phase] approvals=[?eon_eu_accession_approvals^num]') + obs_bool('POL_AFTER_FIRST_REPLY_WINDOW', flag('eon_eu_application_window')) + '} '
        body += check('application_reply_' + tag.lower() + '_records_once', 'FROM = { ' + contains('eon_eu_accession_approvals', 'ROOT') + cv('eon_eu_accession_approvals^num', index + 1) + '} ', 'Actual endorsement records this responding member once, including a repeated callback')
        event(next_id, body)
        next_id += 1
        if index + 1 < len(MEMBERS):
            body = 'eon_eu_progress_accession = yes '
            body += check('partial_application_' + str(index + 1) + '_cannot_grant_candidate', cv('eon_eu_accession_phase', 1) + flag('EU_candidate', False), 'Remaining unsatisfied member consent prevents candidacy')
            body += schedule(MEMBERS[index + 1], next_id + 1) + schedule('POL', next_id + 2, 2)
        else:
            body = 'eon_eu_progress_accession = yes '
            body += check('unanimous_application_grants_candidate_only', cv('eon_eu_accession_phase', 2) + flag('EU_candidate') + flag('eon_eu_negotiation_period') + 'NOT = { has_idea = EU_member } eon_eu_can_view_union = yes eon_eu_can_vote = no ', 'Unanimous governments grant candidacy plus180-day negotiation, without member votes/offices')
            body += 'eon_eu_submit_accession_treaty = yes '
            body += check('minimum_negotiation_period_blocks_premature_treaty', cv('eon_eu_accession_phase', 2), 'Production treaty API rejects an unexpired180-day negotiation period')
            body += 'clr_country_flag = eon_eu_negotiation_period eon_eu_submit_accession_treaty = yes '
            body += check('consumed_negotiation_clock_opens_treaty_phase_three', cv('eon_eu_accession_phase', 3) + flag('eon_eu_application_window') + cv('eon_eu_accession_approvals^num', 0), 'Simulated clock expiry opens a new treaty requiring new ratifications')
            body += schedule('GER', next_id + 1) + schedule('POL', next_id + 2, 2)
        event(next_id, body)
        next_id += 1

    for index, tag in enumerate(MEMBERS):
        body = check('treaty_reply_' + tag.lower() + '_native_pair', f'tag = {tag} FROM = {{ tag = POL }} ', f'Native treaty response ROOT is{tag}, FROM is applicantPOL')
        body += 'eon_eu_ratify_member_accession = yes eon_eu_ratify_member_accession = yes eon_eu_support_accession_ep = yes eon_eu_support_accession_ep = yes '
        body += check('treaty_reply_' + tag.lower() + '_separate_government_and_ep_consent', 'FROM = { ' + contains('eon_eu_accession_approvals', 'ROOT') + contains('eon_eu_accession_ep_approvals', 'ROOT') + cv('eon_eu_accession_approvals^num', index + 1) + cv('eon_eu_accession_ep_approvals^num', index + 1) + '} ', 'Government ratification and Parliament delegation consent are distinct idempotent collections')
        event(next_id, body)
        next_id += 1
        body = 'eon_eu_recount_treaty_parliament = yes eon_eu_progress_accession = yes '
        if index == 2:
            body += check('accession_exact_half_ep_seats_is_insufficient', flag('eon_eu_accession_ep_consent', False) + cv('eon_eu_treaty_accession_ep_yes_display', 60) + cv('eon_eu_treaty_ep_total_display', 120), 'Three national delegations are60 of120 seats; strictly more than half is required')
        if index + 1 < len(MEMBERS):
            body += 'eon_eu_ratify_accession_treaty = yes '
            body += check('partial_treaty_' + str(index + 1) + '_cannot_join', 'NOT = { has_idea = EU_member } ' + cv('eon_eu_accession_phase', 3), 'EP support cannot replace a missing member-government ratification')
            body += schedule(MEMBERS[index + 1], next_id + 1) + schedule('POL', next_id + 2, 2)
        else:
            body += check('unanimous_treaty_and_ep_consent_wait_for_final_applicant_ratification', cv('eon_eu_accession_phase', 4) + flag('eon_eu_accession_ep_consent') + 'NOT = { has_idea = EU_member } ', 'All governments plus EP majority enable, but do not replace, final applicant consent')
            body += 'clr_global_flag = eon_eu_membership_changed eon_eu_ratify_accession_treaty = yes eon_eu_ratify_accession_treaty = yes '
            body += check('final_ratification_joins_once_and_clears_candidate', 'has_idea = EU_member eon_eu_is_active_member = yes ' + cv('global.EU_member_count', 7) + cv('global.EU_member^num', 7) + flag('EU_candidate', False) + contains('global.EU_candidates', yes=False) + cv('eon_eu_accession_phase', 0), 'Final production ratification admits POL once and consumes candidacy/draft')
            body += check('final_article49_consumes_single_use_admission_authority',
                          'has_idea = EU_member ' + flag('eon_eu_membership_recognized') + flag('eon_eu_admission_commit', False),
                          'Real final Article49 branch issues then consumes one-use grant, leaving recognized member status rather than a reusable admission token')
            body += check('actual_accession_sets_membership_changed_for_budget_and_parliament', 'has_global_flag = eon_eu_membership_changed ',
                          'Actual accession callback raises membership-change signal after the fixture cleared it; daily coordinator can then recalculate budget and representation')
            body += schedule('POL', next_id + 1)
        event(next_id, body)
        next_id += 1

    # Article50 is a separate government/Parliament consent process. Parliament
    # consent is majority of votes cast, unlike Article49 all-seat majority.
    body = 'clr_country_flag = cant_invoke_article_50 eon_eu_notify_withdrawal = yes eon_eu_propose_withdrawal_treaty = yes '
    body += check('agreed_withdrawal_draft_preserves_member_rights', 'tag = POL has_idea = EU_member eon_eu_can_vote = yes ' + flag('Article_50') + flag('eon_eu_withdrawal_proposal'),
                  'Actual notice and agreement proposal preserve ordinary membership while collecting distinct consents')
    body += 'eon_eu_finish_withdrawal = yes '
    body += check('unapproved_withdrawal_cannot_finish', 'has_idea = EU_member ' + flag('Article_50') + 'NOT = { has_idea = withdrawal_treaty } ',
                  'Final-consent helper remains inert without other Council approval and Parliament consent')
    body += schedule('GER', next_id + 1) + schedule('POL', next_id + 2, 2)
    event(next_id, body)
    next_id += 1
    for index, tag in enumerate(MEMBERS):
        body = check('withdrawal_reply_' + tag.lower() + '_native_pair', f'tag = {tag} FROM = {{ tag = POL }} ', f'Withdrawal response ROOT is{tag}, FROM is withdrawingPOL')
        body += 'eon_eu_approve_withdrawal_treaty = yes eon_eu_approve_withdrawal_treaty = yes '
        if index < 3:
            body += 'eon_eu_support_withdrawal_ep = yes eon_eu_support_withdrawal_ep = yes '
        elif index < 5:
            body += 'eon_eu_reject_withdrawal_ep = yes eon_eu_reject_withdrawal_ep = yes '
        else:
            body += 'eon_eu_support_withdrawal_ep = yes eon_eu_reject_withdrawal_ep = yes eon_eu_abstain_withdrawal_ep = yes '
        body += check('withdrawal_reply_' + tag.lower() + '_government_consent_once', 'FROM = { ' + contains('eon_eu_withdrawal_approvals', 'ROOT') + cv('eon_eu_withdrawal_approvals^num', index + 1) + '} ',
                      'Government approval is recorded once despite repeated callback, separately from Parliament delegation choice')
        if index == 5:
            body += check('withdrawal_ep_vote_switch_then_abstain_removes_both', 'FROM = { ' + contains('eon_eu_withdrawal_ep_approvals', 'ROOT', False) + contains('eon_eu_withdrawal_ep_rejections', 'ROOT', False) + '} ',
                          'Delegation yes→no→abstain removes both prior ballot entries')
        event(next_id, body)
        next_id += 1
        body = 'eon_eu_recount_treaty_parliament = yes eon_eu_recount_withdrawal = yes '
        if index < 4:
            body += 'eon_eu_finish_withdrawal = yes '
            body += check('partial_withdrawal_' + str(index + 1) + '_cannot_finish', 'has_idea = EU_member ' + flag('eon_eu_withdrawal_council_consent', False),
                          'Fewer than72 percent of other governments cannot finalize withdrawal, even if Parliament supports')
        if index == 4:
            body += check('qualified_withdrawal_awaits_leaver_final_consent', 'has_idea = EU_member ' + flag('eon_eu_withdrawal_council_consent') + flag('eon_eu_withdrawal_ep_consent'),
                          'Other Council72/65 and Parliament consent permit but do not automatically replace the withdrawing state final decision')
        if index + 1 < len(MEMBERS):
            body += schedule(MEMBERS[index + 1], next_id + 1) + schedule('POL', next_id + 2, 2)
        else:
            body += check('withdrawal_ep_uses_votes_cast_not_all_seats', flag('eon_eu_withdrawal_ep_consent') + cv('eon_eu_treaty_withdrawal_ep_yes_display', 60) + cv('eon_eu_treaty_withdrawal_ep_no_display', 40) + cv('eon_eu_treaty_ep_total_display', 140),
                          'Sixty yes exceeds forty no valid votes, although below half of140 total seats; abstentions do not count against')
            # Preserve the actual shared startup NATO even if its optional DLC
            # template metadata is absent. The analyzer also requires the exact
            # recorded NATO name; a different or factionless alliance cannot pass.
            body += obs_bool('NATO_SETUP_HAS_NO_COMPROMISE_NO_SURRENDER', 'has_dlc = "No Compromise, No Surrender" ')
            body += faction_observations('NATO_BEFORE_SETUP')
            body += scope('USA', 'if = { limit = { NOT = { is_in_faction = yes POL = { is_in_faction_with = USA } } } '
                          'if = { limit = { is_in_faction = yes } leave_faction = yes } '
                          'create_faction_from_template = faction_template_nato } ')
            body += faction_observations('NATO_AFTER_CREATE')
            body += scope('POL', 'if = { limit = { is_in_faction = yes NOT = { is_in_faction_with = USA } } leave_faction = yes } ')
            body += scope('USA', 'if = { limit = { is_in_faction = yes } faction_leader = { add_to_faction = POL } } ')
            body += faction_observations('NATO_AFTER_JOIN')
            body += setv(g('nato_admission_date'), 'global.date')
            body += setv(g('nato_leader_before_exit'), 0)
            body += scope('POL', 'if = { limit = { is_in_faction = yes } ' + scope('faction_leader', setv(g('nato_leader_before_exit'), 'THIS.id')) + '} ')
            body += obs('NATO_ADMISSION_CLOCK', 'date=[?global.date] leader=[?' + g('nato_leader_before_exit') + ']')
            # Native hours=1 may dispatch in the same logged game hour. A two-
            # hour request must prove advancement, rather than assume it.
            body += schedule('POL', next_id + 1, 2)
            event(next_id, body)
            next_id += 1
            body = faction_observations('NATO_NEXT_NATIVE_HOUR')
            body += obs('NATO_CONTINUATION_CLOCK', 'date=[?global.date] admission=[?' + g('nato_admission_date') + ']')
            nato_identity = ('is_in_faction = yes is_in_faction_with = USA ' + scope('USA', 'is_in_faction = yes ') +
                             scope('faction_leader', cv('THIS.id', g('nato_leader_before_exit'))) +
                             'OR = { NOT = { has_dlc = "No Compromise, No Surrender" } has_faction_template = faction_template_nato } ')
            body += check('agreed_exit_fixture_is_in_nato_before_edu', nato_identity + cv('global.date', g('nato_admission_date'), 'greater_than'),
                          'POL and USA share actual named NATO with the captured current leader before EU exit, after a proven native game-hour advance; template metadata is additionally required only with NCNS DLC')
            body += 'set_global_flag = EDU set_country_flag = new_EU_open set_country_flag = eu_sec_dis_open set_country_flag = EU_candidate '
            body += setv('eon_eu_accession_phase', 3) + 'add_to_array = { global.EU_candidates = THIS } '
            body += setv('EU_subsidies', 9) + setv('EU_budget_contribution_weekly', 4) + setv('treasury', 321)
            body += 'clr_global_flag = eon_eu_membership_changed eon_eu_finish_withdrawal = yes '
            body += check('final_agreed_exit_consumes_member_candidate_and_draft', 'NOT = { has_idea = EU_member } has_idea = withdrawal_treaty eon_eu_can_view_union = no eon_eu_can_vote = no ' + flag('Article_50', False) + flag('EU_candidate', False) + contains('global.EU_member', yes=False) + contains('global.EU_candidates', yes=False) + cv('eon_eu_accession_phase', 0) + cv('EU_subsidies', 0) + cv('EU_budget_contribution_weekly', 0) + cv('global.EU_member_count', 6),
                          'Leaver final-consent API applies treaty exit once, cleans membership/candidate/UI/draft and zeros payment eligibility')
            body += check('actual_exit_sets_membership_changed_for_budget_and_parliament', 'has_global_flag = eon_eu_membership_changed ',
                          'Actual withdrawal callback raises membership-change signal after the fixture cleared it; canonical-array callback mutation cannot hide the change')
            body += faction_observations('NATO_AFTER_EU_EXIT')
            body += check('eu_exit_does_not_remove_unrelated_nato_despite_edu', nato_identity,
                          'EU exit with globalEDU preserves positive actual named NATO membership and the captured current faction leader; optional template metadata cannot substitute for membership')
            body += 'clr_global_flag = EDU '
            body += obs('AFTER_AGREED_WITHDRAWAL', 'member_count=[?global.EU_member_count] treasury=[?treasury]')
            body += setv(g('agreed_exit_date'), 'global.date')
            body += obs('AGREED_EXIT_CLOCK', 'date=[?global.date]')
            body += schedule('NEP', next_id + 1, 2)
        event(next_id, body)
        next_id += 1

    # Complete exit with cleanup, revocation, deadline and repeat-callback proof.
    body = obs('AGREED_EXIT_DELAYED_CLOCK', 'date=[?global.date] exit=[?' + g('agreed_exit_date') + ']')
    body += check('agreed_exit_effect_survives_next_native_hour', cv('global.date', g('agreed_exit_date'), 'greater_than') + scope('POL', 'NOT = { has_idea = EU_member } has_idea = withdrawal_treaty '),
                  'After proven actual native game-hour advancement, agreed-exit treaty effects remain eligible; absence of membership cannot cancel post-exit consequences')
    body += scope('POL', 'set_country_flag = new_EU_open set_country_flag = eu_sec_dis_open set_country_flag = EU_candidate '
                 'set_variable = { eon_eu_accession_phase = 3 } add_to_array = { global.EU_candidates = THIS } '
                 + setv('EU_subsidies', 9) + setv('EU_budget_contribution_weekly', 4) + setv('treasury', 321) +
                 'leaving_EU = yes ')
    body += check('exit_revokes_member_candidate_ui_and_fiscal_eligibility', scope('POL', 'NOT = { has_idea = EU_member } eon_eu_can_view_union = no eon_eu_can_vote = no ' + flag('EU_candidate', False) + flag('new_EU_open', False) + flag('eu_sec_dis_open', False) + contains('global.EU_member', yes=False) + contains('global.EU_candidates', yes=False) + cv('EU_subsidies', 0) + cv('EU_budget_contribution_weekly', 0) + cv('eon_eu_accession_phase', 0)),
                  'Actual leaving_EU clears candidate/UI/access and zeros weekly subsidy/contribution eligibility; no weekly economic settlement is claimed')
    body += scope('POL', setv(g('treasury_after_exit'), 'treasury') + 'leaving_EU = yes eon_eu_refresh_membership = yes ')
    body += check('repeat_exit_has_no_treasury_or_registry_side_effect', scope('POL', cv('treasury', g('treasury_after_exit')) + cv('EU_subsidies', 0) + cv('EU_budget_contribution_weekly', 0)) + cv('global.EU_member_count', 6), 'Repeated cleanup never grants payout or duplicate membership; treasury stays at captured post-exit value')
    body += scope('POL', 'add_ideas = EU_member ')
    body += check('post_exit_raw_reward_cannot_restore_membership',
                  scope('POL', 'NOT = { has_idea = EU_member } ' + flag('eon_eu_membership_recognized', False) +
                        contains('global.EU_member', yes=False)) + cv('global.EU_member_count', 6),
                  'A later raw grant after completed EU exit cannot bypass Article49 or restore old institutional rights')
    body += scope('GER', 'clr_country_flag = cant_invoke_article_50 eon_eu_notify_withdrawal = yes ' + check('article50_notice_preserves_member_rights', flag('Article_50') + flag('eon_eu_withdrawal_deadline') + 'has_idea = EU_member eon_eu_can_view_union = yes eon_eu_can_vote = yes ', 'Notice starts730-day clock and keeps membership until effective exit') + 'eon_eu_revoke_withdrawal = yes ' + check('unilateral_revocation_restores_ordinary_membership', flag('Article_50', False) + flag('eon_eu_withdrawal_clock_started', False) + 'has_idea = EU_member eon_eu_can_vote = yes ', 'Revocation clears notice/clock without obtaining foreign consent'))
    body += scope('GER', 'clr_country_flag = cant_invoke_article_50 eon_eu_notify_withdrawal = yes clr_country_flag = eon_eu_withdrawal_deadline eon_eu_force_deadline_withdrawal = yes ' + check('deadline_exit_finishes_without_agreement', 'NOT = { has_idea = EU_member } has_idea = no_deal_exit ' + flag('Article_50', False) + contains('global.EU_member', yes=False), 'Simulated expiry invokes actual no-deal exit and consumes membership/notice'))
    body += 'set_global_flag = eon_eu_registry_refreshing ' + seed_member('GER') + 'clr_global_flag = eon_eu_registry_refreshing eon_eu_refresh_membership = yes '
    # One live-union existing legal member made subject loses representation,
    # while its legal idea survives. Releasing it restores representation.
    body += scope('NEP', 'puppet = CZE ')
    body += check('subject_budget_eligibility_stops_before_registry_refresh', scope('CZE', 'is_subject = yes has_idea = EU_member eon_eu_is_budget_participant = no '),
                  'Legal membership idea and stale canonical entry cannot charge a newly subordinated country before the next refresh')
    body += 'eon_eu_refresh_membership = yes '
    body += check('subordinated_member_keeps_legal_idea_but_loses_representation', scope('CZE', 'is_subject = yes has_idea = EU_member eon_eu_is_active_member = no ' + contains('global.EU_member', yes=False)) + cv('global.EU_member_count', 5), 'Live union excludes a subject representative while retaining legal membership marker')
    body += check('subject_budget_eligibility_remains_off_after_refresh', scope('CZE', 'eon_eu_is_budget_participant = no ' + contains('global.EU_member', yes=False)),
                  'Refreshed subject has no contribution/subsidy eligibility while its legal marker remains; this is a gate test, not cash transfer')
    body += scope('NEP', 'end_puppet = CZE ') + 'eon_eu_refresh_membership = yes '
    body += check('restored_sovereignty_restores_live_representation', scope('CZE', 'is_subject = no eon_eu_is_active_member = yes ' + contains('global.EU_member')) + cv('global.EU_member_count', 6), 'Legal member representation returns when sovereign again in an existing active union')
    body += check('restored_live_canonical_member_regains_budget_eligibility', scope('CZE', 'eon_eu_is_budget_participant = yes ' + contains('global.EU_member')),
                  'Restored sovereignty plus current canonical registry restores the shared budget eligibility gate')
    # Dormancy is a game archive, not an assertion about real treaty dissolution.
    body += setv('global.current_active_vote_disp', 101) + scope('FRA', 'eon_eu_support_council_vote = yes ') + 'set_global_flag = EDU '
    body += 'set_global_flag = eon_eu_registry_refreshing '
    body += 'every_country = { limit = { has_idea = EU_member } set_country_flag = eon_eu_leaving_in_progress remove_ideas = EU_member clr_country_flag = eon_eu_leaving_in_progress } '
    body += 'clr_global_flag = eon_eu_registry_refreshing eon_eu_refresh_membership = yes '
    body += check('zero_representatives_archive_union_and_close_institutions', 'has_global_flag = eon_eu_dormant ' + cv('global.EU_member_count', 0) + cv('global.EU_member^num', 0) + cv('global.current_active_vote_disp', 0) + cv('global.eon_eu_office_id', 0) + 'NOT = { has_global_flag = EDU } NOT = { has_global_flag = eon_eu_council_rotating_term } NOT = { any_country = { has_idea = EU_commission_president } } ',
                  'No active representatives archive gameplay union, ballots, offices and staleEDUcreation receipt; this is not automatic legal dissolution of the real EU')
    body += 'set_global_flag = eon_eu_registry_refreshing ' + scope('GER', 'add_ideas = EU_member ') + 'clr_global_flag = eon_eu_registry_refreshing eon_eu_refresh_membership = yes '
    body += check('stale_idea_cannot_automatically_resurrect_archived_union', 'has_global_flag = eon_eu_dormant ' + cv('global.EU_member_count', 0) + cv('global.EU_member^num', 0) + scope('GER', 'eon_eu_can_view_union = no eon_eu_can_vote = no eon_eu_is_budget_participant = no '), 'A stale legal idea cannot resume dormant institutions or payment eligibility without explicit consenting refounding')
    body += scope('GER', 'set_politics = { ruling_party = democratic elections_allowed = yes } ' + setv('eurosceptic', 0) + setv('breach_of_EU_value', 0))
    body += scope('FRA', 'set_politics = { ruling_party = democratic elections_allowed = yes } ' + setv('eurosceptic', 0) + setv('breach_of_EU_value', 0))
    body += obs('BEFORE_REFOUND', 'count=[?global.EU_member_count] passes=[?' + g('passes') + ']')
    body += schedule('FRA', next_id + 1)
    event(next_id, body)
    next_id += 1

    # Caller ROOT=GER, partner FROM=FRA. Send the offer from partner-rooted event
    # to proposer-rooted event, then an actual proposer-rooted acceptance event.
    body = schedule('GER', next_id + 1)
    event(next_id, body)
    next_id += 1
    body = check('refounding_offer_has_native_sovereign_pair', 'tag = GER FROM = { tag = FRA } eon_eu_refound_offer_ready = yes ', 'Native proposerROOT GER and partnerFROM FRA are eligible sovereign Europeans')
    body += 'eon_eu_propose_refounding = yes '
    body += obs('REFOUND_OFFER_STATE', 'target=[?eon_eu_refound_target] from=[?FROM.id]')
    body += obs_bool('REFOUND_OFFER_OUTGOING', flag('eon_eu_refound_outgoing'))
    body += obs_bool('REFOUND_OFFER_INCOMING', 'FROM = { ' + flag('eon_eu_refound_incoming') + '} ')
    body += check('offer_alone_cannot_resume_union', 'has_global_flag = eon_eu_dormant ' + flag('eon_eu_refound_outgoing') + 'FROM = { ' + flag('eon_eu_refound_incoming') + cv('eon_eu_refound_sender', 'ROOT.id') + '} ' + cv('global.EU_member_count', 0), 'Offer records full country tokens but leaves dormant union until partner consents')
    body += schedule('FRA', next_id + 1)
    event(next_id, body)
    next_id += 1
    body = check('refounding_acceptance_has_native_reverse_pair', 'tag = FRA FROM = { tag = GER } eon_eu_refound_response_ready = yes ', 'Native acceptanceROOT FRA and proposerFROM GER match the recorded offer')
    body += 'eon_eu_accept_refounding = yes eon_eu_accept_refounding = yes '
    body += check('explicit_refounding_restores_only_two_consenting_founders', 'NOT = { has_global_flag = eon_eu_dormant } ' + cv('global.EU_member_count', 2) + cv('global.EU_member^num', 2) + 'has_idea = EU_member FROM = { has_idea = EU_member } ' + scope('ITA', 'NOT = { has_idea = EU_member } eon_eu_can_view_union = no '), 'Actual paired acceptance admits onlyGER/FRA once; old members require new Article49 applications')
    body += check('consumed_refounding_offer_cannot_be_replayed', flag('eon_eu_refound_incoming', False) + 'FROM = { ' + flag('eon_eu_refound_outgoing', False) + '} ' + cv('global.EU_member_count', 2), 'Offer/response are consumed before membership callbacks and repeated acceptance is inert')
    body += obs('REFOUNDED_STATE', 'count=[?global.EU_member_count] passes=[?' + g('passes') + '] fails=[?' + g('fails') + ']')
    body += scope('NEP', f'country_event = {{ id = {NS}.{next_id + 1} days = 1 }} ')
    event(next_id, body)
    next_id += 1
    body = check('native_one_day_global_flag_expires_without_manual_clear', f'NOT = {{ has_global_flag = {P}natural_global_one_day }} ',
                 'After an actual native in-game day beyond the complete chain, the one-day global witness expires naturally; no clr_global_flag targets it')
    body += check('native_one_day_country_flag_expires_without_manual_clear', 'tag = NEP ' + flag(P + 'natural_country_one_day', False),
                  'After an actual native in-game day beyond the complete chain, the one-day NEP witness expires naturally; no clr_country_flag targets it')
    body += obs('REFOUNDED_PRE_COORDINATOR_BUDGET', 'budget=[?global.EU_total_budget] expenditure=[?global.EU_total_exp] seats=[?global.MEP_Total]')
    body += 'clr_global_flag = eon_eu_daily_lifecycle_done eon_eu_daily_lifecycle_pulse = yes '
    body += obs('REFOUNDED_POST_COORDINATOR_BUDGET', 'count=[?global.EU_member_count] budget=[?global.EU_total_budget] expenditure=[?global.EU_total_exp] seats=[?global.MEP_Total] germany=[?GER.MEP_Total] france=[?FRA.MEP_Total]')
    body += check('actual_post_refounding_coordinator_rebuilds_two_founder_parliament', 'eon_eu_union_active = yes ' + cv('global.EU_member_count', 2) + cv('global.EU_member^num', 2) + cv('global.MEP_Total', 0, 'greater_than') +
                  scope('GER', cv('MEP_Total', 0, 'greater_than')) + scope('FRA', cv('MEP_Total', 0, 'greater_than')),
                  'Actual coordinator after mutual refounding reconstructs positive real Parliament seats for only two consenting founders; no seeded delegate or membership-change injection at this stage')
    body += check('actual_post_refounding_budget_has_matching_positive_expenditure', 'has_global_flag = eon_eu_budget_year ' + cv('global.EU_total_budget', 0, 'greater_than') + cv('global.EU_total_exp', 'global.EU_total_budget') + cv('global.EU_total_exp', 0, 'greater_than'),
                  'Actual refounded budget recalculation starts annual365-day clock and derives positive expenditure equal to current budget; no expense-variable injection or full legislative annual-budget process/weekly treasury settlement is claimed')
    # Actual core coordinator just consumed its old private hold. Re-establish
    # the declared isolation boundary before the natural legislative chain.
    body += f'set_global_flag = {{ flag = eon_eu_daily_lifecycle_done days = {CONTROLLED_COORDINATOR_HOLD_DAYS} value = 1 }} '
    baseline_labels = [label for label in assertions if label not in ADMISSION_BOUNDARY_ASSERTIONS]
    baseline_contract = {'assertions': baseline_labels,
                         'expectations': {label: expectations[label] for label in baseline_labels}}
    assert len(baseline_labels) == 144, 'Preserve every existing lifecycle assertion'
    assert hashlib.sha256(json.dumps(baseline_contract, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == BASELINE_V12_SHA256, 'Never silently remove, reorder or weaken a v12 lifecycle assertion'
    diagnostic = build_diagnostic(NS, MARK, terminal_effect=end())
    world = build_world_scheduler(NS, MARK, terminal_effect=diagnostic['entry_effect'])
    additional_modules = {}
    continuation = world['entry_effect']
    for name in ('parliament', 'council'):
        if name in additional_module_builders:
            module = additional_module_builders[name](NS, MARK, source=source, terminal_effect=continuation)
            assert module.get('production_dependency_paths') and module.get('production_input_sha256'), 'Additive module must bind actual production sources: ' + name
            additional_modules[name] = module
            continuation = module['entry_effect']
    edu = edu_builder(NS, MARK, source=source, terminal_effect=continuation)
    extension = extension_builder(NS, MARK, source=source, terminal_effect=edu['entry_effect'])
    modules = [('extension', extension, (2000, 2099) if legacy_api_compatibility else (7400, 7599)), ('edu', edu, (3000, 3099))]
    modules += [(name, additional_modules[name], ADDITIVE_RANGES[name]) for name in ('council', 'parliament') if name in additional_modules]
    modules += [('world_scheduler', world, (6000, 6099)), ('faction_identity_diagnostic', diagnostic, (1000, 1099))]
    body += obs('FINAL_STATE', 'count=[?global.EU_member_count] passes=[?' + g('passes') + '] fails=[?' + g('fails') + ']') + extension['entry_effect']
    event(next_id, body)

    additive_daily_contracts = {name: validate_additive_daily_effect(source, name, module, NS)
                                for name, module in additional_modules.items()}
    daily_effect = ''.join(module.get('on_daily_effect', '') for _, module, _ in modules)
    edu_startup = edu.get('startup_effect', '')
    if fixture_version >= 16:
        assert ast(edu_startup) == [('set_variable', '=', [(f'global.{NS}_edu_handler_invocations', '=', '0')])], 'EDU startup may only initialize its private source-dispatch counter'
    fixture = {
        f'events/{NS}.txt': f'add_namespace = {NS}\n' + ''.join(events[number] for number in sorted(events)),
        f'common/on_actions/{NS}.txt': 'on_actions = { on_startup = { effect = { ' + f'log = "{MARK} STARTUP fixture_version={fixture_version}" ' + setv(g('fixture_version'), fixture_version) + f'add_to_variable = {{ {g("startup_count")} = 1 }} ' + setv(g('passes'), 0) + setv(g('fails'), 0) + setv(g('handler_invocations'), 0) + edu_startup + scope('NEP', f'country_event = {{ id = {NS}.1 days = 3 }} ') + '} } on_daily = { effect = { ' + daily_effect + '} } }\n',
    }
    native_modules, module_events, diagnostic_observations = {}, 0, []
    for name, module, bounds in modules:
        labels = module.get('assertions', [])
        assert len(labels) == len(set(labels)) and not set(labels).intersection(assertions), 'Duplicate module assertion: ' + name
        assert set(module.get('expectations', {})) == set(labels), 'Module expectations must be complete: ' + name
        assertions.extend(labels)
        expectations.update(module.get('expectations', {}))
        observations.extend(module['observations'])
        diagnostic_observations.extend(module.get('diagnostic_observations', []))
        event_ids = []
        for rel, text in module['fixture_text'].items():
            if rel.startswith('events/'):
                assert text.startswith(f'add_namespace = {NS}\n')
                for key, _, fields in ast(text):
                    if key == 'country_event':
                        ident = next(value for field, _, value in fields if field == 'id')
                        assert ident.startswith(NS + '.')
                        number = int(ident.split('.')[-1])
                        assert bounds[0] <= number <= bounds[1], 'Module event outside reserved range: ' + name
                        event_ids.append(ident)
                fixture[f'events/{NS}.txt'] += text.split('\n', 1)[1]
            else:
                if name in ('extension', 'edu') and fixture_version >= 15 and (name == 'extension' or fixture_version >= 16):
                    from runtime_override_support import override_actions, RUNTIME_OVERRIDE_ACTIONS_V15
                    RUNTIME_OVERRIDE_ACTIONS = override_actions(fixture_version)
                    if rel in ('descriptor.mod', f'common/on_actions/{NS}.txt'):
                        continue  # Standalone metadata is never loaded by this composition.
                    allowed_overrides = set(RUNTIME_OVERRIDE_ACTIONS_V15) if name == 'extension' else set(RUNTIME_OVERRIDE_ACTIONS) - set(RUNTIME_OVERRIDE_ACTIONS_V15)
                    assert rel in allowed_overrides, 'Unknown runtime override asset for module: ' + name
                else:
                    assert name == 'faction_identity_diagnostic', 'Only reviewed diagnostic may add private assets'
                assert rel not in fixture
                fixture[rel] = text
        assert len(event_ids) == len(set(event_ids)), 'Duplicate module event: ' + name
        for field in ('entry_event_id', 'terminal_event_id'):
            value = module[field]
            ident = f'{NS}.{value}' if isinstance(value, int) else value
            assert ident in event_ids, 'Missing module boundary event: ' + name
        assert len(event_ids) == module.get('events', 5), 'Module event count drift: ' + name
        module_events += len(event_ids)
        pins = module.get('production_input_sha256', {})
        assert set(pins) == set(module.get('production_dependency_paths', [])), 'Missing module source pin: ' + name
        for rel, digest in pins.items():
            assert sha(source / rel) == digest, 'Module source changed during build: ' + rel
        native_modules[name] = {'assertions': len(labels), 'events': len(event_ids),
                                'production_input_sha256': pins,
                                'limits': module.get('limits', module.get('contract', {}).get('limits', []))}
        if name in additive_daily_contracts:
            native_modules[name]['daily_observer_contract'] = additive_daily_contracts[name]
    event_ids = [next(value for field, _, value in fields if field == 'id')
                 for key, _, fields in ast(fixture[f'events/{NS}.txt']) if key == 'country_event']
    assert len(event_ids) == len(set(event_ids)), 'Duplicate integrated event IDs'
    assert fixture[f'events/{NS}.txt'].count('RUN_END') == 1, 'Require exactly one terminal run receipt'
    assert len(fixture) == {14:5, 15:7, 16:9,17:9,18:9}[fixture_version], 'Require exact reviewed fixture inventory'
    extension_fields = {}
    edu_fields = {}
    runtime_fields = {}
    if legacy_api_compatibility:
        extension_fields['extension_callback_contract'] = extension['extension_callback_contract']
    else:
        from runtime_override_support import override_actions, validate_override_bytes
        RUNTIME_OVERRIDE_ACTIONS = override_actions(fixture_version)
        overrides = {}
        for relative, selected in RUNTIME_OVERRIDE_ACTIONS.items():
            overrides[relative] = validate_override_bytes(relative, (source / relative).read_bytes(), fixture[relative].encode('utf-8'), selected, fixture_version=fixture_version)
        extension_fields.update(source_handler_runtime_contract=extension['source_handler_runtime_contract'],
                                baseline114_contract=extension['baseline114_contract'],
                                baseline114_sha256=extension['baseline114_sha256'],
                                extension_runtime_method=extension['method'],
                                negative_native109_history_preserved=extension['negative_native109_history_preserved'])
        if fixture_version >= 16:
            extension_fields['raw_api_diagnostic_contract'] = extension['raw_api_diagnostic_contract']
        if fixture_version==18:
            extension_fields['extension_cleanup_dispatch_contract']=extension['extension_cleanup_dispatch_contract']
        runtime_fields.update(runtime_overrides=overrides,
                              provenance_root=str(source),
                              provenance_sha256={r: v['source_sha256'] for r,v in overrides.items()})
    if fixture_version >= 16:
        edu_fields.update(edu_source_handler_runtime_contract=edu['edu_source_handler_runtime_contract'],
                          baseline41_contract=edu['baseline41_contract'],
                          baseline41_sha256=edu['baseline41_sha256'],
                          edu_runtime_method=edu['contract']['method'],
                          edu_raw_api_diagnostic_contract=edu['edu_raw_api_diagnostic_contract'])
        if fixture_version>=17:
            edu_fields.update(edu_confirmation_contract=edu['edu_confirmation_contract'],
                              baseline41_migration_map=edu['baseline41_migration_map'])
        if fixture_version==18:
            edu_fields['edu_removal_isolation_contract']=edu['edu_removal_isolation_contract']
    elapsed_contracts = [
        {'start_observation': 'NATO_ADMISSION_CLOCK', 'end_observation': 'NATO_CONTINUATION_CLOCK', 'minimum_hours': 1},
        {'start_observation': 'AGREED_EXIT_CLOCK', 'end_observation': 'AGREED_EXIT_DELAYED_CLOCK', 'minimum_hours': 1},
    ]
    for _, module, _ in modules:
        elapsed_contracts.extend(module.get('required_elapsed_game_time', []))
    edu_contract = {**edu['contract'], 'start_observation': 'EDU_START', 'end_observation': 'EDU_TERMINAL'}
    assert len(observations) == len(set(observations))
    assert len(diagnostic_observations) == len(set(diagnostic_observations)), 'Duplicate optional diagnostic label'
    assert not set(diagnostic_observations).intersection(observations), 'Optional diagnostics cannot masquerade as mandatory observations'
    additive_contract = {'allowed_ranges': {name: list(bounds) for name, bounds in ADDITIVE_RANGES.items()},
                         'required': list(required_additional_modules),
                         'included': [name for name in ('council', 'parliament') if name in additional_modules],
                         'acceptance_ready': set(required_additional_modules) == set(ADDITIVE_RANGES) and set(additional_modules) == set(ADDITIVE_RANGES)}
    isolation_contract = {
        'flag': 'eon_eu_daily_lifecycle_done',
        'declared_hold_days': CONTROLLED_COORDINATOR_HOLD_DAYS,
        'controlled_sequence': ['core', 'extension', 'edu', 'council', 'parliament'],
        'release_before_module': 'world_scheduler',
        'world_release_effect': 'clr_global_flag = eon_eu_daily_lifecycle_done',
        'scope': 'Private coordinator isolation input only; proposal deadlines and elapsed acceptance minima are unchanged.',
    }
    assert CONTROLLED_COORDINATOR_HOLD_DAYS >= 180, 'Controlled legislative sequence needs the declared whole-chain isolation hold'
    assert verified_builder_inputs(additional_module_builders, extension_builder, edu_builder) == builder_inputs, 'Builder dependency changed during composition'
    assert verify_edu_trace_source(source,fixture_version) == edu_trace_source, 'Actual EDU trace source changed during composition'
    for rel, text in fixture.items():
        if rel.endswith('.txt'):
            ast(text)
    assert len(assertions) == len(set(assertions))
    if not legacy_api_compatibility:
        # Validation-only composition binds the same authoritative/effective
        # maps as the written template, without writing source or fixture files.
        dependencies = {}
        for directory in ('common', 'events', 'history', 'localisation/english', 'localisation/russian'):
            for path in sorted((source / directory).rglob('*')):
                if path.is_file() and path.suffix.lower() in ('.txt', '.lua', '.yml'):
                    dependencies[path.relative_to(source).as_posix()] = sha(path)
        for rel in fixture:
            if rel not in runtime_fields['runtime_overrides']:
                dependencies.pop(rel, None)
        from runtime_override_support import validate_override_maps
        effective = dict(dependencies)
        effective.update({r: v['runtime_override_sha256'] for r,v in runtime_fields['runtime_overrides'].items()})
        runtime_fields['effective_source_sha256'] = effective
        validate_override_maps(runtime_fields['runtime_overrides'], dependencies, effective, runtime_fields['provenance_sha256'],
                               {r: hashlib.sha256(t.encode('utf-8')).hexdigest() for r,t in fixture.items()}, fixture_version=fixture_version)
    if validate_only:
        return {'assertions': assertions, 'expectations': expectations, 'validated_fixture_only': True,
                'fixture_text': fixture, 'events': len(events) + module_events,
                'core_assertions': len(baseline_labels) + len(ADMISSION_BOUNDARY_ASSERTIONS),
                'native_modules': native_modules, 'baseline_v12_contract_sha256': BASELINE_V12_SHA256,
                'fixture_version': fixture_version, 'marker': MARK, 'native_builder_inputs': builder_inputs,
                'additive_module_contract': additive_contract, 'coordinator_isolation_contract': isolation_contract,
                'edu_trace_source_contract': edu_trace_source,
                **extension_fields, **edu_fields, **runtime_fields,
                **({'source_sha256': dependencies, 'source_root': str(source), 'fixture_root': str(output / 'mod'),
                    'fixture_sha256': {r: hashlib.sha256(t.encode('utf-8')).hexdigest() for r,t in fixture.items()}} if not legacy_api_compatibility else {}),
                'diagnostic_observations': diagnostic_observations,
                'extension_calibrations': extension['calibrations'], 'edu_native_callback_contract': edu_contract,
                'required_elapsed_game_time': elapsed_contracts,
                'faction_identity_diagnostic': diagnostic['contract'],
                'required_observations': observations}
    # All executable common/events/history text is bound, including callback,
    # GUI and economic dependencies; broad binding prevents hidden API drift.
    dependencies = {}
    for directory in ('common', 'events', 'history', 'localisation/english', 'localisation/russian'):
        for path in sorted((source / directory).rglob('*')):
            if path.is_file() and path.suffix.lower() in ('.txt', '.lua', '.yml'):
                dependencies[path.relative_to(source).as_posix()] = sha(path)
    for rel in fixture:
        if rel not in runtime_fields.get('runtime_overrides', {}):
            dependencies.pop(rel, None)
    for module in native_modules.values():
        for rel, digest in module['production_input_sha256'].items():
            assert dependencies.get(rel) == digest, 'Module dependency absent from full source binding: ' + rel
    for area in ('membership', 'voting', 'institutions'):
        for kind in ('effects', 'triggers'):
            assert f'common/scripted_{kind}/eon_eu_{area}_{kind}.txt' in dependencies
    for rel in ('common/scripted_effects/eon_eu_lifecycle_effects.txt',
                'common/scripted_triggers/eon_eu_financial_triggers.txt'):
        assert rel in dependencies, 'Require current lifecycle/financial production API: ' + rel
    if not legacy_api_compatibility:
        from runtime_override_support import validate_override_maps
        effective = dict(dependencies)
        effective.update({r: v['runtime_override_sha256'] for r,v in runtime_fields['runtime_overrides'].items()})
        runtime_fields['effective_source_sha256'] = effective
        validate_override_maps(runtime_fields['runtime_overrides'], dependencies, effective, runtime_fields['provenance_sha256'],
                               {r: hashlib.sha256(t.encode('utf-8')).hexdigest() for r,t in fixture.items()}, fixture_version=fixture_version)
    output.mkdir(parents=True)
    for rel, text in fixture.items():
        path = output / 'mod' / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8', newline='\n')
    manifest = {
        'kind': 'native_eu_lifecycle', 'schema': 1, 'fixture_version': fixture_version, 'marker': MARK,
        'authoritative_template': authoritative_template,
        'assertions': assertions, 'expectations': expectations,
        'events': len(events) + module_events, 'core_assertions': len(baseline_labels) + len(ADMISSION_BOUNDARY_ASSERTIONS),
        'source_root': str(source), 'fixture_root': str(output / 'mod'),
        'expected_start_tag': 'NEP', 'countries': list(dict.fromkeys((*COUNTRIES, 'USA', 'EUU', *edu['contract']['countries']))),
        'source_sha256': dependencies,
        'fixture_sha256': {rel: sha(output / 'mod' / rel) for rel in fixture},
        'required_observations': observations,
        'faction_identity_diagnostic': diagnostic['contract'],
        'native_modules': native_modules, 'baseline_v12_contract_sha256': BASELINE_V12_SHA256,
        'native_builder_inputs': builder_inputs, 'additive_module_contract': additive_contract,
        'coordinator_isolation_contract': isolation_contract,
        'edu_trace_source_contract': edu_trace_source,
        **extension_fields, **edu_fields, **runtime_fields,
        'diagnostic_observations': diagnostic_observations,
        'extension_calibrations': extension['calibrations'], 'edu_native_callback_contract': edu_contract,
        'required_elapsed_game_time': elapsed_contracts,
        'required_named_factions': [
            {'observation': label, 'members': ['usa', 'pol'], 'allowed_names': ['NATO', 'НАТО']}
            for label in ('NATO_NEXT_NATIVE_HOUR_NAMES', 'NATO_AFTER_EU_EXIT_NAMES')
        ],
        'documentation_root': str(docs),
        'documentation_sha256': {name: sha(docs / name) for name in
                               ('effects_documentation.md', 'triggers_documentation.md', 'dynamic_variables_documentation.md')},
        'limits': [
            'Actual original fifteen-member history, one-time startup counter and recognized admission boundary are checked before private cleanup; fixture inputs subsequently use explicit one-use admission commits and actual idea callbacks, never disable the production admission guard.',
            'A prior-loaded-save input omits recognition stamps under a positive daily lock, then invokes the actual first-daily migration boundary. This is helper migration proof, not a real save/reload campaign test.',
            'Eight stale outsider budget callbacks and POTEF term/campaign/environmental callbacks are extracted from the exact source AST; positive current-issuer/term controls accompany inert stale callbacks. No UI click proof is claimed.',
            'Private scalar/timed positive-value flag witnesses isolate the native flag contract; missing-value flag behavior is observed without asserting a default.',
            'Separate one-day global and NEP timed flags are never manually cleared and are checked for natural expiry after an actual extra native day; multi-year clock expiry remains separately simulated.',
            'Actual production daily coordinator executes once before seeding; its daily lock is then held180days across the full controlled extension/EDU/Council/Parliament chain. The final world scheduler explicitly releases it; tested proposal deadlines are untouched.',
            'Actual native ROOT/FROM event dispatch and production helpers execute application, ratification and refounding; no native UI consent clicks are claimed.',
            'Office yes/no APIs are the same as human Decisions controls; this automated probe does not create additional human players or test popup/GUI interaction.',
            'Actual AI institution nomination, Council vote, Parliament vote and appointment execute through repeated production daily-institutions helpers after seeding friendly EU opinion modifiers; deadlines are simulated, not waited14days.',
            'Actual legislative Council AI meta_effect dispatch executes agenda101 twice; remaining agenda IDs are source-bound but not individually executed by this probe.',
            'Resident state_population_k weights are captured from actual frozen-start owned states; MEP_Total delegation20-seat weights are explicitly seeded private data.',
            'Negotiation, Article50, office and rotating-term clock expiry is simulated by consuming timed flags/ideas; multi-year timing is not campaign-validated.',
            'Treasury unchanged after repeat exit plus zero subsidy/contribution and canonical registry exclusion prove payment eligibility cleanup, not a full weekly economic settlement.',
            'Actual budget-cache recalculation follows initial and changed Commission origins without reseeding call rates, subsidies or expenses; twenty-seat private delegations remain unchanged during office-only allocation updates.',
            'Actual shared startup NATO is retained when present; otherwise private NATO creation/admission uses its actual faction leader. Positive actual membership, a captured unchanged leader and recorded exact NATO name are required before/after EU withdrawal. Template metadata is additionally required only with actual NCNS DLC; no DLC absence or factionless state can bypass actual membership.',
            'Two delayed continuations request hours2; both native global.date predicates and independent logger game-date receipts must prove at least one actual game-hour advance. Requested delays alone never prove elapsed time.',
            'A separate OBS-only hidden/visible faction-goal diagnostic performs actual faction leadership transfer, dismantling, same-founder recreation and marker removal after lifecycle assertions. Its supported/unsupported/invalid-controls result is independent of lifecycle assertion PASS and does not implement or accept production EDU behavior.',
            'Synthetic55/65 and four-state boundary counters exercise production predicates separately from the actual six-country ballot aggregation.',
            'Dormant zero-representative gameplay archive and two consenting founders are abstractions, not a claim that occupation legally dissolves the real European Union.',
            'One deterministic isolated lifecycle trace; no campaign balance/performance, save-reload persistence, hotjoin or multiplayer proof.',
        ] + [limit for _, module, _ in modules for limit in module.get('limits', [])],
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


def build_v17(source, output, docs=DOCS, validate_only=False, authoritative_template=False, **kwargs):
    """Historical V17 combined raw removal/create input; preserve failed114."""
    return build(source,output,docs,validate_only,authoritative_template,fixture_version=17,**kwargs)


def build_v16(source, output, docs=DOCS, validate_only=False, authoritative_template=False, **kwargs):
    """Historical V16 hook requirements; never reinterpret sealed113 failures."""
    return build(source,output,docs,validate_only,authoritative_template,fixture_version=16,**kwargs)


def build_v15(source, output, docs=DOCS, validate_only=False, authoritative_template=False, **kwargs):
    """Historical v15 API diagnostics; never reinterpret frozen111 evidence."""
    return build(source, output, docs, validate_only, authoritative_template, fixture_version=15, **kwargs)


def build_v14(source, output, docs=DOCS, validate_only=False, authoritative_template=False,
              additional_module_builders=None, required_additional_modules=None):
    """Explicit compatibility: preserve historical native-API predicates and evidence."""
    return build(source, output, docs, validate_only, authoritative_template,
                 additional_module_builders, required_additional_modules, legacy_api_compatibility=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--docs', type=Path, default=DOCS)
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--authoritative-template', action='store_true',
                        help='Explicitly create a private template below this checkout/.local; never install or launch it')
    args = parser.parse_args()
    result = build(args.source, args.output, args.docs, args.validate_only, args.authoritative_template)
    print(json.dumps({'prepared': not args.validate_only, 'validated_fixture_only': args.validate_only,
                      'assertions': len(result['assertions']), 'native_tested': False}))
