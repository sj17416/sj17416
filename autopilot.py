"""Local recurring workflow, durable queue and per-channel delivery state."""
import hashlib
import threading
from datetime import datetime
import research,deep_writer,channels,naver_handoff
LOCK=threading.Lock()

def config(value):
    value=dict(value)
    value['hour']=max(0,min(23,int(value.get('hour',9))))
    value['count']=max(1,min(3,int(value.get('count',1))))
    value['min_volume']=max(0,int(value.get('min_volume',1000)))
    value['channels']=[c for c in value.get('channels',[]) if c in ['blogger','threads','facebook','x']]
    if not value['channels']:raise ValueError('게시 채널을 선택하세요.')
    if not str(value.get('blog','')).isdigit():raise ValueError('Blogger 블로그 ID를 입력하세요. SNS 요약은 해당 글 링크를 사용합니다.')
    if 'blogger' not in value['channels']:value['channels'].insert(0,'blogger')
    return value

def prepare(app):
    if not LOCK.acquire(False):raise ValueError('자동화 작업이 진행 중입니다.')
    try:
        cfg=config(app.read_store('automation.json',{}));keys=app.get_keys()
        if not keys.get('openai_key'):raise ValueError('심층 글 작성 API를 연결하세요.')
        month=datetime.now(research.KST).strftime('%Y-%m')
        cached=app.read_store('auto-keywords.json',{})
        if cached.get('month')!=month or not cached.get('rows'):
            cached=research.monthly_research(month,keys,app.read_store('metrics.json',{}),'volume',cfg.get('seeds') or None)
            app.write_store('auto-keywords.json',cached)
        queue=app.read_store('queue.json',[])
        used={research.normalize(x['keyword']) for x in queue if x.get('month')==month}
        eligible=[r for r in cached['rows'] if (r.get('measured_volume') if r.get('measured_volume') is not None else r.get('recent_volume')) is not None]
        eligible.sort(key=lambda r:r.get('measured_volume') if r.get('measured_volume') is not None else r.get('recent_volume'),reverse=True)
        selected=[r for r in eligible if research.normalize(r['keyword']) not in used and (r.get('measured_volume') if r.get('measured_volume') is not None else r.get('recent_volume'))>=cfg['min_volume']][:cfg['count']]
        if not selected:raise ValueError('측정된 검색량 기준을 충족하는 새 키워드가 없습니다. API 연결·CSV·최소 검색량을 확인하세요.')
        for r in selected:
            ident=hashlib.sha256((month+research.normalize(r['keyword'])).encode()).hexdigest()[:20]
            entry={'id':ident,'month':month,'keyword':r['keyword'],'metrics':r,'status':'researching','delivery':{},'created_at':datetime.now(research.KST).isoformat(),'channels':cfg['channels'],'blog':cfg['blog']}
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
        return queue
    finally:LOCK.release()

def clean_error(exc,keys):
    text=str(exc)
    for value in keys.values():
        if isinstance(value,str) and len(value)>8:text=text.replace(value,'[비공개]')
    return text[:1000]

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
        return entry
    finally:LOCK.release()

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
    cfg=app.read_store('automation.json',{})
    now=datetime.now(research.KST)
    if not cfg.get('enabled') or now.hour<int(cfg.get('hour',9)) or LOCK.locked():return
    marker=app.read_store('automation-last.json',{})
    if marker.get('day')==now.date().isoformat():return
    app.write_store('automation-last.json',{'day':now.date().isoformat(),'status':'running'})
    try:
        prepare(app)
        if cfg.get('auto_publish'):
            for x in app.read_store('queue.json',[]):
                if x.get('status')=='ready' and x.get('month')==now.strftime('%Y-%m'):deliver(app,x['id'])
        app.write_store('automation-last.json',{'day':now.date().isoformat(),'status':'done'})
    except Exception as exc:app.write_store('automation-last.json',{'day':now.date().isoformat(),'status':'error','error':clean_error(exc,app.get_keys())})
