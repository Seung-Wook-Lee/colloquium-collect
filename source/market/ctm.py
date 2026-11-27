"""CTM (Chande Trend Meter) 추정 계산

CTM은 StockCharts 지표로, 구성은 공개되어 있다:
  고가·저가·종가의 볼린저 밴드 안 위치(20·50·75·100봉), 100봉 표준편차 대비 가격 변화,
  RSI(14), 2봉 채널 돌파 → 0~100 점.
구성별 무게는 공개되어 있지 않다. 의장 11/27 "역시 추정해" → 추정 무게를 쓴다.
추정 무게(볼린저 위치 8 : RSI 3)는 11/22 의장이 준 StockCharts 그림 값 10곳에 맞춘 것(평균 오차 5.5점).
고가·저가가 없는 지수(나스닥100)는 종가로 대신한다.
"""
import numpy as np
import pandas as pd

WEIGHT = dict(BB=8, PC=0, RSI=3, BO=0)   # 추정 무게


def bars(close, high=None, low=None, rule=None):
    """일봉(rule=None)·주봉('W-FRI')·월봉('ME')으로 묶는다."""
    c = close.dropna()
    h = high.reindex(c.index).fillna(c) if high is not None else c
    l = low.reindex(c.index).fillna(c) if low is not None else c
    if rule is None:
        return c, h, l
    return (c.resample(rule).last().dropna(), h.resample(rule).max().dropna(),
            l.resample(rule).min().dropna())


def ctm(close, high=None, low=None, rule=None):
    C, H, L = bars(close, high, low, rule)
    H, L = H.reindex(C.index), L.reindex(C.index)
    if len(C) < 110:
        return pd.Series(dtype=float)

    def pos(x, n):
        m, s = C.rolling(n).mean(), C.rolling(n).std()
        return ((x - (m - 2 * s)) / (4 * s)).clip(0, 1)

    BB = pd.concat([pos(x, n) for n in (20, 50, 75, 100) for x in (H, L, C)], axis=1).mean(axis=1)
    z = C.diff() / C.diff().rolling(100).std()
    PC = ((z + 2) / 4).clip(0, 1)
    d = C.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14).mean()
    RSI = up / (up + dn)
    BO = pd.Series(np.where(C > H.shift(1).rolling(2).max(), 1.0,
                            np.where(C < L.shift(1).rolling(2).min(), 0.0, 0.5)), index=C.index)
    w = WEIGHT
    out = 100 * (w["BB"] * BB + w["PC"] * PC + w["RSI"] * RSI + w["BO"] * BO) / sum(w.values())
    return out.dropna()
