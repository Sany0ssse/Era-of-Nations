"""Version-specific, actual-byte AI isolation controls; no native claim."""
from copy import deepcopy
import unittest
from runtime_override_support import ROOT, override_actions, validate_override_bytes, validate_override_maps
from runtime_support import ai_weight_overlay


class V16OverrideContracts(unittest.TestCase):
    def records(self):
        return {path: validate_override_bytes(path, (ROOT/path).read_bytes(),
                    ai_weight_overlay((ROOT/path).read_bytes().decode('utf-8'), ids).encode(), ids,
                    fixture_version=16) for path,ids in override_actions(16).items()}

    def test_exact_four_source_files_and_thirteen_ai_blocks(self):
        records=self.records();before={path:r['source_sha256'] for path,r in records.items()}
        after={path:r['runtime_override_sha256'] for path,r in records.items()}
        self.assertEqual(len(records),4)
        self.assertEqual(sum(len(r['selected_ai_action_ids']) for r in records.values()),13)
        self.assertTrue(validate_override_maps(records,before,after,before,after,fixture_version=16))
        with self.assertRaises(AssertionError):validate_override_maps(records,before,after,before,after)
        for key in records:
            altered=deepcopy(records);altered[key]['selected_ai_action_ids'].append('unrelated_action')
            with self.assertRaises(AssertionError):validate_override_maps(altered,before,after,before,after,fixture_version=16)

    def test_edu_overrides_reject_handler_comment_and_line_ending_mutants(self):
        for path,ids in override_actions(16).items():
            if path in override_actions(15):continue
            original=(ROOT/path).read_bytes()
            overlay=ai_weight_overlay(original.decode('utf-8'),ids).encode()
            # Any unselected byte change is rejected, including a semantically inert comment.
            for bad in (overlay+b'\n# unapproved\n',overlay.replace(b'\r\n',b'\n'),overlay.replace(b'complete_effect',b'cancel_effect',1)):
                if bad==overlay:continue
                with self.subTest(path=path):
                    with self.assertRaises(AssertionError):validate_override_bytes(path,original,bad,ids,fixture_version=16)
            with self.assertRaises(AssertionError):validate_override_bytes(path,original,overlay,ids,fixture_version=15)

    def test_unknown_or_implicit_version_cannot_expand_historical_contract(self):
        self.assertEqual(len(override_actions()),2)
        for value in (14,19,True,'16',None):
            with self.assertRaises(AssertionError):override_actions(value)


if __name__=='__main__':unittest.main()
