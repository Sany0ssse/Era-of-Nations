"""Byte preservation, callback coverage and native grammar guards."""
from pathlib import Path
import importlib.util
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = '58b27099dc9fdf0eda383fd917167f015564c529'
spec = importlib.util.spec_from_file_location('debt_native_grammar', ROOT/'tools/validation/diplomacy_completion/check_native_grammar.py')
grammar = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = grammar
spec.loader.exec_module(grammar)
p = grammar.parser
checks = 0


def check(ok, why):
    global checks
    checks += 1
    assert ok, why


def old(path):
    return subprocess.check_output(['git', 'show', BASE + ':' + path], cwd=ROOT)


gui_path = 'common/scripted_guis/MD_money_scripted_gui.txt'
before, current = old(gui_path), (ROOT/gui_path).read_bytes()
original_ast = p.one(p.ast(before), 'scripted_gui')
current_ast = p.one(p.ast(current), 'scripted_gui')
restore = current

# Remove exactly the new enabled-predicate insertions, preserving surrounding
# whitespace. Then restore only the authorized existing bodies from the baseline.
for section, prefix in (('debt', 'debt_bg_'), ('budget_tab', 'bottom_bar_debt_bg_')):
    existing = {k for k,o,v in p.one(p.one(original_ast, section), 'triggers')}
    added = [prefix+s+'_enabled' for s in ('right_click', 'control_right_click', 'shift_right_click', 'alt_right_click',
                                         'click', 'control_click', 'shift_click', 'alt_click')
             if prefix+s+'_enabled' not in existing]
    blocks = p.blocks(restore)
    bodies = []
    for key in added:
        found = [b for b in blocks if b['key'] == key and b['parent'] == 'triggers']
        check(len(found) == 1, 'One new enabled predicate ' + key)
        b = found[0]
        bodies.append(restore[b['start']:b['end']])
    insertion = b'\n\t\t\t' + b'\n\t\t\t'.join(bodies) + b'\n\t\t'
    check(restore.count(insertion) == 1, 'Exact narrow predicate insertion ' + section)
    restore = restore.replace(insertion, b'\n\t\t', 1)

before_blocks = p.blocks(before)
replacements = []
for section, prefix in (('debt', 'debt_bg_'), ('budget_tab', 'bottom_bar_debt_bg_')):
    predicates = p.one(p.one(current_ast, section), 'triggers')
    callbacks = p.one(p.one(current_ast, section), 'effects')
    for suffix in ('click', 'control_click', 'shift_click', 'alt_click', 'right_click',
                   'control_right_click', 'shift_right_click', 'alt_right_click'):
        key = prefix + suffix
        check(bool(p.one(callbacks, key)), 'Existing callback ID retained ' + key)
        check(bool(p.one(predicates, key+'_enabled')), 'Callback has enabled predicate ' + key)
        for parent, name in (('effects', key), ('triggers', key+'_enabled')):
            old_blocks = [b for b in before_blocks if b['key']==name and b['parent']==parent]
            if not old_blocks:
                continue
            found = [b for b in p.blocks(restore) if b['key']==name and b['parent']==parent]
            check(len(found)==len(old_blocks)==1, 'Unique authorized block ' + name)
            b, orig = found[0], old_blocks[0]
            replacements.append((b['start'], b['end'], before[orig['start']:orig['end']]))
for start, end, content in sorted(replacements, reverse=True):
    restore = restore[:start] + content + restore[end:]
check(restore == before, 'All unrelated GUI bytes remain exactly unchanged')
p.format_preserved(before, current)

money = 'common/scripted_effects/00_money_system.txt'
before, current = old(money), (ROOT/money).read_bytes()
def loan_block(raw):
    found = [b for b in p.blocks(raw) if b['key']=='automated_debt_taker' and b['depth']==0]
    check(len(found)==1, 'One automatic loan definition')
    return found[0]
b, orig = loan_block(current), loan_block(before)
check(current[:b['start']]+before[orig['start']:orig['end']]+current[b['end']:] == before,
      'All unrelated money-system bytes remain unchanged')
p.format_preserved(before, current)
automatic = p.one(p.ast(current), 'automated_debt_taker')
check('eon_debt_borrow_capacity_available' in str(automatic), 'Automatic loan shares capacity conservation')
check('eon_debt_borrow_manual_available' not in str(automatic), 'No new manual interest policy imposed on automatic loans')

for path in ('common/scripted_effects/eon_debt_accounting_effects.txt',
             'common/scripted_triggers/eon_debt_accounting_triggers.txt'):
    raw = (ROOT/path).read_bytes()
    check(b'\r' not in raw and raw.endswith(b'\n'), path+' LF preserved')
    check(not grammar.inspect(p.ast(raw)), path+' documented native grammar')

from byte_compat import restore_debt_accounting
for path in (gui_path, money):
    raw = (ROOT/path).read_bytes()
    check(restore_debt_accounting(path, raw) == old(path), 'Exact accepted inverse '+path)
    mutant = raw.replace(b'eon_debt_repay_manual = yes', b'eon_debt_repay_manual = no', 1) if path == gui_path else raw.replace(b'eon_debt_borrow_capacity_available = yes', b'eon_debt_borrow_capacity_available = no', 1)
    check(mutant != raw, 'Meaningful owned-body mutant '+path)
    try:
        restore_debt_accounting(path, mutant)
    except AssertionError:
        pass
    else:
        raise AssertionError('Historical inverse accepted an altered debt callback')

print(json.dumps({'source_checks': checks, 'all_passed': True,
                  'unrelated_bytes_preserved': True, 'native_compilation_verified': False}, indent=2))
