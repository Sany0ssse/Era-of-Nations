"""Execute the actual selected GUI/mission AST, never an engine/campaign claim."""
from pathlib import Path
import json, os, sys, unittest

ROOT = Path(os.environ.get('EON_WORKSPACE_ROOT', Path(__file__).resolve().parents[3])).resolve()
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools/validation/eu_voting'))
from test_voting import VoteModel, ast, one, source_path
from test_flows import compare

# Public default is the actual authoritative game source; caller may select a
# separate candidate path for pre-promotion checks.
SOURCE = ROOT

def read(path, source=None):
    source = SOURCE if source is None else source
    return ast(source_path(path, source).read_text(encoding='utf-8-sig'))

def gui_parts():
    gui = one(read('common/scripted_guis/01_european_union_guis.txt'), 'scripted_gui')
    council = one(gui, 'european_council_voting_dynamic_lists')
    return one(council, 'triggers'), one(council, 'effects')

def mission(ident):
    return one(one(read('common/decisions/EU_voting_decisions.txt'), 'EU_voting_category'), ident)

def walk(nodes):
    for node in nodes:
        yield node
        if isinstance(node[2], list): yield from walk(node[2])

class FrontModel(VoteModel):
    def __init__(self):
        super().__init__(6, source=SOURCE)
        # This frontend constructs a fresh proposal/legacy fixture; inherited
        # VoteModel's declared open core fixture must not seed a hidden round.
        for key in list(self.global_vars):
            if key.startswith('eon_eu_council_'): self.global_vars.pop(key)
        self.global_flags.discard('eon_eu_council_vote_clock_started')
        self.global_flags.discard('eon_eu_council_vote_deadline')
        self.native_receipts = []
        for filename in ('common/scripted_effects/99_EU_voting_scripted_effects.txt',):
            self.effects.update({k: v for k, op, v in read(filename, ROOT)})
        for filename in ('common/scripted_effects/eon_eu_voting_effects.txt', 'common/scripted_effects/eon_eu_handoff_effects.txt'):
            if source_path(filename, SOURCE).exists(): self.effects.update({k: v for k, op, v in read(filename)})
        for filename in ('common/scripted_triggers/eon_eu_voting_triggers.txt', 'common/scripted_triggers/eon_eu_handoff_triggers.txt'):
            if source_path(filename, SOURCE).exists(): self.triggers.update({k: v for k, op, v in read(filename)})
        self.gui_triggers, self.gui_effects = gui_parts()
        self.global_vars.update(current_active_vote_disp=0, eucomission=self.countries[2].pointer)
        self.global_arrays['EU_council_votes'] = [101, 401]
        self.countries[2].ideas.add('EU_commission_president')
        self.global_flags.add('eon_eu_admission_guard_ready')
        for c in self.countries.values():
            c.ai = False  # AI weighting is its separately tested literal dispatcher boundary.
            c.missions = set()
            c.mission_days = {}
            c.variables.update(political_power=2000, eurosceptic=.1, EU_pop_ratio=1/6)
            if 'EU_member' in c.ideas: c.flags.add('eon_eu_membership_recognized')
        self.temp['v'] = 101
        self.required('eon_eu_recount_council_vote')

    def scope(self, token, stack):
        if token == 'SOV': return self.countries[7]
        return super().scope(token, stack)

    def value(self, token, stack):
        if token.startswith('days_mission_timeout@'):
            return stack[-1].mission_days.get(token.split('@', 1)[1], 0)
        return super().value(token, stack)

    def trigger(self, nodes, stack):
        index = 0
        while index < len(nodes):
            key, op, value = nodes[index]; index += 1
            if key == 'tooltip': continue
            if key == 'is_ai': passed = stack[-1].ai == (value == 'yes')
            elif key == 'has_active_mission': passed = value in stack[-1].missions
            elif key == 'any_country':
                passed = any(c.exists and self.trigger(value, stack + [c]) for c in self.countries.values())
            elif key == 'has_political_power': passed = compare(stack[-1].variables['political_power'], op, self.value(value, stack))
            elif key == 'SOV':
                target = self.scope(key, stack)
                passed = target is not None and self.trigger(value, stack + [target])
            elif key in ('EU_external_chi_influence_15', 'EU_external_sov_influence_15'):
                # Existing foreign-influence policy is an input receipt, not invented here.
                passed = getattr(stack[-1], key, False) == (value == 'yes')
            elif key == 'influence_on_all_other_EU_members_3_percent':
                passed = getattr(stack[-1], 'proposal_influence', False) == (value == 'yes')
            elif key in ('clamp_temp_variable', 'divide_temp_variable'):
                self.effect([(key, op, value)], stack); passed = True
            elif key == 'any_of':
                name, label = one(value, 'array'), one(value, 'value')
                items = self.global_arrays.get(name.removeprefix('global.'), [])
                body = [n for n in value if n[0] not in ('array', 'value')]
                passed = False
                for item in items:
                    self.temp[label] = item
                    if self.trigger(body, stack): passed = True; break
            elif key == 'if':
                branches, index = self.branches(nodes, index, value)
                passed = True
                for kind, branch in branches:
                    if kind == 'else' or self.trigger(one(branch, 'limit'), stack):
                        passed = self.trigger([n for n in branch if n[0] != 'limit'], stack); break
            else: passed = super().trigger([(key, op, value)], stack)
            if not passed: return False
        return True

    def effect(self, nodes, stack):
        index = 0
        while index < len(nodes):
            key, op, value = nodes[index]; index += 1
            if key in ('log', 'custom_effect_tooltip', 'effect_tooltip'): continue
            if key == 'meta_effect':
                self.native_receipts.append(('LOCALIZED_META_NOT_EXECUTED', value)); continue
            if key == 'hidden_effect': self.effect(value, stack); continue
            if key == 'add_political_power':
                stack[-1].variables['political_power'] += self.value(value, stack); continue
            if key in ('activate_mission', 'remove_mission'):
                self.native_receipts.append((key, stack[-1].ident, value))
                if key == 'activate_mission':
                    stack[-1].missions.add(value); stack[-1].mission_days[value] = 14
                else:
                    stack[-1].missions.discard(value); stack[-1].mission_days.pop(value, None)
                continue
            if key == 'country_event':
                self.native_receipts.append(('country_event', stack[-1].ident, one(value, 'id'))); continue
            if key == 'add_ideas': stack[-1].ideas.add(value); continue
            if key == 'set_the_eu_council_delay':
                self.native_receipts.append(('set_the_eu_council_delay', stack[-1].ident)); continue
            if key == 'add_days_mission_timeout':
                ident, days = one(value, 'mission'), self.value(one(value, 'days'), stack)
                self.native_receipts.append(('add_days_mission_timeout', stack[-1].ident, ident, days))
                stack[-1].mission_days[ident] += days
                continue
            if key == 'set_global_flag' and isinstance(value, list):
                concrete = [(k, op, str(self.value(v, stack)) if k == 'days' else v) for k, op, v in value]
                super().effect([(key, op, concrete)], stack); continue
            if key == 'for_each_scope_loop':
                name = one(value, 'array')
                for pointer in list(self.global_arrays.get(name.removeprefix('global.'), [])):
                    target = next((c for c in self.countries.values() if c.pointer == pointer), None)
                    if target is not None: self.effect([n for n in value if n[0] != 'array'], stack + [target])
                continue
            if key == 'every_possible_country':
                for target in self.countries.values(): self.effect(value, stack + [target])
                continue
            group = [(key, op, value)]
            if key == 'if':
                while index < len(nodes) and nodes[index][0] in ('else_if', 'else'):
                    group.append(nodes[index]); index += 1
            super().effect(group, stack)

    def click(self, key, actor=1, target=None):
        self.root = self.countries[actor]
        self.effect(one(self.gui_effects, key), [self.root] if target is None else [self.root, self.countries[target]])

    def enabled(self, key, actor=1, target=None):
        self.root = self.countries[actor]
        return self.trigger(one(self.gui_triggers, key + '_enabled'), [self.root] if target is None else [self.root, self.countries[target]])

    def timeout(self, holder=2):
        # Execute the ACTUAL production timeout AST at a declared elapsed boundary.
        # Mission scheduling and natural days progression remain native acceptance.
        self.root = self.countries[holder]
        self.global_flags.discard('eon_eu_council_vote_deadline')
        self.effect(one(mission('EU_voting_mission_focus_EUXXX_QMV_result'), 'timeout_effect'), [self.root])


P, S = 'eu_council_available_reforms_button_click', 'eu_council_voting_members_list_button_click'
