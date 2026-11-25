# 히트맵 계산 — 블록 b09_heatmap(07시)과 스트림릿(그날 파일이 없을 때 바로 계산)이 같이 쓴다.
#   한국: heatmap_kr.csv(코스피·코스닥 주요 약 70종목, 섹터별), 칸 크기는 시가총액.
#   S&P500: SPDR 섹터 ETF 11개의 상위 10종목(citadel/holdings_top10.csv)을 섹터별로 묶고, 칸 크기는 시가총액.
#   등락률: 1일(직전 거래일), 1주(5거래일), 1달(21거래일). 판정은 하지 않는다.
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

SECTOR_KO = {'XLK': '기술', 'XLC': '커뮤니케이션', 'XLY': '임의소비재', 'XLF': '금융', 'XLV': '헬스케어',
             'XLI': '산업재', 'XLP': '필수소비재', 'XLE': '에너지', 'XLU': '유틸리티', 'XLRE': '부동산', 'XLB': '소재'}
WIN = {'1일': 1, '1주': 5, '1달': 21}
COLS = ['시장', '묶음', '티커', '이름', '시총', '1일', '1주', '1달', '종가', '기준일']


def returns(c):
    """종가 시계열 → {1일, 1주, 1달} 등락률(%)과 종가·기준일"""
    c = c.dropna()
    out = {k: (round((c.iloc[-1] / c.iloc[-1 - n] - 1) * 100, 2) if len(c) > n else None) for k, n in WIN.items()}
    out['종가'] = round(float(c.iloc[-1]), 4) if len(c) else None
    out['기준일'] = c.index[-1].strftime('%Y-%m-%d') if len(c) else None
    return out


def _cap(yf, t):
    try:
        return float(yf.Ticker(t).fast_info['market_cap'] or 0) or None
    except Exception:
        return None


def _download(yf, syms):
    d = yf.download(syms, period='3mo', interval='1d', auto_adjust=True, group_by='ticker', threads=True, progress=False)
    close = {}
    for t in syms:
        try:
            s = d[t]['Close'].dropna()
            s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
            if len(s):
                close[t] = s
        except Exception:
            pass
    return close


def korea(yf, lst):
    """lst = heatmap_kr.csv (섹터, 티커, 이름): 코스피·코스닥 주요 종목, 칸 크기는 시가총액"""
    close = _download(yf, list(lst.티커))
    stocks = [t for t in lst.티커 if t in close]
    with ThreadPoolExecutor(8) as ex:
        caps = dict(zip(stocks, ex.map(lambda t: _cap(yf, t), stocks)))
    return [{'시장': '한국', '묶음': r.섹터, '티커': r.티커, '이름': r.이름, '시총': caps.get(r.티커), **returns(close[r.티커])}
            for r in lst.itertuples() if r.티커 in close]


def sp500(yf, hold):
    """hold = holdings_top10.csv (ETF, 순위, 티커, 이름) → 히트맵 줄 목록"""
    etfs = list(dict.fromkeys(hold.ETF))
    stocks = list(dict.fromkeys(hold.티커))
    close = _download(yf, etfs + stocks)
    with ThreadPoolExecutor(8) as ex:
        caps = dict(zip(stocks, ex.map(lambda t: _cap(yf, t), stocks)))
    rows, seen = [], set()
    for r in hold.itertuples():
        if r.티커 in seen or r.티커 not in close:   # 두 섹터에 겹치면(예: GOOGL·GOOG) 처음 섹터에만
            continue
        seen.add(r.티커)
        rows.append({'시장': 'S&P500', '묶음': SECTOR_KO.get(r.ETF, r.ETF), '티커': r.티커, '이름': r.이름,
                     '시총': caps.get(r.티커), **returns(close[r.티커])})
    for e in etfs:
        if e in close:
            rows.append({'시장': 'S&P500 섹터 ETF', '묶음': SECTOR_KO.get(e, e), '티커': e, '이름': SECTOR_KO.get(e, e),
                         '시총': None, **returns(close[e])})
    return rows
