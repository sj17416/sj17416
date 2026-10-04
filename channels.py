"""Official text-post adapters. Tokens are user-authorized user/page tokens."""
import re
from research import request_json

def check(channel,keys):
    required={'threads':['threads_token'],'facebook':['facebook_token','facebook_page','facebook_version'],'x':['x_token']}
    if not all(keys.get(k) for k in required[channel]):raise ValueError(channel+' 게시 연결을 설정하세요.')
    if channel=='facebook' and (not str(keys['facebook_page']).isdigit() or not re.fullmatch(r'v\d+\.\d+',keys['facebook_version'])):raise ValueError('Facebook 페이지 ID와 지원되는 Graph API 버전을 확인하세요.')

def post(channel,text,keys):
    check(channel,keys)
    if channel=='threads':
        if len(text)>500:raise ValueError('Threads 텍스트가 500자를 넘습니다.')
        result=request_json('POST','https://graph.threads.net/v1.0/me/threads',headers={'Authorization':'Bearer '+keys['threads_token']},data={'media_type':'TEXT','text':text,'auto_publish_text':'true'})
        ident=result.get('id')
    elif channel=='facebook':
        result=request_json('POST',f'https://graph.facebook.com/{keys["facebook_version"]}/{keys["facebook_page"]}/feed',headers={'Authorization':'Bearer '+keys['facebook_token']},data={'message':text})
        ident=result.get('id')
    else:
        # Conservative weighted-character budget: all non-ASCII chars cost two.
        weighted=sum(1 if ord(c)<128 else 2 for c in re.sub(r'https?://\S+','x'*23,text))
        if weighted>260:raise ValueError('X 텍스트 길이를 줄여주세요.')
        result=request_json('POST','https://api.x.com/2/tweets',headers={'Authorization':'Bearer '+keys['x_token']},json={'text':text})
        ident=result.get('data',{}).get('id')
    if not ident:raise ValueError('게시 ID를 받지 못했습니다. 채널에서 직접 게시 여부를 확인하세요.')
    return {'id':str(ident)}

def summaries(doc,url):
    description=doc.get('description','')
    return {'threads':doc['title'][:100]+'\n\n'+description[:250]+'\n\n자세한 조건·출처: '+url,'facebook':doc['title']+'\n\n'+description+'\n\n'+ '\n'.join('• '+s['heading'] for s in doc['sections'][:4])+'\n\n자세한 안내: '+url,'x':doc['keyword'][:24]+' 확인 가이드\n대상·조건·절차와 놓치기 쉬운 점을 정리했습니다.\n'+url}
