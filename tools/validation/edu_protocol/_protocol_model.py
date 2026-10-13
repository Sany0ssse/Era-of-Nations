"""Strict actual production-AST protocol model. No native hook/GUI/AI proof."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/validation/aid_flag_scope'))
from _model import ast, one, compare, context, switch

HERE = ROOT


def walk(nodes):
    for key, operator, body in nodes:
        yield key, operator, body
        if isinstance(body, list):
            yield from walk(body)


class Model:
    def __init__(self):
        def load(name):
            return {k: v for k, o, v in ast((HERE / name).read_text(encoding='utf-8-sig'))}
        self.effects = load('common/scripted_effects/eon_edu_effects.txt')
        self.triggers = load('common/scripted_triggers/eon_edu_triggers.txt')
        self.decisions = one(ast((HERE / 'common/decisions/eon_edu_decisions.txt').read_text(encoding='utf-8-sig')), 'EU_voting_category')
        self.create = one(one(ast((HERE / 'common/decisions/EU_voting_decisions.txt').read_text(encoding='utf-8-sig')), 'EU_defense_category'), 'EU_create_EDU')
        self.events_source = ast((HERE / 'events/eon_edu_events.txt').read_text(encoding='utf-8-sig'))
        self.c = {i: {'vars': {}, 'flags': {}, 'ideas': {'EU_member'}, 'active': True,
                     'exists': True, 'subject': False, 'offensive': False, 'join': True,
                     'neutral': False, 'threshold': 0, 'faction': None, 'ai': False,
                     'influence': True, 'create_fail': False, 'join_fail': False}
                  for i in range(1, 6)}
        self.c[1]['ideas'].update({'European_Security_Council', 'EU_foreign_minister'})
        self.g, self.gf, self.factions, self.day = {'threat': 1}, set(), {}, 0
        self.events, self.news, self.logs, self.boundaries = [], [], [], []
        self.formation_mode = 'synchronous'
        self.native_formation_hooks = True
        self.deferred_formations = []
        self.temp = {}
        self.native_leave_hooks = True
        self.native_leadership_hooks = True
        self.union_active = True

    def val(self, key, frame):
        try: return float(key)
        except (TypeError, ValueError): pass
        if key == 'ROOT': return frame['root']
        if key == 'FROM': return frame['from']
        if key == 'THIS': return frame['scope']
        if key == 'PREV': return frame['prev'][0]
        if key.startswith('var:'): return self.val(key[4:], frame)
        if key == 'modifier@join_faction_tension': return self.c[frame['scope']]['threshold']
        if key.startswith('global.'): return self.g.get(key[7:], 0)
        if '.' in key:
            prefix, name = key.split('.', 1)
            return self.val(name, switch(frame, self.val(prefix, frame)))
        if key == 'id': return frame['scope']
        if key in self.temp: return self.temp[key]
        return self.c.get(frame['scope'], {}).get('vars', {}).get(key, 0)

    def write(self, key, val, frame):
        if key.startswith('global.'): self.g[key[7:]] = val
        elif '.' in key:
            prefix, name = key.split('.', 1)
            self.write(name, val, switch(frame, self.val(prefix, frame)))
        else: self.c[frame['scope']]['vars'][key] = val

    def flag(self, country, name):
        expires = country['flags'].get(name, -1)
        return expires is None or expires > self.day

    def same(self, actor, target):
        a, b = self.c.get(actor, {}), self.c.get(target, {})
        return a.get('faction') is not None and a.get('faction') == b.get('faction')

    def leader(self, actor):
        faction = self.c[actor]['faction']
        return self.factions[faction]['leader'] if faction is not None else None

    def trigger(self, nodes, frame):
        for key, op, body in nodes:
            c = self.c.get(frame['scope'], {})
            if key in self.triggers: ok = self.trigger(self.triggers[key], frame) == (body == 'yes')
            elif key in ('AND', 'custom_trigger_tooltip', 'hidden_trigger'): ok = self.trigger([n for n in body if n[0] != 'tooltip'], frame)
            elif key == 'OR': ok = any(self.trigger([n], frame) for n in body)
            elif key == 'NOT': ok = not self.trigger(body, frame)
            elif key == 'if': ok = not self.trigger(one(body,'limit'), frame) or self.trigger([n for n in body if n[0] != 'limit'], frame)
            elif key == 'always': ok = body == 'yes'
            elif key == 'exists': ok = c.get('exists', False) == (body == 'yes')
            elif key == 'is_subject': ok = c.get('subject', False) == (body == 'yes')
            elif key == 'is_ai': ok = c.get('ai', False) == (body == 'yes')
            elif key == 'has_offensive_war': ok = c.get('offensive', False) == (body == 'yes')
            elif key == 'is_in_faction': ok = (c.get('faction') is not None) == (body == 'yes')
            elif key == 'is_faction_leader': ok = (bool(c) and self.leader(frame['scope']) == frame['scope']) == (body == 'yes')
            elif key == 'is_in_faction_with': ok = self.same(frame['scope'], self.val(body, frame))
            elif key == 'has_idea': ok = body in c.get('ideas', set())
            elif key == 'has_rule':
                assert body == 'can_join_factions', 'no creator permission bypass assumed'
                ok = c.get('join',False)
            elif key == 'set_temp_variable':
                name,_,source=body[0]; self.temp[name]=self.val(source,frame); ok=True
            elif key == 'has_country_flag': ok = self.flag(c, body)
            elif key == 'has_global_flag': ok = body in self.gf
            elif key == 'eon_eu_is_active_member':
                self.boundaries.append(key)
                ok = c.get('exists', False) and c.get('active', False) and 'EU_member' in c['ideas'] and not c['subject']
                ok = ok == (body == 'yes')
            elif key == 'eon_eu_union_active': ok = self.union_active == (body == 'yes')
            elif key == 'any_owned_state': ok = c.get('owned',True) and self.trigger(body,frame)
            elif key == 'has_faction_template':
                fid=c.get('faction'); ok=fid is not None and self.factions[fid].get('template')==body
            elif key == 'eon_defensive_alliance_member_eligible':
                self.boundaries.append(key)
                ok = c.get('exists', False) and not c['subject'] and c['faction'] is None and c['join'] and not c['offensive'] and not c['neutral'] and self.g['threat'] >= c['threshold']
                ok = ok == (body == 'yes')
            elif key == 'influence_on_all_other_EU_members_25_percent': ok = c['influence'] == (body == 'yes')
            elif key == 'has_opinion':
                target = self.val(one(body, 'target'), frame)
                value = next(n for n in body if n[0] == 'value')
                ok = compare(c.get('opinions', {}).get(target, 20), value[1], float(value[2]))
            elif key == 'check_variable':
                if any(n[0] == 'var' for n in body):
                    left, right = one(body, 'var'), one(body, 'value')
                    operation = next((n[2] for n in body if n[0] == 'compare'), 'equals')
                    op = {'equals': '=', 'not_equals': '!=', 'greater_than': '>', 'greater_than_or_equals': '>=', 'less_than': '<', 'less_than_or_equals': '<='}[operation]
                else: left, op, right = body[0]
                ok = compare(self.val(left, frame), op, self.val(right, frame))
            elif key == 'any_country': ok = any(self.trigger(body, switch(frame, i)) for i in self.c)
            elif key == 'faction_leader':
                target = self.leader(frame['scope'])
                ok = target in self.c and self.trigger(body, switch(frame, target))
            elif key in ('ROOT', 'FROM', 'THIS', 'PREV') or key.startswith('var:'):
                target = self.val(key, frame)
                ok = target in self.c and self.trigger(body, switch(frame, target))
            else: raise AssertionError(('unmodeled production trigger', key, body))
            if not ok: return False
        return True

    def effect(self, nodes, frame):
        pos = 0
        while pos < len(nodes):
            key, op, body = nodes[pos]; pos += 1
            c = self.c.get(frame['scope'], {})
            if key == 'if':
                branches = [('if', body)]
                while pos < len(nodes) and nodes[pos][0] in ('else_if', 'else'):
                    branches.append((nodes[pos][0], nodes[pos][2])); pos += 1
                for kind, block in branches:
                    if kind == 'else' or self.trigger(one(block, 'limit'), frame):
                        self.effect([n for n in block if n[0] != 'limit'], frame); break
            elif key in self.effects: self.effect(self.effects[key], frame)
            elif key in ('set_temp_variable','add_to_temp_variable'):
                name,_,source=body[0]; value=self.val(source,frame)
                self.temp[name]=value if key=='set_temp_variable' else self.temp.get(name,0)+value
            elif key in ('set_variable', 'add_to_variable', 'clear_variable'):
                if key == 'clear_variable': self.write(body, 0, frame)
                else:
                    name, _, source = body[0]; val = self.val(source, frame)
                    self.write(name, val if key == 'set_variable' else self.val(name, frame) + val, frame)
            elif key in ('set_global_flag', 'clr_global_flag'):
                self.gf.add(body) if key == 'set_global_flag' else self.gf.discard(body)
            elif key == 'set_country_flag':
                if isinstance(body, list):
                    assert one(body, 'value') == '1', 'timed flags must have positive value'
                    c['flags'][one(body, 'flag')] = self.day + int(one(body, 'days'))
                else: c['flags'][body] = None
            elif key == 'clr_country_flag': c['flags'].pop(body, None)
            elif key in ('ROOT', 'FROM', 'THIS', 'PREV') or key.startswith('var:'):
                target = self.val(key, frame)
                if target in self.c: self.effect(body, switch(frame, target))
            elif key == 'faction_leader':
                target = self.leader(frame['scope'])
                if target in self.c: self.effect(body, switch(frame, target))
            elif key in ('every_country', 'every_possible_country'):
                for target in self.c:
                    limits = [n[2] for n in body if n[0] == 'limit']
                    if not limits or self.trigger(limits[0], switch(frame, target)):
                        self.effect([n for n in body if n[0] != 'limit'], switch(frame, target))
            elif key == 'every_faction_member':
                for target in list(self.c):
                    if self.same(frame['scope'], target): self.effect(body, switch(frame, target))
            elif key == 'create_faction_from_template':
                self.boundaries.append(('native_create_unproved', frame['scope'], body))
                if c['faction'] is None and not c['create_fail']:
                    fid = max(self.factions, default=0) + 1
                    self.factions[fid] = {'leader': frame['scope']}; c['faction'] = fid
                    if self.native_formation_hooks:
                        if self.formation_mode == 'synchronous': self.run('eon_edu_on_formed', frame['scope'])
                        else: self.deferred_formations.append(frame['scope'])
            elif key == 'add_to_faction':
                target = self.val(body, frame)
                self.boundaries.append(('native_add_unproved', frame['scope'], target))
                if target in self.c and self.leader(frame['scope']) == frame['scope'] and self.c[target]['faction'] is None and not self.c[target]['join_fail']:
                    self.c[target]['faction'] = c['faction']
            elif key == 'set_faction_leader':
                self.boundaries.append(('native_leader_transfer_unproved',frame['scope']))
                if c['faction'] is not None and not c.get('transfer_fail',False):
                    old=self.leader(frame['scope']); self.factions[c['faction']]['leader']=frame['scope']
                    if self.native_leadership_hooks:self.run('eon_edu_on_assume_leadership',frame['scope'],old)
            elif key == 'remove_from_faction':
                target=self.val(body,frame); self.boundaries.append(('native_remove_unproved',frame['scope'],target))
                # Declared conservative model policy: actual same-faction leader
                # removes the member. Not a claim of universal engine semantics.
                if (target in self.c and self.leader(frame['scope']) == frame['scope']
                        and self.same(frame['scope'], target)
                        and not self.c[target].get('remove_fail',False)):
                    old=self.leader(target); self.c[target]['faction']=None
                    if self.native_leave_hooks:self.run('eon_edu_on_leave',target,old)
            elif key == 'dismantle_faction':
                self.boundaries.append(('native_dismantle_unproved',frame['scope']))
                if self.leader(frame['scope'])==frame['scope'] and not c.get('dismantle_fail',False):
                    members=[i for i in self.c if self.same(frame['scope'],i)]
                    for target in members:
                        self.c[target]['faction']=None
                        if self.native_leave_hooks:self.run('eon_edu_on_leave',target,frame['scope'])
            elif key == 'country_event': self.events.append((frame['scope'], one(body, 'id')))
            elif key == 'news_event': self.news.append((frame['scope'], one(body, 'id')))
            elif key == 'log': self.logs.append((frame['root'], frame['scope'], frame['from'], body))
            elif key in ('custom_effect_tooltip', 'hidden_effect'):
                if isinstance(body, list): self.effect(body, frame)
            else: raise AssertionError(('unmodeled production effect', key, body))

    def run(self, name, actor=1, target=None):
        self.effect(self.effects[name], context(actor, actor, target))

    def decision(self, name, actor=1, target=None):
        body = self.create if name == 'EU_create_EDU' else one(self.decisions, name)
        self.effect(one(body, 'complete_effect'), context(actor, actor, target))

    def available(self, name, actor=1, target=None):
        body = self.create if name == 'EU_create_EDU' else one(self.decisions, name)
        return self.trigger(one(body, 'available'), context(actor, actor, target))

    def ai_weight(self, name, actor, target):
        body = one(one(self.decisions, name), 'ai_will_do')
        weight = float(one(body, 'factor'))
        for key, op, modifier in body:
            if key == 'modifier' and self.trigger([n for n in modifier if n[0] != 'factor'], context(actor, actor, target)):
                weight *= float(one(modifier, 'factor'))
        return weight

    def make_foreign_faction(self, leader, members=()):
        fid = max(self.factions, default=0) + 1
        self.factions[fid] = {'leader': leader}
        for i in (leader, *members): self.c[i]['faction'] = fid
        return fid

    def expire(self, days):
        self.day += days
        self.run('eon_edu_daily_pulse')

    def deliver_formed(self):
        actor = self.deferred_formations.pop(0)
        self.run('eon_edu_on_formed', actor)

    def begin_interrupted_constructor(self, actor=1, target=None):
        """Declared interruption fixture: execute exact source through constructor,
        then pause before its return continuation. This is not a native scheduler.
        """
        assert self.formation_mode == 'deferred'
        root = one(self.effects['eon_edu_create_decision_effect'], 'ROOT')
        branch = next(body for key, op, body in root if key == 'if')
        end = next(i for i, node in enumerate(branch) if node[0] == 'create_faction_from_template')
        prefix = [node for node in root if node[0] != 'if']
        prefix.append(('if', '=', branch[:end + 1]))
        self.boundaries.append(('interrupted_constructor_fixture', actor))
        self.effect([('ROOT', '=', prefix)], context(actor, actor, target))

    def leave(self, actor, *, hook=True):
        self.c[actor]['faction'] = None
        if hook: self.run('eon_edu_on_leave', actor)
