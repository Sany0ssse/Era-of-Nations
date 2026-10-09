"""Run focused source and evidence-validator tests, without launching HOI4."""
from pathlib import Path
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
groups = []
for script in ('test_native_probe.py', 'test_core_native_probe.py', 'test_rights_native_probe.py',
               'test_final_rights_native_probe.py', 'test_enrichment_checkpoint_native_probe.py',
               'test_meta_import_binding.py', 'test_native_capability_controls.py', 'test_ai_import_native_trace.py',
               'test_mission_calendar_native_probe.py', 'test_legacy_kg_migration.py',
               'test_core_source.py', 'test_core_mutations.py'):
    process = subprocess.run([sys.executable, str(HERE/script)], capture_output=True, text=True, encoding='utf-8')
    if process.returncode:
        print(process.stdout)
        print(process.stderr, file=sys.stderr)
        raise SystemExit(process.returncode)
    result = json.loads(process.stdout)
    if script == 'test_legacy_kg_migration.py':
        assert result['checks_passed']
        groups.append({'script': script, 'actual_source_cases': len(result['actual_source_cases']),
                       'negative_controls': result['negative_controls'],
                       'source_sha256': result['source_sha256'], 'fixture_encoding_checked': False})
    elif script not in ('test_core_source.py', 'test_core_mutations.py'):
        groups.append({'script': script, 'negative_controls': result['negative_controls'],
                       'fixture_encoding_checked': script not in ('test_meta_import_binding.py', 'test_ai_import_native_trace.py')})
    elif script == 'test_core_source.py':
        assert result['actual_source_behavior_checks_passed']
        groups.append({'script': script, 'actual_source_cases': len(result['passed_cases']),
                       'source_sha256': result['source_sha256']})
    else:
        groups.append({'script': script, 'rejected_source_mutants': result['mutations_rejected']})
print(json.dumps({'focused_source_groups_passed': len(groups), 'groups': groups,
                  'native_game_behavior_tested': False}, indent=2))
