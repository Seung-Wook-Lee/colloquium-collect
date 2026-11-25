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

import pandas as pd

F = {'Open': '시가', 'High': '고가', 'Low': '저가', 'Close': '종가', 'Volume': '거래량'}
TWO = {'Close': '가격2년', 'High': '고가2년', 'Low': '저가2년', 'Volume': '거래량2년'}
OVERLAP_DAYS = 3
ADJ_TOL = 0.02


def name(k):
    return f'가격10년_{F[k]}.csv.gz'


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


def two_years(B, folder, tickers=None):
    """회의용 2년 파일을 저장본에서 잘라 만듦."""
    out = []
    for k, f in TWO.items():
        d = B.get(k)
        if d is None:
            continue
        d = d[d.index >= d.index.max() - pd.Timedelta(days=735)]
        if tickers is not None:
            d = d[[t for t in tickers if t in d.columns]]
        d.to_csv(f'{folder}/{f}.csv', encoding='utf-8-sig')
        out.append(f'{f}.csv')
    return out


# ---- 받기: 저장본 마지막 날 뒤만, 시장별로 새 거래일이 있을 때만(11/25 의장 "블록과 회의프로그램 모두 저장된 것을 쓰도록,
#      회의프로그램이 하루에 2번 업데이트하면 블록은 그걸 가지고 계산")
#   아침(07시 수집·국장전): 미국 전날 장만 새로 있음 → 미국만 받음(한투 접속 없음)
#   저녁(미장전): 한국 오늘 장만 새로 있음 → 한국만 받음(한투 접속 1번)
#   같은 장을 이미 받았으면 아무것도 받지 않는다(국장전 회의 준비 코드는 07시 수집이 받은 것을 그대로 씀).
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
    mk = dict(zip(U['yfinance 티커'].astype(str), U['시장']))
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
    kr = [x for m, tt, _ in frames if m == '한국' for x in tt] + [x for x in NEW if mk[x] == '한국']
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
