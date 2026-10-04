"""Local recurring workflow, durable queue and per-channel delivery state.

Order of work: this month's measured top-N keywords (by search volume),
then related keywords of what was already covered, one run every
interval_min~interval_max hours while the app is running."""
import hashlib
import random
import threading
from datetime import datetime,timedelta
import research,deep_writer,channels,naver_handoff
LOCK=threading.Lock()
MAX_EXPANSIONS=8

def config(value):
    value=dict(value)
    value['hour']=max(0,min(23,int(value.get('hour',9))))
    value['count']=max(1,min(3,int(value.get('count',1))))
    value['min_volume']=max(0,int(value.get('min_volume',1000)))
    value['top_n']=max(1,min(50,int(value.get('top_n',50))))
    low=max(1.0,min(24.0,float(value.get('interval_min',1))));high=max(low,min(24.0,float(value.get('interval_max',3))))
    value['interval_min'],value['interval_max']=low,high
    value['related']=bool(value.get('related',True))
    value['telegram']=bool(value.get('telegram',False))
    value['channels']=[c for c in value.get('channels',[]) if c in ['blogger','threads','facebook','x']]
    if not value['channels']:raise ValueError('게시 채널을 선택하세요.')
    if not str(value.get('blog','')).isdigit():raise ValueError('Blogger 블로그 ID를 입력하세요. SNS 요약은 해당 글 링크를 사용합니다.')
    if 'blogger' not in value['channels']:value['channels'].insert(0,'blogger')
    return value

def volume(row):
    return row.get('measured_volume') if row.get('measured_volume') is not None else row.get('recent_volume')

def availability(queue):
    """A keyword is free if it was never written and failed fewer than 2 times (all months: no duplicate posts)."""
    tried={}
    for x in queue:tried.setdefault(research.normalize(x['keyword']),[]).append(x.get('status'))
    def free(keyword):
        states=tried.get(research.normalize(keyword),[])
        return all(s=='error' for s in states) and len(states)<2
    return free

def monthly_top(app,cfg,keys,month):
    cached=app.read_store('auto-keywords.json',{})
    if cached.get('month')!=month or not cached.get('rows'):
        cached=research.monthly_research(month,keys,app.read_store('metrics.json',{}),'volume',cfg.get('seeds') or None)
        app.write_store('auto-keywords.json',cached)
    rows=[r for r in cached['rows'] if volume(r) is not None]
    rows.sort(key=volume,reverse=True)
    return rows[:cfg['top_n']]

def pick(app,cfg,keys,month,queue):
    """Next keyword: monthly TOP-N first, then related keywords (breadth-first from covered keywords)."""
    free=availability(queue);top=monthly_top(app,cfg,keys,month)
    for rank,r in enumerate(top,1):
        if volume(r)>=cfg['min_volume'] and free(r['keyword']):
            return r,{'phase':'monthly','rank':rank,'total':len(top)}
    if not cfg['related']:return None
    rel=app.read_store('auto-related.json',{})
    if rel.get('month')!=month:rel={'month':month,'expanded':[],'pool':[]}
    metrics=app.read_store('metrics.json',{})
    for _ in range(MAX_EXPANSIONS+1):
        pool=[r for r in rel['pool'] if volume(r) is not None and volume(r)>=cfg['min_volume'] and free(r['keyword'])]
        if pool:
            r=max(pool,key=volume)
            return r,{'phase':'related','parent':r.get('parent','')}
        expanded={research.normalize(k) for k in rel['expanded']}
        parents=[x['keyword'] for x in queue if x.get('status')!='error' and x.get('month')==month]+[r['keyword'] for r in top]+[r['keyword'] for r in rel['pool']]
        parent=next((p for p in parents if research.normalize(p) not in expanded),None)
        if parent is None:break
        rel['expanded'].append(parent)
        try:found=research.naver_keywords(parent,keys)
        except ValueError:found=[]
        known={research.normalize(r['keyword']) for r in rel['pool']}|{research.normalize(r['keyword']) for r in top}
        for row in found:
            name=research.normalize(row['keyword'])
            if name not in known and name!=research.normalize(parent):
                rel['pool'].append(dict(research.join_metrics(row,month,metrics),parent=parent));known.add(name)
        app.write_store('auto-related.json',rel)
    return None

def prepare(app):
    if not LOCK.acquire(False):raise ValueError('자동화 작업이 진행 중입니다.')
    try:
        cfg=config(app.read_store('automation.json',{}));keys=app.get_keys()
        if not keys.get('openai_key'):raise ValueError('심층 글 작성 API를 연결하세요.')
        month=datetime.now(research.KST).strftime('%Y-%m')
        queue=app.read_store('queue.json',[]);made=0
        for _ in range(cfg['count']):
            chosen=pick(app,cfg,keys,month,queue)
            if not chosen:break
            r,order=chosen;made+=1
            ident=hashlib.sha256((month+research.normalize(r['keyword'])+str(len(queue))).encode()).hexdigest()[:20]
            entry={'id':ident,'month':month,'keyword':r['keyword'],'metrics':r,'order':order,'status':'researching','delivery':{},'created_at':datetime.now(research.KST).isoformat(),'channels':cfg['channels'],'blog':cfg['blog']}
            queue.append(entry);app.write_store('queue.json',queue)
            try:
                rel=research.related_keywords(r['keyword'],keys,app.read_store('metrics.json',{}),month)
                doc=deep_writer.deep_article(r['keyword'],'공감형',0,cfg.get('notes',''),[x['keyword'] for x in rel['rows']],keys)
                entry.update(doc=doc,quality=doc['quality'],status='ready' if doc['quality']['passed'] else 'review')
                if cfg.get('naver_draft',True):
                    packet=naver_handoff.package(doc);folder=app.ROOT/'naver-drafts';folder.mkdir(exist_ok=True)
                    (folder/(ident+'.html')).write_text(packet['html'],encoding='utf-8')
                    (folder/(ident+'.txt')).write_text('제목 후보\n'+'\n'.join(packet['titles'])+'\n\n대표 이미지 문구\n'+packet['thumbnail_text']+'\n\n본문\n'+packet['text']+'\n\n발행 전 점검\n'+'\n'.join(packet['checklist']),encoding='utf-8')
                    entry['naver_draft']='naver-drafts/'+ident+'.html'
            except Exception as exc:entry.update(status='error',error=clean_error(exc,keys))
            app.write_store('queue.json',queue)
        if not made:raise ValueError('작성할 새 키워드가 없습니다. 이번 달 TOP 키워드와 연관 키워드를 모두 사용했거나, 검색광고 API 연결·최소 검색량을 확인하세요.')
        return queue
    finally:LOCK.release()

def clean_error(exc,keys):
    text=str(exc)
    for value in keys.values():
        if isinstance(value,str) and len(value)>8:text=text.replace(value,'[비공개]')
    return text[:1000]

def describe(entry):
    order=entry.get('order',{});v=volume(entry.get('metrics',{}))
    where=f"이번 달 TOP {order['rank']}/{order['total']}" if order.get('phase')=='monthly' else (f"연관 키워드 ← {order.get('parent','')}" if order.get('phase')=='related' else '')
    return entry['keyword']+(f' · 월간 검색 {int(v):,}' if v is not None else '')+(' · '+where if where else '')

def notify(app,text):
    """Best-effort Telegram message; never raises (a failed alert must not undo a published post)."""
    if not app.read_store('automation.json',{}).get('telegram'):return False
    keys={}
    try:keys=app.get_keys();channels.telegram(text,keys);return True
    except Exception as exc:
        last=app.read_store('automation-last.json',{});last['telegram_error']=clean_error(exc,keys);app.write_store('automation-last.json',last)
        return False

def deliver(app,ident):
    if not LOCK.acquire(False):raise ValueError('자동화 작업이 진행 중입니다.')
    try:
        queue=app.read_store('queue.json',[]);entry=next((x for x in queue if x['id']==ident),None)
        if not entry or entry.get('status') not in ['ready','approved','partial']:raise ValueError('게시 가능한 글을 선택하세요.')
        keys=app.get_keys();doc=entry['doc'];writer_state=app.state()['state']
        # Verify all credentials before producing any public side effects.
        if not (app.ROOT/'token.json').exists():raise ValueError('Google 연결 / 블로그 조회를 먼저 완료하세요.')
        for c in entry['channels']:
            if c!='blogger':channels.check(c,keys)
        for c in entry['channels']:
            previous=entry['delivery'].get(c,{})
            if previous.get('status')=='done':
                if c=='blogger':ensure_url(app,entry);app.write_store('queue.json',queue)
                continue
            if previous.get('status')=='sending':raise ValueError('게시 결과가 불명확합니다. 채널에서 직접 확인 후 완료 ID를 기록하세요.')
            entry['delivery'][c]={'status':'sending'};app.write_store('queue.json',queue)
            try:
                if c=='blogger':
                    result=app.publish({'doc':doc,'blog':entry['blog'],'mode':'publish','design':writer_state.get('design',{}),'ads':writer_state.get('ads',{})})
                    # Save ID before fetching permalink; retry never inserts again.
                    entry['delivery'][c]={'status':'done',**result};app.write_store('queue.json',queue)
                else:
                    if not entry.get('blog_url'):raise ValueError('블로그 링크를 확인하지 못했습니다.')
                    texts=channels.summaries(doc,entry['blog_url'])
                    result=channels.post(c,texts[c],keys)
                    entry['delivery'][c]={'status':'done',**result};app.write_store('queue.json',queue)
            except Exception as exc:
                entry['status']='partial';entry['error']=clean_error(exc,keys);app.write_store('queue.json',queue)
                raise
            if c=='blogger':
                ensure_url(app,entry);app.write_store('queue.json',queue)
        entry['status']='done';entry.pop('error',None);app.write_store('queue.json',queue)
    finally:LOCK.release()
    if not entry.get('notified'):
        sns=[c for c in entry['channels'] if c!='blogger']
        if notify(app,'✅ 블로그 글 발행 완료\n\n'+doc['title']+'\n'+describe(entry)+('\nSNS: '+', '.join(sns) if sns else '')+'\n\n'+entry.get('blog_url','')):
            queue=app.read_store('queue.json',[]);saved=next((x for x in queue if x['id']==ident),None)
            if saved:saved['notified']=True;app.write_store('queue.json',queue)
    return entry

def ensure_url(app,entry):
    if entry.get('blog_url'):return
    with app.OAUTH_LOCK:
        api=app.engine.service()
        post=api.posts().get(blogId=entry['blog'],postId=entry['delivery']['blogger']['id']).execute(num_retries=2)
    import writer
    url=writer.safe_url(post.get('url',''))
    if not url:raise ValueError('게시 링크를 확인하지 못했습니다.')
    entry['blog_url']=url

def tick(app):
    """Called every 30 s by the studio scheduler; runs one cycle when next_run has passed."""
    stored=app.read_store('automation.json',{})
    if not stored.get('enabled') or LOCK.locked():return
    now=datetime.now(research.KST);marker=app.read_store('automation-last.json',{})
    try:
        if marker.get('next_run') and now<datetime.fromisoformat(marker['next_run']):return
    except ValueError:pass
    app.write_store('automation-last.json',{**marker,'status':'running','started':now.isoformat(timespec='minutes')})
    status,error,keys='done',None,{}
    before={x['id'] for x in app.read_store('queue.json',[])}
    try:
        cfg=config(stored);keys=app.get_keys()
        prepare(app)
        if cfg.get('auto_publish'):
            for x in app.read_store('queue.json',[]):
                if x.get('status')=='ready' and x.get('month')==now.strftime('%Y-%m'):deliver(app,x['id'])
    except Exception as exc:status,error='error',clean_error(exc,keys)
    try:cfg=config(stored);low,high=cfg['interval_min'],cfg['interval_max']
    except ValueError:low,high=1.0,3.0
    following=datetime.now(research.KST)+timedelta(hours=random.uniform(low,high))
    app.write_store('automation-last.json',{'day':now.date().isoformat(),'last_run':now.isoformat(timespec='minutes'),'status':status,'error':error,'next_run':following.isoformat(timespec='minutes')})
    when=following.strftime('%m/%d %H:%M')
    for x in app.read_store('queue.json',[]):
        if x['id'] in before:continue
        if x.get('status')=='review':notify(app,'📝 검토가 필요한 글이 있습니다\n\n'+describe(x)+'\n'+'; '.join((x.get('quality') or {}).get('problems',[]))[:500]+'\n\nBlogFlow ④ 자동화 탭에서 확인 후 게시하세요.')
        if x.get('status')=='ready' and not stored.get('auto_publish'):notify(app,'🟢 게시 준비된 글\n\n'+describe(x)+'\n\nBlogFlow ④ 자동화 탭에서 게시하세요.')
    if error:notify(app,'⚠️ 자동화 오류\n\n'+error+'\n\n다음 시도: '+when)
