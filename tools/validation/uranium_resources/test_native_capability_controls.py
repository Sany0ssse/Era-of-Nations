"""Reject malformed native capability controls; no native game launch or proof."""
from datetime import datetime, timedelta
from pathlib import Path
import json
import tempfile

import build_rights_connectivity_native_probe as rights
import analyze_rights_connectivity_native_probe as rights_analyzer
import build_state_activation_native_probe as state
import analyze_state_activation_native_probe as state_analyzer


def rights_log(manifest, positive=True):
    marker = manifest['marker']
    lines = ['[2000.01.01.01] '+marker+' STARTUP coastal_resource_rights']
    lines += ['[2000.01.01.01] '+marker+' PASS '+label for label in manifest['assertions']]
    for index, label in enumerate(manifest['observation_labels']):
        fields = dict.fromkeys(manifest['observation_fields'], 0)
        fields.update(state_uranium=80, state_oil=100)
        if label.startswith('receiver_') and label not in ('receiver_before',):
            fields.update(oil_balance=70, oil_produced=100)
            if positive: fields.update(uranium_balance=56, uranium_produced=80)
            if label == 'receiver_after_settlement' and positive: fields.update(raw=5600, delivered=5600, rights_supply=8000)
        stamp = datetime(2000, 1, 1)+timedelta(hours=index*8)
        lines.append('['+stamp.strftime('%Y.%m.%d.%H')+'] '+marker+' OBS '+label+
                     ' ROOT='+manifest['expected_observation_roots'][label]+' THIS='+manifest['expected_observation_actors'][label]+' '+
                     ' '.join(k+'='+str(v) for k, v in fields.items()))
    lines.append('[2000.01.04.01] '+marker+' END passes='+str(len(manifest['assertions']))+' fails=0')
    return '\n'.join(lines)


def state_log(manifest):
    marker = manifest['marker']
    if manifest.get('state_evidence_version',1) >= 2:
        lines = ['[2000.01.01.00] '+marker+' STARTUP native_state_activation']
        remaining = set(manifest['assertions'])
        def passes(labels, stamp):
            for label in labels:
                assert label in remaining
                remaining.remove(label)
                lines.append('['+stamp+'] '+marker+' PASS '+label)
        def observe(label, stamp, complete, removed, timed, capacity):
            fields = dict.fromkeys(manifest['observation_fields'],0)
            fields.update(treasury=10,capacity=capacity,ordinary_complete=complete,ordinary_remove=removed,timed_callback=timed)
            lines.append('['+stamp+'] '+marker+' OBS '+label+' ROOT=GER THIS=GER '+' '.join(k+'='+str(v) for k,v in fields.items()))
        passes(['event1_GER_owns_state44','no_native_callback_before_state_fixture_arm'],'2000.01.01.00')
        observe('before_ordinary_activation','2000.01.01.00',0,0,0,5)
        lines.append('[2000.01.01.00] '+marker+' ARMED ordinary_native_AI_selection')
        lines.append('[2000.01.01.02] '+marker+' CALLBACK ordinary_begin')
        passes(['ordinary_complete_native_FROM_state44','ordinary_source_begin_deducts_exactly025'],'2000.01.01.02')
        lines.append('[2000.01.02.02] '+marker+' CALLBACK ordinary_remove')
        passes(['ordinary_remove_native_FROM_state44','ordinary_source_remove_has_no_second_charge','ordinary_source_remove_geometric_expansion'],'2000.01.02.02')
        observe('after_ordinary_activation_wait','2000.01.02.08',1,1,0,7.5)
        passes(['ordinary_native_AI_selected_source_begin','ordinary_native_AI_selected_source_remove_after_one_day'],'2000.01.02.08')
        lines.append('[2000.01.02.08] '+marker+' ARMED timed_native_FROM_control')
        timed_stamp='2000.01.04.00' if manifest.get('state_evidence_version',1) >= 4 else '2000.01.03.00'
        final_stamp='2000.01.05.00' if manifest.get('state_evidence_version',1) >= 4 else '2000.01.03.16'
        lines.append('['+timed_stamp+'] '+marker+' CALLBACK timed_timeout')
        passes([label for label in manifest['assertions'] if label.startswith('timed_') and label != 'timed_native_callback_fired'],timed_stamp)
        observe('after_native_timeout_wait',final_stamp,1,1,1,7.5)
        passes(['timed_native_callback_fired'],final_stamp)
        assert not remaining,remaining
        lines.append('['+final_stamp+'] '+marker+' END passes='+str(len(manifest['assertions']))+' fails=0')
        return '\n'.join(lines)
    labels = [label for label in manifest['assertions'] if not label.startswith('ordinary_')]
    lines = ['[2000.01.01.01] '+marker+' STARTUP native_state_activation']
    lines += ['[2000.01.01.01] '+marker+' PASS '+label for label in labels]
    for index, label in enumerate(manifest['observation_labels']):
        fields = dict.fromkeys(manifest['observation_fields'], 0)
        fields.update(treasury=10, capacity=5)
        if index == 2: fields.update(treasury=9.75, capacity=7.5, timed_callback=1)
        stamp = datetime(2000, 1, 1)+timedelta(hours=index*32)
        lines.append('['+stamp.strftime('%Y.%m.%d.%H')+'] '+marker+' OBS '+label+' ROOT=GER THIS=GER '+
                     ' '.join(k+'='+str(v) for k, v in fields.items()))
    lines.append('[2000.01.04.01] '+marker+' END passes='+str(len(labels))+' fails=0')
    return '\n'.join(lines)


def main():
    negative = 0
    with tempfile.TemporaryDirectory(prefix='eon-native-capabilities-') as temporary:
        base = Path(temporary)
        rm = rights.build(rights.ROOT, base/'rights', preparation_only=True)
        sm = state.build(state.ROOT, base/'state', preparation_only=True, start_delay_hours=16)
        state_analyzer.verify_bindings(state.ROOT, base/'state', sm)
        for manifest, folder in ((rm, 'rights'), (sm, 'state')):
            for rel in manifest['fixture_sha256']:
                assert not (base/folder/'mod'/rel).read_bytes().startswith(b'\xef\xbb\xbf')
        good_r, good_s = rights_log(rm), state_log(sm)
        rp, sp = rights_analyzer.parse_log(good_r, rm), state_analyzer.parse_log(good_s, sm)
        assert rp['paired_control_classification'] == 'both_native_counters_increase'
        assert rp['public_material_credit_matches_native_balance']
        zero = rights_analyzer.parse_log(rights_log(rm, False), rm)
        assert zero['paired_control_classification'] == 'uranium_counter_absent_oil_positive'
        assert zero['public_material_credit_matches_native_balance']
        assert not zero['native_uranium_positive_delivery_observed']
        # An observation alone cannot prove correct credit; parsed unexpected
        # production accounting is retained and explicitly marked false.
        wrong_credit = good_r.replace('raw=5600', 'raw=5700')
        assert not rights_analyzer.parse_log(wrong_credit, rm)['public_material_credit_matches_native_balance']
        assert sp['native_targeted_mission_source_callbacks_verified']
        assert not sp['ordinary_activate_targeted_decision_called_complete_effect']
        assert sp['native_AI_selected_ordinary_source_callbacks_verified']
        state_events=(base/'state/mod/events'/f'{state.NS}_events.txt').read_text(encoding='utf-8')
        assert 'id = '+state.NS+'.3 hours = 64' in state_events
        assert sm['state_evidence_version'] == 5 and sm['minimum_timed_timeout_observation_hours'] == 60
        assert sm['state_target_selector_binding']['value'] == 'any_owned_state'
        version4=dict(sm,state_evidence_version=4)
        assert state_analyzer.parse_log(state_log(version4),version4)['native_targeted_mission_source_callbacks_verified']
        version3=dict(sm,state_evidence_version=3,minimum_total_native_hours=60)
        assert state_analyzer.parse_log(state_log(version3),version3)['native_targeted_mission_source_callbacks_verified']
        early=dict(sm,minimum_total_native_hours=60)
        try:state_analyzer.parse_log(good_s.replace('[2000.01.05.00]','[2000.01.03.16]'),early)
        except AssertionError:negative+=1
        else:raise AssertionError('Version4 accepted early timed completion observation')
        bad_wait=dict(sm,minimum_timed_timeout_observation_hours=30)
        try:state_analyzer.parse_log(good_s,bad_wait)
        except AssertionError:negative+=1
        else:raise AssertionError('Version4 wait declaration was weakened')
        late='[2000.01.04.00] '+sm['marker']+' CALLBACK timed_timeout'
        cases = [(rights_analyzer, rm, good_r.replace('ROOT=GER', 'ROOT=USA', 1)),
                 (rights_analyzer, rm, good_r.replace('uranium_balance=0', 'uranium_balance=nan', 1)),
                 (rights_analyzer, rm, good_r.replace('oil_balance=0', 'oil_balance=0 oil_balance=0', 1)),
                 (rights_analyzer, rm, good_r.replace(' OBS provider_before ', ' OBS wrong_label ', 1)),
                 (rights_analyzer, rm, good_r.replace(' STARTUP coastal_resource_rights', ' STARTUP wrong', 1)),
                 (state_analyzer, sm, good_s.replace('timed_callback=1', 'timed_callback=0')),
                 (state_analyzer, sm, good_s.replace('capacity=7.5', 'capacity=8.5')),
                 (state_analyzer, sm, good_s.replace('ordinary_complete=0', 'ordinary_complete=1')),
                 (state_analyzer, sm, good_s.replace('ROOT=GER', 'ROOT=USA', 1)),
                 (state_analyzer, sm, good_s.replace('[2000.01.05.00]', '[2000.01.01.16]')),
                 (state_analyzer, sm, good_s+'\n'+sm['marker']+' PASS unexpected'),
                 (state_analyzer, sm, '[2000.01.01.00] '+sm['marker']+' CALLBACK timed_timeout\n'+good_s),
                 (state_analyzer, sm, good_s.replace(' ARMED ordinary_native_AI_selection',' ARMED wrong_stage')),
                 (state_analyzer, sm, good_s.replace(' OBS before_ordinary_activation',' OBS wrong_initial')),
                 (state_analyzer, sm, good_s.replace('[2000.01.01.02]','[2000.01.01.20]')),
                 (state_analyzer, sm, good_s.replace(late+'\n','')+'\n'+late)]
        for analyzer, manifest, log in cases:
            try: analyzer.parse_log(log, manifest)
            except AssertionError: negative += 1
            else: raise AssertionError('Malformed native capability evidence accepted')
        for key,value in (('value','yes'),('source_ast_sha256','wrong'),('selector',['eon_uranium_category','eon_uranium_expand_mine','target_trigger'])):
            broken=json.loads(json.dumps(sm));broken['state_target_selector_binding'][key]=value
            try:state_analyzer.verify_bindings(state.ROOT,base/'state',broken)
            except AssertionError:negative+=1
            else:raise AssertionError('Unbound state selector metadata accepted')
        decision_file=base/'state/mod/common/decisions'/f'{state.NS}_decisions.txt'
        original=decision_file.read_bytes()
        for index in (1,2):
            changed=original.decode().split('state_target = any_owned_state')
            assert len(changed) == 3
            data='state_target = any_owned_state'.join(changed[:index])+'state_target = yes'+'state_target = any_owned_state'.join(changed[index:])
            decision_file.write_bytes(data.encode())
            try:state_analyzer.verify_bindings(state.ROOT,base/'state',sm)
            except AssertionError:negative+=1
            else:raise AssertionError('Native state selector was silently changed')
        decision_file.write_bytes(original)
    print(json.dumps({'native_capability_validator_controls_verified': True, 'negative_controls': negative,
                      'native_game_behavior_tested': False}))


if __name__ == '__main__': main()
