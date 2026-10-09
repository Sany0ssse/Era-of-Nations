"""Actual-source asset disposal, bounded accounting, callbacks and old RED.

The state fixture observes independent building stock. It does not implement
an alternate liquidation algorithm; every eligibility/amount/receipt follows
the current AST. Real random selection, economics and five-day timers remain
native boundaries. Historical RED uses a digest-bound selected source AST.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import _model as m
from _asset_model import AssetModel

ROOT=Path(__file__).resolve().parents[3]
DECISIONS='common/decisions/bankruptcy_decisions.txt'
CORE_EFFECTS='common/scripted_effects/eon_debt_default_accounting_effects.txt'
CORE_TRIGGERS='common/scripted_triggers/eon_debt_default_accounting_triggers.txt'
EFFECTS='common/scripted_effects/eon_debt_default_asset_effects.txt'
TRIGGERS='common/scripted_triggers/eon_debt_default_asset_triggers.txt'
ROUTES=[('debt_default_sell_civilian_factories','civilian','industrial_complex'),
        ('debt_default_dismantle_military_factories','military','arms_factory'),
        ('debt_default_scrap_dockyard','dockyard','dockyard'),
        ('debt_default_cut_down_government_services','offices','offices')]


def entries(text):
    return {key:body for _,_,category in m.ast(text) if isinstance(category,list)
            for key,_,body in category if isinstance(body,list)}


def walk(nodes):
    for node in nodes:
        yield node
        if isinstance(node[2],list):
            yield from walk(node[2])


def state(building, count=1, owned=True, controlled=True, remove_fails=False):
    return {'id':123,'owned':owned,'controlled':controlled,
            'remove_fails':remove_fails,'buildings':{building:count}}


def fixture(effects,triggers,building='industrial_complex',claim=5.5,cash=7,
            total=50,active=True,overdue=False,states=None,**kwargs):
    model=AssetModel(effects,triggers,cash,claim,active=active,overdue=overdue,
                     states=states if states is not None else [state(building)],**kwargs)
    model.variables['debt_default_total']=total
    # Retain a prior receipt to prove every rejected callback preserves it.
    model.variables.update({'eon_debt_default_asset_sequence':7,
                            'eon_debt_default_asset_kind':99,
                            'eon_debt_default_asset_credit':77})
    return model


def paid(model):
    return {k:v for k,v in model.variables.items()
            if k.startswith('eon_debt_default_asset_') and not k.startswith('eon_debt_default_asset_attempt_')}


def financial_snapshot(model):
    return {k:v for k,v in model.variables.items() if not k.startswith('eon_debt_default_asset_attempt_')}


def main():
    effects=m.definitions(CORE_EFFECTS)|m.definitions(EFFECTS)
    triggers=m.definitions(CORE_TRIGGERS)|m.definitions(TRIGGERS)
    current=entries(m.read(DECISIONS))
    legacy_path=ROOT/'tools/validation/debt_default_accounting/_legacy_asset_ast.json'
    raw=legacy_path.read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='98e35aa3dc7a1feedd341ff92419345aebcd03331924c9ae7ab2698c612362ab'
    legacy=json.loads(raw)
    assert legacy['source_sha256']=='fd89949d99fa518c5d1a5352776fedc56ddde4623cc97350108026e8ba28f9b7'
    def tree(nodes):
        return [(k,o,tree(v) if isinstance(v,list) else v) for k,o,v in nodes]
    old={key:tree(body) for key,body in legacy['decisions'].items()}
    reds=[]
    for route,kind,building in ROUTES:
        for label,claim,count,controlled in [('fractional_claim',5.5,1,True),
                                             ('settled_queued',0,1,True),
                                             ('missing_asset',20,0,True),
                                             ('occupied_asset',20,1,False)]:
            model=fixture({}, {},building,claim=claim,states=[state(building,count,controlled=controlled)])
            model.effect(m.one(old[route],'remove_effect'))
            assert model.value('debt_default_left')==claim-10
            assert model.states[0]['buildings'][building]==max(0,count-1)
            assert model.value('treasury')==7 and model.value('debt')==73
            reds.append({'route':route,'case':label,'claim_after':model.value('debt_default_left')})
    # Actual old construction had no pending-token protection after settlement.
    assert legacy['core_trigger_source_sha256']=='b7ebf1b71021034882f13c0644f0a101272e276a8987f527edc76961bab01935'
    old_start=tree(legacy['start_record_available'])
    for route,_,_ in ROUTES:
        model=fixture(effects,triggers,claim=0,total=0,active=False,cash=3,interest=20)
        model.decisions.add(route)
        assert model.trigger(old_start) and not model.trigger(triggers['eon_debt_default_start_record_available'])

    cases=0
    def success_contract(ceffects=effects,ctriggers=triggers,callback=None):
        nonlocal cases
        for index,(route,kind,building) in enumerate(ROUTES,1):
            available=m.one(current[route],'available')
            removal=callback if callback is not None else m.one(current[route],'remove_effect')
            assert m.one(current[route],'days_remove')=='5' and m.one(current[route],'cost')=='25'
            # Timed effect rechecks live data and independently observes physical stock.
            for claim in (.001,.5,5.5,10,20):
                credit=min(10,claim);excess=10-credit
                for cash in (-50,0,7,1000000-excess):
                    for active,overdue in ((True,False),(False,True)):
                        model=fixture(ceffects,ctriggers,building,claim=claim,cash=cash,active=active,overdue=overdue)
                        assert model.trigger(m.one(current[route],'visible'))
                        assert model.trigger(available)
                        model.decisions.add(route) # Own current delayed callback may still be present.
                        model.effect(removal)
                        expected_claim=claim-credit
                        assert abs(model.value('debt_default_left')-expected_claim)<1e-8
                        assert abs(model.value('treasury')-(cash+excess))<1e-8
                        assert model.value('debt')==73 and model.states[0]['buildings'][building]==0
                        assert model.value('eon_debt_default_asset_sequence')==8
                        assert model.value('eon_debt_default_asset_kind')==index
                        assert model.value('eon_debt_default_asset_value')==10
                        assert model.value('eon_debt_default_asset_credit')==credit
                        assert abs(model.value('eon_debt_default_asset_excess')-excess)<1e-8
                        assert model.value('eon_debt_default_asset_credit')+model.value('eon_debt_default_asset_excess')==10
                        assert model.value('eon_debt_default_asset_cash_before')==cash
                        assert model.value('eon_debt_default_asset_cash_after')==cash+excess
                        assert model.value('eon_debt_default_asset_claim_before')==claim
                        assert model.value('eon_debt_default_asset_claim_after')==expected_claim
                        assert model.value('eon_debt_default_asset_state')==123
                        assert model.value('eon_debt_default_asset_building_before')==1
                        assert model.value('eon_debt_default_asset_building_after')==0
                        assert model.value('eon_debt_default_asset_attempt_sequence')==1
                        assert model.value('eon_debt_default_asset_attempt_outcome')==3
                        assert model.booms==0 and model.updates==1
                        if overdue and expected_claim==0:
                            assert model.value('debt_default_total')==0 and not model.flags
                        old_paid=paid(model);old_finance=financial_snapshot(model)
                        model.effect(removal) # Closed OR no remaining physical asset.
                        assert paid(model)==old_paid and financial_snapshot(model)==old_finance
                        assert model.value('eon_debt_default_asset_attempt_sequence')==2
                        assert model.value('eon_debt_default_asset_attempt_outcome')==0
                        assert model.updates==1
                        cases+=1

    success_contract()
    def negative_contract(ceffects=effects,ctriggers=triggers):
        nonlocal cases
        for route,kind,building in ROUTES:
            bad_cases=[dict(claim=0),dict(claim=-1),dict(total=0),dict(total=-1),
                       dict(active=False),dict(exists=False),
                       dict(states=[state(building,0)]),
                       dict(states=[state(building,controlled=False)]),
                       dict(states=[state(building,owned=False)]),
                       dict(claim=5.5,cash=999995.501),
                       dict(claim=.5,cash=1000000),
                       dict(states=[state(building,remove_fails=True)])]
            for options in bad_cases:
                model=fixture(ceffects,ctriggers,building,**options)
                # Failed physical removal is not predictable in the button gate.
                if not options.get('states',[{}])[0].get('remove_fails',False):
                    assert not model.trigger(m.one(current[route],'available'))
                before=financial_snapshot(model);stocks=deepcopy(model.states)
                model.effect(m.one(current[route],'remove_effect'))
                assert financial_snapshot(model)==before and model.states==stocks
                assert model.updates==0 and model.booms==0
                assert model.value('eon_debt_default_asset_attempt_sequence')==1
                assert model.value('eon_debt_default_asset_attempt_outcome')== (2 if options.get('states',[{}])[0].get('remove_fails',False) else 0)
                cases+=1
            # Zero excess needs no additional treasury headroom.
            model=fixture(ceffects,ctriggers,building,claim=20,cash=1000001)
            assert model.trigger(m.one(current[route],'available'))
            model.effect(m.one(current[route],'remove_effect'))
            assert model.value('treasury')==1000001 and model.value('debt_default_left')==10
            # Another queued asset decision prevents parallel disposition.
            for other,_,_ in ROUTES:
                if other!=route:
                    model=fixture(ceffects,ctriggers,building)
                    model.decisions.add(other);before=financial_snapshot(model)
                    assert not model.trigger(m.one(current[route],'available'))
                    model.effect(m.one(current[route],'remove_effect'))
                    assert financial_snapshot(model)==before and model.states[0]['buildings'][building]==1
                    cases+=1
            # Repay while the disposal is queued; old callback then has no right
            # to remove anything. New default waits until the queued entry ends.
            model=fixture(ceffects,ctriggers,building,claim=5.5,cash=10,active=False,overdue=True,interest=20)
            model.decisions.add(route)
            assert model.trigger(ctriggers['eon_debt_default_pay_10_available'])
            model.effect(ceffects['eon_debt_default_pay_10'])
            assert model.value('treasury')==4.5 and model.value('debt_default_left')==0
            before=financial_snapshot(model)
            assert not model.trigger(ctriggers['eon_debt_default_start_available'])
            model.effect(m.one(current[route],'remove_effect'))
            assert financial_snapshot(model)==before and model.states[0]['buildings'][building]==1
            model.decisions.remove(route) # Explicit adapter clock boundary.
            assert model.trigger(ctriggers['eon_debt_default_start_available'])
            cases+=1
    negative_contract()
    accepted_cases=cases

    rejected=[]
    def mutation(label, mutate, contract):
        ceffects,ctriggers=deepcopy(effects),deepcopy(triggers)
        mutate(ceffects,ctriggers)
        try:
            contract(ceffects,ctriggers)
        except AssertionError:
            rejected.append(label)
        else:
            raise AssertionError(('Mutation survived',label))
    def remove_node(nodes,predicate):
        found=0
        for index in range(len(nodes)-1,-1,-1):
            node=nodes[index]
            if predicate(node):
                del nodes[index];found+=1
            elif isinstance(node[2],list):
                found+=remove_node(node[2],predicate)
        return found
    def drop_guard(e,t):
        assert remove_node(t['eon_debt_default_asset_record_available'],lambda n:n==('check_variable','=','debt_default_left'))==0
        assert remove_node(t['eon_debt_default_asset_record_available'],lambda n:n[0]=='check_variable' and n[2]==[('debt_default_left','>','0')])==1
    mutation('positive_claim_guard',drop_guard,negative_contract)
    def drop_certificate(e,t):
        assert remove_node(t['eon_debt_default_asset_record_available'],lambda n:n[0]=='check_variable' and n[2]==[('debt_default_total','>','0')])==1
    mutation('positive_certificate',drop_certificate,negative_contract)
    mutation('capacity_before_disposal',lambda e,t:remove_node(t['eon_debt_default_asset_financial_available'],lambda n:n[0]=='OR'),negative_contract)
    def remove_proof(e,t):
        assert remove_node(e['eon_debt_default_asset_settle_removed'],lambda n:n[0]=='check_variable' and n[2]==[('eon_debt_default_asset_removed','=','1')])==1
    mutation('physical_removal_proof',remove_proof,negative_contract)
    def lose_controller(e,t):
        for _,kind,_ in ROUTES:
            assert remove_node(t[f'eon_debt_default_asset_{kind}_available'],lambda n:n[0]=='is_controlled_by')==1
    mutation('owned_controlled_gate',lose_controller,negative_contract)
    def credit_nominal(e,t):
        for node in walk(e['eon_debt_default_asset_settle_removed']):
            if node[0]=='subtract_from_variable' and node[2]==[('debt_default_left','=','eon_debt_default_asset_quoted_credit')]:
                node[2][0]=('debt_default_left','=','10');return
        raise AssertionError('No debit')
    mutation('credit_minimum',credit_nominal,success_contract)
    def lose_excess(e,t):
        assert remove_node(e['eon_debt_default_asset_settle_removed'],lambda n:n[0]=='add_to_variable' and n[2]==[('treasury','=','eon_debt_default_asset_quoted_excess')])==1
    mutation('excess_proceeds_conservation',lose_excess,success_contract)
    def paid_noop(e,t):
        e['eon_debt_default_asset_civilian_dispose'].insert(0,('add_to_variable','=',[('eon_debt_default_asset_sequence','=','1')]))
    mutation('paid_receipt_on_noop',paid_noop,negative_contract)
    def pending_guard(e,t):
        assert remove_node(t['eon_debt_default_start_record_available'],lambda n:n[0]=='NOT' and n[2]==[('has_decision','=','debt_default_sell_civilian_factories')])==1
    mutation('pending_old_callback_new_generation',pending_guard,negative_contract)
    # The real callback selector may not be replaced with a country-only mask.
    def wrong_type(e,t):
        for node in walk(e['eon_debt_default_asset_civilian_dispose']):
            if node[0]=='remove_building':
                node[2][0]=('type','=','arms_factory');return
    mutation('exact_physical_asset_type',wrong_type,success_contract)

    # Success and attempt receipts are not financial source predicates.
    for route,kind,building in ROUTES:
        assert m.one(current[route],'visible')==[('eon_debt_default_payment_period_available','=','yes')]
        assert m.one(current[route],'available')==[('custom_trigger_tooltip','=',[
            ('tooltip','=','eon_debt_default_asset_available_tt'),
            (f'eon_debt_default_asset_{kind}_available','=','yes')])]
        assert m.one(current[route],'remove_effect')==[
            ('custom_effect_tooltip','=','eon_debt_default_asset_liquidation_tt'),
            (f'eon_debt_default_asset_{kind}_dispose','=','yes')]
        for key in ('icon','days_remove','cost','ai_will_do'):
            assert m.one(current[route],key)==m.one(old[route],key)
    assert not any(k in ('modify_treasury_effect','clamp_variable','send_equipment') for k,o,v in walk(m.ast(m.read(EFFECTS))))
    assert not any(k in ('subtract_from_variable','add_to_variable','set_variable') and isinstance(v,list) and any(c[0]=='debt' for c in v)
                   for k,o,v in walk(m.ast(m.read(EFFECTS))))
    sources=[DECISIONS,CORE_EFFECTS,CORE_TRIGGERS,EFFECTS,TRIGGERS,
             'tools/validation/debt_default_accounting/_model.py',
             'tools/validation/debt_default_accounting/_asset_model.py',
             'tools/validation/debt_default_accounting/_legacy_asset_ast.json',
             'tools/validation/debt_default_accounting/test_assets.py']
    print(json.dumps({'checks_passed':True,'actual_AST_cases':accepted_cases,'old_RED_cases':reds,
                      'bounded_mutants_rejected':rejected,
                      'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
                      'native_boundaries':['Actual remove_building/state getters','5-day engine callback and decision expiry',
                                           'Random state selection','Economic refresh and ordinary income','Actual GUI clicks']},indent=2))


if __name__=='__main__':
    main()
