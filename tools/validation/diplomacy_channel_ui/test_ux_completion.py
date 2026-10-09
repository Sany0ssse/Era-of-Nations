"""Description selection and original choice boundaries on current source AST."""
import subprocess
import unittest

import _support as s
import consultation_compat as compat

BASE = 'b174de7fcd77ec386fdf65b79caa3d9613d76d85'
EVENT_PATH = 'events/eon_consultation_events.txt'


def events(data):
    return {s.one(body, 'id'): body for name, op, body in s.parse(data)
            if name == 'country_event'}


def descriptions(result, event_id, actor='A', peer='B'):
    body = events((s.ROOT / EVENT_PATH).read_text(encoding='utf-8-sig'))[event_id]
    return [s.one(data, 'text') for name, op, data in body if name == 'desc'
            and s.condition(s.one(data, 'trigger'), result, s.ctx(actor, peer))]


def draft():
    result = s.state()
    s.execute([('eon_consultation_prepare_draft', '=', 'yes')], result, s.native_ctx())
    assert 'eon_consultation_draft_owner' in result['countries']['A']['flags']
    return result


def request(topic):
    result = draft()
    s.execute(s.parse(f'set_temp_variable = {{ eon_consultation_proposed_topic = {topic} }} eon_consultation_send_request = yes'), result, s.ctx())
    assert 'eon_consultation_incoming' in result['countries']['B']['flags']
    return result


class UXCompletionTests(unittest.TestCase):
    def test_agenda_shows_one_matching_ready_low_power_expired_or_stale_description(self):
        cases = []
        result = draft()
        cases.append((result, 'eon_consultation_agenda_desc'))
        result = draft()
        result['countries']['A']['pp'] = 9.99
        cases.append((result, 'eon_consultation_low_power_agenda_desc'))
        result = draft()
        result['day'] = 8
        s.execute([('eon_consultation_daily_cleanup', '=', 'yes')], result, s.ctx())
        cases.append((result, 'eon_consultation_expired_agenda_desc'))
        result = s.state()
        cases.append((result, 'eon_consultation_stale_agenda_desc'))
        for result, expected in cases:
            self.assertEqual(descriptions(result, 'eon_consultation.1'), [expected])

    def test_all_topics_show_one_matching_live_withdrawn_expired_or_stale_reply(self):
        for topic, label in ((1, 'trade'), (2, 'energy'), (3, 'support')):
            event_id = f'eon_consultation.{topic + 9}'
            result = request(topic)
            self.assertEqual(descriptions(result, event_id, 'B', 'A'), [f'eon_consultation_{label}_invite_desc'])
            s.execute([('eon_consultation_withdraw_request', '=', 'yes')], result, s.ctx())
            self.assertEqual(descriptions(result, event_id, 'B', 'A'), ['eon_consultation_cancelled_invite_desc'])
            result = request(topic)
            result['day'] = 31
            s.execute([('eon_consultation_daily_cleanup', '=', 'yes')], result, s.ctx())
            self.assertEqual(descriptions(result, event_id, 'B', 'A'), ['eon_consultation_expired_invite_desc'])
            # Withdrawal plus expiry must retain a single unambiguous reason.
            result['countries']['A']['flags'].add('eon_consultation_cancelled')
            self.assertEqual(descriptions(result, event_id, 'B', 'A'), ['eon_consultation_expired_invite_desc'])
            self.assertEqual(descriptions(s.state(), event_id, 'B', 'A'), ['eon_consultation_stale_invite_desc'])

    def test_exact_ux_inverse_preserves_unowned_bytes_bom_and_line_endings(self):
        for path in compat.journal()['files']:
            baseline = subprocess.check_output(['git', 'show', BASE + ':' + path], cwd=s.ROOT)
            self.assertEqual(compat.restore_before(path), baseline, path)
            changed = (s.ROOT / path).read_bytes() + b'# unexpected byte\n'
            with self.assertRaises(AssertionError, msg=path):
                compat.restore_before(path, changed)

    def test_localisation_repair_is_exactly_six_core_rows_four_new_and_five_ui_rows(self):
        core_changed = {f'eon_consultation.{n}.desc' for n in (20, 21, 22, 26)} | {
            'eon_consultation.26.t', 'eon_consultation_open_ready_tt'}
        core_added = {'eon_consultation_' + name + '_desc' for name in (
            'expired_agenda', 'expired_invite', 'low_power_agenda', 'stale_agenda')}
        ui_changed = {'eon_consultation_ui.1.closed', 'eon_consultation_ui.1.energy',
                      'eon_consultation_ui_status', 'eon_open_consultation_panel',
                      'eon_open_consultation_panel_desc'}
        for path, item in compat.journal()['files'].items():
            if not path.startswith('localisation/'):
                continue
            added = {x['id'] for x in item['islands'] if not x['before']}
            changed = {x['id'] for x in item['islands'] if x['before']}
            self.assertEqual(added, set() if '_ui_' in path else core_added, path)
            self.assertEqual(changed, ui_changed if '_ui_' in path else core_changed, path)

    def test_invitation_event_ids_choices_and_ai_weights_are_preserved(self):
        before = events(subprocess.check_output(['git', 'show', BASE + ':' + EVENT_PATH], cwd=s.ROOT).decode('utf-8-sig'))
        after = events((s.ROOT / EVENT_PATH).read_text(encoding='utf-8-sig'))
        self.assertEqual(set(before), set(after))
        for event_id in before:
            old_options = [body for name, op, body in before[event_id] if name == 'option']
            new_options = [body for name, op, body in after[event_id] if name == 'option']
            self.assertEqual(old_options, [[node for node in body if node[0] != 'log'] for body in new_options], event_id)
            logs = [node for body in new_options for node in body if node[0] == 'log']
            self.assertEqual(len(logs), 2 if event_id in ('eon_consultation.10', 'eon_consultation.11', 'eon_consultation.12') else 0)


if __name__ == '__main__':
    unittest.main()
