"""수급분석센터 공용 계산 (한국·미국은 kr/·us/ 에서 따로 쓴다)"""
import numpy as np
import pandas as pd


def volume_surge(v):
    """거래량 급증 = 마지막 날 거래량 ÷ 그 앞 20일 평균 (Gervais·Kaniel·Mingelgrin, 2001)"""
    v = v.dropna()
    if len(v) < 21:
        return np.nan
    m = v.iloc[-21:-1].mean()
    return v.iloc[-1] / m if m else np.nan


def etf_units(E, code, days=20):
    """ETF 상장좌수 최근 days 수집일 증감 % (가격10년_ETF좌수일별)"""
    x = E[E["코드"].astype(str) == str(code)].sort_values("수집일")
    x = x.dropna(subset=["상장좌수"]).drop_duplicates("수집일", keep="last")
    if len(x) < 2:
        return np.nan
    a, b = x["상장좌수"].iloc[max(0, len(x) - 1 - days)], x["상장좌수"].iloc[-1]
    return (b / a - 1) * 100 if a else np.nan
