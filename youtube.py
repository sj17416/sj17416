"""YouTube Data API v3 video upload. Defaults to private; never auto-retries an uncertain upload."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path

SCOPES=['https://www.googleapis.com/auth/youtube.upload','https://www.googleapis.com/auth/youtube.readonly']
EXTS={'.mp4','.mov','.m4v','.avi','.wmv','.webm','.mkv','.flv','.3gp','.mpeg','.mpg'}

def service(root):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    root=Path(root);token=root/'youtube-token.json';secret=root/'credentials.json'
    creds=Credentials.from_authorized_user_file(str(token),SCOPES) if token.exists() else None
    if creds and creds.expired and creds.refresh_token:creds.refresh(Request())
    if not creds or not creds.valid:
        if not secret.exists():raise ValueError('연결 탭에서 Google OAuth JSON(데스크톱 앱)을 먼저 선택하세요.')
        creds=InstalledAppFlow.from_client_secrets_file(str(secret),SCOPES).run_local_server(host='localhost',port=0,prompt='consent',timeout_seconds=180)
    token.write_text(creds.to_json(),encoding='utf-8')
    return build('youtube','v3',credentials=creds,cache_discovery=False)

def channels(root):
    return service(root).channels().list(part='snippet',mine=True).execute(num_retries=2).get('items',[])

def describe(doc,post_url=''):
    lines=[doc.get('description') or doc['title'],'']
    if post_url:lines+=['자세한 내용: '+post_url,'']
    for s in doc.get('sources',[])[:5]:
        if s.get('url'):lines.append('출처: '+s.get('title','')+' '+s['url'])
    lines+=['','※ 정부 공식 채널이 아닙니다. 금액·기간·대상은 공식 안내에서 최종 확인하세요.']
    return '\n'.join(lines)[:4900]

def validate(item):
    path=Path(str(item.get('path','')).strip().strip('"'))
    if not path.is_file():raise ValueError('영상 파일 경로를 확인하세요.')
    if path.suffix.lower() not in EXTS:raise ValueError('지원하는 영상 파일(mp4, mov 등)을 선택하세요.')
    title=str(item.get('title','')).strip().replace('<','').replace('>','')
    if not title or len(title)>100:raise ValueError('영상 제목은 1~100자로 입력하세요.')
    privacy=item.get('privacy','private')
    if privacy not in ('private','unlisted','public'):raise ValueError('공개 범위를 선택하세요.')
    publish_at=str(item.get('publish_at','')).strip()
    if publish_at:
        date=datetime.fromisoformat(publish_at.replace('Z','+00:00'))
        if date.tzinfo is None or date<=datetime.now(timezone.utc):raise ValueError('예약 시간은 시간대가 포함된 미래 시간이어야 합니다.')
        privacy='private';publish_at=date.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
    tags=[str(t).strip() for t in item.get('tags',[]) if str(t).strip()][:15]
    return path,{'snippet':{'title':title,'description':str(item.get('description',''))[:4900],'tags':tags,'categoryId':'22','defaultLanguage':'ko'},
        'status':{'privacyStatus':privacy,'selfDeclaredMadeForKids':False,**({'publishAt':publish_at} if publish_at else {})}}

def upload(root,item):
    from googleapiclient.http import MediaFileUpload
    root=Path(root);path,body=validate(item);state_path=root/'youtube-state.json'
    state=json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    st=path.stat();key=hashlib.sha256(json.dumps([str(path.resolve()),st.st_size,int(st.st_mtime),body],sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]
    prev=state.get(key,{})
    if prev.get('status')=='done':return {'id':prev['id'],'url':'https://youtu.be/'+prev['id'],'skipped':True}
    if prev.get('status')=='sending':raise ValueError('이전 업로드 결과가 불확실합니다. YouTube 스튜디오에서 업로드 여부를 확인한 뒤, 없으면 "업로드 기록 초기화" 후 다시 시도하세요.')
    def save():state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    api=service(root)
    state[key]={'status':'sending','file':path.name,'title':body['snippet']['title'],'at':datetime.now(timezone.utc).isoformat()};save()
    request=api.videos().insert(part='snippet,status',body=body,media_body=MediaFileUpload(str(path),chunksize=8*1024*1024,resumable=True))
    response=None
    while response is None:_,response=request.next_chunk(num_retries=3)
    state[key].update(status='done',id=response['id']);save()
    return {'id':response['id'],'url':'https://youtu.be/'+response['id'],'privacy':body['status']['privacyStatus']}

def reset_pending(root):
    state_path=Path(root)/'youtube-state.json'
    if not state_path.exists():return 0
    state=json.loads(state_path.read_text(encoding='utf-8'));n=0
    for k in [k for k,v in state.items() if v.get('status')=='sending']:del state[k];n+=1
    state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8');return n
