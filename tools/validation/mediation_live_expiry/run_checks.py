"""Portable CURRENT AST checks. No historical projection or native claim."""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import sys
import unittest
from byte_compat import CATALOG, certify_cohort
from support import ROOT, SOURCE

HERE = Path(__file__).resolve().parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
cert = certify_cohort({p: (SOURCE / p).read_bytes() for p in CATALOG})
assert cert['role'] == 'after', 'Current lifecycle suite requires exact reviewed AFTER cohort'
stream = io.StringIO()
suite = unittest.defaultTestLoader.discover(str(HERE), pattern='test_*.py')
with contextlib.redirect_stdout(stream):
    result = unittest.TextTestRunner(stream=stream).run(suite)
sys.stderr.write(stream.getvalue())
dependencies = [
    'tools/validation/diplomacy_package_09/test_terms.py',
    'tools/validation/diplomacy_package_08/test_mediation.py',
    'tools/validation/diplomacy_package_07/test_consultations.py',
    'tools/validation/diplomacy_package_01/test_energy.py',
    'tools/validation/diplomacy_package_01/_support.py',
    'events/eon_mediation_events.txt', 'events/eon_mediation_terms_events.txt',
    'common/on_actions/eon_mediation_on_actions.txt', 'common/on_actions/eon_mediation_terms_on_actions.txt',
    'common/scripted_diplomatic_actions/eon_mediation_actions.txt',
    'common/decisions/eon_mediation_decisions.txt', 'common/decisions/eon_mediation_terms_decisions.txt',
    'common/scripted_effects/eon_energy_contract_effects.txt',
    'common/scripted_effects/eon_energy_framework_effects.txt',
    'common/scripted_effects/eon_energy_ai_effects.txt',
    'common/scripted_effects/eon_energy_negotiation_effects.txt',
    'common/scripted_effects/eon_trade_treaty_effects.txt',
    'common/scripted_effects/eon_investment_treaty_effects.txt',
    'common/scripted_effects/eon_investment_project_effects.txt',
    'common/scripted_triggers/eon_energy_capacity_triggers.txt',
    'common/scripted_triggers/eon_energy_negotiation_triggers.txt',
    'common/scripted_effects/eon_aid_effects.txt',
    'common/scripted_effects/eon_support_effects.txt',
    'common/scripted_effects/eon_consultation_effects.txt',
    'common/scripted_effects/00_budget_effects.txt',
    'common/scripted_triggers/eon_aid_triggers.txt',
    'common/scripted_triggers/eon_consultation_triggers.txt',
    'common/scripted_triggers/99_ERI_scripted_triggers.txt',
    'common/scripted_triggers/00_influence_scripted_triggers.txt',
    'common/scripted_guis/01_energy_gui.txt', 'events/00_Energy_market_events.txt',
]
print(json.dumps({'status': 'CURRENT_AST_LIVE_EXPIRY_PASS' if result.wasSuccessful() else 'CURRENT_AST_LIVE_EXPIRY_FAIL',
                  'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
                  'source_sha256': {p: sha(SOURCE / p) for p in CATALOG},
                  'model_dependency_sha256': {p: sha(ROOT / p) for p in dependencies},
                  'proof_scope': 'Actual reviewed AFTER mediation AST, synthetic native facts and explicit expired flag inputs',
                  'historical_semantics_claimed': False, 'native_tested': False,
                  'not_proven': ['native timers/modal dispatch', 'save/load', 'multiplayer', 'campaign'],
                  'public_written': False}, indent=2))
raise SystemExit(0 if result.wasSuccessful() else 1)
