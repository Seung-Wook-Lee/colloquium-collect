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
