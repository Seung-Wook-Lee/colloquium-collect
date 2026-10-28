# ======================================================================
# [블록 9] 간밤 뉴스·오늘 일정 — 뉴스보이가 아침 회의에서 읽는 국제 뉴스와 실적·경제지표 일정
#   하는 일  : (가) 연합뉴스 국제 기사 중 어제 저녁 6시(한국) 이후 올라온 것 최대 NEWS_MAX건
#              (나) 국내 실적발표 일정: 한국 개별주의 DART 거래소공시 중 '기업설명회(IR) 개최'·'결산실적공시 예고'를
#                   찾아 본문에서 날짜·시각을 읽는다. 오늘·어제 나온 '영업(잠정)실적' 공시도 함께 적는다.
#              (다) 미국·일본 종목 실적발표 일정: 야후 실적 발표일(시각은 한국 시각으로 바꿈)
#              (라) 미국 주요 경제지표 발표 일정: FRED 발표 달력(CPI·고용·PCE·GDP·FOMC 등).
#                   FRED에는 발표 시각이 없어 통상 발표 시각(미국 동부)을 한국 시각으로 바꿔 '통상'이라 적는다.
#              일정은 오늘부터 SCHED_DAYS일 안의 것만. 판정은 하지 않는다.
#   소스     : 연합뉴스 RSS(키 없음), DART OpenAPI(DART_KEY), 야후(키 없음), FRED API(FRED_KEY)
#   읽는 것  : 수집데이터/00_누적/00_DART_고유번호.csv (블록 6이 만든 종목코드 → DART 고유번호)
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_뉴스.csv (시각, 제목, 요약, 링크)
#              수집데이터/YYYYMMDD/YYYYMMDD_일정.csv (날짜, 시각, 구분, 대상, 내용, 출처)
#   쓰는 위원: 뉴스보이(간밤 뉴스·오늘 일정), 섹터 위원(담당 종목 실적 일정)
#   고칠 곳  : 뉴스 건수 NEWS_MAX, 일정 기간 SCHED_DAYS, 미국 지표 목록 US_RELEASES, 해마다 FOMC_DAYS
#   실패하면 : 소스별로 건너뛰고 점검 파일에 남긴다
# ======================================================================
import html as _h, re as _re, xml.etree.ElementTree as _ET, zipfile as _zip
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

NEWS_RSS = 'https://www.yna.co.kr/rss/international.xml'
NEWS_MAX = 10
SCHED_DAYS = 7
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


def _add(day, hm, kind, who, what, src, mark=''):
    SCHED.append({'날짜': day.strftime('%Y-%m-%d'), '요일': WD[day.weekday()], '시각(한국)': hm or '미정',
                  '구분': kind, '대상': who, '보유/관심': mark, '내용': what, '출처': src})


# (가) 연합뉴스 국제 -----------------------------------------------------------
news, news_msg = [], ''
try:
    r = get(NEWS_RSS, retry=2)
    if r is None:
        raise RuntimeError('연합뉴스 RSS 응답 없음')
    since = (NOW - dt.timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
    for it in _ET.fromstring(r.content).iter('item'):
        try:
            t = parsedate_to_datetime(it.findtext('pubDate')).astimezone(KST)
        except Exception:
            continue
        if t < since:
            continue
        news.append({'시각(한국)': t.strftime('%m-%d %H:%M'), '제목': _text(it.findtext('title')),
                     '요약': _text(it.findtext('description'))[:160], '링크': (it.findtext('link') or '').strip(),
                     '출처': '연합뉴스 국제'})
    news = sorted(news, key=lambda x: x['시각(한국)'], reverse=True)[:NEWS_MAX]
    pd.DataFrame(news, columns=['시각(한국)', '제목', '요약', '링크', '출처']).to_csv(
        f'{DAY}/{TODAY}_뉴스.csv', index=False, encoding='utf-8-sig')
    news_msg = f'연합뉴스 국제 {len(news)}건'
except Exception as e:
    news_msg = f'연합뉴스 실패({type(e).__name__} {e})'

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
            if not w or w[0] > until or (w[0], s['코드']) in seen:
                continue
            seen.add((w[0], s['코드']))
            _add(w[0], w[1], '한국 실적', s['정식 종목명'], nm.strip(), f'DART {x["rcept_no"]}', s['보유/관심'])
            n_found += 1
    kr_msg = f'국내 실적 일정 {n_found}건'
except Exception as e:
    kr_msg = f'국내 실적 일정 실패({type(e).__name__} {e})'

# (다) 미국·일본 종목 실적발표 — 야후 -------------------------------------------
yf_msg = ''
try:
    n_found, n_fail = 0, 0
    for _, s in u[(u['시장'].isin(['미국', '일본'])) & (u['구분'] == '개별주')].iterrows():
        time.sleep(0.4)
        try:
            tk = yf.Ticker(s['yfinance 티커'])
            ed = tk.get_earnings_dates(limit=8)
            hits = []
            if ed is not None and len(ed):
                for ts in ed.index:
                    k = pd.Timestamp(ts)
                    k = k.tz_localize(ET_TZ) if k.tzinfo is None else k
                    kk = k.tz_convert(KST)
                    if today <= kk.date() <= until:
                        hits.append((kk.date(), '' if (k.hour, k.minute) == (0, 0) else kk.strftime('%H:%M')))
            else:
                cal = tk.calendar or {}
                for d in (cal.get('Earnings Date') or []):
                    if today <= d <= until:
                        hits.append((d, ''))
            for d, hm in sorted(set(hits))[:1]:
                _add(d, hm, f'{s["시장"]} 실적', s['정식 종목명'], '실적 발표(야후 예정일)', '야후', s['보유/관심'])
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
                      '보유/관심': '', '내용': name, '출처': src})
        n_found += 1
    us_msg = f'미국 지표 일정 {n_found}건'
except Exception as e:
    us_msg = f'미국 지표 일정 실패({type(e).__name__} {e})'

cols = ['날짜', '요일', '시각(한국)', '구분', '대상', '보유/관심', '내용', '출처']
sched = pd.DataFrame(SCHED, columns=cols)
if len(sched):
    sched = sched.sort_values(['날짜', '시각(한국)', '구분']).reset_index(drop=True)
sched.to_csv(f'{DAY}/{TODAY}_일정.csv', index=False, encoding='utf-8-sig')
log(f'[9 뉴스·일정] {news_msg} | {kr_msg} | {yf_msg} | {us_msg} (일정은 오늘부터 {SCHED_DAYS}일)')
