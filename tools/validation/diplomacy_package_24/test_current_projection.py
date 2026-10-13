"""Finite projection negatives; never a native or current-v2 entry claim."""
from pathlib import Path
import json,unittest
import investment_offer_source as view
from run_current_v2 import model_module
ROOT=Path(__file__).resolve().parents[3]
class Guards(unittest.TestCase):
 def test_live_inner_and_exact_cohort(self):
  self.assertEqual(view.verify_cohort(ROOT),'AFTER14')
  m=model_module(ROOT);self.assertTrue(view.live_protocol24_inner(ROOT,m.ast,m.one)['guarded_executor_inner_exact'])
 def test_each_changed_file_foreign_byte(self):
  c,rows,b=view.finite_data()
  for rel in c['source_after_sha256']:
   with self.subTest(path=rel):
    def read(path):
     raw=path.read_bytes();return raw+b' ' if path==ROOT/rel else raw
    with self.assertRaises(AssertionError):view.verify_cohort(ROOT,read)
 def test_each_existing_mixed_generation(self):
  c,rows,b=view.finite_data()
  for rel,old in b.items():
   with self.subTest(path=rel):
    with self.assertRaises(AssertionError):view.verify_cohort(ROOT,lambda p:old if p==ROOT/rel else p.read_bytes())
 def test_each_protected_source_foreign_byte(self):
  c,rows,b=view.finite_data()
  for rel in c['protected_current_eleven_sha256']:
   with self.subTest(path=rel):
    with self.assertRaises(AssertionError):view.verify_cohort(ROOT,lambda p:p.read_bytes()+b' ' if p==ROOT/rel else p.read_bytes())
 def test_live_lifecycle_helper_change_rejected(self):
  m=model_module(ROOT);calls=0
  def parse(text):
   nonlocal calls
   calls+=1;nodes=m.ast(text)
   if calls==2:
    next(v for k,o,v in nodes if k=='eon_investment_lifecycle_daily_update').append(('clear_variable','=','treasury'))
   return nodes
  with self.assertRaises(AssertionError):view.live_protocol24_inner(ROOT,parse,m.one)
 def test_guarded_inner_debit_change_rejected(self):
  m=model_module(ROOT);calls=0
  def parse(text):
   nonlocal calls
   calls+=1;nodes=m.ast(text)
   if calls==2:
    inner=m.one(m.one(nodes,'eon_investment_execute_offer'),'if');inner.append(('subtract_from_variable','=',[('treasury','=','1')]))
   return nodes
  with self.assertRaises(AssertionError):view.live_protocol24_inner(ROOT,parse,m.one)
 def test_guarded_executor_flag_change_rejected(self):
  m=model_module(ROOT);calls=0
  def parse(text):
   nonlocal calls
   calls+=1;nodes=m.ast(text)
   if calls==2:
    inner=m.one(m.one(nodes,'eon_investment_execute_offer'),'if');inner[0]=('limit','=',[('always','=','yes')])
   return nodes
  with self.assertRaises(AssertionError):view.live_protocol24_inner(ROOT,parse,m.one)
if __name__=='__main__':unittest.main()
