"""HTTP integration tests against isolated temporary databases."""
import base64
import datetime as dt
import http.cookiejar
import json
import secrets
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from server import AppServer, today

class Browser:
    def __init__(self, base):
        self.base=base
        self.cookies=http.cookiejar.CookieJar()
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
    def call(self,path,data=None,headers=None):
        headers={'Content-Type':'application/json',**(headers or {})}
        request=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        try: response=self.opener.open(request)
        except urllib.error.HTTPError as error: response=error
        raw=response.read()
        body=json.loads(raw) if response.headers.get_content_type()=='application/json' else raw
        return response.status,body,response.headers

def diet():
    return {'title':'Test nutrition','calories':2000,'protein':130,'carbs':230,'fat':60,'water':2500,'items':[{'id':'meal-1','name':'Test meal','slot':'Lunch','calories':650,'protein':40,'carbs':75,'fat':20,'detail':'Test instructions.'}]}

def workout():
    return {'title':'Test training','items':[{'id':'exercise-1','name':'Squat','sets':3,'reps':10,'rest':90,'detail':'Test instructions.'}]}

class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.server=AppServer(('127.0.0.1',0),Path(cls.temp.name)/'test.sqlite3')
        cls.thread=threading.Thread(target=cls.server.serve_forever)
        cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
        cls.password=secrets.token_urlsafe(24)
        cls.admin=Browser(cls.base)
        status,_,_=cls.admin.call('/api/setup',{'name':'Test Admin','email':'admin@example.test','password':cls.password,'consent':True})
        assert status==200
        cls.coach=Browser(cls.base);cls.other_coach=Browser(cls.base)
        for email,name in [('coach@example.test','Test Coach'),('othercoach@example.test','Other Coach')]:
            status,body,_=cls.admin.call('/api/admin/users',{'name':name,'email':email,'password':cls.password,'role':'coach'})
            assert status==200
            if email.startswith('coach@'):cls.coach_id=body['id']
        cls.coach.call('/api/login',{'email':'coach@example.test','password':cls.password})
        cls.other_coach.call('/api/login',{'email':'othercoach@example.test','password':cls.password})
        cls.client=Browser(cls.base);cls.other=Browser(cls.base)
        for browser,email,name in [(cls.client,'client@example.test','Test Client'),(cls.other,'other@example.test','Other Client')]:
            status,_,_=browser.call('/api/register',{'name':name,'email':email,'password':cls.password,'consent':True,'role':'admin'})
            assert status==200
        cls.client_id=cls.client.call('/api/session')[1]['user']['id']
        cls.other_id=cls.other.call('/api/session')[1]['user']['id']
        cls.admin.call('/api/admin/assign',{'client_id':cls.client_id,'coach_id':cls.coach_id})
        for kind,plan in [('diet',diet()),('workout',workout())]:
            status,_,_=cls.coach.call('/api/plan',{'client_id':cls.client_id,'kind':kind,'plan':plan})
            assert status==200

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.temp.cleanup()

    def test_01_owner_setup_is_one_time_and_signup_cannot_escalate(self):
        self.assertEqual(self.admin.call('/api/setup',{})[0],409)
        self.assertEqual(self.client.call('/api/session')[1]['user']['role'],'client')
        self.assertEqual(self.client.call('/api/admin')[0],403)
        self.assertEqual(self.coach.call('/api/admin/users',{})[0],403)

    def test_02_client_and_coach_isolation(self):
        self.assertEqual(self.client.call(f'/api/workspace?client={self.other_id}')[0],403)
        self.assertEqual(self.other.call(f'/api/workspace?client={self.client_id}')[0],403)
        self.assertEqual(self.other_coach.call(f'/api/workspace?client={self.client_id}')[0],403)
        self.assertEqual(self.coach.call(f'/api/workspace?client={self.client_id}')[0],200)
        self.assertEqual(self.coach.call(f'/api/workspace?client={self.other_id}')[0],403)
        self.assertEqual(self.client.call('/api/profile',{'client_id':self.other_id})[0],403)
        self.assertEqual(self.coach.call('/api/logs',{'client_id':self.client_id})[0],403)
        self.assertEqual(self.other_coach.call('/api/messages',{'client_id':self.client_id,'body':'forbidden'})[0],403)

    def test_03_persistent_logs_profile_and_validation(self):
        profile={'goal':'Fat loss','diet':'Vegetarian','height':175,'age':30,'allergies':'Nuts','activity':'Moderately active'}
        self.assertEqual(self.client.call('/api/profile',profile)[0],200)
        for kind,ref,value in [('meal','meal-1',True),('workout','exercise-1',True),('water','today',750),('exercise','exercise-1',{'sets':3,'reps':10,'weight':20})]:
            self.assertEqual(self.client.call('/api/logs',{'kind':kind,'ref':ref,'value':value})[0],200)
        self.assertEqual(self.client.call('/api/logs',{'kind':'water','value':-1})[0],400)
        self.assertEqual(self.client.call('/api/logs',{'kind':'meal','ref':'unknown','value':True})[0],400)
        self.assertEqual(self.client.call('/api/logs',{'kind':'meal','ref':'meal-1','value':'yes'})[0],400)
        self.assertEqual(self.client.call('/api/logs',{'kind':'exercise','ref':'unknown','value':{'sets':1,'reps':1,'weight':1}})[0],400)
        tomorrow=(dt.date.today()+dt.timedelta(days=1)).isoformat()
        self.assertEqual(self.client.call('/api/progress',{'day':tomorrow,'weight':80})[0],400)
        self.assertEqual(self.client.call('/api/progress',{'weight':80,'waist':85})[0],200)
        self.assertEqual(self.client.call('/api/progress',{'weight':79.9,'waist':84.5})[0],200)
        reopened=Browser(self.base)
        self.assertEqual(reopened.call('/api/login',{'email':'client@example.test','password':self.password})[0],200)
        ws=reopened.call('/api/workspace')[1]
        self.assertEqual(ws['profile']['allergies'],'Nuts')
        self.assertEqual(len(ws['logs']),4)
        self.assertEqual(len(ws['measurements']),1)
        self.assertEqual(ws['measurements'][0]['weight'],79.9)
        with self.server.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM logs WHERE client_id=?',(self.client_id,)).fetchone()[0],4)

    def test_04_plan_version_history_and_permissions(self):
        self.assertEqual(self.client.call('/api/plan',{'kind':'diet','plan':diet()})[0],403)
        plan=diet();plan['title']='Revised nutrition'
        self.assertEqual(self.coach.call('/api/plan',{'client_id':self.client_id,'kind':'diet','plan':plan})[0],200)
        ws=self.client.call('/api/workspace')[1]
        self.assertEqual(ws['plans']['diet']['version'],2)
        self.assertEqual(ws['plans']['diet']['data']['title'],'Revised nutrition')
        self.assertEqual(len([p for p in ws['versions'] if p['kind']=='diet']),2)
        plan['items'].append(plan['items'][0].copy())
        self.assertEqual(self.coach.call('/api/plan',{'client_id':self.client_id,'kind':'diet','plan':plan})[0],400)
        self.assertEqual(self.client.call('/api/workspace')[1]['plans']['diet']['version'],2)

    def test_05_checkin_review_and_chat(self):
        checkin={'energy':7,'sleep':8,'hunger':4,'adherence':9,'notes':'Test check-in'}
        self.assertEqual(self.client.call('/api/checkins',checkin)[0],200)
        self.assertEqual(self.client.call('/api/checkins',checkin)[0],400)
        cid=self.client.call('/api/workspace')[1]['checkins'][0]['id']
        review={'client_id':self.client_id,'id':cid,'status':'reviewed','feedback':'Great consistency this week.'}
        self.assertEqual(self.client.call('/api/checkins/review',review)[0],403)
        self.assertEqual(self.other_coach.call('/api/checkins/review',review)[0],403)
        self.assertEqual(self.coach.call('/api/checkins/review',review)[0],200)
        self.assertEqual(self.client.call('/api/workspace')[1]['checkins'][0]['status'],'reviewed')
        self.assertEqual(self.client.call('/api/messages',{'body':'Can we discuss a meal swap?'})[0],200)
        self.assertEqual(self.coach.call('/api/messages',{'client_id':self.client_id,'body':'Yes, let’s review your plan.'})[0],200)
        self.assertEqual(len(self.client.call('/api/workspace')[1]['messages']),2)

    def test_06_private_photos(self):
        png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6mX8AAAAASUVORK5CYII=')
        self.assertEqual(self.client.call('/api/photos',{'view':'front','content':base64.b64encode(png).decode()})[0],200)
        photo_id=self.client.call('/api/workspace')[1]['photos'][0]['id']
        route=f'/api/photo/{photo_id}?client={self.client_id}'
        status,body,headers=self.client.call(route)
        self.assertEqual(status,200);self.assertEqual(body,png);self.assertEqual(headers['Cache-Control'],'no-store')
        self.assertEqual(Browser(self.base).call(route)[0],401)
        self.assertEqual(self.other.call(route)[0],403)
        self.assertEqual(self.other.call(f'/api/photo/{photo_id}')[0],404)
        self.assertEqual(self.other_coach.call(route)[0],403)
        self.assertEqual(self.coach.call(route)[0],200)
        self.assertEqual(self.client.call('/api/photos',{'view':'front','content':base64.b64encode(b'<svg>not allowed</svg>').decode()})[0],400)

    def test_07_membership_pause_transaction_and_limits(self):
        plan={'name':'Three month','months':3,'price':12000,'pause_days':17,'min_pause':2,'max_pause':10}
        self.assertEqual(self.admin.call('/api/admin/plans',plan)[0],200)
        plan_id=self.admin.call('/api/admin')[1]['plans'][0]['id']
        self.assertEqual(self.admin.call('/api/admin/membership',{'client_id':self.client_id,'plan_id':plan_id,'start':today()})[0],200)
        original=self.client.call('/api/workspace')[1]['membership']
        self.assertEqual(original['status'],'active')
        self.assertEqual(self.client.call('/api/membership/pause',{'days':1})[0],400)
        self.assertEqual(self.client.call('/api/membership/pause',{'days':11})[0],400)
        self.assertEqual(self.client.call('/api/membership/pause',{'days':5})[0],200)
        self.assertEqual(self.client.call('/api/membership/pause',{'days':5})[0],400)
        pause=self.admin.call('/api/admin')[1]['pauses'][0]
        self.assertEqual(self.coach.call('/api/admin/pause',{'id':pause['id'],'approve':True})[0],403)
        self.assertEqual(self.admin.call('/api/admin/pause',{'id':pause['id'],'approve':True})[0],200)
        self.assertEqual(self.admin.call('/api/admin/pause',{'id':pause['id'],'approve':True})[0],400)
        updated=self.client.call('/api/workspace')[1]['membership']
        self.assertEqual(updated['used_pause'],5)
        self.assertEqual(updated['status'],'paused')
        self.assertEqual((dt.date.fromisoformat(updated['expiry'])-dt.date.fromisoformat(original['expiry'])).days,5)
        self.assertEqual(self.client.call('/api/membership/pause',{'days':2})[0],400)
        self.assertEqual(self.admin.call('/api/admin/membership',{'client_id':self.client_id,'plan_id':plan_id,'start':today()})[0],400)

    def test_08_security_headers_csrf_logout(self):
        self.assertEqual(self.client.call('/api/messages',{'body':'no'},headers={'Origin':'https://untrusted.invalid'})[0],403)
        self.assertEqual(self.client.call('/api/messages',{'body':'no'},headers={'Content-Type':'text/plain'})[0],415)
        self.assertEqual(Browser(self.base).call('/api/workspace')[0],401)
        temp=Browser(self.base);temp.call('/api/login',{'email':'client@example.test','password':self.password})
        response=temp.call('/api/session')
        self.assertEqual(response[2]['X-Content-Type-Options'],'nosniff')
        self.assertIn("frame-ancestors 'none'",response[2]['Content-Security-Policy'])
        self.assertEqual(temp.call('/api/logout',{})[0],200)
        self.assertEqual(temp.call('/api/workspace')[0],401)
        self.assertEqual(temp.call('/server.py')[0],404)
        self.assertEqual(temp.call('/shraz.sqlite3')[0],404)

if __name__=='__main__':
    unittest.main(verbosity=2)
