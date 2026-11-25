"""지수·시장 일봉은 저장본에서 읽는다(11/25 의장 "블록과 회의프로그램 모두 저장된 것을 쓰도록 하고,
회의프로그램이 하루에 2번 업데이트하면 블록은 그걸 가지고 계산하도록").

저장본 = 회의 준비 코드가 하루 2번(국장전·미장전) 새 날짜만 덧붙이는 in/시장위험.csv (드라이브 00_퀀트입력에 이어 씀).
블록(바닥 확률·분할 판정·조정 단계·시황 한 줄 등)은 이 함수로만 지수를 읽는다. 야후에서 직접 받지 않는다.
저장본에 그 칸이 없으면 10년치 데이터베이스(가격10년_종가)에서 찾고, 거기도 없으면 빈칸으로 두고 남긴다. 받지 않는다(11/26 의장)."""
import os

import pandas as pd

# 야후 티커 → 저장본 칸 이름(fetch_risk_daily.py YF와 같게)
COL = {'^GSPC': 'SPX', '^NDX': 'NDX', '^VIX': 'VIX', '^VIX3M': 'VIX3M', '^IXIC': 'COMPQ', '^RUT': 'RUT', '^MOVE': 'MOVE',
       '^TNX': 'TNX', '^KS11': 'KS11', '^KQ11': 'KQ11', '^DJI': 'DJI', '^SOX': 'SOX', 'QQQ': 'QQQ', 'RSP': 'RSP', 'TLT': 'TLT',
       'GC=F': 'GOLD', 'SI=F': 'SILVER', 'BTC-USD': 'BTC', 'NVDA': 'NVDA', 'SPYG': 'SPYG', 'BIL': 'BIL', 'IWF': 'IWF', 'IWD': 'IWD', 'MGK': 'MGK'}
NOTE = []   # 저장본에 없어 받은 것(실행 기록용)
_cache = {}


def path():
    for p in (os.environ.get('MKT_STORE', ''), 'in/시장위험.csv', 'work_meeting/in/시장위험.csv'):
        if p and os.path.exists(p):
            return p
    return None


def _store():
    p = path()
    if p not in _cache:
        _cache[p] = pd.read_csv(p, index_col=0, parse_dates=True, encoding='utf-8-sig') if p else pd.DataFrame()
    return _cache[p]


def _db():
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'collect', 'data'))
    import px_store as PS
    p = path()
    return PS.frame(os.path.dirname(p)) if p else pd.DataFrame()


def close(tickers, start=None):
    """종가 DataFrame(칸 = 야후 티커). 저장본(시장위험) → 없으면 10년치 데이터베이스."""
    one = isinstance(tickers, str)
    tickers = [tickers] if one else list(tickers)
    S = _store()
    out, miss = {}, []
    for t in tickers:
        c = COL.get(t, t)
        if c in S and S[c].notna().any():
            out[t] = pd.to_numeric(S[c], errors='coerce')
        else:
            miss.append(t)
    if miss:   # 11/26 의장 "따로 받는 코드는 전부 싹 다 지워": 받지 않고 10년치 데이터베이스(가격10년_종가)에서 찾음
        db = _db()
        for t in miss:
            if t in db and db[t].notna().any():
                out[t] = db[t]
        left = [t for t in miss if t not in out]
        if left:
            NOTE.append(f'저장본·데이터베이스에 없음(빈칸): {left}')
    P = pd.DataFrame(out)
    P.index = pd.to_datetime(P.index)
    if start:
        P = P[P.index >= pd.Timestamp(start)]
    P = P.dropna(how='all').sort_index()
    return P[tickers[0]].dropna() if one else P
