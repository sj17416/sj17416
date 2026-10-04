"""Naver Blog editorial handoff. No homefeed submission or posting API."""
import html,re
import writer

def package(doc):
    writer.validate(doc);esc=html.escape
    keyword=doc.get('keyword','생활 정보')
    titles=list(dict.fromkeys([doc['title'],keyword+' 알아보기: 내 조건과 준비 순서',keyword+' 확인 전 놓치기 쉬운 조건 정리']))
    thumb=keyword+'\n대상·조건·절차 확인'
    parts=['<!doctype html><html lang="ko"><meta charset="utf-8"><title>'+esc(titles[0])+'</title><body><article>']
    text=[]
    def para(value):
        # Split long paragraphs at sentence boundaries for mobile reading; no factual rewriting.
        sentences=re.split(r'(?<=[.!?。])\s+',str(value));blocks=[];block=''
        for sentence in sentences:
            if block and len(block)+len(sentence)>180:blocks.append(block);block=''
            block+=((' ' if block else '')+sentence)
        if block:blocks.append(block)
        for b in blocks:
            parts.append('<p>'+esc(b).replace('\n','<br>')+'</p>');text.append(b+'\n')
    for p in doc['intro']:para(p)
    for section in doc['sections']:
        parts.append('<h2>'+esc(section['heading'])+'</h2>');text.append('\n'+section['heading']+'\n')
        for p in section['paragraphs']:para(p)
    para(doc.get('conclusion',''))
    parts.append('<h2>자주 묻는 질문</h2>');text.append('\n자주 묻는 질문\n')
    for f in doc['faq']:parts.append('<h3>'+esc(f['question'])+'</h3>');text.append(f['question']);para(f['answer'])
    parts.append('<h2>참고한 원문</h2><ul>');text.append('\n참고한 원문')
    for s in doc['sources']:
        url=writer.safe_url(s.get('url',''))
        if url:parts.append('<li><a href="'+esc(url,quote=True)+'">'+esc(s['title'])+'</a></li>');text.append(s['title']+' '+url)
    parts.append('</ul></article></body></html>')
    tips=['네이버 블로그에서 공개 범위와 글 주제를 직접 확인하세요.','직접 촬영했거나 사용 권한이 있는 대표 이미지를 지정하세요.','직접 경험·사진이 있다면 추가하되 없는 경험을 만들어 넣지 마세요.','제목과 본문이 같은 질문에 답하는지, 첫 문단에서 효용이 드러나는지 확인하세요.','출처의 적용 연도와 대상·예외를 확인하고 키워드를 반복해서 채우지 마세요.','홈판 노출은 보장되지 않습니다. 공개 글 발행과 홈판 추천은 별개입니다.']
    return {'titles':titles,'thumbnail_text':thumb,'text':'\n'.join(text),'html':''.join(parts),'checklist':tips,'notice':'네이버 블로그에 직접 발행하세요. 홈판 추천은 네이버가 결정하며 직접 등록 API는 지원하지 않습니다.'}
