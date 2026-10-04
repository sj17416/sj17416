"""Offline PASONA variants with topic-specific editorial guidance, not live AI research."""
from itertools import product
import random

TOPICS = {
    '에너지바우처': ('정부지원금', '냉난방비', '가구의 소득·가구원 조건', '신청 대상, 신청 기간, 사용 기간, 에너지 이용 방식', '가구 정보와 에너지 요금 고지서를 준비하고 필요한 서류를 공식 안내에서 확인', 'https://www.energyv.or.kr/info/support_info.do', '에너지바우처 지원 안내'),
    '청년월세 지원': ('정부지원금', '매달 나가는 월세', '연령·거주·소득 조건과 지역별 사업 구분', '해당 사업의 모집 기간, 지원 조건, 중복 지원 제한', '임대차계약과 월세 납부 내역 등 제출 자료를 해당 공고에서 확인', 'https://blog.bokjiro.go.kr/1828', '복지로 청년월세 지원 안내'),
    '주거급여': ('정부지원금', '주거비', '가구의 소득과 주거 형태', '신청 대상, 가구별 심사 기준, 제출 서류', '가구 정보와 현재 거주 형태를 정리하고 공식 신청 안내에서 요구 서류를 확인', 'https://www.bokjiro.go.kr/', '복지로에서 주거급여 검색'),
    '국민내일배움카드': ('정부지원금', '교육·훈련 비용', '발급 대상과 선택할 훈련 과정', '카드 발급 조건, 과정별 자부담, 신청 절차', '훈련 목표와 희망 과정을 정리하고 고용24에서 과정별 조건을 확인', 'https://www.work24.go.kr/hr/h/a/1100/selectIssuGudn.do', '고용24 국민내일배움카드 발급 안내'),
    '복지멤버십': ('정부지원금', '나에게 맞는 복지제도를 찾는 수고', '개인·가구 상황과 안내 대상 서비스', '가입 방법, 안내 방식, 개별 사업의 실제 신청 조건', '가입 안내를 확인하고 안내받은 제도의 개별 공고를 다시 확인', 'https://www.bokjiro.go.kr/ssis-tbu/twatvb/wlfareCust/selectFaqList.do', '복지로 자주 묻는 질문'),
    '정부지원금 찾기': ('정부지원금', '생활비 부담', '현재 거주지와 개인·가구 상황', '지원 제도별 대상, 접수 기간, 신청 기관', '정부24와 복지로에서 자신의 조건에 맞는 사업을 찾고 담당 기관 안내를 확인', 'https://www.gov.kr/', '정부24 공식 서비스'),
    '알뜰폰 요금제 비교': ('생활비 절약·상품 비교', '휴대폰 요금', '실제 데이터·통화 사용량', '할인 종료 후 요금, 결합 혜택, 유심 비용, 테더링 조건', '최근 청구서와 사용량을 정리하고 같은 조건의 후보 두 개를 비교', 'https://smartchoice.or.kr/smc/plan/catalogNew.do', '스마트초이스 요금제 비교'),
    '인터넷 요금 비교': ('생활비 절약·상품 비교', '인터넷 요금', '필요한 속도와 가족 결합 조건', '약정 기간, 설치비, 결합할인, 해지 비용', '현재 계약서와 청구서를 확인하고 각 통신사의 공식 견적을 같은 조건으로 비교', 'https://www.smartchoice.or.kr/', '스마트초이스 통신요금 정보'),
    '이사 비용 비교': ('생활비 절약·상품 비교', '이사 비용', '짐의 양과 이동 거리·작업 조건', '포장 범위, 사다리차, 추가 작업, 취소·변경 조건', '동일한 날짜와 작업 범위로 여러 업체의 서면 견적을 받고 포함 비용을 대조', 'https://www.consumer.go.kr/', '소비자24 공식 정보'),
    '구독 서비스 비용 절약': ('생활비 절약·상품 비교', '매달 결제되는 구독료', '실제 이용 빈도와 필요한 기능', '자동 결제일, 연간 결제 조건, 취소·환불 규정', '최근 결제 내역을 모아 사용하지 않는 서비스와 갱신일을 정리', 'https://www.consumer.go.kr/', '소비자24 공식 정보'),
}
STYLES = ['공감형', '체크리스트형', '비교·분석형']
SECTION_KEYS = ['문제', '공감', '해결', '제안', '대상', '행동']


def draft(keyword, style, sequence=0):
    group, burden, audience, checks, preparation, url, source = TOPICS[keyword]
    government = group == '정부지원금'
    # Each sequence selects a different combination; cycles after 4096 per style/topic.
    seed = random.Random(keyword + style).randrange(4096)
    index = (sequence + seed) % 4096
    digits = [(index // 4 ** i) % 4 for i in range(6)]
    prefixes = {
        '공감형': ('혼자 결정하기 어려울 수 있습니다.', '작은 비용도 반복되면 부담스럽죠.'),
        '체크리스트형': ('복잡하다면 확인할 항목부터 나누어 보세요.', '자료를 먼저 모으면 비교가 쉬워집니다.'),
        '비교·분석형': ('조건을 같은 기준으로 놓고 판단하는 것이 중요합니다.', '눈에 띄는 숫자 하나보다 전체 조건이 필요합니다.'),
    }[style]
    choices = [
        [f'{burden}이 부담될 때 {keyword}를 찾아보지만, 어디부터 확인해야 할지 막막한가요?', f'{keyword}를 검색해도 서로 다른 안내 때문에 판단하기 어렵나요? 먼저 {audience}부터 정리해 보세요.', f'{burden}을 줄이고 싶다면 {keyword}의 조건을 확인하는 것부터 시작할 수 있습니다. 다만 이름만 보고 결정하면 필요한 조건을 놓치기 쉽습니다.', f'{keyword} 관련 정보를 찾고 있다면 광고 문구나 요약 숫자보다 나에게 적용되는 조건이 궁금할 겁니다. {prefixes[0]}'],
        [f'안내마다 표현이 다르면 “내 경우에도 해당할까?”라는 고민이 생깁니다. {prefixes[1]}', f'좋아 보이는 조건을 찾더라도 필요한 자료나 추가 비용이 있으면 쉽게 결정하기 어렵습니다. 확인 순서를 정해 하나씩 살펴보세요.', f'검색 결과를 여러 개 읽었는데도 결론이 나지 않는다면 내 상황과 안내 조건이 섞여 있기 때문일 수 있습니다. 사실과 예시를 나누어 읽는 것이 도움이 됩니다.', f'처음 알아보는 사람에게는 생소한 용어와 복잡한 조건이 걸림돌입니다. 서두르기보다 공식 안내와 내 상황을 함께 놓고 보는 편이 좋습니다.'],
        [f'우선 {audience}를 기준으로 확인하세요. 핵심 비교 항목은 {checks}입니다.', f'{keyword}를 검토할 때는 {checks}을 각각 확인해야 합니다. 한 가지 조건만 맞는다고 최종 결론을 내리지 마세요.', f'확인할 기준을 세 가지로 나누세요. 내 상황, 적용되는 조건, 실제 진행 절차입니다. 특히 {checks}을 공식 자료와 대조하세요.', f'요약 글은 확인 순서를 잡는 데 사용하고, 최종 조건은 담당 기관이나 사업자의 최신 안내에서 확인하세요. 먼저 볼 항목은 {checks}입니다.'],
        [f'첫 단계는 {preparation}하는 것입니다. 확인한 조건과 아직 확인하지 못한 항목을 따로 메모해 보세요.', f'오늘은 {preparation}하는 것까지만 진행해도 좋습니다. 필요한 자료를 갖추면 다음 단계에서 질문할 내용이 분명해집니다.', f'간단한 메모를 만들어 {audience}, {checks}을 적어보세요. 이어서 {preparation}하세요.', f'직접 확인한 정보를 기준으로 체크리스트를 만들 수 있습니다. {preparation}한 뒤 내 조건에 맞는 안내인지 확인하세요.'],
        [f'{burden}을 검토하려는 분, {audience}를 확인할 수 있는 분이라면 이 순서로 자료를 정리해 보세요. 적용 여부는 개별 조건에 따라 달라집니다.', f'내 상황을 정리한 뒤 {audience}를 공식 조건과 비교할 수 있다면 다음 단계를 검토하세요. 아직 자료가 없다면 해당 항목을 확인하는 것이 먼저입니다.', f'특히 {keyword}를 처음 알아보는 분에게 이 확인 순서가 도움이 됩니다. 내 조건과 다른 사례의 조건을 동일하게 취급하지 마세요.', f'이미 관련 정보를 읽었다면 빠진 조건이 없는지 점검하는 용도로 활용하세요. {audience}가 달라지면 적용 결과도 달라질 수 있습니다.'],
        [f'아래 공식 안내에서 {keyword}의 조건과 절차를 확인하세요. 확인되지 않은 조건이 있다면 담당 기관이나 사업자에게 질문한 뒤 진행하세요.', f'먼저 공식 안내를 열고 내 상황에 필요한 항목 두 개를 확인해 보세요. 조건을 기록한 뒤 실제 신청 또는 계약 여부를 판단하세요.', f'확인할 자료를 준비했다면 공식 안내와 항목별로 대조하세요. 적용 조건과 추가 부담을 확인한 후 다음 단계를 진행하세요.', f'지금 할 일은 최신 안내를 읽고 궁금한 항목을 메모하는 것입니다. 확인한 정보를 토대로 다음 행동을 결정하세요.'],
    ]
    sections = {key: choices[i][digits[i]] for i,key in enumerate(SECTION_KEYS)}
    title_options = [f'{keyword}: 대상과 신청 전 확인할 조건' if government else f'{keyword}: 선택 전 확인할 비용과 조건', f'{keyword} 확인 가이드: 놓치기 쉬운 조건과 준비 순서', f'{keyword} 알아보기: 내 상황에 맞게 확인하는 방법', f'{keyword} 체크리스트: 공식 안내에서 먼저 볼 항목']
    return {'keyword':keyword,'style':style,'sections':sections,'title':title_options[sequence%4], 'description':f'{keyword}를 알아볼 때 필요한 {audience}, {checks}을 정리했습니다. 공식 안내와 함께 준비 순서와 자주 묻는 질문을 확인하세요.', 'source_url':url,'source_name':source,'government':government,'checks':checks,'sequence':sequence}


def seo_review(title, description, keyword, body):
    import re
    checks = [
        ('제목에 선택 키워드 포함', keyword in title),
        ('검색 설명 작성', bool(description.strip())),
        ('본문에 선택 키워드 포함', keyword in body),
        ('소제목으로 내용 구분', len(re.findall(r'<h2\b', body, re.I)) >= 3),
        ('공식 출처 링크 포함', bool(re.search(r'<a[^>]+href="https://', body))),
        ('광고 위치 구분', body.count('data-ad-position=') == 3),
    ]
    return '\n'.join(('✓ ' if ok else '보완: ') + label for label,ok in checks)
