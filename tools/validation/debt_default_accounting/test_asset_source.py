"""Exact four-body plus four-pending-guard byte ownership, no normalization.

This inverse is only a preservation view. All behavior runs the real current
AST in test_assets.py. Root's historical bailout journal is a separate gate.
"""
from pathlib import Path
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[3]
DECISIONS='common/decisions/bankruptcy_decisions.txt'
TRIGGERS='common/scripted_triggers/eon_debt_default_accounting_triggers.txt'
JOURNAL='tools/validation/debt_default_accounting/_asset_source_islands.json'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_decisions(raw,journal):
    assert sha(raw)==journal['decision_after_sha256']
    assert not raw.startswith(b'\xef\xbb\xbf') and b'\r' not in raw
    text=raw.decode('utf-8')
    assert len(journal['decision_islands'])==4
    assert {entry['id'] for entry in journal['decision_islands']}=={
        'debt_default_sell_civilian_factories','debt_default_dismantle_military_factories',
        'debt_default_scrap_dockyard','debt_default_cut_down_government_services'}
    for island in reversed(journal['decision_islands']):
        for field in ('before','after'):
            assert island[field].startswith('\t'+island['id']+' = {') and island[field].endswith('\t}')
        assert text.count(island['after'])==1
        text=text.replace(island['after'],island['before'],1)
    assert sha(text.encode('utf-8'))==journal['decision_before_sha256']


def validate_triggers(raw,journal):
    assert sha(raw)==journal['trigger_after_sha256']
    assert not raw.startswith(b'\xef\xbb\xbf') and b'\r' not in raw
    insert=journal['start_record_pending_guard'].encode('utf-8')
    assert raw.count(insert)==1
    assert len(re.findall(rb'NOT = \{ has_decision = debt_default_',insert))==4
    assert sha(raw.replace(insert,b'',1))==journal['trigger_before_sha256']


def main():
    raw=(ROOT/JOURNAL).read_bytes()
    assert sha(raw)=='6aff183ab2803cd4845c253e8f1fb6a681a1f24246eb84b42232b9b159d2e0f1'
    journal=json.loads(raw)
    decision=(ROOT/DECISIONS).read_bytes();triggers=(ROOT/TRIGGERS).read_bytes()
    validate_decisions(decision,journal);validate_triggers(triggers,journal)
    rejected=[]
    def reject(label,fn):
        try:
            fn()
        except AssertionError:
            rejected.append(label)
        else:
            raise AssertionError(('Byte mutation survived',label))
    for index,island in enumerate(journal['decision_islands']):
        for needle,replacement,label in (
            ('days_remove = 5','days_remove = 4','delay'),
            ('cost = 25','cost = 0','cost'),
            ('eon_debt_default_asset_available_tt','unapproved_tooltip','available_tooltip'),
            ('eon_debt_default_asset_liquidation_tt','sell_15_billion_factory','valuation_tooltip'),
            ('_dispose = yes','_dispose = no','actual_callback'),
        ):
            assert island['after'].count(needle)==1
            mutant=decision.replace(island['after'].encode(),island['after'].replace(needle,replacement,1).encode(),1)
            reject(f"{island['id']}:{label}",lambda mutant=mutant:validate_decisions(mutant,journal))
    reject('outside_owned_bodies',lambda:validate_decisions(decision+b'\n# extra unrelated edit\n',journal))
    for route in [item['id'] for item in journal['decision_islands']]:
        line=('\tNOT = { has_decision = '+route+' }\n').encode()
        assert triggers.count(line)==1
        reject('missing_pending:'+route,lambda line=line:validate_triggers(triggers.replace(line,b'',1),journal))
    reject('other_trigger_predicate',lambda:validate_triggers(triggers.replace(b'interest_rate > 14.999',b'interest_rate > 0',1),journal))
    print(json.dumps({'checks_passed':True,'exact_decision_islands':4,
                      'exact_pending_start_guards':4,'outside_owned_bytes_identical':True,
                      'bounded_byte_mutants_rejected':rejected,
                      'source_sha256':{DECISIONS:sha(decision),TRIGGERS:sha(triggers),JOURNAL:sha(raw),
                                       'tools/validation/debt_default_accounting/test_asset_source.py':sha(Path(__file__).read_bytes())},
                      'behavior_inverse_applied':False},indent=2))


if __name__=='__main__':
    main()
