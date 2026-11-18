import sys, unittest, tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
class ReportsTest(unittest.TestCase):
 def test_daily_report_saved_and_listed(self):
  with tempfile.TemporaryDirectory() as d, patch.object(server,'DB',Path(d)/'test.sqlite3'):
   m=[{'name':n,'value':1,'unit':'demo','timestamp':'2026-11-14T00:00:00Z','context':'synthetic demo reading'} for n in ['HR','SpO2','Temp','RR','Sleep','Stress']]
   result=server.handle('daily_report',{'measurements':m})
   self.assertTrue(result['saved'])
   rows=server.handle('cases',None)
   self.assertEqual(len(rows),1)
   self.assertEqual(rows[0]['payload']['report_type'],'daily_scan')
   self.assertEqual(len(rows[0]['payload']['measurements']),6)
 def test_empty_scan_rejected(self):
  with tempfile.TemporaryDirectory() as d, patch.object(server,'DB',Path(d)/'test.sqlite3'):
   with self.assertRaisesRegex(ValueError,'Complete the daily scan'):
    server.handle('daily_report',{'measurements':[]})
if __name__=='__main__':unittest.main()

class CombinedReportTests(unittest.TestCase):
 def sample_measurements(self):
  return [{'name':n,'value':1,'unit':'demo','timestamp':'2026-11-14T00:00:00Z','context':'synthetic demo reading'} for n in ['HR','SpO2','Temp','RR','Sleep','Stress']]
 def test_questionnaire_merges_into_same_daily_report(self):
  with tempfile.TemporaryDirectory() as d, patch.object(server,'DB',Path(d)/'test.sqlite3'):
   daily=server.handle('daily_report',{'measurements':self.sample_measurements()})
   data={'daily_report_id':daily['case_id'],'module':'M01','question_answers':{'M01_Q02':{'fields':{'0':'Forehead','1':'Pressure'},'notes':'test'}},'voice_transcripts':{'M01_Q02':'pressure'},'measurements':self.sample_measurements(),'facts':{}}
   result=server.handle('assess',data)
   cases=server.handle('cases',None)
   self.assertEqual(result['case_id'],daily['case_id'])
   self.assertEqual(len(cases),1)
   self.assertEqual(cases[0]['payload']['question_answers'],data['question_answers'])
   self.assertEqual(cases[0]['payload']['voice_transcripts'],data['voice_transcripts'])
   self.assertEqual(len(cases[0]['payload']['measurements']),6)
   self.assertEqual(cases[0]['payload']['other_symptoms'],'yes')
 def test_no_symptoms_explicitly_recorded(self):
  with tempfile.TemporaryDirectory() as d, patch.object(server,'DB',Path(d)/'test.sqlite3'):
   daily=server.handle('daily_report',{'measurements':self.sample_measurements()})
   server.handle('daily_report_no_symptoms',{'case_id':daily['case_id']})
   cases=server.handle('cases',None)
   self.assertEqual(len(cases),1)
   self.assertEqual(cases[0]['payload']['other_symptoms'],'no')
 def test_invalid_daily_link_cannot_update(self):
  with tempfile.TemporaryDirectory() as d, patch.object(server,'DB',Path(d)/'test.sqlite3'):
   with self.assertRaisesRegex(ValueError,'not found'):
    server.handle('assess',{'daily_report_id':'DAILY-INVALID','facts':{},'measurements':[],'question_answers':{}})
