"""Current package06 aid/debt scenarios; no cumulative historical-suite claim."""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import runpy
import sys


ROOT = Path(__file__).resolve().parents[3]
ENGINE = ROOT / 'tools/validation/diplomacy_package_01/test_energy.py'
SUPPORT = ROOT / 'tools/validation/diplomacy_package_06/test_support.py'
SCENARIO_BOUNDARY = '\ncases=[]\n'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = ENGINE.read_text(encoding='utf-8')
    if source.count(SCENARIO_BOUNDARY) != 1:
        raise RuntimeError('Energy interpreter definitions/scenarios boundary changed')
    definitions = source.split(SCENARIO_BOUNDARY)[0]
    original_run_path = runpy.run_path
    imported = []

    def definitions_only(path, *arguments, **keywords):
        if Path(path).resolve() != ENGINE.resolve():
            return original_run_path(path, *arguments, **keywords)
        namespace = {
            '__file__': str(ENGINE),
            '__name__': 'aid_current_source_executor',
        }
        exec(compile(definitions, str(ENGINE), 'exec'), namespace)
        imported.append(str(ENGINE.relative_to(ROOT)))
        return namespace

    output = io.StringIO()
    try:
        runpy.run_path = definitions_only
        with contextlib.redirect_stdout(output):
            original_run_path(str(SUPPORT))
    finally:
        runpy.run_path = original_run_path

    if imported != [str(ENGINE.relative_to(ROOT))]:
        raise RuntimeError('Expected exactly one energy definitions import')
    report = json.loads(output.getvalue())
    if report.get('all_passed') is not True or report.get('total_cases') != 166:
        raise RuntimeError('Package06 aid/debt scenario inventory changed')
    aid_path = 'common/scripted_triggers/eon_aid_triggers.txt'
    actual_aid_sha = sha(ROOT / aid_path)
    if report.get('source_sha256', {}).get(aid_path) != actual_aid_sha:
        raise RuntimeError('Aid scenario receipt does not identify current source')

    print(json.dumps({
        'all_passed': True,
        'proof_scope': 'unchanged package06 aid/debt scenarios with current game sources; bounded model',
        'total_cases': report['total_cases'],
        'literal_baseline_defect_cases': report['groups']['literal_baseline_defects'],
        'energy_executor_definitions_only': True,
        'energy_scenarios_run': False,
        'historical_cumulative_suite_run': False,
        'game_source_projection_used': False,
        'actual_aid_trigger_sha256': actual_aid_sha,
        'runner_sha256': sha(Path(__file__)),
        'support_test_sha256': sha(SUPPORT),
        'energy_executor_sha256': sha(ENGINE),
        'package06_report': report,
        'native_campaign_proven': False,
        'multiplayer_proven': False,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
