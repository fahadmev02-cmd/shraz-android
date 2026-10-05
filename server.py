"""Shraz first-release web app. Python 3.11+, no runtime dependencies."""
import argparse
import base64
import calendar
import datetime as dt
import hashlib
import hmac
import json
import mimetypes
import re
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).parent
SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS schema_versions(version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_versions VALUES(1);
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('client','coach','admin')), created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id), expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS profiles(user_id INTEGER PRIMARY KEY REFERENCES users(id), data TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS assignments(client_id INTEGER PRIMARY KEY REFERENCES users(id), coach_id INTEGER REFERENCES users(id));
CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY, client_id INTEGER REFERENCES users(id), kind TEXT NOT NULL, version INTEGER NOT NULL, data TEXT NOT NULL, author INTEGER REFERENCES users(id), created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY, client_id INTEGER REFERENCES users(id), day TEXT NOT NULL, kind TEXT NOT NULL, ref TEXT NOT NULL, data TEXT NOT NULL, UNIQUE(client_id,day,kind,ref));
CREATE TABLE IF NOT EXISTS measurements(id INTEGER PRIMARY KEY, client_id INTEGER REFERENCES users(id), day TEXT NOT NULL, weight REAL NOT NULL, waist REAL, UNIQUE(client_id,day));
CREATE TABLE IF NOT EXISTS checkins(id INTEGER PRIMARY KEY, client_id INTEGER REFERENCES users(id), day TEXT NOT NULL, data TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', feedback TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, client_id INTEGER REFERENCES users(id), sender_id INTEGER REFERENCES users(id), body TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS photos(id INTEGER PRIMARY KEY, client_id INTEGER REFERENCES users(id), day TEXT NOT NULL, view TEXT NOT NULL, mime TEXT NOT NULL, content BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS membership_plans(id INTEGER PRIMARY KEY, name TEXT NOT NULL, months INTEGER NOT NULL, price REAL NOT NULL, pause_days INTEGER NOT NULL, min_pause INTEGER NOT NULL DEFAULT 1, max_pause INTEGER NOT NULL DEFAULT 30);
CREATE TABLE IF NOT EXISTS memberships(client_id INTEGER PRIMARY KEY REFERENCES users(id), plan_id INTEGER REFERENCES membership_plans(id), start TEXT NOT NULL, expiry TEXT NOT NULL, used_pause INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS pauses(id INTEGER PRIMARY KEY, client_id INTEGER REFERENCES users(id), days INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', start TEXT, end TEXT);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, actor INTEGER, action TEXT NOT NULL, target INTEGER, created TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS plans_client ON plans(client_id,kind,id);
CREATE INDEX IF NOT EXISTS messages_client ON messages(client_id,id);
"""

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')

def today():
    return dt.date.today().isoformat()

def encode(value):
    return json.dumps(value, separators=(',', ':'))

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 310000).hex()
    return f'{salt}${digest}'

def password_matches(password, stored):
    return hmac.compare_digest(password_hash(password, stored.split('$')[0]), stored)

def text(value, label, maximum=500, minimum=1):
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ValueError(f'{label} must be {minimum}–{maximum} characters.')
    return value.strip()

def number(value, label, low, high, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not low <= value <= high:
        raise ValueError(f'{label} must be between {low} and {high}.')
    if integer and int(value) != value:
        raise ValueError(f'{label} must be a whole number.')
    return int(value) if integer else value

def date_value(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Use a date in YYYY-MM-DD format.')
    return dt.date.fromisoformat(value).isoformat()

def history_date(value):
    value = date_value(value)
    if value > today():
        raise ValueError('Tracking dates cannot be in the future.')
    return value

class AppServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, db_path, secure_cookie=False):
        self.db_path = str(db_path)
        self.secure_cookie = secure_cookie
        self.auth_attempts = defaultdict(deque)
        self.rate_lock = threading.Lock()
        with self.connect() as db:
            db.executescript(SCHEMA)
        super().__init__(address, Handler)

    def connect(self):
        db = sqlite3.connect(self.db_path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

class Handler(BaseHTTPRequestHandler):
    server_version = 'Shraz/0.1'
    def log_message(self, *_):
        pass  # Do not write profiles, messages, or auth data to access logs.

    def send(self, status, body, mime='application/json', cookie=None):
        if mime == 'application/json':
            body = encode(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store' if self.path.startswith('/api/') else 'no-cache')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.route(False)

    def do_POST(self):
        self.route(True)

    def route(self, post):
        db = self.server.connect()
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            if not path.startswith('/api/'):
                if post:
                    return self.send(405, {'error':'Method not allowed.'})
                allowed = {'/':'index.html','/index.html':'index.html','/app.js':'app.js','/styles.css':'styles.css','/manifest.webmanifest':'manifest.webmanifest','/icon.svg':'icon.svg','/sw.js':'sw.js'}
                file = ROOT/'static'/allowed.get(path,'__missing__')
                if not file.is_file():
                    return self.send(404, {'error':'Not found.'})
                return self.send(200, file.read_bytes(), mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
            data = {}
            if post:
                origin = self.headers.get('Origin')
                if origin and urlparse(origin).netloc != self.headers.get('Host'):
                    return self.send(403, {'error':'Cross-origin requests are not allowed.'})
                if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                    return self.send(415, {'error':'Send application/json.'})
                length = int(self.headers.get('Content-Length',0))
                if not 0 < length <= 3_000_000:
                    return self.send(413, {'error':'Request is empty or too large.'})
                data = json.loads(self.rfile.read(length))
                if not isinstance(data,dict):
                    raise ValueError('Expected a JSON object.')
            if post and path in ('/api/login','/api/register','/api/setup'):
                with self.server.rate_lock:
                    key = self.client_address[0]
                    if len(self.server.auth_attempts) > 10000:
                        self.server.auth_attempts.clear()
                    attempts = self.server.auth_attempts[key]
                    while attempts and attempts[0] < time.time()-300:
                        attempts.popleft()
                    if len(attempts) >= 20:
                        return self.send(429, {'error':'Too many attempts. Try again in five minutes.'})
                    attempts.append(time.time())
                return self.authenticate(db, path, data)
            cookie = SimpleCookie(self.headers.get('Cookie',''))
            token = cookie['shraz_session'].value if 'shraz_session' in cookie else ''
            session_hash = hashlib.sha256(token.encode()).hexdigest()
            user = db.execute('SELECT u.id,u.name,u.email,u.role FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?',(session_hash,time.time())).fetchone()
            if path == '/api/session' and not post:
                return self.send(200, {'user':dict(user) if user else None,'needs_setup':not db.execute('SELECT 1 FROM users LIMIT 1').fetchone()})
            if not user:
                return self.send(401, {'error':'Please sign in.'})
            if path == '/api/logout' and post:
                db.execute('DELETE FROM sessions WHERE token=?',(session_hash,)); db.commit()
                return self.send(200, {'ok':True}, cookie='shraz_session=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict')
            if path.startswith('/api/admin'):
                if user['role'] != 'admin':
                    return self.send(403, {'error':'Administrator access required.'})
                return self.admin(db,user,path,data,post)
            if path == '/api/clients' and not post:
                if user['role'] == 'client':
                    return self.send(200, [])
                sql = "SELECT u.id,u.name,u.email FROM users u WHERE u.role='client'"
                params = ()
                if user['role'] == 'coach':
                    sql += ' AND u.id IN (SELECT client_id FROM assignments WHERE coach_id=?)'; params=(user['id'],)
                return self.send(200, [dict(r) for r in db.execute(sql+' ORDER BY u.name',params)])
            query = parse_qs(parsed.query)
            client_id = int(data.get('client_id') or query.get('client',['0'])[0] or 0)
            if user['role'] == 'client':
                if client_id and client_id != user['id']:
                    return self.send(403, {'error':'You can only access your own workspace.'})
                client_id = user['id']
            client = db.execute("SELECT id,name,email FROM users WHERE id=? AND role='client'",(client_id,)).fetchone()
            if not client:
                return self.send(404, {'error':'Select a client to open their workspace.'})
            if user['role'] == 'coach' and not db.execute('SELECT 1 FROM assignments WHERE client_id=? AND coach_id=?',(client_id,user['id'])).fetchone():
                return self.send(403, {'error':'This client is not assigned to you.'})
            if path == '/api/workspace' and not post:
                day = date_value(query.get('day',[today()])[0])
                return self.send(200,self.workspace(db,client,day))
            if path.startswith('/api/photo/') and not post:
                photo = db.execute('SELECT mime,content FROM photos WHERE id=? AND client_id=?',(int(path.rsplit('/',1)[1]),client_id)).fetchone()
                if not photo:
                    return self.send(404, {'error':'Photo not found.'})
                return self.send(200,bytes(photo['content']),photo['mime'])
            if not post:
                return self.send(404, {'error':'Not found.'})
            staff = user['role'] in ('coach','admin')
            client_only = ('/api/profile','/api/logs','/api/progress','/api/checkins','/api/photos','/api/membership/pause')
            if path in client_only and staff:
                return self.send(403, {'error':'Only the client can submit personal tracking data.'})
            if path == '/api/profile':
                profile = {
                    'goal':text(data.get('goal'),'Goal',80),
                    'diet':text(data.get('diet'),'Diet preference',100),
                    'height':number(data.get('height'),'Height in cm',100,250),
                    'age':number(data.get('age'),'Age',18,110,True),
                    'allergies':text(data.get('allergies',''),'Allergies',500,0),
                    'activity':text(data.get('activity'),'Activity level',80),
                }
                db.execute('INSERT INTO profiles VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET data=excluded.data',(client_id,encode(profile)))
            elif path == '/api/logs':
                kind = data.get('kind'); ref = text(data.get('ref','today'),'Item',100)
                day = history_date(data.get('day',today())); payload = data.get('value')
                if kind in ('meal','workout'):
                    if not isinstance(payload,bool):
                        raise ValueError('Completion must be true or false.')
                    plan = db.execute('SELECT data FROM plans WHERE client_id=? AND kind=? ORDER BY id DESC LIMIT 1',(client_id,'diet' if kind=='meal' else 'workout')).fetchone()
                    if not plan or ref not in [str(item['id']) for item in json.loads(plan['data'])['items']]:
                        raise ValueError('This item is not in your current plan. Refresh and try again.')
                elif kind == 'water':
                    payload = number(payload,'Water in ml',0,10000,True)
                elif kind == 'exercise':
                    if not isinstance(payload,dict): raise ValueError('Expected exercise details.')
                    plan = db.execute("SELECT data FROM plans WHERE client_id=? AND kind='workout' ORDER BY id DESC LIMIT 1",(client_id,)).fetchone()
                    if not plan or ref not in [str(item['id']) for item in json.loads(plan['data'])['items']]:
                        raise ValueError('Exercise is not in your current plan.')
                    payload = {k:number(payload.get(k),k,0,1000,k!='weight') for k in ('sets','reps','weight')}
                else:
                    raise ValueError('Unknown log type.')
                db.execute('INSERT INTO logs(client_id,day,kind,ref,data) VALUES(?,?,?,?,?) ON CONFLICT(client_id,day,kind,ref) DO UPDATE SET data=excluded.data',(client_id,day,kind,ref,encode(payload)))
            elif path == '/api/progress':
                day = history_date(data.get('day',today())); weight=number(data.get('weight'),'Weight in kg',25,400)
                waist=number(data['waist'],'Waist in cm',30,250) if data.get('waist') is not None else None
                db.execute('INSERT INTO measurements(client_id,day,weight,waist) VALUES(?,?,?,?) ON CONFLICT(client_id,day) DO UPDATE SET weight=excluded.weight,waist=excluded.waist',(client_id,day,weight,waist))
            elif path == '/api/checkins':
                payload={k:number(data.get(k),k,1,10,True) for k in ('energy','sleep','hunger','adherence')}
                payload['notes']=text(data.get('notes',''),'Notes',3000,0)
                if db.execute("SELECT 1 FROM checkins WHERE client_id=? AND day=?",(client_id,today())).fetchone():
                    raise ValueError('You already submitted a check-in today.')
                db.execute('INSERT INTO checkins(client_id,day,data) VALUES(?,?,?)',(client_id,today(),encode(payload)))
            elif path == '/api/checkins/review':
                if not staff: return self.send(403, {'error':'Coach access required.'})
                status=data.get('status')
                if status not in ('reviewed','changes required'): raise ValueError('Invalid review status.')
                cursor=db.execute('UPDATE checkins SET status=?,feedback=? WHERE id=? AND client_id=?',(status,text(data.get('feedback'),'Feedback',3000),int(data.get('id',0)),client_id))
                if not cursor.rowcount: return self.send(404,{'error':'Check-in not found.'})
                self.audit(db,user['id'],'checkin.review',client_id)
            elif path == '/api/messages':
                if not staff and not db.execute('SELECT 1 FROM assignments WHERE client_id=?',(client_id,)).fetchone():
                    raise ValueError('Your administrator needs to assign a coach before you can message them.')
                db.execute('INSERT INTO messages(client_id,sender_id,body,created) VALUES(?,?,?,?)',(client_id,user['id'],text(data.get('body'),'Message',3000),now()))
            elif path == '/api/plan':
                if not staff: return self.send(403,{'error':'Coach access required.'})
                kind=data.get('kind')
                if kind not in ('diet','workout'): raise ValueError('Invalid plan type.')
                plan=data.get('plan'); self.validate_plan(plan,kind)
                db.execute('BEGIN IMMEDIATE')
                version=db.execute('SELECT COALESCE(MAX(version),0)+1 FROM plans WHERE client_id=? AND kind=?',(client_id,kind)).fetchone()[0]
                db.execute('INSERT INTO plans(client_id,kind,version,data,author,created) VALUES(?,?,?,?,?,?)',(client_id,kind,version,encode(plan),user['id'],now()))
                self.audit(db,user['id'],f'plan.{kind}.v{version}',client_id)
            elif path == '/api/photos':
                view=data.get('view')
                if view not in ('front','side','back'): raise ValueError('Choose front, side or back.')
                try: content=base64.b64decode(data.get('content',''),validate=True)
                except Exception: raise ValueError('Invalid photo encoding.')
                if not 10 < len(content) <= 2_000_000: raise ValueError('Photo must be smaller than 2 MB.')
                if content.startswith(b'\x89PNG\r\n\x1a\n'): mime='image/png'
                elif content.startswith(b'\xff\xd8\xff'): mime='image/jpeg'
                else: raise ValueError('Choose a PNG or JPEG image.')
                db.execute('INSERT INTO photos(client_id,day,view,mime,content) VALUES(?,?,?,?,?)',(client_id,history_date(data.get('day',today())),view,mime,content))
            elif path == '/api/membership/pause':
                db.execute('BEGIN IMMEDIATE')
                member=self.membership(db,client_id)
                if not member or member['status']!='active': raise ValueError('An active membership is required.')
                days=number(data.get('days'),'Pause days',member['min_pause'],member['max_pause'],True)
                if days > member['pause_days']-member['used_pause']: raise ValueError('Not enough pause days remaining.')
                if db.execute("SELECT 1 FROM pauses WHERE client_id=? AND status='pending'",(client_id,)).fetchone(): raise ValueError('You already have a pending request.')
                db.execute('INSERT INTO pauses(client_id,days) VALUES(?,?)',(client_id,days))
            else:
                return self.send(404,{'error':'Not found.'})
            db.commit()
            return self.send(200,{'ok':True})
        except sqlite3.IntegrityError:
            db.rollback(); self.send(409,{'error':'That record already exists or references an invalid record.'})
        except (ValueError,TypeError,KeyError,OverflowError) as exc:
            db.rollback(); self.send(400,{'error':str(exc) if isinstance(exc,ValueError) else 'Invalid or missing input.'})
        except Exception:
            db.rollback(); self.send(500,{'error':'Something went wrong. Your change was not saved.'})
        finally:
            db.close()

    def audit(self,db,actor,action,target):
        db.execute('INSERT INTO audit(actor,action,target,created) VALUES(?,?,?,?)',(actor,action,target,now()))

    def create_user(self,db,data,role):
        name=text(data.get('name'),'Name',100)
        email=text(data.get('email'),'Email',254).lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email): raise ValueError('Enter a valid email address.')
        password=text(data.get('password'),'Password',128,12)
        cursor=db.execute('INSERT INTO users(name,email,password,role,created) VALUES(?,?,?,?,?)',(name,email,password_hash(password),role,now()))
        return cursor.lastrowid

    def authenticate(self,db,path,data):
        if path == '/api/login':
            email=text(data.get('email'),'Email',254).lower()
            password=text(data.get('password'),'Password',128)
            row=db.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
            valid=password_matches(password,row['password'] if row else password_hash('dummy-password', '0'*32))
            if not row or not valid: return self.send(401,{'error':'Email or password is incorrect.'})
            user_id=row['id']
        else:
            db.execute('BEGIN IMMEDIATE')
            exists=db.execute('SELECT 1 FROM users LIMIT 1').fetchone()
            if path == '/api/setup' and exists: return self.send(409,{'error':'Owner setup is already complete.'})
            if path == '/api/register' and not exists: return self.send(409,{'error':'The owner must complete setup first.'})
            if data.get('consent') is not True: raise ValueError('Please confirm the data-use notice.')
            user_id=self.create_user(db,data,'admin' if path=='/api/setup' else 'client')
            self.audit(db,user_id,'account.create.notice-v1',user_id)
        token=secrets.token_urlsafe(32)
        db.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
        db.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user_id,time.time()+86400))
        db.commit()
        cookie=f'shraz_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=86400'
        if self.server.secure_cookie: cookie+='; Secure'
        return self.send(200,{'ok':True},cookie=cookie)

    def membership(self,db,client_id):
        row=db.execute('SELECT m.*,p.name,p.months,p.price,p.pause_days,p.min_pause,p.max_pause FROM memberships m JOIN membership_plans p ON p.id=m.plan_id WHERE m.client_id=?',(client_id,)).fetchone()
        if not row: return None
        value=dict(row)
        value['status']='scheduled' if value['start']>today() else ('expired' if value['expiry']<today() else 'active')
        if value['status']=='active' and db.execute("SELECT 1 FROM pauses WHERE client_id=? AND status='approved' AND start<=? AND end>=?",(client_id,today(),today())).fetchone(): value['status']='paused'
        value['days_remaining']=max(0,(dt.date.fromisoformat(value['expiry'])-dt.date.today()).days)
        return value

    def workspace(self,db,client,day):
        cid=client['id']
        profile=db.execute('SELECT data FROM profiles WHERE user_id=?',(cid,)).fetchone()
        plans={}
        for kind in ('diet','workout'):
            row=db.execute('SELECT id,version,data,created FROM plans WHERE client_id=? AND kind=? ORDER BY id DESC LIMIT 1',(cid,kind)).fetchone()
            plans[kind]={**dict(row),'data':json.loads(row['data'])} if row else None
        coach=db.execute('SELECT u.id,u.name FROM assignments a JOIN users u ON u.id=a.coach_id WHERE a.client_id=?',(cid,)).fetchone()
        checkins=[{**dict(r),'data':json.loads(r['data'])} for r in db.execute('SELECT * FROM checkins WHERE client_id=? ORDER BY id DESC LIMIT 52',(cid,))]
        return {'client':dict(client),'profile':json.loads(profile['data']) if profile else {},'coach':dict(coach) if coach else None,'day':day,'plans':plans,
            'logs':[{**dict(r),'data':json.loads(r['data'])} for r in db.execute('SELECT day,kind,ref,data FROM logs WHERE client_id=? AND day=?',(cid,day))],
            'measurements':[dict(r) for r in db.execute('SELECT day,weight,waist FROM measurements WHERE client_id=? ORDER BY day DESC LIMIT 180',(cid,))][::-1],
            'checkins':checkins,'photos':[dict(r) for r in db.execute('SELECT id,day,view FROM photos WHERE client_id=? ORDER BY id DESC LIMIT 60',(cid,))],
            'messages':[dict(r) for r in db.execute('SELECT m.id,m.sender_id,m.body,m.created,u.name,u.role FROM messages m JOIN users u ON u.id=m.sender_id WHERE client_id=? ORDER BY m.id DESC LIMIT 100',(cid,))][::-1],
            'membership':self.membership(db,cid),'pauses':[dict(r) for r in db.execute('SELECT id,days,status,start,end FROM pauses WHERE client_id=? ORDER BY id DESC',(cid,))],
            'versions':[dict(r) for r in db.execute('SELECT id,kind,version,created,data FROM plans WHERE client_id=? ORDER BY id DESC LIMIT 30',(cid,))]}

    def validate_plan(self,plan,kind):
        if not isinstance(plan,dict): raise ValueError('Plan must be an object.')
        text(plan.get('title'),'Plan title',120)
        if kind=='diet':
            for k,maximum in [('calories',6000),('protein',400),('carbs',1000),('fat',300),('water',6000)]:
                number(plan.get(k),k,0,maximum)
        items=plan.get('items')
        if not isinstance(items,list) or not 1<=len(items)<=30: raise ValueError('Add 1–30 plan items.')
        ids=set()
        for item in items:
            if not isinstance(item,dict): raise ValueError('Invalid plan item.')
            ref=text(item.get('id'),'Item ID',80)
            if ref in ids: raise ValueError('Item IDs must be unique.')
            ids.add(ref); text(item.get('name'),'Item name',150)
            text(item.get('detail',''),'Instructions',2000,0)
            if kind=='diet':
                text(item.get('slot'),'Meal label',60)
                for k,maximum in [('calories',6000),('protein',400),('carbs',1000),('fat',300)]: number(item.get(k),k,0,maximum)
            else:
                number(item.get('sets'),'Sets',1,20,True); number(item.get('reps'),'Reps',1,100,True)
                number(item.get('rest'),'Rest seconds',0,600,True)

    def admin(self,db,user,path,data,post):
        if path=='/api/admin' and not post:
            users=[dict(r) for r in db.execute('SELECT u.id,u.name,u.email,u.role,a.coach_id FROM users u LEFT JOIN assignments a ON a.client_id=u.id ORDER BY u.id')]
            return self.send(200,{'users':users,'plans':[dict(r) for r in db.execute('SELECT * FROM membership_plans')],
                'memberships':[{**self.membership(db,r['id']),'client_name':r['name']} for r in users if r['role']=='client' and self.membership(db,r['id'])],
                'pauses':[dict(r) for r in db.execute("SELECT p.*,u.name FROM pauses p JOIN users u ON u.id=p.client_id WHERE p.status='pending'")],
                'pending_checkins':db.execute("SELECT COUNT(*) FROM checkins WHERE status='pending'").fetchone()[0],
                'audit':[dict(r) for r in db.execute('SELECT a.action,a.target,a.created,u.name FROM audit a LEFT JOIN users u ON u.id=a.actor ORDER BY a.id DESC LIMIT 30')]})
        if not post: return self.send(404,{'error':'Not found.'})
        target=None
        if path=='/api/admin/users':
            role=data.get('role')
            if role not in ('client','coach'): raise ValueError('Choose client or coach.')
            target=self.create_user(db,data,role)
        elif path=='/api/admin/assign':
            target=int(data.get('client_id',0)); coach=int(data.get('coach_id',0))
            if not db.execute("SELECT 1 FROM users WHERE id=? AND role='client'",(target,)).fetchone(): raise ValueError('Invalid client.')
            if not db.execute("SELECT 1 FROM users WHERE id=? AND role='coach'",(coach,)).fetchone(): raise ValueError('Invalid coach.')
            db.execute('INSERT INTO assignments VALUES(?,?) ON CONFLICT(client_id) DO UPDATE SET coach_id=excluded.coach_id',(target,coach))
        elif path=='/api/admin/plans':
            values=(text(data.get('name'),'Plan name',100),number(data.get('months'),'Months',1,36,True),number(data.get('price'),'Price',0,1000000),number(data.get('pause_days'),'Pause allowance',0,365,True),number(data.get('min_pause'),'Minimum pause',1,90,True),number(data.get('max_pause'),'Maximum pause',1,90,True))
            if values[4]>values[5]: raise ValueError('Minimum pause cannot exceed maximum.')
            db.execute('INSERT INTO membership_plans(name,months,price,pause_days,min_pause,max_pause) VALUES(?,?,?,?,?,?)',values)
        elif path=='/api/admin/membership':
            target=int(data.get('client_id',0)); plan_id=int(data.get('plan_id',0)); start=date_value(data.get('start',today()))
            if not db.execute("SELECT 1 FROM users WHERE id=? AND role='client'",(target,)).fetchone(): raise ValueError('Invalid client.')
            plan=db.execute('SELECT * FROM membership_plans WHERE id=?',(plan_id,)).fetchone()
            if not plan: raise ValueError('Membership plan not found.')
            previous=self.membership(db,target)
            if previous and previous['status']!='expired': raise ValueError('An unexpired membership already exists. Renew after expiry in this release.')
            start_date=dt.date.fromisoformat(start); month=start_date.month-1+plan['months']; year=start_date.year+month//12; month=month%12+1
            expiry=(dt.date(year,month,min(start_date.day,calendar.monthrange(year,month)[1]))-dt.timedelta(days=1)).isoformat()
            db.execute('INSERT INTO memberships(client_id,plan_id,start,expiry) VALUES(?,?,?,?) ON CONFLICT(client_id) DO UPDATE SET plan_id=excluded.plan_id,start=excluded.start,expiry=excluded.expiry,used_pause=0',(target,plan_id,start,expiry))
            db.execute("UPDATE pauses SET status='archived' WHERE client_id=?",(target,))
        elif path=='/api/admin/pause':
            db.execute('BEGIN IMMEDIATE')
            pause=db.execute("SELECT * FROM pauses WHERE id=? AND status='pending'",(int(data.get('id',0)),)).fetchone()
            if not pause: raise ValueError('Pending request not found.')
            target=pause['client_id']; approve=data.get('approve')
            if not isinstance(approve,bool): raise ValueError('Approval must be true or false.')
            if approve:
                member=self.membership(db,target)
                if not member or member['status']!='active' or pause['days']>member['pause_days']-member['used_pause']: raise ValueError('Membership is no longer eligible for this pause.')
                end=(dt.date.today()+dt.timedelta(days=pause['days']-1)).isoformat()
                expiry=(dt.date.fromisoformat(member['expiry'])+dt.timedelta(days=pause['days'])).isoformat()
                db.execute('UPDATE memberships SET used_pause=used_pause+?,expiry=? WHERE client_id=?',(pause['days'],expiry,target))
                db.execute("UPDATE pauses SET status='approved',start=?,end=? WHERE id=?",(today(),end,pause['id']))
            else: db.execute("UPDATE pauses SET status='rejected' WHERE id=?",(pause['id'],))
        else: return self.send(404,{'error':'Not found.'})
        self.audit(db,user['id'],path.removeprefix('/api/'),target); db.commit()
        return self.send(200,{'ok':True,'id':target})

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8080)
    parser.add_argument('--db',default=str(ROOT/'shraz.sqlite3'))
    parser.add_argument('--secure-cookie',action='store_true',help='Required behind production HTTPS.')
    args=parser.parse_args()
    server=AppServer((args.host,args.port),args.db,args.secure_cookie)
    print(f'Shraz is ready at http://{args.host}:{args.port}. Press Ctrl+C to stop.',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
