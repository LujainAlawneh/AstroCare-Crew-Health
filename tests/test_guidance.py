import sys,unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import guidance,server
class GuidanceTests(unittest.TestCase):
 def no_warnings(self,module='M01'):
  return {a['id']:'no' for a in guidance.KB['alerts'] if a['module']==module}
 def test_unknown_is_not_absent(self):
  d=guidance.educational_guidance('M01',{})
  self.assertEqual(d['safety']['level'],'incomplete');self.assertEqual(d['safety']['unanswered_warnings'],3)
  self.assertTrue(all(c['confirmed_features']==0 for c in d['patterns']))
 def test_structured_character_suggests_association_only(self):
  d=guidance.educational_guidance('M01',{'M01_Q02':{'fields':{'1':'Throbbing / pulsating'}}})
  self.assertEqual(d['patterns'][0]['id'],'M01_C01');self.assertEqual(d['patterns'][0]['confirmed_features'],0)
  self.assertTrue(d['patterns'][0]['answer_associations'])
 def test_grouped_yes_does_not_confirm_conjunction(self):
  d=guidance.educational_guidance('M01',{'M01_Q03':'true'})
  c=next(c for c in d['patterns'] if c['id']=='M01_C01')
  self.assertTrue(c['answer_associations']);self.assertTrue(all(f['state']=='unknown' for f in c['features']))
 def test_free_text_negation_never_keyword_matched(self):
  d=guidance.educational_guidance('M02',{'M02_Q05':'No diarrhea; not associated with motion'})
  self.assertFalse(any(c['answer_associations'] for c in d['patterns']))
 def test_confirmed_features_and_conflicts_separate(self):
  d=guidance.educational_guidance('M01',{}, {'M01_C01:0':'yes','M01_C01:1':'no'})
  c=next(c for c in d['patterns'] if c['id']=='M01_C01')
  self.assertEqual(c['confirmed_features'],1);self.assertEqual(c['not_reported_features'],1)
  self.assertIn('Mixed',c['match_label'])
 def test_no_care_before_safety_review(self):
  d=guidance.educational_guidance('M01',{'M01_Q03':'true'})
  self.assertEqual(d['non_drug_options'],[]);self.assertEqual(d['clinician_only_options'],[])
 def test_conditional_care_after_review(self):
  d=guidance.educational_guidance('M01',{}, {'M01_C01:0':'yes'}, self.no_warnings())
  self.assertEqual(d['safety']['level'],'review');self.assertTrue(d['non_drug_options'])
  self.assertTrue(all(c['eligibility'] and c['cautions'] for c in d['non_drug_options']))
 def test_reported_emergency_overrides_care(self):
  warnings=self.no_warnings();warnings['M01_A01']='yes'
  d=guidance.educational_guidance('M01',{}, {'M01_C01:0':'yes'}, warnings)
  self.assertEqual(d['safety']['level'],'emergency');self.assertFalse(d['non_drug_options']);self.assertFalse(d['clinician_only_options'])
 def test_urgent_warning_overrides_care(self):
  warnings=self.no_warnings();warnings['M01_A03']='yes'
  d=guidance.educational_guidance('M01',{}, {}, warnings)
  self.assertEqual(d['safety']['level'],'urgent');self.assertFalse(d['non_drug_options'])
 def test_neurological_answer_cannot_be_cleared_by_checkbox(self):
  d=guidance.educational_guidance('M01',{'M01_Q04':'true'}, {},self.no_warnings())
  self.assertEqual(d['safety']['level'],'emergency')
  self.assertEqual(d['warnings'][0]['reported_in_questions'],['M01_Q04'])
 def test_no_cross_module_confirmations(self):
  with self.assertRaises(ValueError):guidance.educational_guidance('M01',{}, {'M02_C01:0':'yes'})
 def test_all_modules_have_sourced_candidates(self):
  for module in guidance.KB['modules']:
   d=guidance.educational_guidance(module['id'],{})
   self.assertTrue(d['patterns']);self.assertTrue(d['sources'])
   self.assertTrue(all(c['source_ids'] for c in d['patterns']))
 def test_no_probability_field(self):
  d=guidance.educational_guidance('M01',{})
  self.assertFalse(any('probability' in c or 'score' in c for c in d['patterns']))
 def test_guidance_saved_without_losing_case(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(server,'DB',Path(tmp)/'db.sqlite3'):
   answers={'M01_Q02':{'fields':{'1':'Throbbing / pulsating'},'notes':'test'}}
   case=server.handle('assess',{'module':'M01','question_answers':answers,'facts':{},'measurements':[]})
   warning=self.no_warnings();warning['M01_A01']='yes'
   saved=server.handle('guidance',{'case_id':case['case_id'],'confirmations':{'M01_C01:0':'yes'},'alert_answers':warning})
   self.assertEqual(saved['guidance']['safety']['level'],'emergency')
   row=server.handle('cases',None)[0]
   self.assertEqual(row['payload']['question_answers'],answers)
   self.assertEqual(row['status'],'EMERGENCY_REVIEW')
   self.assertFalse(row['assessment']['clinical_mode_enabled'])
   self.assertEqual(row['assessment']['risk_workflow'],case['assessment']['risk_workflow'])
   loaded=server.handle('guidance',{'case_id':case['case_id']})
   self.assertEqual(loaded['guidance']['confirmations']['M01_C01:0'],'yes')
 def test_original_emergency_is_preserved(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(server,'DB',Path(tmp)/'db.sqlite3'):
   case=server.handle('assess',{'module':'M01','question_answers':{},'facts':{'demo_emergency_signal':'true'},'measurements':[]})
   result=server.handle('guidance',{'case_id':case['case_id'],'alert_answers':self.no_warnings()})
   self.assertEqual(result['guidance']['safety']['level'],'emergency')
if __name__=='__main__':unittest.main()
