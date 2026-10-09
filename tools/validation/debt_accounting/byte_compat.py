"""Exact inverse of the accepted debt edits for historical byte comparisons only.

Actual behavior tests always execute current source. Unknown/altered owned bodies
fail before normalization; no broad accounting block may be silently masked.
"""
from pathlib import Path
import hashlib
import importlib.util
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = '58b27099dc9fdf0eda383fd917167f015564c529'
OWNED_SHA256 = {'common/scripted_guis/MD_money_scripted_gui.txt': {'effects/debt_bg_click': '758978d017b9d467a955b1fa99bff608062d4402d95c1ccbb7f84bed0e29ba78', 'effects/debt_bg_control_click': '1d7f9289120d1e7b27edb985aadf9b25a92d02bd0918f77453595d64dec23941', 'effects/debt_bg_shift_click': 'fc0502d29eda6bee278c6c221cdc045eb34949ece1953099628c9f220118d7ff', 'effects/debt_bg_alt_click': 'c25fb4aa137546aa8692307b70364350fce6fd737a1a3bcb5733be9744712b77', 'effects/debt_bg_right_click': '9e1664351396b96fcc6b88bdc13e742f1578543f7d36691c6d84ac403ec84e7f', 'effects/debt_bg_control_right_click': '0433a81f0cff3c632263eec35dbbfb453479bba4c829054827e5cf063f42e6b8', 'effects/debt_bg_shift_right_click': '7ceb2ecbd95f196774a08b9eca2a7f1abac3b7d3400dd354ebb20d1c0fb8885c', 'effects/debt_bg_alt_right_click': '2b3429b7134e3cf302c4fb91ca8b620837264dfae7f9e1a7fc971eec8c0f8fbf', 'triggers/debt_bg_right_click_enabled': 'f374d99391618e9fad1bec47d97f79afc028981b94e0da39b50cc7a6f7c4e167', 'triggers/debt_bg_control_right_click_enabled': '2899c7ff82bc6601b05ed6417dc4c494c5b6fcaf33498b6864ce9bea9e6b569e', 'triggers/debt_bg_shift_right_click_enabled': 'c8345ac28ac554cd915621b63a3de85866bc643ffa0dc9ef1bd5d9412db80d40', 'triggers/debt_bg_alt_click_enabled': '5b1f48ef606dde1b214263b199c76e5f344d1b2f6d0633d7ff0ba225875838bd', 'triggers/debt_bg_alt_right_click_enabled': 'cd2e51e2548571b8726ffe56e9f1b5d93e7ef20db1a19dbbd3526edfd4f48447', 'triggers/debt_bg_click_enabled': '591e2b01ad7c1b4cb5dad6a9feca9d3ab5ee4fef7cdd162c60a14fc29e3bb4dd', 'triggers/debt_bg_control_click_enabled': 'edccec01c99d4049342d71293b5e56420e611ba5cd228999ebeab4701a992769', 'triggers/debt_bg_shift_click_enabled': '987a899f9bf03915546d4bb34e3f21cf815f95bace98017529b3fa39999fcea0', 'triggers/bottom_bar_debt_bg_right_click_enabled': 'dfb4537823880e51ae08778fef12f60bf711cc45a26998c590e9e45efdefa750', 'triggers/bottom_bar_debt_bg_control_right_click_enabled': '2e2b750f55e183bbe5b48d203d0bf919916622d0485e3d5f607b6ca5c0847f47', 'triggers/bottom_bar_debt_bg_shift_right_click_enabled': '3bd462f0346761c1567eabacd0da957a3f88927baa5667c9223273e8cd5a8b18', 'triggers/bottom_bar_debt_bg_alt_right_click_enabled': 'cfa7c758a79beb481989612d9b42219a22340511f6e575bb5c8c2ec9503aeb3d', 'triggers/bottom_bar_debt_bg_click_enabled': '0d729c6e9aca901496b8b4825e20e0339b26bef88bc5c033d17a01e80119ec69', 'triggers/bottom_bar_debt_bg_control_click_enabled': 'fd73426b750f6d8c026c50c7cfb6bfc7ee2858610be920531fa6149dd9004a6b', 'triggers/bottom_bar_debt_bg_shift_click_enabled': '9c1392182bfa095d1a642e9917d107159acb390f013b1111a82336398bb61b79', 'triggers/bottom_bar_debt_bg_alt_click_enabled': '3f0f174b5d91bb34105c1e9a98cac66d1839528977af12a825c661f07d6622fa', 'effects/bottom_bar_debt_bg_click': 'efaf68a108c5da787f51702d1e2972fd1abdeaecc2c74daf6fc9c88427de5322', 'effects/bottom_bar_debt_bg_control_click': 'fa3bba1a122b0d5b7fd4e2dba9b3948ff31df7c765f6a299b22f376e59d667bd', 'effects/bottom_bar_debt_bg_shift_click': '7e675d86df6636373fb96284fd74eff15a5646b77e9accb63fe013af9729abd7', 'effects/bottom_bar_debt_bg_alt_click': '7b8a1a3a2da4d5cee3471d504fd27bbd79afe8716f838796a984342c11a878d8', 'effects/bottom_bar_debt_bg_right_click': '68e9fc538ff79df283dc3cd524cf7f93ce1b3eac4ddc36ad50ee6fd9633fd82f', 'effects/bottom_bar_debt_bg_control_right_click': '348fec000dea25f133bf8bd49ff049c5f4cafdfb768353f44f2f150e1ce7fe30', 'effects/bottom_bar_debt_bg_shift_right_click': '1f8d97c62a58f1e4abf2d912e4d03c50d5518d14c36156a2c320d9ff3bdebecf', 'effects/bottom_bar_debt_bg_alt_right_click': '6278bc980924a98e107957a933522d1c157ef3a5d782a7b80b03cb3c048b7dd7'}, 'common/scripted_effects/00_money_system.txt': {'/automated_debt_taker': '3ff7f893f5885e019738af690c8260fa216c320b12e252ee50d805e512d3f0b7'}}

def restore_debt_accounting(relative, raw):
    if isinstance(raw, str):
        return restore_debt_accounting(relative, raw.encode('utf-8')).decode('utf-8')
    # Later missile packet adds exact arsenal hooks and one market-temp reset.
    # Keep the debt-body digests and every other byte comparison intact.
    if relative == 'common/scripted_effects/00_money_system.txt':
        arsenal_spec = importlib.util.spec_from_file_location(
            'arsenal_budget_bytes', ROOT/'tools/validation/missile_system/byte_compat.py')
        arsenal = importlib.util.module_from_spec(arsenal_spec)
        arsenal_spec.loader.exec_module(arsenal)
        raw = arsenal.restore_arsenal_budget(relative, raw)
    expected = OWNED_SHA256[relative]
    spec = importlib.util.spec_from_file_location('debt_byte_parser', ROOT/'tools/validation/diplomacy_package_03/_support.py')
    p = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = p
    spec.loader.exec_module(p)
    baseline = subprocess.check_output(['git', 'show', BASE+':'+relative], cwd=ROOT)
    if raw == baseline:
        return raw
    before_blocks = p.blocks(baseline)
    blocks = p.blocks(raw)
    for identifier, digest in expected.items():
        parent, key = identifier.split('/', 1)
        found = [b for b in blocks if (b['parent'] or '') == parent and b['key'] == key]
        assert len(found) == 1, identifier
        b = found[0]
        assert hashlib.sha256(raw[b['start']:b['end']]).hexdigest() == digest, 'Altered accepted debt body: '+identifier
    restored = raw
    if relative.endswith('gui.txt'):
        before_ast = p.one(p.ast(baseline), 'scripted_gui')
        for section, prefix in (('debt', 'debt_bg_'), ('budget_tab', 'bottom_bar_debt_bg_')):
            existing = {k for k,o,v in p.one(p.one(before_ast, section), 'triggers')}
            added = [prefix+s+'_enabled' for s in ('right_click','control_right_click','shift_right_click','alt_right_click','click','control_click','shift_click','alt_click') if prefix+s+'_enabled' not in existing]
            bodies = []
            for key in added:
                found = [b for b in p.blocks(restored) if b['key']==key and b['parent']=='triggers']
                assert len(found)==1
                b = found[0]
                bodies.append(restored[b['start']:b['end']])
            insertion = b'\n\t\t\t'+b'\n\t\t\t'.join(bodies)+b'\n\t\t'
            assert restored.count(insertion)==1
            restored = restored.replace(insertion, b'\n\t\t', 1)
    replacements = []
    for identifier in expected:
        parent, key = identifier.split('/', 1)
        original = [b for b in before_blocks if (b['parent'] or '')==parent and b['key']==key]
        if not original:
            continue
        current = [b for b in p.blocks(restored) if (b['parent'] or '')==parent and b['key']==key]
        assert len(current)==len(original)==1
        b, old = current[0], original[0]
        replacements.append((b['start'],b['end'],baseline[old['start']:old['end']]))
    for start, end, body in sorted(replacements, reverse=True):
        restored = restored[:start]+body+restored[end:]
    p.format_preserved(raw, restored)
    return restored
