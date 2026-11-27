"""CTA(추세추종 펀드) 포지션 근사(σ)

CTA 포지션 근사값.
- 지수 무게: S&P500 20% · 나스닥100 60% · 러셀2000 20%
- 느린 추세(2·4·8개월, 선형, 20일 평활, 60일 변동성 조정) 80% + 빠른 추세(1·2·3개월, tanh, 40일 변동성) 20%
- 2018년 이후 평균·표준편차로 σ 눈금, 시타델 그림(2025-11~2026-11, 27점)에 맞춘 배율 3.04
- 추세 신호 매수 수: S&P500 이 21·63·100일 전보다 높은 개수(0~3)
"""
import numpy as np
import pandas as pd

WEIGHTS = {"SPX": 0.2, "NDX": 0.6, "RUT": 0.2}
TV = 0.10
CAL_K = 3.04


def _trend(px, looks, kind, smooth, volwin):
    e = 0
    for c, w in WEIGHTS.items():
        lp = np.log(px[c])
        r = lp.diff()
        sd = r.rolling(250).std()
        s = 0
        for L in looks:
            t = (lp - lp.shift(L)) / (sd * np.sqrt(L))
            s = s + (np.tanh(t) if kind == "tanh" else t.clip(-2, 2) / 2)
        s = s / len(looks)
        if smooth > 1:
            s = s.ewm(span=smooth).mean()
        s = s * (TV / (r.ewm(span=volwin).std() * np.sqrt(252))).clip(upper=3)
        e = e + w * s
    return (e - e["2018":].mean()) / e["2018":].std()


def cta(D):
    """D: 날짜 인덱스, SPX·NDX·RUT 종가 칸 → 일별 표"""
    px = D[list(WEIGHTS)].dropna()
    sig = CAL_K * (0.8 * _trend(px, (40, 80, 160), "lin", 20, 60) + 0.2 * _trend(px, (20, 40, 60), "tanh", 1, 40))
    s = px["SPX"]
    on = pd.DataFrame({n: s > s.shift(n) for n in (21, 63, 100)})
    return pd.DataFrame({"CTA σ": sig, "CTA σ 5일 변화": sig.diff(5),
                         "추세 신호 매수 수": on.sum(axis=1)}).dropna()
