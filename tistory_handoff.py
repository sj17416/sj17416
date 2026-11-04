"""Tistory editorial handoff. Tistory Open API (posting) was shut down in 2024, so this only prepares paste-ready content."""
import html,re
import writer

def tags(doc):
    keyword=str(doc.get('keyword','')).strip();found=[]
    for t in [keyword,keyword.replace(' ','')]+keyword.split()+[keyword.replace(' ','')+x for x in ('신청','대상','조건','신청방법')]+[str(r.get('keyword',r) if isinstance(r,dict) else r) for r in doc.get('related',[])]:
        t=t.strip()
        if len(t)>=2 and t not in found:found.append(t)
    return found[:10]

def package(doc,design=None):
    writer.validate(doc);esc=html.escape
    keyword=doc.get('keyword','생활 정보')
    titles=list(dict.fromkeys([doc['title'],keyword+' 총정리: 대상·조건·신청 순서',keyword+' 확인 전 꼭 볼 체크리스트']))
    # Ads are omitted: Tistory serves its own AdSense placement, and pasting scripts into the editor is unreliable.
    body=writer.render(doc,design,{},False)
    disclaimer='<p style="font-size:13px;color:#687180">이 글은 정부 공식 사이트가 아닙니다. 금액·기간·대상은 공식 안내에서 최종 확인하세요.</p>'
    if '정부 공식 사이트가 아닙니다' not in body:body+=disclaimer
    tips=['티스토리 편집기 우측 상단의 [기본모드] → [HTML]로 바꾼 뒤 본문 HTML을 붙여 넣으세요.','카테고리·공개 범위·발행 시간은 티스토리에서 직접 정하세요.','대표 이미지는 직접 촬영했거나 사용 권한이 있는 이미지를 지정하세요.','같은 글을 Blogger에도 발행했다면 중복 문서로 보일 수 있으니 제목·도입부를 다듬는 것을 권장합니다.','출처의 기준일과 적용 연도를 다시 확인하세요.']
    return {'titles':titles,'tags':tags(doc),'html':body,'checklist':tips,'notice':'티스토리 글쓰기 API는 2024년에 종료되어 직접 발행이 필요합니다.'}
