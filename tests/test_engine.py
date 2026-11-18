import unittest,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import assess,evaluate,Truth,validate_measurements
RULES=json.loads((Path(__file__).resolve().parents[1]/'data/demo_rules.json').read_text())['rules']
class EngineTests(unittest.TestCase):
 def test_emergency_precedence(self):
  a=assess({'demo_emergency_signal':True,'demo_a':True,'demo_b':True},RULES)
  self.assertEqual(a['risk_workflow'],'emergency')
 def test_unknown_not_false(self):
  v,m=evaluate({'op':'and','args':[{'op':'fact','id':'x'},{'op':'fact','id':'y'}]},{'x':True})
  self.assertEqual(v,Truth.UNKNOWN);self.assertEqual(m,['y'])
 def test_not_unknown(self):
  v,_=evaluate({'op':'not','arg':{'op':'fact','id':'missing'}},{})
  self.assertEqual(v,Truth.UNKNOWN)
 def test_conflicting_evidence(self):
  a=assess({'demo_a':True,'demo_c':False,'demo_b':False,'demo_emergency_signal':False},RULES)
  self.assertEqual(a['status'],'Unresolved — further assessment required')
  self.assertTrue(any('demo_c' in r['conflicts'] for r in a['all_evaluations']))
 def test_multiple_candidates(self):
  a=assess({'demo_emergency_signal':False,'demo_a':True,'demo_b':True,'demo_c':True},RULES)
  self.assertEqual(len(a['candidate_patterns']),2)
 def test_unresolved(self):
  a=assess({},RULES)
  self.assertEqual(a['risk_workflow'],'unresolved');self.assertTrue(a['unknown_red_flags'])
 def test_missing_freshness_policy(self):
  v,issues=validate_measurements([{'id':'heart_rate','value':70,'unit':'bpm','timestamp':'2026-11-14T08:00:00Z','context':'resting'}],{})
  self.assertEqual(v,{});self.assertIn('no approved freshness policy',issues[0]['issue'])
 def test_clinical_blocked(self):
  with self.assertRaises(PermissionError):assess({},RULES,clinical=True)
 def test_unreviewed_rules_ignored(self):
  r=[dict(RULES[0],approval_status='draft')]
  self.assertEqual(assess({'demo_emergency_signal':True},r)['matched_emergency_rules'],[])
 def test_or_and_not(self):
  exp={'op':'or','args':[{'op':'fact','id':'x'},{'op':'not','arg':{'op':'fact','id':'y'}}]}
  self.assertEqual(evaluate(exp,{'x':False,'y':False})[0],Truth.TRUE)
if __name__=='__main__':unittest.main()
