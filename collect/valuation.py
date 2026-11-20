# 지수 밸류·등락 계산 — 블록 b09_valuation(07시)과 스트림릿(그날 파일이 없을 때 바로 계산)이 같이 쓴다.
#   2026-11-11 의장: 자문사 C 자료의 세 그림(지수 12개월 선행 P/E 밴드, 필반 200일 이격도, 주요국·미국 지수
#   이달·연초 이후 등락)을 우리 자료로 만들어 스트림릿 맨 위에.
#   (가) 지수 등락: 이달(지난달 마지막 종가 대비)·연초 이후(작년 마지막 종가 대비), %.
#   (나) 필반 200일 이격도: 종가 ÷ 200일 이동평균 × 100 (100 = 200일선). 1995-10-16부터 평균·표준편차.
#   (다) 지수 12개월 선행 P/E: 구성종목마다 12개월 선행 EPS(야후 애널리스트 평균, 이번 회계연도·다음 회계연도를
#        남은 기간 비율로 섞음) → 지수 비중으로 가중한 조화평균(= 지수 시총 ÷ 지수 선행 이익).
#        과거 컨센서스 이력은 무료로 없어 오늘부터 쌓는다. 10년 평균·±1표준편차는 자문사 C(블룸버그) 캡처 값을
#        '참고선'으로만 쓴다(추정치).
import datetime as dt
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

BARS = {   # 묶음 → [(화면 이름, 야후 티커)]  (자문사 C 그림과 같은 지수)
    '주요국': [('상해종합', '000001.SS'), ('EuroStoxx600', '^STOXX'), ('S&P500', '^GSPC'),
             ('Nikkei225', '^N225'), ('KOSPI', '^KS11')],
    '미국': [('다우지수', '^DJI'), ('러셀2000', '^RUT'), ('S&P500', '^GSPC'), ('나스닥', '^IXIC'), ('필반지수', '^SOX')],
}
BAR_COLS = ['묶음', '지수', '티커', '이달', '연초 이후', '종가', '기준일']

DISP_FROM = '1995-10-16'          # 자문사 C 그림과 같은 시작일
DISP_COLS = ['날짜', '종가', '200일선', '이격도']

# 자문사 C(블룸버그, 주간·12개월 선행 EPS 컨센서스) 캡처에서 읽은 값 — 추정치, 참고선으로만 쓴다
REF = {
    'S&P500':   {'평균': 19.2, '+1σ': 21.3, '-1σ': 17.0, '캡처값': 18.1},
    '나스닥100': {'평균': 23.7, '+1σ': 26.9, '-1σ': 20.4, '캡처값': 18.9},
    '필반지수':  {'평균': 19.3, '+1σ': 23.5, '-1σ': 15.0, '캡처값': 15.1},
}
REF_DAY = '2026-11-09'
REF_SRC = '자문사 C(블룸버그) 캡처, 10년 평균·±1표준편차, 추정치'
DISP_REF = {'평균': 105.8, '+1σ': 124.3, '-1σ': 87.3, '캡처값': 92.5}   # 같은 캡처(% → 100 기준으로 바꿈)

# 필라델피아 반도체 지수 구성 30종목(나스닥 공시 기준, 해마다 9월 정기 변경 뒤 점검)
SOX_MEMBERS = ['NVDA', 'AVGO', 'AMD', 'TSM', 'ASML', 'MU', 'QCOM', 'TXN', 'INTC', 'AMAT', 'LRCX', 'KLAC', 'ADI',
               'MRVL', 'NXPI', 'MCHP', 'MPWR', 'ON', 'ARM', 'TER', 'ENTG', 'COHR', 'SWKS', 'QRVO', 'LSCC',
               'MTSI', 'RMBS', 'ONTO', 'AMKR', 'GFS']
PE_INDEX = {'S&P500': 'S&P500', '나스닥100': 'NDX', '필반지수': 'SOX'}
PE_COLS = ['날짜', '지수', '선행PE', '종목수', '받은 종목수', '받은 비중(%)', '방법']
NDX_API = 'https://api.nasdaq.com/api/quote/list-type/nasdaq100'
MEMBER_ERR = {}   # 위키백과 목록을 못 받은 까닭(점검 파일용)
WIKI = {'S&P500': ('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', 'Symbol'),
        '나스닥100': ('https://en.wikipedia.org/wiki/Nasdaq-100', 'Ticker')}


# ---------------------------------------------------------------- (가) 지수 등락
def _close(yf, syms, period):
    d = yf.download(syms, period=period, interval='1d', auto_adjust=False, group_by='ticker', threads=True,
                    progress=False)
    out = {}
    for t in syms:
        try:
            s = (d[t] if isinstance(d.columns, pd.MultiIndex) and t in d.columns.get_level_values(0) else d)['Close']
            s = (s.iloc[:, 0] if isinstance(s, pd.DataFrame) else s).dropna()
            s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
            if len(s):
                out[t] = s.astype(float)
        except Exception:
            pass
    return out


def period_returns(c):
    """종가 → (이달 %, 연초 이후 %, 종가, 기준일). 기준 = 지난달·작년 마지막 거래일 종가."""
    c = c.dropna()
    if not len(c):
        return None, None, None, None
    last = c.index[-1]
    m0 = c[c.index < last.replace(day=1)]
    y0 = c[c.index < pd.Timestamp(last.year, 1, 1)]
    mtd = round((c.iloc[-1] / m0.iloc[-1] - 1) * 100, 2) if len(m0) else None
    ytd = round((c.iloc[-1] / y0.iloc[-1] - 1) * 100, 2) if len(y0) else None
    return mtd, ytd, round(float(c.iloc[-1]), 2), last.strftime('%Y-%m-%d')


def bars(yf, have=None):
    """have = {티커: 종가 시계열}(블록 3이 받아 둔 것) → 등락 표"""
    have = dict(have or {})
    syms = list(dict.fromkeys(t for v in BARS.values() for _, t in v))
    need = [t for t in syms if t not in have or have[t].index[-1] < pd.Timestamp.now() - pd.Timedelta(days=7)]
    if need:
        have.update(_close(yf, need, '2y'))
    rows = []
    for g, lst in BARS.items():
        for nm, t in lst:
            if t in have:
                rows.append(dict(zip(BAR_COLS, [g, nm, t, *period_returns(have[t])])))
    return pd.DataFrame(rows, columns=BAR_COLS)


# ---------------------------------------------------------------- (나) 필반 200일 이격도
def disparity(c):
    """종가(1994~) → 날짜·종가·200일선·이격도(100 기준) 표, DISP_FROM부터"""
    c = c.dropna().astype(float)
    ma = c.rolling(200).mean()
    d = pd.DataFrame({'종가': c, '200일선': ma, '이격도': c / ma * 100}).dropna()
    d = d[d.index >= pd.Timestamp(DISP_FROM)].rename_axis('날짜').reset_index()
    d['날짜'] = d['날짜'].dt.strftime('%Y-%m-%d')
    return d.round({'종가': 2, '200일선': 2, '이격도': 2})[DISP_COLS]


def disp_stats(d):
    v = pd.to_numeric(d['이격도'], errors='coerce').dropna()
    m, s = float(v.mean()), float(v.std())
    return {'평균': m, '+1σ': m + s, '-1σ': m - s, '현재': float(v.iloc[-1])}


def sox_disparity(yf):
    return disparity(_close(yf, ['^SOX'], 'max')['^SOX'])


# ---------------------------------------------------------------- (다) 지수 12개월 선행 P/E
def members(get, name, cache=None):
    """위키백과 구성종목 표 → 야후 티커 목록. 못 받으면 cache(이전 목록)."""
    if name == '필반지수':
        return list(SOX_MEMBERS)
    url, col = WIKI[name]
    MEMBER_ERR[name] = ''
    try:
        import io
        r = get(url)
        lo = 90 if name == '나스닥100' else 400
        for t in pd.read_html(io.StringIO(r.text)):
            if isinstance(t.columns, pd.MultiIndex):
                t.columns = [c[-1] for c in t.columns]
            t.columns = [str(c).strip() for c in t.columns]
            c = next((c for c in (col, 'Ticker', 'Symbol', 'Ticker symbol') if c in t.columns), None)
            if c and lo <= len(t) <= 600:   # 11/12 나스닥100 표를 못 찾음 → 열 이름(Ticker·Symbol) 둘 다 본다
                return [str(s).strip().replace('.', '-') for s in t[c].dropna()]
        MEMBER_ERR[name] = '표 못 찾음: ' + '; '.join(f'{len(x)}줄 {list(x.columns)[:4]}' for x in pd.read_html(io.StringIO(r.text))[:6])
    except Exception as e:
        MEMBER_ERR[name] = f'{type(e).__name__} {e}'[:200]
    if name == '나스닥100':          # 위키백과가 안 되면 나스닥 공식 목록(나스닥 사이트가 쓰는 주소)
        try:
            rows = get(NDX_API).json()['data']['data']['rows']
            tick = [str(x['symbol']).strip().replace('.', '-') for x in rows if x.get('symbol')]
            if len(tick) >= 90:
                return tick
            MEMBER_ERR[name] += f' | 나스닥 {len(tick)}종목'
        except Exception as e:
            MEMBER_ERR[name] += f' | 나스닥 {type(e).__name__}'
    return list(cache or [])


def _fwd(yf, t, today):
    """한 종목 → {티커, 시총, 주가, EPS12, PE}. 이번 회계연도(0y)·다음(+1y) 평균 EPS를 남은 기간 비율로 섞는다."""
    out = {'티커': t, '시총': None, 'PE': None, '방법': ''}
    for n in range(2):
        try:
            tk = yf.Ticker(t)
            i = tk.info or {}
            cap, px, fpe = i.get('marketCap'), i.get('currentPrice') or i.get('regularMarketPrice'), i.get('forwardPE')
            e0 = e1 = None
            try:
                ee = tk.earnings_estimate
                e0 = float(ee.loc['0y', 'avg']) if '0y' in ee.index else None
                e1 = float(ee.loc['+1y', 'avg']) if '+1y' in ee.index else None
            except Exception:
                pass
            lfy = i.get('lastFiscalYearEnd')
            pe = None
            if px and e0 is not None and e1 is not None and lfy:
                end = dt.datetime.fromtimestamp(lfy, dt.timezone.utc).date() + dt.timedelta(days=365)
                w = min(max((end - today).days / 365, 0), 1)
                eps = w * e0 + (1 - w) * e1
                if eps:
                    pe, out['방법'] = px / eps, f'섞음 {w:.2f}'
            if fpe and (pe is None or not 0.5 <= pe / fpe <= 2):   # 통화가 다른 ADR 등은 야후 선행 PER로
                pe, out['방법'] = float(fpe), '야후 선행PER'
            out.update({'시총': float(cap) if cap else None, 'PE': pe})
            return out
        except Exception:
            if n == 0:
                import time
                time.sleep(2)
    return out


def weights(df, name):
    """지수 비중(%). 필반은 상위 3종목 12·10·8%, 나머지 4% 상한(나스닥 방식) 근사, 그 외는 시총 비중."""
    cap = df['시총'].fillna(0)
    if name != '필반지수' or cap.sum() == 0:
        return cap / cap.sum() * 100
    order = cap.sort_values(ascending=False).index
    w = pd.Series(0.0, index=df.index)
    top = {order[0]: 12.0, order[1]: 10.0, order[2]: 8.0}
    for k, v in top.items():
        w[k] = v
    rest = [k for k in order if k not in top]
    left, pool = 70.0, list(rest)
    while pool:                                   # 4% 상한을 넘는 몫을 나머지에 다시 나눈다
        s = cap[pool].sum()
        over = [k for k in pool if cap[k] / s * left > 4.0]
        if not over:
            for k in pool:
                w[k] = cap[k] / s * left
            break
        for k in over:
            w[k] = 4.0
        left -= 4.0 * len(over)
        pool = [k for k in pool if k not in over]
    return w


def index_pe(yf, name, tickers, today=None, workers=6):
    """→ (요약 dict, 종목 표). PE = 1 / Σ(비중 × 1/PE_i), 이익이 마이너스인 종목도 그대로 넣는다."""
    today = today or dt.date.today()
    with ThreadPoolExecutor(workers) as ex:
        rows = list(ex.map(lambda t: _fwd(yf, t, today), tickers))
    df = pd.DataFrame(rows)
    df['비중(%)'] = weights(df, name)
    ok = df['PE'].notna() & (df['PE'] != 0) & df['시총'].notna()
    got = float(df.loc[ok, '비중(%)'].sum())
    pe = got / float((df.loc[ok, '비중(%)'] / df.loc[ok, 'PE']).sum()) if ok.any() else None
    summ = {'날짜': today.strftime('%Y-%m-%d'), '지수': name, '선행PE': round(pe, 2) if pe else None,
            '종목수': len(df), '받은 종목수': int(ok.sum()), '받은 비중(%)': round(got, 1),
            '방법': '야후 12개월 선행 EPS 합산'}
    df.insert(0, '지수', name)
    return summ, df
