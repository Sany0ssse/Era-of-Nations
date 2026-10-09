"""Negative controls for country-mission matrix/calendar evidence; never launch HOI4."""
from datetime import datetime, timedelta
from pathlib import Path
import json
import tempfile

import build_mission_calendar_native_probe as builder
import analyze_mission_calendar_native_probe as analyzer


def synthetic(manifest):
    marker=manifest['marker']
    lines=['[2000.01.01.00] '+marker+' STARTUP native_mission_calendar']
    lines += ['[2000.01.01.00] '+marker+' PASS '+label for label in manifest['assertions']]
    version=manifest.get('mission_calendar_evidence_version',1)
    last_hour=256 if version == 4 else (160 if version == 3 else 128)
    times=[0,0,8,40,72,72,80,80,88,96,192,192,last_hour] if version == 4 else [0,0,8,40,72,72,80,80,88,96,last_hour]
    projects=([(0,0,0,0),(0,3,75,1),(0,3,75,1),(0,3,75,1),(3,0,0,0),
              (3,1,25,1),(3,1,25,1),(3,0,0,0),(3,1,25,1),(3,1,25,1)]+
             ([(3,1,25,1),(3,1,25,1)] if version == 4 else [])+[(4,0,0,0)])
    for i,label in enumerate(manifest['observation_labels']):
        values=dict.fromkeys(manifest['observation_fields'],0)
        values.update(treasury=100,facilities=projects[i][0],count=projects[i][1],escrow=projects[i][2],paid=projects[i][3])
        if label in ('triple_start','matrix_and_triple_poll','triple_base_period_elapsed','cancel_single_start','cancel_single_poll','cancel_source_callbacks','calendar_single_start','calendar_single_poll'):
            values['active']=1
        if label in ('triple_start','matrix_and_triple_poll'):values['remaining']=1095
        if label == 'triple_base_period_elapsed':values['remaining']=365
        if label in ('cancel_single_start','cancel_single_poll','calendar_single_start','calendar_single_poll'):values['remaining']=730
        if label == 'single_running_after_native_cancel_ack':values['remaining']=726
        if label == 'single_accelerated_after_ack':values['remaining']=1
        if version == 4:
            values['mission_visible']=projects[i][3]
            values['legacy_time']=values['remaining']
            values['triple_flag']=int(projects[i][1] == 3)
            values['single_flag']=int(projects[i][1] == 1)
            if label in ('cancel_source_callbacks','calendar_single_start','calendar_single_poll'):values['ack_pending']=123
        if label == 'matrix_and_triple_poll':values.update(yes_literal_active=1,yes_literal_remaining=730)
        if label == 'triple_start':values['delta']=75
        if label in ('cancel_single_start','cancel_source_callbacks','calendar_single_start'):values['delta']=25
        stamp=(datetime(2000,1,1)+timedelta(hours=times[i])).strftime('%Y.%m.%d.%H')
        lines.append('['+stamp+'] '+marker+' OBS '+label+' ROOT=GER THIS=GER '+' '.join(key+'='+str(value) for key,value in values.items()))
    end_stamp=(datetime(2000,1,1)+timedelta(hours=last_hour)).strftime('%Y.%m.%d.%H')
    lines.append('['+end_stamp+'] '+marker+' END passes='+str(len(manifest['assertions']))+' fails=0')
    return '\n'.join(lines)


def main():
    negative=0
    with tempfile.TemporaryDirectory(prefix='eon-mission-calendar-controls-') as temp:
        fixture=Path(temp)/'fixture'
        manifest=builder.build(builder.ROOT,fixture,preparation_only=True)
        analyzer.verify_bindings(builder.ROOT,fixture,manifest)
        for rel in manifest['fixture_sha256']:
            assert not (fixture/'mod'/rel).read_bytes().startswith(b'\xef\xbb\xbf')
        events=(fixture/'mod/events'/f'{builder.NS}_events.txt').read_text(encoding='utf-8')
        assert events.index('set_variable = { '+builder.NS+'_timer = 730 }') < events.index('activate_mission = '+builder.NS+'_yes_literal')
        assert 'id = '+builder.NS+'.8 hours = 64' in events
        assert manifest['mission_calendar_evidence_version'] == 4
        assert manifest['direct_cancellation_event_option'] == 'energy.5.a'
        assert manifest['callback_bindings'][2]['event_id'] == 'energy.5'
        assert manifest['minimum_single_timeout_observation_hours'] == 60
        good=synthetic(manifest)
        result=analyzer.parse_log(good,manifest)
        assert result['actual_native_enrichment_calendar_completed']
        assert result['mission_registration_matrix']['yes_literal_active'] == 1
        assert not result['native_cancellation_complete_effect_selected']
        assert result['source_direct_cancellation_option_and_cleanup_verified']
        final_stamp='['+(datetime(2000,1,1)+timedelta(hours=256)).strftime('%Y.%m.%d.%H')+']'
        cases=[good.replace(' STARTUP native_mission_calendar',' STARTUP wrong'),
               good+'\n'+manifest['marker']+' PASS '+manifest['assertions'][0],
               good.replace('ROOT=GER','ROOT=USA',1),
               good.replace(' OBS matrix_and_triple_poll ',' OBS wrong '),
               good.replace('yes_literal_active=1','yes_literal_active=2'),
               good.replace('remaining=1095','remaining=730'),
               good.replace('remaining=365','remaining=0'),
               good.replace('facilities=4','facilities=5'),
               good.replace('delta=75','delta=74.5'),
               good.replace('delta=25','delta=24.5'),
               good.replace('count=3','count=2'),
               good.replace(final_stamp,'[2000.01.04.08]'),
               good+'\n'+manifest['marker']+' CONTROL_TIMEOUT yes_literal',
               good.replace('yes_dynamic_active=0','yes_dynamic_active=2'),
               good.replace('yes_dynamic_remaining=0','yes_dynamic_remaining=20'),
               good.replace('remaining=730','remaining=729'),
               good.replace('facilities=4 count=0 escrow=0 paid=0','facilities=4 count=1 escrow=25 paid=1'),
               good.replace('facilities=4 count=0 escrow=0 paid=0','facilities=3 count=1 escrow=25 paid=1')]
        for log in cases:
            try:analyzer.parse_log(log,manifest)
            except AssertionError:negative+=1
            else:raise AssertionError('Malformed calendar evidence accepted')
        # Native60 observed false active predicates with genuine ticking
        # counters and natural callbacks. Only the new version uses counters;
        # the legacy reader must keep rejecting that same observation.
        predicate_zero=good.replace('active=1','active=0')
        assert analyzer.parse_log(predicate_zero,manifest)['actual_native_enrichment_calendar_completed']
        # The new delayed observation is stricter. Old version2 accepts its
        # original32-hour successful callback fixture without changing rules.
        def legacy_version(version):
            result=json.loads(json.dumps(manifest))
            result['mission_calendar_evidence_version']=version
            result['minimum_total_native_hours']=152 if version == 3 else 120
            result['observation_labels']=[label for label in result['observation_labels'] if label not in ('single_running_after_native_cancel_ack','single_accelerated_after_ack')]
            for field in ('legacy_time','single_flag','triple_flag','mission_visible','ack_pending'):result['observation_fields'].pop(field)
            return result
        version2=legacy_version(2)
        assert analyzer.parse_log(synthetic(version2),version2)['actual_native_enrichment_calendar_completed']
        early_manifest=dict(manifest,minimum_total_native_hours=120)
        early=good.replace(final_stamp,'[2000.01.10.00]')
        try:analyzer.parse_log(early,early_manifest)
        except AssertionError:negative+=1
        else:raise AssertionError('Version3 accepted early zero-counter observation')
        bad_wait=dict(manifest,minimum_single_timeout_observation_hours=30)
        try:analyzer.parse_log(good,bad_wait)
        except AssertionError:negative+=1
        else:raise AssertionError('Version3 wait declaration was weakened')
        legacy=legacy_version(1);legacy.pop('mission_calendar_evidence_version')
        try:analyzer.parse_log(synthetic(legacy).replace('active=1','active=0'),legacy)
        except AssertionError:negative+=1
        else:raise AssertionError('Legacy active-predicate contract was weakened')
        # Version3 remains independently supported with its original timing
        # and fields. New cleanup criteria never retroactively alter it.
        version3=legacy_version(3)
        assert analyzer.parse_log(synthetic(version3),version3)['actual_native_enrichment_calendar_completed']
        cancel_line=next(line for line in good.splitlines() if ' OBS cancel_source_callbacks ' in line)
        for field in ('legacy_time','single_flag','triple_flag','mission_visible'):
            broken=good.replace(cancel_line,cancel_line.replace(field+'=0',field+'=1'))
            try:analyzer.parse_log(broken,manifest)
            except AssertionError:negative+=1
            else:raise AssertionError('Direct option cleanup field not checked: '+field)
        ack_line=next(line for line in good.splitlines() if ' OBS single_running_after_native_cancel_ack ' in line)
        for broken in (good.replace(ack_line,ack_line.replace('ack_pending=0','ack_pending=123')),
                       good.replace('[2000.01.09.00]','[2000.01.08.00]'),
                       good.replace(ack_line,ack_line.replace('paid=1','paid=0')),
                       good.replace(ack_line,ack_line.replace('remaining=726','remaining=0'))):
            try:analyzer.parse_log(broken,manifest)
            except AssertionError:negative+=1
            else:raise AssertionError('Cancellation acknowledgement boundary not enforced')
        for key,value in (('event_id','energy.6'),('option_name','energy.5.b'),('excluded_metadata',['name'])):
            broken=json.loads(json.dumps(manifest));broken['callback_bindings'][2][key]=value
            try:analyzer.verify_bindings(builder.ROOT,fixture,broken)
            except AssertionError:negative+=1
            else:raise AssertionError('Incorrect direct option binding accepted')
        triggers=fixture/'mod/common/scripted_triggers'/f'{builder.NS}_triggers.txt'
        original=triggers.read_bytes()
        triggers.write_bytes((builder.NS+'_production_visible = { always = no }').encode())
        try:analyzer.verify_bindings(builder.ROOT,fixture,manifest)
        except AssertionError:negative+=1
        else:raise AssertionError('Unbound production visibility predicate accepted')
        triggers.write_bytes(original)
        controls=fixture/'mod/common/decisions'/f'{builder.NS}_controls.txt'
        controls.write_text(controls.read_text(encoding='utf-8').replace('ROOT.'+builder.NS+'_timer','730'),encoding='utf-8')
        try:analyzer.verify_bindings(builder.ROOT,fixture,manifest)
        except AssertionError:negative+=1
        else:raise AssertionError('Changed dynamic control accepted')
    print(json.dumps({'mission_calendar_validator_controls_verified':True,'negative_controls':negative,'native_game_behavior_tested':False}))


if __name__ == '__main__':main()
