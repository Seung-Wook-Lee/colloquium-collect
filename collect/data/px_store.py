"""가격 저장본 하나에 새 날짜만 쌓기(11/25 의장).

의장: "매일매일 그날 자료만 받아오고, 구글 드라이브에 쌓고..이러면 되는 거 아닌가."
      "일요일에 10년치를 통째로 왜 다시 받지? 당장 지워. 지금 10년치 있잖아."

규칙
1. 저장본은 드라이브 1_data/가격10년_{시가,고가,저가,종가,거래량}.csv.gz 하나뿐이다.
2. 저장본에 있는 종목은 저장본 마지막 날 3일 전부터만 받아 덧붙인다(겹치는 3일은 새 값으로 맞춤).
3. 저장본에 없는 종목(새 종목)만 그 종목의 과거치를 한 번 받는다.
4. 겹치는 날 새 값과 저장본 값이 2% 넘게 다르면(분할·배당 보정이 바뀐 것) 그 종목 저장본 과거치를
   같은 비율로 고쳐 잇는다(다시 받지 않음).
5. 회의용 2년 파일(가격2년·고가2년·저가2년·거래량2년)은 이 저장본에서 잘라 만든다.
tests/test_store_first.py가 이 규칙을 지킨다."""
import datetime as dt
import os

import pandas as pd

F = {'Open': '시가', 'High': '고가', 'Low': '저가', 'Close': '종가', 'Volume': '거래량'}
OVERLAP_DAYS = 3
ADJ_TOL = 0.02
# 지수도 같은 데이터베이스 칸(종목과 같은 날짜 줄). 미국 지수는 아침 8시, 한국 지수는 저녁 8시에 새 날만 덧붙임(야후).
IDX = {'^GSPC': '미국', '^NDX': '미국', '^VIX': '미국', '^KS11': '한국', '^KQ11': '한국'}


def name(k):
    return f'가격10년_{F.get(k, k)}.csv.gz'   # k = Open·High·Low·Close·Volume 또는 'EPS'(주당순이익 TTM 칸, 1-4가 매주 만듦)


# 11/26 의장 "10년치 저장본 밖에 따로 있는 과거 자료들을 저장본에 합치시오"(카드: 저장본의 칸으로 합침).
# 날짜 × 종목 칸(시가·고가·저가·종가·거래량·EPS) 말고, 공시·보유처럼 줄 단위인 과거 자료도 같은 저장본(1_data/가격10년_{칸}.csv.gz)의 칸으로 둔다.
# 읽기는 table(), 쓰기는 put_table(), 드라이브에서 받기는 fetch() 하나로. 옛 자리 파일은 fetch()가 처음 한 번 칸으로 옮기고 휴지통으로 보낸다.
BASE = '콜로키움 수집데이터'
TABLES = {   # 칸 이름: 옛 자리(BASE 아래)
    '블록점수': '00_퀀트입력/블록점수이력.csv',            # 블록 점수·N주 뒤 수익(성적표, 2017-12~ 매주)
    'SEC재무': '1_data/SEC재무_분기.csv.gz',               # 미국 분기 재무(공시일 기준)
    'DART재무': '1_data/DART재무_분기.csv.gz',             # 한국 분기 재무(공시일 기준)
    '국내수급': '1_data/장기/국내수급_일별.csv.gz',        # 한국 종목 외국인·기관·개인 순매수(일별)
    '13F': '1_data/장기/장기펀드13F_이력.csv',              # 장기 펀드 13F 종목×분기
    '노르웨이보유': '1_data/장기/노르웨이_보유_이력.csv.gz',  # 노르웨이 국부펀드 보유(반기)
    '공매도': '1_data/장기/공매도_미국_이력.csv.gz',        # 미국 공매도 잔고(FINRA 결제일)
    'ETF좌수': '1_data/장기/ETF좌수_이력.csv.gz',          # ETF 상장좌수·NAV(일별)
    '지수장기': '1_data/지수_장기.csv.gz',                  # 지수 가능한 가장 긴 일봉(^GSPC·^NDX·^KS11)
    '추가종가': '1_data/추가자료_종가.csv',                 # 한투 추가 자료(우리 가격 칸에 없는 것, 저가는 '_LOW')
    '수급포지셔닝': '00_누적/00_수급포지셔닝_이력.csv',     # CTA σ 근사·변동성 타기팅 등 일별(미스 시타델)
    'MMF': '00_누적/00_MMF잔고.csv',                       # 미국 MMF 잔고(주별)
    'ETF좌수일별': '00_누적/00_ETF좌수이력.csv',           # 유니버스 ETF 좌수·NAV 매일 한 줄(b09_flow)
    '지수선행PE': '00_누적/00_지수선행PE.csv',             # S&P500 구성종목 선행 EPS 합산 PER(b09_valuation)
}
# 11/26 의장 카드 '안 쓰는 5개만 지움': 00_누적 창고에서 매일 쓰는 이력 4개는 위 칸으로, 안 쓰는 5개는 휴지통.
# 수집 블록은 작업 폴더(KEEP)에서 옛 이름 그대로 읽고 쓰고, 드라이브에는 칸으로만 올린다(b00_setup 받기, b11_summary 올리기).
KEEP_DB = {'00_수급포지셔닝_이력.csv': '수급포지셔닝', '00_MMF잔고.csv': 'MMF', '00_ETF좌수이력.csv': 'ETF좌수일별', '00_지수선행PE.csv': '지수선행PE'}
KEEP_DROP = ['00_일본공시_누적.csv', '00_일본_실적달력.csv', '00_일본_밸류스냅숏.csv', '00_시타델_국내구성.csv', '00_DBMF보유이력.csv']
# 시장 지표 과거 자료 5개(옛 1_data/장기/)는 날짜 × 지표 칸 하나(가격10년_시장지표)로 합침. {옛 파일: 칸 이름 바꾸기}
# 순서: 뒤의 것이 앞의 것보다 우선(시장위험_장기에 CPCE가 있으면 그 값을 씀 — hist_market 옛 규칙과 같음).
MARKET = {'CPCE.csv': {}, '신용스프레드_이력.csv': {}, '공포탐욕_이력.csv': {'Fear Greed': '공포탐욕'},
          '지정학위험_이력.csv': {'GPRD': '지정학위험'}, '시장위험_장기.csv': {}}


def table(d, k, **kw):
    """저장본의 줄 단위 칸 읽기. 없으면 빈 표."""
    p = f'{d}/{name(k)}'
    if not os.path.exists(p):
        return pd.DataFrame()
    return pd.read_csv(p, encoding='utf-8-sig', **kw)


def put_table(d, k, df):
    """저장본의 줄 단위 칸 쓰기(gzip)."""
    p = f'{d}/{name(k)}'
    df.to_csv(p, index=False, encoding='utf-8-sig', compression='gzip')
    return p


def fetch(drive, k, folder, log=print):
    """드라이브 저장본 칸(1_data/가격10년_{k}.csv.gz) → folder. 칸이 아직 없고 옛 자리에 파일이 있으면
    칸으로 옮겨 올리고(내용 그대로, gzip) 올라간 것을 확인한 뒤 옛 파일을 휴지통으로(11/26 의장 "옛 파일을 지우고")."""
    import gzip
    new = f'{BASE}/1_data/{name(k)}'
    b = drive.get(new)
    if not b and k in TABLES:
        old = f'{BASE}/{TABLES[k]}'
        ob = drive.get(old)
        if ob:
            b = ob if old.endswith('.gz') else gzip.compress(ob)
            drive.put(new, b)
            if drive.get(new):
                drive.trash(old)
                log(f'[저장본] {TABLES[k]} → {name(k)} 옮기고 옛 파일 휴지통')
    if b:
        open(f'{folder}/{name(k)}', 'wb').write(b)
    return bool(b)


def market(drive, hist, folder, log=print):
    """시장 지표 칸(1_data/가격10년_시장지표.csv.gz) 만들기: 이번에 새로 받은 것(hist 폴더) > 저장본 칸 > 옛 파일(1_data/장기/).
    칸을 올리고 확인한 뒤 옛 파일 5개는 휴지통. 돌려주는 값: 날짜 × 지표 표."""
    import gzip
    import io
    new = f'{BASE}/1_data/{name("시장지표")}'
    b = drive.get(new)
    M = pd.read_csv(io.BytesIO(gzip.decompress(b)), index_col=0, parse_dates=True, encoding='utf-8-sig') if b else pd.DataFrame()
    for fn, ren in MARKET.items():
        p = os.path.join(hist, fn) if hist else ''
        fresh = bool(p) and os.path.exists(p)
        if fresh:
            x = pd.read_csv(p, index_col=0, parse_dates=True, encoding='utf-8-sig')
        elif not b:   # 칸이 아직 없을 때만 옛 자리에서
            ob = drive.get(f'{BASE}/1_data/장기/{fn}')
            if not ob:
                continue
            x = pd.read_csv(io.BytesIO(ob), index_col=0, parse_dates=True, encoding='utf-8-sig')
        else:
            continue
        x = x.rename(columns=ren); x.index = pd.to_datetime(x.index); x = x[~x.index.duplicated(keep='last')]
        M = x.combine_first(M) if fresh or fn == '시장위험_장기.csv' else M.combine_first(x)
        log(f'[시장지표] {fn} {"새로 받은 것" if fresh else "옛 파일"} {x.shape}')
    if M.empty:
        return M
    M = M.sort_index(); M.index.name = '날짜'
    gz = gzip.compress(M.to_csv(encoding='utf-8-sig').encode('utf-8-sig'))
    open(f'{folder}/{name("시장지표")}', 'wb').write(gz)
    drive.put(new, gz)
    if drive.get(new):
        n = sum(drive.trash(f'{BASE}/1_data/장기/{fn}') or 0 for fn in MARKET)
        if n:
            log(f'[저장본] 옛 1_data/장기 시장 지표 파일 {n}개 → {name("시장지표")} 옮기고 휴지통')
    return M


def load(folder):
    """저장본 읽기: {k: DataFrame(index=날짜, columns=티커)}. 없는 파일은 빠짐."""
    B = {}
    for k in F:
        try:
            d = pd.read_csv(f'{folder}/{name(k)}', index_col=0, parse_dates=True, encoding='utf-8-sig')
            d.index = pd.to_datetime(d.index)
            B[k] = d
        except Exception:
            pass
    return B


_CACHE = {}


def frame(d, k='Close', days=None):
    """11/26 의장 "10년치 자료만 남겨놔. 거기서 다 찾아서 읽을 수 있게": 데이터베이스(폴더 d의 가격10년_*) 한 칸을 읽는 단 하나의 함수.
    k = Open·High·Low·Close·Volume, days = 마지막 날부터 며칠(없으면 10년 전체). 칸 = 티커(지수는 ^로 시작)."""
    p = f'{d}/{name(k)}'
    if not os.path.exists(p):
        return pd.DataFrame()
    key = (os.path.abspath(p), os.path.getmtime(p))
    if key not in _CACHE:
        x = pd.read_csv(p, index_col=0, parse_dates=True, encoding='utf-8-sig')
        x.index = pd.to_datetime(x.index)
        _CACHE[key] = x.sort_index()
    x = _CACHE[key]
    if days:
        x = x[x.index >= x.index.max() - pd.Timedelta(days=days)]
    return x


def stocks(d, k='Close', days=None):
    """종목 칸만(지수 제외)."""
    x = frame(d, k, days)
    return x[[c for c in x.columns if not str(c).startswith('^')]]


def index(d, days=None):
    """지수 종가 칸만(^GSPC·^NDX·^VIX·^KS11·^KQ11)."""
    x = frame(d, 'Close', days)
    return x[[c for c in x.columns if str(c).startswith('^')]]


def per(d, days=None):
    """11/26 의장 "PER은 10년치 기록에 열을 만들어서 합치면": 일별 PER = 종가 ÷ 그날 알 수 있던 EPS TTM(공시일 기준, 적자면 빈칸).
    EPS 칸(가격10년_EPS)은 1-4(b1_4_per.py)가 SEC·DART 분기 순이익 4분기 합 ÷ 주식수로 만든다. 새 날은 마지막 EPS를 이어 씀."""
    C = stocks(d, 'Close', days)
    E = frame(d, 'EPS')
    if C.empty or E.empty:
        return pd.DataFrame(index=C.index)
    E = E.reindex(E.index.union(C.index)).ffill().reindex(C.index)[[c for c in C.columns if c in E.columns]]
    return (C[E.columns] / E).where(E > 0)


def per_band(d):
    """종목별 PER 위치: per_now(오늘), per_med3·per_pct3(3년 중앙값·백분위, 0=가장 쌈), per_med1·per_pct1(52주). 상식 밖(2 미만·2000 초과)은 비움."""
    P = per(d, 3 * 366)
    rows = []
    for t in P.columns:
        x = P[t].dropna()
        if len(x) < 250 or pd.isna(P[t].iloc[-1]) or not (2 <= x.iloc[-1] <= 2000):
            continue
        now = float(x.iloc[-1]); y = x[x.index >= x.index[-1] - pd.Timedelta(days=365)]
        rows.append(dict(ticker=t, per_now=round(now, 2), per_med3=round(float(x.median()), 2), per_pct3=round(float((x < now).mean()), 3),
                         per_med1=round(float(y.median()), 2), per_pct1=round(float((y < now).mean()), 3)))
    return pd.DataFrame(rows, columns=['ticker', 'per_now', 'per_med3', 'per_pct3', 'per_med1', 'per_pct1'])


_PW = {}


def per_weekly(d):
    """과거 판정(성적표)용 주별 긴 표: 날짜·ticker·EPS_TTM·PER·PER_52주중앙·PER_3년백분위(금요일, 그 주까지 알 수 있던 값만)."""
    key = (os.path.abspath(f'{d}/{name("EPS")}'), os.path.getmtime(f'{d}/{name("EPS")}') if os.path.exists(f'{d}/{name("EPS")}') else 0)
    if key in _PW:
        return _PW[key]
    C = stocks(d, 'Close')
    E = frame(d, 'EPS')
    if C.empty or E.empty:
        _PW[key] = None
        return None
    E = E.reindex(E.index.union(C.index)).ffill().reindex(C.index)[[c for c in C.columns if c in E.columns]]
    Cw, Ew = C[E.columns].resample('W-FRI').last(), E.resample('W-FRI').last()
    Pw = (Cw / Ew).where(Ew > 0)
    def lng(X, n):
        X = X.copy(); X.index.name = '날짜'; X.columns.name = 'ticker'
        return X.reset_index().melt(id_vars='날짜', var_name='ticker', value_name=n)
    out = lng(Ew, 'EPS_TTM')
    for X, n in ((Pw, 'PER'), (Pw.rolling(52, min_periods=26).median(), 'PER_52주중앙'), (Pw.rolling(156, min_periods=52).rank(pct=True), 'PER_3년백분위')):
        out[n] = lng(X, n)[n].values
    out = out.dropna(subset=['EPS_TTM'])
    out['날짜'] = out['날짜'].astype('datetime64[ns]')
    _PW[key] = out.sort_values('날짜').reset_index(drop=True)
    return _PW[key]


def long(d, tickers=None, days=None):
    """수집 블록(닉스·섹터·데스크)용 긴 표: 날짜·티커·시가·고가·저가·종가·수정종가·거래량. 파일로 남기지 않음(사본 금지)."""
    parts = []
    for k in ('Open', 'High', 'Low', 'Close', 'Volume'):
        x = frame(d, k, days)
        if tickers is not None:
            x = x[[t for t in tickers if t in x.columns]]
        parts.append(x.stack().rename(F[k]))
    if not parts or all(len(p) == 0 for p in parts):
        return pd.DataFrame(columns=['날짜', '티커', '시가', '고가', '저가', '종가', '수정종가', '거래량'])
    h = pd.concat(parts, axis=1).reset_index()
    h.columns = ['날짜', '티커'] + list(h.columns[2:])
    h['수정종가'] = h['종가']
    return h[['날짜', '티커', '시가', '고가', '저가', '종가', '수정종가', '거래량']].dropna(subset=['종가']).sort_values(['티커', '날짜']).reset_index(drop=True)


def missing(B, tickers):
    """저장본에 없는(또는 값이 하나도 없는) 종목."""
    c = B.get('Close')
    if c is None:
        return list(tickers)
    return [t for t in tickers if t not in c.columns or c[t].dropna().empty]


def start(B):
    """저장본에 있는 종목을 받기 시작할 날(마지막 날 3일 전). 저장본이 없으면 None."""
    c = B.get('Close')
    if c is None or not len(c.dropna(how='all')):
        return None
    return (c.dropna(how='all').index.max() - pd.Timedelta(days=OVERLAP_DAYS)).date()


def _adjust(B, new_close, log):
    """겹치는 날 비율이 2% 넘게 다르면 저장본 과거치를 그 비율로 고침(분할·배당 보정)."""
    c = B.get('Close')
    if c is None:
        return
    fixed = []
    for t in new_close.columns:
        if t not in c.columns:
            continue
        a, b = c[t].dropna(), new_close[t].dropna()
        both = a.index.intersection(b.index)
        if not len(both):
            continue
        r = float((b.loc[both] / a.loc[both]).median())
        if r > 0 and abs(r - 1) > ADJ_TOL:
            for k in ('Open', 'High', 'Low', 'Close'):
                if k in B and t in B[k].columns:
                    B[k][t] = B[k][t] * r
            if 'Volume' in B and t in B['Volume'].columns:
                B['Volume'][t] = B['Volume'][t] / r
            fixed.append(f'{t}×{r:.3f}')
    if fixed:
        log(f'저장본 과거치 보정(분할·배당) {fixed}')


def merge(B, N, log=print):
    """저장본 B에 새로 받은 N({k: DataFrame})을 덧붙임. 새 값 우선, 없는 날·종목은 저장본."""
    if 'Close' in N:
        _adjust(B, N['Close'], log)
    out = {}
    for k in F:
        n, b = N.get(k), B.get(k)
        if n is not None:
            n = n.copy()
            n.index = pd.to_datetime(n.index)
            n = n.loc[:, ~n.columns.duplicated()]
        if b is None:
            out[k] = n
        elif n is None:
            out[k] = b
        else:
            out[k] = n.combine_first(b).sort_index()
    return {k: v for k, v in out.items() if v is not None}


def keep(B, tickers):
    """11/25 의장 "10년치 자료에서 유니버스에 없는 종목의 기록들은 모두 삭제": 유니버스 티커와 지수(^로 시작)만 남김.
    돌려주는 것: (새 B, 지운 티커 목록). 지울 것이 없으면 같은 B."""
    want = set(map(str, tickers))
    drop = sorted({c for d in B.values() for c in d.columns if c not in want and not str(c).startswith('^')})
    if not drop:
        return B, []
    return {k: d[[c for c in d.columns if c not in drop]] for k, d in B.items()}, drop


def save(B, folder):
    for k, d in B.items():
        d.to_csv(f'{folder}/{name(k)}', encoding='utf-8-sig', compression='gzip')
    return [name(k) for k in B]


def _prev_weekday(d):
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def last_session(market, now_kst):
    """그 시장에서 지금(한국 시각) 끝난 마지막 거래일(공휴일은 따지지 않음 — 받으면 빈 값이라 해 없음)."""
    if market == '한국':
        d = now_kst.date() if now_kst.hour >= 16 else now_kst.date() - dt.timedelta(days=1)
    else:   # 미국 장은 한국 시각 다음 날 06시(서머타임 05시)에 끝남
        d = (now_kst - dt.timedelta(hours=6)).date() - dt.timedelta(days=1)
    return _prev_weekday(d)


def update(B, U, now_kst, log=print):
    """B(저장본)에 새 거래일만 덧붙여 돌려줌. U = 유니버스(yfinance 티커·시장·코드·거래소)."""
    import yfinance as yf
    U = U.dropna(subset=['yfinance 티커']).drop_duplicates('yfinance 티커')
    mk = {**dict(zip(U['yfinance 티커'].astype(str), U['시장'])), **IDX}
    t = list(mk)
    NEW = missing(B, t)
    c = B.get('Close')
    N, frames = {}, []
    import os
    kis_off = os.environ.get('KIS_OFF') == '1'   # 11/25 의장: 아침 8시엔 미국만, 한국은 저녁 8시 수집이 한투로
    if kis_off:
        NEW = [x for x in NEW if mk[x] != '한국']
    for m in ('미국', '한국'):
        if m == '한국' and kis_off:
            log('가격 한국: 아침엔 받지 않음(저녁 8시 수집이 한투로 덧붙임)')
            continue
        tt = [x for x in t if mk[x] == m and x not in NEW]
        if not tt:
            continue
        have = c[tt].apply(lambda s: s.last_valid_index()).dropna()
        last = have.max().date() if len(have) else None
        want = last_session(m, now_kst)
        if last is not None and last >= want:
            log(f'가격 {m}: 저장본 {last}까지 있음(마지막 장 {want}) → 받지 않음')
            continue
        s0 = (pd.Timestamp(last) - pd.Timedelta(days=OVERLAP_DAYS)).date() if last else None
        log(f'가격 {m}: 저장본 {last}까지 → {s0}부터 {len(tt)}종목 받음')
        frames.append((m, tt, s0))
    if NEW:
        log(f'가격: 저장본에 없는 새 종목 {NEW} → 그 종목만 과거치')
    D = None
    us = [x for m, tt, _ in frames if m == '미국' for x in tt]
    s_us = next((s0 for m, _, s0 in frames if m == '미국'), None)
    if us:
        D = yf.download(us, start=str(s_us), auto_adjust=True, progress=False, threads=True)
    if NEW:
        D2 = yf.download(NEW, period='10y', auto_adjust=True, progress=False, threads=True)
        D = D2 if D is None else pd.concat([D, D2], axis=1, sort=True)
    kr = [x for m, tt, _ in frames if m == '한국' for x in tt if x not in IDX] + [x for x in NEW if mk[x] == '한국' and x not in IDX]
    kri = [x for m, tt, _ in frames if m == '한국' for x in tt if x in IDX]   # 한국 지수는 한투 일봉이 아니라 야후
    if kri:
        s_kri = next((s0 for m, _, s0 in frames if m == '한국'), None)
        D4 = yf.download(kri, start=str(s_kri), auto_adjust=True, progress=False, threads=True)
        D = D4 if D is None else pd.concat([D, D4], axis=1, sort=True)
    s_kr = next((s0 for m, _, s0 in frames if m == '한국'), None)
    KD = {}
    if kr:   # 11/21 의장: 한국 종목은 한투 일봉
        try:
            import kis
            if kis.ready():
                M = U.set_index('yfinance 티커')
                days = (dt.date.today() - s_kr).days + 1 if s_kr else 730
                got = []
                for x in kr:
                    k = kis.daily_kr(str(M.loc[x].get('코드') or x).split('.')[0], days=730 if x in NEW else days)
                    if not len(k):
                        continue
                    k.index = pd.to_datetime(k.index)
                    for col in ('Close', 'High', 'Low', 'Volume'):
                        KD.setdefault(col, {})[x] = k[col]
                    got.append(x)
                log(f'한투 일봉 {len(got)}/{len(kr)}')
            else:
                log('한투 키 없음 → 한국도 야후')
                old_kr = [x for x in kr if x not in NEW]
                if old_kr:
                    D3 = yf.download(old_kr, start=str(s_kr), auto_adjust=True, progress=False, threads=True)
                    D = D3 if D is None else pd.concat([D, D3], axis=1, sort=True)
        except Exception as e:   # noqa: BLE001
            log(f'한투 일봉 실패 {e}')
    if D is not None and len(D):
        if not isinstance(D.columns, pd.MultiIndex):
            D.columns = pd.MultiIndex.from_tuples(D.columns)
        for k in F:
            if k in D.columns.get_level_values(0):
                N[k] = D[k].dropna(how='all')
    for k, d in KD.items():   # 한투 값이 우선(한국)
        kd = pd.DataFrame(d)
        N[k] = kd if k not in N else kd.combine_first(N[k])
    if not N:
        return B
    return merge(B, N, log)


# ---------------------------------------------------------------- 유니버스 = 10년치 데이터베이스 칸 하나(11/26 의장 "하나로 통일해")
# 유니버스를 읽는 곳(회의·엔진·수집·블록 1·진단)은 모두 universe()만 쓴다. 넣기·빼기는 collect/universe_manage.py(layers.OUT·ADD)가 이 칸을 고친다.
# 칸이 아직 없으면 첫 한 번만 옛 자리(콜로키움/포트폴리오 최신 CSV)를 칸으로 옮긴다(옛 파일은 지우지 않음 — 지우기는 의장 허락).
UNIV_KAN = '유니버스'
_UNIV_OLD = ('콜로키움/포트폴리오', '콜로키움100_유니버스_')


def universe(drive, log=print):
    """유니버스 표(dtype=str). 칸 1_data/가격10년_유니버스.csv.gz."""
    import io
    p = f'{BASE}/1_data/{name(UNIV_KAN)}'
    b = drive.get(p)
    if b:
        return pd.read_csv(io.BytesIO(b), dtype=str, encoding='utf-8-sig', compression='gzip')
    fo, pre = _UNIV_OLD
    names = sorted(f['name'] for f in drive.ls(fo) if f['name'].startswith(pre) and f['name'].endswith('.csv'))
    if not names:
        return pd.DataFrame()
    u = pd.read_csv(io.BytesIO(drive.get(f'{fo}/{names[-1]}')), dtype=str, encoding='utf-8-sig')
    put_universe(drive, u)
    log(f'[유니버스] 옛 {fo}/{names[-1]} → 데이터베이스 칸 {name(UNIV_KAN)}로 옮김(앞으로 이 칸 하나만 씀)')
    return u


def put_universe(drive, u):
    import io
    buf = io.BytesIO()
    u.to_csv(buf, index=False, encoding='utf-8-sig', compression={'method': 'gzip'})
    return drive.put(f'{BASE}/1_data/{name(UNIV_KAN)}', buf.getvalue())
