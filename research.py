"""Measured keyword research. Unknown numbers remain unknown."""
import base64
import calendar
import csv
import hashlib
import hmac
import io
import math
import re
import time
from datetime import datetime, timezone, timedelta
import requests

KST = timezone(timedelta(hours=9))
MONTH_SEEDS = {
    1:['연말정산','난방비 지원','에너지바우처','자동차보험 갱신','알뜰폰'],
    2:['이사 비용','청년월세 지원','주거급여','교육비 지원','인터넷 가입'],
    3:['청년월세 지원','이사 비용','교육급여','국민내일배움카드','인터넷 요금'],
    4:['근로장려금','종합소득세','청년 지원금','알뜰폰','에어컨 청소'],
    5:['근로장려금','종합소득세','자녀장려금','에너지바우처','에어컨 청소'],
    6:['에너지바우처','전기요금 절약','여행자보험','알뜰폰','국민내일배움카드'],
    7:['전기요금 절약','에어컨 전기요금','에너지바우처','여행자보험','청년월세 지원'],
    8:['전기요금 절약','이사 비용','근로장려금','인터넷 요금','구독 서비스'],
    9:['근로장려금','이사 비용','주거급여','인터넷 가입','청년 지원금'],
    10:['난방비 지원','에너지바우처','보일러 교체','알뜰폰','주거급여'],
    11:['난방비 지원','에너지바우처','연말정산','자동차보험','인터넷 요금'],
    12:['연말정산','난방비 지원','에너지바우처','정부지원금','구독 서비스'],
}


def normalize(value):
    return re.sub(r'\s+', '', str(value)).casefold()


def month_bounds(month):
    if not re.fullmatch(r'20\d\d-(0[1-9]|1[0-2])', str(month)):
        raise ValueError('조회 월은 YYYY-MM 형식이어야 합니다.')
    year, number = map(int, month.split('-'))
    return f'{month}-01', f'{month}-{calendar.monthrange(year,number)[1]:02d}'


def number(value):
    if value is None or str(value).strip() == '' or str(value).lstrip().startswith('<'):
        return None
    try:
        result = float(str(value).replace(',','').replace('%',''))
        return result if math.isfinite(result) and result >= 0 else None
    except ValueError:
        return None


def request_json(method, url, **kwargs):
    try:
        response = requests.request(method, url, timeout=(10,180), **kwargs)
    except requests.RequestException:
        raise ValueError('외부 서비스에 연결하지 못했습니다. 인터넷 연결과 연결 설정을 확인하세요.') from None
    if not response.ok:
        raise ValueError(f'외부 서비스가 요청을 거부했습니다 (HTTP {response.status_code}). API 권한·키·사용 한도를 확인하세요.')
    return response.json()


def naver_keywords(keyword, keys):
    needed = ['naver_ad_key','naver_ad_secret','naver_customer']
    if not all(keys.get(k) for k in needed):
        return []
    uri='/keywordstool'
    timestamp=str(int(time.time()*1000))
    signature=base64.b64encode(hmac.new(keys['naver_ad_secret'].encode(), f'{timestamp}.GET.{uri}'.encode(), hashlib.sha256).digest()).decode()
    data=request_json('GET','https://api.searchad.naver.com'+uri,
        params={'hintKeywords':normalize(keyword), 'showDetail':'1'},
        headers={'X-Timestamp':timestamp,'X-API-KEY':keys['naver_ad_key'],'X-Customer':keys['naver_customer'],'X-Signature':signature})
    today=datetime.now(KST).strftime('%Y-%m-%d')
    rows=[]
    for item in data.get('keywordList',[]):
        pc=number(item.get('monthlyPcQcCnt'));mobile=number(item.get('monthlyMobileQcCnt'))
        rows.append({'keyword':item['relKeyword'], 'recent_volume':pc+mobile if pc is not None and mobile is not None else None,
            'volume_display':f'PC {item.get("monthlyPcQcCnt","—")} / 모바일 {item.get("monthlyMobileQcCnt","—")}',
            'search_ctr_pc':number(item.get('monthlyAvePcCtr')), 'search_ctr_mobile':number(item.get('monthlyAveMobileCtr')),
            'competition':item.get('compIdx','미확인'),'observed':today,'source':'네이버 검색광고 키워드 도구', 'seed':keyword})
    return rows


def trend_for_month(keyword, month, keys):
    if not keys.get('naver_client') or not keys.get('naver_secret'):
        return {'trend':None,'trend_series':[]}
    start,end=month_bounds(month)
    today=datetime.now(KST).date()
    if start > today.isoformat():
        return {'trend':None,'trend_series':[],'trend_note':'미래 월은 실제 검색 추이가 없습니다.'}
    year,number_=map(int,month.split('-'))
    end=min(end,today.isoformat())
    start_year = year-1 if number_ < 12 else year
    start_month = number_+1 if number_ < 12 else 1
    start=f'{start_year}-{start_month:02d}-01'
    data=request_json('POST','https://openapi.naver.com/v1/datalab/search',
        headers={'X-Naver-Client-Id':keys['naver_client'],'X-Naver-Client-Secret':keys['naver_secret'],'Content-Type':'application/json'},
        json={'startDate':start,'endDate':end,'timeUnit':'month','keywordGroups':[{'groupName':keyword,'keywords':[keyword]}]})
    series=data.get('results',[{}])[0].get('data',[])
    current=next((number(row['ratio']) for row in series if row.get('period','').startswith(month)),None)
    return {'trend':current,'trend_series':series,'trend_note':'각 키워드의 최근 12개월 최고=100. 키워드 간 검색량 비교 수치가 아닙니다.'}


def import_metrics(text):
    reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    if not reader.fieldnames or not {'month','keyword','source'}.issubset(reader.fieldnames):
        raise ValueError('CSV에 month, keyword, source 열이 필요합니다. 앱의 CSV 양식을 사용하세요.')
    result={}
    for index,row in enumerate(reader,2):
        month=row['month'].strip();month_bounds(month)
        keyword=row['keyword'].strip()
        if not keyword or not row['source'].strip():
            raise ValueError(f'{index}행: 키워드와 출처가 필요합니다.')
        values={}
        for name in ['search_volume','ad_impressions','ad_clicks']:
            raw=(row.get(name) or '').strip()
            val=number(raw)
            if raw and (val is None or not val.is_integer()):
                raise ValueError(f'{index}행: {name}은 0 이상의 정수여야 합니다.')
            values[name]=int(val) if val is not None else None
        impressions=values['ad_impressions'];clicks=values['ad_clicks']
        if (impressions is None)!=(clicks is None) or (clicks is not None and clicks > impressions):
            raise ValueError(f'{index}행: 광고 노출과 클릭 수를 함께 입력하고 클릭 수가 노출 수를 넘지 않게 하세요.')
        ctr=clicks/impressions*100 if impressions else None
        key=f'{month}:{normalize(keyword)}'
        if key in result:
            raise ValueError(f'{index}행: 같은 월·키워드가 중복되었습니다. 원본 데이터를 합산한 뒤 넣으세요.')
        result[key]={'month':month,'keyword':keyword, 'source':row['source'].strip(), 'measured_volume':values['search_volume'],
            'adsense_ctr':ctr, 'ad_impressions':impressions,'ad_clicks':clicks}
    return result


def join_metrics(row, month, metrics):
    result=dict(row)
    measured=metrics.get(f'{month}:{normalize(row["keyword"])}',{})
    result.update({'measured_volume':measured.get('measured_volume'), 'adsense_ctr':measured.get('adsense_ctr'),
        'ad_impressions':measured.get('ad_impressions'),'ad_clicks':measured.get('ad_clicks'),
        'measurement_source':measured.get('source'), 'month':month})
    return result


def sort_rows(rows, sort):
    def key(row):
        volume=row.get('measured_volume')
        if volume is None:volume=row.get('recent_volume')
        if sort=='adsense':
            # Tiny samples must not dominate click-rate ordering.
            ctr=row.get('adsense_ctr') if (row.get('ad_impressions') or 0)>=100 else None
            return (ctr is not None, ctr or 0, volume is not None, volume or 0)
        if sort=='search_ctr':
            ctr=row.get('search_ctr_mobile')
            return (ctr is not None, ctr or 0, volume is not None, volume or 0)
        return (volume is not None, volume or 0, row.get('adsense_ctr') is not None, row.get('adsense_ctr') or 0)
    return sorted(rows,key=key,reverse=True)


def monthly_research(month, keys, metrics, sort='volume', seeds=None):
    month_bounds(month)
    seeds=seeds or MONTH_SEEDS[int(month[-2:])]
    seeds=list(dict.fromkeys(s.strip() for s in seeds if s.strip()))[:5]
    found={};warnings=[]
    live=all(keys.get(k) for k in ['naver_ad_key','naver_ad_secret','naver_customer'])
    for seed in seeds:
        if live:
            try:
                records=naver_keywords(seed,keys)
            except ValueError as exc:
                warnings.append(f'{seed}: {exc}');records=[]
        else:records=[]
        if not records:
            records=[{'keyword':seed,'recent_volume':None,'source':'월별 주제 후보 · 검색량 미측정','seed':seed}]
        for row in records:
            found[normalize(row['keyword'])]=join_metrics(row,month,metrics)
    # Include imported monthly records, even when an API returned no such keyword.
    for measurement in metrics.values():
        if measurement['month']==month:
            name=normalize(measurement['keyword'])
            if name not in found:
                found[name]=join_metrics({'keyword':measurement['keyword'],'recent_volume':None,'source':'사용자 월별 CSV'},month,metrics)
    ordered=sort_rows(list(found.values()),sort)[:50]
    # Trend values are normalized within each keyword, never ranked across keywords.
    if keys.get('naver_client') and keys.get('naver_secret'):
        for row in ordered[:10]:
            try:row.update(trend_for_month(row['keyword'],month,keys))
            except ValueError as exc:warnings.append(str(exc))
    return {'month':month,'rows':ordered,'warnings':list(dict.fromkeys(warnings)), 'measured':live or bool(metrics),
        'note':'선택 월의 정확한 검색량·애드센스 CTR은 월별 CSV 기준입니다. 네이버 API 검색량·검색광고 CTR은 조회 시점의 최근 월간 지표이며 과거 선택 월의 값이 아닙니다. 미래 월은 주제 계획만 가능합니다.'}


def related_keywords(keyword, keys, metrics, month):
    rows=naver_keywords(keyword,keys)
    rows=[join_metrics(r,month,metrics) for r in rows if normalize(r['keyword'])!=normalize(keyword)]
    rows=sort_rows(rows,'volume')
    source='네이버 연관 키워드'
    if not rows:
        endings=['신청 조건','대상 확인','신청 방법','필요 서류','신청 기간','온라인 신청','비교 방법','추가 비용','자주 묻는 질문','공식 안내']
        rows=[join_metrics({'keyword':keyword+' '+suffix,'recent_volume':None,'source':'편집용 키워드 아이디어 · 검색량 미측정'},month,metrics) for suffix in endings]
        source='편집용 아이디어 — 실제 연관 검색 데이터가 아닙니다.'
    return {'rows':rows[:10],'source':source,'count':min(10,len(rows)), 'note':'API가 10개 미만을 반환하면 실제 반환 개수만 표시합니다.'}
