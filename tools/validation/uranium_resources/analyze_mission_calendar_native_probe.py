"""Accept source-bound native mission calendar evidence with strict observations."""
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import importlib.util
import json
import math
import re

from build_native_probe import load_parser, sha
from build_core_native_probe import canonical
from build_mission_calendar_native_probe import NS, MISSION, resolve_binding


def parse_log(text, manifest):
    marker = re.escape(manifest['marker'])
    assert len(re.findall(marker+r' STARTUP native_mission_calendar',text)) == 1
    passed = re.findall(marker+r' PASS ([A-Za-z0-9_]+)',text)
    failed = re.findall(marker+r' FAIL ([A-Za-z0-9_]+)',text)
    assert Counter(passed+failed) == Counter(manifest['assertions'])
    assert all(count == 1 for count in Counter(passed+failed).values())
    end = re.findall(marker+r' END passes=([0-9.]+) fails=([0-9.]+)',text)
    assert len(end) == 1 and list(map(float,end[0])) == [len(passed),len(failed)]
    assert not re.search(marker+r' (ABORT|DUPLICATE_EVENT|CONTROL_TIMEOUT)',text), 'Premature control or duplicate event'
    observations = {}
    for index,line in enumerate(text.splitlines(),1):
        match = re.search(marker+r' OBS ([A-Za-z0-9_]+) ROOT=([^ ]+) THIS=([^ ]+) (.*)',line)
        if not match: continue
        label,root,actor,fields = match.groups()
        assert label in manifest['observation_labels'] and label not in observations
        assert root == actor == 'GER'
        stamp = re.findall(r'\[(\d{4}\.\d{2}\.\d{2}\.\d{2})\]',line)
        assert stamp
        year,month,day,hour = map(int,stamp[-1].split('.'))
        assert 0 <= hour <= 24
        instant = datetime(year,month,day)+timedelta(hours=hour)
        pairs = re.findall(r'([a-z_]+)=(-?\d+(?:\.\d+)?)',fields)
        assert Counter(key for key,value in pairs) == Counter(list(manifest['observation_fields']))
        values = {key:float(value) for key,value in pairs}
        assert all(math.isfinite(value) for value in values.values())
        for key,value in values.items():
            if key.endswith('_active') or key in ('active','paid','single_flag','triple_flag','mission_visible'): assert value in (0,1)
        observations[label] = {'line_index':index,'native_date':stamp[-1],'instant':instant,**values}
    assert set(observations) == set(manifest['observation_labels'])
    ordered = [observations[label] for label in manifest['observation_labels']]
    assert all(a['line_index'] < b['line_index'] and a['instant'] <= b['instant'] for a,b in zip(ordered,ordered[1:]))
    elapsed = (ordered[-1]['instant']-ordered[0]['instant']).total_seconds()/3600
    assert elapsed >= manifest['minimum_total_native_hours']
    def near(actual,expected): assert math.isclose(actual,expected,abs_tol=.02,rel_tol=1e-6),(actual,expected)
    for label,values in {'before_activation':(0,0,0,0), 'triple_start':(0,3,75,1),
                         'matrix_and_triple_poll':(0,3,75,1),'triple_base_period_elapsed':(0,3,75,1),
                         'triple_native_expired':(3,0,0,0),'cancel_single_start':(3,1,25,1),
                         'cancel_single_poll':(3,1,25,1),'cancel_source_callbacks':(3,0,0,0),
                         'calendar_single_start':(3,1,25,1),'calendar_single_poll':(3,1,25,1),
                         'single_native_expired':(4,0,0,0)}.items():
        for key,expected in zip(('facilities','count','escrow','paid'),values): near(observations[label][key],expected)
    for label,expected in (('triple_start',75),('cancel_single_start',25),('cancel_source_callbacks',25),('calendar_single_start',25)):
        near(observations[label]['delta'],expected)
    if manifest.get('mission_calendar_evidence_version',1) == 1:
        # Preserve the original predicate contract and failed60 evidence.
        for label in ('matrix_and_triple_poll','triple_base_period_elapsed','cancel_single_poll','calendar_single_poll'):
            assert observations[label]['active'] == 1, ('Production mission inactive',label)
        for label in ('triple_native_expired','single_native_expired'): assert observations[label]['active'] == 0
        assert observations['matrix_and_triple_poll']['yes_literal_active'] == 1
    else:
        assert manifest['mission_calendar_evidence_version'] in (2,3,4)
        for label in ('matrix_and_triple_poll','triple_base_period_elapsed','cancel_single_poll','calendar_single_poll'):
            assert observations[label]['remaining'] > 0, ('Production native timer absent',label)
        for label in ('triple_native_expired','cancel_source_callbacks','single_native_expired'):
            near(observations[label]['remaining'],0)
        near(observations['calendar_single_start']['remaining'],730)
        assert observations['matrix_and_triple_poll']['yes_literal_remaining'] > 0
        matrix_position=manifest['observation_labels'].index('matrix_and_triple_poll')
        for value in ordered[matrix_position+1:]:
            for key in manifest['observation_fields']:
                if key.startswith(('yes_','no_')) and key.endswith('_remaining'):near(value[key],0)
    assert 1090 <= observations['matrix_and_triple_poll']['remaining'] <= 1095
    assert 350 <= observations['triple_base_period_elapsed']['remaining'] <= 366
    assert 725 <= observations['calendar_single_poll']['remaining'] <= 730
    single_minimum=30
    if manifest.get('mission_calendar_evidence_version',1) in (3,4):
        assert manifest['single_native_timeout_observation_delay_hours'] == 64
        assert manifest['minimum_single_timeout_observation_hours'] == 60
        single_minimum=60
    if manifest.get('mission_calendar_evidence_version',1) == 4:
        assert manifest['direct_cancellation_event_option'] == 'energy.5.a'
        assert manifest['cancellation_ack_observation_delay_hours'] == 96
        assert manifest['minimum_cancellation_ack_observation_hours'] == 92
        cancelled=observations['cancel_source_callbacks']
        for key in ('legacy_time','single_flag','triple_flag','mission_visible'): near(cancelled[key],0)
        assert observations['cancel_single_poll']['mission_visible'] == 1
        assert observations['calendar_single_start']['ack_pending'] > 0, 'Replacement project must begin before its pending diplomatic acknowledgement'
        after_ack=observations['single_running_after_native_cancel_ack']
        accelerated=observations['single_accelerated_after_ack']
        for key,expected in (('facilities',3),('count',1),('escrow',25),('paid',1),('ack_pending',0)):
            near(after_ack[key],expected);near(accelerated[key],expected)
        assert 720 <= after_ack['remaining'] <= 730 and after_ack['mission_visible'] == 1
        near(accelerated['remaining'],1)
        assert (after_ack['instant']-observations['calendar_single_poll']['instant']).total_seconds()/3600 >= 92
        assert (observations['single_native_expired']['instant']-accelerated['instant']).total_seconds()/3600 >= 60
    for before,after,minimum in (('triple_start','matrix_and_triple_poll',6),
                                ('matrix_and_triple_poll','triple_base_period_elapsed',30),
                                ('triple_base_period_elapsed','triple_native_expired',30),
                                ('calendar_single_start','calendar_single_poll',6),
                                ('calendar_single_poll','single_native_expired',single_minimum)):
        assert (observations[after]['instant']-observations[before]['instant']).total_seconds()/3600 >= minimum
    matrix = {key:observations['matrix_and_triple_poll'][key] for key in manifest['observation_fields'] if key.startswith(('yes_','no_'))}
    for value in observations.values(): value.pop('instant')
    return {'passed':passed,'failed':failed,'observations':observations,'elapsed_native_hours':elapsed,
            'mission_registration_matrix':matrix,'actual_native_enrichment_calendar_completed':not failed,
            'native_cancellation_complete_effect_selected':False,
            'source_direct_cancellation_option_and_cleanup_verified':manifest.get('mission_calendar_evidence_version',1) == 4 and not failed}


def verify_bindings(source,fixture,manifest):
    p=load_parser()
    aliases=p.ast((fixture/'mod/common/scripted_effects'/f'{NS}_effects.txt').read_bytes())
    assert len(manifest['callback_bindings']) == 4
    for binding in manifest['callback_bindings']:
        body=resolve_binding(p,source,binding)
        assert canonical(body) == canonical(p.one(aliases,binding['alias'])) == binding['source_ast_sha256']
    if manifest.get('mission_calendar_evidence_version',1) == 4:
        assert manifest['callback_bindings'][2]['binding_kind'] == 'event_option_effects'
        assert manifest['callback_bindings'][2]['event_id'] == 'energy.5'
        assert manifest['callback_bindings'][2]['option_name'] == 'energy.5.a'
        assert len(manifest['predicate_bindings']) == 1
        triggers=p.ast((fixture/'mod/common/scripted_triggers'/f'{NS}_triggers.txt').read_bytes())
        for binding in manifest['predicate_bindings']:
            body=resolve_binding(p,source,binding)
            assert binding['selector'] == ['GENERIC_economic_category',MISSION,'visible']
            assert canonical(body) == canonical(p.one(triggers,binding['alias'])) == binding['source_ast_sha256']
    candidate=p.one(p.one(p.ast((source/'common/decisions/generic.txt').read_bytes()),'GENERIC_economic_category'),MISSION)
    assert canonical(candidate) == manifest['production_mission_ast_sha256']
    controls=p.one(p.ast((fixture/'mod/common/decisions'/f'{NS}_controls.txt').read_bytes()),'GENERIC_economic_category')
    assert canonical(controls) == manifest['matrix_ast_sha256']
    assert [ident for ident,op,body in controls] == manifest['matrix_ids']
    for ident,op,body in controls:
        allowed,clock=ident.removeprefix(NS+'_').split('_')
        assert p.one(body,'allowed') == p.ast('always = '+allowed)
        assert p.one(body,'days_mission_timeout') == ('730' if clock == 'literal' else 'ROOT.'+NS+'_timer')
        assert p.one(body,'activation') == p.ast('always = no')


def analyze(manifest_path,launch_path,game_log):
    manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    assert manifest['kind'] == 'native_uranium_mission_calendar'
    verify_bindings(Path(manifest['source_root']),Path(manifest['fixture_root']),manifest)
    path=Path(__file__).with_name('analyze_native_probe.py')
    spec=importlib.util.spec_from_file_location('mission_calendar_receipt_verifier',path)
    evidence=importlib.util.module_from_spec(spec);spec.loader.exec_module(evidence)
    evidence.parse_log=parse_log
    result=evidence.analyze(manifest_path,launch_path,game_log)
    result['native_mission_calendar_verified']=result.pop('native_resource_trade_prototype_passed')
    result['receipt_verifier_sha256']=sha(path)
    result['analyzer_sha256']=sha(Path(__file__))
    return result


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--manifest',type=Path,required=True)
    cli.add_argument('--launch-receipt',type=Path,required=True)
    cli.add_argument('--game-log',type=Path,required=True)
    args=cli.parse_args()
    result=analyze(args.manifest,args.launch_receipt,args.game_log)
    print(json.dumps(result,indent=2))
    if not result['native_mission_calendar_verified']: raise SystemExit(1)


if __name__ == '__main__':main()
