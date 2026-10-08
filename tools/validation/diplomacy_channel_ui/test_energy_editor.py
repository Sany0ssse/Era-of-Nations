"""Execute the actual energy-editor handoff against HEAD25 and current27 sources.

Native GUI rendering is not modeled. The existing read-pair and dirty functions
are loaded independently from each checkout, never replaced with a copied rule.
Unknown visited statements remain errors in the shared scoped AST interpreter.
"""
from pathlib import Path
from copy import deepcopy
from collections import Counter
from itertools import product
import hashlib
import importlib.util
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _support as model

TRIGGER = 'common/scripted_triggers/eon_consultation_energy_ui_triggers.txt'
EFFECT = 'common/scripted_effects/eon_consultation_energy_ui_effects.txt'
SHARED = 'common/scripted_triggers/eon_consultation_ui_triggers.txt'
CONSULT = 'common/scripted_triggers/eon_consultation_triggers.txt'
ENERGY = 'common/scripted_effects/eon_energy_contract_effects.txt'
MONEY = 'common/scripted_effects/00_money_system.txt'
GUI = 'common/scripted_guis/01_energy_gui.txt'
READY = 'eon_consultation_energy_editor_ready'
OPEN = 'eon_consultation_energy_editor_open'
counts = Counter()
editor_visible = None
GUI_PARSER = 'tools/validation/diplomacy_package_03/_support.py'
gui_spec = importlib.util.spec_from_file_location('channel_energy_gui_parser', ROOT / GUI_PARSER)
gui_parser = importlib.util.module_from_spec(gui_spec)
sys.modules[gui_spec.name] = gui_parser
gui_spec.loader.exec_module(gui_parser)


def check(actual, message, group):
    assert actual, message
    counts[group] += 1


def parsed(raw):
    return {key: value for key, operator, value in model.parse(raw.decode('utf-8-sig'))}


def persistent(result):
    result = deepcopy(result)
    for country in result['countries'].values():
        country['temps'] = {}
    result['global']['temps'] = {}
    return result


def fixture(quantity=None, price=.05, actor='A', peer='B'):
    result = model.state()
    for who, partner in ((actor, peer), (peer, actor)):
        country = result['countries'][who]
        country['flags'] = {'eon_consultation_reserved', 'eon_consultation_active',
                            'eon_consultation_active_window', 'energy_agreement@' + partner}
        country['expires'] = {'eon_consultation_active_window': 100}
        country['wars'] = set()
        country['variables'].update({
            'eon_consultation_partner': model.IDS[partner],
            'eon_consultation_topic': 2,
            'eon_energy_offer_partner': 0,
            'eon_energy_framework_pending_sender': 0,
            'pending_energy_offer_country': 0,
            'energy_selling_selected_TAG': 0,
            'temp_energy_ammount': 777,
            'temp_energy_price': .777,
            'treasury': 120 if who == actor else 240,
        })
        country['temps'].update({
            'eon_consultation_energy_partner_count': 91,
            'eon_consultation_energy_owner_count': 92,
            'eon_consultation_energy_owner_amount': 999,
            'eon_energy_current_count': 12,
            'eon_energy_current_amount': 888,
        })
        # Unrelated rows deliberately bracket this pair and must never change.
        country['arrays'].update({
            'energy_contractors': [model.IDS['C'], model.IDS['D']],
            'energy_contracts_ammount': [7, -9],
            'energy_contracts_price': [.07, .09],
        })
        if quantity is not None:
            country['arrays']['energy_contractors'].insert(1, model.IDS[partner])
            country['arrays']['energy_contracts_ammount'].insert(1, quantity if who == actor else -quantity)
            country['arrays']['energy_contracts_price'].insert(1, price)
    result['countries'][actor]['flags'].add('energy_main')
    # Native10 proved these temporaries share one invocation across country scopes.
    result['global']['temps'].update({
        'eon_consultation_energy_partner_count': 91,
        'eon_consultation_energy_owner_count': 92,
        'eon_consultation_energy_owner_amount': 999,
        'eon_energy_current_count': 12,
        'eon_energy_current_amount': 888,
        'eon_energy_pair_partner': model.IDS['C'],
    })
    return result


def context(actor='A', peer='B'):
    return model.native_ctx(actor, peer)


def ready(result, actor='A', peer='B'):
    return model.condition(model.TRIGGERS[READY], result, context(actor, peer))


def open_editor(result, actor='A', peer='B'):
    model.execute(model.EFFECTS[OPEN], result, context(actor, peer))


def assert_rejected(result, label, actor='A', peer='B'):
    before = persistent(result)
    check(not ready(result, actor, peer), label + ': trigger should reject', 'rejected')
    open_editor(result, actor, peer)
    check(persistent(result) == before, label + ': forced effect mutated persistent state', 'forced-noop')


def assert_opened(result, quantity, price, label, actor='A', peer='B'):
    before = persistent(result)
    check(not model.condition(editor_visible, result, model.ctx(actor, peer)), label + ': fixture editor already visible', 'actual-gui-gate')
    check(ready(result, actor, peer), label + ': trigger not ready', 'ready')
    open_editor(result, actor, peer)
    after = persistent(result)
    country = after['countries'][actor]
    check(country['variables']['energy_selling_selected_TAG'] == model.IDS[peer], label + ': wrong frozen selection', 'preload')
    check(country['variables']['temp_energy_ammount'] == quantity, label + ': actual amount not loaded', 'preload')
    check(country['variables']['temp_energy_price'] == price, label + ': actual price not loaded', 'preload')
    check({'open_energy_screen', 'energy_sell'} <= country['flags'], label + ': editor not visible', 'visible')
    check('energy_main' not in country['flags'] and 'open_energy_sell_country_selection' not in country['flags'], label + ': wrong panel', 'visible')
    expected_flags = (before['countries'][actor]['flags'] - {'energy_main', 'open_energy_sell_country_selection'}) | {'open_energy_screen', 'energy_sell'}
    check(country['flags'] == expected_flags, label + ': unrelated flag changed', 'preservation')
    check(model.condition(editor_visible, result, model.ctx(actor, peer)), label + ': actual existing GUI visibility failed', 'actual-gui-gate')
    for field in ('energy_selling_selected_TAG', 'temp_energy_ammount', 'temp_energy_price'):
        country['variables'][field] = before['countries'][actor]['variables'][field]
    country['flags'] = before['countries'][actor]['flags']
    # The actual dirty helper is the sole permitted global persistent change.
    old_dirty = before['global']['variables'].get('update_energy_ui')
    check(after['global']['variables']['update_energy_ui'] == (0 if old_dirty is None else old_dirty + 1), label + ': wrong actual dirty counter', 'dirty')
    after['global']['variables'].pop('update_energy_ui')
    if old_dirty is not None:
        after['global']['variables']['update_energy_ui'] = old_dirty
    check(after == before, label + ': handoff changed contracts, money, PP, parties or other state', 'preservation')
    duplicate_before = persistent(result)
    open_editor(result, actor, peer)
    check(persistent(result) == duplicate_before, label + ': repeat overwrote an unsent editor', 'duplicate-noop')


def exercise_variant(name, blobs):
    global editor_visible
    energy = parsed(blobs[ENERGY])
    money = parsed(blobs[MONEY])
    model.EFFECTS['eon_energy_read_pair_record'] = energy['eon_energy_read_pair_record']
    model.EFFECTS['update_energy_dirty_variable'] = money['update_energy_dirty_variable']
    # This existing GUI also contains bare remove_ideas lists. Its full ordered
    # parser handles those literals; only its actual visibility subtree executes.
    editor_visible = model.one(model.one(model.one(gui_parser.ast(blobs[GUI]), 'scripted_gui'), 'energy_scripted_gui'), 'visible')
    for quantity, price in ((None, .05), (16, .05), (-32, .125), (64, 0), (-16, .1)):
        assert_opened(fixture(quantity, price), 0 if quantity is None else quantity, price, name + ':preload')
    assert_opened(fixture(-32, .125, actor='B', peer='A'), -32, .125, name + ':reverse', 'B', 'A')
    result = fixture(16)
    result['global']['variables']['update_energy_ui'] = 9
    assert_opened(result, 16, .05, name + ':existing-dirty-counter')
    for owner_index, partner_index in product(range(3), repeat=2):
        result = fixture(-32, .125)
        for who, wanted_index in (('A', owner_index), ('B', partner_index)):
            for array in ('energy_contractors', 'energy_contracts_ammount', 'energy_contracts_price'):
                values = result['countries'][who]['arrays'][array]
                values.insert(wanted_index, values.pop(1))
        assert_opened(result, -32, .125, name + ':independent-row-indices')

    for who in ('A', 'B'):
        for flag in ('question_about_contract', 'eon_energy_outgoing_offer', 'eon_energy_incoming_offer',
                     'eon_energy_offer_cancelled', 'eon_energy_counter_draft_owner', 'eon_energy_counter_awaiting',
                     'open_energy_sell_country_selection'):
            result = fixture(32)
            result['countries'][who]['flags'].add(flag)
            assert_rejected(result, name + ':' + who + ':' + flag)
        for field in ('eon_energy_offer_partner', 'eon_energy_framework_pending_sender', 'pending_energy_offer_country'):
            result = fixture(32)
            result['countries'][who]['variables'][field] = model.IDS['C']
            assert_rejected(result, name + ':' + who + ':' + field)
        for screen, sell, selected in product((False, True), repeat=3):
            result = fixture(32)
            country = result['countries'][who]
            if screen: country['flags'].add('open_energy_screen')
            if sell: country['flags'].add('energy_sell')
            country['variables']['energy_selling_selected_TAG'] = model.IDS['C'] if selected else 0
            check(ready(result) == (not (screen and sell and selected)), name + ': ordinary edit truth table', 'editor-truth-table')
            if screen and sell and selected:
                assert_rejected(result, name + ':ordinary-editor-' + who)

        for array in ('energy_contracts_ammount', 'energy_contracts_price'):
            result = fixture(32)
            result['countries'][who]['arrays'][array].pop()
            assert_rejected(result, name + ':' + who + ':unaligned-' + array)
        result = fixture(32)
        result['countries'][who]['arrays']['energy_contractors'].append(model.IDS['B' if who == 'A' else 'A'])
        result['countries'][who]['arrays']['energy_contracts_ammount'].append(32 if who == 'A' else -32)
        result['countries'][who]['arrays']['energy_contracts_price'].append(.05)
        assert_rejected(result, name + ':' + who + ':duplicate-pair')
        result = fixture(32)
        for array in ('energy_contractors', 'energy_contracts_ammount', 'energy_contracts_price'):
            result['countries'][who]['arrays'][array].pop(1)
        assert_rejected(result, name + ':' + who + ':one-sided-pair')
        result = fixture(32)
        result['countries'][who]['flags'].remove('energy_agreement@' + ('B' if who == 'A' else 'A'))
        assert_rejected(result, name + ':' + who + ':one-sided-framework')
        result = fixture(32)
        result['countries'][who]['wars'].add('B' if who == 'A' else 'A')
        assert_rejected(result, name + ':' + who + ':late-war')
        result = fixture(32)
        result['countries'][who]['exists'] = False
        assert_rejected(result, name + ':' + who + ':late-annex')
        result = fixture(32)
        result['countries'][who]['flags'].discard('eon_consultation_active_window')
        assert_rejected(result, name + ':' + who + ':late-expiry')
        result = fixture(32)
        result['countries'][who]['expires']['eon_consultation_active_window'] = 10
        result['day'] = 11
        assert_rejected(result, name + ':' + who + ':native-flag-deadline-fixture')
        result = fixture(32)
        result['countries'][who]['variables']['eon_consultation_partner'] = model.IDS['C']
        assert_rejected(result, name + ':' + who + ':foreign-channel')
        result = fixture(32)
        result['countries'][who]['flags'].add('eon_consultation_outgoing')
        assert_rejected(result, name + ':' + who + ':conflicting-channel-role')

    for field, amount in (('energy_contracts_ammount', 32), ('energy_contracts_ammount', -16), ('energy_contracts_price', .1)):
        result = fixture(32)
        result['countries']['B']['arrays'][field][1] = amount
        assert_rejected(result, name + ':mirror-' + field + '-' + str(amount))
    for quantity, price in ((0, .05), (32, -.05)):
        assert_rejected(fixture(quantity, price), name + ':invalid-terms')
    for topic in (1, 3, 0):
        result = fixture(32)
        for who in ('A', 'B'): result['countries'][who]['variables']['eon_consultation_topic'] = topic
        assert_rejected(result, name + ':wrong-topic-' + str(topic))
    result = fixture(32)
    check(ready(result), name + ': rendered-ready seed', 'late-race')
    result['countries']['B']['flags'].add('question_about_contract')
    assert_rejected(result, name + ': changed-after-render')
    assert_rejected(fixture(32), name + ':wrong-self-frame', 'A', 'A')
    assert_rejected(fixture(32), name + ':wrong-third-party-frame', 'C', 'B')
    # The old country-temp assumption passed the earlier model but failed native10.
    # Each actual-source regression independently detects its unreadable PREV form.
    source_text = (ROOT / TRIGGER).read_text(encoding='utf-8-sig')
    correct_ready = model.TRIGGERS[READY]
    for field in ('eon_consultation_energy_partner_count', 'eon_consultation_energy_partner_amount', 'eon_consultation_energy_partner_price'):
        original = '= ' + field + ' }'
        check(source_text.count(original) == 1, field + ': exact mutation site changed', 'native10-regression')
        mutant = source_text.replace(original, '= PREV.' + field + ' }')
        model.TRIGGERS[READY] = parsed(mutant.encode('utf-8'))[READY]
        try:
            assert_rejected(fixture(32, .05), name + ':native10-unreadable-' + field)
        finally:
            model.TRIGGERS[READY] = correct_ready


def main():
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    for path in (TRIGGER, SHARED, CONSULT):
        model.TRIGGERS.update(parsed((ROOT / path).read_bytes()))
    model.EFFECTS.update(parsed((ROOT / EFFECT).read_bytes()))
    # Neither of these adapters may acquire any metering/settlement dependency.
    for path in (TRIGGER, EFFECT):
        raw = (ROOT / path).read_bytes()
        check(b'eon_energy_settlement' not in raw and b'eon_energy_delivery' not in raw, path + ': package27 dependency', 'source')
    variants = {
        'published-head': {path: subprocess.check_output(['git', 'show', head + ':' + path], cwd=ROOT) for path in (ENERGY, MONEY, GUI)},
        'current-checkout': {path: (ROOT / path).read_bytes() for path in (ENERGY, MONEY, GUI)},
    }
    for name, blobs in variants.items():
        exercise_variant(name, blobs)
    print(json.dumps({
        'suite': 'diplomacy_channel_ui_energy_editor', 'all_passed': True,
        'assertions': sum(counts.values()), 'groups': dict(counts), 'head': head,
        'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in (TRIGGER, EFFECT, SHARED, CONSULT)},
        'variant_source_sha256': {name: {path: hashlib.sha256(raw).hexdigest() for path, raw in blobs.items()} for name, blobs in variants.items()},
        'adapter_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in (GUI_PARSER, 'tools/validation/diplomacy_channel_ui/_support.py')},
        'native_gui_proven': False, 'native_campaign_proven': False, 'multiplayer_proven': False,
        'temp_model': 'native-unscoped-shared-qualified-country-persistent',
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
