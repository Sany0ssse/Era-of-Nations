"""Private OBS-only native faction-goal characterization, never a model proof.

The core builder owns startup, its 144 assertions and terminal receipt. It must
pass its terminal effect here, enter event1000 after the core, merge the returned
fixture texts/observations, and bind all fixture bytes. No production source is
written. A negative or incomplete diagnostic must not become an automatic PASS.
"""
import re

PREFIX = 'EDU_GOAL_DIAG'
START = 'global.eon_private_edu_diag_start_date'
PREVIOUS = 'global.eon_private_edu_diag_previous_date'
DAY_FLAG = 'eon_private_edu_diag_natural_day'


def build_diagnostic(namespace, marker, *, terminal_effect=''):
    """Return private fixtures, atomic OBS labels, entry and verdict contract.

    goal support is judged separately from the core assertions, and only after
    positive native membership, clocks and mutation controls are established.
    """
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', namespace):
        raise ValueError('Invalid private namespace')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', marker):
        raise ValueError('Invalid diagnostic marker')
    GOAL = namespace + '_edu_identity_v12'
    CONTROL = namespace + '_edu_control_v12'
    BASE = namespace + '_faction_identity_diagnostic'
    observations = []
    events = {}

    def label(part):
        return PREFIX + '_' + part

    def obs(part, values):
        name = label(part)
        if name in observations:
            raise ValueError('Duplicate observation: ' + name)
        observations.append(name)
        return f'log = "{marker} OBS {name} {values}" '

    def boolean(part, predicate):
        name = label(part)
        if name in observations:
            raise ValueError('Duplicate observation: ' + name)
        observations.append(name)
        return (f'if = {{ limit = {{ {predicate} }} log = "{marker} OBS {name} value=1" }} '
                f'else = {{ log = "{marker} OBS {name} value=0" }} ')

    def scope(tag, body):
        return tag + ' = { ' + body + '} '

    def schedule(number):
        return scope('NEP', f'country_event = {{ id = {namespace}.{number} hours = 12 }} ')

    def state(stage):
        body = obs(stage + '_NAMES', 'usa=[USA.GetFactionName] pol=[POL.GetFactionName]')
        for tag in ('USA', 'POL'):
            for suffix, predicate in (
                ('EXISTS', 'exists = yes'),
                ('IN_FACTION', 'is_in_faction = yes'),
                ('LEADER', 'is_faction_leader = yes'),
                ('NATO_TEMPLATE', 'has_faction_template = faction_template_nato'),
                ('IDENTITY', f'has_faction_goal = {GOAL}'),
                ('CONTROL', f'has_faction_goal = {CONTROL}'),
            ):
                body += boolean(stage + '_' + tag + '_' + suffix, scope(tag, predicate))
            leader_obs = obs(stage + '_' + tag + '_LEADER_TOKEN', 'token=[?THIS.id]')
            body += ('if = { limit = { ' + scope(tag, 'is_in_faction = yes') + '} ' +
                     scope(tag, scope('faction_leader', leader_obs)) + '} '
                     f'else = {{ log = "{marker} OBS {label(stage + "_" + tag + "_LEADER_TOKEN")} token=0" }} ')
        body += boolean(stage + '_SHARED_FACTION', scope('POL', 'is_in_faction_with = USA'))
        return body

    def clock(stage, *, initial=False):
        body = obs(stage + '_CLOCK', f'raw=[?global.date] start=[?{START}] previous=[?{PREVIOUS}]')
        if not initial:
            body += boolean(stage + '_CLOCK_ADVANCED',
                            f'check_variable = {{ var = global.date value = {PREVIOUS} compare = greater_than }} ')
        body += boolean(stage + '_ONE_DAY_FLAG_ACTIVE', 'has_global_flag = ' + DAY_FLAG)
        body += f'set_variable = {{ {PREVIOUS} = global.date }} '
        return body

    actual_pair = scope('USA', 'exists = yes is_in_faction = yes ') + scope('POL', 'exists = yes is_in_faction = yes is_in_faction_with = USA ')
    actual_founder_pair = scope('USA', 'exists = yes is_in_faction = yes is_faction_leader = yes ') + scope('POL', 'exists = yes is_in_faction = yes is_in_faction_with = USA ')
    add_both = f'add_faction_goal = {GOAL} add_faction_goal = {CONTROL} '
    remove_both = f'remove_faction_goal = {GOAL} remove_faction_goal = {CONTROL} '

    body = boolean('HAS_NO_COMPROMISE_NO_SURRENDER', 'has_dlc = "No Compromise, No Surrender" ')
    body += f'set_variable = {{ {START} = global.date }} '
    body += f'set_global_flag = {{ flag = {DAY_FLAG} days = 1 value = 1 }} '
    body += clock('START', initial=True)
    body += boolean('START_ACTUAL_FOUNDER_PAIR', actual_founder_pair)
    body += 'if = { limit = { ' + actual_founder_pair + '} ' + scope('USA', remove_both) + '} '
    body += state('BEFORE_ADD')
    body += 'if = { limit = { ' + actual_founder_pair + '} ' + scope('USA', add_both) + '} '
    body += state('AFTER_ADD') + schedule(1001)
    events[1000] = body

    body = clock('WAIT') + state('AFTER_WAIT')
    body += boolean('TRANSFER_PRECONDITION', actual_pair)
    body += scope('POL', 'if = { limit = { exists = yes is_in_faction = yes is_in_faction_with = USA } set_faction_leader = yes } ')
    body += state('AFTER_TRANSFER') + schedule(1002)
    events[1001] = body

    body = clock('TRANSFER_WAIT') + state('AFTER_TRANSFER_WAIT')
    body += boolean('DISMANTLE_PRECONDITION', scope('POL', 'exists = yes is_in_faction = yes is_faction_leader = yes ') + scope('USA', 'exists = yes is_in_faction = yes is_in_faction_with = POL '))
    body += scope('POL', 'if = { limit = { exists = yes is_in_faction = yes is_faction_leader = yes USA = { is_in_faction_with = POL } } dismantle_faction = yes } ')
    body += state('AFTER_DISMANTLE') + schedule(1003)
    events[1002] = body

    body = clock('DISMANTLE_WAIT') + state('AFTER_DISMANTLE_WAIT')
    factionless_pair = scope('USA', 'exists = yes is_in_faction = no ') + scope('POL', 'exists = yes is_in_faction = no ')
    body += boolean('RECREATE_PRECONDITION', factionless_pair)
    body += 'if = { limit = { ' + factionless_pair + '} '
    body += scope('USA', 'create_faction_from_template = faction_template_nato if = { limit = { is_in_faction = yes is_faction_leader = yes } add_to_faction = POL } ')
    body += '} ' + state('AFTER_RECREATE')
    body += 'if = { limit = { ' + actual_founder_pair + '} ' + scope('USA', add_both) + '} '
    body += state('AFTER_READD')
    body += 'if = { limit = { ' + actual_founder_pair + '} ' + scope('USA', remove_both) + '} '
    body += state('AFTER_REMOVE') + schedule(1004)
    events[1003] = body

    body = clock('FINAL') + state('FINAL')
    body += obs('END', 'diagnostic_only=1 core_assertions_unchanged=1')
    body += terminal_effect
    events[1004] = body

    def goal(ident, visible):
        return (f'{ident} = {{\n name = {ident}_name\n description = {ident}_desc\n'
                ' category = medium_term\n group = FOCUS_FILTER_WAR_SUPPORT\n'
                f' visible = {{ always = {visible} }}\n available = {{ always = yes }}\n'
                ' completed = { always = no }\n cancel = { always = no }\n'
                ' ai_will_do = { factor = 0 }\n}\n')

    goal_text = goal(GOAL, 'no') + goal(CONTROL, 'yes')
    event_text = f'add_namespace = {namespace}\n' + ''.join(
        f'country_event = {{ id = {namespace}.{number} hidden = yes is_triggered_only = yes immediate = {{ {body} }} }}\n'
        for number, body in sorted(events.items()))
    fixture = {
        f'common/factions/goals/{BASE}.txt': goal_text,
        f'events/{BASE}.txt': event_text,
        f'localisation/english/{BASE}_l_english.yml':
            '\ufeffl_english:\n' + f' {GOAL}_name: "Private founding charter diagnostic"\n {GOAL}_desc: "Private native identity test. No gameplay reward."\n'
            + f' {CONTROL}_name: "Private visible goal control"\n {CONTROL}_desc: "Private never-completing control. No gameplay reward."\n',
        f'localisation/russian/{BASE}_l_russian.yml':
            '\ufeffl_russian:\n' + f' {GOAL}_name: "Проверка учредительной хартии"\n {GOAL}_desc: "Изолированная проверка идентичности альянса. Без игровых наград."\n'
            + f' {CONTROL}_name: "Видимая контрольная цель"\n {CONTROL}_desc: "Изолированная постоянная цель. Без игровых наград."\n',
    }
    stages_true = ['AFTER_ADD', 'AFTER_WAIT', 'AFTER_TRANSFER', 'AFTER_TRANSFER_WAIT', 'AFTER_READD']
    stages_false = ['BEFORE_ADD', 'AFTER_DISMANTLE', 'AFTER_DISMANTLE_WAIT', 'AFTER_RECREATE', 'AFTER_REMOVE', 'FINAL']
    return {
        'diagnostic_only': True,
        'fixture_text': fixture,
        'observations': observations,
        'entry_event_id': 1000,
        'terminal_event_id': 1004,
        'entry_effect': scope('NEP', f'country_event = {{ id = {namespace}.1000 hours = 2 }} '),
        'contract': {
            'schema': 1,
            'unsupported_is_not_core_failure_or_pass': True,
            'goal_id': GOAL,
            'visible_control_goal_id': CONTROL,
            'no_dlc_label': label('HAS_NO_COMPROMISE_NO_SURRENDER'),
            'clock_labels': [label(stage + '_CLOCK') for stage in ('START', 'WAIT', 'TRANSFER_WAIT', 'DISMANTLE_WAIT', 'FINAL')],
            'clock_advance_labels': [label(stage + '_CLOCK_ADVANCED') for stage in ('WAIT', 'TRANSFER_WAIT', 'DISMANTLE_WAIT', 'FINAL')],
            'required_delay_hours': 12,
            'natural_flag_positive_labels': [label('START_ONE_DAY_FLAG_ACTIVE')],
            'natural_flag_negative_labels': [label('FINAL_ONE_DAY_FLAG_ACTIVE')],
            'required_native_preconditions': [label(stage) for stage in ('START_ACTUAL_FOUNDER_PAIR', 'TRANSFER_PRECONDITION', 'DISMANTLE_PRECONDITION', 'RECREATE_PRECONDITION')],
            'structure_positive_labels': [label(stage + '_' + tag + '_IN_FACTION')
                                         for stage in ('AFTER_ADD', 'AFTER_WAIT', 'AFTER_TRANSFER', 'AFTER_TRANSFER_WAIT', 'AFTER_RECREATE', 'AFTER_READD', 'AFTER_REMOVE', 'FINAL')
                                         for tag in ('USA', 'POL')]
                                        + [label(stage + '_SHARED_FACTION') for stage in ('AFTER_ADD', 'AFTER_WAIT', 'AFTER_TRANSFER', 'AFTER_TRANSFER_WAIT', 'AFTER_RECREATE', 'AFTER_READD', 'AFTER_REMOVE', 'FINAL')]
                                        + [label(stage + '_POL_LEADER') for stage in ('AFTER_TRANSFER', 'AFTER_TRANSFER_WAIT')]
                                        + [label(stage + '_USA_LEADER') for stage in ('AFTER_RECREATE', 'AFTER_READD', 'AFTER_REMOVE', 'FINAL')],
            'structure_negative_labels': [label(stage + '_' + tag + '_IN_FACTION') for stage in ('AFTER_DISMANTLE', 'AFTER_DISMANTLE_WAIT') for tag in ('USA', 'POL')]
                                        + [label(stage + '_SHARED_FACTION') for stage in ('AFTER_DISMANTLE', 'AFTER_DISMANTLE_WAIT')]
                                        + [label(stage + '_USA_LEADER') for stage in ('AFTER_TRANSFER', 'AFTER_TRANSFER_WAIT')]
                                        + [label(stage + '_POL_LEADER') for stage in ('AFTER_RECREATE', 'AFTER_READD', 'AFTER_REMOVE', 'FINAL')],
            'marker_positive_labels': [label(stage + '_' + tag + '_IDENTITY') for stage in stages_true for tag in ('USA', 'POL')],
            'marker_negative_labels': [label(stage + '_' + tag + '_IDENTITY') for stage in stages_false for tag in ('USA', 'POL')],
            'control_positive_labels': [label(stage + '_' + tag + '_CONTROL') for stage in stages_true for tag in ('USA', 'POL')],
            'control_negative_labels': [label(stage + '_' + tag + '_CONTROL') for stage in stages_false for tag in ('USA', 'POL')],
            'native_effects': ['add_faction_goal', 'remove_faction_goal', 'set_faction_leader', 'dismantle_faction', 'create_faction_from_template', 'add_to_faction', 'country_event', 'set_global_flag', 'set_variable', 'log'],
            'native_triggers': ['has_faction_goal', 'exists', 'is_in_faction', 'is_faction_leader', 'is_in_faction_with', 'has_faction_template', 'has_global_flag', 'has_dlc', 'check_variable'],
            'limits': [
                'Characterizes one private NATO faction only; does not implement EDU identity or native decision context.',
                'Goal APIs may be disabled without NCNS; atomic observations must distinguish unsupported marker from failed structural/time controls.',
                'Twelve-hour scheduled phases require independently observed raw logger time/date advance; an event label alone is not elapsed-time proof.',
                'Private never-completing visible control separates hidden definition visibility from marker storage capability.',
                'No save/reload, same-tick faction merge, native GUI goal removal, multiplayer or campaign proof.',
            ],
        },
    }
