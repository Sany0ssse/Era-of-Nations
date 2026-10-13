"""Certified current weekly islands and adversarial historical-byte controls."""
from pathlib import Path
import unittest
import weekly_optimization_byte_compat as w
ROOT=Path(__file__).resolve().parents[3]
class WeeklyOptimizationCompatibility(unittest.TestCase):
 def test_current_registered_money_reaches_pre_tax_source(self):
  w.certify_weekly_money_source((ROOT/w.MONEY).read_bytes())
 def test_current_registered_spy_reaches_before_source(self):
  w.certify_weekly_spy_source((ROOT/w.MISSILES).read_bytes())
 def test_foreign_paths_passthrough(self):
  for f in [w.restore_tax_membership_guard,w.restore_spy_first_refresh,w.restore_weekly_validator_bytes]:self.assertEqual(f('foreign.txt',b'unchanged'),b'unchanged')
 def test_foreign_whole_money_and_missiles_rejected(self):
  for rel,certify in [(w.MONEY,w.certify_weekly_money_source),(w.MISSILES,w.certify_weekly_spy_source)]:
   raw=(ROOT/rel).read_bytes()
   for suffix in [b'\n',b'\nforeign_effect = yes\n']:
    with self.assertRaises(AssertionError):certify(raw+suffix)
 def test_money_tax_missing_duplicate_mutated_anchor_rejected(self):
  raw=(ROOT/w.MONEY).read_bytes();old=bytes.fromhex(w.CATALOG['tax_before_hex']);new=bytes.fromhex(w.CATALOG['tax_after_hex']);span=new if new in raw else old
  for bad in [raw.replace(span,b'',1),raw+span,raw.replace(span,span.replace(b'countries_with_branches',b'foreign_array',1),1)]:
   with self.assertRaises(AssertionError):w.restore_tax_membership_guard(w.MONEY,bad)
 def test_spy_missing_duplicate_mutated_helper_rejected(self):
  raw=(ROOT/w.MISSILES).read_bytes();old=bytes.fromhex(w.CATALOG['spy_before_helper_hex']);new=bytes.fromhex(w.CATALOG['spy_after_helper_hex']);span=new if new in raw else old
  for bad in [raw.replace(span,b'',1),raw+span,raw.replace(span,span.replace(b'var_SPY_civ_coverage',b'foreign_value',1),1)]:
   with self.assertRaises(AssertionError):w.restore_spy_first_refresh(w.MISSILES,bad)
if __name__=='__main__':unittest.main(verbosity=2)
