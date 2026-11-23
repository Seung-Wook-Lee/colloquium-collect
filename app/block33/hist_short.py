"""블록점수이력용 B22 미국 공매도 칸 과거 값 (11/24 의장 "공매도와 수급 DATA가 없다고?").
features.py는 오늘 공매도.csv(야후, FINRA 기준)만 읽어 과거 주에는 같은 값이 들어갔다(그래서 비웠음).
여기서는 1_data/장기/공매도_미국_이력.csv.gz(FINRA 결제일별)에서 그 주에 공표돼 있던 값(결제일 + 10일 ≤ 그 주)을 쓴다.
  short_pf = 공매도주식 ÷ 그 주 발행주식수(SEC 공시 주식수, hist_fund) × 100  — 야후는 유통주식 대비라 조금 낮게 나올 수 있음(발행주식 ≥ 유통주식)
  short_chg = 약 한 달 전(두 결제일 앞) 대비 변화(%) — 야후 '전월 대비'와 같은 간격
쓰는 곳: backtest._one → apply(f, t, d)"""
import os

import numpy as np
import pandas as pd

import hist_fund as HF

VARS = {'short_pf', 'short_chg'}
_S = None


def _load(d):
    p = f'{d}/장기/공매도_미국_이력.csv.gz'
    if not os.path.exists(p):
        return None
    S = pd.read_csv(p)
    S['결제일'] = pd.to_datetime(S['결제일'], errors='coerce'); S['공매도주식'] = pd.to_numeric(S['공매도주식'], errors='coerce')
    S = S.dropna(subset=['결제일', '공매도주식']).sort_values(['ticker', '결제일'])
    S['chg'] = S.groupby('ticker')['공매도주식'].transform(lambda x: (x / x.shift(2) - 1) * 100)
    S['공표'] = S['결제일'] + pd.Timedelta(days=10)
    return S


def apply(f, t, d):
    global _S
    if _S is None:
        _S = _load(d)
        if _S is None: _S = False
    if _S is False:
        return f
    t = pd.Timestamp(t); f = f.copy()
    x = _S[(_S['공표'] <= t) & (_S['공표'] >= t - pd.Timedelta(days=45))].groupby('ticker').tail(1).set_index('ticker')
    key = f['ticker'].astype(str).str.upper()
    sh = pd.Series(dtype=float)
    if HF._EV is not None and HF._EV[0] is not None:
        E = HF._EV[0]
        sh = E[(E['이용일'] <= t) & (E['이용일'] >= t - pd.Timedelta(days=200))].drop_duplicates('ticker', keep='last').set_index('ticker')['sh']
    f['short_pf'] = (key.map(x['공매도주식']) / key.map(sh) * 100).astype(float).values
    f['short_chg'] = key.map(x['chg']).astype(float).values
    return f
