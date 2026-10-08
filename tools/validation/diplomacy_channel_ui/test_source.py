"""Additive boundaries and native-evidenced primitive regressions."""
import re
import subprocess
import unittest

import _support as s
from test_lifecycle import ACTIONS, DECISIONS, EVENTS

BASELINE = 'f2832b6bfd980066163d0a69a6306169c992c5d7'
LEGACY = [
    'common/scripted_triggers/eon_consultation_triggers.txt',
    'common/scripted_effects/eon_consultation_effects.txt',
    'common/scripted_diplomatic_actions/eon_consultation_actions.txt',
    'common/on_actions/eon_consultation_on_actions.txt',
    'events/eon_consultation_events.txt',
]

def old_bytes(path):
    return subprocess.check_output(['git', 'show', BASELINE + ':' + path], cwd=s.ROOT)

def localisation(data):
    text = data.decode('utf-8-sig')
    pairs = re.findall(r'^\s*([A-Za-z0-9_.]+):\d*\s*(".*")\s*$', text, re.M)
    assert len(pairs) == len(dict(pairs)), 'Duplicate localisation keys'
    return dict(pairs)

def walk(nodes):
    for name, op, data in nodes:
        yield name, op, data
        if isinstance(data, list):
            yield from walk(data)

class SourceTests(unittest.TestCase):
    def test_old_consultation_callbacks_and_lifecycle_are_byte_preserved(self):
        for path in LEGACY:
            self.assertEqual((s.ROOT / path).read_bytes(), old_bytes(path), path)

    def test_legacy_notice_locales_only_add_navigation_to_20_21_22(self):
        allowed = {'eon_consultation.' + str(n) + '.desc' for n in (20, 21, 22)}
        for lang in ('english', 'russian'):
            path = f'localisation/{lang}/eon_consultation_l_{lang}.yml'
            old, current = localisation(old_bytes(path)), localisation((s.ROOT / path).read_bytes())
            self.assertEqual(set(old), set(current), path)
            changed = {name for name in old if old[name] != current[name]}
            self.assertEqual(changed, allowed)
            for name in set(old) - allowed:
                self.assertEqual(current[name], old[name], name)
            for name in allowed:
                self.assertTrue(current[name].startswith(old[name][:-1]), name)

    def test_exact_additive_product_manifest_exists(self):
        self.assertEqual(len(s.UI_FILES), 11)
        for path in s.UI_FILES:
            self.assertTrue((s.ROOT / path).is_file(), path)
        self.assertEqual(set(EVENTS), {'eon_consultation_ui.1', 'eon_consultation_ui.2'})
        self.assertEqual(set(ACTIONS), {'eon_open_consultation_panel'})
        self.assertEqual(set(DECISIONS), {'eon_consultation_ui_' + name for name in (
            'status', 'end', 'trade_propose_90', 'trade_propose_180', 'trade_review',
            'trade_accept_90', 'trade_accept_180', 'trade_counter_90', 'trade_counter_180',
            'trade_decline', 'trade_withdraw', 'trade_notice', 'trade_end_request',
            'trade_end_accept', 'energy_editor', 'aid_draft', 'debt_guidance')})

    def test_panels_never_have_resource_or_state_callbacks(self):
        for event_id, body in EVENTS.items():
            self.assertNotIn('immediate', [name for name, op, data in body])
            options = [data for name, op, data in body if name == 'option']
            self.assertEqual(len(options), 1)
            self.assertEqual({name for name, op, data in options[0]}, {'name', 'ai_chance'})
            self.assertEqual(s.one(options[0], 'name'), 'eon_consultation_ui_ack')

    def test_no_duplicate_engine_cost_or_recipient_auto_assent(self):
        for name, body in {**DECISIONS, **ACTIONS}.items():
            self.assertEqual(s.one(body, 'cost'), '0', name)
            ai = s.one(body, 'ai_will_do' if name in DECISIONS else 'ai_desire')
            self.assertEqual(s.one(ai, 'factor'), '0')
        self.assertEqual(s.one(ACTIONS['eon_open_consultation_panel'], 'requires_acceptance'), 'no')

    def test_localisation_keys_resolve_in_both_shipped_languages(self):
        needed = set()
        for path in s.UI_FILES:
            if path.endswith('.txt'):
                for name, op, data in walk(s.parse((s.ROOT / path).read_text(encoding='utf-8-sig'))):
                    if name in ('title', 'text', 'tooltip', 'localization_key', 'send_description') and isinstance(data, str) and data.startswith('eon_consultation_ui'):
                        needed.add(data)
        for lang in ('english', 'russian'):
            keys = localisation((s.ROOT / f'localisation/{lang}/eon_consultation_ui_l_{lang}.yml').read_bytes())
            self.assertFalse(needed - keys.keys(), (lang, needed - keys.keys()))

    def test_native10_shared_unscoped_and_persistent_only_scoped_temp_reads(self):
        # Immutable primary game evidence: .local/diplomacy-completion/
        # native-startup-10/user-data/logs/game.log:10083-10087.
        r = s.state()
        s.execute(s.parse('set_temp_variable = { channel_probe_temp = 7 } B = { set_temp_variable = { channel_probe_copy = channel_probe_temp } add_to_temp_variable = { channel_probe_temp = 4 } }'), r, s.ctx())
        self.assertEqual(s.value(r, s.ctx(), 'channel_probe_temp'), 11)
        self.assertEqual(s.value(r, s.ctx('B', 'A'), 'channel_probe_copy'), 7)
        self.assertEqual(s.value(r, s.switch(s.ctx(), 'B'), 'PREV.channel_probe_temp'), 0)
        r['countries']['A']['variables']['channel_probe_temp'] = 23
        self.assertEqual(s.value(r, s.switch(s.ctx(), 'B'), 'PREV.channel_probe_temp'), 23)
        self.assertEqual(s.value(r, s.ctx(), 'channel_probe_temp'), 11)

    def test_native_country_id_array_and_nested_scope_frames(self):
        r = s.state()
        s.execute(s.parse('set_variable = { channel_country = ROOT } FROM = { set_variable = { channel_reverse = PREV } }'), r, s.ctx())
        self.assertEqual(r['countries']['A']['variables']['channel_country'], s.IDS['A'])
        self.assertEqual(r['countries']['B']['variables']['channel_reverse'], s.IDS['A'])
        self.assertEqual(s.country_ref(r, s.ctx('B', 'A'), 'var:channel_reverse'), 'A')
        r['countries']['A']['arrays']['channel_array'] = [s.IDS['B'], s.IDS['C']]
        self.assertEqual(s.value(r, s.ctx(), 'channel_array^num'), 2)
        self.assertTrue(s.condition(s.parse('all_of = { array = channel_array value = channel_v index = channel_i check_variable = { channel_v > 0 } }'), r, s.ctx()))
        self.assertEqual(s.value(r, s.ctx(), 'channel_v'), s.IDS['C'])

if __name__ == '__main__':
    unittest.main()
