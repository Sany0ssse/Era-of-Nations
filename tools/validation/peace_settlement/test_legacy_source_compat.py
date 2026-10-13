"""Inverse and mutation tests for the narrow legacy annex projection."""
from pathlib import Path
import hashlib, unittest
from legacy_source_compat import restore_consensual_annex_guards
ROOT=Path(__file__).resolve().parents[3]
PATH='common/on_actions/00_costili.txt'
BEFORE_SHA='5202e99948854e04958a0aded1b7fb43a70cfcd43a74f45da653cf2474ca1aeb'
GUARD=b'\t\t\t\t\t# A mutually accepted peace must not trigger historical forced annexation.\n\t\t\t\t\tNOT = {\n\t\t\t\t\t\tAND = {\n\t\t\t\t\t\t\tROOT = { has_country_flag = eon_consensual_peace@FROM }\n\t\t\t\t\t\t\tFROM = { has_country_flag = eon_consensual_peace@ROOT }\n\t\t\t\t\t\t}\n\t\t\t\t\t}\n'
ANCHORS=(b'\t\t\t\t\tNOT = { has_global_flag = chechen_war_ended }\n',b'\t\t\t\t\tROOT = { has_country_flag = annex_on_peace_conference@FROM }\n')
class CompatibilityTests(unittest.TestCase):
 def test_guard_inverse_preserves_every_unowned_byte(self):
  current=(ROOT/PATH).read_bytes();original=restore_consensual_annex_guards(current)
  self.assertEqual(hashlib.sha256(original).hexdigest(),BEFORE_SHA)
  for anchor in ANCHORS:
   self.assertEqual(original.count(anchor),1);original=original.replace(anchor,anchor+GUARD)
  self.assertEqual(original,current)
 def test_missing_partial_moved_duplicate_and_outside_mutations_rejected(self):
  current=(ROOT/PATH).read_bytes()
  self.assertEqual(current.count(GUARD),2)
  probes=[current.replace(GUARD,b''),current.replace(GUARD,b'',1),current+GUARD,current.replace(ANCHORS[0]+GUARD,GUARD+ANCHORS[0]),current.replace(b'@FROM }\n',b'@ROOT }\n',1),current+b'\n# Unowned comment\n',current.replace(b'transfer_troops = no',b'transfer_troops = yes',1),current.replace(b'\n',b'\r\n'),b'\xef\xbb\xbf'+current]
  for data in probes:
   self.assertNotEqual(data,current)
   with self.assertRaises(AssertionError):restore_consensual_annex_guards(data)
if __name__=='__main__':unittest.main(verbosity=2)
