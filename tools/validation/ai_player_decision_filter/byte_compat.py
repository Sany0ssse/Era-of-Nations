"""Exact inverse of the independently checked six framework root filters.

Retain the older nine-filter proof's canonical input. Reject any other edits.
"""
import hashlib

FRAMEWORK = 'common/decisions/eon_framework_negotiation_decisions.txt'
BEFORE = 'afb4dcd174b2dabff9767a5999de522a683d86883f0bc83dd92f91c39c2c8d35'
AFTER = '636357e64b16661dfc712f7cfab6469e528c899c3e947b105552f04c9fab2a8f'
OLD = b'target_root_trigger = { exists = yes }'
NEW = b'target_root_trigger = { exists = yes is_ai = no }'


def canonical_framework_view(raw):
    digest = hashlib.sha256(raw).hexdigest()
    if digest == BEFORE:
        return raw
    if digest != AFTER or raw.count(NEW) != 6:
        raise ValueError('Unreviewed framework source bytes')
    canonical = raw.replace(NEW, OLD)
    if hashlib.sha256(canonical).hexdigest() != BEFORE:
        raise ValueError('Framework six-filter inverse mismatch')
    return canonical
