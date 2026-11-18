"""AstroCare demo server for local use or a temporary hosted demo."""
import hmac
import json, sqlite3, uuid
import os
import secrets
from datetime import datetime,timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse
from engine import assess,validate_measurements
from guidance import educational_guidance
ROOT=Path(__file__).parent
DB=ROOT/'local_demo.sqlite3'
KB=json.loads((ROOT/'data/source_knowledge_base.json').read_text(encoding='utf-8'))
DEMO=json.loads((ROOT/'data/demo_rules.json').read_text(encoding='utf-8'))['rules']
POLICY=json.loads((ROOT/'data/policies.json').read_text(encoding='utf-8'))
SESSION_COOKIE = '__Host-astrocare-demo'
HOSTED_NOTICE = b'''<p class="ent-notice" role="note"><strong>Public demo.</strong>
Use fictional details only. Reports, exercise and journal entries are temporary and
may disappear when the server restarts.</p>'''

def now():return datetime.now(timezone.utc).isoformat()
def conn(db_path=None):
    db=sqlite3.connect(DB if db_path is None else db_path)
    db.execute('BEGIN IMMEDIATE')
    db.execute('CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, created TEXT, payload TEXT, assessment TEXT, status TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, action TEXT, case_id TEXT, detail TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS profile (id TEXT PRIMARY KEY, payload TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS followups (id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT, time TEXT, symptom TEXT, severity TEXT, notes TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS exercise (day TEXT PRIMARY KEY, status TEXT NOT NULL, activity TEXT, minutes INTEGER, updated TEXT NOT NULL)')
    # Non-destructive migration: preserve existing exercise and journal records.
    existing={row[1] for row in db.execute('PRAGMA table_info(exercise)')}
    for column,typ in [('cardio_activity','TEXT'),('cardio_minutes','INTEGER'),('resistance_activity','TEXT'),('resistance_minutes','INTEGER')]:
        if column not in existing:db.execute(f'ALTER TABLE exercise ADD COLUMN {column} {typ}')

    db.execute('CREATE TABLE IF NOT EXISTS journal (id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT NOT NULL, prompt_id TEXT NOT NULL, prompt TEXT NOT NULL, entry TEXT NOT NULL)')
    db.commit();return db
def log(db,action,case_id='',detail=''):
    db.execute('INSERT INTO audit(time,action,case_id,detail) VALUES(?,?,?,?)',(now(),action,case_id,detail))
def handle(action,data,db_path=None):
    if action=='metadata':
        return {'modules':KB['modules'],'questions':KB['questions'],'candidates':KB['candidates'],'alerts':KB['alerts'],'mode':'SYNTHETIC DEMO ONLY','clinical_enabled':False}
    db=conn(db_path)
    try:
        if action=='profile':
            if data is None:
                r=db.execute("SELECT payload FROM profile WHERE id='crew'").fetchone();return json.loads(r[0]) if r else {}
            db.execute("INSERT OR REPLACE INTO profile VALUES('crew',?)",(json.dumps(data),));log(db,'profile_saved',detail='Pre-mission profile updated');db.commit();return {'saved':True}
        if action=='assess':
            facts=data.get('facts',{});measures=data.get('measurements',[])
            valid,issues=validate_measurements(measures,POLICY['measurement_freshness_policy'])
            assessment=assess(facts,DEMO)
            assessment['measurement_issues']=issues
            assessment['validated_measurements']=list(valid)
            assessment['important_unknowns']=sorted({m for r in assessment['unknown_red_flags'] for m in r['missing']})
            assessment['educational_guidance']=educational_guidance(data.get('module'),data.get('question_answers',{}))
            linked_daily_id=data.get('daily_report_id')
            cid='CASE-'+uuid.uuid4().hex[:10].upper()
            status='EMERGENCY_REVIEW' if assessment['risk_workflow']=='emergency' else 'URGENT_REVIEW' if assessment['risk_workflow']=='urgent_review' else 'PENDING_CLINICIAN_REVIEW'
            if assessment['educational_guidance']['safety']['level']=='emergency':status='EMERGENCY_REVIEW'
            elif assessment['educational_guidance']['safety']['level']=='urgent' and status!='EMERGENCY_REVIEW':status='URGENT_REVIEW'
            if linked_daily_id:
                row=db.execute('SELECT payload FROM cases WHERE id=? AND status IN (?,?)',
                               (linked_daily_id,'DAILY_SCAN_DEMO','PENDING_CLINICIAN_REVIEW')).fetchone()
                if not row:raise ValueError('Daily scan report not found or cannot be updated')
                original=json.loads(row[0]);original.update(data)
                original['report_type']='daily_scan'
                original['other_symptoms']='yes'
                original['measurements']=original.get('measurements') or measures
                cid=linked_daily_id
                db.execute('UPDATE cases SET payload=?,assessment=?,status=? WHERE id=?',
                           (json.dumps(original),json.dumps(assessment),status,cid))
                log(db,'daily_report_symptoms_added',cid,'Questionnaire answers merged with daily measurements')
            else:
                db.execute('INSERT INTO cases VALUES(?,?,?,?,?)',(cid,now(),json.dumps(data),json.dumps(assessment),status))
                log(db,'case_created',cid,'Demo assessment; no medical diagnosis')
            if status=='EMERGENCY_REVIEW':log(db,'emergency_workflow_activated',cid,'Local alert only; no message transmitted')
            db.commit();return {'case_id':cid,'status':status,'assessment':assessment}
        if action=='daily_report':
            if not isinstance(data,dict):raise ValueError('Report payload must be an object')
            measurements=data.get('measurements')
            if not isinstance(measurements,list) or len(measurements)!=6:
                raise ValueError('Complete the daily scan before creating a report')
            for m in measurements:
                if not isinstance(m,dict) or not all(k in m for k in ('name','value','unit','timestamp','context')):
                    raise ValueError('Incomplete demo measurement')
                if 'synthetic demo' not in str(m['context']).lower():
                    raise ValueError('Daily demo report accepts synthetic readings only')
            cid='DAILY-'+uuid.uuid4().hex[:10].upper()
            payload={'report_type':'daily_scan','module':None,'measurements':measurements,
                     'question_answers':{},'other_symptoms':data.get('other_symptoms','unknown')}
            assessment={'mode':'SYNTHETIC DEMO — NOT CLINICAL','clinical_mode_enabled':False,
                        'status':'Daily scan recorded; no clinical assessment or diagnosis'}
            db.execute('INSERT INTO cases VALUES(?,?,?,?,?)',(cid,now(),json.dumps(payload),json.dumps(assessment),'DAILY_SCAN_DEMO'))
            log(db,'daily_scan_report_created',cid,'Synthetic measurements only')
            db.commit();return {'case_id':cid,'status':'DAILY_SCAN_DEMO','saved':True}
        if action=='daily_report_no_symptoms':
            cid=data.get('case_id') if isinstance(data,dict) else None
            row=db.execute('SELECT payload FROM cases WHERE id=? AND status=?',(cid,'DAILY_SCAN_DEMO')).fetchone()
            if not row:raise ValueError('Daily scan report not found')
            payload=json.loads(row[0]);payload['other_symptoms']='no'
            db.execute('UPDATE cases SET payload=? WHERE id=?',(json.dumps(payload),cid))
            log(db,'daily_report_no_symptoms',cid,'Astronaut explicitly reported no other symptoms')
            db.commit();return {'saved':True,'case_id':cid}
        if action=='cases':
            rows=db.execute('SELECT id,created,status,payload,assessment FROM cases ORDER BY created DESC LIMIT 100').fetchall()
            return [{'id':r[0],'created':r[1],'status':r[2],'payload':json.loads(r[3]),'assessment':json.loads(r[4])} for r in rows]
        if action=='review':
            cid=data.get('case_id');status=data.get('status')
            if status not in ('UNDER_REVIEW','NEEDS_MORE_INFORMATION','REVIEWED_DEMO'):
                raise ValueError('Invalid review status')
            if not db.execute('SELECT 1 FROM cases WHERE id=?',(cid,)).fetchone():raise ValueError('Case not found')
            db.execute('UPDATE cases SET status=? WHERE id=?',(status,cid));log(db,'case_review_updated',cid,status);db.commit();return {'saved':True}
        if action=='followup':
            if data.get('severity') not in ('mild','moderate','severe','unknown'):raise ValueError('Invalid severity')
            db.execute('INSERT INTO followups(case_id,time,symptom,severity,notes) VALUES(?,?,?,?,?)',(data.get('case_id',''),now(),data.get('symptom',''),data['severity'],data.get('notes','')))
            log(db,'followup_recorded',data.get('case_id',''));db.commit();return {'saved':True}
        if action=='followups':
            rows=db.execute('SELECT case_id,time,symptom,severity,notes FROM followups ORDER BY time DESC').fetchall()
            return [dict(zip(('case_id','time','symptom','severity','notes'),r)) for r in rows]
        if action=='exercise':
            if data is None:
                rows=db.execute('SELECT day,status,cardio_activity,cardio_minutes,resistance_activity,resistance_minutes,updated FROM exercise ORDER BY day DESC LIMIT 90').fetchall()
                return [dict(zip(('day','status','cardio_activity','cardio_minutes','resistance_activity','resistance_minutes','updated'),r)) for r in rows]
            day=data.get('day')
            try:
                parsed=datetime.strptime(day,'%Y-%m-%d')
                if parsed.strftime('%Y-%m-%d')!=day:raise ValueError()
            except (ValueError,TypeError):raise ValueError('Invalid exercise date')
            status=data.get('status')
            if status not in ('yes','no','not_yet'):raise ValueError('Invalid exercise status')
            ca=data.get('cardio_activity') or ''
            ra=data.get('resistance_activity') or ''
            cm=data.get('cardio_minutes')
            rm=data.get('resistance_minutes')
            if ca not in ('','Treadmill','Stationary cycling','Other cardio') or ra not in ('','Resistance device','Resistance bands','Other resistance'):
                raise ValueError('Invalid exercise activity')
            for activity,minutes in ((ca,cm),(ra,rm)):
                if bool(activity)!=(minutes is not None):
                    raise ValueError('Activity and duration must be provided together')
                if minutes is not None and (type(minutes) is not int or not 1<=minutes<=1440):
                    raise ValueError('Exercise duration must be positive whole minutes')
            if (cm or 0)+(rm or 0)>1440:
                raise ValueError('Total exercise time cannot exceed one day')
            if status=='yes' and not (ca and ra and cm and rm):
                raise ValueError('Both cardio and resistance with durations required to mark completed')
            if status=='no' and (ca or ra):
                raise ValueError('Choose partial to record completed exercise')
            db.execute('INSERT OR REPLACE INTO exercise(day,status,activity,minutes,updated,cardio_activity,cardio_minutes,resistance_activity,resistance_minutes) VALUES(?,?,?,?,?,?,?,?,?)',
                (day,status,' / '.join(x for x in (ca,ra) if x),((cm or 0)+(rm or 0)) if (cm or rm) else None,now(),ca,cm,ra,rm))
            log(db,'exercise_check_saved',detail=day+' '+status);db.commit();return {'saved':True}
        if action=='journal':
            if data is None:
                rows=db.execute('SELECT id,created,prompt_id,prompt,entry FROM journal ORDER BY id DESC LIMIT 100').fetchall()
                return [dict(zip(('id','created','prompt_id','prompt','entry'),r)) for r in rows]
            entry=str(data.get('entry','')).strip()
            prompt_id=str(data.get('prompt_id',''))
            prompt=str(data.get('prompt',''))
            if not entry or len(entry)>10000:raise ValueError('Journal entry must contain 1-10000 characters')
            if not prompt_id or len(prompt_id)>80 or not prompt or len(prompt)>500:raise ValueError('Invalid journal prompt')
            db.execute('INSERT INTO journal(created,prompt_id,prompt,entry) VALUES(?,?,?,?)',(now(),prompt_id,prompt,entry))
            log(db,'journal_entry_saved',detail='Journal entry saved (content excluded from audit)')
            db.commit();return {'saved':True}
        if action=='guidance':
            if not isinstance(data,dict):raise ValueError('Guidance request must be an object')
            cid=data.get('case_id')
            row=db.execute('SELECT payload,assessment FROM cases WHERE id=?',(cid,)).fetchone()
            if not row:raise ValueError('Case not found')
            payload=json.loads(row[0]);assessment=json.loads(row[1])
            confirmations=data.get('confirmations',payload.get('guidance_confirmations',{}))
            alert_answers=data.get('alert_answers',payload.get('guidance_alert_answers',{}))
            guide=educational_guidance(payload.get('module'),payload.get('question_answers',{}),confirmations,alert_answers)
            if assessment.get('risk_workflow')=='emergency':
                guide['safety']['level']='emergency'
                guide['non_drug_options']=[]
                guide['clinician_only_options']=[]
            if 'confirmations' in data or 'alert_answers' in data:
                payload['guidance_confirmations']=guide['confirmations']
                payload['guidance_alert_answers']=guide['alert_answers']
                assessment['educational_guidance']=guide
                # Keep the original evaluator result intact. Record reported warning
                # escalation separately; do not label a patient medically cleared.
                prior=assessment.setdefault('original_case_workflow_status',db.execute('SELECT status FROM cases WHERE id=?',(cid,)).fetchone()[0])
                status='EMERGENCY_REVIEW' if guide['safety']['level']=='emergency' else 'URGENT_REVIEW' if guide['safety']['level']=='urgent' else prior
                db.execute('UPDATE cases SET payload=?,assessment=?,status=? WHERE id=?',(json.dumps(payload),json.dumps(assessment),status,cid))
                log(db,'educational_guidance_updated',cid,'Reported feature/warning confirmations; no clinical diagnosis')
                db.commit()
            return {'case_id':cid,'guidance':guide}
        if action=='audit':
            rows=db.execute('SELECT time,action,case_id,detail FROM audit ORDER BY id DESC LIMIT 200').fetchall()
            return [dict(zip(('time','action','case_id','detail'),r)) for r in rows]
        raise ValueError('Unknown action')
    finally:db.close()
class Handler(BaseHTTPRequestHandler):
    def visitor_id(self):
        cookie = SimpleCookie()
        cookie.load(self.headers.get('Cookie', ''))
        session = cookie.get(SESSION_COOKIE)
        if session:
            visitor, _, signature = session.value.partition('.')
            if len(visitor) == 32 and all(c in '0123456789abcdef' for c in visitor):
                expected = hmac.digest(self.server.session_key, visitor.encode(), 'sha256').hex()
                if hmac.compare_digest(signature.encode(), expected.encode()):
                    return visitor
        return None

    def serve_home(self):
        page = (ROOT/'index.html').read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        if self.server.demo_dir is not None:
            page = page.replace(b'<main>', b'<main>' + HOSTED_NOTICE, 1)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "frame-ancestors 'none'")
            if self.visitor_id() is None:
                visitor = secrets.token_hex(16)
                signature = hmac.digest(self.server.session_key, visitor.encode(), 'sha256').hex()
                self.send_header('Set-Cookie', f'{SESSION_COOKIE}={visitor}.{signature}; Path=/; Secure; HttpOnly; SameSite=Lax')
        self.send_header('Content-Length', str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def serve_api(self, action, data):
        if self.server.demo_dir is None or action == 'metadata':
            self.send(handle(action, data))
            return
        visitor = self.visitor_id()
        if visitor is None:
            self.send({'error': 'Reload the demo with cookies enabled to start a session.'}, 403)
            return
        self.send(handle(action, data, self.server.demo_dir / f'{visitor}.sqlite3'))

    def send(self,obj,code=200):
        b=json.dumps(obj,ensure_ascii=False).encode();self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/':
            self.serve_home()
        elif path=='/healthz':
            self.send({'status':'ok'})
        elif path=='/question_ui_options.json':
            b=(ROOT/'data/question_ui_options.json').read_bytes();self.send_response(200);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
        elif path.startswith('/api/'):
            try:self.serve_api(path[5:],None)
            except Exception as e:self.send({'error':str(e)},400)
        else:self.send({'error':'Not found'},404)
    def do_POST(self):
        path=urlparse(self.path).path
        if not path.startswith('/api/'):
            self.send({'error':'Not found'},404)
            return
        if self.server.demo_dir is not None and (
            self.headers.get('Sec-Fetch-Site') not in (None, 'same-origin')
            or self.headers.get_content_type() != 'application/json'
        ):
            self.send({'error':'The hosted demo accepts same-origin JSON requests.'},403)
            return
        try:
            n=int(self.headers.get('Content-Length',0))
            if not 0 <= n <= 1000000:raise ValueError('Invalid request size')
            data=json.loads(self.rfile.read(n) or '{}')
            self.serve_api(path[5:],data)
        except Exception as e:self.send({'error':str(e)},400)

def run(host, port, demo_dir=None):
    with ThreadingHTTPServer((host, port), Handler) as server:
        server.demo_dir = demo_dir
        server.session_key = secrets.token_bytes(32)
        print(f'AstroCare demo listening on http://{host}:{server.server_port}', flush=True)
        server.serve_forever()

if __name__=='__main__':
    if os.environ.get('ASTROCARE_PUBLIC_DEMO') == '1':
        with TemporaryDirectory(prefix='astrocare-demo-') as directory:
            run('0.0.0.0', int(os.environ.get('PORT', '10000')), Path(directory))
    else:
        run('127.0.0.1', 8765)
