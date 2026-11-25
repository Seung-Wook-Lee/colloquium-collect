"""지수·시장 일봉은 저장본에서 읽는다(11/25 의장 "블록과 회의프로그램 모두 저장된 것을 쓰도록 하고,
회의프로그램이 하루에 2번 업데이트하면 블록은 그걸 가지고 계산하도록").

저장본 = 회의 준비 코드가 하루 2번(국장전·미장전) 새 날짜만 덧붙이는 in/시장위험.csv (드라이브 00_퀀트입력에 이어 씀).
블록(바닥 확률·분할 판정·조정 단계·시황 한 줄 등)은 이 함수로만 지수를 읽는다. 야후에서 직접 받지 않는다.
저장본에 그 칸이 아예 없을 때만 그 칸 하나를 받고 그렇게 했다고 남긴다(store_first 규칙과 같음)."""
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


def close(tickers, start=None):
    """종가 DataFrame(칸 = 야후 티커). 저장본에서 읽고, 저장본에 그 칸이 없을 때만 그 칸을 받는다."""
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
    if miss:
        import yfinance as yf   # 저장본에 없는 칸만
        D = yf.download(miss, start=start or '1985-01-01', auto_adjust=True, progress=False)['Close']
        D = D.to_frame(miss[0]) if isinstance(D, pd.Series) else D
        for t in miss:
            if t in D:
                out[t] = D[t]
        NOTE.append(f'저장본에 없어 받음: {miss}')
    P = pd.DataFrame(out)
    P.index = pd.to_datetime(P.index)
    if start:
        P = P[P.index >= pd.Timestamp(start)]
    P = P.dropna(how='all').sort_index()
    return P[tickers[0]].dropna() if one else P
