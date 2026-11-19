# ======================================================================
# [블록 9] 간밤 뉴스·오늘 일정 — 뉴스보이가 아침 회의에서 읽는 국제 뉴스와 실적·경제지표 일정
#   하는 일  : (가) 간밤 뉴스, 어제 저녁 6시(한국) 이후 올라온 것만. 세 곳에서 각각 최대 NEWS_MAX건
#                   ① 연합뉴스 국제 ② 야후 파이낸스 종목별 뉴스(한국·미국·일본 보유·관심 개별주, 한 종목 최대 2건, 보유 먼저)
#                   ③ CNBC 주요 뉴스(Top News). ⑩ 블룸버그 공식 RSS 5개 면(2026-11-20, 주가 뉴스 10용). 2026-10-29 의장 지시("국제 뉴스를 넓히자, 꼭 넣도록")
#                   ⑤ 한국·일본 종목별 뉴스: 구글 뉴스 검색 RSS로 개별주 이름을 검색(보유 먼저, 한 종목 최대 2건).
#                      2026-10-31 추가 — SK하이닉스 10/28 실적처럼 한국 종목 큰 뉴스가 수집에서 빠지던 구멍을 막는다.
#                   ④ 아침 정리 기사: 국내 언론사의 '뉴욕증시 마감·간밤 해외증시·모닝 브리핑' 기사를 구글 뉴스 검색 RSS로 모은다.
#                      한 언론사만 막혀도 다른 곳 기사가 잡히는 예비 통로. 2026-10-30 의장 "뉴스블록의 대안을 마련하자"
#                   ⑥ DART 공시 제목: 한국 개별주의 어제·오늘 공시 전부. 자사주·배당·소각은 [주주환원], 증자·합병·수주는 [자본·지배구조]
#                      꼬리표를 달고 먼저 싣는다. 2026-10-31 의장 "주주 환원 같은 건 공시가 뜨잖아, DART도 자주 봐야"
#                   ⑦ 네이버 뉴스 검색 API: 한국 개별주, 제목+요약(키 NAVER_CLIENT_ID·NAVER_CLIENT_SECRET, 무료 하루 25,000회)
#                      새 키는 네이버 클라우드 NAVER API HUB에서 발급(한시 무료, 유료 전환 땐 사전 공지)
#                   무료 한도: API_LIMITS. 80% 넘으면 브리핑 맨 위 [사용량 주의], 95% 넘으면 그 통로를 쉰다(00_누적/00_API사용량.csv)
#                   ⑧ Finnhub 종목 뉴스: 미국 개별주, 제목+요약(키 FINNHUB_KEY, 무료 분당 60회)
#                   ⑨ 사건 검색(Tavily): 전일 ±5% 넘게 움직인 개별주만 '종목명 + 급등/급락 이유'로 검색(키 TAVILY_KEY, 무료 월 1,000)
#                      ⑦⑧⑨는 키가 없으면 건너뛰고 점검 파일에 '건너뜀'으로 남긴다.
#              (나) 국내 실적발표 일정: 한국 개별주의 DART 거래소공시 중 '기업설명회(IR) 개최'·'결산실적공시 예고'를
#                   찾아 본문에서 날짜·시각을 읽는다. 오늘·어제 나온 '영업(잠정)실적' 공시도 함께 적는다.
#              (다) 미국·일본 종목 실적발표 일정: 야후 실적 발표일(시각은 한국 시각으로 바꿈)
#                   야후 실적 목록(get_earnings_dates)에 빠지는 종목이 있어 야후 calendar 날짜도 함께 본다(10/28 MSFT·알파벳 누락).
#                   간밤(어제, 미국 날짜) 발표한 종목은 '간밤 발표'로 적고, 야후에 실제 EPS가 있으면 예상치와 함께 적는다.
#              (라) 미국 주요 경제지표 발표 일정: FRED 발표 달력(CPI·고용·PCE·GDP·FOMC 등).
#                   FRED에는 발표 시각이 없어 통상 발표 시각(미국 동부)을 한국 시각으로 바꿔 '통상'이라 적는다.
#              일정은 오늘부터 SCHED_DAYS일 안의 것만. 판정은 하지 않는다.
#   소스     : 연합뉴스·야후 종목별·CNBC·구글 뉴스 검색 RSS(키 없음), DART OpenAPI(DART_KEY), 야후(키 없음), FRED API(FRED_KEY),
#              네이버 검색 API(NAVER_CLIENT_ID·SECRET), Finnhub(FINNHUB_KEY), Tavily(TAVILY_KEY)
#   읽는 것  : 수집데이터/00_누적/00_DART_고유번호.csv (블록 6이 만든 종목코드 → DART 고유번호)
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_뉴스.csv (시각, 제목, 요약, 링크, 출처, 종목)
#              수집데이터/YYYYMMDD/YYYYMMDD_일정.csv (날짜, 시각, 구분, 대상, 내용, 출처)
#   쓰는 위원: 뉴스보이(간밤 뉴스·오늘 일정), 섹터 위원(담당 종목 실적 일정)
#   고칠 곳  : 뉴스 건수 NEWS_MAX, 일정 기간 SCHED_DAYS, 미국 지표 목록 US_RELEASES, 해마다 FOMC_DAYS
#   실패하면 : 소스별로 건너뛰고 점검 파일에 남긴다
# ======================================================================
import html as _h, re as _re, xml.etree.ElementTree as _ET, zipfile as _zip
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

NEWS_RSS = 'https://www.yna.co.kr/rss/international.xml'
NEWS_RSS_ECON = 'https://www.yna.co.kr/rss/economy.xml'   # 국제 면 시장 기사가 모자라면 채움(2026-11-03)
# 2026-11-03 의장 "이따위 홍보 기사를 주요뉴스라고 붙이는 건 판단력 부재": 칼럼·인터뷰·홍보는 빼고 시장 기사만 (고칠 곳)
NEWS_DROP = (r'칼럼|인터뷰|기고|사설|르포|포토|화보|\[인사\]|부고|브랜드평판|브랜드 평판|ESG 브랜드|사회공헌|사회적 가치|'
             r'개막전|스포츠|\d+대\d+ |봉사|후원|기부|캠페인|시상식|축제|사진=|기사와 직접|^["“].*["”]$')
NEWS_KEEP = (r'증시|주가|급등|급락|금리|연준|Fed|채권|국채|유가|원유|달러|환율|관세|무역|실적|매출|영업이익|순이익|인수|합병|'
             r'반도체|AI|인공지능|메모리|HBM|칩|데이터센터|전쟁|이란|이스라엘|우크라|중동|휴전|제재|선거|트럼프|대통령|의회|'
             r'경기|침체|물가|인플레|고용|일자리|GDP|수출|투자|조달|증자|채권 발행|IPO|상장|파산|부도|신용')
NEWS_POOL = 40            # 거르기 전 연합뉴스에서 받는 건수
YAHOO_RSS = 'https://feeds.finance.yahoo.com/rss/2.0/headline'
BBG_RSS = [f'https://feeds.bloomberg.com/{x}/news.rss' for x in ('markets', 'economics', 'technology', 'politics', 'industries')]
CNBC_RSS = 'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114'
GNEWS_RSS = 'https://news.google.com/rss/search'
MORNING_QUERIES = ['뉴욕증시 마감', '간밤 해외증시', '모닝 브리핑 증시', '뉴욕마감']   # 아침 정리 기사 검색어 (고칠 곳)
# 2026-11-05 의장 "텍사스·아이오와·조지아 주지사의 데이터센터 발언을 매일 챙겨라(당분간 가장 중요)" (고칠 곳)
GOV_QUERIES = ['Texas governor data center', 'Hinojosa data center', 'Abbott data center',
               'Iowa governor data center', 'Iowa governor-elect data center',
               'Georgia governor data center', 'Georgia governor-elect data center', 'Kemp data center']
GOV_TITLE = r'(?i)data ?cent(er|re)|데이터 ?센터'
GOV_STATE = r'(?i)governor|주지사|texas|iowa|georgia|hinojosa|abbott|kemp|reynolds|텍사스|아이오와|조지아'
MORNING_TITLE = r'뉴욕증시|뉴욕마감|뉴욕 마감|美증시|미 증시|미국 증시|간밤|해외증시|월가|글로벌 마켓'   # 제목에 이 말이 있는 것만
MORNING_MEDIA = ('매일경제', '연합뉴스', '조선일보')   # 2026-11-11 의장 "믿을 만한 언론만. 매경, 연합뉴스, 조선일보 정도" (고칠 곳)
NEWS_MAX = 10             # 출처마다 최대 건수
YAHOO_PER_TICKER = 2      # 야후 종목별 뉴스에서 한 종목 최대 건수
ASIA_PER_TICKER = 2       # 한국·일본 종목별(구글 뉴스)에서 한 종목 최대 건수
ASIA_MAX = 20             # 한국·일본 종목별 전체 최대 건수
ARCHIVE_PER_TICKER = 5    # 종목 뉴스 누적 파일에 한 종목 하루 최대 건수
ARCHIVE_DAYS = 365        # 종목 뉴스 누적 파일 보관 기간(일)
ARCHIVE = []              # 기업 카드용 종목 뉴스 누적(야후·구글, 브리핑 건수 제한 전)
SCHED_DAYS = 7
NAVER_PER_TICKER = 3      # 네이버 종목별: 한 종목 최대 건수
NAVER_MAX = 40            # 네이버 종목별 전체 최대 건수
FINNHUB_PER_TICKER = 2    # Finnhub 종목별: 한 종목 최대 건수
FINNHUB_MAX = 30          # Finnhub 종목별 전체 최대 건수
DART_MAX = 40             # DART 공시 전체 최대 건수
DART_SKIP = r'임원ㆍ주요주주특정증권등소유상황보고서|임원·주요주주특정증권등소유상황보고서|특정증권등소유상황보고서'   # 너무 잦은 공시는 뺀다
DART_RETURN = r'자기주식|자사주|배당|소각|주주환원|기업가치 ?제고|밸류업'   # [주주환원] 꼬리표 (고칠 곳)
DART_CAPITAL = r'유상증자|무상증자|전환사채|신주인수권|교환사채|합병|분할|최대주주|대량보유|공개매수|단일판매|공급계약|타법인주식'
MOVE_PCT = 5.0            # 사건 검색: 전일 등락률 절댓값이 이만큼 넘는 종목만
API_LIMITS = {   # 무료 한도: 서비스 → (기간 '월'/'일', 한도). 80% 넘으면 브리핑 맨 위에 [사용량 주의] (2026-10-31 의장 "한도 전에 미리 알려줘")
    'Tavily': ('월', 1000), '네이버 검색': ('일', 25000), 'Finnhub': ('일', 60 * 60 * 24),
}
API_WARN_PCT = 80         # 이 비율(%)을 넘으면 경고
API_STOP_PCT = 95         # 이 비율(%)을 넘으면 그 달(그날)은 그 통로를 쉬어 한도를 넘기지 않는다
USAGE = {}                # 오늘 쓴 호출 수(서비스별)
API_WARN = []             # 브리핑 맨 위에 실을 경고
MOVE_MAX = 10             # 사건 검색: 하루 최대 종목 수(종목당 Tavily 1크레딧, 무료 월 1,000)
ET_TZ = ZoneInfo('America/New_York')
US_RELEASES = {   # FRED 발표 이름(정확히 같아야 함) → (한국어 이름, 통상 발표 시각(미국 동부))
    'Consumer Price Index': ('미국 CPI(소비자물가)', '08:30'),
    'Producer Price Index': ('미국 PPI(생산자물가)', '08:30'),
    'Employment Situation': ('미국 고용보고서(비농업·실업률)', '08:30'),
    'Personal Income and Outlays': ('미국 PCE 물가·개인소득', '08:30'),
    'Gross Domestic Product': ('미국 GDP', '08:30'),
    'Advance Monthly Sales for Retail and Food Services': ('미국 소매판매', '08:30'),
    'Unemployment Insurance Weekly Claims Report': ('미국 신규 실업수당 청구', '08:30'),
    'Job Openings and Labor Turnover Survey': ('미국 JOLTS(구인)', '10:00'),
    'Surveys of Consumers': ('미시간대 소비자심리', '10:00'),
    'G.17 Industrial Production and Capacity Utilization': ('미국 산업생산', '09:15'),
}
# FOMC 금리 결정일(회의 둘째 날, 미국 동부 14:00 발표). FRED 달력에는 매일 나와 쓸 수 없어 연준 발표 일정을 적어 둔다.
# 해마다 연준 누리집(federalreserve.gov, FOMC 일정)을 보고 고친다.
FOMC_DAYS = ['2026-01-28', '2026-03-18', '2026-04-29', '2026-06-17', '2026-07-29', '2026-09-16', '2026-10-28', '2026-12-09']
WD = '월화수목금토일'
today = NOW.date()
until = today + dt.timedelta(days=SCHED_DAYS)
SCHED = []


def _text(s):
    return _re.sub(r'\s+', ' ', _h.unescape(_re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def _add(day, hm, kind, who, what, src, mark='', check=''):
    # 11/3 의장 "일정 체크 오류 많음": 이미 발표한 실적은 '간밤 실적'으로 따로, 날짜마다 확인 정도(확정/예상/다름)를 붙인다
    if str(what).startswith(('간밤 발표', '공시됨')):
        kind, check = (kind.replace('실적', '').strip() + ' 간밤 실적' if '실적' in kind else kind), '발표됨'
    SCHED.append({'날짜': day.strftime('%Y-%m-%d'), '요일': WD[day.weekday()], '시각(한국)': hm or '미정',
                  '구분': kind, '대상': who, '보유/관심': mark, '확인': check, '내용': what, '출처': src})


# (가) 간밤 뉴스 — 연합뉴스 국제 · 야후 종목별 · CNBC --------------------------
NEWS_COLS = ['시각(한국)', '제목', '요약', '링크', '출처', '종목']
since = (NOW - dt.timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)


def _rss(url, src, who='', params=None):
    """RSS 항목 중 since 이후 것. 실패하면 예외"""
    r = get(url, retry=2, params=params)
    if r is None:
        raise RuntimeError('응답 없음')
    out = []
    for it in _ET.fromstring(r.content).iter('item'):
        try:
            t = parsedate_to_datetime(it.findtext('pubDate')).astimezone(KST)
        except Exception:
            continue
        if t < since:
            continue
        out.append({'시각(한국)': t.strftime('%m-%d %H:%M'), '제목': _text(it.findtext('title')),
                    '요약': _text(it.findtext('description'))[:160], '링크': (it.findtext('link') or '').strip(),
                    '출처': src, '종목': who})
    return sorted(out, key=lambda x: x['시각(한국)'], reverse=True)


news, msgs = [], []
try:                                    # ① 연합뉴스 국제
    def _market(items):
        return [x for x in items if not _re.search(NEWS_DROP, x['제목'])
                and (_re.search(NEWS_KEEP, x['제목']) or any(nm and nm in x['제목'] for nm in NAMES_KO))]
    NAMES_KO = [str(x) for x in u['정식 종목명'].dropna() if _re.search('[가-힣]', str(x)) and len(str(x)) >= 2]
    raw = _rss(NEWS_RSS, '연합뉴스 국제')[:NEWS_POOL]
    got = _market(raw)[:NEWS_MAX]
    n_drop = len(raw) - len(_market(raw))
    if len(got) < 5:                    # 국제 면에 시장 기사가 적으면 경제 면에서 채움
        try:
            more = [x for x in _market(_rss(NEWS_RSS_ECON, '연합뉴스 경제')[:NEWS_POOL]) if x['제목'] not in {g['제목'] for g in got}]
            got += more[:NEWS_MAX - len(got)]
        except Exception:
            pass
    news += got
    msgs.append(f'연합뉴스 {len(got)}건(시장과 무관한 {n_drop}건 뺌)')
except Exception as e:
    msgs.append(f'연합뉴스 실패({type(e).__name__} {e})')
try:                                    # ② 야후 종목별 — 보유 먼저, 한 종목 최대 YAHOO_PER_TICKER건
    us = u[u['시장'].isin(['미국', '한국', '일본']) & (u['구분'] == '개별주')]   # 10/31: 한국(.KS)·일본(.T)도 야후 종목 뉴스가 있음
    us = pd.concat([us[us['보유/관심'] == '보유'], us[us['보유/관심'] != '보유']])
    pool, seen_link, n_fail = [], set(), 0
    for _, s in us.iterrows():
        time.sleep(0.3)
        try:
            items = _rss(YAHOO_RSS, '야후 종목별', s['정식 종목명'],
                         params={'s': s['yfinance 티커'], 'region': 'US', 'lang': 'en-US'})
        except Exception:
            n_fail += 1
            continue
        ARCHIVE.extend(dict(x, 종목=s['정식 종목명'], 번호=s['번호']) for x in items[:ARCHIVE_PER_TICKER])
        k = 0
        for x in items:
            if x['링크'] in seen_link or x['제목'] in seen_link:
                continue
            seen_link.update([x['링크'], x['제목']])
            x['보유'] = s['보유/관심'] == '보유'
            pool.append(x)
            k += 1
            if k >= YAHOO_PER_TICKER:
                break
    pool = sorted(pool, key=lambda x: x['시각(한국)'], reverse=True)          # 새것 먼저
    pool = sorted(pool, key=lambda x: not x.pop('보유'))                       # 그중 보유 종목 먼저
    got = sorted(pool[:NEWS_MAX], key=lambda x: x['시각(한국)'], reverse=True)
    news += got
    msgs.append(f'야후 종목별 {len(got)}건' + (f'(조회 실패 {n_fail}종목)' if n_fail else ''))
except Exception as e:
    msgs.append(f'야후 종목별 실패({type(e).__name__} {e})')
try:                                    # ③ CNBC 주요 뉴스
    got = _rss(CNBC_RSS, 'CNBC')[:NEWS_MAX]
    news += got
    msgs.append(f'CNBC {len(got)}건')
except Exception as e:
    msgs.append(f'CNBC 실패({type(e).__name__} {e})')
try:                                    # ⑩ 블룸버그 공식 RSS(제목+요약, robots 허용) — 11/20 의장 "밤새 미국 뉴스에 집중"
    pool, seen = [], set()
    for url in BBG_RSS:
        try:
            for x in _rss(url, '블룸버그'):
                if x['제목'] not in seen and not _re.search(NEWS_DROP, x['제목']):
                    seen.add(x['제목']); pool.append(x)
        except Exception:
            continue
    got = sorted(pool, key=lambda x: x['시각(한국)'], reverse=True)[:NEWS_MAX * 2]
    news += got
    msgs.append(f'블룸버그 {len(got)}건')
except Exception as e:
    msgs.append(f'블룸버그 실패({type(e).__name__} {e})')
try:                                    # ④ 아침 정리 기사 — 구글 뉴스 검색(국내 언론사), 제목 끝 ' - 매체'를 출처로
    pool, seen, n_fail = [], set(), 0
    for q in MORNING_QUERIES:
        try:
            items = _rss(GNEWS_RSS, '아침 정리', params={'q': f'{q} when:1d', 'hl': 'ko', 'gl': 'KR', 'ceid': 'KR:ko'})
        except Exception:
            n_fail += 1
            continue
        for x in items:
            title, _, media = x['제목'].rpartition(' - ')
            title = title or x['제목']
            if title in seen or not _re.search(MORNING_TITLE, title) or media.strip() not in MORNING_MEDIA:
                continue
            seen.add(title)
            x.update({'제목': title, '종목': media, '요약': ''})   # 구글 요약은 제목 반복이라 비움, 매체는 '종목' 칸에
            pool.append(x)
    got = sorted(pool, key=lambda x: x['시각(한국)'], reverse=True)[:NEWS_MAX]
    news += got
    msgs.append(f'아침 정리 {len(got)}건' + (f'(검색어 실패 {n_fail})' if n_fail else ''))
except Exception as e:
    msgs.append(f'아침 정리 실패({type(e).__name__} {e})')
try:                                    # ⑥ 주지사·데이터센터 — 구글 뉴스(영어), 텍사스·아이오와·조지아 (2026-11-05)
    pool, seen, n_fail = [], set(), 0
    for q in GOV_QUERIES:
        try:
            items = _rss(GNEWS_RSS, '주지사 데이터센터', params={'q': f'{q} when:1d', 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'})
        except Exception:
            n_fail += 1
            continue
        for x in items:
            title, _, media = x['제목'].rpartition(' - ')
            title = title or x['제목']
            if title in seen or not _re.search(GOV_TITLE, title) or not _re.search(GOV_STATE, title):
                continue
            seen.add(title)
            x.update({'제목': f'{title} ({media})' if media else title, '요약': ''})
            pool.append(x)
        time.sleep(0.3)
    got = sorted(pool, key=lambda x: x['시각(한국)'], reverse=True)[:NEWS_MAX]
    news += got
    msgs.append(f'주지사 데이터센터 {len(got)}건' + (f'(검색어 실패 {n_fail})' if n_fail else ''))
except Exception as e:
    msgs.append(f'주지사 데이터센터 실패({type(e).__name__} {e})')
try:                                    # ⑤ 한국·일본 종목별 — 구글 뉴스 검색, 보유 먼저, 한 종목 최대 ASIA_PER_TICKER건
    asia = u[u['시장'].isin(['한국', '일본']) & (u['구분'] == '개별주')]
    asia = pd.concat([asia[asia['보유/관심'] == '보유'], asia[asia['보유/관심'] != '보유']])
    pool, seen, n_fail = [], set(), 0
    for _, s in asia.iterrows():
        time.sleep(0.3)
        name = s['정식 종목명']
        try:
            items = _rss(GNEWS_RSS, f'{s["시장"]} 종목별', name,
                         params={'q': f'"{name}" when:1d', 'hl': 'ko', 'gl': 'KR', 'ceid': 'KR:ko'})
        except Exception:
            n_fail += 1
            continue
        k = 0
        for x in items:
            title, _, media = x['제목'].rpartition(' - ')
            title = title or x['제목']
            if title in seen or name.replace(' ', '') not in title.replace(' ', ''):   # 제목에 종목명이 있는 것만
                continue
            if _re.search(NEWS_DROP, title):    # 홍보·스포츠·사회공헌 기사 빼기(2026-11-03)
                continue
            if k < ARCHIVE_PER_TICKER:
                ARCHIVE.append(dict(x, 제목=f'{title} ({media})' if media else title, 요약='', 종목=name, 번호=s['번호']))
            seen.add(title)
            x.update({'제목': f'{title} ({media})' if media else title, '요약': '', '보유': s['보유/관심'] == '보유'})
            pool.append(x)
            k += 1
            if k >= ASIA_PER_TICKER:
                break
    pool = sorted(pool, key=lambda x: x['시각(한국)'], reverse=True)
    pool = sorted(pool, key=lambda x: not x.pop('보유'))
    got = sorted(pool[:ASIA_MAX], key=lambda x: x['시각(한국)'], reverse=True)
    news += got
    msgs.append(f'한국·일본 종목별 {len(got)}건' + (f'(조회 실패 {n_fail}종목)' if n_fail else ''))
except Exception as e:
    msgs.append(f'한국·일본 종목별 실패({type(e).__name__} {e})')
f_use = f'{KEEP}/00_API사용량.csv'
use_old = pd.read_csv(f_use, dtype={'날짜': str}, encoding='utf-8-sig') if os.path.exists(f_use) else pd.DataFrame(columns=['날짜', '서비스', '건수'])
use_old = use_old[use_old['날짜'] != TODAY]       # 같은 날 다시 돌리면 그날 줄은 새로 쓴다


def _used(svc):
    """이번 달(또는 오늘)까지 쓴 양: 누적 파일 + 오늘 지금까지"""
    per = API_LIMITS[svc][0]
    pre = TODAY[:6] if per == '월' else TODAY
    past = use_old[(use_old['서비스'] == svc) & use_old['날짜'].astype(str).str.startswith(pre)]['건수'].sum()
    return int(past) + USAGE.get(svc, 0)


def _room(svc):
    """한도의 API_STOP_PCT% 전이면 True"""
    return _used(svc) < API_LIMITS[svc][1] * API_STOP_PCT / 100


def _use(svc, n=1):
    USAGE[svc] = USAGE.get(svc, 0) + n


def _tag(nm):
    """공시 제목에 붙일 꼬리표: 주주환원은 의장이 특히 챙김(2026-10-31)"""
    if _re.search(DART_RETURN, nm):
        return '[주주환원] '
    if _re.search(DART_CAPITAL, nm):
        return '[자본·지배구조] '
    return ''


try:                                    # ⑥ DART 공시 제목 — 한국 개별주의 어제·오늘 공시 전부(주주환원 꼬리표)
    if not SEC.get('DART_KEY'):
        raise RuntimeError('DART_KEY 없음')
    cpath = f'{KEEP}/00_DART_고유번호.csv'
    if os.path.exists(cpath):
        cc6 = pd.read_csv(cpath, dtype=str).set_index('stock_code')['corp_code']
    elif 'corp_codes' in globals():
        cc6 = corp_codes().set_index('stock_code')['corp_code']
    else:
        raise RuntimeError('DART 고유번호 목록 없음(블록 6을 한 번 돌려야 함)')
    kr6 = u[(u['시장'] == '한국') & (u['구분'] == '개별주')]
    kr6 = pd.concat([kr6[kr6['보유/관심'] == '보유'], kr6[kr6['보유/관심'] != '보유']])
    bgn6 = (today - dt.timedelta(days=1)).strftime('%Y%m%d')
    pool, n_fail = [], 0
    for _, s in kr6.iterrows():
        corp = cc6.get(s['코드'])
        if not corp:
            continue
        time.sleep(0.3)
        try:
            j = requests.get('https://opendart.fss.or.kr/api/list.json', timeout=30,
                             params={'crtfc_key': SEC['DART_KEY'], 'corp_code': corp, 'bgn_de': bgn6,
                                     'end_de': TODAY, 'page_count': 100}).json()
        except Exception:
            n_fail += 1
            continue
        for x in j.get('list') or []:
            nm = _re.sub(r'\s+', ' ', x.get('report_nm', '')).strip()
            if _re.search(DART_SKIP, nm):
                continue
            d = x['rcept_dt']
            row = {'시각(한국)': f'{d[4:6]}-{d[6:8]} --:--', '제목': _tag(nm) + nm + (f' (제출 {x["flr_nm"]})' if x.get('flr_nm') and x['flr_nm'] != x.get('corp_name') else ''),
                   '요약': '', '링크': f'https://dart.fss.or.kr/dsaf001/main.do?rcpNo={x["rcept_no"]}',
                   '출처': 'DART 공시', '종목': s['정식 종목명']}
            ARCHIVE.append(dict(row, 번호=s['번호']))
            pool.append(dict(row, 보유=s['보유/관심'] == '보유', 환원=bool(_tag(nm))))
    pool = sorted(pool, key=lambda x: (not x.pop('환원'), not x.pop('보유')))    # 주주환원·자본 먼저, 그다음 보유
    got = pool[:DART_MAX]
    news += got
    msgs.append(f'DART 공시 {len(got)}건(주주환원·자본 {sum(1 for x in got if x["제목"].startswith("["))})'
                + (f'(조회 실패 {n_fail}종목)' if n_fail else ''))
except Exception as e:
    msgs.append(f'DART 공시 실패({type(e).__name__} {e})')

try:                                    # ⑦ 네이버 뉴스 검색 API — 한국 개별주, 제목+요약
    if not (SEC.get('NAVER_CLIENT_ID') and SEC.get('NAVER_CLIENT_SECRET')):
        raise RuntimeError('네이버 키 없음')
    # 2026-07 이후 새 키는 네이버 클라우드 NAVER API HUB에서만 나온다(개발자센터 신규 신청 종료).
    # HUB 주소를 먼저 쓰고, 안 되면 옛 개발자센터 주소로 한 번 더 시도한다(옛 방식은 2027-06 종료 예정).
    NAVER_EPS = [('https://naverapihub.apigw.ntruss.com/search/v1/news',
                  {'X-NCP-APIGW-API-KEY-ID': SEC['NAVER_CLIENT_ID'], 'X-NCP-APIGW-API-KEY': SEC['NAVER_CLIENT_SECRET']}),
                 ('https://openapi.naver.com/v1/search/news.json',
                  {'X-Naver-Client-Id': SEC['NAVER_CLIENT_ID'], 'X-Naver-Client-Secret': SEC['NAVER_CLIENT_SECRET']})]
    if not _room('네이버 검색'):
        raise RuntimeError('오늘 무료 한도 거의 다 씀')
    kr7 = u[(u['시장'] == '한국') & (u['구분'] == '개별주')]
    kr7 = pd.concat([kr7[kr7['보유/관심'] == '보유'], kr7[kr7['보유/관심'] != '보유']])
    pool, seen, n_fail = [], set(), 0
    for _, s in kr7.iterrows():
        time.sleep(0.15)
        name = s['정식 종목명']
        try:
            for ep, hdr in list(NAVER_EPS):
                _use('네이버 검색')
                r = requests.get(ep, headers=hdr, timeout=30, params={'query': f'"{name}"', 'display': 30, 'sort': 'date'})
                if r.status_code in (401, 403, 404) and len(NAVER_EPS) > 1:
                    NAVER_EPS.remove((ep, hdr))      # 이 주소는 이 키로 안 됨 → 다음 주소로, 이후 종목도 그 주소만
                    continue
                break
            r.raise_for_status()
            items = r.json().get('items') or []
        except Exception:
            n_fail += 1
            continue
        k = 0
        for it in items:
            try:
                t = parsedate_to_datetime(it.get('pubDate')).astimezone(KST)
            except Exception:
                continue
            title = _text(it.get('title'))
            if t < since or title in seen or name.replace(' ', '') not in title.replace(' ', ''):
                continue
            seen.add(title)
            x = {'시각(한국)': t.strftime('%m-%d %H:%M'), '제목': title, '요약': _text(it.get('description'))[:200],
                 '링크': it.get('originallink') or it.get('link') or '', '출처': '네이버 종목별', '종목': name}
            if k < ARCHIVE_PER_TICKER:
                ARCHIVE.append(dict(x, 번호=s['번호']))
            if k < NAVER_PER_TICKER:
                pool.append(dict(x, 보유=s['보유/관심'] == '보유'))
            k += 1
    pool = sorted(pool, key=lambda x: x['시각(한국)'], reverse=True)
    pool = sorted(pool, key=lambda x: not x.pop('보유'))
    got = sorted(pool[:NAVER_MAX], key=lambda x: x['시각(한국)'], reverse=True)
    news += got
    msgs.append(f'네이버 종목별 {len(got)}건' + (f'(조회 실패 {n_fail}종목)' if n_fail else ''))
except Exception as e:
    msgs.append(f'네이버 종목별 건너뜀({type(e).__name__} {e})')

try:                                    # ⑧ Finnhub 종목 뉴스 — 미국 개별주, 제목+요약 (무료 분당 60회)
    if not SEC.get('FINNHUB_KEY'):
        raise RuntimeError('FINNHUB_KEY 없음')
    us8 = u[(u['시장'] == '미국') & (u['구분'] == '개별주')]
    us8 = pd.concat([us8[us8['보유/관심'] == '보유'], us8[us8['보유/관심'] != '보유']])
    pool, seen, n_fail = [], set(), 0
    for _, s in us8.iterrows():
        time.sleep(1.1)
        try:
            _use('Finnhub')
            r = requests.get('https://finnhub.io/api/v1/company-news', timeout=30,
                             params={'symbol': s['yfinance 티커'], 'from': (today - dt.timedelta(days=1)).isoformat(),
                                     'to': today.isoformat(), 'token': SEC['FINNHUB_KEY']})
            r.raise_for_status()
            items = r.json() or []
        except Exception:
            n_fail += 1
            continue
        k = 0
        for it in sorted(items, key=lambda z: z.get('datetime') or 0, reverse=True):
            t = dt.datetime.fromtimestamp(it.get('datetime') or 0, KST)
            title = _text(it.get('headline'))
            if t < since or not title or title in seen:
                continue
            seen.add(title)
            media = it.get('source') or ''
            x = {'시각(한국)': t.strftime('%m-%d %H:%M'), '제목': f'{title} ({media})' if media else title,
                 '요약': _text(it.get('summary'))[:300], '링크': it.get('url') or '', '출처': 'Finnhub 종목별',
                 '종목': s['정식 종목명']}
            if k < ARCHIVE_PER_TICKER:
                ARCHIVE.append(dict(x, 번호=s['번호']))
            if k < FINNHUB_PER_TICKER:
                pool.append(dict(x, 보유=s['보유/관심'] == '보유'))
            k += 1
    pool = sorted(pool, key=lambda x: x['시각(한국)'], reverse=True)
    pool = sorted(pool, key=lambda x: not x.pop('보유'))
    got = sorted(pool[:FINNHUB_MAX], key=lambda x: x['시각(한국)'], reverse=True)
    news += got
    msgs.append(f'Finnhub 종목별 {len(got)}건' + (f'(조회 실패 {n_fail}종목)' if n_fail else ''))
except Exception as e:
    msgs.append(f'Finnhub 종목별 건너뜀({type(e).__name__} {e})')

try:                                    # ⑨ 사건 검색(Tavily) — 전일 ±MOVE_PCT% 넘게 움직인 개별주만, 이유를 찾는다
    if not SEC.get('TAVILY_KEY'):
        raise RuntimeError('TAVILY_KEY 없음')
    f_px = f'{DAY}/{TODAY}_시세.csv'
    if not os.path.exists(f_px):
        raise RuntimeError('오늘 시세 파일 없음(블록 1)')
    px = pd.read_csv(f_px, encoding='utf-8-sig')
    px = px[(px['구분'] == '개별주') & (px['등락률(%)'].abs() >= MOVE_PCT)]
    px = px.reindex(px['등락률(%)'].abs().sort_values(ascending=False).index).head(MOVE_MAX)
    got, n_fail = [], 0
    for _, s in px.iterrows():
        name, chg, up = s['정식 종목명'], s['등락률(%)'], s['등락률(%)'] > 0
        if s['시장'] == '미국':
            q = f'{name} ({s["yfinance 티커"]}) stock {"jumps" if up else "falls"} why'
        else:
            q = f'{name} 주가 {"급등" if up else "급락"} 이유'
        if not _room('Tavily'):
            msgs.append('사건 검색: 이번 달 Tavily 무료 한도 거의 다 써서 쉼')
            break
        try:
            _use('Tavily')
            r = requests.post('https://api.tavily.com/search', timeout=60,
                              headers={'Authorization': f'Bearer {SEC["TAVILY_KEY"]}'},
                              json={'query': q, 'topic': 'news', 'days': 2, 'max_results': 3, 'search_depth': 'basic'})
            r.raise_for_status()
            items = r.json().get('results') or []
        except Exception:
            n_fail += 1
            continue
        for it in items:
            try:
                hm = parsedate_to_datetime(it.get('published_date')).astimezone(KST).strftime('%m-%d %H:%M')
            except Exception:
                hm = (it.get('published_date') or '')[:16]
            x = {'시각(한국)': hm, '제목': f'({chg:+.1f}%) ' + _text(it.get('title')),
                 '요약': _text(it.get('content'))[:300], '링크': it.get('url') or '', '출처': '사건 검색',
                 '종목': name}
            got.append(x)
            ARCHIVE.append(dict(x, 번호=s['번호']))
    news += got
    msgs.append(f'사건 검색 {len(px)}종목 {len(got)}건' + (f'(검색 실패 {n_fail})' if n_fail else ''))
except Exception as e:
    msgs.append(f'사건 검색 건너뜀({type(e).__name__} {e})')
try:                                    # 무료 한도 사용량 누적: 00_누적/00_API사용량.csv, 80% 넘으면 경고
    use_new = pd.DataFrame([{'날짜': TODAY, '서비스': k, '건수': v} for k, v in USAGE.items()], columns=['날짜', '서비스', '건수'])
    pd.concat([use_old, use_new], ignore_index=True).to_csv(f_use, index=False, encoding='utf-8-sig')
    for svc, (per, lim) in API_LIMITS.items():
        n = _used(svc)
        if n >= lim * API_WARN_PCT / 100:
            API_WARN.append(f'{svc} 무료 한도 {per} {lim:,}회 중 {n:,}회 사용({n / lim:.0%})'
                            + (' — 한도 직전이라 쉬는 중' if n >= lim * API_STOP_PCT / 100 else ''))
    msgs.append('API 사용 ' + ', '.join(f'{k} {_used(k):,}/{API_LIMITS[k][1]:,}({API_LIMITS[k][0]})' for k in USAGE)
                + (f' | 경고 {len(API_WARN)}' if API_WARN else ''))
except Exception as e:
    msgs.append(f'API 사용량 기록 실패({type(e).__name__} {e})')
try:                                    # 기업 카드용 누적: 00_누적/00_종목뉴스.csv (링크·제목 중복 제거, ARCHIVE_DAYS일 보관)
    f_arc = f'{KEEP}/00_종목뉴스.csv'
    arc_cols = ['날짜', '번호', '종목', '시각(한국)', '제목', '요약', '출처', '링크']
    new_arc = pd.DataFrame([dict(x, 날짜=TODAY) for x in ARCHIVE], columns=arc_cols)
    old_arc = pd.read_csv(f_arc, dtype=str, encoding='utf-8-sig') if os.path.exists(f_arc) else pd.DataFrame(columns=arc_cols)
    arc = pd.concat([old_arc, new_arc], ignore_index=True).drop_duplicates(['번호', '링크']).drop_duplicates(['번호', '제목'])
    cut = (NOW - dt.timedelta(days=ARCHIVE_DAYS)).strftime('%Y%m%d')
    arc = arc[arc['날짜'].astype(str) >= cut].sort_values(['날짜', '시각(한국)'], ascending=False)
    arc.to_csv(f_arc, index=False, encoding='utf-8-sig')
    msgs.append(f'종목뉴스 누적 +{len(arc) - len(old_arc)}건(전체 {len(arc)})')
except Exception as e:
    msgs.append(f'종목뉴스 누적 실패({type(e).__name__} {e})')
pd.DataFrame(news, columns=NEWS_COLS).to_csv(f'{DAY}/{TODAY}_뉴스.csv', index=False, encoding='utf-8-sig')
news_msg = ', '.join(msgs)

# (나) 국내 실적발표 일정 — DART 거래소공시 ----------------------------------
DATE_RE = _re.compile(r'(20\d\d)\s*[-./년]\s*(\d{1,2})\s*[-./월]\s*(\d{1,2})')
TIME_RE = _re.compile(r'(\d{1,2})\s*(?::|시)\s*(\d{2})?')


def _dart(api, params, raw=False):
    time.sleep(0.3)
    r = requests.get(f'https://opendart.fss.or.kr/api/{api}', params={'crtfc_key': SEC['DART_KEY'], **params}, timeout=30)
    return r.content if raw else r.json()


def _doc_text(rcept_no):
    z = _zip.ZipFile(io.BytesIO(_dart('document.xml', {'rcept_no': rcept_no}, raw=True)))
    return ' '.join(_text(z.read(n).decode('utf-8', 'ignore')) for n in z.namelist())


def _when(text):
    """본문에서 오늘 이후 가장 이른 날짜와 그 뒤 40자 안의 시각"""
    best = None
    for m in DATE_RE.finditer(text):
        try:
            d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
        if d < today or (best and (d > best[0] or (d == best[0] and best[1]))):
            continue            # 더 이른 날짜를 이미 찾았거나, 같은 날짜에 시각까지 찾았으면 넘어간다
        tm = TIME_RE.search(text[m.end():m.end() + 40])
        hm = f'{int(tm.group(1)):02d}:{tm.group(2) or "00"}' if tm and int(tm.group(1)) < 24 else ''
        best = (d, hm)
    return best


kr_msg = ''
try:
    if not SEC.get('DART_KEY'):
        raise RuntimeError('DART_KEY 없음')
    cpath = f'{KEEP}/00_DART_고유번호.csv'
    if os.path.exists(cpath):
        cc = pd.read_csv(cpath, dtype=str).set_index('stock_code')['corp_code']
    elif 'corp_codes' in globals():
        cc = corp_codes().set_index('stock_code')['corp_code']
    else:
        raise RuntimeError('DART 고유번호 목록 없음(블록 6을 한 번 돌려야 함)')
    kr = u[(u['시장'] == '한국') & (u['구분'] == '개별주')]
    bgn = (today - dt.timedelta(days=40)).strftime('%Y%m%d')
    n_found = 0
    for _, s in kr.iterrows():
        corp = cc.get(s['코드'])
        if not corp:
            continue
        j = _dart('list.json', {'corp_code': corp, 'bgn_de': bgn, 'end_de': TODAY, 'pblntf_ty': 'I', 'page_count': 100})
        seen = set()
        for x in j.get('list') or []:
            nm = x.get('report_nm', '')
            rdate = dt.datetime.strptime(x['rcept_dt'], '%Y%m%d').date()
            if '잠정' in nm and '실적' in nm and rdate >= today - dt.timedelta(days=1):
                if ('잠정', rdate) in seen:      # 자회사 실적 공시가 여러 건 나와도 한 줄만
                    continue
                seen.add(('잠정', rdate))
                _add(rdate, '', '한국 실적', s['정식 종목명'], f'공시됨: {nm.strip()}', f'DART {x["rcept_no"]}', s['보유/관심'])
                n_found += 1
                continue
            if not ('기업설명회' in nm or '결산실적공시' in nm or '실적발표' in nm):
                continue
            try:
                w = _when(_doc_text(x['rcept_no']))
            except Exception as e:
                print(f'  DART 본문 실패 {s["정식 종목명"]} {x["rcept_no"]}: {e}')
                continue
            if not w or w[0] > until or w[0] < today or (w[0], s['코드']) in seen:   # 지난 IR 날짜는 일정에서 뺀다
                continue
            seen.add((w[0], s['코드']))
            _add(w[0], w[1], '한국 실적', s['정식 종목명'], nm.strip(), f'DART {x["rcept_no"]}', s['보유/관심'],
                 check='확정(DART 공시)')
            n_found += 1
    kr_msg = f'국내 실적 일정 {n_found}건'
except Exception as e:
    kr_msg = f'국내 실적 일정 실패({type(e).__name__} {e})'

# (다) 미국·일본 종목 실적발표 — 야후 -------------------------------------------
yf_msg = ''
# 두 번째 출처: Finnhub 실적 달력(무료 키 FINNHUB_KEY). 야후 날짜와 대조해 확정/예상/다름을 붙이고,
# 간밤 발표 종목은 매출 실제·예상도 함께 적는다. 키가 없으면 야후 하나로만(확인 칸 '예상(야후만)').
FH = {}
if SEC.get('FINNHUB_KEY'):
    try:
        r = get('https://finnhub.io/api/v1/calendar/earnings', retry=1,
                params={'from': (today - dt.timedelta(days=3)).isoformat(), 'to': until.isoformat(), 'token': SEC['FINNHUB_KEY']})
        for x in ((r.json() if r is not None else {}) or {}).get('earningsCalendar') or []:
            if x.get('symbol') and x.get('date'):
                FH.setdefault(x['symbol'], []).append(x)
    except Exception as e:
        print(f'  Finnhub 실적 달력 실패: {e}')


def _fh_check(sym, d):
    """야후 미국 날짜 d를 Finnhub와 대조 → (확인 글, Finnhub 행)"""
    if not FH:
        return '예상(야후만, Finnhub 없음)', None
    rows = FH.get(sym) or []
    for x in rows:
        if x['date'] == d.isoformat():
            return '확정(야후·Finnhub 일치)', x
    if rows:
        return f'날짜 다름(야후 {d:%m/%d}, Finnhub {rows[0]["date"][5:].replace("-", "/")})', rows[0]
    return '예상(야후만)', None


def _fh_numbers(x):
    """Finnhub 한 줄 → '매출 실제 ○ / 예상 ○' (십억 달러)"""
    if not x:
        return ''
    ra, re_ = x.get('revenueActual'), x.get('revenueEstimate')
    if ra:
        return f' · 매출 실제 {ra / 1e9:.2f}B$' + (f' / 예상 {re_ / 1e9:.2f}B$' if re_ else '') + '(Finnhub)'
    return ''


try:
    n_found, n_fail = 0, 0
    for _, s in u[(u['시장'].isin(['미국', '일본'])) & (u['구분'] == '개별주')].iterrows():
        time.sleep(0.4)
        try:
            tk = yf.Ticker(s['yfinance 티커'])
            hits = {}           # 미국(현지) 날짜 → (한국 날짜, 한국 시각, 내용)
            try:
                ed = tk.get_earnings_dates(limit=8)
            except Exception:
                ed = None
            if ed is not None and len(ed):
                for ts, row in ed.iterrows():
                    k = pd.Timestamp(ts)
                    k = k.tz_localize(ET_TZ) if k.tzinfo is None else k
                    kk = k.tz_convert(KST)
                    hm = '' if (k.hour, k.minute) == (0, 0) else kk.strftime('%H:%M') + '경'   # 야후 시각은 정각 반올림(실제 06:05·06:30 등)
                    eps, est = row.get('Reported EPS'), row.get('EPS Estimate')
                    if today <= kk.date() <= until and kk <= NOW and pd.notna(eps):
                        what = f'간밤 발표: EPS 실제 {eps:.2f} / 예상 {est:.2f}' if pd.notna(est) else f'간밤 발표: EPS 실제 {eps:.2f}'
                        hits[k.date()] = (kk.date(), hm, what + '(야후)')
                    elif today <= kk.date() <= until:
                        hits[k.date()] = (kk.date(), hm, '실적 발표(야후 예정일)')
            try:                # 야후 calendar(날짜만) — get_earnings_dates에 빠진 종목을 메운다
                cal = tk.calendar or {}
            except Exception:
                cal = {}
            for d in (cal.get('Earnings Date') or []):
                if d in hits:
                    continue
                if d == today - dt.timedelta(days=1) and s['시장'] == '미국':   # 미국 날짜 어제 = 한국 기준 간밤 발표
                    hits[d] = (today, '', f'간밤 발표(미국 {d:%m-%d}, 야후 calendar) — 결과는 뉴스 확인')
                elif today <= d <= until:
                    hits[d] = (d, '', '실적 발표(야후 calendar, 미국 날짜·시각 미정)')
            sym = str(s['yfinance 티커'])
            if s['시장'] == '미국' and not hits and FH.get(sym):   # 야후에 없고 Finnhub에만 있는 날짜
                for x in FH[sym]:
                    fd = dt.date.fromisoformat(x['date'])
                    kd = fd + dt.timedelta(days=1) if x.get('hour') == 'amc' else fd   # 장 뒤 발표 = 한국 다음 날 아침
                    if today <= kd <= until:
                        hits[fd] = (kd, '', '실적 발표(Finnhub 예정일, 야후에 없음)')
            for d in sorted(hits)[:2]:
                day_k, hm, what = hits[d]
                if s['시장'] == '미국':
                    chk, x = _fh_check(sym, d)
                    if '(Finnhub 예정일' in what:
                        chk = '예상(Finnhub만)'
                    if what.startswith('간밤 발표'):
                        what += _fh_numbers(x)
                else:
                    chk = '예상(야후만)'
                _add(day_k, hm, f'{s["시장"]} 실적', s['정식 종목명'], what, '야후' + ('·Finnhub' if FH else ''), s['보유/관심'], check=chk)
                n_found += 1
        except Exception as e:
            n_fail += 1
            print(f'  야후 실적일 실패 {s["yfinance 티커"]}: {e}')
    yf_msg = f'미국·일본 실적 일정 {n_found}건' + (f'(조회 실패 {n_fail})' if n_fail else '')
except Exception as e:
    yf_msg = f'미국·일본 실적 일정 실패({type(e).__name__} {e})'

# (라) 미국 경제지표 발표 — FRED 발표 달력 ------------------------------------
us_msg = ''
try:
    if not SEC.get('FRED_KEY'):
        raise RuntimeError('FRED_KEY 없음')
    r = get('https://api.stlouisfed.org/fred/releases/dates', retry=1,
            params={'api_key': SEC['FRED_KEY'], 'file_type': 'json', 'realtime_start': today.isoformat(),
                    'realtime_end': until.isoformat(), 'include_release_dates_with_no_data': 'true',
                    'sort_order': 'asc', 'limit': 1000})
    if r is None:
        raise RuntimeError('FRED 응답 없음')
    n_found, seen = 0, set()
    rel = [(x['date'], x.get('release_name', ''), 'FRED 발표 달력') for x in r.json().get('release_dates', [])
           if x.get('release_name') in US_RELEASES]
    rel += [(d, 'FOMC', '연준 FOMC 일정') for d in FOMC_DAYS]
    for day_s, name, src in rel:
        ko, hm = US_RELEASES[name] if name in US_RELEASES else ('FOMC 금리 결정', '14:00')
        if (day_s, ko) in seen:
            continue
        seen.add((day_s, ko))
        d = dt.date.fromisoformat(day_s)
        h, m = map(int, hm.split(':'))
        kst = dt.datetime(d.year, d.month, d.day, h, m, tzinfo=ET_TZ).astimezone(KST)
        if not today <= kst.date() <= until:
            continue
        SCHED.append({'날짜': kst.strftime('%Y-%m-%d'), '요일': WD[kst.weekday()],
                      '시각(한국)': kst.strftime('%H:%M') + ' 통상', '구분': '미국 지표', '대상': ko,
                      '보유/관심': '', '확인': '확정(' + src + ')', '내용': name, '출처': src})
        n_found += 1
    us_msg = f'미국 지표 일정 {n_found}건'
except Exception as e:
    us_msg = f'미국 지표 일정 실패({type(e).__name__} {e})'

cols = ['날짜', '요일', '시각(한국)', '구분', '대상', '보유/관심', '확인', '내용', '출처']
sched = pd.DataFrame(SCHED, columns=cols)
if len(sched):
    sched = sched.sort_values(['날짜', '시각(한국)', '구분']).reset_index(drop=True)
sched.to_csv(f'{DAY}/{TODAY}_일정.csv', index=False, encoding='utf-8-sig')
log(f'[9 뉴스·일정] {news_msg} | {kr_msg} | {yf_msg} | {us_msg} (일정은 오늘부터 {SCHED_DAYS}일)')
