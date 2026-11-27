"""시험용(의장 11/27 19:54·19:59, 나중에 지움)
1) 맥클렐런 오실레이터를 우리 유니버스로: 날마다 오른 종목 수(A)·내린 종목 수(D)로 비율 조정 순상승
   RANA = (A − D) ÷ (A + D) × 1000, 오실레이터 = RANA의 19일 지수이동평균 − 39일 지수이동평균
   (McClellan, 비율 조정판 — 원래는 뉴욕거래소·나스닥 전체 종목, 여기는 유니버스 종목만)
2) 나스닥100 ÷ S&P500 동일가중(RSP) 비율의 앵커 VWAP(고정 시작일부터 거래량 가중 평균). 사진의 주황선.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_mi as M  # noqa: E402


def mcclellan(P, cols):
    X = P[cols].astype(float)
    X = X[X.notna().sum(axis=1) >= len(cols) * 0.5]  # 그 시장이 열린 날만
    ch = X.diff()
    a, d = (ch > 0).sum(axis=1), (ch < 0).sum(axis=1)
    rana = ((a - d) / (a + d).where(a + d > 0) * 1000).dropna()
    return rana.ewm(span=19, adjust=False).mean() - rana.ewm(span=39, adjust=False).mean()


def avwap(px, vol, start):
    w, v = px[start:], vol.reindex(px[start:].index).fillna(0)
    return (w * v).cumsum() / v.cumsum()


def reverse(px, spx, s, low_side=True):
    rows = {}
    for ep, (days, ld, low) in M.zones(px, spx).items():
        v = s.reindex(days).dropna()
        rows[ep] = (round(v.min(), 1), round(v.max(), 1)) if len(v) else None
    return rows
