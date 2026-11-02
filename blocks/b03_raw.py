# ======================================================================
# [블록 3] 원자료 — 매크로(블록 4)·리스크(블록 5)·체크리스트(블록 8)가 쓰는 시계열을 한꺼번에 받는다
#   하는 일  : 숫자를 받아 메모리에 들고만 있다. 표로 정리하고 저장하는 일은 블록 4·5·8이 한다.
#              (가) 야후: 지수 7개, 환율 3개, 원자재 3개, VIX·VIX3M·MOVE, 미국 10·30년 — 상장 이후 전체 일봉
#              (나) FRED: 금리·정책금리·물가·성장·고용·신용·스트레스·유동성 — 작년 1월부터
#              (다) 뉴욕연준 SOFR, 일본 재무성 10년 국채(전체 이력), CNN 공포탐욕 원문
#   소스     : 야후(키 없음), FRED API(FRED_KEY, 간격 0.6초), 뉴욕연준·재무성·CNN(키 없음)
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_연준매크로.csv (FRED 시리즈별 최신값·기준일·직전값)
#              메모리: YS(야후 시계열), FS(FRED 시계열), JP10(일본 10년), SOFR_NY, CNN, 계산 함수들
#   고칠 곳  : 받을 지표를 늘리거나 줄일 때는 YF_SERIES, FRED_SERIES 표
#   실패하면 : 소스별로 건너뛰고 점검 파일에 남긴다(그 지표는 다음 블록에서 '데이터 없음')
# ======================================================================
YF_SERIES = {   # 이름 → 야후 티커
    'S&P500': '^GSPC', '나스닥': '^IXIC', '코스피': '^KS11', '니케이225': '^N225',
    '필라델피아 반도체(SOX)': '^SOX', '대만 가권': '^TWII', '유로스톡스50': '^STOXX50E',
    '원/달러': 'KRW=X', '엔/달러': 'JPY=X', '달러지수': 'DX-Y.NYB',
    'WTI': 'CL=F', '구리': 'HG=F', '금': 'GC=F',
    'VIX': '^VIX', 'VIX3M': '^VIX3M', 'MOVE': '^MOVE', '미국 10년': '^TNX', '미국 30년': '^TYX',
}
FRED_SERIES = [  # (FRED ID, 이름, 구분)
    ('DGS3MO', '미국 3개월 국채', '금리'), ('DGS2', '미국 2년 국채', '금리'),
    ('DGS10', '미국 10년 국채', '금리'), ('DGS30', '미국 30년 국채', '금리'),
    ('DFII10', '미국 10년 실질금리(TIPS)', '금리'),
    ('DFEDTARU', '기준금리 상단', '정책'), ('DFEDTARL', '기준금리 하단', '정책'),
    ('EFFR', '실효 연방기금금리', '정책'), ('IORB', '지급준비금 이자율(IORB)', '정책'), ('SOFR', 'SOFR(FRED)', '정책'),
    ('CPIAUCSL', 'CPI', '물가'), ('CPILFESL', '근원 CPI', '물가'), ('PCEPILFE', '근원 PCE', '물가'),
    ('PCETRIM12M159SFRBDAL', '댈러스 연준 절사평균 PCE(전년비)', '물가'),
    ('T5YIE', '5년 BEI', '물가 기대'), ('EXPINF1YR', '클리블랜드 1년 기대인플레', '물가 기대'),
    ('EXPINF10YR', '클리블랜드 10년 기대인플레', '물가 기대'),
    ('GDPNOW', '애틀랜타 연준 GDPNow', '성장'), ('UNRATE', '실업률', '고용'), ('PAYEMS', '비농업 고용(천명)', '고용'),
    ('ICSA', '신규 실업수당 청구', '고용'), ('SAHMREALTIME', '샴 룰 침체 지표', '고용'),
    ('RECPROUSM156N', '경기침체 확률', '경기'),
    ('T10Y2Y', '장단기 금리차(10년-2년)', '금리차'), ('T10Y3M', '장단기 금리차(10년-3개월)', '금리차'),
    ('BAMLH0A0HYM2', '하이일드 스프레드', '신용'), ('BAMLC0A0CM', '투자등급 스프레드', '신용'),
    ('STLFSI4', '세인트루이스 연준 금융스트레스', '금융스트레스'), ('KCFSI', '캔자스시티 연준 금융스트레스', '금융스트레스'),
    ('NFCI', '시카고 연준 금융여건지수', '금융여건'), ('ANFCI', '시카고 연준 조정 금융여건지수', '금융여건'),
    ('WALCL', '연준 총자산(백만$)', '유동성'), ('WTREGEN', 'TGA 잔고(백만$)', '유동성'),
    ('RRPONTSYD', '역레포 잔고(십억$)', '유동성'),
]

# ---- 계산 함수 (블록 4·5·8이 같이 쓴다) ----------------------------------------
def last(s):
    """시계열의 (최신값, 기준일 'YYYY-MM-DD') 또는 (None, None)"""
    if s is None or len(s) == 0:
        return None, None
    return float(s.iloc[-1]), s.index[-1].strftime('%Y-%m-%d')


def at_or_before(s, when):
    """when 당일 또는 그 이전 가장 가까운 값"""
    if s is None or len(s) == 0:
        return None
    x = s[s.index <= pd.Timestamp(when)]
    return float(x.iloc[-1]) if len(x) else None


def change(s, base, pct=True):
    """최신값과 base 날짜 값의 차이. pct=True면 %, 아니면 차이(금리는 %p)"""
    v, d = last(s)
    b = at_or_before(s, base)
    if v is None or b is None or (pct and b == 0):
        return None
    return round((v / b - 1) * 100, 2) if pct else round(v - b, 3)


def ytd(s, pct=True):
    v, d = last(s)
    return change(s, f'{int(d[:4]) - 1}-12-31', pct) if d else None


def m1(s, pct=True):
    v, d = last(s)
    return change(s, pd.Timestamp(d) - pd.DateOffset(months=1), pct) if d else None


def yoy(s):
    """월간 지수의 전년비(%)"""
    v, d = last(s)
    b = at_or_before(s, pd.Timestamp(d) - pd.DateOffset(years=1)) if d else None
    return round((v / b - 1) * 100, 2) if v and b else None


def prev_obs(s, n=1):
    return float(s.iloc[-1 - n]) if s is not None and len(s) > n else None


# (가) 야후 -----------------------------------------------------------------
YS = {}
try:
    d = yf.download(list(YF_SERIES.values()), period='max', interval='1d', auto_adjust=False,
                    group_by='ticker', threads=False, progress=False)
    for k, t in YF_SERIES.items():
        try:
            s = d[t]['Close'].dropna()
            s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
            if len(s):
                YS[k] = s
        except Exception:
            pass
    # 100엔당 원 = 원/달러 ÷ 엔/달러 × 100 (같은 날짜끼리)
    if '원/달러' in YS and '엔/달러' in YS:
        x = pd.concat([YS['원/달러'], YS['엔/달러']], axis=1, join='inner').dropna()
        YS['100엔당 원'] = (x.iloc[:, 0] / x.iloc[:, 1] * 100).round(2)
except Exception as e:
    print('  야후 실패:', e)
# (가-2) 네이버 지수: 네이버 증권 일봉(최근 약 6개월)으로 야후 값을 덮어쓴다. 네이버가 막히면 야후 그대로.
#   (2026-11-02 의장 "네이버가 정확하고 좋다, 막히면 야후로". 공식 API가 아니라 네이버 화면이 쓰는 주소라 바뀔 수 있음)
#   야후의 긴 이력(사상 최고·50일 이격도용) 위에 네이버 날짜를 겹쳐 쓴다(같은 날짜는 네이버 값).
NAVER_IDX = {   # 이름 → (국내/해외, 네이버 코드)
    '코스피': ('domestic', 'KOSPI'), '코스닥': ('domestic', 'KOSDAQ'),
    'S&P500': ('foreign', '.INX'), '나스닥': ('foreign', '.IXIC'), '다우': ('foreign', '.DJI'),
    '필라델피아 반도체(SOX)': ('foreign', '.SOX'), '니케이225': ('foreign', '.N225'), '대만 가권': ('foreign', '.TWII'),
}
YSRC = {k: f'야후 {t}' for k, t in YF_SERIES.items()}
NAVER_FAIL = []
for k, (kind, code) in NAVER_IDX.items():
    try:
        r = requests.get(f'https://api.stock.naver.com/chart/{kind}/index/{code}?periodType=dayCandle',
                         headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://m.stock.naver.com/'}, timeout=15)
        pts = r.json().get('priceInfos') or []
        nv = pd.Series({pd.to_datetime(p['localDate']): float(p['closePrice']) for p in pts if p.get('closePrice')}).sort_index()
        if len(nv) < 5:
            raise ValueError(f'{len(nv)}개')
        old = YS.get(k)
        YS[k] = nv if old is None else pd.concat([old[old.index < nv.index[0]], nv])
        YSRC[k] = f'네이버 {code}' + (' (이전 이력은 야후)' if old is not None else '')
    except Exception as e:
        NAVER_FAIL.append(f'{k}({type(e).__name__})')
if NAVER_FAIL:
    print('  네이버 지수 실패 → 야후 사용:', ', '.join(NAVER_FAIL))
miss_y = [k for k in YF_SERIES if k not in YS]

# (나) FRED -----------------------------------------------------------------
FS = {}
FRED_ROWS = []
try:
    if not SEC.get('FRED_KEY'):
        raise RuntimeError('FRED_KEY 없음')
    start = f'{NOW.year - 2}-01-01'   # 전년비(월간 지표 발표 지연 포함)를 내려면 2년 전부터
    for sid, name, grp in FRED_SERIES:
        r = get('https://api.stlouisfed.org/fred/series/observations', retry=1,
                params={'series_id': sid, 'api_key': SEC['FRED_KEY'], 'file_type': 'json',
                        'observation_start': start})
        time.sleep(0.6)
        obs = [o for o in (r.json().get('observations', []) if r is not None else []) if o['value'] not in ('.', '')]
        if obs:
            FS[sid] = pd.Series([float(o['value']) for o in obs], index=pd.to_datetime([o['date'] for o in obs]))
        v, dd = last(FS.get(sid))
        FRED_ROWS.append({'구분': grp, 'FRED ID': sid, '이름': name, '최신값': v if v is not None else '데이터 없음',
                          '기준일': dd, '직전값': prev_obs(FS.get(sid))})
except Exception as e:
    print('  FRED 실패:', e)
miss_f = [sid for sid, _, _ in FRED_SERIES if sid not in FS]

# 순유동성(조$) = 연준 총자산 − TGA − 역레포 (주간, 연준 총자산 날짜 기준)
NETLIQ = None
if all(k in FS for k in ['WALCL', 'WTREGEN', 'RRPONTSYD']):
    NETLIQ = pd.Series({dd: (FS['WALCL'][dd] - at_or_before(FS['WTREGEN'], dd)) / 1e6 - at_or_before(FS['RRPONTSYD'], dd) / 1e3
                        for dd in FS['WALCL'].index
                        if at_or_before(FS['WTREGEN'], dd) is not None and at_or_before(FS['RRPONTSYD'], dd) is not None})

# (다) 뉴욕연준 SOFR, 일본 10년, CNN ------------------------------------------------
SOFR_NY = (None, None)
r = get('https://markets.newyorkfed.org/api/rates/secured/sofr/last/1.json', retry=1)
if r is not None:
    try:
        x = r.json()['refRates'][0]
        SOFR_NY = (float(x['percentRate']), x['effectiveDate'])
    except Exception as e:
        print('  뉴욕연준 SOFR 형식 오류:', e)

JP10 = None
parts = []
for url in ['https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv',
            'https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv']:
    r = get(url, retry=1)
    if r is None:
        continue
    try:
        x = pd.read_csv(io.StringIO(r.content.decode('utf-8', 'ignore')), skiprows=1)
        x = x[[x.columns[0], '10Y']].copy()
        x['10Y'] = pd.to_numeric(x['10Y'], errors='coerce')
        x.index = pd.to_datetime(x[x.columns[0]], errors='coerce')
        parts.append(x['10Y'][x.index.notna()].dropna())
    except Exception as e:
        print('  일본 재무성 형식 오류:', e)
if parts:
    JP10 = pd.concat(parts)
    JP10 = JP10[~JP10.index.duplicated(keep='last')].sort_index()

CNN = None
r = get('https://production.dataviz.cnn.io/index/fearandgreed/graphdata')
if r is not None:
    try:
        CNN = r.json()
    except Exception as e:
        print('  CNN 형식 오류:', e)

# 저장: 연준매크로.csv (FRED 원자료 + 순유동성 + 뉴욕연준 SOFR)
fm = pd.DataFrame(FRED_ROWS)
if NETLIQ is not None and len(NETLIQ):
    fm.loc[len(fm)] = {'구분': '유동성', 'FRED ID': '계산', '이름': '순유동성(조$) = 총자산 − TGA − 역레포',
                       '최신값': round(NETLIQ.iloc[-1], 3), '기준일': NETLIQ.index[-1].strftime('%Y-%m-%d'),
                       '직전값': round(NETLIQ.iloc[-2], 3) if len(NETLIQ) > 1 else None}
if SOFR_NY[0] is not None:
    fm.loc[len(fm)] = {'구분': '정책', 'FRED ID': '뉴욕연준', '이름': 'SOFR(뉴욕연준)',
                       '최신값': SOFR_NY[0], '기준일': SOFR_NY[1], '직전값': None}
fm['수집시각(KST)'] = stamp()
fm.to_csv(f'{DAY}/{TODAY}_연준매크로.csv', index=False, encoding='utf-8-sig')

log(f'[3 원자료] 야후 {len(YF_SERIES) - len(miss_y)}/{len(YF_SERIES)} (빠짐: {", ".join(miss_y) or "없음"}) | '
    f'FRED {len(FRED_SERIES) - len(miss_f)}/{len(FRED_SERIES)} (빠짐: {", ".join(miss_f) or "없음"}) | '
    f'뉴욕연준 SOFR {"성공" if SOFR_NY[0] is not None else "실패"} | 일본 10년 {"성공" if JP10 is not None else "실패"} | '
    f'CNN {"성공" if CNN else "실패"}')
