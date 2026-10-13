"""Execute unchanged ordered model definitions with reviewed CURRENT mediation AST.

Supplied native facts and flag expiry are synthetic. This is not engine timing,
event-modal, save/load, or multiplayer proof.
"""
from pathlib import Path
import os

ROOT = Path(os.environ.get('EON_MEDIATION_MOD_ROOT', str(Path(__file__).resolve().parents[3]))).resolve()
SOURCE = Path(os.environ.get('EON_MEDIATION_SOURCE_ROOT', str(ROOT))).resolve()
TERMS_PATH = ROOT / 'tools/validation/diplomacy_package_09/test_terms.py'
BOUNDARY = '\n# Six literal agreements preserve the existing mandate through the first'


def load():
    text = TERMS_PATH.read_text(encoding='utf-8-sig')
    assert text.count(BOUNDARY) == 1, 'Historical definitions boundary changed'
    namespace = {'__file__': str(TERMS_PATH), '__name__': 'live_expiry_ordered_definitions'}
    exec(compile(text.split(BOUNDARY)[0], str(TERMS_PATH), 'exec'), namespace)
    model = namespace['model']
    for kind, registry in (('scripted_effects', 'effects'), ('scripted_triggers', 'capacity_triggers')):
        for stem in ('eon_mediation', 'eon_mediation_terms'):
            path = SOURCE / ('common/' + kind + '/' + stem + '_' + ('effects' if kind == 'scripted_effects' else 'triggers') + '.txt')
            nodes = namespace['ast'](path.read_text(encoding='utf-8-sig'))
            assert len({k for k, _, _ in nodes}) == len(nodes), path
            model[registry].update({k: value for k, _, value in nodes})
    return namespace
