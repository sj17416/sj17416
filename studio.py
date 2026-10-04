"""BlogFlow 3: local browser app, authenticated loopback API, desktop launcher."""
import base64
import ctypes
from ctypes import wintypes
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import webbrowser
import blogger_auto as engine
import research
import writer
import deep_writer
import autopilot
import naver_handoff

ASSETS=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
ROOT=Path(os.environ.get('BLOGFLOW_DATA_DIR', str(Path(sys.executable).resolve().parent/'BlogFlow-data' if getattr(sys,'frozen',False) else Path(__file__).resolve().parent/'BlogFlow-data')))
ROOT.mkdir(exist_ok=True)
engine.ROOT=ROOT
TOKEN=secrets.token_urlsafe(32)
DATA_LOCK=threading.RLock()
JOBS={}
LAST_HEARTBEAT=time.monotonic()
BUSY=0
PUBLISH_LOCK=threading.Lock()
OAUTH_LOCK=threading.Lock()
SERVER=None


class Blob(ctypes.Structure):
    _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]


def crypt(raw, decrypt=False):
    if os.name!='nt':raise ValueError('API 키 저장은 Windows에서 지원합니다.')
    buffer=ctypes.create_string_buffer(raw)
    source=Blob(len(raw),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));target=Blob()
    crypt32=ctypes.windll.crypt32;kernel32=ctypes.windll.kernel32
    crypt32.CryptProtectData.argtypes=[ctypes.POINTER(Blob),wintypes.LPCWSTR,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    crypt32.CryptUnprotectData.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    kernel32.LocalFree.argtypes=[ctypes.c_void_p];kernel32.LocalFree.restype=ctypes.c_void_p
    if decrypt:
        ok=crypt32.CryptUnprotectData(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target))
    else:
        ok=crypt32.CryptProtectData(ctypes.byref(source),'BlogFlow API settings',None,None,None,1,ctypes.byref(target))
    if not ok:raise ValueError('Windows 계정으로 API 연결 정보를 저장하거나 읽지 못했습니다.')
    try:return ctypes.string_at(target.pbData,target.cbData)
    finally:kernel32.LocalFree(target.pbData)


def get_keys():
    path=ROOT/'connections.sec'
    return json.loads(crypt(path.read_bytes(),True)) if path.exists() else {}


def save_keys(updates):
    allowed=['naver_ad_key','naver_ad_secret','naver_customer','naver_client','naver_secret','openai_key','openai_model','threads_token','facebook_token','facebook_page','facebook_version','x_token','telegram_token','telegram_chat']
    with DATA_LOCK:
        keys=get_keys()
        for key in allowed:
            if updates.get(key):keys[key]=str(updates[key]).strip()
        path=ROOT/'connections.sec';tmp=ROOT/'connections.tmp'
        tmp.write_bytes(crypt(json.dumps(keys).encode()));tmp.replace(path)
    return connections()


def connections():
    keys=get_keys()
    return {'naver_ad':all(keys.get(k) for k in ['naver_ad_key','naver_ad_secret','naver_customer']),
        'naver_trend':bool(keys.get('naver_client') and keys.get('naver_secret')),'openai':bool(keys.get('openai_key')),
        'openai_model':keys.get('openai_model','gpt-4.1-mini'),'google':(ROOT/'credentials.json').exists(),'threads':bool(keys.get('threads_token')),'facebook':bool(keys.get('facebook_token') and keys.get('facebook_page')),'x':bool(keys.get('x_token')),'telegram':bool(keys.get('telegram_token') and keys.get('telegram_chat'))}


def read_store(name,default):
    path=ROOT/name
    return engine.read_json(path) if path.exists() else default


def write_store(name,data):
    with DATA_LOCK:engine.save_json(ROOT/name,data)


def task(work):
    global BUSY
    with DATA_LOCK:
        if BUSY>=4:raise ValueError('진행 중인 작업을 기다린 뒤 다시 시도하세요.')
        ident=secrets.token_hex(10);JOBS[ident]={'status':'running'};BUSY+=1
        # Keep completed jobs bounded.
        if len(JOBS)>80:
            for old in list(JOBS):
                if old!=ident and JOBS[old]['status']!='running':del JOBS[old]
                if len(JOBS)<=60:break
    def run():
        global BUSY
        try:
            result=work()
            with DATA_LOCK:JOBS[ident]={'status':'done','result':result}
        except Exception as exc:
            message=str(exc)
            try:
                for value in get_keys().values():
                    if isinstance(value,str) and len(value)>8:message=message.replace(value,'[비공개]')
            except Exception:pass
            with DATA_LOCK:JOBS[ident]={'status':'error','error':message[:1200]}
        finally:
            with DATA_LOCK:BUSY-=1
    threading.Thread(target=run,daemon=True).start()
    return {'job':ident}


def state():
    stored=read_store('studio-state.json',{})
    if not stored:
        previous=read_store('settings.json',{})
        keyword=previous.get('keyword','에너지바우처')
        doc=writer.offline_article(keyword,previous.get('style','공감형'))
        stored={'doc':doc,'design':{'color':'#2f6fed','font':17,'radius':16,'toc':True,'ad_TOP':True,'ad_MID':True,'ad_BOTTOM':True,'cta':'공식 안내에서 조건 확인하기'},'ads':previous.get('ads',{}),'style':'공감형','month':datetime.now(research.KST).strftime('%Y-%m'),'sequence':0}
    return {'state':stored,'connections':connections(),'month':datetime.now(research.KST).strftime('%Y-%m')}


def publish(payload):
    doc=payload['doc'];writer.validate(doc)
    blog=str(payload.get('blog',''))
    if not blog.isdigit():raise ValueError('Google 연결 후 블로그를 선택하세요.')
    mode=payload.get('mode','draft')
    if mode not in ['draft','publish','schedule']:raise ValueError('발행 방식을 확인하세요.')
    content=writer.render(doc,payload.get('design'),payload.get('ads'),False)
    item={'id':'studio-post','title':doc['title'],'content_file':'article.html','labels':[doc['keyword']],'mode':mode}
    if mode=='schedule':
        date=datetime.fromisoformat(payload['date']).replace(tzinfo=research.KST)
        if date<=datetime.now(timezone.utc):raise ValueError('예약 시간은 미래의 한국 시간으로 입력하세요.')
        item['publish_at']=date.isoformat()
    fingerprint=hashlib.sha256((blog+json.dumps(item,sort_keys=True,ensure_ascii=False)+content).encode()).hexdigest()[:24]
    if not PUBLISH_LOCK.acquire(blocking=False):raise ValueError('다른 발행 작업이 진행 중입니다.')
    lock=ROOT/'.run.lock'
    owned=False
    try:
        try:
            with lock.open('x'):pass
            owned=True
        except FileExistsError:raise ValueError('다른 발행 작업 또는 이전 종료 기록이 있습니다. 실행 중인 앱을 확인하세요.')
        folder=ROOT/'jobs'/fingerprint
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'article.html').write_text(content,encoding='utf-8')
        engine.save_json(folder/'posts.json',[item])
        engine.save_json(folder/'article.json',doc)
        (folder/'검색설명.txt').write_text(doc.get('description',''),encoding='utf-8')
        with OAUTH_LOCK:api=engine.service()
        engine.run(api,blog,engine.load_posts(folder/'posts.json'),folder/'state.json')
        entry=engine.read_json(folder/'state.json')[blog+':studio-post']
        return {'id':entry['post_id'],'mode':mode,'note':'Blogger에서 확인하세요. 검색 설명은 편집 화면에 별도로 붙여 넣으세요.'}
    finally:
        if owned:lock.unlink(missing_ok=True)
        PUBLISH_LOCK.release()


def action(name,payload):
    if name=='automation-state':return {'config':read_store('automation.json',{}),'queue':read_store('queue.json',[]),'last':read_store('automation-last.json',{})}
    if name=='automation-save':
        cfg=autopilot.config(payload)
        if cfg.get('enabled') and not get_keys().get('openai_key'):raise ValueError('심층 작성 API 키를 먼저 연결하세요.')
        if cfg.get('enabled') and cfg.get('auto_publish'):
            if not (ROOT/'token.json').exists():raise ValueError('Google 연결을 먼저 완료하세요.')
            import channels
            for channel in cfg['channels']:
                if channel!='blogger':channels.check(channel,get_keys())
        if cfg.get('telegram') and not connections()['telegram']:raise ValueError('텔레그램 봇 토큰과 채팅 ID를 연결 설정에서 먼저 저장하세요.')
        previous=read_store('automation.json',{})
        write_store('automation.json',cfg)
        if cfg.get('enabled') and not previous.get('enabled'):
            # Turning automation on starts the first run within a minute.
            last=read_store('automation-last.json',{});last.pop('next_run',None);write_store('automation-last.json',last)
        return {'saved':True}
    if name=='telegram-test':
        import channels
        return channels.telegram('🔔 BlogFlow 텔레그램 알림 테스트입니다. 글이 발행되면 여기로 알려 드릴게요.',get_keys())
    if name=='automation-prepare':return task(lambda:autopilot.prepare(sys.modules[__name__]))
    if name=='automation-deliver':return task(lambda:autopilot.deliver(sys.modules[__name__],payload['id']))
    if name=='automation-edit':
        writer.validate(payload['doc']);queue=read_store('queue.json',[])
        entry=next(x for x in queue if x['id']==payload['id'])
        if entry['delivery'] or entry['status'] not in ['ready','review','approved']:raise ValueError('게시 전 대기 글만 수정할 수 있습니다.')
        entry['doc']=payload['doc'];entry['quality']=deep_writer.quality(payload['doc']);entry['status']='review'
        write_store('queue.json',queue);return {'saved':True}
    if name=='automation-approve':
        queue=read_store('queue.json',[])
        entry=next(x for x in queue if x['id']==payload['id'])
        if not entry.get('doc') or entry['status'] not in ['ready','review']:raise ValueError('검토할 초안이 없습니다.')
        entry['status']='approved';write_store('queue.json',queue);return {'approved':True}
    if name=='automation-reconcile':
        queue=read_store('queue.json',[]);entry=next(x for x in queue if x['id']==payload['id']);channel=payload['channel']
        if channel not in entry['channels'] or not re.fullmatch(r'[0-9_]+',str(payload['post_id'])):raise ValueError('직접 확인한 게시 ID를 입력하세요.')
        entry['delivery'][channel]={'status':'done','id':str(payload['post_id'])};entry['status']='partial'
        if channel=='blogger':autopilot.ensure_url(sys.modules[__name__],entry)
        write_store('queue.json',queue);return {'saved':True}
    if name=='state':return state()
    if name=='save':
        writer.validate(payload['doc']);write_store('studio-state.json',payload);return {'saved':True}
    if name=='connections':return save_keys(payload)
    if name=='clear-connections':
        (ROOT/'connections.sec').unlink(missing_ok=True);return connections()
    if name=='render':return {'html':writer.render(payload['doc'],payload.get('design'),payload.get('ads'),True)}
    if name=='research':
        return task(lambda: research.monthly_research(payload['month'],get_keys(),read_store('metrics.json',{}),payload.get('sort','volume'),payload.get('seeds')))
    if name=='related':return task(lambda:research.related_keywords(payload['keyword'],get_keys(),read_store('metrics.json',{}),payload['month']))
    if name=='metrics':
        imported=research.import_metrics(payload['csv'])
        existing=read_store('metrics.json',{});existing.update(imported);write_store('metrics.json',existing)
        return {'count':len(imported)}
    if name=='generate':
        keyword=str(payload['keyword']).strip()
        if not keyword or len(keyword)>120:raise ValueError('키워드를 1~120자로 입력하세요.')
        style=payload.get('style','공감형')
        if style not in content_styles():raise ValueError('말투를 선택하세요.')
        def generate():
            if payload.get('ai'):
                return deep_writer.deep_article(keyword,style,int(payload.get('sequence',0)),str(payload.get('notes','')),payload.get('related',[]),get_keys())
            return writer.offline_article(keyword,style,int(payload.get('sequence',0)),str(payload.get('notes','')))
        return task(generate)
    if name=='google-credentials':
        data=json.loads(payload['json'])
        if 'installed' not in data:raise ValueError('데스크톱 앱 OAuth JSON을 선택하세요.')
        if (ROOT/'token.json').exists():raise ValueError('이미 계정이 연결되어 있습니다. Google 연결 초기화 후 새 파일을 선택하세요.')
        write_store('credentials.json',data);return connections()
    if name=='google-reset':
        if BUSY:raise ValueError('진행 중인 작업이 끝난 뒤 초기화하세요.')
        (ROOT/'token.json').unlink(missing_ok=True)
        return {'reset':True}
    if name=='blogs':
        def blogs():
            with OAUTH_LOCK:api=engine.service()
            return api.blogs().listByUser(userId='self').execute(num_retries=2).get('items',[])
        return task(blogs)
    if name=='publish':return task(lambda:publish(payload))
    if name=='favorite':
        writer.validate(payload['doc']);folder=ROOT/'favorites';folder.mkdir(exist_ok=True)
        ident=datetime.now(research.KST).strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3)
        engine.save_json(folder/(ident+'.json'),payload)
        (folder/(ident+'.html')).write_text(writer.render(payload['doc'],payload.get('design'),payload.get('ads')),encoding='utf-8')
        return {'id':ident}
    if name=='favorites':
        folder=ROOT/'favorites'
        result=[]
        if folder.exists():
            for path in sorted(folder.glob('*.json'),reverse=True)[:80]:
                data=engine.read_json(path)
                if 'doc' in data:result.append({'id':path.stem,'title':data['doc']['title']})
        return result
    if name=='load-favorite':
        ident=str(payload['id'])
        if not re.fullmatch(r'[\w-]+',ident):raise ValueError('저장 글을 선택하세요.')
        return engine.read_json(ROOT/'favorites'/(ident+'.json'))
    if name=='naver-package':return naver_handoff.package(payload['doc'])
    if name=='export':
        writer.validate(payload['doc'])
        return {'html':writer.render(payload['doc'],payload.get('design'),payload.get('ads')), 'json':json.dumps(payload,ensure_ascii=False,indent=2)}
    if name=='shutdown':
        if BUSY or autopilot.LOCK.locked():raise ValueError('진행 중인 작업을 완료한 후 종료하세요.')
        threading.Thread(target=SERVER.shutdown,daemon=True).start();return {'closed':True}
    raise ValueError('지원하지 않는 작업입니다.')


def content_styles():return ['공감형','체크리스트형','비교·분석형']


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass

    def send(self,status,body,kind='application/json; charset=utf-8'):
        data=body.encode('utf-8') if isinstance(body,str) else body
        self.send_response(status)
        self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.end_headers();self.wfile.write(data)

    def json(self,data,status=200):self.send(status,json.dumps(data,ensure_ascii=False))

    def host_valid(self):
        return self.headers.get('Host')==f'127.0.0.1:{SERVER.server_port}'

    def do_GET(self):
        if not self.host_valid():return self.json({'error':'로컬 주소로 접근하세요.'},403)
        parsed=urlparse(self.path)
        if parsed.path=='/logo.png':return self.send(200,(ASSETS/'logo.png').read_bytes(),'image/png')
        supplied=parse_qs(parsed.query).get('token',[''])[0]
        if parsed.path=='/' and secrets.compare_digest(supplied,TOKEN):
            page=(ASSETS/'web'/'index.html').read_text(encoding='utf-8')
            return self.send(200,page.replace('__TOKEN__',TOKEN),'text/html; charset=utf-8')
        self.json({'error':'앱 실행 파일을 통해 열어주세요.'},403)

    def do_POST(self):
        global LAST_HEARTBEAT
        if not self.host_valid() or not secrets.compare_digest(self.headers.get('X-BlogFlow-Token',''),TOKEN):return self.json({'error':'접근 권한이 없습니다.'},403)
        origin=self.headers.get('Origin')
        if origin and origin!=f'http://127.0.0.1:{SERVER.server_port}':return self.json({'error':'허용되지 않은 요청입니다.'},403)
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.json({'error':'JSON 요청이 필요합니다.'},400)
        try:
            size=int(self.headers.get('Content-Length',0))
            if not 0<size<=3_000_000:raise ValueError('요청 크기를 확인하세요.')
            payload=json.loads(self.rfile.read(size))
            LAST_HEARTBEAT=time.monotonic()
            name=urlparse(self.path).path.removeprefix('/api/')
            if name=='ping':return self.json({'ok':True})
            if name=='job':
                with DATA_LOCK:result=JOBS.get(payload.get('job'),{'status':'error','error':'작업을 찾지 못했습니다.'})
                return self.json(result)
            result=action(name,payload)
            self.json(result)
        except Exception as exc:
            message=str(exc)
            try:
                for value in get_keys().values():
                    if len(str(value))>8:message=message.replace(str(value),'[비공개]')
            except Exception:pass
            self.json({'error':message[:1200]},400)


def open_app(url):
    # Edge app mode provides a desktop-like window with a modern HTML renderer.
    paths=[Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',
           Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Microsoft/Edge/Application/msedge.exe']
    for path in paths:
        if path.exists():
            subprocess.Popen([str(path),'--app='+url,'--new-window'],creationflags=0x08000000)
            return
    webbrowser.open(url)


def main():
    global SERVER, INSTANCE_MUTEX
    if os.name=='nt':
        kernel=ctypes.windll.kernel32
        kernel.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR]
        kernel.CreateMutexW.restype=wintypes.HANDLE
        name='Local\\BlogFlow-'+hashlib.sha256(str(ROOT.resolve()).casefold().encode()).hexdigest()[:24]
        INSTANCE_MUTEX=kernel.CreateMutexW(None,False,name)
        if kernel.GetLastError()==183:
            if '--self-test' not in sys.argv and '--serve-test' not in sys.argv and '--background' not in sys.argv:
                # Running in the background (e.g. started with Windows): reopen its window.
                try:open_app(json.loads((ROOT/'.server.json').read_text(encoding='utf-8'))['url'])
                except Exception:ctypes.windll.user32.MessageBoxW(None,'BlogFlow가 이미 실행 중입니다. 열려 있는 앱 창을 사용하세요.','BlogFlow',0)
            return
    if sys.stdout is None:
        sys.stdout=open(ROOT/'app.log','a',encoding='utf-8');sys.stderr=sys.stdout
    SERVER=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    SERVER.daemon_threads=True
    url=f'http://127.0.0.1:{SERVER.server_port}/?token={TOKEN}'
    if '--self-test' in sys.argv:
        raw=crypt(b'{"test":true}');assert crypt(raw,True)==b'{"test":true}'
        doc=writer.offline_article('청년월세 지원','공감형')
        html=writer.render(doc,preview=True);assert html.count('data-ad-position=')==3
        assert not any(x in html for x in ['[문제]','PASONA','문제 → 공감'])
        from googleapiclient.discovery import build
        build('blogger','v3',developerKey='test',static_discovery=True)
        (ROOT/'self-test-v3.json').write_text(json.dumps({'ok':True,'natural_writing':True,'preview':True,'encryption':True}),encoding='utf-8')
        SERVER.server_close();return
    if '--serve-test' in sys.argv:
        (ROOT/'test-server.json').write_text(json.dumps({'url':url,'token':TOKEN,'port':SERVER.server_port}),encoding='utf-8')
    else:
        (ROOT/'.server.json').write_text(json.dumps({'url':url}),encoding='utf-8')
        if '--background' not in sys.argv:open_app(url)
    def scheduler():
        while True:
            time.sleep(30)
            if BUSY==0:
                try:autopilot.tick(sys.modules[__name__])
                except Exception:pass
    if '--serve-test' not in sys.argv:threading.Thread(target=scheduler,daemon=True).start()
    def watcher():
        while True:
            time.sleep(15)
            if time.monotonic()-LAST_HEARTBEAT>180 and BUSY==0 and not read_store('automation.json',{}).get('enabled'):
                SERVER.shutdown();return
    threading.Thread(target=watcher,daemon=True).start()
    SERVER.serve_forever(poll_interval=.3)
    SERVER.server_close()


if __name__=='__main__':main()
