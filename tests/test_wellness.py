import unittest,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
class WellnessTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.previous=server.DB
  server.DB=Path(self.tmp.name)/'test.sqlite3'
 def tearDown(self):
  server.DB=self.previous
  self.tmp.cleanup()
 def test_exercise_persists_and_updates(self):
  self.assertTrue(server.handle('exercise',{'day':'2026-11-14','status':'yes','cardio_activity':'Treadmill','cardio_minutes':30,'resistance_activity':'Resistance device','resistance_minutes':40})['saved'])
  self.assertEqual(server.handle('exercise',None)[0]['cardio_minutes'],30)
  self.assertEqual(server.handle('exercise',None)[0]['resistance_minutes'],40)
  server.handle('exercise',{'day':'2026-11-14','status':'not_yet','cardio_activity':'Treadmill','cardio_minutes':20,'resistance_activity':'','resistance_minutes':None})
  self.assertEqual(server.handle('exercise',None)[0]['status'],'not_yet')
  self.assertEqual(server.handle('exercise',None)[0]['cardio_minutes'],20)
  self.assertIsNone(server.handle('exercise',None)[0]['resistance_minutes'])
 def test_both_required_for_completed(self):
  with self.assertRaises(ValueError):server.handle('exercise',{'day':'2026-11-14','status':'yes','cardio_activity':'Treadmill','cardio_minutes':20})
 def test_partial_may_save_single_exercise(self):
  server.handle('exercise',{'day':'2026-11-14','status':'not_yet','cardio_activity':'Treadmill','cardio_minutes':60,'resistance_activity':'','resistance_minutes':None})
  self.assertEqual(server.handle('exercise',None)[0]['cardio_minutes'],60)
 def test_exercise_invalid_status(self):
  with self.assertRaises(ValueError):server.handle('exercise',{'day':'2026-11-14','status':'maybe'})
 def test_journal_save_and_history(self):
  server.handle('journal',{'prompt_id':'love','prompt':'What does love mean to you?','entry':'Being connected.'})
  rows=server.handle('journal',None)
  self.assertEqual(rows[0]['entry'],'Being connected.')
  audit=server.handle('audit',None)
  self.assertNotIn('Being connected.',str(audit))
 def test_empty_journal_rejected(self):
  with self.assertRaises(ValueError):server.handle('journal',{'prompt_id':'hope','prompt':'Hope?','entry':' '})
if __name__=='__main__':unittest.main()
