"""Exact source certification and adversarial sanctions byte-inverse controls."""
from pathlib import Path
import copy, hashlib, unittest
import sanctions_income_byte_compat as s
from weekly_optimization_byte_compat import restore_tax_membership_guard
from byte_compat import restore_adjacent_state_refresh

ROOT = Path(__file__).resolve().parents[3]
MONEY = s.SOURCE_PATH
HISTORICAL_FUSED_PREIMAGE = '938ca3a0b62a5f0c9cf6cc8dde82cbf4187ee4d560b2ef567014aa47b4043135'

class SanctionsIncomeCompatibility(unittest.TestCase):
    def setUp(self):
        raw = restore_tax_membership_guard(MONEY,(ROOT/MONEY).read_bytes())
        s.certify_sanctions_money_source(raw)
        self.before=s.restore_sanctions_income_loop(MONEY,raw)
        lead,deleted,tail=s.spans();self.lead,self.deleted,self.tail=lead,deleted,tail
        self.fixed=self.before.replace(lead+deleted+tail,lead+tail,1)
        self.assertEqual(s.sha(self.before),s.BEFORE_SHA256)
        self.assertEqual(s.sha(self.fixed),s.CANDIDATE_SHA256)

    def test_exact_whole_sources_forward_inverse_and_baseline_passthrough(self):
        for raw in (self.before,self.fixed):
            self.assertEqual(s.certify_sanctions_money_source(raw)['restored_sha256'],s.BEFORE_SHA256)
            self.assertEqual(s.restore_sanctions_income_loop(MONEY,raw),self.before)
        self.assertEqual(self.fixed[:20387]+self.deleted+self.fixed[20387:],self.before)

    def test_existing_fused_inverse_reaches_unchanged_historical_digest(self):
        for raw in (self.before,self.fixed):
            restored=restore_adjacent_state_refresh(MONEY,raw)
            self.assertEqual(hashlib.sha256(restored).hexdigest(),HISTORICAL_FUSED_PREIMAGE)

    def test_missing_duplicate_changed_owned_anchors_fail_closed(self):
        fixed=self.lead+self.tail
        mutants=[self.fixed.replace(self.lead,b'',1),self.fixed.replace(self.tail,b'',1),
                 self.fixed+self.lead,self.fixed+self.tail,self.fixed+self.deleted,
                 self.fixed.replace(fixed,self.lead+b'# unknown interior\n'+self.tail,1),
                 self.fixed.replace(self.lead,self.lead.replace(b'clear_variable',b'set_variable'),1),
                 self.before.replace(b'sanctions_evasion_income = 0.05',b'sanctions_evasion_income = 0.06',1)]
        for raw in mutants:
            with self.subTest(digest=s.sha(raw)):
                self.assertNotIn(s.sha(raw),{s.BEFORE_SHA256,s.CANDIDATE_SHA256})
                with self.assertRaises(AssertionError):s.restore_sanctions_income_loop(MONEY,raw)

    def test_foreign_mutations_never_disappear_and_whole_certification_rejects(self):
        for original in (self.before,self.fixed):
            for raw in (b'# foreign prefix\n'+original,original+b'# foreign suffix\n',
                        original.replace(self.lead,b'# foreign adjacent\n'+self.lead,1),
                        original.replace(b'adding_migrants_income = 0',b'adding_migrants_income = 1',1)):
                with self.subTest(source=s.sha(original),mutant=s.sha(raw)):
                    self.assertNotEqual(raw,original)
                    with self.assertRaises(AssertionError):s.certify_sanctions_money_source(raw)
                    projected=s.restore_sanctions_income_loop(MONEY,raw)
                    self.assertNotEqual(s.sha(projected),s.BEFORE_SHA256)
                    if original==self.before:self.assertEqual(projected,raw)
                    old=restore_adjacent_state_refresh(MONEY,raw)
                    self.assertNotEqual(s.sha(old),HISTORICAL_FUSED_PREIMAGE)
                    for token in (b'# foreign prefix',b'# foreign suffix',b'# foreign adjacent',b'adding_migrants_income = 1'):
                        if token in raw:self.assertIn(token,projected);self.assertIn(token,old)

    def test_wrong_catalog_digest_span_or_source_identity_rejected(self):
        original=s.CATALOG
        edits={'deleted_utf8':original['deleted_utf8'].replace('0.05','0.06',1),
               'deleted_sha256':'0'*64,'deleted_bytes':844,'deleted_byte_span':[20386,21231],
               'before_sha256':'0'*64,'candidate_sha256':'0'*64,'version':2}
        try:
            for key,value in edits.items():
                with self.subTest(key=key):
                    s.CATALOG=copy.deepcopy(original);s.CATALOG[key]=value
                    with self.assertRaises(AssertionError):s.restore_sanctions_income_loop(MONEY,self.fixed)
        finally:s.CATALOG=original

    def test_foreign_path_str_bytes_and_encoding_preserved(self):
        self.assertEqual(s.restore_sanctions_income_loop('other.txt',b'anything'),b'anything')
        for raw in (self.before,self.fixed):
            restored=s.restore_sanctions_income_loop(MONEY,raw)
            self.assertEqual(s.restore_sanctions_income_loop(MONEY,raw.decode('utf-8')),restored.decode('utf-8'))
            self.assertEqual(restored.startswith(b'\xef\xbb\xbf'),raw.startswith(b'\xef\xbb\xbf'))
            self.assertEqual(restored.count(b'\r\n'),raw.count(b'\r\n'))
            self.assertNotIn(b'\r',restored)
        with self.assertRaises(AssertionError):s.restore_sanctions_income_loop(MONEY,None)

    def test_unregistered_historical_file_not_current_source(self):
        old=restore_adjacent_state_refresh(MONEY,self.fixed)
        with self.assertRaises(AssertionError):s.certify_sanctions_money_source(old)
        with self.assertRaises(AssertionError):restore_adjacent_state_refresh(MONEY,old)

if __name__=='__main__':unittest.main(verbosity=2)
