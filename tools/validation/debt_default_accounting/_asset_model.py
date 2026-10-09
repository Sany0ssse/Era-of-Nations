"""Execute the real asset AST with country/state frames and shared temps.

Building removal and timers are native boundaries. This fixture independently
tracks stock and can reject a failed removal. Economic refresh stays opaque;
ordinary AI/income, asynchronous callbacks and actual UI need native evidence.
"""
from contextlib import contextmanager
from copy import deepcopy
import _model as m


class AssetModel(m.Model):
    def __init__(self, *args, states=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.states = deepcopy(states or [])
        self.frames = [('country', None)]
        self.removals = []

    @contextmanager
    def frame(self, kind, state=None):
        self.frames.append((kind, state))
        try:
            yield
        finally:
            self.frames.pop()

    def value(self, key):
        try:
            return float(key)
        except (TypeError, ValueError):
            pass
        if key in self.temp:
            return self.temp[key]
        kind, state = self.frames[-1]
        if kind == 'state':
            if key in ('THIS.id', 'THIS'):
                return state['id']
            if isinstance(key, str) and key.startswith('building_level@'):
                return state['buildings'].get(key.split('@', 1)[1], 0)
            return state.get('variables', {}).get(key, 0)
        return super().value(key)

    def trigger(self, nodes):
        for key, op, body in nodes:
            if key == 'any_owned_state':
                assert self.frames[-1][0] == 'country'
                passed = False
                for state in self.states:
                    if state.get('owned', True):
                        with self.frame('state', state):
                            passed = self.trigger(body)
                        if passed:
                            break
            elif key == 'is_controlled_by':
                assert body == 'PREV' and self.frames[-1][0] == 'state'
                assert self.frames[-2][0] == 'country'
                passed = self.frames[-1][1].get('controlled', True)
            elif key in ('industrial_complex', 'arms_factory', 'dockyard', 'offices'):
                assert self.frames[-1][0] == 'state'
                passed = m.parser.compare(self.frames[-1][1]['buildings'].get(key, 0), op, self.value(body))
            else:
                passed = super().trigger([(key, op, body)])
            if not passed:
                return False
        return True

    def effect(self, nodes):
        # Keep parent if/else dispatch intact so nested calls use this adapter.
        for key, op, body in nodes:
            if key in ('random_owned_state', 'random_owned_controlled_state'):
                assert self.frames[-1][0] == 'country'
                for state in self.states:
                    if not state.get('owned', True):
                        continue
                    if key == 'random_owned_controlled_state' and not state.get('controlled', True):
                        continue
                    with self.frame('state', state):
                        if self.trigger(m.one(body, 'limit')):
                            self.effect([node for node in body if node[0] != 'limit'])
                            break
            elif key == 'remove_building':
                assert self.frames[-1][0] == 'state'
                state = self.frames[-1][1]
                building, amount = m.one(body, 'type'), int(m.one(body, 'level'))
                before = state['buildings'].get(building, 0)
                after = before if state.get('remove_fails', False) else max(0, before - amount)
                state['buildings'][building] = after
                self.removals.append((state['id'], building, before, after))
            elif key == 'PREV':
                assert self.frames[-1][0] == 'state' and self.frames[-2][0] == 'country'
                with self.frame('country'):
                    self.effect(body)
            else:
                # All financial/persistent writes must occur in a country.
                if key in ('set_variable', 'add_to_variable', 'subtract_from_variable',
                           'clear_variable', 'ingame_update_setup'):
                    assert self.frames[-1][0] == 'country', ('Country write in state frame', key)
                super().effect([(key, op, body)])
