"""Recorded-only native fuel probe analysis; never launches or edits game data."""
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import re
import sys
import native_state_trace as state_trace
import build_native_probe as native_builder
from build_native_probe import validate_cash_api_overlay


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def read_blocked_cash_records(text, require):
    rows=[]
    pattern=r'EON_PRIVATE_FUEL_CASH BLOCKED api=modify_treasury_effect ROOT=([A-Za-z0-9_-]*) THIS=(USA|HOL) FROM=([A-Za-z0-9_-]*) cash=([^ ]+) change=([^ ]+)\s*$'
    for line_index,line in enumerate(text.splitlines(),1):
        if 'EON_PRIVATE_FUEL_CASH' not in line:continue
        match=re.search(pattern,line)
        require(bool(match),'Malformed or wrong-recipient ordinary blocked cash log')
        if not match:continue
        try:
            cash,change=Decimal(match[4]),Decimal(match[5])
            require(cash.is_finite() and change.is_finite(),'Nonfinite ordinary blocked cash log')
        except ArithmeticError:
            require(False,'Invalid ordinary blocked cash numeric log');continue
        rows.append({'line_index':line_index,'root':match[1],'recipient_this':match[2],
                     'from':match[3],'cash':match[4],'change':match[5],'line':line})
    return rows


def analyze(manifest_path, log_path, receipt_path=None, diagnostic=False):
    manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    source=Path(manifest['source_root']); fixture=Path(manifest['fixture_root'])
    marker=manifest['marker']; errors=[]
    trace_config=manifest.get('state_trace')
    def require(condition,message):
        if not condition: errors.append(message)
    text=log_path.read_text(encoding='utf-8-sig',errors='replace')
    passed=re.findall(re.escape(marker)+r' PASS ([A-Za-z0-9_]+)',text)
    failed=re.findall(re.escape(marker)+r' FAIL ([A-Za-z0-9_]+)',text)
    high_accepted=marker+' OBS high_cash_sent ' in text
    excluded=manifest['conditional_assertions']['high_cash_rejected' if high_accepted else 'high_cash_accepted']
    expected=Counter(label for label in manifest['assertions'] if label not in excluded); actual=Counter(passed+failed)
    require(actual==expected,'Missing, unexpected or duplicated assertion labels: '+str(dict(expected-actual))+' / '+str(dict(actual-expected)))
    require(not failed,'Native assertions failed: '+str(failed))
    require(text.count(marker+' START fixture_loaded')==1,'Exactly one private startup required')
    require(not re.search(re.escape(marker)+r' (ABORT|DUPLICATE_PRIVATE_EVENT)',text),'Abort/duplicate private event marker')
    ends=re.findall(re.escape(marker)+r' END passes=([0-9.]+) fails=([0-9.]+)',text)
    require(len(ends)==1,'Exactly one complete END receipt required')
    if len(ends)==1:require(list(map(float,ends[0]))==[len(passed),len(failed)],'END counters disagree with recorded labels')
    def date(line):
        dates=re.findall(r'\[(\d{4}\.\d{2}\.\d{2}\.\d{2})\]',line)
        if not dates:raise ValueError('Missing native calendar in observation')
        year,month,day,hour=map(int,dates[-1].split('.'))
        if not 0<=hour<=24:raise ValueError('Invalid native hour')
        return dates[-1],datetime(year,month,day)+timedelta(hours=hour)
    obs={}; selections=[]; wait_ready={}
    for line_index,line in enumerate(text.splitlines(),1):
        match=re.search(re.escape(marker)+r' OBS ([A-Za-z0-9_]+) ',line)
        if match:
            label=match[1];require(label in manifest['observation_labels'] and label not in obs,'Unexpected/duplicate observation '+label)
            stamp,moment=date(line)
            obs[label]={'line_index':line_index,'line':line,'native_date':stamp,'date':moment}
        match=re.search(re.escape(marker)+r' WAIT_READY ([A-Za-z0-9_]+) ',line)
        if match:
            label=match[1];require(label not in wait_ready,'Duplicate result-aware readiness '+label)
            stamp,moment=date(line)
            wait_ready[label]={'line_index':line_index,'line':line,'native_date':stamp,'date':moment}
        match=re.search(r':\s*([^:\r\n]+):\s*(energy\.(?:1|10)\.[ab]) executed',line)
        if match:
            stamp,moment=date(line)
            selections.append({'line_index':line_index,'actor_name':match[1].strip(),'option':match[2],'native_date':stamp,'date':moment,'line':line})
    excluded_obs={'high_cash_rejected'} if high_accepted else {'high_cash_sent','high_cash_observed'}
    expected_obs=set(manifest['observation_labels'])-excluded_obs
    require(set(obs)==expected_obs,'Missing/unexpected required observations: '+str(sorted(expected_obs-set(obs)))+' / '+str(sorted(set(obs)-expected_obs)))
    rows=[]
    wait_config=manifest.get('result_aware_wait')
    wait_specs={row['name']:row for row in wait_config['cases']} if wait_config else {}
    if wait_config:
        expected_wait={row['name'] for row in manifest['actual_ai_cases'] if not row.get('optional_precision_branch') or high_accepted}
        require(set(wait_ready)==expected_wait,'Missing/unexpected result-aware readiness: '+str(sorted(expected_wait-set(wait_ready)))+' / '+str(sorted(set(wait_ready)-expected_wait)))
        require(wait_config.get('poll_hours') in (1,2) and wait_config.get('deadline_hours')==68,'Unexpected result-aware scheduling contract')
        if wait_config.get('poll_hours')==2:
            require(wait_config.get('max_poll_attempts')==72,'Unbounded result-aware native poll contract')
    for case in manifest['actual_ai_cases']:
        start,done=obs.get(case['begin']),obs.get(case['done'])
        if not start or not done:continue
        actor=re.search(r'recipient_name=(.*?) kind=',start['line'])
        require(bool(actor),'Missing original responder country name '+case['name'])
        actor_name=actor[1] if actor else ''
        choices=[row for row in selections if row['actor_name']==actor_name and start['line_index']<row['line_index']<done['line_index'] and start['date']<=row['date']<=done['date']]
        elapsed=(done['date']-start['date']).total_seconds()/3600
        valid=len(choices)==1 and choices[0]['option']==case['expected_option'] and elapsed>=case['minimum_hours']
        for record in (start,done):
            frame=re.search(r'ROOT=([^ ]+) THIS=([^ ]+) FROM=([^ ]+)',record['line'])
            valid=valid and bool(frame) and frame.groups()==('USA','USA','HOL')
        cash=re.search(r'cash_delta_kusd=(-?[0-9.]+)',done['line'])
        require(bool(cash),'Missing scaled cash observation '+case['name'])
        if cash and case['expected_option'].endswith('.a'):
            valid=valid and float(cash[1])!=0
        if wait_config:
            ready=wait_ready.get(case['name']);spec=wait_specs.get(case['name'])
            require(bool(ready and spec),'Missing result-aware case binding '+case['name'])
            if ready and spec:
                frame=re.search(r'ROOT=([^ ]+) THIS=([^ ]+) FROM=([^ ]+)',ready['line'])
                elapsed_ready=(ready['date']-start['date']).total_seconds()/3600
                observation_lag=(done['date']-ready['date']).total_seconds()/3600
                valid=valid and bool(frame) and frame.groups()==('USA','USA','HOL')
                valid=valid and start['line_index']<ready['line_index']<done['line_index']
                valid=valid and 0<=elapsed_ready<=spec['deadline_hours'] and 0<=observation_lag<=spec['observer_grace_hours']
                valid=valid and len(choices)==1 and choices[0]['line_index']<ready['line_index'] and choices[0]['date']<=ready['date']
                values={}
                for key in ('cash','expected_cash','stock','expected_stock','peer_cash','expected_peer_cash','peer_stock','expected_peer_stock','phase','partner','peer_phase','peer_partner'):
                    field=re.search(r'(?:^| )'+key+r'=(-?[0-9]+(?:\.[0-9]+)?)\b',ready['line'])
                    require(bool(field),'Missing result-aware outcome field '+case['name']+'/'+key)
                    if field:values[key]=float(field[1])
                valid=valid and len(values)==12
                if len(values)==12:
                    valid=valid and all(values[key]==values['expected_'+key] for key in ('cash','stock','peer_cash','peer_stock'))
                    valid=valid and all(values[key]==0 for key in ('phase','partner','peer_phase','peer_partner'))
                if wait_config.get('poll_hours')==2:
                    attempts=re.search(r'(?:^| )attempts=([0-9]+)\b',ready['line'])
                    valid=valid and bool(attempts) and 1<=int(attempts[1])<=spec['max_poll_attempts']
                require(valid,'Premature/unacknowledged or wrong asset result-aware outcome: '+case['name'])
        require(valid,'Original queued AI source choice, native interval, frame or payment invalid: '+case['name'])
        rows.append({'case':case['name'],'actual_source_queued_reply':True,'unchanged_original_events':True,
                     'native_elapsed_hours':elapsed,'expected_option':case['expected_option'],
                     'matched_original_selections':len(choices),'selection':({k:v for k,v in choices[0].items() if k!='date'} if len(choices)==1 else None),
                     'cash_delta_thousand_usd':float(cash[1]) if cash else None,'passed':valid,
                     'result_acknowledgement':'Both original AI slots are empty before next reset; original result options have no selection log.'})
    # The forced wrong peer precedes the real response; the forced duplicate is
    # after real result consumption. No unconsumed native result is replaced.
    if 'wrong_from_inert' in obs and rows:
        first=obs[manifest['actual_ai_cases'][0]['begin']];last=obs[manifest['actual_ai_cases'][0]['done']]
        wrong=obs['wrong_from_inert'];frame=re.search(r'ROOT=([^ ]+) THIS=([^ ]+) FROM=([^ ]+)',wrong['line'])
        require(frame is not None and frame.groups()==('HOL','HOL','NEP'),'Wrong-FROM calibration is not the actual third country')
        choices=[row for row in selections if first['line_index']<row['line_index']<last['line_index']]
        require(len(choices)==1 and wrong['line_index']<choices[0]['line_index'],'Wrong-FROM control was not before original reply')
    if 'duplicate_after_real_result' in obs and 'buy_accept_observed' in obs:
        require(obs['buy_accept_observed']['line_index']<obs['duplicate_after_real_result']['line_index'],'Duplicate callback preceded original result observation')
    if not high_accepted and 'high_cash_before' in obs and 'high_cash_after' in obs:
        begin,done=obs['high_cash_before'],obs['high_cash_after']
        require(not any(begin['line_index']<row['line_index']<done['line_index'] for row in selections),'Rejected high-cash quote unexpectedly issued source response')
    # Hash identity is mandatory. Explicit private control overlays are the only
    # permitted differences from the immutable source bytes used by the builder.
    overlay_sources={row['source'] for row in manifest['private_controls']}
    if trace_config:
        overlay_sources.update(row['source'] for row in trace_config['source_overlays'])
    for rel,digest in manifest['source_sha256'].items():
        expected_digest=manifest['fixture_sha256'][rel] if rel in overlay_sources else digest
        require((source/rel).is_file() and sha(source/rel)==expected_digest,'Changed/missing embedded source '+rel)
    for rel,digest in manifest['fixture_sha256'].items():
        require((fixture/rel).is_file() and sha(fixture/rel)==digest,'Changed/missing prepared fixture '+rel)
        require((source/rel).is_file() and sha(source/rel)==digest,'Changed/missing embedded fixture '+rel)
    # Re-resolve every copied effect/predicate from its original location, even
    # when its containing GUI file has the narrowly declared AI control overlay.
    spec=importlib.util.spec_from_file_location('fuel_recorded_grammar',source/'tools/validation/diplomacy_completion/check_native_grammar.py')
    g=importlib.util.module_from_spec(spec);sys.modules[spec.name]=g;spec.loader.exec_module(g);p=g.parser
    for control in manifest['private_controls']:
        if 'cash_api_selector' in control:
            try:validate_cash_api_overlay(p.ast((source/control['source']).read_bytes()),control)
            except (AssertionError,KeyError) as error:errors.append('Invalid ordinary cash API control: '+str(error))
    original_trace_bytes={};trace_records=[]
    if trace_config:
        require(trace_config.get('marker')==state_trace.MARKER,'Unexpected state trace marker')
        for declaration in trace_config['source_overlays']:
            rel=declaration['source'];raw=(source/rel).read_bytes()
            try:
                stripped=state_trace.strip_islands(raw,declaration['islands'])
                require(hashlib.sha256(stripped).hexdigest()==declaration['original_sha256']==manifest['source_sha256'][rel],'Trace does not recover original bytes '+rel)
                require(sha(source/rel)==declaration['played_sha256'],'Traced source bytes differ '+rel)
                require(json.loads(json.dumps(p.ast(stripped)))==declaration['original_ast'],'Trace does not recover original AST '+rel)
                original_trace_bytes[rel]=stripped
            except AssertionError as error:
                errors.append('Invalid source trace island '+rel+': '+str(error))
        for rel in {row['source'] for row in trace_config['private_islands']}:
            declarations=[row for row in trace_config['private_islands'] if row['source']==rel]
            try:state_trace.strip_islands((source/rel).read_bytes(),declarations)
            except AssertionError as error:errors.append('Invalid private trace island '+rel+': '+str(error))
        labels={row['label'] for spec in trace_config['source_overlays'] for row in spec['islands']}
        labels.update(row['label'] for row in trace_config['private_islands'])
        trace_records=state_trace.read_records(text,labels,require)
        for case in manifest['actual_ai_cases']:
            start,done=obs.get(case['begin']),obs.get(case['done'])
            if not start or not done:continue
            response=case['expected_option']
            result='energy.'+('2' if case['direction']==1 else '11')+'.a' if response.endswith('.a') else 'energy.'+('3' if case['direction']==1 else '12')+'.a'
            for option,actor,peer in ((response,'HOL','USA'),(result,'USA','HOL')):
                records=[]
                for suffix in ('before','after'):
                    matching=[row for row in trace_records if row['label']==option+'.'+suffix and start['line_index']<row['line_index']<done['line_index']]
                    require(len(matching)==1,'Missing/duplicated original callback trace '+case['name']+' '+option+'.'+suffix)
                    if len(matching)==1:
                        records+=matching
                        require(tuple(matching[0]['fields'].get(k) for k in ('ROOT','THIS','FROM'))==(actor,actor,peer),'Original callback trace frame differs '+case['name']+' '+option)
                        require(all(len(matching[0].get('flags',{}).get(tag,{}))==5 for tag in ('USA','HOL')),'Incomplete actual flag trace '+case['name']+' '+option)
                if len(records)==2:require(records[0]['line_index']<records[1]['line_index'],'Callback traces out of order '+option)
    for family in ('source_effect_bindings','source_trigger_bindings'):
        for name,binding in manifest[family].items():
            nodes=p.ast(original_trace_bytes.get(binding['source'],(source/binding['source']).read_bytes()))
            if 'selector' in binding:
                for key in binding['selector']:nodes=p.one(nodes,key)
            else:
                nodes=[v for k,op,v in nodes if k=='country_event' and p.one(v,'id')==binding['event_id']]
                require(len(nodes)==1,'Ambiguous bound source event '+name)
                nodes=nodes[0]
                if binding.get('option_effect'):
                    found=[v for k,op,v in nodes if k=='option' and p.one(v,'name')==binding['option_name']]
                    require(len(found)==1,'Ambiguous bound source option '+name)
                    nodes=[n for n in found[0] if n[0] not in ('name','trigger','ai_chance','ai_will_do','highlight')]
                else:nodes=p.one(nodes,'immediate')
            require(json.loads(json.dumps(nodes))==binding['ast'],'Source binding AST changed '+name)
    if wait_config:
        effect_nodes=p.ast((source/'common/scripted_effects/eon_private_fuel_probe_effects.txt').read_bytes())
        trigger_nodes=p.ast((source/'common/scripted_triggers/eon_private_fuel_probe_triggers.txt').read_bytes())
        for spec in wait_specs.values():
            for prefix,nodes in (('prepare',effect_nodes),('poll',effect_nodes),('ready',trigger_nodes)):
                key=spec[prefix+'_trigger' if prefix=='ready' else prefix+'_effect']
                found=[v for k,op,v in nodes if k==key]
                require(len(found)==1 and json.loads(json.dumps(found[0]))==spec[prefix+'_ast'],'Changed result-aware private AST '+key)
    cash_controls=[control for control in manifest['private_controls'] if 'cash_api_selector' in control]
    require(len(cash_controls)<=1,'Duplicated ordinary cash API controls')
    if cash_controls:
        validator_rel='tools/validation/nuclear_fuel_trade/build_native_probe.py'
        require(manifest['source_sha256'].get(validator_rel)==sha(Path(native_builder.__file__)),'Ordinary cash validator implementation differs from the source-bound builder')
    blocked_cash_records=read_blocked_cash_records(text,require) if cash_controls else []
    launch_bound=False
    if receipt_path and receipt_path.is_file():
        receipt=json.loads(receipt_path.read_text(encoding='utf-8-sig'))
        require(Path(receipt['source_root']).resolve()==source.resolve(),'Launch source differs')
        expected_manifest=receipt.get('fuel_fixture_manifest_sha256',receipt.get('manifest_sha256'))
        require(expected_manifest==sha(manifest_path),'Launch receipt does not bind this fuel manifest')
        require(Path(receipt['game_log']).resolve()==log_path.resolve(),'Launch game log differs')
        require(isinstance(receipt.get('pid'),int) and receipt['pid']>0,'Native PID missing')
        require(receipt.get('enabled_mods')==['mod/era_of_nations.mod'],'Unexpected enabled mods')
        start=json.loads(Path(receipt['start_receipt']).read_text(encoding='utf-8-sig'))
        require(start['pid']==receipt['pid'] and start['exe']==receipt['exe'],'Process receipt differs')
        require('-start_tag=NEP' in start['arguments'],'Native start tag must leave USA/HOL as AI')
        started=datetime.fromisoformat(start['process_start_utc'].replace('Z','+00:00'))
        require(log_path.stat().st_ctime>=started.timestamp()-3 and log_path.stat().st_mtime>=started.timestamp(),'Log predates recorded native process')
        require(sha(Path(receipt['exe']))==receipt['exe_sha256'].lower(),'Native executable hash differs')
        userdir=Path(receipt['user_dir'])
        require(log_path.resolve()==(userdir/'logs/game.log').resolve(),'Log is not in recorded native user directory')
        require(json.loads((userdir/'dlc_load.json').read_text(encoding='utf-8-sig'))['enabled_mods']==receipt['enabled_mods'],'Recorded profile mods differ')
        descriptor=(userdir/'mod/era_of_nations.mod').read_text(encoding='utf-8-sig')
        paths=re.findall(r'^\s*path\s*=\s*"([^"]+)"',descriptor,re.M)
        require(len(paths)==1 and Path(paths[0]).resolve()==source.resolve(),'Private profile mod path differs')
        system=(userdir/'logs/system.log').read_text(encoding='utf-8-sig',errors='replace')
        require(re.findall(r'Active Mod Count: (\d+)',system)==['1'],'Native active mod count differs')
        error_text=(userdir/'logs/error.log').read_text(encoding='utf-8-sig',errors='replace')
        relevant=[line for line in error_text.splitlines() if re.search(r'eon_private_fuel_probe|eon_nuclear_fuel_trade|eon_nuclear_fuel_exports_blocked|00_Energy_events',line,re.I)]
        require(not relevant,'Relevant native compiler/runtime errors: '+str(relevant[:20]))
        if cash_controls:
            cash_errors=[line for line in error_text.splitlines() if re.search(r'00_budget_effects|modify_treasury_effect',line,re.I)]
            require(not cash_errors,'Ordinary cash API native compiler/runtime errors: '+str(cash_errors[:20]))
        launch_bound=True
    elif not diagnostic:
        errors.append('Strict native acceptance requires a process/export/manifest-bound launch receipt')
    return {'schema':1,'manifest':str(manifest_path),'manifest_sha256':sha(manifest_path),'game_log':str(log_path),'game_log_sha256':sha(log_path),
            'assertions_passed':len(passed),'assertions_failed':failed,'actual_ai_cases':rows,'errors':errors,
            'launch_receipt_bound':launch_bound,'native_acceptance':not diagnostic and launch_bound and not errors,
            'state_trace_observations':trace_records,
            'ordinary_blocked_cash_observations':blocked_cash_records,
            'proof_scope':'Original energy.1/10 queued AI replies, naturally acknowledged original AI results, physical inventory and representable cash, controlled native frame boundaries.',
            'limits':manifest['limits']}


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--manifest',required=True,type=Path)
    cli.add_argument('--game-log',required=True,type=Path)
    cli.add_argument('--launch-receipt',type=Path)
    cli.add_argument('--out',type=Path)
    cli.add_argument('--diagnostic',action='store_true')
    args=cli.parse_args()
    result=analyze(args.manifest.resolve(),args.game_log.resolve(),args.launch_receipt,args.diagnostic)
    if args.out:
        assert not args.out.exists(),'Preserve previous acceptance receipt'
        args.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    if result['errors']:raise SystemExit(1)


if __name__=='__main__':main()
