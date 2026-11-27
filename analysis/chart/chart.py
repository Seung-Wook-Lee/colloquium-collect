"""3. 차트센터 (미스 차트) C01~C12 — 의장 11/28 0:38 "그냥 만들어", 번호 C01·C02…
드라이브 가격10년_시가·고가·저가·종가·거래량만 읽는다. 기준은 모두 원래 표준(출처 RULES).
값은 종목마다 마지막 날 하나. '상태'는 표준 기준에 맞으면 강함(+1)·약함(−1)·보통(0).
"""
import numpy as np
import pandas as pd

RULES = [  # (번호, 이름, 표준 기준, 출처)
    ("C01", "RSI(14일)", "30 이하 과매도 · 70 이상 과매수", "Wilder, 1978"),
    ("C02", "MACD(12·26·9일)", "MACD선 − 신호선 > 0 이면 위로 뚫은 상태", "Appel, 1979"),
    ("C03", "볼린저 밴드(20일, 2표준편차) 위치", "0 아래 = 아래 띠 아래(과매도) · 1 위 = 위 띠 위", "Bollinger, 2001"),
    ("C04", "스토캐스틱(14·3일)", "20 이하 과매도 · 80 이상 과매수", "Lane, 1950년대"),
    ("C05", "50일선 − 200일선", "50일선이 200일선 위 = 골든크로스 상태", "Murphy, 1999"),
    ("C06", "10개월 이동평균 대비", "월말 종가가 10개월선 위면 보유", "Faber, 2007"),
    ("C07", "52주 최고가 대비", "최고가에 가까울수록 강함", "George·Hwang, 2004"),
    ("C08", "12개월 모멘텀(최근 1개월 뺌)", "높을수록 강함", "Jegadeesh·Titman, 1993"),
    ("C09", "거래량 누적(OBV) 20일 변화", "가격보다 먼저 오르면 매수세", "Granville, 1963"),
    ("C10", "109주선 대비", "주봉 종가가 109주선 위 = 지지", "의장 기준(11/22)"),
    ("C11", "상대 강도 3달(지수 대비)", "종목 3달 수익률 − 지수 3달 수익률 (미국 QQQM, 한국 코스피)", "Levy, 1967"),
    ("C12", "업종 안 순위(3달 수익률)", "같은 층(업종 묶음) 안 순위, 1 = 가장 강함", "Moskowitz·Grinblatt, 1999"),
]


def rsi(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def one(c, h, l, v, bench):
    """한 종목 → {번호: 값}"""
    c = c.dropna()
    if len(c) < 30:
        return {}
    h, l, v = h.reindex(c.index), l.reindex(c.index), v.reindex(c.index)
    out = {"날짜": c.index[-1], "종가": c.iloc[-1]}
    out["C01"] = rsi(c).iloc[-1]
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    out["C02"] = (macd - macd.ewm(span=9, adjust=False).mean()).iloc[-1] / c.iloc[-1] * 100   # 종가 대비 %
    m, s = c.rolling(20).mean(), c.rolling(20).std()
    out["C03"] = ((c - (m - 2 * s)) / (4 * s)).iloc[-1]
    lo, hi = l.rolling(14).min(), h.rolling(14).max()
    k = ((c - lo) / (hi - lo) * 100).rolling(3).mean()
    out["C04"] = k.iloc[-1]
    out["C05"] = (c.rolling(50).mean() / c.rolling(200).mean() - 1).iloc[-1] * 100 if len(c) >= 200 else np.nan
    mo = c.resample("ME").last()           # 이번 달은 지금 종가가 월말 값 자리
    out["C06"] = (c.iloc[-1] / mo.iloc[-10:].mean() - 1) * 100 if len(mo) >= 10 else np.nan
    out["C07"] = (c.iloc[-1] / c.iloc[-252:].max() - 1) * 100
    out["C08"] = (c.iloc[-22] / c.iloc[-253] - 1) * 100 if len(c) >= 253 else np.nan
    obv = (v.fillna(0) * np.sign(c.diff().fillna(0))).cumsum()
    avg = v.iloc[-20:].mean()
    out["C09"] = (obv.iloc[-1] - obv.iloc[-21]) / (avg * 20) * 100 if avg and avg == avg else np.nan  # 20일 거래량 대비 %
    wk = c.resample("W-FRI").last()
    out["C10"] = (wk.iloc[-1] / wk.rolling(109).mean().iloc[-1] - 1) * 100 if len(wk) >= 109 else np.nan
    b = bench.dropna()
    if len(c) > 63 and len(b) > 63:
        out["C11"] = ((c.iloc[-1] / c.iloc[-64] - 1) - (b.iloc[-1] / b.asof(c.index[-64]) - 1)) * 100
        out["3달"] = (c.iloc[-1] / c.iloc[-64] - 1) * 100
    return out


def state(no, x):
    """표준 기준으로 강함 +1 · 약함 −1 · 보통 0 (C07·C08·C11·C12는 값만, 상태 없음)"""
    if x != x:
        return np.nan
    return {"C01": 1 if x <= 30 else (-1 if x >= 70 else 0),          # 과매도 = 반등 후보
            "C02": 1 if x > 0 else -1,
            "C03": 1 if x < 0 else (-1 if x > 1 else 0),
            "C04": 1 if x <= 20 else (-1 if x >= 80 else 0),
            "C05": 1 if x > 0 else -1,
            "C06": 1 if x > 0 else -1,
            "C09": 1 if x > 0 else -1,
            "C10": 1 if x > 0 else -1}.get(no, np.nan)


def table(C, H, L, Vol, tickers, layer=None):
    """tickers 종목 → 표 (줄 = 종목, 칸 = C01~C12)"""
    rows = {}
    for t in tickers:
        if t not in C:
            continue
        kr = t.endswith((".KS", ".KQ"))
        bench = C["^KS11"] if kr and "^KS11" in C else C.get("QQQM", pd.Series(dtype=float))
        rows[t] = one(C[t], H.get(t, pd.Series(dtype=float)), L.get(t, pd.Series(dtype=float)),
                      Vol.get(t, pd.Series(dtype=float)), bench)
    T = pd.DataFrame(rows).T
    if layer is not None and "3달" in T:
        g = layer.reindex(T.index)["층"]
        T["C12"] = T.groupby(g)["3달"].rank(ascending=False)
        T["C12 수"] = T.groupby(g)["3달"].transform("count")
    return T


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import drive as DR
    C, H, L, V = (DR.wide(f"가격10년_{k}") for k in ("종가", "고가", "저가", "거래량"))
    t = table(C, H, L, V, ["GOOGL", "META", "AAPL", "NVDA", "005930.KS", "000660.KS"], DR.layers())
    pd.set_option("display.width", 250)
    print(t.round(2).to_string())
