"""Adversarial reader self-check using synthetic logs, never native evidence.

Run against an already embedded private preparation fixture. This verifies the
reader rejects plausible-looking incomplete receipts, not that HOI4 played them.
"""
from pathlib import Path
from datetime import datetime,timedelta
import argparse
import json
import tempfile
from analyze_native_probe import analyze


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--manifest',required=True,type=Path)
    args=cli.parse_args()
    manifest=args.manifest.resolve();m=json.loads(manifest.read_text())
    marker=m['marker'];rejected=m['conditional_assertions']['high_cash_accepted']
    labels=[label for label in m['assertions'] if label not in rejected]
    lines=[marker+' START fixture_loaded']+[marker+' PASS '+label for label in labels]
    def stamp(hour):return (datetime(2000,1,1)+timedelta(hours=hour)).strftime('[%Y.%m.%d.%H]')
    def obs(label,hour,extra='',frame=('USA','USA','HOL')):
        lines.append(stamp(hour)+' '+marker+' OBS '+label+' ROOT='+frame[0]+' THIS='+frame[1]+' FROM='+frame[2]+' '+extra)
    for index,case in enumerate(m['actual_ai_cases']):
        if case.get('optional_precision_branch'):continue
        start=index*(8 if m.get('result_aware_wait') else 72);obs(case['begin'],start,'recipient_name=Fixture Netherlands kind='+str(case['direction']))
        if index==0:obs('wrong_from_inert',start,frame=('HOL','HOL','NEP'))
        lines.append(stamp(start+1)+': Fixture Netherlands: '+case['expected_option']+' executed')
        if m.get('result_aware_wait'):
            lines.append(stamp(start+3)+' '+marker+' WAIT_READY '+case['name']+' ROOT=USA THIS=USA FROM=HOL attempts=2 cash=500 expected_cash=500 stock=1500 expected_stock=1500 peer_cash=500 expected_peer_cash=500 peer_stock=4500 expected_peer_stock=4500 phase=0 partner=0 peer_phase=0 peer_partner=0')
        obs(case['done'],start+(4 if m.get('result_aware_wait') else 68),'cash_delta_kusd='+('250' if case['expected_option'].endswith('.a') else '0'))
        if index==1:obs('duplicate_after_real_result',start+(5 if m.get('result_aware_wait') else 69),frame=('HOL','HOL','USA'))
    obs('high_cash_before',360);obs('high_cash_rejected',360);obs('high_cash_after',360)
    lines.append(marker+' END passes='+str(len(labels))+' fails=0')
    original='\n'.join(lines)+'\n'
    mutations={
        'missing_original_queued_choice':original.replace(': Fixture Netherlands: energy.10.a executed',': Fixture Netherlands: unrelated.1.a executed',1),
        'wrong_source_option':original.replace(': Fixture Netherlands: energy.10.a executed',': Fixture Netherlands: energy.10.b executed',1),
        'zero_payment':original.replace('cash_delta_kusd=250','cash_delta_kusd=0',1),
        'wrong_observer_country_frame':original.replace('OBS sell_accept_observed ROOT=USA THIS=USA FROM=HOL','OBS sell_accept_observed ROOT=HOL THIS=HOL FROM=USA',1),
        'duplicate_original_selection':original.replace(': Fixture Netherlands: energy.10.a executed',': Fixture Netherlands: energy.10.a executed\n[2000.01.01.02]: Fixture Netherlands: energy.10.a executed',1),
        'missing_end':original.rsplit(marker+' END ',1)[0],
    }
    if m.get('result_aware_wait'):
        mutations.update({
            'wrong_waiter_from':original.replace('WAIT_READY sell_accept ROOT=USA THIS=USA FROM=HOL','WAIT_READY sell_accept ROOT=USA THIS=USA FROM=NEP',1),
            'double_delivery_balance':original.replace('stock=1500 expected_stock=1500','stock=2000 expected_stock=1500',1),
            'premature_cash_balance':original.replace('cash=500 expected_cash=500','cash=499.999 expected_cash=500',1),
            'still_reserved_phase':original.replace('phase=0 partner=0 peer_phase=0 peer_partner=0','phase=2 partner=2 peer_phase=2 peer_partner=1',1),
            'waiter_deadline_exceeded':original.replace(stamp(3)+' '+marker+' WAIT_READY sell_accept',stamp(69)+' '+marker+' WAIT_READY sell_accept',1),
            'observer_before_readiness':original.replace(stamp(4)+' '+marker+' OBS sell_accept_observed',stamp(2)+' '+marker+' OBS sell_accept_observed',1),
            'missing_readiness': '\n'.join(line for line in lines if 'WAIT_READY sell_accept ' not in line)+'\n',
            'readiness_precedes_original_choice':original.replace(stamp(3)+' '+marker+' WAIT_READY sell_accept',stamp(0)+' '+marker+' WAIT_READY sell_accept',1),
            'duplicate_readiness':original.replace(stamp(3)+' '+marker+' WAIT_READY sell_accept',stamp(3)+' '+marker+' WAIT_READY sell_accept ROOT=USA THIS=USA FROM=HOL\n'+stamp(3)+' '+marker+' WAIT_READY sell_accept',1),
        })
        if m['result_aware_wait'].get('poll_hours')==2:
            mutations.update({'zero_poll_attempts':original.replace('attempts=2','attempts=0',1),
                              'poll_attempt_budget_exceeded':original.replace('attempts=2','attempts=73',1)})
    with tempfile.TemporaryDirectory(prefix='eon-fuel-reader-') as folder:
        log=Path(folder)/'synthetic.log';log.write_text(original)
        result=analyze(manifest,log,diagnostic=True)
        assert not result['errors'],result['errors']
        assert not result['native_acceptance'] and not result['launch_receipt_bound']
        rejected_controls=[]
        for name,text in mutations.items():
            log.write_text(text);result=analyze(manifest,log,diagnostic=True)
            assert result['errors'],('Reader accepted corrupted synthetic receipt',name)
            assert not result['native_acceptance']
            rejected_controls.append(name)
        log.write_text(original);strict=analyze(manifest,log,diagnostic=False)
        assert strict['errors'] and not strict['native_acceptance'],'Synthetic log without launch receipt became native evidence'
    print(json.dumps({'scope':'Reader sensitivity only: synthetic diagnostic logs, not game evidence','rejected_controls':rejected_controls,'strict_missing_receipt_rejected':True}))


if __name__=='__main__':main()
