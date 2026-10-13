from pathlib import Path
import base64
import unittest
from byte_compat import CATALOG, certify_cohort
from support import SOURCE


class ByteOwnershipTests(unittest.TestCase):
    def before(self):
        return {p: base64.b64decode(r['before_b64'], validate=True) for p, r in CATALOG.items()}

    def after(self):
        return {p: (SOURCE / p).read_bytes() for p in CATALOG}

    def test_exact_before_after_and_full_inverse(self):
        before, after = self.before(), self.after()
        self.assertEqual(certify_cohort(before)['role'], 'before')
        cert = certify_cohort(after)
        self.assertEqual(cert['role'], 'after'); self.assertEqual(cert['originals'], before)

    def test_all_eight_foreign_mutations_fail(self):
        for path in CATALOG:
            for cohort in (self.before(), self.after()):
                with self.subTest(path=path):
                    cohort[path] += b'\n# foreign retained work\n'
                    with self.assertRaisesRegex(AssertionError, 'Foreign source bytes'): certify_cohort(cohort)

    def test_every_single_path_mixed_cohort_fails(self):
        before, after = self.before(), self.after()
        for path in CATALOG:
            for first, second in ((before, after), (after, before)):
                with self.subTest(path=path):
                    mixed = dict(first); mixed[path] = second[path]
                    with self.assertRaisesRegex(AssertionError, 'Mixed source cohorts'): certify_cohort(mixed)

    def test_invalid_types_paths_and_corrupt_preimage_rejected(self):
        before = self.before()
        for mapping in (None, {}, {**before, 'foreign/path.txt': b'foreign'}):
            with self.assertRaises(AssertionError): certify_cohort(mapping)
        path = next(iter(before)); bad = dict(before); bad[path] = 'text instead of raw bytes'
        with self.assertRaisesRegex(AssertionError, 'Source bytes required'): certify_cohort(bad)
        old = CATALOG[path]['before_b64']
        try:
            raw = before[path]
            CATALOG[path]['before_b64'] = base64.b64encode(bytes([raw[0] ^ 1]) + raw[1:]).decode('ascii')
            with self.assertRaisesRegex(AssertionError, 'Corrupt preimage catalog'): certify_cohort(before)
        finally:
            CATALOG[path]['before_b64'] = old


if __name__ == '__main__': unittest.main()
