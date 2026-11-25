# 섹터 ETF 주봉·섹터 지도 공용 계산(미스 시타델 수급 자료) — 매일 수집 블록 b09_citadel이 쓴다.
#   11/26 의장 "상위종목 하지마. ETF만 해. 유니버스에 없는 것은 하지마. 그리고 병합해. DB":
#   자료      : 따로 받는 주봉 창고 없음. 10년치 데이터베이스(1_data/가격10년_시가·고가·저가·종가·거래량)의 일봉을 weekly()로 주봉으로 묶음.
#              날짜는 그 주 금요일. 진행 중인 주는 그날까지의 값.
#   종목 목록 : 섹터 ETF만. 해외 citadel/etfs_us.csv(SPDR 섹터 ETF 11개), 국내 citadel/etfs_kr.csv. 유니버스(= 데이터베이스)에 없는 것은 계산하지 않음.
#              국내 티커는 6자리 코드. 해외·국내 같은 계산(11/9 의장: 완전히 같이 움직이고 보고만 따로).
#   기준      : 아래 CFG. 이론을 바꾸면 CFG만 고치고, 백테스트(Team_Q contrarian/)도 같은 CFG 숫자로 다시 돌린다(룰 변경은 의장 승인 뒤).
import pandas as pd, numpy as np

CFG = dict(
    선=(60, 20),            # 60주선이 본 신호, 20주선은 참고
    터치_저가=1.01,          # 그 주 저가 <= 선 x1.01
    터치_종가=0.97,          # 그 주 종가 >= 선 x0.97
    추세_기울기주=13,        # 선이 13주 전보다 높음
    추세_위비율=0.8,         # 지난 52주 중 80% 이상 종가가 선 위
    첫터치_간격주=13,        # 직전 13주 안에 같은 터치 없음
    RSI_n=14, RSI_바닥=40,   # 주봉 와일더 RSI
    MACD=(12, 26, 9),
)
COLS = ['티커', '날짜', '시가', '고가', '저가', '종가', '거래량']


def code(t):
    """데이터베이스 티커 → 시타델 티커(국내는 6자리 코드, .KS/.KQ 뗌)."""
    return str(t).split('.')[0] if str(t).endswith(('.KS', '.KQ')) else str(t)


def weekly(L):
    """L: px_store.long() 일봉 긴 표 → 주봉 긴 표(COLS). 주 = 금요일 끝."""
    if L is None or not len(L):
        return pd.DataFrame(columns=COLS)
    L = L.copy(); L['날짜'] = pd.to_datetime(L['날짜'])
    out = []
    for t, x in L.groupby('티커'):
        w = x.set_index('날짜').sort_index().resample('W-FRI').agg({'시가': 'first', '고가': 'max', '저가': 'min', '종가': 'last', '거래량': 'sum'}).dropna(subset=['종가'])
        w['티커'] = code(t); out.append(w.reset_index())
    return pd.concat(out, ignore_index=True)[COLS] if out else pd.DataFrame(columns=COLS)


def rsi(c, n):
    d = c.diff(); u = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + u / dn)


def signals(w):
    """w: 한 종목 주봉(날짜 색인, 시가·고가·저가·종가). 선마다 터치·하향돌파 뒤 상향돌파와 보조 값."""
    c, l = w.종가, w.저가; out = {}
    R = rsi(c, CFG['RSI_n']); f, s_, g = CFG['MACD']
    macd = c.ewm(span=f, adjust=False).mean() - c.ewm(span=s_, adjust=False).mean(); hist = macd - macd.ewm(span=g, adjust=False).mean()
    turn = (hist > hist.shift(1)) & (hist.shift(1) <= hist.shift(2))
    for n in CFG['선']:
        m = c.rolling(n).mean()
        up = (m > m.shift(CFG['추세_기울기주'])) & ((c > m).astype(float).rolling(52).mean() >= CFG['추세_위비율'])
        t = (l <= m * CFG['터치_저가']) & (c >= m * CFG['터치_종가']) & up
        t = t & ~t.shift(1).rolling(CFG['첫터치_간격주'], min_periods=1).max().fillna(0).astype(bool)
        below = c < m
        cu = (~below) & below.shift(1).fillna(False).astype(bool)
        out[n] = dict(선=m, 이격=c / m * 100, 저가이격=l / m * 100, 상승추세=up, 터치=t, 상향돌파=cu)
    slope = np.where(hist > hist.shift(1), np.where(hist.shift(1) <= hist.shift(2), '양 전환', '양'), '음')
    mon = c.groupby(c.index.to_period('M')).last(); m5 = mon.rolling(5).mean()
    m5w = pd.Series(m5.reindex(c.index.to_period('M')).values, index=c.index)
    return out, dict(RSI=R, 오실레이터=hist, 오실레이터상승전환=turn, MACD음수=macd < 0,
                     주MACD기울기=pd.Series(slope, index=c.index), 월5개월선이격=c / m5w * 100)


def now_table(store, holdings):
    """섹터 지도: 섹터 ETF의 마지막 주 상태(상위 종목 없음, 11/26 의장). 두 번째 값 = 60주선 첫 터치 ETF."""
    rows = []
    g = {t: x.set_index('날짜').sort_index() for t, x in store.groupby('티커')}
    for e in dict.fromkeys(holdings.ETF):
        for tk, kind, rank, nm in [(e, 'ETF', 0, '')]:
            w = g.get(tk)
            if w is None or len(w) < 80:
                rows.append(dict(ETF=e, 구분=kind, 순위=rank, 티커=tk, 이름=nm, 상태='자료 부족')); continue
            sg, ind = signals(w); i = -1
            r = dict(ETF=e, 구분=kind, 순위=rank, 티커=tk, 이름=nm, 주=w.index[i].date(), 종가=round(w.종가.iloc[i], 2),
                     고점대비52주=round((w.종가.iloc[i] / w.고가.iloc[-52:].max() - 1) * 100, 1),
                     RSI=round(ind['RSI'].iloc[i], 1), MACD음수='예' if ind['MACD음수'].iloc[i] else '',
                     오실레이터상승전환_3주안='예' if ind['오실레이터상승전환'].iloc[-3:].any() else '',
                     주MACD기울기=ind['주MACD기울기'].iloc[i], 월5개월선이격=round(ind['월5개월선이격'].iloc[i], 1))
            for n, s in sg.items():
                r[f'{n}주 이격'] = round(s['이격'].iloc[i], 1); r[f'{n}주 저가이격'] = round(s['저가이격'].iloc[i], 1)
                r[f'{n}주 상승추세'] = '예' if s['상승추세'].iloc[i] else ''
                r[f'{n}주 첫터치'] = '예' if s['터치'].iloc[i] else ''
                r[f'{n}주 상향돌파'] = '예' if s['상향돌파'].iloc[i] else ''
            rows.append(r)
    T = pd.DataFrame(rows)
    cut = T[(T.구분 == 'ETF') & (T.get('60주 첫터치') == '예')].ETF.tolist() if '60주 첫터치' in T else []
    return T, cut
