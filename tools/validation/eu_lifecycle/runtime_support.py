"""PRIVATE proposal: source complete_effect AST dispatched by event, never a click.

Does not install, prepare a launcher profile, launch, edit production or modify
native109. The frozen original 114 predictions remain a separate contract.
"""
from pathlib import Path
from copy import deepcopy
import hashlib
import importlib.util
import json
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[3]
BASE_PATH = HERE / 'extension_support.py'
SOURCE_METHOD = 'source complete_effect AST dispatched by event'
AI_IDS = ('eon_eu_notify_withdrawal', 'eon_eu_revoke_withdrawal',
          'eon_eu_extension_propose', 'eon_eu_extension_approve',
          'eon_eu_extension_reject', 'eon_eu_extension_abstain',
          'eon_eu_extension_accept_final', 'eon_eu_extension_cancel_proposal')
GOLDEN114 = '39f60d06ad216072284d6c9a72ed5c7003857ea2bec47a2c799ceef31ab58166'
BASE_SHA256 = 'eacafff928b5d773be6f99ad2fdf5c924e23ec1fa2d34841c343dd4ceef14121'

# This adapter replaces only the PRIVATE generator's action-dispatch function.
# The source callback is planned unconditionally after the API diagnostic.
# Its execution is gated by source prerequisites, never by the raw API result.
ADAPTER = r'''
    runtime_actions = []
    def decision(ident, expected_actor=None):
        nonlocal decision_sequence
        decision_sequence += 1
        assert ident in AI_IDS
        action = actions[ident]
        assert one(action, 'cost') == '0', ('Unsupported nonzero cost', ident)
        assert not any(k in ('custom_cost_trigger', 'custom_cost_text', 'cost_trigger') for k, _, _ in action)
        gates = []
        for key in ('allowed', 'visible'):
            gates.extend(next((v for k, _, v in categories[action_categories[ident]] if k == key), []))
        for key in ('allowed', 'visible', 'available', 'target_root_trigger', 'target_trigger'):
            gates.extend(next((v for k, _, v in action if k == key), []))
        gates.append(('has_political_power', '>=', '0'))
        gates.append(('check_variable', '=', [('var', '=', 'ROOT.id'), ('value', '=', 'THIS.id'), ('compare', '=', 'equals')]))
        targeted = any(k == 'target_trigger' for k, _, _ in action)
        if targeted:
            assert expected_actor in MEMBERS
            gates.extend([('tag', '=', expected_actor), ('FROM', '=', [('tag', '=', 'POL')])])
        complete = one(action, 'complete_effect')
        stamp = f'ACTION_{decision_sequence:03d}_{ident.upper()}'
        prefix = f'global.{namespace}_handler_{decision_sequence:03d}_'
        counter_fields = {
            'answer':'eon_eu_extension_answer_count', 'yes':'eon_eu_extension_yes_count',
            'no':'eon_eu_extension_no_count', 'abstain':'eon_eu_extension_abstain_count',
            'approvals':'eon_eu_extension_approvals^num', 'rejections':'eon_eu_extension_rejections^num',
            'abstentions':'eon_eu_extension_abstentions^num', 'queue':'eon_eu_extension_queued_units',
            'notice':'eon_eu_extension_notice_serial', 'project':'eon_eu_extension_proposal_serial',
            'project_notice':'eon_eu_extension_project_notice_serial',
            'electorate':'eon_eu_extension_electorate_total'}
        def snapshot():
            return ''.join(setv(prefix + field, 'POL.' + token) for field, token in counter_fields.items())
        def unchanged(fields=counter_fields):
            return ''.join(cv('POL.'+counter_fields[field], prefix+field) for field in fields)
        def witness(stage):
            label = 'HANDLER_' + stamp + '_' + stage
            current_identity = setv(prefix+'current_treaty', 0)+setv(prefix+'current_proposal', 0)
            current_identity += scope('POL', 'if = { limit = { has_idea = withdrawal_treaty } '+setv(prefix+'current_treaty', 1)+' } '
                               +'if = { limit = { has_country_flag = eon_eu_withdrawal_proposal } '+setv(prefix+'current_proposal', 1)+' } ')
            payload = ('actor=[?ROOT.id] scope=[?THIS.id] sender=[?FROM.id] target=[?POL.id] '
                       f'expected_actor=[?{expected_actor or "THIS"}.id] method=source_complete_effect_AST_dispatched_by_event '
                       'answer=[?POL.eon_eu_extension_answer_count] yes=[?POL.eon_eu_extension_yes_count] '
                       'no=[?POL.eon_eu_extension_no_count] abstain=[?POL.eon_eu_extension_abstain_count] '
                       'approvals=[?POL.eon_eu_extension_approvals^num] rejections=[?POL.eon_eu_extension_rejections^num] '
                       'abstentions=[?POL.eon_eu_extension_abstentions^num] queue=[?POL.eon_eu_extension_queued_units] '
                       'notice=[?POL.eon_eu_extension_notice_serial] project=[?POL.eon_eu_extension_proposal_serial] '
                       'project_notice=[?POL.eon_eu_extension_project_notice_serial] '
                       'electorate=[?POL.eon_eu_extension_electorate_total] '
                       f'treaty=[?{prefix}current_treaty] treaty_proposal=[?{prefix}current_proposal] '
                       f'gate=[?{prefix}gate] '
                       f'handler_count=[?global.{namespace}_handler_invocations]')
            return current_identity + context(label, expected_actor) + f'log = "{marker} TRACE {label} {payload}" '
        activate = (f'activate_targeted_decision = {{ target = POL decision = {ident} }} '
                    if targeted else f'activate_decision = {ident} ')
        text = snapshot() + setv(prefix+'gate', 0)
        text += setv(prefix+'invocations', f'global.{namespace}_handler_invocations')
        text += 'if = { limit = { '+render(gates)+' } '+setv(prefix+'gate', 1)+' } '
        text += witness('BEFORE_API')
        text += 'if = { limit = { '+render(gates)+' } '
        text += f'log = "{marker} TRACE HANDLER_{stamp}_RAW_UI_ACTIVATION_REQUESTED" '+activate+' } '
        text += witness('AFTER_RAW_API')
        text += bool_observation('HANDLER_'+stamp+'_INTERFACE_ACTIVE', f'has_decision = {ident}')
        text += check('runtime_'+stamp.lower()+'_raw_api_does_not_execute_handler', unchanged()+
                      cv(f'global.{namespace}_handler_invocations',prefix+'invocations'),
                      'Interface activation is observed separately; it must not alter the canonical response ledger or execute the explicit event adapter')
        # Treaty identity is a separate input witness, never synthesized consent.
        text += setv(prefix+'treaty', 0)+setv(prefix+'treaty_proposal', 0)
        text += scope('POL', 'if = { limit = { has_idea = withdrawal_treaty } '+setv(prefix+'treaty', 1)+' } '
                      +'if = { limit = { has_country_flag = eon_eu_withdrawal_proposal } '+setv(prefix+'treaty_proposal', 1)+' } ')
        text += witness('BEFORE_EXPLICIT_HANDLER')
        text += 'if = { limit = { '+render(gates)+' } '
        text += f'log = "{marker} TRACE HANDLER_{stamp}_SOURCE_COMPLETE_AST_INVOKED" '
        text += f'add_to_variable = {{ global.{namespace}_handler_invocations = 1 }} '+render(complete)+' } '
        text += witness('AFTER_EXPLICIT_HANDLER')
        text += setv(prefix+'expected_invocations',prefix+'invocations')
        text += f'add_to_variable = {{ {prefix}expected_invocations = {prefix}gate }} '
        text += check('runtime_'+stamp.lower()+'_planned_or_untaken_dispatch_count',
                      cv(f'global.{namespace}_handler_invocations',prefix+'expected_invocations'),
                      'Exact source gates determine one planned dispatch or an untaken handler; the raw API outcome does not choose a fallback')
        if targeted:
            kind = {'eon_eu_extension_approve':('approvals','yes'),
                    'eon_eu_extension_reject':('rejections','no'),
                    'eon_eu_extension_abstain':('abstentions','abstain')}[ident]
            delta = ''
            for field in ('answer','yes','no','abstain','approvals','rejections','abstentions'):
                text += setv(prefix+'expected_'+field,prefix+field)
                if field in ('answer',)+kind:
                    text += f'add_to_variable = {{ {prefix}expected_{field} = {prefix}gate }} '
                delta += cv('POL.'+counter_fields[field],prefix+'expected_'+field)
            identity = unchanged(('notice','project','project_notice','electorate','queue'))
            identity += 'if = { limit = { '+cv(prefix+'treaty',1)+' } POL = { has_idea = withdrawal_treaty } } '
            identity += 'else = { POL = { NOT = { has_idea = withdrawal_treaty } } } '
            identity += 'if = { limit = { '+cv(prefix+'treaty_proposal',1)+' } POL = { has_country_flag = eon_eu_withdrawal_proposal } } '
            identity += 'else = { POL = { NOT = { has_country_flag = eon_eu_withdrawal_proposal } } } '
            identity += f'tag = {expected_actor} FROM = {{ tag = POL }} '+cv('ROOT.id','THIS.id')+cv('FROM.id','POL.id')
            identity += 'if = { limit = { '+cv(prefix+'gate',1)+' } '
            identity += 'POL = { is_in_array = { '+counter_fields[kind[0]].removesuffix('^num')+' = ROOT } } } '
            text += check('runtime_'+stamp.lower()+'_exact_actor_delta_and_identity',delta+identity,
                          'One exact actor response changes only its selected canonical ledger and recount; notice, project, electorate, queue and separate withdrawal treaty remain bound')
            runtime_actions.append({'decision':ident,'actor_tag':expected_actor,'target_tag':'POL',
                                   'stamp':'HANDLER_'+stamp,'increment_array':kind[0],
                                   'increment_counter':kind[1],'method':SOURCE_METHOD})
            # Direct repeated source callback is an explicit negative backend
            # control, not another frontend click or another activation API.
            text += snapshot()+witness('BEFORE_DIRECT_REPLAY')
            text += f'log = "{marker} TRACE HANDLER_{stamp}_EXPLICIT_NEGATIVE_DIRECT_REPLAY" '+render(complete)+' '
            text += witness('AFTER_DIRECT_REPLAY')
            text += check('runtime_'+stamp.lower()+'_source_replay_inert',unchanged(),
                          'Repeated exact source complete_effect cannot duplicate a recorded response')
        elif ident == 'eon_eu_revoke_withdrawal':
            clean = 'POL = { has_idea = EU_member NOT = { has_country_flag = Article_50 } '
            clean += 'NOT = { has_country_flag = eon_eu_extension_notice_initialized } '
            clean += 'NOT = { has_country_flag = eon_eu_withdrawal_deadline } '
            clean += 'NOT = { has_active_mission = EU_exit } NOT = { has_active_mission = EU_exit_three_month } '
            clean += cv('eon_eu_extension_queued_units',0)+cv('eon_eu_extension_queued_notice_serial',0)
            clean += cv('eon_eu_extension_queued_proposal_serial',0)+cv('eon_eu_extension_project_notice_serial',0)
            clean += cv('eon_eu_extension_approvals^num',0)+cv('eon_eu_extension_rejections^num',0)+cv('eon_eu_extension_abstentions^num',0)+' } '
            text += check('runtime_'+stamp.lower()+'_revocation_cleans_consumed_or_pending_notice',
                          'if = { limit = { '+cv(prefix+'gate',1)+' } '+clean+' } ',
                          'A taken source revocation clears pending/consumed extension clocks and identity; an untaken action cannot manufacture cleanup')
        return text

'''

EXTRA = r'''
    # Extra veto/cleanup chapter follows the original six clock chapters.
    start = private_political_boundary('runtime_veto')
    start += 'if = { limit = { NOT = { has_idea = EU_member } } set_country_flag = eon_eu_admission_commit add_ideas = EU_member } '
    start += 'clr_country_flag = cant_invoke_article_50 remove_ideas = no_deal_exit remove_ideas = withdrawal_treaty eon_eu_refresh_membership = yes '
    start += decision('eon_eu_notify_withdrawal') + decision('eon_eu_extension_propose')
    for index, tag in enumerate(MEMBERS): start += schedule(tag, 2401+index, 2*(index+1))
    start += schedule('POL',2409,11)+schedule('POL',2410,16)
    event(2400,start)
    for index, tag in enumerate(MEMBERS):
        ident = 'eon_eu_extension_reject' if index == 1 else ('eon_eu_extension_abstain' if index == 5 else 'eon_eu_extension_approve')
        body = check('runtime_veto_pair_'+tag,f'tag = {tag} FROM = {{ tag = POL }} ',
                     'Independent country_event sent by POL preserves actual responder ROOT and proposal FROM')
        body += decision(ident,expected_actor=tag)
        if index == 4:
            local = (decision('eon_eu_extension_accept_final')+
                          check('runtime_veto_silence_does_not_count_as_abstention',cv(q,0)+cv('eon_eu_extension_answer_count',5)+
                                cv('eon_eu_extension_abstain_count',0),
                                'Fifth response leaves a silent sixth unrepresented; no missing answer is invented'))
            event(2409,local)
        event(2401+index,body)
    final = decision('eon_eu_extension_accept_final')
    final += check('runtime_veto_all_represented_one_no_blocks_agreement',
                   cv(q,0)+cv('eon_eu_extension_answer_count',6)+cv('eon_eu_extension_no_count',1)+cv('eon_eu_extension_abstain_count',1)+flag('eon_eu_extension_council_consent',False),
                   'All six governments are represented, including one abstention; an actual veto blocks final extension')
    final += decision('eon_eu_revoke_withdrawal')
    final += check('runtime_terminal_cleanup_no_extension_or_native_clock',
                   flag('Article_50',False)+flag(init,False)+flag(deadline,False)+cv(q,0)+
                   'NOT = { has_active_mission = EU_exit } NOT = { has_active_mission = EU_exit_three_month } has_idea = EU_member ',
                   'Explicit current source revocation leaves a live member with no extension or stale clock')
    final += terminal_effect
    event(2410,final)
'''


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def ai_weight_overlay(text, selected):
    """Replace only selected source AI bodies; retain comments/BOM/EOL/IDs."""
    def brace_end(begin):
        depth, quoted, escaped, comment = 0,False,False,False
        for index in range(begin,len(text)):
            character=text[index]
            if comment:
                if character in '\r\n':comment=False
                continue
            if quoted:
                if escaped:escaped=False
                elif character=='\\':escaped=True
                elif character=='"':quoted=False
                continue
            if character=='#':comment=True
            elif character=='"':quoted=True
            elif character=='{':depth+=1
            elif character=='}':
                depth-=1
                if depth==0:return index
        raise AssertionError('Unclosed actual source block')
    edits=[]
    for ident in selected:
        matches=list(re.finditer(r'(?m)^[ \t]*'+re.escape(ident)+r'\s*=\s*\{',text))
        assert len(matches)==1,('Actual decision identity must be unique',ident)
        begin=text.index('{',matches[0].start());end=brace_end(begin)
        weights=list(re.finditer(r'(?m)^[ \t]*ai_will_do\s*=\s*\{',text[begin+1:end]))
        assert len(weights)==1,('Actual decision AI field must be unique',ident)
        weight_begin=text.index('{',begin+1+weights[0].start())
        weight_end=brace_end(weight_begin)
        assert weight_end < end
        edits.append((weight_begin+1,weight_end,' factor = 0 '))
    for begin,end,value in sorted(edits,reverse=True):text=text[:begin]+value+text[end:]
    return text


def load_base():
    assert sha(BASE_PATH) == BASE_SHA256, 'Frozen v14 generator differs from the declared original114 input'
    code = BASE_PATH.read_text('utf-8')
    # Root resolution is the only environmental adaptation in this frozen copy.
    code = code.replace('ROOT = Path(__file__).resolve().parents[3]', 'ROOT = Path('+repr(str(ROOT))+')', 1)
    environment = {'__file__':str(BASE_PATH),'__name__':'private_extension_frozen'}
    exec(compile(code,str(BASE_PATH),'exec'),environment)
    return code, environment


def contract114(module):
    return {k:module[k] for k in ('assertions','expectations','calibrations','required_elapsed_game_time','required_observations')}


def source_handler_callback_result(contract, text, marker, observation_lines=None):
    """Check exact source-handler receipt deltas, never native decision clicks.

    The full native analyzer must independently require source/fixture hashes,
    ordered original/new assertions, real game-time minima and clean errors.
    Synthetic text can test this validator but cannot establish engine support.
    """
    from decimal import Decimal, InvalidOperation
    if not contract:
        return None
    failures, receipts = [], []
    if contract.get('schema') != 1 or contract.get('method') != SOURCE_METHOD or not contract.get('actions'):
        return {'passed':False,'method':SOURCE_METHOD,'failures':[{'invalid_source_handler_contract':True}],
                'actions':[],'claims_excluded':['Decision engine click','Native AI selection','Multiplayer acceptance']}
    stages = ('BEFORE_API','AFTER_RAW_API','BEFORE_EXPLICIT_HANDLER','AFTER_EXPLICIT_HANDLER',
              'BEFORE_DIRECT_REPLAY','AFTER_DIRECT_REPLAY')
    delta_fields = ('answer','yes','no','abstain','approvals','rejections','abstentions')
    identity_fields = ('queue','notice','project','project_notice','electorate','treaty','treaty_proposal')
    number_fields = delta_fields + identity_fields + ('gate','handler_count')
    token_fields = ('actor','scope','sender','target','expected_actor')

    def row(label, kind='TRACE', payload=True):
        matches = list(re.finditer(re.escape(marker+' '+kind+' '+label)+r'(?:\s|$)([^\r\n]*)',text))
        if len(matches) != 1:
            failures.append({'source_handler_missing_or_duplicate_'+kind.lower():label,'count':len(matches)})
            return None,None
        pairs = re.findall(r'\b([a-z_]+)=([^\s]+)',matches[0][1].strip())
        parsed = dict(pairs)
        if len(pairs) != len(parsed):
            failures.append({'source_handler_duplicate_payload_key':label})
        if not payload:
            return parsed,matches[0].start()
        try:
            for key in number_fields:
                value = Decimal(parsed[key])
                if not value.is_finite() or value != value.to_integral_value() or value < 0:
                    raise ValueError(key)
                parsed[key] = int(value)
            # Country id is an opaque native token (e.g. 10792.03137),
            # while ballot counters are integers. Preserve exact token text.
            for key in token_fields:
                if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', parsed[key]):
                    raise ValueError(key)
                value = Decimal(parsed[key])
                if not value.is_finite() or value <= 0:
                    raise ValueError(key)
        except (KeyError,ValueError,InvalidOperation):
            failures.append({'source_handler_invalid_context':label})
            return None,matches[0].start()
        if parsed.get('method') != 'source_complete_effect_AST_dispatched_by_event':
            failures.append({'source_handler_method_mismatch':label})
        return parsed,matches[0].start()

    stamps = [a.get('stamp') for a in contract['actions']]
    if len(stamps) != len(set(stamps)) or any(not isinstance(s,str) or not re.fullmatch(r'HANDLER_ACTION_\d{3}_[A-Z_]+',s) for s in stamps):
        failures.append({'source_handler_invalid_action_stamps':True})
        return {'passed':False,'method':SOURCE_METHOD,'failures':failures,'actions':receipts}
    expected_kinds = {'eon_eu_extension_approve':('approvals','yes'),
                      'eon_eu_extension_reject':('rejections','no'),
                      'eon_eu_extension_abstain':('abstentions','abstain')}
    for action in contract['actions']:
        prior = len(failures)
        stamp = action['stamp']
        expected_kind = expected_kinds.get(action.get('decision'))
        if (action.get('method') != SOURCE_METHOD or action.get('actor_tag') not in ('GER','FRA','ITA','HOL','SPR','CZE')
                or action.get('target_tag') != 'POL' or expected_kind != (action.get('increment_array'),action.get('increment_counter'))):
            failures.append({'source_handler_invalid_action_contract':stamp})
            receipts.append({'stamp':stamp,'passed':False})
            continue
        contexts, positions = [],[]
        for stage in stages:
            context,position = row(stamp+'_'+stage)
            contexts.append(context);positions.append(position)
        requests = []
        for suffix in ('RAW_UI_ACTIVATION_REQUESTED','SOURCE_COMPLETE_AST_INVOKED','EXPLICIT_NEGATIVE_DIRECT_REPLAY'):
            _,position = row(stamp+'_'+suffix,payload=False)
            requests.append(position)
        interface_label='EXTENSION_'+stamp+'_INTERFACE_ACTIVE'
        interface,interface_at = row(interface_label,'OBS',payload=False)
        if interface is None or interface.get('value') not in ('0','1') or set(interface) != {'value'}:
            failures.append({'source_handler_invalid_interface_observation':interface_label})
        if observation_lines is not None:
            rows = observation_lines.get(interface_label,[])
            if len(rows) != 1 or dict(re.findall(r'\b([a-z_]+)=([^\s]+)',rows[0][1])) != interface:
                failures.append({'source_handler_interface_receipt_mismatch':interface_label})
        if any(context is None for context in contexts) or any(position is None for position in positions+requests+[interface_at]):
            receipts.append({'stamp':stamp,'passed':False})
            continue
        b,r,pre,post,replay_before,replay_after=contexts
        ba,ra,pa,poa,rba,raa=positions
        raw_request,invoke,replay_request=requests
        if not ba < raw_request < ra < interface_at < pa < invoke < poa < rba < replay_request < raa:
            failures.append({'source_handler_stage_order_invalid':stamp})
        actor,target=b['expected_actor'],b['target']
        if Decimal(actor) == Decimal(target):
            failures.append({'source_handler_country_identity_invalid':stamp})
        for context in contexts:
            if any(context[field] != expected for field,expected in
                   (('actor',actor),('scope',actor),('expected_actor',actor),('target',target),('sender',target))):
                failures.append({'source_handler_actor_sender_scope_mismatch':stamp,'context':context})
            if (context['gate'] != 1 or context['queue'] != 0 or context['notice'] <= 0 or context['project'] <= 0
                    or context['project_notice'] != context['notice'] or context['electorate'] != 6
                    or context['treaty'] not in (0,1) or context['treaty_proposal'] not in (0,1)):
                failures.append({'source_handler_not_current_exact_electorate':stamp,'context':context})
            if any(context[field] != b[field] for field in identity_fields):
                failures.append({'source_handler_project_or_treaty_identity_changed':stamp})
        if any(r[field] != b[field] or pre[field] != b[field] for field in number_fields):
            failures.append({'source_handler_raw_api_changed_ledger_or_invocation':stamp})
        wanted=dict.fromkeys(delta_fields,0)
        wanted['answer']=wanted[action['increment_array']]=wanted[action['increment_counter']]=1
        actual={field:post[field]-pre[field] for field in delta_fields}
        if actual != wanted or post['handler_count'] != pre['handler_count']+1:
            failures.append({'source_handler_explicit_delta_not_exactly_one':stamp,'delta':actual})
        if any(replay_before[field] != post[field] or replay_after[field] != post[field] for field in number_fields):
            failures.append({'source_handler_direct_replay_not_inert':stamp})
        receipts.append({'stamp':stamp,'decision':action['decision'],'actor_tag':action['actor_tag'],'target_tag':'POL',
                         'passed':len(failures)==prior,'raw_activation_changed_response':False if not any(r[f]!=b[f] for f in delta_fields) else True,
                         'interface_active':interface.get('value')=='1','explicit_delta':actual,
                         'method':SOURCE_METHOD})
    return {'passed':not failures,'failures':failures,'method':SOURCE_METHOD,'actions':receipts,
            'raw_interface_observations':len(receipts),'claims_excluded':['Decision engine click','Native AI selection','Multiplayer acceptance',
            'Automatic whole-world campaign behavior','Native114 API acceptance rewritten to source handler']}


def build_runtime(namespace='eon_private_eu_handler_runtime', marker='EON_EU_HANDLER_RUNTIME_V1', *, source=ROOT, terminal_effect=''):
    source = Path(source).resolve()
    code, baseline = load_base()
    original = baseline['build_extension'](namespace,marker,source=source)
    original_contract = contract114(original)
    assert hashlib.sha256(json.dumps(original_contract,sort_keys=True,separators=(',',':')).encode()).hexdigest() == GOLDEN114
    start, end = code.index('    def decision('), code.index('    events, assertions, expectations')
    changed = code[:start]+ADAPTER+code[end:]
    old_terminal = 'last += schedule(LEAVER, next_entry) if next_entry is not None else terminal_effect'
    assert changed.count(old_terminal)==1
    changed = changed.replace(old_terminal,'last += schedule(LEAVER, next_entry) if next_entry is not None else schedule(LEAVER,2400)')
    partial = '''                        body += scope("FROM", decision("eon_eu_extension_accept_final") + check(name + "_missing_sixth_blocks_final", cv(q, 0),
                                     "Five represented governments cannot auto-agree for an unanswered sixth"))'''
    assert changed.count(partial)==1
    changed = changed.replace(partial,'''                        local = decision("eon_eu_extension_accept_final") + check(name + "_missing_sixth_blocks_final", cv(q, 0),
                                     "Five represented governments cannot auto-agree for an unanswered sixth")
                        event(base + 9, local)''')
    schedule_final = 'start += schedule(LEAVER, base + 10, 16)'
    assert changed.count(schedule_final)==1
    changed = changed.replace(schedule_final,'start += schedule(LEAVER, base + 9, 11) + schedule(LEAVER, base + 10, 16)')
    insertion = '    inputs = decision_paths + '
    assert changed.count(insertion)==1
    changed = changed.replace(insertion,EXTRA+'\n'+insertion,1)
    changed = changed.replace('2000 + index for index, number in enumerate(sorted(events))','7400 + index for index, number in enumerate(sorted(events))')
    changed = changed.replace('min(remap.values()) >= 2000 and max(remap.values()) <= 2099','min(remap.values()) >= 7400 and max(remap.values()) <= 7599')
    changed = changed.replace('"extension_callback_contract": {"schema": 1, "actions": action_callback_contract}',
                              '"source_handler_runtime_contract": {"schema": 1, "method": SOURCE_METHOD, "actions": runtime_actions}')
    environment = {'__file__':str(BASE_PATH),'__name__':'private_extension_runtime','AI_IDS':AI_IDS,'SOURCE_METHOD':SOURCE_METHOD}
    exec(compile(changed,str(HERE/'generated_adapter.py'),'exec'),environment)
    module = environment['build_extension'](namespace,marker,source=source,terminal_effect=terminal_effect)
    # Original predictions/clocks remain exactly retrievable, independently of
    # new raw-interface and handler assertions. No API acceptance is rewritten.
    kept = {k:({n:module[k][n] for n in original_contract[k]} if k=='expectations' else
               [n for n in module[k] if n in original_contract[k]] if k in ('assertions','required_observations') else module[k])
            for k in original_contract}
    assert kept == original_contract
    module['baseline114_contract'] = original_contract
    module['baseline114_sha256'] = GOLDEN114
    module['method'] = SOURCE_METHOD
    module['negative_native109_history_preserved'] = True
    module['limits'] = [
        'Source complete_effect AST dispatched by event. Backend runtime only; no decision engine click, mouse UI, native AI selection or multiplayer acceptance.',
        'Raw activate_decision/activate_targeted_decision is a separately observed interface activation and is expected not to mutate the handler ledger. Explicit dispatch is always planned after that diagnostic, never an outcome-selected fallback.',
        'Exact source category/allowed/visible/available/target conditions plus supported literal zero cost guard the first dispatch; direct repeated callbacks are explicit negative backend controls.',
        'Seven lawful private membership origins and eurosceptic=1 POL preference remain declared inputs. Only eight selected action ai_will_do blocks are privately replaced with factor0 to isolate response ordering; production source bodies/gates/costs remain exact.',
        'Original114 predicates, expectations, calibration receipts and1/2-day natural clock minima are preserved. Neither this module nor its result changes native109 API acceptance or its negative history.',
        'Calibrated native remaining mission days and one-day positive flag are private clock inputs. Natural elapsed logger dates must prove1/2days; no natural365/730-day campaign claim.',
        'Interface observations using has_decision do not identify a targeted UI row or prove a click. Exact country_event ROOT/FROM and canonical response membership are separately required.',
        'No install, launcher preparation, game launch, subscribed Workshop mutation, production change, save/reload or long campaign proof.'
    ]
    module['private_builder_sha256'] = {p.name:sha(p) for p in (BASE_PATH,Path(__file__))}
    module['actual_source_callback_ast'] = {}
    actions = {}
    for relative in ('common/decisions/eon_eu_membership_decisions.txt','common/decisions/eon_eu_withdrawal_extension_decisions.txt'):
        nodes = baseline['ast']((source/relative).read_text('utf-8-sig'))
        overlay = deepcopy(nodes)
        for (category,_,body), (_,_,private_body) in zip(nodes,overlay):
            for (_,_,action),(ident,_,private_action) in zip(body,private_body):
                if ident in AI_IDS:
                    actions[ident]=action
                    positions=[i for i,n in enumerate(private_action) if n[0]=='ai_will_do']
                    assert len(positions)==1
                    private_action[positions[0]]=('ai_will_do','=',[('factor','=','0')])
                    module['actual_source_callback_ast'][ident]={k:baseline['one'](action,k) for k in ('allowed','visible','available','cost','complete_effect','target_root_trigger','target_trigger','ai_will_do') if any(n==k for n,_,v in action)}
        raw=(source/relative).read_bytes().decode('utf-8')
        selected=[ident for _,_,body in nodes for ident,_,action in body if ident in AI_IDS]
        module['fixture_text'][relative]=ai_weight_overlay(raw,selected)
        assert baseline['ast'](module['fixture_text'][relative].lstrip('\ufeff')) == overlay
    assert set(actions)==set(AI_IDS)
    # Five standalone fixture paths. A future root-reviewed harness must bind
    # all five; this function only returns text and performs no preparation.
    module['fixture_text']['descriptor.mod']='name="Era of Nations - private source-handler runtime proof"\nsupported_version="1.19.*"\ndependencies={"Era of Nations"}\n'
    module['fixture_text'][f'common/on_actions/{namespace}.txt']=(
        'on_actions = { on_startup = { effect = { '
        f'log = "{marker} STARTUP method=source_complete_effect_AST_dispatched_by_event" '
        f'set_variable = {{ global.{namespace}_passes = 0 }} set_variable = {{ global.{namespace}_fails = 0 }} '
        f'set_variable = {{ global.{namespace}_handler_invocations = 0 }} '
        f'POL = {{ log = "{marker} RUN_BEGIN" '+module['entry_effect']+' } } } }\n')
    assert len(module['fixture_text'])==5
    module['fixture_text_sha256']={p:hashlib.sha256(t.encode()).hexdigest() for p,t in module['fixture_text'].items()}
    module['fixture_paths'] = list(module['fixture_text'])
    module['runtime_overrides'] = {
        path:{'source_sha256':sha(source/path),'runtime_override_sha256':module['fixture_text_sha256'][path],
              'changed_field':'Selected ai_will_do bodies only; all other source bytes/comments/BOM/EOL/IDs/gates/costs/complete_effect preserved',
              'declared_selected_ids':[ident for ident in AI_IDS if any(ident==i for _,_,body in baseline['ast']((source/path).read_text('utf-8-sig')) for i,_,v in body)],
              'runtime_weight':[('factor','=','0')],
              'method':'Private native decision-AI isolation, not ordinary production source or scheduler acceptance'}
        for path in ('common/decisions/eon_eu_membership_decisions.txt','common/decisions/eon_eu_withdrawal_extension_decisions.txt')}
    module['documentation_input_sha256'] = {
        'effects_documentation.md':sha(Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation/effects_documentation.md')),
        'triggers_documentation.md':sha(Path('D:/SteamLibrary/steamapps/common/Hearts of Iron IV/documentation/triggers_documentation.md'))}
    for path,text in module['fixture_text'].items():
        if path.endswith('.txt'): baseline['ast'](text)
    return module


if __name__ == '__main__':
    raise SystemExit('Use the source-bound native builder; this module does not install or launch.')
