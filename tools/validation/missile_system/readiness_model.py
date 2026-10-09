"""Evaluate the actual arsenal readiness source, with an explicit prototype fixture.

The shipped prototype is disabled. Tests exercising its retained safety contract
must opt in; a stale safety/recovery value cannot block a production launch.
"""
from functools import lru_cache


@lru_cache(maxsize=1)
def source():
    # Lazy import avoids a parser/model cycle when test_launch is the entry point.
    from test_launch import one, read
    nodes = read('common/scripted_triggers/eon_nuclear_arsenal_triggers.txt')
    return (one(nodes, 'eon_nuclear_arsenal_enabled'),
            one(nodes, 'eon_nuclear_arsenal_ready'))


def is_ready(country_ready=True, flags=(), recovery=0, prototype_enabled=None):
    enabled_source, ready_source = source()
    flags = set(flags)
    if not country_ready:
        flags.add('eon_nuclear_arsenal_safety_mode')

    def evaluate(nodes):
        checks = []
        for key, op, value in nodes:
            assert op == '=', (key, op)
            if key == 'tooltip':
                continue
            if key in ('custom_override_tooltip', 'AND'):
                allowed = evaluate(value)
            elif key == 'OR':
                allowed = any(evaluate([node]) for node in value)
            elif key == 'NOT':
                allowed = not evaluate(value)
            elif key == 'always':
                allowed = value == 'yes'
            elif key == 'eon_nuclear_arsenal_enabled':
                enabled = evaluate(enabled_source) if prototype_enabled is None else prototype_enabled
                allowed = enabled == (value == 'yes')
            elif key == 'has_country_flag':
                allowed = value in flags
            elif key == 'check_variable':
                assert value == [('eon_nuclear_arsenal_recovery_remaining', '>', '0')]
                allowed = recovery > 0
            else:
                raise AssertionError(('Unsupported readiness source', key, value))
            checks.append(allowed)
        return all(checks)

    return evaluate(ready_source)


def assert_default_off_contract():
    assert source()[0] == [('always', '=', 'no')], 'Production must keep the incomplete prototype disabled'
    for safety in (False, True):
        for recovery in (0, 1, 4):
            flags = {'eon_nuclear_arsenal_safety_mode'} if safety else set()
            assert is_ready(not safety, flags, recovery), 'Default-off readiness must ignore stale prototype state'
            assert is_ready(not safety, flags, recovery, True) == (not safety and recovery == 0)
